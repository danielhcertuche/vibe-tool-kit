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
#   - Una línea de métricas por corrida en $KIT_METRICS (TSV): segundos, CPU
#     consumida y % de la CPU asignada, pico de RAM con caché y sin ella (cgroup v2),
#     exit y huérfanos.
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
[ -s "$METRICS" ] || printf 'fecha\therramienta\tsegundos\tcpu_seg\tuso_cpu_pct\tpico_mib\tpico_anon_mib\texit\thuerfanos\tcpus\tmem\n' >"$METRICS"

name="kit-$tool-$$-$RANDOM"
stat_dir=$(mktemp -d)
sampler=""

# shellcheck disable=SC2329  # se invoca desde trap
cleanup() {
  [ -n "$sampler" ] && kill "$sampler" 2>/dev/null || true
  docker rm -f "$name" >/dev/null 2>&1 || true
  [ "${KIT_PURGE:-0}" = 1 ] && docker rmi "$image" >/dev/null 2>&1 || true
  rm -rf "$stat_dir"
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
# Pico de RAM y CPU consumida, leídos del cgroup v2 del contenedor cada 0,1 s.
# memory.peak y cpu.stat son acumulados, así que la última lectura antes de que el
# cgroup desaparezca es el valor final. memory.peak incluye la caché de páginas de lo
# que el proceso lee (recuperable, no causa OOM); pico_anon_mib es la memoria propia
# del proceso: el máximo de `anon` en memory.stat. Sin cgroup v2 (cgroupfs v1, Docker Desktop
# en macOS) las columnas salen con "-" en vez de un muestreo engañoso.
id=$(docker inspect -f '{{.Id}}' "$name")
cg=""
for p in "/sys/fs/cgroup/system.slice/docker-$id.scope" "/sys/fs/cgroup/docker/$id"; do
  [ -r "$p/memory.peak" ] && cg=$p
done
if [ -n "$cg" ]; then
  ( while [ -r "$cg/memory.peak" ]; do
      v=$(cat "$cg/memory.peak" 2>/dev/null) && [ -n "$v" ] && echo "$v" >"$stat_dir/peak"
      v=$(awk '/^usage_usec/{print $2}' "$cg/cpu.stat" 2>/dev/null) && [ -n "$v" ] && echo "$v" >"$stat_dir/cpu"
      v=$(awk '/^anon /{print $2}' "$cg/memory.stat" 2>/dev/null)
      [ -n "$v" ] && [ "$v" -gt "$(cat "$stat_dir/anon" 2>/dev/null || echo 0)" ] && echo "$v" >"$stat_dir/anon"
      sleep 0.1
    done ) &
  sampler=$!
fi
docker logs -f "$name" &
logs=$!
rc=$(docker wait "$name")
wait "$logs" 2>/dev/null || true
end=$(date +%s.%N)
[ -n "$sampler" ] && { kill "$sampler" 2>/dev/null || true; sampler=""; }
docker rm -f "$name" >/dev/null 2>&1 || true
orphans=$(docker ps -aq --filter "label=$LABEL" --filter "name=kit-$tool-$$" | wc -l)
awk -v t0="$start" -v t1="$end" -v cpus="$CPUS" -v pk="$(cat "$stat_dir/peak" 2>/dev/null)" \
    -v cu="$(cat "$stat_dir/cpu" 2>/dev/null)" -v an="$(cat "$stat_dir/anon" 2>/dev/null)" -v d="$(date -Is)" -v tool="$tool" -v rc="$rc" \
    -v orph="$orphans" -v mem="$MEM" 'BEGIN{
  s = t1 - t0
  cs = (cu == "") ? "-" : sprintf("%.1f", cu / 1e6)
  pct = (cu == "" || s <= 0) ? "-" : sprintf("%.0f", 100 * cu / 1e6 / (s * cpus))
  pm = (pk == "") ? "-" : sprintf("%.0f", pk / 1048576)
  am = (an == "") ? "-" : sprintf("%.0f", an / 1048576)
  printf "%s\t%s\t%.1f\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", d, tool, s, cs, pct, pm, am, rc, orph, cpus, mem
}' >>"$METRICS"
exit "$rc"
