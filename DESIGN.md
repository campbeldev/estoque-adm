# Design System — Sistemas Campbel

Padrão visual dos sistemas da Campbel, extraído do Controle de Estoque.
Aplicar este padrão em qualquer software novo da empresa.

## 1. Visão geral

- **Base**: Bootstrap 5.3 vendado (arquivos locais em `static/vendor/`, sem CDN — funciona offline) + uma folha de tema própria (`app.css`) que ajusta o Bootstrap.
- **Personalidade**: sóbrio, corporativo, "industrial". Bordas quadradas, paleta escura de azuis, nada de sombras nem cantos arredondados.
- **Offline/PWA**: instalável, com service worker e ícones de instalação.

## 2. Paleta de cores

| Papel | Cor | Uso |
|---|---|---|
| Azul primário | `#1f4e79` | Botões primários, links, item ativo, hover do autocomplete, filete sob a navbar |
| Azul primário (hover) | `#16395c` | Links em hover |
| Azul-escuro | `#1d2a38` | Barra superior, fundo do dropdown de autocomplete, `theme-color` |
| Cinza-claro | `#f4f6f8` | Cabeçalhos de cards e de tabelas, fundo do app (PWA) |
| Borda | `#d8dee4` | Bordas de cards, tabelas, divisórias, rodapé |
| Cinza de texto | `#5c6b7a` | Cabeçalhos de tabela |
| Cinza de texto 2 | `#77828e` | Rodapé, textos secundários |
| Borda de inputs | `#b9c4ce` | `form-control` e `form-select` |

Cores semânticas do Bootstrap (success, danger, warning, info) mantidas no padrão.

## 3. Tipografia

- **Fonte base**: pilha de fontes padrão do sistema (nenhuma webfont carregada).
- **Monospace** (códigos, IDs): `Consolas, Menlo, monospace`, 0.85rem.
- **Marca no navbar**: 0.9rem, caixa alta, `letter-spacing: 0.08em`.
- **Cabeçalhos de tabela**: 0.72rem, caixa alta, `letter-spacing: 0.05em`, peso 600, cor `#5c6b7a`, sem quebra de linha.

## 4. Formas e componentes

- **Bordas quadradas em tudo**: os tokens de raio do Bootstrap são zerados — cards, botões, inputs, badges, dropdowns, pills. Nenhum componente tem canto arredondado.
- **Cards**: planos — sem sombra, borda de 1px `#d8dee4`. Cabeçalho de card em `#f4f6f8` com borda inferior.
- **Botões**: `font-weight: 500`.
- **Inputs**: borda `#b9c4ce` para maior definição.
- **Alertas**: padrão Bootstrap, sempre dismissíveis (com `btn-close`).
- **Rodapé**: borda superior de 1px, texto pequeno (0.82rem) em cinza discreto.
- **Autocomplete**: dropdown escuro na cor da navbar (`#1d2a38`), cantos quadrados, hover/item ativo no azul primário `#1f4e79`.

### Bloco de tema (copiar para o `app.css` do novo sistema)

```css
:root {
  --bs-border-radius: 0;
  --bs-border-radius-sm: 0;
  --bs-border-radius-lg: 0;
  --bs-border-radius-xl: 0;
  --bs-border-radius-2xl: 0;
  --bs-border-radius-pill: 0;

  --bs-primary: #1f4e79;
  --bs-primary-rgb: 31, 78, 121;
  --bs-link-color: #1f4e79;
  --bs-link-color-rgb: 31, 78, 121;
  --bs-link-hover-color: #16395c;
  --bs-link-hover-color-rgb: 22, 57, 92;
}
```

## 5. Layout geral (todas as telas autenticadas)

1. **Navbar escura** (`#1d2a38`) com filete de 3px do azul primário na borda inferior.
   - Esquerda: logo (imagem, 36px de altura) — funciona como link para a home.
   - Centro: links de seção, com estado `active` na seção atual; agrupamentos secundários em dropdown.
   - Direita: nome do usuário + badge de perfil (Admin = `danger`, Operador = `primary`), link "Alterar senha" e botão "Sair" (estilo link).
   - Colapsa em menu hambúrguer no mobile.
