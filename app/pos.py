"""Linha de frente (caixa): saídas via leitor de código.

O leitor USB funciona como um teclado: digita o código e envia Enter.
Cada leitura vira um POST e o redirect (PRG) devolve a tela com o campo
de código em foco (autofocus) — sem JavaScript, sem perder leitura.
O pacote (grupo de itens aguardando confirmação) vive na sessão Flask:
sobrevive a atualizações e a saídas inacabadas, e é limpo ao confirmar
ou ao sair do sistema.

Destino: toda saída indica obra + setor. Se a obra não for a sede, exige
também o entregador e cria uma Remessa (evento "despachada") para o
rastreio. Saída para a sede não gera remessa (operamos aqui).
"""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from . import db
from .auth import login_required
from .models import (
    Entregador,
    EventoRemessa,
    Item,
    Movimentacao,
    Obra,
    Remessa,
    Setor,
    custos_medios_por_item,
    opcoes_autocomplete,
    resolver_item,
    saldos_por_item,
)

bp = Blueprint("pos", __name__, url_prefix="/pos")


def _pacote():
    # a chave "carrinho" na sessão é herdada de antes do nome "pacote";
    # renomeá-la apagaria pacotes em andamento nos navegadores
    return session.get("carrinho", {})  # {str(item_id): quantidade}


def _opcoes_destino():
    obras = Obra.query.filter_by(ativo=True).order_by(Obra.nome).all()
    setores = Setor.query.order_by(Setor.nome).all()
    entregadores = (
        Entregador.query.filter_by(ativo=True).order_by(Entregador.nome).all()
    )
    return obras, setores, entregadores


def _linhas_do_pacote(pacote):
    if not pacote:
        return []
    ids = [int(chave) for chave in pacote]
    itens = {item.id: item for item in Item.query.filter(Item.id.in_(ids)).all()}
    saldos = saldos_por_item(ids)
    custos = custos_medios_por_item(ids)
    linhas = []
    for chave, quantidade in pacote.items():
        item = itens.get(int(chave))
        if item is None:
            continue  # item foi excluído do cadastro; some do pacote
        linhas.append(
            {
                "item": item,
                "qtd": quantidade,
                "saldo": saldos.get(item.id, 0),
                "custo": custos.get(item.id),
            }
        )
    linhas.sort(key=lambda linha: linha["item"].nome)
    return linhas


@bp.route("/")
@login_required
def index():
    linhas = _linhas_do_pacote(_pacote())
    obras, setores, entregadores = _opcoes_destino()
    buscar = request.args.get("buscar", "").strip()
    sugestoes = []
    if buscar:
        _, sugestoes = resolver_item(buscar)
        sugestoes = [s for s in sugestoes if s.ativo]

    # Destino pré-preenchido do último lançamento (ou da URL pós-erro).
    obra_id = request.args.get("obra_id", type=int)
    if obra_id is None:
        obra_id = session.get("pos_ultima_obra")
    setor_id = request.args.get("setor_id", type=int)
    if setor_id is None:
        setor_id = session.get("pos_ultimo_setor")
    entregador_id = request.args.get("entregador_id", type=int)
    if entregador_id is None:
        entregador_id = session.get("pos_ultimo_entregador")

    return render_template(
        "pos/index.html",
        linhas=linhas,
        total_estimado=sum(
            linha["qtd"] * (linha["custo"] or 0) for linha in linhas
        ),
        obras=obras,
        setores=setores,
        entregadores=entregadores,
        modo_rapido=session.get("pos_modo_rapido", False),
        obra_id=obra_id,
        setor_id=setor_id,
        entregador_id=entregador_id,
        sugestoes=sugestoes,
        autocomplete=opcoes_autocomplete(),
    )


