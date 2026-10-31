---
name: diagramas-drawio
description: Modela y genera diagramas editables (.drawio + .svg) desde un spec YAML — ER de bases de datos con cabecera de tabla, columna PK/FK y relaciones ancladas a la columna, y diagramas de componentes/infraestructura con secciones de dominio, iconos y corredores de ruteo. Determinista: mismo spec, mismos bytes. Incluye validador de modelado y geometría, juez de píxeles para iterar, e importador de .drawio heredados. Usar cuando se pida crear, rehacer, auditar o publicar un diagrama ER, de arquitectura, de componentes o de infraestructura, o cuando un diagrama existente esté hecho a mano y haya que volverlo editable y validable.
---

# Diagramas editables (draw.io)

Un diagrama que no se puede editar se vuelve mentira en dos semanas: alguien
mueve una tabla en la base, nadie puede tocar el PNG, y el diagrama sigue
colgado en la wiki diciendo lo que era. Este skill produce **.drawio** — se abre,
se arrastra una caja, se alinea, se cambia un tipo de dato — generado desde un
**spec** que es la fuente de verdad y que se valida antes de publicar.

## Regla cero

**El spec manda. El .drawio se genera. El .svg no se edita nunca a mano.**

- `spec.yaml` → se versiona, se revisa en PR, es lo que se corrige.
- `.drawio` → artefacto editable que se entrega y se abre en app.diagrams.net.
- `.svg` → misma geometría, para README/Wiki y para que el juez lo rasterice.

Retocar el `.drawio` a mano está bien para un ajuste fino de última hora
(mover 20px una caja). Si el cambio es de contenido —una tabla, una columna, una
relación— va en el spec y se regenera; si no, el siguiente `build` lo borra.
Cuando alguien ya editó el `.drawio` y hay que recuperar ese modelo, se usa
`import_drawio.py`, no se retipea.

## Cuándo usar este skill

- "Hazme el ER de …", "diagrama de arquitectura", "diagrama de componentes",
  "diagrama de infraestructura", "modelo de datos en draw.io".
- Un diagrama existente hay que rehacerlo, actualizarlo o auditarlo.
- Hay un `.png` de arquitectura sin fuente editable y hace falta la fuente.
- Antes de publicar en Wiki/PR: validar que el diagrama no miente ni desborda.

## Los tres tipos

| `kind` | Para qué | Elemento base | Relaciones |
|---|---|---|---|
| `er` | Modelo de datos: tablas, llaves, cardinalidad | tabla con cabecera de color, columna PK/FK y una fila por campo | derivadas de los `ref:` de las FK, ancladas a la fila |
| `componentes` | Arquitectura, infraestructura, flujo entre servicios | sección de dominio con barra de color + tarjetas de nodo con icono | declaradas en `connections`, ruteadas por corredores |
| `linaje` | Linaje e ingeniería de datos: de dónde sale cada tabla y qué le pasa | carriles por capa + tabla con bloque de metadatos y columna **K** | `flows`: flechas de flujo con su etiqueta pegada al destino |

Si el spec no declara `kind`, se autodetecta: con `sections`/`nodes` es
`componentes`, si no es `er`. Un `infra-diagram.config.json` existente se
consume tal cual.

### Qué distingue al `linaje` del `er`

No es decoración. Las tres diferencias responden a que en un lago **no hay
llaves declaradas ni integridad referencial**, así que el diagrama tiene que
decir qué se midió y qué no:

1. **El color dice el ESTADO de la tabla, no su dominio.** `canon` se conserva,
   `subset` es variante, `dup` sobra, `origen` está fuera de Unity Catalog,
   `destino` es el sistema al que hay que llegar. El lector pregunta «¿esta
   tabla sirve o sobra?», no «¿de qué esquema es?».
2. **Bajo la cabecera va un bloque de metadatos** (`info:`): volumen, ritmo de
   actualización y **su evidencia**. Un `⟳ diaria ~14:47 UTC` sin decir de dónde
   sale es una afirmación sin respaldo.
