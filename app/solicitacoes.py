"""Registro e consulta das solicitações de materiais."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import db
from .auth import login_required
from .models import Item, ItemSolicitacao, Obra, Setor, Solicitacao, valores_unicos

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


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome).all()
    obras = Obra.query.filter_by(ativo=True).order_by(Obra.nome).all()
    setores = Setor.query.filter_by(ativo=True).order_by(Setor.nome).all()
    solicitantes = valores_unicos(Solicitacao.solicitante)

    if request.method == "POST":
        solicitante = request.form.get("solicitante", "").strip()
        obra_id = request.form.get("obra_id", type=int)
        setor_id = request.form.get("setor_id", type=int)
        item_id = request.form.get("item_id", type=int)
        quantidade = request.form.get("quantidade", type=int)

        obra = db.session.get(Obra, obra_id) if obra_id else None
        setor = db.session.get(Setor, setor_id) if setor_id else None
        item = db.session.get(Item, item_id) if item_id else None

        if not solicitante:
            flash("Informe quem fez a solicitação.", "danger")
        elif obra is None or not obra.ativo:
            flash("Selecione uma obra ativa.", "danger")
        elif setor is None or not setor.ativo:
            flash("Selecione um setor ativo.", "danger")
        elif item is None or not item.ativo:
            flash("Selecione um item ativo.", "danger")
        elif quantidade is None or quantidade <= 0:
            flash("A quantidade deve ser maior que zero.", "danger")
        else:
            solicitacao = Solicitacao(
                solicitante=solicitante,
                obra_id=obra.id,
                setor_id=setor.id,
                usuario_id=g.usuario.id,
            )
            db.session.add(solicitacao)
            db.session.flush()

            db.session.add(
                ItemSolicitacao(
                    solicitacao_id=solicitacao.id,
                    item_id=item.id,
                    quantidade=quantidade,
                )
            )
            db.session.commit()

            flash("Solicitação registrada com sucesso.", "success")
            return redirect(url_for("solicitacoes.listar"))

    return render_template(
        "solicitacoes/form.html",
        itens=itens,
        obras=obras,
        setores=setores,
        solicitantes=solicitantes,
        aba="solicitacoes",
    )