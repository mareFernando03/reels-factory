"""Historias de Instagram con el estilo de la marca: foto o video corto + texto + firma.

Uso:
    uv run python herramientas/armar_historia.py pedidos/<pedido> [--sin-render]

Lee plan/historia.yaml:
    marca: salon-demo
    plantilla: novedad | turno | resultado | detras | teaser
    medio: { archivo: entrada/foto.jpg | entrada/video.mp4, desde, hasta, encuadre, foco: "50% 40%" }
    duracion: 7                  # segundos (foto); con video, el largo del tramo (máx. 60)
    etiqueta: "turnos disponibles"   # píldora arriba del título (opcional)
    titulo: { texto: "...", destacar: "palabra" }
    nota: "..."                  # manuscrita (estilo › manuscrita), debajo del título (opcional)
    espacio_sticker: abajo | arriba | no   # franja libre para el sticker interactivo
    fondo: sombra | bloques      # opcional; si falta se mide el brillo detrás del texto (legibilidad.py)
    sticker_sugerido: "link a WhatsApp"   # va al informe: lo pone Ana en la app

Zona segura de historias (Meta): 14 % arriba, 20 % abajo, 6 % a los costados.
La firma es su logo chico sobre una placa clara (su marca de agua, no una de terceros).
Escribe render/index.html y, salvo --sin-render, salida/historia.mp4 y salida/historia.jpg
(el último cuadro, para subirla como foto fija).
"""

import argparse
import html
import math
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from estilo import capas_look, copiar_assets, css, de_marca, destellos, grano_tween, palabras, r  # noqa: E402
from render import hyperframes  # noqa: E402
from comun import FFMPEG, RAIZ, correr  # noqa: E402
from legibilidad import ALTO, ANCHO, brillo, franja_titulo, tratamiento  # noqa: E402

FOTOS = {".jpg", ".jpeg", ".png", ".webp"}
# línea inferior del bloque de texto por plantilla (% del alto); el bloque crece hacia arriba
BASE = {"novedad": "38%", "turno": "52%", "resultado": "70%", "detras": "34%", "teaser": "31%"}


def preparar_medio(pedido, medio, dur):
    src = pedido / medio["archivo"]
    assets = pedido / "render" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in FOTOS:
        destino = assets / f"medio{src.suffix.lower()}"
        shutil.copy2(src, destino)
        return destino.name, "foto"
    from preparar_clips import cortar
    t = {"desde": medio.get("desde", 0.0), "hasta": medio["hasta"], **{k: medio[k] for k in ("encuadre", "espejar", "estabilizar") if k in medio}}
    cortar(src, t, dur, assets / "medio.mp4")
    return "medio.mp4", "video"


def lado_firma(base, espacio_sticker):
    """arriba (a la derecha, al 15 %) o abajo (al 21 % del borde de abajo).

    Abajo si el sticker va arriba (por eso "resultado" termina al 70 %) o si el título va arriba
    (novedad, detras, teaser: el bloque termina antes del 45 % y su primer renglón cae a la altura
    de la firma, que lo tapaba; 07/10/2026, historia de las tarjetas con Olinail's).
    """
    if espacio_sticker == "arriba" or float(str(base).rstrip("%")) < 45:
        return "abajo"
    return "arriba"


def fondo_bloque(medio, titulo, nota, base, foco):
    """sombra | bloques según el brillo detrás del título y la nota (que van debajo)."""
    alto_nota = 0
    if nota:  # manuscrita 78 px, ~26 caracteres por renglón
        alto_nota = math.ceil(len(nota) / 26) * 82 + 18
    abajo = ALTO * float(base.rstrip("%")) / 100
    x0, y0, x1, _ = franja_titulo(titulo, f"{(abajo - alto_nota) / ALTO * 100:.2f}%")
    caja = (min(x0, 100), y0, max(x1, ANCHO - 100), int(abajo)) if nota else (x0, y0, x1, int(abajo))
    fx, fy = (float(v.rstrip("%")) / 100 for v in foco.split())
    lum = brillo([medio], caja, foco=(fx, fy))
    fondo = tratamiento(lum)
    print(f"  fondo del texto {lum:.2f} → {fondo}")
    return fondo


