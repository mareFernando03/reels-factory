"""Mide un reel de referencia: tomas, ritmo, beats, habla y fotogramas.

Uso:
    uv run python herramientas/analizar_referencia.py pedidos/<pedido>
    uv run python herramientas/analizar_referencia.py <video.mp4> --salida <dir>

Escribe analisis/referencia.json y analisis/fotogramas/ref-*.jpg + ref-hoja.jpg.
Lo que no se puede medir (estructura, textos en pantalla, transiciones) lo
completa Claude mirando la hoja de contactos, en el campo "lectura".
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, fotograma, hoja_de_contactos, probar, transcribir  # noqa: E402


def detectar_tomas(video, umbral=27.0):
    """Cortes con PySceneDetect. Devuelve [(inicio, fin), ...] en segundos."""
    from scenedetect import ContentDetector, detect

    escenas = detect(str(video), ContentDetector(threshold=umbral, min_scene_len=6))
    if not escenas:
        return [(0.0, probar(video)["duracion"])]
    return [(round(a.seconds, 3), round(b.seconds, 3)) for a, b in escenas]


def instante(a, b, duracion, margen=0.15):
    """El segundo del que se saca el fotograma de una toma: su mitad, sin pasarse del final del video.

    Una toma de uno o dos cuadros pegada al final (un fundido, un cuadro negro) tiene la mitad
    después del último cuadro que ffmpeg puede leer, y el análisis entero se caía."""
    return max(0.0, min(a + (b - a) / 2, duracion - margen))


def desajuste(cortes, bpm):
    """Cuánto se apartan los intervalos entre cortes de un número entero de beats (0 a 0,5).

    Mide en beats, no en segundos, y usa intervalos (no tiempos absolutos): no depende de
    dónde arranca la grilla. Un editor que corta en el compás da valores cerca de 0."""
    beat = 60 / bpm
    ints = [b - a for a, b in zip(cortes, cortes[1:])]
    errs = [abs(x - round(x)) for d in ints if (x := d / beat) >= 0.75]
    return sum(errs) / len(errs) if errs else 0.5


def bpm_por_cortes(cortes, candidatos, margen=0.08):
    """De los tempos candidatos, el que mejor explica los cortes de la referencia.

    librosa confunde octavas y relaciones 2/3 («Pump It»: 103 en vez de 156; los picos del
    tempograma casi empatan). Si el editor cortó en el beat, el tempo real deja los
    intervalos entre cortes en números enteros de beats. Con menos de 3 cortes no hay con
    qué decidir y queda el primer candidato. Solo cambia si mejora por más de `margen`."""
    if len(cortes) < 3 or not candidatos:
        return candidatos[0] if candidatos else None
    base = desajuste(cortes, candidatos[0])
    mejor = min(candidatos, key=lambda b: desajuste(cortes, b))
    return mejor if desajuste(cortes, mejor) < base - margen else candidatos[0]


def afinar(cortes, bpm, rango=0.04, paso=0.1):
    """El tempo cercano (±4 %) que deja los cortes más cerca de números enteros de beats.
    Es el que sirve para una grilla pareja en el guion: el de librosa puede correrse 2-3 %."""
    if len(cortes) < 3:
        return bpm
    pasos = int(bpm * rango / paso)
    return round(min((bpm + k * paso for k in range(-pasos, pasos + 1)),
                     key=lambda b: (round(desajuste(cortes, b), 3), abs(b - bpm))), 1)


def beats(video, cortes=()):
    """BPM y tiempos de beat del audio, con el tempo verificado contra los cortes.
    None si no hay audio."""
    import librosa
    import numpy as np

    wav = Path(video).with_suffix(".beats.wav")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1",
                    "-ar", "22050", str(wav)], check=True)
    try:
        y, sr = librosa.load(str(wav), sr=22050)
        if y.size == 0 or float(np.abs(y).max()) < 1e-3:
            return None
        oenv = librosa.onset.onset_strength(y=y, sr=sr)

        def seguir(inicio=120.0):
            tempo, frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, start_bpm=inicio)
            return float(np.atleast_1d(tempo)[0]), librosa.frames_to_time(frames, sr=sr)

        bpm0, t0 = seguir()
        # candidatos: el de librosa y sus parientes (×2, ×1/2, ×3/2, ×2/3), reajustados al audio
        pistas = [bpm0 * f for f in (2, 0.5, 1.5, 2 / 3) if 60 <= bpm0 * f <= 200]
        seguidos = {round(bpm0, 1): t0}
        for pista in pistas:
            b, t = seguir(pista)
            seguidos.setdefault(round(b, 1), t)
        elegido = bpm_por_cortes(list(cortes), list(seguidos))
        datos = {"bpm": elegido, "beats": [round(float(x), 3) for x in seguidos[elegido]],
                 "candidatos": {str(b): round(desajuste(list(cortes), b), 3) for b in seguidos}}
        if len(cortes) >= 3:
            datos["bpm_grilla"] = afinar(list(cortes), elegido)   # para `bpm` del guion sin musica.analisis
        if elegido != round(bpm0, 1):
            datos["aviso"] = (f"librosa dio {bpm0:.1f} bpm, pero los cortes caen en la grilla de "
                              f"{elegido} bpm: se usa ese (relación de octava o 2/3)")
        return datos
    finally:
        wav.unlink(missing_ok=True)


def analizar(video, dir_analisis, con_habla=True):
    dir_analisis = Path(dir_analisis)
    dir_fot = dir_analisis / "fotogramas"
    meta = probar(video)
    tomas = detectar_tomas(video)
    fotos, etiquetas, detalle = [], [], []
    for i, (a, b) in enumerate(tomas):
        p = fotograma(video, instante(a, b, meta["duracion"]), dir_fot / f"ref-{i:02d}.jpg")
        fotos.append(p)
        etiquetas.append(f"{i}: {a:.1f}-{b:.1f}s")
        detalle.append({"n": i, "inicio": a, "fin": b, "dur": round(b - a, 3),
                        "fotograma": p.relative_to(dir_analisis).as_posix()})
    hoja = hoja_de_contactos(fotos, dir_fot / "ref-hoja.jpg", etiquetas)
    durs = [t["dur"] for t in detalle]
    ritmo = beats(video, [t["inicio"] for t in detalle[1:]]) if meta["audio"] else None
    habla = transcribir(video) if (meta["audio"] and con_habla) else []
    return {
        "video": Path(video).name,
        "meta": meta,
        "tomas": detalle,
        "resumen": {
            "cantidad_tomas": len(detalle),
            "dur_media_toma": round(sum(durs) / len(durs), 2),
            "dur_min": min(durs), "dur_max": max(durs),
        },
        "musica": ritmo,
        "habla": habla,
        "hoja_de_contactos": hoja.relative_to(dir_analisis).as_posix() if hoja else None,
        "lectura": {  # lo completa Claude mirando la hoja de contactos
            "formato": None, "estructura": [], "textos_en_pantalla": [],
            "transiciones": None, "encuadres": None, "notas": None,
        },
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("objetivo", help="carpeta del pedido o un video")
    ap.add_argument("--salida", help="carpeta de análisis (si se pasa un video)")
    ap.add_argument("--sin-habla", action="store_true", help="no transcribir")
    a = ap.parse_args()
    obj = Path(a.objetivo)
    if obj.is_dir():
        cands = sorted((obj / "entrada").glob("referencia.*"))
        video = next((c for c in cands if c.suffix.lower() in (".mp4", ".mov", ".webm")), None)
        if not video:
            sys.exit("No hay entrada/referencia.mp4 (corré antes la ingesta).")
        salida = obj / "analisis"
    else:
        video, salida = obj, Path(a.salida or obj.parent / "analisis")
    salida.mkdir(parents=True, exist_ok=True)
    datos = analizar(video, salida, con_habla=not a.sin_habla)
    (salida / "referencia.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    r = datos["resumen"]
    print(f"{datos['meta']['duracion']}s · {r['cantidad_tomas']} tomas · "
          f"media {r['dur_media_toma']}s · "
          f"{datos['musica']['bpm'] if datos['musica'] else 'sin'} bpm · "
          f"{len(datos['habla'])} frases habladas")
    if datos["musica"] and datos["musica"].get("aviso"):
        print(f"⚠ {datos['musica']['aviso']}")
    print(f"→ {salida / 'referencia.json'}")


if __name__ == "__main__":
    main()