2. **Conteúdo**: container com `max-width: 1400px` e margem superior de 1.5rem.
   - Mensagens flash no topo, como alertas dismissíveis.
3. **Rodapé**: container discreto com borda superior, texto simples com o nome do sistema.

## 6. Tela de login (padrão para todos os sistemas)

A tela de login usa a mesma base das demais telas: a navbar escura com o logo
pequeno aparece no topo (apenas os links de menu e a área do usuário ficam
ocultos quando não há sessão), e abaixo dela fica o card de autenticação.

- **Card centralizado**: `row justify-content-center` + `col-md-5 col-lg-4`, com `mt-4`.
- Dentro do card (padding `p-4`):
  1. Logo grande centralizado (imagem com ~90px de altura);
  2. Subtítulo discreto centralizado (`text-muted small`), ex.: "Controle de estoque da empresa";
  3. Erro de login como `alert alert-danger` acima do formulário;
  4. Formulário: rótulo (`form-label`) + `form-control`, usuário com `autofocus` e `autocomplete="username"`, senha com `autocomplete="current-password"`;
  5. Botão `btn btn-primary w-100` ("Entrar").
- O visual herda o tema: cantos quadrados e card plano com borda (a classe `shadow-sm` do HTML é anulada pelo tema).
- **Mesmo padrão** (card centralizado + botão de largura total) é usado na tela de alteração de senha.

### Template padrão do login

```html
{% extends "base.html" %}
{% block titulo %}Entrar — {{ nome_sistema }}{% endblock %}
{% block conteudo %}
<div class="row justify-content-center">
  <div class="col-md-5 col-lg-4">
    <div class="card shadow-sm mt-4">
      <div class="card-body p-4">
        <div class="text-center mb-3">
          <img src="{{ url_for('static', filename='img/login.png') }}" alt="{{ empresa }}" height="90">
        </div>
        <p class="text-center text-muted small mb-4">{{ nome_sistema }} da empresa</p>
        {% if erro %}
        <div class="alert alert-danger">{{ erro }}</div>
        {% endif %}
        <form method="post">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <div class="mb-3">
            <label class="form-label" for="login">Usuário</label>
            <input class="form-control" id="login" name="login" autofocus autocomplete="username" required>
          </div>
          <div class="mb-3">
            <label class="form-label" for="senha">Senha</label>
            <input class="form-control" id="senha" name="senha" type="password" autocomplete="current-password" required>
          </div>
          <button class="btn btn-primary w-100" type="submit">Entrar</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

Nada a personalizar dentro do template: título, subtítulo e nome vêm de
`nome_sistema`/`empresa`, definidos em um único lugar (seção 10).

## 7. Páginas de erro

- Centralizadas: código grande (`display-4`), texto explicativo (`lead`), botão primário "Voltar ao início".

## 8. Imagens (pasta `static/img`)

| Arquivo | Dimensão | Uso |
|---|---|---|
| `logo.png` | 800×473 | Logo na navbar, renderizado com 36px de altura |
| `favicon.png` | 1080×1080 | Ícone da aba do navegador (`<link rel="icon">`) |
| `icon-192.png` | 192×192 | Ícone PWA no manifest + `apple-touch-icon` |
| `icon-512.png` | 512×512 | Ícone PWA no manifest |
| `campbel2.png` | 3189×1772 | Logo grande da tela de login (~90px de altura); no kit entra como `login.png` |

Observações práticas:

- **Convenção de nomes para novos sistemas**: `logo.png` (navbar), `login.png` (tela de login), `favicon.png`, `icon-192.png` e `icon-512.png` — os mesmos nomes em todos os sistemas.
- As imagens são referenciadas sempre via `url_for('static', filename='img/...')`, nunca com caminho fixo.
- `favicon.png` em 1080×1080 (212 KB) é desnecessariamente grande para favicon — gerar versão 32×32 ou 64×64 para o novo sistema.
- `campbel2.png` foi restaurada no projeto e já está copiada para o kit como `login.png` — a pasta `design-kit/static/img/` sai completa.

## 9. PWA / instalação

- `manifest.webmanifest` com `theme_color: #1d2a38` (cor da navbar), `background_color: #f4f6f8`, `display: fullscreen`, ícones 192 e 512.
- `<meta name="theme-color">` igual à cor da navbar.
- Service worker registrado no fim do `<body>` para cache de arquivos estáticos (uso offline em campo).

