"""Procesa una reunión: obtener → transcribir → entregables. Corre en el venv del plugin.

  worker.py <fuente> <dir_salida> <archivo_estado>

fuente: ruta local (video o audio) o enlace de OneDrive/SharePoint (Graph).
Efímero: la descarga y todo intermedio viven en VTK_DATA/tmp/<job> y se borran al terminar,
aunque falle. El audio se decodifica en memoria (PyAV): no se escribe ningún WAV.
Caché: la transcripción se guarda por SHA-256 del medio; repetir la misma grabación no
vuelve a transcribir. VTK_CONSERVAR=si deja también el medio descargado en la salida.
"""
import hashlib
import json
import os
import shutil
import sys
import time

# Perfiles medidos en docs/kit-dual/video/03-rendimiento.md (Core Ultra 7 165U, CPU, int8, 8 hilos).
# Sin BatchedInferencePipeline: era 4 % más rápido pero perdía ~8 % de las palabras y usaba +75 % de RAM.
PERFILES = {
    "rapido": {"model": "large-v3-turbo", "beam_size": 1},   # RTF 0,43, 2,0 GB
    "preciso": {"model": "large-v3-turbo", "beam_size": 5},  # RTF 0,57, 2,1 GB
}


def status(path, **kw):
    kw["actualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(kw, f, ensure_ascii=False)
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def hms(s):
    return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"


def transcribe(media, perfil, idioma, hilos, on_progress):
    from faster_whisper import WhisperModel

    p = PERFILES[perfil]
    # Caché estándar de Hugging Face (~/.cache/huggingface): si otra herramienta ya bajó el modelo,
    # no se vuelven a descargar 1,6 GB.
    model = WhisperModel(p["model"], device="cpu", compute_type="int8", cpu_threads=hilos)
    kw = {"beam_size": p["beam_size"], "language": None if idioma == "auto" else idioma}
    segs, info = model.transcribe(media, vad_filter=True, **kw)
    out = []
    for s in segs:
        out.append({"inicio": round(s.start, 1), "fin": round(s.end, 1), "texto": s.text.strip()})
        on_progress(s.end / info.duration if info.duration else 0)
    return {"duracion_s": round(info.duration, 1), "idioma": info.language,
            "voz_s": round(info.duration_after_vad or info.duration, 1), "segmentos": out}


def main():
    fuente, salida, estado = sys.argv[1:4]
    perfil = os.environ.get("VTK_PERFIL", "rapido")
    idioma = os.environ.get("VTK_IDIOMA", "es")
    hilos = int(os.environ.get("VTK_HILOS") or min(8, os.cpu_count() or 4))
    data = os.environ["VTK_DATA"]
    job = os.path.basename(salida.rstrip("/")) or "job"
    tmp = os.path.join(data, "tmp", job)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(salida, exist_ok=True)
    t0 = time.time()
    try:
        if fuente.startswith(("http://", "https://")):
            status(estado, fase="descargando", progreso=0)
            sys.path.insert(0, os.path.dirname(__file__))
            import graph
            media, nombre, _ = graph.download(fuente, tmp, notify=lambda m: status(estado, fase="login", mensaje=m))
        else:
            media, nombre = os.path.abspath(fuente), os.path.basename(fuente)
            if not os.path.isfile(media):
                raise FileNotFoundError(f"no existe {fuente}")
        status(estado, fase="huella", progreso=0)
        digest = sha256(media)
        cache = os.path.join(data, "cache", f"{digest}-{perfil}-{idioma}.json")
        if os.path.exists(cache):
            tx = json.load(open(cache))
            tx["desde_cache"] = True
        else:
            t1 = time.time()
            tx = transcribe(media, perfil, idioma, hilos,
                            lambda p: status(estado, fase="transcribiendo", progreso=round(p, 3)))
            tx["segundos_transcripcion"] = round(time.time() - t1, 1)
            tx["rtf"] = round(tx["segundos_transcripcion"] / tx["duracion_s"], 3) if tx["duracion_s"] else None
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            json.dump(tx, open(cache, "w"), ensure_ascii=False)
        md = [f"# Transcripción — {nombre}", "",
              f"Duración {hms(tx['duracion_s'])} · idioma {tx['idioma']} · perfil {perfil}", ""]
        md += [f"[{hms(s['inicio'])}] {s['texto']}" for s in tx["segmentos"]]
        open(os.path.join(salida, "transcripcion.md"), "w").write("\n".join(md) + "\n")
        if os.environ.get("VTK_CONSERVAR") == "si" and media.startswith(tmp):
            shutil.move(media, os.path.join(salida, nombre))
        resumen = {"fase": "listo", "progreso": 1, "salida": salida, "archivo": nombre,
                   "duracion_s": tx["duracion_s"], "voz_s": tx["voz_s"], "rtf": tx.get("rtf"),
                   "desde_cache": tx.get("desde_cache", False), "segundos_total": round(time.time() - t0, 1),
                   "perfil": perfil}
        status(estado, **resumen)
    except Exception as e:  # el estado lleva el error; nunca variables de entorno
        status(estado, fase="error", error=f"{type(e).__name__}: {e}")
        raise SystemExit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
