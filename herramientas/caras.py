"""Caras en las tomas y altura de los títulos que no las tapan.

Detector: YuNet (modelos/face_detection_yunet_2023mar.onnx, opencv_zoo, licencia MIT),
con el FaceDetectorYN de OpenCV. OpenCV 5 ya no trae las cascadas Haar y la cascada
LBP de scikit-image no ve perfiles ni caras de tres cuartos (probado el 03/10/2026).

Cada cara se agranda a la cabeza (frente y pelo arriba, orejas a los costados): un
título pegado a la ceja también tapa. El pelo como sujeto (un rodete, los rulos de un
resultado) no se detecta: eso sigue siendo criterio al mirar la hoja de control.
"""

from pathlib import Path

import cv2

from legibilidad import ALTO, ANCHO, a_lienzo, cuadros, franja_titulo

MODELO = Path(__file__).parent / "modelos" / "face_detection_yunet_2023mar.onnx"
UMBRAL = 0.85   # falsos vistos: brazos y mechones (0,57-0,67), una oreja y un cuadro (0,76-0,77), una mano con
                #   un cepillo que se repetía en 4 cuadros (0,83, «la obra de arte»); caras reales: 0,87-0,95, de
                #   perfil y de tres cuartos 0,90-0,93. La geometría de los 5 puntos no sirve para filtrar: de
                #   perfil YuNet los amontona y una cara real parece tan rara como el cepillo
ESCALA = 0.5    # se detecta sobre 540×960: sobra para caras de más de ~40 px
ZONA = (0.14, 0.65)   # los títulos van entre el 14 % y el 65 % del alto (zona segura de reels)
MARGEN = 24     # px de aire entre el título y la cabeza
_det = None


def _detector():
    global _det
    if _det is None:
        _det = cv2.FaceDetectorYN.create(str(MODELO), "", (int(ANCHO * ESCALA), int(ALTO * ESCALA)), UMBRAL, 0.3, 50)
    return _det


def cabeza(caja):
    """De la caja de la cara a la de la cabeza: +60 % arriba, +25 % a los lados, +15 % abajo."""
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    return (x0 - 0.25 * w, y0 - 0.6 * h, x1 + 0.25 * w, y1 + 0.15 * h)


def _persisten(por_cuadro):
    """Las caras que aparecen en al menos 2 cuadros, más o menos en el mismo lugar. Un falso
    positivo (una oreja, un cuadro en la pared) sale en un cuadro suelto; una cara real se repite.
    Con un solo cuadro (una foto) no hay con qué comparar y cuenta todo."""
    if len(por_cuadro) < 2:
        return [c for cs in por_cuadro for c in cs]
    out = []
    for i, cs in enumerate(por_cuadro):
        for c in cs:
            cx, cy, lado = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2, max(c[2] - c[0], c[3] - c[1])
            if any(abs((o[0] + o[2]) / 2 - cx) < lado and abs((o[1] + o[3]) / 2 - cy) < lado
                   for j, os_ in enumerate(por_cuadro) if j != i for o in os_):
                out.append(c)
    return out


def detectar(medios, n=6, foco=(0.5, 0.5)):
    """Cajas de caras (x0, y0, x1, y1) en px del lienzo 1080×1920, en `n` cuadros de cada medio
    (solo las que se repiten en más de un cuadro: ver _persisten)."""
    det, cajas = _detector(), []
    for medio in medios:
        por_cuadro = []
        for im in cuadros(medio, n):
            peq = cv2.resize(a_lienzo(im, foco), (int(ANCHO * ESCALA), int(ALTO * ESCALA)))
            _, caras = det.detect(peq)
            por_cuadro.append([(x, y, x + w, y + h) for x, y, w, h in
                               ((v / ESCALA for v in c[:4]) for c in ([] if caras is None else caras))])
        cajas += _persisten(por_cuadro)
    return cajas


def con_push(cajas, push):
    """El acercamiento de la toma (`push`: de → a, alrededor de `origen`) mueve las caras:
    se toma la unión de la caja al principio y al final."""
    if not push:
        return cajas
    ox, oy = (float(v.rstrip("%")) / 100 for v in push.get("origen", "50% 50%").split())
    ox, oy = ox * ANCHO, oy * ALTO
    out = []
    for x0, y0, x1, y1 in cajas:
        pts = [(ox + (x - ox) * s, oy + (y - oy) * s) for s in (push["de"], push["a"]) for x, y in ((x0, y0), (x1, y1))]
        out.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)))
    return out


def cruce(caja, cajas, margen=MARGEN):
    """Área (px²) en que la caja de un título se mete en las cabezas, con margen."""
    x0, y0, x1, y1 = caja
    total = 0.0
    for c0, d0, c1, d1 in cajas:
        w = min(x1 + margen, c1) - max(x0 - margen, c0)
        h = min(y1 + margen, d1) - max(y0 - margen, d0)
        if w > 0 and h > 0:
            total += w * h
    return total


def elegir_base(texto, caras, preferida="62%", bloques=True, **medidas):
    """La línea inferior del título (en %) más cercana a `preferida` que no tapa ninguna cabeza,
    dentro de la zona segura. Si no hay lugar libre (un selfie muy cerca), se prioriza no tapar
    la cara (ojos, boca) aunque roce la cabeza. Devuelve (base, cruce con caras, con cabezas).
    Por defecto mide la caja en bloques, la más grande: si después va con sombra, igual queda libre.
    `medidas`: la fuente y el cuerpo de la marca (Estilo.medidas_titulo), para franja_titulo."""
    cabezas = [cabeza(c) for c in caras]
    caja = lambda b: franja_titulo(texto, f"{b}%", bloques, **medidas)  # noqa: E731
    alto = lambda b: (lambda c: c[3] - c[1])(caja(b))  # noqa: E731
    pref = float(str(preferida).rstrip("%"))
    candidatas = [b for b in range(int(ZONA[1] * 100), 0, -1) if b / 100 * ALTO - alto(b) >= ZONA[0] * ALTO]
    candidatas.sort(key=lambda b: abs(b - pref))
    if not candidatas:   # ni en la parte de abajo de la zona entra: armar_pop lo achica
        return f"{int(ZONA[1] * 100)}%", False, False
    puntaje = [(cruce(caja(b), caras), cruce(caja(b), cabezas), abs(b - pref), b) for b in candidatas]
    en_cara, en_cabeza, _, b = min(puntaje)
    return f"{b}%", en_cara, en_cabeza
