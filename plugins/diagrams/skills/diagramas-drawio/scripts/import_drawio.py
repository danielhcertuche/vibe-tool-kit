#!/usr/bin/env python3
"""Extrae un spec YAML desde un .drawio ER existente (migración de diagramas viejos).

PARA QUÉ
--------
Los diagramas ER hechos a mano guardan el modelo dentro del HTML de la etiqueta
de cada caja: negrita = nombre de tabla, subrayado = PK, cursiva o "(FK)" = FK.
Ese modelo es recuperable. Este script lo lee y escribe el spec que consume
forge.py, así que un diagrama heredado se convierte en editable + validable sin
retipear 40 tablas.

RECONOCE DOS FORMATOS
---------------------
1. Cajas de texto plano  (`verticalAlign=top` + HTML en el value) — el formato de
   los ER v1/v2 de este repo.
2. Tablas nativas de drawio (`childLayout=tableLayout`) — celda de llave + celda
   de columna.

LO QUE NO PUEDE ADIVINAR
------------------------
El destino de una FK cuando la caja sólo dice "(FK)" sin nombrar la tabla. Esas
columnas salen con `ref: "?"` y hay que resolverlas a mano: el spec queda con
TODO marcado y forge.py --strict falla hasta que se completen. Es deliberado —
inventar el destino de una FK es peor que dejar el hueco visible.

Uso:
    import_drawio.py ENTRADA.drawio --out spec.yaml [--group-by-prefix]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TYPE_RX = re.compile(r"^(.*?)\s*:\s*(.+)$")


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_plain_box(value: str) -> tuple[str, list[dict]] | None:
    """Caja de texto plano: <b>Tabla</b> seguido de un <span> por columna."""
    v = html.unescape(value or "")
    segs = [s for s in re.split(r"<br\s*/?>", v) if strip_tags(s)]
    if not segs:
        return None
    m = re.search(r"<b[^>]*>(.*?)</b>", segs[0], re.S)
    name = strip_tags(m.group(1)) if m else strip_tags(segs[0])
    if not name or " " in name.strip() and len(name.split()) > 4:
        return None
    cols: list[dict] = []
    for seg in segs[1:]:
        raw = strip_tags(seg)
        if not raw:
            continue
        pk = bool(re.search(r"<u>", seg))
        fk = bool(re.search(r"<i>", seg)) or "(FK)" in raw
        raw = raw.replace("(FK)", "").replace("(PK)", "").strip()
        mm = TYPE_RX.match(raw)
        cname, ctype = (mm.group(1).strip(), mm.group(2).strip()) if mm else (raw, "")
        key = ",".join([k for k, on in (("PK", pk), ("FK", fk)) if on])
        col: dict = {"name": cname, "type": ctype}
        if key:
            col["key"] = key
        if fk:
            col["ref"] = "?"
        cols.append(col)
    return (name, cols) if cols else None


def parse_native_table(tid: str, cells: dict[str, ET.Element]) -> tuple[str, list[dict]]:
    name = strip_tags(cells[tid].get("value") or tid)
    rows = [c for c in cells.values()
            if c.get("parent") == tid and "shape=tableRow" in (c.get("style") or "")]
    rows.sort(key=lambda c: float((c.find("mxGeometry") or ET.Element("g")).get("y") or 0))
    cols: list[dict] = []
    for r in rows:
        kids = [c for c in cells.values() if c.get("parent") == r.get("id")]
        kids.sort(key=lambda c: float((c.find("mxGeometry") or ET.Element("g")).get("x") or 0))
        vals = [strip_tags(k.get("value") or "") for k in kids]
        if not any(vals):
            continue
        key = vals[0].upper().replace(" ", "") if len(vals) > 1 else ""
        body = vals[1] if len(vals) > 1 else vals[0]
        mm = TYPE_RX.match(body)
        cname, ctype = (mm.group(1).strip(), mm.group(2).strip()) if mm else (body, "")
        ctype = re.sub(r"^\((.*)\)$", r"\1", ctype)
        col: dict = {"name": cname, "type": ctype}
        if key in ("PK", "FK", "PK,FK", "PFK", "U"):
            col["key"] = "PK,FK" if key == "PFK" else key
            if "FK" in col["key"]:
                col["ref"] = "?"
        cols.append(col)
    return name, cols


ARROW_RX = re.compile(r"([A-Za-z_][\w]*)\s*(?:→|->|=>)\s*([A-Za-z_][\w]*)")


def resolve_refs_from_edges(tables: list[tuple[str, list[dict]]],
                            cells: dict[str, ET.Element]) -> int:
    """Rellena los `ref: "?"` usando las aristas del diagrama de origen.

    Una arista ER legada suele traer todo lo necesario: source/target apuntan a
    las cajas y la etiqueta dice "ColOrigen → ColDestino". Con eso el destino de
    la FK se deduce sin inventar nada. Lo que no cubra una arista se queda en
    TODO: es la diferencia entre recuperar y adivinar."""
    # El match va del nombre más largo al más corto: si no, "tbl_ejemplo_VersionPedido"
    # se resuelve como "Pedido" por sufijo y la FK apunta a la tabla equivocada.
    names = sorted((n for n, _ in tables), key=len, reverse=True)
    name_of: dict[str, str] = {}
    for cid, c in cells.items():
        if c.get("vertex") != "1":
            continue
        first = (strip_tags(c.get("value") or "").split(" ") or [""])[0]
        for tname in names:
            if first == tname or cid == tname or cid.endswith("_" + tname):
                name_of[cid] = tname
                break

    cols_of = {n: c for n, c in tables}
    resolved = 0
    for c in cells.values():
        if c.get("edge") != "1":
            continue
        src, tgt = name_of.get(c.get("source") or ""), name_of.get(c.get("target") or "")
        if not src or not tgt or src not in cols_of:
            continue
        label = strip_tags(c.get("value") or "")
        m = ARROW_RX.search(label)
        if m:
            scol, tcol = m.group(1), m.group(2)
            for col in cols_of[src]:
                if col["name"].lower() == scol.lower():
                    col["ref"] = f"{tgt}.{tcol}"
                    col["key"] = "PK,FK" if "PK" in (col.get("key") or "") else "FK"
                    resolved += 1
        else:                      # sin etiqueta: única FK sin resolver hacia esa tabla
            pend = [x for x in cols_of[src] if x.get("ref") == "?"]
            if len(pend) == 1:
                pk = next((y["name"] for y in cols_of.get(tgt, []) if "PK" in (y.get("key") or "")), "")
                pend[0]["ref"] = f"{tgt}.{pk}" if pk else f"{tgt}"
                resolved += 1
    return resolved


def yaml_dump(spec: dict) -> str:
    """Volcado propio: comillas estables y orden fijo. Evita depender del estilo
    de PyYAML, que cambia entre versiones y rompe el determinismo byte a byte."""
    def q(s: str) -> str:
        s = str(s)
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    out = [f"kind: {spec['kind']}", f"title: {q(spec['title'])}"]
    if spec.get("subtitle"):
        out.append(f"subtitle: {q(spec['subtitle'])}")
    out.append(f"max_columns: {spec.get('max_columns', 4)}")
    if spec.get("groups"):
        out.append("groups:")
        for g in spec["groups"]:
            out.append(f"  - id: {q(g['id'])}")
            out.append(f"    title: {q(g['title'])}")
            out.append(f"    theme: {g['theme']}")
    out.append("tables:")
    for t in spec["tables"]:
        out.append(f"  - name: {q(t['name'])}")
        if t.get("group"):
            out.append(f"    group: {q(t['group'])}")
        out.append("    columns:")
        for c in t["columns"]:
            bits = [f"name: {q(c['name'])}"]
            if c.get("type"):
                bits.append(f"type: {q(c['type'])}")
            if c.get("key"):
                bits.append(f"key: {c['key']}")
            if c.get("ref"):
                bits.append(f"ref: {q(c['ref'])}")
            todo = "   # TODO resolver destino de la FK" if c.get("ref") == "?" else ""
            out.append("      - {" + ", ".join(bits) + "}" + todo)
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--group-by-prefix", action="store_true",
                    help="agrupa por el primer token del nombre (heurística, revisar a mano)")
    a = ap.parse_args()

    tree = ET.parse(a.input)
    cells = {c.get("id"): c for c in tree.iter("mxCell") if c.get("id")}
    tables: list[tuple[str, list[dict]]] = []
    seen: set[str] = set()

    for cid, c in cells.items():
        st = c.get("style") or ""
        if "childLayout=tableLayout" in st or st.startswith("shape=table;"):
            name, cols = parse_native_table(cid, cells)
            if cols and name not in seen:
                seen.add(name)
                tables.append((name, cols))

    for cid, c in cells.items():
        st = c.get("style") or ""
        if c.get("vertex") != "1" or "shape=" in st or "childLayout" in st:
            continue
        if "verticalAlign=top" not in st:
            continue
        got = parse_plain_box(c.get("value") or "")
        if got and got[0] not in seen:
            seen.add(got[0])
            tables.append(got)

    if not tables:
        print("no se reconoció ninguna entidad; revisa el formato del .drawio", file=sys.stderr)
        return 1

    resolve_refs_from_edges(tables, cells)

    tables.sort(key=lambda t: t[0].lower())
    spec: dict = {
        "kind": "er",
        "title": a.title or f"ER importado desde {a.input.name}",
        "subtitle": "spec generado por import_drawio.py — revisar los TODO antes de publicar",
        "max_columns": 4,
        "tables": [],
    }
    if a.group_by_prefix:
        groups: dict[str, None] = {}
        for name, _ in tables:
            g = re.split(r"(?=[A-Z])", name)[1] if re.split(r"(?=[A-Z])", name)[1:] else name
            groups[g] = None
        themes = ["blue", "green", "orange", "purple", "teal", "red", "neutral"]
        spec["groups"] = [{"id": g, "title": g, "theme": themes[i % len(themes)]}
                          for i, g in enumerate(sorted(groups))]

    for name, cols in tables:
        t: dict = {"name": name, "columns": cols}
        if a.group_by_prefix:
            parts = re.split(r"(?=[A-Z])", name)
            t["group"] = parts[1] if len(parts) > 1 else name
        spec["tables"].append(t)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(yaml_dump(spec), encoding="utf-8")
    unresolved = sum(1 for _, cols in tables for c in cols if c.get("ref") == "?")
    print(f"{a.out}\n  tablas: {len(tables)}   FK sin destino (TODO): {unresolved}")
    if unresolved:
        print("  resuelve los 'ref: \"?\"' antes de `forge.py build --strict`", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
