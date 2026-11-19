"""Le pone sonido a un reel: música al tempo del guion + efectos en las transiciones.

Uso:
    uv run python herramientas/audio.py pedidos/<pedido> [--musica tema.wav --inicio s] [--video salida/reel.mp4]

Modo de música: `musica:` del guion ({modo, fuente, inicio}) o, si falta, el de
pedido.yaml; --musica lo fuerza a `archivo`. Ver conocimiento/09-audio.md.
    sintetica  (default) base propia al bpm del guion + efectos → reel-con-audio.mp4
    archivo    tema libre de derechos desde `inicio` (un tiempo 1, ver analizar_audio.py)
               + efectos más bajos → reel-con-audio.mp4
    instagram  el audio lo pone Ana en la app: NO se mezcla. Sale reel-efectos.mp4
               (solo efectos, a -20 LUFS, para dejar el sonido original bajo debajo de
               la canción) y la instrucción de dónde arrancar el audio.

Música: si no se pasa --musica, sintetiza una base pop/house al bpm del guion
(acordes C-G-Am-F, bombo en negras, palmas en 2 y 4, bajo a contratiempo, pad con
"sidechain"). Es nuestra, así que no hay derechos que cuidar; un tema elegido a mano
(libre de derechos) suena mejor y se pasa con --musica.

Efectos, derivados del guion:
    entrada barrido / zoom → whoosh que pica en el corte
    entrada golpe          → impacto grave
    entrada luz            → brillo (arpegio agudo con cola)
    sticker / etiqueta     → pop
    cierre                 → subida + brillo cuando abre el iris
    sonidos: [{beat, tipo, ajuste}] en el guion agrega efectos a mano (composiciones a medida);
             tipo: whoosh | impacto | brillo | pop | subida | cierre; ajuste en segundos

Mezcla: música abajo, efectos arriba, final con fundido y normalizado a -14 LUFS,
picos ≤ -1,5 dBTP (conocimiento/rubrica.yaml, O7). Escribe salida/reel-con-audio.mp4.
"""

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from scipy.signal import butter, lfilter, sosfilt

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, FFPROBE, correr, duraciones  # noqa: E402

SR = 48000
RNG = np.random.default_rng(7)  # determinista: el mismo guion suena igual


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def env_exp(dur, decay):
    return np.exp(-t_(dur) / decay)


def poner(pista, seg, t0, ganancia=1.0):
    i = int(round(t0 * SR))
    if i >= len(pista):
        return
    if i < 0:
        seg, i = seg[-i:], 0
    n = min(len(seg), len(pista) - i)
    pista[i:i + n] += ganancia * seg[:n]


def filtro(x, tipo, f, orden=2):
    return sosfilt(butter(orden, f, btype=tipo, fs=SR, output="sos"), x)


# ---------------------------------------------------------------- instrumentos
def bombo():
    t = t_(0.4)
    f = 45 + 75 * np.exp(-t / 0.03)
    cuerpo = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16)
    click = filtro(RNG.standard_normal(len(t)), "highpass", 3000) * np.exp(-t / 0.004) * 0.3
    return cuerpo + click


def palmas():
    out = np.zeros(int(0.25 * SR))
    for k, d in enumerate((0, 0.011, 0.022)):
        r = filtro(RNG.standard_normal(int(0.2 * SR)), "bandpass", (900, 3200)) * env_exp(0.2, 0.05 if k == 2 else 0.008)
        poner(out, r, d)
    return out


def platillo(abierto=False):
    dur = 0.25 if abierto else 0.06
    return filtro(RNG.standard_normal(int(dur * SR)), "highpass", 7000) * env_exp(dur, 0.07 if abierto else 0.015)


def sierra(f, dur, desafinar=(0.0,)):
    t = t_(dur)
    s = np.zeros_like(t)
    for c in desafinar:
        ff = f * 2 ** (c / 1200)
        fase = (t * ff + RNG.random()) % 1.0
        s += 2 * fase - 1
    return s / len(desafinar)


def bajo(nota, dur):
    x = filtro(sierra(hz(nota), dur), "lowpass", 420, 4)
    return x * np.minimum(1, t_(dur) / 0.005) * np.exp(-t_(dur) / 0.18)


