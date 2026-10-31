"""Cuánto audio se puede mandar a la nube sin pasar la cuota gratuita de Groq. Solo stdlib.

Groq solo informa en cabeceras la cuota de peticiones; la de segundos de audio por hora y por día no viene
en ninguna respuesta, así que se lleva la cuenta en local con registro_nube.jsonl (cada envío ya registra
su duración). Se cobra el mínimo de 10 s por petición, como Groq, y solo se usa MARGEN del límite gratuito.
Con una llave compartida entre varias máquinas este registro no ve el consumo de las otras: una llave por
persona.
"""
import json
import os
import time

# Plan Free de Groq para whisper-large-v3-turbo (console.groq.com/docs/rate-limits, 2026-10-31).
LIMITE = {"audio_s_hora": 7200, "audio_s_dia": 28800, "peticiones_dia": 2000}
MIN_COBRO_S = 10
MARGEN = float(os.environ.get("VTK_NUBE_MARGEN", "0.8"))
PCT_TOPE = float(os.environ.get("VTK_NUBE_PCT_MAX", "0.3"))


def _filas(registro):
    try:
        with open(registro) as f:
            for line in f:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def usado(registro, ahora=None):
    """Consumo en ventanas móviles de 1 h, 24 h y mes calendario (segundos cobrables y peticiones)."""
    ahora = ahora or time.time()
    mes = time.strftime("%Y-%m", time.localtime(ahora))
    u = {"audio_s_hora": 0.0, "audio_s_dia": 0.0, "peticiones_dia": 0, "audio_s_mes": 0.0}
    for f in _filas(registro):
        try:
            t = time.mktime(time.strptime(f["ts"], "%Y-%m-%dT%H:%M:%S"))
        except (KeyError, ValueError):
            continue
        if f.get("http") not in (200, 429):  # 429 cuenta como petición, no como audio
            continue
        cobro = max(float(f.get("dur_s", 0)), MIN_COBRO_S) if f["http"] == 200 else 0
        if ahora - t <= 86400:
            u["peticiones_dia"] += 1
            u["audio_s_dia"] += cobro
            if ahora - t <= 3600:
                u["audio_s_hora"] += cobro
        if f["ts"][:7] == mes:
            u["audio_s_mes"] += cobro
    return u


def permitido(pct_pedido, duracion_s, registro, bloques=1, presupuesto_mes_s=0, ahora=None):
    """(pct_efectivo, motivo). Nunca más que el pedido, ni que PCT_TOPE, ni que lo que queda de cuota."""
    u = usado(registro, ahora)
    cand = {"pedido": pct_pedido, "tope del plugin": PCT_TOPE}
    if duracion_s > 0:
        cand["cupo por hora"] = (LIMITE["audio_s_hora"] * MARGEN - u["audio_s_hora"]) / duracion_s
        cand["cupo diario"] = (LIMITE["audio_s_dia"] * MARGEN - u["audio_s_dia"]) / duracion_s
        if presupuesto_mes_s:
            cand["presupuesto del mes"] = (presupuesto_mes_s - u["audio_s_mes"]) / duracion_s
    if u["peticiones_dia"] + bloques > LIMITE["peticiones_dia"] * MARGEN:
        cand["peticiones del día"] = 0.0
    motivo, pct = min(cand.items(), key=lambda kv: kv[1])
    pct = max(0.0, round(pct, 3))
    # Un tramo que se cobra como mínimo 10 s no vale la pena por debajo de 30 s de audio.
    if 0 < pct and pct * duracion_s < 30:
        pct, motivo = 0.0, "tramo menor a 30 s"
    return pct, motivo, u
