#!/usr/bin/env bash
# scan-secrets.sh — Detect hardcoded secrets with gitleaks
# Usage: ./scan-secrets.sh [path|git] [--staged]
# Called by: security-appsec agent via Bash tool

set -euo pipefail

MODE="${1:-git}"      # "git" = full history scan, "dir" = directory scan
STAGED="${2:-}"

if ! command -v gitleaks &>/dev/null; then
  echo "[ERROR] gitleaks not installed. See: https://github.com/gitleaks/gitleaks" >&2
  exit 1
fi

echo "=== Secret Scanning (gitleaks) ==="
echo "Mode: $MODE"
echo ""

REPORT_FILE="/tmp/gitleaks-report-$(date +%s).json"

if [[ "$MODE" == "git" ]]; then
  if [[ "$STAGED" == "--staged" ]]; then
    echo "Scanning staged changes only..."
    gitleaks protect --staged --report-format json --report-path "$REPORT_FILE" || true
  else
    echo "Scanning full git history..."
    gitleaks detect --source . --report-format json --report-path "$REPORT_FILE" || true
  fi
else
  echo "Scanning directory: $MODE"
  gitleaks detect --source "$MODE" --no-git --report-format json --report-path "$REPORT_FILE" || true
fi

if [[ ! -f "$REPORT_FILE" ]]; then
  echo "[PASS] No secrets found"
  exit 0
fi

FINDINGS=$(jq '. | length' "$REPORT_FILE" 2>/dev/null || echo "0")

if [[ "$FINDINGS" == "0" || "$FINDINGS" == "null" ]]; then
  echo "[PASS] No secrets detected"
  exit 0
fi

echo "[FAIL] $FINDINGS secret(s) detected — IMMEDIATE ACTION REQUIRED"
echo ""
echo "=== Findings ==="
jq -r '.[] | "Rule    : \(.RuleID)\nFile    : \(.File):\(.StartLine)\nSecret  : \(.Secret | .[0:8])...\nCommit  : \(.Commit // "N/A")\n"' \
  "$REPORT_FILE"

echo ""
echo "Action: Rotate all detected secrets immediately, then purge from git history."
exit 1