3. **La columna de llave dice `K` = llave MEDIDA.** Una tabla sin `K` no es un
   descuido: es el hallazgo, y el validador lo marca con `LIN-KEY` en vez de
   bloquear. Por lo mismo, **la pata de gallina sólo se dibuja cuando el flujo
   declara `card`**: sin perfil de duplicidad medido, afirmar la cardinalidad
   sería inventarla.

El estilo viene de diagramas de linaje que se generaban con scripts copiados
entre repos. Vive aquí para que haya un solo motor.

**El bloque de metadatos y el color de estado también funcionan en `kind: er`**:
una tabla del ER puede declarar `info:` y `estado:` y adopta la misma anatomía,
conservando bandas de dominio, `ref:` y pata de gallina. Es lo correcto cuando
el diagrama es un modelo relacional y aun así hay que decir el volumen medido o
de dónde sale cada entidad.

## Flujo

### 1. Ingerir (sólo si ya hay algo)

```bash
S=~/.claude/skills/diagramas-drawio/scripts

# De un .drawio heredado a spec. Recupera nombres, tipos, PK/FK, y resuelve el
# destino de cada FK leyendo las aristas ("IdCliente → Id" + source/target).
python3 $S/import_drawio.py viejo.drawio --out docs/diagramas/modelo.yaml

# Auditar un .drawio sin convertirlo (¿tiene tablas nativas? ¿PK? ¿las
# relaciones están ancladas a la columna o a la caja?)
python3 $S/forge.py inspect viejo.drawio
```

Lo que el importador no puede deducir sale como `ref: "?"` con un `# TODO`.
**Resolverlos leyendo la fuente real** (DDL, `describe_table`, la app) — nunca
inventando un destino plausible.

### 2. Especificar

Copia una plantilla de `templates/` y edítala. El contrato completo está en
[references/spec.md](references/spec.md). Lo mínimo de un ER:

```yaml
kind: er
title: "ER Cotizador PRD (SQL Server)"
groups:
  - {id: cot, title: "Cotización", theme: blue}
  - {id: mat, title: "Materiales y costos", theme: orange}
tables:
  - name: Cotizacion
    group: cot
    schema: dbo
    columns:
      - {name: IdGeneral, type: "varchar(20)", key: PK}
      - {name: IdCliente, type: int, key: FK, ref: "Cliente.Id"}
      - {name: Fecha, type: date}
```

Reglas de contenido, no de sintaxis:

- **Una tabla sin PK no se publica.** Si la fuente real no la tiene, eso es el
  hallazgo — se reporta, no se inventa una llave.
- **Cada FK lleva `ref:`.** Una FK sin `ref` no dibuja relación: el diagrama se
  vería completo y estaría vacío de información. El validador lo marca.
- **Tablas de 40+ columnas van con `focus: keys` o `columns_limit: 12`** en los
  diagramas de visión general; con todas las columnas sólo en el ER de detalle.
  Una tabla de 90 filas mide 2000px y arrastra el lienzo entero.
- **Agrupar por dominio, no por esquema.** El color de grupo es lo que hace el
  diagrama legible de un vistazo.

### 3. Construir

```bash
python3 $S/forge.py build docs/diagramas/modelo.yaml --out-dir docs/diagramas
# → modelo.drawio  modelo.svg  modelo.metrics.json
```

### 4. Validar — las compuertas

`build` valida siempre e imprime los hallazgos. `ERROR` bloquea la publicación;
`WARN` se decide caso por caso y con `--strict` también bloquea.

