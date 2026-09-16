"""Rastreio e conclusão de entregas.

Separado do estoque de propósito — a Movimentacao continua imutável; aqui a
logística (Remessa + EventoRemessa) é lida no rastreio e concluída na entrega:
quem recebeu + assinatura (canvas) e, opcionalmente, uma foto.
"""
import base64
import binascii
import os
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import db
from .auth import login_required
from .models import EventoRemessa, Remessa

bp = Blueprint("logistica", __name__, url_prefix="/logistica")

# Rótulo e cor do badge por status (status derivado do último evento).
STATUS = {
    "despachada": {"rotulo": "Em trânsito", "badge": "text-bg-primary"},
    "recebida": {"rotulo": "Recebida", "badge": "text-bg-success"},
    "cancelada": {"rotulo": "Cancelada", "badge": "text-bg-danger"},
}

# Ordem de exibição: o que está em trânsito vem primeiro.
ORDEM_STATUS = {"despachada": 0, "recebida": 1, "cancelada": 2}

_PREFIXO_ASSINATURA = "data:image/png;base64,"
_EXTENSOES_FOTO = {".png": "png", ".jpg": "jpg", ".jpeg": "jpg"}


@bp.route("/")
@login_required
def index():
    status_filtro = request.args.get("status", "").strip()
    remessas = Remessa.query.order_by(Remessa.data_criacao.desc()).all()
    if status_filtro in ORDEM_STATUS:
        remessas = [r for r in remessas if r.status == status_filtro]
    # sort estável: agrupa por status (pendentes na frente) e preserva a
    # ordem por data decrescente dentro de cada grupo
    remessas.sort(key=lambda r: ORDEM_STATUS.get(r.status, 9))
    return render_template(
        "logistica/index.html",
        remessas=remessas,
        status_filtro=status_filtro,
        STATUS=STATUS,
    )


@bp.route("/<int:remessa_id>")
@login_required
def detalhe(remessa_id):
    remessa = db.get_or_404(Remessa, remessa_id)
    eventos = {e.tipo: e for e in remessa.eventos}
    return render_template(
        "logistica/detalhe.html",
        remessa=remessa,
        STATUS=STATUS,
        despachada=eventos.get("despachada"),
        recebida=eventos.get("recebida"),
        cancelada=eventos.get("cancelada"),
    )


@bp.route("/<int:remessa_id>/receber", methods=["GET", "POST"])
@login_required
def receber(remessa_id):
    remessa = db.get_or_404(Remessa, remessa_id)
    if remessa.status != "despachada":
        flash("Esta remessa já foi concluída ou cancelada.", "warning")
        return redirect(url_for("logistica.detalhe", remessa_id=remessa.id))

    if request.method == "POST":
        erro = _concluir_recebimento(remessa)
        if erro:
            flash(erro, "danger")
        else:
            flash("Entrega registrada com sucesso.", "success")
            return redirect(url_for("logistica.detalhe", remessa_id=remessa.id))

    return render_template("logistica/receber.html", remessa=remessa)


@bp.route("/<int:remessa_id>/comprovante/<tipo>")
@login_required
def comprovante(remessa_id, tipo):
    """Serve o arquivo de comprovante (assinatura ou foto) da remessa."""
    remessa = db.get_or_404(Remessa, remessa_id)
    if tipo == "assinatura":
        nome = remessa.comprovante_arq
    elif tipo == "foto":
        nome = remessa.comprovante_foto_arq
    else:
        return abort(404)
    if not nome:
        return abort(404)
    return send_from_directory(current_app.config["COMPROVANTES_DIR"], nome)


def _concluir_recebimento(remessa):
    """Valida e grava o recebimento. Retorna mensagem de erro ou None."""
    recebido_por = (request.form.get("recebido_por") or "").strip()
    if not recebido_por:
        return "Informe quem recebeu a remessa."

    assinatura = request.form.get("assinatura") or ""
    dados_assinatura = _decodificar_assinatura(assinatura)
    if dados_assinatura is None:
        return "Assine para registrar o recebimento."

    # valida a foto antes de gravar qualquer arquivo (evita órfão)
    foto = request.files.get("foto")
    nome_foto = None
    if foto and foto.filename:
        extensao = os.path.splitext(foto.filename)[1].lower()
        if extensao not in _EXTENSOES_FOTO:
            return "Foto inválida — envie um PNG ou JPG."
        nome_foto = f"{remessa.codigo}_foto{extensao}"

    pasta = current_app.config["COMPROVANTES_DIR"]
    nome_assinatura = f"{remessa.codigo}_assinatura.png"
    with open(os.path.join(pasta, nome_assinatura), "wb") as arquivo:
        arquivo.write(dados_assinatura)
    if nome_foto:
        foto.save(os.path.join(pasta, nome_foto))

    remessa.recebido_por = recebido_por
    remessa.comprovante_tipo = "ambos" if nome_foto else "assinatura"
    remessa.comprovante_arq = nome_assinatura
    remessa.comprovante_foto_arq = nome_foto
    remessa.data_recebimento = datetime.now()
    db.session.add(
        EventoRemessa(
            remessa_id=remessa.id,
            tipo="recebida",
            usuario_id=g.usuario.id,
            observacao=f"Recebido por {recebido_por}",
        )
    )
    db.session.commit()
    return None


def _decodificar_assinatura(assinatura):
    """Extrai os bytes PNG do data URL do canvas (None se inválido)."""
    if not assinatura.startswith(_PREFIXO_ASSINATURA):
        return None
    try:
        dados = base64.b64decode(assinatura[len(_PREFIXO_ASSINATURA):])
    except (binascii.Error, ValueError):
        return None
    return dados or None
