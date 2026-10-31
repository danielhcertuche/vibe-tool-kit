#!/usr/bin/env bash
# run-gate.sh — Code quality gate orchestrator
# Usage: ./run-gate.sh [path] [--lang=python,sql,ts,notebook,terraform]
# Outputs aggregated JSON to stdout; human summary to stderr.
# Exit 0 = all pass/skip; Exit 1 = one or more checks failed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKS_DIR="$SCRIPT_DIR/checks"
SCAN_PATH="${1:-.}"
LANG_FILTER=""

# Parse --lang= flag
for arg in "$@"; do
  case "$arg" in
    --lang=*) LANG_FILTER="${arg#--lang=}" ;;
  esac
done

# JSON aggregation helper — use jq if available, else Python
aggregate_json() {
  if command -v jq &>/dev/null; then
    echo "$1" | jq -s '{
      gate: "code-quality-gate",
      status: (if any(.[]; .status == "fail") then "fail" else "pass" end),
      checks: .,
      timestamp: now | todate
    }'
  else
    python3 - "$1" <<'PYEOF'
import sys, json
from datetime import datetime, timezone

raw = sys.argv[1]
checks = json.loads(raw)
status = "fail" if any(c.get("status") == "fail" for c in checks) else "pass"
result = {
    "gate": "code-quality-gate",
    "status": status,
    "checks": checks,
    "timestamp": datetime.now(timezone.utc).isoformat()
}
print(json.dumps(result, indent=2))
PYEOF
  fi
}

# Detect which languages exist under SCAN_PATH
has_lang() {
  local ext="$1"
  find "$SCAN_PATH" -name "*.$ext" -not -path "*/node_modules/*" -not -path "*/.venv/*" \
    -not -path "*/__pycache__/*" -not -path "*/.git/*" 2>/dev/null | grep -q .
}

should_run() {
  local lang="$1"
  if [ -n "$LANG_FILTER" ]; then
    echo "$LANG_FILTER" | tr ',' '\n' | grep -qx "$lang"
  else
    return 0
  fi
}

echo "[gate] Scanning: $SCAN_PATH" >&2

RESULTS=()
OVERALL_EXIT=0

run_check() {
  local lang="$1"
  local script="$CHECKS_DIR/${lang}.sh"

  if [ ! -f "$script" ]; then
    echo "[gate] No check script for language: $lang" >&2
    return
  fi

  echo "[gate] Running $lang check..." >&2
  local output
  if output=$(bash "$script" "$SCAN_PATH" 2>/dev/null); then
    echo "[gate] $lang: PASS" >&2
  else
    OVERALL_EXIT=1
    echo "[gate] $lang: FAIL" >&2
  fi
  RESULTS+=("$output")
}

# Auto-detect and run relevant checks
if should_run "python" && has_lang "py"; then
  run_check "python"
fi

if should_run "sql" && has_lang "sql"; then
  run_check "sql"
fi

if should_run "ts" && (has_lang "ts" || has_lang "tsx"); then
  run_check "ts"
fi

if should_run "notebook" && has_lang "ipynb"; then
  run_check "notebook"
fi

if should_run "terraform" && has_lang "tf"; then
  run_check "terraform"
fi

# If no languages detected, emit a no-op result
if [ ${#RESULTS[@]} -eq 0 ]; then
  echo '{"gate":"code-quality-gate","status":"pass","checks":[],"timestamp":"'$(date -u +%FT%TZ)'"}'
  exit 0
fi

# Build JSON array from results
JSON_ARRAY="["
for i in "${!RESULTS[@]}"; do
  if [ $i -gt 0 ]; then JSON_ARRAY+=","; fi
  JSON_ARRAY+="${RESULTS[$i]}"
done
JSON_ARRAY+="]"

aggregate_json "$JSON_ARRAY"
exit $OVERALL_EXIT
