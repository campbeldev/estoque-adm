"""Testes de fluxo do sistema (smoke tests) com banco SQLite temporário."""
import base64
import os
import re
import tempfile
import unittest
import zlib
from datetime import date

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    Categoria,
    Funcionario,
    Item,
    Movimentacao,
    Nota,
    Obra,
    Usuario,
    saldo_do_item,
    saldos_por_lote,
)


class BaseTeste(unittest.TestCase):
    def setUp(self):
        fd, self.caminho_banco = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.caminho_banco)  # o SQLAlchemy cria o arquivo sozinho
        self.pasta_backup = tempfile.mkdtemp()

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "chave-de-teste",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///"
                + self.caminho_banco.replace(os.sep, "/"),
                "ESTOQUE_DB_PATH": self.caminho_banco,
                "BACKUP_DIR": self.pasta_backup,
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            db.create_all()
            db.session.add(Categoria(nome="EPI"))
            db.session.add(
                Usuario(
                    login="admin",
                    nome="Administrador",
                    perfil="admin",
                    senha_hash=generate_password_hash("senha123"),
                )
            )
            db.session.add(
                Usuario(
                    login="operador",
                    nome="Operador",
                    perfil="operador",
                    senha_hash=generate_password_hash("senha123"),
                )
            )
            db.session.commit()
        self.cliente = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()  # libera o arquivo no Windows
        for sufixo in ("", "-wal", "-shm"):
            caminho = self.caminho_banco + sufixo
            try:
                if os.path.exists(caminho):
                    os.unlink(caminho)
            except PermissionError:
                pass

    def logar(self, login="admin", senha="senha123"):
        return self.cliente.post(
            "/login", data={"login": login, "senha": senha}, follow_redirects=True
        )

    def criar_item(self, nome="Capacete de Segurança", minimo=10):
        with self.app.app_context():
            categoria = Categoria.query.first()
            item = Item(
                nome=nome, categoria_id=categoria.id, unidade="un",
                estoque_minimo=minimo, codigo="",  # placeholder até o flush
            )
            db.session.add(item)
            db.session.flush()
            item.codigo = f"EV{item.id:06d}"
            db.session.commit()
            return item.id, item.codigo

    def dar_entrada(self, codigo=None, item_id=None, quantidade=5, **extras):
        dados = {
            "codigo": codigo or "",
            "item_id": item_id or "",
            "quantidade": quantidade,
            "fornecedor": "Fornecedor Teste",
            "numero_nota": "NF-0001",
            "serie": "1",
            "valor_unitario": "12,50",
            "validade": "2030-06-15",  # EPI exige validade do lote na entrada
            "data": "",
        }
        dados.update(extras)
        return self.cliente.post(
            "/entradas/", data=dados, follow_redirects=True
        )


