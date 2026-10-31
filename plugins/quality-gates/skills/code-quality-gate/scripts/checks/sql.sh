#!/usr/bin/env bash
# checks/sql.sh — SQL quality check (sqlfluff)
# Usage: ./sql.sh <path>
# Outputs JSON to stdout; human summary to stderr.
# Exit 0 = pass/skip; Exit 1 = fail.
set -euo pipefail

SCAN_PATH="${1:-.}"
FINDINGS=()
STATUS="pass"

any_sql_files() {
  find "$SCAN_PATH" -name "*.sql" -not -path "*/.git/*" 2>/dev/null | grep -q .
}

if ! any_sql_files; then
  echo '{"check":"sql","status":"skip","findings":0,"details":["no-sql-files"]}'; exit 0
fi

if ! command -v sqlfluff &>/dev/null; then
  echo "[sql] sqlfluff not found — install: uv pip install sqlfluff" >&2
  echo '{"check":"sql","status":"skip","findings":0,"details":["tool-missing: sqlfluff (install: uv pip install sqlfluff)"]}'
  exit 0
fi

# Detect dialect — default tsql for this project (SQL Server)
DIALECT="${SQLFLUFF_DIALECT:-tsql}"

if ! output=$(sqlfluff lint "$SCAN_PATH" --dialect "$DIALECT" --format json 2>/dev/null); then
  count=$(echo "$output" | python3 -c "
import json,sys
data = json.load(sys.stdin)
total = sum(len(f.get('violations', [])) for f in data.get('files', []))
print(total)
" 2>/dev/null || echo "?")
  echo "[sql] sqlfluff: $count violation(s)" >&2
  FINDINGS+=("sqlfluff: $count violation(s)")
  STATUS="fail"
else
  echo "[sql] sqlfluff: pass" >&2
fi

DETAILS_JSON="["
for i in "${!FINDINGS[@]}"; do
  if [ $i -gt 0 ]; then DETAILS_JSON+=","; fi
  DETAILS_JSON+=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${FINDINGS[$i]}")
done
DETAILS_JSON+="]"

echo "{\"check\":\"sql\",\"status\":\"$STATUS\",\"findings\":${#FINDINGS[@]},\"details\":$DETAILS_JSON}"
[ "$STATUS" = "pass" ] && exit 0 || exit 1
