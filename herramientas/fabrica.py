"""Un comando por pedido: corre todos los pasos mecánicos en orden y saltea los que no cambiaron.

Uso:
    uv run python herramientas/fabrica.py pedidos/<pedido> [--solo PASO] [--forzar] [--sin-check]

El formato sale del plan:
    plan/guion.yaml       → reel:     clips → composicion → render → audio → portada → verificar → puntaje → mensaje
    plan/historia.yaml    → historia: historia → verificar → mensaje
    plan/publicacion.yaml → foto o carrusel: placas → verificar → puntaje → mensaje

Cada paso guarda en render/.fabrica.json una huella de sus entradas (las partes del plan
que usa, los archivos que lee, el código de sus herramientas). Si la huella no cambió y sus
salidas existen, no se rehace. Cambiar un texto del guion rearma la composición y el render,
pero no vuelve a preparar los clips. Un `verificar` que falla no guarda huella: se repite.
La portada se rehace cuando cambia el video, salvo que alguien la haya reemplazado a mano
(la fábrica guarda la huella del archivo que escribió): esa no se pisa sin --forzar.

Lo que lleva criterio no lo hace: el guion, caption.txt, informe.md y salida/puntos.yaml
los escribe Claude. Si faltan, la fábrica los lista como pendientes al final.

`mensaje` escribe salida/para-<quien>.txt, el mensaje de WhatsApp para reenviarle tal cual a quien
publica (`mensaje:` en marca.yaml; si falta, Ana):
    mensaje:
      para: Pablo                       # a quién va; el archivo es para-pablo.txt
      saludo: ""                        # lo que cierra el saludo (default "💞", el de Ana)
Necesita caption.txt (salvo en historias) y el bloque `publicar` del plan:
    publicar:
      nombre: "los pochoclos"          # cómo se nombra la pieza en el mensaje (si falta, el slug)
      colaboradora: "@usuaria"          # invitarla como colaboradora (opcional; nunca a una menor)
      permisos: ["Andrea"]              # a quién pedirle el OK antes de publicar; [] si solo aparece quien publica
      portada: 1.2                      # segundo del reel para portada.jpg (si falta, cuando entró el título del gancho)
      antes: ["Archivá el reel original (no lo borres)."]   # pasos propios de esta pieza, van primero
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from comun import FFMPEG, RAIZ, correr, duraciones  # noqa: E402
from render import HYPERFRAMES, entorno, hyperframes  # noqa: E402

HERR = Path(__file__).parent
ENV = entorno()


# ---------------------------------------------------------------- huellas

def archivo(p):
    """Identidad barata de un archivo: ruta, tamaño y fecha (o que no existe)."""
    p = Path(p)
    if not p.exists():
        return [str(p), None]
    if p.is_dir():
        return [archivo(x) for x in sorted(p.rglob("*")) if x.is_file()]
    st = p.stat()
    return [str(p), st.st_size, st.st_mtime_ns]


def codigo(*nombres):
    """El contenido de las herramientas: si cambia el código de un paso, el paso se rehace."""
    return [hashlib.sha1((HERR / n).read_bytes()).hexdigest() for n in nombres]


def medios_de_la_composicion(pedido, plan):
    """Los archivos que la composición lee además de los clips: imágenes de los insertos (desde el pedido),
    `tarjetas` (desde la raíz) y las transcripciones de `subtitulos_fuente`. Si se rehace una imagen sin
    tocar el guion, la composición tiene que volver a armarse (pasó con las tarjetas de Olinail's, 16/10)."""
    out = []
    for t in plan.get("tomas") or []:
        out += [pedido / i["archivo"] for i in t.get("insertos") or [] if i.get("archivo")]
        out += [RAIZ / c for c in t.get("tarjetas") or []]
    fuente = plan.get("subtitulos_fuente")
    out += [pedido / f for f in (fuente.values() if isinstance(fuente, dict) else [fuente] if fuente else [])]
    return out


def huella(*partes):
    return hashlib.sha1(json.dumps(partes, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


# Partes del plan que son notas o van solo al mensaje: cambiarlas no rehace la imagen.
NOTAS = {"publicar", "adaptaciones", "diagnostico_original", "direccion_de_arte", "momento_wow",
         "zonas_seguras", "pilar", "sticker_sugerido"}


# Lo que preparar_clips.py lee de cada toma: la transición o la descripción no cambian el clip.
CLIPS = ("n", "fuente", "desde", "hasta", "beats", "comparar", "encuadre", "espejar", "estabilizar", "solape", "cierre",
         "color", "rol", "que", "voz")   # rol y que: eligen la toma de referencia del color


def visual(plan):
    """El plan sin notas; de `musica` solo lo que mueve los cortes (análisis e inicio)."""
    out = {k: v for k, v in plan.items() if k not in NOTAS}
    if isinstance(out.get("musica"), dict):
        out["musica"] = {k: out["musica"].get(k) for k in ("analisis", "inicio")}
    return out


class Paso:
    def __init__(self, nombre, entradas, salidas, correr, a_mano=False):
        self.nombre, self.entradas, self.salidas, self.correr = nombre, entradas, salidas, correr
        # la salida se puede reemplazar a mano (una portada elegida por Fernando): si no es la que
        # escribió la fábrica, no se pisa. Antes la portada se hacía una sola vez y quedaba la de un
        # render viejo aunque el video cambiara
        self.a_mano = a_mano


def uv(script, *args, cwd=None):
    """Corre una herramienta con el mismo Python y muestra su salida con sangría."""
    res = subprocess.run([sys.executable, str(HERR / script), *map(str, args)], cwd=cwd, env=ENV,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linea in (res.stdout + res.stderr).splitlines():
        if linea.strip() and "VIRTUAL_ENV" not in linea and "net_impl_backend" not in linea:
            print(f"      {linea}")
    return res.returncode == 0


def a_medida_ok(script):
    """Composición a medida (render/armar.py): se corre desde su carpeta."""
    script = Path(script).resolve()  # se corre desde su carpeta: una ruta relativa se duplicaría
    res = subprocess.run([sys.executable, str(script)], cwd=script.parent, env=ENV,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linea in (res.stdout + res.stderr).splitlines():
        if linea.strip() and "VIRTUAL_ENV" not in linea and "net_impl_backend" not in linea:
            print(f"      {linea}")
    return res.returncode == 0


def borrador(pedido):
    """Render liviano para revisar (15 fps, calidad draft) con el audio de siempre, en salida/borrador.mp4.
    Iterar sobre el borrador y renderizar en calidad final una sola vez: en un relato de 2 min, la vuelta
    completa (render delivery + verificación) tardaba entre 1,5 y 2 horas."""
    print("  → borrador")
    ok, error = hyperframes(pedido / "render", "../salida/borrador-mudo.mp4", calidad="draft", fps=15)
    if not ok:
        print(f"      ✗ render: {error}")
        return False
    uv("audio.py", pedido, "--video", "salida/borrador-mudo.mp4", "--salida", "salida/borrador.mp4")
    (pedido / "salida" / "borrador-mudo.mp4").unlink(missing_ok=True)
    print("\nBorrador: salida/borrador.mp4 (15 fps, calidad draft). Para la versión final, la fábrica sin --borrador.")
    return True


def render_hyperframes(pedido, destino):
    ok, error = hyperframes(pedido / "render", destino)
    if not ok:
        print("      " + error.replace("\n", "\n      "))
    return ok


# ---------------------------------------------------------------- reel

def pasos_reel(pedido, plan, a):
    from audio import archivo_final, musica_del_pedido

    tomas = plan.get("tomas") or plan.get("escenas") or []
    marca = RAIZ / "marcas" / plan["marca"]
    clips = pedido / "render" / "assets" / "clips"
    a_medida = pedido / "render" / "armar.py"
    modo, musica = musica_del_pedido(pedido, plan)
    analisis = pedido / musica["analisis"] if musica.get("analisis") else None
    final = pedido / "salida" / archivo_final(modo)

    esperados = []
    for t in tomas:
        if t.get("comparar"):
            esperados += [clips / f"{t['n']:02d}a.mp4", clips / f"{t['n']:02d}b.mp4"]
        elif t.get("fuente"):
            esperados.append(clips / f"{t['n']:02d}.mp4")
    ritmo = {k: plan.get(k) for k in ("bpm", "desfase")} | {"musica": visual(plan).get("musica")}

    def portada():
        t = (plan.get("publicar") or {}).get("portada")
        if t is None:  # cuando el título del gancho ya entró, sin pasarse de la primera toma
            t = min(1.5, duraciones(plan, pedido)[0] * 0.7)
        correr([FFMPEG, "-v", "error", "-y", "-ss", f"{float(t):.3f}", "-i", str(pedido / "salida" / "reel.mp4"),
                "-frames:v", "1", "-q:v", "2", str(pedido / "salida" / "portada.jpg")])
        return True

    pasos = []
    if esperados:
        pasos.append(Paso("clips",
                          lambda: [[{k: t.get(k) for k in CLIPS} for t in tomas if not t.get("cierre")], ritmo, archivo(analisis) if analisis else None,
                                   [archivo(RAIZ / t["fuente"]) for t in tomas if t.get("fuente")],
                                   plan.get("igualar_color"), codigo("preparar_clips.py", "movimiento.py", "color.py", "voz.py", "separar.py", "legibilidad.py", "comun.py")],
                          esperados, lambda: uv("preparar_clips.py", pedido)))
    pasos += [
        Paso("composicion",
             lambda: [visual(plan), archivo(marca / "marca.yaml"), archivo(marca / "assets"), archivo(pedido / "analisis" / "voz.json"),
                      [archivo(c) for c in esperados], archivo(analisis) if analisis else None,
                      [archivo(m) for m in medios_de_la_composicion(pedido, plan)],
                      [archivo(a_medida), codigo("estilo.py", "comun.py")] if a_medida.exists()
                      else codigo("armar_pop.py", "estilo.py", "legibilidad.py", "caras.py", "comun.py")],
             [pedido / "render" / "index.html"],
             (lambda: a_medida_ok(a_medida)) if a_medida.exists() else lambda: uv("armar_pop.py", pedido)),
        Paso("render",
             lambda: [archivo(pedido / "render" / "index.html"), archivo(pedido / "render" / "assets"), HYPERFRAMES],
             [pedido / "salida" / "reel.mp4"],
             lambda: render_hyperframes(pedido, "../salida/reel.mp4")),
        Paso("audio",
             lambda: [archivo(pedido / "salida" / "reel.mp4"), modo, visual(plan).get("musica"), musica.get("fuente") if modo == "archivo" else None,
                      tomas, plan.get("sonidos"), archivo(pedido / "analisis" / "voz.json"),
                      archivo(analisis) if analisis else None,
                      archivo(musica.get("fuente")) if modo == "archivo" else None, codigo("audio.py")],
             [final], lambda: uv("audio.py", pedido)),
        Paso("portada",
             lambda: [archivo(pedido / "salida" / "reel.mp4"), (plan.get("publicar") or {}).get("portada")],
             [pedido / "salida" / "portada.jpg"], portada, a_mano=True),
        Paso("verificar",
             lambda: [archivo(pedido / "salida" / "reel.mp4"), archivo(pedido / "render" / "index.html"), visual(plan),
                      codigo("verificar.py", "legibilidad.py", "caras.py"), a.sin_check],
             [pedido / "salida" / "reel-qa.jpg"],
             lambda: uv("verificar.py", pedido / "salida" / "reel.mp4", "--pedido", pedido,
                        *(["--sin-check"] if a.sin_check else []))),
    ]
    return pasos, "reel", [final]


# ---------------------------------------------------------------- historia y foto

def pasos_historia(pedido, plan, a):
    medio = pedido / plan["medio"]["archivo"]
    marca = RAIZ / "marcas" / plan["marca"]
    salida = pedido / "salida"
    return [
        Paso("historia",
             lambda: [visual(plan), archivo(medio), archivo(marca / "marca.yaml"), archivo(marca / "assets"),
                      codigo("armar_historia.py", "estilo.py", "legibilidad.py", "preparar_clips.py", "comun.py", "render.py")],
             [salida / "historia.mp4", salida / "historia.jpg"], lambda: uv("armar_historia.py", pedido)),
        Paso("verificar",
             lambda: [archivo(salida / "historia.mp4"), archivo(pedido / "render" / "index.html"),
                      codigo("verificar.py", "legibilidad.py"), a.sin_check],
             [salida / "historia-qa.jpg"],
             lambda: uv("verificar.py", salida / "historia.mp4", "--formato", "historia", "--pedido", pedido,
                        *(["--sin-check"] if a.sin_check else []))),
    ], "historia", [salida / "historia.mp4"]


def pasos_foto(pedido, plan, a):
    marca = RAIZ / "marcas" / plan["marca"]
    salida = pedido / "salida"
    placas = [salida / f"placa-{k:02d}.jpg" for k in range(1, len(plan["placas"]) + 1)]
    fotos = [archivo(pedido / p["foto"]) for p in plan["placas"] if p.get("foto")]
    return [
        Paso("placas",
             lambda: [visual(plan), fotos, archivo(marca / "marca.yaml"), archivo(marca / "assets"),
                      codigo("armar_foto.py", "estilo.py", "comun.py", "render.py")],
             placas, lambda: uv("armar_foto.py", pedido)),
        Paso("verificar", lambda: [[archivo(p) for p in placas], codigo("verificar.py")], [],
             lambda: all([uv("verificar.py", p, "--formato", "foto") for p in placas])),
    ], plan.get("formato", "foto"), placas


# ---------------------------------------------------------------- mensaje para quien publica (M-07)

def destinatario(plan):
    """(nombre, saludo, archivo) del mensaje: `mensaje:` de marca.yaml; sin él, Ana."""
    marca = RAIZ / "marcas" / plan["marca"] / "marca.yaml"
    m = ((yaml.safe_load(marca.read_text(encoding="utf-8")) or {}).get("mensaje") or {}) if marca.exists() else {}
    para = m.get("para", "Ana")
    slug = "".join(c for c in para.lower().replace(" ", "-") if c.isalnum() or c == "-")
    return para, m.get("saludo", "💞"), f"para-{slug}.txt"


def para_quien_publica(pedido, plan, formato, archivos):
    """Mensaje corto de WhatsApp, en lenguaje simple, para reenviarle tal cual."""
    pub = plan.get("publicar") or {}
    _, saludo, nombre_archivo = destinatario(plan)
    nombre = pub.get("nombre") or pedido.name.split("-", 5)[-1].replace("-", " ")
    caption = pedido / "salida" / "caption.txt"
    lineas, n = [], 0

    def paso(texto):
        nonlocal n
        n += 1
        lineas.append(f"{n}. {texto}")

    faltan = [x.name for x in archivos if not x.exists()]
    if faltan:  # p. ej. con --solo mensaje en un pedido al que le falta el paso de audio
        print(f"      no está {', '.join(faltan)}: correr la fábrica sin --solo")
        return False
    pieza = {"reel": "el reel", "historia": "la historia"}.get(formato, "el carrusel" if len(archivos) > 1 else "la foto")
    de = f"del {nombre[3:]}" if nombre.startswith("el ") else f"de {nombre}"
    lineas += [f"Te paso {pieza} {de}" + (f" {saludo}" if saludo else ""), ""]
    if pub.get("permisos"):
        paso("Antes de publicar, pedile el OK a " + " y a ".join(pub["permisos"]) + ".")
    for extra in pub.get("antes") or []:
        paso(extra)
    if formato == "reel":
        from audio import instruccion_instagram, musica_del_pedido
        modo, musica = musica_del_pedido(pedido, plan)
        paso(f"Subí el video {archivos[0].name} como reel.")
        archivo_voz = pedido / "analisis" / "voz.json"
        con_voz = archivo_voz.exists() and bool(json.loads(archivo_voz.read_text(encoding="utf-8")).get("tomas"))
        if modo == "instagram":
            paso(f"Música: {instruccion_instagram(musica, con_voz)}")
        else:
            paso("Ya tiene música: no le agregues otra." + (" Tiene voz y subtítulos: no le bajes el sonido." if con_voz else ""))
        if (pedido / "salida" / "portada.jpg").exists():
            paso("Portada: en «Editar portada» → «Agregar desde la galería», elegí la foto portada.jpg que te mando.")
    elif formato == "historia":
        paso(f"Subí {archivos[0].name} como historia.")
        if plan.get("espacio_sticker") not in (None, "no"):
            paso(f"En la parte de {plan['espacio_sticker']}, que quedó libre para eso, poné este sticker: "
                 f"{plan.get('sticker_sugerido', 'el que quieras')}.")
    elif len(archivos) > 1:
        paso(f"Subí las {len(archivos)} fotos juntas, en una sola publicación y en este orden: "
             + ", ".join(x.name for x in archivos) + ".")
    else:
        paso(f"Subí la foto {archivos[0].name}.")
    if pub.get("colaboradora"):
        paso(f"Antes de compartir, tocá «Etiquetar personas» → «Invitar colaborador» y poné a {pub['colaboradora']}: "
             "si acepta, aparece también en su perfil.")
    if caption.exists():
        paso("Copiá esta descripción:")
        lineas += ["", caption.read_text(encoding="utf-8").strip()]
    (pedido / "salida" / nombre_archivo).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return True


# ---------------------------------------------------------------- orquestación

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pedido")
    ap.add_argument("--solo", help="correr solo ese paso (p. ej. mensaje; `ana` es el nombre viejo)")
    ap.add_argument("--forzar", action="store_true", help="rehacer los pasos aunque no hayan cambiado")
    ap.add_argument("--sin-check", action="store_true", help="verificar sin hyperframes check (más rápido)")
    ap.add_argument("--borrador", action="store_true",
                    help="reel para revisar: clips y composición como siempre, render liviano (15 fps, draft) con audio "
                         "en salida/borrador.mp4, sin portada ni verificación. El final se hace una vez, ya aprobado")
    a = ap.parse_args()
    if a.solo == "ana":
        a.solo = "mensaje"
    pedido = Path(a.pedido)
    plan_dir = pedido / "plan"
    for archivo_plan, armar in (("guion.yaml", pasos_reel), ("historia.yaml", pasos_historia),
                                ("publicacion.yaml", pasos_foto)):
        if (plan_dir / archivo_plan).exists():
            plan = yaml.safe_load((plan_dir / archivo_plan).read_text(encoding="utf-8"))
            break
    else:
        raise SystemExit(f"{pedido}: no hay plan (guion.yaml, historia.yaml o publicacion.yaml). El plan lo escribe Claude.")
    pasos, formato, archivos = armar(pedido, plan, a)
    salida = pedido / "salida"
    salida.mkdir(exist_ok=True)

    para, _, nombre_mensaje = destinatario(plan)
    mensaje = salida / nombre_mensaje
    # lo que lleva criterio lo escribe Claude: si falta, se lista y el mensaje espera
    pendientes = []
    if formato != "historia" and not (salida / "caption.txt").exists():
        pendientes.append("caption.txt (conocimiento/11-descripciones.md)")
    if formato == "reel" and not (salida / "informe.md").exists():
        pendientes.append("informe.md (decisiones y cómo publicarlo)")
    if formato != "historia" and not (salida / "puntos.yaml").exists() and not (salida / "evaluacion.md").exists():
        pendientes.append("puntos.yaml con la rúbrica → puntaje.py → evaluacion.md")
    if "permisos" not in (plan.get("publicar") or {}):
        pendientes.append(f"publicar.permisos en el plan: ¿aparece alguien más? (lista vacía si solo aparece {para})")
    if (salida / "puntos.yaml").exists():
        pasos.append(Paso("puntaje", lambda: [archivo(salida / "puntos.yaml"), archivo(RAIZ / "conocimiento" / "rubrica.yaml"),
                                              codigo("puntaje.py")], [], lambda: uv("puntaje.py", pedido)))
    if not pendientes:
        pasos.append(Paso("mensaje", lambda: [plan, archivo(salida / "caption.txt"), [x.name for x in archivos],
                                              (salida / "portada.jpg").exists(), archivo(pedido / "pedido.yaml"),
                                              archivo(RAIZ / "marcas" / plan["marca"] / "marca.yaml"),
                                              codigo("fabrica.py", "audio.py")],
                          [mensaje], lambda: para_quien_publica(pedido, plan, formato, archivos)))
    print(f"{pedido.name} ({formato})")

    sello = pedido / "render" / ".fabrica.json"
    sello.parent.mkdir(parents=True, exist_ok=True)
    hechos = json.loads(sello.read_text(encoding="utf-8")) if sello.exists() else {}
    ok_todo, hizo = True, []
    if a.borrador and formato != "reel":
        raise SystemExit("--borrador es para reels (historias y fotos ya salen en segundos)")
    for p in pasos:
        if a.solo and p.nombre != a.solo:
            continue
        if a.borrador and p.nombre not in ("clips", "composicion"):
            continue
        faltan = [x for x in p.salidas if not Path(x).exists()]
        if not a.forzar and not faltan and p.a_mano and hechos.get(f"{p.nombre}:salidas") != [archivo(x) for x in p.salidas]:
            print(f"  · {p.nombre}: reemplazada a mano, no se pisa (borrarla o --forzar para rehacerla)")
            continue
        if not a.forzar and not faltan and hechos.get(p.nombre) == huella(p.nombre, p.entradas()):
            print(f"  · {p.nombre}: sin cambios")
            continue
        print(f"  → {p.nombre}")
        if not p.correr():
            print(f"  ✗ {p.nombre} falló: se corta acá")
            hechos.pop(p.nombre, None)
            sello.write_text(json.dumps(hechos, indent=1), encoding="utf-8")
            ok_todo = False
            break
        hizo.append(p.nombre)
        hechos[p.nombre] = huella(p.nombre, p.entradas())  # después de correr: lo generado ya tiene su fecha
        if p.a_mano:
            hechos[f"{p.nombre}:salidas"] = [archivo(x) for x in p.salidas]
        sello.write_text(json.dumps(hechos, indent=1), encoding="utf-8")

    if a.borrador:
        if ok_todo:
            borrador(pedido)
        return
    if ok_todo and mensaje.exists() and not pendientes:
        print(f"\nPara {para}: reenviale salida/{mensaje.name} y mandale {', '.join(x.name for x in archivos)}"
              + (" y portada.jpg" if formato == "reel" and (salida / "portada.jpg").exists() else "")
              + " como Documento (📎 → Documento), así WhatsApp no los comprime.")
    if pendientes:
        print(f"\nPendiente (Claude), y hasta entonces no hay mensaje para {para}:\n" + "\n".join(f"  - {x}" for x in pendientes))
    if not hizo and ok_todo:
        print("\nNada que rehacer.")
    sys.exit(0 if ok_todo else 1)


if __name__ == "__main__":
    main()
