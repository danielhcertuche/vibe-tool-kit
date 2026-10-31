#!/usr/bin/env bash
# Corre una herramienta en un contenedor desechable: usa la CPU y la RAM de la
# máquina mientras procesa y las libera al terminar, sin instalar nada en el host.
#
#   kit_ephemeral.sh <herramienta> [args...]       herramientas: ver TOOLS abajo
#   kit_ephemeral.sh --list | --pull | --verify-clean
#
# Garantías:
#   - El contenedor se borra siempre (trap EXIT), también si la herramienta falla
#     o se interrumpe con Ctrl-C.
#   - Límites: KIT_CPUS (def. mitad de los núcleos), KIT_MEM (def. 4g), 512 pids.
#   - El código se monta en /src en solo lectura; solo /out es escribible.
#   - Sin red salvo las herramientas que la necesitan (NET=1 en TOOLS).
#   - KIT_PURGE=1 borra además la imagen al final (libera también el disco).
#   - Una línea de métricas por corrida en $KIT_METRICS (TSV): herramienta,
#     segundos, pico de RAM en MiB, código de salida, contenedores huérfanos.
set -euo pipefail

SRC="${KIT_SRC:-$PWD}"
OUT="${KIT_OUT:-$PWD/.kit-out}"
CPUS="${KIT_CPUS:-$(( $(nproc) / 2 ))}"
MEM="${KIT_MEM:-4g}"
METRICS="${KIT_METRICS:-$OUT/metrics.tsv}"
LABEL="kit-ephemeral=1"

# herramienta|imagen fijada por digest (versión en docs/kit-dual/00-entorno.md)|red (0/1)|entrypoint
TOOLS="
gitleaks|ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f|0|
trufflehog|trufflesecurity/trufflehog@sha256:0d003fc3abc4e1565eca8462b992001314de51451e96e3c44de80d116794d5d1|0|
semgrep|semgrep/semgrep@sha256:451b3d875c00dac7ed5db5293e584a07de11449a409c10b3c2d2652f429630b6|1|
bandit|ghcr.io/pycqa/bandit/bandit@sha256:2af36b230e3e7e816812c03157e5b86ed89f26611248994987fe694d72b9044d|0|
shellcheck|koalaman/shellcheck@sha256:bb596a0d169b85ddd81d8b6d3a2ff6d5baf5fca10b97f575ebc647c3dff62b3d|0|
osv-scanner|ghcr.io/google/osv-scanner@sha256:4f3b7e2c64b9d38a5febc5a7e4a3dfef1d1362f726dea7a2ef4762b46469fcd0|1|
syft|anchore/syft@sha256:4cc92b64ca74ffca4c94d4c8fcc01f217731375300be14d0b6eeb2e82eaa110a|0|
jq|ghcr.io/jqlang/jq@sha256:b9c68867e5766576263a222e91db3de422d802069c7af70440e667a95344e486|0|
python|python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159|0|python3
"

lookup() { printf '%s\n' "$TOOLS" | awk -F'|' -v t="$1" '$1==t'; }

case "${1:-}" in
  ""|-h|--help) sed -n '2,16p' "$0"; exit 0 ;;
  --list) printf '%s\n' "$TOOLS" | awk -F'|' 'NF{print $1" -> "$2}'; exit 0 ;;
  --pull)
    printf '%s\n' "$TOOLS" | awk -F'|' 'NF{print $2}' | while read -r img; do
      docker pull -q "$img" >/dev/null && docker image inspect --format '{{index .RepoDigests 0}}' "$img"
    done; exit 0 ;;
  --verify-clean)
    n=$(docker ps -aq --filter "label=$LABEL" | wc -l)
    echo "contenedores kit-ephemeral vivos: $n"; [ "$n" -eq 0 ]; exit ;;
esac

tool="$1"; shift
row=$(lookup "$tool"); [ -n "$row" ] || { echo "herramienta desconocida: $tool" >&2; exit 2; }
IFS='|' read -r _ image net entry <<<"$row"

mkdir -p "$OUT"
[ -s "$METRICS" ] || printf 'fecha\therramienta\tsegundos\tpico_mib\texit\thuerfanos\tcpus\tmem\n' >"$METRICS"

name="kit-$tool-$$-$RANDOM"
peak_file=$(mktemp)
echo 0 >"$peak_file"
sampler=""

# shellcheck disable=SC2329  # se invoca desde trap
cleanup() {
  [ -n "$sampler" ] && kill "$sampler" 2>/dev/null || true
  docker rm -f "$name" >/dev/null 2>&1 || true
  [ "${KIT_PURGE:-0}" = 1 ] && docker rmi "$image" >/dev/null 2>&1 || true
  rm -f "$peak_file"
}
trap cleanup EXIT INT TERM

args=(--name "$name" --label "$LABEL" --cpus "$CPUS" --memory "$MEM" --memory-swap "$MEM"
      --pids-limit 512 --security-opt no-new-privileges --cap-drop ALL
      -u "$(id -u):$(id -g)" -e HOME=/tmp -w /src
      -v "$SRC:/src:ro" -v "$OUT:/out")
[ "$net" = 1 ] || args+=(--network none)
[ -n "$entry" ] && args+=(--entrypoint "$entry")
for m in ${KIT_EXTRA_RO:-}; do args+=(-v "$m:$m:ro"); done

start=$(date +%s.%N)
docker create "${args[@]}" "$image" "$@" >/dev/null
docker start "$name" >/dev/null
# Muestrea la RAM del contenedor cada 0,5 s y guarda el pico.
( while docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null | grep -q true; do
    m=$(docker stats --no-stream --format '{{.MemUsage}}' "$name" 2>/dev/null | awk '{print $1}')
    mib=$(awk -v m="$m" 'BEGIN{v=m+0; if(m~/GiB/)v*=1024; else if(m~/KiB/)v/=1024; else if(m~/[0-9]B$/ && m!~/[KMG]iB/)v/=1048576; printf "%.0f", v}')
    [ "${mib:-0}" -gt "$(cat "$peak_file")" ] && echo "$mib" >"$peak_file"
    sleep 0.5
  done ) &
sampler=$!
docker logs -f "$name" &
logs=$!
rc=$(docker wait "$name")
wait "$logs" 2>/dev/null || true
end=$(date +%s.%N)
kill "$sampler" 2>/dev/null || true; sampler=""
peak=$(cat "$peak_file")
docker rm -f "$name" >/dev/null 2>&1 || true
orphans=$(docker ps -aq --filter "label=$LABEL" --filter "name=kit-$tool-$$" | wc -l)
printf '%s\t%s\t%.1f\t%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$tool" "$(echo "$end - $start" | bc)" \
  "$peak" "$rc" "$orphans" "$CPUS" "$MEM" >>"$METRICS"
exit "$rc"
