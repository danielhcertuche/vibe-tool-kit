#!/usr/bin/env bash
# Falla (exit 1) si algún patrón de una denylist aparece en el árbol o el historial de un repo.
#   check_denylist.sh <repo> [denylist]        (por defecto config/denylist.generic.txt)
# Árbol: todo archivo fuera de .git, binarios y notebooks incluidos (rg -a).
# Historial: cada blob de todas las ramas y tags, volcado y pasado por el mismo rg, para
# que el motor de regex sea igual en ambos (git log -G no entiende \b).
# Imprime patrón y rutas o blobs, nunca el texto encontrado.
set -euo pipefail
repo=${1:?repo}; list=${2:-$(dirname "$0")/../config/denylist.generic.txt}
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
grep -vE '^\s*(#|$)' "$list" >"$work/pats"
if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  mkdir "$work/blobs"
  git -C "$repo" rev-list --objects --all | cut -d' ' -f1 |
    git -C "$repo" cat-file --batch-check='%(objecttype) %(objectname)' |
    awk '$1=="blob"{print $2}' | while read -r b; do
      git -C "$repo" cat-file -p "$b" >"$work/blobs/$b"
    done
fi
hits=0
while IFS= read -r p; do
  out=$(rg -P -a -l -i -e "$p" "$repo" --glob '!.git' 2>/dev/null | sort -u | tr '\n' ' ' || true)
  [ -n "$out" ] && { printf 'árbol\t%s\t%s\n' "$p" "$out"; hits=$((hits+1)); }
  if [ -d "$work/blobs" ]; then
    out=$(rg -P -a -l -i -e "$p" "$work/blobs" 2>/dev/null | xargs -r -n1 basename | cut -c1-8 | head -5 | tr '\n' ' ' || true)
    [ -n "$out" ] && { printf 'historial\t%s\tblobs %s\n' "$p" "$out"; hits=$((hits+1)); }
  fi
done <"$work/pats"
echo "coincidencias: $hits"
[ "$hits" -eq 0 ]
