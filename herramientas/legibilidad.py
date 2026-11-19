"""Legibilidad de los títulos: qué tan claro es el fondo detrás de cada uno.

Mide la luminancia relativa (WCAG) del video o la foto en la franja donde va a
quedar el título, en varios cuadros del tramo en que se ve. Sin criterio
editorial: devuelve números y la decisión mecánica de `tratamiento()`.

  sombra  → fondo oscuro o medio: el título blanco con la sombra difusa alcanza.
  bloques → fondo claro: cada palabra sobre un bloque magenta (la sombra difusa
            sobre una pared blanca queda como una mancha gris y no llega a 3:1).
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

ANCHO, ALTO = 1080, 1920
# Luminancia (p75 de la franja) a partir de la cual el fondo se trata como claro.
# Calibrado el 03/10/2026 con los títulos de los reels publicados: la pared blanca de
# "Las espero!" (día de trabajo) da ~0,6 y falla 3:1 aun con la sombra.
UMBRAL_CLARO = 0.40


def _lineal(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminancia(bgr):
    """Luminancia relativa WCAG por píxel de una imagen BGR (uint8)."""
    b, g, r = (_lineal(bgr[..., i].astype(np.float32)) for i in range(3))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


@lru_cache(maxsize=16)
def _medidor(fuente, px):
    from PIL import ImageFont
    return ImageFont.truetype(str(fuente), px)


def franja_titulo(texto, base, bloques=False, tam=104, tam_largo=92, max_ancho=900, fuente=None,
                  mayusculas=False, interletra=0.0, escala=1.0):
    """Caja aproximada (x0, y0, x1, y1) en px de un título centrado.

    `base` es la línea inferior en % del alto ("62%"); el título crece hacia arriba.
    Corta en renglones palabra por palabra, como el navegador (text-wrap: balance reparte
    distinto pero no cambia la cantidad). Con `fuente` (el woff2 de la marca, ver
    Estilo.medidas_titulo) mide cada renglón con la fuente real; sin ella, ancho medio de un
    carácter ≈ 0,56 em de la Fraunces, medido en "no me había dado cuenta…" (antes y después),
    que sale en 4 renglones. En `bloques` cada palabra suma el relleno de su bloque (~0,38 em) y
    el renglón mide 1,3 em (line-height 1,2 más el relleno vertical del bloque, 0,1 em: en el
    gancho de «El Extranjero», Bebas a 120 px, son 156 px por renglón); con sombra, 1,06 em.
    `escala` achica el cuerpo (armar_pop lo usa cuando el título no entra en la zona segura).
    """
    fuente_px = (tam_largo if len(texto) > 26 else tam) * escala
    # cada palabra va en un .p con relleno a los lados: 0,08 + 0,08 em menos 0,02 + 0,02 de margen = 0,12 em
    # con sombra. Sin contarlo, «asustan todo el año» medía 895 px y en el render no entraba en 900:
    # el título salía en 4 renglones, no 3, y el primero quedaba arriba del 14 % (28/10/2026)
    extra = 0.38 if bloques else 0.12
    if mayusculas:
        texto = texto.upper()
    medidor = _medidor(fuente, round(fuente_px)) if fuente and Path(fuente).exists() else None

    def ancho(renglon):  # en em
        letras = medidor.getlength(renglon) / round(fuente_px) if medidor else len(renglon) * 0.56
        return letras + len(renglon) * interletra + len(renglon.split()) * extra

    renglones = [""]
    for palabra in texto.split():
        prueba = f"{renglones[-1]} {palabra}".strip()
        if ancho(prueba) * fuente_px <= max_ancho or not renglones[-1]:
            renglones[-1] = prueba
        else:
            renglones.append(palabra)
    caja = min(max_ancho, max(ancho(x) for x in renglones) * fuente_px)
    abajo = ALTO * float(str(base).rstrip("%")) / 100
    arriba = abajo - len(renglones) * (1.3 if bloques else 1.06) * fuente_px
    x0 = (ANCHO - caja) / 2
    return int(x0), int(max(0, arriba)), int(x0 + caja), int(abajo)


def cuadros(medio, n):
    """`n` cuadros repartidos de un video (o la foto, si es una imagen), en BGR."""
    import cv2

    medio = Path(medio)
    if medio.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        im = cv2.imread(str(medio))
        return [im] if im is not None else []
    cap = cv2.VideoCapture(str(medio))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    out = []
    for k in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((k + 0.5) * total / n))
        ok, im = cap.read()
        if ok:
            out.append(im)
    cap.release()
    return out


def a_lienzo(im, foco=(0.5, 0.5)):
    """Lleva el cuadro a 1080×1920 como `object-fit: cover` con `object-position: foco`."""
    import cv2

    h, w = im.shape[:2]
    s = max(ANCHO / w, ALTO / h)
    im = cv2.resize(im, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    h, w = im.shape[:2]
    x = int((w - ANCHO) * foco[0])
    y = int((h - ALTO) * foco[1])
    return im[y:y + ALTO, x:x + ANCHO]


def brillo(medios, caja, n=6, foco=(0.5, 0.5)):
    """Percentil 75 de la luminancia en `caja`, sobre `n` cuadros de cada medio.

    Se usa el p75 y no la media: un título se lee mal en cuanto una parte grande
    de su fondo es clara, aunque el resto sea oscuro.
    """
    x0, y0, x1, y1 = caja
    vals = []
    for medio in medios:
        for im in cuadros(medio, n):
            zona = a_lienzo(im, foco)[y0:y1, x0:x1]
            if zona.size:
                vals.append(float(np.percentile(luminancia(zona), 75)))
    return max(vals) if vals else 0.0


def tratamiento(lum):
    return "bloques" if lum >= UMBRAL_CLARO else "sombra"
