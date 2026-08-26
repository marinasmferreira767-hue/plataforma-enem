"""Plataforma ENEM — app FastAPI único (padrão Vercel 2025+).

A Vercel agora espera um único app Python (FastAPI/Flask) e faz o roteamento
sozinha. Este arquivo unifica os 3 endpoints antigos em rotas de um mesmo app.
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ─── Localizar diretórios do projeto ─────────────────────────────────────────
# Este arquivo está em api/index.py. A raiz do projeto é dois níveis acima.
RAIZ = Path(__file__).resolve().parent.parent
PUBLIC = RAIZ / "public"
DATA = RAIZ / "data"


# ─── Banco estático de questões ──────────────────────────────────────────────
try:
    with (DATA / "questoes.json").open(encoding="utf-8") as f:
        BANCO = json.load(f)
except FileNotFoundError:
    BANCO = []


AREAS = {
    "matematica": "Matemática e suas Tecnologias",
    "natureza":   "Ciências da Natureza e suas Tecnologias",
    "humanas":    "Ciências Humanas e suas Tecnologias",
    "linguagens": "Linguagens, Códigos e suas Tecnologias",
}

COMPETENCIAS = {
    1: "Domínio da norma culta da língua portuguesa",
    2: "Compreender o tema e aplicar repertório sociocultural",
    3: "Selecionar, relacionar e organizar argumentos",
    4: "Domínio dos mecanismos linguísticos de coesão",
    5: "Elaborar proposta de intervenção respeitando os direitos humanos",
}

VALORES_ENEM = [0, 40, 80, 120, 160, 200]


# ─── Camada de IA ────────────────────────────────────────────────────────────
def chamar_ia(system: str, prompt: str, max_tokens: int = 3200) -> str:
    """Chama Anthropic (prioridade) ou OpenAI."""
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        from anthropic import Anthropic
        cliente = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip())
        modelo = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        resp = cliente.messages.create(
            model=modelo, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    if os.environ.get("OPENAI_API_KEY", "").strip():
        from openai import OpenAI
        cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
        modelo = os.environ.get("OPENAI_MODEL", "gpt-4o")
        resp = cliente.chat.completions.create(
            model=modelo, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    raise HTTPException(400, "Nenhuma chave de IA configurada.")


def extrair_json(bruto: str) -> dict:
    limpo = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        ini, fim = limpo.find("{"), limpo.rfind("}")
        if ini == -1 or fim == -1:
            raise HTTPException(502, "A IA não devolveu um JSON válido.")
        return json.loads(limpo[ini:fim + 1])


def normalizar_nota(v) -> int:
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    v = max(0, min(200, v))
    return min(VALORES_ENEM, key=lambda x: abs(x - v))


# ─── Prompts ─────────────────────────────────────────────────────────────────
SYSTEM_CORRIGIR = """Você é um corretor oficial de redações do ENEM, treinado pelo INEP.
Aplica a Matriz de Referência de forma rigorosa e justa, sem inflar notas.
Responde SEMPRE e SOMENTE com um objeto JSON válido, sem markdown."""

PROMPT_CORRIGIR = """Corrija a redação abaixo segundo as 5 competências oficiais do ENEM.

TEMA PROPOSTO:
{tema}

REDAÇÃO DO ALUNO:
\"\"\"{texto}\"\"\"

REGRAS:
- Cada competência vale 0, 40, 80, 120, 160 ou 200 pontos — use APENAS esses valores.
- Zere em caso de: fuga total ao tema, menos de 7 linhas, desrespeito aos direitos humanos.
- Cite trechos reais do texto do aluno em cada comentário.

Responda EXATAMENTE neste JSON:
{{
  "competencias": [
    {{"numero": 1, "nota": 0, "comentario": "..."}},
    {{"numero": 2, "nota": 0, "comentario": "..."}},
    {{"numero": 3, "nota": 0, "comentario": "..."}},
    {{"numero": 4, "nota": 0, "comentario": "..."}},
    {{"numero": 5, "nota": 0, "comentario": "..."}}
  ],
  "resumo": "parágrafo curto com o diagnóstico geral",
  "pontos_fortes": ["3 a 5 pontos"],
  "pontos_a_melhorar": ["3 a 5 orientações"],
  "reescritas": [
    {{"trecho_original": "...", "sugestao": "...", "motivo": "..."}}
  ]
}}"""

SYSTEM_GERAR = """Você é um elaborador de questões objetivas do ENEM.
Suas questões são inéditas e contextualizadas. Distratores refletem erros conceituais reais.
Responde SEMPRE e SOMENTE com JSON válido, sem markdown."""

PROMPT_GERAR = """Elabore {n} questões inéditas do ENEM sobre o tópico:

ÁREA: {area}
TÓPICO: {topico}

REGRAS:
- 5 alternativas (A-E), uma única correta.
- Enunciado com contexto (texto/dado/situação).
- Distratores plausíveis (erros conceituais reais).
- Explicação mostra o raciocínio e por que cada distrator está errado.

