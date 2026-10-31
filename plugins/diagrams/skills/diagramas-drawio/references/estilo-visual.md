# Estándar visual

Fuente de verdad ejecutable: `scripts/forge.py` (diccionarios `THEMES`, `LINES`,
`G`, `FS`, `ICONS`). Este documento explica el porqué y deja los números
verificados por escrito; si se toca un hex hay que recalcular la tabla de
contraste, no suponer que sigue pasando.

## 1. Paleta por dominio

Cada tema tiene **tres** roles, no dos:

- `header` — barra sólida con texto **blanco** encima.
- `fill` — fondo tintado del cuerpo, con texto gris oscuro encima.
- `title` — texto de acento sobre `fill` (la columna de llave del ER, el destino
  de una FK).

`header` es más oscuro que el tono claro que uno elegiría por instinto: la
versión clara no alcanza 4.5:1 con blanco encima. Ratios calculados con la
fórmula WCAG 2.x de luminancia relativa (no estimados):

| tema | header | header/blanco | fill | `#4b5563`/fill | title | title/fill |
|---|---|---:|---|---:|---|---:|
| `blue` | `#1e6fd9` | **4.85:1** | `#f5f9ff` | 7.15:1 | `#0b3f8f` | 9.37:1 |
| `green` | `#158132` | **4.98:1** | `#f4fdf6` | 7.28:1 | `#0c6b26` | 6.43:1 |
| `orange` | `#aa5c00` | **4.95:1** | `#fffaf3` | 7.28:1 | `#a85a00` | 4.90:1 |
| `purple` | `#7b3fbf` | **6.35:1** | `#faf6ff` | 7.09:1 | `#53257f` | 10.16:1 |
| `teal` | `#0c7e7e` | **4.88:1** | `#f2fdfd` | 7.29:1 | `#0a5f5f` | 7.19:1 |
| `red` | `#b3261e` | **6.54:1** | `#fff6f5` | 7.11:1 | `#8c1d18` | 8.57:1 |
| `neutral` | `#6e7279` | **4.83:1** | `#fbfbfc` | 7.31:1 | `#2b2f36` | 13.00:1 |

Umbral: **≥ 4.5:1** para texto normal (WCAG AA). Los siete lo cumplen. Los
márgenes más ajustados son `neutral` (4.83) y `blue` (4.85) — oscurecer
cualquiera de los dos obliga a recalcular. `A11Y-CONTRAST` lo verifica en cada
`build`, así que un cambio que rompa el umbral falla antes de publicarse.

Otros pares del mismo lienzo:

| Par | Contraste |
|---|---:|
| Texto principal `#111827` / blanco | 17.74:1 |
| Texto secundario `#4b5563` / blanco | 7.56:1 |
| Línea de separación de filas `#dde3ea` / blanco | 1.29:1 (decorativa, no lleva texto) |

**Rotación de temas.** Sin `theme` explícito, los grupos y secciones rotan en el
orden `blue → green → orange → purple → teal → red → neutral`. Es estable: el
mismo spec siempre da los mismos colores. Poner `theme` explícito sólo cuando el
color signifique algo (rojo = deuda, gris = externo).

## 2. Tipos de línea

| Tipo | Color | Contraste/blanco | Patrón | Cuándo |
|---|---|---:|---|---|
| `fk` | `#4a5568` | 7.53:1 | continuo | Relación con FK declarada en la base |
| `soft` | `#6b7688` | 4.59:1 | `5 4` | Relación lógica sin FK física (join por convención) |
| `request` | `#1f2937` | 14.68:1 | continuo | Solicitud / paso de datos sin autenticación en el propio conector |
| `secure` | `#0c7a2c` | 5.47:1 | continuo | Conexión autenticada sobre HTTPS |
| `integration` | `#1e6fd9` | 4.85:1 | `6 4` | Llamada a un servicio externo al proceso |
| `telemetry` | `#7b3fbf` | 6.35:1 | `3 4` | Métricas, logs, trazas |
| `pipeline` | `#aa5c00` | 4.95:1 | `8 4` | CI, build, despliegue |

El color de la línea **también rotula su etiqueta**, así que todos pasan el
umbral de texto (4.5:1), no el de objeto gráfico (3:1). `soft` era `#8b95a5`
(3.03:1) y se oscureció por eso; `A11Y-EDGE-LABEL` lo verifica en cada `build`.

Reglas de trazo, sin excepción:

- Sólo ortogonal. Ninguna diagonal.
- Ninguna línea sin destino explícito.
- Los tramos entre bandas viajan por el **corredor** reservado bajo la banda
  superior, repartidos en carriles para que dos trazos no compartan altura.
- Un tramo recto entre dos tarjetas de la misma banda sólo se usa si no
  atraviesa una tarjeta intermedia; si la atraviesa, baja al corredor. Ahorra
  dos defectos a la vez: el cruce y la etiqueta escrita encima del nombre de esa
  tarjeta.