| Código | Qué detecta | Sev |
|---|---|---|
| `ER-PK` | tabla sin PK: el grano no está definido | ERROR |
| `ER-REF` / `ER-REF-COL` | la FK apunta a una tabla o columna que no existe | ERROR |
| `ER-DUP-COL` | columna repetida en la misma tabla | ERROR |
| `ER-REF-NOTPK` | la FK apunta a algo que no es PK ni único | WARN |
| `ER-TYPE` | tipo de la FK distinto del tipo de la PK destino | WARN |
| `ER-FK-NOREF` | marcada FK y sin `ref`: no genera relación | WARN |
| `ER-ORPHAN` | tabla sin ninguna relación | WARN |
| `ER-NAMING` | no cumple `naming_pattern` | WARN |
| `GEO-OVERLAP` | dos cajas encimadas | ERROR |
| `GEO-ESCAPE` | una tabla/nodo se sale de su contenedor | ERROR |
| `A11Y-CONTRAST` | cabecera con texto blanco por debajo de 4.5:1 | ERROR |
| `XML-*` | el `.drawio` no abriría bien (padre colgando, fila fuera de tabla, arista sin extremo) | ERROR |
| `GEO-CROSS` | un trazo cruza una caja ajena | WARN |
| `TXT-*` | texto que se recorta | WARN |
| `ICON-MISS` | `kind` sin glifo: caería al cuadrado genérico | WARN |
| `GEO-CANVAS` | lienzo desproporcionado | WARN |
| `LIN-KEY` | tabla de linaje sin ninguna columna `K`: no se midió la llave | WARN |
| `LIN-INFO` | tabla de linaje sin bloque de metadatos | WARN |
| `LIN-ORPHAN` | tabla de linaje sin flujo de entrada ni de salida | WARN |
| `TXT-INFO` | renglón del bloque de metadatos que se recorta | WARN |

`XML-*` existe porque aquí no hay motor de draw.io para abrir el archivo y
comprobarlo. Un `parent` colgando no da error al abrir: draw.io simplemente no
dibuja ese elemento. La compuerta verifica las invariantes que draw.io exige en
vez de suponer que el archivo está bien.

### 5. Juzgar — el bucle

Los hallazgos prueban que la geometría es correcta; **no** prueban que el
diagrama se vea bien. Para eso hay que mirarlo.

```bash
TMP=$(mktemp -d)                       # las iteraciones NO van en el repo

python3 $S/forge.py build spec.yaml --out-dir $TMP/i1 --name d
python3 $S/judge.py render $TMP/i1/d.svg --dpi 90
python3 $S/judge.py score  $TMP/i1/d.png --metrics $TMP/i1/d.metrics.json
```

`score` da un veredicto objetivo (densidad de tinta, blanco muerto, márgenes,
alineación de columnas) más los `ERROR` del build. Después **mira el PNG**: es
el único paso que detecta "está correcto y se ve mal".

Al cambiar algo, compara contra la iteración anterior:

```bash
python3 $S/forge.py build spec.yaml --out-dir $TMP/i2 --name d
python3 $S/judge.py render $TMP/i2/d.svg --dpi 90
python3 $S/judge.py compare $TMP/i1/d.png $TMP/i2/d.png --out-dir $TMP/j
# → changed_pct, band_pct por franjas, side_by_side.png, diff_heatmap.png
```

`compare` sirve para dos preguntas distintas:

- **¿Cambió sólo lo que quería?** `changed_pct` alto con veredicto `GLOBAL`
  después de un ajuste local significa que se movió el layout entero — casi
  siempre un token de geometría tocado por accidente.
- **¿Es determinista?** Dos `build` del mismo spec deben dar
  `changed_pct: 0.0` y veredicto `IDENTICAL`. Si no, hay algo no determinista
  (un `set` sin ordenar, un dict recorrido por inserción) y hay que arreglarlo
  antes de seguir.

Iterar sobre PNG hasta que: `score` = PASS, `build` = 0 ERROR, y la imagen se
vea bien a ojo. Sólo entonces copiar el `.drawio` y el `.svg` al repo.

**Lo que el juez no es:** el PNG sale del SVG propio, no del motor de draw.io.
Layout, colores y textos son la misma geometría, pero la tipografía la pone
MuPDF. Sirve para juzgar composición, no es una captura de draw.io. Para eso,
abrir el `.drawio`.

### 6. Publicar

```bash
python3 $S/forge.py build spec.yaml --out-dir docs/arquitectura --strict
```

Al repo van **spec + .drawio + .svg**. El `.metrics.json` es de trabajo: útil en
el PR como evidencia, innecesario después. Los `.png` de iteración se quedan en
el `$TMP` y se tiran.

## Estilo visual

No se improvisa: [references/estilo-visual.md](references/estilo-visual.md)
tiene la paleta con contraste WCAG calculado, la geometría y el porqué de cada
decisión. Lo que importa recordar:

- Seis temas de dominio (`blue`, `green`, `orange`, `purple`, `teal`, `red`,
  `neutral`), cada uno con barra sólida + texto blanco + cuerpo tintado.
- Todo el ruteo es ortogonal. Sin diagonales, sin líneas sin destino.
- Un nodo `pending` va con borde discontinuo e insignia "PENDIENTE DE
  PROVISIÓN". **No se dibuja como real algo que no existe** — la honestidad del
  diagrama es la razón por la que alguien lo va a creer la próxima vez.

## Buenas prácticas de modelado ER

La versión practicable, con el código de validador que corresponde a cada regla,
está en [references/er-buenas-practicas.md](references/er-buenas-practicas.md).
En una línea: PK explícita en cada tabla, FK con destino verificado y del mismo
tipo, cardinalidad declarada, y una nota de grano en las tablas de hechos. Nada
más. No hace falta normalizar hasta 5FN un diagrama que existe para que alguien
entienda el modelo.

## Qué NO hacer

- **No editar el `.svg`.** Es salida. El siguiente `build` lo sobreescribe.
- **No inventar un componente ni una FK para que el diagrama quede simétrico.**
  Un hueco visible es información; un hueco rellenado es una mentira.
- **No usar `stroke-dasharray` ni `marker-end` en el SVG.** MuPDF los ignora
  (verificado 2026-08-19): los guiones se emiten segmentados y las puntas como
  polígonos. Ver [references/drawio-verificado.md](references/drawio-verificado.md).
- **No meter coordenadas en el spec.** La geometría la calcula el generador; un
  spec con `x`/`y` deja de ser regenerable.
- **No dejar los PNG de iteración en el repo.** Van al `$TMP`.
- **No publicar con `ERROR`.** Ni con `--strict` desactivado "porque es sólo un
  warning de texto recortado": un tipo de dato cortado a la mitad es un tipo de
  dato que alguien va a leer mal.

## Render pictórico (opcional, no autoritativo)

Para portada de un documento o un deck se puede generar una versión pictórica
con Azure OpenAI gpt-image. **Nunca sustituye al `.drawio`/`.svg`.** El patrón verificado:

- `api-version=2025-04-01-preview` para `/images/edits`; `2024-02-01` para
  `/images/generations` (confirmado vigente en agosto 2026).
- El prompt se construye **enumerando literalmente** cada sección y cada nodo
  del spec, más una lista explícita de servicios prohibidos. Con un prompt
  genérico el modelo inventó Front Door, Cosmos DB, Redis y Sentinel — ninguno
  existía en ese sistema.
- Se manda el SVG rasterizado como imagen de referencia (modo `edits`), para que
  reestilice contenido ya fijado en píxeles en vez de componerlo de cero.
- **Revisión a ojo obligatoria** contra el SVG. Si aparece un servicio que no
  está en el spec, se descarta el render. No hay forma de garantizar fidelidad
  por construcción con un modelo de imagen.

## Quién la usa

Cárgala en el frontmatter `skills:` solo de los agentes que son dueños de un
diagrama (arquitectura de datos, DBA, ingeniería de datos, documentación, plataforma,
tech lead). Si dos agentes dibujan lo mismo, el diagrama tiene dos dueños y ninguno lo
actualiza. Los agentes read-only (`disallowedTools: Write`) escriben el spec con un
heredoc de Bash en un directorio temporal y entregan los artefactos sin aterrizarlos.

## Referencias

| Archivo | Contenido |
|---|---|
| [references/spec.md](references/spec.md) | contrato completo del spec, campo por campo, los dos `kind` |
| [references/estilo-visual.md](references/estilo-visual.md) | paleta con contraste calculado, geometría, tipos de línea, iconos |
| [references/er-buenas-practicas.md](references/er-buenas-practicas.md) | checklist de modelado ER practicable, mapeado al validador |
| [references/drawio-verificado.md](references/drawio-verificado.md) | estilos mxGraph verificados contra archivos reales y trampas del rasterizador |
| `templates/er.example.yaml` | ER mínimo funcional |
| `templates/linaje.example.yaml` | linaje mínimo funcional: carriles, bloque de metadatos, columna K |
| `templates/componentes.example.yaml` | componentes mínimo funcional |
