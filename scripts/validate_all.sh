#!/usr/bin/env bash
# claude plugin validate --strict sobre el marketplace y cada plugin. Exit != 0 si alguno falla.
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0
claude plugin validate --strict . || fail=1
for p in plugins/*/; do
  echo "== $p"; claude plugin validate --strict "$p" || fail=1
done
# Los manifests Claude y Codex de cada plugin deben ser idénticos (una sola fuente, ADR-010).
for p in plugins/*/; do
  cmp -s "$p/.claude-plugin/plugin.json" "$p/.codex-plugin/plugin.json" || { echo "deriva Claude/Codex: $p"; fail=1; }
done
cmp -s .claude-plugin/marketplace.json .agents/plugins/marketplace.json || { echo "deriva de marketplace"; fail=1; }
exit $fail
