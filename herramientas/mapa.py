"""Mapas animados para los relatos: la tierra, la grilla y las rutas de un viaje, en SVG.

Lo usa armar_pop.py en los insertos `{tipo: mapa}` (13-divulgacion.md › 6: el mapa de una ruta
con fechas es un gráfico propio, sin problema de derechos, y es lo que hizo crecer a una cuenta de
divulgación del tamaño de Historia Breve). Las costas salen de Natural Earth 110m (dominio público,
`herramientas/datos/ne_110m_land.geojson`).

Proyección Mercator: un rango de longitudes ocupa el ancho del cuadro y la latitud del centro
queda a la mitad del alto; el resto se llena con lo que haya arriba y abajo (un reel es vertical,
así que se ve más norte y sur que en un mapa apaisado).
"""

import json
import math
from functools import lru_cache
from pathlib import Path

TIERRA = Path(__file__).parent / "datos" / "ne_110m_land.geojson"
ANCHO, ALTO = 1080, 1920


def _merc(lat):
    lat = max(min(lat, 85.0), -85.0)
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def vista(lon=(-115.0, 15.0), centro_lat=20.0, ancho=ANCHO, alto=ALTO):
    """Parámetros de la proyección: `lon` (oeste, este) llena el ancho; `centro_lat` va al medio."""
    escala = ancho / math.radians(lon[1] - lon[0])
    return {"lon0": lon[0], "escala": escala, "y0": alto / 2 + escala * _merc(centro_lat), "ancho": ancho, "alto": alto}


def proyectar(lon, lat, v):
    """(x, y) en px del cuadro."""
    return (v["escala"] * math.radians(lon - v["lon0"]), v["y0"] - v["escala"] * _merc(lat))


@lru_cache(maxsize=1)
def _poligonos():
    datos = json.loads(TIERRA.read_text(encoding="utf-8"))
    out = []
    for f in datos["features"]:
        g = f["geometry"]
        partes = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        out += [anillo for poligono in partes for anillo in poligono]
    return out


def tierra(v, margen=200):
    """`d` de un path con las costas que caen en el cuadro (más un margen)."""
    trazos = []
    for anillo in _poligonos():
        pts = [proyectar(lon, lat, v) for lon, lat in anillo]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if max(xs) < -margen or min(xs) > v["ancho"] + margen or max(ys) < -margen or min(ys) > v["alto"] + margen:
            continue
        trazos.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(trazos)


def grilla(v, paso=15):
    """`d` de los meridianos y paralelos cada `paso` grados."""
    trazos = []
    for lon in range(-180, 181, paso):
        x, _ = proyectar(lon, 0, v)
        if 0 <= x <= v["ancho"]:
            trazos.append(f"M{x:.1f},0V{v['alto']}")
    for lat in range(-75, 76, paso):
        _, y = proyectar(0, lat, v)
        if 0 <= y <= v["alto"]:
            trazos.append(f"M0,{y:.1f}H{v['ancho']}")
    return "".join(trazos)


def ruta(de, a, v, curva=0.18):
    """Una ruta curva de `de` a `a` ([lon, lat]): (d, largo en px, punto final).

    Es una cuadrática con el control corrido hacia la izquierda del avance en `curva` × la
    distancia (positivo: hacia el norte si va de oeste a este). El largo sirve para dibujarla
    de a poco con stroke-dashoffset."""
    (x0, y0), (x1, y1) = proyectar(*de, v), proyectar(*a, v)
    dx, dy = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2 + dy * curva, (y0 + y1) / 2 - dx * curva
    largo, previo = 0.0, (x0, y0)
    for i in range(1, 65):
        t = i / 64
        p = ((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1)
        largo += math.dist(previo, p)
        previo = p
    return f"M{x0:.1f},{y0:.1f}Q{cx:.1f},{cy:.1f} {x1:.1f},{y1:.1f}", largo, (x1, y1)