class TesteAutenticacao(BaseTeste):
    def test_senha_errada_rejeitada(self):
        resposta = self.logar(senha="errada")
        self.assertIn("inválidos".encode(), resposta.data)

    def test_login_admin_vai_para_estoque(self):
        resposta = self.logar()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Estoque atual".encode(), resposta.data)

    def test_login_operador_vai_para_pos(self):
        resposta = self.logar(login="operador")
        self.assertIn("Leitura de código".encode(), resposta.data)

    def test_operador_nao_acessa_itens(self):
        self.logar(login="operador")
        resposta = self.cliente.get("/itens/")
        self.assertEqual(resposta.status_code, 403)

    def test_nao_logado_redireciona(self):
        resposta = self.cliente.get("/estoque/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])

    def test_troca_forcada_de_senha(self):
        with self.app.app_context():
            admin = Usuario.query.filter_by(login="admin").first()
            admin.forcar_troca = True
            db.session.commit()
        resposta = self.logar()
        self.assertIn("Alterar senha".encode(), resposta.data)
        # troca a senha e volta para a página inicial
        resposta = self.cliente.post(
            "/alterar-senha",
            data={
                "senha_atual": "senha123",
                "senha_nova": "novasenha",
                "senha_confirmacao": "novasenha",
            },
            follow_redirects=True,
        )
        self.assertIn("Estoque atual".encode(), resposta.data)


class TesteItens(BaseTeste):
    def test_novo_item_gera_codigo_automatico(self):
        self.logar()
        self.cliente.post(
            "/itens/novo",
            data={
                "nome": "Luva de Raspa",
                "categoria_id": 1,  # EPI — exige CA
                "unidade": "pc",
                "estoque_minimo": 20,
                "codigo": "",
                "tamanho": "",
                "ca": "12345",
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            item = Item.query.filter_by(nome="Luva de Raspa").first()
            self.assertIsNotNone(item)
            self.assertEqual(item.codigo, f"EV{item.id:06d}")

    def test_codigo_duplicado_rejeitado(self):
        self.logar()
        _, codigo = self.criar_item()
        self.cliente.post(
            "/itens/novo",
            data={
                "nome": "Outro Item",
                "categoria_id": 1,
                "unidade": "un",
                "estoque_minimo": 0,
                "codigo": codigo,
                "tamanho": "",
                "ca": "12345",
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            self.assertEqual(Item.query.count(), 1)

    def test_epi_exige_ca(self):
        self.logar()
        resposta = self.cliente.post(
            "/itens/novo",
            data={
                "nome": "Capacete de Segurança",
                "categoria_id": 1,  # EPI
                "unidade": "un",
                "estoque_minimo": 0,
                "codigo": "",
                "tamanho": "",
                "ca": "",
            },
            follow_redirects=True,
        )
        self.assertIn("Itens de EPI exigem o CA".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Item.query.count(), 0)


class TesteFuncionarios(BaseTeste):
    def test_empresa_obrigatoria(self):
        self.logar()
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "Sem Empresa", "matricula": "M1", "empresa": "", "cargo": ""},
            follow_redirects=True,
        )
        self.assertIn("Informe a empresa".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Funcionario.query.count(), 0)

    def test_matricula_obrigatoria(self):
        self.logar()
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "Sem Matrícula", "matricula": "", "empresa": "Alfa", "cargo": ""},
            follow_redirects=True,
        )
        self.assertIn("Informe a matrícula".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Funcionario.query.count(), 0)

    def test_matricula_duplicada_rejeitada_mesma_empresa(self):
        self.logar()
        self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "João", "matricula": "001", "empresa": "Alfa", "cargo": "Pedreiro"},
        )
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "Maria", "matricula": "001", "empresa": "Alfa", "cargo": "Engenheira"},
            follow_redirects=True,
        )
        self.assertIn(
            "Já existe um funcionário com esta matrícula nesta empresa".encode(),
            resposta.data,
        )
        with self.app.app_context():
            self.assertEqual(Funcionario.query.count(), 1)

    def test_matricula_repetida_em_empresa_diferente_permitida(self):
        self.logar()
        self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "João", "matricula": "001", "empresa": "Alfa", "cargo": "Pedreiro"},
        )
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "Maria", "matricula": "001", "empresa": "Beta", "cargo": "Engenheira"},
            follow_redirects=True,
        )
        self.assertIn("Funcionário criado: Maria".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Funcionario.query.count(), 2)

    def test_cargo_obrigatorio(self):
        self.logar()
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "Sem Cargo", "matricula": "M1", "empresa": "Alfa", "cargo": ""},
            follow_redirects=True,
        )
        self.assertIn("Informe o cargo".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Funcionario.query.count(), 0)

    def test_criar_funcionario_com_empresa_e_cargo(self):
        self.logar()
        resposta = self.cliente.post(
            "/funcionarios/novo",
            data={"nome": "João", "matricula": "001", "empresa": "Construtora Alfa",
                  "cargo": "Pedreiro"},
            follow_redirects=True,
        )
        self.assertIn("Funcionário criado".encode(), resposta.data)
        with self.app.app_context():
            funcionario = Funcionario.query.first()
            self.assertEqual(funcionario.empresa, "Construtora Alfa")
            self.assertEqual(funcionario.matricula, "001")
            self.assertEqual(funcionario.cargo, "Pedreiro")


class TesteObras(BaseTeste):
    def test_nome_obrigatorio(self):
        self.logar()
        resposta = self.cliente.post(
            "/obras/novo",
            data={"nome": ""},
            follow_redirects=True,
        )
        self.assertIn("Informe o nome da obra".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Obra.query.count(), 0)

    def test_criar_obra(self):
        self.logar()
        resposta = self.cliente.post(
            "/obras/novo",
            data={"nome": "Edifício Central"},
            follow_redirects=True,
        )
        self.assertIn("Obra criada".encode(), resposta.data)
        with self.app.app_context():
            obra = Obra.query.first()
            self.assertEqual(obra.nome, "Edifício Central")


