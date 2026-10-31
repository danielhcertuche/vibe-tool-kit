#!/usr/bin/env bash
# checks/notebook.sh — Jupyter notebook quality check (nbqa ruff + output check)
# Usage: ./notebook.sh <path>
# Outputs JSON to stdout; human summary to stderr.
# Exit 0 = pass/skip; Exit 1 = fail.
set -euo pipefail

SCAN_PATH="${1:-.}"
FINDINGS=()
STATUS="pass"

MAX_OUTPUT_BYTES=102400  # 100 KB

any_ipynb_files() {
  find "$SCAN_PATH" -name "*.ipynb" -not -path "*/.git/*" 2>/dev/null | grep -q .
}

if ! any_ipynb_files; then
  echo '{"check":"notebook","status":"skip","findings":0,"details":["no-ipynb-files"]}'; exit 0
fi

# Locate tool helpers
find_tool() {
  local name="$1"
  local venv_path
  venv_path="$(pwd)/.venv/bin/$name"
  if [ -x "$venv_path" ]; then echo "$venv_path"; return; fi
  if command -v "$name" &>/dev/null; then echo "$name"; return; fi
  echo ""
}

# --- nbqa ruff ---
NBQA=$(find_tool "nbqa")
RUFF=$(find_tool "ruff")
if [ -z "$NBQA" ] || [ -z "$RUFF" ]; then
  missing=""
  [ -z "$NBQA" ] && missing+="nbqa "
  [ -z "$RUFF" ] && missing+="ruff"
  echo "[notebook] tools not found: $missing — install: uv pip install nbqa ruff" >&2
  FINDINGS+=("tool-missing: $missing (install: uv pip install nbqa ruff)")
else
  while IFS= read -r nb; do
    if ! "$NBQA" ruff "$nb" 2>/dev/null; then
      echo "[notebook] ruff issues in: $nb" >&2
      FINDINGS+=("nbqa-ruff: issues in $(basename "$nb")")
      STATUS="fail"
    fi
  done < <(find "$SCAN_PATH" -name "*.ipynb" -not -path "*/.git/*" 2>/dev/null)
  if [ "$STATUS" = "pass" ]; then echo "[notebook] nbqa ruff: pass" >&2; fi
fi

# --- output size check ---
while IFS= read -r nb; do
  size=$(python3 - "$nb" <<'PYEOF'
import json, sys
nb_path = sys.argv[1]
with open(nb_path) as f:
    nb = json.load(f)
total = 0
for cell in nb.get("cells", []):
    for output in cell.get("outputs", []):
        for key in ("text", "data"):
            val = output.get(key)
            if isinstance(val, list):
                total += sum(len(v) for v in val)
            elif isinstance(val, dict):
                total += sum(len(str(v)) for v in val.values())
print(total)
PYEOF
)
  if [ "$size" -gt "$MAX_OUTPUT_BYTES" ] 2>/dev/null; then
    kb=$((size / 1024))
    echo "[notebook] large outputs (${kb} KB) in: $nb" >&2
    FINDINGS+=("large-output: ${kb}KB in $(basename "$nb") — consider clearing outputs")
  fi
done < <(find "$SCAN_PATH" -name "*.ipynb" -not -path "*/.git/*" 2>/dev/null)

if [ "$STATUS" = "pass" ]; then echo "[notebook] output check: pass" >&2; fi

DETAILS_JSON="["
for i in "${!FINDINGS[@]}"; do
  if [ $i -gt 0 ]; then DETAILS_JSON+=","; fi
  DETAILS_JSON+=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${FINDINGS[$i]}")
done
DETAILS_JSON+="]"

echo "{\"check\":\"notebook\",\"status\":\"$STATUS\",\"findings\":${#FINDINGS[@]},\"details\":$DETAILS_JSON}"
[ "$STATUS" = "pass" ] && exit 0 || exit 1
