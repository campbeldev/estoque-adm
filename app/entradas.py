"""Entradas de estoque (compra, devolução etc.) — admin e operador.

Cada item registrado entra agrupado na sua Nota (número + série +
fornecedor): itens consecutivos da mesma nota se agrupam sozinhos, e o
formulário pré-preenche os dados da última nota digitada (sessão).

O campo de leitura aceita código OU nome do produto; quando o
nome casar com vários itens, o formulário volta com botões para escolher
o item correto (sem perder os demais campos digitados).
"""
from datetime import date, datetime

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import db
from .auth import login_required
from .models import (
    Item,
    Movimentacao,
    Nota,
    UNIDADES_EXIBICAO,
    opcoes_autocomplete,
    resolver_item,
    valores_unicos,
)
from .moeda import formatar_moeda, parse_valor_centavos

bp = Blueprint("entradas", __name__, url_prefix="/entradas")


@bp.route("/", methods=["GET", "POST"])
@login_required
def nova():
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome).all()
    recentes = (
        Movimentacao.query.filter_by(tipo="entrada")
        .order_by(Movimentacao.data.desc())
        .limit(20)
        .all()
    )

    # Valores do formulário (preservados quando a página volta com erro)
    form_data = {
        "codigo": request.form.get("codigo", "").strip(),
        "item_id": request.form.get("item_id", type=int) or "",
        "quantidade": request.form.get("quantidade", type=int) or "",
        "valor_unitario": request.form.get("valor_unitario", "").strip(),
        "fornecedor": request.form.get("fornecedor", "").strip(),
        "numero_nota": request.form.get("numero_nota", "").strip(),
        "serie": request.form.get("serie", "").strip(),
        "validade": request.form.get("validade", "").strip(),
        "data": request.form.get("data", "").strip(),
    }
    # Pré-preenche com a última nota registrada — só no GET: no re-render
    # de erro, o que o usuário digitou tem prioridade.
    if request.method == "GET":
        ultima = session.get("ultima_nota")
        if ultima:
            for campo in ("numero_nota", "serie", "fornecedor"):
                if not form_data[campo]:
                    form_data[campo] = ultima.get(campo, "")
    alternativas = []

    # Fornecedores conhecidos: notas novas + legado das movimentações
    fornecedores = sorted(
        set(valores_unicos(Nota.fornecedor))
        | set(valores_unicos(Movimentacao.fornecedor))
    )

    def _render(erro=None, categoria="danger"):
        if erro:
            flash(erro, categoria)
        return render_template(
            "entradas/form.html",
            itens=itens,
            recentes=recentes,
            form_data=form_data,
            alternativas=alternativas,
            autocomplete=opcoes_autocomplete(),
            sugestoes_fornecedores=fornecedores,
            sugestoes_notas_numeros=valores_unicos(Nota.numero),
            sugestoes_notas_series=valores_unicos(Nota.serie),
        )

    if request.method == "POST":
        item = None
        # 1º: item já escolhido (botão de alternativa ou seletor);
        # senão, resolve o texto digitado (código ou nome)
        if form_data["item_id"]:
            item = db.session.get(Item, form_data["item_id"])
        elif form_data["codigo"]:
            item, alternativas = resolver_item(form_data["codigo"])
            alternativas = [a for a in alternativas if a.ativo]
            if item is None and alternativas:
                return _render(
                    f"Vários itens correspondem a \"{form_data['codigo']}\" — "
                    "clique no item correto para registrar.",
                    "warning",
                )

        if item is None:
            return _render(
                "Selecione o item, ou digite o código/nome do produto."
            )
        if not item.ativo:
            return _render("Item desativado — reative antes de dar entrada.")

        quantidade = form_data["quantidade"]
        if not quantidade or quantidade <= 0:
            return _render("A quantidade deve ser maior que zero.")
        if not form_data["fornecedor"]:
            return _render("Informe o fornecedor.")
        if not form_data["numero_nota"]:
            return _render("Informe o número da nota.")
        if not form_data["serie"]:
            return _render("Informe a série da nota.")

        valor_unitario = parse_valor_centavos(form_data["valor_unitario"])
        if valor_unitario is None or valor_unitario <= 0:
            return _render("Valor unitário inválido — use o formato 12,50.")

        # Validade do lote que está chegando (opcional — nem todo material
        # de escritório/limpeza/alojamento tem vencimento).
        validade_str = form_data["validade"]
        if validade_str:
            try:
                validade = date.fromisoformat(validade_str)
            except ValueError:
                return _render("Data de validade inválida.")
        else:
            validade = None

        if form_data["data"]:
            try:
                data_entrada = datetime.combine(
                    datetime.fromisoformat(form_data["data"]).date(),
                    datetime.now().time(),
                )
            except ValueError:
                return _render("Data inválida.")
        else:
            data_entrada = datetime.now()

        # Nota: get-or-create por (numero, serie) — itens da mesma nota se
        # agrupam; mesmo número com outro fornecedor é erro (evita
        # duplicata silenciosa).
        numero, serie, fornecedor = (
            form_data["numero_nota"],
            form_data["serie"],
            form_data["fornecedor"],
        )
        nota = Nota.query.filter_by(numero=numero, serie=serie).first()
        if nota is not None and (
            nota.fornecedor.strip().lower() != fornecedor.strip().lower()
        ):
            return _render(
                f"Já existe a nota {numero} (série {serie}) do fornecedor "
                f"{nota.fornecedor} — confira os dados antes de continuar."
            )
        if nota is None:
            nota = Nota(
                numero=numero,
                serie=serie,
                fornecedor=fornecedor,
                data=data_entrada,
                usuario_id=g.usuario.id,
            )
            db.session.add(nota)
            db.session.flush()  # id para o movimento, sem commit

        db.session.add(
            Movimentacao(
                tipo="entrada",
                quantidade=quantidade,
                item_id=item.id,
                usuario_id=g.usuario.id,
                nota_id=nota.id,
                valor_unitario_cents=valor_unitario,
                validade=validade,
                fornecedor=fornecedor,
                nota_fiscal=numero,
                data=data_entrada,
            )
        )
        db.session.commit()
        session["ultima_nota"] = {
            "numero_nota": numero,
            "serie": serie,
            "fornecedor": fornecedor,
        }
        detalhe_validade = (
            f" — val. {validade.strftime('%d/%m/%Y')}" if validade else ""
        )
        flash(
            f"Entrada registrada: {item.nome} — "
            f"{quantidade} {UNIDADES_EXIBICAO[item.unidade]} × "
            f"{formatar_moeda(valor_unitario)} = "
            f"{formatar_moeda(quantidade * valor_unitario)} "
            f"(nota {numero}/{serie}){detalhe_validade}.",
            "success",
        )
        return redirect(url_for("entradas.nova"))

    return _render()
