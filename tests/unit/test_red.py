"""Pruebas de red.py: esquemas permitidos y redirecciones seguras, con servidores locales.

  python3 tests/unit/test_red.py
"""
import http.server
import os
import sys
import threading
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "meeting-to-backlog", "server"))
import red  # noqa: E402

ok = []
vistos = {}


def check(c, m):
    ok.append(bool(c))
    print(("ok   " if c else "FAIL ") + m)


def servidor(nombre, destino=None):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            vistos[nombre] = self.headers.get("Authorization")
            if destino:
                self.send_response(302)
                self.send_header("Location", destino(self.path))
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


def pide(url, seguir):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer secreto"})
    try:
        with red.abrir(req, 5, seguir_redirecciones=seguir) as r:
            return r.read()
    except (red.RedError, urllib.error.HTTPError) as e:  # rechazo por red.py o por el propio urllib
        return e


for url in ("file:///etc/passwd", "http://example.com/x", "ftp://example.com/x"):
    check(isinstance(pide(url, True), red.RedError), f"rechaza {url.split(':')[0]}:// no permitido")

final, url_final = servidor("final")
otro, url_otro = servidor("otro_host", destino=lambda p: url_final + "/archivo")
mismo, url_mismo = servidor("mismo_host", destino=lambda p: "/fin" if p == "/" else None)
a_file, url_file = servidor("a_file", destino=lambda p: "file:///etc/passwd")
a_http, url_http = servidor("a_http", destino=lambda p: "http://example.com/robo")

check(isinstance(pide(url_otro, False), red.RedError), "sin seguir redirecciones (Groq): una redirección es error")

vistos.clear()
r = pide(url_otro, True)
check(r == b"ok", "con redirecciones (Graph): llega al destino")
check(vistos.get("otro_host") == "Bearer secreto", "el token llega al host original")
check(vistos.get("final") is None, "el token NO viaja a otro host tras la redirección")

check(isinstance(pide(url_file, True), Exception), "redirección hacia file:// rechazada")
check(isinstance(pide(url_http, True), Exception), "redirección hacia http externo rechazada")

req = urllib.request.Request(url_final)
with red.abrir(req, 5) as resp:
    resp.read()
check(req.get_header("User-agent") == red.UA, "identifica el cliente (Cloudflare bloquea el agente de urllib)")

for s in (final, otro, mismo, a_file, a_http):
    s.shutdown()
print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
