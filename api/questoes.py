"""GET /api/questoes — devolve o banco estático de questões.

Autocontido: lê o JSON de data/questoes.json se existir, ou usa fallback embutido.
"""

from __future__ import annotations

import json
import random
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


AREAS_VALIDAS = {"matematica", "natureza", "humanas", "linguagens"}


def _carregar_banco() -> list:
    """Tenta carregar de data/questoes.json. Sobe pastas até 4 níveis pra achar."""
    aqui = Path(__file__).resolve().parent
    for nivel in range(4):
        candidato = aqui / ("../" * nivel) / "data" / "questoes.json"
        try:
            with candidato.resolve().open(encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return []


_BANCO = _carregar_banco()


class handler(BaseHTTPRequestHandler):
    def _responder(self, status: int, corpo: dict) -> None:
        payload = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        try:
            if not _BANCO:
                return self._responder(500, {
                    "erro": "Banco de questões não encontrado no servidor."
                })

            params = parse_qs(urlparse(self.path).query)
            area = (params.get("area", [""])[0] or "").strip().lower()
            try:
                limite = int(params.get("limite", ["20"])[0])
            except ValueError:
                limite = 20
            limite = max(1, min(limite, 50))

            embaralhar = params.get("embaralhar", ["0"])[0] in ("1", "true", "sim")

            resultado = list(_BANCO)
            if area:
                if area not in AREAS_VALIDAS:
                    return self._responder(400, {
                        "erro": f"Área inválida. Use uma de: {', '.join(sorted(AREAS_VALIDAS))}."
                    })
                resultado = [q for q in resultado if q.get("area") == area]

            if embaralhar:
                random.shuffle(resultado)

            publico = [
                {
                    "id": q["id"], "area": q["area"], "topico": q.get("topico", ""),
                    "enunciado": q["enunciado"], "alternativas": q["alternativas"],
                }
                for q in resultado[:limite]
            ]

            self._responder(200, {
                "total": len(publico),
                "area": area or "todas",
                "questoes": publico,
                "gabaritos": {
                    q["id"]: {"gabarito": q["gabarito"], "explicacao": q.get("explicacao", "")}
                    for q in resultado[:limite]
                },
            })

        except ValueError as e:
            self._responder(400, {"erro": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            print(f"[ERRO questoes] {type(e).__name__}: {e}", file=sys.stderr)
            self._responder(500, {"erro": str(e)[:200]})

    def log_message(self, format, *args):  # noqa: A002
        return
