"""Cadastros auxiliares: entregadores, setores e obras (perfil admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from . import db
from .auth import admin_required
from .models import Entregador, Movimentacao, Obra, Remessa, Setor, Solicitacao, valores_unicos

bp = Blueprint("cadastros", __name__)


# ------------------------------ Entregadores -----------------------------


def _sugestoes_busca_entregador():
    pares = []
    for valor in valores_unicos(Entregador.nome):
        pares.append((valor, "entregador"))
    for valor in valores_unicos(Entregador.contato):
        pares.append((valor, "contato"))
    return pares


def _aplicar_entregador(entregador):
    nome = request.form.get("nome", "").strip()
    contato = request.form.get("contato", "").strip()
    if not nome:
        return "Informe o nome do entregador."
    entregador.nome = nome
    entregador.contato = contato or None
    return None


@bp.route("/entregadores")
@admin_required
def entregadores():
    busca = request.args.get("busca", "").strip()
    query = Entregador.query
    if busca:
        padrao = f"%{busca}%"
        query = query.filter(
            db.or_(
                Entregador.nome.ilike(padrao),
                Entregador.contato.ilike(padrao),
            )
        )
    return render_template(
        "cadastros/entregadores.html",
        entregadores=query.order_by(Entregador.nome).all(),
        busca=busca,
        sugestoes_busca=_sugestoes_busca_entregador(),
    )


@bp.route("/entregadores/novo", methods=["GET", "POST"])
@admin_required
def entregador_novo():
    if request.method == "POST":
        entregador = Entregador()
        erro = _aplicar_entregador(entregador)
        if erro:
            flash(erro, "danger")
        else:
            db.session.add(entregador)
            db.session.commit()
            flash(f"Entregador criado: {entregador.nome}.", "success")
            return redirect(url_for("cadastros.entregadores"))
    return render_template("cadastros/entregador_form.html", entregador=None)


@bp.route("/entregadores/<int:entregador_id>/editar", methods=["GET", "POST"])
@admin_required
def entregador_editar(entregador_id):
    entregador = db.get_or_404(Entregador, entregador_id)
    if request.method == "POST":
        erro = _aplicar_entregador(entregador)
        if erro:
            flash(erro, "danger")
        else:
            db.session.commit()
            flash("Entregador atualizado.", "success")
            return redirect(url_for("cadastros.entregadores"))
    return render_template("cadastros/entregador_form.html", entregador=entregador)


@bp.route("/entregadores/<int:entregador_id>/desativar", methods=["POST"])
@admin_required
def entregador_desativar(entregador_id):
    entregador = db.get_or_404(Entregador, entregador_id)
    entregador.ativo = not entregador.ativo
    db.session.commit()
    estado = "reativado" if entregador.ativo else "desativado"
    flash(f"Entregador {estado}: {entregador.nome}.", "success")
    return redirect(url_for("cadastros.entregadores"))


# -------------------------------- Setores --------------------------------


def _sugestoes_busca_setor():
    return [(valor, "setor") for valor in valores_unicos(Setor.nome)]


def _aplicar_setor(setor):
    nome = request.form.get("nome", "").strip()
    if not nome:
        return "Informe o nome do setor."
    setor.nome = nome
    return None


@bp.route("/setores")
@admin_required
def setores():
    busca = request.args.get("busca", "").strip()
    query = Setor.query
    if busca:
        query = query.filter(Setor.nome.ilike(f"%{busca}%"))
    return render_template(
        "cadastros/setores.html",
        setores=query.order_by(Setor.nome).all(),
        busca=busca,
        sugestoes_busca=_sugestoes_busca_setor(),
    )


@bp.route("/setores/novo", methods=["GET", "POST"])
@admin_required
def setor_novo():
    if request.method == "POST":
        setor = Setor()
        erro = _aplicar_setor(setor)
        if erro:
            flash(erro, "danger")
        else:
            db.session.add(setor)
            try:
                db.session.commit()
            except IntegrityError:  # nome é único
                db.session.rollback()
                flash("Já existe um setor com este nome.", "danger")
            else:
                flash(f"Setor criado: {setor.nome}.", "success")
                return redirect(url_for("cadastros.setores"))
    return render_template("cadastros/setor_form.html", setor=None)


@bp.route("/setores/<int:setor_id>/editar", methods=["GET", "POST"])
@admin_required
def setor_editar(setor_id):
    setor = db.get_or_404(Setor, setor_id)
    if request.method == "POST":
        erro = _aplicar_setor(setor)
        if erro:
            flash(erro, "danger")
        else:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Já existe um setor com este nome.", "danger")
            else:
                flash("Setor atualizado.", "success")
                return redirect(url_for("cadastros.setores"))
    return render_template("cadastros/setor_form.html", setor=setor)


@bp.route("/setores/<int:setor_id>/excluir", methods=["POST"])
@admin_required
def setor_excluir(setor_id):
    setor = db.get_or_404(Setor, setor_id)
    usos = (
        Solicitacao.query.filter_by(setor_id=setor.id).count()
        + Remessa.query.filter_by(setor_id=setor.id).count()
        + Movimentacao.query.filter_by(setor_id=setor.id).count()
    )
    if usos:
        flash(
            "Não é possível excluir este setor porque ele já está em uso "
            "por solicitações, remessas ou movimentações.",
            "warning",
        )
    else:
        db.session.delete(setor)
        db.session.commit()
        flash(f"Setor excluído: {setor.nome}.", "success")
    return redirect(url_for("cadastros.setores"))


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
