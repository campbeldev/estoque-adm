"""Cadastro de usuários do sistema (perfil admin)."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from . import db
from .auth import admin_required
from .models import PERFIS, Usuario

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

SENHA_RESET = "mudar123"


@bp.route("/")
@admin_required
def listar():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template("usuarios/listar.html", usuarios=usuarios)


@bp.route("/novo", methods=["GET", "POST"])
@admin_required
def novo():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        nome = request.form.get("nome", "").strip()
        perfil = request.form.get("perfil", "")
        senha = request.form.get("senha", "")

        if not login or not nome:
            flash("Informe o nome e o login.", "danger")
        elif perfil not in PERFIS:
            flash("Perfil inválido.", "danger")
        elif len(senha) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
        else:
            db.session.add(
                Usuario(
                    login=login,
                    nome=nome,
                    perfil=perfil,
                    senha_hash=generate_password_hash(senha),
                    forcar_troca=True,  # troca obrigatória no 1º login
                )
            )
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Já existe um usuário com este login.", "danger")
            else:
                flash(f"Usuário criado: {nome}.", "success")
                return redirect(url_for("usuarios.listar"))
    return render_template("usuarios/form.html", usuario=None, PERFIS=PERFIS)


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@admin_required
def editar(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        perfil = request.form.get("perfil", "")
        if not nome:
            flash("Informe o nome do usuário.", "danger")
        elif perfil not in PERFIS:
            flash("Perfil inválido.", "danger")
        else:
            usuario.nome = nome
            usuario.perfil = perfil
            db.session.commit()
            flash("Usuário atualizado.", "success")
            return redirect(url_for("usuarios.listar"))
    return render_template("usuarios/form.html", usuario=usuario, PERFIS=PERFIS)


@bp.route("/<int:usuario_id>/resetar-senha", methods=["POST"])
@admin_required
def resetar_senha(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    usuario.senha_hash = generate_password_hash(SENHA_RESET)
    usuario.forcar_troca = True
    db.session.commit()
    flash(
        f"Senha de {usuario.nome} resetada para {SENHA_RESET} "
        "(troca obrigatória no próximo login).",
        "success",
    )
    return redirect(url_for("usuarios.listar"))


@bp.route("/<int:usuario_id>/desativar", methods=["POST"])
@admin_required
def desativar(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if usuario.id == g.usuario.id:
        flash("Você não pode desativar o próprio usuário.", "danger")
        return redirect(url_for("usuarios.listar"))
    usuario.ativo = not usuario.ativo
    db.session.commit()
    estado = "reativado" if usuario.ativo else "desativado"
    flash(f"Usuário {estado}: {usuario.nome}.", "success")
    return redirect(url_for("usuarios.listar"))
