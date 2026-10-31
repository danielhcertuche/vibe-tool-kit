#!/usr/bin/env bash
# Regresion del checker: los casos malos deben disparar, los buenos no.
# Correr tras cualquier cambio en scripts/tsql_gotchas.py.
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
CHK="$AQUI/../scripts/tsql_gotchas.py"
ESPERADOS_MALOS=11
fallos=0

n=$(python3 "$CHK" "$AQUI/casos_malos.sql" 2>&1 | grep -cE "^  (ERROR|AVISO)")
if [ "$n" -eq "$ESPERADOS_MALOS" ]; then
    echo "OK   casos_malos: $n hallazgos"
else
    echo "MAL  casos_malos: $n hallazgos, esperados $ESPERADOS_MALOS"; fallos=1
fi

if python3 "$CHK" "$AQUI/casos_buenos.sql" >/dev/null 2>&1; then
    echo "OK   casos_buenos: sin hallazgos"
else
    echo "MAL  casos_buenos: hay falsos positivos"
    python3 "$CHK" "$AQUI/casos_buenos.sql" | grep -E "^  (ERROR|AVISO)"
    fallos=1
fi

[ "$fallos" -eq 0 ] && echo "TESTS OK" || echo "TESTS FALLAN"
exit "$fallos"