def pad(notas, dur):
    x = sum(sierra(hz(n), dur, (-9, 0, 9)) for n in notas) / len(notas)
    x = filtro(x, "lowpass", 2300, 2)
    return x * np.minimum(1, t_(dur) / 0.04)


def pluck(nota, dur=0.3):
    t = t_(dur)
    f = hz(nota)
    x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
    return x * np.exp(-t / 0.09) * np.minimum(1, t / 0.002)


# La base propia es el respaldo: lo normal es un tema distinto por reel (musica.py). Para que
# tampoco suene igual en todos, la tonalidad, los acordes y el ritmo salen del nombre del pedido.
PROGRESIONES = [  # (semitonos sobre la tónica, mayor/menor) de cada compás
    ((0, "M"), (7, "M"), (9, "m"), (5, "M")),   # I-V-vi-IV
    ((9, "m"), (5, "M"), (0, "M"), (7, "M")),   # vi-IV-I-V
    ((0, "M"), (9, "m"), (5, "M"), (7, "M")),   # I-vi-IV-V
    ((2, "m"), (7, "M"), (0, "M"), (0, "M")),   # ii-V-I
    ((0, "M"), (4, "m"), (5, "M"), (7, "M")),   # I-iii-IV-V
]
ARPEGIOS = [(0, 1, 2, 3), (3, 2, 1, 0), (0, 2, 1, 3), (0, 1, 0, 2)]


NOTAS = ["do", "do#", "re", "mib", "mi", "fa", "fa#", "sol", "lab", "la", "sib", "si"]


def acordes(tonica, progresion):
    """[(raíz del bajo, notas del pad)] con el pad cerca del do central, como C - G - Am - F."""
    out = []
    for grado, tipo in progresion:
        raiz = (tonica + grado) % 12
        notas = sorted(57 + (raiz + i - 57) % 12 for i in (0, 4 if tipo == "M" else 3, 7))
        out.append((36 + raiz, tuple(notas)))
    return out


def variante(semilla):
    """Tonalidad, progresión, arpegio, platillos y swing de la base (semilla 0: la de siempre, C - G - Am - F)."""
    if not semilla:
        return {"tonica": 0, "progresion": 0, "arpegio": 0, "semicorcheas": False, "swing": 0.012}
    r = np.random.default_rng(semilla)
    return {"tonica": int(r.integers(0, 12)), "progresion": int(r.integers(0, len(PROGRESIONES))),
            "arpegio": int(r.integers(0, len(ARPEGIOS))), "semicorcheas": bool(r.integers(0, 2)),
            "swing": float(r.choice([0.0, 0.012, 0.024]))}


def musica_sintetica(bpm, total, semilla=0):
    v = variante(semilla)
    progresion = acordes(v["tonica"], PROGRESIONES[v["progresion"]])
    orden = ARPEGIOS[v["arpegio"]]
    beat = 60 / bpm
    n = int((total + 1) * SR)
    pistas = {k: np.zeros(n) for k in ("bombo", "palmas", "hats", "bajo", "pad", "pluck")}
    compases = math.ceil(total / (4 * beat)) + 1
    for c in range(compases):
        raiz, notas = progresion[c % 4]
        t0 = c * 4 * beat
        poner(pistas["pad"], pad(notas, 4 * beat + 0.05), t0)
        arpegio = [notas[0] + 12, notas[1] + 12, notas[2] + 12, notas[0] + 24]
        for b in range(4):
            tb = t0 + b * beat
            poner(pistas["bombo"], bombo(), tb)
            if b in (1, 3):
                poner(pistas["palmas"], palmas(), tb)
            poner(pistas["hats"], platillo(), tb + beat / 2 + v["swing"])  # apenas atrasado: swing
            poner(pistas["hats"], platillo(abierto=True), tb + beat / 2, 0.6)
            if v["semicorcheas"]:
                for q in (1, 3):
                    poner(pistas["hats"], platillo(), tb + q * beat / 4 + v["swing"] / 2, 0.45)
            poner(pistas["bajo"], bajo(raiz, beat / 2), tb + beat / 2)
            for k in range(2):
                poner(pistas["pluck"], pluck(arpegio[orden[(b * 2 + k) % 4]]), tb + k * beat / 2)
    # "sidechain": el pad respira con cada bombo
    tt = np.arange(n) / SR
    pistas["pad"] *= 1 - 0.65 * np.exp(-((tt % beat) / 0.11))
    pistas["bajo"] *= 1 - 0.5 * np.exp(-((tt % beat) / 0.06))
    mezcla = (0.95 * pistas["bombo"] + 0.38 * pistas["palmas"] + 0.16 * pistas["hats"]
              + 0.42 * pistas["bajo"] + 0.22 * pistas["pad"] + 0.13 * pistas["pluck"])
    return np.tanh(1.2 * mezcla) / np.tanh(1.2)


