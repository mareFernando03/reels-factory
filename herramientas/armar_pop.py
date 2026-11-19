"""El motor de reels: arma render/index.html con la dirección de arte de la marca.

Uso:
    uv run python herramientas/armar_pop.py pedidos/<pedido> [--texto gancho="…"]

Capas (de abajo hacia arriba):
  video  → cada toma en .trans (transición de entrada) > .marco (acercamiento) > <video>
  look   → corrección de color + calidez + viñeta + grano de película (disimula fuentes chicas)
  luz    → destello de luz para la transición "luz"
  textos → títulos palabra por palabra con resaltador; stickers de pasos
  cierre → apertura circular sobre la placa clara de la marca, logo, CTA y destellos

Estilo (tokens, CSS base, look, palabras, destellos): estilo.py, con lo que pise `estilo:` en
marca.yaml (por defecto, salon-pop). Render: render.py.

Guion (plan/guion.yaml):
  marca, bpm, tomas[]: {n, fuente, desde, hasta, beats, que, push: {de, a, ease, origen}, cierre}
  tomas[].entrada: corte | golpe | zoom | barrido | luz | temblor | humo
  tomas[].solape:  segundos que el clip sigue debajo de la toma siguiente (para el iris)
  tomas[].comparar: pantalla dividida antes | después (clips NNa/NNb de preparar_clips.py):
                    la línea barre hasta la mitad, etiquetas arriba, y al final el después ocupa todo
  tomas[].insertos: lo que se ve encima de la toma mientras la voz sigue (corte en L; 13-divulgacion.md).
                    Tiempos `desde`/`hasta` en segundos desde el arranque de la toma:
      { tipo: imagen, archivo, desde, hasta, modo: cuadro | llena, mover: {de, a, origen}, pan: [x0, x1],
        foco: "50% 30%", rotulo: "ALBERT CAMUS · 1913-1960" }
          cuadro (default): la obra entera, enmarcada, sobre ella misma desenfocada (no se amplía de más);
          llena: cubre el cuadro y se mueve (pan en % del ancho sobrante, para apaisadas)
      filtro: bn (en cualquier inserto) lo pasa a blanco y negro: el gancho como flash-forward, distinto del resto
      { tipo: placa, texto, destacar, pie, desde, hasta }   palabra clave o cita grande sobre la placa de la marca (título de
                                                        sección); mientras está, no hay subtítulos (los repetiría)
      { tipo: rotulo, texto, desde, hasta, alto: "58%" }  etiqueta corta (un nombre) sin tapar el video
      { tipo: mapa, desde, hasta, lon: [-115, 15], centro_lat: 20, mover: {de, a, origen},
        rutas: [{de: [lon, lat], a: [lon, lat], curva: 0.18, color: acento | claro | secundario, dibujar: [t0, t1], apagar: t}],
        lugares: [{nombre, en: [lon, lat], desde, hasta, lado: der | izq | arriba}] }
          mapa a pantalla completa (mapa.py, costas de Natural Earth): la ruta de un viaje se dibuja de a poco
  tomas[].subtitulos: false   esa toma sin subtítulos (p. ej. el gancho, que lleva su versión corta como título)
  tomas[].tarjetas: [rutas de imágenes] que entran de a una por beat (back.out, giro leve) sobre el
                    clip de la toma desenfocado: vouchers, productos, precios. `zona: [arriba, abajo]`
                    en % del alto (default [30, 65]); se superponen si no entran.
                    `columnas: 2`: en grilla (collage de fotos). `cada: 0.5`: una cada medio beat.
                    `foco: true`: una por vez, grande (1000 px), `foco_beats` cada una (default 2),
                    y al final todas juntas: para que se lea la letra chica (vouchers, precios)
  textos[]: {id, texto, destacar, tipo: titulo|sticker|encabezado, tomas: [n…]}
            encabezado: fijo arriba durante muchas tomas, una placa crema de una línea (base 19 %); con más de
                        28 caracteres va en dos líneas (subir la base a ~21,5 % para que no pase el 14 %); `tam: 58` lo agranda (default 50 px)
  texto_base: línea inferior preferida de los títulos (default 62 %); crecen hacia arriba, nunca pasan el 65 %
  textos[].base: la misma línea para un solo título, fija. Si falta, el motor busca caras en las
                 tomas del título (caras.py) y usa la línea libre más cercana a texto_base
  textos[].fondo: sombra | bloques. Si falta, se mide el brillo detrás del título en sus clips
                  (legibilidad.py): fondo claro → bloques del resaltador; oscuro o medio → sombra difusa
  subtitulos: false   apaga los subtítulos de la voz. Por defecto, cada toma con voz
                      (preparar_clips.py, voz.py) los lleva, de a 2-4 palabras, a la altura del 64 %
  subtitulos_base: "30%"   otra línea inferior para los subtítulos (p. ej. arriba de la cabeza cuando
                           la cara llena el cuadro); los títulos esquivan esa franja
  subtitulos_correcciones: {Marzot: Meursault}   palabras que Whisper escribió mal (nombres propios)
  subtitulos_fuente: analisis/habla-original.json   transcripción de la fuente entera ({palabras: [{w, ini, fin}]}
                     en segundos de la fuente): cada toma toma las palabras que arrancan en su tramo. Para relatos
                     cortados en tramos continuos: transcribir cada toma suelta pierde o parte palabras en los bordes.
                     Con dos fuentes (dos personas grabadas por separado): {fuente: archivo}, una por fuente
  desfase: segundos que se alarga la primera toma para que los cortes caigan en los
           tiempos de una canción cuyo primer tiempo 1 no está en 0 (analizar_audio.py)
Tiempos: todos sobre la grilla de beats.
"""

import argparse
import html
import json
import shutil
import sys
from functools import lru_cache
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import mapa  # noqa: E402
from comun import duraciones  # noqa: E402
from caras import ZONA, con_push, detectar, elegir_base  # noqa: E402
from legibilidad import ALTO, brillo, franja_titulo, tratamiento  # noqa: E402
from estilo import (SUBTITULO_FRANJA, capas_look, copiar_assets, css, de_marca, destellos,  # noqa: E402
                    grano_tween, palabras, r)

RAIZ = Path(__file__).resolve().parent.parent


ESCALA_MIN = 0.7   # un título se achica hasta acá para entrar en la zona segura; si ni así entra, avisa
FOCO_ANCHO = 1000  # tarjetas en foco: casi todo el ancho, para que se lea la letra chica


