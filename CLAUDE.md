# estoque-adm

Sistema de controle de estoque da Campbel (Flask + SQLAlchemy + PostgreSQL/SQLite).
Base do antigo `estoque-rh`, agora para o **setor administrativo**.

## Contexto (leia antes de mexer)

- **Repositório:** `campbeldev/estoque-adm` (branch `main`). ⚠️ A conta GitHub é
  **`campbeldev`**, não `campbel` — essa é de outra pessoa, sem relação.
- **Histórico recomeçado do zero** de propósito (commit inicial único). O
  histórico completo de origem está em `nathanssna/gestaodeestoque`.
- O código interno ainda usa "estoque" de forma genérica (rotas `/estoque`,
  banco SQLite de dev `instance/estoque.db`). A distinção "adm" fica só no
  Docker/repositório/banco de produção — não renomeie as rotas sem necessidade.
- O `estoque-rh` original continua rodando nesta máquina nas portas 5050/5433.

## Como rodar (resumo — detalhes no README.md)

- **Produção (Docker):** app em `http://localhost:5051` (container 5050);
  PostgreSQL no host `5434` (container 5432); volume `estoque_adm_pgdata`
  (externo); banco/usuário `estoque_adm` via `.env`.
  - Antes do 1º up: `docker volume create estoque_adm_pgdata estoque_adm_comprovantes`.
  - Seed: `docker compose exec app python -m flask --app app seed`.
- **Dev (SQLite):** `python -m flask --app app run --debug` (porta 5000).
- **Testes:** `python -m unittest discover tests`.

## Arquitetura

- App factory em `app/__init__.py` (`create_app`). `migrar_leve()` chama
  `db.create_all()` no boot — por isso o gunicorn usa `--workers 1` (com 2
  workers, disputariam o schema no banco vazio → `UniqueViolation`).
- Blueprints por domínio: `auth`, `itens`, `cadastros`, `usuarios`, `entradas`,
  `notas`, `pos` (caixa), `estoque`, `relatorios`.
- `models.py`: saldo **derivado** das movimentações (nunca salvo); custo médio
  nas saídas. Dinheiro em **centavos inteiros** (`moeda.py`).
- PWA (service worker em `app/static/sw.js`).

## Próximos passos

- Adaptar o sistema para o **setor administrativo** (requisitos a definir).
