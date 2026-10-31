#!/usr/bin/env bash
# Pasos como usuario nuevo (sin privilegios). Lo llama usuario_nuevo_dentro.sh con la entrada estándar cerrada,
# para que ningún programa se coma las líneas del guion.
set -euo pipefail
cd ~
echo "== instalación como en docs/GUIA-INSTALACION.md"
claude plugin marketplace add /tmp/kit
claude plugin install meeting-to-backlog@vibe-tool-kit
echo '{"PERFIL":"rapido","IDIOMA":"es","GRAPH_AUTH":"ninguno"}' | claude plugin configure meeting-to-backlog@vibe-tool-kit --values-stdin

echo "== medios de prueba (públicos y sintéticos)"
python3 - <<'P'
import json, urllib.request
u = "https://datasets-server.huggingface.co/rows?dataset=PolyAI/minds14&config=es-ES&split=train&offset=0&length=1"
row = json.load(urllib.request.urlopen(u, timeout=60))["rows"][0]["row"]
open("/tmp/clip.wav", "wb").write(urllib.request.urlopen(row["audio"][0]["src"], timeout=60).read())
P
ffmpeg -v error -y -stream_loop 5 -i /tmp/clip.wav -t 60 -ac 1 -ar 16000 /tmp/voz.wav
ffmpeg -v error -y -f lavfi -i "smptebars=s=1280x720:r=10" -f lavfi -i "testsrc2=s=1280x720:r=10" \
  -f lavfi -i "mandelbrot=s=1280x720:r=10" -f lavfi -i "rgbtestsrc=s=1280x720:r=10" -i /tmp/voz.wav \
  -filter_complex "[0:v]trim=0:15,setpts=PTS-STARTPTS[a];[1:v]trim=0:15,setpts=PTS-STARTPTS[b];[2:v]trim=0:15,setpts=PTS-STARTPTS[c];[3:v]trim=0:15,setpts=PTS-STARTPTS[d];[a][b][c][d]concat=n=4:v=1:a=0[v]" \
  -map "[v]" -map 4:a -c:v libx264 -g 20 -pix_fmt yuv420p -c:a aac -shortest /tmp/reunion.mp4

echo "== primera reunión: instalación desde cero (dependencias fijadas + modelo fijado) desde la copia instalada"
python3 /tmp/kit/tests/e2e/meeting_to_backlog.py /tmp/reunion.mp4 --instalado meeting-to-backlog@vibe-tool-kit --min-marcas 1 --timeout 1500
echo "== segunda reunión (solo audio): reutiliza lo instalado"
python3 /tmp/kit/tests/e2e/meeting_to_backlog.py /tmp/clip.wav --instalado meeting-to-backlog@vibe-tool-kit --min-marcas 1 --timeout 600

echo "== permisos de lo que creó el plugin"
D=$(ls -d ~/.claude/plugins/data/meeting-to-backlog* | head -1)
echo "datos: $D ($(stat -c %a "$D"))"
[ "$(stat -c %a "$D")" = 700 ] || { echo "FAIL: la carpeta de datos no es 700"; exit 1; }
abiertos=$(find "$D" -path "$D/venv" -prune -o \( -perm -o=r -o -perm -g=r \) -print | wc -l)
echo "archivos legibles por otros usuarios fuera del venv: $abiertos"
[ "$abiertos" -eq 0 ] || { find "$D" -path "$D/venv" -prune -o \( -perm -o=r -o -perm -g=r \) -print | head; exit 1; }
echo USUARIO_NUEVO_OK