def tarjetas(pedido, toma, a, dur, beat, tw, ancho=820, giros=(-2.2, 1.6, -1.2, 2.0)):
    """Capa de tarjetas sobre el clip desenfocado.

    Por defecto, cada imagen entra en un beat, apiladas en la zona (se superponen si no entran).
    `columnas: 2` las acomoda en grilla (un collage de fotos), centrada en la zona.
    `cada: 0.5` entra una cada medio beat (default 1).
    `foco: true` muestra una por vez, grande en el centro de la zona, `foco_beats` beats cada una
    (default 2); al final vuelven todas juntas, apiladas, en lo que queda de la toma.
    """
    import cv2
    destino = pedido / "render" / "assets" / "tarjetas"
    destino.mkdir(parents=True, exist_ok=True)
    cols = int(toma.get("columnas", 1))
    if cols > 1:  # 45 px de margen y 30 entre columnas
        ancho = (1080 - 90 - 30 * (cols - 1)) / cols
    altos, nombres = [], []
    for i, ruta in enumerate(toma["tarjetas"]):
        src = RAIZ / ruta
        nombre = f"{toma['n']:02d}-{i}{src.suffix.lower()}"
        shutil.copy2(src, destino / nombre)
        h, w = cv2.imread(str(src)).shape[:2]
        altos.append(ancho * h / w)
        nombres.append(nombre)
    z0, z1 = (float(x) * 1920 / 100 for x in toma.get("zona", [30, 65]))
    if cols > 1:
        filas = [altos[k:k + cols] for k in range(0, len(altos), cols)]
        alto_total = sum(max(f) for f in filas) + 30 * (len(filas) - 1)
        y = z0 + (z1 - z0 - alto_total) / 2
        pos = []
        for f in filas:
            pos += [((1080 - cols * ancho - 30 * (cols - 1)) / 2 + c * (ancho + 30), y + (max(f) - h) / 2)
                    for c, h in enumerate(f)]
            y += max(f) + 30
    else:
        libre = (z1 - z0) - sum(altos)
        paso = libre / max(1, len(altos) - 1) if len(altos) > 1 else 0  # negativo = se superponen
        y, pos = z0, []
        for h in altos:
            pos.append(((1080 - ancho) / 2, y))
            y += h + paso
    items = []
    foco, cada = toma.get("foco"), float(toma.get("cada", 1))
    fb = float(toma.get("foco_beats", 2)) * beat
    for i, (nombre, h, (x, y)) in enumerate(zip(nombres, altos, pos)):
        tid = f"tj{toma['n']}-{i}"
        g = giros[i % len(giros)]
        items.append(f'<img class="tarjeta" id="{tid}" src="assets/tarjetas/{nombre}" alt="" '
                     f'style="top:{y:.0f}px; left:{x:.0f}px; width:{ancho:.0f}px; z-index:{i + 1}; '
                     f'transform: rotate({g}deg)" />')
        if not foco:
            tw.append(f'tl.fromTo("#{tid}", {{ y: 140, scale: 0.82, opacity: 0, rotation: {g * 4} }}, '
                      f'{{ y: 0, scale: 1, opacity: 1, rotation: {g}, duration: 0.42, ease: "back.out(1.7)" }}, {r(a + 0.05 + i * cada * beat)});')
            continue
        # en foco: centrada y ampliada a FOCO_ANCHO (escala desde el centro de la tarjeta), casi derecha
        s = FOCO_ANCHO / ancho
        dy = (z0 + z1) / 2 - (y + h / 2)
        t0, t1 = a + i * fb, a + (i + 1) * fb
        # todo fromTo con valores explícitos: el render salta a cualquier cuadro (seek) y un `to`
        # tomaría como partida lo que hubiera en ese momento
        quieta = f"y: {dy:.0f}, rotation: {g * 0.3:.2f}"
        tw.append(f'tl.fromTo("#{tid}", {{ y: {dy + 160:.0f}, scale: {s * 0.8:.3f}, opacity: 0, rotation: {g * 4} }}, '
                  f'{{ {quieta}, scale: {s:.3f}, opacity: 1, duration: 0.45, ease: "back.out(1.6)" }}, {r(t0 + 0.05)});')
        tw.append(f'tl.fromTo("#{tid}", {{ scale: {s:.3f} }}, {{ scale: {s * 1.03:.3f}, duration: {r(fb - 0.75)}, '
                  f'ease: "sine.inOut", immediateRender: false }}, {r(t0 + 0.5)});')
        tw.append(f'tl.fromTo("#{tid}", {{ {quieta}, scale: {s * 1.03:.3f}, opacity: 1 }}, {{ y: {dy - 120:.0f}, opacity: 0, '
                  f'duration: 0.25, ease: "power2.in", immediateRender: false }}, {r(t1 - 0.2)});')
        # el repaso: todas juntas en su lugar de la pila
        tw.append(f'tl.fromTo("#{tid}", {{ y: 90, scale: 0.86, opacity: 0, rotation: {g * 3} }}, '
                  f'{{ y: 0, scale: 1, opacity: 1, rotation: {g}, duration: 0.4, ease: "back.out(1.7)", immediateRender: false }}, '
                  f'{r(a + len(nombres) * fb + 0.05 + i * 0.1)});')
    return (f'      <div class="clip capa-tarjetas" id="tj{toma["n"]}" data-start="{r(a)}" data-duration="{r(dur)}" '
            f'data-track-index="2">{"".join(items)}</div>')


