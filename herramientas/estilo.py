"""Dirección de arte por marca (M-23): tokens, CSS base, look (calidez, viñeta, grano) y helpers de texto.

Un solo lugar para el estilo: lo usan armar_pop.py (reels), armar_historia.py, armar_foto.py y
las composiciones a medida (render/armar.py). Los valores por defecto son los de "salon-pop"
(Salón Demo); cada marca los pisa con el bloque `estilo:` de su marca.yaml, y lo que no
declara queda como en salon-pop:

    estilo:
      nombre: archivo                # para los mensajes y el HTML
      claro: "#F5EDE1"               # firma, píldoras, texto sobre foto
      sombra: "30, 24, 20"           # rgb de sombras y viñeta
      calidez: { color: "#E8B04A", opacidad: 0.12 }   # capa soft-light encima del video
      destello: "#F2C230"            # estrellitas; `destellos: false` las apaga
      fondo: "#141210"               # detrás del video
      correccion: "contrast(1.05) saturate(0.95)"
      vineta: 0.45                   # alfa del borde (reels e historias); vineta_foto para placas
      grano: 0.14                    # grano de película; grano_foto para placas
      luz: ["255, 230, 180", "242, 194, 48"]          # destello de la transición "luz" (rgb)
      cierre: ["#FBF6EE", "#F5EDE1", "#E6D6BC"]       # degradé de la placa de cierre (centro → borde)
      resaltador: "#F2C230"          # fondo de la palabra clave y de los bloques (default: colores.primario)
      resaltador_texto: "#1E1A17"    # texto encima del resaltador (default: claro)
      subtitulo_fondo: "#F2C230"     # píldora de los subtítulos de la voz (default: sombra al 78 %)
      subtitulo_texto: "#1E1A17"     # (default: claro)
      subtitulo_tipografia: titulo   # titulo | texto (default): la de display, más grande, en vez de la sans
      titulo: { familia: "Bebas Neue", archivo: bebas-neue-latin-400-normal.woff2, peso: 400,
                estilo: normal, escala: 1.25, mayusculas: true, interletra: 0.01em }
      texto: { familia: Montserrat, archivos: { 800: montserrat-latin-800-normal.woff2, 600: montserrat-latin-600-normal.woff2 } }
      manuscrita: { familia: Caveat, archivo: caveat-latin-700-normal.woff2, peso: 700 }

Las fuentes salen de marcas/<marca>/assets/fuentes/. `escala` multiplica el tamaño de los
títulos (una condensada necesita más cuerpo que la Fraunces para pesar lo mismo).
"""

import html
import shutil
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

TITULO_TAM, TITULO_TAM_LARGO = 104, 92   # px de los títulos (largo: más de 26 caracteres), antes de `escala`


