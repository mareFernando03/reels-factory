"""Utilidades compartidas: ubicar ffmpeg, leer metadatos, sacar fotogramas y
armar hojas de contactos. Sin criterio editorial: eso lo pone Claude."""

import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _bin(nombre):
    """ffmpeg/ffprobe del PATH o, si la shell es vieja, el de winget."""
    if p := shutil.which(nombre):
        return p
    patron = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin")
    for d in sorted(glob.glob(patron), reverse=True):
        exe = Path(d) / f"{nombre}.exe"
        if exe.exists():
            return str(exe)
    raise SystemExit(f"No encuentro {nombre}: instalalo con `winget install Gyan.FFmpeg`.")


FFMPEG = _bin("ffmpeg")
FFPROBE = _bin("ffprobe")


def correr(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probar(video):
    """Metadatos básicos de un video: duración, tamaño, fps, rotación, audio."""
    out = correr([FFPROBE, "-v", "error", "-print_format", "json",
                  "-show_streams", "-show_format", str(video)]).stdout
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    rot = 0
    if v:
        for sd in v.get("side_data_list", []):
            rot = int(sd.get("rotation", 0) or 0)
    num, den = (v["avg_frame_rate"] if v else "0/1").split("/")
    ancho, alto = (v["width"], v["height"]) if v else (0, 0)
    if abs(rot) in (90, 270):
        ancho, alto = alto, ancho
    return {
        "duracion": round(float(d["format"].get("duration", 0)), 3),
        "ancho": ancho, "alto": alto,
        "fps": round(int(num) / int(den), 2) if int(den) else 0,
        "rotacion": rot,
        "codec": v["codec_name"] if v else None,
        "audio": a is not None,
    }


def fotograma(video, t, destino, ancho=360):
    """Guarda el fotograma del segundo t, escalado a `ancho` px."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    correr([FFMPEG, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", f"scale={ancho}:-2", str(destino)])
    return destino


def hoja_de_contactos(imagenes, destino, etiquetas=None, columnas=6):
    """Junta fotogramas en una grilla con su etiqueta (p.ej. el segundo)."""
    import cv2
    import numpy as np

    imgs = [cv2.imread(str(p)) for p in imagenes]
    imgs = [i for i in imgs if i is not None]
    if not imgs:
        return None
    h, w = imgs[0].shape[:2]
    filas = (len(imgs) + columnas - 1) // columnas
    hoja = np.full((filas * (h + 28), columnas * w, 3), 255, np.uint8)
    for k, im in enumerate(imgs):
        im = cv2.resize(im, (w, h))
        f, c = divmod(k, columnas)
        y, x = f * (h + 28), c * w
        hoja[y + 28:y + 28 + h, x:x + w] = im
        txt = etiquetas[k] if etiquetas else str(k)
        cv2.putText(hoja, txt, (x + 6, y + 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imwrite(str(destino), hoja)
    return Path(destino)


def transcribir(audio_o_video, modelo="small", idioma="es"):
    """Segmentos con tiempos (faster-whisper, CPU int8). Lista vacía si no hay habla."""
    from faster_whisper import WhisperModel

    ws = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = ws.transcribe(str(audio_o_video), language=idioma, vad_filter=True,
                            word_timestamps=True)
    return [{"inicio": round(s.start, 2), "fin": round(s.end, 2), "texto": s.text.strip()}
            for s in segs]


CIERRE = 2.0  # s: R3 pide un cierre ≤2 s y el CTA necesita ~1,5 s a la vista (O5)


def duraciones(guion, pedido=None):
    """Duración en segundos de cada toma del guion (en orden, incluido el cierre).

    El cierre sin `beats` dura CIERRE: como es lo último, no hace falta que caiga en la grilla
    (a 100 bpm, 4 beats son 2,4 s y R3 falla).

    Sin canción: grilla pareja, beats × 60/bpm (+ `desfase` en la primera toma).
    Con `musica.analisis` (JSON de analizar_audio.py, relativo al pedido): cada corte
    cae en el beat real detectado desde `musica.inicio`; las canciones no tienen tempo
    perfectamente parejo y una grilla teórica se corre hasta medio beat en 15 s.
    """
    beat = 60 / guion["bpm"]
    tomas = guion.get("tomas") or guion.get("escenas") or []
    musica = guion.get("musica") or {}
    if musica.get("analisis") and pedido is not None:
        datos = json.loads((Path(pedido) / musica["analisis"]).read_text(encoding="utf-8"))
        s0 = float(musica.get("inicio", 0))
        grilla = [b - s0 for b in datos["beats"] if b >= s0 - 0.01]
        # El primer beat cerca del arranque (menos de medio beat) es el tiempo 1 del
        # compás: la primera toma lo incluye y se alarga lo que haga falta (desfase).
        if not grilla or grilla[0] >= beat / 2:
            grilla = [0.0] + grilla

        def entero(k):
            return grilla[k] if k < len(grilla) else grilla[-1] + (k - len(grilla) + 1) * beat

        def t(k):  # tiempo del k-ésimo beat del reel (k=0 es el arranque, siempre 0 s); k puede ser 3,5
            if k == 0:
                return 0.0
            base = int(k)
            return entero(base) if k == base else entero(base) + (k - base) * (entero(base + 1) - entero(base))

        out, k = [], 0
        for toma in tomas:
            if toma.get("cierre") and "beats" not in toma:
                out.append(CIERRE)
                continue
            out.append(t(k + toma["beats"]) - t(k))
            k += toma["beats"]
        return out
    out = [CIERRE if toma.get("cierre") and "beats" not in toma else toma["beats"] * beat for toma in tomas]
    if out:
        out[0] += guion.get("desfase", 0)
    return out