def capa_mapa(ins, iid, reloj, a, colores, tw):
    """Un mapa a pantalla completa (mapa.py) con rutas que se dibujan y lugares que aparecen.
    Los tiempos (`dibujar`, `apagar`, `desde` de los lugares) van desde el arranque de la toma."""
    v = mapa.vista(tuple(ins.get("lon", (-115, 15))), ins.get("centro_lat", 20))
    m = ins.get("mover") or {"de": 1.0, "a": 1.06, "origen": "50% 50%"}
    t0 = a + ins.get("desde", 0)
    t1 = a + ins.get("hasta", ins.get("desde", 0) + 4)
    trazos, lugares = [], []
    for k, rt in enumerate(ins.get("rutas", [])):
        d, largo, (x1, y1) = mapa.ruta(rt["de"], rt["a"], v, rt.get("curva", 0.18))
        color = colores[rt.get("color", "acento")]
        rid = f"{iid}-r{k}"
        trazos.append(f'<path id="{rid}" class="mapa-ruta" d="{d}" stroke="{color}" '
                      f'style="stroke-dasharray: {largo:.0f}; stroke-dashoffset: {largo:.0f}" />'
                      f'<circle id="{rid}p" cx="{x1:.1f}" cy="{y1:.1f}" r="0" fill="{color}" class="mapa-punto" />')
        d0, d1 = (a + x for x in rt.get("dibujar", (ins.get("desde", 0) + 0.3, ins.get("desde", 0) + 2.3)))
        tw.append(f'tl.fromTo("#{rid}", {{ strokeDashoffset: {largo:.0f} }}, {{ strokeDashoffset: 0, duration: {r(d1 - d0)}, ease: "power1.inOut" }}, {r(d0)});')
        tw.append(f'tl.fromTo("#{rid}p", {{ attr: {{ r: 0 }} }}, {{ attr: {{ r: 15 }}, duration: 0.35, ease: "back.out(2.5)" }}, {r(d1 - 0.05)});')
        if "apagar" in rt:
            tw.append(f'tl.fromTo("#{rid}, #{rid}p", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.4, ease: "power1.in", immediateRender: false }}, {r(a + rt["apagar"])});')
    for k, lg in enumerate(ins.get("lugares", [])):
        x, y = mapa.proyectar(*lg["en"], v)
        lid = f"{iid}-l{k}"
        lado = lg.get("lado") if lg.get("lado") in ("izq", "arriba") else "der"
        # el p se ubica con un transform de CSS (translate en %) y lo que se anima es el em de adentro: GSAP
        # pisaba ese transform al animar el p y el punto del lugar quedaba ~120 px corrido de la ruta
        lugares.append(f'<p class="mapa-lugar {lado}" id="{lid}" style="left:{x:.0f}px; top:{y:.0f}px"><em class="ml"><i></i>'
                       f'<span>{html.escape(lg["nombre"])}</span></em></p>')
        tw.append(f'tl.fromTo("#{lid} .ml", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }}, {r(a + lg.get("desde", 0))});')
        if "hasta" in lg:  # p. ej. el nombre de una ruta que se apaga
            tw.append(f'tl.fromTo("#{lid} .ml", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.4, ease: "power1.in", immediateRender: false }}, {r(a + lg["hasta"])});')
    tw.append(f'tl.fromTo("#{iid}-m", {{ scale: {m["de"]} }}, {{ scale: {m["a"]}, duration: {r(t1 - t0)}, ease: "sine.inOut" }}, {r(t0)});')
    svg = (f'<svg class="mapa-svg" viewBox="0 0 {v["ancho"]} {v["alto"]}" width="{v["ancho"]}" height="{v["alto"]}">'
           f'<path class="mapa-grilla" d="{mapa.grilla(v)}" /><path class="mapa-tierra" d="{mapa.tierra(v)}" />{"".join(trazos)}</svg>')
    return (f'      <div class="clip inserto mapa" id="{iid}" {reloj} data-track-index="5">'
            f'<div class="ins-marco" id="{iid}-m" style="transform-origin: {m["origen"]}">{svg}{"".join(lugares)}</div></div>')


CUADRO_SIN_SUBTITULOS = (0.29, 0.71)  # fracción del alto: la obra enmarcada cuando nadie habla
CUADRO_ARRIBA = 0.255                 # con subtítulos: el cuadro sube y termina arriba de su franja


def caja_cuadro(w, h, franja=None, escala_max=1.08):
    """(ancho, alto, left, top, alto del rótulo) de una imagen `cuadro` de w×h.

    Sin subtítulos, la caja va del 29 al 71 % (puede entrar un poco en la franja de la interfaz porque es
    imagen, no texto). Con subtítulos (`franja` = (arriba, abajo) en fracción del alto), la caja termina
    arriba de la franja: en «El Conquistador» (11/10/2026) la línea de los subtítulos, al 64 %, tapaba el
    pie de cada foto. El acercamiento (`mover.a`) se descuenta para que tampoco entre al crecer, y el
    rótulo va arriba del cuadro, no en la línea de los subtítulos."""
    arriba, abajo = CUADRO_SIN_SUBTITULOS if franja is None else (CUADRO_ARRIBA, franja[0] - 0.012)
    alto_caja = (abajo - arriba) * 1920 / (max(1.0, escala_max) if franja is not None else 1.0)
    escala = min(930 / w, alto_caja / h)
    cw, ch = w * escala, h * escala
    centro = (arriba + abajo) / 2 * 1920
    rotulo = f"{(arriba - 0.008) * 100:.1f}%" if franja is not None else "64%"
    return cw, ch, (1080 - cw) / 2, centro - ch / 2, rotulo


def insertos(pedido, toma, a, dur, tw, colores=None, franja=None):
    """Capas encima del video de una toma: imágenes de archivo, placas de sección, rótulos y mapas.
    Devuelve (html, intervalos absolutos de las placas) para que los subtítulos las esquiven.
    `colores`: {acento, claro, secundario} para las rutas de los mapas. `franja`: (arriba, abajo) de los
    subtítulos de esta toma, si los lleva: las imágenes enmarcadas no entran ahí."""
    colores = colores or {"acento": "#F2C230", "claro": "#FFFFFF", "secundario": "#3F6E9E"}
    from PIL import Image
    destino = pedido / "render" / "assets" / "insertos"
    destino.mkdir(parents=True, exist_ok=True)
    capas, placas = [], []
    for k, ins in enumerate(toma["insertos"]):
        iid = f"in{toma['n']}-{k}"
        t0 = a + ins.get("desde", 0)
        t1 = a + min(ins.get("hasta", dur), dur + toma.get("solape", 0))
        reloj = f'data-start="{r(t0)}" data-duration="{r(t1 - t0)}"'
        tipo = ins.get("tipo", "imagen")
        filtro = ' style="filter: grayscale(1) contrast(1.18) brightness(0.96)"' if ins.get("filtro") == "bn" else ""
        if tipo == "imagen":
            src = pedido / ins["archivo"] if (pedido / ins["archivo"]).exists() else RAIZ / ins["archivo"]
            nombre = f"{toma['n']:02d}-{k}{src.suffix.lower()}"
            shutil.copy2(src, destino / nombre)
            w, h = Image.open(src).size
            m = ins.get("mover") or {"de": 1.0, "a": 1.08, "origen": "50% 45%"}
            foco = ins.get("foco", "50% 45%")
            if ins.get("modo", "cuadro") == "llena":
                cuerpo = (f'<div class="ins-marco" id="{iid}-m" style="transform-origin: {m["origen"]}">'
                          f'<img class="medio" src="assets/insertos/{nombre}" alt="" style="object-position: {foco}" /></div>')
                alto_rotulo = f"{(CUADRO_ARRIBA - 0.008) * 100:.1f}%" if franja is not None else "64%"
            else:
                cw, ch, x, y, alto_rotulo = caja_cuadro(w, h, franja, max(m["de"], m["a"]))
                cuerpo = (f'<img class="medio ins-fondo" src="assets/insertos/{nombre}" alt="" />'
                          f'<div class="ins-marco" id="{iid}-m" style="transform-origin: {m["origen"]}">'
                          f'<img class="ins-cuadro" src="assets/insertos/{nombre}" alt="" '
                          f'style="width:{cw:.0f}px; height:{ch:.0f}px; left:{x:.0f}px; top:{y:.0f}px" /></div>')
            rotulo = (f'<p class="rotulo" id="{iid}-r" style="bottom: calc(100% - {ins.get("alto", alto_rotulo)})">'
                      f'<span>{html.escape(ins["rotulo"])}</span></p>' if ins.get("rotulo") else "")
            capas.append(f'      <div class="clip inserto" id="{iid}" {reloj} data-track-index="5"{filtro}>{cuerpo}{rotulo}</div>')
            tw.append(f'tl.fromTo("#{iid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.18, ease: "power1.out" }}, {r(t0)});')
            tw.append(f'tl.fromTo("#{iid}-m", {{ scale: {m["de"]}, xPercent: {(ins.get("pan") or [0, 0])[0]} }}, '
                      f'{{ scale: {m["a"]}, xPercent: {(ins.get("pan") or [0, 0])[1]}, duration: {r(t1 - t0)}, ease: "sine.inOut" }}, {r(t0)});')
            if rotulo:
                tw.append(f'tl.fromTo("#{iid}-r span", {{ xPercent: -110, opacity: 0 }}, {{ xPercent: 0, opacity: 1, duration: 0.45, ease: "power3.out" }}, {r(t0 + 0.25)});')
        elif tipo == "placa":
            cuerpo, claves = palabras(ins["texto"], ins.get("destacar"), iid)
            pie = f'<p class="placa-pie">{html.escape(ins["pie"])}</p>' if ins.get("pie") else ""
            capas.append(f'      <div class="clip placa{" cita" if pie else ""}" id="{iid}" {reloj} data-track-index="6"{filtro}><div><h2>{cuerpo}</h2>{pie}</div></div>')
            tw.append(f'tl.fromTo("#{iid}", {{ clipPath: "inset(0% 0% 100% 0%)" }}, {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.32, ease: "power3.inOut" }}, {r(t0)});')
            tw.append(f'tl.fromTo("#{iid} .pi", {{ yPercent: 115 }}, {{ yPercent: 0, duration: 0.5, ease: "power4.out", stagger: 0.08 }}, {r(t0 + 0.12)});')
            for c in claves:
                tw.append(f'tl.fromTo("#{c} .fondo", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.4, ease: "power3.inOut" }}, {r(t0 + 0.45)});')
            placas.append((t0, t1))
        elif tipo == "rotulo":
            capas.append(f'      <div class="clip rotulo" id="{iid}" {reloj} data-track-index="7" '
                         f'style="bottom: calc(100% - {ins.get("alto", "58%")})"><span>{html.escape(ins["texto"])}</span></div>')
            tw.append(f'tl.fromTo("#{iid} span", {{ xPercent: -110, opacity: 0 }}, {{ xPercent: 0, opacity: 1, duration: 0.45, ease: "power3.out" }}, {r(t0)});')
        elif tipo == "mapa":
            capas.append(capa_mapa(ins, iid, reloj, a, colores, tw))
            tw.append(f'tl.fromTo("#{iid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.18, ease: "power1.out" }}, {r(t0)});')
        else:
            raise SystemExit(f"toma {toma['n']}: inserto de tipo desconocido «{tipo}» (imagen | placa | rotulo | mapa)")
    return "\n".join(capas), placas


