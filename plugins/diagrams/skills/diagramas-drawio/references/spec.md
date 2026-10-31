# Contrato del spec

YAML o JSON. Los nombres de campo aceptan alias en español (`titulo`, `tablas`,
`columnas`, `llave`, `grupo`, `secciones`, `nodos`, `conexiones`…): usa uno de
los dos y no los mezcles dentro de un mismo archivo.

**El spec nunca lleva coordenadas.** La geometría la calcula el generador. Un
spec con `x`/`y` deja de ser regenerable, que es lo único que hace que el
diagrama siga siendo verdad el mes que viene.

---

## Raíz (común a los dos tipos)

| Campo | Tipo | Obligatorio | Uso |
|---|---|---|---|
| `kind` | `er` \| `componentes` | no | Se autodetecta: con `sections`/`nodes` es `componentes`, si no `er` |
| `title` | string | sí | Título del lienzo |
| `subtitle` | string | no | Línea bajo el título |
| `source` | `{repo, branch, commit, as_of}` | no | Se imprime en el pie. Es la trazabilidad del diagrama: de dónde salió el contenido |
| `legend` | lista `{label, type}` | no | Tipos de flujo. En ER trae un default sensato |
| `icon_legend` | lista `{icon, label}` | no | Segunda columna de la leyenda (sólo `componentes`) |

---

## `kind: er`

| Campo | Tipo | Obligatorio | Uso |
|---|---|---|---|
| `tables` | lista de tabla | sí | Las entidades |
| `groups` | lista de grupo | no | Bandas de dominio con barra de color. Sin grupos, todas las tablas van en una banda sin contenedor |
| `relations` | lista de relación | no | Relaciones **extra** a las que ya derivan las FK |
| `max_columns` | int | no (4) | Máximo de columnas de tablas por banda |
| `allow_orphan` | lista de nombres | no | Tablas para las que `ER-ORPHAN` no aplica (catálogos sueltos legítimos) |
| `naming_pattern` | regex | no | Si está, se avisa de cada tabla que no lo cumpla |

### Tabla

| Campo | Tipo | Uso |
|---|---|---|
| `name` | string | Nombre real, tal cual está en la base. Es el id de las relaciones |
| `schema` | string | Se muestra pequeño bajo el nombre, en la cabecera |
| `group` | string | `id` del grupo |
| `theme` | tema | Fuerza el color de esta tabla; por defecto hereda el del grupo |
| `note` | string | Nota amarilla al costado. **El sitio del grano**: "1 fila = 1 material por centro" |
| `columns` | lista de columna | Las filas de la tabla |
| `focus` | `keys` | Muestra sólo las columnas con llave y resume el resto en "… +N columnas" |
| `columns_limit` | int | Muestra las llaves + las primeras N sin llave, resume el resto |

`focus` y `columns_limit` son para los diagramas de visión general. En el ER de
detalle van todas las columnas.

### Columna

Forma larga:

```yaml
- {name: IdCliente, type: int, key: FK, ref: "Cliente.Id", nullable: false}
```

Forma corta `nombre:tipo:llave` (para tablas de catálogo, sin FK):

```yaml
- "CodigoCentro:varchar(5):PK"
- "DescripcionCentro:varchar(200)"
```

| Campo | Valores | Uso |
|---|---|---|
| `key` | `PK`, `FK`, `PK,FK`, `U`, vacío | Contenido de la columna de llave. Se pinta en negrita con el color del dominio |
| `ref` | `"Tabla.Columna"` | **Genera la relación.** Poner `ref` implica `FK` aunque no se declare |
| `type` | string | Tipo tal cual en la base |
| `nullable` | bool | Informativo |

Cómo se ve cada llave: `PK` subraya el nombre, `FK` lo pone en cursiva y añade
`→ Tabla.Columna` en el color del dominio, `PK,FK` hace las dos cosas.

### Relación explícita

Sólo para lo que no es una FK física — una relación lógica, un join por
convención, una FK que la base nunca declaró:

```yaml
relations:
  - {from: "TelaRuta.co_reftel", to: "Material.CodigoSap", card: "N:1", style: soft,
     label: "join por convención, sin FK en la BD"}
```

| Campo | Valores | Uso |
|---|---|---|
| `from` / `to` | `"Tabla.Columna"` | Extremos |
| `card` | `N:1` (def), `1:N`, `1:1`, `N:N`, `0..1` | Notación de las puntas |
| `style` | `fk` (línea continua), `soft` (discontinua) | `soft` es lo correcto cuando no hay FK física |
| `label` | string | Texto sobre el trazo |

---

## `kind: linaje`

| Campo | Tipo | Obligatorio | Uso |
|---|---|---|---|
| `lanes` | lista `{id, title}` | sí | Carriles verticales por capa, de izquierda a derecha en el sentido del flujo |
| `tables` | lista de tabla | sí | Las tablas, repartidas en los carriles |
| `flows` | lista de flujo | no | Flechas de flujo |
| `legend` | lista `{color, label}` | no | Chips de estado. Por defecto, canon / dup / origen |

### Tabla de linaje

