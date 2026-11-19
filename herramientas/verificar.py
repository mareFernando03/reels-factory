"""Control de calidad de un reel renderizado.

Uso:
    uv run python herramientas/verificar.py <reel.mp4> [--cada 1.0] [--pedido pedidos/<pedido>]

Chequea lo técnico que pide Instagram y arma <reel>-qa.jpg: fotogramas cada
`--cada` segundos con la zona segura oficial de Meta para Reels sombreada en
rojo (reel: 14 % arriba, 35 % abajo, 6 % a cada lado; historia: 14 / 20 / 6; ver
conocimiento/02-anatomia-del-reel.md). --formato historia | foto cambia la zona y el tamaño;
una imagen (.jpg/.png) se chequea como foto fija. Texto o logo en lo rojo = criterio T5 de
la rúbrica falla. Esa revisión visual la hace Claude.

Con --pedido también chequea el ritmo del guion contra conocimiento/ritmo.yaml
(criterios R2 y O12): duración total y duración de cada toma según su `rol`
(toma | revelado | barrido; si falta, se deduce de `que`: "WOW"/"REVELADO" → revelado,
"barrido" → barrido).
"""

import argparse
import math
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from comun import RAIZ, duraciones, fotograma, hoja_de_contactos, probar  # noqa: E402

# Zona segura de Meta (2026): (arriba, abajo, lados) y tamaño esperado por formato.
# Foto y carrusel no tienen interfaz encima en el feed: solo se chequea el tamaño 3:4.
FORMATOS = {
    "reel": ((0.14, 0.35, 0.06), (1080, 1920)),
    "historia": ((0.14, 0.20, 0.06), (1080, 1920)),
    "foto": ((0.0, 0.0, 0.0), (1080, 1440)),
}


def sombrear(img_path, zona):
    ARRIBA, ABAJO, LADOS = zona
    import cv2
    im = cv2.imread(str(img_path))
    h, w = im.shape[:2]
    capa = im.copy()
    rojo = (0, 0, 255)
    cv2.rectangle(capa, (0, 0), (w, int(h * ARRIBA)), rojo, -1)
    cv2.rectangle(capa, (0, int(h * (1 - ABAJO))), (w, h), rojo, -1)
    cv2.rectangle(capa, (0, 0), (int(w * LADOS), h), rojo, -1)
    cv2.rectangle(capa, (int(w * (1 - LADOS)), 0), (w, h), rojo, -1)
    cv2.imwrite(str(img_path), cv2.addWeighted(capa, 0.35, im, 0.65, 0))


ALIAS_FORMATO = {"resultado": "fotos", "transformación": "transformacion"}


def rol(toma):
    if toma.get("rol"):
        return toma["rol"]
    que = str(toma.get("que", "")).lower()
    if "wow" in que or "revelado" in que:
        return "revelado"
    return "barrido" if "barrido" in que else "toma"


