"""Prepara los clips de un guion: tramo exacto, sin barras negras, 1080×1920,
30 fps, sin audio y con la velocidad que haga falta para durar lo pedido.

Uso:
    uv run python herramientas/preparar_clips.py pedidos/<pedido>

Lee plan/guion.yaml (lista `tomas`: fuente, desde, hasta, beats) y bpm.
Escribe render/assets/clips/NN.mp4. La velocidad sale sola:
    velocidad = (hasta - desde) / (beats * 60 / bpm)
>1 es acelerado (proceso), <1 cámara lenta (revelado).

Una toma puede ser una foto (`fuente` .jpg, .png o .webp, sin desde/hasta): sale un clip quieto
que dura lo que la toma, y el movimiento lo pone armar_pop.py (`push`). Acepta `encuadre`,
`espejar`, `realce`, `color` y `afinar` (retoque.py: correr un contorno, p. ej. achicar un brazo).

Opcionales por toma:
    encuadre: {arriba: 0, abajo: 0.79, centro_x: 0.5}  recorte 9:16 a mano (fracciones
        de la fuente), p. ej. para dejar afuera un texto quemado; reemplaza al cropdetect.
    espejar: true  voltea horizontal (selfies en el espejo: el logo se lee al derecho).
    comparar: {antes: {desde, hasta}, despues: {desde, hasta}}  pantalla dividida
        antes | después: escribe NNa.mp4 y NNb.mp4 (la toma no lleva desde/hasta propios).
    estabilizar: auto | true | false  (default auto) vidstab en dos pasadas; en auto se
        aplica si movimiento.py mide temblor en el tramo. Suaviza el pulso y conserva
        los paneos intencionales; hace un zoom leve para tapar los bordes.
    color: false  no igualar el color de esta toma (ver abajo).
    realce: true  enfoque de luminancia y saturación +8 %, sin tocar el tono (también en el guion,
        para todas las tomas). Para material nítido que se ve plano («más definición, más color»).
    voz: auto | true | false  (default auto) si alguien habla en el tramo (voz.py), su audio se
        conserva en render/assets/voz/NN.wav para que audio.py lo mezcle con la música abajo y
        armar_pop.py le ponga subtítulos. Con voz, la toma tiene que ir a velocidad ~1 (±15 %, se
        corrige con atempo sin cambiar el tono); si no, avisa y la voz se pierde.

Al final iguala el color entre tomas (color.py): acerca el brillo y el balance de cada clip
a la toma del revelado, en forma parcial y con topes. `igualar_color: false` en el guion lo
apaga. Las mediciones y correcciones quedan en analisis/color.json.
"""

import json

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, FFPROBE, correr, duraciones  # noqa: E402
from color import correccion, filtro, medir, referencia  # noqa: E402
from voz import cache as cache_voz, detectar, extraer, tiene_audio  # noqa: E402
from movimiento import PANEO, TEMBLOR, movimiento_de, tramo as ventanas_del_tramo  # noqa: E402
from retoque import afinar_archivo  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def recorte_util(src, desde, hasta):
    """crop=w:h:x:y del área sin barras negras (cropdetect sobre el tramo)."""
    err = correr([FFMPEG, "-v", "info", "-ss", f"{desde:.3f}", "-t", f"{hasta - desde:.3f}",
                  "-i", str(src), "-vf", "cropdetect=limit=24:round=2:reset=0",
                  "-f", "null", "-"]).stderr
    hallados = re.findall(r"crop=(\d+:\d+:\d+:\d+)", err)
    return hallados[-1] if hallados else None


def tamano_visible(w, h, rotacion):
    """El tamaño como se ve: ffmpeg rota al decodificar, así que los filtros (crop) trabajan sobre
    el cuadro ya rotado. Los celulares guardan el vertical acostado con −90° (4K de Cata, 26/10/2026:
    el recorte a mano salía de 704×1252 sobre un cuadro de 3840×2160)."""
    return (h, w) if round(float(rotacion or 0)) % 180 == 90 else (w, h)


