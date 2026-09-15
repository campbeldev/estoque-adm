"""Comando `flask --app app seed` — cria o banco e os dados iniciais."""
import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from . import db
from .models import Categoria, Funcionario, Item, Obra, Usuario

CATEGORIAS_PADRAO = [
    "EPI",
    "Uniforme",
    "Ferramenta",
    "Material de Consumo",
    "Escritório",
    "Outros",
]


def _criar_item(nome, categoria, unidade, minimo=0, tamanho=None, ca=None):
    """Cria item com código automático (EV + id com 6 dígitos)."""
    item = Item(
        nome=nome,
        categoria=categoria,
        unidade=unidade,
        estoque_minimo=minimo,
        tamanho=tamanho,
        ca=ca,
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


def _semear_exemplos():
    """Dados de exemplo para conhecer o sistema com algo na tela."""
    if Item.query.first() is not None:
        return False

    epi = Categoria.query.filter_by(nome="EPI").first()
    uniforme = Categoria.query.filter_by(nome="Uniforme").first()
    consumo = Categoria.query.filter_by(nome="Material de Consumo").first()

    _criar_item(
        "Capacete de Segurança", epi, "un", minimo=10,
        ca="12345",
    )
    _criar_item("Luva de Raspa", epi, "pc", minimo=50, ca="67890")
    _criar_item("Camisa Uniforme", uniforme, "un", minimo=5, tamanho="M")
    _criar_item("Calça Uniforme", uniforme, "un", minimo=5, tamanho="G")
    _criar_item("Fita Isolante", consumo, "un", minimo=20)

    db.session.add(
        Funcionario(
            nome="João da Silva",
            matricula="001",
            empresa="Construtora Alfa Ltda.",
            cargo="Pedreiro",
        )
    )
    db.session.add(
        Funcionario(
            nome="Maria de Souza",
            matricula="002",
            empresa="Engenharia Beta S.A.",
            cargo="Engenheira Civil",
        )
    )
    db.session.add(Obra(nome="Edifício Central"))
    db.session.add(Obra(nome="Ponte do Rio Verde"))
    return True


@click.command("seed")
@click.option(
    "--exemplos",
    is_flag=True,
    help="Cria também itens, funcionários e obras de exemplo.",
)
@with_appcontext
def seed_command(exemplos):
    db.create_all()

    criados = _semear_usuarios()
    novas_categorias = _semear_categorias()
    com_exemplos = _semear_exemplos() if exemplos else False
    db.session.commit()

    click.echo("Banco criado e dados iniciais aplicados.")
    for linha in criados:
        click.echo(f"  usuário criado: {linha}")
    click.echo(f"  categorias novas: {novas_categorias}")
    if exemplos:
        if com_exemplos:
            click.echo("  dados de exemplo criados (itens, funcionários, obras).")
        else:
            click.echo("  dados de exemplo ignorados (já existem itens).")