## 10. Esqueleto inicial para novos sistemas

Um sistema novo começa com esta estrutura e estes dois templates. Tudo o que
muda de sistema para sistema fica concentrado em um único lugar: o processador
de contexto com `nome_sistema` e `empresa`.

Este repositório já contém a pasta `design-kit/` com todos os arquivos reais
prontos para copiar (tema, Bootstrap vendado, imagens, manifest, service worker
e os dois templates) e um `LEIA-ME.md` com o passo a passo — copiar a pasta
dispensa digitar qualquer código desta seção.

### 10.1 Estrutura de pastas

```
projeto/
├── run.py
└── app/
    ├── __init__.py               # cria o app + processador de contexto
    ├── static/
    │   ├── css/app.css           # copiar deste projeto (tema completo)
    │   ├── img/                  # logo.png, login.png, favicon.png, icon-192/512.png
    │   ├── js/autocomplete.js    # copiar, se houver busca com autocomplete
    │   ├── manifest.webmanifest  # copiar e ajustar name/short_name
    │   ├── sw.js                 # service worker (rota /sw.js no __init__.py)
    │   └── vendor/               # bootstrap.min.css + bootstrap.bundle.min.js
    └── templates/
        ├── base.html             # esqueleto 10.3
        └── auth/
            ├── login.html        # template da seção 6
            └── alterar_senha.html
```

### 10.2 Nome do sistema em um lugar só

```python
# app/__init__.py
from flask import Flask

def criar_app():
    app = Flask(__name__)

    @app.context_processor
    def contexto_global():
        return {
            "nome_sistema": "Controle de Estoque",  # ← muda por sistema
            "empresa": "Campbel",
        }

    return app
```

Com isso, `{{ nome_sistema }}` funciona em qualquer template — `<title>`,
subtítulo do login, rodapé — e o nome só é alterado em um lugar.

### 10.3 `base.html` — esqueleto da plataforma

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}{{ nome_sistema }}{% endblock %}</title>
  <link rel="icon" type="image/png" href="{{ url_for('static', filename='img/favicon.png') }}">
  <link rel="apple-touch-icon" href="{{ url_for('static', filename='img/icon-192.png') }}">
  <link rel="manifest" href="{{ url_for('static', filename='manifest.webmanifest') }}">
  <meta name="theme-color" content="#1d2a38">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
