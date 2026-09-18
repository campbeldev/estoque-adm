"""Testes de fluxo do sistema (smoke tests) com banco SQLite temporário."""
import base64
import os
import tempfile
import unittest
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    Categoria,
    Entregador,
    EventoRemessa,
    Item,
    Movimentacao,
    Nota,
    Obra,
    Remessa,
    Setor,
    Usuario,
    saldo_do_item,
)


class BaseTeste(unittest.TestCase):
    def setUp(self):
        fd, self.caminho_banco = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.caminho_banco)  # o SQLAlchemy cria o arquivo sozinho
        self.pasta_backup = tempfile.mkdtemp()
        self.pasta_comprovantes = tempfile.mkdtemp()

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "chave-de-teste",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///"
                + self.caminho_banco.replace(os.sep, "/"),
                "ESTOQUE_DB_PATH": self.caminho_banco,
                "BACKUP_DIR": self.pasta_backup,
                "COMPROVANTES_DIR": self.pasta_comprovantes,
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            db.create_all()
            db.session.add(Categoria(nome="Material de Escritório"))
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
                "nome": "Papel Sulfite A4",
                "categoria_id": 1,
                "unidade": "pc",
                "estoque_minimo": 20,
                "codigo": "",
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            item = Item.query.filter_by(nome="Papel Sulfite A4").first()
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
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            self.assertEqual(Item.query.count(), 1)


class TesteEntregadores(BaseTeste):
    def test_nome_obrigatorio(self):
        self.logar()
        resposta = self.cliente.post(
            "/entregadores/novo",
            data={"nome": "", "contato": ""},
            follow_redirects=True,
        )
        self.assertIn("Informe o nome do entregador".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Entregador.query.count(), 0)

    def test_criar_entregador_sem_contato(self):
        self.logar()
        resposta = self.cliente.post(
            "/entregadores/novo",
            data={"nome": "Carlos Motorista", "contato": ""},
            follow_redirects=True,
        )
        self.assertIn("Entregador criado".encode(), resposta.data)
        with self.app.app_context():
            entregador = Entregador.query.first()
            self.assertEqual(entregador.nome, "Carlos Motorista")
            self.assertIsNone(entregador.contato)

    def test_desativar_e_reativar(self):
        self.logar()
        self.cliente.post(
            "/entregadores/novo",
            data={"nome": "Carlos Motorista", "contato": "(11) 99999-0000"},
        )
        self.cliente.post("/entregadores/1/desativar", follow_redirects=True)
        with self.app.app_context():
            self.assertFalse(Entregador.query.first().ativo)
        self.cliente.post("/entregadores/1/desativar", follow_redirects=True)
        with self.app.app_context():
            self.assertTrue(Entregador.query.first().ativo)


