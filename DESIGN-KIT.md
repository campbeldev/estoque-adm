# Campbel — Design Kit / Identidade Visual

> Guia portátil da identidade visual do site **Campbel Construções e Terraplenagem**.
> Fonte de verdade no repositório:
> - `assets/css/variables.css` — tokens (cores, tipografia, raios, sombras)
> - `assets/css/base.css` — reset, tipografia, contêiner, cabeçalhos de seção
> - `assets/css/components.css` — componentes do site público
> - `assets/css/admin.css` — componentes do painel administrativo
>
> Arquivos `layout.css` e `responsive.css` cuidam de estrutura e responsividade.
> O arquivo `padraovisual.css` é **legado do site antigo** (Verdana/Gill Sans) e deve ser ignorado.

---

## 1. Marca

- **Nome:** Campbel Construções e Terraplenagem
- **Ramo:** construção civil · terraplenagem · pavimentação · urbanização
- **Tom da identidade:** discreto, corporativo e sóbrio. Pouco azul, tipografia em escala menor, sem excessos.
- **Logotipo:** `img/logo.png` (cor) · `img/logo5.png` (favicon)

---

## 2. Paleta de cores

Todas as cores são consumidas via tokens `var(--c-*)`. **Não hardcode** valores hex em novos componentes — use o token.

| Token | Hex | Uso |
|---|---|---|
| `--c-primary` | `#10151c` | Azul-marinho profundo — fundos escuros, footer, textos de destaque |
| `--c-primary-700` | `#041c3b` | Variação escura do primário |
| `--c-primary-800` | `#03142c` | Variação ainda mais escura |
| `--c-accent` | `#e20712` | **Vermelho institucional** — detalhes, CTAs, links ativos, foco, erros |
| `--c-accent-600` | `#c90000` | Vermelho em hover |
| `--c-accent-soft` | `rgba(230, 57, 70, .15)` | Vermelho translúcido — anel de foco de campos |
| `--c-ink` | `#10141a` | Texto principal (quase preto) |
| `--c-ink-soft` | `#4b5563` | Texto secundário (cinza) |
| `--c-ink-faint` | `#9aa3af` | Placeholders, textos bem discretos |
| `--c-ink-inverse` | `#ffffff` | Texto sobre fundo escuro |
| `--c-surface` | `#ffffff` | Fundo principal |
| `--c-surface-alt` | `#f3f5f8` | Fundo alternado / seções secundárias |
| `--c-border` | `#e2e6ec` | Bordas |
| `--c-dark` | `#10151c` | Fundo escuro neutro (footer) |

### Cores de status (painel admin)

| Estado | Cor | Fundo |
|---|---|---|
| Ativa / Aprovada (positivo) | `#15803d` | `#e7f6ec` |
| Recusada (negativo) | `#b91c1c` | `#fdeaea` |
| Encerrada / Pendente (neutro) | `#64748b` | `#eceff3` |

---

## 3. Tipografia

| Papel | Fonte | Pesos |
|---|---|---|
| Títulos, botões, labels | **Montserrat** (`--font-heading`) | 600 · 700 · 800 |
| Corpo, interface | **Inter** (`--font-body`) | 400 · 500 · 600 · 700 |

- **Corpo:** 15px (`0.9375rem`), line-height `1.6`.
- **Títulos (`h1`–`h6`):** Montserrat, peso 700, line-height `1.15`.
- **Kicker / rótulos:** Montserrat 700, caixa alta, letter-spacing amplo (`0.16em`), cor vermelha.
- Escala de títulos de seção: `clamp(1.5rem, 2.6vw, 2.1rem)`.

---

## 4. Raios, sombras e layout

### Raios (`border-radius`)
| Token | Valor |
|---|---|
| `--radius-sm` | `4px` |
| `--radius` | `6px` |
| `--radius-lg` | `8px` |

### Sombras
| Token | Uso |
|---|---|
| `--shadow-sm` | Elementos sutis |
| `--shadow-md` | Cards, hover (`0 6px 18px rgba(3,20,44,.10)`) |
| `--shadow-lg` | Modais, toast (`0 18px 48px rgba(3,20,44,.16)`) |

### Layout
- **Contêiner:** `--container: 1180px`, com `padding-inline: 1.5rem` (24px).
- **Altura do header:** `--header-h: 76px`.
- **Espaçamento de seção:** `.section` = `6rem` vertical; `--about` = `7rem`.

### Movimento
- `--ease: 180ms cubic-bezier(.4, 0, .2, 1)` — todas as transições usam este easing.

---

## 5. Hero e fundos

- **Home:** imagem de fundo (`img/headerimage.png`) sob gradiente escuro + overlay preto.
- **Páginas internas:** apenas gradiente escuro (sem foto).
- **Vagas:** `img/banner.png`.
- Gradiente padrão do hero:
  `linear-gradient(135deg, #161a20 0%, #0c0f13 55%, #050607 100%)`

---

## 6. Inventário de componentes

Convenção de nomenclatura: **BEM** — `bloco__elemento--modificador`.