@dataclass(frozen=True)
class Estilo:
    nombre: str = "salon-pop"
    claro: str = "#fff8fb"                 # blanco rosado
    sombra: str = "40, 4, 24"              # ciruela
    calidez_color: str = "#ff9a6a"         # durazno
    calidez: float = 0.16
    destello: str = "#F5C76B"              # dorado
    destellos: bool = True
    fondo: str = "#1a0712"
    correccion: str = "contrast(1.07) saturate(1.16) brightness(1.03)"
    vineta: float = 0.42
    grano: float = 0.11
    vineta_foto: float = 0.4               # fotos y carruseles: imagen fija, más suave
    grano_foto: float = 0.1
    luz: tuple = ("255, 214, 160", "255, 140, 120")
    cierre: tuple = ("#fff6fa", "#fbe3ef", "#f4c3dc")
    resaltador: str | None = None          # None: colores.primario de la marca
    resaltador_texto: str | None = None    # None: claro
    subtitulo_fondo: str | None = None     # None: rgba(sombra, 0.78)
    subtitulo_texto: str | None = None     # None: claro
    subtitulo_tipografia: str = "texto"    # titulo: los subtítulos en la tipografía de display
    titulo: dict = field(default_factory=lambda: {
        "familia": "Fraunces", "archivo": "fraunces-latin-900-italic.woff2", "peso": 900,
        "estilo": "italic", "escala": 1.0, "mayusculas": False, "interletra": "-0.01em", "respaldo": "serif"})
    texto: dict = field(default_factory=lambda: {
        "familia": "Montserrat", "archivos": {800: "montserrat-latin-800-normal.woff2", 600: "montserrat-latin-600-normal.woff2"}})
    manuscrita: dict = field(default_factory=lambda: {
        "familia": "Caveat", "archivo": "caveat-latin-700-normal.woff2", "peso": 700})

    # ---- derivados
    def tam(self, px):
        """Tamaño de un título, escalado según la fuente de la marca."""
        return f"{round(px * self.titulo.get('escala', 1.0))}px"

    def medidas_titulo(self, marca_dir):
        """Lo que legibilidad.franja_titulo necesita para medir un título con la fuente de la marca."""
        t, escala = self.titulo, self.titulo.get("escala", 1.0)
        return {"tam": round(TITULO_TAM * escala), "tam_largo": round(TITULO_TAM_LARGO * escala),
                "fuente": Path(marca_dir) / "assets" / "fuentes" / t["archivo"], "mayusculas": bool(t.get("mayusculas")),
                "interletra": float(str(t.get("interletra", "0")).removesuffix("em") or 0)}

    @property
    def fuente_titulo(self):
        t = self.titulo
        return (f'font-family: "{t["familia"]}", {t.get("respaldo", "serif")}; font-style: {t.get("estilo", "normal")}; '
                f'font-weight: {t.get("peso", 400)};' + (" text-transform: uppercase;" if t.get("mayusculas") else ""))

    @property
    def fuente_subtitulo(self):
        if self.subtitulo_tipografia == "titulo":
            return f"{self.fuente_titulo} font-size: {self.tam(56)}; letter-spacing: 0.02em;"
        return f'font-family: "{self.texto["familia"]}", sans-serif; font-weight: 800; font-size: 50px;'

    @property
    def fuente_manuscrita(self):
        m = self.manuscrita
        return f'font-family: "{m["familia"]}", cursive; font-weight: {m.get("peso", 700)};'

    def resalta(self, c):
        return self.resaltador or c["primario"]

    def resalta_texto(self):
        return self.resaltador_texto or self.claro

    def archivos_fuentes(self, manuscrita=False):
        return ([self.titulo["archivo"]] + list(self.texto["archivos"].values())
                + ([self.manuscrita["archivo"]] if manuscrita else []))

    def font_faces(self, manuscrita=False):
        t, m = self.titulo, self.manuscrita
        caras = [f'@font-face {{ font-family: "{t["familia"]}"; font-style: {t.get("estilo", "normal")}; '
                 f'font-weight: {t.get("peso", 400)}; src: url("assets/{t["archivo"]}") format("woff2"); }}']
        caras += [f'@font-face {{ font-family: "{self.texto["familia"]}"; font-weight: {peso}; src: url("assets/{a}") format("woff2"); }}'
                  for peso, a in self.texto["archivos"].items()]
        if manuscrita:
            caras.append(f'@font-face {{ font-family: "{m["familia"]}"; font-weight: {m.get("peso", 700)}; '
                         f'src: url("assets/{m["archivo"]}") format("woff2"); }}')
        return "\n  ".join(caras)


SALON_POP = Estilo()


def de_marca(marca, ajustes=None):
    """El estilo de una marca: salon-pop con lo que declare `marca.yaml › estilo`.

    `ajustes` (guion › estilo_ajustes) pisa tokens solo para ese reel: el look de una tendencia
    (tipografía de sus rótulos) o menos grano con material nítido. Los tokens que son
    diccionarios (titulo, texto, calidez…) se combinan clave por clave con los de la marca."""
    e = dict(marca.get("estilo") or {})
    for k, v in (ajustes or {}).items():
        e[k] = {**e[k], **v} if isinstance(v, dict) and isinstance(e.get(k), dict) else v
    if isinstance(e.get("calidez"), dict):
        cal = e.pop("calidez")
        e["calidez_color"], e["calidez"] = cal.get("color", SALON_POP.calidez_color), cal.get("opacidad", SALON_POP.calidez)
    for k in ("titulo", "texto", "manuscrita"):
        if k in e:
            e[k] = {**getattr(SALON_POP, k), **e[k]}
    for k in ("luz", "cierre"):
        if k in e:
            e[k] = tuple(e[k])
    validos = {f.name for f in fields(Estilo)}
    desconocidos = set(e) - validos
    if desconocidos:
        raise SystemExit(f"marca.yaml › estilo: no conozco {', '.join(sorted(desconocidos))}")
    return replace(SALON_POP, **e)


