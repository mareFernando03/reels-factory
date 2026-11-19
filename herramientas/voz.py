"""Voz en las tomas: detectar si alguien habla en un tramo y con qué palabras y tiempos.

Si en una toma alguien habla, su voz se respeta: el clip conserva ese audio, la música
baja debajo de la voz (audio.py) y lleva subtítulos (armar_pop.py). Si no, se reemplaza
el sonido como siempre. Ver conocimiento/09-audio.md › Voz.

Habla vs. canción: una canción con letra también se transcribe. Se distingue por:
  - el idioma: Ana y sus clientas hablan en castellano; una letra en inglés es la canción de
    fondo («I shake it off» en el revelado de los pochoclos);
  - la confianza: el canto da palabras dudosas y segmentos con avg_logprob bajo; el habla de un
    selfie da confianza alta. Umbrales medidos el 03/10/2026.
Una canción en castellano cantada claro puede pasar como habla: por eso el guion puede fijar
`voz: true | false` por toma, y la fábrica muestra lo que transcribió para revisarlo.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from comun import FFMPEG

CONFIANZA = 0.6      # probabilidad media mínima de las palabras para contar como habla
LOGPROB = -0.6       # avg_logprob mínimo: habla de selfie -0,3/-0,45; letra de canción de fondo -0,77/-0,88
MIN_PALABRAS = 2
# Frases que Whisper inventa sobre música o silencio (vienen de los subtítulos con que se entrenó)
ALUCINACIONES = ("amara.org", "subtítulos realizados", "subtitulado por", "gracias por ver", "suscríbete")
_modelo = None


def _whisper():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        _modelo = WhisperModel("small", device="cpu", compute_type="int8")
    return _modelo


LIMPIEZA = "highpass=f=90,afftdn=nr=10:nf=-40:tn=1,lowpass=f=12000"   # graves del local, siseo y zumbido


def extraer(src, desde, hasta, destino, tempo=1.0, limpiar=False):
    """El audio del tramo a WAV mono 48 kHz; `tempo` lo acelera o frena sin cambiar el tono.
    `limpiar` (para la voz que va al reel; para transcribir, el audio tal cual): primero separa la
    voz de la canción que traía el reel (separar.py, si está el modelo) y después le pasa LIMPIEZA."""
    filtros = ["aresample=48000"] + ([LIMPIEZA] if limpiar else [])
    if abs(tempo - 1) > 0.005:
        filtros.append(f"atempo={tempo:.4f}")
    corte = ["-ss", f"{desde:.3f}", "-t", f"{hasta - desde:.3f}", "-i", str(src)]
    import separar
    if limpiar and separar.disponible():
        with tempfile.TemporaryDirectory() as d:
            mezcla, sola = Path(d) / "mezcla.wav", Path(d) / "voz.wav"
            subprocess.run([FFMPEG, "-v", "error", "-y", *corte, "-vn", "-ac", "2", "-ar", str(separar.SR),
                            str(mezcla)], check=True)
            separar.separar_archivo(mezcla, sola)
            subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(sola), "-ac", "1", "-af", ",".join(filtros),
                            str(destino)], check=True)
        return Path(destino)
    subprocess.run([FFMPEG, "-v", "error", "-y", *corte, "-vn", "-ac", "1", "-af", ",".join(filtros),
                    str(destino)], check=True)
    return Path(destino)


def tiene_audio(src):
    from comun import probar
    return probar(src)["audio"]


def detectar(src, desde, hasta, estricto=True):
    """{habla: bool, palabras: [{w, ini, fin}] relativas a `desde`, texto, confianza}.
    estricto=False no descarta segmentos por confianza (para verificar una voz que ya se sabe que está: quien
    habla más bajo da avg_logprob de -0,7 y el filtro lo tomaba por una canción de fondo)."""
    if not tiene_audio(src):
        return {"habla": False, "palabras": [], "texto": "", "confianza": 0.0}
    with tempfile.TemporaryDirectory() as d:
        wav = extraer(src, desde, hasta, Path(d) / "tramo.wav")
        _, info = _whisper().transcribe(str(wav), vad_filter=True, without_timestamps=True)  # idioma
        idioma, p_idioma = info.language, float(info.language_probability)
        segs, _ = _whisper().transcribe(str(wav), language="es", vad_filter=True, word_timestamps=True)
        segs = list(segs)
    palabras = [{"w": w.word.strip(), "ini": round(float(w.start), 2), "fin": round(float(w.end), 2), "p": round(float(w.probability), 2)}
                for s in segs if not estricto or s.avg_logprob >= LOGPROB for w in (s.words or []) if w.word.strip()]
    conf = sum(p["p"] for p in palabras) / len(palabras) if palabras else 0.0
    castellano = idioma == "es" or p_idioma < 0.5   # con poca certeza del idioma no se descarta
    texto_bajo = " ".join(p["w"] for p in palabras).lower()
    if any(a in texto_bajo for a in ALUCINACIONES):
        palabras = []
    habla = len(palabras) >= MIN_PALABRAS and (conf >= CONFIANZA or not estricto) and castellano
    return {"habla": habla, "palabras": palabras if habla else [], "confianza": round(conf, 2),
            "idioma": idioma, "p_idioma": round(p_idioma, 2),
            "texto": " ".join(p["w"] for p in palabras),
            "segmentos": [{"texto": s.text.strip(), "logprob": round(float(s.avg_logprob), 2)} for s in segs]}


def cache(pedido):
    archivo = Path(pedido) / "analisis" / "voz.json"
    return archivo, (json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {})
