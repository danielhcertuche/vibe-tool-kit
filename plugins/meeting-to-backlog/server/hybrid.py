"""Transcripción híbrida: un tramo continuo en local y el resto en la nube, en paralelo.

Medido (docs del kit): trocear en local no acelera (la CPU ya está al tope) y cada corte pierde palabras
porque el modelo arranca sin contexto. Por eso hay pocos cortes: el local se lleva un bloque continuo
(1 - pct) y la nube el tramo final en bloques de hasta BLOQUE_MAX s, todos cortados en silencios.

Controles: solo con pct > 0 pedido para esta reunión y con llave configurada; nunca más del 30 % ni de
lo que deja la cuota gratuita (cupo.py); el audio sale como FLAC
en memoria con nombre fijo, sin metadatos ni prompt; tope de proporción; ante 429 respeta retry-after y
tras 2 fallos el bloque vuelve a local; registro local (huella, proveedor, desplazamiento, código HTTP),
nunca audio ni texto.
"""
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

SR = 16000
BLOQUE_MAX = 600          # 10 min de FLAC 16 kHz mono ≈ 12–20 MB, bajo el tope de 25 MB de Groq
URL = os.environ.get("VTK_NUBE_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
MODELO = os.environ.get("VTK_NUBE_MODELO", "whisper-large-v3-turbo")


def _silencios(audio):
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    ts = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=300))
    return [(a["end"] + b["start"]) // 2 for a, b in zip(ts, ts[1:])]  # puntos medios de cada silencio


def _corte(sil, objetivo):
    return min(sil, key=lambda x: abs(x - objetivo)) if sil else objetivo


def plan(audio, pct):
    """[(inicio, fin, 'local'|'nube')] en muestras. Un bloque local y bloques de nube ≤ BLOQUE_MAX."""
    n = len(audio)
    if pct <= 0:
        return [(0, n, "local")]
    sil = _silencios(audio)
    corte = _corte(sil, int(n * (1 - pct)))
    out = [(0, corte, "local")]
    ini = corte
    while ini < n:
        fin = n if n - ini <= BLOQUE_MAX * SR else _corte([s for s in sil if ini < s < ini + BLOQUE_MAX * SR],
                                                        ini + BLOQUE_MAX * SR)
        out.append((ini, fin, "nube"))
        ini = fin
    return out


def _flac(audio):
    import av
    import numpy as np

    buf = io.BytesIO()
    with av.open(buf, "w", format="flac") as c:
        st = c.add_stream("flac", rate=SR, layout="mono")
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).reshape(1, -1)
        fr = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        fr.sample_rate = SR
        for p in st.encode(fr):
            c.mux(p)
        for p in st.encode(None):
            c.mux(p)
    return buf.getvalue()


def _abrir(req, timeout):
    """Solo https (o http a 127.0.0.1 para pruebas): urllib también acepta file://."""
    u = urllib.parse.urlparse(req.full_url)
    if not (u.scheme == "https" or (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost"))):
        raise ValueError("VTK_NUBE_URL debe ser https")
    # El esquema ya está validado arriba, por eso se silencia dynamic-urllib-use-detected.
    return urllib.request.urlopen(req, timeout=timeout)  # nosemgrep


def _post(data, idioma, key):
    b = "----vtk" + uuid.uuid4().hex
    parts = []
    for k, v in (("model", MODELO), ("response_format", "verbose_json"), ("temperature", "0")) + \
            ((("language", idioma),) if idioma != "auto" else ()):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="a.flac"\r\n'
                 f"Content-Type: audio/flac\r\n\r\n".encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(URL, data=b"".join(parts), headers={
        "Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + b,
        # Cloudflare (delante de Groq) rechaza el agente por defecto de urllib con 403 / error 1010.
        "User-Agent": "meeting-to-backlog/0.1"})
    with _abrir(req, 300) as r:
        return json.load(r)


def _nube(audio, ini, idioma, key, registro):
    data = _flac(audio)
    h = hashlib.sha256(data).hexdigest()[:16]
    for intento in range(3):
        t0 = time.time()
        code = 0
        try:
            res = _post(data, idioma, key)
            code = 200
            return [{"inicio": round(s["start"] + ini / SR, 1), "fin": round(s["end"] + ini / SR, 1),
                     "texto": s["text"].strip(), "origen": "nube"} for s in res.get("segments", [])]
        except urllib.error.HTTPError as e:
            code = e.code
            if e.code not in (429, 500, 502, 503, 504) or intento == 2:  # 4xx de cliente: no reintentar
                return None
            time.sleep(min(float(e.headers.get("retry-after") or 2 * (intento + 1)), 60))
        except (urllib.error.URLError, TimeoutError, ValueError):
            code = -1
            if intento == 2:
                return None
        finally:
            with open(registro, "a") as f:  # qué salió, nunca audio ni texto
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "huella": h,
                                    "proveedor": URL.split("/")[2], "desde_s": round(ini / SR, 1),
                                    "dur_s": round(len(audio) / SR, 1), "bytes": len(data),
                                    "http": code, "seg": round(time.time() - t0, 2)}) + "\n")
    return None


def transcribe(media, pct, idioma, transcribir_local, data_dir):
    """Devuelve (segmentos, duracion_s, detalle). transcribir_local(audio_np) -> segmentos con tiempos relativos."""
    from faster_whisper.audio import decode_audio

    import cupo

    key = os.environ.get("GROQ_API_KEY", "").strip()
    audio = decode_audio(media, sampling_rate=SR)
    registro = os.path.join(data_dir, "registro_nube.jsonl")
    dur = len(audio) / SR
    # Nunca más del 30 % ni más de lo que deja la cuota gratuita (hora, día, presupuesto del mes).
    mes_s = float(os.environ.get("VTK_NUBE_MES_MIN") or 0) * 60
    n_bloques = max(1, int(pct * dur // BLOQUE_MAX) + 1)
    pct_ef, limitado_por, uso = cupo.permitido(pct, dur, registro, n_bloques, mes_s) if key else (0.0, "sin llave", {})
    bloques = plan(audio, pct_ef)
    segs, devueltos = [], []
    nube = [(i, f) for i, f, d in bloques if d == "nube"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(_nube, audio[i:f], i, idioma, key, registro): (i, f) for i, f in nube}
        for i, f, d in bloques:  # el bloque local corre en este hilo mientras la nube trabaja
            if d == "local":
                segs += [dict(s, inicio=round(s["inicio"] + i / SR, 1), fin=round(s["fin"] + i / SR, 1),
                              origen="local") for s in transcribir_local(audio[i:f])]
        for fut, (i, f) in futs.items():
            r = fut.result()
            if r is None:  # la nube falló: ese bloque vuelve a local
                devueltos.append((i, f))
                r = [dict(s, inicio=round(s["inicio"] + i / SR, 1), fin=round(s["fin"] + i / SR, 1),
                          origen="local-respaldo") for s in transcribir_local(audio[i:f])]
            segs += r
    segs.sort(key=lambda s: s["inicio"])
    enviado = sum(f - i for i, f in nube) / len(audio) if len(audio) else 0
    return segs, round(len(audio) / SR, 1), {
        "bloques": len(bloques), "pct_pedido": pct, "pct_permitido": pct_ef, "limitado_por": limitado_por,
        "uso_previo": uso, "pct_enviado": round(enviado, 3),
        "bloques_nube": len(nube), "devueltos_a_local": len(devueltos), "llave": bool(key)}
