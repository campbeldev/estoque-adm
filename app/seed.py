"""Comando `flask --app app seed` — cria o banco e os dados iniciais."""
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from . import db
from .models import Categoria, Entregador, Item, Obra, Setor, Usuario

CATEGORIAS_PADRAO = [
    "Material de Escritório",
    "Material de Limpeza",
    "Alojamento",
    "Outros",
]

# Áreas de destino do material — distintas de Categoria (o que o item é).
SETORES_PADRAO = [
    "Escritório",
    "Limpeza",
    "Alojamento",
    "Outros",
]


def _criar_item(nome, categoria, unidade, minimo=0):
    """Cria item com código automático (EV + id com 6 dígitos)."""
    item = Item(
        nome=nome,
        categoria=categoria,
        unidade=unidade,
        estoque_minimo=minimo,
        codigo="",  # placeholder até o flush liberar o id
    )
    db.session.add(item)
    db.session.flush()  # atribui o id sem commitar
    item.codigo = f"EV{item.id:06d}"
    return item


def _semear_usuarios():
    criados = []
    if Usuario.query.filter_by(login="admin").first() is None:
        db.session.add(
            Usuario(
                login="admin",
                nome="Administrador",
                perfil="admin",
                senha_hash=generate_password_hash("admin123"),
                forcar_troca=True,
            )
        )
        criados.append(
            "admin (senha inicial admin123 — troca obrigatória no 1º login)"
        )
    if Usuario.query.filter_by(login="operador").first() is None:
        db.session.add(
            Usuario(
                login="operador",
                nome="Operador do Almoxarifado",
                perfil="operador",
                senha_hash=generate_password_hash("operador123"),
                forcar_troca=True,
            )
        )
        criados.append(
            "operador (senha inicial operador123 — troca obrigatória no 1º login)"
        )
    return criados


def _semear_categorias():
    novas = 0
    for nome in CATEGORIAS_PADRAO:
        if Categoria.query.filter_by(nome=nome).first() is None:
            db.session.add(Categoria(nome=nome))
            novas += 1
    return novas


def _semear_setores():
    novas = 0
    for nome in SETORES_PADRAO:
        if Setor.query.filter_by(nome=nome).first() is None:
            db.session.add(Setor(nome=nome))
            novas += 1
    return novas


def _semear_exemplos():
    """Dados de exemplo para conhecer o sistema com algo na tela."""
    if Item.query.first() is not None:
        return False

    escritorio = Categoria.query.filter_by(nome="Material de Escritório").first()
    limpeza = Categoria.query.filter_by(nome="Material de Limpeza").first()
    alojamento = Categoria.query.filter_by(nome="Alojamento").first()

    _criar_item("Papel Sulfite A4", escritorio, "cx", minimo=20)
    _criar_item("Caneta Esferográfica Azul", escritorio, "cx", minimo=10)
    _criar_item("Detergente Neutro", limpeza, "un", minimo=30)
    _criar_item("Sabão em Pó", limpeza, "cx", minimo=15)
    _criar_item("Lençol de Solteiro", alojamento, "un", minimo=10)

    db.session.add(Obra(nome="Sede", eh_sede=True))
    db.session.add(Obra(nome="Edifício Central"))
    db.session.add(Obra(nome="Ponte do Rio Verde"))
    db.session.add(Entregador(nome="Carlos Motorista", contato="(11) 99999-0000"))
    return True


@click.command("seed")
@click.option(
    "--exemplos",
    is_flag=True,
    help="Cria também itens, entregadores e obras de exemplo.",
)
@with_appcontext
def seed_command(exemplos):
    db.create_all()

    criados = _semear_usuarios()
    novas_categorias = _semear_categorias()
    novos_setores = _semear_setores()
    com_exemplos = _semear_exemplos() if exemplos else False
    db.session.commit()

    click.echo("Banco criado e dados iniciais aplicados.")
    for linha in criados:
        click.echo(f"  usuário criado: {linha}")
    click.echo(f"  categorias novas: {novas_categorias}")
    click.echo(f"  setores novos: {novos_setores}")
    if exemplos:
        if com_exemplos:
            click.echo("  dados de exemplo criados (itens, entregadores, obras).")
        else:
            click.echo("  dados de exemplo ignorados (já existem itens).")
