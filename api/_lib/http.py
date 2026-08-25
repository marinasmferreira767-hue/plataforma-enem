"""Helpers para as funções serverless da Vercel.

Padrão da Vercel para Python: cada arquivo em /api/*.py exporta uma classe
`handler` que herda de BaseHTTPRequestHandler. Não é FastAPI — é a lib
padrão do Python. Estes helpers cortam boilerplate.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from typing import Any


def _erro_para_usuario(exc: Exception) -> str:
    """Mensagem enxuta e útil, sem vazar stack trace ou nomes internos."""
    texto = str(exc)
    if len(texto) > 200:
        texto = texto[:197] + "…"
    return texto or exc.__class__.__name__


class Handler(BaseHTTPRequestHandler):
    """Base para os endpoints. Filhos sobrescrevem processar()."""

    def _responder(self, status: int, corpo: dict[str, Any]) -> None:
        payload = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # Sem cache — endpoints são dinâmicos e não devem ficar guardados no CDN
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _ler_json(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho == 0:
            return {}
        if tamanho > 200_000:                       # ~200KB — protege contra abuso
            raise ValueError("Payload muito grande (máximo 200KB).")
        bruto = self.rfile.read(tamanho)
        try:
            return json.loads(bruto.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido no corpo da requisição: {e.msg}")

    # ─── Ciclo de vida ────────────────────────────────────────────────────
    # Cada endpoint sobrescreve processar_get() ou processar_post()

    def do_GET(self) -> None:      # noqa: N802 (nome fixado pela lib)
        try:
            self._responder(200, self.processar_get())
        except ValueError as e:
            self._responder(400, {"erro": _erro_para_usuario(e)})
        except NotImplementedError:
            self._responder(405, {"erro": "Método não permitido."})
        except Exception as e:      # noqa: BLE001 — devolve JSON, não HTML
            print(f"[ERRO] {type(e).__name__}: {e}", file=sys.stderr)
            self._responder(500, {"erro": _erro_para_usuario(e)})

    def do_POST(self) -> None:     # noqa: N802
        try:
            dados = self._ler_json()
            self._responder(200, self.processar_post(dados))
        except ValueError as e:
            self._responder(400, {"erro": _erro_para_usuario(e)})
        except NotImplementedError:
            self._responder(405, {"erro": "Método não permitido."})
        except Exception as e:      # noqa: BLE001
            print(f"[ERRO] {type(e).__name__}: {e}", file=sys.stderr)
            self._responder(500, {"erro": _erro_para_usuario(e)})

    def processar_get(self) -> dict:
        raise NotImplementedError

    def processar_post(self, dados: dict) -> dict:
        raise NotImplementedError

    def log_message(self, format: str, *args) -> None:   # noqa: A002
        """Silencia o access log padrão — a Vercel já faz isso melhor."""
        return
