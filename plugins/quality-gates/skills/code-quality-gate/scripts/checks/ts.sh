#!/usr/bin/env bash
# checks/ts.sh — TypeScript/TSX quality check (prettier + tsc + vitest)
# Usage: ./ts.sh <path>
# Outputs JSON to stdout; human summary to stderr.
# Exit 0 = pass/skip; Exit 1 = fail.
set -euo pipefail

SCAN_PATH="${1:-.}"
FINDINGS=()
STATUS="pass"

any_ts_files() {
  find "$SCAN_PATH" \( -name "*.ts" -o -name "*.tsx" \) \
    -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | grep -q .
}

if ! any_ts_files; then
  echo '{"check":"ts","status":"skip","findings":0,"details":["no-ts-files"]}'; exit 0
fi

# Locate nearest package.json to determine project root
find_pkg_root() {
  local dir
  dir=$(find "$SCAN_PATH" -name "package.json" -not -path "*/node_modules/*" 2>/dev/null | head -1)
  if [ -n "$dir" ]; then dirname "$dir"; else echo "$SCAN_PATH"; fi
}

PKG_ROOT=$(find_pkg_root)

# --- prettier ---
if ! (cd "$PKG_ROOT" && npx --yes prettier --check "**/*.{ts,tsx}" 2>/dev/null); then
  echo "[ts] prettier: formatting issues" >&2
  FINDINGS+=("prettier: files need formatting")
  STATUS="fail"
else
  echo "[ts] prettier: pass" >&2
fi

# --- tsc ---
if [ -f "$PKG_ROOT/tsconfig.json" ]; then
  if ! (cd "$PKG_ROOT" && npx --yes tsc --noEmit 2>/dev/null); then
    echo "[ts] tsc: type errors" >&2
    FINDINGS+=("tsc: type errors found")
    STATUS="fail"
  else
    echo "[ts] tsc: pass" >&2
  fi
else
  echo "[ts] tsc: no tsconfig.json found — skipping" >&2
  FINDINGS+=("tool-missing: tsconfig.json not found at $PKG_ROOT")
fi

# --- vitest (if test files exist) ---
test_files=$(find "$SCAN_PATH" \( -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" -o -name "*.spec.tsx" \) \
  -not -path "*/node_modules/*" 2>/dev/null | head -1)
if [ -n "$test_files" ]; then
  if ! (cd "$PKG_ROOT" && npx --yes vitest run --reporter=verbose 2>/dev/null); then
    echo "[ts] vitest: test failures" >&2
    FINDINGS+=("vitest: test failures")
    STATUS="fail"
  else
    echo "[ts] vitest: pass" >&2
  fi
fi

DETAILS_JSON="["
for i in "${!FINDINGS[@]}"; do
  if [ $i -gt 0 ]; then DETAILS_JSON+=","; fi
  DETAILS_JSON+=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${FINDINGS[$i]}")
done
DETAILS_JSON+="]"

echo "{\"check\":\"ts\",\"status\":\"$STATUS\",\"findings\":${#FINDINGS[@]},\"details\":$DETAILS_JSON}"
[ "$STATUS" = "pass" ] && exit 0 || exit 1
