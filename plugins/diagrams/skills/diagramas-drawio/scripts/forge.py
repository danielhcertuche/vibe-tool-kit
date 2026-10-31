#!/usr/bin/env python3
"""Forja de diagramas editables: un spec YAML/JSON -> .drawio (canónico) + .svg (previsualización).

POR QUÉ UN SOLO GENERADOR PARA LOS DOS ARTEFACTOS
-------------------------------------------------
La geometría se calcula UNA vez y se emite dos veces. El .drawio es el artefacto
editable que abre el usuario (mover una caja, alinear, cambiar un tipo de dato);
el .svg es el mismo layout rasterizable, y por eso sirve como testigo del juez de
píxeles y como imagen para README/Wiki. Si cada formato calculara su propio
layout, el juez validaría una imagen que no corresponde al archivo entregado.

DETERMINISMO
------------
Mismo spec -> mismos bytes. Sin timestamps, sin ids aleatorios (los ids salen del
slug del elemento), sin dependencias del orden de un dict, sin métricas de fuentes
instaladas (el ancho de texto se estima con una tabla de anchos por clase de
carácter, no con PIL/fontconfig).

COMANDOS
--------
    forge.py build SPEC [--out-dir DIR] [--name BASE] [--strict] [--only drawio|svg]
    forge.py validate SPEC [--strict]
    forge.py inspect FILE.drawio          # audita un .drawio ER hecho a mano

SALIDAS de `build`
------------------
    <base>.drawio        artefacto editable (fuente de verdad para el usuario)
    <base>.svg           misma geometría, rasterizable
    <base>.metrics.json  geometría + hallazgos, entrada del juez (judge.py)
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape as xml_escape

# ---------------------------------------------------------------------------
# 1. Tokens visuales. Paleta con contraste WCAG AA verificado (>= 4.5:1 con
#    texto blanco sobre `header`). Si se toca un hex, hay que recalcular:
#    scripts/judge.py --contrast lo hace.
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, str]] = {
    "blue":    {"header": "#1e6fd9", "fill": "#f5f9ff", "title": "#0b3f8f", "stroke": "#1e6fd9"},
    "green":   {"header": "#158132", "fill": "#f4fdf6", "title": "#0c6b26", "stroke": "#158132"},
    "orange":  {"header": "#aa5c00", "fill": "#fffaf3", "title": "#a85a00", "stroke": "#aa5c00"},
    "purple":  {"header": "#7b3fbf", "fill": "#faf6ff", "title": "#53257f", "stroke": "#7b3fbf"},
    "teal":    {"header": "#0c7e7e", "fill": "#f2fdfd", "title": "#0a5f5f", "stroke": "#0c7e7e"},
    "neutral": {"header": "#6e7279", "fill": "#fbfbfc", "title": "#2b2f36", "stroke": "#6e7279"},
    "red":     {"header": "#b3261e", "fill": "#fff6f5", "title": "#8c1d18", "stroke": "#b3261e"},
}
THEME_ORDER = ["blue", "green", "orange", "purple", "teal", "red", "neutral"]

# Paleta semántica del estilo "linaje": la cabecera va en pastel con texto
# oscuro, no en color sólido con texto blanco. El color dice QUÉ ES la tabla
# (se conserva, es variante, está duplicada, está fuera del catálogo), no a qué
# dominio pertenece. Tomada de los diagramas de linaje del equipo de origen para que un
# mismo lector reconozca los dos sin tener que reaprender el código de color.
ESTADOS: dict[str, dict[str, str]] = {
    "canon":  {"header": "#d5e8d4", "fill": "#ffffff", "title": "#3f6b3a", "stroke": "#82b366", "ink": "#16321a"},
    "subset": {"header": "#ffe6cc", "fill": "#ffffff", "title": "#8a5a00", "stroke": "#d79b00", "ink": "#3a2600"},
    "dup":    {"header": "#f8cecc", "fill": "#ffffff", "title": "#8c1d18", "stroke": "#b85450", "ink": "#3d0f0d"},
    "origen": {"header": "#eeeeee", "fill": "#ffffff", "title": "#44474d", "stroke": "#7a7a7a", "ink": "#1f2227"},
    "destino":{"header": "#dae8fc", "fill": "#ffffff", "title": "#2a4f85", "stroke": "#6c8ebf", "ink": "#122policy"},
}
ESTADOS["destino"]["ink"] = "#102a4d"
THEMES.update(ESTADOS)

# Tipos de línea: (color, patrón de guiones en px o None para continuo).
LINES: dict[str, tuple[str, tuple[int, int] | None]] = {
    "fk":          ("#4a5568", None),        # relación con FK física declarada
    "soft":        ("#6b7688", (5, 4)),      # relación lógica sin FK en la BD
    "request":     ("#1f2937", None),
    "secure":      ("#0c7a2c", None),
    "integration": ("#1e6fd9", (6, 4)),
    "telemetry":   ("#7b3fbf", (3, 4)),
    "pipeline":    ("#aa5c00", (8, 4)),
}

_LABEL_RECTS: list[tuple[float, float, float, float]] = []   # etiquetas ya colocadas

INK = "#111827"        # texto principal
MUTED = "#4b5563"      # texto secundario (7.56:1 sobre blanco)
HAIR = "#dde3ea"       # líneas de separación de filas
PAPER = "#ffffff"
TABLE_BODY = "#ffffff"   # cuerpo de la tabla ER: el color va SÓLO en la cabecera
ZEBRA = "#f7f8fb"        # fila alterna: separa la vista sin meter otra línea
CHIP_FILL = "#eef0f4"    # chip de la etiqueta de relación
CHIP_INK = "#3f4753"
FONT = "Segoe UI,Helvetica Neue,Arial,sans-serif"

# Geometría. Todo múltiplo de 2 para caer limpio en la grilla de 10 de drawio.
G = {
    "margin": 40,
    "title_h": 64,
    "footer_h": 44,
    # --- ER ---
    "tbl_w": 336,
    "tbl_type_w": 104,        # columna del tipo, a la IZQUIERDA
    "tbl_key_w": 46,          # badge PK/FK/UK, a la DERECHA
    "tbl_head_h": 38,
    "tbl_row_h": 24,
    "tbl_gap_x": 156,         # hueco horizontal: por aquí viajan los codos Y el chip
                              # con el nombre de la columna FK. Con 72 px el chip
                              # no cabía y terminaba encima de la tabla vecina.
    "tbl_gap_y": 40,
    # --- contenedores (grupos ER y secciones de componentes) ---
    "grp_head_h": 34,
    "grp_pad_x": 18,
    "grp_pad_top": 12,
    "grp_pad_bottom": 18,
    "grp_gap_x": 34,
    "grp_gap_y": 56,          # corredor entre bandas
    # --- nodos de componentes ---
    "node_w": 208,
    "node_min_h": 92,
    "node_gap_x": 18,
    "node_gap_y": 16,
    "icon_h": 26,
    # --- ruteo ---
    "lane_h": 20,
    "lanes": 6,
    # --- linaje (carriles) ---
    "lin_w": 340,             # ancho de tabla en el estilo linaje
    "lin_info_h": 15,         # alto de cada renglón del bloque de metadatos
    "lin_chip_h": 26,         # chip de cabecera del carril
    "lin_gap_x": 150,         # corredor entre carriles: aquí viaja la etiqueta
    "lin_gap_y": 30,
}

FS = {"title": 22, "subtitle": 13, "grp": 13, "grp_sub": 10,
      "tbl": 13, "tbl_sub": 9, "row": 11, "node": 12, "node_sub": 10,
      "edge": 10, "note": 11, "legend": 11}

# ---------------------------------------------------------------------------
# 2. Métrica de texto determinista (sin fuentes del sistema).
#    Anchos en "em" por clase de carácter, calibrados contra Segoe UI / Arial.
# ---------------------------------------------------------------------------

_NARROW = set("iljItfr.,:;'`|!()[]{}-/\\ ")
_WIDE = set("mMWQ@%&")
_UPPER = set("ABCDEFGHJKLNOPRSTUVXYZ")
_DIGIT = set("0123456789")


def char_em(ch: str) -> float:
    if ch in _NARROW:
        return 0.30
    if ch in _WIDE:
        return 0.92
    if ch in _UPPER:
        return 0.66
    if ch in _DIGIT:
        return 0.55
    return 0.52


def text_w(s: str, size: int, bold: bool = False) -> float:
    """Ancho estimado en px. Sesgado ~4% al alza: preferimos avisar de un
    desborde inexistente antes que entregar un diagrama con texto cortado."""
    base = sum(char_em(c) for c in s) * size
    return base * (1.06 if bold else 1.0) * 1.04


def wrap(text: str, max_px: float, size: int, bold: bool = False) -> list[str]:
    """Corta en palabras; si una palabra sola no cabe, la parte por caracteres."""
    if not text:
        return []
    out: list[str] = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            probe = f"{line} {word}".strip()
            if text_w(probe, size, bold) <= max_px or not line:
                line = probe
                if text_w(line, size, bold) > max_px and " " not in line:
                    while text_w(line, size, bold) > max_px and len(line) > 1:
                        out.append(line[:-1])
                        line = line[-1]
            else:
                out.append(line)
                line = word
        out.append(line)
    return [l for l in out if l != ""] or [""]


def ellipsize(text: str, max_px: float, size: int, bold: bool = False) -> str:
    if text_w(text, size, bold) <= max_px:
        return text
    cut = text
    while cut and text_w(cut + "…", size, bold) > max_px:
        cut = cut[:-1]
    return (cut + "…") if cut else ""


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s or "x"


# ---------------------------------------------------------------------------
# 3. Representación intermedia. Los dos emisores leen esto y nada más.
# ---------------------------------------------------------------------------

# Glifos de nodo. Trazo, no relleno: se leen igual a 100% y a 25% de zoom, y no
# dependen de ninguna librería de stencils que pueda no estar instalada.
# Cada entrada dibuja dentro de una caja de 20x20 centrada en (0,0).
ICONS: dict[str, str] = {
    "web":      "M-9-7h18v14h-18z M-9-3h18 M-6-5.2h1.2",
    "api":      "M-4-6 -9 0 -4 6 M4-6 9 0 4 6",
    "runtime":  "M-9-6h18v12h-18z M-6-2 -3 0 -6 2 M-1 2h5",
    "db":       "M-7-6c0-1.6 3.1-2.6 7-2.6s7 1 7 2.6v12c0 1.6-3.1 2.6-7 2.6s-7-1-7-2.6z M-7-6c0 1.6 3.1 2.6 7 2.6s7-1 7-2.6",
    "mongo":    "M-7-6c0-1.6 3.1-2.6 7-2.6s7 1 7 2.6v12c0 1.6-3.1 2.6-7 2.6s-7-1-7-2.6z M-7-6c0 1.6 3.1 2.6 7 2.6s7-1 7-2.6 M-7 0c0 1.6 3.1 2.6 7 2.6s7-1 7-2.6",
    "identity": "M0-8a4 4 0 1 0 0 8 4 4 0 1 0 0-8 M-7 9c0-4 3.1-6 7-6s7 2 7 6",
    "users":    "M-3-7a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 1 0 0-6.4 M-9 8c0-3.4 2.7-5 6-5s6 1.6 6 5 M5-6a2.6 2.6 0 1 0 0 5.2 M4 3c3 0 5 1.6 5 5",
    "vault":    "M-6-1h12v9h-12z M-4-1v-3.4a4 4 0 0 1 8 0v3.4 M0 2.6v2.6",
    "ai":       "M0-9v4 M0 5v4 M-9 0h4 M5 0h4 M-6.4-6.4 -3.6-3.6 M6.4 6.4 3.6 3.6 M6.4-6.4 3.6-3.6 M-6.4 6.4 -3.6 3.6 M0-2.4a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 1 0 0-4.8",
    "graph":    "M6-6a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 1 0 0-4.8 M-6-2.4a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 1 0 0-4.8 M6 1.2a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 1 0 0-4.8 M-4-1.6 4-4.4 M-4 1.6 4 4.4",
    "files":    "M-6-8h8l4 4v12h-12z M2-8v4h4",
    "doc":      "M-6-8h8l4 4v12h-12z M2-8v4h4 M-3 2h6 M-3 5h6",
    "monitor":  "M-9-6h18v12h-18z M-6 2 -2-2 1 1 6-4",
    "network":  "M0-8a3 3 0 1 0 0 6 3 3 0 1 0 0-6 M-7 4a3 3 0 1 0 0 6 3 3 0 1 0 0-6 M7 4a3 3 0 1 0 0 6 3 3 0 1 0 0-6 M-1.6-1.6 -5 3 M1.6-1.6 5 3",
    "pipeline": "M-9-4h6 M3-4h6 M-3-7a3 3 0 1 0 0 6 3 3 0 1 0 0-6 M-9 5h12 M3 2a3 3 0 1 0 0 6 3 3 0 1 0 0-6",
    "repo":     "M-6-8h12v16h-12z M-6-2h12 M-3-5.4h4",
    "wiki":     "M-8-7h7v14h-7z M1-7h7v14h-7z M-1-7v14",
    "queue":    "M-9-4h5v8h-5z M-2-4h5v8h-5z M5-4h4v8h-4z",
    "storage":  "M-8-6h16v5h-16z M-8 1h16v5h-16z M-5-3.6h.1 M-5 3.4h.1",
    "external": "M-6-6h8v3h-5v9h9v-5h3v8h-15z M2-8h7v7 M9-8 1 0",
}
ICON_FALLBACK = "M-7-7h14v14h-14z"

# Alias: nombres que aparecen en configs reales y apuntan al mismo glifo. Sin
# esto un `kind` no previsto cae al cuadrado genérico y el diagrama pierde la
# lectura por icono sin avisar de nada.
ICONS.update({
    "lock": ICONS["vault"], "secret": ICONS["vault"], "key": ICONS["vault"],
    "shield": "M0-8 7-5.4v5.6C7 4 4 7 0 8.4-4 7-7 4-7-.2v-5.6z M-3 0 -0.6 2.4 3.4-1.6",
    "sharepoint": ICONS["files"], "excel": ICONS["files"], "onedrive": ICONS["files"],
    "spa": ICONS["web"], "browser": ICONS["web"], "frontend": ICONS["web"],
    "backend": ICONS["api"], "service": ICONS["api"], "fastapi": ICONS["api"],
    "sql": ICONS["db"], "table": ICONS["db"], "lakehouse": ICONS["db"],
    "warehouse": ICONS["db"], "delta": ICONS["db"], "catalog": ICONS["storage"],
    "volume": ICONS["storage"], "blob": ICONS["storage"], "job": ICONS["pipeline"],
    "etl": ICONS["pipeline"], "ci": ICONS["pipeline"], "notebook": ICONS["doc"],
    "model": ICONS["ai"], "llm": ICONS["ai"], "embeddings": ICONS["ai"],
    "user": ICONS["users"], "app": ICONS["runtime"], "container": ICONS["runtime"],
})


@dataclass
class Row:
    key: str = ""          # "PK" | "FK" | "PK,FK" | "U" | ""
    name: str = ""
    type: str = ""
    nullable: bool = True
    ref: str | None = None
    more: bool = False     # fila "… +N columnas"
    info: bool = False     # bloque de metadatos bajo la cabecera (estilo linaje)


@dataclass
class Box:
    id: str
    x: float
    y: float
    w: float
    h: float
    role: str                       # container | table | node | note | legend | title
    theme: str = "neutral"
    title: str = ""
    subtitle: str = ""
    rows: list[Row] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)   # etiqueta ya envuelta (node/note)
    sublines: list[str] = field(default_factory=list)  # subetiqueta ya envuelta
    parent: str = "1"
    pending: bool = False
    kind: str = ""                  # icono para nodos de componentes
    estado: str = ""                # estado semántico (estilo linaje)

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Edge:
    id: str
    src: str
    dst: str
    style: str = "fk"
    label: str = ""
    src_row: int | None = None      # índice de fila (ER): ancla en la columna
    dst_row: int | None = None
    card: str = "N:1"
    points: list[tuple[float, float]] = field(default_factory=list)  # ruta absoluta (SVG)


@dataclass
class Doc:
    kind: str
    title: str
    subtitle: str
    width: float
    height: float
    boxes: list[Box]
    edges: list[Edge]
    legend: list[dict[str, str]]
    footer: str = ""

    def by_id(self) -> dict[str, Box]:
        return {b.id: b for b in self.boxes}


# ---------------------------------------------------------------------------
# 4. Carga y normalización del spec.
# ---------------------------------------------------------------------------

def load_spec(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)
    if not isinstance(spec, dict):
        raise SystemExit(f"{path}: el spec debe ser un mapeo en la raíz")
    # Autodetección: un config de infraestructura (secciones + nodos) no trae
    # `kind`. Adivinarlo por la forma evita pedir un campo ceremonial y permite
    # consumir tal cual los infra-diagram.config.json que ya existen.
    kind = spec.get("kind")
    if not kind:
        kind = "componentes" if (spec.get("sections") or spec.get("secciones")
                                 or spec.get("nodes") or spec.get("nodos")) else "er"
    if kind in ("linaje", "lineage"):
        spec["kind"] = "linaje"
        return spec
    if kind not in ("er", "componentes", "components"):
        raise SystemExit(f"kind no soportado: {kind!r} (usa 'er', 'componentes' o 'linaje')")
    spec["kind"] = "componentes" if kind in ("componentes", "components") else "er"
    return spec


def theme_for(idx: int, explicit: str | None) -> str:
    if explicit and explicit in THEMES:
        return explicit
    return THEME_ORDER[idx % len(THEME_ORDER)]


# ---------------------------------------------------------------------------
# 5. Layout ER.
#    Bandas por grupo de dominio -> dentro de cada banda, tablas en grilla.
#    Orden dentro del grupo: primero los hubs (más referencias entrantes),
#    después alfabético. Determinista y además pone lo importante a la izquierda.
# ---------------------------------------------------------------------------

def _er_rows(tbl: dict[str, Any]) -> list[Row]:
    cols = tbl.get("columns") or tbl.get("columnas") or []
    focus = str(tbl.get("focus", "")).lower()
    limit = int(tbl.get("columns_limit", tbl.get("limite_columnas", 0)) or 0)

    rows: list[Row] = []
    info = tbl.get("info") or tbl.get("meta") or []
    if isinstance(info, str):
        info = [info]
    head_info = [Row(name="\n".join(str(x) for x in info), info=True)] if info else []
    for c in cols:
        if isinstance(c, str):                      # forma corta "Id:bigint:PK"
            parts = [p.strip() for p in c.split(":")]
            c = {"name": parts[0],
                 "type": parts[1] if len(parts) > 1 else "",
                 "key": parts[2] if len(parts) > 2 else ""}
        key = str(c.get("key", c.get("llave", "")) or "").upper().replace(" ", "")
        ref = c.get("ref") or c.get("referencia")
        if ref and "FK" not in key:
            key = ("PK,FK" if "PK" in key else "FK")
        rows.append(Row(key=key,
                        name=str(c.get("name", c.get("nombre", ""))),
                        type=str(c.get("type", c.get("tipo", "")) or ""),
                        nullable=bool(c.get("nullable", True)),
                        ref=str(ref) if ref else None))

    keyed = [r for r in rows if r.key]
    plain = [r for r in rows if not r.key]

    if focus == "keys" or focus == "llaves":
        shown, hidden = keyed, plain
    elif limit and len(rows) > limit:
        room = max(0, limit - len(keyed))
        shown, hidden = keyed + plain[:room], plain[room:]
    else:
        return head_info + rows                      # sin recorte: fidelidad total

    if hidden:
        shown = shown + [Row(name=f"… +{len(hidden)} columnas", more=True)]
    return head_info + shown


def _row_h(r: Row) -> float:
    """Alto de una fila. El bloque de metadatos del estilo linaje ocupa un
    renglón por línea; las columnas, el alto normal."""
    return G["lin_info_h"] * max(1, len(r.name.split("\n"))) if r.info else G["tbl_row_h"]


def _rows_h(rows: list[Row]) -> float:
    return sum(_row_h(r) for r in rows)


def _tbl_h(rows: list[Row]) -> float:
    return G["tbl_head_h"] + _rows_h(rows)



def layout_er(spec: dict[str, Any]) -> Doc:
    tables = spec.get("tables") or spec.get("tablas") or []
    if not tables:
        raise SystemExit("el spec ER no declara 'tables'")

    norm: list[dict[str, Any]] = []
    for t in tables:
        rows = _er_rows(t)
        norm.append({
            "name": str(t.get("name", t.get("nombre", ""))),
            "schema": str(t.get("question", t.get("pregunta",
                          t.get("schema", t.get("esquema", "")))) or ""),
            "group": str(t.get("group", t.get("grupo", "")) or "_"),
            "note": str(t.get("note", t.get("nota", "")) or ""),
            "theme": t.get("theme", t.get("tema")),
            "estado": str(t.get("estado") or t.get("state") or ""),
            "pending": bool(t.get("pending")) or
                       str(t.get("status", t.get("estado", "")) or "").lower() == "pending",
            "rows": rows,
            "h": _tbl_h(rows),
        })

    by_name = {t["name"]: t for t in norm}

    # Relaciones derivadas de las FK (`ref`) + las explícitas.
    rels: list[dict[str, Any]] = []
    for t in norm:
        for i, r in enumerate(t["rows"]):
            if not r.ref:
                continue
            tgt_tbl, _, tgt_col = str(r.ref).rpartition(".")
            rels.append({"from": t["name"], "from_row": i, "to": tgt_tbl.strip(),
                         "to_col": tgt_col.strip(), "card": "N:1", "style": "fk",
                         "label": ""})
    for rel in (spec.get("relations") or spec.get("relaciones") or []):
        f, _, fc = str(rel.get("from", rel.get("desde", ""))).rpartition(".")
        t, _, tc = str(rel.get("to", rel.get("hasta", ""))).rpartition(".")
        rels.append({"from": f.strip(), "from_col": fc.strip(), "to": t.strip(),
                     "to_col": tc.strip(), "card": str(rel.get("card", rel.get("cardinalidad", "N:1"))),
                     "style": str(rel.get("style", rel.get("estilo", "soft"))),
                     "label": str(rel.get("label", rel.get("etiqueta", "")) or "")})

    incoming: dict[str, int] = {t["name"]: 0 for t in norm}
    for rel in rels:
        if rel["to"] in incoming:
            incoming[rel["to"]] += 1

    # Grupos: orden declarado; los no declarados van al final, alfabéticos.
    declared = spec.get("groups") or spec.get("grupos") or []
    gmeta: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for i, g in enumerate(declared):
        gid = str(g.get("id", g.get("title", f"g{i}")))
        gmeta[gid] = {"title": str(g.get("title", g.get("titulo", gid))),
                      "subtitle": str(g.get("subtitle", g.get("subtitulo", "")) or ""),
                      "theme": theme_for(i, g.get("theme", g.get("tema"))),
                      "columns": int(g.get("columns", g.get("columnas", 0)) or 0)}
        order.append(gid)
    for t in sorted({t["group"] for t in norm}):
        if t not in gmeta:
            gmeta[t] = {"title": "" if t == "_" else t, "subtitle": "",
                        "theme": theme_for(len(order), None), "columns": 0}
            order.append(t)

    max_cols = int(spec.get("max_columns", spec.get("max_columnas", 4)) or 4)
    boxes: list[Box] = []
    corridors: list[float] = []      # x de los pasillos verticales libres (ruteo)
    # Un subtítulo largo ocupa varias líneas: la primera banda tiene que empezar
    # por debajo de todas ellas.
    _sub = str(spec.get("subtitle", spec.get("subtitulo", "")) or "")
    _sub_h = max(0, (len(wrap(_sub, 1660 - 2 * G["margin"], FS["subtitle"])) - 1) * 16) if _sub else 0
    y = G["margin"] + G["title_h"] + _sub_h
    max_x = 0.0
    row_anchor: dict[str, list[float]] = {}   # nombre tabla -> y absoluta de cada fila

    for gid in order:
        members = [t for t in norm if t["group"] == gid]
        if not members:
            continue
        members.sort(key=lambda t: (-incoming[t["name"]], t["name"]))
        meta = gmeta[gid]
        ncols = meta["columns"] or min(max_cols, len(members))
        show_container = bool(meta["title"])

        gx = G["margin"]
        # El subtítulo del grupo se dibuja bajo la barra, DENTRO del cuerpo: si no
        # se le reserva alto, la primera tabla se le monta encima.
        sub_h = 16 if (show_container and meta["subtitle"]) else 0
        inner_x = gx + (G["grp_pad_x"] if show_container else 0)
        inner_y = y + ((G["grp_head_h"] + sub_h + G["grp_pad_top"]) if show_container else 0)

        # Empaquetado tipo mampostería: cada tabla entra en la columna que va más
        # corta. Con una grilla de filas de altura uniforme, una sola tabla de 90
        # columnas estira su banda entera y deja tres cuartos del ancho en blanco;
        # así las tablas cortas se apilan al lado de la larga.
        cols_x = [inner_x + j * (G["tbl_w"] + G["tbl_gap_x"]) for j in range(ncols)]
        heights = [inner_y] * ncols
        for t in members:
            j = min(range(ncols), key=lambda k: (heights[k], k))
            cy = heights[j]
            b = Box(id="tbl_" + slug(t["name"]), x=cols_x[j], y=cy, w=G["tbl_w"], h=t["h"],
                    role="table", estado=t["estado"],
                    theme=(t["estado"] if t["estado"] in ESTADOS
                           else theme_for(order.index(gid), t["theme"] or meta["theme"])),
                    title=t["name"], subtitle=t["schema"], rows=t["rows"],
                    pending=t["pending"])
            boxes.append(b)
            anchors, ay = [], cy + G["tbl_head_h"]
            for r in t["rows"]:
                anchors.append(ay + _row_h(r) / 2)
                ay += _row_h(r)
            row_anchor[t["name"]] = anchors
            heights[j] = cy + t["h"] + G["tbl_gap_y"]
            max_x = max(max_x, b.x2)
        corridors.extend(cols_x[j] + G["tbl_w"] + G["tbl_gap_x"] / 2 for j in range(ncols - 1))
        corridors.append(max(G["margin"] / 2, inner_x - G["tbl_gap_x"] / 2))
        corridors.append(cols_x[-1] + G["tbl_w"] + G["tbl_gap_x"] / 2)

        content_bottom = max(heights) - G["tbl_gap_y"]
        if show_container:
            gw = (G["grp_pad_x"] * 2 + ncols * G["tbl_w"] + (ncols - 1) * G["tbl_gap_x"])
            gh = content_bottom - y + G["grp_pad_bottom"]
            cont = Box(id="grp_" + slug(gid), x=gx, y=y, w=gw, h=gh, role="container",
                       theme=meta["theme"], title=meta["title"], subtitle=meta["subtitle"])
            boxes.insert(0, cont)          # z-order: contenedores primero
            max_x = max(max_x, cont.x2)
            y = cont.y2 + G["grp_gap_y"]
        else:
            y = content_bottom + G["grp_gap_y"]

    # Notas en una columna reservada a la derecha de TODO el contenido, apiladas
    # para que no se pisen. Colgarlas junto a su tabla las ponía encima de la
    # tabla vecina y fuera del lienzo cuando la tabla ya estaba en el borde.
    bid = {b.id: b for b in boxes}
    noted = [t for t in norm if t["note"]]
    if noted:
        col_x = max_x + 24
        note_w = 210
        last_bottom = 0.0
        for t in sorted(noted, key=lambda t: bid["tbl_" + slug(t["name"])].y):
            anchor = bid["tbl_" + slug(t["name"])]
            lines = wrap(t["note"], note_w - 18, FS["note"])
            h = 12 + len(lines) * 14
            ny = max(anchor.y, last_bottom + 10)
            boxes.append(Box(id="note_" + slug(t["name"]), x=col_x, y=ny, w=note_w, h=h,
                             role="note", theme="neutral", lines=lines))
            last_bottom = ny + h
        max_x = col_x + note_w
        # La columna de notas puede pasar del último grupo: si su fondo no entra
        # en el alto del lienzo, las últimas notas salen recortadas. Se apilan
        # para no solaparse, así que crecer más que el contenido es lo normal.
        notes_bottom = last_bottom

    y = max(y, (notes_bottom + G["grp_gap_y"]) if noted else y)
    edges = _er_edges(rels, by_name, bid, row_anchor, sorted(set(corridors)))

    legend = spec.get("legend") or spec.get("leyenda") or [
        {"label": "Relación con FK declarada en la base", "type": "fk"},
        {"label": "Relación lógica sin FK física (join por convención)", "type": "soft"},
    ]
    lgd_w = float(round(60 + max(text_w(str(it.get("label", "")), FS["legend"]) for it in legend)))
    lgd_h = G["grp_head_h"] + 18 + 16 + len(legend) * 20 + 14
    boxes.append(Box(id="legend", x=G["margin"], y=y, w=lgd_w, h=lgd_h,
                     role="legend", theme="neutral", title="Leyenda"))
    max_x = max(max_x, G["margin"] + lgd_w)
    y += lgd_h

    return Doc(kind="er",
               title=str(spec.get("title", spec.get("titulo", "Modelo entidad-relación"))),
               subtitle=str(spec.get("subtitle", spec.get("subtitulo", "")) or ""),
               width=max_x + G["margin"], height=y + G["footer_h"] + G["margin"],
               boxes=boxes, edges=edges, legend=legend,
               footer=_footer(spec))


def _er_edges(rels, by_name, bid, row_anchor, corridors) -> list[Edge]:
    """Rutea cada relación como codo ER: sale por el costado de la fila FK,
    entra por el costado de la fila PK del destino. Los tramos verticales se
    reparten en carriles dentro del hueco entre columnas de tablas."""
    edges: list[Edge] = []
    seen: dict[str, int] = {}
    for rel in sorted(rels, key=lambda r: (r["from"], r.get("from_row", 0), r["to"])):
        src_t, dst_t = rel["from"], rel["to"]
        if src_t not in by_name or dst_t not in by_name:
            continue                     # lo reporta el validador, no se dibuja
        sb, db = bid["tbl_" + slug(src_t)], bid["tbl_" + slug(dst_t)]

        srow = rel.get("from_row")
        if srow is None:
            srow = _find_row(by_name[src_t]["rows"], rel.get("from_col"))
        drow = _find_row(by_name[dst_t]["rows"], rel.get("to_col"), prefer_pk=True)

        sy = row_anchor[src_t][srow] if srow is not None and srow < len(row_anchor[src_t]) else sb.cy
        dy = row_anchor[dst_t][drow] if drow is not None and drow < len(row_anchor[dst_t]) else db.cy

        base = f"rel_{slug(src_t)}__{slug(dst_t)}"
        seen[base] = seen.get(base, 0) + 1
        eid = base if seen[base] == 1 else f"{base}_{seen[base]}"

        obstacles = [b for b in bid.values() if b.role == "table" and b.id not in (sb.id, db.id)]
        lane = (seen[base] - 1) * 7
        pts = _elbow(sb, sy, db, dy, corridors, obstacles, lane)

        etiqueta = rel["label"]
        if not etiqueta and srow is not None and srow < len(by_name[src_t]["rows"]):
            # Sin etiqueta explícita, el chip lleva el nombre de la columna FK:
            # es lo que el lector busca cuando sigue una relación, y evita
            # repetir el destino dentro de la fila.
            etiqueta = by_name[src_t]["rows"][srow].name
        edges.append(Edge(id=eid, src=sb.id, dst=db.id, style=rel["style"],
                          label=etiqueta, src_row=srow, dst_row=drow,
                          card=rel["card"], points=pts))
    return edges


def _elbow(sb: Box, sy: float, db: Box, dy: float, corridors: list[float],
           obstacles: list[Box], lane: float) -> list[tuple[float, float]]:
    """Codo de tres tramos por un pasillo vertical libre.

    Los pasillos son los huecos entre columnas de tablas, que el layout ya dejó
    reservados. Se prueban en orden de cercanía al punto medio y se queda el
    primero que no atraviese ninguna tabla ajena; si ninguno sirve, gana el que
    menos cruces produce. Sin esto, el codo por el punto medio geométrico entra
    de lleno en la tabla que esté en medio."""
    def sides(sx: float, dx: float) -> tuple[float, float]:
        return sx, dx

    best: tuple[int, float, list[tuple[float, float]]] | None = None
    for s_right in (db.cx >= sb.cx, db.cx < sb.cx):
        sx = sb.x2 if s_right else sb.x
        dx = db.x if s_right else db.x2
        cands = sorted(corridors, key=lambda c: abs(c - (sx + dx) / 2))
        cands = cands[:6] + [(sx + dx) / 2]
        for c in cands:
            cx = c + lane
            pts = [(sx, sy), (cx, sy), (cx, dy), (dx, dy)]
            hits = sum(1 for i in range(len(pts) - 1) for o in obstacles
                       if _seg_hits(pts[i], pts[i + 1], o))
            if hits == 0:
                return pts
            if best is None or hits < best[0] or (hits == best[0] and abs(cx - (sx + dx) / 2) < best[1]):
                best = (hits, abs(cx - (sx + dx) / 2), pts)
    return best[2] if best else [(sb.x2, sy), (db.x, dy)]


def _find_row(rows: list[Row], col: str | None, prefer_pk: bool = False) -> int | None:
    if col:
        for i, r in enumerate(rows):
            if r.name.lower() == col.lower():
                return i
    if prefer_pk:
        for i, r in enumerate(rows):
            if "PK" in r.key:
                return i
    return None


# ---------------------------------------------------------------------------
# 6. Layout de componentes. Filas de secciones; nodos en grilla dentro de cada
#    sección; conectores por corredores reservados entre filas.
# ---------------------------------------------------------------------------

def layout_components(spec: dict[str, Any]) -> Doc:
    sections = {str(s.get("id")): s for s in (spec.get("sections") or spec.get("secciones") or [])}
    nodes_by_sec: dict[str, list[dict[str, Any]]] = {}
    for n in (spec.get("nodes") or spec.get("nodos") or []):
        nodes_by_sec.setdefault(str(n.get("section", n.get("seccion"))), []).append(n)

    rows_spec = spec.get("rows") or spec.get("filas") or [{"sections": list(sections)}]
    canvas_w = float((spec.get("style") or {}).get("width", 1740))
    avail = canvas_w - 2 * G["margin"]

    boxes: list[Box] = []
    y = G["margin"] + G["title_h"]
    theme_i = 0
    bands: list[dict[str, Any]] = []
    max_x = 0.0

    for r_idx, row in enumerate(rows_spec):
        ids = [str(i) for i in (row.get("sections") or row.get("secciones") or [])]
        ids = [i for i in ids if i in sections]
        if not ids:
            continue
        spans = [float(sections[i].get("span", 1) or 1) for i in ids]
        total = sum(spans)
        gaps = G["grp_gap_x"] * (len(ids) - 1)
        widths = [float(round(max(G["node_w"] + 2 * G["grp_pad_x"],
                                  (avail - gaps) * s / total))) for s in spans]

        x = G["margin"]
        band_boxes: list[Box] = []
        band_h = 0.0
        for i, sid in enumerate(ids):
            s = sections[sid]
            sw = widths[i]
            theme = theme_for(theme_i, s.get("theme", s.get("tema")))
            theme_i += 1
            members = nodes_by_sec.get(sid, [])
            inner_w = sw - 2 * G["grp_pad_x"]
            ncols = int(s.get("columns", s.get("columnas", 0)) or 0) or max(
                1, int((inner_w + G["node_gap_x"]) // (G["node_w"] + G["node_gap_x"])))
            ncols = min(ncols, max(1, len(members)))
            nw = float(round((inner_w - (ncols - 1) * G["node_gap_x"]) / ncols)) if ncols else inner_w

            prepared = []
            for n in members:
                lbl = wrap(str(n.get("label", n.get("etiqueta", ""))), nw - 20, FS["node"], True)
                sub = wrap(str(n.get("sublabel", n.get("subetiqueta", "")) or ""), nw - 20, FS["node_sub"])
                h = (14 + G["icon_h"] + 14 + len(lbl) * 16
                     + (len(sub) * 13 + 2 if sub else 0) + 14
                     + (12 if str(n.get("status", n.get("estado", ""))).lower() == "pending" else 0))
                prepared.append((n, lbl, sub, max(G["node_min_h"], h)))

            head_lines = wrap(str(s.get("title", s.get("titulo", sid))), sw - 24, FS["grp"], True)
            sub_lines = wrap(str(s.get("subtitle", s.get("subtitulo", "")) or ""), sw - 24, FS["grp_sub"])
            head_h = max(G["grp_head_h"], 12 + len(head_lines) * 17)
            if sid in ("legend", "leyenda"):
                n_rows = max(len(spec.get("legend") or spec.get("leyenda") or []),
                             len(spec.get("icon_legend") or spec.get("leyenda_iconos") or []))
                prepared = []          # la leyenda no lleva nodos
                grid = []
            sub_h = (len(sub_lines) * 13 + 6) if sub_lines else 0

            ny = y + head_h + sub_h + G["grp_pad_top"]
            grid = [prepared[k:k + ncols] for k in range(0, len(prepared), ncols)]
            cy = ny
            child: list[Box] = []
            for line in grid:
                lh = max(p[3] for p in line)
                for j, (n, lbl, sub, _h) in enumerate(line):
                    nb = Box(id="nd_" + slug(n.get("id", n.get("label", "n"))),
                             x=round(x + G["grp_pad_x"] + j * (nw + G["node_gap_x"])), y=cy,
                             w=nw, h=lh, role="node", theme=theme,
                             title=" ".join(lbl), subtitle=" ".join(sub),
                             lines=lbl, sublines=sub,
                             parent="sec_" + slug(sid),
                             pending=str(n.get("status", n.get("estado", "real"))).lower() == "pending",
                             kind=str(n.get("kind", n.get("tipo", "")) or ""))
                    child.append(nb)
                cy += lh + G["node_gap_y"]

            sh = (cy - (G["node_gap_y"] if grid else 0)) - y + G["grp_pad_bottom"]
            if sid in ("legend", "leyenda"):
                sh = head_h + sub_h + 24 + n_rows * 20 + G["grp_pad_bottom"]
            sec = Box(id="sec_" + slug(sid),
                      x=x, y=y, w=sw, h=sh,
                      role="legend" if sid in ("legend", "leyenda") else "container",
                      theme=theme, title=str(s.get("title", s.get("titulo", sid))),
                      subtitle=str(s.get("subtitle", s.get("subtitulo", "")) or ""))
            band_boxes.append(sec)
            band_boxes.extend(child)
            band_h = max(band_h, sh)
            x += sw + G["grp_gap_x"]
            max_x = max(max_x, sec.x2)

        boxes.extend(band_boxes)
        bands.append({"y": y, "h": band_h, "ids": ["sec_" + slug(i) for i in ids],
                      "gutter_top": y + band_h, "index": r_idx})
        y += band_h + G["grp_gap_y"]

    legend = spec.get("legend") or spec.get("leyenda") or []
    icon_legend = spec.get("icon_legend") or spec.get("leyenda_iconos") or []
    declared_inline = any(b.role == "legend" for b in boxes)
    if (legend or icon_legend) and not declared_inline:
        rows_n = max(len(legend), len(icon_legend))
        lw = 520 if icon_legend else 340
        lh = 34 + 18 + rows_n * 20 + 14
        boxes.append(Box(id="legend", x=max(G["margin"], max_x - lw), y=y, w=lw, h=lh,
                         role="legend", theme="neutral", title="Leyenda"))
        y += lh

    doc = Doc(kind="componentes",
              title=str(spec.get("title", spec.get("titulo", "Arquitectura de componentes"))),
              subtitle=str(spec.get("subtitle", spec.get("subtitulo", "")) or ""),
              width=max(canvas_w, max_x + G["margin"]),
              height=y + G["footer_h"] + G["margin"],
              boxes=boxes, edges=[], legend=legend, footer=_footer(spec))
    doc.edges = _cmp_edges(spec, doc, bands)
    doc.legend = legend
    setattr(doc, "icon_legend", icon_legend)
    return doc


def _cmp_edges(spec: dict[str, Any], doc: Doc, bands: list[dict[str, Any]]) -> list[Edge]:
    bid = doc.by_id()
    conns = spec.get("connections") or spec.get("conexiones") or []
    obstacles = [b for b in doc.boxes if b.role in ("container", "node", "legend")]
    edges: list[Edge] = []
    lane_use: dict[int, int] = {}

    for k, c in enumerate(sorted(conns, key=lambda c: (str(c.get("from")), str(c.get("to"))))):
        s = bid.get("nd_" + slug(c.get("from", c.get("desde", ""))))
        t = bid.get("nd_" + slug(c.get("to", c.get("hasta", ""))))
        if not s or not t:
            continue
        style = str(c.get("type", c.get("tipo", "request")) or "request")
        label = str(c.get("label", c.get("etiqueta", "")) or "")
        eid = f"cn_{slug(c.get('from'))}__{slug(c.get('to'))}"

        bs, bt = _band_of(s, bands), _band_of(t, bands)
        direct: list[tuple[float, float]] | None = None
        if bs == bt and abs(s.cy - t.cy) < max(s.h, t.h):
            y = (max(s.y, t.y) + min(s.y2, t.y2)) / 2
            cand = [(s.x2, y), (t.x, y)] if t.cx >= s.cx else [(s.x, y), (t.x2, y)]
            # El tramo recto sólo vale si no atraviesa una tarjeta intermedia.
            # Si la atraviesa, baja al corredor: así se evita a la vez el cruce y
            # que la etiqueta acabe escrita sobre el nombre de esa tarjeta.
            blockers = [o for o in obstacles
                        if o.role == "node" and o.id not in (s.id, t.id)]
            if not any(_seg_hits(cand[0], cand[1], o) for o in blockers):
                direct = cand
        if direct is not None:
            pts = direct
        else:
            # El corredor es el hueco bajo la banda MÁS ALTA de las dos, sin
            # importar la dirección de la flecha. Usar el hueco "arriba de la
            # banda origen" mandaba los tramos de la primera fila por encima del
            # título, fuera del lienzo.
            up = min(bs, bt)
            lane = lane_use.get(up, 0)
            lane_use[up] = lane + 1
            gy = bands[up]["gutter_top"] + G["lane_h"] * (0.6 + lane % G["lanes"])
            sx, tx = _free_x(s, obstacles), _free_x(t, obstacles)
            sy = s.y2 if bs == up else s.y
            ty = t.y if bt != up else t.y2
            pts = [(sx, sy), (sx, gy), (tx, gy), (tx, ty)]

        edges.append(Edge(id=eid, src=s.id, dst=t.id, style=style, label=label, points=pts))
    return edges


def _band_of(b: Box, bands: list[dict[str, Any]]) -> int:
    for i, band in enumerate(bands):
        if band["y"] - 1 <= b.cy <= band["y"] + band["h"] + 1:
            return i
    return 0


def _free_x(b: Box, obstacles: list[Box]) -> float:
    return round(b.cx / 2) * 2


def _footer(spec: dict[str, Any]) -> str:
    src = spec.get("source") or spec.get("fuente") or {}
    bits = [str(src[k]) for k in ("repo", "branch", "commit", "as_of", "fecha") if src.get(k)]
    return " · ".join(bits)



# ---------------------------------------------------------------------------
# 6 bis. Layout LINAJE.
#    Carriles verticales por capa (origen -> silver -> gold -> ...), tablas
#    apiladas dentro de cada carril, y flechas de flujo cuya etiqueta se ancla
#    PEGADA A LA TABLA DESTINO y encima de la línea, para que se lea en
#    horizontal sin cruzar el ruteo vertical.
#
#    Es el estilo de los diagramas de linaje del equipo de origen. Lo que lo distingue
#    del ER no es decorativo:
#      - el color de la cabecera dice el ESTADO de la tabla, no su dominio;
#      - bajo la cabecera va un bloque de metadatos (volumen, ritmo, evidencia);
#      - la columna de llave dice "K" = llave MEDIDA, no llave declarada: en el
#        lago no hay llaves, así que afirmar una sin medirla sería inventarla.
# ---------------------------------------------------------------------------

def _lin_rows(tbl: dict[str, Any]) -> list[Row]:
    rows: list[Row] = []
    info = tbl.get("info") or tbl.get("meta") or []
    if isinstance(info, str):
        info = [info]
    if info:
        rows.append(Row(name="\n".join(str(x) for x in info), info=True))
    cols = tbl.get("columns") or tbl.get("columnas") or []
    limit = tbl.get("columns_limit") or tbl.get("limite_columnas")
    shown, hidden = [], 0
    for c in cols:
        if isinstance(c, str):
            parts = c.split(":")
            c = {"name": parts[0], "type": parts[1] if len(parts) > 1 else "",
                 "key": parts[2] if len(parts) > 2 else ""}
        shown.append(Row(key=str(c.get("key") or c.get("llave") or ""),
                         name=str(c.get("name") or c.get("nombre") or ""),
                         type=str(c.get("type") or c.get("tipo") or "")))
    if limit and len(shown) > int(limit):
        keyed = [r for r in shown if r.key]
        rest = [r for r in shown if not r.key]
        keep = keyed + rest[: max(0, int(limit) - len(keyed))]
        hidden = len(shown) - len(keep)
        shown = keep
    rows.extend(shown)
    if hidden:
        rows.append(Row(name=f"… +{hidden} columnas", more=True))
    return rows


def layout_linaje(spec: dict[str, Any]) -> Doc:
    lanes = spec.get("lanes") or spec.get("carriles") or []
    if not lanes:
        raise SystemExit("kind 'linaje': falta `lanes` (los carriles por capa)")
    lanes = [{"id": str(l.get("id") or l.get("title")), "title": str(l.get("title") or l.get("titulo") or "")}
             for l in lanes]
    lane_ix = {l["id"]: i for i, l in enumerate(lanes)}

    raw = spec.get("tables") or spec.get("tablas") or []
    if not raw:
        raise SystemExit("kind 'linaje': falta `tables`")
    W, GX, GY = G["lin_w"], G["lin_gap_x"], G["lin_gap_y"]
    x0 = G["margin"]
    # El subtítulo del estilo linaje suele ser una frase larga: hay que medir
    # cuántos renglones ocupa ANTES de colocar los chips, o se le montan encima.
    lienzo = x0 + len(lanes) * (W + GX) - GX + G["margin"]
    sub = str(spec.get("subtitle") or spec.get("subtitulo") or "")
    n_sub = len(wrap(sub, lienzo - 2 * G["margin"], FS["subtitle"])) if sub else 0
    chip_y = max(G["title_h"] + 6, G["margin"] + 46 + n_sub * 16 + 4)
    top = chip_y + G["lin_chip_h"] + 26

    boxes: list[Box] = []
    for i, l in enumerate(lanes):
        boxes.append(Box(id="lane_" + slug(l["id"]), x=x0 + i * (W + GX),
                         y=chip_y, w=W, h=G["lin_chip_h"],
                         role="lane", theme="neutral", title=l["title"]))

    norm = []
    for t in raw:
        name = str(t.get("name") or t.get("nombre"))
        lane = str(t.get("lane") or t.get("carril") or lanes[0]["id"])
        if lane not in lane_ix:
            raise SystemExit(f"{name}: carril desconocido {lane!r}")
        estado = str(t.get("estado") or t.get("state") or "canon")
        if estado not in ESTADOS:
            raise SystemExit(f"{name}: estado {estado!r} (usa {', '.join(sorted(ESTADOS))})")
        rows = _lin_rows(t)
        norm.append({"name": name, "lane": lane, "estado": estado, "rows": rows,
                     "sub": str(t.get("schema") or t.get("esquema") or ""),
                     "note": t.get("note") or t.get("nota") or "",
                     "h": G["tbl_head_h"] + _rows_h(rows)})

    heights = [top] * len(lanes)
    by_name: dict[str, Box] = {}
    max_x = 0.0
    for t in norm:
        j = lane_ix[t["lane"]]
        b = Box(id="tbl_" + slug(t["name"]), x=x0 + j * (W + GX), y=heights[j], w=W, h=t["h"],
                role="table", theme=t["estado"], estado=t["estado"],
                title=t["name"], subtitle=t["sub"], rows=t["rows"])
        boxes.append(b)
        by_name[t["name"]] = b
        heights[j] = b.y2 + GY
        max_x = max(max_x, b.x2)

    # Notas en una columna a la derecha, apiladas, como en el ER.
    bottom = max(heights) - GY
    noted = [t for t in norm if t["note"]]
    if noted:
        col_x, note_w, last = max_x + 26, 230, 0.0
        for t in sorted(noted, key=lambda t: by_name[t["name"]].y):
            a = by_name[t["name"]]
            lines = wrap(str(t["note"]), note_w - 18, FS["note"])
            h = 12 + len(lines) * 14
            ny = max(a.y, last + 10)
            boxes.append(Box(id="note_" + slug(t["name"]), x=col_x, y=ny, w=note_w, h=h,
                             role="note", theme="neutral", lines=lines))
            last = ny + h
        max_x = col_x + note_w
        bottom = max(bottom, last)

    edges: list[Edge] = []
    for i, fl in enumerate(spec.get("flows") or spec.get("flujos") or []):
        a = str(fl.get("from") or fl.get("desde"))
        z = str(fl.get("to") or fl.get("hacia"))
        if a not in by_name or z not in by_name:
            raise SystemExit(f"flujo {i}: tabla desconocida ({a} → {z})")
        sb, db = by_name[a], by_name[z]
        # Corredor: a mitad del hueco entre los dos carriles, o pegado por la
        # izquierda cuando el destino está en el mismo carril o más atrás.
        if db.x > sb.x:
            cx = sb.x2 + GX / 2
            pts = [(sb.x2, sb.y + G["tbl_head_h"] / 2), (cx, sb.y + G["tbl_head_h"] / 2),
                   (cx, db.y + G["tbl_head_h"] / 2), (db.x, db.y + G["tbl_head_h"] / 2)]
        else:
            cx = min(sb.x, db.x) - GX / 2
            pts = [(sb.x, sb.y + G["tbl_head_h"] / 2), (cx, sb.y + G["tbl_head_h"] / 2),
                   (cx, db.y + G["tbl_head_h"] / 2), (db.x, db.y + G["tbl_head_h"] / 2)]
        edges.append(Edge(id=f"flow_{i}", src=sb.id, dst=db.id,
                          style=str(fl.get("style") or fl.get("estilo") or "fk"),
                          label=str(fl.get("label") or fl.get("etiqueta") or ""),
                          card=str(fl.get("card") or fl.get("cardinalidad") or ""),
                          points=pts))

    legend = spec.get("legend") or spec.get("leyenda") or [
        {"color": "canon", "label": "Fuente que se conserva"},
        {"color": "dup", "label": "Duplicada o redundante"},
        {"color": "origen", "label": "Fuera de Unity Catalog"},
    ]
    y = bottom + G["grp_gap_y"]
    lw = float(round(80 + max(text_w(str(it.get("label", "")), FS["legend"]) for it in legend)))
    lh = G["grp_head_h"] + 18 + 16 + len(legend) * 20 + 14
    boxes.append(Box(id="legend", x=G["margin"], y=y, w=lw, h=lh, role="legend",
                     theme="neutral", title="Leyenda"))
    width = max(max_x, G["margin"] + lw) + G["margin"]
    height = y + lh + G["footer_h"] + 12
    doc = Doc(kind="linaje", title=str(spec.get("title") or spec.get("titulo") or ""),
              subtitle=str(spec.get("subtitle") or spec.get("subtitulo") or ""),
              width=width, height=height, boxes=boxes, edges=edges, legend=legend,
              footer=_footer(spec))
    return doc


# ---------------------------------------------------------------------------
# 7. Emisor .drawio. Estilos verificados contra archivos reales de app.diagrams.net.
# ---------------------------------------------------------------------------

TABLE_STYLE = ("shape=table;startSize={head};container=1;collapsible=0;childLayout=tableLayout;"
               "fixedRows=1;rowLines=1;columnLines=1;html=1;whiteSpace=wrap;align=center;"
               "resizeLast=1;fontSize={fs};fontStyle=1;fontColor=#ffffff;verticalAlign=middle;"
               "fillColor={head_fill};strokeColor={stroke};swimlaneFillColor={body_fill};"
               "swimlaneLine=1;arcSize=6;rounded=1;")
ROW_STYLE = ("shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;"
             "fillColor=none;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];"
             "portConstraint=eastwest;top=0;left=0;right=0;bottom=0;strokeColor={hair};html=1;")
CELL_STYLE = ("shape=partialRectangle;connectable=0;fillColor=none;top=0;left=0;bottom=0;right=0;"
              "overflow=hidden;whiteSpace=nowrap;html=1;fontSize={fs};align={align};"
              "spacingLeft={sl};fontColor={color};{extra}")


def _e(s: str) -> str:
    return xml_escape(str(s), {'"': "&quot;"})


def emit_drawio(doc: Doc) -> str:
    out: list[str] = []
    a = out.append
    page_w = int(math.ceil(doc.width / 10.0) * 10)
    page_h = int(math.ceil(doc.height / 10.0) * 10)
    a('<mxfile host="forge.diagramas-drawio" type="device">')
    a(f'  <diagram id="{_e(slug(doc.title))}" name="{_e(doc.title[:60])}">')
    a(f'    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" '
      f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{page_w}" '
      f'pageHeight="{page_h}" math="0" shadow="0">')
    a("      <root>")
    a('        <mxCell id="0" />')
    a('        <mxCell id="1" parent="0" />')

    # Título y subtítulo.
    a(_cell("title", _rich_title(doc),
            "text;html=1;align=left;verticalAlign=top;fontSize=%d;fontStyle=1;strokeColor=none;"
            "fillColor=none;fontColor=%s;" % (FS["title"], INK),
            G["margin"], G["margin"], max(600, doc.width - 2 * G["margin"]), G["title_h"] - 10))

    bid = doc.by_id()
    for b in doc.boxes:
        px, py = (0.0, 0.0)
        if b.parent != "1" and b.parent in bid:
            px, py = bid[b.parent].x, bid[b.parent].y
        if b.role == "lane":
            out.append(_cell(b.id, f"<b>{_e(b.title)}</b>",
                             "rounded=0;html=1;whiteSpace=wrap;fillColor=#f5f5f5;"
                             f"strokeColor=#bdbdbd;fontSize={FS['grp']};fontColor={INK};"
                             "align=center;verticalAlign=middle;",
                             b.x, b.y, b.w, b.h))
        elif b.role == "container":
            a(_container_drawio(b))
        elif b.role == "table":
            out.extend(_table_drawio(b))
        elif b.role == "node":
            a(_node_drawio(b, px, py))
        elif b.role == "note":
            a(_cell(b.id, "\n".join(b.lines),
                    "shape=note;whiteSpace=wrap;html=1;size=12;verticalAlign=top;align=left;"
                    "spacing=6;fontSize=%d;fillColor=#fffbe6;strokeColor=#d6b656;fontColor=%s;"
                    % (FS["note"], MUTED), b.x, b.y, b.w, b.h))
        elif b.role == "legend":
            out.extend(_legend_drawio(doc, b))

    for e in doc.edges:
        a(_edge_drawio(doc, e))

    if doc.footer:
        a(_cell("footer", doc.footer,
                "text;html=1;align=left;verticalAlign=middle;fontSize=10;fontColor=%s;"
                "strokeColor=none;fillColor=none;" % MUTED,
                G["margin"], doc.height - G["margin"] - 24, doc.width - 2 * G["margin"], 20))

    a("      </root>")
    a("    </mxGraphModel>")
    a("  </diagram>")
    a("</mxfile>")
    return "\n".join(out) + "\n"


def _rich_title(doc: Doc) -> str:
    """HTML crudo. El escape lo aplica quien escribe el atributo `value`."""
    if not doc.subtitle:
        return doc.title
    return (f'<b>{doc.title}</b><br><span style="font-size:{FS["subtitle"]}px;'
            f'font-weight:400;color:{MUTED}">{doc.subtitle}</span>')


def _cell(cid: str, value: str, style: str, x: float, y: float, w: float, h: float,
          parent: str = "1") -> str:
    return (f'        <mxCell id="{_e(cid)}" value="{_e(value)}" style="{style}" '
            f'parent="{_e(parent)}" vertex="1">\n'
            f'          <mxGeometry x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" as="geometry" />\n'
            f'        </mxCell>')


def _n(v: float) -> str:
    r = round(float(v), 2)
    return str(int(r)) if r == int(r) else str(r)


def _container_drawio(b: Box) -> str:
    th = THEMES[b.theme]
    val = b.title
    if b.subtitle:
        val = (f'<b>{b.title}</b><div style="font-size:{FS["grp_sub"]}px;font-weight:400">'
               f'{b.subtitle}</div>')
    style = ("swimlane;html=1;rounded=1;arcSize=6;startSize=%d;horizontal=1;"
             "fontSize=%d;fontStyle=1;fontColor=#ffffff;align=center;verticalAlign=middle;"
             "fillColor=%s;strokeColor=%s;swimlaneFillColor=%s;swimlaneLine=1;"
             "collapsible=0;connectable=0;"
             % (G["grp_head_h"], FS["grp"], th["header"], th["stroke"], th["fill"]))
    return (f'        <mxCell id="{_e(b.id)}" value="{_e(val)}" style="{style}" parent="1" vertex="1">\n'
            f'          <mxGeometry x="{_n(b.x)}" y="{_n(b.y)}" width="{_n(b.w)}" height="{_n(b.h)}" as="geometry" />\n'
            f'        </mxCell>')


def _table_drawio(b: Box) -> list[str]:
    """Tabla ER nativa de drawio: cabecera + una fila por columna + celda de
    llave. Cada fila es un puerto de conexión (portConstraint=eastwest), así que
    las relaciones se anclan a la columna, no a la caja."""
    th = THEMES[b.theme]
    out: list[str] = []
    head = b.title
    if b.subtitle:
        head = (f'{b.title}<div style="font-size:{FS["tbl_sub"]}px;font-weight:400;'
                f'opacity:0.85">{b.subtitle}</div>')
    style = TABLE_STYLE.format(head=G["tbl_head_h"], fs=FS["tbl"],
                               head_fill=th["header"], body_fill=TABLE_BODY,
                               stroke=th["stroke"])
    if th.get("ink"):                      # estilo linaje: cabecera pastel, texto oscuro
        style = style.replace("fontColor=#ffffff;", f'fontColor={th["ink"]};')
    if b.pending:
        style += "dashed=1;dashPattern=6 4;"
        head = f'{head} · PROPUESTA' if not b.subtitle else head
    out.append(f'        <mxCell id="{_e(b.id)}" value="{_e(head)}" style="{style}" parent="1" vertex="1">\n'
               f'          <mxGeometry x="{_n(b.x)}" y="{_n(b.y)}" width="{_n(b.w)}" '
               f'height="{_n(b.h)}" as="geometry" />\n        </mxCell>')

    kw, bw = G["tbl_key_w"], b.w - G["tbl_key_w"]
    ry = G["tbl_head_h"]
    for i, r in enumerate(b.rows):
        rid = f"{b.id}_r{i}"
        rh = _row_h(r)
        rstyle = ROW_STYLE.format(hair=HAIR)
        if r.info:
            rstyle = rstyle.replace("fillColor=none;", "fillColor=#fafafa;")
        out.append(f'        <mxCell id="{_e(rid)}" value="" style="{rstyle}" '
                   f'parent="{_e(b.id)}" vertex="1">\n'
                   f'          <mxGeometry y="{_n(ry)}" width="{_n(b.w)}" height="{_n(rh)}" as="geometry" />\n'
                   f'        </mxCell>')
        if r.info:
            val = "<br>".join(_e(x) for x in r.name.split("\n"))
            out.append(_tbl_cell(f"{rid}_c", val, b.w, rh, 0, rid, FS["tbl_sub"], "left", 8,
                                 MUTED, "fontStyle=2;whiteSpace=wrap;"))
            ry += rh
            continue
        # Tres columnas, como en la referencia: tipo · nombre · badge de llave.
        # El destino de la FK NO va aquí: va como chip sobre la línea, que es
        # donde el lector lo busca cuando sigue una relación.
        tw = G["tbl_type_w"]
        nw = b.w - tw - kw
        zebra = "fillColor=%s;" % ZEBRA if i % 2 else ""
        if r.more:
            out.append(_tbl_cell(f"{rid}_c", r.name, b.w, rh, 0, rid, FS["row"], "left", 8,
                                 MUTED, "fontStyle=2;" + zebra))
            ry += rh
            continue
        out.append(_tbl_cell(f"{rid}_t", r.type, tw, rh, 0, rid, FS["row"] - 1, "left", 8,
                             MUTED, zebra))
        out.append(_tbl_cell(f"{rid}_c", _row_name(r), nw, rh, tw, rid, FS["row"], "left", 8,
                             INK, zebra))
        out.append(_tbl_cell(f"{rid}_k", r.key, kw, rh, tw + nw, rid, FS["row"] - 2, "center", 0,
                             th["title"] if r.key else MUTED, "fontStyle=1;" + zebra))
        ry += rh
    return out


def row_tail(r: Row, avail: float) -> str:
    """Cola de la fila (`: tipo → destino`) degradada al ancho disponible.

    Se degrada en pasos, no se corta a lo bruto: primero cae la columna del
    destino, despues la tabla destino, y solo al final se recorta el tipo. El
    .drawio y el .svg llaman a esta misma funcion, asi que el texto entregado y
    el texto juzgado son el mismo."""
    if r.more:
        return ""
    room = avail - text_w(r.name, FS["row"]) - 4
    tipo = f" : {r.type}" if r.type else ""
    if not r.ref:
        return tipo if text_w(tipo, FS["row"]) <= room else ellipsize(tipo, room, FS["row"])
    tbl, _, _col = r.ref.rpartition(".")
    for cand in (f"{tipo}  → {r.ref}", f"{tipo}  → {tbl}", tipo):
        if text_w(cand, FS["row"]) <= room:
            return cand
    return ellipsize(tipo, room, FS["row"])


def _row_name(r: Row) -> str:
    """Sólo el nombre. PK subrayado, FK en cursiva: la decoración dice el papel
    sin gastar una columna más."""
    name = _e(r.name)
    if "PK" in r.key:
        name = f"<u>{name}</u>"
    if "FK" in r.key and "PK" not in r.key:
        name = f"<i>{name}</i>"
    return name


def _row_label(r: Row, th: dict[str, str]) -> tuple[str, str]:
    if r.more:
        return r.name, "fontStyle=2;"
    name = r.name
    if "PK" in r.key:
        name = f"<u>{name}</u>"
    if "FK" in r.key and "PK" not in r.key:
        name = f"<i>{name}</i>"
    tail = row_tail(r, G["tbl_w"] - G["tbl_key_w"] - 12)
    if r.ref and "→" in tail:
        head, _, dest = tail.partition("→")
        tail = (f'<span style="color:{MUTED}">{head}</span>'
                f'<span style="color:{th["title"]}">→ {dest.strip()}</span>')
    else:
        tail = f'<span style="color:{MUTED}">{tail}</span>'
    return f"{name}{tail}", ""


def _tbl_cell(cid: str, value: str, w: float, h: float, x: float, parent: str,
              fs: int, align: str, sl: int, color: str, extra: str) -> str:
    style = CELL_STYLE.format(fs=fs, align=align, sl=sl, color=color, extra=extra)
    return (f'        <mxCell id="{_e(cid)}" value="{_e(value)}" style="{style}" '
            f'parent="{_e(parent)}" vertex="1">\n'
            f'          <mxGeometry x="{_n(x)}" width="{_n(w)}" height="{_n(h)}" as="geometry">\n'
            f'            <mxRectangle width="{_n(w)}" height="{_n(h)}" as="alternateBounds" />\n'
            f'          </mxGeometry>\n        </mxCell>')


ICON_HINT = {
    "web": "mxgraph.azure.general.browser", "api": "mxgraph.azure.general.code",
    "db": "mxgraph.azure.general.database", "queue": "mxgraph.azure.general.queue",
    "identity": "mxgraph.azure.general.key", "ai": "mxgraph.azure.general.cognitive_services",
    "storage": "mxgraph.azure.general.storage_blob", "ci": "mxgraph.azure.general.gear",
}


def _node_drawio(b: Box, px: float, py: float) -> str:
    th = THEMES[b.theme]
    val = f'<b>{b.title}</b>'
    if b.subtitle:
        val += (f'<div style="font-size:{FS["node_sub"]}px;font-weight:400;color:{MUTED}">'
                f'{b.subtitle}</div>')
    if b.pending:
        val += ('<div style="font-size:8px;font-weight:700;color:#a85a00">'
                'PENDIENTE DE PROVISIÓN</div>')
    dash = "dashed=1;dashPattern=6 4;" if b.pending else ""
    style = ("rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor=#ffffff;strokeColor=%s;"
             "fontSize=%d;fontColor=%s;align=center;verticalAlign=middle;spacing=6;%s"
             % (th["stroke"], FS["node"], INK, dash))
    return (f'        <mxCell id="{_e(b.id)}" value="{_e(val)}" style="{style}" '
            f'parent="{_e(b.parent)}" vertex="1">\n'
            f'          <mxGeometry x="{_n(b.x - px)}" y="{_n(b.y - py)}" width="{_n(b.w)}" '
            f'height="{_n(b.h)}" as="geometry" />\n        </mxCell>')


# Notación ER completa en los dos extremos, como la referencia: pata de gallo
# en el lado "muchos" y barra (o círculo + barra, si es opcional) en el lado
# "uno". Se abandonó la punta sólida de dirección: con el chip de la columna FK
# sobre la línea el sentido ya se lee, y mezclar flecha con notación ER obliga
# al lector a sostener dos códigos a la vez.
ER_ARROW = {
    "N:1":  ("ERoneToMany", "ERmandOne"),
    "1:N":  ("ERmandOne",   "ERoneToMany"),
    "1:1":  ("ERmandOne",   "ERmandOne"),
    "N:N":  ("ERoneToMany", "ERoneToMany"),
    "0..1": ("ERoneToMany", "ERzeroToOne"),
}


def _edge_drawio(doc: Doc, e: Edge) -> str:
    color, dash = LINES.get(e.style, LINES["request"])
    dstyle = f"dashed=1;dashPattern={dash[0]} {dash[1]};" if dash else "dashed=0;"
    bid = doc.by_id()
    src, dst = e.src, e.dst
    waypoints = ""

    if doc.kind in ("er", "linaje"):
        if e.src_row is not None:
            src = f"{e.src}_r{e.src_row}"
        if e.dst_row is not None:
            dst = f"{e.dst}_r{e.dst_row}"
        # Sin `card` el trazo es un flujo de datos, no una relación: flecha
        # simple. En el estilo linaje la pata de gallina solo se dibuja cuando
        # hay un perfil de duplicidad MEDIDO; afirmarla sin medirla es inventarla.
        sa, ea = ER_ARROW.get(e.card, ("none", "block")) if e.card else ("none", "block")

        # Ruta EXPLÍCITA, la misma que el .svg. `entityRelationEdgeStyle` autorutea
        # y con 31 aristas convergiendo en una fila produce un abanico de diagonales
        # que cruza tablas enteras. Con waypoints, draw.io dibuja los mismos
        # pasillos ortogonales que ya calculó el layout.
        # Contrapartida: si se arrastra una tabla, los waypoints quedan viejos.
        # Se limpian con clic derecho -> "Clear Waypoints" y draw.io rerutea.
        sb, db = bid[e.src], bid[e.dst]
        ex = 1 if (e.points and abs(e.points[0][0] - sb.x2) < 1) else 0
        en = 0 if (e.points and abs(e.points[-1][0] - db.x) < 1) else 1
        anchors = (f"exitX={ex};exitY=0.5;exitDx=0;exitDy=0;"
                   f"entryX={en};entryY=0.5;entryDx=0;entryDy=0;")
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=6;html=1;"
                 f"orthogonalLoop=1;jettySize=auto;{anchors}"
                 f"startArrow={sa};startFill=0;endArrow={ea};endFill=1;"
                 f"strokeColor={color};strokeWidth=1.4;{dstyle}"
                 f"fontSize={FS['edge']};fontColor={CHIP_INK};labelBackgroundColor={CHIP_FILL};")
        label = e.label or ""
        mid = e.points[1:-1] if len(e.points) > 2 else []
        if mid:
            pts = "".join(f'\n            <mxPoint x="{_n(x)}" y="{_n(y)}" />' for x, y in mid)
            waypoints = f'\n            <Array as="points">{pts}\n            </Array>'
    else:
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;orthogonalLoop=1;jettySize=auto;"
                 f"endArrow=blockThin;endFill=1;strokeColor={color};strokeWidth=1.6;{dstyle}"
                 f"fontSize={FS['edge']};fontColor={color};labelBackgroundColor=#ffffff;")
        label = e.label

    parent = "1"
    if doc.kind != "er":
        ps, pd = bid[e.src].parent, bid[e.dst].parent
        parent = ps if ps == pd else "1"
    geo = (f'          <mxGeometry relative="1" as="geometry">{waypoints}\n'
           f'          </mxGeometry>' if waypoints
           else '          <mxGeometry relative="1" as="geometry" />')
    return (f'        <mxCell id="{_e(e.id)}" value="{_e(label)}" style="{style}" '
            f'parent="{parent}" source="{_e(src)}" target="{_e(dst)}" edge="1">\n'
            f'{geo}\n        </mxCell>')


def _legend_head(doc: Doc) -> str:
    """Encabezado de la leyenda según lo que contenga de verdad. Decir «tipos de
    flujo» encima de unos chips de color es mentirle al lector sobre qué está
    mirando."""
    chips = any("color" in it for it in doc.legend)
    lines = any("color" not in it and "icon" not in it for it in doc.legend)
    if chips and lines:
        return "Color y trazo"
    if chips:
        return "Estado de la tabla" if doc.kind == "linaje" else "Capa"
    return "Tipos de flujo"


def _legend_drawio(doc: Doc, b: Box) -> list[str]:
    th = THEMES["neutral"]
    out = [_container_drawio(Box(id=b.id, x=b.x, y=b.y, w=b.w, h=b.h, role="container",
                                 theme="neutral", title="Leyenda"))]
    icon_legend = getattr(doc, "icon_legend", []) or []
    cols = 2 if icon_legend else 1
    cw = (b.w - 2 * G["grp_pad_x"] - (12 if cols == 2 else 0)) / cols
    for ci, (head, items) in enumerate([(_legend_head(doc), doc.legend),
                                        ("Iconografía", icon_legend)][:cols]):
        rows_html = "".join(
            f'<div style="margin:2px 0">{_swatch(it)}&nbsp;{it.get("label", "")}</div>'
            for it in items)
        val = (f'<div style="text-align:left"><b style="font-size:10px;color:{MUTED}">'
               f'{head.upper()}</b>{rows_html}</div>')
        out.append(_cell(f"{b.id}_c{ci}", val,
                         "text;html=1;align=left;verticalAlign=top;fontSize=%d;strokeColor=none;"
                         "fillColor=none;fontColor=%s;" % (FS["legend"], INK),
                         G["grp_pad_x"] + ci * (cw + 12), G["grp_head_h"] + 6,
                         cw, b.h - G["grp_head_h"] - 12, parent=b.id))
    return out


def _swatch(it: dict[str, str]) -> str:
    """Muestra de la leyenda en HTML. La columna de iconografía no tiene línea:
    se marca con un recuadro punteado (pendiente) o un cuadro del color del
    dominio, porque un <span> con border-top no puede dibujar un icono."""
    if "color" in it:
        th = THEMES.get(str(it["color"]), THEMES["neutral"])
        return ('<span style="display:inline-block;width:22px;height:11px;'
                f'background:{th["header"]};border:1px solid {th["stroke"]};'
                'vertical-align:middle"></span>')
    if "icon" in it:
        if str(it["icon"]) in ("pending", "pendiente"):
            return ('<span style="display:inline-block;width:22px;height:10px;'
                    'border:1.4px dashed #aa5c00;vertical-align:middle"></span>')
        return ('<span style="display:inline-block;width:22px;height:10px;'
                f'border:1.4px solid {MUTED};vertical-align:middle"></span>')
    color, dash = LINES.get(it.get("type", "request"), LINES["request"])
    style = "dotted" if dash and dash[0] <= 3 else ("dashed" if dash else "solid")
    return (f'<span style="display:inline-block;width:26px;border-top:2px {style} {color};'
            f'vertical-align:middle"></span>')


# ---------------------------------------------------------------------------
# 8. Emisor SVG. Sin dasharray y sin marker: los guiones se segmentan y las
#    puntas se dibujan como polígonos, porque MuPDF (y Word, y Confluence)
#    ignoran ambos. Verificado 2026-08-19 con PyMuPDF.
# ---------------------------------------------------------------------------

def emit_svg(doc: Doc) -> str:
    _LABEL_RECTS.clear()
    p: list[str] = []
    a = p.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(doc.width)}" '
      f'height="{_n(doc.height)}" viewBox="0 0 {_n(doc.width)} {_n(doc.height)}" '
      f'font-family="{FONT}">')
    a(f'<rect width="{_n(doc.width)}" height="{_n(doc.height)}" fill="{PAPER}"/>')
    a(_txt(G["margin"], G["margin"] + 24, doc.title, FS["title"], INK, bold=True))
    y_sub = G["margin"] + 46
    for ln in wrap(doc.subtitle, doc.width - 2 * G["margin"], FS["subtitle"]):
        a(_txt(G["margin"], y_sub, ln, FS["subtitle"], MUTED))
        y_sub += 16

    for b in doc.boxes:
        if b.role == "container":
            a(_svg_container(b))
        elif b.role == "lane":               # chip de carril (estilo linaje)
            a(_rr(b.x, b.y, b.w, b.h, 2, "#f5f5f5", "#bdbdbd", 1.2))
            a(_txt(b.cx, b.cy + 4, b.title, FS["grp"], INK, bold=True, anchor="middle"))
    for e in doc.edges:                      # trazos bajo las cajas de contenido
        a(_svg_edge(doc, e))
    for b in doc.boxes:
        if b.role == "table":
            a(_svg_table(b))
        elif b.role == "node":
            a(_svg_node(b))
        elif b.role == "note":
            a(_svg_note(b))
        elif b.role == "legend":
            a(_svg_legend(doc, b))
    for e in doc.edges:                      # etiquetas encima de todo
        a(_svg_edge_label(doc, e))
    if doc.footer:
        a(_txt(G["margin"], doc.height - G["margin"], doc.footer, 10, MUTED))
    a("</svg>")
    return "\n".join(p) + "\n"


def _txt(x: float, y: float, s: str, size: int, color: str, bold: bool = False,
         anchor: str = "start", italic: bool = False, deco: str = "") -> str:
    attrs = (f'x="{_n(x)}" y="{_n(y)}" font-size="{size}" fill="{color}" '
             f'text-anchor="{anchor}"')
    if bold:
        attrs += ' font-weight="700"'
    if italic:
        attrs += ' font-style="italic"'
    if deco:
        attrs += f' text-decoration="{deco}"'
    return f"<text {attrs}>{xml_escape(str(s))}</text>"


def _rr(x: float, y: float, w: float, h: float, r: float, fill: str,
        stroke: str = "none", sw: float = 1.4, dash: tuple[int, int] | None = None) -> str:
    if dash:
        return _dashed_rect(x, y, w, h, r, fill, stroke, sw, dash)
    return (f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="{_n(r)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def _dashed_rect(x, y, w, h, r, fill, stroke, sw, dash) -> str:
    body = (f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="{_n(r)}" '
            f'fill="{fill}" stroke="none"/>')
    pts = [(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r),
           (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)]
    segs = []
    for i in range(len(pts)):
        segs.extend(_dash_segments(pts[i], pts[(i + 1) % len(pts)], dash))
    lines = "".join(f'<path d="M{_n(s[0])} {_n(s[1])} L{_n(t[0])} {_n(t[1])}" stroke="{stroke}" '
                    f'stroke-width="{sw}" fill="none"/>' for s, t in segs)
    return body + lines


def _dash_segments(a: tuple[float, float], b: tuple[float, float],
                   dash: tuple[int, int]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    on, off = dash
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    if ln < 0.5:
        return []
    ux, uy = dx / ln, dy / ln
    out, pos = [], 0.0
    while pos < ln:
        end = min(pos + on, ln)
        out.append(((a[0] + ux * pos, a[1] + uy * pos), (a[0] + ux * end, a[1] + uy * end)))
        pos = end + off
    return out


def _svg_container(b: Box) -> str:
    th = THEMES[b.theme]
    hh = G["grp_head_h"]
    r = 6
    out = [_rr(b.x, b.y, b.w, b.h, r, th["fill"], th["stroke"], 1.4)]
    out.append(f'<path d="M{_n(b.x)} {_n(b.y + r)} a{r} {r} 0 0 1 {r} -{r} '
               f'h{_n(b.w - 2 * r)} a{r} {r} 0 0 1 {r} {r} v{_n(hh - r)} h-{_n(b.w)} z" '
               f'fill="{th["header"]}"/>')
    out.append(_txt(b.cx, b.y + hh / 2 + 5, b.title, FS["grp"], "#ffffff", bold=True, anchor="middle"))
    if b.subtitle:
        out.append(_txt(b.cx, b.y + hh + 14, b.subtitle, FS["grp_sub"], MUTED, anchor="middle"))
    return "".join(out)


def _svg_table(b: Box) -> str:
    th = THEMES[b.theme]
    hh, rh, kw = G["tbl_head_h"], G["tbl_row_h"], G["tbl_key_w"]
    r = 6
    out = [_rr(b.x, b.y, b.w, b.h, r, PAPER, th["stroke"], 1.4,
               (6, 4) if b.pending else None)]
    out.append(f'<path d="M{_n(b.x)} {_n(b.y + r)} a{r} {r} 0 0 1 {r} -{r} h{_n(b.w - 2 * r)} '
               f'a{r} {r} 0 0 1 {r} {r} v{_n(hh - r)} h-{_n(b.w)} z" fill="{th["header"]}"/>')
    hink = th.get("ink", "#ffffff")
    ty = b.y + (hh / 2 + 5 if not b.subtitle else hh / 2 + 1)
    out.append(_txt(b.cx, ty, b.title, FS["tbl"], hink, bold=True, anchor="middle"))
    if b.pending:
        out.append(_txt(b.x2 - 6, b.y + 11, "PROPUESTA", 8, hink, bold=True, anchor="end"))
    if b.subtitle:
        out.append(_txt(b.cx, b.y + hh - 7, b.subtitle, FS["tbl_sub"],
                        "#55606e" if th.get("ink") else "#e8eef7", anchor="middle"))
    tw, kx = G["tbl_type_w"], b.w - kw
    kline_top = b.y + hh + (_row_h(b.rows[0]) if b.rows and b.rows[0].info else 0)
    ry = b.y + hh
    for i, row in enumerate(b.rows):
        rh = _row_h(row)
        if i % 2 and not row.info:
            out.append(f'<rect x="{_n(b.x + 1)}" y="{_n(ry)}" width="{_n(b.w - 2)}" '
                       f'height="{_n(rh)}" fill="{ZEBRA}"/>')
        if i:
            out.append(f'<line x1="{_n(b.x + 1)}" y1="{_n(ry)}" x2="{_n(b.x2 - 1)}" y2="{_n(ry)}" '
                       f'stroke="{HAIR}" stroke-width="1"/>')
        if row.info:
            out.append(f'<rect x="{_n(b.x + 1)}" y="{_n(ry)}" width="{_n(b.w - 2)}" '
                       f'height="{_n(rh)}" fill="#fafafa"/>')
            for k, ln in enumerate(row.name.split("\n")):
                out.append(_txt(b.x + 8, ry + G["lin_info_h"] * k + 11, ln, FS["tbl_sub"],
                                MUTED, italic=True))
            ry += rh
            continue
        base = ry + rh / 2 + 4
        if row.more:
            out.append(_txt(b.x + 8, base, row.name, FS["row"], MUTED, italic=True))
            ry += rh
            continue
        out.append(_txt(b.x + 8, base, row.type, FS["row"] - 1, MUTED))
        deco = "underline" if "PK" in row.key else ""
        ital = "FK" in row.key and "PK" not in row.key
        out.append(_txt(b.x + tw + 8, base, row.name, FS["row"], INK, italic=ital, deco=deco))
        if row.key:
            out.append(_txt(b.x + kx + kw / 2, base, row.key, FS["row"] - 2, th["title"],
                            bold=True, anchor="middle"))
        ry += rh
    # Separadores de columna: van ENCIMA de las franjas, debajo del texto ya
    # emitido no se verían, así que se dibujan al final sobre el cuerpo.
    body_top = kline_top
    for cx in (b.x + tw, b.x + kx):
        out.append(f'<line x1="{_n(cx)}" y1="{_n(body_top)}" x2="{_n(cx)}" '
                   f'y2="{_n(b.y2 - r / 2)}" stroke="{HAIR}" stroke-width="1"/>')
    return "".join(out)


def _svg_node(b: Box) -> str:
    th = THEMES[b.theme]
    dash = (6, 4) if b.pending else None
    out = [_rr(b.x, b.y, b.w, b.h, 8, PAPER, th["stroke"], 1.5, dash)]
    icon = ICONS.get(b.kind, ICON_FALLBACK)
    iy = b.y + 14 + G["icon_h"] / 2
    out.append(f'<g transform="translate({_n(b.cx)},{_n(iy)}) scale(0.78)">'
               f'<path d="{icon}" fill="none" stroke="{th["stroke"]}" stroke-width="2" '
               f'stroke-linecap="round" stroke-linejoin="round"/></g>')
    y = b.y + 14 + G["icon_h"] + 14
    for ln in b.lines:
        out.append(_txt(b.cx, y, ln, FS["node"], INK, bold=True, anchor="middle"))
        y += 16
    y += 2
    for ln in b.sublines:
        out.append(_txt(b.cx, y, ln, FS["node_sub"], MUTED, anchor="middle"))
        y += 13
    if b.pending:
        out.append(_txt(b.cx, b.y2 - 7, "PENDIENTE DE PROVISIÓN", 8, "#a85a00",
                        bold=True, anchor="middle"))
    return "".join(out)


def _svg_note(b: Box) -> str:
    out = [_rr(b.x, b.y, b.w, b.h, 3, "#fffbe6", "#d6b656", 1.2)]
    y = b.y + 15
    for ln in b.lines:
        out.append(_txt(b.x + 8, y, ln, FS["note"], MUTED))
        y += 14
    return "".join(out)


def _svg_legend(doc: Doc, b: Box) -> str:
    out = [_svg_container(Box(id=b.id, x=b.x, y=b.y, w=b.w, h=b.h, role="container",
                              theme="neutral", title="Leyenda"))]
    icon_legend = getattr(doc, "icon_legend", []) or []
    cols = [(_legend_head(doc).upper(), doc.legend)]
    if icon_legend:
        cols.append(("ICONOGRAFÍA", icon_legend))
    cw = (b.w - 2 * G["grp_pad_x"]) / len(cols)
    for ci, (head, items) in enumerate(cols):
        x = b.x + G["grp_pad_x"] + ci * cw
        y = b.y + G["grp_head_h"] + 18
        out.append(_txt(x, y, head, 10, MUTED, bold=True))
        y += 16
        for it in items:
            if "color" in it:                # chip de estado (estilo linaje)
                th = THEMES.get(str(it["color"]), THEMES["neutral"])
                out.append(f'<rect x="{_n(x)}" y="{_n(y - 9)}" width="22" height="11" '
                           f'fill="{th["header"]}" stroke="{th["stroke"]}" stroke-width="1"/>')
                out.append(_txt(x + 30, y, str(it.get("label", "")), FS["legend"], INK))
                y += 20
                continue
            if "icon" in it:                     # columna de iconografía
                ic = str(it["icon"])
                if ic in ("pending", "pendiente"):
                    for sg in _dash_segments((x, y - 9), (x + 22, y - 9), (4, 3)) + \
                              _dash_segments((x, y + 1), (x + 22, y + 1), (4, 3)) + \
                              _dash_segments((x, y - 9), (x, y + 1), (4, 3)) + \
                              _dash_segments((x + 22, y - 9), (x + 22, y + 1), (4, 3)):
                        out.append(f'<path d="M{_n(sg[0][0])} {_n(sg[0][1])} L{_n(sg[1][0])} '
                                   f'{_n(sg[1][1])}" stroke="#aa5c00" stroke-width="1.4" fill="none"/>')
                else:
                    out.append(f'<g transform="translate({_n(x + 11)},{_n(y - 4)}) scale(0.55)">'
                               f'<path d="{ICONS.get(ic, ICON_FALLBACK)}" fill="none" '
                               f'stroke="{MUTED}" stroke-width="2.4" stroke-linecap="round" '
                               f'stroke-linejoin="round"/></g>')
            else:                                # columna de tipos de flujo
                t = it.get("type", "request")
                color, dash = LINES.get(t, LINES["request"])
                segs = _dash_segments((x, y - 4), (x + 26, y - 4), dash) if dash else \
                    [((x, y - 4), (x + 26, y - 4))]
                for sg in segs:
                    out.append(f'<path d="M{_n(sg[0][0])} {_n(sg[0][1])} L{_n(sg[1][0])} '
                               f'{_n(sg[1][1])}" stroke="{color}" stroke-width="2" fill="none"/>')
            out.append(_txt(x + 34, y, it.get("label", ""), FS["legend"], INK))
            y += 20
    return "".join(out)


def _svg_edge(doc: Doc, e: Edge) -> str:
    color, dash = LINES.get(e.style, LINES["request"])
    pts = e.points
    if len(pts) < 2:
        return ""
    out: list[str] = []
    for i in range(len(pts) - 1):
        segs = _dash_segments(pts[i], pts[i + 1], dash) if dash else [(pts[i], pts[i + 1])]
        for s, t in segs:
            out.append(f'<path d="M{_n(s[0])} {_n(s[1])} L{_n(t[0])} {_n(t[1])}" stroke="{color}" '
                       f'stroke-width="1.6" fill="none" stroke-linecap="round"/>')
    if doc.kind in ("er", "linaje") and e.card.startswith(("1:N", "N:N")):
        out.append(_crow(pts[-2], pts[-1], color, "N:1"))
    else:
        out.append(_arrow(pts[-2], pts[-1], color, doc.kind, e.card))
    if doc.kind == "er" or (doc.kind == "linaje" and e.card):
        if e.card.startswith(("N:", "0..")):
            out.append(_crow(pts[1], pts[0], color, "N:1"))
        else:
            out.append(_arrow(pts[1], pts[0], color, doc.kind, "1:1"))
    return "".join(out)


def _svg_edge_label(doc: Doc, e: Edge) -> str:
    if not e.label or len(e.points) < 2:
        return ""
    color, _ = LINES.get(e.style, LINES["request"])
    w = text_w(e.label, FS["edge"]) + 10
    blockers = [x for x in doc.boxes if x.role in ("node", "table", "legend")]
    mx, my = _mid(e.points, blockers, w)
    # Un codo que viaja por el pasillo más externo deja la etiqueta a caballo del
    # borde: se recorta al margen antes de dibujarla.
    lo, hi = w / 2 + G["margin"] / 2, doc.width - w / 2 - G["margin"] / 2
    mx = min(max(mx, lo), hi) if hi > lo else doc.width / 2
    return (f'<rect x="{_n(mx - w / 2)}" y="{_n(my - 9)}" width="{_n(w)}" height="17" '
            f'rx="4" fill="{CHIP_FILL}" stroke="none"/>'
            + _txt(mx, my + 3, e.label, FS["edge"], CHIP_INK, anchor="middle"))


def _mid(pts: list[tuple[float, float]], obstacles: list[Box] | None = None,
         w: float = 0.0) -> tuple[float, float]:
    """Dónde va la etiqueta: se recorre el trazo, del tramo más largo al más
    corto y en varias posiciones dentro de cada uno, y gana el primer punto que
    no cae sobre una caja ni sobre otra etiqueta ya colocada.

    Probar sólo el punto medio no basta: cuando un trazo pasa por encima de una
    tarjeta, su punto medio queda justo sobre el texto de esa tarjeta y la
    etiqueta se lee encima del nombre del componente."""
    order = sorted(range(len(pts) - 1),
                   key=lambda i: -math.hypot(pts[i + 1][0] - pts[i][0],
                                             pts[i + 1][1] - pts[i][1]))
    for i in order:
        a, b = pts[i], pts[i + 1]
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        if ln < w * 0.6:
            continue
        for f in (0.5, 0.34, 0.66, 0.2, 0.8):
            mx, my = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            r = (mx - w / 2, my - 8, mx + w / 2, my + 7)
            if obstacles and any(o.x - 2 < r[2] and o.x2 + 2 > r[0]
                                 and o.y - 2 < r[3] and o.y2 + 2 > r[1] for o in obstacles):
                continue
            if any(r[0] < q[2] and r[2] > q[0] and r[1] < q[3] and r[3] > q[1]
                   for q in _LABEL_RECTS):
                continue
            _LABEL_RECTS.append(r)
            return (mx, my)
    for i in order:
        a, b = pts[i], pts[i + 1]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 12:
            continue
        horiz = abs(b[1] - a[1]) < abs(b[0] - a[0])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        for d in (14, -14, 24, -24, 34, -34):
            cx, cy = (mx, my + d) if horiz else (mx + d, my)
            r = (cx - w / 2, cy - 8, cx + w / 2, cy + 7)
            if obstacles and any(o.x - 2 < r[2] and o.x2 + 2 > r[0]
                                 and o.y - 2 < r[3] and o.y2 + 2 > r[1] for o in obstacles):
                continue
            if any(r[0] < q[2] and r[2] > q[0] and r[1] < q[3] and r[3] > q[1]
                   for q in _LABEL_RECTS):
                continue
            _LABEL_RECTS.append(r)
            return (cx, cy)
    # Último recurso: sobre el tramo más largo, desplazando en perpendicular
    # hasta que el chip no pise otro chip. Dos etiquetas encimadas no se leen
    # ninguna de las dos, así que vale más alejarla que dejarla en su sitio.
    a, b = pts[order[0]], pts[order[0] + 1]
    horiz = abs(b[1] - a[1]) < abs(b[0] - a[0])
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    for k in range(0, 14):
        for sg in (1, -1):
            d = k * 17 * sg
            cx, cy = (mx, my + d) if horiz else (mx + d, my)
            r = (cx - w / 2, cy - 8, cx + w / 2, cy + 7)
            if any(r[0] < q[2] and r[2] > q[0] and r[1] < q[3] and r[3] > q[1]
                   for q in _LABEL_RECTS):
                continue
            _LABEL_RECTS.append(r)
            return (cx, cy)
    fb = (mx, my)
    _LABEL_RECTS.append((fb[0] - w / 2, fb[1] - 8, fb[0] + w / 2, fb[1] + 7))
    return fb


def _arrow(a: tuple[float, float], b: tuple[float, float], color: str,
           kind: str, card: str) -> str:
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    if kind in ("er", "linaje"):
        px, py = -uy, ux

        def bar(d: float) -> str:
            x0, y0 = b[0] - ux * d, b[1] - uy * d
            return (f'<path d="M{_n(x0 + px * 5)} {_n(y0 + py * 5)} L{_n(x0 - px * 5)} '
                    f'{_n(y0 - py * 5)}" stroke="{color}" stroke-width="1.6"/>')

        if card == "0..1":                      # cero o uno: círculo + barra
            cx, cy = b[0] - ux * 13, b[1] - uy * 13
            return (bar(6) + f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="3.4" fill="{PAPER}" '
                             f'stroke="{color}" stroke-width="1.4"/>')
        if card.endswith(":1") or card == "1:1":   # uno y sólo uno: barra doble
            return bar(6) + bar(11)
        return bar(7)
    tip = (b[0], b[1])
    l = (b[0] - ux * 9 - uy * 4, b[1] - uy * 9 + ux * 4)
    r = (b[0] - ux * 9 + uy * 4, b[1] - uy * 9 - ux * 4)
    return (f'<polygon points="{_n(tip[0])},{_n(tip[1])} {_n(l[0])},{_n(l[1])} '
            f'{_n(r[0])},{_n(r[1])}" fill="{color}"/>')


def _crow(a: tuple[float, float], b: tuple[float, float], color: str, card: str) -> str:
    """Pata de gallo en el extremo 'muchos' (el lado FK)."""
    if not card.startswith("N"):
        return ""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    px, py = -uy, ux
    base = (b[0] - ux * 9, b[1] - uy * 9)
    out = []
    for s in (-1, 0, 1):
        out.append(f'<path d="M{_n(b[0])} {_n(b[1])} L{_n(base[0] + px * 5 * s)} '
                   f'{_n(base[1] + py * 5 * s)}" stroke="{color}" stroke-width="1.4"/>')
    return "".join(out)


# ---------------------------------------------------------------------------
# 9. Validación. Modelo (ER) + geometría (ambos) + contraste.
#    severidad: ERROR bloquea siempre; WARN bloquea con --strict.
# ---------------------------------------------------------------------------

def rel_lum(hexc: str) -> float:
    c = hexc.lstrip("#")
    vals = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        vals.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def contrast(a: str, b: str) -> float:
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def validate(doc: Doc, spec: dict[str, Any]) -> list[dict[str, str]]:
    f: list[dict[str, str]] = []

    def add(sev: str, code: str, msg: str) -> None:
        f.append({"sev": sev, "code": code, "msg": msg})

    if doc.kind == "linaje":
        tbls = {b.title: b for b in doc.boxes if b.role == "table"}
        tocadas = {e.src for e in doc.edges} | {e.dst for e in doc.edges}
        for name, b in sorted(tbls.items()):
            if not any(r.key for r in b.rows if not r.info and not r.more):
                add("WARN", "LIN-KEY",
                    f"{name}: ninguna columna marcada K. En el lago no hay llaves declaradas: "
                    "si no se midió, el hallazgo es ese, y conviene decirlo en el bloque de info")
            if not any(r.info for r in b.rows):
                add("WARN", "LIN-INFO",
                    f"{name}: sin bloque de metadatos (volumen, ritmo o evidencia)")
            if b.id not in tocadas:
                add("WARN", "LIN-ORPHAN", f"{name}: sin ningún flujo de entrada ni de salida")

    if doc.kind == "er":
        tables = {b.title: b for b in doc.boxes if b.role == "table"}
        for name, b in sorted(tables.items()):
            keys = [r for r in b.rows if "PK" in r.key]
            if not keys:
                add("ERROR", "ER-PK", f"{name}: ninguna columna marcada PK (grano indefinido)")
            if len(b.rows) == 0:
                add("ERROR", "ER-EMPTY", f"{name}: tabla sin columnas")
            dupes = {r.name for r in b.rows if [x.name for x in b.rows].count(r.name) > 1}
            for d in sorted(dupes):
                add("ERROR", "ER-DUP-COL", f"{name}.{d}: columna repetida")
            for r in b.rows:
                if r.ref:
                    tt, _, tc = r.ref.rpartition(".")
                    if tt not in tables:
                        add("ERROR", "ER-REF", f"{name}.{r.name} → {r.ref}: la tabla destino no existe")
                    elif tc:
                        tgt = next((x for x in tables[tt].rows if x.name.lower() == tc.lower()), None)
                        if tgt is None:
                            add("ERROR", "ER-REF-COL", f"{name}.{r.name} → {r.ref}: la columna destino no existe")
                        elif "PK" not in tgt.key and "U" not in tgt.key:
                            add("WARN", "ER-REF-NOTPK",
                                f"{name}.{r.name} → {r.ref}: el destino no es PK ni único")
                        elif tgt.type and r.type and tgt.type != r.type:
                            add("WARN", "ER-TYPE",
                                f"{name}.{r.name} ({r.type}) vs {r.ref} ({tgt.type}): tipos distintos")
                if "FK" in r.key and not r.ref:
                    add("WARN", "ER-FK-NOREF", f"{name}.{r.name}: marcada FK sin 'ref:' → no genera relación")

        # Una relación explícita que nombra una columna no dibujada (recortada por
        # `focus`/`columns_limit`) se ancla a la CAJA en vez de a la fila. El
        # diagrama sigue siendo válido y pierde en silencio justo la propiedad que
        # lo hace legible: de qué columna sale y a qué columna llega.
        for rel in (spec.get("relations") or spec.get("relaciones") or []):
            for extremo in ("from", "to", "desde", "hasta"):
                val = rel.get(extremo)
                if not val or "." not in str(val):
                    continue
                tn, _, cn = str(val).rpartition(".")
                tb = tables.get(tn.strip())
                if tb is None:
                    add("ERROR", "ER-REL-TBL", f"relación {val}: la tabla no existe")
                elif not any(r.name.lower() == cn.strip().lower() for r in tb.rows):
                    add("WARN", "ER-REL-COL",
                        f"relación {val}: la columna no está dibujada → la línea se "
                        f"ancla a la caja, no a la fila (añádela a 'show'/quita el recorte)")
        linked = {e.src for e in doc.edges} | {e.dst for e in doc.edges}
        allow = set(spec.get("allow_orphan") or spec.get("permitir_huerfanas") or [])
        for name, b in sorted(tables.items()):
            if b.id not in linked and name not in allow:
                add("WARN", "ER-ORPHAN", f"{name}: sin ninguna relación (¿falta FK o sobra la tabla?)")
        pat = spec.get("naming_pattern") or spec.get("patron_nombres")
        if pat:
            rx = re.compile(pat)
            for name in sorted(tables):
                if not rx.match(name):
                    add("WARN", "ER-NAMING", f"{name}: no cumple el patrón {pat}")

    if doc.kind != "er":
        for b in doc.boxes:
            if b.role == "node" and b.kind and b.kind not in ICONS:
                add("WARN", "ICON-MISS",
                    f"{b.id}: kind '{b.kind}' sin glifo, cae al cuadrado genérico "
                    f"(añádelo a ICONS o usa un alias)")

    # Geometría: solape entre hermanos del mismo nivel.
    peers: dict[str, list[Box]] = {}
    for b in doc.boxes:
        if b.role in ("container", "table", "node", "legend"):
            peers.setdefault(b.parent if b.role == "node" else "1", []).append(b)
    for lvl, group in peers.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, c = group[i], group[j]
                if a.role == "container" and c.role in ("table", "node"):
                    continue
                if c.role == "container" and a.role in ("table", "node"):
                    continue
                ox = min(a.x2, c.x2) - max(a.x, c.x)
                oy = min(a.y2, c.y2) - max(a.y, c.y)
                if ox > 1 and oy > 1:
                    add("ERROR", "GEO-OVERLAP",
                        f"{a.id} y {c.id} se solapan ({_n(ox)}×{_n(oy)} px)")

    # Tablas/nodos fuera de su contenedor.
    bid = doc.by_id()
    for b in doc.boxes:
        if b.role in ("table", "node"):
            for cont in [x for x in doc.boxes if x.role == "container" and x.id != "legend"]:
                inside_x = cont.x <= b.cx <= cont.x2
                if inside_x and cont.y <= b.cy <= cont.y2:
                    if not (b.x >= cont.x - 1 and b.x2 <= cont.x2 + 1 and b.y2 <= cont.y2 + 1):
                        add("ERROR", "GEO-ESCAPE", f"{b.id} desborda su contenedor {cont.id}")

    # Texto que no cabe.
    for b in doc.boxes:
        if b.role == "table":
            if text_w(b.title, FS["tbl"], True) > b.w - 16:
                add("WARN", "TXT-HEAD", f"{b.title}: el nombre no cabe en la cabecera")
            for r in b.rows:
                if r.info:        # el bloque de metadatos ocupa el ancho completo
                    for ln in r.name.split("\n"):
                        if text_w(ln, FS["tbl_sub"]) > b.w - 16:
                            add("WARN", "TXT-INFO",
                                f"{b.title}: «{ln[:48]}…» no cabe en el bloque de metadatos")
                    continue
                if text_w(r.name, FS["row"]) > b.w - G["tbl_type_w"] - G["tbl_key_w"] - 16:
                    add("WARN", "TXT-ROW", f"{b.title}.{r.name}: el nombre se recorta")
                if text_w(r.type, FS["row"] - 1) > G["tbl_type_w"] - 14:
                    add("WARN", "TXT-TYPE", f"{b.title}.{r.name}: el tipo «{r.type}» se recorta")
        if b.role == "container" and text_w(b.title, FS["grp"], True) > b.w - 20:
            add("WARN", "TXT-CONT", f"{b.id}: el título de la sección no cabe")

    # Aristas que atraviesan cajas ajenas.
    obstacles = [b for b in doc.boxes if b.role in ("table", "node", "legend")]
    for e in doc.edges:
        for i in range(len(e.points) - 1):
            p, q = e.points[i], e.points[i + 1]
            for o in obstacles:
                if o.id in (e.src, e.dst):
                    continue
                if _seg_hits(p, q, o):
                    add("WARN", "GEO-CROSS", f"{e.id}: el trazo cruza {o.id}")
                    break

    if any(b.role == "table" for b in doc.boxes):
        cr = contrast(INK, TABLE_BODY)
        if cr < 4.5:
            add("ERROR", "A11Y-TABLE-BODY",
                f"cuerpo de tabla {TABLE_BODY} con texto {INK} = {cr:.2f}:1 (<4.5). "
                f"El color de dominio va en la cabecera, no detrás de las columnas")

    # El color de un tipo de línea también se usa para su etiqueta, así que tiene
    # que pasar el umbral de TEXTO (4.5:1), no el de objeto gráfico (3:1).
    for style in sorted({e.style for e in doc.edges if e.label}):
        color = LINES.get(style, LINES["request"])[0]
        cr = contrast(color, "#ffffff")
        if cr < 4.5:
            add("ERROR", "A11Y-EDGE-LABEL",
                f"tipo '{style}': etiqueta {color} sobre chip blanco = {cr:.2f}:1 (<4.5)")

    # Contraste de las cabeceras usadas.
    for theme in sorted({b.theme for b in doc.boxes if b.role in ("container", "table")}):
        ink = THEMES[theme].get("ink", "#ffffff")
        cr = contrast(THEMES[theme]["header"], ink)
        if cr < 4.5:
            add("ERROR", "A11Y-CONTRAST",
                f"tema {theme}: cabecera {THEMES[theme]['header']} con texto {ink} = {cr:.2f}:1 (<4.5)")

    if doc.width > 4200 or doc.height > 4200:
        add("WARN", "GEO-CANVAS",
            f"lienzo {_n(doc.width)}×{_n(doc.height)}: usa 'focus: keys' o divide en páginas")
    return f


def _seg_hits(p, q, o: Box) -> bool:
    x1, x2 = sorted((p[0], q[0]))
    y1, y2 = sorted((p[1], q[1]))
    return (x1 < o.x2 - 2 and x2 > o.x + 2 and y1 < o.y2 - 2 and y2 > o.y + 2)



def check_drawio_xml(xml: str) -> list[dict[str, str]]:
    """Comprueba que el .drawio emitido sea estructuralmente válido.

    No hay motor de draw.io disponible aquí, así que la única forma honesta de
    afirmar que el archivo abre es verificar las invariantes que draw.io exige:
    XML bien formado, todo `parent` resuelto, filas dentro de tablas, celdas
    dentro de filas, y `source`/`target` de cada arista existentes. Un `parent`
    colgando no da error al abrir: draw.io simplemente no dibuja ese elemento,
    que es el fallo silencioso que este chequeo evita."""
    out: list[dict[str, str]] = []

    def add(code: str, msg: str, sev: str = "ERROR") -> None:
        out.append({"sev": sev, "code": code, "msg": msg})

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        add("XML-PARSE", f"XML mal formado: {exc}")
        return out

    cells = {c.get("id"): c for c in root.iter("mxCell")}

    def style_of(ref: str | None) -> str:
        c = cells.get(ref or "")
        return (c.get("style") or "") if c is not None else ""

    if "0" not in cells or "1" not in cells:
        add("XML-ROOT", "faltan las celdas raíz 0 y 1")
    for cid, c in cells.items():
        if cid is None:
            add("XML-ID", "hay una mxCell sin id")
            continue
        par = c.get("parent")
        if par is not None and par not in cells:
            add("XML-PARENT", f"{cid}: parent '{par}' no existe (draw.io lo omitiría en silencio)")
        st = c.get("style") or ""
        if "shape=tableRow" in st:
            if "childLayout=tableLayout" not in style_of(par):
                add("XML-ROW", f"{cid}: tableRow cuyo padre no es una tabla")
        if "shape=partialRectangle" in st:
            if "shape=tableRow" not in style_of(par):
                add("XML-CELL", f"{cid}: celda cuyo padre no es una tableRow")
        if c.get("edge") == "1":
            for role in ("source", "target"):
                ref = c.get(role)
                if ref and ref not in cells:
                    add("XML-EDGE", f"{cid}: {role} '{ref}' no existe")
        geo = c.find("mxGeometry")
        if c.get("vertex") == "1" and geo is None:
            add("XML-GEO", f"{cid}: vértice sin mxGeometry")
    dup = len(list(root.iter("mxCell"))) - len(cells)
    if dup:
        add("XML-DUP", f"{dup} id(s) duplicado(s) entre mxCell")
    return out


# ---------------------------------------------------------------------------
# 10. Auditoría de un .drawio hecho a mano (no generado por el spec).
# ---------------------------------------------------------------------------

def inspect_drawio(path: Path) -> int:
    tree = ET.parse(path)
    cells = {c.get("id"): c for c in tree.iter("mxCell")}
    tables, rows_of = {}, {}
    for cid, c in cells.items():
        st = c.get("style") or ""
        if "childLayout=tableLayout" in st or "shape=table;" in st:
            tables[cid] = _strip_html(c.get("value") or cid)
            rows_of[cid] = []
    for cid, c in cells.items():
        if "shape=tableRow" in (c.get("style") or "") and c.get("parent") in rows_of:
            cellvals = [_strip_html(k.get("value") or "")
                        for k in cells.values() if k.get("parent") == cid]
            rows_of[c.get("parent")].append(cellvals)

    # Entidad de texto plano = caja con relleno y borde propios cuyo contenido es
    # una lista de columnas. Los rótulos (título, pie) también llevan
    # verticalAlign=top, así que se excluyen por no tener trazo ni relleno.
    legacy = []
    for cid, c in cells.items():
        st = c.get("style") or ""
        if c.get("vertex") != "1" or "shape=" in st or "childLayout" in st:
            continue
        if "verticalAlign=top" not in st or "strokeColor=none" in st or st.startswith("text;"):
            continue
        legacy.append((_strip_html(c.get("value") or ""), cid))

    print(f"# Auditoría ER — {path.name}\n")
    if not tables and legacy:
        print(f"Formato: cajas de texto plano ({len(legacy)} entidades). No hay tablas nativas de")
        print("drawio, así que no existe columna PK/FK ni anclaje de relaciones por columna.")
        print("Recomendación: regenerar con `forge.py build` desde un spec para obtener")
        print("cabecera, columna de llave y relaciones ancladas a la fila.\n")
    edges = [c for c in cells.values() if c.get("edge") == "1"]
    def style_of(ref: str | None) -> str:
        c = cells.get(ref or "")
        return (c.get("style") or "") if c is not None else ""

    row_anchored = sum(1 for e in edges if "shape=tableRow" in style_of(e.get("source")))
    print(f"Tablas nativas: {len(tables)}   Entidades de texto plano: {len(legacy)}")
    print(f"Relaciones: {len(edges)} (ancladas a columna: {row_anchored})")
    problems = 0
    for cid, name in sorted(tables.items(), key=lambda kv: kv[1]):
        keys = [r for r in rows_of[cid] if r and any("PK" in (v or "").upper() for v in r)]
        if not keys:
            print(f"  ERROR  {name}: sin columna marcada PK")
            problems += 1
    if row_anchored < len(edges):
        print(f"  WARN   {len(edges) - row_anchored} relación(es) ancladas a la caja, no a la columna")
        problems += 1
    print(f"\nHallazgos: {problems}")
    return 0 if problems == 0 else 1


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------------------------------------------------------------------------
# 11. CLI
# ---------------------------------------------------------------------------

def build_doc(spec: dict[str, Any]) -> Doc:
    if spec["kind"] == "linaje":
        return layout_linaje(spec)
    return layout_er(spec) if spec["kind"] == "er" else layout_components(spec)


def report(findings: list[dict[str, str]]) -> tuple[int, int]:
    errs = sum(1 for x in findings if x["sev"] == "ERROR")
    warns = len(findings) - errs
    for x in findings:
        print(f"  {x['sev']:<5} {x['code']:<15} {x['msg']}", file=sys.stderr)
    print(f"  → {errs} ERROR, {warns} WARN", file=sys.stderr)
    return errs, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("spec", type=Path)
    b.add_argument("--out-dir", type=Path, default=None)
    b.add_argument("--name", default=None)
    b.add_argument("--strict", action="store_true")
    b.add_argument("--only", choices=("drawio", "svg"), default=None)

    v = sub.add_parser("validate")
    v.add_argument("spec", type=Path)
    v.add_argument("--strict", action="store_true")

    i = sub.add_parser("inspect")
    i.add_argument("file", type=Path)

    args = ap.parse_args()

    if args.cmd == "inspect":
        return inspect_drawio(args.file)

    spec = load_spec(args.spec)
    doc = build_doc(spec)
    findings = validate(doc, spec)

    if args.cmd == "validate":
        errs, warns = report(findings)
        return 1 if errs or (warns and args.strict) else 0

    out_dir = args.out_dir or args.spec.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.name or args.spec.stem
    written = []
    if args.only != "svg":
        p = out_dir / f"{base}.drawio"
        xml = emit_drawio(doc)
        findings.extend(check_drawio_xml(xml))
        p.write_text(xml, encoding="utf-8")
        written.append(p)
    if args.only != "drawio":
        p = out_dir / f"{base}.svg"
        p.write_text(emit_svg(doc), encoding="utf-8")
        written.append(p)

    metrics = {
        "kind": doc.kind, "title": doc.title,
        "canvas": {"w": round(doc.width, 1), "h": round(doc.height, 1)},
        "counts": {
            "containers": sum(1 for x in doc.boxes if x.role == "container"),
            "lanes": sum(1 for x in doc.boxes if x.role == "lane"),
            "tables": sum(1 for x in doc.boxes if x.role == "table"),
            "nodes": sum(1 for x in doc.boxes if x.role == "node"),
            "edges": len(doc.edges),
            "rows": sum(len(x.rows) for x in doc.boxes if x.role == "table"),
        },
        "findings": findings,
        "boxes": [{"id": x.id, "role": x.role, "x": round(x.x, 1), "y": round(x.y, 1),
                   "w": round(x.w, 1), "h": round(x.h, 1)} for x in doc.boxes],
    }
    mp = out_dir / f"{base}.metrics.json"
    mp.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                  encoding="utf-8")
    written.append(mp)

    errs, warns = report(findings)
    for p in written:
        print(p)
    return 1 if errs or (warns and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