### 6.1 Botões
| Classe | Descrição |
|---|---|
| `.btn` | Base — flex inline, Montserrat 700, `padding: .8rem 1.6rem`, raio `--radius` |
| `.btn--accent` | Fundo vermelho, texto branco (ação principal) |
| `.btn--outline` | Contorno branco translúcido (sobre fundo escuro) |
| `.btn--outline-dark` | Contorno cinza, texto primário (ações secundárias em fundo claro) |
| `.btn--block` | Largura total |
| `.btn--sm` | Versão compacta (`padding: .5rem 1rem`, fonte `.82rem`) |
| `.btn--approve` | Fundo verde (aprovar) |
| `.btn--reject` | Fundo vermelho escuro `#b91c1c` (recusar) |

### 6.2 Badges
| Classe | Estado |
|---|---|
| `.badge` | Base — pill (`border-radius: 999px`), fonte `.74rem` 700 |
| `.badge--ativa` / `.badge--aprovada` | Verde |
| `.badge--encerrada` / `.badge--pendente` | Cinza neutro |
| `.badge--recusada` | Vermelho |

### 6.3 Cards
| Classe | Descrição |
|---|---|
| `.card-service` | Card de serviço (mídia + corpo), hover eleva e amplia imagem |
| `.card` | Card genérico (fundo branco, borda, raio `--radius-lg`, `--shadow-md`) |
| `.job-card` | Card de vaga no portal público (título, local, tempo, CTA, vagas restantes) |
| `.admin-row` | Linha de registro no painel (título + meta + ações) |

### 6.4 Formulários
| Classe | Descrição |
|---|---|
| `.form` | Grid vertical com gap, `padding: 2.25rem` |
| `.form__row` | Duas colunas (`1fr 1fr`) |
| `.field` | Grupo rótulo + input (gap `.4rem`) |
| `.field__label` | Rótulo, Inter 600 `.88rem` |
| `.field__input` | Input/select/textarea — `padding .7rem .9rem`, borda `--c-border`, foco vermelho com anel `--c-accent-soft` |
| `.form__status` | Mensagem de status (`is-success` verde / `is-error` vermelho) |
| `.form__note` | Nota informativa (caixa em `--c-surface-alt`) |
| `.form__honeypot` | Anti-spam invisível |
| `.file-drop` | Área de upload (currículo) — caixa tracejada, estado `has-file` verde |

### 6.5 Modal e Toast
| Classe | Descrição |
|---|---|
| `.modal` | Overlay fixo com fundo `rgba(6,8,10,.55)`, `z-index 200` |
| `.modal__card` | Cartão do modal (`max-width 640px`, `--radius-lg`, `--shadow-lg`) |
| `.modal__card--sm` | Versão compacta (`max-width 440px`) |
| `.modal__head` / `.modal__title` / `.modal__close` | Cabeçalho do modal |
| `.toast` | Aviso fixo inferior-direito (`z-index 300`), `is-visible` anima entrada |
| `.toast--success` | Verde `#15803d` |
| `.toast--error` | Vermelho `--c-accent` |

### 6.6 Tabela e listas
| Classe | Descrição |
|---|---|
| `.table-wrap` / `.table` | Tabela do painel (cabeçalho em `--c-surface-alt`) |
| `.admin-list` | Lista de registros |
| `.cand-group` | Grupo de candidaturas por vaga (accordion) |
| `.cand` | Linha de candidatura (clicável, hover com borda cinza `--c-ink-soft`) |
| `.empty` / `.vagas-empty` | Estado vazio (borda tracejada) |

### 6.7 Navegação e estrutura
| Classe | Descrição |
|---|---|
| `.section` (+ `--alt`, `--dark`, `--about`) | Seção com espaçamento vertical |
| `.section-head` (+ `--center`) | Cabeçalho de seção |
| `.kicker` | Rótulo superior (uppercase vermelho) |
| `.section-title` / `.section-text` | Título e texto de seção |
| `.icon` | Ícone SVG baseado em traço (`stroke: currentColor`) |
| `.visually-hidden` | Acessibilidade (texto só para leitores de tela) |
| `.container` | Contêiner central (1180px) |

### 6.8 Portal de vagas
| Classe | Descrição |
|---|---|
| `.vagas-list` | Lista de vagas |
| `.vaga-hero` | Cabeçalho do detalhe da vaga |
| `.vaga-desc` | Descrição da vaga |
| `.apply` | Página de candidatura (grid `280px 1fr`) |
| `.apply__steps` / `.apply__step` | Wizard de etapas (números com estado `is-active`/`is-done`) |
| `.wizard-step` | Passo do formulário |

---

## 7. Regras de uso

1. **Sempre use tokens** (`var(--c-*)`, `var(--radius)`, `var(--ease)`, `var(--font-*)`) — nunca hardcode cores ou espaçamentos.
2. **Vermelho (`--c-accent`) é o acento**, não a cor de fundo de grandes áreas. Use com moderação em detalhes e CTAs.
3. **Tipografia:** títulos = Montserrat; corpo/interface = Inter. Escala contida.
4. **Estado:** verde = positivo/aprovado; vermelho = negativo/recusado; cinza = neutro/pendente.
5. **Foco de campos:** borda vermelha + anel `--c-accent-soft` (acessível via teclado).
6. **Movimento:** transições rápidas e discretas (`--ease`), hover com leve elevação (`transform: translateY` + `--shadow-md`).
