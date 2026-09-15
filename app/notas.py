"""Notas de entrada — listagem e detalhe (admin).

As notas agrupam as movimentações de entrada: cada nota tem número,
série e fornecedor, e o total é a soma de quantidade × valor unitário
dos seus itens.
"""
from datetime import datetime

from flask import Blueprint, Response, abort, render_template, request
from sqlalchemy import func

from . import db
from .auth import admin_required
from .models import Movimentacao, Nota
from .moeda import formatar_moeda
from .services.csv_export import montar_csv

bp = Blueprint("notas", __name__, url_prefix="/notas")

LIMITE_REGISTROS = 1000

CABECALHOS = ["Data", "Nota", "Serie", "Fornecedor", "Itens", "Total", "Usuario"]


def _totais_por_nota():
    """{nota_id: {"itens": n, "total": centavos}} numa query só."""
    linhas = (
        db.session.query(
            Movimentacao.nota_id,
            func.count(Movimentacao.id),
            func.sum(
                Movimentacao.quantidade
                * func.coalesce(Movimentacao.valor_unitario_cents, 0)
            ),
        )
        .filter(Movimentacao.nota_id.isnot(None))
        .group_by(Movimentacao.nota_id)
        .all()
    )
    return {
        nota_id: {"itens": itens, "total": total or 0}
        for nota_id, itens, total in linhas
    }


@bp.route("/")
@admin_required
def listar():
    notas = (
        Nota.query.order_by(Nota.data.desc(), Nota.id.desc())
        .limit(LIMITE_REGISTROS)
        .all()
    )
    totais = _totais_por_nota()

    if request.args.get("exportar"):
        linhas = [
            [
                nota.data.strftime("%d/%m/%Y %H:%M"),
                nota.numero,
                nota.serie,
                nota.fornecedor,
                totais.get(nota.id, {}).get("itens", 0),
                formatar_moeda(totais.get(nota.id, {}).get("total", 0)),
                nota.usuario.nome,
            ]
            for nota in notas
        ]
        csv_texto = montar_csv(CABECALHOS, linhas)
        return Response(
            csv_texto,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=notas_{datetime.now():%Y%m%d}.csv"
                )
            },
        )

    return render_template("notas/listar.html", notas=notas, totais=totais)


@bp.route("/<int:nota_id>")
@admin_required
def detalhe(nota_id):
    nota = db.session.get(Nota, nota_id)
    if nota is None:
        abort(404)
    movs = (
        Movimentacao.query.filter_by(nota_id=nota.id)
        .order_by(Movimentacao.id)
        .all()
    )
    total = sum(m.quantidade * (m.valor_unitario_cents or 0) for m in movs)
    return render_template("notas/detalhe.html", nota=nota, movs=movs, total=total)