class TesteSetores(BaseTeste):
    def test_nome_obrigatorio(self):
        self.logar()
        resposta = self.cliente.post(
            "/setores/novo", data={"nome": ""}, follow_redirects=True
        )
        self.assertIn("Informe o nome do setor".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Setor.query.count(), 0)

    def test_nome_duplicado_rejeitado(self):
        self.logar()
        self.cliente.post("/setores/novo", data={"nome": "Escritório"})
        resposta = self.cliente.post(
            "/setores/novo", data={"nome": "Escritório"}, follow_redirects=True
        )
        self.assertIn("Já existe um setor".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Setor.query.count(), 1)

    def test_criar_setor(self):
        self.logar()
        resposta = self.cliente.post(
            "/setores/novo", data={"nome": "Alojamento"}, follow_redirects=True
        )
        self.assertIn("Setor criado".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Setor.query.first().nome, "Alojamento")


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
            db.session.add(Setor(nome="Escritório"))
            db.session.add(
                Entregador(nome="Carlos Motorista", contato="(11) 99999-0000")
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
            data={"obra_id": 1, "setor_id": 1, "entregador_id": 1, "modo_rapido": ""},
            follow_redirects=True,
        )
        self.assertIn("Saída registrada".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 7)
            mov = Movimentacao.query.filter_by(tipo="saida").first()
            self.assertEqual(mov.quantidade, 3)
            self.assertEqual(mov.obra_id, 1)
            self.assertEqual(mov.setor_id, 1)
            self.assertIsNotNone(mov.remessa_id)
            self.assertEqual(mov.usuario.login, "operador")
            # a saída carrega o custo médio da entrada (12,50)
            self.assertEqual(mov.valor_unitario_cents, 1250)
            # obra não-sede cria a remessa com o evento "despachada"
            remessa = Remessa.query.first()
            self.assertEqual(remessa.obra_id, 1)
            self.assertEqual(remessa.transportador_id, 1)
            self.assertEqual(remessa.status, "despachada")

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
            data={"obra_id": 1, "setor_id": 1, "entregador_id": 1, "modo_rapido": ""},
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
            data={"codigo": codigo, "modo_rapido": "on", "obra_id": 1, "setor_id": 1, "entregador_id": 1},
            follow_redirects=True,
        )
        self.assertIn("Saída registrada".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(saldo_do_item(1), 4)
            saida = Movimentacao.query.filter_by(tipo="saida").first()
            self.assertEqual(saida.valor_unitario_cents, 1250)

    def test_finalizar_sem_entregador_para_obra_nao_sede_bloqueia(self):
        self.logar(login="operador")
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)
        self.cliente.post("/pos/adicionar", data={"codigo": codigo})
        resposta = self.cliente.post(
            "/pos/finalizar",
            data={"obra_id": 1, "setor_id": 1, "entregador_id": "", "modo_rapido": ""},
            follow_redirects=True,
        )
        self.assertIn(b"informe quem transporta", resposta.data)
        with self.app.app_context():
            self.assertEqual(Movimentacao.query.filter_by(tipo="saida").count(), 0)
            self.assertEqual(Remessa.query.count(), 0)

    def test_saida_para_sede_nao_cria_remessa(self):
        self.logar(login="operador")
        with self.app.app_context():
            db.session.add(Obra(nome="Sede", eh_sede=True))
            db.session.commit()
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)
        resposta = self.cliente.post(
            "/pos/adicionar",
            data={"codigo": codigo, "modo_rapido": "on", "obra_id": 2, "setor_id": 1, "entregador_id": ""},
            follow_redirects=True,
        )
        self.assertIn("Saída registrada".encode(), resposta.data)
        with self.app.app_context():
            mov = Movimentacao.query.filter_by(tipo="saida").first()
            self.assertIsNone(mov.remessa_id)
            self.assertEqual(mov.obra_id, 2)
            self.assertEqual(Remessa.query.count(), 0)


