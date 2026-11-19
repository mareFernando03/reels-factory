"""Render de una composición HyperFrames: la versión fijada y ffmpeg en el PATH, en un solo lugar.

Lo usan fabrica.py, armar_historia.py, armar_foto.py y verificar.py (`hyperframes check`).
"""

import os
import subprocess
from pathlib import Path

from comun import FFMPEG

HYPERFRAMES = "hyperframes@0.8.113"   # sigue en 0.x y cambia seguido: se sube a mano y se prueba


def entorno():
    """El entorno del proceso con el ffmpeg de winget adelante en el PATH (las shells viejas no lo ven)."""
    return {**os.environ, "PATH": str(Path(FFMPEG).parent) + os.pathsep + os.environ.get("PATH", "")}


def npx(args, render_dir):
    """Corre `npx hyperframes <args>` en la carpeta de la composición."""
    return subprocess.run(f"npx --yes {HYPERFRAMES} {args}", cwd=render_dir, shell=True, env=entorno(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


PESO_MAX_MB = 92        # verificar.py pide < 100 MB; margen para el audio y el contenedor
BITRATE_MAX = 25_000    # kbps: en reels cortos no hace falta más (delivery anda por ~12 Mbps)


def bitrate_para(duracion, peso_mb=PESO_MAX_MB, audio_kbps=192):
    """kbps de video para que `duracion` segundos no pasen de `peso_mb` (un reel de 90 s en delivery
    pesaba 140 MB). Los cortos quedan en BITRATE_MAX, que es más de lo que usa delivery."""
    return int(min(BITRATE_MAX, peso_mb * 8000 / max(1.0, duracion) - audio_kbps))


def duracion_composicion(render_dir):
    import re
    html = (Path(render_dir) / "index.html").read_text(encoding="utf-8")
    m = re.search(r'data-composition-id="main"[^>]*data-duration="([\d.]+)"', html)
    return float(m.group(1)) if m else 0.0


def hyperframes(render_dir, destino, calidad="delivery", fps=None):
    """Renderiza render_dir/index.html a `destino` (relativo a render_dir). Devuelve (ok, error).
    Por encima de ~45 s, el bitrate se topea para que el MP4 quede debajo de PESO_MAX_MB."""
    dur = duracion_composicion(render_dir)
    tope = f" --video-bitrate {bitrate_para(dur)}k" if bitrate_para(dur) < 12_000 else ""
    res = npx(f"render -q {calidad}{tope}{f' --fps {fps}' if fps else ''} -o {destino} --quiet", render_dir)
    return res.returncode == 0, (res.stderr or res.stdout).strip()[-600:]
