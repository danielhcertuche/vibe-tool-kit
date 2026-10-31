"""Pruebas de la limpieza de transcripciones (worker.limpiar y worker.agrupar).

  python3 tests/unit/test_postproceso.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "meeting-to-backlog", "server"))
import worker  # noqa: E402

ok = []


def check(c, m):
    ok.append(bool(c))
    print(("ok   " if c else "FAIL ") + m)


def seg(i, f, t):
    return {"inicio": i, "fin": f, "texto": t}


cola = [seg(100, 101, "acordamos el cierre el 26"), seg(101, 102, "Muchas gracias.")] + \
       [seg(102 + k, 103 + k, "muchas gracias") for k in range(12)]
lim = worker.limpiar(cola, duracion=108)
check(sum("gracias" in s["texto"].lower() for s in lim) == 2, "deja como mucho dos repeticiones seguidas")
check(all(s["inicio"] <= 108.5 for s in lim), "quita marcas posteriores al final del audio")
check(lim[0]["texto"] == "acordamos el cierre el 26", "no toca el habla real")
check(len(worker.limpiar([seg(0, 1, "sí"), seg(1, 2, "no"), seg(2, 3, "sí")], 10)) == 3,
      "repeticiones no seguidas se conservan")

frag = [seg(0, 1, "vamos a tener"), seg(1.2, 2, "12 sesiones"), seg(2.1, 3, "de 2 horas"),
        seg(9, 10, "¿quién define los retos?"), seg(10.2, 11, "nosotros")]
ag = worker.agrupar(frag)
check(len(ag) == 3 and ag[0]["texto"] == "vamos a tener 12 sesiones de 2 horas", "une fragmentos seguidos")
check(ag[0]["inicio"] == 0 and ag[0]["fin"] == 3, "conserva el inicio y el fin del grupo")
check(ag[1]["texto"].endswith("?") and ag[2]["texto"] == "nosotros", "no une una pregunta con la respuesta")
largo = [seg(i, i + 1, "x" * 100) for i in range(5)]
check(all(len(s["texto"]) < 240 for s in worker.agrupar(largo)), "respeta el máximo de caracteres por línea")
print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
