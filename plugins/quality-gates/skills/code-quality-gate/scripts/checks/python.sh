#!/usr/bin/env bash
# checks/python.sh — Python quality check (ruff + mypy + pytest)
# Usage: ./python.sh <path>
# Outputs JSON to stdout; human summary to stderr.
# Exit 0 = pass/skip; Exit 1 = fail.
set -euo pipefail

SCAN_PATH="${1:-.}"
FINDINGS=()
STATUS="pass"

emit() {
  local check_status="${1:-pass}"
  local findings_json="["
  for i in "${!FINDINGS[@]}"; do
    if [ $i -gt 0 ]; then findings_json+=","; fi
    findings_json+="$(echo "${FINDINGS[$i]}" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))")"
  done
  findings_json+="]"
  echo "{\"check\":\"python\",\"status\":\"$check_status\",\"findings\":${#FINDINGS[@]},\"details\":$findings_json}"
}

# Locate tool: prefer .venv, then PATH
find_tool() {
  local name="$1"
  local venv_path="$SCAN_PATH/.venv/bin/$name"
  if [ -x "$venv_path" ]; then echo "$venv_path"; return; fi
  venv_path="$(pwd)/.venv/bin/$name"
  if [ -x "$venv_path" ]; then echo "$venv_path"; return; fi
  if command -v "$name" &>/dev/null; then echo "$name"; return; fi
  echo ""
}

any_py_files() {
  find "$SCAN_PATH" -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" \
    -not -path "*/.git/*" 2>/dev/null | grep -q .
}

if ! any_py_files; then
  echo '{"check":"python","status":"skip","findings":0,"details":["no-py-files"]}'; exit 0
fi

# --- ruff check ---
RUFF=$(find_tool "ruff")
if [ -z "$RUFF" ]; then
  echo "[python] ruff not found — install: uv pip install ruff" >&2
  FINDINGS+=("tool-missing: ruff (install: uv pip install ruff)")
else
  if ! output=$("$RUFF" check "$SCAN_PATH" --output-format=json 2>/dev/null); then
    count=$(echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "?")
    echo "[python] ruff check: $count issue(s)" >&2
    FINDINGS+=("ruff-check: $count violation(s)")
    STATUS="fail"
  else
    echo "[python] ruff check: pass" >&2
  fi

  if ! "$RUFF" format --check "$SCAN_PATH" &>/dev/null; then
    echo "[python] ruff format: needs formatting" >&2
    FINDINGS+=("ruff-format: files not formatted")
    STATUS="fail"
  else
    echo "[python] ruff format: pass" >&2
  fi
fi

# --- mypy ---
MYPY=$(find_tool "mypy")
if [ -z "$MYPY" ]; then
  echo "[python] mypy not found — install: uv pip install mypy" >&2
  FINDINGS+=("tool-missing: mypy (install: uv pip install mypy)")
else
  if ! mypy_out=$("$MYPY" "$SCAN_PATH" --ignore-missing-imports --no-error-summary 2>&1); then
    errors=$(echo "$mypy_out" | grep -c "error:" || true)
    echo "[python] mypy: $errors error(s)" >&2
    FINDINGS+=("mypy: $errors type error(s)")
    STATUS="fail"
  else
    echo "[python] mypy: pass" >&2
  fi
fi

# --- pytest (if test files exist) ---
PYTEST=$(find_tool "pytest")
test_files=$(find "$SCAN_PATH" -name "test_*.py" -o -name "*_test.py" 2>/dev/null | head -1)
if [ -n "$test_files" ]; then
  if [ -z "$PYTEST" ]; then
    echo "[python] pytest not found — install: uv pip install pytest" >&2
    FINDINGS+=("tool-missing: pytest (install: uv pip install pytest)")
  else
    if ! "$PYTEST" "$SCAN_PATH" -q --tb=no 2>/dev/null; then
      echo "[python] pytest: failures" >&2
      FINDINGS+=("pytest: test failures")
      STATUS="fail"
    else
      echo "[python] pytest: pass" >&2
    fi
  fi
fi

emit "$STATUS"
[ "$STATUS" = "pass" ] && exit 0 || exit 1
