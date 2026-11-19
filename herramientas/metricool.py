"""Carga en los pedidos las métricas de un volcado de Metricool (M-22): sin capturas.

Uso:
    uv run python herramientas/metricool.py --campos [reels|posts|stories]
    uv run python herramientas/metricool.py marcas/<marca>/metricool/<volcado>.json [--marca salon-demo] [--probar]

El MCP de Metricool lo llama Claude, no este script: pide `getAnalyticsDataByMetrics` con los
campos que lista `--campos` y guarda la respuesta tal cual en
    marcas/<marca>/metricool/<AAAA-MM-DD>-<tipo>.json
    = {"consultado": ISO, "tipo": "reels", "campos": [los fieldId pedidos, en orden], "filas": <respuesta>}
Los volcados se versionan: Metricool da el acumulado del momento, así que la foto de las 72 h
no se puede volver a pedir después. Los reels que no son de ningún pedido también quedan
ahí (sirven para la mediana de la cuenta, M-19).

Este script, con cada fila del volcado:
  - la une a su pedido: por el link si `salida/metricas.md` ya lo tiene; si no, por la
    descripción (`salida/caption.txt`), publicada el día del pedido o después. Las historias
    no tienen descripción: solo por link;
  - pasa los nombres y las unidades de Metricool a los de la plantilla (ms → s, fracción → %,
    salteo = 100 − % que pasó los 3 s);
  - escribe o actualiza la medición en `salida/metricas.md`. La etiqueta `a` es la edad real
    (72h y 7d solo si cae cerca; si no, p. ej. 10d). Lo que Metricool no trae (no seguidores,
    pozo, conversaciones) no se pisa: puede venir de una captura.
Después, `metricas.py` regenera la tabla de la marca.
Solo lectura: Metricool nunca se usa para publicar (ver `.claude/settings.json › permissions.deny`).
"""

import argparse
import difflib
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from comun import RAIZ  # noqa: E402

# Campos que se piden por tipo (fieldId de getAnalyticsAvailableMetrics) → nombre en metricas.md.
# Los de fecha, texto y link son para unir la fila con su pedido.
CAMPOS = {
    "reels": {
        "IGRE02": "fecha_hora", "IGRE03": "texto", "IGRE06": "link",
        "IGRE23": "visualizaciones", "IGRE11": "alcance", "IGRE28": "vistas_3s_pct",
        "IGRE24": "tiempo_medio", "IGRE27": "retencion_pct", "IGRE26": "duracion_s",
        "IGRE10": "me_gusta", "IGRE07": "comentarios", "IGRE21": "envios", "IGRE12": "guardados",
    },
    "posts": {
        "IGPO02": "fecha_hora", "IGPO03": "texto", "IGPO06": "link", "IGPO07": "tipo",
        "IGPO28": "visualizaciones", "IGPO14": "alcance",
        "IGPO13": "me_gusta", "IGPO08": "comentarios", "IGPO27": "envios", "IGPO15": "guardados",
        "IGPO29": "seguidores_ganados",
    },
    "stories": {
        "IGST02": "fecha_hora", "IGST06": "link", "IGST07": "tipo",
        "IGST09": "visualizaciones", "IGST10": "alcance", "IGST08": "salidas",
        "IGST13": "toques_adelante", "IGST12": "toques_atras", "IGST11": "respuestas",
    },
}
# metricName de Metricool, por si la respuesta viene con esos nombres y no con el fieldId
NOMBRES = {
    "timestamp": "fecha_hora", "content": "texto", "url": "link", "permalink": "link", "type": "tipo",
    "views": "visualizaciones", "reach": "alcance", "reelsViewRate": "vistas_3s_pct",
    "averageWatchTime": "tiempo_medio", "retention": "retencion_pct", "durationSeconds": "duracion_s",
    "likes": "me_gusta", "comments": "comentarios", "shares": "envios", "saved": "guardados",
    "follows": "seguidores_ganados", "impressions": "visualizaciones", "exits": "salidas",
    "tapsForward": "toques_adelante", "tapsBack": "toques_atras", "replies": "respuestas",
}
# con qué plan se hace cada tipo de publicación
PLAN = {"reels": "guion.yaml", "posts": "publicacion.yaml", "stories": "historia.yaml"}
ZONA_MARCA = timezone(timedelta(hours=-3))   # America/Buenos_Aires, sin horario de verano
PARECIDO_MINIMO = 0.6       # descripción del pedido contra la publicada (Ana puede retocarla)
METRICAS = ("visualizaciones", "alcance", "salteo_pct", "tiempo_medio_s", "retencion_pct", "me_gusta",
            "comentarios", "envios", "guardados", "seguidores_ganados", "salidas", "toques_adelante",
            "toques_atras", "respuestas")