class TesteLogistica(BaseTeste):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            db.session.add(Setor(nome="Escritório"))
            db.session.add(
                Entregador(nome="Carlos Motorista", contato="(11) 99999-0000")
            )
            db.session.add(Obra(nome="Obra Central"))
            db.session.commit()

    def _despachar(self):
        """Saída para obra não-sede: cria uma remessa em trânsito."""
        self.logar(login="operador")
        _, codigo = self.criar_item()
        self.dar_entrada(codigo=codigo, quantidade=5)
        self.cliente.post(
            "/pos/adicionar",
            data={
                "codigo": codigo,
                "modo_rapido": "on",
                "obra_id": 1,
                "setor_id": 1,
                "entregador_id": 1,
            },
            follow_redirects=True,
        )

    def test_lista_mostra_remessa_em_transito(self):
        self._despachar()
        resposta = self.cliente.get("/logistica/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("RM000001".encode(), resposta.data)
        self.assertIn("Em trânsito".encode(), resposta.data)
        self.assertIn("Carlos Motorista".encode(), resposta.data)

    def test_detalhe_mostra_timeline(self):
        self._despachar()
        resposta = self.cliente.get("/logistica/1")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Despachada".encode(), resposta.data)
        self.assertIn("Aguardando".encode(), resposta.data)
        self.assertIn("Obra Central".encode(), resposta.data)
        self.assertIn("Escritório".encode(), resposta.data)

    def test_operador_acessa_rastreio(self):
        self._despachar()
        self.assertEqual(self.cliente.get("/logistica/").status_code, 200)
        self.assertEqual(self.cliente.get("/logistica/1").status_code, 200)

    def test_remessa_inexistente_404(self):
        self.logar(login="operador")
        self.assertEqual(self.cliente.get("/logistica/999").status_code, 404)

    def _assinatura(self, conteudo=b"assinatura-de-teste"):
        return "data:image/png;base64," + base64.b64encode(conteudo).decode()

    def test_receber_mostra_formulario(self):
        self._despachar()
        resposta = self.cliente.get("/logistica/1/receber")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Recebido por".encode(), resposta.data)
        self.assertIn("canvas-assinatura".encode(), resposta.data)

    def test_concluir_recebimento(self):
        self._despachar()
        resposta = self.cliente.post(
            "/logistica/1/receber",
            data={"recebido_por": "João da Obra", "assinatura": self._assinatura()},
            follow_redirects=True,
        )
        self.assertIn("Entrega registrada".encode(), resposta.data)
        with self.app.app_context():
            remessa = Remessa.query.first()
            self.assertEqual(remessa.status, "recebida")
            self.assertEqual(remessa.recebido_por, "João da Obra")
            self.assertEqual(remessa.comprovante_tipo, "assinatura")
            self.assertIsNotNone(remessa.data_recebimento)
            self.assertEqual(remessa.eventos[-1].tipo, "recebida")
            nome_arquivo = remessa.comprovante_arq
        self.assertTrue(
            os.path.exists(os.path.join(self.pasta_comprovantes, nome_arquivo))
        )

    def test_comprovante_serve_arquivo(self):
        self._despachar()
        self.cliente.post(
            "/logistica/1/receber",
            data={"recebido_por": "João da Obra", "assinatura": self._assinatura()},
        )
        resposta = self.cliente.get("/logistica/1/comprovante/assinatura")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data, b"assinatura-de-teste")
        # sem foto, a rota da foto responde 404
        self.assertEqual(
            self.cliente.get("/logistica/1/comprovante/foto").status_code, 404
        )

    def test_recebimento_sem_assinatura_bloqueia(self):
        self._despachar()
        resposta = self.cliente.post(
            "/logistica/1/receber",
            data={"recebido_por": "João da Obra", "assinatura": ""},
            follow_redirects=True,
        )
        self.assertIn("Assine".encode(), resposta.data)
        with self.app.app_context():
            remessa = Remessa.query.first()
            self.assertEqual(remessa.status, "despachada")
            self.assertEqual(remessa.eventos[-1].tipo, "despachada")

    def test_recebimento_sem_recebedor_bloqueia(self):
        self._despachar()
        resposta = self.cliente.post(
            "/logistica/1/receber",
            data={"recebido_por": "", "assinatura": self._assinatura()},
            follow_redirects=True,
        )
        self.assertIn("Informe quem recebeu".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Remessa.query.first().status, "despachada")

    def test_receber_em_remessa_ja_recebida_redireciona(self):
        self._despachar()
        self.cliente.post(
            "/logistica/1/receber",
            data={"recebido_por": "João da Obra", "assinatura": self._assinatura()},
        )
        resposta = self.cliente.get("/logistica/1/receber", follow_redirects=True)
        self.assertIn("já foi concluída".encode(), resposta.data)
        with self.app.app_context():
            self.assertEqual(Remessa.query.first().status, "recebida")


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
        # busca por nome/código, com autocomplete
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
        resposta = self.cliente.get("/entregadores")
        self.assertIn(b'list="sugestoes-busca-entregador"', resposta.data)
        resposta = self.cliente.get("/setores")
        self.assertIn(b'list="sugestoes-busca-setor"', resposta.data)
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
        resposta = self.cliente.get("/entregadores/novo")
        self.assertNotIn(b"list=", resposta.data)
        resposta = self.cliente.get("/setores/novo")
        self.assertNotIn(b"list=", resposta.data)


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