## 3. Geometría

Todo múltiplo de 2 para caer limpio en la grilla de 10 de draw.io.

| Token | px | Nota |
|---|---:|---|
| `margin` | 40 | Aire real en los cuatro bordes |
| `tbl_w` | 336 | Ancho de tabla ER: tres columnas sin apretar |
| `tbl_type_w` | 104 | Columna del **tipo**, a la izquierda |
| `tbl_key_w` | 46 | Badge de llave (`PK`/`FK`/`UK`), a la **derecha** |
| `tbl_head_h` | 38 | Cabecera: nombre + esquema |
| `tbl_row_h` | 24 | Fila de columna |
| `tbl_gap_x` | 156 | Hueco entre columnas de tablas — **aquí van los codos Y el chip de la FK** |
| `tbl_gap_y` | 40 | Hueco vertical entre tablas apiladas |
| `grp_head_h` | 34 | Barra de título de grupo/sección |
| `grp_gap_y` | 56 | Corredor entre bandas |
| `node_w` | 208 | Ancho de referencia de tarjeta |
| `lane_h` / `lanes` | 20 / 6 | Carriles dentro de un corredor |

## Anatomía de la fila ER

Tres columnas, en este orden: **tipo · nombre · badge de llave**.

```
┌──────────────┬───────────────────────────┬──────┐
│ varchar(20)  │ CodigoMaterial            │ PK,FK│
└──────────────┴───────────────────────────┴──────┘
```

Tres decisiones que vale la pena no deshacer:

- **El tipo va a la izquierda, en gris y un punto más pequeño.** Se escanea en
  vertical cuando hace falta y no estorba cuando no.
- **El destino de la FK NO va dentro de la fila.** Va como **chip** sobre la
  línea de la relación, con el nombre de la columna. Es donde el lector lo busca
  cuando sigue un trazo, y evita que cada fila FK cargue un texto que repite lo
  que la línea ya dice. Por eso `tbl_gap_x` es 156 y no 72: con el corredor
  estrecho el chip no cabía y terminaba encima de la tabla vecina.
- **Filas alternas con fondo `#f7f8fb`.** Separa la vista sin meter otra línea.
  En una tabla de 15 columnas, las rayas hacen más por la lectura que cualquier
  borde.

La decoración del nombre dice el papel sin gastar otra columna: **PK subrayado**,
*FK en cursiva*.

### Puntas de relación

Notación ER en los dos extremos, nunca mezclada con flechas de dirección:

| Cardinalidad | Origen | Destino |
|---|---|---|
| `N:1` | pata de gallo | barra doble (uno y sólo uno) |
| `1:N` | barra doble | pata de gallo |
| `1:1` | barra doble | barra doble |
| `N:N` | pata de gallo | pata de gallo |
| `0..1` | pata de gallo | círculo + barra (cero o uno) |

Se abandonó la punta sólida de dirección: con el chip de la columna FK sobre la
línea el sentido ya se lee, y sostener dos códigos a la vez —flecha y notación
ER— es trabajo que se le pasa al lector sin necesidad.

**Altura de contenedor: al contenido propio, no a la banda.** Si todas las
secciones de una fila se estiraran a la más alta, la corta queda con la mitad
inferior vacía y los conectores que bajan justo después de su contenido real
atraviesan esa zona vacía como si perforaran la caja.

**Empaquetado de tablas ER: mampostería, no grilla.** Cada tabla entra en la
columna que va más corta. Con filas de altura uniforme, una sola tabla de 90
columnas estira su banda entera: medido en el ER del Cotizador, 4296px de alto
con grilla contra 2574px con mampostería, mismo contenido.

## 4. Iconos

Glifos de **trazo**, no de relleno: se leen igual al 100% y al 25% de zoom. Cada
uno se dibuja en una caja de 20×20 centrada en el origen, escalada a 0.78 en la
tarjeta y a 0.55 en la leyenda.

No se usan librerías de stencils (`mxgraph.azure.*`, etc.): si la librería no
está disponible el nodo sale vacío y nadie se enteró. Un glifo propio siempre
dibuja.

`kind` sin glifo cae a un cuadrado genérico **y se avisa** (`ICON-MISS`), porque
el fallo alternativo —perder la lectura por icono sin decir nada— es el que no
se detecta a ojo en un diagrama de 20 nodos.

## 5. Honestidad del diagrama

Un nodo `status: pending` va con borde discontinuo e insignia "PENDIENTE DE
PROVISIÓN". Es la regla que hace que el diagrama valga algo: si lo no
provisionado se dibuja igual que lo real, el diagrama sirve una vez y después
nadie lo cree.

Lo mismo en el ER: una tabla sin PK en la fuente real se reporta como hallazgo
(`ER-PK`), no se le inventa una llave para que el diagrama quede completo. Una
FK cuyo destino no se pudo verificar se queda como TODO visible.
