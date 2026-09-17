"""Fábrica da aplicação — tudo nasce aqui: banco, CSRF, blueprints e CLI."""
import os
from datetime import date

from flask import Flask, g, render_template, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config

db = SQLAlchemy()
csrf = CSRFProtect()


def formatar_data(valor):
    """Exibe datas no formato brasileiro (dd/mm/aaaa)."""
    return valor.strftime("%d/%m/%Y") if valor else "—"


def formatar_data_hora(valor):
    return valor.strftime("%d/%m/%Y %H:%M") if valor else "—"


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # instance/ guarda o banco; backups/ guarda as cópias de segurança
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)
    os.makedirs(app.config["COMPROVANTES_DIR"], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    # Migração leve do SQLite (uma vez por processo): cria a tabela `nota`,
    # as colunas novas da movimentacao e vincula as entradas legadas.
    with app.app_context():
        from .migracao import migrar_leve

        migrar_leve()

    from .models import TIPOS_EXIBICAO, UNIDADES_EXIBICAO, Usuario
    from .moeda import formatar_moeda

    @app.before_request
    def carregar_usuario():
        """Disponibiliza o usuário logado em g.usuario (ou None)."""
        g.usuario = None
        usuario_id = session.get("usuario_id")
        if usuario_id is not None:
            g.usuario = db.session.get(Usuario, usuario_id)

    @app.context_processor
    def utilidades_de_template():
        return {
            "usuario_atual": g.usuario,
            "UNIDADES": UNIDADES_EXIBICAO,
            "TIPOS": TIPOS_EXIBICAO,
            "formatar_data": formatar_data,
            "formatar_data_hora": formatar_data_hora,
            "formatar_moeda": formatar_moeda,
            "hoje": date.today(),
        }

    from . import (
        auth,
        backup,
        cadastros,
        entradas,
        estoque,
        itens,
        logistica,
        notas,
        pos,
        relatorios,
        solicitacoes,
        seed,
        usuarios,
        
    )
    app.register_blueprint(auth.bp)
    app.register_blueprint(itens.bp)
    app.register_blueprint(cadastros.bp)
    app.register_blueprint(usuarios.bp)
    app.register_blueprint(entradas.bp)
    app.register_blueprint(notas.bp)
    app.register_blueprint(pos.bp)
    app.register_blueprint(estoque.bp)
    app.register_blueprint(relatorios.bp)
    app.register_blueprint(solicitacoes.bp)
    app.register_blueprint(logistica.bp)
    app.cli.add_command(seed.seed_command)
    app.cli.add_command(backup.backup_command)

    @app.errorhandler(403)
    def erro_403(_e):
        return render_template("erros/403.html"), 403

    @app.errorhandler(404)
    def erro_404(_e):
        return render_template("erros/404.html"), 404

    @app.route("/sw.js")
    def service_worker():
        # o header permite que o service worker atue em todo o site (/)
        # mesmo o arquivo morando na pasta de estáticos
        resposta = send_from_directory(
            app.static_folder, "sw.js", mimetype="application/javascript"
        )
        resposta.headers["Service-Worker-Allowed"] = "/"
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta

    return app