# ---- compatibilidad: las composiciones a medida viejas importan los tokens de salon-pop sueltos
CLARO, CIRUELA, DURAZNO, DORADO, FONDO = SALON_POP.claro, SALON_POP.sombra, SALON_POP.calidez_color, SALON_POP.destello, SALON_POP.fondo
CORRECCION, CALIDEZ, VINETA, GRANO_OPACIDAD = SALON_POP.correccion, SALON_POP.calidez, SALON_POP.vineta, SALON_POP.grano
VINETA_FOTO, GRANO_FOTO = SALON_POP.vineta_foto, SALON_POP.grano_foto
CAVEAT = SALON_POP.manuscrita["archivo"]
FUENTES = SALON_POP.archivos_fuentes()

SUBTITULO_BASE = "64%"       # línea inferior de los subtítulos de la voz
SUBTITULO_FRANJA = (0.565, 0.645)   # alto que ocupan (fracción): los títulos de esa toma la esquivan

GRANO = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' "
         "stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")
ESTRELLA = ("<svg viewBox='0 0 100 100'><path d='M50 0 C54 34 66 46 100 50 C66 54 54 66 50 100 "
            "C46 66 34 54 0 50 C34 46 46 34 50 0Z' fill='currentColor'/></svg>")


def r(x):
    return f"{x:.3f}"


