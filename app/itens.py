"""Cadastro de itens do estoque (perfil admin)."""
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from . import db
from .auth import admin_required
from .models import (
    Categoria,
    Item,
    nome_com_tamanho,
    opcoes_autocomplete,
    saldos_por_item,
)

bp = Blueprint("itens", __name__, url_prefix="/itens")

UNIDADES = ("un", "pc", "cx")
TAMANHOS = ("P", "M", "G", "GG", "XG", "EXGG")


def _aplicar_form(item):
    """Lê o formulário e preenche o item. Retorna mensagem de erro ou None."""
    nome = request.form.get("nome", "").strip()
    categoria_id = request.form.get("categoria_id", type=int)
    unidade = request.form.get("unidade", "")
    estoque_minimo = request.form.get("estoque_minimo", type=int)
    tamanho = request.form.get("tamanho", "").strip()
    ca = request.form.get("ca", "").strip()

    if not nome:
        return "Informe o nome do item."
    categoria = db.session.get(Categoria, categoria_id) if categoria_id else None
    if categoria is None:
        return "Selecione uma categoria válida."
    if unidade not in UNIDADES:
        return "Selecione uma unidade válida."
    if estoque_minimo is None or estoque_minimo < 0:
        return "O estoque mínimo deve ser um número inteiro maior ou igual a 0."

    item.nome = nome
    item.categoria_id = categoria.id
    item.unidade = unidade
    item.estoque_minimo = estoque_minimo
    item.tamanho = tamanho or None
    item.ca = ca or None

    # A validade é do lote que chega, não do cadastro — é informada
    # na entrada (Movimentacao.validade).
    if categoria.nome == "EPI" and not item.ca:
        return "Itens de EPI exigem o CA (Certificado de Aprovação)."
    return None


@bp.route("/")
@admin_required
def listar():
    busca = request.args.get("busca", "").strip()
    query = Item.query
    if busca:
        padrao = f"%{busca}%"
        query = query.filter(
            db.or_(
                Item.nome.ilike(padrao),
                Item.codigo.ilike(padrao),
                nome_com_tamanho().ilike(padrao),  # "Camisa Azul P"
            )
        )
    itens = query.order_by(Item.nome).all()
    saldos = saldos_por_item()
    return render_template(
        "itens/listar.html",
        itens=itens,
        saldos=saldos,
        busca=busca,
        autocomplete=opcoes_autocomplete(),
    )


@bp.route("/novo", methods=["GET", "POST"])
@admin_required
def novo():
    categorias = Categoria.query.order_by(Categoria.nome).all()
    if request.method == "POST":
        item = Item()
        erro = _aplicar_form(item)
        if erro:
            flash(erro, "danger")
        else:
            item.codigo = ""  # placeholder até o flush liberar o id
            db.session.add(item)
            db.session.flush()
            codigo_digitado = request.form.get("codigo", "").strip()
            item.codigo = codigo_digitado or f"EV{item.id:06d}"
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(
                    "Código já existe. Escolha outro ou deixe em branco.",
                    "danger",
                )
            else:
                flash(
                    f"Item criado — código: {item.codigo}.", "success"
                )
                return redirect(url_for("itens.listar"))
    return render_template(
        "itens/form.html", item=None, categorias=categorias, tamanhos=TAMANHOS
    )


@bp.route("/<int:item_id>/editar", methods=["GET", "POST"])
@admin_required
def editar(item_id):
    item = db.get_or_404(Item, item_id)
    categorias = Categoria.query.order_by(Categoria.nome).all()
    if request.method == "POST":
        erro = _aplicar_form(item)
        if erro:
            flash(erro, "danger")
        else:
            codigo_digitado = request.form.get("codigo", "").strip()
            if codigo_digitado and codigo_digitado != item.codigo:
                item.codigo = codigo_digitado
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Código já existe. Escolha outro.", "danger")
            else:
                flash("Item atualizado.", "success")
                return redirect(url_for("itens.listar"))
    return render_template(
        "itens/form.html", item=item, categorias=categorias, tamanhos=TAMANHOS
    )


@bp.route("/<int:item_id>/desativar", methods=["POST"])
@admin_required
def desativar(item_id):
    item = db.get_or_404(Item, item_id)
    item.ativo = not item.ativo  # alterna: permite reativar depois
    db.session.commit()
    estado = "reativado" if item.ativo else "desativado"
    flash(f"Item {estado}: {item.nome}.", "success")
    return redirect(url_for("itens.listar"))
