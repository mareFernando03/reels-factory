"""Inventario de los crudos de un pedido (fotos y videos).

Uso:
    uv run python herramientas/inventario.py pedidos/<pedido> [--sin-habla]

Escribe analisis/crudos.json y una hoja de contactos por crudo en
analisis/fotogramas/crudo-*.jpg. Por video mide duración, orientación,
silencios, (opcional) lo hablado y el movimiento de cámara por tramos
(movimiento.py: estable / paneo / barrido / temblor / borroso); por foto, tamaño y
nitidez. Marca `baja_resolucion` si el ancho útil es menor a 720 px (pedir el
original como Documento). Qué tomas sirven lo decide Claude mirando las hojas y los
tramos, en el campo "eleccion".
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, correr, fotograma, hoja_de_contactos, probar, transcribir  # noqa: E402
from movimiento import movimiento_de  # noqa: E402

FOTOS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEOS = {".mp4", ".mov", ".m4v", ".webm", ".3gp"}


def nitidez(img_path):
    """Varianza del laplaciano: < ~60 suele ser una foto movida o fuera de foco."""
    import cv2
    im = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    return round(float(cv2.Laplacian(im, cv2.CV_64F).var()), 1) if im is not None else None


def silencios(video, umbral_db=-35, min_s=0.4):
    err = correr([FFMPEG, "-v", "info", "-i", str(video), "-af",
                  f"silencedetect=noise={umbral_db}dB:d={min_s}", "-f", "null", "-"]).stderr
    ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    fin = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return [[round(a, 2), round(b, 2)] for a, b in zip(ini, fin)]


def inventariar(pedido, con_habla=True):
    crudos = sorted(p for p in (pedido / "entrada" / "crudos").iterdir()
                    if p.suffix.lower() in FOTOS | VIDEOS)
    dir_fot = pedido / "analisis" / "fotogramas"
    dir_fot.mkdir(parents=True, exist_ok=True)
    items = []
    for c in crudos:
        rel = c.relative_to(pedido).as_posix()
        if c.suffix.lower() in FOTOS:
            import cv2
            im = cv2.imread(str(c))
            alto, ancho = im.shape[:2]
            items.append({"archivo": rel, "tipo": "foto", "ancho": ancho, "alto": alto,
                          "vertical": alto > ancho, "nitidez": nitidez(c),
                          "baja_resolucion": min(ancho, alto) < 720})
            continue
        meta = probar(c)
        n = max(2, min(12, int(meta["duracion"])))
        paso = meta["duracion"] / n
        tiempos = [round(paso * (k + 0.5), 2) for k in range(n)]
        fotos = [fotograma(c, t, dir_fot / f"crudo-{c.stem}-{k:02d}.jpg", ancho=240)
                 for k, t in enumerate(tiempos)]
        hoja = hoja_de_contactos(fotos, dir_fot / f"crudo-{c.stem}.jpg",
                                 [f"{t:.1f}s" for t in tiempos])
        for f in fotos:
            f.unlink(missing_ok=True)
        items.append({
            "archivo": rel, "tipo": "video", **meta,
            "vertical": meta["alto"] > meta["ancho"],
            "silencios": silencios(c) if meta["audio"] else [],
            "habla": transcribir(c) if (meta["audio"] and con_habla) else [],
            "baja_resolucion": min(meta["ancho"], meta["alto"]) < 720,
            "movimiento": (lambda m: {**m["resumen"], "tramos": m["tramos"]})(movimiento_de(c)),
            "hoja": hoja.relative_to(pedido / "analisis").as_posix() if hoja else None,
        })
    return {"crudos": items,
            "eleccion": []}  # Claude: [{archivo, in, out, por_que}] en orden sugerido


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--sin-habla", action="store_true")
    a = ap.parse_args()
    pedido = Path(a.pedido)
    datos = inventariar(pedido, con_habla=not a.sin_habla)
    destino = pedido / "analisis" / "crudos.json"
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    fotos = sum(1 for i in datos["crudos"] if i["tipo"] == "foto")
    print(f"{len(datos['crudos'])} crudos ({fotos} fotos, "
          f"{len(datos['crudos']) - fotos} videos) → {destino}")
    for i in datos["crudos"]:
        extra = (f"nitidez {i['nitidez']}" if i["tipo"] == "foto"
                 else f"{i['duracion']}s, {len(i['silencios'])} silencios, "
                      f"{i['movimiento']['proporcion_estable']:.0%} estable")
        extra += "  ⚠ menos de 720p" if i["baja_resolucion"] else ""
        print(f"  {i['archivo']}: {i['ancho']}x{i['alto']} {extra}")


if __name__ == "__main__":
    main()
