"""Registro e consulta das solicitações de materiais."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import db
from .auth import login_required
from .models import Entregador, EventoRemessa, Item, ItemSolicitacao, Movimentacao, Obra, Remessa, Setor, Solicitacao, custos_medios_por_item, saldos_por_item, valores_unicos

bp = Blueprint("solicitacoes", __name__, url_prefix="/solicitacoes")


@bp.route("/")
@login_required
def listar():
    solicitacoes = (
        Solicitacao.query
        .order_by(Solicitacao.data_criacao.desc())
        .all()
    )
    return render_template(
        "solicitacoes/listar.html",
        solicitacoes=solicitacoes,
        aba="solicitacoes",
    )


@bp.route("/<int:solicitacao_id>")
@login_required
def detalhe(solicitacao_id):
    solicitacao = db.get_or_404(Solicitacao, solicitacao_id)

    return render_template(
        "solicitacoes/detalhe.html",
        solicitacao=solicitacao,
        aba="solicitacoes",
    )
@bp.route(
    "/<int:solicitacao_id>/emitir-saida",
    methods=["GET", "POST"],
)
@login_required
def emitir_saida(solicitacao_id):
    solicitacao = db.get_or_404(Solicitacao, solicitacao_id)

    item_ids = [item.item_id for item in solicitacao.itens]
    saldos = saldos_por_item(item_ids)
    entregadores = (
        Entregador.query
        .filter_by(ativo=True)
        .order_by(Entregador.nome)
        .all()
    )
    if request.method == "POST":
        ids_recebidos = request.form.getlist(
            "item_solicitacao_id", type=int
        )
        quantidades = request.form.getlist("quantidade", type=int)

        if len(ids_recebidos) != len(quantidades):
            flash("Dados dos itens inválidos.", "danger")
            return redirect(
                url_for(
                    "solicitacoes.emitir_saida",
                    solicitacao_id=solicitacao.id,
                )
            )

        itens_por_id = {
            item_solicitado.id: item_solicitado
            for item_solicitado in solicitacao.itens
        }

        linhas = []
        erro = None

        for item_solicitacao_id, quantidade in zip(
            ids_recebidos, quantidades
        ):
            item_solicitado = itens_por_id.get(item_solicitacao_id)

            if item_solicitado is None:
                erro = "Item inválido para esta solicitação."
                break

            if quantidade is None or quantidade < 0:
                erro = "A quantidade não pode ser negativa."
                break

            if quantidade > item_solicitado.quantidade_restante:
                erro = (
                    f"A quantidade de {item_solicitado.item.nome} "
                    "excede o restante solicitado."
                )
                break

            saldo = saldos.get(item_solicitado.item_id, 0)
            if quantidade > saldo:
                erro = f"Estoque insuficiente para {item_solicitado.item.nome}."
                break

            if quantidade > 0:
                linhas.append((item_solicitado, quantidade))

        if erro:
            flash(erro, "danger")
        elif not linhas:
            flash("Informe pelo menos uma quantidade.", "warning")
        else:
            entregador = None

            if not solicitacao.obra.eh_sede:
                entregador_id = request.form.get("entregador_id", type=int)
                entregador = (
                    db.session.get(Entregador, entregador_id)
                    if entregador_id
                    else None
                )

                if entregador is None or not entregador.ativo:
                    flash(
                        "Selecione um entregador ativo para esta obra.",
                        "danger",
                    )
                    return redirect(
                        url_for(
                            "solicitacoes.emitir_saida",
                            solicitacao_id=solicitacao.id,
                        )
                    )

            remessa = None

            if not solicitacao.obra.eh_sede:
                remessa = Remessa(
                    codigo="",
                    obra_id=solicitacao.obra_id,
                    setor_id=solicitacao.setor_id,
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

            custos = custos_medios_por_item(
                [item_solicitado.item_id for item_solicitado, _ in linhas]
            )

            for item_solicitado, quantidade in linhas:
                db.session.add(
                    Movimentacao(
                        tipo="saida",
                        quantidade=quantidade,
                        item_id=item_solicitado.item_id,
                        usuario_id=g.usuario.id,
                        obra_id=solicitacao.obra_id,
                        setor_id=solicitacao.setor_id,
                        remessa_id=remessa.id if remessa else None,
                        item_solicitacao_id=item_solicitado.id,
                        valor_unitario_cents=custos.get(
                            item_solicitado.item_id
                        ),
                    )
                )

            db.session.commit()

            flash("Saída registrada com sucesso.", "success")
            return redirect(
                url_for(
                    "solicitacoes.detalhe",
                    solicitacao_id=solicitacao.id,
                )
            )
        

    return render_template(
        "solicitacoes/emitir_saida.html",
        solicitacao=solicitacao,
        saldos=saldos,
        entregadores=entregadores,
        aba="solicitacoes",
    )

@bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome).all()
    obras = Obra.query.filter_by(ativo=True).order_by(Obra.nome).all()
    setores = Setor.query.order_by(Setor.nome).all()
    solicitantes = valores_unicos(Solicitacao.solicitante)

    if request.method == "POST":
        solicitante = request.form.get("solicitante", "").strip()
        obra_id = request.form.get("obra_id", type=int)
        setor_id = request.form.get("setor_id", type=int)
        item_ids = request.form.getlist("item_id", type=int)
        quantidades = request.form.getlist("quantidade", type=int)

        obra = db.session.get(Obra, obra_id) if obra_id else None
        setor = db.session.get(Setor, setor_id) if setor_id else None

        if not solicitante:
            flash("Informe quem fez a solicitação.", "danger")
        elif obra is None or not obra.ativo:
            flash("Selecione uma obra ativa.", "danger")
        elif setor is None:
            flash("Selecione um setor válido.", "danger")
        elif not item_ids or len(item_ids) != len(quantidades):
            flash("Informe pelo menos um item com quantidade válida.", "danger")
        else:
            linhas = []
            itens_usados = set()
            erro = None

            for numero_linha, (item_id, quantidade) in enumerate(
                zip(item_ids, quantidades), start=1
            ):
                item = db.session.get(Item, item_id)

                if item is None or not item.ativo:
                    erro = f"Linha {numero_linha}: selecione um item ativo."
                    break
                if item.id in itens_usados:
                    erro = f"Linha {numero_linha}: o item {item.nome} foi repetido."
                    break
                if quantidade is None or quantidade <= 0:
                    erro = (
                        f"Linha {numero_linha}: a quantidade deve ser maior que zero."
                    )
                    break

                itens_usados.add(item.id)
                linhas.append((item, quantidade))

            if erro:
                flash(erro, "danger")
            else:
                solicitacao = Solicitacao(
                    solicitante=solicitante,
                    obra_id=obra.id,
                    setor_id=setor.id,
                    usuario_id=g.usuario.id,
                )
                db.session.add(solicitacao)
                db.session.flush()

                for item, quantidade in linhas:
                    db.session.add(
                        ItemSolicitacao(
                            solicitacao_id=solicitacao.id,
                            item_id=item.id,
                            quantidade=quantidade,
                        )
                    )

                db.session.commit()
                total = len(linhas)
                rotulo = "item" if total == 1 else "itens"
                flash(
                    f"Solicitação registrada com {total} {rotulo}.",
                    "success",
                )
                return redirect(url_for("solicitacoes.listar"))

    return render_template(
        "solicitacoes/form.html",
        itens=itens,
        obras=obras,
        setores=setores,
        solicitantes=solicitantes,
        aba="solicitacoes",
    )