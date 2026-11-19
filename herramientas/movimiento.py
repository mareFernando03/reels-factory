"""Mide el movimiento de cámara de un video y lo clasifica por tramos.

Uso:
    uv run python herramientas/movimiento.py <video> [--desde s] [--hasta s] [--json salida.json]

Por cada cuadro sigue puntos (goodFeaturesToTrack + flujo óptico Lucas-Kanade) y
estima el movimiento global de la cámara (estimateAffinePartial2D). Con eso arma
la trayectoria y separa:
    paneo   = la trayectoria suavizada (~0,5 s): el movimiento intencional
    temblor = la trayectoria menos la suavizada: el pulso, lo que hay que estabilizar
    nitidez = varianza del laplaciano (baja = movido o fuera de foco)

Cada medio segundo queda como:
    estable  cámara quieta y nítida
    paneo    movimiento lento e intencional: sirve como toma
    barrido  paneo rápido: sirve como transición natural entre tomas (acelerado)
    temblor  pulso de cámara en mano: se corrige con `estabilizar` en preparar_clips.py
    borroso  fuera de foco o movido: se evita
Los puntos se toman de los bordes del cuadro (donde suele estar el fondo), para que
la persona moviendo los brazos no cuente como movimiento de cámara.
Escribe <video>.movimiento.json y <video>.movimiento.png (gráfico) junto al video
o donde diga --json.
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ANCHO = 360          # se analiza achicado: rápido y con umbrales comparables entre fuentes
VENTANA_S = 0.5
# Umbrales (calibrados con la biblioteca de Salón Demo, ver conocimiento/07 › movimiento)
PANEO = 15.0         # % del ancho por segundo: de acá para arriba hay paneo
BARRIDO = 50.0       # % del ancho por segundo: paneo rápido (latigazo)
TEMBLOR = 0.65       # % del ancho, RMS del pulso (trípode ~0,2; mano firme ~0,5)
NITIDEZ = 45.0       # varianza del laplaciano a 360 px de ancho


CORTE = 50  # diferencia media de gris (0-255) entre cuadros seguidos a partir de la cual es un corte


def suavizar(x, n):
    if n < 2:
        return x.copy()
    k = np.ones(n) / n
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, k, mode="valid")


def borde(forma):
    """Máscara de los bordes (22 % a los costados, 15 % arriba): ahí suele estar el fondo."""
    h, w = forma
    m = np.zeros((h, w), np.uint8)
    m[:, : int(w * 0.22)] = 255
    m[:, int(w * 0.78):] = 255
    m[: int(h * 0.15), :] = 255
    return m


def analizar_movimiento(video, desde=0.0, hasta=None):
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if desde:
        cap.set(cv2.CAP_PROP_POS_MSEC, desde * 1000)
    previo, puntos = None, None
    dx, dy, da, nit, ts = [], [], [], [], []
    t = desde
    while True:
        ok, cuadro = cap.read()
        if not ok or (hasta is not None and t > hasta):
            break
        h, w = cuadro.shape[:2]
        gris = cv2.cvtColor(cv2.resize(cuadro, (ANCHO, int(h * ANCHO / w))), cv2.COLOR_BGR2GRAY)
        nit.append(cv2.Laplacian(gris, cv2.CV_64F).var())
        mov = (0.0, 0.0, 0.0)
        # un corte de plano no es movimiento de cámara: sin esto, en el análisis del video
        # entero cada corte cuenta como un salto enorme (medido: 65-91 en los cortes del
        # reel de los pochoclos contra 18-40 dentro de una toma movida)
        corte = previo is not None and float(np.mean(cv2.absdiff(previo, gris))) > CORTE
        if previo is not None and not corte and puntos is not None and len(puntos) >= 8:
            sig, st, _ = cv2.calcOpticalFlowPyrLK(previo, gris, puntos, None)
            buenos = st.reshape(-1) == 1
            if buenos.sum() >= 8:
                m, _ = cv2.estimateAffinePartial2D(puntos[buenos], sig[buenos])
                if m is not None:
                    mov = (m[0, 2], m[1, 2], np.degrees(np.arctan2(m[1, 0], m[0, 0])))
        dx.append(mov[0]); dy.append(mov[1]); da.append(mov[2]); ts.append(t)
        puntos = cv2.goodFeaturesToTrack(gris, maxCorners=200, qualityLevel=0.01, minDistance=15,
                                         mask=borde(gris.shape))
        if puntos is None or len(puntos) < 20:  # bordes lisos: usar todo el cuadro
            puntos = cv2.goodFeaturesToTrack(gris, maxCorners=200, qualityLevel=0.01, minDistance=15)
        previo = gris
        t += 1 / fps
    cap.release()
    if not ts:
        return {"fps": fps, "tramos": [], "ventanas": []}

    dx, dy, da = (np.array(v) for v in (dx, dy, da))
    nit, ts = np.array(nit), np.array(ts)
    n = max(3, int(round(fps * VENTANA_S)))
    tray = np.stack([np.cumsum(dx), np.cumsum(dy)], axis=1) / ANCHO * 100  # % del ancho
    ang = np.cumsum(da)
    suave = np.stack([suavizar(tray[:, 0], n), suavizar(tray[:, 1], n)], axis=1)
    pulso = tray - suave
    pulso_ang = ang - suavizar(ang, n)
    vel = np.linalg.norm(np.diff(suave, axis=0, prepend=suave[:1]), axis=1) * fps  # %/s

    ventanas = []
    t0 = ts[0]
    while t0 < ts[-1]:
        sel = (ts >= t0) & (ts < t0 + VENTANA_S)
        if sel.sum() >= 2:
            temblor = float(np.sqrt(np.mean(np.sum(pulso[sel] ** 2, axis=1)) + np.mean(pulso_ang[sel] ** 2) * 0.25))
            paneo = float(np.mean(vel[sel]))
            nitidez = float(np.median(nit[sel]))
            if paneo > BARRIDO:
                clase = "barrido"
            elif temblor > TEMBLOR:
                clase = "temblor"
            elif nitidez < NITIDEZ:
                clase = "borroso"
            elif paneo > PANEO:
                clase = "paneo"
            else:
                clase = "estable"
            ventanas.append({"t": round(float(t0), 2), "clase": clase, "temblor": round(temblor, 2),
                             "paneo": round(paneo, 1), "nitidez": round(nitidez, 0)})
        t0 += VENTANA_S

    tramos = []
    for v in ventanas:
        if tramos and tramos[-1]["clase"] == v["clase"]:
            tramos[-1]["fin"] = round(v["t"] + VENTANA_S, 2)
        else:
            tramos.append({"inicio": v["t"], "fin": round(v["t"] + VENTANA_S, 2), "clase": v["clase"]})
    estables = [v for v in ventanas if v["clase"] in ("estable", "paneo")]
    if not ventanas:  # video de menos de medio segundo útil (p. ej. un cuadro fijo largo)
        return {"fps": round(fps, 2), "resumen": {"temblor_medio": None, "proporcion_estable": None},
                "tramos": [], "ventanas": []}
    return {
        "fps": round(fps, 2),
        "resumen": {
            "temblor_medio": round(float(np.mean([v["temblor"] for v in ventanas])), 2),
            "proporcion_estable": round(len(estables) / len(ventanas), 2),  # estable + paneo lento
        },
        "tramos": tramos,
        "ventanas": ventanas,
    }


def movimiento_de(video):
    """Análisis del video entero, guardado junto a él en <video>.movimiento.json.

    Se calcula una sola vez por fuente: preparar_clips.py (estabilizar, cámara lenta) e
    inventario.py la recortan por tramo con `tramo()`. La firma (tamaño, fecha y versión
    de este código) invalida la caché si cambia el video o la forma de medir.
    """
    import hashlib
    video = Path(video)
    st = video.stat()
    firma = {"tamaño": st.st_size, "fecha": st.st_mtime_ns,
             "codigo": hashlib.sha1(Path(__file__).read_bytes()).hexdigest()[:12]}
    cache = video.with_suffix(".movimiento.json")
    if cache.exists():
        try:
            datos = json.loads(cache.read_text(encoding="utf-8"))
            if datos.get("firma") == firma:
                return datos
        except (json.JSONDecodeError, OSError):
            pass
    datos = {**analizar_movimiento(video), "firma": firma}
    cache.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return datos


def tramo(datos, desde, hasta):
    """Las ventanas de medio segundo del análisis completo que caen en [desde, hasta].

    Primero las que caen enteras adentro: una ventana de borde puede traer el corte de
    plano anterior, y si los dos planos se parecen (mesa blanca → bowl en los pochoclos)
    no se distingue de un barrido. Si el tramo es más corto, las que tienen el centro
    adentro, y si tampoco hay, la más cercana.
    """
    vs = datos["ventanas"]
    enteras = [v for v in vs if v["t"] >= desde - 0.01 and v["t"] + VENTANA_S <= hasta + 0.01]
    if enteras:
        return enteras
    centro = [v for v in vs if desde <= v["t"] + VENTANA_S / 2 <= hasta]
    if centro or not vs:
        return centro
    medio = (desde + hasta) / 2
    return [min(vs, key=lambda v: abs(v["t"] + VENTANA_S / 2 - medio))]


COLORES = {"estable": (120, 200, 120), "paneo": (200, 220, 140), "barrido": (230, 180, 90),
           "temblor": (90, 90, 230), "borroso": (170, 170, 170)}


def grafico(datos, destino):
    """Bandas por clase + curvas de temblor (rojo), paneo (azul) y nitidez (gris)."""
    vs = datos["ventanas"]
    if not vs:
        return None
    W, H, m = 1200, 320, 40
    img = np.full((H, W, 3), 255, np.uint8)
    t_ini, t_fin = vs[0]["t"], vs[-1]["t"] + VENTANA_S
    x = lambda t: int(m + (t - t_ini) / (t_fin - t_ini) * (W - 2 * m))  # noqa: E731
    for v in vs:
        cv2.rectangle(img, (x(v["t"]), 30), (x(v["t"] + VENTANA_S), 50), COLORES[v["clase"]], -1)
    for clave, tope, color in (("temblor", TEMBLOR * 3, (40, 40, 220)), ("paneo", PANEO * 3, (200, 120, 30)),
                               ("nitidez", NITIDEZ * 8, (110, 110, 110))):
        pts = [(x(v["t"] + VENTANA_S / 2), int(H - m - min(v[clave] / tope, 1) * (H - 2 * m - 30))) for v in vs]
        cv2.polylines(img, [np.array(pts, np.int32)], False, color, 2, cv2.LINE_AA)
    for k, (clase, c) in enumerate(COLORES.items()):
        cv2.rectangle(img, (m + k * 140, 6), (m + k * 140 + 14, 20), c, -1)
        cv2.putText(img, clase, (m + k * 140 + 20, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    s = t_ini
    while s <= t_fin:
        cv2.putText(img, f"{s:.0f}s", (x(s) - 8, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        s += 1 if t_fin - t_ini <= 30 else 5
    cv2.imwrite(str(destino), img)
    return Path(destino)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video")
    ap.add_argument("--desde", type=float, default=0.0)
    ap.add_argument("--hasta", type=float)
    ap.add_argument("--json")
    a = ap.parse_args()
    video = Path(a.video)
    if a.desde or a.hasta is not None or a.json:  # un tramo o un destino a mano: sin caché
        datos = analizar_movimiento(video, a.desde, a.hasta)
        destino = Path(a.json) if a.json else video.with_suffix(f".movimiento-{a.desde:g}-{a.hasta or 'fin'}.json")
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        datos = movimiento_de(video)
        destino = video.with_suffix(".movimiento.json")
    png = grafico(datos, destino.with_suffix(".png"))
    print(f"temblor medio {datos['resumen']['temblor_medio']} · "
          f"{datos['resumen']['proporcion_estable']:.0%} estable → {destino.name}, {png.name if png else '—'}")
    for tr in datos["tramos"]:
        print(f"  {tr['inicio']:6.2f}-{tr['fin']:6.2f}s  {tr['clase']}")


if __name__ == "__main__":
    main()
