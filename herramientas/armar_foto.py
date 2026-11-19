"""Publicaciones de foto y carruseles (1080×1440, 3:4) con el estilo de la marca.

Uso:
    uv run python herramientas/armar_foto.py pedidos/<pedido> [--sin-render]

Lee plan/publicacion.yaml:
    marca: salon-demo
    formato: foto | carrusel
    placas:                       # una placa = una imagen; foto = una sola placa
      - { tipo: portada, foto: entrada/a.jpg, foco: "50% 40%", etiqueta: "...", titulo: {texto, destacar}, nota: "..." }
      - { tipo: foto, foto: entrada/b.jpg, foco: "50% 40%", nota: "..." }   # la foto limpia + firma
      # zoom: 1.3 acerca la foto alrededor del `foco` (para dejar afuera lo que distrae en un borde)
      - { tipo: precios, etiqueta: "...", titulo: {texto, destacar}, nota: "...",
          items: [{ nombre, detalle, precio, color: primario|acento|secundario }] }
      - { tipo: cierre }          # logo, CTA y ciudad

Desde 2026 el 3:4 se sube nativo y llena el feed y la grilla del perfil sin recorte.
El feed no tiene interfaz encima: no hay zona segura, pero el texto va con aire
(márgenes del 7 %). Todas las placas de un carrusel tienen el mismo tamaño.
Escribe render/index.html (una placa por segundo) y salida/placa-NN.jpg.
"""

import argparse
import html
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from estilo import copiar_assets, css, de_marca, destellos, look_css_foto, palabras  # noqa: E402
from render import hyperframes  # noqa: E402
from comun import FFMPEG, RAIZ, correr  # noqa: E402

W, H = 1080, 1440


def titulo_html(p, pid, c):
    tit = p.get("titulo") or {}
    cuerpo, _ = palabras(tit.get("texto", ""), tit.get("destacar"), pid)
    etiqueta = f'<p class="f-etiqueta"><span>{html.escape(p["etiqueta"])}</span></p>' if p.get("etiqueta") else ""
    nota = f'<p class="f-nota">{html.escape(p["nota"])}</p>' if p.get("nota") else ""
    return etiqueta, (f"<h2>{cuerpo}</h2>" if tit else ""), nota


def estilo_foto(p):
    """CSS de la foto de una placa: `foco` es el punto que se conserva al recortar a 3:4
    y `zoom` (≥1) acerca alrededor de ese mismo punto."""
    foco = p.get("foco", "50% 45%")
    zoom = max(1.0, float(p.get("zoom", 1)))
    return f"object-position: {foco}" + (f"; transform: scale({zoom:g}); transform-origin: {foco}" if zoom > 1 else "")


