"""Temas libres de derechos para el modo `archivo`: buscar, bajar, sugerir y no repetir.

Todos los reels con la misma música se ven iguales (pedido de Fernando, 04/10/2026). Por eso
cada reel lleva un tema distinto del catálogo, y verificar.py avisa si uno ya se usó en otro
pedido.

Fuente: Mixkit (de Envato). Su «Stock Music Free License» permite uso comercial, también en
redes sociales y avisos, sin atribución. Hay temas con licencia restringida (solo personal):
este script lee la licencia de cada tema en la página y baja solo los libres. Pixabay Music
bloquea las descargas automáticas (Cloudflare).

Uso:
    uv run python herramientas/musica.py --buscar funk           # temas de una etiqueta de Mixkit
    uv run python herramientas/musica.py --bajar 872 1087 --tag funk
    uv run python herramientas/musica.py --sugerir 100 --rango 95 110 [--voz]
    uv run python herramientas/musica.py --usados

El catálogo (`musica/catalogo.yaml`) se versiona; los MP3 (`musica/libre/`) no: se vuelven a bajar
desde `url`. `voz_db` es cuánto suena la voz cantada respecto del tema (separar.py sobre 20 s del
medio): menos de -35 dB es instrumental. Debajo de alguien que habla, mejor instrumental.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "musica" / "catalogo.yaml"
LIBRE = RAIZ / "musica" / "libre"
LICENCIA_LIBRE = "Mixkit Stock Music Free License"
INSTRUMENTAL_DB = -35.0
AGENTE = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130"}


def leer():
    return yaml.safe_load(CATALOGO.read_text(encoding="utf-8")) or {} if CATALOGO.exists() else {}


def guardar(cat):
    cabecera = ("# Temas libres de derechos para el modo `archivo` (herramientas/musica.py).\n"
                "# Los MP3 van en musica/libre/ (fuera de git); se vuelven a bajar desde `url`.\n")
    CATALOGO.write_text(cabecera + yaml.safe_dump(cat, allow_unicode=True, sort_keys=True, width=200), encoding="utf-8")


def mixkit(tag):
    """Los temas de una etiqueta de Mixkit: {id: {titulo, artista, genero, duracion, licencia, url}}."""
    pedido = urllib.request.Request(f"https://mixkit.co/free-stock-music/tag/{tag}/", headers=AGENTE)
    html = urllib.request.urlopen(pedido, timeout=30).read().decode("utf-8")
    temas = {}

    def recorrer(x):
        if isinstance(x, dict):
            if x.get("@type") == "MusicRecording":
                tid = x["url"].split("/")[-1].split(".")[0]
                temas[tid] = {"titulo": x["name"], "artista": x["byArtist"], "genero": x.get("genre"),
                              "duracion": x.get("duration"), "licencia": x.get("copyrightNotice"), "url": x["url"]}
            for v in x.values():
                recorrer(v)
        elif isinstance(x, list):
            for v in x:
                recorrer(v)

    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            recorrer(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
    return temas


def medir(archivo):
    """bpm (como analizar_audio.py) y cuánto suena la voz cantada (dB respecto del tema)."""
    import librosa
    import numpy as np
    import separar
    y, sr = librosa.load(str(archivo), sr=22050, mono=True)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr)
    est, _ = librosa.load(str(archivo), sr=separar.SR, mono=False)
    est = est if est.ndim == 2 else np.stack([est, est])
    a = int(est.shape[1] * 0.4)
    trozo = est[:, a:a + 20 * separar.SR]
    voz = separar.separar(trozo)
    rel = 20 * np.log10(np.sqrt(np.mean(voz ** 2)) / (np.sqrt(np.mean(trozo ** 2)) + 1e-12) + 1e-12)
    return round(float(np.atleast_1d(tempo)[0]), 1), round(float(rel), 1)


def usados():
    """{fuente: [pedidos]} de los guiones en modo archivo."""
    out = {}
    for g in sorted((RAIZ / "pedidos").glob("*/plan/guion.yaml")):
        musica = (yaml.safe_load(g.read_text(encoding="utf-8")) or {}).get("musica") or {}
        if isinstance(musica, dict) and musica.get("modo") == "archivo" and musica.get("fuente"):
            out.setdefault(Path(musica["fuente"]).as_posix(), []).append(g.parent.parent.name)
    return out


def sugerir(bpm, rango=None, con_voz=False, cat=None):
    """Temas sin usar, ordenados por cercanía de bpm (dentro de `rango` si se da)."""
    cat = cat if cat is not None else leer()
    ya = usados()
    lo, hi = rango or (bpm * 0.92, bpm * 1.08)
    out = []
    for tid, t in cat.items():
        if t["archivo"] in ya or not lo <= t["bpm"] <= hi:
            continue
        if con_voz and t["voz_db"] > INSTRUMENTAL_DB:
            continue
        out.append((abs(t["bpm"] - bpm), tid, t))
    return [(tid, t) for _, tid, t in sorted(out)]


def bajar(ids, tag):
    temas = mixkit(tag)
    cat = leer()
    LIBRE.mkdir(parents=True, exist_ok=True)
    for tid in ids:
        t = temas.get(tid)
        if not t:
            print(f"  {tid}: no está en la etiqueta «{tag}»")
            continue
        if t["licencia"] != LICENCIA_LIBRE:
            print(f"  {tid} «{t['titulo']}»: licencia «{t['licencia']}», no se baja")
            continue
        destino = LIBRE / f"mixkit-{tid}.mp3"
        if not destino.exists():
            destino.write_bytes(urllib.request.urlopen(urllib.request.Request(t["url"], headers=AGENTE), timeout=60).read())
        bpm, voz = medir(destino)
        cat[tid] = {**t, "archivo": destino.relative_to(RAIZ).as_posix(), "bpm": bpm, "voz_db": voz}
        print(f"  {tid} «{t['titulo']}» {bpm} bpm, voz {voz} dB")
    guardar(cat)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--buscar", metavar="TAG")
    ap.add_argument("--bajar", nargs="+", metavar="ID")
    ap.add_argument("--tag", default="pop")
    ap.add_argument("--sugerir", type=float, metavar="BPM")
    ap.add_argument("--rango", type=float, nargs=2)
    ap.add_argument("--voz", action="store_true", help="el reel tiene voz: solo instrumentales")
    ap.add_argument("--usados", action="store_true")
    a = ap.parse_args()
    if a.buscar:
        cat = leer()
        for tid, t in mixkit(a.buscar).items():
            marca = "en catálogo" if tid in cat else ("" if t["licencia"] == LICENCIA_LIBRE else "RESTRINGIDA")
            print(f"{tid:>5}  {t['titulo'][:30]:30} {str(t['genero'])[:14]:14} {t['duracion']:8} {marca}")
    elif a.bajar:
        bajar(a.bajar, a.tag)
    elif a.sugerir:
        for tid, t in sugerir(a.sugerir, a.rango, a.voz):
            print(f"{tid:>5}  {t['titulo'][:30]:30} {t['bpm']:6} bpm  voz {t['voz_db']:6} dB  {t['archivo']}")
    elif a.usados:
        for fuente, pedidos in usados().items():
            print(f"{fuente}: {', '.join(pedidos)}" + ("   ← REPETIDO" if len(pedidos) > 1 else ""))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