def girada_por_exif(orientacion):
    """Las orientaciones EXIF 5-8 guardan la foto acostada: ffmpeg la endereza antes de los filtros."""
    return orientacion in (5, 6, 7, 8)


def dimensiones(src):
    if es_foto(src):   # ffprobe da el tamaño guardado, sin el giro EXIF del celular («asustan todo el año», 28/10/2026)
        from PIL import Image
        with Image.open(src) as im:
            w, h = im.size
            return (h, w) if girada_por_exif(im.getexif().get(0x0112)) else (w, h)
    out = correr([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                  "stream=width,height:stream_side_data=rotation:stream_tags=rotate", "-of", "json", str(src)]).stdout
    s = json.loads(out)["streams"][0]
    rot = next((d["rotation"] for d in s.get("side_data_list", []) if "rotation" in d),
               (s.get("tags") or {}).get("rotate", 0))
    return tamano_visible(int(s["width"]), int(s["height"]), rot)


def recorte_manual(src, enc):
    """crop=w:h:x:y de una ventana 9:16 entre `arriba` y `abajo`, centrada en `centro_x`."""
    W, H = dimensiones(src)
    y0 = round(enc.get("arriba", 0) * H)
    h = round(enc.get("abajo", 1) * H) - y0
    w = min(W, round(h * 9 / 16))
    x = round(enc.get("centro_x", 0.5) * W - w / 2)
    x = max(0, min(W - w, x))
    return f"{w - w % 2}:{h - h % 2}:{x}:{y0}"


FOTOS = (".jpg", ".jpeg", ".png", ".webp")


def es_foto(src):
    return Path(src).suffix.lower() in FOTOS


def filtros_foto(t, crop, ancho_util):
    """Cadena de una foto: sin tramo, velocidad, cámara lenta ni estabilización (no hay movimiento)."""
    filtros = ["hflip"] if t.get("espejar") else []
    filtros += [f"crop={crop}"] if crop else []
    filtros += ["scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos", "crop=1080:1920", "setsar=1"]
    return filtros + realce(ancho_util, t.get("realce", False))


def foto(src, t, dur, destino):
    """Una foto como toma: un clip quieto de `dur` segundos (el acercamiento lo anima armar_pop.py)."""
    if t.get("afinar"):   # retoque.py, antes del recorte: las zonas van en fracciones de la foto entera
        src = afinar_archivo(src, t["afinar"], destino.with_suffix(".afinada.jpg"))
    crop = recorte_manual(src, t["encuadre"]) if t.get("encuadre") else None
    ancho_util = int(crop.split(":")[0]) if crop else dimensiones(src)[0]
    correr([FFMPEG, "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-i", str(Path(src).resolve()),
            "-vf", ",".join(filtros_foto(t, crop, ancho_util)), "-t", f"{dur:.3f}", "-an", "-r", "30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", str(destino.resolve())])
    print(f"  {destino.stem}: foto → {dur:.3f}s recorte {crop or '—'}")