# ---------------------------------------------------------------- efectos
def whoosh(dur=0.5, pico=0.7):
    """Ruido con un pasabanda que sube y baja; el máximo cae en `pico` (fracción)."""
    n = int(dur * SR)
    ruido = RNG.standard_normal(n)
    out = np.zeros(n)
    bloque = 256
    zi = None
    for i in range(0, n, bloque):
        x = i / n
        fc = 300 + 4200 * (math.sin(math.pi * min(x / pico, 1) / 2) if x < pico else 1 - (x - pico) / (1 - pico) * 0.8)
        b, a = butter(2, (fc * 0.6, min(fc * 1.6, SR / 2 - 100)), btype="bandpass", fs=SR)
        if zi is None:
            zi = np.zeros(max(len(a), len(b)) - 1)
        out[i:i + bloque], zi = lfilter(b, a, ruido[i:i + bloque], zi=zi)
    x = np.arange(n) / n
    forma = np.where(x < pico, (x / pico) ** 2, np.exp(-(x - pico) / 0.08))
    return out * forma * 2.2


def impacto():
    t = t_(0.45)
    f = 38 + 50 * np.exp(-t / 0.05)
    grave = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2)
    golpe = filtro(RNG.standard_normal(len(t)), "lowpass", 2500) * np.exp(-t / 0.03) * 0.5
    return grave + golpe


def brillo():
    out = np.zeros(int(1.6 * SR))
    for k, nota in enumerate((84, 88, 91, 96, 100)):
        t = t_(1.4)
        f = hz(nota) * (1 + 0.003 * np.sin(2 * np.pi * 6 * t))
        tono = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45) * np.minimum(1, t / 0.003)
        poner(out, tono * 0.35, k * 0.045)
    aire = filtro(RNG.standard_normal(len(out)), "highpass", 6500) * env_exp(len(out) / SR, 0.25) * 0.25
    return out + aire


def tic():
    """Corte común: un toque corto y seco, casi un clic con cuerpo. El impacto grave se guarda
    para el momento fuerte: usado en cada corte cansa (conocimiento/09-audio.md › Efectos)."""
    t = t_(0.07)
    cuerpo = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.018)
    clic = filtro(RNG.standard_normal(len(t)), "bandpass", (2500, 7000)) * np.exp(-t / 0.006) * 0.6
    return (cuerpo * 0.7 + clic) * np.minimum(1, t / 0.001)


def pop():
    t = t_(0.12)
    f = 520 + 600 * np.exp(-t / 0.015)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * np.minimum(1, t / 0.001)


def subida(dur=0.6):
    t = t_(dur)
    x = filtro(RNG.standard_normal(len(t)), "highpass", 1500)
    return x * (t / dur) ** 2 * 0.6