def chequear_ritmo(pedido):
    """R2 y O12: el guion contra el preset del formato. Devuelve [(nombre, ok, valor)]."""
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    presets = yaml.safe_load((RAIZ / "conocimiento" / "ritmo.yaml").read_text(encoding="utf-8"))
    pedido_yaml = pedido / "pedido.yaml"
    pedido_v = yaml.safe_load(pedido_yaml.read_text(encoding="utf-8")) if pedido_yaml.exists() else {}
    marca = yaml.safe_load((RAIZ / "marcas" / guion["marca"] / "marca.yaml").read_text(encoding="utf-8"))
    formato = ALIAS_FORMATO.get(guion.get("formato"), guion.get("formato"))
    preset = presets["formatos"].get(formato)
    if not preset:
        return [(f"ritmo: formato '{formato}' sin preset en ritmo.yaml", False, "—")]
    ajuste = (guion.get("ritmo") or (pedido_v or {}).get("ritmo")
              or (marca.get("preferencias") or {}).get("ritmo") or "medio")
    if ajuste not in presets["ajustes"]:  # guiones del 02/10: `ritmo` era una descripción libre
        return [(f"ritmo: guion con formato viejo (`ritmo` debe ser {' | '.join(presets['ajustes'])}, "
                 f"no «{str(ajuste)[:40]}»)", False, "—")]
    f = presets["ajustes"][ajuste]
    todas = guion.get("tomas") or guion.get("escenas") or []
    durs = dict(zip((id(t) for t in todas), duraciones(guion, pedido)))
    tomas = [t for t in todas if not t.get("cierre")]
    if guion.get("escenas") and tomas:  # composición a medida: la última escena es el cierre
        tomas = tomas[:-1] if "cierre" in str(tomas[-1].get("que", "")).lower() else tomas
    total = sum(durs[id(t)] for t in tomas)
    d0, d1 = (x * f for x in preset["duracion"])
    out = [(f"R2 duración {d0:.0f}-{d1:.0f} s ({formato}, ritmo {ajuste})", d0 <= total <= d1, f"{total:.1f} s")]
    fuera = []
    for t in tomas:
        r = rol(t)
        if r == "barrido":
            continue
        lo, hi = (x * f for x in preset["revelado" if r == "revelado" else "toma"])
        if t.get("voz") is True:  # una frase dura lo que dura: no se acelera ni se corta
            hi = max(hi, VOZ_MAX)
        if t.get("tarjetas") and t.get("foco"):  # una tarjeta por vez y el repaso: la imagen cambia adentro
            hi = max(hi, FOCO_MAX * (len(t["tarjetas"]) + 1))
        dur = durs[id(t)]
        if not (lo - 0.01 <= dur <= hi + 0.01):
            fuera.append(f"{t['n']}:{dur:.1f}s ({r} {lo:.1f}-{hi:.1f})")
    cierre = [durs[id(t)] for t in todas if t not in tomas]
    if cierre:  # el cierre de marca no puede alargar el reel después de la recompensa
        out.append(("R3 cierre ≤ 2 s", cierre[-1] <= 2.01, f"{cierre[-1]:.2f} s"))
    if preset.get("cambio_visual_max"):  # relato: la toma puede ser larga si la imagen cambia adentro
        quieto, donde = sin_cambio_visual(tomas, durs)
        out.append((f"O12b imagen sin cambio ≤ {preset['cambio_visual_max']:.0f} s (cortes e insertos)",
                    quieto <= preset["cambio_visual_max"] + 0.01, f"{quieto:.1f} s (toma {donde})"))
    bpm_ok = preset["bpm"][0] <= guion["bpm"] <= preset["bpm"][1]
    out.append((f"O12 tomas en rango ({len(tomas)} tomas, {guion['bpm']} bpm"
                f"{'' if bpm_ok else ' fuera de ' + str(preset['bpm'])})", not fuera,
                ", ".join(fuera) if fuera else "todas"))
    return out


def sin_cambio_visual(tomas, durs):
    """(segundos, toma) del tramo más largo sin un cambio de imagen: cada toma arranca con un corte,
    y cada inserto cambia la imagen al entrar y al salir. En un mapa, también cuenta cada ruta que
    empieza o termina de dibujarse o se apaga, y cada lugar que aparece o se va (la imagen cambia
    adentro: el gancho de «El Conquistador» daba 8,5 s quieto con dos rutas dibujándose). Los
    acercamientos lentos no cuentan."""
    peor, donde = 0.0, None
    for t in tomas:
        dur = durs[id(t)]
        tiempos = []
        for i in t.get("insertos") or []:
            if i.get("tipo", "imagen") == "rotulo":
                continue
            tiempos += [i.get("desde", 0.0), i.get("hasta", dur)]
            if i.get("tipo") == "mapa":
                for rt in i.get("rutas") or []:
                    tiempos += list(rt.get("dibujar") or []) + ([rt["apagar"]] if "apagar" in rt else [])
                for lg in i.get("lugares") or []:
                    tiempos += [lg.get("desde", 0.0)] + ([lg["hasta"]] if "hasta" in lg else [])
        marcas = sorted({0.0, dur, *(min(max(x, 0.0), dur) for x in tiempos)})
        tramo = max(b - a for a, b in zip(marcas, marcas[1:])) if len(marcas) > 1 else dur
        if tramo > peor:
            peor, donde = tramo, t["n"]
    return peor, donde


