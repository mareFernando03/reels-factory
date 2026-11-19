"""Puntaje de la rúbrica para una publicación, filtrado por formato.

Uso:
    uv run python herramientas/puntaje.py pedidos/<pedido>

Lee salida/puntos.yaml (lo completa Claude al evaluar, criterio por criterio):
    formato: reel | historia | foto | carrusel
    fallan: [T5]              # bloqueantes que fallan (vacío = todos pasan)
    no_aplica: [X3, E4]       # criterios del formato que no aplican a esta pieza
    puntos: { G1: 2, R4: 1, ... }   # importantes y deseables del formato: 0, 1 o 2

Importante vale doble. Veredicto según conocimiento/rubrica.yaml: un bloqueante que
falla → CORREGIR; ≥ 75 % → ENTREGAR; si no → ENTREGAR CON OBSERVACIONES.
Si falta puntuar un criterio que aplica, lo dice y no calcula: no se evalúa a medias.
"""

import argparse
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent


def calcular(ev, rub):
    """Puntaje de `ev` (lo de puntos.yaml) contra la rúbrica `rub`.

    Devuelve un dict con tot, mx, pct, veredicto, faltan (criterios del formato sin
    puntuar) y bajos ("ID=nota" de los que no llegan a 2). Si faltan, pct y veredicto son None.
    """
    formato, no_aplica = ev["formato"], set(ev.get("no_aplica") or [])
    puntos, fallan = ev.get("puntos") or {}, set(ev.get("fallan") or [])
    tot = mx = 0
    faltan, bajos = [], []
    for grupo, lista in rub.items():
        if not isinstance(lista, list) or grupo == "humano":
            continue
        for c in lista:
            if formato not in c.get("aplica_a", ["reel"]) or c["id"] in no_aplica:
                continue
            if c["peso"] == "bloqueante":
                continue
            f = 2 if c["peso"] == "importante" else 1
            if c["id"] not in puntos:
                faltan.append(c["id"])
                continue
            tot += puntos[c["id"]] * f
            mx += 2 * f
            if puntos[c["id"]] < 2:
                bajos.append(f"{c['id']}={puntos[c['id']]}")
    if faltan:
        return {"tot": tot, "mx": mx, "pct": None, "veredicto": None, "faltan": faltan, "bajos": bajos, "fallan": fallan}
    pct = 100 * tot / mx if mx else 0
    veredicto = "CORREGIR" if fallan else ("ENTREGAR" if pct >= 75 else "ENTREGAR CON OBSERVACIONES")
    return {"tot": tot, "mx": mx, "pct": pct, "veredicto": veredicto, "faltan": [], "bajos": bajos, "fallan": fallan}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    a = ap.parse_args()
    ev = yaml.safe_load((Path(a.pedido) / "salida" / "puntos.yaml").read_text(encoding="utf-8"))
    rub = yaml.safe_load((RAIZ / "conocimiento" / "rubrica.yaml").read_text(encoding="utf-8"))
    r = calcular(ev, rub)
    if r["faltan"]:
        sys.exit(f"Faltan puntuar ({ev['formato']}): {', '.join(r['faltan'])}")
    print(f"{ev['formato']}: {r['tot']}/{r['mx']} ({r['pct']:.1f} %) → {r['veredicto']}")
    if r["fallan"]:
        print(f"  bloqueantes que fallan: {', '.join(sorted(r['fallan']))}")
    if r["bajos"]:
        print(f"  por debajo del máximo: {', '.join(r['bajos'])}")
    if ev.get("no_aplica"):
        print(f"  no aplican: {', '.join(sorted(ev['no_aplica']))}")


if __name__ == "__main__":
    main()