ENCABEZADO_LARGO = 28      # más caracteres que esto no entran en una línea a 1080 px: la placa va en dos, parejas
ENCABEZADO_BASE = "19%"   # con la placa de ~4,6 % de alto, el borde de arriba queda en el 14 % (zona segura)


def entrada_sombra(pid, a):
    """La sombra difusa de un título entra con sus palabras. Aparecía entera en el primer cuadro, antes
    que el texto: sobre un pelo castaño era una mancha violeta («me saqué turno», 11/10/2026)."""
    return (f'tl.fromTo("#{pid}", {{ "--sombra": 0 }}, {{ "--sombra": 1, duration: 0.45, ease: "power2.out" }}, {r(a + 0.03)});')


def encabezado(tx, pid, a, b, tw):
    """Un título que queda fijo arriba durante muchas tomas (13-divulgacion.md › 6): una sola placa
    crema de una línea, más chica que un título y sin bloques por palabra. En «El Conquistador» el título
    fijo con un bloque por palabra competía 100 s con los rótulos y los subtítulos (Fernando, 11/10/2026).
    `destacar` pinta esa palabra con el resaltador de la marca."""
    clave = (tx.get("destacar") or "").lower()
    partes = []
    for w in tx["texto"].split():
        nucleo = w.strip("¿?¡!.,;:").lower()
        partes.append(f'<b>{html.escape(w)}</b>' if clave and nucleo == clave else html.escape(w))
    base = tx.get("base", ENCABEZADO_BASE)
    tw.append(f'tl.fromTo("#{pid} span", {{ y: -24, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: "power3.out" }}, {r(a + 0.05)});')
    largo = " largo" if len(tx["texto"]) > ENCABEZADO_LARGO else ""
    cuerpo = f' style="font-size: {int(tx["tam"])}px"' if tx.get("tam") else ""
    return (f'      <div class="clip encabezado{largo}" id="{pid}" style="bottom: calc(100% - {base})" data-start="{r(a)}" '
            f'data-duration="{r(b - a)}" data-track-index="1"><span{cuerpo}>{" ".join(partes)}</span></div>')


def tapado(ini, fin, intervalos):
    """El tramo [ini, fin] recortado por los intervalos que lo tapan (None si queda menos de 0,2 s)."""
    for a, b in intervalos:
        if a <= ini < b:
            ini = b
        elif ini < a < fin:
            fin = a
    return (ini, fin) if fin - ini >= 0.2 else None


# Temblor: un solo tween con rebote elástico desde la sacudida inicial (x, y en px, giro en grados), que
# oscila y se apaga en 0,6 s. Va en un solo fromTo: varios tweens sobre el mismo .trans hacían que
# hyperframes check avisara que se pisaban. La escala fija tapa los bordes con el corrimiento y el giro máximos.
TEMBLOR = {"x": -28, "y": 12, "giro": -0.8, "escala": 1.09, "dur": 0.6}
# Humo: bocanadas (izquierda %, arriba %, tamaño px) que tapan el corte y se van subiendo.
HUMO = [(-12, 18, 1300), (38, -6, 1150), (8, 52, 1400), (52, 40, 1200), (20, 78, 1250)]