</head>
<body class="bg-body-tertiary">
<nav class="navbar navbar-expand-lg navbar-dark navbar-estoque">
  <div class="container">
    <a class="navbar-brand d-flex align-items-center" href="{{ url_for('auth.raiz') }}">
      <img src="{{ url_for('static', filename='img/logo.png') }}" alt="{{ empresa }}" height="36">
    </a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#menuPrincipal">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="menuPrincipal">
      {% if usuario_atual %}
      <ul class="navbar-nav me-auto">
        <!-- Seções do sistema: uma entrada por área principal.
             O estado ativo usa a variável `aba`, passada no render_template. -->
        <li class="nav-item"><a class="nav-link {% if aba == 'inicio' %}active{% endif %}" href="{{ url_for('inicio.index') }}">Início</a></li>

        <!-- Áreas secundárias agrupadas em dropdown: -->
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">Cadastros</a>
          <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="{{ url_for('cadastros.um') }}">Cadastro 1</a></li>
            <li><a class="dropdown-item" href="{{ url_for('cadastros.dois') }}">Cadastro 2</a></li>
          </ul>
        </li>

        <!-- Áreas exclusivas de admin: -->
        {% if usuario_atual.perfil == 'admin' %}
        <li class="nav-item"><a class="nav-link {% if aba == 'admin' %}active{% endif %}" href="{{ url_for('admin.index') }}">Administração</a></li>
        {% endif %}
      </ul>
      <ul class="navbar-nav">
        <li class="nav-item d-flex align-items-center">
          <span class="navbar-text me-2">
            {{ usuario_atual.nome }}
            <span class="badge text-bg-{{ 'danger' if usuario_atual.perfil == 'admin' else 'primary' }}">
              {{ 'Admin' if usuario_atual.perfil == 'admin' else 'Operador' }}
            </span>
          </span>
        </li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('auth.alterar_senha') }}">Alterar senha</a></li>
        <li class="nav-item">
          <form method="post" action="{{ url_for('auth.logout') }}" class="d-flex align-items-center">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button class="btn btn-link nav-link" type="submit">Sair</button>
          </form>
        </li>
      </ul>
      {% endif %}
    </div>
  </div>
</nav>
<main class="container pb-5">
  {% with mensagens = get_flashed_messages(with_categories=true) %}
    {% for categoria, mensagem in mensagens %}
      <div class="alert alert-{{ 'info' if categoria == 'message' else categoria }} alert-dismissible fade show" role="alert">
        {{ mensagem }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    {% endfor %}
  {% endwith %}
  {% block conteudo %}{% endblock %}
</main>
<footer class="container rodape">
  {{ nome_sistema }}
</footer>
<script src="{{ url_for('static', filename='vendor/bootstrap.bundle.min.js') }}"></script>
<script>
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  }
</script>
</body>
</html>
```

### 10.4 `login.html`

Copiar o template da seção 6 — ele já é genérico. Nada muda além de
`nome_sistema`/`empresa` (10.2).

### 10.5 Como montar o menu

- Cada área principal vira um `<li class="nav-item">` com `<a class="nav-link">`.
- O link da área atual recebe `active` quando a variável `aba` (passada no `render_template`) bate com o valor do link.
- Áreas secundárias (cadastros, configurações) ficam num dropdown.
- O que for exclusivo de admin fica dentro de `{% if usuario_atual.perfil == 'admin' %}`.
- Ordem padrão: áreas de operação primeiro, depois dropdown de cadastros, relatórios e administração por último.

### 10.6 Passo a passo para um sistema novo

1. Criar a estrutura de pastas da seção 10.1.
2. Copiar a pasta `design-kit/` (conteúdo de `static/` e de `templates/`) para o novo projeto e ajustar `name`/`short_name` no manifest.
3. Criar `app/__init__.py` com o processador de contexto e mudar `nome_sistema`.
4. Copiar `base.html` (10.3) e `login.html` (seção 6).
5. Adicionar/remover itens de menu conforme as seções do sistema (10.5).
6. Conferir: cantos quadrados, cards com borda, navbar escura com filete azul, login centralizado.

## 11. Checklist para aplicar em outro sistema

1. Copiar `static/vendor/bootstrap.min.css` e `bootstrap.bundle.min.js` (Bootstrap local, sem CDN).
2. Copiar `static/css/app.css` (tema) e `static/js/autocomplete.js` (se houver autocomplete).
3. Copiar `static/img/` com os logos e ícones da empresa (ajustar `favicon.png` para tamanho menor).
4. Copiar `manifest.webmanifest` ajustando `name`/`short_name` do novo sistema.
5. Estrutura de página: `base.html` com navbar escura + filete azul, container 1400px, flash messages, rodapé.
6. Login: card centralizado (`col-md-5 col-lg-4`), logo grande, subtítulo discreto, botão primário de largura total.
7. Manter: cantos quadrados, cards com borda (sem sombra), tabelas com cabeçalho em caixa alta e fundo `#f4f6f8`.