@bp.route("/adicionar", methods=["POST"])
@login_required
def adicionar():
    codigo = request.form.get("codigo", "").strip()
    modo_rapido = request.form.get("modo_rapido") == "on"
    session["pos_modo_rapido"] = modo_rapido

    item, alternativas = resolver_item(codigo)
    if item is None:
        if alternativas:
            flash(
                f"Vários itens correspondem a \"{codigo}\" — escolha um abaixo "
                "ou digite o código exato.",
                "warning",
            )
            return redirect(url_for("pos.index", buscar=codigo))
        flash(f"Não encontrado: {codigo or '(vazio)'}.", "danger")
        return redirect(url_for("pos.index"))
    if not item.ativo:
        flash(f"Item desativado: {item.nome}.", "danger")
        return redirect(url_for("pos.index"))

    if modo_rapido:
        return _saida_direta(item)

    pacote = _pacote()
    chave = str(item.id)
    pacote[chave] = pacote.get(chave, 0) + 1
    session["carrinho"] = pacote
    flash(f"Adicionado ao pacote: {item.nome} (×{pacote[chave]}).", "success")
    return redirect(url_for("pos.index"))


def _destino_do_form():
    """Resolve obra + setor (+ entregador, se a obra não for a sede).

    Retorna (obra, setor, entregador, erro) — preenche OU os três destinos,
    OU a mensagem de erro.
    """
    obra_id = request.form.get("obra_id", type=int)
    setor_id = request.form.get("setor_id", type=int)
    obra = db.session.get(Obra, obra_id) if obra_id else None
    if obra is None:
        return None, None, None, "Selecione a obra de destino."
    setor = db.session.get(Setor, setor_id) if setor_id else None
    if setor is None:
        return None, None, None, "Selecione o setor de destino."
    entregador = None
    if not obra.eh_sede:
        entregador_id = request.form.get("entregador_id", type=int)
        entregador = (
            db.session.get(Entregador, entregador_id) if entregador_id else None
        )
        if entregador is None:
            return None, None, None, (
                "A obra não é a sede — informe quem transporta (entregador)."
            )
    return obra, setor, entregador, None


def _criar_remessa(obra, setor, entregador):
    """Cria a Remessa + evento "despachada" (o pontapé do rastreio)."""
    remessa = Remessa(
        codigo="",  # placeholder — o flush libera o id
        obra_id=obra.id,
        setor_id=setor.id,
        transportador_id=entregador.id,
    )
    db.session.add(remessa)
    db.session.flush()
    remessa.codigo = f"RM{remessa.id:06d}"
    db.session.add(
        EventoRemessa(
            remessa_id=remessa.id,
            tipo="despachada",
            usuario_id=g.usuario.id,
        )
    )
    return remessa


def _voltar_com_contexto(erro):
    """Flash do erro + volta para o caixa preservando o que foi digitado."""
    flash(erro, "danger")
    return redirect(
        url_for(
            "pos.index",
            obra_id=request.form.get("obra_id", type=int),
            setor_id=request.form.get("setor_id", type=int),
            entregador_id=request.form.get("entregador_id", type=int),
        )
    )


def _saida_direta(item):
    """Modo rápido: cada leitura baixa 1 unidade na hora."""
    obra, setor, entregador, erro = _destino_do_form()
    if erro:
        return _voltar_com_contexto(erro)
    if saldos_por_item([item.id]).get(item.id, 0) < 1:
        flash(f"Sem saldo para {item.nome}.", "danger")
        return redirect(url_for("pos.index"))

    remessa = None
    if not obra.eh_sede:
        remessa = _criar_remessa(obra, setor, entregador)

    # A saída guarda o custo médio do item naquele momento: é o que dá
    # valor aos relatórios de retiradas (a entrada é a única com preço).
    custo = custos_medios_por_item([item.id]).get(item.id)
    db.session.add(
        Movimentacao(
            tipo="saida",
            quantidade=1,
            item_id=item.id,
            usuario_id=g.usuario.id,
            obra_id=obra.id,
            setor_id=setor.id,
            remessa_id=remessa.id if remessa else None,
            valor_unitario_cents=custo,
        )
    )
    db.session.commit()
    # Lembra o destino para agilizar as próximas leituras
    session["pos_ultima_obra"] = obra.id
    session["pos_ultimo_setor"] = setor.id
    if entregador:
        session["pos_ultimo_entregador"] = entregador.id
    flash(f"Saída registrada: {item.nome} (1 unidade).", "success")
    return redirect(url_for("pos.index"))