def preparar(pedido):
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    salida = pedido / "render" / "assets" / "clips"
    salida.mkdir(parents=True, exist_ok=True)
    archivo_voz, previo = cache_voz(pedido)
    detecciones, voces = previo.get("detecciones", {}), {}
    for f in (salida.parent / "voz").glob("*.wav"):  # se rehacen: una toma puede haber dejado de tener voz
        f.unlink()
    for t, dur_toma in zip(guion["tomas"], duraciones(guion, pedido)):
        if t.get("cierre"):
            continue
        t = {"realce": guion.get("realce", False), **t}   # `realce` del guion vale para todas; la toma lo pisa
        src = (RAIZ / t["fuente"]) if not Path(t["fuente"]).is_absolute() else Path(t["fuente"])
        # solape: el clip sigue visible debajo de la toma siguiente (transiciones)
        dur = dur_toma + t.get("solape", 0)
        if es_foto(src):
            foto(src, t, dur, salida / f"{t['n']:02d}.mp4")
            continue
        if t.get("comparar"):
            # pantalla dividida: un clip por lado, misma duración
            for sufijo, lado in (("a", "antes"), ("b", "despues")):
                cortar(src, {**t, **t["comparar"][lado]}, dur, salida / f"{t['n']:02d}{sufijo}.mp4")
        else:
            # el solape se cubre con más material de la fuente, a la misma velocidad: estirar el clip
            # desfasaba los labios de la voz y frenaba el final. Si la fuente no alcanza, se estira
            tc = dict(t)
            if t.get("solape"):
                extra = t["solape"] * (t["hasta"] - t["desde"]) / dur_toma
                if t["hasta"] + extra <= probar_duracion(src):
                    tc["hasta"] = round(t["hasta"] + extra, 3)
            cortar(src, tc, dur, salida / f"{t['n']:02d}.mp4")
            v = voz_de_toma(t, src, dur_toma, salida.parent / "voz", detecciones)
            if v:
                voces[t["n"]] = v
    archivo_voz.parent.mkdir(exist_ok=True)
    archivo_voz.write_text(json.dumps({"tomas": voces, "detecciones": detecciones}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    if guion.get("igualar_color", True):
        igualar_color(pedido, guion, salida)


def probar_duracion(src):
    from comun import probar
    return probar(src)["duracion"]


MARGEN_CORTE = 0.8   # cuánto se escucha más allá del tramo para saber si una palabra queda partida


def palabras_partidas(src, t, detecciones):
    """Las palabras que el tramo corta por la mitad, al principio o al final: suena a que se cortó."""
    desde = max(0.0, t["desde"] - MARGEN_CORTE)
    clave = f"{t['fuente']}|{desde:.3f}|{t['hasta'] + MARGEN_CORTE:.3f}"
    if clave not in detecciones:
        detecciones[clave] = detectar(src, desde, t["hasta"] + MARGEN_CORTE)
    bordes = (t["desde"] - desde, t["hasta"] - desde)
    return [p["w"] for p in detecciones[clave]["palabras"]
            if any(p["ini"] < b - 0.02 and p["fin"] > b + 0.02 for b in bordes)]


def voz_de_toma(t, src, dur_toma, carpeta, detecciones):
    """Si alguien habla en el tramo, guarda su audio (al tiempo de la toma) y sus palabras."""
    modo = t.get("voz", "auto")
    if modo is False or not tiene_audio(src):
        return None
    clave = f"{t['fuente']}|{t['desde']:.3f}|{t['hasta']:.3f}"
    if clave not in detecciones:
        detecciones[clave] = detectar(src, t["desde"], t["hasta"])
    det = detecciones[clave]
    if modo == "auto" and not det["habla"]:
        return None
    tempo = (t["hasta"] - t["desde"]) / dur_toma
    if abs(tempo - 1) > 0.15:
        print(f"  ! toma {t['n']:02d}: habla («{det['texto'][:50]}») pero va a ×{tempo:.2f}: la voz se pierde. "
              f"Ajustar beats o tramo para que dure lo mismo, o poner voz: false")
        return None
    partidas = palabras_partidas(src, t, detecciones)
    if partidas:
        print(f"  ! toma {t['n']:02d}: el tramo corta la voz en mitad de «{'», «'.join(partidas)}». "
              f"Mover desde/hasta a una pausa (o voz: false)")
    carpeta.mkdir(exist_ok=True)
    extraer(src, t["desde"], t["hasta"], carpeta / f"{t['n']:02d}.wav", tempo, limpiar=True)
    print(f"  voz en la toma {t['n']:02d}: «{det['texto'][:60]}»" + (f" (×{tempo:.2f})" if abs(tempo - 1) > 0.005 else ""))
    return {"archivo": f"voz/{t['n']:02d}.wav", "tempo": round(tempo, 4), "texto": det["texto"], "partidas": partidas,
            "palabras": [{**p, "ini": round(p["ini"] / tempo, 2), "fin": round(p["fin"] / tempo, 2)} for p in det["palabras"]]}


def igualar_color(pedido, guion, salida):
    """Acerca cada clip a la toma de referencia (color.py) y lo recodifica si hace falta."""
    import statistics
    tomas = [t for t in guion["tomas"] if not t.get("cierre")]
    simples = [t for t in tomas if not t.get("comparar")]  # los lados de una comparación no se tocan
    if len(simples) < 2:
        return
    med = {t["n"]: medir(salida / f"{t['n']:02d}.mp4") for t in simples}
    n_ref = referencia(tomas)
    ref = med.get(n_ref) or {  # sin revelado: la mediana de las tomas
        "y": statistics.median(m["y"] for m in med.values()), "neutros": 1.0,
        "rg": statistics.median(m["rg"] for m in med.values() if m["rg"]) if any(m["rg"] for m in med.values()) else None,
        "bg": statistics.median(m["bg"] for m in med.values() if m["bg"]) if any(m["bg"] for m in med.values()) else None}
    informe = {"referencia": n_ref, "tomas": {}}
    for t in simples:
        n = t["n"]
        c = correccion(med[n], ref) if n != n_ref and t.get("color", True) else None
        if c:
            clip = salida / f"{n:02d}.mp4"
            tmp = clip.with_name(f"{n:02d}-color.mp4")
            correr([FFMPEG, "-v", "error", "-y", "-i", str(clip), "-vf", filtro(c), "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", str(tmp)])
            tmp.replace(clip)
        informe["tomas"][n] = {**med[n], "correccion": c}
    ys = [m["y"] for m in med.values()]
    despues = [medir(salida / f"{n:02d}.mp4")["y"] if informe["tomas"][n]["correccion"] else med[n]["y"] for n in med]
    informe["desvio_brillo"] = {"antes": round(statistics.pstdev(ys), 1), "despues": round(statistics.pstdev(despues), 1)}
    (pedido / "analisis").mkdir(exist_ok=True)
    (pedido / "analisis" / "color.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
    corregidas = [f"{n:02d} ({c['gamma']}·{c['rr']}·{c['bb']})" for n, x in informe["tomas"].items() if (c := x["correccion"])]
    print(f"  color: referencia toma {n_ref or 'mediana'}; desvío de brillo {informe['desvio_brillo']['antes']} → "
          f"{informe['desvio_brillo']['despues']}; corregidas: {', '.join(corregidas) or 'ninguna'} (gamma·rojo·azul)")


def hace_falta_estabilizar(src, desde, hasta):
    """Temblor medio de las ventanas que no son barrido (un barrido se mueve a propósito)."""
    vs = [v for v in ventanas_del_tramo(movimiento_de(src), desde, hasta) if v["clase"] != "barrido"]
    if not vs:  # todo el tramo es barrido
        return False, None
    medio = sum(v["temblor"] for v in vs) / len(vs)
    return medio > TEMBLOR * 0.8, medio


def estabilizacion(src, desde, tramo, destino, margen):
    """Pasada 1 de vidstab; devuelve el filtro de la pasada 2. Corre en la carpeta del
    clip para no pelear con los ':' de las rutas de Windows dentro del filtro.

    Si el recorte 9:16 deja margen a los costados (fuente más ancha o encuadre a mano),
    zoom fijo de 4 % y bordes rellenos con el cuadro anterior: el relleno queda fuera
    del recorte y no se pierde resolución. Si no hay margen, zoom automático
    (optzoom), que acerca lo necesario para tapar los bordes (~10-30 %)."""
    trf = destino.with_suffix(".trf").name
    correr([FFMPEG, "-v", "error", "-y", "-ss", f"{desde:.3f}", "-t", f"{tramo:.3f}",
            "-i", str(Path(src).resolve()), "-vf", f"vidstabdetect=shakiness=6:accuracy=15:result={trf}",
            "-f", "null", "-"], cwd=destino.parent)
    if margen >= 0.06:
        return f"vidstabtransform=input={trf}:smoothing=10:optzoom=0:zoom=4:crop=keep:interpol=bicubic"
    return f"vidstabtransform=input={trf}:smoothing=15:optzoom=1:interpol=bicubic"


def realce(ancho_util, pedido=False):
    """Filtros de definición y color al final de la cadena.

    Fuente chica (<720 px de ancho): enfoque leve para compensar la ampliación.
    `realce: true` (guion o toma; lo pidió Ana: «más definición, más color»): enfoque de
    luminancia un poco más firme y saturación +8 %. Sin tocar el tono ni el balance: el color
    del pelo es el producto (07-edicion-y-estetica.md › Color)."""
    if pedido:
        return ["unsharp=5:5:0.8:5:5:0.0", "eq=saturation=1.08"]
    return ["unsharp=5:5:0.6:5:5:0.0"] if ancho_util < 720 else []


def cortar(src, t, dur, destino):
    tramo = t["hasta"] - t["desde"]
    vel = tramo / dur
    modo = t.get("estabilizar", "auto")
    estab, temblor = (hace_falta_estabilizar(src, t["desde"], t["hasta"]) if modo == "auto"
                      else (bool(modo), None))
    crop = (recorte_manual(src, t["encuadre"]) if t.get("encuadre")
            else recorte_util(src, t["desde"], t["hasta"]))
    ancho_util = int(crop.split(":")[0]) if crop else 1080
    margen = 0.0
    if estab and crop:
        W, _ = dimensiones(src)
        w, _, x, _ = (int(v) for v in crop.split(":"))
        margen = min(x, W - x - w) / W  # el lado más justo manda
    filtros = [estabilizacion(src, t["desde"], tramo, destino, margen)] if estab else []
    filtros += ["hflip"] if t.get("espejar") else []
    filtros += [f"crop={crop}"] if crop else []
    filtros.append(f"setpts={1 / vel:.6f}*(PTS-STARTPTS)")
    # Cámara lenta: interpolar cuadros para que no se vea entrecortada. La interpolación
    # por movimiento (mci) deforma todo cuando la cámara se mueve (el cartel de la v2 del
    # "día de trabajo" salió destrozado): con paneo, mezcla de cuadros, que no inventa formas.
    lenta = "fps=30"
    if vel < 0.8:
        vs = ventanas_del_tramo(movimiento_de(src), t["desde"], t["hasta"])
        paneo = sum(v["paneo"] for v in vs) / max(1, len(vs))
        lenta = ("minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if paneo < PANEO
                 else "framerate=fps=30:interp_start=0:interp_end=255")
    filtros.append(lenta)
    filtros += ["scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos",
                "crop=1080:1920", "setsar=1"]
    filtros += realce(ancho_util, t.get("realce", False))
    destino = destino.resolve()
    correr([FFMPEG, "-v", "error", "-y", "-ss", f"{t['desde']:.3f}", "-t", f"{tramo:.3f}",
            "-i", str(Path(src).resolve()), "-vf", ",".join(filtros), "-t", f"{dur:.3f}", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
            str(destino)], cwd=destino.parent)
    destino.with_suffix(".trf").unlink(missing_ok=True)
    nota = f"estabilizado (temblor {temblor:.2f})" if estab and temblor else ("estabilizado" if estab else
           (f"sin estabilizar (temblor {temblor:.2f})" if temblor is not None else "sin estabilizar"))
    print(f"  {destino.stem}: {t['desde']:7.2f}-{t['hasta']:7.2f}s → {dur:.3f}s "
          f"(×{vel:.2f}) recorte {crop or '—'} · {nota}")

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    preparar(Path(ap.parse_args().pedido))


if __name__ == "__main__":
    main()
