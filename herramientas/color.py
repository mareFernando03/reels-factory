"""Igualar el color entre las tomas de un reel (criterio O6) sin cambiar el tono del pelo (M3).

Mide cada clip preparado y lo acerca a la toma de referencia (la del revelado):
  brillo   → mediana de la luminancia; se corrige con gamma (no levanta los negros)
  balance  → R/G y B/G medidos solo en píxeles casi neutros (paredes, piso, guardapolvo):
             el promedio de toda la imagen mide el contenido (una campera celeste), no la luz
La corrección es parcial (FUERZA) y con topes: una pared blanca y una ventana nunca van a
tener el mismo brillo, y eso está bien. No se tocan la referencia ni los dos lados de una
comparación antes | después (su diferencia es real, es lo que se muestra).
"""

import math

import numpy as np

FUERZA = 0.5                 # qué parte de la diferencia se corrige
GAMMA = (0.85, 1.25)         # tope de la corrección de brillo
GANANCIA = 0.04              # tope de la corrección de balance (±4 % por canal)
NEUTROS_MIN = 0.25           # fracción mínima de píxeles neutros para corregir el balance
UMBRAL_GAMMA = 0.03          # por debajo de esto no vale la pena recodificar
UMBRAL_GANANCIA = 0.01


def medir(clip, n=6):
    """{y: mediana de luminancia 0-255, rg, bg: balance en neutros, neutros: fracción}."""
    import cv2

    from legibilidad import cuadros
    px = np.concatenate([cv2.resize(f, (108, 192)).reshape(-1, 3).astype(float) for f in cuadros(clip, n)])
    b, g, r = px.T
    y = 0.299 * r + 0.587 * g + 0.114 * b
    mx, mn = px.max(1), px.min(1)
    neutro = ((mx - mn) / np.maximum(mx, 1) < 0.18) & (mx > 60) & (mx < 240)
    out = {"y": round(float(np.median(y)), 1), "neutros": round(float(neutro.mean()), 2), "rg": None, "bg": None}
    if neutro.sum() > 500:
        nb, ng, nr = px[neutro].mean(0)
        out.update(rg=round(float(nr / ng), 4), bg=round(float(nb / ng), 4))
    return out


def correccion(m, ref):
    """{gamma, rr, bb} para acercar la medición `m` a `ref`, o None si no hace falta."""
    objetivo = m["y"] + FUERZA * (ref["y"] - m["y"])
    gamma = 1.0
    if 1 < m["y"] < 254 and 1 < objetivo < 254:
        gamma = math.log(m["y"] / 255) / math.log(objetivo / 255)
        gamma = min(max(gamma, GAMMA[0]), GAMMA[1])
    rr = bb = 1.0
    if m["rg"] and ref["rg"] and m["neutros"] >= NEUTROS_MIN and ref["neutros"] >= NEUTROS_MIN:
        acotar = lambda x: min(max(x, 1 - GANANCIA), 1 + GANANCIA)  # noqa: E731
        rr = acotar((ref["rg"] / m["rg"]) ** FUERZA)
        bb = acotar((ref["bg"] / m["bg"]) ** FUERZA)
    if abs(gamma - 1) < UMBRAL_GAMMA and abs(rr - 1) < UMBRAL_GANANCIA and abs(bb - 1) < UMBRAL_GANANCIA:
        return None
    return {"gamma": round(gamma, 3), "rr": round(rr, 3), "bb": round(bb, 3)}


def filtro(c):
    """Filtro de ffmpeg para una corrección."""
    return f"eq=gamma={c['gamma']},colorchannelmixer=rr={c['rr']}:bb={c['bb']}"


def referencia(tomas):
    """La toma del revelado (rol revelado, o WOW/REVELADO en `que`); si no hay, None (se usa la mediana)."""
    for t in tomas:
        que = str(t.get("que", "")).lower()
        if t.get("rol") == "revelado" or "wow" in que or "revelado" in que:
            return t["n"]
    return None
