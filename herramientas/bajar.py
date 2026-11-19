"""Baja reels de Instagram en la mejor calidad disponible.

Uso:
    uv run python herramientas/bajar.py <url o id> [...] [--destino carpeta] [--forzar]
    uv run python herramientas/bajar.py --lista marcas/<marca>/biblioteca/reels.txt --destino marcas/<marca>/biblioteca/reels

Sin sesión, Instagram entrega 360-720p. Con la sesión de una cuenta (cookies),
llega a 1080p. Si existe secretos/instagram-cookies.txt (formato Netscape,
exportado del navegador por Fernando), se usa. Es una credencial de sesión: está
en .gitignore y este script nunca muestra su contenido.

Por cada reel escribe <id>.mp4 + <id>.info.json y avisa si quedó por debajo de 720p.
Con --forzar vuelve a bajar los que ya existen y se queda con el de más resolución.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, RAIZ, probar  # noqa: E402

COOKIES = RAIZ / "secretos" / "instagram-cookies.txt"
MINIMO = 720


def id_de(x):
    m = re.search(r"/(?:reel|reels|p)/([\w-]+)", x)
    return m.group(1) if m else x.strip().strip("/")


def bajar(rid, destino, forzar=False):
    final = destino / f"{rid}.mp4"
    previo = probar(final)["ancho"] if final.exists() else 0
    if final.exists() and not forzar:
        return final, previo, "ya estaba"
    tmp = destino / f"{rid}.nuevo.mp4"
    args = ["yt-dlp", "-q", "--no-warnings", "--no-progress",
            "-f", "bv*+ba/b", "-S", "res,fps", "--merge-output-format", "mp4",
            "--ffmpeg-location", str(Path(FFMPEG).parent),
            "--write-info-json", "-o", str(destino / f"{rid}.nuevo.%(ext)s"),
            f"https://www.instagram.com/reel/{rid}/"]
    if COOKIES.exists():
        args[1:1] = ["--cookies", str(COOKIES)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not tmp.exists():
        return final if final.exists() else None, previo, f"error: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode}"
    nuevo = probar(tmp)["ancho"]
    info_tmp = destino / f"{rid}.nuevo.info.json"
    if nuevo >= previo:
        tmp.replace(final)
        if info_tmp.exists():
            info_tmp.replace(destino / f"{rid}.info.json")
        return final, nuevo, ("mejoró" if previo and nuevo > previo else "nuevo" if not previo else "igual")
    tmp.unlink()
    info_tmp.unlink(missing_ok=True)
    return final, previo, "se quedó el anterior (era mejor)"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reels", nargs="*", help="URLs o ids")
    ap.add_argument("--lista", help="archivo con una URL por línea")
    ap.add_argument("--destino", default=".")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    ids = [id_de(x) for x in a.reels]
    if a.lista:
        ids += [id_de(l) for l in Path(a.lista).read_text(encoding="utf-8").splitlines() if l.strip()]
    destino = Path(a.destino)
    destino.mkdir(parents=True, exist_ok=True)
    print(f"sesión: {'sí (cookies)' if COOKIES.exists() else 'no: máximo 720p, a veces menos'}")
    bajos = 0
    for rid in ids:
        archivo, ancho, estado = bajar(rid, destino, a.forzar)
        aviso = "  ⚠ menos de 720p" if archivo and ancho < MINIMO else ""
        bajos += bool(aviso)
        print(f"  {rid}: {ancho or '—'} px de ancho · {estado}{aviso}")
    if bajos:
        print(f"{bajos} por debajo de {MINIMO}p: pedir el original o usar cookies (ver docstring).")


if __name__ == "__main__":
    main()