class TesteMovimentacoes(BaseTeste):
    def test_entrada_atualiza_saldo(self):
        self.logar()
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=50)
        resposta = self.cliente.get("/estoque/")
        self.assertIn(b">50<", resposta.data)

    def test_ajuste_remove_e_bloqueia_negativo(self):
        self.logar()
        item_id, _ = self.criar_item()
        self.dar_entrada(item_id=item_id, quantidade=5)

        # remover 6 com saldo 5 → bloqueado
        resposta = self.cliente.post(
            "/estoque/ajuste",
            data={
                "item_id": item_id,
                "quantidade": 6,
                "direcao": "remover",
                "motivo": "teste",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Saldo insuficiente", resposta.data)

        # remover 2 → saldo 3
        self.cliente.post(
            "/estoque/ajuste",
            data={
                "item_id": item_id,
                "quantidade": 2,
                "direcao": "remover",
                "motivo": "quebra em obra",
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            self.assertEqual(saldo_do_item(item_id), 3)


class TestePos(BaseTeste):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            db.session.add(
                Funcionario(
                    nome="João da Silva",
                    matricula="001",
                    empresa="Construtora Alfa",
                )
            )
            db.session.add(Obra(nome="Obra Central"))
            db.session.commit()

    def test_pacote_e_finalizar(self):
        self.logar(login="operador")
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=10)

        for _ in range(3):
            resposta = self.cliente.post(
                "/pos/adicionar", data={"codigo": codigo}, follow_redirects=True
            )
            self.assertIn(b"Adicionado ao pacote", resposta.data)
        # o pacote mostra o valor estimado (3 × custo médio de 12,50)
        self.assertIn(b"Total estimado", resposta.data)
        self.assertIn(b"R$ 37,50", resposta.data)

        resposta = self.cliente.post(
            "/pos/finalizar",
            data={"funcionario": "João da Silva", "obra_id": 1, "modo_rapido": ""},
            follow_redirects=True,
        )
        self.assertIn("Saída registrada".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 7)
            mov = Movimentacao.query.filter_by(tipo="saida").first()
            self.assertEqual(mov.quantidade, 3)
            self.assertEqual(mov.funcionario_id, 1)
            self.assertEqual(mov.usuario.login, "operador")
            # a saída carrega o custo médio da entrada (12,50)
            self.assertEqual(mov.valor_unitario_cents, 1250)

    def test_finalizar_bloqueia_saldo_insuficiente(self):
        self.logar(login="operador")
        item_id, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)

        self.cliente.post("/pos/adicionar", data={"codigo": codigo})
        self.cliente.post(
            "/pos/atualizar", data={f"qtd_{item_id}": 9}, follow_redirects=True
        )
        resposta = self.cliente.post(
            "/pos/finalizar",
            data={"funcionario": "João da Silva", "obra_id": 1, "modo_rapido": ""},
            follow_redirects=True,
        )
        self.assertIn(b"Saldo insuficiente", resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.filter_by(tipo="saida").count(), 0)

    def test_modo_rapido_baixa_direto(self):
        self.logar(login="operador")
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)

        resposta = self.cliente.post(
            "/pos/adicionar",
            data={"codigo": codigo, "modo_rapido": "on", "funcionario": "João da Silva", "obra_id": 1},
            follow_redirects=True,
        )
        self.assertIn("Saída registrada".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 4)
            saida = Movimentacao.query.filter_by(tipo="saida").first()
            self.assertEqual(saida.valor_unitario_cents, 1250)

    def test_finalizar_funcionario_ambiguo_bloqueia(self):
        self.logar(login="operador")
        with self.app.app_context():
            db.session.add(
                Funcionario(
                    nome="Maria Souza",
                    matricula="001",  # mesma matrícula em outra empresa
                    empresa="Engenharia Beta",
                    cargo="Engenheira",
                )
            )
            db.session.commit()
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)
        self.cliente.post("/pos/adicionar", data={"codigo": codigo})
        resposta = self.cliente.post(
            "/pos/finalizar",
            data={"funcionario": "001", "obra_id": 1, "modo_rapido": ""},
            follow_redirects=True,
        )
        self.assertIn(b"V\xc3\xa1rios funcion\xc3\xa1rios", resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.filter_by(tipo="saida").count(), 0)


