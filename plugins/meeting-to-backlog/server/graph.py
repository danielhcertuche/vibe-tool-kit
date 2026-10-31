"""Descarga de grabaciones desde OneDrive/SharePoint por Microsoft Graph. Solo stdlib.

Dos modos, elegidos por GRAPH_AUTH:
  aplicacion  client credentials (GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET).
              El secreto llega solo por el entorno del servidor MCP (userConfig sensible).
  delegado    device code: cada usuario inicia sesión y Graph aplica sus propios permisos.
              El token se cachea en VTK_DATA/graph_token.json con permisos 600.
Ningún mensaje de error incluye el secreto ni el token.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import red

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com"
DELEGATED_SCOPE = "offline_access Files.Read.All"


class GraphError(RuntimeError):
    pass


def _abrir(req, timeout):
    # https obligatorio; /content redirige a una URL pre-autorizada: se sigue sin el token (red.py).
    try:
        return red.abrir(req, timeout, seguir_redirecciones=True)
    except red.RedError as e:
        raise GraphError(str(e)) from None


def _post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    try:
        req = urllib.request.Request(url, data=data, headers={})
        with _abrir(req, 60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
        return {"error": body.get("error", str(e.code)), "error_description": body.get("error_description", "")}


def _need(k):
    v = os.environ.get(k, "").strip()
    if not v:
        raise GraphError(f"falta {k}: configúralo en el plugin (claude plugin configure meeting-to-backlog@…)")
    return v


def _app_token():
    tenant = _need("GRAPH_TENANT_ID")
    tok = _post(f"{LOGIN}/{tenant}/oauth2/v2.0/token", {
        "grant_type": "client_credentials", "client_id": _need("GRAPH_CLIENT_ID"),
        "client_secret": _need("GRAPH_CLIENT_SECRET"), "scope": "https://graph.microsoft.com/.default"})
    if "access_token" not in tok:
        # Solo el código de error de Entra (p. ej. invalid_client), nunca la descripción completa.
        raise GraphError(f"token de aplicación rechazado: {tok.get('error')}")
    return tok["access_token"]


def _cache_path():
    return os.path.join(os.environ["VTK_DATA"], "graph_token.json")


def _save(tok):
    p = _cache_path()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"refresh_token": tok.get("refresh_token"), "access_token": tok["access_token"],
                   "expira": time.time() + int(tok.get("expires_in", 0)) - 60}, f)


def _delegated_token(notify):
    tenant, client = _need("GRAPH_TENANT_ID"), _need("GRAPH_CLIENT_ID")
    url = f"{LOGIN}/{tenant}/oauth2/v2.0"
    try:
        c = json.load(open(_cache_path()))
        if c.get("expira", 0) > time.time():
            return c["access_token"]
        if c.get("refresh_token"):
            tok = _post(f"{url}/token", {"grant_type": "refresh_token", "client_id": client,
                                          "refresh_token": c["refresh_token"], "scope": DELEGATED_SCOPE})
            if "access_token" in tok:
                _save(tok)
                return tok["access_token"]
    except (OSError, ValueError):
        pass
    dc = _post(f"{url}/devicecode", {"client_id": client, "scope": DELEGATED_SCOPE})
    if "device_code" not in dc:
        raise GraphError(f"no se pudo iniciar el inicio de sesión: {dc.get('error')}")
    notify(f"Inicia sesión: abre {dc['verification_uri']} y escribe el código {dc['user_code']}")
    deadline = time.time() + int(dc.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(int(dc.get("interval", 5)))
        tok = _post(f"{url}/token", {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                      "client_id": client, "device_code": dc["device_code"]})
        if "access_token" in tok:
            _save(tok)
            return tok["access_token"]
        if tok.get("error") not in ("authorization_pending", "slow_down"):
            raise GraphError(f"inicio de sesión fallido: {tok.get('error')}")
    raise GraphError("el código de inicio de sesión expiró")


def token(notify=print):
    mode = os.environ.get("GRAPH_AUTH", "delegado")
    if mode == "aplicacion":
        return _app_token()
    if mode == "delegado":
        return _delegated_token(notify)
    raise GraphError("GRAPH_AUTH vale 'ninguno': usa un archivo local o configura Graph")


def _get(tok, path):
    req = urllib.request.Request(GRAPH + path, headers={"Authorization": "Bearer " + tok})
    try:
        with _abrir(req, 120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise GraphError(f"Graph respondió {e.code} en {path.split('?')[0]}") from None


def download(url, dest_dir, notify=print):
    """Descarga el archivo de un enlace compartido a dest_dir. Devuelve (ruta, nombre, bytes)."""
    tok = token(notify)
    enc = "u!" + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    item = _get(tok, f"/shares/{enc}/driveItem?$select=id,name,size,parentReference")
    drive = item["parentReference"]["driveId"]
    name = os.path.basename(item["name"]) or "grabacion.mp4"
    out = os.path.join(dest_dir, name)
    req = urllib.request.Request(f"{GRAPH}/drives/{drive}/items/{item['id']}/content",
                                 headers={"Authorization": "Bearer " + tok})
    total = 0
    with _abrir(req, 1800) as r, open(out, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
            total += len(chunk)
    return out, name, total
