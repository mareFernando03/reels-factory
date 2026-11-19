"""Tabla comparativa de las publicaciones de una marca: métricas + cómo estaba hecho cada reel.

Uso:
    uv run python herramientas/metricas.py [--marca salon-demo] [--pedidos pedidos]

Lee pedidos/*/salida/metricas.md (los escribe metricool.py o Claude desde una captura;
plantilla en pedidos/_plantilla/metricas.md), le suma
del plan el formato, el ritmo y la duración, y escribe marcas/<marca>/metricas.md:
una tabla por formato (un proceso no se compara con un resultado) con la última
medición de cada publicación, más los cocientes que importan (conocimiento/06-medicion.md):
    retención = tiempo medio / duración del reel       (objetivo ≥ 50 %; si no hay tiempo medio, la de Instagram)
    salteo                                            (objetivo < 30 %)
    envíos / alcance, me gusta / alcance               (comparar entre publicaciones)
Sin criterio editorial: la lectura la hace Claude con la tabla delante.
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from comun import RAIZ, duraciones  # noqa: E402


def leer_metricas(archivo):
    """El bloque YAML entre los dos primeros `---` de metricas.md."""
    texto = archivo.read_text(encoding="utf-8")
    partes = texto.split("---", 2)
    if len(partes) < 3:
        raise ValueError(f"{archivo}: falta el bloque YAML entre ---")
    return yaml.safe_load(partes[1]) or {}


def ficha(pedido):
    """Cómo estaba hecho: formato, bpm, duración y toma media, del plan del pedido."""
    plan_dir = pedido / "plan"
    if (plan_dir / "guion.yaml").exists():
        g = yaml.safe_load((plan_dir / "guion.yaml").read_text(encoding="utf-8"))
        tomas = g.get("tomas") or g.get("escenas") or []
        todas = duraciones(g, pedido)
        durs = [d for t, d in zip(tomas, todas) if not t.get("cierre")]
        # la retención se mide contra lo que dura el video entero, cierre incluido
        return {"formato": g.get("formato"), "bpm": g.get("bpm"), "estilo": g.get("estilo"),
                "duracion": round(sum(todas), 1), "toma_media": round(sum(durs) / len(durs), 2) if durs else None,
                "tomas": len(durs)}
    for nombre, formato in (("historia.yaml", "historia"), ("publicacion.yaml", None)):
        if (plan_dir / nombre).exists():
            p = yaml.safe_load((plan_dir / nombre).read_text(encoding="utf-8"))
            return {"formato": formato or p.get("formato", "foto"), "estilo": p.get("plantilla")}
    return {"formato": "?"}


def pct(a, b):
    try:
        return round(100 * float(a) / float(b), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def fila(pedido, m, f, marca):
    med = sorted(m.get("mediciones") or [], key=lambda x: str(x.get("fecha") or ""))
    ult = med[-1] if med else {}
    return {
        "pedido": pedido.name[11:].removeprefix(f"{marca}-"),   # sin la fecha ni la marca
        "publicado": m.get("publicado") or "", "a": ult.get("a") or "",
        "vis": ult.get("visualizaciones"), "alcance": ult.get("alcance"), "salteo": ult.get("salteo_pct"),
        # la de Instagram (% medio visto, viene de Metricool) solo si no hay tiempo medio
        "t_medio": ult.get("tiempo_medio_s"),
        "retencion": pct(ult.get("tiempo_medio_s"), f.get("duracion")) or ult.get("retencion_pct"),
        "envios_alc": pct(ult.get("envios"), ult.get("alcance")), "mg_alc": pct(ult.get("me_gusta"), ult.get("alcance")),
        "guardados": ult.get("guardados"), "no_seg": ult.get("no_seguidores_pct"), "pozo": ult.get("pozo_s"), **f,
    }


def celda(v, sufijo=""):
    return "—" if v is None or v == "" else f"{v}{sufijo}"


def tabla(filas):
    cab = ("| Publicación | Publicado | Medición | bpm | Dur. (s) | Toma media (s) | Vistas | Alcance | Salteo | "
           "Tiempo medio | Retención | Envíos/alc. | MG/alc. | Guardados | No seguidores | Pozo |")
    out = [cab, "|" + "---|" * (cab.count("|") - 1)]
    for r in sorted(filas, key=lambda x: str(x["publicado"])):
        aviso_s = " ⚠" if isinstance(r["salteo"], (int, float)) and r["salteo"] >= 30 else ""
        aviso_r = " ⚠" if isinstance(r["retencion"], (int, float)) and r["retencion"] < 50 else ""
        out.append(f"| {r['pedido']} | {r['publicado']} | {r['a']} | {celda(r.get('bpm'))} | {celda(r.get('duracion'))} | "
                   f"{celda(r.get('toma_media'))} | {celda(r['vis'])} | {celda(r['alcance'])} | {celda(r['salteo'], ' %')}{aviso_s} | "
                   f"{celda(r['t_medio'], ' s')} | {celda(r['retencion'], ' %')}{aviso_r} | {celda(r['envios_alc'], ' %')} | "
                   f"{celda(r['mg_alc'], ' %')} | {celda(r['guardados'])} | {celda(r['no_seg'], ' %')} | {celda(r['pozo'], ' s')} |")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--marca", default="salon-demo")
    ap.add_argument("--pedidos", default=str(RAIZ / "pedidos"))
    ap.add_argument("--salida", help="default: marcas/<marca>/metricas.md")
    a = ap.parse_args()
    filas = []
    for archivo in sorted(Path(a.pedidos).glob("*/salida/metricas.md")):
        pedido = archivo.parent.parent
        if a.marca not in pedido.name:
            continue
        filas.append(fila(pedido, leer_metricas(archivo), ficha(pedido), a.marca))
    lineas = [f"# Métricas de {a.marca}", "",
              "Generado por `herramientas/metricas.py` desde `pedidos/*/salida/metricas.md`: no editar a mano.",
              "Última medición de cada publicación. ⚠ = fuera del objetivo de `conocimiento/06-medicion.md`",
              "(salteo < 30 %, retención ≥ 50 % de la duración). Se compara dentro de cada formato.", ""]
    if not filas:
        lineas.append("Todavía no hay métricas cargadas.")
    for formato in sorted({r["formato"] or "?" for r in filas}):
        grupo = [r for r in filas if (r["formato"] or "?") == formato]
        lineas += [f"## {formato} ({len(grupo)})", ""] + tabla(grupo) + [""]
    destino = Path(a.salida) if a.salida else RAIZ / "marcas" / a.marca / "metricas.md"
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"{len(filas)} publicaciones con métricas → {destino}")


if __name__ == "__main__":
    main()