class TesteBuscaPorNome(BaseTeste):
    def test_saida_pelo_nome(self):
        self.logar(login="operador")
        _, codigo = self.criar_item("Luva de Raspa")
        self.dar_entrada(codigo=codigo, quantidade=5)
        resposta = self.cliente.post(
            "/pos/adicionar", data={"codigo": "Luva de Raspa"}, follow_redirects=True
        )
        self.assertIn("Adicionado ao pacote: Luva de Raspa".encode(), resposta.data)

    def test_saida_nome_ambiguo_mostra_sugestoes(self):
        self.logar(login="operador")
        self.criar_item("Luva de Raspa")
        self.criar_item("Luva Nitrílica")
        resposta = self.cliente.post(
            "/pos/adicionar", data={"codigo": "Luva"}, follow_redirects=True
        )
        self.assertIn("Correspondências".encode(), resposta.data)
        self.assertIn("Luva de Raspa".encode(), resposta.data)
        self.assertIn("Luva Nitrílica".encode(), resposta.data)

    def test_entrada_pelo_nome(self):
        self.logar()
        self.criar_item("Capacete de Segurança")
        resposta = self.cliente.post(
            "/entradas/",
            data={
                "codigo": "Capacete de Segurança",
                "item_id": "",
                "quantidade": 7,
                "fornecedor": "Fornecedor X",
                "numero_nota": "NF-0007",
                "serie": "1",
                "valor_unitario": "8,00",
                "validade": "2030-06-15",
                "data": "",
            },
            follow_redirects=True,
        )
        self.assertIn("Entrada registrada: Capacete".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 7)

    def test_entrada_nome_ambiguo_lista_alternativas(self):
        self.logar()
        self.criar_item("Luva de Raspa")
        self.criar_item("Luva Nitrílica")
        resposta = self.cliente.post(
            "/entradas/",
            data={
                "codigo": "Luva",
                "item_id": "",
                "quantidade": 3,
                "fornecedor": "X",
                "numero_nota": "",
                "serie": "",
                "valor_unitario": "2,00",
                "data": "",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Qual item?".encode(), resposta.data)
        self.assertIn("Luva Nitrílica".encode(), resposta.data)
        # o fornecedor digitado é preservado ao escolher a alternativa
        self.assertIn('value="X"'.encode(), resposta.data)


class TesteEntradas(BaseTeste):
    def _postar(self, **alteracoes):
        """Entrada por item_id com os campos novos já preenchidos."""
        return self.dar_entrada(item_id=1, **alteracoes)

    def test_campos_obrigatorios(self):
        self.logar()
        self.criar_item()
        for campo, mensagem in [
            ("numero_nota", "número da nota"),
            ("serie", "série da nota"),
            ("valor_unitario", "Valor unitário inválido"),
        ]:
            with self.subTest(campo=campo):
                resposta = self._postar(**{campo: ""})
                self.assertIn(mensagem.encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.count(), 0)
            self.assertEqual(Nota.query.count(), 0)

    def test_valor_unitario_invalido(self):
        self.logar()
        self.criar_item()
        for valor in ("abc", "0", "-5"):
            with self.subTest(valor=valor):
                resposta = self._postar(valor_unitario=valor)
                self.assertIn("Valor unitário inválido".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.count(), 0)

    def test_itens_da_mesma_nota_se_agrupam(self):
        self.logar()
        self.criar_item()
        self._postar(quantidade=2, valor_unitario="10,00")
        self._postar(quantidade=3, valor_unitario="20,50")
        with self.app.app_context():
            self.assertEqual(Nota.query.count(), 1)
            movs = Movimentacao.query.all()
            self.assertEqual(len(movs), 2)
            self.assertEqual(movs[0].nota_id, movs[1].nota_id)
            self.assertEqual(movs[0].valor_unitario_cents, 1000)
            self.assertEqual(movs[1].valor_unitario_cents, 2050)

    def test_mesma_nota_outro_fornecedor_bloqueada(self):
        self.logar()
        self.criar_item()
        self._postar()
        resposta = self._postar(fornecedor="Outro Fornecedor")
        self.assertIn("Já existe a nota".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Nota.query.count(), 1)
            self.assertEqual(Movimentacao.query.count(), 1)

    def test_fornecedor_maiusculo_reusa_nota(self):
        self.logar()
        self.criar_item()
        self._postar(fornecedor="Fornecedor ABC")
        self._postar(fornecedor="fornecedor abc")
        with self.app.app_context():
            self.assertEqual(Nota.query.count(), 1)
            self.assertEqual(Movimentacao.query.count(), 2)

    def test_ultima_nota_prepreenchida(self):
        self.logar()
        self.criar_item()
        self._postar()
        resposta = self.cliente.get("/entradas/")
        self.assertIn(b'name="numero_nota" value="NF-0001"', resposta.data)
        self.assertIn(b'name="serie" value="1"', resposta.data)

    def test_total_exibido_na_tela(self):
        self.logar()
        self.criar_item()
        resposta = self._postar(quantidade=5, valor_unitario="12,50")
        self.assertIn("R$ 62,50".encode(), resposta.data)


class TesteNotas(BaseTeste):
    def test_listar_admin_e_bloquear_operador(self):
        self.logar()
        self.criar_item()
        self.dar_entrada(item_id=1, quantidade=5)
        resposta = self.cliente.get("/notas/")
        self.assertIn("NF-0001".encode(), resposta.data)
        self.assertIn("Fornecedor Teste".encode(), resposta.data)
        self.assertIn("R$ 62,50".encode(), resposta.data)

        self.cliente.post("/logout")
        self.logar(login="operador")
        self.assertEqual(self.cliente.get("/notas/").status_code, 403)
        self.assertEqual(self.cliente.get("/notas/1").status_code, 403)

    def test_detalhe_da_nota(self):
        self.logar()
        self.criar_item()
        self.dar_entrada(item_id=1, quantidade=2, valor_unitario="15,00")
        resposta = self.cliente.get("/notas/1")
        self.assertIn("Capacete de Segurança".encode(), resposta.data)
        self.assertIn("R$ 15,00".encode(), resposta.data)
        self.assertIn("R$ 30,00".encode(), resposta.data)
        self.assertEqual(self.cliente.get("/notas/999").status_code, 404)


class TesteMigracao(BaseTeste):
    def test_migra_banco_com_schema_antigo(self):
        """Banco criado antes das notas ganha colunas novas e backfill."""
        import sqlite3

        # libera o arquivo do app original antes de recriá-lo
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        os.unlink(self.caminho_banco)

        conn = sqlite3.connect(self.caminho_banco)
        conn.executescript(
            """
            CREATE TABLE usuario (
                id INTEGER PRIMARY KEY, login VARCHAR(50) NOT NULL UNIQUE,
                nome VARCHAR(100) NOT NULL, senha_hash VARCHAR(255) NOT NULL,
                perfil VARCHAR(10) NOT NULL, ativo BOOLEAN NOT NULL,
                forcar_troca BOOLEAN NOT NULL, data_criacao DATETIME NOT NULL
            );
            CREATE TABLE categoria (
                id INTEGER PRIMARY KEY, nome VARCHAR(60) NOT NULL UNIQUE
            );
            CREATE TABLE item (
                id INTEGER PRIMARY KEY, nome VARCHAR(120) NOT NULL,
                categoria_id INTEGER NOT NULL, unidade VARCHAR(5) NOT NULL,
                estoque_minimo INTEGER NOT NULL,
                codigo VARCHAR(30) NOT NULL UNIQUE,
                tamanho VARCHAR(10), validade DATE, ca VARCHAR(30),
                ativo BOOLEAN NOT NULL, data_criacao DATETIME NOT NULL
            );
            CREATE TABLE movimentacao (
                id INTEGER PRIMARY KEY, tipo VARCHAR(10) NOT NULL,
                quantidade INTEGER NOT NULL, item_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL, funcionario_id INTEGER,
                obra_id INTEGER, fornecedor VARCHAR(120),
                nota_fiscal VARCHAR(30), observacao VARCHAR(255),
                data DATETIME NOT NULL
            );
            INSERT INTO usuario (id, login, nome, senha_hash, perfil, ativo,
                                 forcar_troca, data_criacao)
                VALUES (1, 'admin', 'Administrador', 'x', 'admin', 1, 0,
                        '2026-01-01 10:00:00');
            INSERT INTO categoria (id, nome) VALUES (1, 'EPI');
            INSERT INTO item (id, nome, categoria_id, unidade, estoque_minimo,
                              codigo, ativo, data_criacao)
                VALUES (1, 'Capacete', 1, 'un', 0, 'EV000001', 1,
                        '2026-01-01 10:00:00');
            INSERT INTO movimentacao (id, tipo, quantidade, item_id,
                                      usuario_id, fornecedor, nota_fiscal, data)
                VALUES (1, 'entrada', 5, 1, 1, 'Fornecedor Antigo', 'NF-100',
                        '2026-01-02 10:00:00'),
                       (2, 'entrada', 3, 1, 1, 'Fornecedor Antigo', 'NF-100',
                        '2026-01-02 11:00:00'),
                       (3, 'saida', 1, 1, 1, NULL, NULL,
                        '2026-01-03 10:00:00');
            """
        )
        conn.commit()
        conn.close()

        # o create_app roda a migração sozinho — este é o caminho real
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "chave-de-teste",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///"
                + self.caminho_banco.replace(os.sep, "/"),
                "ESTOQUE_DB_PATH": self.caminho_banco,
                "BACKUP_DIR": self.pasta_backup,
                "WTF_CSRF_ENABLED": False,
            }
        )
        try:
            with app.app_context():
                colunas = {
                    linha[1]
                    for linha in db.session.execute(
                        db.text("PRAGMA table_info(movimentacao)")
                    )
                }
                self.assertIn("nota_id", colunas)
                self.assertIn("valor_unitario_cents", colunas)

                self.assertEqual(Nota.query.count(), 1)
                nota = Nota.query.first()
                self.assertEqual(nota.numero, "NF-100")
                self.assertEqual(nota.serie, "")
                self.assertEqual(nota.fornecedor, "Fornecedor Antigo")
                vinculadas = Movimentacao.query.filter(
                    Movimentacao.nota_id.isnot(None)
                ).count()
                self.assertEqual(vinculadas, 2)
                saida = Movimentacao.query.filter_by(tipo="saida").first()
                self.assertIsNone(saida.nota_id)

                # idempotência: rodar de novo não duplica nada
                from app.migracao import migrar_leve

                migrar_leve()
                self.assertEqual(Nota.query.count(), 1)
                self.assertEqual(
                    Movimentacao.query.filter(
                        Movimentacao.nota_id.isnot(None)
                    ).count(),
                    2,
                )
        finally:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