def transicion(n, entrada, a, tw):
    """Los tweens de la entrada de la toma `n` (que arranca en `a`). Devuelve el HTML de una capa
    propia si la transición la necesita (humo), o "". Temblor y humo los pidió Ana para su reel de
    Halloween: «que entre foto y foto le meta efecto especial: zoom, temblor, humo» (28/10/2026)."""
    t = f"#t{n}"
    if entrada == "golpe":
        tw.append(f'tl.fromTo("{t}", {{ scale: 1.14 }}, {{ scale: 1, duration: 0.28, ease: "power3.out" }}, {r(a)});')
    elif entrada == "zoom":
        tw.append(f'tl.fromTo("{t}", {{ scale: 1.45, filter: "blur(22px)" }}, {{ scale: 1, filter: "blur(0px)", duration: 0.42, ease: "power3.out" }}, {r(a)});')
    elif entrada == "barrido":
        tw.append(f'tl.fromTo("{t}", {{ xPercent: 38, filter: "blur(18px)" }}, {{ xPercent: 0, filter: "blur(0px)", duration: 0.34, ease: "expo.out" }}, {r(a)});')
    elif entrada == "luz":
        tw.append(f'tl.fromTo("{t}", {{ filter: "brightness(1.9)" }}, {{ filter: "brightness(1)", duration: 0.7, ease: "power2.out" }}, {r(a)});')
        tw.append(f'tl.fromTo("#luz", {{ opacity: 0, x: -500 }}, {{ opacity: 1, x: 0, duration: 0.25, ease: "power2.out" }}, {r(a - 0.1)});')
        tw.append(f'tl.to("#luz", {{ opacity: 0, x: 420, duration: 0.65, ease: "sine.inOut" }}, {r(a + 0.15)});')
    elif entrada == "temblor":
        s = TEMBLOR
        tw.append(f'tl.fromTo("{t}", {{ x: {s["x"]}, y: {s["y"]}, rotation: {s["giro"]}, scale: {s["escala"]} }}, '
                  f'{{ x: 0, y: 0, rotation: 0, scale: {s["escala"]}, duration: {s["dur"]}, ease: "elastic.out(1, 0.12)" }}, {r(a)});')
    elif entrada == "humo":
        hid = f"humo{n}"
        bocanadas = "".join(f'<i style="left: {x}%; top: {y}%; width: {s}px; height: {s}px"></i>' for x, y, s in HUMO)
        tw.append(f'tl.fromTo("#{hid}", {{ opacity: 0, scale: 0.85, y: 120 }}, {{ opacity: 1, scale: 1, y: 0, duration: 0.3, ease: "power2.out" }}, {r(a - 0.3)});')
        tw.append(f'tl.to("#{hid}", {{ opacity: 0, scale: 1.35, y: -260, duration: 0.9, ease: "sine.in" }}, {r(a)});')
        tw.append(f'tl.fromTo("{t}", {{ filter: "blur(16px) brightness(1.3)" }}, {{ filter: "blur(0px) brightness(1)", duration: 0.6, ease: "power2.out" }}, {r(a)});')
        return f'      <div class="humo" id="{hid}">{bocanadas}</div>'
    elif entrada != "corte":
        raise SystemExit(f"toma {n}: entrada desconocida «{entrada}» (corte | golpe | zoom | barrido | luz | temblor | humo)")
    return ""


def comparacion(n, a, vis, dur, tw):
    """Antes | después: el después entra barriendo hasta la mitad, cada lado centra a su sujeto."""
    def video(lado, pista):
        return (f'<video id="v{n}{lado}" class="clip medio" src="assets/clips/{n:02d}{lado}.mp4" muted playsinline '
                f'data-start="{r(a)}" data-duration="{r(vis)}" data-track-index="{pista}"></video>')
    b = a + dur
    tw += [
        f'tl.fromTo("#l{n}b", {{ clipPath: "inset(0% 0% 0% 100%)" }}, {{ clipPath: "inset(0% 0% 0% 50%)", duration: 0.7, ease: "power3.inOut" }}, {r(a + 0.15)});',
        f'tl.fromTo("#s{n}a", {{ xPercent: 0 }}, {{ xPercent: -25, duration: 0.7, ease: "power3.inOut" }}, {r(a + 0.15)});',
        f'tl.fromTo("#d{n}", {{ x: 1090 }}, {{ x: 540, duration: 0.7, ease: "power3.inOut" }}, {r(a + 0.15)});',
        f'tl.fromTo("#e{n}a span", {{ scale: 0.4, rotation: -14, opacity: 0 }}, {{ scale: 1, rotation: -4, opacity: 1, duration: 0.38, ease: "back.out(2.2)" }}, {r(a + 0.6)});',
        f'tl.fromTo("#e{n}b span", {{ scale: 0.4, rotation: 14, opacity: 0 }}, {{ scale: 1, rotation: 4, opacity: 1, duration: 0.38, ease: "back.out(2.2)" }}, {r(a + 0.75)});',
        # el después se queda con toda la pantalla
        f'tl.to("#l{n}b", {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.55, ease: "power3.inOut" }}, {r(b - 0.6)});',
        f'tl.fromTo("#s{n}b", {{ xPercent: 25 }}, {{ xPercent: 0, duration: 0.55, ease: "power3.inOut" }}, {r(b - 0.6)});',
        f'tl.to("#d{n}", {{ x: -20, duration: 0.55, ease: "power3.inOut" }}, {r(b - 0.6)});',
        f'tl.to("#e{n}a span, #e{n}b span", {{ scale: 0.6, opacity: 0, duration: 0.3, ease: "power2.in" }}, {r(b - 0.65)});',
    ]
    return (f'      <div class="trans" id="t{n}"><div class="marco" id="m{n}">'
            f'<div class="lado" id="l{n}a"><div class="desliz" id="s{n}a">{video("a", 0)}</div></div>'
            f'<div class="lado" id="l{n}b" style="clip-path: inset(0% 0% 0% 100%)"><div class="desliz" id="s{n}b">{video("b", 2)}</div></div>'
            f'<div class="divisor" id="d{n}"></div>'
            f'<div class="etiqueta izq" id="e{n}a"><span>antes</span></div><div class="etiqueta der" id="e{n}b"><span>después</span></div>'
            f'</div></div>')


def voces(pedido, guion):
    """{n: info} de las tomas con voz que llevan subtítulos (analisis/voz.json). Con `subtitulos_fuente`,
    las palabras salen de la transcripción entera de la fuente, recortada al tramo de cada toma."""
    archivo = pedido / "analisis" / "voz.json"
    if guion.get("subtitulos") is False or not archivo.exists():
        return {}
    out = {int(k): v for k, v in (json.loads(archivo.read_text(encoding="utf-8")).get("tomas") or {}).items()}
    if guion.get("subtitulos_fuente"):
        por_n = {t["n"]: t for t in guion["tomas"]}
        for n, info in out.items():
            palabras = transcripcion_de(pedido, guion["subtitulos_fuente"], por_n[n]["fuente"])
            if palabras is not None:
                info["palabras"] = palabras_del_tramo(palabras, por_n[n]["desde"], por_n[n]["hasta"], info.get("tempo", 1.0))
    return out


