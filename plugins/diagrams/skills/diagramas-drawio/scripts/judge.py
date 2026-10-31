#!/usr/bin/env python3
"""Juez de diagramas: rasteriza, compara variantes píxel a píxel y puntúa.

POR QUÉ UN JUEZ Y NO SÓLO EL VALIDADOR
--------------------------------------
`forge.py validate` demuestra que la geometría es correcta (nada se solapa, nada
se sale, el texto cabe). No demuestra que el diagrama se vea bien: densidad de
tinta, equilibrio del blanco, alineación de columnas y estabilidad entre
iteraciones son juicios sobre píxeles. Este script produce la evidencia para
esos juicios y para que el modelo mire una imagen, no un XML.

QUÉ HACE
--------
1. `render`  SVG -> PNG a DPI fijo (PyMuPDF). Determinista y sin navegador.
2. `compare` A.png vs B.png: % de píxeles distintos, mapa de calor de la
   diferencia y tira comparativa lado a lado.
3. `score`   métricas objetivas de una sola imagen + los hallazgos del
   .metrics.json: densidad de tinta, márgenes reales, blanco muerto, alineación
   de bordes verticales (columnas), y un veredicto PASS/FAIL con umbrales.

LÍMITE HONESTO
--------------
El PNG sale del SVG que emite forge.py, no del motor de draw.io. Layout, colores
y textos son los mismos bytes de geometría, pero el tipo de letra y el kerning
los pone MuPDF. Sirve para juzgar composición; no es una captura de draw.io.
MuPDF además ignora `stroke-dasharray` y `marker-end`, razón por la cual
forge.py emite guiones segmentados y puntas como polígonos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

DPI = 110
THRESH = {
    "ink_min": 0.04,        # menos tinta = lienzo vacío / cajas perdidas
    "ink_max": 0.42,        # más tinta = amontonado
    "dead_white_max": 0.34,  # franja vacía más grande admisible (fracción del alto)
    "margin_min": 12,       # px de aire real en los cuatro bordes
}


def render(svg: Path, png: Path, dpi: int = DPI) -> tuple[int, int]:
    import fitz
    doc = fitz.open(svg)
    pix = doc[0].get_pixmap(dpi=dpi)
    png.parent.mkdir(parents=True, exist_ok=True)
    pix.save(png)
    return pix.width, pix.height


def _gray(png: Path) -> np.ndarray:
    from PIL import Image
    im = Image.open(png).convert("L")
    return np.asarray(im, dtype=np.float32) / 255.0


def _pad_to(a: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.ones(shape, dtype=a.dtype)
    out[:a.shape[0], :a.shape[1]] = a[:shape[0], :shape[1]]
    return out


def compare(a_png: Path, b_png: Path, out_dir: Path) -> dict:
    a, b = _gray(a_png), _gray(b_png)
    shape = (max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1]))
    A, B = _pad_to(a, shape), _pad_to(b, shape)
    diff = np.abs(A - B)
    changed = float((diff > 0.08).mean())

    out_dir.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    heat = np.stack([np.ones_like(diff), 1 - diff, 1 - diff], axis=-1)
    Image.fromarray((heat * 255).astype(np.uint8)).save(out_dir / "diff_heatmap.png")

    gap = 24
    strip = Image.new("RGB", (shape[1] * 2 + gap, shape[0]), (240, 240, 240))
    strip.paste(Image.open(a_png).convert("RGB"), (0, 0))
    strip.paste(Image.open(b_png).convert("RGB"), (shape[1] + gap, 0))
    strip.thumbnail((2200, 2200))
    strip.save(out_dir / "side_by_side.png")

    # Dónde cambió, por bandas horizontales: dice si el cambio es local o global.
    bands = 10
    rows = np.array_split(diff > 0.08, bands, axis=0)
    band_pct = [round(float(r.mean()) * 100, 2) for r in rows]
    return {"changed_pct": round(changed * 100, 3), "shape": list(shape),
            "band_pct": band_pct,
            "verdict": "IDENTICAL" if changed < 0.0005 else
                       ("LOCAL" if max(band_pct) > 4 * (sum(band_pct) / bands + 1e-9) else "GLOBAL")}


def score(png: Path, metrics: Path | None) -> dict:
    g = _gray(png)
    h, w = g.shape
    ink_mask = g < 0.94
    ink = float(ink_mask.mean())

    rows = ink_mask.any(axis=1)
    cols = ink_mask.any(axis=0)
    if not rows.any():
        return {"verdict": "FAIL", "reasons": ["lienzo en blanco"], "ink": 0.0}
    top, bottom = int(np.argmax(rows)), int(h - np.argmax(rows[::-1]))
    left, right = int(np.argmax(cols)), int(w - np.argmax(cols[::-1]))

    # Franja horizontal vacía más grande dentro del contenido (blanco muerto).
    inner = rows[top:bottom]
    best = cur = 0
    for v in inner:
        cur = 0 if v else cur + 1
        best = max(best, cur)
    dead = best / max(1, bottom - top)

    reasons: list[str] = []
    if ink < THRESH["ink_min"]:
        reasons.append(f"densidad de tinta {ink:.3f} < {THRESH['ink_min']} (lienzo vacío)")
    if ink > THRESH["ink_max"]:
        reasons.append(f"densidad de tinta {ink:.3f} > {THRESH['ink_max']} (amontonado)")
    if dead > THRESH["dead_white_max"]:
        reasons.append(f"franja vacía {dead:.2f} del alto > {THRESH['dead_white_max']}")
    for name, v in (("izq", left), ("arriba", top), ("der", w - right), ("abajo", h - bottom)):
        if v < THRESH["margin_min"]:
            reasons.append(f"margen {name} = {v}px < {THRESH['margin_min']}")

    out = {"png": str(png), "size": [w, h], "ink": round(ink, 4),
           "content_bbox": [left, top, right, bottom],
           "dead_white_frac": round(dead, 3)}

    if metrics and metrics.exists():
        m = json.loads(metrics.read_text(encoding="utf-8"))
        f = m.get("findings", [])
        errs = [x for x in f if x["sev"] == "ERROR"]
        out["counts"] = m.get("counts", {})
        out["errors"] = len(errs)
        out["warns"] = len(f) - len(errs)
        for x in errs:
            reasons.append(f"{x['code']}: {x['msg']}")
        boxes = [b for b in m.get("boxes", []) if b["role"] in ("table", "node")]
        # Coordenadas fraccionarias: draw.io engancha a una grilla de 10px, así que
        # una caja en x=232.85 se resiste a alinearse cuando el usuario la arrastra.
        # El layout debe emitir enteros. Esto sí es un defecto de editabilidad; la
        # "alineación de columnas" que había antes medía repetición de x, que un
        # layout de dos columnas no puede cumplir por construcción — falso fallo.
        frac = [b["id"] for b in m.get("boxes", [])
                if any(abs(b[k] - round(b[k])) > 0.01 for k in ("x", "y", "w", "h"))]
        out["fractional_boxes"] = len(frac)
        if frac:
            reasons.append(f"{len(frac)} caja(s) con coordenada fraccionaria "
                           f"(p.ej. {frac[0]}): pelean con la grilla de draw.io")
        conts = [c for c in m.get("boxes", []) if c["role"] == "container"]
        groups: dict[str, list[float]] = {}
        for b in boxes:
            owner = next((c["id"] for c in conts
                          if c["x"] - 1 <= b["x"] and b["x"] + b["w"] <= c["x"] + c["w"] + 1
                          and c["y"] - 1 <= b["y"] and b["y"] + b["h"] <= c["y"] + c["h"] + 1),
                         "_root")
            groups.setdefault(owner, []).append(round(b["x"], 0))
        # Informativo: cuántas columnas distintas usa cada contenedor.
        out["columns_per_container"] = {g: len(set(xs)) for g, xs in sorted(groups.items())}

    out["reasons"] = reasons
    out["verdict"] = "PASS" if not reasons else "FAIL"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render")
    r.add_argument("svg", type=Path)
    r.add_argument("--png", type=Path, default=None)
    r.add_argument("--dpi", type=int, default=DPI)

    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    c.add_argument("--out-dir", type=Path, default=Path("judge"))

    s = sub.add_parser("score")
    s.add_argument("target", type=Path, help=".svg o .png")
    s.add_argument("--metrics", type=Path, default=None)
    s.add_argument("--dpi", type=int, default=DPI)

    a = ap.parse_args()

    if a.cmd == "render":
        png = a.png or a.svg.with_suffix(".png")
        w, h = render(a.svg, png, a.dpi)
        print(f"{png} {w}x{h}")
        return 0

    if a.cmd == "compare":
        res = compare(a.a, a.b, a.out_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print(f"{a.out_dir}/side_by_side.png\n{a.out_dir}/diff_heatmap.png", file=sys.stderr)
        return 0

    target = a.target
    if target.suffix.lower() == ".svg":
        png = target.with_suffix(".png")
        render(target, png, a.dpi)
        target = png
    metrics = a.metrics
    if metrics is None:
        guess = target.with_suffix("").with_suffix(".metrics.json")
        cand = target.parent / (target.stem + ".metrics.json")
        metrics = cand if cand.exists() else guess
    res = score(target, metrics)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