def placa(p, k, c, marca, assets, pedido, e):
    pid = f"p{k}"
    firma = f'<div class="f-firma"><img src="assets/logo.png" alt="{html.escape(marca["nombre"])}" /></div>'
    look = '<div class="f-calidez"></div><div class="f-vineta"></div><div class="f-grano"></div>'
    tipo = p.get("tipo", "foto")
    if tipo in ("portada", "foto"):
        src = pedido / p["foto"]
        nombre = f"foto-{k:02d}{src.suffix.lower()}"
        shutil.copy2(src, assets / nombre)
        foto = f'<img class="f-foto" src="assets/{nombre}" alt="" style="{estilo_foto(p)}" />'
        if tipo == "foto":
            nota = (f'<div class="f-sombra f-sombra-baja"></div><p class="f-nota f-nota-sola">{html.escape(p["nota"])}</p>'
                    if p.get("nota") else "")  # degradé: la nota tiene que leerse sobre una capa blanca
            return f'{foto}{look}{nota}{firma}'
        etiqueta, h2, nota = titulo_html(p, pid, c)
        dest = destellos(pid, [e.claro, e.destello, c["claro"]], [(2, -8, 60), (90, -2, 46), (93, 72, 38)], e)
        return (f'{foto}{look}<div class="f-sombra"></div>'
                f'<div class="f-bloque f-abajo"><div>{etiqueta}{h2}{nota}{dest}</div></div>{firma}')
    if tipo == "precios":
        etiqueta, h2, nota = titulo_html(p, pid, c)
        filas = []
        for it in p["items"]:
            color = c.get(it.get("color", "primario"), it.get("color", c["primario"]))
            filas.append(f'<div class="f-item" style="--tono: {color}"><div class="f-item-txt">'
                         f'<p class="f-item-nombre">{html.escape(it["nombre"])}</p>'
                         f'<p class="f-item-detalle">{html.escape(it.get("detalle", ""))}</p></div>'
                         f'<p class="f-item-precio">{html.escape(it["precio"])}</p></div>')
        dest = destellos(pid, [c["primario"], e.destello, c["secundario"]], [(6, 4, 56), (88, 6, 44), (90, 90, 40)], e)
        return (f'<div class="f-placa-clara"></div><div class="f-grano"></div>'
                f'<div class="f-precios"><div class="f-precios-tit">{etiqueta}{h2.replace("<h2>", "<h2 class=oscuro>")}</div>'
                f'{"".join(filas)}{nota}</div>{dest}{firma}')
    if tipo == "cierre":
        cta, _ = palabras(marca.get("cta_por_defecto", ""), None, pid)
        lugar = (marca.get("ciudad") or "").split(",")[0]
        dest = destellos(pid, [c["primario"], e.destello, c["secundario"]], [(16, 14, 60), (80, 12, 46), (82, 70, 38)], e)
        return (f'<div class="f-placa-clara"></div><div class="f-grano"></div>'
                f'<div class="f-cierre"><img src="assets/logo.png" alt="{html.escape(marca["nombre"])}" />'
                f'<p class="f-cta">{cta}</p><p class="f-lugar">{html.escape(lugar)}</p></div>{dest}')
    raise SystemExit(f"tipo de placa desconocido: {tipo}")


