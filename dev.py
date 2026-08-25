"""Servidor local para dev — replica o comportamento da Vercel.

  python dev.py

Rota / e /plataforma → serve arquivos de /public/.
Rota /api/<funcao>   → carrega api/<funcao>.py e instancia sua classe handler.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PUBLIC = RAIZ / "public"
API = RAIZ / "api"

# carrega .env se existir
env_file = RAIZ / ".env"
if env_file.exists():
    for linha in env_file.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip())


def _carregar_handler(nome_funcao: str):
    """Importa api/<nome>.py e devolve sua classe `handler`."""
    caminho = API / f"{nome_funcao}.py"
    if not caminho.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"api_{nome_funcao}", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.handler


class DevHandler(BaseHTTPRequestHandler):
    def _servir_arquivo(self, caminho: Path):
        if not caminho.is_file():
            self.send_error(404, "Arquivo não encontrado")
            return
        conteudo = caminho.read_bytes()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css":  "text/css; charset=utf-8",
            ".js":   "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg":  "image/svg+xml",
            ".png":  "image/png",
        }.get(caminho.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(conteudo)))
        self.end_headers()
        self.wfile.write(conteudo)

    def _delegar_api(self):
        # /api/foo/bar → foo (a Vercel só olha o primeiro segmento)
        partes = self.path.lstrip("/").split("?")[0].split("/")
        if len(partes) < 2 or partes[0] != "api":
            self.send_error(404)
            return
        nome = partes[1]
        handler_cls = _carregar_handler(nome)
        if not handler_cls:
            self.send_error(404, f"Endpoint /api/{nome} não existe")
            return
        # instancia o handler manualmente reaproveitando o socket
        handler = handler_cls.__new__(handler_cls)
        handler.rfile = self.rfile
        handler.wfile = self.wfile
        handler.headers = self.headers
        handler.path = self.path
        handler.command = self.command
        handler.request_version = self.request_version
        handler.client_address = self.client_address
        handler.server = self.server
        handler.requestline = self.requestline
        handler.raw_requestline = self.raw_requestline
        handler.protocol_version = self.protocol_version
        # roda o do_GET/do_POST correto
        metodo = getattr(handler, f"do_{self.command}")
        metodo()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/api/"):
            return self._delegar_api()
        # rewrite: /plataforma → app.html
        if p == "/plataforma":
            return self._servir_arquivo(PUBLIC / "app.html")
        if p == "/":
            return self._servir_arquivo(PUBLIC / "index.html")
        arq = PUBLIC / p.lstrip("/")
        return self._servir_arquivo(arq)

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._delegar_api()
        self.send_error(405)

    def log_message(self, format, *args):
        sys.stderr.write(f"  {self.command} {self.path} → {args[1]}\n")


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8000"))
    print(f"→ Dev server em http://localhost:{porta}")
    print(f"→ Landing:  http://localhost:{porta}/")
    print(f"→ App:      http://localhost:{porta}/plataforma")
    print(f"→ API:      http://localhost:{porta}/api/questoes")
    print()
    ThreadingHTTPServer(("0.0.0.0", porta), DevHandler).serve_forever()
