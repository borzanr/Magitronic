"""Servidor local que imita o GitHub Pages: /contato -> contato.html, 404.html para o resto.

Uso:  python tools/serve.py [porta]   (padrão 8080)
"""
import http.server
import sys
from functools import partial
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        target = DOCS / path.lstrip("/")
        if not path.endswith("/") and not target.exists() and target.with_suffix(".html").exists():
            self.path = path + ".html"
        elif path.endswith("/") and not (target / "index.html").exists() and not target.is_dir():
            return self._not_found()
        elif not path.endswith("/") and not target.exists():
            return self._not_found()
        return super().send_head()

    def _not_found(self):
        body = (DOCS / "404.html").read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    handler = partial(Handler, directory=str(DOCS))
    print(f"Servindo {DOCS} em http://localhost:{port}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