Responda EXATAMENTE neste JSON:
{{
  "questoes": [
    {{
      "enunciado": "...",
      "alternativas": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
      "gabarito": "A",
      "explicacao": "..."
    }}
  ]
}}"""


# ─── Modelos Pydantic ────────────────────────────────────────────────────────
class EntradaRedacao(BaseModel):
    tema: str = Field(min_length=5, max_length=300)
    texto: str = Field(min_length=1, max_length=15000)


class EntradaGerar(BaseModel):
    area: str
    topico: str = Field(min_length=3, max_length=200)
    quantidade: int = Field(default=3, ge=1, le=5)


# ─── App FastAPI ─────────────────────────────────────────────────────────────
app = FastAPI(title="Plataforma ENEM", docs_url="/api/docs", redoc_url=None)


@app.post("/api/corrigir")
def corrigir(entrada: EntradaRedacao):
    if len(entrada.texto.split()) < 50:
        raise HTTPException(400, "A redação precisa ter pelo menos 50 palavras.")

    bruto = chamar_ia(SYSTEM_CORRIGIR,
                      PROMPT_CORRIGIR.format(tema=entrada.tema, texto=entrada.texto),
                      max_tokens=3500)
    r = extrair_json(bruto)

    comps, notas = [], {}
    for n in range(1, 6):
        item = next((c for c in r.get("competencias", []) if int(c.get("numero", 0)) == n), {})
        nota = normalizar_nota(item.get("nota", 0))
        notas[n] = nota
        comps.append({
            "numero": n, "titulo": COMPETENCIAS[n], "nota": nota,
            "comentario": str(item.get("comentario", "—")).strip(),
        })

    return {
        "nota_final": sum(notas.values()),
        "competencias": comps,
        "resumo": str(r.get("resumo", "")).strip(),
        "pontos_fortes": [str(p).strip() for p in (r.get("pontos_fortes") or [])[:5]],
        "pontos_a_melhorar": [str(p).strip() for p in (r.get("pontos_a_melhorar") or [])[:5]],
        "reescritas": [
            {"trecho_original": str(x.get("trecho_original", "")).strip(),
             "sugestao": str(x.get("sugestao", "")).strip(),
             "motivo": str(x.get("motivo", "")).strip()}
            for x in (r.get("reescritas") or [])[:4]
            if x.get("trecho_original") and x.get("sugestao")
        ],
    }


@app.post("/api/gerar")
def gerar(entrada: EntradaGerar):
    area = entrada.area.strip().lower()
    if area not in AREAS:
        raise HTTPException(400, f"Área inválida. Use uma de: {', '.join(AREAS)}.")

    bruto = chamar_ia(SYSTEM_GERAR,
                      PROMPT_GERAR.format(n=entrada.quantidade, area=AREAS[area],
                                          topico=entrada.topico))
    r = extrair_json(bruto)

    questoes = []
    for i, q in enumerate((r.get("questoes") or [])[:entrada.quantidade], start=1):
        alts = q.get("alternativas") or {}
        gab = str(q.get("gabarito", "")).strip().upper()[:1]
        if gab not in "ABCDE" or not all(alts.get(letra) for letra in "ABCDE"):
            continue
        questoes.append({
            "id": f"ia-{i}", "area": area, "topico": entrada.topico,
            "enunciado": str(q.get("enunciado", "")).strip(),
            "alternativas": [{"letra": L, "texto": str(alts[L]).strip()} for L in "ABCDE"],
            "gabarito": gab,
            "explicacao": str(q.get("explicacao", "")).strip(),
        })

    if not questoes:
        raise HTTPException(502, "A IA não devolveu questões válidas. Tente novamente.")

    return {"questoes": questoes, "area": AREAS[area], "topico": entrada.topico}


@app.get("/api/questoes")
def listar_questoes(area: str = "", limite: int = 20, embaralhar: bool = False):
    if not BANCO:
        raise HTTPException(500, "Banco de questões não encontrado.")

    limite = max(1, min(limite, 50))
    area = area.strip().lower()

    resultado = list(BANCO)
    if area:
        if area not in AREAS:
            raise HTTPException(400, f"Área inválida. Use uma de: {', '.join(AREAS)}.")
        resultado = [q for q in resultado if q.get("area") == area]

    if embaralhar:
        random.shuffle(resultado)

    resultado = resultado[:limite]

    return {
        "total": len(resultado),
        "area": area or "todas",
        "questoes": [
            {"id": q["id"], "area": q["area"], "topico": q.get("topico", ""),
             "enunciado": q["enunciado"], "alternativas": q["alternativas"]}
            for q in resultado
        ],
        "gabaritos": {
            q["id"]: {"gabarito": q["gabarito"], "explicacao": q.get("explicacao", "")}
            for q in resultado
        },
    }


# ─── Arquivos estáticos e rotas HTML ─────────────────────────────────────────
if PUBLIC.exists():
    # Serve arquivos estáticos (CSS, JS) direto de /public/
    app.mount("/static", StaticFiles(directory=PUBLIC), name="static")

    @app.get("/")
    def landing():
        return FileResponse(PUBLIC / "index.html")

    @app.get("/plataforma")
    def plataforma():
        return FileResponse(PUBLIC / "app.html")

    @app.get("/{arquivo:path}")
    def arquivos_publicos(arquivo: str):
        """Serve app.css, app.js, landing.css, etc. direto da raiz."""
        alvo = PUBLIC / arquivo
        if alvo.is_file():
            return FileResponse(alvo)
        return JSONResponse({"erro": "Não encontrado"}, status_code=404)
