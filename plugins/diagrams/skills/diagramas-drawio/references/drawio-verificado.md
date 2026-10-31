# draw.io y rasterizado: lo verificado

Todo lo de aquí está comprobado contra archivos reales de `app.diagrams.net` en
esta máquina o ejecutando el rasterizador. Donde una suposición razonable
resultó falsa, se dice.

## 1. Tabla ER nativa

Ground truth: un diagrama hecho a mano en app.diagrams.net (no incluido)
(hecho a mano en app.diagrams.net con Chrome). Tres niveles anidados:

```
mxCell  shape=table;childLayout=tableLayout;startSize=<alto cabecera>   ← la tabla
 └─ mxCell  shape=tableRow;points=[[0,0.5],[1,0.5]];portConstraint=eastwest   ← una fila
     ├─ mxCell  shape=partialRectangle;connectable=0   (x=0,  w=38)   ← celda de llave
     └─ mxCell  shape=partialRectangle;connectable=0   (x=38, w=258)  ← celda de columna
```

Lo que hace que esto valga la pena en vez de una caja de texto:

- **La fila es un puerto de conexión.** `points=[[0,0.5],[1,0.5]]` con
  `portConstraint=eastwest` permite anclar una arista a la columna. Es lo que
  convierte "líneas entre rectángulos" en "esta columna referencia a esa".
- **Cada celda es editable in situ.** Doble clic y se cambia el tipo de dato o se
  marca PK/FK, sin tocar el spec.
- **`resizeLast=1`** deja que la última columna absorba el cambio al ensanchar la
  tabla, en vez de repartirlo.

Detalles que no se pueden omitir:

- Las celdas necesitan `<mxRectangle as="alternateBounds">` con el mismo ancho y
  alto de su `mxGeometry`. Sin eso el layout de tabla se descoloca al editar.
- La geometría de los hijos es **relativa al padre**. La fila lleva sólo `y`
  (offset dentro de la tabla); la celda sólo `x` (offset dentro de la fila).
- `startSize` de la tabla = alto de la cabecera. Debe coincidir con el `y` de la
  primera fila, o la primera fila se solapa con el título.

## 2. Aristas ER

```
edgeStyle=entityRelationEdgeStyle;startArrow=ERmany;endArrow=ERone;startFill=0;endFill=0;
```

`entityRelationEdgeStyle` **autorutea**: sale horizontal del costado y hace el
codo solo. Por eso las aristas ER se emiten **sin waypoints** — así el usuario
arrastra una tabla y la relación se reacomoda. Fijar waypoints daría un archivo
que se ve idéntico y se rompe en cuanto alguien mueve algo.

Puntas por cardinalidad:

| `card` | startArrow | endArrow |
|---|---|---|
| `N:1` | `ERmany` | `ERone` |
| `1:N` | `ERone` | `ERmany` |
| `1:1` | `ERone` | `ERone` |
| `N:N` | `ERmany` | `ERmany` |
| `0..1` | `ERmany` | `ERzeroToOne` |

## 3. Contenedores con hijos

Ground truth: un diagrama hecho a mano en app.diagrams.net (no incluido).

```
mxCell  swimlane;startSize=34;...          ← sección, parent="1"
 └─ mxCell  rounded=1;...   parent=<idSección>, geometría RELATIVA   ← nodo
```

Mover el contenedor mueve sus hijos: es lo que se quiere de un diagrama de
componentes. Las aristas **entre secciones distintas** van con `parent="1"`
(el ancestro común) y `source`/`target` por id; draw.io resuelve el ruteo. Las
aristas internas a una sección llevan `parent=<idSección>`.

## 4. El escape del atributo `value` — la trampa que rompe el archivo

El `value` de una `mxCell` contiene HTML, y ese HTML va **escapado como XML**:

```xml
value="&lt;b&gt;Usuarios&lt;/b&gt;&lt;div style=&quot;font-size:10px&quot;&gt;…&lt;/div&gt;"
```

El error fácil —y el que efectivamente se cometió al escribir el generador— es
escapar el *texto interior* y dejar crudas las etiquetas HTML que lo envuelven.
El resultado: la comilla de `style="…"` cierra el atributo XML y el archivo deja
de ser XML bien formado. draw.io no lo abre.

Regla: los constructores devuelven **HTML crudo con texto crudo**, y el escape
ocurre **una sola vez**, al escribir el atributo. Lo verifica `XML-PARSE` en cada
`build` — que es exactamente cómo se encontró el fallo.

## 5. Por qué existe la compuerta `XML-*`

Aquí no hay motor de draw.io (ni Electron, ni headless Chrome), así que no se
puede abrir el archivo para comprobar que abre. La alternativa honesta es
verificar las invariantes que draw.io exige:

| Chequeo | Por qué |
|---|---|
| `XML-PARSE` | XML bien formado |
| `XML-PARENT` | Un `parent` colgando **no da error**: draw.io simplemente no dibuja ese elemento. Fallo silencioso |
| `XML-ROW` / `XML-CELL` | Fila fuera de una tabla, o celda fuera de una fila: el `tableLayout` no aplica y la tabla sale deformada |
| `XML-EDGE` | `source`/`target` inexistente: la arista desaparece |
| `XML-GEO` | Vértice sin `mxGeometry`: se dibuja en 0,0 |
| `XML-DUP` | Ids duplicados: draw.io se queda con uno |

Instalar un exportador de draw.io por npm es posible (arrastra Electron) y sería
el chequeo definitivo. No se hizo: las invariantes cubren los fallos reales y no
añaden 300MB de dependencia a un generador de 1500 líneas.

## 6. Rasterizado: lo que MuPDF ignora

Verificado el 2026-08-19 con PyMuPDF renderizando SVG a PNG:

| Se ignora | Consecuencia | Solución aplicada |
|---|---|---|
| `stroke-dasharray` (atributo **y** dentro de `style`) | toda línea discontinua sale continua: `integration`, `telemetry`, `pipeline` y `soft` se vuelven indistinguibles | los guiones se emiten como **segmentos explícitos** |
| `marker-end` / `marker-start` | ninguna flecha tiene punta | las puntas se dibujan como **polígonos**; la pata de gallo y la barra "uno", como trazos |

Lo que sí funciona bien: `rect` con `rx`, `path` con arcos, `text` con
`font-family` / `font-weight` / `font-style` / `text-decoration` / `text-anchor`,
`transform` con `translate` y `scale`, `opacity`.

Efecto secundario deseable: un SVG con geometría explícita en vez de atributos de
presentación se ve igual en el navegador, en Word, en Confluence y en cualquier
rasterizador parcial. La portabilidad salió de tener que rodear una limitación.

## 7. Orden de pintado del SVG

1. Contenedores (fondo).
2. Trazos de arista.
3. Tablas, nodos, notas, leyenda.
4. **Etiquetas de arista.**

Las etiquetas van al final a propósito. Con el trazo, las cajas que se pintan
después las tapan a medias y se leen cosas como `T +` donde debía decir
`id + access token`.