class TesteTamanhoNaBusca(BaseTeste):
    def _criar_com_tamanho(self, nome="Camisa Azul", tamanho="P"):
        with self.app.app_context():
            categoria = Categoria.query.first()
            item = Item(
                nome=nome, categoria_id=categoria.id, unidade="un",
                estoque_minimo=0, codigo="", tamanho=tamanho,
            )
            db.session.add(item)
            db.session.flush()
            item.codigo = f"EV{item.id:06d}"
            db.session.commit()
            return item.id, item.codigo

    def test_autocomplete_exibe_nome_com_tamanho(self):
        self.logar()
        self._criar_com_tamanho()
        resposta = self.cliente.get("/estoque/")
        self.assertIn(b'value="Camisa Azul P"', resposta.data)

    def test_entrada_pelo_nome_com_tamanho(self):
        self.logar()
        self._criar_com_tamanho()
        resposta = self.cliente.post(
            "/entradas/",
            data={
                "codigo": "Camisa Azul P",
                "item_id": "",
                "quantidade": 2,
                "fornecedor": "Fornecedor X",
                "numero_nota": "NF-0009",
                "serie": "1",
                "valor_unitario": "45,00",
                "validade": "2030-06-15",
                "data": "",
            },
            follow_redirects=True,
        )
        self.assertIn("Entrada registrada: Camisa Azul".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 2)

    def test_busca_no_estoque_com_tamanho(self):
        self.logar()
        self._criar_com_tamanho()
        resposta = self.cliente.get(
            "/estoque/", query_string={"busca": "Camisa Azul P"}
        )
        self.assertIn(b"Camisa Azul", resposta.data)
        # a busca só pelo nome continua funcionando
        resposta = self.cliente.get(
            "/estoque/", query_string={"busca": "Camisa Azul"}
        )
        self.assertIn(b"Camisa Azul", resposta.data)