FOCO_MAX = 1.5         # O12: por tarjeta en foco (armar_pop.py), más el repaso de todas juntas
VOZ_MAX = 4.0          # O12: tope de una toma con `voz: true` (la frase entera, ver 09-audio.md)
AMPLIACION_MAX = 1.5   # Q1: más que esto, la toma se ve blanda (12-calidad-percibida.md)
PALABRAS_MAX = 10      # más palabras por texto y la gente deja de leer


def chequear_calidad(pedido):
    """Q1 (ampliación por toma), textos largos y Q2 (la voz se entiende en el reel terminado)."""
    import json
    import re as _re
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    out = []
    # Q1: cuánto se amplía cada toma para llenar 1080×1920
    amp = {}
    for t in guion.get("tomas") or []:
        if t.get("cierre") or not t.get("fuente") or t.get("tarjetas"):  # con tarjetas, el clip va desenfocado de fondo
            continue
        m = probar(RAIZ / t["fuente"])
        if not m["alto"]:
            continue
        enc = t.get("encuadre")
        if enc:
            h = (enc.get("abajo", 1) - enc.get("arriba", 0)) * m["alto"]
            amp[t["n"]] = 1920 / max(1, h)
        else:
            amp[t["n"]] = max(1080 / m["ancho"], 1920 / m["alto"])
    if amp:
        blandas = [f"{n:02d} ×{f:.1f}" for n, f in sorted(amp.items()) if f > AMPLIACION_MAX]
        out.append((f"Q1 ampliación ≤ {AMPLIACION_MAX}× (máx. ×{max(amp.values()):.1f})", not blandas,
                    ", ".join(blandas) if blandas else "todas"))
    # textos largos
    largos = [f"{tx['id']} ({len(tx['texto'].split())})" for tx in guion.get("textos") or []
              if len(str(tx.get("texto", "")).split()) > PALABRAS_MAX]
    out.append((f"textos de ≤ {PALABRAS_MAX} palabras", not largos, ", ".join(largos) if largos else "todos"))
    # X5: en un relato, todas las tomas son su voz. Si la detección automática no la vio en una toma,
    # esa toma queda muda en la mezcla (pasó en «El Extranjero» v6: 4 s de silencio en la reflexión)
    if guion.get("formato") == "relato":
        archivo_v = pedido / "analisis" / "voz.json"
        con_voz = set((json.loads(archivo_v.read_text(encoding="utf-8")).get("tomas") or {}) if archivo_v.exists() else {})
        mudas = [str(t["n"]) for t in guion.get("tomas") or [] if not t.get("cierre") and str(t["n"]) not in con_voz]
        out.append(("X5 relato: todas las tomas llevan su voz", not mudas,
                    "todas" if not mudas else f"mudas: {', '.join(mudas)} (poner voz: true)"))

    # Q2: la voz se entiende en la mezcla final (Whisper sobre el reel terminado)
    archivo = pedido / "analisis" / "voz.json"
    voces = (json.loads(archivo.read_text(encoding="utf-8")).get("tomas") or {}) if archivo.exists() else {}
    if voces:
        from audio import archivo_final, musica_del_pedido
        from voz import detectar
        final = pedido / "salida" / archivo_final(musica_del_pedido(pedido, guion)[0])
        if final.exists():
            norm = lambda x: _re.sub(r"[^\wáéíóúñü]", "", x.lower())  # noqa: E731
            inicio, t0 = {}, 0.0
            tomas = guion.get("tomas") or []
            for toma, d in zip(tomas, duraciones(guion, pedido)):
                inicio[toma["n"]] = (t0, d)
                t0 += d
            fallan = []
            # lo que se dijo, de la misma fuente que los subtítulos (con subtitulos_fuente, la transcripción entera:
            # una toma que la detección no reconoció queda con la lista vacía y daba 0 % aunque se oyera bien)
            from armar_pop import voces as voces_con_palabras
            dichas = voces_con_palabras(pedido, guion)
            for n, info in voces.items():
                info = dichas.get(int(n), info)
                a, d = inicio[int(n)]
                # con contexto (en 1-2 s sueltos Whisper duda del idioma y descarta la voz aunque se oiga bien)
                # y de a tramos de ≤8 s (en una toma de 15 s llegó a devolver «absurdo o el abuelo»)
                x0, x1, oido = max(0.0, a - CONTEXTO_Q2), a + d + CONTEXTO_Q2, set()
                partes = max(1, math.ceil((x1 - x0) / 8))
                for k in range(partes):
                    ini = x0 + k * (x1 - x0) / partes
                    oido |= {norm(w["w"]) for w in detectar(final, max(0.0, ini - 0.3), ini + (x1 - x0) / partes + 0.3,
                                                             estricto=False)["palabras"]}
                dicho = [norm(w["w"]) for w in info["palabras"]]
                tasa = sum(1 for w in dicho if w in oido) / max(1, len(dicho))
                if tasa < 0.6:
                    fallan.append(f"{int(n):02d} ({tasa:.0%})")
            out.append((f"Q2 la voz se entiende ({len(voces)} tomas)", not fallan,
                        ", ".join(fallan) if fallan else "Whisper la transcribe en la mezcla final"))
    return out


