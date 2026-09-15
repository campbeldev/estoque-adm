"""PDF do relatório individual do funcionário (A4 retrato, pronto p/ imprimir)."""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import UNIDADES_EXIBICAO
from ..moeda import formatar_moeda

AZUL_ESCURO = colors.HexColor("#10151c")  # cor do header do sistema
CINZA_CLARO = colors.HexColor("#f4f6f8")
CINZA_BORDA = colors.HexColor("#d8dee4")
CINZA_TEXTO = colors.HexColor("#5c6b7a")


def gerar_pdf_relatorio_funcionario(
    funcionario, retiradas, data_inicio="", data_fim="", total_valor=0
):
    """Gera o PDF do relatório de retiradas de um funcionário."""
    saida = BytesIO()
    doc = SimpleDocTemplate(
        saida,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Relatório de retiradas — {funcionario.nome}",
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "titulo",
        parent=estilos["Title"],
        fontSize=15,
        leading=18,
        spaceAfter=2,
        textColor=AZUL_ESCURO,
    )
    estilo_subtitulo = ParagraphStyle(
        "subtitulo",
        parent=estilos["Normal"],
        fontSize=8.5,
        textColor=CINZA_TEXTO,
        spaceAfter=8,
    )
    estilo_celula = ParagraphStyle(
        "celula",
        parent=estilos["Normal"],
        fontSize=8.5,
        leading=11,
    )

    periodo = "Todo o período"
    if data_inicio or data_fim:
        periodo = f"{data_inicio or '…'} a {data_fim or '…'}"

    elementos = [
        Paragraph(f"Relatório de Retiradas — {funcionario.nome}", estilo_titulo),
        Paragraph(
            f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
            f"Período: {periodo}",
            estilo_subtitulo,
        ),
    ]

    # Cabeçalho com os dados do funcionário
    dados_funcionario = [
        ["NOME", funcionario.nome, "MATRÍCULA", funcionario.matricula],
        ["EMPRESA", funcionario.empresa, "CARGO", funcionario.cargo or "—"],
    ]
    tabela_dados = Table(
        dados_funcionario,
        colWidths=[22 * mm, 62 * mm, 22 * mm, 62 * mm],
    )
    tabela_dados.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, -1), 7),
                ("FONTSIZE", (2, 0), (2, -1), 7),
                ("TEXTCOLOR", (0, 0), (0, -1), CINZA_TEXTO),
                ("TEXTCOLOR", (2, 0), (2, -1), CINZA_TEXTO),
                ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
                ("BOX", (0, 0), (-1, -1), 0.75, CINZA_BORDA),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, CINZA_BORDA),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elementos.append(tabela_dados)
    elementos.append(Spacer(1, 8 * mm))

    # Tabela de retiradas (cabeçalho repetido a cada página)
    linhas = [["Data", "Produto", "Qtd", "Un.", "Obra", "Lançado por", "Valor"]]
    for mov in retiradas:
        produto = mov.item.nome
        if mov.item.tamanho:
            produto += f" (Tam. {mov.item.tamanho})"
        valor = (
            formatar_moeda(mov.quantidade * mov.valor_unitario_cents)
            if mov.valor_unitario_cents is not None
            else "—"
        )
        linhas.append(
            [
                mov.data.strftime("%d/%m/%Y %H:%M"),
                Paragraph(produto, estilo_celula),
                str(mov.quantidade),
                UNIDADES_EXIBICAO[mov.item.unidade],
                Paragraph(mov.obra.nome if mov.obra else "—", estilo_celula),
                Paragraph(mov.usuario.nome, estilo_celula),
                valor,
            ]
        )
    if retiradas:
        linhas.append(
            [
                "",
                "TOTAL DE ITENS",
                str(sum(m.quantidade for m in retiradas)),
                "",
                "",
                "",
                formatar_moeda(total_valor),
            ]
        )
    else:
        linhas.append(["", "Nenhuma retirada no período", "", "", "", "", ""])

    tabela_retiradas = Table(
        linhas,
        colWidths=[28 * mm, 52 * mm, 12 * mm, 10 * mm, 28 * mm, 24 * mm, 24 * mm],
        repeatRows=1,
    )
    estilo_retiradas = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), CINZA_CLARO),
        ("TEXTCOLOR", (0, 0), (-1, 0), CINZA_TEXTO),
        ("BOX", (0, 0), (-1, -1), 0.75, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, CINZA_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ALIGN", (6, 0), (6, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if retiradas:
        estilo_retiradas += [
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), CINZA_CLARO),
        ]
    tabela_retiradas.setStyle(TableStyle(estilo_retiradas))
    elementos.append(tabela_retiradas)

    doc.build(elementos)
    return saida.getvalue()
