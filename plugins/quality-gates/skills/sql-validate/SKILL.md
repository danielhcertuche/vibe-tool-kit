---
name: sql-validate
description: Valida cualquier archivo .sql antes de entregarlo — parseo con sqlfluff más un chequeo de errores semánticos de T-SQL que el parser acepta pero SQL Server rechaza. Usar SIEMPRE al generar o modificar SQL destinado a ejecutarse a mano (SSMS, azure-cli, psql) o en producción, y especialmente cuando no hay forma de probarlo contra el motor. Cubre T-SQL, PostgreSQL, MySQL, Snowflake, BigQuery, Databricks y más.
---

# Validar SQL antes de entregarlo

SQL que no se puede ejecutar antes de entregar hay que validarlo igual. Un
error de sintaxis aborta el lote entero, y quien lo corre pierde una ventana de
VPN o de mantenimiento por algo que se detecta en dos segundos.

## Cuándo

Siempre que se escriba o modifique un `.sql` que alguien vaya a ejecutar. Sobre
todo si:

- Va a correrse a mano en SSMS, Azure Data Studio o similar.
- Toca producción, QAS o cualquier ambiente compartido.
- No hay conexión al motor para probarlo.

## Las dos capas

Ninguna sustituye a la otra.

| Capa | Qué atrapa | Qué NO atrapa |
|---|---|---|
| `sqlfluff parse` | Gramática: bloques sin cerrar, cláusulas mal puestas, paréntesis | Todo lo semántico |
| `tsql_gotchas.py` | Reglas que el motor rechaza aunque parseen | Errores de lógica de negocio |

El caso que motivó esto: `RAISERROR('...', 16, 1, DB_NAME())` **parsea sin
problema** y SQL Server responde `Incorrect syntax near 'DB_NAME'`, porque los
argumentos de sustitución tienen que ser variables o literales. Solo la segunda
capa lo ve.

## Cómo correrlo

```bash
# 1. Gramática
sqlfluff parse --dialect tsql archivo.sql > /dev/null && echo "PARSE OK"

# 2. Semántica
python3 ~/.claude/skills/sql-validate/scripts/tsql_gotchas.py archivo.sql
```

Ambas deben pasar antes de entregar. `tsql_gotchas.py` sale con código 1 si hay
algún hallazgo de severidad ERROR.

Dialectos de `sqlfluff`: `tsql`, `postgres`, `mysql`, `snowflake`, `bigquery`,
`sparksql`, `databricks`, `oracle`, `duckdb`, `sqlite`, `ansi`. Elegir el que
corresponde; `ansi` da falsos negativos con sintaxis específica del motor.

## Reglas de `tsql_gotchas.py`

**ERROR** — el motor lo rechaza o el resultado es incorrecto:

| Regla | Problema |
|---|---|
| `raiserror-arg-funcion` | `RAISERROR(..., DB_NAME())`: los argumentos deben ser variable o literal |
| `rowcount-tras-declare` | `DECLARE @n int = @@ROWCOUNT` puede leer 0; usar `SET` tras el DML |
| `error-tras-declare` | Igual con `@@ERROR` |
| `throw-sin-punto-y-coma` | La instrucción previa a `THROW` debe cerrar con `;` |
| `update-sin-where` | `UPDATE` que abarca la tabla completa |
| `delete-sin-where` | `DELETE` que abarca la tabla completa |
| `tran-sin-commit` / `tran-sin-rollback` | Transacción sin camino de cierre |

**AVISO** — funciona, pero suele ser un defecto:

| Regla | Problema |
|---|---|
| `like-guion-bajo` | En `LIKE`, `_` es comodín; usar `CHARINDEX` o `ESCAPE` |
| `not-in-subconsulta` | `NOT IN` con NULL no devuelve filas; usar `NOT EXISTS` |
| `top-sin-order` | `TOP` sin `ORDER BY` no es determinístico |
| `isnumeric` | Acepta `'1e5'`, `'$1'`; usar `TRY_CAST` |
| `nolock` | Lecturas sucias, filas duplicadas o ausentes |
| `drop-objeto-real` / `truncate` | Destructivo sobre objeto no temporal |
| `tran-sin-xact-abort` | Falta `SET XACT_ABORT ON` |

Las tablas temporales (`#`) y variables (`@`) quedan fuera de las reglas
destructivas: ahí no hay dato de negocio.

## Además del validador

Lo que ninguna herramienta revisa y hay que mirar a mano:

- **Nombres reales de tablas y columnas.** No asumirlos. Consultar
  `sys.columns` primero y guardar el esquema; un `Invalid column name` cuesta
  una ronda completa.
- **Los JOIN.** Que la llave de cruce exista en ambas tablas. Que una tabla
  hija cuelgue por el campo correcto y no por uno homónimo.
- **Filtros de alcance.** Una llave que se repite entre versiones o
  cotizaciones trae histórico si no se filtra.
- **SQL dinámico.** Si se puede escribir estático, escribirlo estático. Las
  comillas anidadas de `sp_executesql` son una fuente constante de errores y
  no se ven al leer.

## Scripts que escriben

Cuando el SQL modifica datos, además:

1. Guarda por ambiente (`IF DB_NAME() NOT LIKE '%QAS%' ... RETURN`).
2. Bandera `@APLICAR bit = 0` que simula y hace `ROLLBACK`; solo escribe al
   ponerla en 1.
3. Transacción con `TRY/CATCH` y `SET XACT_ABORT ON`.
4. Respaldo de los valores previos en una tabla antes del `UPDATE`.
5. Verificación posterior que aborte si el número de filas afectadas no es el
   planificado.
6. Script de reversión.

## Si se tocan las reglas

`scripts/tsql_gotchas.py` tiene regresión. Correrla después de cualquier cambio:

```bash
~/.claude/skills/sql-validate/tests/correr_tests.sh
```

`casos_malos.sql` debe disparar 11 hallazgos y `casos_buenos.sql` ninguno. Una
regex mal escrita puede tumbar el script entero y hacer que *todo* se reporte
como sospechoso, o peor, que nada se reporte; la regresión lo detecta enseguida.

Cuando aparezca un error nuevo de T-SQL en producción, agregarlo como regla y
como caso de prueba, en vez de solo corregir el archivo afectado.

## Instalación

`sqlfluff` está instalado con pipx. Si falta:

```bash
pipx install sqlfluff
```