# ---------------------------------------------------------------- lectura del volcado

def _clave(k):
    """'IGRE23', 'views' o 'Instagram Reels > Views' → nombre de la plantilla (o None)."""
    k = str(k).strip()
    for campos in CAMPOS.values():
        if k.upper() in campos:
            return campos[k.upper()]
    k = k.split(">")[-1].strip()
    for nombre, destino in NOMBRES.items():
        if k.lower() == nombre.lower():
            return destino
    return None


def filas_crudas(datos, campos=None):
    """Las filas de la respuesta, venga como lista de objetos, envuelta, o en columnas.
    Filas que son listas sin encabezado: en el orden de `campos` (los fieldId pedidos)."""
    if isinstance(datos, dict):
        if "filas" in datos:
            return filas_crudas(datos["filas"], datos.get("campos") or campos)
        cols = datos.get("headers") or datos.get("columns")
        if cols and isinstance(datos.get("rows"), list):
            cols = [c.get("fieldId") or c.get("metricName") or c.get("name") if isinstance(c, dict) else c for c in cols]
            return [dict(zip(cols, r)) for r in datos["rows"]]
        for k in ("data", "rows", "values", "result", "results", "items"):
            if isinstance(datos.get(k), list):
                return filas_crudas(datos[k], campos)
        return [datos]
    return [f if isinstance(f, dict) else dict(zip(campos or [], f))
            for f in datos or [] if isinstance(f, dict) or (campos and isinstance(f, list))]


