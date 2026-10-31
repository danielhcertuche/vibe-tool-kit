#!/usr/bin/env bash
# checks/terraform.sh — Terraform quality check (fmt + validate)
# Usage: ./terraform.sh <path>
# Outputs JSON to stdout; human summary to stderr.
# Exit 0 = pass/skip; Exit 1 = fail.
set -euo pipefail

SCAN_PATH="${1:-.}"
FINDINGS=()
STATUS="pass"

any_tf_files() {
  find "$SCAN_PATH" -name "*.tf" -not -path "*/.git/*" 2>/dev/null | grep -q .
}

if ! any_tf_files; then
  echo '{"check":"terraform","status":"skip","findings":0,"details":["no-tf-files"]}'; exit 0
fi

if ! command -v terraform &>/dev/null; then
  echo "[terraform] terraform not found — install from https://developer.hashicorp.com/terraform/install" >&2
  echo '{"check":"terraform","status":"skip","findings":0,"details":["tool-missing: terraform (install: https://developer.hashicorp.com/terraform/install)"]}'
  exit 0
fi

# --- terraform fmt ---
if ! terraform fmt -check -recursive "$SCAN_PATH" 2>/dev/null; then
  echo "[terraform] fmt: files not formatted" >&2
  FINDINGS+=("terraform-fmt: files need formatting (run: terraform fmt -recursive)")
  STATUS="fail"
else
  echo "[terraform] fmt: pass" >&2
fi

# --- terraform validate (per module directory) ---
while IFS= read -r tf_dir; do
  if ! (cd "$tf_dir" && terraform validate -json 2>/dev/null | python3 -c "
import json,sys
data = json.load(sys.stdin)
sys.exit(0 if data.get('valid') else 1)
" 2>/dev/null); then
    echo "[terraform] validate failed in: $tf_dir" >&2
    FINDINGS+=("terraform-validate: errors in $(basename "$tf_dir")")
    STATUS="fail"
  fi
done < <(find "$SCAN_PATH" -name "*.tf" -not -path "*/.git/*" -exec dirname {} \; 2>/dev/null | sort -u)

if [ "$STATUS" = "pass" ]; then echo "[terraform] validate: pass" >&2; fi

DETAILS_JSON="["
for i in "${!FINDINGS[@]}"; do
  if [ $i -gt 0 ]; then DETAILS_JSON+=","; fi
  DETAILS_JSON+=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "${FINDINGS[$i]}")
done
DETAILS_JSON+="]"

echo "{\"check\":\"terraform\",\"status\":\"$STATUS\",\"findings\":${#FINDINGS[@]},\"details\":$DETAILS_JSON}"
[ "$STATUS" = "pass" ] && exit 0 || exit 1
