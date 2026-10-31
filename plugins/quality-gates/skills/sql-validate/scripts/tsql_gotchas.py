"""Detecta errores de T-SQL que el parser acepta pero SQL Server rechaza.

`sqlfluff parse` valida gramática. No valida semántica: `RAISERROR(msg, 16, 1,
DB_NAME())` parsea perfecto y SQL Server lo rechaza con "Incorrect syntax near
'DB_NAME'". Este script cubre esa segunda capa con reglas que salieron de
errores reales en producción.

Uso:
    python3 tsql_gotchas.py archivo.sql [archivo2.sql ...]
    python3 tsql_gotchas.py --json archivo.sql

Salida: hallazgos por línea. Código de salida 1 si hay alguno de severidad
ERROR, 0 en el resto.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Hallazgo:
    archivo: str
    linea: int
    severidad: str
    regla: str
    mensaje: str
    arreglo: str
    fragmento: str


def _sin_comentarios(texto: str) -> str:
    """Neutraliza comentarios y literales conservando el número de líneas."""
    fuera = []
    i, n = 0, len(texto)
    while i < n:
        if texto.startswith("--", i):
            j = texto.find("\n", i)
            j = n if j == -1 else j
            fuera.append(" " * (j - i))
            i = j
        elif texto.startswith("/*", i):
            j = texto.find("*/", i + 2)
            j = n if j == -1 else j + 2
            fuera.append("".join(c if c == "\n" else " " for c in texto[i:j]))
            i = j
        elif texto[i] == "'":
            j = i + 1
            while j < n:
                if texto[j] == "'":
                    if j + 1 < n and texto[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            fuera.append("".join(c if c == "\n" else " " for c in texto[i:j]))
            i = j
        else:
            fuera.append(texto[i])
            i += 1
    return "".join(fuera)


# (regla, severidad, patrón, mensaje, arreglo)
REGLAS: list[tuple[str, str, str, str, str]] = [
    (
        "raiserror-arg-funcion",
        "ERROR",
        r"RAISERROR\s*\([^)]*?,\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)",
        "RAISERROR con una llamada a función como argumento de sustitución.",
        "Asignar a variable primero: DECLARE @v sysname = DB_NAME(); RAISERROR(..., @v);",
    ),
    (
        "rowcount-tras-declare",
        "ERROR",
        r"DECLARE\s+@\w+\s+\w+(\s*\(\s*\d+\s*\))?\s*=\s*@@ROWCOUNT",
        "DECLARE con asignación puede dejar @@ROWCOUNT en 0 antes de leerlo.",
        "Declarar aparte y capturar con SET en la instrucción inmediata al DML.",
    ),
    (
        "error-tras-declare",
        "ERROR",
        r"DECLARE\s+@\w+\s+\w+(\s*\(\s*\d+\s*\))?\s*=\s*@@ERROR",
        "DECLARE con asignación puede resetear @@ERROR antes de leerlo.",
        "Declarar aparte y capturar con SET justo después de la instrucción.",
    ),
    (
        "like-guion-bajo",
        "AVISO",
        r"LIKE\s+N?'[^']*[A-Za-z0-9]_[A-Za-z0-9][^']*'(?!\s+ESCAPE)",
        "En LIKE el guion bajo es comodín de un carácter, no literal.",
        "Usar CHARINDEX, o ESCAPE: LIKE '%a\\_b%' ESCAPE '\\'.",
    ),
    (
        "drop-objeto-real",
        "AVISO",
        r"\bDROP\s+(TABLE|VIEW|PROCEDURE|FUNCTION|INDEX)\s+(?!#|tempdb|IF\s+EXISTS\s+#)",
        "DROP sobre un objeto que no es temporal.",
        "Confirmar que es intencional y que hay respaldo.",
    ),
    (
        "truncate",
        "AVISO",
        r"\bTRUNCATE\s+TABLE\s+(?!#)",
        "TRUNCATE no se puede filtrar y reinicia IDENTITY.",
        "Usar DELETE con WHERE si se quiere borrado parcial o auditable.",
    ),
    (
        "not-in-subconsulta",
        "AVISO",
        r"\bNOT\s+IN\s*\(\s*SELECT\b",
        "NOT IN con una subconsulta que devuelva NULL no retorna filas.",
        "Usar NOT EXISTS.",
    ),
    (
        "top-sin-order",
        "AVISO",
        r"\bSELECT\s+TOP\s*\(?\s*\d+\s*\)?(?:(?!\bORDER\s+BY\b|;).)*?;",
        "TOP sin ORDER BY: el resultado no es determinístico.",
        "Agregar ORDER BY explícito.",
    ),
    (
        "isnumeric",
        "AVISO",
        r"\bISNUMERIC\s*\(",
        "ISNUMERIC acepta valores que no convierten a int, como '1e5' o '$1'.",
        "Usar TRY_CAST/TRY_CONVERT y comparar contra NULL.",
    ),
    (
        "nolock",
        "AVISO",
        r"WITH\s*\(\s*NOLOCK\s*\)",
        "NOLOCK permite lecturas sucias y filas duplicadas o ausentes.",
        "Quitarlo, o usar READ COMMITTED SNAPSHOT si el objetivo es no bloquear.",
    ),
]


# Encabezados de control: no son la "instrucción anterior" a THROW, solo lo
# envuelven. Hay que seguir mirando hacia atrás por encima de ellos.
_ENCABEZADO = re.compile(r"^\s*(IF|ELSE|WHILE|BEGIN)\b", re.I)

# Continuación de una condición repartida en varias líneas: tampoco es la
# instrucción anterior.
_CONTINUACION = re.compile(r"^\s*((OR|AND)\b|[,()])", re.I)


def _dml_sin_where(codigo: str) -> list[tuple[int, str, str]]:
    """UPDATE/DELETE que abarcan la tabla entera.

    Se aisla cada instrucción hasta su punto y coma y se busca WHERE dentro.
    Una sola expresión regular para esto es frágil: los subselects y los JOIN
    meten palabras clave que confunden el conteo.
    """
    fallos = []
    # Ambitos de MERGE. Dentro de un MERGE, el UPDATE y el DELETE de las ramas
    # WHEN estan acotados por la clausula ON y por los predicados de cada WHEN:
    # un WHERE ahi no es que falte, es que no es T-SQL valido. Se calcula el
    # tramo de cada MERGE y se ignora cualquier DML que caiga dentro.
    #
    # Antes esto se resolvia con una ventana de 200 caracteres hacia atras
    # buscando "WHEN MATCHED ... THEN", y fallaba con predicados largos
    # (`WHEN MATCHED AND (a <> b OR c <> d OR ...) THEN`) y no cubria nada el
    # `WHEN NOT MATCHED BY SOURCE THEN DELETE`. Un validador que marca todo
    # MERGE correcto se acaba ignorando, que es peor que no tenerlo.
    ambitos_merge = [(m.start(), m.end())
                     for m in re.finditer(r"\bMERGE\b[^;]*;", codigo, re.I | re.S)]

    def dentro_de_merge(pos: int) -> bool:
        return any(ini <= pos < fin for ini, fin in ambitos_merge)

    for verbo in ("UPDATE", "DELETE"):
        for m in re.finditer(rf"\b{verbo}\b[^;]*;", codigo, re.I | re.S):
            if dentro_de_merge(m.start()):
                continue
            fragmento = m.group(0)
            objetivo = re.search(
                rf"\b{verbo}\s+(?:FROM\s+)?(?:TOP\s*\(?\d+\)?\s+)?([#\w\[\]\.]+)",
                fragmento, re.I,
            )
            nombre = objetivo.group(1) if objetivo else "?"
            # `UPDATE STATISTICS` no es DML: es mantenimiento del optimizador y
            # nunca lleva WHERE. Mismo caso `UPDATE STATISTICS ... WITH FULLSCAN`.
            # Se filtra por el objetivo para no depender del resto del fragmento.
            if nombre.upper() in ("STATISTICS",):
                continue
            if nombre.startswith("#") or nombre.startswith("@"):
                continue  # tabla temporal o variable: no es dato de negocio
            # `UPDATE SET` con SET como objetivo solo ocurre dentro de un MERGE,
            # y eso ya se filtro por ambito mas arriba. Se deja la salida por si
            # aparece un MERGE sin punto y coma final, que el ambito no veria.
            if nombre.upper() == "SET":
                continue
            if re.search(r"\bWHERE\b", fragmento, re.I):
                continue
            linea = codigo[: m.start()].count("\n") + 1
            fallos.append((linea, verbo, nombre))
    return fallos


def _throw_sin_punto_y_coma(codigo: str) -> list[int]:
    """THROW exige que la instrucción anterior termine en punto y coma."""
    lineas = codigo.split("\n")
    fallos = []
    for idx, linea in enumerate(lineas):
        marca = re.search(r"\bTHROW\b", linea, re.I)
        if not marca:
            continue
        # THROW con algo antes en la misma línea (p. ej. `IF cond THROW ...`)
        # se evalúa contra lo que hubiera antes de ese bloque.
        antes_en_linea = linea[: marca.start()].strip()
        if antes_en_linea and not _ENCABEZADO.match(antes_en_linea) \
           and not antes_en_linea.endswith((")", "BEGIN", "ELSE")):
            continue

        previo = ""
        for anterior in reversed(lineas[:idx]):
            texto = anterior.strip()
            # Un encabezado que ya cierra con ';' es una instrucción completa
            # (`IF cond ROLLBACK TRANSACTION;`), no un envoltorio.
            if not texto or (_ENCABEZADO.match(texto) and not texto.endswith(";")):
                continue
            # Línea de continuación de una condición multilínea.
            if _CONTINUACION.match(texto) and not texto.endswith(";"):
                continue
            previo = texto
            break
        if previo and not previo.endswith((";", "BEGIN", "ELSE")):
            fallos.append(idx + 1)
    return fallos


def revisar(path: Path) -> list[Hallazgo]:
    texto = path.read_text(encoding="utf-8-sig", errors="replace")
    codigo = _sin_comentarios(texto)
    lineas = texto.split("\n")
    hallazgos: list[Hallazgo] = []

    for regla, severidad, patron, mensaje, arreglo in REGLAS:
        for m in re.finditer(patron, codigo, re.I | re.S):
            linea = codigo[: m.start()].count("\n") + 1
            hallazgos.append(
                Hallazgo(
                    archivo=str(path),
                    linea=linea,
                    severidad=severidad,
                    regla=regla,
                    mensaje=mensaje,
                    arreglo=arreglo,
                    fragmento=lineas[linea - 1].strip()[:110] if linea <= len(lineas) else "",
                )
            )

    for linea, verbo, tabla in _dml_sin_where(codigo):
        hallazgos.append(
            Hallazgo(
                archivo=str(path), linea=linea, severidad="ERROR",
                regla=f"{verbo.lower()}-sin-where",
                mensaje=f"{verbo} sobre {tabla} sin WHERE: afecta la tabla completa.",
                arreglo="Agregar WHERE, o confirmar explícitamente que es intencional.",
                fragmento=lineas[linea - 1].strip()[:110] if linea <= len(lineas) else "",
            )
        )

    for linea in _throw_sin_punto_y_coma(codigo):
        hallazgos.append(
            Hallazgo(
                archivo=str(path),
                linea=linea,
                severidad="ERROR",
                regla="throw-sin-punto-y-coma",
                mensaje="La instrucción anterior a THROW debe terminar en punto y coma.",
                arreglo="Cerrar la instrucción previa con ';'.",
                fragmento=lineas[linea - 1].strip()[:110] if linea <= len(lineas) else "",
            )
        )

    # Una transacción sin ambos caminos de cierre queda abierta si falla.
    if re.search(r"\bBEGIN\s+TRAN(SACTION)?\b", codigo, re.I):
        if not re.search(r"SET\s+XACT_ABORT\s+ON", codigo, re.I):
            hallazgos.append(
                Hallazgo(str(path), 1, "AVISO", "tran-sin-xact-abort",
                         "Hay transacción y falta SET XACT_ABORT ON.",
                         "Agregarlo al inicio para que un error revierta todo.", "")
            )
        if not re.search(r"\bROLLBACK\b", codigo, re.I):
            hallazgos.append(
                Hallazgo(str(path), 1, "ERROR", "tran-sin-rollback",
                         "Hay BEGIN TRANSACTION sin ningún ROLLBACK.",
                         "Agregar TRY/CATCH con ROLLBACK.", "")
            )
        if not re.search(r"\bCOMMIT\b", codigo, re.I):
            hallazgos.append(
                Hallazgo(str(path), 1, "ERROR", "tran-sin-commit",
                         "Hay BEGIN TRANSACTION sin ningún COMMIT.",
                         "Agregar COMMIT en el camino feliz.", "")
            )

    return sorted(hallazgos, key=lambda h: (h.linea, h.regla))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivos", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    todos: list[Hallazgo] = []
    for path in args.archivos:
        if not path.exists():
            print(f"No existe: {path}", file=sys.stderr)
            return 2
        todos.extend(revisar(path))

    if args.json:
        print(json.dumps([asdict(h) for h in todos], indent=2, ensure_ascii=False))
    elif not todos:
        print("Sin hallazgos semánticos.")
    else:
        actual = None
        for h in todos:
            if h.archivo != actual:
                actual = h.archivo
                print(f"\n== {actual}")
            print(f"  {h.severidad:<5} L{h.linea:<5} {h.regla}")
            print(f"        {h.mensaje}")
            print(f"        arreglo: {h.arreglo}")
            if h.fragmento:
                print(f"        > {h.fragmento}")

    errores = sum(1 for h in todos if h.severidad == "ERROR")
    avisos = len(todos) - errores
    print(f"\nERROR={errores}  AVISO={avisos}")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