@bp.route("/remover/<int:item_id>", methods=["POST"])
@login_required
def remover(item_id):
    pacote = _pacote()
    pacote.pop(str(item_id), None)
    session["carrinho"] = pacote
    return redirect(url_for("pos.index"))


@bp.route("/atualizar", methods=["POST"])
@login_required
def atualizar():
    pacote = _pacote()
    novo = {}
    for chave, quantidade_antiga in pacote.items():
        digitada = request.form.get(f"qtd_{chave}", type=int)
        if digitada is not None and digitada >= 0:
            if digitada > 0:
                novo[chave] = digitada
            # quantidade 0 remove a linha do pacote
        else:
            novo[chave] = quantidade_antiga  # entrada inválida: mantém
    session["carrinho"] = novo
    if not novo:
        flash("Pacote esvaziado.", "info")
    return redirect(url_for("pos.index"))


@bp.route("/finalizar", methods=["POST"])
@login_required
def finalizar():
    session["pos_modo_rapido"] = request.form.get("modo_rapido") == "on"
    pacote = _pacote()

    if not pacote:
        flash("Pacote vazio.", "warning")
        return redirect(url_for("pos.index"))
    obra, setor, entregador, erro = _destino_do_form()
    if erro:
        return _voltar_com_contexto(erro)

    ids = [int(chave) for chave in pacote]
    itens = {item.id: item for item in Item.query.filter(Item.id.in_(ids)).all()}
    # Descarta itens que deixaram de existir no cadastro
    pacote = {chave: qtd for chave, qtd in pacote.items() if int(chave) in itens}
    if not pacote:
        flash("Pacote vazio.", "warning")
        return redirect(url_for("pos.index"))

    saldos = saldos_por_item([int(chave) for chave in pacote])
    bloqueios = []
    for chave, quantidade in pacote.items():
        item = itens[int(chave)]
        if not item.ativo:
            bloqueios.append(f"{item.nome}: item desativado")
        elif quantidade > saldos.get(item.id, 0):
            bloqueios.append(
                f"{item.nome}: pedido {quantidade}, saldo {saldos.get(item.id, 0)}"
            )

    if bloqueios:
        for bloqueio in bloqueios:
            flash(f"Saldo insuficiente — {bloqueio}.", "danger")
        return redirect(url_for("pos.index"))  # pacote permanece intacto

    remessa = None
    if not obra.eh_sede:
        remessa = _criar_remessa(obra, setor, entregador)

    # Custo médio de cada item do pacote — gravado na saída para os
    # relatórios terem valor mesmo depois que novos preços chegarem.
    custos = custos_medios_por_item([int(chave) for chave in pacote])
    for chave, quantidade in pacote.items():
        db.session.add(
            Movimentacao(
                tipo="saida",
                quantidade=quantidade,
                item_id=int(chave),
                usuario_id=g.usuario.id,
                obra_id=obra.id,
                setor_id=setor.id,
                remessa_id=remessa.id if remessa else None,
                valor_unitario_cents=custos.get(int(chave)),
            )
        )
    db.session.commit()
    total_itens = len(pacote)
    session["carrinho"] = {}
    session["pos_ultima_obra"] = obra.id
    session["pos_ultimo_setor"] = setor.id
    if entregador:
        session["pos_ultimo_entregador"] = entregador.id
    flash(
        f"Saída registrada — {total_itens} "
        f"{'item baixado' if total_itens == 1 else 'itens baixados'} do estoque.",
        "success",
    )
    return redirect(url_for("pos.index"))
