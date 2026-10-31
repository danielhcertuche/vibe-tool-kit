"""Fotogramas de una reunión: candidatos baratos y selección de los 4 que se conservan.

Candidatos: solo fotogramas clave (I-frames, sin decodificar el resto del video), como mucho uno cada
MIN_GAP segundos, reducidos a ANCHO px. Se descartan los casi vacíos (entropía baja: pantalla negra,
transición) y los casi iguales a uno ya guardado (dHash): en una reunión la pantalla compartida cambia
poco, así que una hora deja decenas de candidatos, no miles.

Selección automática (garantía de que siempre quedan 4): los más informativos (entropía) separados en
el tiempo. La skill la reemplaza después por la guiada por la transcripción (conservar_fotogramas).
"""
import json
import math
import os
import shutil

N_FINAL = 4
MIN_GAP = float(os.environ.get("VTK_FOTO_GAP", "5"))
ANCHO = 960
MAX_CAND = 150
MIN_ENTROPIA = 2.5
MIN_DIST_HASH = 6


def _dhash(img):
    g = img.convert("L").resize((9, 8))
    px = list(g.getdata())
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def _entropia(img):
    h = img.convert("L").histogram()
    n = sum(h)
    return -sum(c / n * math.log2(c / n) for c in h if c)


def hms(s):
    return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"


def extraer_candidatos(media, dest):
    """Lista de candidatos [{t, archivo, entropia}] en dest/index.json; [] si no hay video."""
    import av

    os.makedirs(dest, exist_ok=True)
    idx = os.path.join(dest, "index.json")
    if os.path.exists(idx):
        return json.load(open(idx))
    cands, hashes, last = [], [], -1e9
    with av.open(media) as c:
        if not c.streams.video:
            json.dump([], open(idx, "w"))
            return []
        vs = c.streams.video[0]
        vs.codec_context.skip_frame = "NONKEY"
        for fr in c.decode(vs):
            t = float(fr.time or 0)
            if t - last < MIN_GAP:
                continue
            img = fr.to_image()
            e = _entropia(img)
            if e < MIN_ENTROPIA:
                continue
            h = _dhash(img)
            if any(bin(h ^ o).count("1") < MIN_DIST_HASH for o in hashes):
                continue
            last = t
            hashes.append(h)
            if img.width > ANCHO:
                img = img.resize((ANCHO, round(img.height * ANCHO / img.width)))
            name = f"c_{int(t):06d}.jpg"
            img.save(os.path.join(dest, name), "JPEG", quality=80)
            cands.append({"t": round(t, 1), "marca": hms(t), "archivo": name, "entropia": round(e, 2)})
    if len(cands) > MAX_CAND:  # se quedan los más informativos, en orden temporal
        keep = {x["archivo"] for x in sorted(cands, key=lambda x: -x["entropia"])[:MAX_CAND]}
        for x in cands:
            if x["archivo"] not in keep:
                os.remove(os.path.join(dest, x["archivo"]))
        cands = [x for x in cands if x["archivo"] in keep]
    json.dump(cands, open(idx, "w"), ensure_ascii=False)
    return cands


def seleccion_auto(cands, duracion):
    """Los N_FINAL más informativos, separados al menos duracion / (2·N_FINAL)."""
    sep = (duracion or 0) / (2 * N_FINAL)
    out = []
    for x in sorted(cands, key=lambda x: -x["entropia"]):
        if all(abs(x["t"] - y["t"]) >= sep for y in out):
            out.append(x)
        if len(out) == N_FINAL:
            break
    for x in sorted(cands, key=lambda x: -x["entropia"]):  # si la separación no alcanzó, se completa
        if len(out) == N_FINAL:
            break
        if x not in out:
            out.append(x)
    return sorted(out, key=lambda x: x["t"])


def publicar(elegidos, cand_dir, salida, modo):
    """Copia los elegidos a salida/fotogramas/ y escribe fotogramas.md. elegidos: [{archivo, t, motivo?, relacion?}]."""
    fdir = os.path.join(salida, "fotogramas")
    shutil.rmtree(fdir, ignore_errors=True)
    os.makedirs(fdir)
    md = [f"# Fotogramas clave ({modo})", "",
          "| # | Momento | Archivo | Por qué es relevante | Relacionado con |", "|---|---|---|---|---|"]
    for i, x in enumerate(elegidos, 1):
        name = f"f{i}_{hms(x['t']).replace(':', '')}.jpg"
        shutil.copy2(os.path.join(cand_dir, x["archivo"]), os.path.join(fdir, name))
        md.append(f"| {i} | `[{hms(x['t'])}]` | `fotogramas/{name}` | {x.get('motivo', 'más informativo de su tramo')} "
                  f"| {x.get('relacion', '—')} |")
    open(os.path.join(salida, "fotogramas.md"), "w").write("\n".join(md) + "\n")
    return len(elegidos)
