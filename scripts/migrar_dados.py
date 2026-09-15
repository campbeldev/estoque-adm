"""Migra os dados do SQLite local para o PostgreSQL.

Passo único da troca de banco: cria o schema no PostgreSQL (a partir dos
modelos), copia as tabelas preservando os IDs e ajusta as sequences para o
próximo autoincremento não colidir com os registros copiados.

Uso (com o PostgreSQL de destino já no ar — ex.: `docker compose up -d db`):

    $env:DATABASE_URL = "postgresql+psycopg://estoque_adm:senha@localhost:5434/estoque_adm"
    python scripts/migrar_dados.py

A origem é o `instance/estoque.db` (ou o caminho em `ESTOQUE_DB`).
"""
import os
import sys

from sqlalchemy import Boolean, create_engine, text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

SRC_PATH = os.environ.get("ESTOQUE_DB") or os.path.join(
    BASE_DIR, "instance", "estoque.db"
)
DATABASE_URL = os.environ.get("DATABASE_URL")

# Ordem que respeita as chaves estrangeiras (pais antes de filhos).
TABELAS = [
    "usuario",
    "categoria",
    "item",
    "funcionario",
    "obra",
    "nota",
    "movimentacao",
]


def _normalizar(linha, table):
    """Converte a linha lida (Row) num dict pronto para o INSERT.

    O SQLite guarda booleanos como 0/1; o PostgreSQL exige true/false.
    Os demais tipos (int, str, date, datetime) já vêm corretos do leitor
    do SQLAlchemy.
    """
    dados = {}
    for coluna in table.c:
        valor = linha._mapping[coluna.name]
        if isinstance(coluna.type, Boolean) and valor is not None:
            valor = bool(valor)
        dados[coluna.name] = valor
    return dados


def _contar(engine, tabela):
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT COUNT(*) FROM "{tabela}"')).scalar()


def main():
    if not DATABASE_URL:
        sys.exit(
            "Defina DATABASE_URL apontando para o PostgreSQL de destino. "
            "Ex.: postgresql+psycopg://usuario:senha@localhost:5432/banco"
        )
    if not os.path.exists(SRC_PATH):
        sys.exit(f"Banco de origem não encontrado: {SRC_PATH}")

    origem = create_engine("sqlite:///" + SRC_PATH.replace(os.sep, "/"))
    destino = create_engine(DATABASE_URL)

    # Registra os modelos e cria o schema no destino.
    from app import db, models  # noqa: F401

    db.metadata.create_all(destino)

    contagem = {}
    with destino.begin() as conn:
        for tabela in TABELAS:
            table = db.metadata.tables[tabela]
            with origem.connect() as oconn:
                linhas = oconn.execute(
                    table.select().order_by(table.c.id)
                ).all()
            dados = [_normalizar(linha, table) for linha in linhas]
            if dados:
                conn.execute(table.insert(), dados)
            contagem[tabela] = len(dados)

        # Ajusta as sequences para o próximo id não colidir com os copiados.
        for tabela in TABELAS:
            conn.execute(
                text(
                    f"SELECT setval("
                    f"pg_get_serial_sequence('{tabela}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{tabela}\"), 1), "
                    f"(SELECT MAX(id) FROM \"{tabela}\") IS NOT NULL)"
                )
            )

    # Confere contagem origem x destino.
    print("Migração concluída. Conferência (origem → destino):")
    tudo_ok = True
    for tabela in TABELAS:
        n_origem = _contar(origem, tabela)
        n_destino = _contar(destino, tabela)
        ok = n_origem == n_destino == contagem[tabela]
        tudo_ok = tudo_ok and ok
        print(
            f"  {tabela}: {n_origem} → {n_destino} "
            f"({'ok' if ok else 'DIVERGENTE'})"
        )
    if not tudo_ok:
        sys.exit("Falha na conferência: contagens divergentes.")
    print("Dados migrados com sucesso.")


if __name__ == "__main__":
    main()
