"""GET /api/questoes — devolve o banco estático de questões, com filtros opcionais.

Query params:
  ?area=matematica    filtra por área (matematica|natureza|humanas|linguagens)
  ?limite=10          quantas questões devolver (padrão 20, máx 50)
  ?embaralhar=1       randomiza a ordem
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.http import Handler


# Carrega o JSON uma vez por instância da função — Vercel reusa instâncias
# entre invocações dentro de uma mesma "warm window", então isso vira cache
BANCO_PATH = Path(__file__).resolve().parent.parent / "data" / "questoes.json"

try:
    with BANCO_PATH.open(encoding="utf-8") as f:
        _BANCO = json.load(f)
except FileNotFoundError:
    _BANCO = []


AREAS_VALIDAS = {"matematica", "natureza", "humanas", "linguagens"}


class handler(Handler):
    def processar_get(self) -> dict:
        params = parse_qs(urlparse(self.path).query)

        area = (params.get("area", [""])[0] or "").strip().lower()
        try:
            limite = int(params.get("limite", ["20"])[0])
        except ValueError:
            limite = 20
        limite = max(1, min(limite, 50))

        embaralhar = params.get("embaralhar", ["0"])[0] in ("1", "true", "sim")

        # filtra
        resultado = list(_BANCO)
        if area:
            if area not in AREAS_VALIDAS:
                raise ValueError(f"Área inválida. Use uma de: {', '.join(sorted(AREAS_VALIDAS))}.")
            resultado = [q for q in resultado if q.get("area") == area]

        if embaralhar:
            random.shuffle(resultado)

        # não vaza gabarito nem explicação — a resposta certa só vem via /api/questoes/{id}/gabarito
        # aqui devolve só o que o aluno precisa para responder
        publico = [
            {
                "id": q["id"],
                "area": q["area"],
                "topico": q.get("topico", ""),
                "enunciado": q["enunciado"],
                "alternativas": q["alternativas"],
            }
            for q in resultado[:limite]
        ]

        return {
            "total": len(publico),
            "area": area or "todas",
            "questoes": publico,
            # devolve gabaritos como um mapa separado para o cliente resolver localmente
            # (esta plataforma é sem persistência — não faz sentido esconder do JS)
            "gabaritos": {
                q["id"]: {"gabarito": q["gabarito"], "explicacao": q.get("explicacao", "")}
                for q in resultado[:limite]
            },
        }