class TesteValidade(BaseTeste):
    def test_entrada_epi_sem_validade_bloqueia(self):
        """A validade é do lote: EPI sem validade na entrada é recusado."""
        self.logar()
        self.criar_item()
        resposta = self.dar_entrada(item_id=1, validade="")
        self.assertIn(
            "exigem a data de validade do lote".encode(), resposta.data
        )
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.count(), 0)

    def test_entrada_com_validade_explicita(self):
        self.logar()
        self.criar_item()
        self.dar_entrada(item_id=1, validade="2027-01-01")
        with self.app.app_context():
            mov = Movimentacao.query.filter_by(tipo="entrada").first()
            self.assertEqual(mov.validade, date(2027, 1, 1))

    def test_entrada_com_validade_invalida_bloqueia(self):
        self.logar()
        self.criar_item()
        resposta = self.dar_entrada(item_id=1, validade="xx/yy/zzzz")
        self.assertIn("Data de validade inválida".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.count(), 0)

    def test_saldos_por_lote_fifo(self):
        """PEPS: o lote mais antigo é consumido primeiro pelas saídas."""
        self.logar()
        self.criar_item()
        with self.app.app_context():
            db.session.add_all(
                [
                    Movimentacao(
                        tipo="entrada", quantidade=10, item_id=1,
                        usuario_id=1, validade=date(2026, 1, 1),
                    ),
                    Movimentacao(
                        tipo="saida", quantidade=7, item_id=1,
                        usuario_id=1, valor_unitario_cents=100,
                    ),
                    Movimentacao(
                        tipo="entrada", quantidade=5, item_id=1,
                        usuario_id=1, validade=date(2027, 1, 1),
                    ),
                ]
            )
            db.session.commit()
            lotes = saldos_por_lote([1])[1]
            self.assertEqual(
                [(l["validade"], l["qtd"]) for l in lotes["lotes"]],
                [(date(2026, 1, 1), 3), (date(2027, 1, 1), 5)],
            )
            self.assertEqual(lotes["sem_validade"], 0)

    def test_estoque_mostra_vencimentos(self):
        self.logar()
        self.criar_item()
        self.dar_entrada(item_id=1, quantidade=5, validade="2020-01-01")
        resposta = self.cliente.get("/estoque/")
        self.assertIn("5 × 01/01/2020".encode(), resposta.data)
        self.assertIn("VENCIDO".encode(), resposta.data)


