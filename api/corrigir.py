"""POST /api/corrigir — corrige uma redação pelas 5 competências do ENEM.

Autocontido: sem imports de outros módulos do projeto.
"""

from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler


COMPETENCIAS = {
    1: "Domínio da norma culta da língua portuguesa",
    2: "Compreender o tema e aplicar repertório sociocultural",
    3: "Selecionar, relacionar e organizar argumentos",
    4: "Domínio dos mecanismos linguísticos de coesão",
    5: "Elaborar proposta de intervenção respeitando os direitos humanos",
}

VALORES_ENEM = [0, 40, 80, 120, 160, 200]


SYSTEM = """Você é um corretor oficial de redações do ENEM, treinado pelo INEP.
Aplica a Matriz de Referência de forma rigorosa e justa, sem inflar notas.
Responde SEMPRE e SOMENTE com um objeto JSON válido, sem markdown e sem
texto fora do JSON."""


PROMPT = """Corrija a redação abaixo segundo as 5 competências oficiais do ENEM.

TEMA PROPOSTO:
{tema}

REDAÇÃO DO ALUNO:
\"\"\"{texto}\"\"\"

REGRAS DE CORREÇÃO:
- Cada competência vale 0, 40, 80, 120, 160 ou 200 pontos — use APENAS esses valores.
- Zere a redação inteira em caso de: fuga total ao tema, texto com menos de 7 linhas,
  desrespeito aos direitos humanos, ou não atendimento ao tipo dissertativo-argumentativo.
- Seja específico: cite trechos reais do texto do aluno em cada comentário.
- Justifique tecnicamente cada nota — nada de vaguezas do tipo "bom texto".

Responda EXATAMENTE neste JSON:
{{
  "competencias": [
    {{"numero": 1, "nota": 0, "comentario": "análise de 2 a 4 frases citando trechos"}},
    {{"numero": 2, "nota": 0, "comentario": "..."}},
    {{"numero": 3, "nota": 0, "comentario": "..."}},
    {{"numero": 4, "nota": 0, "comentario": "..."}},
    {{"numero": 5, "nota": 0, "comentario": "..."}}
  ],
  "resumo": "parágrafo curto com o diagnóstico geral",
  "pontos_fortes": ["3 a 5 pontos objetivos"],
  "pontos_a_melhorar": ["3 a 5 orientações acionáveis"],
  "reescritas": [
    {{"trecho_original": "trecho literal do aluno",
      "sugestao": "versão reescrita",
      "motivo": "por que a nova versão é melhor"}}
  ]
}}
Inclua 2 a 4 itens em "reescritas"."""


def _chamar_ia(system: str, prompt: str, max_tokens: int = 3500) -> str:
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

    raise RuntimeError("Nenhuma chave de IA configurada.")


def _extrair_json(bruto: str) -> dict:
    limpo = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        ini, fim = limpo.find("{"), limpo.rfind("}")
        if ini == -1 or fim == -1:
            raise ValueError("A IA não devolveu um JSON válido.")
        return json.loads(limpo[ini:fim + 1])


def _normalizar_nota(v) -> int:
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    v = max(0, min(200, v))
    return min(VALORES_ENEM, key=lambda x: abs(x - v))


class handler(BaseHTTPRequestHandler):
    def _responder(self, status: int, corpo: dict) -> None:
        payload = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > 200_000:
                return self._responder(400, {"erro": "Payload muito grande."})
            dados = json.loads(self.rfile.read(tamanho).decode("utf-8")) if tamanho else {}

            tema = str(dados.get("tema", "")).strip()
            texto = str(dados.get("texto", "")).strip()

            if len(tema) < 5:
                return self._responder(400, {"erro": "Informe o tema da redação (mínimo 5 caracteres)."})
            if len(texto.split()) < 50:
                return self._responder(400, {"erro": "A redação precisa ter pelo menos 50 palavras para ser avaliada."})
            if len(texto) > 15_000:
                return self._responder(400, {"erro": "Redação muito longa (máximo ~15.000 caracteres)."})

            bruto = _chamar_ia(SYSTEM, PROMPT.format(tema=tema, texto=texto))
            r = _extrair_json(bruto)

            comps, notas = [], {}
            for n in range(1, 6):
                item = next((c for c in r.get("competencias", []) if int(c.get("numero", 0)) == n), {})
                nota = _normalizar_nota(item.get("nota", 0))
                notas[n] = nota
                comps.append({
                    "numero": n, "titulo": COMPETENCIAS[n], "nota": nota,
                    "comentario": str(item.get("comentario", "—")).strip(),
                })

            return self._responder(200, {
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
            })

        except RuntimeError as e:
            self._responder(400, {"erro": str(e)})
        except ValueError as e:
            self._responder(400, {"erro": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            print(f"[ERRO corrigir] {type(e).__name__}: {e}", file=sys.stderr)
            self._responder(500, {"erro": str(e)[:200]})

    def log_message(self, format, *args):  # noqa: A002
        return
