"""Salida a la red del plugin, con las protecciones comunes. Solo stdlib.

- Solo https (http únicamente a 127.0.0.1/localhost, para las pruebas): urllib también acepta file://.
- Certificados verificados (contexto por defecto de ssl).
- Redirecciones: o no se siguen (Groq: una API no redirige; si lo hace, algo anda mal), o se siguen solo hacia
  https y quitando Authorization cuando cambia el host (Graph: /content redirige a una URL de descarga
  pre-autorizada que no necesita el token).
"""
import urllib.error
import urllib.parse
import urllib.request

UA = "meeting-to-backlog/0.1"
LOCALES = ("127.0.0.1", "localhost")


class RedError(ValueError):
    pass


def _permitida(url):
    u = urllib.parse.urlparse(url)
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCALES)


class _Redirecciones(urllib.request.HTTPRedirectHandler):
    def __init__(self, seguir):
        self.seguir = seguir

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.seguir:
            raise RedError(f"redirección no esperada ({code}) hacia {urllib.parse.urlparse(newurl).hostname}")
        if not _permitida(newurl):
            raise RedError("redirección hacia un esquema no permitido")
        nuevo = super().redirect_request(req, fp, code, msg, headers, newurl)
        if nuevo is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            for h in list(nuevo.headers):  # el token nunca viaja a otro host
                if h.lower() == "authorization":
                    del nuevo.headers[h]
            nuevo.unredirected_hdrs.pop("Authorization", None)
        return nuevo


def abrir(req, timeout, seguir_redirecciones=False):
    if not _permitida(req.full_url):
        raise RedError("solo se permiten URL https")
    req.add_header("User-Agent", UA)  # Cloudflare (delante de Groq) bloquea el agente por defecto de urllib
    opener = urllib.request.build_opener(_Redirecciones(seguir_redirecciones))
    # El esquema ya está validado arriba y en cada redirección; por eso se silencia la regla de semgrep.
    return opener.open(req, timeout=timeout)  # nosemgrep
