"""Analiza una canción o audio para armar el reel a su ritmo.

Uso:
    uv run python herramientas/analizar_audio.py <audio|video|url de reel> --largo 18 [--letra] [--json salida.json] [--bpm 156]

Sirve para los tres modos de música (ver conocimiento/09-audio.md):
    archivo    tema libre de derechos: se mezcla en el MP4 desde `inicio`
    instagram  audio de Instagram (viral, gracioso, una canción): NO va en el MP4;
               se arma el reel a su ritmo y Ana lo elige en la app arrancando en `inicio`
Con una URL de reel baja solo el audio (bajar.py) para analizarlo.

Devuelve:
    bpm y beats (librosa), con la fase del compás estimada (tiempos 1 de cada 4)
    tramos: los mejores `--largo` segundos que arrancan en un tiempo 1 (energía alta y
            pareja, con un arranque marcado), con la frase de la letra que suena ahí
    letra:  frases con tiempo (Whisper), para que Ana ubique el arranque en la app
            por la letra, que Instagram muestra al elegir el tramo
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from comun import transcribir  # noqa: E402


LEIBLES = {".wav", ".flac", ".ogg", ".mp3", ".aiff", ".aif"}  # los que abre soundfile


def necesita_extraer(fuente):
    """Un video (mp4, mov, webm…) se pasa antes a WAV con ffmpeg: soundfile no lo abre."""
    return Path(fuente).suffix.lower() not in LEIBLES


def cargar(fuente):
    import librosa
    if str(fuente).startswith("http"):
        from bajar import id_de
        import subprocess
        tmp = Path(tempfile.mkdtemp())
        rid = id_de(fuente)
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "ba", "-x", "--audio-format", "wav",
                        "-o", str(tmp / f"{rid}.%(ext)s"), f"https://www.instagram.com/reel/{rid}/"], check=True)
        fuente = next(tmp.glob(f"{rid}.*"))
    if necesita_extraer(fuente):
        from comun import FFMPEG, correr
        wav = Path(tempfile.mkdtemp()) / f"{Path(fuente).stem}.wav"
        correr([FFMPEG, "-y", "-v", "error", "-i", str(fuente), "-vn", "-ac", "1", str(wav)])
        y, sr = librosa.load(str(wav), sr=22050, mono=True)
        return y, sr, Path(fuente)
    y, sr = librosa.load(str(fuente), sr=22050, mono=True)
    return y, sr, Path(fuente)


def analizar(fuente, largo, con_letra=False, bpm_pista=None):
    import librosa
    y, sr, archivo = cargar(fuente)
    dur = len(y) / sr
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    # bpm_pista: el tempo verificado contra los cortes de la referencia (referencia.json):
    # librosa solo puede elegir mal la octava («Pump It»: 103 en vez de 156)
    tempo, cuadros = librosa.beat.beat_track(onset_envelope=onset, sr=sr, start_bpm=bpm_pista or 120.0)
    bpm = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(cuadros, sr=sr)
    # fase del compás: la posición (mod 4) con más ataque es el tiempo 1
    fuerza = onset[np.clip(cuadros, 0, len(onset) - 1)]
    fase = int(np.argmax([fuerza[k::4].mean() if len(fuerza[k::4]) else 0 for k in range(4)]))
    tiempos_1 = beats[fase::4]

    rms = librosa.feature.rms(y=y)[0]
    t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    letra = []
    if con_letra:
        letra = transcribir(archivo)

    tramos = []
    for s in tiempos_1:
        if s + largo > dur + 0.05:
            break
        sel = (t_rms >= s) & (t_rms < s + largo)
        if not sel.any():
            continue
        energia = float(rms[sel].mean())
        parejo = 1.0 - float(rms[sel].std() / (rms[sel].mean() + 1e-9)) * 0.3
        arranque = float(onset[librosa.time_to_frames(s, sr=sr)]) / (onset.max() + 1e-9)
        tramos.append({"inicio": round(float(s), 2), "puntaje": round(float(energia * parejo * (1 + 0.5 * arranque)), 5)})
    tramos.sort(key=lambda x: -x["puntaje"])
    mejores = []
    for tr in tramos:  # los 3 mejores que no se pisen
        if all(abs(tr["inicio"] - m["inicio"]) >= largo / 2 for m in mejores):
            frase = next((f["texto"] for f in letra if f["inicio"] <= tr["inicio"] + 0.5 < f["fin"] + 1.5), None)
            mejores.append({**tr, "fin": round(tr["inicio"] + largo, 2), "letra_al_arrancar": frase})
        if len(mejores) == 3:
            break
    return {
        "archivo": archivo.name, "duracion": round(dur, 2), "bpm": round(bpm, 1),
        "beat_s": round(60 / bpm, 4), "beats": [round(float(b), 3) for b in beats],
        "tiempos_1": [round(float(b), 3) for b in tiempos_1], "largo_pedido": largo,
        "tramos": mejores, "letra": letra,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fuente")
    ap.add_argument("--largo", type=float, default=18.0, help="segundos de reel (sin el cierre)")
    ap.add_argument("--letra", action="store_true", help="transcribir letra/habla con Whisper")
    ap.add_argument("--json")
    ap.add_argument("--bpm", type=float, help="tempo de partida (el de referencia.json, ya verificado con los cortes)")
    a = ap.parse_args()
    d = analizar(a.fuente, a.largo, a.letra, a.bpm)
    destino = Path(a.json) if a.json else Path(d["archivo"]).with_suffix(".audio.json")
    destino.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{d['archivo']}: {d['duracion']} s, {d['bpm']} bpm (beat {d['beat_s']} s) → {destino}")
    for tr in d["tramos"]:
        print(f"  tramo {tr['inicio']:6.2f}-{tr['fin']:6.2f}s  puntaje {tr['puntaje']}"
              + (f"  letra: «{tr['letra_al_arrancar']}»" if tr.get("letra_al_arrancar") else ""))
    if d["letra"]:
        print(f"  letra: {len(d['letra'])} frases")


if __name__ == "__main__":
    main()
