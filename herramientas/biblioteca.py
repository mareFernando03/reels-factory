"""Cataloga la biblioteca de una marca: los reels que ya publicó.

Uso:
    uv run python herramientas/biblioteca.py marcas/<marca>/biblioteca            # catalogar lo nuevo
    uv run python herramientas/biblioteca.py marcas/<marca>/biblioteca --calidad  # resolución y movimiento
    uv run python herramientas/biblioteca.py marcas/<marca>/biblioteca --habla    # qué se dice y cuándo
    uv run python herramientas/biblioteca.py marcas/<marca>/biblioteca --buscar "rulos 1080p"

Lee reels/*.mp4 (+ indice.tsv de yt-dlp) y escribe catalogo.json y
hojas/<id>.jpg. Por reel: duración, tomas, y si cada toma es FOTO fija o VIDEO
real (diferencia entre dos cuadros de la toma). Qué sirve para un reel nuevo lo
decide Claude mirando las hojas, y lo escribe en lecturas.yaml (aparte del catálogo,
así volver a catalogar no lo borra): servicio, quién aparece, si está Ana, los mejores
tramos con segundos, notas (texto quemado, marca de agua, lo filmó otra cuenta) y etiquetas.

--calidad agrega a cada reel la resolución y cuánto es estable (movimiento.py, con caché)
y rehace las hojas de los reels de más de 18 tomas, repartiendo las 18 a lo largo del reel.
--habla transcribe los reels donde alguien habla (voz.py: descarta las canciones) y guarda las
frases con sus tiempos en el catálogo (`habla`): lo que dice Ana es material, porque sirve como
gancho o título con sus palabras (M2) y como toma con voz.
--buscar puntúa cada reel por las palabras de la consulta en su lectura, su texto y su
calidad ("1080p", "720p", "estable", "video", "fotos", "ana") y lista los tramos útiles.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import fotograma, hoja_de_contactos, probar  # noqa: E402
from analizar_referencia import detectar_tomas  # noqa: E402

UMBRAL_MOVIMIENTO = 4.0  # diferencia media de píxel (0-255) entre dos cuadros de la toma


def movimiento(video, a, b, tmp):
    import cv2
    import numpy as np
    if b - a < 0.4:
        return None
    f1 = fotograma(video, a + (b - a) * 0.25, tmp / "m1.jpg", ancho=160)
    f2 = fotograma(video, a + (b - a) * 0.75, tmp / "m2.jpg", ancho=160)
    i1, i2 = cv2.imread(str(f1), 0), cv2.imread(str(f2), 0)
    return round(float(np.abs(i1.astype(int) - i2.astype(int)).mean()), 2)


def leer_indice(path):
    idx = {}
    if path.exists():
        for linea in path.read_text(encoding="utf-8").splitlines():
            p = linea.split("\t")
            if len(p) >= 7:
                desc = json.loads(p[6]) if p[6] not in ("NA", "") else ""
                num = lambda x: None if x in ("NA", "") else float(x)
                idx[p[0]] = {"fecha": p[1], "likes": num(p[3]), "comentarios": num(p[4]),
                             "vistas": num(p[5]), "texto": desc}
    return idx


def elegir_tomas(detalle, n=18):
    """Hasta n tomas repartidas a lo largo del reel (no solo las primeras)."""
    if len(detalle) <= n:
        return detalle
    return [detalle[round(i * (len(detalle) - 1) / (n - 1))] for i in range(n)]


def calidad(bib, catalogo):
    """Resolución y movimiento por reel; rehace las hojas de los reels largos."""
    from movimiento import movimiento_de
    tmp = bib / ".tmp"
    tmp.mkdir(exist_ok=True)
    for rid, c in sorted(catalogo.items()):
        video = bib / "reels" / f"{rid}.mp4"
        if not video.exists():
            continue
        m = movimiento_de(video)
        lado = min(c.get("ancho") or 0, c.get("alto") or 0)
        c["calidad"] = {"resolucion": f"{lado}p", "baja": lado < 720,
                        "estable": m.get("resumen", {}).get("proporcion_estable"),
                        "temblor": m.get("resumen", {}).get("temblor_medio")}
        if len(c.get("detalle") or []) > 18:
            fotos, etiquetas = [], []
            for t in elegir_tomas(c["detalle"]):
                try:
                    fotos.append(fotograma(video, t["inicio"] + t["dur"] / 2, tmp / f"h{t['n']:03d}.jpg", ancho=200))
                    etiquetas.append(f"{t['n']} {t['inicio']:.1f}s {'V' if t['clase'] == 'video' else 'F'}")
                except Exception:
                    pass
            hoja_de_contactos(fotos, bib / "hojas" / f"{rid}.jpg", etiquetas, columnas=6)
        est = c["calidad"]["estable"]
        print(f"{rid}: {c['calidad']['resolucion']}, " + (f"{est:.0%} estable" if est is not None else "sin medición de movimiento")
              + (f", hoja rehecha ({len(c['detalle'])} tomas)" if len(c.get("detalle") or []) > 18 else ""))
        (bib / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()


def habla(bib, catalogo):
    """Frases dichas en cada reel (solo habla en castellano, no letras de canciones)."""
    from voz import detectar
    for rid, c in sorted(catalogo.items()):
        video = bib / "reels" / f"{rid}.mp4"
        if not video.exists() or not c.get("audio") or c.get("habla") is not None:
            continue
        d = detectar(video, 0, c["duracion"])
        frases, actual = [], []
        for w in d["palabras"]:  # frases: se corta en pausas de más de 0,6 s
            if actual and w["ini"] - actual[-1]["fin"] > 0.6:
                frases.append(actual)
                actual = []
            actual.append(w)
        if actual:
            frases.append(actual)
        c["habla"] = [{"desde": f[0]["ini"], "hasta": f[-1]["fin"], "texto": " ".join(x["w"] for x in f)} for f in frases]
        print(f"{rid}: " + (f"{len(c['habla'])} frases · «{d['texto'][:70]}»" if c["habla"] else f"sin habla ({d['idioma']})"))
        (bib / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")


def buscar(bib, catalogo, consulta):
    """Reels ordenados por cuántas palabras de la consulta aparecen en su lectura, texto y calidad."""
    import unicodedata

    import yaml

    def norm(x):
        return "".join(ch for ch in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(ch) != "Mn")

    lecturas = yaml.safe_load((bib / "lecturas.yaml").read_text(encoding="utf-8")) if (bib / "lecturas.yaml").exists() else {}
    palabras = norm(consulta).split()
    resultados = []
    for rid, c in catalogo.items():
        lec = (lecturas or {}).get(rid) or {}
        cal = c.get("calidad") or {}
        campos = [lec.get("servicio"), lec.get("notas"), " ".join(lec.get("etiquetas") or []),
                  " ".join(lec.get("personas") or []), c.get("texto"), c.get("tipo"), cal.get("resolucion"),
                  "ana" if lec.get("aparece_duena") else "", "estable" if (cal.get("estable") or 0) >= 0.6 else "",
                  " ".join(t.get("que", "") for t in lec.get("tramos") or []),
                  " ".join(f["texto"] for f in c.get("habla") or []) if lec.get("voz", "ana") == "ana" else "",
                  " ".join(lec.get("frases") or []), "habla" if lec.get("voz") == "ana" else ""]
        bolsa = norm(" ".join(str(x) for x in campos if x))
        puntos = sum(1 for w in palabras if w in bolsa)
        # "1080p" también acepta más resolución; "720p" acepta 720 o más
        for w in palabras:
            if w.endswith("p") and w[:-1].isdigit() and cal.get("resolucion"):
                puntos += int(cal["resolucion"][:-1]) >= int(w[:-1]) and w not in bolsa
        if puntos:
            resultados.append((puntos, rid, c, lec))
    resultados.sort(key=lambda x: (-x[0], -(int((x[2].get("calidad") or {}).get("resolucion", "0p")[:-1] or 0))))
    for puntos, rid, c, lec in resultados[:12]:
        cal = c.get("calidad") or {}
        print(f"{rid} [{puntos}/{len(palabras)}] {c.get('fecha')} {cal.get('resolucion', '?')} {c['tipo']} "
              f"{c['duracion']:.0f}s · {lec.get('servicio') or (c.get('texto') or '')[:50]!r}")
        for t in lec.get("tramos") or []:
            print(f"    {t['desde']:6.1f}-{t['hasta']:6.1f}s  {t['que']}")
        for f in (c.get("habla") or []) if lec.get("voz", "ana") == "ana" else []:  # lo que dice ella
            if any(w in norm(f["texto"]) for w in palabras):
                print(f"    {f['desde']:6.1f}-{f['hasta']:6.1f}s  dice: «{f['texto']}»")
    if not resultados:
        print("Nada. Probar con otras palabras (servicio, persona, '1080p', 'ana', 'video').")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("biblioteca")
    ap.add_argument("--calidad", action="store_true")
    ap.add_argument("--buscar", metavar="CONSULTA")
    ap.add_argument("--habla", action="store_true")
    a = ap.parse_args()
    bib = Path(a.biblioteca)
    if a.calidad or a.buscar or a.habla:
        catalogo = json.loads((bib / "catalogo.json").read_text(encoding="utf-8"))
        if a.habla:
            return habla(bib, catalogo)
        return calidad(bib, catalogo) if a.calidad else buscar(bib, catalogo, a.buscar)
    hojas, tmp = bib / "hojas", bib / ".tmp"
    hojas.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    indice = leer_indice(bib / "indice.tsv")
    destino = bib / "catalogo.json"
    catalogo = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}

    for video in sorted((bib / "reels").glob("*.mp4")):
        rid = video.stem
        if "." in rid:  # parcial de yt-dlp (id.fdash-….mp4) todavía sin unir
            continue
        meta = probar(video)
        previo = catalogo.get(rid)
        # incremental: lo ya catalogado no se rehace, salvo que el archivo haya cambiado
        # (p. ej. bajar.py --forzar trajo una versión de más resolución)
        if previo and previo.get("ancho") == meta["ancho"]:
            continue
        if previo and previo.get("ancho") is None:
            previo.update(ancho=meta["ancho"], alto=meta["alto"])
            destino.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
            continue
        tomas = detectar_tomas(video)
        detalle, fotos, etiquetas = [], [], []
        for i, (ini, fin) in enumerate(tomas):
            try:
                mov = movimiento(video, ini, fin, tmp)
            except Exception:  # cuadro ilegible al final del archivo
                mov = None
            clase = "video" if (mov is None or mov >= UMBRAL_MOVIMIENTO) else "foto"
            detalle.append({"n": i, "inicio": ini, "fin": fin, "dur": round(fin - ini, 2),
                            "clase": clase, "movimiento": mov})
            if i < 18:
                try:
                    fotos.append(fotograma(video, ini + (fin - ini) / 2, tmp / f"h{i:02d}.jpg", ancho=200))
                    etiquetas.append(f"{i} {ini:.1f}s {'V' if clase == 'video' else 'F'}")
                except Exception:  # el último cuadro a veces no se puede leer: se saltea
                    pass
        hoja_de_contactos(fotos, hojas / f"{rid}.jpg", etiquetas, columnas=6)
        seg_video = sum(t["dur"] for t in detalle if t["clase"] == "video")
        catalogo[rid] = {
            **indice.get(rid, {}), "duracion": meta["duracion"], "fps": meta["fps"],
            "ancho": meta["ancho"], "alto": meta["alto"],
            "audio": meta["audio"], "tomas": len(detalle),
            "segundos_de_video": round(seg_video, 1),
            "tipo": "video" if seg_video >= 0.5 * meta["duracion"] else "fotos",
            "detalle": detalle, "lectura": None,
        }
        destino.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
        c = catalogo[rid]
        print(f"{rid}: {c['duracion']:5.1f}s {c['ancho']}x{c['alto']} {c['tipo']:6s} {c['tomas']:2d} tomas, "
              f"{c['segundos_de_video']}s de video · {(c.get('texto') or '')[:50]!r}")
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()
    print(f"→ {destino} ({len(catalogo)} reels)")


if __name__ == "__main__":
    main()