def css(c, texto_base, e=SALON_POP):
    s, cl, tx = e.sombra, e.claro, e.texto["familia"]
    return f"""
  {e.font_faces()}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: {e.fondo}; }}
  #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; font-family: "{tx}", sans-serif; }}

  /* VIDEO: corrección de color común a todas las tomas */
  #capa-video {{ position: absolute; inset: 0; filter: {e.correccion}; }}
  .trans, .marco {{ position: absolute; inset: 0; will-change: transform, filter; }}
  .medio {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}

  /* LOOK: calidez + viñeta + grano */
  #calidez {{ position: absolute; inset: 0; background: {e.calidez_color}; mix-blend-mode: soft-light; opacity: {e.calidez}; }}
  #vineta {{ position: absolute; inset: 0; background: radial-gradient(ellipse 75% 60% at 50% 45%, transparent 55%, rgba({s}, {e.vineta}) 100%); }}
  #grano {{ position: absolute; inset: -200px; background-image: url("{GRANO}"); background-size: 256px 256px; opacity: {e.grano}; mix-blend-mode: overlay; }}
  #luz {{ position: absolute; width: 2600px; height: 2600px; left: -760px; top: -340px; opacity: 0;
          background: radial-gradient(circle at 50% 50%, rgba({e.luz[0]}, 0.95) 0%, rgba({e.luz[1]}, 0.55) 30%, rgba({e.luz[1]}, 0.0) 62%);
          mix-blend-mode: screen; }}
  /* HUMO: la transición "humo" (armar_pop.transicion), bocanadas claras difusas que tapan el corte */
  .humo {{ position: absolute; inset: -20%; opacity: 0; pointer-events: none; filter: blur(36px); }}
  .humo i {{ position: absolute; border-radius: 50%; transform: translate(-50%, -50%);
             background: radial-gradient(circle at 50% 50%, rgba(238, 232, 250, 0.95) 0%, rgba(214, 204, 236, 0.7) 35%, rgba(200, 190, 230, 0) 68%); }}

  /* TÍTULOS: palabra por palabra, palabra clave con resaltador */
  .titulo {{ position: absolute; left: 0; right: 0; bottom: calc(100% - {texto_base}); display: flex; justify-content: center; padding: 0 90px; }}
  /* Sombra difusa detrás del título (no una caja): legible sobre fondos claros sin parecer plantilla */
  .titulo::before {{ content: ""; position: absolute; left: 50%; top: 50%; width: 1100px; height: 520px; transform: translate(-50%, -50%);
                     background: radial-gradient(ellipse 50% 50% at 50% 50%, rgba({s}, 0.62) 0%, rgba({s}, 0.34) 45%, transparent 75%); opacity: var(--sombra, 1); }}
  .titulo > div {{ position: relative; }}
  .titulo h2 {{ {e.fuente_titulo} font-size: {e.tam(TITULO_TAM)}; line-height: 1.06;
                letter-spacing: {e.titulo.get("interletra", "0")}; color: {cl}; text-align: center; text-wrap: balance; max-width: 900px;
                text-shadow: 0 6px 30px rgba({s}, 0.55), 0 2px 6px rgba({s}, 0.5); }}
  .p {{ display: inline-block; overflow: hidden; vertical-align: bottom; padding: 0.04em 0.08em 0.12em; margin: -0.04em -0.02em -0.12em; }}
  .pi {{ display: inline-block; will-change: transform; }}
  .titulo.largo h2 {{ font-size: {e.tam(TITULO_TAM_LARGO)}; }}
  .clave {{ position: relative; display: inline-block; }}
  .clave .fondo {{ position: absolute; left: -0.06em; right: -0.1em; top: 0.18em; bottom: 0.04em; background: {e.resalta(c)};
                   border-radius: 0.12em; transform: skewX(-8deg) scaleX(0); transform-origin: left center; z-index: 0; }}
  .clave .pi {{ position: relative; z-index: 1; text-shadow: none; color: {e.resalta_texto()}; }}
  /* Fondo claro (legibilidad.py): cada palabra en un bloque del resaltador y la clave invertida.
     La sombra difusa sobre una pared blanca queda como una mancha gris y no llega a 3:1. */
  .titulo.bloques::before {{ display: none; }}
  .titulo.bloques h2 {{ line-height: 1.2; text-shadow: none; color: {e.resalta_texto()}; }}
  .titulo.bloques .p {{ padding: 0.06em 0.2em 0.16em; margin: -0.06em -0.17em -0.16em; }}
  .titulo.bloques .pi {{ background: {e.resalta(c)}; padding: 0.02em 0.16em 0.08em; border-radius: 0.14em;
                         box-shadow: 0 8px 22px rgba({s}, 0.35); }}
  .titulo.bloques .clave .fondo {{ display: none; }}
  .titulo.bloques .clave .pi {{ background: {cl}; color: {c['primario']}; }}

  /* STICKERS de pasos: píldora clara, levemente torcida */
  .sticker {{ position: absolute; left: 8%; top: 17%; }}
  .sticker span {{ display: inline-block; background: {cl}; color: {c['primario']}; font-weight: 800; font-size: 44px;
                   letter-spacing: 0.05em; text-transform: uppercase; padding: 16px 30px 14px; border-radius: 999px;
                   transform: rotate(-4deg); box-shadow: 0 10px 30px rgba({s}, 0.35); will-change: transform; }}
  .sticker b {{ color: {c['secundario']}; margin-right: 14px; }}

  /* COMPARACIÓN antes | después */
  .lado, .desliz {{ position: absolute; inset: 0; will-change: transform; }}
  .divisor {{ position: absolute; top: 0; bottom: 0; left: 0; width: 10px; margin-left: -5px; background: {cl};
              box-shadow: 0 0 30px {cl}, 0 0 6px rgba({s}, 0.6); will-change: transform; }}
  /* a la altura del torso: arriba taparían el pelo, que es lo que se compara */
  .etiqueta {{ position: absolute; top: 57%; width: 50%; display: flex; justify-content: center; }}
  .etiqueta span {{ display: inline-block; background: {cl}; color: {c['primario']}; font-weight: 800; font-size: 44px;
                    letter-spacing: 0.08em; text-transform: uppercase; padding: 16px 30px 14px; border-radius: 999px;
                    box-shadow: 0 10px 30px rgba({s}, 0.35); will-change: transform; }}
  .etiqueta.der {{ left: 50%; }}
  .etiqueta.der span {{ background: {c['primario']}; color: {cl}; }}

  /* SUBTÍTULOS de la voz (voz.py): píldora oscura, encima del borde de la zona segura (64 %) */
  .subtitulo {{ position: absolute; left: 0; right: 0; bottom: calc(100% - {SUBTITULO_BASE}); display: flex; justify-content: center; padding: 0 80px; }}
  .subtitulo span {{ {e.fuente_subtitulo} line-height: 1.3; color: {e.subtitulo_texto or cl};
                     background: {e.subtitulo_fondo or f"rgba({s}, 0.78)"}; padding: 8px 22px 10px; border-radius: 16px; text-align: center; max-width: 900px;
                     -webkit-box-decoration-break: clone; box-decoration-break: clone; }}

  /* TARJETAS (vouchers, productos): borde redondeado, sombra del tono de la marca */
  .capa-tarjetas {{ position: absolute; inset: 0; }}
  .tarjeta {{ position: absolute; border-radius: 22px; box-shadow: 0 22px 46px rgba({s}, 0.5), 0 0 0 6px {cl}; will-change: transform; }}

  /* INSERTOS (armar_pop.py): archivo encima de la toma mientras la voz sigue */
  .inserto {{ position: absolute; inset: 0; overflow: hidden; background: {e.fondo}; }}
  .ins-marco {{ position: absolute; inset: 0; will-change: transform; }}
  .ins-fondo {{ filter: blur(36px) brightness(0.55) saturate(0.9); transform: scale(1.2); }}
  .ins-cuadro {{ position: absolute; object-fit: cover; border: 14px solid {cl}; box-shadow: 0 30px 70px rgba({s}, 0.6); }}
  .placa {{ position: absolute; inset: 0; background: radial-gradient(ellipse 90% 70% at 50% 42%, {e.cierre[0]} 0%, {e.cierre[1]} 50%, {e.cierre[2]} 100%);
            display: flex; align-items: center; justify-content: center; padding: 0 90px 520px; }}
  .placa h2 {{ {e.fuente_titulo} font-size: {e.tam(118)}; line-height: 1.05; color: {c['primario']}; text-align: center; text-wrap: balance; max-width: 900px; }}
  .placa.cita h2 {{ font-size: {e.tam(84)}; }}
  .placa-pie {{ margin: 28px 0 0; font-weight: 600; font-size: 34px; letter-spacing: 0.06em; text-transform: uppercase; color: {c['secundario']}; text-align: center; }}
  .mapa {{ background: radial-gradient(ellipse 80% 60% at 50% 45%, rgba({e.luz[0]}, 0.07) 0%, rgba(0, 0, 0, 0) 70%), {e.fondo}; }}
  .mapa-svg {{ position: absolute; inset: 0; overflow: visible; }}
  .mapa-grilla {{ fill: none; stroke: {cl}; stroke-opacity: 0.08; stroke-width: 1.5; }}
  .mapa-tierra {{ fill: {e.cierre[2]}; fill-opacity: 0.92; stroke: rgba({s}, 0.6); stroke-width: 2; stroke-linejoin: round; }}
  .mapa-ruta {{ fill: none; stroke-width: 10; stroke-linecap: round; filter: drop-shadow(0 4px 10px rgba({s}, 0.55)); }}
  .mapa-punto {{ stroke: {e.fondo}; stroke-width: 5; }}
  .mapa-lugar {{ position: absolute; margin: 0; transform: translateY(-50%); white-space: nowrap; }}
  .mapa-lugar.izq {{ transform: translate(-100%, -50%); }}
  .mapa-lugar.arriba {{ transform: translate(-50%, calc(-100% + 13px)); }}
  .mapa-lugar .ml {{ display: flex; align-items: center; gap: 12px; font-style: normal; will-change: transform; }}
  .mapa-lugar.izq .ml {{ flex-direction: row-reverse; }}
  .mapa-lugar.arriba .ml {{ flex-direction: column-reverse; gap: 10px; }}
  .mapa-lugar i {{ width: 18px; height: 18px; border-radius: 50%; background: {e.fondo}; border: 4px solid {cl}; flex: none; }}
  .mapa-lugar span {{ {e.fuente_titulo} font-size: {e.tam(40)}; letter-spacing: 0.05em; line-height: 1; color: {cl};
                      background: rgba({s}, 0.82); padding: 8px 16px 6px; border-radius: 8px; }}
  .encabezado {{ position: absolute; left: 0; right: 0; display: flex; justify-content: center; padding: 0 90px; }}
  .encabezado span {{ display: inline-block; {e.fuente_titulo} font-size: {e.tam(50)}; letter-spacing: 0.04em; line-height: 1.1;
                      background: {cl}; color: {c['primario']}; padding: 10px 26px 7px; border-radius: 12px;
                      box-shadow: 0 10px 28px rgba({s}, 0.35); white-space: nowrap; will-change: transform; }}
  .encabezado.largo span {{ white-space: normal; text-wrap: balance; text-align: center; max-width: 860px; }}
  .encabezado b {{ font-weight: inherit; background: {e.resalta(c)}; color: {e.resalta_texto()}; padding: 0 0.18em; border-radius: 0.12em; }}
  .rotulo {{ position: absolute; left: 7%; margin: 0; }}
  .rotulo span {{ display: inline-block; {e.fuente_titulo} font-size: {e.tam(44)}; letter-spacing: 0.04em; line-height: 1.1;
                  background: {e.resalta(c)}; color: {e.resalta_texto()}; padding: 10px 22px 8px; border-radius: 10px;
                  box-shadow: 0 10px 28px rgba({s}, 0.4); will-change: transform; }}

  /* DESTELLOS */
  .destello {{ position: absolute; width: 64px; height: 64px; will-change: transform; }}
  .destello svg {{ width: 100%; height: 100%; display: block; }}

  /* CIERRE */
  #cierre {{ position: absolute; inset: 0; }}
  #cierre-placa {{ position: absolute; inset: 0; background: radial-gradient(ellipse 90% 70% at 50% 40%, {e.cierre[0]} 0%, {e.cierre[1]} 45%, {e.cierre[2]} 100%);
                   clip-path: circle(0% at 50% 42%); }}
  #cierre-contenido {{ position: absolute; left: 0; right: 0; top: 15%; display: flex; flex-direction: column; align-items: center; gap: 30px; }}
  #cierre-logo {{ width: 470px; height: auto; display: block; will-change: transform; }}
  #cierre-cta {{ {e.fuente_titulo} font-size: {e.tam(76)}; line-height: 1.05; color: {c['primario']};
                 text-align: center; max-width: 760px; text-wrap: balance; }}
  #cierre-lugar {{ font-weight: 800; font-size: 30px; letter-spacing: 0.32em; text-transform: uppercase; color: {c['secundario']}; }}
"""


