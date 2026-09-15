"""Comando `flask --app app backup` — cópia segura do banco.

Usa a API oficial de backup online do SQLite: funciona até com o app
rodando, sem risco de copiar o arquivo pela metade.
"""
import os
import sqlite3
from datetime import datetime

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("backup")
@with_appcontext
def backup_command():
    caminho_banco = current_app.config["ESTOQUE_DB_PATH"]
    if not os.path.exists(caminho_banco):
        click.echo(f"Banco não encontrado em: {caminho_banco}")
        return

    pasta_destino = current_app.config["BACKUP_DIR"]
    os.makedirs(pasta_destino, exist_ok=True)
    destino = os.path.join(
        pasta_destino, f"estoque_{datetime.now():%Y%m%d_%H%M}.db"
    )

    fonte = sqlite3.connect(caminho_banco)
    alvo = sqlite3.connect(destino)
    try:
        with alvo:  # garante o commit/fechamento do backup
            fonte.backup(alvo)
    finally:
        alvo.close()
        fonte.close()

    click.echo(f"Backup criado: {destino}")
