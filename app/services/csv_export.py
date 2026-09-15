"""CSV no formato que o Excel pt-BR abre corretamente (BOM UTF-8 + ';')."""
import csv
from io import StringIO


def montar_csv(cabecalhos, linhas):
    saida = StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(cabecalhos)
    escritor.writerows(linhas)
    # BOM: sem ele, o Excel pt-BR bagunça os acentos ("Saída" vira "SaÃda")
    return "﻿" + saida.getvalue()