class TesteUI(BaseTeste):
    def test_pos_tem_campo_de_leitura_maior(self):
        self.logar(login="operador")
        resposta = self.cliente.get("/pos/")
        self.assertIn("input-leitura".encode(), resposta.data)
        self.assertIn(
            "Digite o nome do produto ou código".encode(), resposta.data
        )

    def test_entradas_e_estoque_ui(self):
        self.logar()
        resposta = self.cliente.get("/entradas/")
        self.assertIn(
            "Código ou nome do produto".encode(), resposta.data
        )
        self.assertIn(b'list="sugestoes-itens"', resposta.data)
        resposta = self.cliente.get("/estoque/")
        # busca de tamanho normal, com autocomplete
        self.assertIn(b'class="form-control" name="busca"', resposta.data)
        self.assertIn(b'<datalist id="sugestoes-itens"', resposta.data)

    def test_autocomplete_lista_nomes_dos_itens(self):
        self.logar()
        self.criar_item("Capacete de Segurança")
        resposta = self.cliente.get("/estoque/")
        self.assertIn(b'<option value="Capacete de Seguran', resposta.data)
        self.assertIn(b'<option value="EV000001"', resposta.data)

    def test_autocomplete_em_todos_os_campos(self):
        self.logar()
        resposta = self.cliente.get("/entradas/")
        self.assertIn(b'list="sugestoes-fornecedores"', resposta.data)
        resposta = self.cliente.get("/funcionarios/novo")
        self.assertIn(b'list="sugestoes-f-empresas"', resposta.data)
        resposta = self.cliente.get("/funcionarios")
        self.assertIn(b'list="sugestoes-busca-f"', resposta.data)
        resposta = self.cliente.get("/obras")
        self.assertIn(b'list="sugestoes-busca-obra"', resposta.data)
        resposta = self.cliente.get("/estoque/ajuste")
        self.assertIn(b'list="sugestoes-motivos"', resposta.data)

    def test_pwa_manifest_e_service_worker(self):
        resposta = self.cliente.get("/static/manifest.webmanifest")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(b'"name": "Controle de Estoque"', resposta.data)
        resposta = self.cliente.get("/sw.js")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers.get("Service-Worker-Allowed"), "/")
        resposta = self.cliente.get("/static/img/icon-192.png")
        self.assertEqual(resposta.status_code, 200)

    def test_campos_sem_autocomplete_desnecessario(self):
        self.logar()
        # cadastros novos não sugerem valores únicos (nome, código, matrícula…)
        resposta = self.cliente.get("/itens/novo")
        self.assertNotIn(b"list=", resposta.data)
        resposta = self.cliente.get("/obras/novo")
        self.assertNotIn(b"list=", resposta.data)
        resposta = self.cliente.get("/usuarios/novo")
        self.assertNotIn(b"list=", resposta.data)
        resposta = self.cliente.get("/funcionarios/novo")
        self.assertNotIn(b'sugestoes-f-matriculas', resposta.data)