def palabras(texto, destacar, prefijo):
    """Envuelve cada palabra para la entrada enmascarada; la clave lleva resaltador."""
    out, claves = [], []
    for i, w in enumerate(texto.split()):
        limpio = w.strip("¿?¡!.,").lower()
        if destacar and limpio == destacar.lower():
            claves.append(f"{prefijo}-k{i}")
            out.append(f'<span class="p"><span class="clave" id="{prefijo}-k{i}"><span class="fondo"></span>'
                       f'<span class="pi">{html.escape(w)}</span></span></span>')
        else:
            out.append(f'<span class="p"><span class="pi">{html.escape(w)}</span></span>')
    return " ".join(out), claves


def destellos(prefijo, colores, posiciones, e=SALON_POP):
    """Estrellitas alrededor de un título. Con `destellos: false` en la marca no hay ninguna
    (los tweens que las animan se saltean con `hay_destellos`)."""
    if not e.destellos:
        return ""
    return "".join(
        # data-layout-allow-overflow: van a propósito fuera de la caja del título (check avisaba escaped_container)
        f'<div class="destello" id="{prefijo}-d{i}" data-layout-allow-overflow style="left:{x}%; top:{y}%; width:{s}px; height:{s}px; color:{colores[i % len(colores)]}">{ESTRELLA}</div>'
        for i, (x, y, s) in enumerate(posiciones))


