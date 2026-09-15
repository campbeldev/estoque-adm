"""Relatórios: histórico de movimentações e relatório por funcionário."""
from datetime import date, datetime, time
from io import BytesIO

from flask import (
    Blueprint,
    Response,
    flash,
    render_template,
    request,
    send_file,
)

from . import db
from .auth import admin_required
from .models import (
    Funcionario,
    Item,
    Movimentacao,
    TIPOS_EXIBICAO,
    UNIDADES_EXIBICAO,
    nome_com_tamanho,
    opcoes_autocomplete,
    resolver_funcionario,
    sugestoes_funcionarios,
)
from .moeda import formatar_moeda
from .services.csv_export import montar_csv
from .services.relatorios_pdf import gerar_pdf_relatorio_funcionario

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

CABECALHOS = [
    "Data", "Tipo", "Item", "Quantidade", "Unidade", "Funcionario",
    "Obra", "Usuario", "Fornecedor", "Nota", "Observacao", "Validade",
    "Valor Unitario", "Valor Total",
]

CABECALHOS_FUNCIONARIO = [
    "Data", "Produto", "Quantidade", "Unidade", "Obra", "Usuario",
    "Observacao", "Valor Unitario", "Valor Total",
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
                nome_com_tamanho().ilike(padrao),  # "Camisa Azul P"
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
        mov.funcionario.nome if mov.funcionario else "",
        mov.obra.nome if mov.obra else "",
        mov.usuario.nome,
        mov.fornecedor or "",
        mov.nota_rotulo,
        mov.observacao or "",
        mov.validade.strftime("%d/%m/%Y") if mov.validade else "",
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


@bp.route("/por-funcionario")
@admin_required
def por_funcionario():
    """Retiradas (saídas) de um funcionário específico, com seus dados."""
    busca = request.args.get("funcionario", "").strip()
    funcionario_id = request.args.get("funcionario_id", type=int)

    funcionario = None
    if funcionario_id:
        funcionario = db.session.get(Funcionario, funcionario_id)
    elif busca:
        funcionario, alternativas = resolver_funcionario(busca)
        if funcionario is None and alternativas:
            flash(
                f"Vários funcionários correspondem a \"{busca}\" — escolha um "
                "no seletor abaixo.",
                "warning",
            )

    retiradas = []
    total_valor = 0
    if funcionario is not None:
        query = Movimentacao.query.filter_by(
            tipo="saida", funcionario_id=funcionario.id
        )
        query = _aplicar_filtros(query)
        retiradas = (
            query.order_by(Movimentacao.data.desc(), Movimentacao.id.desc())
            .limit(LIMITE_REGISTROS)
            .all()
        )
        total_valor = sum(
            m.quantidade * (m.valor_unitario_cents or 0) for m in retiradas
        )

        if request.args.get("exportar"):
            csv_texto = montar_csv(
                CABECALHOS_FUNCIONARIO,
                [_linha_csv_retirada(mov) for mov in retiradas],
            )
            return Response(
                csv_texto,
                mimetype="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=retiradas_{funcionario.matricula}"
                        f"_{datetime.now():%Y%m%d}.csv"
                    )
                },
            )

        if request.args.get("pdf"):
            pdf = gerar_pdf_relatorio_funcionario(
                funcionario,
                retiradas,
                request.args.get("data_inicio", "").strip(),
                request.args.get("data_fim", "").strip(),
                total_valor,
            )
            return send_file(
                BytesIO(pdf),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=(
                    f"relatorio_{funcionario.matricula}_{datetime.now():%Y%m%d}.pdf"
                ),
            )

    return render_template(
        "relatorios/por_funcionario.html",
        busca=busca,
        funcionario=funcionario,
        retiradas=retiradas,
        total_unidades=sum(mov.quantidade for mov in retiradas),
        total_valor=total_valor,
        funcionarios=Funcionario.query.order_by(Funcionario.nome).all(),
        sugestoes_busca=sugestoes_funcionarios(),
    )


def _linha_csv_retirada(mov):
    tem_valor = mov.valor_unitario_cents is not None
    return [
        mov.data.strftime("%d/%m/%Y %H:%M"),
        mov.item.nome,
        mov.quantidade,
        UNIDADES_EXIBICAO[mov.item.unidade],
        mov.obra.nome if mov.obra else "",
        mov.usuario.nome,
        mov.observacao or "",
        formatar_moeda(mov.valor_unitario_cents) if tem_valor else "",
        formatar_moeda(mov.quantidade * mov.valor_unitario_cents)
        if tem_valor
        else "",
    ]