class TesteRelatorioPorFuncionario(BaseTeste):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            db.session.add(
                Funcionario(
                    nome="João da Silva",
                    matricula="001",
                    empresa="Construtora Alfa",
                    cargo="Pedreiro",
                )
            )
            db.session.add(Obra(nome="Obra Central"))
            db.session.commit()

    @staticmethod
    def _conteudo_dos_streams(pdf_bytes):
        """Descomprime os streams de conteúdo do PDF (A85 + Flate, ou só Flate)."""
        conteudo = b""
        for trecho in re.findall(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
            dados = trecho.strip()
            try:
                dados = base64.a85decode(dados, adobe=True)
            except ValueError:
                pass  # stream só com Flate
            try:
                conteudo += zlib.decompress(dados)
            except zlib.error:
                pass
        return conteudo

    def _fazer_retirada(self, codigo):
        self.dar_entrada(codigo=codigo, quantidade=5)
        self.cliente.post("/pos/adicionar", data={"codigo": codigo})
        self.cliente.post(
            "/pos/finalizar",
            data={"funcionario": "João da Silva", "obra_id": 1, "modo_rapido": ""},
        )

    def test_retiradas_do_funcionario(self):
        self.logar()
        _, codigo = self.criar_item("Capacete de Segurança")
        self._fazer_retirada(codigo)
        resposta = self.cliente.get("/relatorios/por-funcionario?funcionario=001")
        self.assertIn("João da Silva".encode(), resposta.data)
        self.assertIn("Pedreiro".encode(), resposta.data)
        self.assertIn("Capacete de Segurança".encode(), resposta.data)
        self.assertIn("Total de itens retirados".encode(), resposta.data)
        # a retirada tem valor: custo médio da entrada (12,50)
        self.assertIn("R$ 12,50".encode(), resposta.data)

    def test_busca_ambigua_sugere_seletor(self):
        self.logar()
        with self.app.app_context():
            db.session.add(
                Funcionario(
                    nome="João Carlos",
                    matricula="002",
                    empresa="Engenharia Beta",
                    cargo="Eletricista",
                )
            )
            db.session.commit()
        resposta = self.cliente.get("/relatorios/por-funcionario?funcionario=João")
        self.assertIn("Vários funcionários".encode(), resposta.data)

    def test_exportar_csv_retiradas(self):
        self.logar()
        _, codigo = self.criar_item("Capacete de Segurança")
        self._fazer_retirada(codigo)
        resposta = self.cliente.get(
            "/relatorios/por-funcionario?funcionario=001&exportar=1"
        )
        texto = resposta.data.decode("utf-8")
        self.assertTrue(texto.startswith("﻿"))
        self.assertIn("Data;Produto;Quantidade", texto)
        self.assertIn("Capacete de Segurança", texto)
        self.assertIn("R$ 12,50", texto)

    def test_pdf_relatorio_funcionario(self):
        self.logar()
        _, codigo = self.criar_item("Capacete de Segurança")
        self._fazer_retirada(codigo)
        resposta = self.cliente.get(
            "/relatorios/por-funcionario?funcionario=001&pdf=1"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.mimetype, "application/pdf")
        self.assertTrue(resposta.data.startswith(b"%PDF"))
        conteudo = self._conteudo_dos_streams(resposta.data)
        # o reportlab grava acentos em octal (\343 = ã) — confere trechos sem acento
        self.assertIn(b"da Silva", conteudo)
        self.assertIn(b"Pedreiro", conteudo)
        self.assertIn(b"Capacete de Seguran", conteudo)
        self.assertIn(b"TOTAL DE ITENS", conteudo)
        self.assertIn(b"R$", conteudo)  # total em R$ na última coluna


class TesteRelatorios(BaseTeste):
    def test_csv_exportado(self):
        self.logar()
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)

        resposta = self.cliente.get("/relatorios/movimentacoes?exportar=1")
        self.assertEqual(resposta.status_code, 200)
        texto = resposta.data.decode("utf-8")
        self.assertTrue(texto.startswith("﻿"))
        self.assertIn("Data;Tipo;Item", texto)
        self.assertIn("Capacete de Segurança", texto)
        # a nota aparece agrupada (número + série) e com os valores
        self.assertIn("NF-0001 (série 1)", texto)
        self.assertIn("R$ 12,50", texto)
        self.assertIn("R$ 62,50", texto)


class TesteBackup(BaseTeste):
    def test_comando_backup_cria_copia(self):
        executor = self.app.test_cli_runner()
        resultado = executor.invoke(args=["backup"])
        self.assertEqual(resultado.exit_code, 0, resultado.output)
        arquivos = os.listdir(self.pasta_backup)
        self.assertEqual(len(arquivos), 1)
        self.assertTrue(arquivos[0].startswith("estoque_"))
        self.assertTrue(arquivos[0].endswith(".db"))


if __name__ == "__main__":
    unittest.main()