def armar(pedido):
    pub = yaml.safe_load((pedido / "plan" / "publicacion.yaml").read_text(encoding="utf-8"))
    marca_dir = RAIZ / "marcas" / pub["marca"]
    marca = yaml.safe_load((marca_dir / "marca.yaml").read_text(encoding="utf-8"))
    c = marca["colores"]
    e = de_marca(marca)
    assets = pedido / "render" / "assets"
    copiar_assets(marca_dir, assets, caveat=True, e=e)
    placas = pub["placas"]
    n = len(placas)
    capas = [f'      <div class="clip f-placa" id="placa{k}" data-start="{k}" data-duration="1" data-track-index="0">'
             f'{placa(p, k, c, marca, assets, pedido, e)}</div>' for k, p in enumerate(placas)]
    extra = f"""
  {e.font_faces(manuscrita=True)}
  html, body {{ width: {W}px; height: {H}px; }}
  .f-placa {{ position: absolute; inset: 0; overflow: hidden; background: {e.fondo}; }}
  .f-foto {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: {e.correccion}; }}
{look_css_foto(e=e)}
  .f-sombra {{ position: absolute; left: 0; right: 0; bottom: 0; height: 55%; background: linear-gradient(to top, rgba({e.sombra}, 0.72), rgba({e.sombra}, 0.0)); }}
  .f-sombra-baja {{ height: 30%; }}
  .f-bloque {{ position: absolute; left: 7%; right: 7%; display: flex; justify-content: center; }}
  .f-bloque > div {{ position: relative; text-align: center; }}
  .f-abajo {{ bottom: 8%; }}
  .f-bloque h2, .f-precios h2 {{ {e.fuente_titulo} font-size: {e.tam(96)}; line-height: 1.06;
                 color: {e.claro}; text-align: center; text-wrap: balance; text-shadow: 0 6px 30px rgba({e.sombra}, 0.55); }}
  .f-precios h2.oscuro {{ color: {c['primario']}; text-shadow: none; font-size: {e.tam(92)}; }}
  .clave .fondo {{ transform: skewX(-8deg) scaleX(1); }}
  .f-precios .clave .pi {{ color: {e.resalta_texto()}; }}
  .f-etiqueta {{ margin-bottom: 22px; }}
  .f-etiqueta span {{ display: inline-block; background: {e.claro}; color: {c['primario']}; font-weight: 800; font-size: 36px; letter-spacing: 0.08em;
                      text-transform: uppercase; padding: 13px 26px 11px; border-radius: 999px; transform: rotate(-3deg);
                      box-shadow: 0 10px 30px rgba({e.sombra}, 0.3); }}
  .f-precios .f-etiqueta span {{ background: {c['primario']}; color: {e.claro}; }}
  .f-nota {{ {e.fuente_manuscrita} font-size: 70px; line-height: 1.05; color: {e.claro}; margin-top: 16px;
             text-wrap: balance; text-shadow: 0 3px 18px rgba({e.sombra}, 0.7); }}
  .f-nota-sola {{ position: absolute; left: 7%; right: 7%; bottom: 7%; text-align: center; }}
  .f-firma {{ position: absolute; right: 5.5%; top: 4%; width: 130px; height: 130px; border-radius: 50%; background: {e.claro};
              box-shadow: 0 8px 26px rgba({e.sombra}, 0.3); display: flex; align-items: center; justify-content: center; }}
  .f-firma img {{ width: 102px; height: auto; }}
  .f-placa-clara {{ position: absolute; inset: 0; background: radial-gradient(ellipse 90% 70% at 50% 35%, {e.cierre[0]} 0%, {e.cierre[1]} 50%, {e.cierre[2]} 100%); }}
  .f-precios {{ position: absolute; left: 7%; right: 7%; top: 13%; bottom: 7%; display: flex; flex-direction: column; justify-content: center; gap: 30px; }}
  .f-precios-tit {{ text-align: center; margin-bottom: 10px; }}
  .f-item {{ display: flex; align-items: center; justify-content: space-between; gap: 24px; background: {e.claro}; border-radius: 30px;
             padding: 30px 36px; border-left: 16px solid var(--tono); box-shadow: 0 14px 34px rgba({e.sombra}, 0.16); }}
  .f-item-nombre {{ {e.fuente_titulo} font-size: {e.tam(64)}; line-height: 1; color: var(--tono); }}
  .f-item-detalle {{ font-weight: 600; font-size: 28px; line-height: 1.3; color: rgba({e.sombra}, 0.8); margin-top: 10px; max-width: 500px; }}
  .f-item-precio {{ font-weight: 800; font-size: 46px; color: {e.claro}; background: var(--tono); padding: 14px 24px; border-radius: 18px; white-space: nowrap; }}
  .f-precios .f-nota {{ color: {c['secundario']}; text-shadow: none; text-align: center; font-size: 62px; }}
  .f-cierre {{ position: absolute; left: 0; right: 0; top: 18%; display: flex; flex-direction: column; align-items: center; gap: 34px; }}
  .f-cierre img {{ width: 520px; height: auto; }}
  .f-cta {{ {e.fuente_titulo} font-size: {e.tam(80)}; line-height: 1.05; color: {c['primario']};
            text-align: center; max-width: 820px; text-wrap: balance; }}
  .f-lugar {{ font-weight: 800; font-size: 32px; letter-spacing: 0.32em; text-transform: uppercase; color: {c['secundario']}; }}
"""
    documento = f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{html.escape(marca['nombre'])} — {pedido.name}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{css(c, "50%", e)}{extra}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{n}">
      <!-- Generado por herramientas/armar_foto.py desde plan/publicacion.yaml: una placa por segundo -->
{chr(10).join(capas)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.to({{}}, {{ duration: {n} }}, 0);  // placas fijas: la línea de tiempo solo marca la duración
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (pedido / "render" / "index.html").write_text(documento, encoding="utf-8")
    print(f"index.html ({pub.get('formato', 'foto')}): {n} placa(s) de {W}×{H}")
    return n


def renderizar(pedido, n):
    salida = pedido / "salida"
    salida.mkdir(exist_ok=True)
    ok, error = hyperframes(pedido / "render", "placas.mp4")
    if not ok:
        raise SystemExit(f"render: {error}")
    for k in range(n):
        correr([FFMPEG, "-v", "error", "-y", "-ss", f"{k + 0.5:.2f}", "-i", str(pedido / "render" / "placas.mp4"),
                "-frames:v", "1", "-q:v", "1", str(salida / f"placa-{k + 1:02d}.jpg")])
    print(f"→ {salida}/placa-01.jpg … placa-{n:02d}.jpg")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--sin-render", action="store_true")
    a = ap.parse_args()
    pedido = Path(a.pedido)
    n = armar(pedido)
    if not a.sin_render:
        renderizar(pedido, n)


if __name__ == "__main__":
    main()