# ---------------------------------------------------------------- guion → eventos
def eventos(guion, beat, pedido=None):
    ev, t = [], 0.0
    inicio = {}
    tomas = guion.get("tomas") or guion.get("escenas") or []  # escenas: composición a medida
    for toma, dur in zip(tomas, duraciones(guion, pedido) if tomas else []):
        inicio[toma["n"]] = t
        e = toma.get("entrada", "corte")
        if toma.get("cierre"):
            ev += [("subida", t - 0.45), ("brillo", t + 0.15), ("pop", t + 0.45)]
        elif t > 0 and e in ("barrido", "zoom"):
            ev.append(("whoosh", t - 0.35))   # pica en el corte
        elif toma.get("sonido"):            # el guion elige el sonido de esta entrada
            ev.append((toma["sonido"], t))
        elif e == "golpe":
            # impacto grave solo si la toma es el revelado; los demás golpes, un tic
            ev.append(("impacto" if toma.get("rol") == "revelado" else "tic", t))
        elif e == "luz":
            ev.append(("brillo", t - 0.05))
        for i, _ in enumerate(toma.get("tarjetas") or []):
            ev.append(("pop", t + 0.05 + i * beat))
        if toma.get("comparar"):
            ev += [("whoosh", t + 0.15 - 0.35 + 0.5), ("pop", t + 0.6), ("pop", t + 0.75)]
        t += dur
    for tx in guion.get("textos", []):
        if tx.get("tipo") == "sticker" and tx.get("tomas"):
            ev.append(("pop", inicio[tx["tomas"][0]]))
    for s in guion.get("sonidos", []):
        # `escena: n` cuenta los beats desde el inicio de esa escena; sin escena, desde el principio
        t0 = inicio[s["escena"]] if "escena" in s else 0.0
        t0 += s.get("beat", 0) * beat + s.get("ajuste", 0)
        if s["tipo"] == "cierre":
            ev += [("subida", t0 - 0.45), ("brillo", t0 + 0.15), ("pop", t0 + 0.45)]
        else:
            ev.append((s["tipo"], t0))
    return ev


def duracion(video):
    out = correr([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]).stdout
    return float(out.strip())


DUCK_MUSICA_DB = -16     # la música baja esto mientras alguien habla (la voz queda ~20 dB arriba)
DUCK_FX = 0.4            # los efectos también se corren
MUSICA_SOLA_DB = -6      # sin voz, la música va 6 dB por debajo del nivel de la voz


VOZ_RMS = 0.12        # nivel de referencia de lo hablado en cada toma, antes del nivel general
VOZ_PAREJA_DB = 6.0   # cuánto puede subir o bajar una toma para emparejarse (más, y se nota el ruido de fondo)