def transcripcion_de(pedido, subtitulos_fuente, fuente):
    """Las palabras de la transcripción entera de `fuente`. `subtitulos_fuente` es un archivo (una sola fuente)
    o {fuente: archivo} cuando el reel junta dos (los tiempos de cada una arrancan en 0 y se pisarían).
    None si esa fuente no tiene transcripción: la toma se queda con lo que detectó voz.py."""
    if isinstance(subtitulos_fuente, dict):
        # la toma nombra su fuente desde la raíz del repo (pedidos/<pedido>/entrada/…) y la clave suele ir
        # desde el pedido (entrada/…) o ser solo el nombre: vale la que coincide con el final de la ruta
        ruta = Path(fuente).as_posix()
        archivo = next((v for k, v in subtitulos_fuente.items()
                        if ruta == Path(k).as_posix() or ruta.endswith("/" + Path(k).as_posix())), None)
        if archivo is None:
            return None
    else:
        archivo = subtitulos_fuente
    return json.loads((pedido / archivo).read_text(encoding="utf-8"))["palabras"]


def palabras_del_tramo(palabras, desde, hasta, tempo=1.0):
    """Las palabras (en segundos de la fuente) que arrancan dentro de [desde, hasta), en segundos de la toma."""
    return [{**w, "ini": round((w["ini"] - desde) / tempo, 2), "fin": round((min(w["fin"], hasta) - desde) / tempo, 2)}
            for w in palabras if desde - 0.05 <= w["ini"] < hasta - 0.05]


def franja_subtitulos(guion):
    """(arriba, abajo) en fracción del alto que ocupan los subtítulos de la voz."""
    if "subtitulos_base" not in guion:
        return SUBTITULO_FRANJA
    base = float(str(guion["subtitulos_base"]).rstrip("%")) / 100
    return base - (SUBTITULO_FRANJA[1] - SUBTITULO_FRANJA[0]) + 0.005, base + 0.005


def corregir(texto, correcciones):
    """Reemplaza las palabras mal transcriptas, respetando la puntuación pegada ("Marzot," → "Meursault,")
    y la mayúscula inicial ("Puzgan" → "Juzgan"). No distingue mayúsculas al buscar."""
    tabla = {k.lower(): v for k, v in (correcciones or {}).items()}
    out = []
    for w in texto.split():
        nucleo = w.strip("¿?¡!.,;:")
        nuevo = tabla.get(nucleo.lower())
        if nuevo and nucleo[:1].isupper():
            nuevo = nuevo[:1].upper() + nuevo[1:]
        out.append(w.replace(nucleo, nuevo) if nuevo else w)
    return " ".join(out)


SOSTENER = 0.6  # s: una pausa más corta que esto no deja la pantalla sin subtítulo


def subtitulos(palabras, max_palabras=4, max_dur=1.6, pausa=0.4):
    """Frases cortas de [{w, ini, fin}]: cortan por cantidad, por duración o en una pausa."""
    frases, actual = [], []
    for w in palabras:
        if actual and (len(actual) >= max_palabras or w["fin"] - actual[0]["ini"] > max_dur
                       or w["ini"] - actual[-1]["fin"] > pausa):
            frases.append(actual)
            actual = []
        actual.append(w)
    if actual:
        frases.append(actual)
    out = [{"texto": " ".join(x["w"] for x in f), "ini": f[0]["ini"], "fin": max(f[-1]["fin"], f[0]["ini"] + 0.6)}
           for f in frases]
    for f, sig in zip(out, out[1:]):
        # en una pausa corta la frase queda hasta que entra la siguiente (más tiempo de lectura, O5);
        # el mínimo de 0,6 s nunca pisa a la siguiente (content_overlap)
        f["fin"] = sig["ini"] if sig["ini"] - f["fin"] < SOSTENER else min(f["fin"], sig["ini"])
    return out


def cubierta(toma, dur):
    """La toma queda tapada entera por insertos (imágenes, placas o mapas: los rótulos no tapan).
    Entonces el video de abajo no se ve y sus caras no cuentan para ubicar un título: el gancho de
    «El Conquistador» va sobre un mapa que cubre toda la toma, con la cara de Pablo abajo."""
    tramos = sorted((i.get("desde", 0.0), i.get("hasta", dur)) for i in toma.get("insertos") or []
                    if i.get("tipo", "imagen") != "rotulo")
    hasta = 0.0
    for a, b in tramos:
        if a > hasta + 0.05:
            return False
        hasta = max(hasta, b)
    return dur > 0 and hasta >= dur - 0.05


def caras_en_tomas(pedido, guion, nums):
    """Caras que se ven en las tomas `nums`, en px del lienzo, con el acercamiento aplicado.
    La franja de los subtítulos de una toma con voz cuenta como ocupada: el título la esquiva."""
    clips = pedido / "render" / "assets" / "clips"
    por_n = {t["n"]: t for t in guion["tomas"]}
    con_voz = voces(pedido, guion)
    durs = {t["n"]: d for t, d in zip(guion["tomas"], duraciones(guion, pedido))}
    out = []
    for n in nums:
        if cubierta(por_n.get(n, {}), durs.get(n, 0.0)):
            continue  # un mapa o una imagen tapa todo el video de la toma: sus caras no se ven
        if n in con_voz and por_n.get(n, {}).get("subtitulos") is not False:
            arriba, abajo = franja_subtitulos(guion)
            out.append((60, arriba * 1920, 1020, abajo * 1920))
        toma = por_n.get(n, {})
        if toma.get("comparar"):
            # pantalla dividida: cada lado muestra el centro de su clip corrido un cuarto de
            # ancho; al final el después ocupa todo
            a, b = detectar([clips / f"{n:02d}a.mp4"]), detectar([clips / f"{n:02d}b.mp4"])
            out += [(max(x0 - 270, 0), y0, min(x1 - 270, 540), y1) for x0, y0, x1, y1 in a if x0 - 270 < 540]
            out += [(max(x0 + 270, 540), y0, x1 + 270, y1) for x0, y0, x1, y1 in b if x1 + 270 > 540] + b
        elif (clips / f"{n:02d}.mp4").exists():
            out += con_push(detectar([clips / f"{n:02d}.mp4"]), toma.get("push"))
    return out


@lru_cache(maxsize=4)
def _medidas(marca, ajustes_json="{}"):
    marca_dir = RAIZ / "marcas" / marca
    m = yaml.safe_load((marca_dir / "marca.yaml").read_text(encoding="utf-8"))
    return de_marca(m, json.loads(ajustes_json)).medidas_titulo(marca_dir)


def medidas(guion):
    """Fuente y cuerpo de los títulos del guion (los de la marca con sus `estilo_ajustes`),
    para medirlos con franja_titulo."""
    return _medidas(guion["marca"], json.dumps(guion.get("estilo_ajustes") or {}, sort_keys=True))


def escala_en_zona(texto, base, bloques, m):
    """Cuánto achicar un título para que, con la línea inferior en `base`, no pase arriba del 14 %
    (zona segura). 1 si entra con su cuerpo; ESCALA_MIN como mucho."""
    for k in range(100, int(ESCALA_MIN * 100) - 1, -2):
        if franja_titulo(texto, base, bloques, escala=k / 100, **m)[1] >= ZONA[0] * ALTO:
            return k / 100
    return ESCALA_MIN


