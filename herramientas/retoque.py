"""Retoque de fotos: afinar un contorno (un brazo) empujándolo hacia adentro, como el «licuar» de un editor.

Uso:
    uv run python herramientas/retoque.py <foto> <salida> --zona x,y,radio,dx,dy [--zona …]

En el guion va por toma, en una foto (preparar_clips.py la retoca antes de recortarla):
    afinar:
      - {x: 0.61, y: 0.718, radio: 0.06, dx: 0, dy: -0.012}

`x`, `y` es un punto del borde que se quiere correr (fracciones de la foto); `radio` (fracción del
ancho) es cuánto alrededor arrastra; `dx`, `dy` (fracción del ancho) es hacia dónde y cuánto se corre
ese borde. Lo que está del lado de afuera del borde se estira para llenar: conviene que ahí haya algo
liso (una remera negra) y no líneas rectas (ladrillos, un cartel), que se doblan. Corrimientos de hasta
un tercio del radio no pliegan la imagen. Pedido de Ana, 28/10/2026: «a estas dos achicar brazo».
"""

import argparse
import sys
from pathlib import Path

import numpy as np

PLIEGUE = 1 / 3   # corrimiento máximo / radio: más que esto, la imagen se pliega sobre sí misma


def mapa(alto, ancho, zonas):
    """Coordenadas de origen (map_x, map_y) para cv2.remap: cada píxel toma el que estaba
    `d·f(dist)` atrás, con f = (1 - (dist/radio)²)² (1 en el centro, 0 en el borde del radio)."""
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    mx, my = xx.copy(), yy.copy()
    for z in zonas:
        cx, cy, r = z["x"] * ancho, z["y"] * alto, z["radio"] * ancho
        dx, dy = z.get("dx", 0) * ancho, z.get("dy", 0) * ancho
        if np.hypot(dx, dy) > PLIEGUE * r:
            raise SystemExit(f"afinar: el corrimiento ({np.hypot(dx, dy):.0f} px) pasa de un tercio del "
                             f"radio ({r:.0f} px): la imagen se pliega. Agrandar el radio o correr menos.")
        d2 = ((mx - cx) ** 2 + (my - cy) ** 2) / r ** 2
        f = np.where(d2 < 1, (1 - d2) ** 2, 0).astype(np.float32)
        mx, my = mx - dx * f, my - dy * f
    return mx, my


def afinar(imagen, zonas):
    """La imagen (BGR) con cada zona corrida."""
    import cv2

    alto, ancho = imagen.shape[:2]
    mx, my = mapa(alto, ancho, zonas)
    return cv2.remap(imagen, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def afinar_archivo(src, zonas, destino):
    import cv2

    im = cv2.imread(str(src))
    if im is None:
        raise SystemExit(f"afinar: no pude leer {src}")
    cv2.imwrite(str(destino), afinar(im, zonas), [cv2.IMWRITE_JPEG_QUALITY, 97])
    return Path(destino)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("foto", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--zona", action="append", required=True, help="x,y,radio,dx,dy (fracciones)")
    a = ap.parse_args()
    zonas = [dict(zip(("x", "y", "radio", "dx", "dy"), map(float, z.split(",")))) for z in a.zona]
    print(afinar_archivo(a.foto, zonas, a.salida))


if __name__ == "__main__":
    sys.exit(main())
