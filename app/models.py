"""Modelos de dados do controle de estoque.

Regra de ouro: o saldo de um item NUNCA é salvo — ele é sempre derivado
da soma das movimentações (entrada +, saída −, ajuste com sinal).
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func

from . import db

# Rótulos usados nos templates e no CSV
UNIDADES_EXIBICAO = {"un": "un", "pc": "pç", "cx": "cx"}
TIPOS_EXIBICAO = {"entrada": "Entrada", "saida": "Saída", "ajuste": "Ajuste"}

PERFIS = ("admin", "operador")


class Usuario(db.Model):
    __tablename__ = "usuario"
    __table_args__ = (
        db.CheckConstraint(
            "perfil IN ('admin', 'operador')", name="ck_usuario_perfil"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(10), nullable=False)
    # Desativação em vez de exclusão: as movimentações continuam apontando
    # para o usuário que operou
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    forcar_troca = db.Column(db.Boolean, nullable=False, default=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.now)


class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), nullable=False, unique=True)


class Setor(db.Model):
    """Área de destino do material (escritório, limpeza, alojamento...).

    Diferente de Categoria (o que o item é): o setor responde *para qual
    área* o material vai. Uma saída escolhe obra + setor.
    """

    __tablename__ = "setor"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), nullable=False, unique=True)


class Item(db.Model):
    __tablename__ = "item"
    __table_args__ = (
        db.CheckConstraint(
            "unidade IN ('un', 'pc', 'cx')", name="ck_item_unidade"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    categoria_id = db.Column(
        db.Integer, db.ForeignKey("categoria.id"), nullable=False
    )
    unidade = db.Column(db.String(5), nullable=False)
    # Quantidade em unidades inteiras; se um dia houver itens fracionados
    # (ex.: kg de cimento), migrar para Numeric junto com o PostgreSQL
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    # A validade é do LOTE que chega (Movimentacao.validade), não do cadastro.
    # Colunas legadas do estoque-rh (tamanho/uniforme, ca/EPI) ficam órfãs em
    # bancos antigos — a migração só adiciona, nunca destrói.
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.now)

    categoria = db.relationship("Categoria", lazy="joined")


class Entregador(db.Model):
    """Quem transporta uma remessa (funcionário, motoboy ou terceiro).

    Substitui o Funcionario legado do RH: só nome e contato, sem
    matrícula/empresa/cargo — que não fazem sentido no setor administrativo.
    """

    __tablename__ = "entregador"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    contato = db.Column(db.String(60))  # telefone/whatsapp
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class Obra(db.Model):
    __tablename__ = "obra"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    # A sede é a exceção logística: saída para ela não gera remessa.
    eh_sede = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class Nota(db.Model):
    """Nota de entrada: número + série + fornecedor agrupam os itens.

    Uma nota de mercadoria chega com vários itens; cada movimentação de
    entrada aponta para a sua nota (get-or-create no formulário).
    """

    __tablename__ = "nota"
    __table_args__ = (
        db.UniqueConstraint(
            "numero", "serie", "fornecedor", name="uq_nota_numero_serie_fornecedor"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), nullable=False)
    serie = db.Column(db.String(20), nullable=False)
    fornecedor = db.Column(db.String(120), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)

    usuario = db.relationship("Usuario", lazy="joined")

class Solicitacao(db.Model):
    __tablename__ = "solicitacao"

    id = db.Column(db.Integer, primary_key=True)
    solicitante = db.Column(db.String(120), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey("obra.id"), nullable=False)
    setor_id = db.Column(db.Integer, db.ForeignKey("setor.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.now)

    obra = db.relationship("Obra", lazy="joined")
    setor = db.relationship("Setor", lazy="joined")
    usuario = db.relationship("Usuario", lazy="joined")
    itens = db.relationship(
        "ItemSolicitacao",
        lazy="selectin",
        order_by="ItemSolicitacao.id",
        back_populates="solicitacao",
    )
  
class ItemSolicitacao(db.Model):
    __tablename__ = "item_solicitacao"

    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey("solicitacao.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)

    solicitacao = db.relationship("Solicitacao", lazy="joined", back_populates="itens")
    item = db.relationship("Item", lazy="joined")


class Remessa(db.Model):
    """A viagem de entrega: um destino (obra + setor) e um transportador.

    Nasce junto com a saída para uma obra que não seja a sede. O status é
    derivado do último EventoRemessa (despachada → recebida → ...), nunca
    salvo — mesmo princípio do saldo.
    """

    __tablename__ = "remessa"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obra.id"), nullable=False)
    setor_id = db.Column(db.Integer, db.ForeignKey("setor.id"), nullable=False)
    transportador_id = db.Column(
        db.Integer, db.ForeignKey("entregador.id"), nullable=False
    )
    # Preenchidos na entrega (evento "recebida"):
    recebido_por = db.Column(db.String(120))  # nome livre de quem recebeu
    comprovante_tipo = db.Column(db.String(20))  # 'assinatura' | 'foto' | 'ambos'
    comprovante_arq = db.Column(db.String(255))  # arquivo da assinatura (PNG)
    comprovante_foto_arq = db.Column(db.String(255))  # arquivo da foto (opcional)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.now)
    data_recebimento = db.Column(db.DateTime)

    obra = db.relationship("Obra", lazy="joined")
    setor = db.relationship("Setor", lazy="joined")
    transportador = db.relationship("Entregador", lazy="joined")
    eventos = db.relationship(
        "EventoRemessa", lazy="selectin", order_by="EventoRemessa.id",
        back_populates="remessa",
    )

    @property
    def status(self):
        """Status derivado do último evento (ou 'despachada' sem eventos)."""
        return self.eventos[-1].tipo if self.eventos else "despachada"


class EventoRemessa(db.Model):
    """Um passo na timeline da remessa — inserido, nunca editado.

    Cada linha vira uma bolinha do rastreio (despachada, recebida, ...).
    """

    __tablename__ = "evento_remessa"
    __table_args__ = (
        db.Index("ix_evento_remessa_remessa", "remessa_id"),
        db.CheckConstraint(
            "tipo IN ('despachada', 'recebida', 'cancelada')",
            name="ck_evento_remessa_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    remessa_id = db.Column(db.Integer, db.ForeignKey("remessa.id"), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    observacao = db.Column(db.String(255))

    remessa = db.relationship("Remessa", lazy="joined", back_populates="eventos")
    usuario = db.relationship("Usuario", lazy="joined")


class Movimentacao(db.Model):
    """Registro imutável de cada entrada/saída/ajuste — a fonte da verdade.

    Nenhuma rota altera ou exclui movimentações: só inserem. O saldo é
    sempre a soma viva destes registros.
    """

    __tablename__ = "movimentacao"
    __table_args__ = (
        db.Index("ix_movimentacao_item", "item_id"),
        db.Index("ix_movimentacao_tipo", "tipo"),
        db.Index("ix_movimentacao_remessa", "remessa_id"),
        db.CheckConstraint(
            "tipo IN ('entrada', 'saida', 'ajuste')", name="ck_movimentacao_tipo"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)
    # Entrada/saída guardam o valor absoluto; ajuste guarda o valor com sinal
    # (+ adiciona, − remove). Validação no código, não no banco.
    quantidade = db.Column(db.Integer, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey("obra.id"))  # destino (saída)
    setor_id = db.Column(db.Integer, db.ForeignKey("setor.id"))  # área do destino (saída)
    remessa_id = db.Column(db.Integer, db.ForeignKey("remessa.id"))  # logística (saída)
    # Legado (deprecado): as entradas novas gravam fornecedor/nota_fiscal
    # como cópia para exibição, mas a fonte canônica é a Nota.
    fornecedor = db.Column(db.String(120))  # entrada
    nota_fiscal = db.Column(db.String(30))  # entrada
    nota_id = db.Column(db.Integer, db.ForeignKey("nota.id"))  # entrada
    valor_unitario_cents = db.Column(db.Integer)  # entrada; centavos
    validade = db.Column(db.Date)  # entrada; vencimento do lote que chegou
    observacao = db.Column(db.String(255))  # motivo do ajuste
    data = db.Column(
        db.DateTime, nullable=False, default=datetime.now, index=True
    )

    item = db.relationship("Item", lazy="joined")
    usuario = db.relationship("Usuario", lazy="joined")
    obra = db.relationship("Obra", lazy="joined")
    setor = db.relationship("Setor", lazy="joined")
    remessa = db.relationship("Remessa", lazy="joined")
    nota = db.relationship("Nota", lazy="joined")

    @property
    def nota_rotulo(self):
        """Número (e série) da nota para exibição; legado cai no fallback."""
        if self.nota is not None:
            if self.nota.serie:
                return f"{self.nota.numero} (série {self.nota.serie})"
            return self.nota.numero
        return self.nota_fiscal or ""


def saldos_por_item(item_ids=None):
    """Retorna {item_id: saldo_atual} derivado das movimentações (1 query só).

    Itens sem nenhuma movimentação não aparecem no resultado (saldo = 0).
    """
    soma = func.sum(
        case(
            (Movimentacao.tipo == "saida", -Movimentacao.quantidade),
            else_=Movimentacao.quantidade,
        )
    )
    query = db.session.query(Movimentacao.item_id, soma.label("saldo"))
    if item_ids is not None:
        query = query.filter(Movimentacao.item_id.in_(item_ids))
    linhas = query.group_by(Movimentacao.item_id).all()
    return {item_id: (saldo or 0) for item_id, saldo in linhas}


def saldo_do_item(item_id):
    return saldos_por_item([item_id]).get(item_id, 0)


def custos_medios_por_item(item_ids=None):
    """Custo médio por item a partir das entradas com valor (centavos).

    {item_id: custo_medio} — soma(quantidade × valor unitário) ÷
    soma(quantidade) das entradas. Cada nota de compra pode ter preço
    diferente; o custo médio é a referência para avaliar as saídas.
    Itens sem nenhuma entrada com valor não aparecem no resultado.
    """
    total_valores = func.sum(
        Movimentacao.quantidade * Movimentacao.valor_unitario_cents
    )
    query = db.session.query(
        Movimentacao.item_id,
        total_valores,
        func.sum(Movimentacao.quantidade),
    ).filter(
        Movimentacao.tipo == "entrada",
        Movimentacao.valor_unitario_cents.isnot(None),
    )
    if item_ids is not None:
        query = query.filter(Movimentacao.item_id.in_(item_ids))
    query = query.group_by(Movimentacao.item_id)
    return {
        item_id: int(total / quantidade + 0.5)
        for item_id, total, quantidade in query.all()
        if total is not None and quantidade
    }


def saldos_por_lote(item_ids=None):
    """Saldo por lote de validade (PEPS — primeiro que vence, primeiro que sai).

    Cada entrada com validade forma um lote; as saídas e os ajustes
    negativos consomem os lotes na ordem de vencimento. O que o consumo
    não cobrir vem de unidades sem validade (ajustes positivos e entradas
    sem data). Retorna:

        {item_id: {"lotes": [{"validade": date, "qtd": int}, ...],
                   "sem_validade": int}}

    A soma dos lotes + sem_validade sempre fecha com o saldo total.
    Itens sem nenhuma entrada com validade não aparecem no resultado.
    """
    if item_ids is not None and not item_ids:
        return {}
    query = db.session.query(
        Movimentacao.item_id,
        Movimentacao.tipo,
        Movimentacao.quantidade,
        Movimentacao.validade,
    )
    if item_ids is not None:
        query = query.filter(Movimentacao.item_id.in_(item_ids))
    movs = query.order_by(
        Movimentacao.item_id, Movimentacao.validade, Movimentacao.id
    ).all()

    lotes = defaultdict(list)  # item_id -> [(validade, quantidade)]
    consumo = defaultdict(int)
    saldo = defaultdict(int)
    for item_id, tipo, quantidade, validade in movs:
        if tipo == "saida":
            saldo[item_id] -= quantidade
            consumo[item_id] += quantidade
        elif tipo == "ajuste":
            saldo[item_id] += quantidade  # quantidade já vem com sinal
            if quantidade < 0:
                consumo[item_id] += -quantidade
        elif validade is not None:  # entrada com validade vira lote
            saldo[item_id] += quantidade
            lotes[item_id].append([validade, quantidade])

    resultado = {}
    for item_id, lista in lotes.items():
        resto = consumo.get(item_id, 0)
        for lote in lista:  # já ordenadas por validade, depois id
            lote[1], resto = max(0, lote[1] - resto), max(0, resto - lote[1])
        restante_em_lotes = sum(l[1] for l in lista)
        resultado[item_id] = {
            "lotes": [
                {"validade": v, "qtd": q} for v, q in lista if q > 0
            ],
            "sem_validade": max(
                0, saldo.get(item_id, 0) - restante_em_lotes
            ),
        }
    return resultado


def opcoes_autocomplete():
    """Pares (nome, codigo) dos itens ativos para o autocomplete nativo
    (datalist) dos campos de busca."""
    return [
        (nome, codigo)
        for nome, codigo in Item.query.with_entities(Item.nome, Item.codigo)
        .filter_by(ativo=True)
        .order_by(Item.nome)
        .all()
    ]


def valores_unicos(coluna):
    """Valores distintos já usados numa coluna, para autocomplete de campos."""
    return [
        linha[0]
        for linha in db.session.query(coluna)
        .filter(coluna.isnot(None), coluna != "")
        .distinct()
        .order_by(coluna)
        .all()
    ]


def resolver_item(texto):
    """Resolve texto digitado (código ou nome) para um item.

    Retorna (item, alternativas): casou com exatamente um item → `item`
    preenchido e alternativas vazia. Senão, `item` é None e `alternativas`
    lista os candidatos (vazia = nada encontrado).
    """
    texto = (texto or "").strip()
    if not texto:
        return None, []

    item = Item.query.filter_by(codigo=texto).first()
    if item is not None:
        return item, []

    exatos = Item.query.filter(db.func.lower(Item.nome) == texto.lower()).all()
    if len(exatos) == 1:
        return exatos[0], []

    padrao = f"%{texto}%"
    contem = (
        Item.query.filter(Item.nome.ilike(padrao))
        .order_by(Item.nome)
        .limit(12)
        .all()
    )
    if len(contem) == 1:
        return contem[0], []
    return None, contem or exatos