def armar(pedido):
    h = yaml.safe_load((pedido / "plan" / "historia.yaml").read_text(encoding="utf-8"))
    marca_dir = RAIZ / "marcas" / h["marca"]
    marca = yaml.safe_load((marca_dir / "marca.yaml").read_text(encoding="utf-8"))
    c = marca["colores"]
    e = de_marca(marca)
    plantilla = h.get("plantilla", "novedad")
    medio = h["medio"]
    es_video = Path(medio["archivo"]).suffix.lower() not in FOTOS
    dur = float(h.get("duracion") or (min(60, medio["hasta"] - medio.get("desde", 0)) if es_video else 7))
    archivo, tipo = preparar_medio(pedido, medio, dur)
    assets = pedido / "render" / "assets"
    copiar_assets(marca_dir, assets, caveat=True, e=e)

    base = h.get("base") or BASE[plantilla]
    foco = medio.get("foco", "50% 45%")
    tw = []
    # ---- medio: foto con acercamiento lento / video; en el teaser, fondo desenfocado + tarjeta
    etiqueta_medio = (f'<img id="medio" class="medio" src="assets/{archivo}" alt="" style="object-position: {foco}" />'
                      if tipo == "foto" else
                      f'<video id="medio" class="clip medio" src="assets/{archivo}" muted playsinline data-start="0" '
                      f'data-duration="{r(dur)}" data-track-index="0" style="object-position: {foco}"></video>')
    # con video, el <video> ya es la capa temporizada: un contenedor con tiempo propio encima
    # es un error de HyperFrames (video_nested_in_timed_element) y frena el `check`
    lienzo = ('<div id="lienzo">' if tipo == "video" else
              f'<div id="lienzo" class="clip" data-start="0" data-duration="{r(dur)}" data-track-index="2">')
    if plantilla == "teaser":
        fondo = (f'<img class="medio" src="assets/{archivo}" alt="" style="filter: blur(38px) brightness(0.7) saturate(1.2); transform: scale(1.15)" />'
                 if tipo == "foto" else f'<div class="medio" style="background: {e.fondo}"></div>')
        capa_medio = (lienzo + fondo +
                      f'<div id="tarjeta"><div id="tarjeta-marco">{etiqueta_medio}</div></div></div>')
        tw.append('tl.fromTo("#tarjeta", { scale: 0.86, rotation: -5, y: 80 }, { scale: 1, rotation: -2, y: 0, duration: 0.8, ease: "back.out(1.6)" }, 0.1);')
        tw.append(f'tl.fromTo("#tarjeta-marco", {{ scale: 1.0 }}, {{ scale: 1.0, duration: {r(dur)}, ease: "none" }}, 0);')
    else:
        capa_medio = (lienzo +
                      f'<div id="acerca" style="transform-origin: {foco}">{etiqueta_medio}</div></div>')
        tw.append(f'tl.fromTo("#acerca", {{ scale: 1.0 }}, {{ scale: {1.08 if tipo == "foto" else 1.04}, duration: {r(dur)}, ease: "sine.inOut" }}, 0);')

    # ---- bloque de texto: etiqueta, título palabra por palabra, nota manuscrita
    tit = h.get("titulo") or {}
    cuerpo, claves = palabras(tit.get("texto", ""), tit.get("destacar"), "ht")
    etiqueta = f'<p id="h-etiqueta"><span>{html.escape(h["etiqueta"])}</span></p>' if h.get("etiqueta") else ""
    nota = f'<p id="h-nota"><span>{html.escape(h["nota"])}</span></p>' if h.get("nota") else ""
    dest = destellos("hd", [e.claro, e.destello, c["claro"]], [(2, -10, 64), (90, -4, 48), (94, 70, 40)], e)
    largo = " largo" if len(tit.get("texto", "")) > 26 else ""
    fondo = h.get("fondo") or fondo_bloque(assets / archivo, tit.get("texto", ""), h.get("nota"), base, foco)
    bloque = (f'<div class="clip titulo{largo}{" bloques" if fondo == "bloques" else ""}" id="bloque" data-start="0" '
              f'data-duration="{r(dur)}" data-track-index="1"><div>{etiqueta}<h2>{cuerpo}</h2>{nota}{dest}</div></div>')
    if etiqueta:
        tw.append('tl.fromTo("#h-etiqueta span", { scale: 0.4, rotation: -14 }, { scale: 1, rotation: -3, duration: 0.42, ease: "back.out(2.2)" }, 0.25);')
    tw.append('tl.fromTo("#bloque .pi", { yPercent: 115, rotation: 7 }, { yPercent: 0, rotation: 0, duration: 0.6, ease: "power4.out", stagger: 0.07 }, 0.4);')
    for k in claves if fondo == "sombra" else []:
        tw.append(f'tl.fromTo("#{k} .fondo", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.4, ease: "power3.inOut" }}, 0.75);')
        tw.append(f'tl.to("#{k} .pi", {{ color: "{e.resalta_texto()}", duration: 0.2 }}, 0.75);')
    if nota:
        tw.append('tl.fromTo("#h-nota", { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.9, ease: "power2.inOut" }, 1.0);')
    for i in range(3 if e.destellos else 0):
        tw.append(f'tl.fromTo("#hd-d{i}", {{ scale: 0, rotation: -40 }}, {{ scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2.4)" }}, {r(0.7 + 0.12 * i)});')
        tw.append(f'tl.to("#hd-d{i}", {{ scale: 0.72, duration: 0.5, ease: "sine.inOut", yoyo: true, repeat: {max(1, int((dur - 1.3) / 0.5) - 1)} }}, {r(1.16 + 0.12 * i)});')

    # ---- firma: logo chico en placa clara, fuera de la franja del sticker y del título
    lado = lado_firma(base, h.get("espacio_sticker"))
    firma = f'<div class="clip" id="firma" data-start="0" data-duration="{r(dur)}" data-track-index="3"><img src="assets/logo.png" alt="{html.escape(marca["nombre"])}" /></div>'
    tw.append('tl.fromTo("#firma", { scale: 0.5, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.5, ease: "back.out(2)" }, 1.2);')

    tw.append(grano_tween(dur))

    extra = f"""
  {e.font_faces(manuscrita=True)}
  #lienzo, #acerca {{ position: absolute; inset: 0; overflow: hidden; }}
  #tarjeta {{ position: absolute; left: 15%; width: 70%; top: 37%; aspect-ratio: 4 / 5; padding: 14px; background: {e.claro};
             border-radius: 34px; box-shadow: 0 30px 70px rgba({e.sombra}, 0.55); transform: rotate(-2deg); }}
  #tarjeta-marco {{ position: relative; width: 100%; height: 100%; border-radius: 24px; overflow: hidden; }}
  #h-etiqueta {{ text-align: center; margin-bottom: 26px; }}
  #h-etiqueta span {{ display: inline-block; background: {e.claro}; color: {c['primario']}; font-weight: 800; font-size: 40px;
                      letter-spacing: 0.08em; text-transform: uppercase; padding: 14px 28px 12px; border-radius: 999px;
                      box-shadow: 0 10px 30px rgba({e.sombra}, 0.35); }}
  #h-nota {{ {e.fuente_manuscrita} font-size: 78px; line-height: 1.05; color: {e.claro}; text-align: center;
             margin-top: 18px; max-width: 880px; text-wrap: balance; text-shadow: 0 3px 18px rgba({e.sombra}, 0.7); }}
  /* fondo claro: la nota también va sobre el resaltador, renglón por renglón */
  .bloques #h-nota {{ line-height: 1.3; text-shadow: none; margin-top: 18px; padding: 0.08em 0 0.16em; }}  /* la máscara de la entrada recorta en el borde */
  .bloques #h-nota span {{ background: {e.resalta(c)}; color: {e.resalta_texto()}; padding: 0.02em 0.24em 0.08em; border-radius: 0.14em;
                           -webkit-box-decoration-break: clone; box-decoration-break: clone; }}
  #firma {{ position: absolute; right: 7%; {"top: 15%" if lado == "arriba" else "bottom: 21%"}; width: 150px; height: 150px; border-radius: 50%;
            background: {e.claro}; box-shadow: 0 8px 26px rgba({e.sombra}, 0.35); display: flex; align-items: center; justify-content: center; }}
  #firma img {{ width: 118px; height: auto; display: block; }}
"""
    documento = f"""<!doctype html>
<html lang="es" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{html.escape(marca['nombre'])} — historia {pedido.name}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{css(c, base, e)}{extra}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{r(dur)}">
      <!-- Generado por herramientas/armar_historia.py (plantilla {plantilla}) desde plan/historia.yaml -->
      <div id="capa-video">
      {capa_medio}
      </div>
      {capas_look()}
      {bloque}
      {firma}
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
    print(f"index.html (historia {plantilla}, {tipo}): {dur:.1f} s, {len(tw)} animaciones")
    return dur, h


def renderizar(pedido, dur):
    salida = pedido / "salida"
    salida.mkdir(exist_ok=True)
    ok, error = hyperframes(pedido / "render", "../salida/historia.mp4")
    if not ok:
        raise SystemExit(f"render: {error}")
    correr([FFMPEG, "-v", "error", "-y", "-sseof", "-0.25", "-i", str(salida / "historia.mp4"),
            "-frames:v", "1", "-q:v", "1", str(salida / "historia.jpg")])
    print(f"→ {salida / 'historia.mp4'} y historia.jpg")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--sin-render", action="store_true")
    a = ap.parse_args()
    pedido = Path(a.pedido)
    dur, h = armar(pedido)
    if not a.sin_render:
        renderizar(pedido, dur)
    if h.get("espacio_sticker") not in (None, "no"):
        print(f"  Sticker para Ana: {h.get('sticker_sugerido', 'el que corresponda')} en la franja de {h['espacio_sticker']}.")


if __name__ == "__main__":
    main()
