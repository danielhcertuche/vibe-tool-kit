#!/usr/bin/env bash
# run-sast.sh — SAST scan with Semgrep
# Usage: ./run-sast.sh [path] [--config=auto|p/python|p/javascript|...]
# Called by: security-appsec agent via Bash tool

set -euo pipefail

SCAN_PATH="${1:-.}"
CONFIG="${2:---config=auto}"

if ! command -v semgrep &>/dev/null; then
  echo "[ERROR] semgrep not installed. Run: pip install semgrep" >&2
  exit 1
fi

echo "=== SAST Scan (Semgrep) ==="
echo "Path   : $SCAN_PATH"
echo "Config : $CONFIG"
echo ""

semgrep \
  $CONFIG \
  --json \
  --output /tmp/semgrep-results.json \
  "$SCAN_PATH" || true

FINDINGS=$(jq '.results | length' /tmp/semgrep-results.json)
CRITICAL=$(jq '[.results[] | select(.extra.severity == "ERROR")] | length' /tmp/semgrep-results.json)
HIGH=$(jq '[.results[] | select(.extra.severity == "WARNING")] | length' /tmp/semgrep-results.json)

echo "=== Results ==="
echo "Total findings : $FINDINGS"
echo "Critical/Error : $CRITICAL"
echo "High/Warning   : $HIGH"
echo ""

if [[ $FINDINGS -gt 0 ]]; then
  echo "=== Top findings ==="
  jq -r '.results[:10][] | "[\(.extra.severity)] \(.path):\(.start.line) — \(.check_id)\n  \(.extra.message)\n"' \
    /tmp/semgrep-results.json
fi

if [[ $CRITICAL -gt 0 ]]; then
  echo "[FAIL] $CRITICAL critical findings — must fix before merge"
  exit 1
elif [[ $HIGH -gt 0 ]]; then
  echo "[WARN] $HIGH high findings — review before merge"
  exit 0
else
  echo "[PASS] No critical/high findings"
  exit 0
fi