def ubicar_titulo(pedido, guion, tx):
    """(base, fondo, escala) de un título. `textos[].base` y `textos[].fondo` mandan; lo que falte se
    decide en orden: fondo a la altura preferida, altura libre de caras con ese modo (bloques
    ocupa más), y si el título se movió, fondo otra vez a la altura nueva. Si con su cuerpo no
    entra entre la base y el 14 % (una base fija baja, un título largo en una condensada grande),
    se achica: el gancho de «El Extranjero» quedaba con el primer renglón al 3 %, bajo el nombre
    de la cuenta y cortado en la grilla del perfil."""
    m = medidas(guion)
    preferida = guion.get("texto_base", "62%")
    fondo = fondo_titulo(pedido, guion, tx, tx.get("base") or preferida)
    aviso = ""
    if tx.get("base"):
        base = tx["base"]
    else:
        caras = caras_en_tomas(pedido, guion, tx["tomas"])
        base, en_cara, en_cabeza = elegir_base(tx["texto"], caras, preferida, fondo == "bloques", **m)
        if base != preferida and not tx.get("fondo"):
            nuevo = fondo_titulo(pedido, guion, tx, base)
            if nuevo != fondo:
                fondo = nuevo
                base, en_cara, en_cabeza = elegir_base(tx["texto"], caras, preferida, fondo == "bloques", **m)
        aviso = (" ¡tapa una cara igual: no hay lugar libre! Elegir a mano (textos[].base) u otra toma" if en_cara else
                 " (roza la cabeza: no hay lugar del todo libre; la cara queda a la vista)" if en_cabeza else "")
    escala = escala_en_zona(tx["texto"], base, fondo == "bloques", m)
    if franja_titulo(tx["texto"], base, fondo == "bloques", escala=escala, **m)[1] < ZONA[0] * ALTO:
        aviso += f" ¡no entra en la zona segura ni al {ESCALA_MIN:.0%}: bajar la base o acortar el texto!"
    elif escala < 1:
        aviso += f" (achicado al {escala:.0%}: con su cuerpo pasaba arriba del 14 %)"
    if float(str(base).rstrip("%")) > ZONA[1] * 100:
        aviso += f" ¡la base pasa el {ZONA[1]:.0%}: queda bajo los botones!"
    if not tx.get("base") or aviso:
        print(f"  «{tx['texto']}»: base {base}{'' if tx.get('base') or base == preferida else f' (no {preferida}: cara)'}, {fondo}{aviso}")
    return base, fondo, escala


def fondo_titulo(pedido, guion, tx, base):
    """sombra | bloques para un título a la altura `base`: lo fija `textos[].fondo` o se mide en sus clips."""
    if tx.get("fondo"):
        return tx["fondo"]
    clips = []
    for n in tx["tomas"]:
        unico = pedido / "render" / "assets" / "clips" / f"{n:02d}.mp4"
        # en una comparación se ven los dos lados: cuenta el más claro
        clips += [unico] if unico.exists() else sorted(unico.parent.glob(f"{n:02d}?.mp4"))
    if not clips:
        print(f"  ! «{tx['texto']}»: faltan los clips de sus tomas (¿preparar_clips.py?); va con sombra")
        return "sombra"
    return tratamiento(brillo(clips, franja_titulo(tx["texto"], base, **medidas(guion))))