def chequear_musica(pedido):
    """Q5: el tema (modo archivo) no se repite en otro pedido: con la misma música todos los reels se ven iguales."""
    from musica import usados
    musica = (yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8")) or {}).get("musica") or {}
    if not isinstance(musica, dict) or musica.get("modo") != "archivo" or not musica.get("fuente"):
        return []
    otros = [p for p in usados().get(Path(musica["fuente"]).as_posix(), []) if p != pedido.resolve().name]
    return [("Q5 música no repetida en otro reel", not otros,
             Path(musica["fuente"]).name + (f" — también en {', '.join(otros)}" if otros else ""))]


def chequear_voz(pedido):
    """X3: si alguien habla, el reel lleva subtítulos (y su voz se conserva: voz.py, audio.py)."""
    import json
    archivo = pedido / "analisis" / "voz.json"
    tomas = (json.loads(archivo.read_text(encoding="utf-8")).get("tomas") or {}) if archivo.exists() else {}
    if not tomas:
        return []
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    index = pedido / "render" / "index.html"
    con_subs = index.exists() and 'class="clip subtitulo"' in index.read_text(encoding="utf-8")
    textos = "; ".join(f"{int(n):02d} «{t['texto'][:30]}»" for n, t in sorted(tomas.items()))
    ok = con_subs or guion.get("subtitulos") is False
    return [(f"X3 voz con subtítulos ({len(tomas)} tomas con voz)", ok,
             textos + ("" if con_subs else " — sin subtítulos" + (" (apagados en el guion)" if guion.get("subtitulos") is False else "")))]


def titulos_del_render(pedido):
    """[(texto del guion, base, caja)] de cada título como quedó en render/index.html: su base,
    su modo (bloques o sombra) y su cuerpo, si armar_pop lo achicó; medido con la fuente de la marca."""
    index = pedido / "render" / "index.html"
    if not index.exists():
        return [], None
    from armar_pop import medidas
    from legibilidad import franja_titulo
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    html_ = index.read_text(encoding="utf-8")
    med, out = medidas(guion), []
    for tx in guion.get("textos", []):
        if tx["id"] == "cta" or tx.get("tipo", "titulo") != "titulo":
            continue
        tag = re.search(rf'<div class="([^"]*)" id="x-{re.escape(tx["id"])}"([^>]*)><div><h2([^>]*)>', html_)
        if not tag:
            continue
        m = re.search(r"bottom: calc\(100% - ([\d.]+%)\)", tag.group(2))
        base = m.group(1) if m else guion.get("texto_base", "62%")
        px = re.search(r"font-size: ([\d.]+)px", tag.group(3))
        escala = float(px.group(1)) / (med["tam_largo"] if "largo" in tag.group(1).split() else med["tam"]) if px else 1.0
        out.append((tx, base, franja_titulo(tx["texto"], base, "bloques" in tag.group(1).split(), escala=escala, **med)))
    return out, guion


def chequear_zona(pedido):
    """T5 (bloqueante): cada título entre el 14 % y el 65 % del alto. Arriba lo tapan el nombre de la
    cuenta y los botones, y la grilla del perfil (3:4) corta la portada; abajo, la descripción."""
    titulos, _ = titulos_del_render(pedido)
    if not titulos:
        return []
    from caras import ZONA
    from legibilidad import ALTO
    fuera = [f"«{tx['texto']}» ({caja[1] / ALTO:.0%}-{caja[3] / ALTO:.0%})" for tx, _, caja in titulos
             if caja[1] < ZONA[0] * ALTO - 2 or caja[3] > ZONA[1] * ALTO + 2]
    return [(f"títulos en la zona segura, {ZONA[0]:.0%}-{ZONA[1]:.0%} (T5, {len(titulos)} títulos)", not fuera,
             ", ".join(fuera) if fuera else "todos")]


def chequear_caras(pedido):
    """Títulos que tapan una cara (YuNet, caras.py) a la altura que quedaron en render/index.html.
    Rozar la cabeza (frente, pelo, mentón) se informa aparte: a veces no hay lugar libre (selfie muy cerca)."""
    titulos, guion = titulos_del_render(pedido)
    if not titulos:
        return []
    from armar_pop import caras_en_tomas
    from caras import cabeza, cruce
    tapan, rozan, n = [], [], 0
    for tx, base, caja in titulos:
        caras = caras_en_tomas(pedido, guion, tx["tomas"])
        n += 1
        if cruce(caja, caras):
            tapan.append(f"{tx['id']} (base {base})")
        elif cruce(caja, [cabeza(c) for c in caras]):
            rozan.append(tx["id"])
    valor = ", ".join(tapan) if tapan else "ninguno"
    if rozan:
        valor += f"; rozan la cabeza: {', '.join(rozan)}"
    return [(f"títulos sin tapar caras ({n} títulos)", not tapan, valor)]


# Avisos de `hyperframes check` que el motor produce a propósito y no son defectos:
# la entrada palabra por palabra desborda su máscara unos px (text_box_overflow) y las
# composiciones son de un solo archivo (sin subcomposiciones ni ids para el Studio).
CHECK_IGNORAR = {"text_box_overflow", "nested_structure_needs_subcomposition",
                 "studio_missing_editable_id", "timeline_track_too_dense",
                 "duplicate_media_discovery_risk"}   # insertos en modo cuadro: la obra y su fondo desenfocado son la misma imagen
ENTRADA = 0.8  # s que tarda en asentarse un texto (palabras, resaltador, píldoras)
CONTEXTO_Q2 = 2.5     # s de más a cada lado al transcribir una toma: en 4 s sueltos Whisper oyó «pues» por «por qué entonces sentimos»
TANDAS_A_LA_VEZ = 2   # navegadores de `check` en paralelo: con 3 y un video de 2 min, Windows se quedó sin memoria (04/10)


def tiempos_de_texto(index_html):
    """Instantes en que medir los textos: en cada capa temporizada (`div.clip`: títulos,
    stickers, escenas a medida, cierre), ya terminada la entrada y al final de su tramo.

    Durante la entrada no se mide: las palabras suben dentro de una máscara y `check`
    no ve el recorte, así que compara texto todavía invisible contra el video de atrás.
    """
    out, entradas, subtitulo_medido = [], [], False
    for tag in re.findall(r"<div [^>]*data-start=[^>]*>", index_html):
        clase = re.search(r'class="([^"]*)"', tag)
        clases = clase.group(1).split() if clase else []
        if "clip" not in clases:
            continue
        a = float(re.search(r'data-start="([\d.]+)"', tag).group(1))
        d = float(re.search(r'data-duration="([\d.]+)"', tag).group(1))
        entradas.append(a)
        if "subtitulo" in clases:
            # van todos en la misma píldora opaca: con medir uno se mide el estilo (en un relato de 2 min
            # eran 80 de los 94 textos y la mayor parte de la hora y media de check)
            if subtitulo_medido:
                continue
            subtitulo_medido = True
        # sobre video, el fondo cambia mientras el título está: se mide al asentarse y al final.
        # Placas, rótulos, insertos y subtítulos tienen su propio fondo: alcanza con una medición
        out += [a + min(2.0, d * 0.6)] + ([a + d - 0.15] if "titulo" in clases or "sticker" in clases else [])
    # el final de una capa puede caer en la entrada de la siguiente: ese instante tampoco vale
    out = [t for t in out if not any(0 <= t - a < ENTRADA for a in entradas)]
    juntos = []  # los instantes a menos de 0,3 s de otro ya elegido no suman información
    for t in sorted(out):
        if not juntos or t - juntos[-1] >= 0.3:
            juntos.append(round(t, 3))
    return juntos


def chequear_composicion(render):
    """`hyperframes check` sobre render/index.html, con el contraste medido en cada texto.

    El pase de contraste usa a lo sumo 5 instantes por corrida, así que se corre por
    tandas. Devuelve [(nombre, ok, valor)] y la lista de avisos que importan.
    """
    import json

    from render import npx
    html_ = (render / "index.html").read_text(encoding="utf-8")
    tiempos = tiempos_de_texto(html_) or [None]
    from concurrent.futures import ThreadPoolExecutor

    def correr(tanda):
        return npx("check --json" + ("" if tanda == [None] else " --at " + ",".join(f"{t}" for t in tanda)), render)

    tandas = [tiempos[k:k + 5] for k in range(0, len(tiempos), 5)]
    # cada tanda abre su navegador y carga el video: de a TANDAS_A_LA_VEZ en paralelo en vez de una por vez
    with ThreadPoolExecutor(max_workers=TANDAS_A_LA_VEZ) as pool:
        resultados = list(pool.map(correr, tandas))
    avisos, vistos, medidos = [], set(), 0
    for res in resultados:
        try:
            d = json.loads(res.stdout)
        except json.JSONDecodeError:
            return [("hyperframes check", False, (res.stderr or res.stdout).strip()[-300:])], []
        medidos += d["contrast"].get("checked", 0)
        for etapa in ("lint", "runtime", "layout", "contrast"):
            for f in d[etapa]["findings"]:
                if f["code"] in CHECK_IGNORAR or f["severity"] == "info":
                    continue
                clave = (f["code"], f.get("selector"), f.get("text"), f.get("time") if etapa == "contrast" else None)
                if clave not in vistos:
                    vistos.add(clave)
                    avisos.append(f)
    contraste = [f for f in avisos if f["code"] == "contrast_aa_failure"]
    otros = [f for f in avisos if f["code"] != "contrast_aa_failure"]
    peor = min((f["ratio"] for f in contraste), default=None)
    return [
        (f"contraste ≥ 3:1 ({medidos} textos medidos en {len(tiempos)} instantes)", not contraste,
         "todos" if not contraste else f"{len(contraste)} fallan, el peor {peor}:1"),
        ("check sin errores", not any(f["severity"] == "error" for f in otros),
         f"{len(otros)} avisos" if otros else "ninguno"),
    ], avisos


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reel")
    ap.add_argument("--cada", type=float, default=1.0)
    ap.add_argument("--pedido", help="chequea también el ritmo del guion (R2, O12)")
    ap.add_argument("--formato", choices=sorted(FORMATOS), default="reel")
    ap.add_argument("--sin-check", action="store_true",
                    help="no correr hyperframes check sobre render/ (contraste; tarda ~20 s por cada 5 instantes)")
    a = ap.parse_args()
    reel = Path(a.reel)
    zona, (W, H) = FORMATOS[a.formato]
    if reel.suffix.lower() in (".jpg", ".jpeg", ".png"):
        import cv2
        alto, ancho = cv2.imread(str(reel)).shape[:2]
        ok = (ancho, alto) == (W, H)
        print(f"  {'✓' if ok else '✗'} {W}x{H}: {ancho}x{alto}")
        if any(zona):
            hoja = reel.with_name(f"{reel.stem}-qa.jpg")
            import shutil
            shutil.copy2(reel, hoja)
            sombrear(hoja, zona)
            print(f"→ {hoja}")
        sys.exit(0 if ok else 1)
    m = probar(reel)
    # reels: hasta 3 min se recomiendan a quienes no siguen la cuenta (Instagram, enero de 2025; 08-ritmo.md).
    # El tope de 90 s venía del límite viejo; cuánto dura cada formato lo dice ritmo.yaml (R2)
    maximo = 60 if a.formato == "historia" else 180
    chequeos = [
        (f"{W}x{H}", (m["ancho"], m["alto"]) == (W, H), f"{m['ancho']}x{m['alto']}"),
        ("H.264", m["codec"] == "h264", m["codec"]),
        ("30 fps", abs(m["fps"] - 30) < 0.5, m["fps"]),
        (f"3 a {maximo} s", 3 <= m["duracion"] <= maximo, f"{m['duracion']} s"),
        ("peso < 100 MB", reel.stat().st_size < 100e6, f"{reel.stat().st_size / 1e6:.1f} MB"),
    ]
    for nombre, ok, valor in chequeos:
        print(f"  {'✓' if ok else '✗'} {nombre}: {valor}")
    # el audio se mira en el archivo que se sube (reel-con-audio.mp4 o reel-efectos.mp4), no en reel.mp4
    final = reel
    if a.pedido and (Path(a.pedido) / "plan" / "guion.yaml").exists():
        from audio import archivo_final, musica_del_pedido
        guion = yaml.safe_load((Path(a.pedido) / "plan" / "guion.yaml").read_text(encoding="utf-8"))
        modo, _ = musica_del_pedido(Path(a.pedido), guion)
        if (Path(a.pedido) / "salida" / archivo_final(modo)).exists():
            final = Path(a.pedido) / "salida" / archivo_final(modo)
            m["audio"] = probar(final)["audio"]
    nota = " (la canción la pone Ana en Instagram)" if final.name == "reel-efectos.mp4" else ""
    print(f"  · audio de {final.name}: {'sí' if m['audio'] else 'no'}{nota}")
    # el ritmo no corta la entrega: lo pesa la rúbrica (las historias no tienen guion)
    if a.pedido and (Path(a.pedido) / "plan" / "guion.yaml").exists():
        zona_ok = chequear_zona(Path(a.pedido))   # T5 sí corta: es bloqueante
        chequeos += zona_ok
        for nombre, ok, valor in zona_ok:
            print(f"  {'✓' if ok else '✗'} {nombre}: {valor}")
        for nombre, ok, valor in (chequear_ritmo(Path(a.pedido)) + chequear_caras(Path(a.pedido))
                                  + chequear_voz(Path(a.pedido)) + chequear_calidad(Path(a.pedido))
                                  + chequear_musica(Path(a.pedido))):
            print(f"  {'✓' if ok else '✗'} {nombre}: {valor}")
    render = Path(a.pedido) / "render" if a.pedido else None
    if render and (render / "index.html").exists() and not a.sin_check:
        # contraste y errores de la composición sí cortan: un título ilegible no se entrega
        comp, avisos = chequear_composicion(render)
        chequeos += comp
        for nombre, ok, valor in comp:
            print(f"  {'✓' if ok else '✗'} {nombre}: {valor}")
        for f in avisos:
            donde = f" «{f['text']}» a los {f['time']} s" if f.get("text") else ""
            print(f"      · {f['code']}{donde}: {f['message'][:140]}")

    tmp = reel.parent / f".{reel.stem}-qa"
    tiempos, t = [], a.cada / 2
    while t < m["duracion"]:
        tiempos.append(round(t, 2))
        t += a.cada
    fotos = [fotograma(reel, t, tmp / f"{k:03d}.jpg", ancho=270) for k, t in enumerate(tiempos)]
    for f in fotos:
        sombrear(f, zona)
    hoja = hoja_de_contactos(fotos, reel.with_name(f"{reel.stem}-qa.jpg"),
                             [f"{t:.1f}s" for t in tiempos], columnas=7)
    for f in fotos:
        f.unlink()
    tmp.rmdir()
    print(f"→ {hoja}")
    sys.exit(0 if all(ok for _, ok, _ in chequeos) else 1)


if __name__ == "__main__":
    main()
