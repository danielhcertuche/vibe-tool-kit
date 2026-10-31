"""Pruebas del control de cuota gratuita de Groq (plugins/meeting-to-backlog/server/cupo.py).

  python3 tests/unit/test_cupo.py
"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "meeting-to-backlog", "server"))
import cupo  # noqa: E402

AHORA = time.mktime(time.strptime("2026-10-31T15:00:00", "%Y-%m-%dT%H:%M:%S"))
ok = []


def check(c, m):
    ok.append(bool(c))
    print(("ok   " if c else "FAIL ") + m)


def registro(filas):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for hace_s, dur, http in filas:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(AHORA - hace_s))
        f.write(json.dumps({"ts": ts, "dur_s": dur, "http": http}) + "\n")
    f.close()
    return f.name


H1 = 3600  # una reunión de 1 h
vacio = registro([])
pct, motivo, _ = cupo.permitido(0.3, H1, vacio, ahora=AHORA)
check(pct == 0.3, f"sin consumo previo: manda el 30 % pedido ({pct}, {motivo})")

pct, motivo, _ = cupo.permitido(0.5, H1, vacio, ahora=AHORA)
check(pct == 0.3 and motivo == "tope del plugin", f"pide 50 %: lo baja al tope del 30 % ({pct})")

# 5.000 s ya usados en la última hora: quedan 7200*0,8 - 5000 = 760 s -> 760/3600 = 21 %
r = registro([(600, 2500, 200), (1200, 2500, 200)])
pct, motivo, u = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(motivo == "cupo por hora" and abs(pct - 0.211) < 0.002, f"cupo por hora casi lleno: baja a {pct} ({motivo})")

# Hora llena: todo local
r = registro([(300, 5800, 200)])
pct, motivo, _ = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(pct == 0.0, f"cupo por hora agotado: todo local ({motivo})")

# Día casi lleno (fuera de la última hora): 23 000 s -> quedan 23 040 - 23 000 = 40 s: manda solo eso (1,1 %)
r = registro([(7200 + i * 600, 2300, 200) for i in range(10)])
pct, motivo, u = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(motivo == "cupo diario" and abs(pct - 0.011) < 0.001, f"cupo diario casi lleno: baja a {pct} ({motivo})")

# Quedan 20 s en el día: menos de 30 s útiles, todo local
r = registro([(7200 + i * 600, 2302, 200) for i in range(10)])
pct, motivo, _ = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(pct == 0.0, f"cupo diario agotado: todo local ({motivo})")

# Lo de hace más de 24 h no cuenta en el día
r = registro([(90000, 20000, 200)])
pct, _, u = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(pct == 0.3 and u["audio_s_dia"] == 0, "consumo de ayer no cuenta para hoy")

# Mínimo de cobro de 10 s por petición
r = registro([(60, 2, 200), (120, 3, 200)])
_, _, u = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(u["audio_s_hora"] == 20, f"cobra mínimo 10 s por petición ({u['audio_s_hora']} s)")

# Los errores no cuentan como audio; el 429 sí como petición
r = registro([(60, 600, 403), (90, 600, 429)])
_, _, u = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(u["audio_s_hora"] == 0 and u["peticiones_dia"] == 1, "403 no cuenta; 429 cuenta solo como petición")

# Presupuesto mensual: 60 min al mes, ya usados 50 -> quedan 600 s -> 600/3600 = 16,7 %
r = registro([(3 * 86400, 3000, 200)])
pct, motivo, _ = cupo.permitido(0.3, H1, r, presupuesto_mes_s=3600, ahora=AHORA)
check(motivo == "presupuesto del mes" and abs(pct - 0.167) < 0.002, f"presupuesto del mes reduce a {pct}")

# Reunión corta: menos de 30 s a la nube no vale la pena
pct, _, _ = cupo.permitido(0.3, 60, vacio, ahora=AHORA)
check(pct == 0.0, "reunión de 1 min: el 30 % son 18 s, va todo local")

# Peticiones del día al límite
r = registro([(3700 + i * 50, 1, 200) for i in range(1600)])  # repartidas en el día, fuera de la última hora
pct, motivo, _ = cupo.permitido(0.3, H1, r, ahora=AHORA)
check(pct == 0.0 and motivo == "peticiones del día", f"peticiones del día al 80 %: todo local ({motivo})")
print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
