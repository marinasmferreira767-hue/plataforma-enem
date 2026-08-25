"""POST /api/gerar — gera questões inéditas no padrão ENEM.

Autocontido: sem imports de outros módulos do projeto.
"""

from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler


AREAS = {
    "matematica": "Matemática e suas Tecnologias",
    "natureza":   "Ciências da Natureza e suas Tecnologias",
    "humanas":    "Ciências Humanas e suas Tecnologias",
    "linguagens": "Linguagens, Códigos e suas Tecnologias",
}


SYSTEM = """Você é um elaborador oficial de questões objetivas do ENEM.
Suas questões são inéditas, tecnicamente precisas e contextualizadas:
partem sempre de uma situação-problema, texto ou dado, e cobram uma
habilidade específica. Os distratores refletem erros conceituais reais
que o aluno cometeria, nunca são absurdos.
Você responde SEMPRE e SOMENTE com JSON válido — sem markdown, sem
texto fora do JSON."""


PROMPT = """Elabore {n} questões inéditas, no padrão ENEM, sobre o tópico abaixo.

ÁREA: {area}
TÓPICO: {topico}

REGRAS OBRIGATÓRIAS:
- Cada questão tem EXATAMENTE 5 alternativas (A, B, C, D, E) e UMA única correta.
- O enunciado começa com um contexto (texto curto, dado, situação-problema).
- Os distratores refletem erros conceituais reais — nada de "todas as anteriores"
  ou "nenhuma das anteriores".
- A explicação mostra o raciocínio completo até a resposta e, em uma linha por
  distrator, por que cada alternativa errada está errada.
- Nada de referências a imagens, tabelas ou anexos que não estejam descritos
  em palavras dentro do próprio enunciado.
- Não cite direitos autorais, provas anteriores ou gabaritos oficiais.

Responda EXATAMENTE neste JSON:
{{
  "questoes": [
    {{
      "enunciado": "texto completo com contexto e pergunta",
      "alternativas": {{
        "A": "texto da alternativa A",
        "B": "texto da alternativa B",
        "C": "texto da alternativa C",
        "D": "texto da alternativa D",
        "E": "texto da alternativa E"
      }},
      "gabarito": "A",
      "explicacao": "resolução em 3 a 6 frases, terminando com por que os distratores estão errados"
    }}
  ]
}}"""


def _chamar_ia(system: str, prompt: str, max_tokens: int = 3200) -> str:
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

            area = str(dados.get("area", "")).strip().lower()
            topico = str(dados.get("topico", "")).strip()

            try:
                n = int(dados.get("quantidade", 3))
            except (TypeError, ValueError):
                n = 3
            n = max(1, min(n, 5))

            if area not in AREAS:
                return self._responder(400, {"erro": f"Área inválida. Use uma de: {', '.join(AREAS)}."})
            if len(topico) < 3:
                return self._responder(400, {"erro": "Descreva melhor o tópico (mínimo 3 caracteres)."})
            if len(topico) > 200:
                return self._responder(400, {"erro": "Tópico muito longo (máximo 200 caracteres)."})

            bruto = _chamar_ia(SYSTEM, PROMPT.format(n=n, area=AREAS[area], topico=topico))
            r = _extrair_json(bruto)

            questoes = []
            for i, q in enumerate((r.get("questoes") or [])[:n], start=1):
                alts = q.get("alternativas") or {}
                gab = str(q.get("gabarito", "")).strip().upper()[:1]

                if gab not in "ABCDE":
                    continue
                if not all(alts.get(letra) for letra in "ABCDE"):
                    continue

                questoes.append({
                    "id": f"ia-{i}", "area": area, "topico": topico,
                    "enunciado": str(q.get("enunciado", "")).strip(),
                    "alternativas": [
                        {"letra": letra, "texto": str(alts[letra]).strip()}
                        for letra in "ABCDE"
                    ],
                    "gabarito": gab,
                    "explicacao": str(q.get("explicacao", "")).strip(),
                })

            if not questoes:
                return self._responder(400, {"erro": "A IA não devolveu questões válidas. Tente novamente."})

            return self._responder(200, {"questoes": questoes, "area": AREAS[area], "topico": topico})

        except RuntimeError as e:
            self._responder(400, {"erro": str(e)})
        except ValueError as e:
            self._responder(400, {"erro": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            print(f"[ERRO gerar] {type(e).__name__}: {e}", file=sys.stderr)
            self._responder(500, {"erro": str(e)[:200]})

    def log_message(self, format, *args):  # noqa: A002
        return
