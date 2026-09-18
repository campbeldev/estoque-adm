"""Visão do estoque atual e ajustes de balanço."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import db
from .auth import admin_required, login_required
from .models import (
    Item,
    Movimentacao,
    opcoes_autocomplete,
    saldos_por_item,
    valores_unicos,
)

bp = Blueprint("estoque", __name__, url_prefix="/estoque")

@bp.route("/")
@login_required
def index():
    busca = request.args.get("busca", "").strip()
    query = Item.query
    if busca:
        padrao = f"%{busca}%"
        query = query.filter(
            db.or_(
                Item.nome.ilike(padrao),
                Item.codigo.ilike(padrao),
            )
        )
    itens = query.order_by(Item.nome).all()
    saldos = saldos_por_item()
    return render_template(
        "estoque/index.html",
        itens=itens,
        saldos=saldos,
        busca=busca,
        autocomplete=opcoes_autocomplete(),
    )


@bp.route("/ajuste", methods=["GET", "POST"])
@admin_required
def ajuste():
    itens = Item.query.filter_by(ativo=True).order_by(Item.nome).all()
    saldos = saldos_por_item()
    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        quantidade = request.form.get("quantidade", type=int)
        direcao = request.form.get("direcao", "")
        motivo = request.form.get("motivo", "").strip()

        item = db.session.get(Item, item_id)
        if item is None:
            flash("Selecione um item válido.", "danger")
        elif quantidade is None or quantidade <= 0:
            flash("A quantidade deve ser maior que zero.", "danger")
        elif direcao not in ("adicionar", "remover"):
            flash("Selecione a direção do ajuste.", "danger")
        elif not motivo:
            flash("Informe o motivo do ajuste (fica registrado no histórico).", "danger")
        elif direcao == "remover" and saldos.get(item_id, 0) < quantidade:
            flash(
                f"Saldo insuficiente para remover — saldo atual: "
                f"{saldos.get(item_id, 0)}.",
                "danger",
            )
        else:
            db.session.add(
                Movimentacao(
                    tipo="ajuste",
                    quantidade=quantidade if direcao == "adicionar" else -quantidade,
                    item_id=item.id,
                    usuario_id=g.usuario.id,
                    observacao=motivo,
                )
            )
            db.session.commit()
            flash(f"Ajuste registrado para {item.nome}.", "success")
            return redirect(url_for("estoque.index"))

    return render_template(
        "estoque/ajuste.html",
        itens=itens,
        saldos=saldos,
        sugestoes_motivos=valores_unicos(Movimentacao.observacao),
    )
