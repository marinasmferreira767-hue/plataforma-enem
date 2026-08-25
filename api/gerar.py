"""POST /api/gerar — gera questões inéditas no padrão ENEM."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.http import Handler
from _lib.ia import chamar, extrair_json, ia_disponivel


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


class handler(Handler):
    def processar_post(self, dados: dict) -> dict:
        area = str(dados.get("area", "")).strip().lower()
        topico = str(dados.get("topico", "")).strip()

        try:
            n = int(dados.get("quantidade", 3))
        except (TypeError, ValueError):
            n = 3
        n = max(1, min(n, 5))

        if area not in AREAS:
            areas_validas = ", ".join(AREAS)
            raise ValueError(f"Área inválida. Use uma de: {areas_validas}.")
        if len(topico) < 3:
            raise ValueError("Descreva melhor o tópico (mínimo 3 caracteres).")
        if len(topico) > 200:
            raise ValueError("Tópico muito longo (máximo 200 caracteres).")
        if not ia_disponivel():
            raise ValueError("Geração por IA indisponível: chave de API não configurada.")

        bruto = chamar(
            SYSTEM,
            PROMPT.format(n=n, area=AREAS[area], topico=topico),
            max_tokens=3200,
        )
        r = extrair_json(bruto)

        # valida e limpa
        questoes = []
        for i, q in enumerate((r.get("questoes") or [])[:n], start=1):
            alts = q.get("alternativas") or {}
            gab = str(q.get("gabarito", "")).strip().upper()[:1]

            if gab not in "ABCDE":
                continue
            if not all(alts.get(letra) for letra in "ABCDE"):
                continue

            questoes.append({
                "id": f"ia-{i}",
                "area": area,
                "topico": topico,
                "enunciado": str(q.get("enunciado", "")).strip(),
                "alternativas": [
                    {"letra": letra, "texto": str(alts[letra]).strip()}
                    for letra in "ABCDE"
                ],
                "gabarito": gab,
                "explicacao": str(q.get("explicacao", "")).strip(),
            })

        if not questoes:
            raise ValueError("A IA não devolveu questões válidas. Tente novamente.")

        return {"questoes": questoes, "area": AREAS[area], "topico": topico}
