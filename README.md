# Nota Mil — Simples (Vercel Edition)

Plataforma de estudos com IA para ENEM. Correção de redação nas 5 competências oficiais do INEP,
banco de questões interativo com gabarito comentado e gerador de questões inéditas com IA sob demanda.

**Sem cadastro, sem senha, sem banco de dados.** O aluno acessa o link e já usa.

Arquitetura 100% compatível com o modelo serverless da Vercel: `/public/` servido pelo CDN,
`/api/*.py` como funções Python independentes usando `BaseHTTPRequestHandler` (sem FastAPI).


## Sumário

- [O que tem dentro](#o-que-tem-dentro)
- [Deploy na Vercel (passo a passo)](#deploy-na-vercel-passo-a-passo)
- [Rodando localmente](#rodando-localmente)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Editando o banco de questões](#editando-o-banco-de-questões)


## O que tem dentro

- **Landing page** (`index.html`) com apresentação e botão "Acessar plataforma"
- **Plataforma** (`app.html`) com três módulos em abas:
  - **Corretor de redação** — cola texto + tema, IA devolve nota total, 5 competências, comentários, pontos fortes/fracos e reescritas
  - **Banco de questões** — 32 questões (8 por área) do padrão ENEM, uma por vez, com filtro por área e gabarito comentado
  - **Gerar com IA** — aluno escolhe área e tópico, IA cria de 1 a 5 questões inéditas no formato ENEM
- **3 funções serverless** independentes em `/api/`, cada uma com seu próprio timeout
- **CSS moderno** dark-mode, responsivo em desktop/tablet/mobile


## Deploy na Vercel (passo a passo)

Do zero ao link público em ~10 minutos. Assume que você nunca usou GitHub ou Vercel antes.

### 1. Conseguir uma chave da IA

Você precisa de **uma das duas**:

- **Anthropic (recomendado)** — <https://console.anthropic.com>. Crie a conta, adicione US$ 5 de crédito, gere uma chave em **API Keys**. Formato: `sk-ant-...`
- **OpenAI** — <https://platform.openai.com/api-keys>. Formato: `sk-...`

Guarde a chave — você vai colar na Vercel no passo 3.

### 2. Subir o código no GitHub

1. Crie uma conta em <https://github.com> se não tem.
2. Novo repositório em <https://github.com/new>. Nome sugerido: `nota-mil`. Deixe **vazio** (sem README/gitignore — já estão inclusos).
3. No seu terminal, dentro da pasta do projeto:

   ```bash
   git init
   git add .
   git commit -m "primeiro commit"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/nota-mil.git
   git push -u origin main
   ```

   Se pedir credencial, use seu username + um [Personal Access Token](https://github.com/settings/tokens) com permissão `repo`.

### 3. Deploy na Vercel

1. Acesse <https://vercel.com> e faça **Sign Up** com sua conta GitHub.
2. No painel, clique em **Add New… → Project**.
3. Selecione o repositório `nota-mil` e clique **Import**.
4. Expanda **Environment Variables** e adicione:

   | Nome                  | Valor                              |
   |-----------------------|------------------------------------|
   | `ANTHROPIC_API_KEY`   | `sk-ant-...` (a chave que você guardou) |

   Ou, se preferir OpenAI, use `OPENAI_API_KEY` no lugar.

5. Clique **Deploy**. Leva ~2 minutos.

### 4. Pronto

Quando aparecer **Ready**, seu link fica no topo:

```
https://nota-mil-XXXXXX.vercel.app
```

Abra, clique em **Acessar plataforma** e comece a usar. Cada `git push` para a branch `main` dispara um novo deploy automático.


## Rodando localmente

Requer Python 3.10+.

```bash
# instala as dependências
pip install -r requirements.txt

# copia o exemplo de env e cola sua chave
cp .env.example .env
# → edite .env e ponha ANTHROPIC_API_KEY ou OPENAI_API_KEY

# sobe o servidor de desenvolvimento
python dev.py
```

Acesse <http://localhost:8000>.

O `dev.py` é um servidor pequeno que replica o comportamento da Vercel localmente:
serve `/public/` como estático e carrega dinamicamente cada `/api/*.py` como função.
**Não vai para produção** — a Vercel usa seu próprio runtime.


## Estrutura do projeto

```
nota-mil-simples/
├── api/                         # funções serverless (uma por endpoint)
│   ├── _lib/
│   │   ├── ia.py                # camada Anthropic + OpenAI compartilhada
│   │   └── http.py              # Handler base (BaseHTTPRequestHandler)
│   ├── corrigir.py              # POST /api/corrigir  → correção de redação
│   ├── gerar.py                 # POST /api/gerar     → questões geradas por IA
│   └── questoes.py              # GET  /api/questoes  → banco estático + gabaritos
│
├── public/                      # servido pelo CDN da Vercel (sem passar por Python)
│   ├── index.html               # landing page
│   ├── landing.css
│   ├── app.html                 # plataforma (3 abas)
│   ├── app.css
│   └── app.js
│
├── data/
│   └── questoes.json            # 32 questões estáticas (8 por área)
│
├── dev.py                       # servidor local (não vai para produção)
├── vercel.json                  # rewrites + timeout por função
├── requirements.txt             # anthropic + openai (só isso)
├── .env.example
├── .gitignore
└── README.md
```

### Como a Vercel entende cada pasta

- **`public/`** → tudo aí vira estático servido pelo CDN. `index.html` responde em `/`, `landing.css` em `/landing.css`, etc.
- **`api/*.py`** → cada arquivo vira uma função serverless em `/api/<nome>`. Arquivos começando com `_` (como `_lib/`) são ignorados como endpoint.
- **`vercel.json`** → define o `maxDuration` de cada função (60s para IA, 10s para o banco estático) e o rewrite `/plataforma` → `/app.html`.


## Variáveis de ambiente

| Variável              | Onde configurar                                       | Padrão                |
|-----------------------|-------------------------------------------------------|-----------------------|
| `ANTHROPIC_API_KEY`   | Vercel + `.env` local                                 | —                     |
| `OPENAI_API_KEY`      | Vercel + `.env` local                                 | —                     |
| `ANTHROPIC_MODEL`     | Opcional — trocar modelo Anthropic                    | `claude-sonnet-4-5`   |
| `OPENAI_MODEL`        | Opcional — trocar modelo OpenAI                       | `gpt-4o`              |

Sem chave configurada, os endpoints de redação e geração respondem **400** com mensagem clara.
O banco de questões continua funcionando (é 100% estático).


## Editando o banco de questões

O banco vive em `data/questoes.json`. Cada questão tem esta forma:

```json
{
  "id": "mat-009",
  "area": "matematica",
  "topico": "Sistemas lineares",
  "enunciado": "…",
  "alternativas": [
    {"letra": "A", "texto": "…"},
    …
    {"letra": "E", "texto": "…"}
  ],
  "gabarito": "C",
  "explicacao": "…"
}
```

Áreas válidas: `matematica`, `natureza`, `humanas`, `linguagens`.

Depois de editar, é só `git commit` e `git push`. A Vercel redeploya sozinha e a nova questão fica no ar em ~90 segundos.


## Limites e custos

- **Vercel Hobby (grátis)** — 100 GB de banda/mês, 60s por função. Suficiente para milhares de alunos.
- **Custo real** — só a API da IA. ~US$ 0,05 a US$ 0,10 por redação corrigida (Claude Sonnet), ~US$ 0,03 por questão gerada.
- **Sem persistência** — respostas e correções não são salvas. Cada sessão é independente. Se você quiser histórico por aluno, precisa de banco (Turso, Supabase etc).

Termos da Vercel Hobby proíbem uso comercial pesado. Para vender de verdade, migre para o Vercel Pro (US$ 20/mês) ou considere alternativas (Render, Railway).