def ganancia_pareja(data, umbral=0.02):
    """Ganancia para que lo hablado de una toma quede al nivel de las demás: si alguien baja la voz en una
    frase (pasó en «El Extranjero», 3 dB menos en una toma), la música no la tapa. Mide solo las ventanas
    con voz y no pasa de ±VOZ_PAREJA_DB."""
    k = int(0.05 * SR)
    if data.size < k:
        return 1.0
    ventanas = np.sqrt(np.mean(data[: data.size // k * k].reshape(-1, k) ** 2, axis=1))
    hablado = ventanas[ventanas > umbral]
    if hablado.size == 0:
        return 1.0
    g = VOZ_RMS / float(np.sqrt(np.mean(hablado ** 2)))
    tope = 10 ** (VOZ_PAREJA_DB / 20)
    return float(np.clip(g, 1 / tope, tope))


def pista_de_voz(pedido, guion, n):
    """(voz, actividad): la voz de las tomas que hablan (preparar_clips.py, voz.py) en su lugar
    del reel, y una curva 0-1 de cuándo se habla (de los tiempos de las palabras, suavizada)."""
    archivo = pedido / "analisis" / "voz.json"
    if not archivo.exists():
        return None, None
    voces = json.loads(archivo.read_text(encoding="utf-8")).get("tomas") or {}
    if not voces:
        return None, None
    tomas = guion.get("tomas") or guion.get("escenas") or []
    inicio, t = {}, 0.0
    for toma, d in zip(tomas, duraciones(guion, pedido)):
        inicio[toma["n"]] = t
        t += d
    # las mismas palabras que los subtítulos (con subtitulos_fuente, la transcripción entera): una toma con
    # `voz: true` que la detección no reconoció tiene la lista vacía, y la compuerta la bajaba 20 dB entera
    from armar_pop import voces as voces_con_palabras
    palabras = {k: v["palabras"] for k, v in voces_con_palabras(pedido, guion).items()}
    voz, activo = np.zeros(n), np.zeros(n)
    for clave, info in voces.items():
        k = int(clave)
        data, sr = sf.read(pedido / "render" / "assets" / info["archivo"])
        data = data.mean(axis=1) if data.ndim > 1 else data
        data = data * ganancia_pareja(data)
        poner(voz, data, inicio[k])
        dichas = palabras.get(k) or info["palabras"]
        if not dichas:  # hay voz pero no se sabe dónde: la toma entera cuenta como habla
            dichas = [{"ini": 0.0, "fin": len(data) / SR}]
        for w in dichas:
            a = int((inicio[k] + w["ini"] - 0.12) * SR)
            b = int((inicio[k] + w["fin"] + 0.25) * SR)
            activo[max(0, a):max(0, min(n, b))] = 1
    # compuerta: entre palabras la pista de voz baja 20 dB, así no se oye en las pausas lo que hay
    # debajo de ella (la canción del reel original, el ruido del local)
    k = int(0.08 * SR)
    abierta = np.clip(np.convolve(activo, np.ones(k) / k, mode="same"), 0, 1)
    voz *= 0.1 + 0.9 * abierta
    # nivel de la voz: RMS de lo hablado a ~-15 dBFS
    hablado = voz[activo > 0]
    if hablado.size:
        voz *= 0.18 / max(1e-6, float(np.sqrt(np.mean(hablado ** 2))))
    # suavizado: ataque y relajación de ~0,15 s para que la música no "salte"
    k = int(0.15 * SR)
    activo = np.convolve(activo, np.ones(k) / k, mode="same")
    return voz, np.clip(activo, 0, 1)


def musica_del_pedido(pedido, guion):
    """(modo, musica) del reel: `musica` del guion o, si no tiene modo, la de pedido.yaml."""
    musica = dict(guion.get("musica") or {})
    if not musica.get("modo") and (pedido / "pedido.yaml").exists():
        musica = dict((yaml.safe_load((pedido / "pedido.yaml").read_text(encoding="utf-8")) or {}).get("musica") or {})
    modo = musica.get("modo") or "sintetica"
    if modo in ("sin-audio", "incluida"):  # nombres viejos de pedido.yaml
        modo = "archivo" if musica.get("fuente") or musica.get("archivo") else "sintetica"
    return modo, musica


def archivo_final(modo):
    """El MP4 que se sube: con música propia, o solo con efectos si la canción la pone Ana."""
    return "reel-efectos.mp4" if modo == "instagram" else "reel-con-audio.mp4"


def nombre_salida(pedida, modo):
    """Dónde va la mezcla: la que se pidió con --salida (el borrador de la fábrica) o el final del modo.
    Antes el modo instagram pisaba siempre --salida y el borrador quedaba como reel-efectos.mp4."""
    return pedida or "salida/" + archivo_final(modo)


def instruccion_instagram(musica, con_voz=False):
    """Qué audio elegir en la app y desde dónde (modo instagram). `fuente` se escribe para Ana."""
    ini = float(musica.get("inicio") or 0)
    volumen = (" Dejá el sonido original del video al 100 % (ahí está la voz) y la música bajita, al 15-20 %, "
               "para que se entienda lo que se dice." if con_voz else
               " Bajá el volumen del sonido original del video al 20-30 %: son los efectos.")
    return (musica.get("fuente", "(sin fuente en el guion)")
            + (f", desde el {int(ini // 60)}:{int(ini % 60):02d}" if ini >= 1 else "")
            + (f" (donde dice «{musica['letra']}»)" if musica.get("letra") else "") + "." + volumen)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--musica", help="tema libre de derechos (fuerza el modo archivo)")
    ap.add_argument("--inicio", type=float, help="segundo del tema donde arranca (default: el del guion o 0)")
    ap.add_argument("--video", default="salida/reel.mp4")
    ap.add_argument("--salida", help="default: reel-con-audio.mp4, o reel-efectos.mp4 en modo instagram")
    a = ap.parse_args()
    pedido = Path(a.pedido)
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    beat = 60 / guion["bpm"]
    video = pedido / a.video
    total = duracion(video)
    n = int(total * SR)

    modo, musica = musica_del_pedido(pedido, guion)
    if a.musica:
        modo = "archivo"
        musica.update(modo="archivo", fuente=a.musica)
    if a.inicio is not None:
        musica["inicio"] = a.inicio
    a.salida = nombre_salida(a.salida, modo)
    ganancia_fx = 1.0
    # los intermedios van a una carpeta temporal: en render/, `hyperframes check` avisaba
    # "audio_file_without_element" (un audio suelto en el proyecto que ninguna capa usa)
    tmpdir = Path(tempfile.mkdtemp(prefix="reel-audio-"))

    if modo == "instagram":
        m = np.zeros(n)
        origen = "sin música (la pone Ana en Instagram)"
        ganancia_fx = 1.0
    elif modo == "archivo":
        fuente = musica.get("fuente") or musica.get("archivo")
        tmpw = tmpdir / "musica-48k.wav"
        correr([FFMPEG, "-v", "error", "-y", "-ss", f"{float(musica.get('inicio', 0)):.3f}", "-i", str(fuente),
                "-t", f"{total + 0.1:.3f}", "-ac", "1", "-ar", str(SR), str(tmpw)])
        m, _ = sf.read(tmpw)
        m = np.pad(m, (0, max(0, n - len(m))))[:n]
        origen = f"{Path(fuente).name} desde {float(musica.get('inicio', 0)):.2f} s"
        ganancia_fx = 0.55  # con un tema real, los efectos acompañan, no compiten
    else:
        import zlib
        semilla = zlib.crc32(pedido.resolve().name.encode())
        m = musica_sintetica(guion["bpm"], total, semilla)[:n]
        v = variante(semilla)
        origen = (f"base sintética {guion['bpm']} bpm, en {NOTAS[v['tonica']]}, acordes {v['progresion'] + 1} "
                  f"(variante del pedido; mejor un tema de musica.py)")

    fx = np.zeros(n)
    sonidos = {"whoosh": (whoosh, 0.55), "impacto": (impacto, 0.7), "brillo": (brillo, 0.45),
               "pop": (pop, 0.35), "subida": (subida, 0.5), "tic": (tic, 0.3)}
    lista = eventos(guion, beat, pedido)
    for tipo, t0 in lista:
        f, g = sonidos[tipo]
        poner(fx, f(), t0, g * ganancia_fx)

    # fundido final y mezcla (la música queda debajo de los efectos)
    fin = int(0.7 * SR)
    m[-fin:] *= np.linspace(1, 0, fin) ** 2
    voz, activo = pista_de_voz(pedido, guion, n)
    if voz is None:
        mezcla = (0.5 if modo == "sintetica" else 0.8) * m + fx
    else:
        # con voz: la música va 6 dB por debajo del nivel de la voz y baja 16 dB más mientras se
        # habla; los efectos también se corren. La voz manda (conocimiento/09-audio.md › Voz)
        rms_m = float(np.sqrt(np.mean(m ** 2))) if m.any() else 1.0
        m *= 0.18 * 10 ** (MUSICA_SOLA_DB / 20) / max(1e-6, rms_m)
        duck = 1 - (1 - 10 ** (DUCK_MUSICA_DB / 20)) * activo
        mezcla = m * duck + fx * (1 - (1 - DUCK_FX) * activo) * 0.5 + voz
        origen += f" + voz de {len(json.loads((pedido / 'analisis' / 'voz.json').read_text(encoding='utf-8'))['tomas'])} toma(s), con la música abajo"
    mezcla /= max(1e-9, np.abs(mezcla).max()) / 0.9
    tmp = tmpdir / "audio-mezcla.wav"
    sf.write(tmp, np.stack([mezcla, mezcla], axis=1).astype(np.float32), SR)

    # normalizado a -14 LUFS / -1,5 dBTP en dos pasadas (loudnorm lineal); solo efectos: -20
    # (con voz, el sonido original es lo principal aunque la canción la ponga Ana: -14)
    lufs = -20 if modo == "instagram" and voz is None else -14
    med = correr([FFMPEG, "-hide_banner", "-i", str(tmp), "-af",
                  f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    j = json.loads(med[med.rindex("{"):med.rindex("}") + 1])
    filtro_ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
                 f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    destino = pedido / a.salida
    correr([FFMPEG, "-v", "error", "-y", "-i", str(video), "-i", str(tmp), "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-af", filtro_ln + f",aresample={SR}", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(destino)])
    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"{destino}: {origen} + {len(lista)} efectos ({', '.join(sorted({t for t, _ in lista}))})")
    if modo == "instagram":
        print(f"  En Instagram, el audio: {instruccion_instagram(musica, voz is not None)}")


if __name__ == "__main__":
    main()
