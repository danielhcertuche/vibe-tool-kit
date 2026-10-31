#!/usr/bin/env bash
# run-sca.sh — Software Composition Analysis: scan dependencies for CVEs
# Usage: ./run-sca.sh [python|node|auto]
# Called by: security-appsec agent via Bash tool

set -euo pipefail

LANG="${1:-auto}"

echo "=== Dependency CVE Scan (SCA) ==="

run_python_audit() {
  echo "--- Python: pip-audit ---"
  if command -v pip-audit &>/dev/null; then
    pip-audit --format=json --output /tmp/pip-audit.json 2>/dev/null || true
    VULNS=$(jq '[.[] | .vulns | length] | add // 0' /tmp/pip-audit.json)
    echo "Vulnerabilities found: $VULNS"
    if [[ $VULNS -gt 0 ]]; then
      jq -r '.[] | select(.vulns | length > 0) | "Package: \(.name) \(.version)\n\(.vulns[] | "  [\(.id)] \(.fix_versions | join(", ")) — \(.description | .[0:100])")\n"' \
        /tmp/pip-audit.json
    fi
  else
    echo "[SKIP] pip-audit not installed (pip install pip-audit)"
  fi
}

run_node_audit() {
  echo "--- Node.js: npm audit ---"
  if [[ -f "package.json" ]]; then
    npm audit --json 2>/dev/null | tee /tmp/npm-audit.json | \
      jq -r '"Critical: \(.metadata.vulnerabilities.critical), High: \(.metadata.vulnerabilities.high), Moderate: \(.metadata.vulnerabilities.moderate)"' \
      || echo "[WARN] npm audit failed or no package.json"
  else
    echo "[SKIP] No package.json in current directory"
  fi
}

run_trivy_fs() {
  echo "--- Filesystem: trivy fs ---"
  if command -v trivy &>/dev/null; then
    trivy fs . --severity HIGH,CRITICAL --format table 2>/dev/null || true
  else
    echo "[SKIP] trivy not installed"
  fi
}

case "$LANG" in
  python) run_python_audit ;;
  node)   run_node_audit ;;
  auto)
    run_python_audit
    echo ""
    run_node_audit
    echo ""
    run_trivy_fs
    ;;
  *)
    echo "Usage: $0 [python|node|auto]" >&2
    exit 1
    ;;
esac

echo ""
echo "=== SCA scan complete ==="
