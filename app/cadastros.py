"""Cadastros auxiliares: funcionários e obras (perfil admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from . import db
from .auth import admin_required
from .models import (
    Funcionario,
    Obra,
    opcoes_cargos,
    sugestoes_funcionarios,
    valores_unicos,
)

bp = Blueprint("cadastros", __name__)


# ----------------------------- Funcionários -----------------------------


def _sugestoes_busca_funcionario():
    """Sugestões da busca de funcionários: nome, matrícula e empresa."""
    return sugestoes_funcionarios()


def _sugestoes_form_funcionario():
    # empresa e cargo se repetem entre funcionários; nome/matrícula não
    return {"empresas": valores_unicos(Funcionario.empresa)}


def _aplicar_funcionario(funcionario):
    nome = request.form.get("nome", "").strip()
    matricula = request.form.get("matricula", "").strip()
    empresa = request.form.get("empresa", "").strip()
    cargo = request.form.get("cargo", "").strip()
    if not nome:
        return "Informe o nome do funcionário."
    if not matricula:
        return "Informe a matrícula do funcionário."
    if not empresa:
        return "Informe a empresa do funcionário."
    if not cargo:
        return "Informe o cargo do funcionário."
    repetida = Funcionario.query.filter(
        Funcionario.matricula == matricula,
        Funcionario.empresa == empresa,
        Funcionario.id != funcionario.id,
    ).first()
    if repetida is not None:
        return "Já existe um funcionário com esta matrícula nesta empresa."
    funcionario.nome = nome
    funcionario.matricula = matricula
    funcionario.empresa = empresa
    funcionario.cargo = cargo
    return None


@bp.route("/funcionarios")
@admin_required
def funcionarios():
    busca = request.args.get("busca", "").strip()
    empresa = request.args.get("empresa", "").strip()
    query = Funcionario.query
    if empresa:
        query = query.filter(Funcionario.empresa == empresa)
    if busca:
        padrao = f"%{busca}%"
        query = query.filter(
            db.or_(
                Funcionario.nome.ilike(padrao),
                Funcionario.matricula.ilike(padrao),
                Funcionario.empresa.ilike(padrao),
            )
        )
    return render_template(
        "cadastros/funcionarios.html",
        funcionarios=query.order_by(Funcionario.nome).all(),
        busca=busca,
        empresa=empresa,
        empresas=valores_unicos(Funcionario.empresa),
        sugestoes_busca=_sugestoes_busca_funcionario(),
    )


@bp.route("/funcionarios/novo", methods=["GET", "POST"])
@admin_required
def funcionario_novo():
    if request.method == "POST":
        funcionario = Funcionario()
        erro = _aplicar_funcionario(funcionario)
        if erro:
            flash(erro, "danger")
        else:
            db.session.add(funcionario)
            try:
                db.session.commit()
            except IntegrityError:  # corrida entre dois cadastros simultâneos
                db.session.rollback()
                flash("Já existe um funcionário com esta matrícula nesta empresa.", "danger")
            else:
                flash(f"Funcionário criado: {funcionario.nome}.", "success")
                return redirect(url_for("cadastros.funcionarios"))
    return render_template(
        "cadastros/funcionario_form.html",
        funcionario=None,
        cargos=opcoes_cargos(),
        **_sugestoes_form_funcionario(),
    )


@bp.route("/funcionarios/<int:funcionario_id>/editar", methods=["GET", "POST"])
@admin_required
def funcionario_editar(funcionario_id):
    funcionario = db.get_or_404(Funcionario, funcionario_id)
    if request.method == "POST":
        erro = _aplicar_funcionario(funcionario)
        if erro:
            flash(erro, "danger")
        else:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Já existe um funcionário com esta matrícula nesta empresa.", "danger")
            else:
                flash("Funcionário atualizado.", "success")
                return redirect(url_for("cadastros.funcionarios"))
    return render_template(
        "cadastros/funcionario_form.html",
        funcionario=funcionario,
        cargos=opcoes_cargos(),
        **_sugestoes_form_funcionario(),
    )


@bp.route("/funcionarios/<int:funcionario_id>/desativar", methods=["POST"])
@admin_required
def funcionario_desativar(funcionario_id):
    funcionario = db.get_or_404(Funcionario, funcionario_id)
    funcionario.ativo = not funcionario.ativo
    db.session.commit()
    estado = "reativado" if funcionario.ativo else "desativado"
    flash(f"Funcionário {estado}: {funcionario.nome}.", "success")
    return redirect(url_for("cadastros.funcionarios"))


# -------------------------------- Obras ---------------------------------


def _sugestoes_busca_obra():
    return [(valor, "obra") for valor in valores_unicos(Obra.nome)]


def _aplicar_obra(obra):
    nome = request.form.get("nome", "").strip()
    if not nome:
        return "Informe o nome da obra."
    obra.nome = nome
    return None


@bp.route("/obras")
@admin_required
def obras():
    busca = request.args.get("busca", "").strip()
    query = Obra.query
    if busca:
        query = query.filter(Obra.nome.ilike(f"%{busca}%"))
    return render_template(
        "cadastros/obras.html",
        obras=query.order_by(Obra.nome).all(),
        busca=busca,
        sugestoes_busca=_sugestoes_busca_obra(),
    )


@bp.route("/obras/novo", methods=["GET", "POST"])
@admin_required
def obra_nova():
    if request.method == "POST":
        obra = Obra()
        erro = _aplicar_obra(obra)
        if erro:
            flash(erro, "danger")
        else:
            db.session.add(obra)
            db.session.commit()
            flash(f"Obra criada: {obra.nome}.", "success")
            return redirect(url_for("cadastros.obras"))
    return render_template("cadastros/obra_form.html", obra=None)


@bp.route("/obras/<int:obra_id>/editar", methods=["GET", "POST"])
@admin_required
def obra_editar(obra_id):
    obra = db.get_or_404(Obra, obra_id)
    if request.method == "POST":
        erro = _aplicar_obra(obra)
        if erro:
            flash(erro, "danger")
        else:
            db.session.commit()
            flash("Obra atualizada.", "success")
            return redirect(url_for("cadastros.obras"))
    return render_template("cadastros/obra_form.html", obra=obra)


@bp.route("/obras/<int:obra_id>/desativar", methods=["POST"])
@admin_required
def obra_desativar(obra_id):
    obra = db.get_or_404(Obra, obra_id)
    obra.ativo = not obra.ativo
    db.session.commit()
    estado = "reativada" if obra.ativo else "desativada"
    flash(f"Obra {estado}: {obra.nome}.", "success")
    return redirect(url_for("cadastros.obras"))
