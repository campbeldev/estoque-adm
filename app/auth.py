"""Autenticação: login, logout, troca de senha e decorators de perfil."""
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .models import Usuario

bp = Blueprint("auth", __name__)


def login_required(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.login"))
        if g.usuario.forcar_troca and request.endpoint not in (
            "auth.alterar_senha",
            "auth.logout",
        ):
            return redirect(url_for("auth.alterar_senha"))
        return funcao(*args, **kwargs)

    return decorada


def admin_required(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.login"))
        if g.usuario.perfil != "admin":
            abort(403)
        return funcao(*args, **kwargs)

    return decorada


@bp.route("/")
@login_required
def raiz():
    """Início conforme o perfil: admin vê o estoque, operador vai ao caixa."""
    if g.usuario.perfil == "admin":
        return redirect(url_for("estoque.index"))
    return redirect(url_for("pos.index"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario is not None and not g.usuario.forcar_troca:
        return redirect(url_for("auth.raiz"))

    erro = None
    if request.method == "POST":
        login_digitado = request.form.get("login", "").strip()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(login=login_digitado).first()

        if usuario is None or not check_password_hash(usuario.senha_hash, senha):
            erro = "Usuário ou senha inválidos."
        elif not usuario.ativo:
            erro = "Usuário desativado. Fale com o administrador."
        else:
            session.clear()  # evita fixação de sessão
            session["usuario_id"] = usuario.id
            session.permanent = True
            return redirect(url_for("auth.raiz"))

    return render_template("auth/login.html", erro=erro)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/alterar-senha", methods=["GET", "POST"])
@login_required
def alterar_senha():
    if request.method == "POST":
        atual = request.form.get("senha_atual", "")
        nova = request.form.get("senha_nova", "")
        confirmacao = request.form.get("senha_confirmacao", "")

        if not check_password_hash(g.usuario.senha_hash, atual):
            flash("Senha atual incorreta.", "danger")
        elif len(nova) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "danger")
        elif nova != confirmacao:
            flash("A confirmação não confere com a nova senha.", "danger")
        else:
            g.usuario.senha_hash = generate_password_hash(nova)
            g.usuario.forcar_troca = False
            db.session.commit()
            flash("Senha alterada com sucesso.", "success")
            return redirect(url_for("auth.raiz"))

    return render_template(
        "auth/alterar_senha.html", obrigatoria=g.usuario.forcar_troca
    )
