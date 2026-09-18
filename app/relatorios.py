"""Relatórios: histórico de movimentações (exportável em CSV)."""
from datetime import date, datetime, time

from flask import Blueprint, Response, render_template, request

from . import db
from .auth import admin_required
from .models import (
    Item,
    Movimentacao,
    TIPOS_EXIBICAO,
    UNIDADES_EXIBICAO,
    opcoes_autocomplete,
)
from .moeda import formatar_moeda
from .services.csv_export import montar_csv

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

CABECALHOS = [
    "Data", "Tipo", "Item", "Quantidade", "Unidade", "Setor",
    "Obra", "Usuario", "Fornecedor", "Nota", "Observacao",
    "Valor Unitario", "Valor Total",
]

LIMITE_REGISTROS = 1000


def _aplicar_filtros(query):
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    tipo = request.args.get("tipo", "").strip()
    item_busca = request.args.get("item", "").strip()

    if data_inicio:
        try:
            query = query.filter(
                Movimentacao.data
                >= datetime.combine(date.fromisoformat(data_inicio), time.min)
            )
        except ValueError:
            pass  # data malformada: ignora o filtro
    if data_fim:
        try:
            query = query.filter(
                Movimentacao.data
                <= datetime.combine(date.fromisoformat(data_fim), time.max)
            )
        except ValueError:
            pass
    if tipo in TIPOS_EXIBICAO:
        query = query.filter(Movimentacao.tipo == tipo)
    if item_busca:
        padrao = f"%{item_busca}%"
        query = query.join(Movimentacao.item).filter(
            db.or_(
                Item.nome.ilike(padrao),
                Item.codigo.ilike(padrao),
            )
        )
    return query


def _linha_csv(mov):
    tem_valor = mov.valor_unitario_cents is not None
    return [
        mov.data.strftime("%d/%m/%Y %H:%M"),
        TIPOS_EXIBICAO[mov.tipo],
        mov.item.nome,
        mov.quantidade,
        UNIDADES_EXIBICAO[mov.item.unidade],
        mov.setor.nome if mov.setor else "",
        mov.obra.nome if mov.obra else "",
        mov.usuario.nome,
        mov.fornecedor or "",
        mov.nota_rotulo,
        mov.observacao or "",
        formatar_moeda(mov.valor_unitario_cents) if tem_valor else "",
        formatar_moeda(mov.quantidade * mov.valor_unitario_cents)
        if tem_valor
        else "",
    ]


@bp.route("/movimentacoes")
@admin_required
def movimentacoes():
    query = _aplicar_filtros(Movimentacao.query)
    movs = (
        query.order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
        .limit(LIMITE_REGISTROS)
        .all()
    )

    if request.args.get("exportar"):
        csv_texto = montar_csv(CABECALHOS, [_linha_csv(mov) for mov in movs])
        return Response(
            csv_texto,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=movimentacoes_{datetime.now():%Y%m%d}.csv"
                )
            },
        )

    return render_template(
        "relatorios/movimentacoes.html",
        movimentacoes=movs,
        autocomplete=opcoes_autocomplete(),
    )