def copiar_assets(marca_dir, assets, caveat=False, e=SALON_POP):
    """Logo y fuentes de la marca a render/assets/."""
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(marca_dir / "assets" / "logo.png", assets / "logo.png")
    for f in e.archivos_fuentes(manuscrita=caveat):
        shutil.copy2(marca_dir / "assets" / "fuentes" / f, assets / f)


def capas_look(luz=False):
    """Las capas del look, encima del video y debajo de los textos."""
    return '<div id="calidez"></div><div id="vineta"></div><div id="grano"></div>' + ('<div id="luz"></div>' if luz else "")


def grano_tween(total):
    """El grano salta de posición 12 veces por segundo, de forma determinista (igual en cada render)."""
    pasos = int(total * 12)
    return (f'tl.fromTo("#grano", {{ x: 0, y: 0 }}, {{ x: {pasos * 37 % 200}, y: {pasos * 53 % 200}, '
            f'duration: {r(total)}, ease: "steps({pasos})" }}, 0);')


def look_css_foto(prefijo="f-", e=SALON_POP):
    """Calidez, viñeta y grano para una imagen fija (placas de foto y carrusel)."""
    return f"""  .{prefijo}calidez {{ position: absolute; inset: 0; background: {e.calidez_color}; mix-blend-mode: soft-light; opacity: {e.calidez}; }}
  .{prefijo}vineta {{ position: absolute; inset: 0; background: radial-gradient(ellipse 80% 65% at 50% 45%, transparent 55%, rgba({e.sombra}, {e.vineta_foto}) 100%); }}
  .{prefijo}grano {{ position: absolute; inset: 0; background-image: url("{GRANO}"); background-size: 256px 256px; opacity: {e.grano_foto}; mix-blend-mode: overlay; }}"""
