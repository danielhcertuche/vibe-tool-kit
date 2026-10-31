# Modelado ER: lo practicable

Un ER de documentación no es un ejercicio de normalización. Existe para que
alguien que no escribió el esquema entienda el modelo y no se equivoque al
escribir un join. Todo lo que no sirva a eso es peso muerto.

Estas son las reglas que el validador exige o avisa. No hay más.

## Las cinco que sí

### 1. Toda tabla declara su PK — `ER-PK` (ERROR)

Sin PK no hay grano, y sin grano nadie sabe qué representa una fila. Es lo
primero que se pregunta quien va a consultar la tabla.

Si la tabla real **no tiene** PK, eso es el hallazgo y se reporta como tal. No
se marca una columna cualquiera como PK para que el diagrama pase la compuerta:
el diagrama diría algo falso y el problema de la base seguiría escondido.

PK compuesta: se marcan las dos columnas.

```yaml
- {name: CodigoMaterial, type: "varchar(20)", key: "PK,FK", ref: "Material.CodigoSap"}
- {name: CodigoCentro,   type: "varchar(5)",  key: "PK,FK", ref: "Centro.CodigoCentro"}
```

### 2. Toda FK apunta a un destino que existe y es PK — `ER-REF`, `ER-REF-COL` (ERROR) / `ER-REF-NOTPK` (WARN)

`ref: "Tabla.Columna"` es lo que **genera la relación**. Una FK sin `ref` no
dibuja nada: el diagrama parece completo y no dice a dónde va esa columna
(`ER-FK-NOREF`).

Apuntar a algo que no es PK ni único es un aviso, no un error: pasa de verdad
en esquemas legados. Pero hay que saberlo, porque un join contra una columna no
única multiplica filas.

### 3. Los tipos coinciden a los dos lados — `ER-TYPE` (WARN)

`varchar(20)` contra `varchar(30)` funciona hasta que trunca. En SQL Server, un
join entre `varchar` y `nvarchar` puede además tirar el índice y convertir una
consulta de milisegundos en un scan.

### 4. Cardinalidad declarada cuando no es N:1

`N:1` es el default y cubre casi todas las FK. Se declara explícitamente cuando
no lo es:

```yaml
relations:
  - {from: "A.id", to: "B.id", card: "1:1"}    # extensión, no detalle
  - {from: "A.x",  to: "B.y",  card: "N:N"}    # falta la tabla puente: ¿está modelada?
```

Un `N:N` en un ER físico casi siempre significa que hay una tabla puente que no
se dibujó. Vale la pena mirarlo antes de dejarlo así.

### 5. El grano va escrito, en la nota de la tabla

El campo que más rinde de todo el spec:

```yaml
- name: PrecioMaterialCentro
  note: "1 fila = 1 material × 1 centro × 1 vigencia"
```

Una línea que ahorra la pregunta que siempre llega. Se pone en las tablas de
hechos y en cualquiera cuyo grano no sea obvio por el nombre.

## Las que se avisan y se deciden

### Tabla sin relaciones — `ER-ORPHAN` (WARN)

Una tabla suelta en un ER es una de tres cosas: un catálogo legítimo que nadie
referencia por FK, una FK que falta declarar, o una tabla que no pertenece a
este diagrama. Las tres importan; ninguna se resuelve sola.

Cuando es legítima, se silencia explícitamente y queda constancia de la decisión:

```yaml
allow_orphan: [Tarifas, BaseDeCostos]
```

### Nomenclatura — `ER-NAMING` (WARN)

Sólo si el repo tiene una convención escrita. Se declara y el validador avisa:

```yaml
naming_pattern: "^(dim|fct|tbl)_[a-z0-9_]+$"
```

Sin convención escrita, no se inventa una en el diagrama.

## Lo que deliberadamente NO se pide

- **Normalización formal (3FN, BCNF, 5FN).** Un ER de documentación describe el
  esquema que existe. Si hay que rediseñarlo, eso es un ADR, no un diagrama.
- **Todos los índices y constraints.** Ruido: nadie lee un ER para saber los
  índices, y quien los necesita va al DDL.
- **Notación Chen ni UML estricto.** Cabecera de color, columna de llave y pata
  de gallo se leen sin leyenda. Barroquismo notacional obliga a explicar el
  diagrama antes de usarlo.
- **Todas las columnas de todas las tablas, siempre.** En el diagrama de visión
  general, `focus: keys` o `columns_limit: 12`. Las 90 columnas van en el ER de
  detalle de ese dominio, no en el mapa general.

## Cómo se ve cada llave

| `key` | En el diagrama |
|---|---|
| `PK` | `PK` en la columna de llave + nombre **subrayado** |
| `FK` | `FK` + nombre en *cursiva* + `→ Tabla.Columna` en el color del dominio |
| `PK,FK` | las dos cosas: subrayado y cursiva (típico de tabla puente) |
| `U` | `U`, único no primario — destino válido de FK |
| vacío | columna de atributo |

Las relaciones se anclan a la **fila** de la columna, no al borde de la caja.
Esa es la diferencia entre un ER que se puede leer —se ve de qué columna sale y
a qué columna llega— y una maraña de líneas entre rectángulos. `forge.py inspect`
lo mide: `Relaciones: 16 (ancladas a columna: 16)`.
