"""Local dev server for the calc viewer: serves the repo root (so the viewer can reach the source PDFs)
on 127.0.0.1 only, with caching off so edits show up on reload.

    python prototyping/calc-viewer/build/serve.py [port]
    then open http://127.0.0.1:8765/prototyping/calc-viewer/drawings.html
"""
import functools
import http.server
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".js": "text/javascript"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    # PORT (set by a launcher that had to move the port) wins over the command-line default
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8765))
    handler = functools.partial(Handler, directory=str(REPO))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving {REPO} at http://127.0.0.1:{port}/prototyping/calc-viewer/drawings.html")
        httpd.serve_forever()
