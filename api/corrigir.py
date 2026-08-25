"""POST /api/corrigir — corrige uma redação pelas 5 competências do ENEM."""

from __future__ import annotations

import sys
from pathlib import Path

# Necessário para importar de api/_lib/ quando a Vercel executa este arquivo
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.http import Handler
from _lib.ia import chamar, extrair_json, ia_disponivel


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


def _normalizar_nota(v) -> int:
    """Força qualquer valor devolvido pela IA para os 6 valores válidos do ENEM."""
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    v = max(0, min(200, v))
    return min(VALORES_ENEM, key=lambda x: abs(x - v))


class handler(Handler):
    def processar_post(self, dados: dict) -> dict:
        tema = str(dados.get("tema", "")).strip()
        texto = str(dados.get("texto", "")).strip()

        if len(tema) < 5:
            raise ValueError("Informe o tema da redação (mínimo 5 caracteres).")
        if len(texto.split()) < 50:
            raise ValueError("A redação precisa ter pelo menos 50 palavras para ser avaliada.")
        if len(texto) > 15_000:
            raise ValueError("Redação muito longa (máximo ~15.000 caracteres).")
        if not ia_disponivel():
            raise ValueError("Correção por IA indisponível: chave de API não configurada.")

        bruto = chamar(SYSTEM, PROMPT.format(tema=tema, texto=texto), max_tokens=3500)
        r = extrair_json(bruto)

        # sanitiza cada competência
        comps = []
        notas = {}
        for n in range(1, 6):
            item = next((c for c in r.get("competencias", []) if int(c.get("numero", 0)) == n), {})
            nota = _normalizar_nota(item.get("nota", 0))
            notas[n] = nota
            comps.append({
                "numero": n,
                "titulo": COMPETENCIAS[n],
                "nota": nota,
                "comentario": str(item.get("comentario", "—")).strip(),
            })

        return {
            "nota_final": sum(notas.values()),
            "competencias": comps,
            "resumo": str(r.get("resumo", "")).strip(),
            "pontos_fortes": [str(p).strip() for p in (r.get("pontos_fortes") or [])[:5]],
            "pontos_a_melhorar": [str(p).strip() for p in (r.get("pontos_a_melhorar") or [])[:5]],
            "reescritas": [
                {
                    "trecho_original": str(x.get("trecho_original", "")).strip(),
                    "sugestao": str(x.get("sugestao", "")).strip(),
                    "motivo": str(x.get("motivo", "")).strip(),
                }
                for x in (r.get("reescritas") or [])[:4]
                if x.get("trecho_original") and x.get("sugestao")
            ],
        }
