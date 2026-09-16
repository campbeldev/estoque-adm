# Estoque Campbel — Controle de Estoque

Sistema de controle de estoque para empresa de engenharia: uniformes, EPIs,
materiais e ferramentas. Com entrada e saída de itens, linha de frente tipo
caixa (leitor de código), alertas de estoque baixo e relatórios.

Feito com **Python + Flask**. Em produção roda com **PostgreSQL** dentro de
containers **Docker**; em desenvolvimento e nos testes usa **SQLite**. O
sistema roda na rede local da empresa — nenhum dado sai da máquina servidora.

## Funcionalidades

- **Login com 2 perfis**: `admin` (cadastros, ajustes, relatórios) e
  `operador` (entradas, caixa/saídas)
- **Itens** com categoria, unidade, estoque mínimo, tamanho (uniformes) e
  CA (EPIs) e código automático (`EV000001`, `EV000002`…)
- **Funcionários por empresa** (matrícula única por empresa) e **obras**
- **Entradas** com número da nota, série, fornecedor e valor unitário
  (aceita leitor de código) — itens da mesma nota ficam agrupados
  automaticamente e o total é valor unitário × quantidade. Cada entrada
  registra a **validade do seu lote** (obrigatória para EPIs)
- **Validade por lote**: o estoque mostra o saldo por vencimento (PEPS —
  o lote que vence primeiro sai primeiro), com alerta de lote **vencido**
  e destaque para vencimentos próximos
- **Notas** (admin): listagem e detalhe das notas de entrada, com itens,
  totais e exportação CSV
- **Caixa (linha de frente)**: cada leitura adiciona ao pacote, ou usa o
  **modo rápido** para baixar 1 unidade por leitura. Toda saída registra o
  funcionário que retirou e a obra de destino
- **Estoque**: saldo sempre derivado das movimentações (nunca salvo),
  destaque para itens abaixo do mínimo
- **Ajuste de balanço** com motivo obrigatório (quebras, extravios, contagens)
- **Relatórios**: histórico filtrável + exportação CSV compatível com Excel pt-BR.
  Saídas carregam o **custo médio** do item (calculado nas entradas), então o
  relatório por funcionário mostra o **valor total das retiradas**

## Primeiro acesso

| Login | Senha inicial |
|---|---|
| `admin` | `admin123` |
| `operador` | `operador123` |

As senhas iniciais **exigem troca no primeiro login**. Cadastre novos
usuários em *Cadastros → Usuários* (perfil admin).

## Produção (PostgreSQL + Docker)

Em produção o sistema usa **PostgreSQL** e roda em **containers Docker**, com
manutenção contínua via **git**. O banco e o app sobem juntos com
`docker compose`; os dados ficam em volumes nomeados (`pgdata` para o banco
e `estoque_adm_comprovantes` para os comprovantes de entrega) que sobrevivem
a rebuilds e reinícios.

### Pré-requisitos

- Docker + Docker Compose instalados no servidor (Linux ou Windows — os
  containers rodam Linux).
- Acesso à internet no servidor (para `git pull` e baixar as imagens).

### Primeira subida (uma vez só)

```bash
git clone https://github.com/campbeldev/estoque-adm.git
cd estoque-adm
cp .env.example .env      # edite: POSTGRES_PASSWORD e SECRET_KEY
docker volume create estoque_adm_pgdata
docker volume create estoque_adm_comprovantes
docker compose up -d --build
```

Abra http://IP-DO-SERVIDOR:5051.

> O `.env` é obrigatório e **não** vai para o git (já está no `.gitignore`).
> Troque `POSTGRES_PASSWORD` e `SECRET_KEY` por valores reais antes de subir.

> Banco recém-criado fica vazio. Para criar os usuários iniciais
> (`admin`/`operador`) e as categorias, rode uma vez:
>
> ```bash
> docker compose exec app python -m flask --app app seed
> ```
>
> Se estiver **restaurando um backup**, pule o `seed` (os dados já vêm no
> backup).

### Backup (pg_dump)

O backup é do PostgreSQL. O `-T` é importante para o redirecionamento sair
limpo (sem TTY). O comando funciona com o sistema em uso:

```bash
docker compose exec -T db pg_dump -U estoque_adm -d estoque_adm -Fc > backups/backup.dump
```

- `-Fc` = formato custom (compacto; restaurado com `pg_restore`).
- O arquivo contém **tudo**: itens, funcionários, obras, usuários (com as
  senhas hash), movimentações e notas.
- ⚠️ **Não comite esse arquivo no git** — ele tem dados pessoais e senhas.
  Guarde em outro disco/pen drive.

> Para agendar (Agendador de Tarefas no Windows, ou `cron` no Linux), aponte
> para esse mesmo comando. Adicione data/hora no nome se quiser:
> PowerShell `$(Get-Date -Format yyyyMMdd_HHmm)` · Linux `$(date +%Y%m%d_%H%M)`.

### Restaurar / levar para outro servidor

O fluxo para migrar os dados para uma máquina nova (ou reverter) é:

```bash
# 1) levar o arquivo para o servidor (fora do git)
scp backups/backup.dump usuario@IP-DO-SERVIDOR:/caminho/no/servidor/

# 2) no servidor, subir só o banco primeiro
cd estoque-adm
docker compose up -d db

# 3) restaurar
docker compose exec -T db pg_restore -U estoque_adm -d estoque_adm --clean --if-exists < /caminho/backup.dump

# 4) subir o app
docker compose up -d --build
```

A ordem importa: subir o `db` → restaurar → subir o `app`. Assim o banco já
nasce populado e o `create_all()` do app vira no-op.

Conferência:

```bash
docker compose exec -T db psql -U estoque_adm -d estoque_adm -c "SELECT count(*) FROM movimentacao;"
```

### Manutenção (rotina)

1. Na sua máquina: desenvolva, teste e `git push`.
2. No servidor: puxe as mudanças e reconstrua o app:

   ```bash
   git pull
   docker compose up -d --build
   ```

Os dados no volume `pgdata` não são afetados pelo rebuild.

### Migrar de um SQLite antigo (legado, uma vez só)

Se ainda existir um `instance/estoque.db` de uma instalação antiga que
precise ser levado ao PostgreSQL, use o script de migração:

```bash
docker compose up -d db
DATABASE_URL="postgresql+psycopg://estoque_adm:SENHA@localhost:5434/estoque_adm" \
  python scripts/migrar_dados.py
docker compose up -d --build
```

> A porta no **host** é `5434` (a 5432 fica dentro da rede do compose e é
> usada pelo próprio app). A conferência de contagens aparece na saída.
>
> Este passo **não** é necessário na instalação atual (o sistema já está no
> PostgreSQL) — existe apenas para quem ainda tiver um banco SQLite legado.

## Desenvolvimento local (SQLite)

Sem `DATABASE_URL`, o sistema cai no SQLite local — útil para desenvolver e
rodar os testes. Requisitos: Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m flask --app app seed --exemplos   # cria usuários + dados de exemplo
python -m flask --app app run --debug
```

Abra http://127.0.0.1:5000.

> No desenvolvimento o banco fica em `instance/estoque.db`. Não o mantenha
> numa pasta sincronizada (OneDrive/Dropbox) — a sincronização durante a
> gravação pode corromper o arquivo. Para apontar para outro caminho, use a
> variável `ESTOQUE_DB`.

Backup do SQLite (apenas desenvolvimento): `python -m flask --app app backup`
— copia `instance/estoque.db` para `backups/` com data/hora. **Em produção,
use o `pg_dump` da seção anterior.**

## Testes

```bash
python -m unittest discover tests
```

Os testes usam SQLite e validam a lógica (saldo derivado, custo médio,
importações).

## Leitor de código

Qualquer leitor USB funciona: ele se comporta como um teclado (digita o
código e envia Enter). Basta manter o campo de código em foco — a tela do
caixa foi desenhada para isso (autofocus a cada leitura). Códigos que não
existem no cadastro são recusados com aviso na tela.

## Instalar como aplicativo (PWA)

O sistema é um PWA: dá para instalar um atalho com janela própria no
computador (com ícone do logo) e os arquivos ficam em cache no navegador.

- **Na máquina que roda o servidor** (http://localhost:5051 ou
  http://127.0.0.1:5051): o Chrome/Edge mostram o ícone de **instalação
  na barra de endereço** (ou *Menu ⋮ → Instalar aplicativo*). Instalação
  completa, com janela independente, abrindo em **tela cheia**.
- **Nas outras máquinas da rede** (http://IP-DA-MAQUINA:5051): o navegador
  não permite instalação PWA em HTTP puro (exige HTTPS). A alternativa
  equivalente: *Menu ⋮ → Salvar e compartilhar → Criar atalho* e marque
  **"Abrir como janela"** — fica com cara de aplicativo, sem aba do
  navegador. Nesse modo o atalho não usa o manifest, então **não abre em
  tela cheia automaticamente** — pressione F11 (ou Fn+F11) para tela cheia.
- Se o aplicativo já estava instalado antes de uma mudança no manifest
  (ex.: modo tela cheia), **desinstale e instale de novo** para aplicar.
- Ao alterar arquivos estáticos (CSS/JS), aumente a versão em `CACHE` no
  `app/static/sw.js` para os navegadores baixarem o novo cache.

## Estrutura

```
Dockerfile           imagem do app (python:3.12-slim + gunicorn)
docker-compose.yml   banco (postgres:16-alpine) + app
.env.example         modelo de variáveis de ambiente (copie para .env)
requirements.txt     dependências (Flask, psycopg, gunicorn…)
config.py            configuração (DATABASE_URL ou SQLite; sessão; pastas)
scripts/
  migrar_dados.py    migração SQLite → PostgreSQL (legado, uma vez só)
app/
  __init__.py        fábrica da aplicação (banco, CSRF, blueprints, CLI)
  models.py          modelos + cálculo de saldo (derivado das movimentações)
  auth.py            login/logout/troca de senha + decorators de perfil
  itens.py           cadastro de itens (código automático)
  cadastros.py       funcionários e obras
  usuarios.py        usuários do sistema
  entradas.py        entrada de estoque (agrupada por nota)
  notas.py           listagem e detalhe das notas de entrada (admin)
  migracao.py        migração leve do schema (SQLite e PostgreSQL)
  moeda.py           dinheiro em centavos inteiros (formatação pt-BR)
  pos.py             linha de frente (caixa) — pacote em sessão + modo rápido
  estoque.py         saldos e ajuste de balanço
  relatorios.py      histórico + CSV
  services/          PDF de relatórios e exportação CSV
  seed.py            comando `flask --app app seed [--exemplos]`
  backup.py          comando `flask --app app backup` (SQLite, dev)
tests/               testes de unidade (rodam em SQLite)
```

## Futuro

- **Alembic/Flask-Migrate**: adotar quando o schema voltar a evoluir (hoje a
  migração leve do `migracao.py` cobre o básico).
- **Concorrência no saldo**: com vários operadores no PostgreSQL, a checagem
  "saldo → insere" do caixa vira condição de corrida; usar transação +
  `SELECT ... FOR UPDATE` (ou trigger).
- **Itens fracionados** (kg, m): trocar a quantidade inteira por `Numeric`.
