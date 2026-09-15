# Design Kit — Sistemas Campbel

Pasta pronta para copiar em qualquer sistema novo da Campbel. Contém todos os
arquivos **reais** do padrão visual (não é só descrição). O
[DESIGN.md](../DESIGN.md) do projeto de referência explica as regras, decisões e
o passo a passo completo.

## Conteúdo

- `static/css/app.css` — tema completo (cores, cantos quadrados, navbar, cards, tabelas, autocomplete, rodapé)
- `static/vendor/` — Bootstrap 5.3 vendado (funciona offline, sem CDN)
- `static/js/autocomplete.js` — dropdown de autocomplete no padrão do tema
- `static/img/` — `logo.png` (navbar, 36px), `favicon.png`, `icon-192/512.png` (PWA)
- `static/manifest.webmanifest` — PWA instalável (ajustar `name`/`short_name`)
- `static/sw.js` — service worker (cache offline)
- `templates/base.html` — esqueleto da plataforma: navbar, menu, flash messages, rodapé
- `templates/auth/login.html` — tela de login padrão

## Como usar

1. Copiar o conteúdo de `static/` para o `app/static/` do novo projeto e o de
   `templates/` para o `app/templates/` (manter a estrutura de pastas).
2. As imagens já vêm incluídas em `static/img/`, inclusive o `login.png`
   (logo grande da tela de login, copiado da `campbel2.png` do projeto de
   referência). Nada a adicionar.
   - Dica: gerar também um `favicon.png` de 32×32 ou 64×64 no lugar do atual
     de 1080×1080 (212 KB), e uma versão menor do `login.png` (o atual tem
     3189×1772 — 679 KB para uma imagem exibida em ~90px).
3. Criar o processador de contexto no `app/__init__.py` (seção 10.2 do
   DESIGN.md) — `nome_sistema` e `empresa` alimentam título, subtítulo do login
   e rodapé; o nome do sistema só é alterado nesse único lugar:
   ```python
   @app.context_processor
   def contexto_global():
       return {
           "nome_sistema": "Nome do Sistema",  # ← muda por sistema
           "empresa": "Campbel",
       }
   ```
4. Trocar `name`/`short_name` no `manifest.webmanifest` pelo nome do sistema.
5. O `base.html` registra o service worker em `/sw.js`. Para servi-lo na raiz
   (o arquivo mora em `app/static/`), criar a rota no `app/__init__.py`:
   ```python
   from flask import send_from_directory

   @app.route("/sw.js")
   def service_worker():
       resposta = send_from_directory(
           app.static_folder, "sw.js", mimetype="application/javascript"
       )
       resposta.headers["Service-Worker-Allowed"] = "/"
       resposta.headers["Cache-Control"] = "no-cache"
       return resposta
   ```
6. Montar o menu do `base.html` conforme as seções do sistema (seção 10.5 do
   DESIGN.md): uma entrada por área principal, variável `aba` para o estado
   ativo, dropdown para cadastros, `perfil == 'admin'` para áreas restritas.
7. Em `sw.js`, a lista `ESTATICOS` já referencia `login.png`; adicionar ali
   qualquer estático próprio do novo sistema.

## Conferência final (o visual está certo se…)

- Todos os componentes têm cantos quadrados (nenhum arredondado).
- Cards têm borda de 1px, sem sombra.
- Navbar escura `#1d2a38` com filete azul de 3px (`#1f4e79`) na base.
- Tabelas com cabeçalho em caixa alta, fundo `#f4f6f8`, texto `#5c6b7a`.
- Login: navbar com logo pequeno em cima + card centralizado com logo grande,
  subtítulo "… da empresa" e botão primário de largura total.