def _numero(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None


def _pct(v):
    """Metricool puede dar 0,72 o 72: siempre a %."""
    v = _numero(v)
    if v is None:
        return None
    return round(v * 100 if 0 < v <= 1 else v, 1)


def _segundos(v):
    """Tiempo medio de visualización: la API de Instagram lo da en ms; si viene en s, se deja."""
    v = _numero(v)
    if v is None:
        return None
    return round(v / 1000 if v > 600 else v, 1)      # 600 s de promedio en un reel no existe; 600 ms tampoco


def _fecha(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
    if isinstance(v, dict):
        return _fecha(v.get("dateTime") or v.get("date"))
    s = str(v).strip().replace("Z", "+00:00")
    try:
        f = datetime.fromisoformat(s)                  # incluye 20260915, como llega de Metricool
    except ValueError:
        for formato in ("%Y%m%d %H%M%S", "%Y%m%d %H:%M:%S", "%Y%m%d%H%M%S", "%d/%m/%Y %H:%M"):
            try:
                f = datetime.strptime(s, formato)
                break
            except ValueError:
                continue
        else:
            return None
    # sin zona: Metricool usa la de la marca (getBrandSettings › timezone)
    return f if f.tzinfo else f.replace(tzinfo=ZONA_MARCA)


def normalizar(cruda):
    """Una fila de Metricool → dict con los nombres y unidades de metricas.md."""
    f = {}
    for k, v in cruda.items():
        destino = _clave(k)
        if destino and f.get(destino) is None:
            f[destino] = v
    out = {"link": f.get("link"), "texto": f.get("texto") or "", "fecha_hora": _fecha(f.get("fecha_hora")),
           "tipo": f.get("tipo")}
    for k in ("visualizaciones", "alcance", "me_gusta", "comentarios", "envios", "guardados",
              "seguidores_ganados", "salidas", "toques_adelante", "toques_atras", "respuestas", "duracion_s"):
        n = _numero(f.get(k))
        out[k] = int(n) if n is not None and float(n).is_integer() else n
    out["tiempo_medio_s"] = _segundos(f.get("tiempo_medio"))
    out["retencion_pct"] = _pct(f.get("retencion_pct"))
    vistas_3s = _pct(f.get("vistas_3s_pct"))
    out["salteo_pct"] = round(100 - vistas_3s, 1) if vistas_3s is not None else None
    return out


def leer_volcado(archivo):
    """(tipo, cuándo se consultó, filas normalizadas)."""
    datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
    tipo = datos.get("tipo") if isinstance(datos, dict) else None
    if tipo not in CAMPOS:
        tipo = next((t for t in CAMPOS if t in Path(archivo).stem), "reels")
    consultado = _fecha(datos.get("consultado")) if isinstance(datos, dict) else None
    if consultado is None:
        consultado = datetime.fromtimestamp(Path(archivo).stat().st_mtime, tz=timezone.utc)
    return tipo, consultado, [normalizar(c) for c in filas_crudas(datos, list(CAMPOS[tipo]))]


# ---------------------------------------------------------------- unir con los pedidos

def codigo(link):
    """El shortcode de una URL de Instagram (…/reel/DdkhxC5S3mP/ → DdkhxC5S3mP)."""
    m = re.search(r"/(?:reel|reels|p|tv|stories/[^/]+)/([A-Za-z0-9_-]+)", str(link or ""))
    return m.group(1) if m else (str(link).strip("/") if link else None)


def _limpio(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[#@]\S+", " ", t)                 # hashtags y menciones se retocan seguido
    return re.sub(r"[^\w]+", " ", t).strip()[:400]


def parecido(a, b):
    a, b = _limpio(a), _limpio(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def edad(publicado, consultado):
    """'72h' / '7d' si cae cerca; si no, la edad real ('30h', '10d')."""
    h = (consultado - publicado).total_seconds() / 3600
    if 60 <= h < 120:
        return "72h"
    if 144 <= h < 216:
        return "7d"
    return f"{round(h)}h" if h < 48 else f"{round(h / 24)}d"


def pedidos_de(marca, tipo, raiz_pedidos):
    for p in sorted(Path(raiz_pedidos).glob(f"*-{marca}-*")):
        if (p / "plan" / PLAN[tipo]).exists():
            yield p


def leer_md(archivo):
    texto = archivo.read_text(encoding="utf-8")
    partes = texto.split("---", 2)
    if len(partes) < 3:
        raise ValueError(f"{archivo}: falta el bloque YAML entre ---")
    return (yaml.safe_load(partes[1]) or {}), partes[2]


def unir(filas, pedidos):
    """[(pedido, fila, cómo)]: por link y, si no hay, por la descripción más parecida."""
    usadas, pares = set(), []
    pendientes = []
    for p in pedidos:
        md = p / "salida" / "metricas.md"
        link = leer_md(md)[0].get("link") if md.exists() else None
        if link:
            f = next((f for f in filas if codigo(f["link"]) == codigo(link)), None)
            if f:
                usadas.add(id(f))
                pares.append((p, f, "link"))
            continue
        pendientes.append(p)
    for p in pendientes:
        cap = p / "salida" / "caption.txt"
        if not cap.exists():
            continue
        desde = datetime.strptime(p.name[:10], "%Y-%m-%d").date()
        # un reel que el plan cita es material (p. ej. el original de una reversión), no el resultado
        plan = " ".join(f.read_text(encoding="utf-8") for f in (p / "plan").glob("*.yaml"))
        candidatas = [(parecido(cap.read_text(encoding="utf-8"), f["texto"]), f) for f in filas
                      if id(f) not in usadas and f["texto"] and (f["fecha_hora"] is None or f["fecha_hora"].date() >= desde)
                      and not (codigo(f["link"]) and codigo(f["link"]) in plan)]
        if not candidatas:
            continue
        r, f = max(candidatas, key=lambda x: x[0])
        if r >= PARECIDO_MINIMO:
            usadas.add(id(f))
            pares.append((p, f, f"descripción {r:.2f}"))
    return pares, [f for f in filas if id(f) not in usadas]


# ---------------------------------------------------------------- escribir

def medicion(fila, consultado):
    m = {"a": edad(fila["fecha_hora"], consultado) if fila["fecha_hora"] else None,
         "fecha": consultado.date().isoformat(), "fuente": "metricool"}
    m.update({k: fila.get(k) for k in METRICAS if fila.get(k) is not None})
    return m


def cargar(pedido, fila, consultado, plantilla=None):
    """Escribe la medición en salida/metricas.md (la crea desde la plantilla si falta)."""
    md = pedido / "salida" / "metricas.md"
    if md.exists():
        datos, cuerpo = leer_md(md)
    else:
        datos, cuerpo = leer_md(plantilla or RAIZ / "pedidos" / "_plantilla" / "metricas.md")
        datos["mediciones"] = []
    if fila["fecha_hora"] and not datos.get("publicado"):
        datos["publicado"] = fila["fecha_hora"].date().isoformat()
    datos["link"] = datos.get("link") or fila["link"]
    nueva = medicion(fila, consultado)
    meds = [m for m in datos.get("mediciones") or [] if any(v not in (None, "") for k, v in m.items() if k != "a")]
    previa = next((m for m in meds if m.get("a") == nueva["a"]), None)
    if previa:
        # lo de Metricool manda; lo que solo da la captura (pozo, no seguidores) se conserva
        previa.update({k: v for k, v in nueva.items() if v is not None})
    else:
        meds.append(nueva)
    datos["mediciones"] = sorted(meds, key=lambda m: str(m.get("fecha") or ""))
    encabezado = ("# Métricas de esta publicación. Las de `fuente: metricool` las escribe herramientas/metricool.py;\n"
                  "# las demás, Claude desde una captura. Plantilla y significado de cada campo: pedidos/_plantilla/metricas.md.\n")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\n" + encabezado + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False)
                  + "---" + cuerpo, encoding="utf-8")
    return nueva


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("volcado", nargs="?")
    ap.add_argument("--campos", nargs="?", const="reels", choices=list(CAMPOS),
                    help="lista los fieldId que hay que pedirle al MCP para ese tipo")
    ap.add_argument("--marca", default="salon-demo")
    ap.add_argument("--pedidos", default=str(RAIZ / "pedidos"))
    ap.add_argument("--probar", action="store_true", help="muestra qué uniría, sin escribir")
    a = ap.parse_args()
    if a.campos:
        print(json.dumps(list(CAMPOS[a.campos]), ensure_ascii=False))
        return
    if not a.volcado:
        ap.error("falta el volcado (o --campos)")
    tipo, consultado, filas = leer_volcado(a.volcado)
    print(f"{len(filas)} {tipo} en el volcado, consultado {consultado:%Y-%m-%d %H:%M %z}")
    pares, sueltas = unir(filas, pedidos_de(a.marca, tipo, a.pedidos))
    for pedido, fila, como in pares:
        m = medicion(fila, consultado) if a.probar else cargar(pedido, fila, consultado)
        datos = ", ".join(f"{k} {m[k]}" for k in ("visualizaciones", "alcance", "salteo_pct", "tiempo_medio_s") if k in m)
        print(f"  {pedido.name} ← {codigo(fila['link'])} ({como}) · {m['a']} · {datos}")
    if sueltas:
        print(f"{len(sueltas)} sin pedido (quedan en el volcado, para la mediana de la cuenta):")
        for f in sorted(sueltas, key=lambda f: str(f["fecha_hora"]))[-10:]:
            print(f"  {f['fecha_hora']:%Y-%m-%d} {codigo(f['link'])} · {f['texto'][:50]!r}" if f["fecha_hora"]
                  else f"  {codigo(f['link'])} · {f['texto'][:50]!r}")
    if pares and not a.probar:
        print("Siguiente: uv run python herramientas/metricas.py --marca", a.marca)


if __name__ == "__main__":
    main()
