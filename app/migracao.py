"""Migração leve do SQLite — sem alembic, idempotente.

Roda uma vez por processo no create_app: garante o esquema atual
(tabela `nota` e colunas novas da movimentacao) e agrupa as entradas
legadas (nota_fiscal + fornecedor soltos) em Notas.
"""
from sqlalchemy import inspect

from . import db
from .models import Movimentacao, Nota


def migrar_leve():
    """Garante o esquema atual e vincula entradas legadas a Notas."""
    # 1) cria as tabelas que faltam (em banco novo, cria tudo)
    db.create_all()

    # 2) colunas novas na movimentacao (SQLite e PostgreSQL aceitam ADD COLUMN)
    insp = inspect(db.engine)
    colunas = {c["name"] for c in insp.get_columns("movimentacao")}
    if "nota_id" not in colunas:
        db.session.execute(
            db.text(
                "ALTER TABLE movimentacao ADD COLUMN nota_id INTEGER "
                "REFERENCES nota(id)"
            )
        )
    if "valor_unitario_cents" not in colunas:
        db.session.execute(
            db.text(
                "ALTER TABLE movimentacao ADD COLUMN valor_unitario_cents INTEGER"
            )
        )
    if "validade" not in colunas:
        db.session.execute(
            db.text("ALTER TABLE movimentacao ADD COLUMN validade DATE")
        )
    db.session.execute(
        db.text(
            "CREATE INDEX IF NOT EXISTS ix_movimentacao_nota_id "
            "ON movimentacao (nota_id)"
        )
    )

    # 3) entradas legadas viram Notas (série vazia), agrupadas por
    #    (nota_fiscal, fornecedor) — idempotente: só pega nota_id NULL
    pendentes = (
        Movimentacao.query.filter(
            Movimentacao.nota_id.is_(None),
            Movimentacao.tipo == "entrada",
            Movimentacao.nota_fiscal.isnot(None),
            Movimentacao.nota_fiscal != "",
        )
        .order_by(Movimentacao.id)
        .all()
    )
    notas_por_chave = {}
    for mov in pendentes:
        chave = (mov.nota_fiscal.strip(), (mov.fornecedor or "").strip())
        nota = notas_por_chave.get(chave)
        if nota is None:
            nota = Nota(
                numero=chave[0],
                serie="",
                fornecedor=chave[1],
                data=mov.data,
                usuario_id=mov.usuario_id,
            )
            db.session.add(nota)
            db.session.flush()  # id para o vínculo, sem commit
            notas_por_chave[chave] = nota
        mov.nota_id = nota.id

    # 4) entradas legadas sem validade herdam a do cadastro do item
    #    (antes a validade morava lá; hoje ela é do lote) — idempotente:
    #    só pega NULL. O modelo atual não tem mais Item.validade, então a
    #    atualização é via SQL puro, só em bancos que ainda têm a coluna.
    colunas_item = {c["name"] for c in insp.get_columns("item")}
    if "validade" in colunas_item:
        db.session.execute(
            db.text(
                "UPDATE movimentacao SET validade = ("
                "SELECT validade FROM item WHERE item.id = movimentacao.item_id"
                ") WHERE tipo = 'entrada' AND validade IS NULL"
            )
        )
    db.session.commit()
