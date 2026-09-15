r"""Configuração central do sistema.

O caminho do banco pode ser trocado pela variável de ambiente ESTOQUE_DB,
útil para manter o arquivo fora da pasta sincronizada do OneDrive:
    $env:ESTOQUE_DB = "C:\Dados\estoque.db"
"""
import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    # Em produção, defina: $env:SECRET_KEY = "uma-chave-aleatoria-bem-longa"
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")

    ESTOQUE_DB_PATH = os.environ.get("ESTOQUE_DB") or os.path.join(
        BASE_DIR, "instance", "estoque.db"
    )
    # Produção: DATABASE_URL aponta para o PostgreSQL
    # (ex.: postgresql+psycopg://usuario:senha@host:5432/banco).
    # Sem ela, mantém o SQLite local (desenvolvimento e testes).
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + ESTOQUE_DB_PATH.replace(os.sep, "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessão dura 12h (um turno inteiro no caixa sem precisar logar de novo)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # Token CSRF válido pela sessão inteira (o padrão de 1h quebraria o caixa
    # no meio do expediente)
    WTF_CSRF_TIME_LIMIT = None

    # Pasta das cópias do banco (comando `flask --app app backup`)
    BACKUP_DIR = os.environ.get("ESTOQUE_BACKUP_DIR") or os.path.join(
        BASE_DIR, "backups"
    )