def armar(pedido, reemplazos=None):
    guion = yaml.safe_load((pedido / "plan" / "guion.yaml").read_text(encoding="utf-8"))
    for tx in guion.get("textos", []):
        tx["texto"] = (reemplazos or {}).get(tx["id"], tx["texto"])
    marca_dir = RAIZ / "marcas" / guion["marca"]
    marca = yaml.safe_load((marca_dir / "marca.yaml").read_text(encoding="utf-8"))
    c = marca["colores"]
    e = de_marca(marca, guion.get("estilo_ajustes"))
    assets = pedido / "render" / "assets"
    copiar_assets(marca_dir, assets, e=e)

    # ---- tiempos
    t, inicio, cierre = 0.0, {}, None
    for toma, dur in zip(guion["tomas"], duraciones(guion, pedido)):
        inicio[toma["n"]] = (t, dur)
        if toma.get("cierre"):
            cierre = (t, dur)
        t += dur
    total = t
    tw = []  # tweens

    # ---- video + transiciones de entrada
    capas, capas_tarjetas, capas_insertos, sin_subtitulos = [], [], [], []
    con_voz = voces(pedido, guion)
    for toma in guion["tomas"]:
        if toma.get("cierre"):
            continue
        n = toma["n"]
        a, dur = inicio[n]
        vis = dur + toma.get("solape", 0)
        p = toma.get("push") or {}
        if toma.get("comparar"):
            capas.append(comparacion(n, a, vis, dur, tw))
            continue
        desenfoque = ' style="filter: blur(22px) brightness(0.78) saturate(1.1)"' if toma.get("tarjetas") else ""
        capas.append(f'      <div class="trans" id="t{n}"><div class="marco" id="m{n}" style="transform-origin: {p.get("origen", "50% 50%")}">'
                     f'<video id="v{n}" class="clip medio" src="assets/clips/{n:02d}.mp4" muted playsinline{desenfoque} '
                     f'data-start="{r(a)}" data-duration="{r(vis)}" data-track-index="0"></video></div></div>')
        if toma.get("tarjetas"):
            capas_tarjetas.append(tarjetas(pedido, toma, a, dur, 60 / guion["bpm"], tw))
        if toma.get("insertos"):
            franja = franja_subtitulos(guion) if n in con_voz and toma.get("subtitulos") is not False else None
            capa, placas = insertos(pedido, toma, a, dur, tw, {"acento": e.resalta(c), "claro": e.claro, "secundario": c["secundario"]}, franja)
            capas_insertos.append(capa)
            sin_subtitulos += placas
        if toma.get("subtitulos") is False:
            sin_subtitulos.append((a, a + dur))
        if p:
            tw.append(f'tl.fromTo("#m{n}", {{ scale: {p["de"]} }}, {{ scale: {p["a"]}, duration: {r(vis)}, ease: "{p["ease"]}" }}, {r(a)});')
        capa_extra = transicion(n, toma.get("entrada", "corte"), a, tw)
        if capa_extra:
            capas_insertos.append(capa_extra)

    # ---- textos
    capas_txt = []
    for tx in guion.get("textos", []):
        if tx["id"] == "cta":
            continue
        a = inicio[tx["tomas"][0]][0]
        ult = inicio[tx["tomas"][-1]]
        b = ult[0] + ult[1]
        pid = f"x-{tx['id']}"
        if tx.get("tipo", "titulo") == "titulo":
            cuerpo, claves = palabras(tx["texto"], tx.get("destacar"), pid)
            dest = destellos(pid, [e.claro, e.destello, c["claro"]], [(4, -22, 70), (88, -14, 52), (92, 78, 44)], e)
            largo = " largo" if len(tx["texto"]) > 26 else ""
            tx["base"], fondo, escala = ubicar_titulo(pedido, guion, tx)
            base = f' style="bottom: calc(100% - {tx["base"]})"'
            m = medidas(guion)
            cuerpo_px = f' style="font-size: {round((m["tam_largo"] if largo else m["tam"]) * escala)}px"' if escala < 1 else ""
            capas_txt.append(f'      <div class="clip titulo{largo}{" bloques" if fondo == "bloques" else ""}" id="{pid}"{base} '
                             f'data-start="{r(a)}" data-duration="{r(b - a)}" data-track-index="1">'
                             f'<div><h2{cuerpo_px}>{cuerpo}</h2>{dest}</div></div>')
            tw.append(f'tl.fromTo("#{pid} .pi", {{ yPercent: 115, rotation: 7 }}, {{ yPercent: 0, rotation: 0, duration: 0.55, ease: "power4.out", stagger: 0.07 }}, {r(a + 0.03)});')
            if fondo == "sombra":
                tw.append(entrada_sombra(pid, a))
            for k in claves if fondo == "sombra" else []:
                tw.append(f'tl.fromTo("#{k} .fondo", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.4, ease: "power3.inOut" }}, {r(a + 0.32)});')
            for i in range(3 if e.destellos else 0):
                d0 = a + 0.25 + 0.12 * i
                tw.append(f'tl.fromTo("#{pid}-d{i}", {{ scale: 0, rotation: -40 }}, {{ scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2.4)" }}, {r(d0)});')
                tw.append(f'tl.to("#{pid}-d{i}", {{ scale: 0.72, duration: 0.5, ease: "sine.inOut", yoyo: true, repeat: {max(1, int((b - d0 - 0.45) / 0.5) - 1)} }}, {r(d0 + 0.46)});')
        elif tx["tipo"] == "encabezado":
            capas_txt.append(encabezado(tx, pid, a, b, tw))
        else:  # sticker
            num, _, resto = tx["texto"].partition("·")
            capas_txt.append(f'      <div class="clip sticker" data-start="{r(a)}" data-duration="{r(b - a)}" data-track-index="1">'
                             f'<span id="{pid}"><b>{html.escape(num.strip())}</b>{html.escape(resto.strip())}</span></div>')
            tw.append(f'tl.fromTo("#{pid}", {{ scale: 0.4, rotation: -14 }}, {{ scale: 1, rotation: -4, duration: 0.38, ease: "back.out(2.2)" }}, {r(a)});')

    # ---- subtítulos de la voz
    altura = f' style="bottom: calc(100% - {guion["subtitulos_base"]})"' if "subtitulos_base" in guion else ""
    for n, info in voces(pedido, guion).items():
        if n not in inicio:
            continue
        a0, dur = inicio[n]
        for k, f in enumerate(subtitulos(info["palabras"])):
            visible = tapado(a0 + f["ini"], min(a0 + f["fin"], a0 + dur), sin_subtitulos)
            if not visible:
                continue
            ini, fin = visible
            texto = corregir(f["texto"], guion.get("subtitulos_correcciones"))
            capas_txt.append(f'      <div class="clip subtitulo" id="sub-{n}-{k}"{altura} data-start="{r(ini)}" data-duration="{r(fin - ini)}" '
                             f'data-track-index="4"><span>{html.escape(texto)}</span></div>')

    # ---- cierre
    bloque_cierre = ""
    if cierre:
        tc, dc = cierre
        cta = next((tx["texto"] for tx in guion["textos"] if tx["id"] == "cta"), marca.get("cta_por_defecto", ""))
        cuerpo, _ = palabras(cta, None, "cta")
        dest = destellos("ci", [c["primario"], e.destello, c["secundario"]], [(16, 14, 66), (79, 12, 50), (82, 34, 40), (13, 37, 46)], e)
        lugar = (marca.get("ciudad") or "").split(",")[0]
        bloque_cierre = f"""
      <div id="cierre" class="clip" data-start="{r(tc)}" data-duration="{r(dc)}" data-track-index="3">
        <div id="cierre-placa"></div>
        <div id="cierre-contenido">
          <img id="cierre-logo" src="assets/logo.png" alt="{html.escape(marca['nombre'])}" />
          <p id="cierre-cta">{cuerpo}</p>
          <p id="cierre-lugar">{html.escape(lugar)}</p>
        </div>{dest}
      </div>"""
        tw += [
            f'tl.fromTo("#cierre-placa", {{ clipPath: "circle(0% at 50% 42%)" }}, {{ clipPath: "circle(150% at 50% 42%)", duration: 0.55, ease: "power3.inOut" }}, {r(tc)});',
            f'tl.fromTo("#cierre-logo", {{ scale: 0.6, opacity: 0, rotation: -6 }}, {{ scale: 1, opacity: 1, rotation: 0, duration: 0.6, ease: "back.out(1.8)" }}, {r(tc + 0.2)});',
            f'tl.fromTo("#cierre-cta .pi", {{ yPercent: 115 }}, {{ yPercent: 0, duration: 0.5, ease: "power4.out", stagger: 0.06 }}, {r(tc + 0.45)});',
            f'tl.fromTo("#cierre-lugar", {{ opacity: 0, y: 18 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }}, {r(tc + 0.7)});',
        ]
        for i in range(4 if e.destellos else 0):
            tw.append(f'tl.fromTo("#ci-d{i}", {{ scale: 0, rotation: -60 }}, {{ scale: 1, rotation: 0, duration: 0.5, ease: "back.out(2.4)" }}, {r(tc + 0.5 + 0.1 * i)});')

    tw.append(grano_tween(total))

    documento = f"""<!doctype html>
<html lang="es" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{html.escape(marca['nombre'])} — {pedido.name}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{css(c, guion.get("texto_base", "62%"), e)}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{r(total)}">
      <!-- Generado por herramientas/armar_pop.py (estilo {e.nombre}) desde plan/guion.yaml -->
      <div id="capa-video">
{chr(10).join(capas)}
{chr(10).join(capas_insertos)}
      </div>
      {capas_look(luz=True)}
{chr(10).join(capas_tarjetas)}
{chr(10).join(capas_txt)}{bloque_cierre}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      {(chr(10) + "      ").join(tw)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (pedido / "render" / "index.html").write_text(documento, encoding="utf-8")
    print(f"index.html ({e.nombre}): {len(capas)} tomas, {len(capas_txt)} textos, {len(tw)} animaciones, {total:.3f} s")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--texto", action="append", default=[], metavar='ID="texto"')
    a = ap.parse_args()
    armar(Path(a.pedido), dict(x.split("=", 1) for x in a.texto))


if __name__ == "__main__":
    main()
