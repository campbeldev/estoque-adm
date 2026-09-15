"""Dinheiro em centavos inteiros — sem float, sem locale.

Os valores monetários são guardados como inteiros (centavos) para a
aritmética ficar exata no SQLite; a formatação pt-BR acontece só aqui,
na hora de exibir.
"""
import re

_PADRAO_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$")


def formatar_moeda(centavos):
    """Formata centavos inteiros como dinheiro pt-BR (None → "—")."""
    if centavos is None:
        return "—"
    sinal = "-" if centavos < 0 else ""
    valor = abs(int(centavos))
    inteiro, decimais = divmod(valor, 100)
    milhar = f"{inteiro:,}".replace(",", ".")
    return f"{sinal}R$ {milhar},{decimais:02d}"


def parse_valor_centavos(texto):
    """Converte texto digitado em centavos inteiros; None quando inválido.

    Aceita os formatos comuns do dia a dia: "12,50", "12.50", "12,5",
    "1.234,56" (milhar com ponto) e até "R$ 12,50". Números negativos
    e vazios são rejeitados.
    """
    bruto = (texto or "").strip().replace("R$", "").replace(" ", "")
    if not bruto:
        return None
    if _PADRAO_MILHAR.match(bruto):
        bruto = bruto.replace(".", "")  # milhar: 1.234,56 → 1234,56
    bruto = bruto.replace(".", ",")  # decimal com ponto: 12.50 → 12,50
    if len(bruto.split(",")) > 2:
        return None
    try:
        valor = float(bruto.replace(",", "."))
    except ValueError:
        return None
    if valor < 0:
        return None
    return int(round(valor * 100))