| Campo | Tipo | Uso |
|---|---|---|
| `name` | string | Nombre real de la tabla; es el id de los flujos |
| `lane` | string | `id` del carril |
| `schema` | string | Se muestra pequeño bajo el nombre |
| `estado` | `canon` · `subset` · `dup` · `origen` · `destino` | **Color de la cabecera.** Dice qué es la tabla, no de qué dominio es |
| `info` | lista de string | Bloque de metadatos bajo la cabecera: volumen, ritmo y su evidencia |
| `columns` | lista de columna | Forma corta `nombre:tipo:llave`. La llave se marca `K` = **medida** |
| `columns_limit` | int | Deja las columnas con llave + las primeras N, y resume el resto |
| `note` | string | Nota amarilla al costado |

### Flujo

```yaml
flows:
  - {from: tbl_origen, to: tbl_destino, label: "ADF · …_silver_to_gold · CTAS", style: soft}
```

| Campo | Valores | Uso |
|---|---|---|
| `from` / `to` | nombre de tabla | Extremos |
| `label` | string | Quién escribe la tabla destino: job o pipeline, operación, cadencia |
| `style` | `fk` (continua) · `soft` (discontinua) | — |
| `card` | `N:1`, `1:N`, `1:1`, `N:N`, `0..1` | **Opcional y excepcional.** Sólo con perfil de duplicidad medido; sin él, el trazo es una flecha simple |

Los estados `canon`, `subset`, `dup`, `origen` y `destino` también se pueden
declarar en una tabla de `kind: er`, junto con `info:`, para darle al ER la
misma anatomía sin perder las bandas de dominio ni la pata de gallina.

---

## `kind: componentes`

| Campo | Tipo | Obligatorio | Uso |
|---|---|---|---|
| `rows` | lista `{sections: [id, …]}` | sí | Orden de bandas, de arriba a abajo; dentro de cada una, de izquierda a derecha |
| `sections` | lista de sección | sí | Contenedores de dominio |
| `nodes` | lista de nodo | sí | Componentes reales |
| `connections` | lista de conexión | no | Flechas |
| `style` | `{width}` | no | Ancho de lienzo (1740 por defecto) |

El orden de `rows` es **dependencia funcional, no cronología de despliegue**.
La fila 1 reproduce el camino de una petición (usuario → identidad → aplicación
→ datos), que es lo primero que alguien nuevo necesita leer. Lo que no está en
ese camino crítico —IA, integraciones, CI/CD, pendientes— va debajo.

Una sección con `id: legend` se renderiza como la leyenda en ese sitio, en vez
de un contenedor vacío.

### Sección

| Campo | Tipo | Uso |
|---|---|---|
| `id` | string | Referenciado desde `rows` y desde `nodes[].section` |
| `title` | string | Texto de la barra de color |
| `subtitle` | string | Línea bajo la barra, sobre el fondo tintado |
| `theme` | tema | Color de dominio; si se omite, rota en orden estable |
| `span` | número (1) | Peso del ancho dentro de su fila. Dos secciones con span 1 y 2 reparten 1:2 |
| `columns` | int | Columnas de la grilla de nodos; por defecto lo que quepa |

### Nodo

| Campo | Tipo | Uso |
|---|---|---|
| `id` | string | Referenciado desde `connections` |
| `section` | string | Sección donde vive |
| `label` | string | Nombre del componente (negrita) |
| `sublabel` | string | Detalle operativo: versión, ruta, protocolo, recuento real |
| `kind` | clave de iconos | Determina el glifo. Un `kind` sin glifo se avisa (`ICON-MISS`) |
| `status` | `real` \| `pending` | `pending` → borde discontinuo + insignia "PENDIENTE DE PROVISIÓN" |

`kind` disponibles y sus alias: ver `ICONS` en `scripts/forge.py`. Cubren web,
api, runtime, db/sql/lakehouse, mongo, identity/lock/key, users, vault, ai/llm,
graph, files/sharepoint/excel, doc/notebook, monitor, network, pipeline/ci/job,
repo, wiki, queue, storage/blob/volume, external, shield.

### Conexión

| Campo | Tipo | Uso |
|---|---|---|
| `from` / `to` | id de nodo | Extremos |
| `label` | string | Texto sobre chip blanco |
| `type` | `request`, `secure`, `integration`, `telemetry`, `pipeline` | Estilo de línea — ver estilo-visual.md |

---

## Determinismo

Mismo spec → mismos bytes. Lo que lo garantiza y no se debe romper al extender
el generador:

- Sin marcas de tiempo ni ids aleatorios: cada id sale del slug del elemento.
- Todo recorrido de conjuntos va ordenado (`sorted()`), nunca por orden de
  inserción de un `set`.
- El ancho del texto se estima con una tabla de anchos por clase de carácter,
  no con métricas de fuentes instaladas: la misma máquina y otra dan el mismo
  layout.
- El orden de tablas dentro de un grupo es `(-referencias_entrantes, nombre)`:
  reproducible y además pone los hubs a la izquierda.

Verificarlo: dos `build` seguidos y `judge.py compare` debe decir
`IDENTICAL` con `changed_pct: 0.0`.
