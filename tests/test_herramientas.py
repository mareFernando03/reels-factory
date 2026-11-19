"""Recortes, textos, legibilidad, caras, puntaje, huellas de la fábrica y métricas."""

from pathlib import Path

import numpy as np
import pytest
import yaml

import preparar_clips
from armar_pop import escala_en_zona, palabras
from caras import ZONA, cabeza, cruce, elegir_base
from estilo import de_marca
from fabrica import destinatario, huella, visual
from legibilidad import ALTO, contraste, franja_titulo, luminancia, tratamiento
from metricas import leer_metricas, pct
from movimiento import suavizar
from puntaje import calcular
from verificar import tiempos_de_texto


# ---------------------------------------------------------------- preparar_clips.recorte_manual

@pytest.fixture
def fuente_480p(monkeypatch):
    monkeypatch.setattr(preparar_clips, "dimensiones", lambda src: (480, 854))


def test_recorte_deja_afuera_el_texto_quemado(fuente_480p):
    # hasta el 78,5 % del alto, centrado: 9:16 de 670 px de alto
    assert preparar_clips.recorte_manual("x.mp4", {"abajo": 0.785}) == "376:670:52:0"


def test_recorte_no_se_sale_del_cuadro(fuente_480p):
    w, h, x, y = map(int, preparar_clips.recorte_manual("x.mp4", {"abajo": 0.785, "centro_x": 0.99}).split(":"))
    assert x + w <= 480 and x == 480 - 377


def test_tamano_visible_con_rotacion():
    # el 4K vertical del celular se guarda acostado con −90°: el recorte se mide sobre 2160×3840
    assert preparar_clips.tamano_visible(3840, 2160, -90) == (2160, 3840)
    assert preparar_clips.tamano_visible(3840, 2160, "90") == (2160, 3840)
    assert preparar_clips.tamano_visible(1080, 1920, 180) == (1080, 1920)
    assert preparar_clips.tamano_visible(1080, 1920, None) == (1080, 1920)


def test_recorte_con_arriba(fuente_480p):
    w, h, x, y = map(int, preparar_clips.recorte_manual("x.mp4", {"arriba": 0.1, "abajo": 0.9}).split(":"))
    assert y == 85 and h % 2 == 0 and w % 2 == 0


# ---------------------------------------------------------------- armar_pop.palabras

def test_palabras_marca_la_clave_aunque_lleve_signos():
    cuerpo, claves = palabras("¿pochoclos en el pelo?", "pochoclos", "x")
    assert claves == ["x-k0"]
    assert cuerpo.count('class="p"') == 4


def test_palabras_escapa_html():
    cuerpo, _ = palabras("<b>rulos</b> & más", None, "x")
    assert "<b>" not in cuerpo and "&amp;" in cuerpo


# ---------------------------------------------------------------- movimiento.suavizar

def test_suavizar_conserva_largo_y_constantes():
    x = np.full(10, 3.0)
    assert np.allclose(suavizar(x, 5), x)


def test_suavizar_n_chico_devuelve_copia():
    x = np.arange(5.0)
    y = suavizar(x, 1)
    assert np.array_equal(x, y) and y is not x


def test_suavizar_aplana_un_escalon():
    x = np.r_[np.zeros(10), np.ones(10)]
    y = suavizar(x, 4)
    assert len(y) == len(x) and 0 < y[9] < 1 and y[0] == 0 and y[-1] == 1


# ---------------------------------------------------------------- legibilidad

def test_contraste_blanco_negro():
    assert contraste(1.0, 0.0) == pytest.approx(21.0)


def test_luminancia_de_blanco_y_negro():
    im = np.array([[[255, 255, 255], [0, 0, 0]]], np.uint8)
    assert luminancia(im) == pytest.approx(np.array([[1.0, 0.0]]))


@pytest.mark.parametrize("texto, bloques, renglones", [
    ("no me había dado cuenta el crecimiento que tenía!", False, 4),   # antes y después
    ("para empezar este día de trabajo!", True, 3),                    # día de trabajo
    ("¿pochoclos en el pelo?", True, 2),
    ("Las espero!", True, 1),
])
def test_renglones_como_en_el_render(texto, bloques, renglones):
    x0, y0, x1, y1 = franja_titulo(texto, "62%", bloques)
    alto_renglon = (92 if len(texto) > 26 else 104) * (1.3 if bloques else 1.06)
    assert round((y1 - y0) / alto_renglon) == renglones
    assert y1 == int(ALTO * 0.62)


RAIZ = Path(__file__).resolve().parent.parent


def medidas_de(marca):
    md = RAIZ / "marcas" / marca
    if not (md / "marca.yaml").exists():
        pytest.skip(f"falta marcas/{marca}")
    m = de_marca(yaml.safe_load((md / "marca.yaml").read_text(encoding="utf-8"))).medidas_titulo(md)
    if not m["fuente"].exists():
        pytest.skip(f"falta la fuente de {marca}")
    return m


def test_con_la_fuente_de_la_marca_como_en_el_render():
    # el gancho de «El Extranjero» (Bebas a 120 px, bloques, base 27,5 %): 3 renglones de 156 px,
    # arriba en y = 60 en el render, bajo el nombre de la cuenta (pasó la evaluación a ojo)
    m = medidas_de("historia-breve")
    x0, y0, x1, y1 = franja_titulo("¿Condenado por no llorar a su madre?", "27.5%", True, **m)
    assert abs(y0 - 60) <= 4 and y1 == int(ALTO * 0.275)


@pytest.mark.parametrize("texto, bloques, renglones", [
    ("no me había dado cuenta el crecimiento que tenía!", False, 4),
    ("para empezar este día de trabajo!", True, 3),
    ("¿pochoclos en el pelo?", True, 2),
    ("Las espero!", True, 1),
    ("Cosas que verdaderamente asustan todo el año", False, 4),   # con sombra: el relleno de cada palabra lo pasa a 4
])
def test_fraunces_medida_da_los_renglones_del_render(texto, bloques, renglones):
    m = medidas_de("salon-demo")
    x0, y0, x1, y1 = franja_titulo(texto, "62%", bloques, **m)
    alto_renglon = (m["tam_largo"] if len(texto) > 26 else m["tam"]) * (1.3 if bloques else 1.06)
    assert round((y1 - y0) / alto_renglon) == renglones


def test_un_titulo_que_no_entra_se_achica_hasta_la_zona():
    m = medidas_de("historia-breve")
    texto = "¿Condenado por no llorar a su madre?"
    escala = escala_en_zona(texto, "27.5%", True, m)
    assert escala < 1
    assert franja_titulo(texto, "27.5%", True, escala=escala, **m)[1] >= ZONA[0] * ALTO
    assert escala_en_zona("Las espero!", "62%", True, m) == 1


def test_tratamiento_por_brillo():
    assert tratamiento(0.6) == "bloques" and tratamiento(0.2) == "sombra"


# ---------------------------------------------------------------- caras

def test_cruce_con_y_sin_superposicion():
    cara = [(400, 400, 600, 600)]
    assert cruce((0, 0, 100, 100), cara) == 0
    assert cruce((450, 450, 550, 550), cara) > 0


def test_cabeza_agranda_arriba():
    x0, y0, x1, y1 = cabeza((100, 200, 200, 300))
    assert y0 == 140 and x0 == 75 and y1 == 315


def test_elegir_base_esquiva_la_cara():
    cara = [(300, 1050, 700, 1250)]          # a la altura del 62 %
    base, en_cara, _ = elegir_base("Las espero!", cara, "62%", bloques=True)
    assert en_cara == 0 and base != "62%"


def test_elegir_base_sin_caras_queda_en_la_preferida():
    assert elegir_base("Las espero!", [], "62%")[0] == "62%"


# ---------------------------------------------------------------- puntaje

RUB = {"g": [
    {"id": "B1", "peso": "bloqueante", "aplica_a": ["reel"]},
    {"id": "I1", "peso": "importante", "aplica_a": ["reel"]},
    {"id": "D1", "peso": "deseable", "aplica_a": ["reel", "foto"]},
], "humano": [{"id": "H1"}]}


def test_puntaje_importante_vale_doble():
    r = calcular({"formato": "reel", "puntos": {"I1": 1, "D1": 2}}, RUB)
    assert (r["tot"], r["mx"], r["veredicto"]) == (4, 6, "ENTREGAR CON OBSERVACIONES")
    assert r["bajos"] == ["I1=1"]


def test_puntaje_bloqueante_que_falla_corrige():
    assert calcular({"formato": "reel", "fallan": ["B1"], "puntos": {"I1": 2, "D1": 2}}, RUB)["veredicto"] == "CORREGIR"


def test_puntaje_no_calcula_a_medias():
    r = calcular({"formato": "reel", "puntos": {"D1": 2}}, RUB)
    assert r["faltan"] == ["I1"] and r["veredicto"] is None


def test_puntaje_filtra_por_formato_y_no_aplica():
    r = calcular({"formato": "foto", "puntos": {"D1": 2}}, RUB)
    assert (r["mx"], r["veredicto"]) == (2, "ENTREGAR")
    assert calcular({"formato": "reel", "no_aplica": ["I1"], "puntos": {"D1": 2}}, RUB)["mx"] == 2


# ---------------------------------------------------------------- fábrica

def test_la_composicion_mira_las_imagenes_de_los_insertos(tmp_path):
    from fabrica import RAIZ, medios_de_la_composicion
    plan = {"subtitulos_fuente": {"entrada/a.mp4": "analisis/a.json"},
            "tomas": [{"n": 1, "insertos": [{"tipo": "imagen", "archivo": "entrada/disenos/x.jpg"}, {"tipo": "rotulo", "texto": "y"}],
                       "tarjetas": ["marcas/m/assets/v.png"]}, {"n": 2, "cierre": True}]}
    medios = medios_de_la_composicion(tmp_path, plan)
    assert medios == [tmp_path / "entrada/disenos/x.jpg", RAIZ / "marcas/m/assets/v.png", tmp_path / "analisis/a.json"]
    assert medios_de_la_composicion(tmp_path, {"subtitulos_fuente": "analisis/b.json", "tomas": []}) == [tmp_path / "analisis/b.json"]


def test_las_notas_no_cambian_la_huella_visual():
    a = {"bpm": 100, "tomas": [1], "publicar": {"nombre": "x"}, "musica": {"modo": "instagram", "fuente": "tal canción", "inicio": 2}}
    b = {**a, "publicar": {"nombre": "y"}, "adaptaciones": ["otra"], "musica": {**a["musica"], "fuente": "otra canción"}}
    assert huella(visual(a)) == huella(visual(b))
    c = {**a, "musica": {**a["musica"], "inicio": 3}}
    assert huella(visual(a)) != huella(visual(c))


def test_mensaje_para_quien_publica():
    assert destinatario({"marca": "salon-demo"}) == ("Ana", "💞", "para-ana.txt")
    if (RAIZ / "marcas" / "historia-breve" / "marca.yaml").exists():
        assert destinatario({"marca": "historia-breve"}) == ("Pablo", "", "para-pablo.txt")


# ---------------------------------------------------------------- verificar.tiempos_de_texto

def test_instantes_de_medicion_esquivan_las_entradas():
    # el título termina a los 3,0 s, pero el cierre entra a los 2,5: el final del título (2,85)
    # cae en la entrada del cierre (2,5-3,3), cuando su texto todavía está oculto, y no cuenta
    html = ('<div class="clip titulo" id="x-a" data-start="0.000" data-duration="3.000" data-track-index="1">'
            '<div id="cierre" class="clip" data-start="2.500" data-duration="2.000" data-track-index="3">')
    assert tiempos_de_texto(html) == [1.8, 3.7]   # el cierre tiene su placa: se mide una vez, ya asentado


def test_subtitulos_se_miden_una_sola_vez():
    subs = "".join(f'<div class="clip subtitulo" id="s{k}" data-start="{10 + 2 * k}.000" data-duration="1.500" data-track-index="4">'
                   for k in range(20))
    assert tiempos_de_texto(subs) == [10.9]   # 20 subtítulos en la misma píldora opaca: uno solo como muestra


# ---------------------------------------------------------------- métricas

def test_leer_metricas_y_cocientes(tmp_path):
    f = tmp_path / "metricas.md"
    f.write_text("---\npublicado: 2026-10-05\nmediciones:\n  - { a: 72h, alcance: 400, envios: 6 }\n---\n## Lectura\n", encoding="utf-8")
    m = leer_metricas(f)
    assert m["mediciones"][0]["alcance"] == 400
    assert pct(6, 400) == 1.5 and pct(None, 400) is None and pct(3, 0) is None


def test_tabla_de_la_marca_con_datos(tmp_path):
    # con una medición cargada, la tabla se arma (antes faltaban "publicado" y "a" en la fila)
    import metricas
    p = tmp_path / "2026-10-03-salon-demo-x"
    (p / "salida").mkdir(parents=True)
    (p / "salida" / "metricas.md").write_text(
        "---\npublicado: 2026-10-05\nmediciones:\n  - { a: 72h, alcance: 400, salteo_pct: 35, retencion_pct: 61 }\n---\n",
        encoding="utf-8")
    r = metricas.fila(p, metricas.leer_metricas(p / "salida" / "metricas.md"), {"formato": "reel"}, "salon-demo")
    assert r["pedido"] == "x" and str(r["publicado"]) == "2026-10-05" and r["retencion"] == 61
    assert "35 % ⚠" in metricas.tabla([r])[2]


# ---------------------------------------------------------------- metricool (M-22)

import metricool  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


def test_metricool_unidades_y_nombres():
    f = metricool.normalizar({"IGRE23": 1200, "IGRE11": "800", "IGRE24": 7400, "IGRE28": 0.68,
                              "Instagram Reels > Retention": 55.5, "shares": 9,
                              "IGRE06": "https://www.instagram.com/reel/AbC_1/", "IGRE02": "2026-10-06T19:30:00-03:00"})
    assert f["visualizaciones"] == 1200 and f["alcance"] == 800 and f["envios"] == 9
    assert f["tiempo_medio_s"] == 7.4 and f["salteo_pct"] == 32.0 and f["retencion_pct"] == 55.5
    assert metricool.codigo(f["link"]) == "AbC_1" and f["fecha_hora"].hour == 19
    assert metricool.normalizar({"averageWatchTime": 8.2})["tiempo_medio_s"] == 8.2     # ya en segundos


def test_metricool_filas_en_columnas():
    datos = {"filas": {"headers": ["IGRE06", "IGRE23"], "rows": [["https://instagram.com/reel/X1/", 5]]}}
    assert metricool.filas_crudas(datos) == [{"IGRE06": "https://instagram.com/reel/X1/", "IGRE23": 5}]
    # así responde el MCP: {"rows": [...]}; si las filas son listas, van en el orden de lo pedido
    datos = {"campos": ["IGRE06", "IGRE23"], "filas": {"rows": [["https://instagram.com/reel/X1/", 5]]}}
    assert metricool.filas_crudas(datos) == [{"IGRE06": "https://instagram.com/reel/X1/", "IGRE23": 5}]
    assert metricool.filas_crudas({"filas": {"rows": []}}) == []


def test_metricool_forma_real_de_la_respuesta():
    # visto el 04/10/2026: listas en el orden pedido, números como texto y la fecha al final, de más
    datos = {"tipo": "reels", "campos": ["IGRE06", "IGRE23", "IGRE28", "IGRE02"],
             "filas": {"rows": [["https://www.instagram.com/reel/X1/", "1500.0", "64.0", "20261006", "20261009"]]}}
    f = metricool.normalizar(metricool.filas_crudas(datos)[0])
    assert f["visualizaciones"] == 1500 and f["salteo_pct"] == 36.0
    assert f["fecha_hora"].date().isoformat() == "2026-10-06" and f["fecha_hora"].utcoffset().total_seconds() == -3 * 3600


def test_metricool_edad():
    pub = datetime(2026, 10, 6, 19, tzinfo=timezone.utc)
    assert metricool.edad(pub, datetime(2026, 10, 9, 21, tzinfo=timezone.utc)) == "72h"
    assert metricool.edad(pub, datetime(2026, 10, 13, 20, tzinfo=timezone.utc)) == "7d"
    assert metricool.edad(pub, datetime(2026, 10, 16, 19, tzinfo=timezone.utc)) == "10d"
    assert metricool.edad(pub, datetime(2026, 10, 7, 19, tzinfo=timezone.utc)) == "24h"


def _pedido(raiz, nombre, caption=None, plan="", link=None):
    p = raiz / nombre
    (p / "plan").mkdir(parents=True)
    (p / "salida").mkdir()
    (p / "plan" / "guion.yaml").write_text(plan, encoding="utf-8")
    if caption:
        (p / "salida" / "caption.txt").write_text(caption, encoding="utf-8")
    if link:
        (p / "salida" / "metricas.md").write_text(
            f"---\nlink: {link}\nmediciones:\n  - a: 72h\n    pozo_s: 6\n---\n## Lectura\nbien\n", encoding="utf-8")
    return p


def _fila(codigo, texto, dia):
    return metricool.normalizar({"IGRE06": f"https://www.instagram.com/reel/{codigo}/", "IGRE03": texto,
                                 "IGRE02": f"2026-10-{dia:02d}T20:00:00-03:00", "IGRE23": 900, "IGRE24": 6100})


def test_metricool_une_por_descripcion_y_por_link(tmp_path):
    a = _pedido(tmp_path, "2026-10-03-salon-demo-pochoclos", "¿Pochoclos en el pelo? Así quedan los rulos en Rafaela #rulos")
    b = _pedido(tmp_path, "2026-10-03-salon-demo-dia", "Un día de trabajo en el salón", plan="# Material: DeCDK9sSE_T")
    c = _pedido(tmp_path, "2026-10-04-salon-demo-mama", link="https://www.instagram.com/reel/MAMA1/")
    filas = [_fila("VIEJO", "¿Pochoclos en el pelo? Así quedan los rulos en Rafaela", 1),     # anterior al pedido
             _fila("POCH1", "¿Pochoclos en el pelo? Así quedan los rulos, en Rafaela! #salondemo", 6),
             _fila("DeCDK9sSE_T", "Un día de trabajo en el salón", 3),                         # el original de la reversión
             _fila("MAMA1", "otra cosa", 10)]
    pares, sueltas = metricool.unir(filas, [a, b, c])
    unidos = {p.name: (metricool.codigo(f["link"]), como.split()[0]) for p, f, como in pares}
    assert unidos == {a.name: ("POCH1", "descripción"), c.name: ("MAMA1", "link")}
    assert {metricool.codigo(f["link"]) for f in sueltas} == {"VIEJO", "DeCDK9sSE_T"}


def test_metricool_carga_sin_pisar_la_captura(tmp_path):
    c = _pedido(tmp_path, "2026-10-04-salon-demo-mama", link="https://www.instagram.com/reel/MAMA1/")
    metricool.cargar(c, _fila("MAMA1", "x", 6), datetime(2026, 10, 9, 23, tzinfo=timezone.utc))
    datos, cuerpo = metricool.leer_md(c / "salida" / "metricas.md")
    m = datos["mediciones"][0]
    assert len(datos["mediciones"]) == 1 and m["a"] == "72h" and m["pozo_s"] == 6
    assert m["visualizaciones"] == 900 and m["tiempo_medio_s"] == 6.1 and m["fuente"] == "metricool"
    assert datos["publicado"] == "2026-10-06" and "bien" in cuerpo


def test_metricool_crea_desde_la_plantilla(tmp_path):
    a = _pedido(tmp_path, "2026-10-03-salon-demo-pochoclos", "x")
    metricool.cargar(a, _fila("POCH1", "x", 6), datetime(2026, 10, 13, 23, tzinfo=timezone.utc))
    datos, cuerpo = metricool.leer_md(a / "salida" / "metricas.md")
    assert [m["a"] for m in datos["mediciones"]] == ["7d"] and datos["link"].endswith("/POCH1/")
    assert "## Lectura" in cuerpo


# ---------------------------------------------------------------- movimiento.tramo (caché)

from movimiento import tramo  # noqa: E402

VENTANAS = {"ventanas": [{"t": t / 2, "clase": "x"} for t in range(0, 20)]}   # 0, 0,5, … 9,5


def test_tramo_prefiere_ventanas_enteras():
    # 69,15-70,65 en el original: la ventana 69,0-69,5 trae el corte de plano y no cuenta
    datos = {"ventanas": [{"t": 69.0}, {"t": 69.5}, {"t": 70.0}, {"t": 70.5}]}
    assert [v["t"] for v in tramo(datos, 69.15, 70.65)] == [69.5, 70.0]


def test_tramo_corto_usa_el_centro_o_la_mas_cercana():
    assert [v["t"] for v in tramo(VENTANAS, 1.1, 1.6)] == [1.0]      # centro 1,25 adentro
    assert [v["t"] for v in tramo(VENTANAS, 1.3, 1.4)] == [1.0]      # ninguno: la más cercana


# ---------------------------------------------------------------- color (igualar tomas)

from color import GAMMA, GANANCIA, correccion, referencia  # noqa: E402

REF = {"y": 130, "rg": 1.0, "bg": 1.0, "neutros": 0.5}


def test_color_sin_diferencia_no_corrige():
    assert correccion(dict(REF), REF) is None


def test_color_toma_oscura_se_aclara_con_tope():
    c = correccion({"y": 80, "rg": 1.0, "bg": 1.0, "neutros": 0.5}, REF)
    assert 1 < c["gamma"] <= GAMMA[1]
    assert correccion({"y": 20, "rg": 1.0, "bg": 1.0, "neutros": 0.5}, REF)["gamma"] == GAMMA[1]


def test_color_balance_parcial_y_acotado():
    c = correccion({"y": 130, "rg": 1.04, "bg": 0.96, "neutros": 0.5}, REF)
    assert c["rr"] < 1 < c["bb"]                  # baja el rojo, sube el azul
    assert abs(c["rr"] - 1) < 0.04                 # la mitad del camino, no todo
    lejos = correccion({"y": 130, "rg": 1.5, "bg": 1.0, "neutros": 0.5}, REF)
    assert lejos["rr"] == 1 - GANANCIA


def test_color_sin_neutros_no_toca_el_balance():
    c = correccion({"y": 80, "rg": 1.2, "bg": 0.9, "neutros": 0.1}, REF)
    assert c["rr"] == 1.0 and c["bb"] == 1.0


def test_referencia_es_el_revelado():
    assert referencia([{"n": 1, "que": "gancho"}, {"n": 2, "rol": "revelado"}]) == 2
    assert referencia([{"n": 1, "que": "WOW: cartel"}]) == 1
    assert referencia([{"n": 1, "que": "toma"}]) is None


# ---------------------------------------------------------------- biblioteca

from biblioteca import buscar, elegir_tomas  # noqa: E402


def test_elegir_tomas_reparte_a_lo_largo_del_reel():
    detalle = [{"n": i} for i in range(49)]
    elegidas = elegir_tomas(detalle)
    assert len(elegidas) == 18 and elegidas[0]["n"] == 0 and elegidas[-1]["n"] == 48


def test_buscar_cruza_lectura_y_calidad(tmp_path, capsys):
    (tmp_path / "lecturas.yaml").write_text(
        "A1:\n  servicio: rulos con mechas\n  etiquetas: [rulos]\n  tramos: [{desde: 1, hasta: 3, que: de cerca}]\n"
        "B2:\n  servicio: corte masculino\n", encoding="utf-8")
    cat = {"A1": {"fecha": "2026", "tipo": "video", "duracion": 10, "calidad": {"resolucion": "1080p"}},
           "B2": {"fecha": "2026", "tipo": "video", "duracion": 10, "calidad": {"resolucion": "480p"}}}
    buscar(tmp_path, cat, "Rulos 720p")
    salida = capsys.readouterr().out
    assert salida.startswith("A1 [2/2]") and "de cerca" in salida and "B2" not in salida


# ---------------------------------------------------------------- voz y subtítulos

from armar_pop import subtitulos  # noqa: E402
from audio import instruccion_instagram  # noqa: E402


def test_subtitulos_cortan_por_cantidad_y_por_pausa():
    w = lambda t, a, b: {"w": t, "ini": a, "fin": b}  # noqa: E731
    frases = subtitulos([w("Hola", 0.0, 0.3), w("buen", 0.35, 0.5), w("día", 0.5, 0.8),
                         w("chicas", 1.6, 2.0)])          # pausa de 0,8 s antes de "chicas"
    assert [f["texto"] for f in frases] == ["Hola buen día", "chicas"]
    largas = subtitulos([w(str(i), i * 0.2, i * 0.2 + 0.15) for i in range(9)])
    assert all(len(f["texto"].split()) <= 4 for f in largas)
    assert frases[1]["fin"] - frases[1]["ini"] >= 0.6   # mínimo a la vista


def test_instruccion_con_voz_pide_la_musica_bajita():
    con = instruccion_instagram({"fuente": "la canción"}, con_voz=True)
    sin = instruccion_instagram({"fuente": "la canción"})
    assert "100 %" in con and "15-20 %" in con and "20-30 %" in sin


def test_caras_que_no_se_repiten_no_cuentan():
    from caras import _persisten
    oreja = [(600, 740, 750, 920)]
    cara = (300, 800, 470, 990)
    por_cuadro = [[], [cara], oreja + [(305, 805, 475, 995)], [], [], []]
    assert _persisten(por_cuadro) == [cara, (305, 805, 475, 995)]
    assert _persisten([oreja]) == oreja          # una foto: cuenta lo que haya


def test_voz_partida_en_el_borde_del_tramo():
    # el saludo de los pochoclos: «Hola buen día, buen | día» (palabras de 0,4 a 3,7 s del original)
    t = {"fuente": "x.mp4", "desde": 1.20, "hasta": 2.90}
    palabras = [{"w": w, "ini": a - 0.4, "fin": b - 0.4} for w, a, b in
                [("Hola", 1.30, 1.88), ("buen", 1.88, 2.14), ("día,", 2.14, 2.60), ("buen", 2.76, 2.94), ("día", 2.94, 3.26)]]
    cache = {"x.mp4|0.400|3.700": {"palabras": palabras}}
    assert preparar_clips.palabras_partidas("x.mp4", t, cache) == ["buen"]
    t2 = {**t, "hasta": 3.45}
    cache["x.mp4|0.400|4.250"] = {"palabras": palabras}
    assert preparar_clips.palabras_partidas("x.mp4", t2, cache) == []


def test_base_sintetica_sin_semilla_es_la_de_siempre():
    from audio import PROGRESIONES, acordes, variante
    assert acordes(0, PROGRESIONES[0]) == [(36, (60, 64, 67)), (43, (59, 62, 67)), (45, (57, 60, 64)), (41, (57, 60, 65))]
    assert variante(0)["tonica"] == 0 and variante(123) == variante(123)


def test_sugerir_saltea_usados_y_con_voz_solo_instrumentales(monkeypatch):
    import musica
    cat = {"1": {"archivo": "musica/libre/a.mp3", "bpm": 100, "voz_db": -45},
           "2": {"archivo": "musica/libre/b.mp3", "bpm": 101, "voz_db": -20},
           "3": {"archivo": "musica/libre/c.mp3", "bpm": 99, "voz_db": -48},
           "4": {"archivo": "musica/libre/d.mp3", "bpm": 130, "voz_db": -48}}
    monkeypatch.setattr(musica, "usados", lambda: {"musica/libre/c.mp3": ["otro-pedido"]})
    assert [tid for tid, _ in musica.sugerir(100, cat=cat)] == ["1", "2"]
    assert [tid for tid, _ in musica.sugerir(100, con_voz=True, cat=cat)] == ["1"]


# ---------------------------------------------------------------- estilo por marca (M-23)

def test_marca_sin_estilo_es_salon_pop():
    from estilo import SALON_POP, css, de_marca
    assert de_marca({"colores": {}}) == SALON_POP
    c = {"primario": "#CE1269", "secundario": "#861196"}
    assert 'font-family: "Fraunces", serif; font-style: italic' in css(c, "62%")


def test_estilo_de_marca_pisa_solo_lo_que_declara():
    from estilo import SALON_POP, css, de_marca, destellos
    e = de_marca({"estilo": {"claro": "#F5EDE0", "calidez": {"color": "#DCAD8E", "opacidad": 0.1}, "destellos": False,
                             "resaltador": "#F2C230", "titulo": {"familia": "Bebas Neue", "archivo": "b.woff2", "escala": 1.3,
                                                                 "mayusculas": True, "estilo": "normal"}}})
    assert (e.claro, e.calidez_color, e.calidez, e.grano) == ("#F5EDE0", "#DCAD8E", 0.1, SALON_POP.grano)
    assert e.titulo["peso"] == 900 and e.tam(100) == "130px"   # lo no declarado de la fuente se hereda
    assert e.archivos_fuentes()[0] == "b.woff2" and destellos("x", ["#fff"], [(0, 0, 10)], e) == ""
    hoja = css({"primario": "#372F2B", "secundario": "#3F6E9E"}, "62%", e)
    assert "text-transform: uppercase" in hoja and "background: #F2C230" in hoja and "Fraunces" not in hoja


def test_estilo_con_un_token_desconocido_avisa():
    from estilo import de_marca
    with pytest.raises(SystemExit, match="rosa"):
        de_marca({"estilo": {"rosa": "#f0f"}})


def test_subtitulos_a_otra_altura_y_corregidos():
    from armar_pop import corregir, franja_subtitulos
    from estilo import SUBTITULO_FRANJA
    assert franja_subtitulos({}) == SUBTITULO_FRANJA
    arriba, abajo = franja_subtitulos({"subtitulos_base": "30%"})
    assert abajo == 0.305 and round(abajo - arriba, 3) == round(SUBTITULO_FRANJA[1] - SUBTITULO_FRANJA[0], 3)
    assert corregir("se centra en Marzot, un hombre", {"Marzot": "Meursault"}) == "se centra en Meursault, un hombre"
    assert corregir("Pusgan más", {"puzgan": "juzgan", "pusgan": "juzgan"}) == "Juzgan más"


def test_subtitulos_no_se_pisan():
    from armar_pop import subtitulos
    palabras = [{"w": "procesa", "ini": 0.0, "fin": 1.4}, {"w": "bastante", "ini": 1.7, "fin": 2.1},
                {"w": "indiferente", "ini": 2.2, "fin": 3.0}]
    fr = subtitulos(palabras, max_palabras=1)
    assert all(a["fin"] <= b["ini"] for a, b in zip(fr, fr[1:]))
    assert fr[-1]["fin"] == 3.0
    assert fr[0]["fin"] == 1.7 and fr[1]["fin"] == 2.2   # pausas cortas: cada frase queda hasta la siguiente
    lejos = subtitulos([{"w": "hola", "ini": 0.0, "fin": 0.8}, {"w": "chau", "ini": 3.0, "fin": 3.5}])
    assert lejos[0]["fin"] == 0.8                          # pausa larga: se apaga


def test_subtitulos_esquivan_placas_y_tomas_sin_subtitulos():
    from armar_pop import tapado
    assert tapado(1.0, 2.0, [(1.5, 3.0)]) == (1.0, 1.5)       # una placa entra a mitad de la frase: se corta
    assert tapado(2.0, 3.5, [(1.5, 3.0)]) == (3.0, 3.5)       # arranca tapada: aparece cuando sale la placa
    assert tapado(1.6, 2.9, [(1.5, 3.0)]) is None             # entera debajo de la placa: no va
    assert tapado(4.0, 5.0, [(1.5, 3.0)]) == (4.0, 5.0)


def test_relato_mide_la_imagen_sin_cambio():
    from verificar import sin_cambio_visual
    larga = {"n": 1, "insertos": [{"tipo": "imagen", "desde": 3.0, "hasta": 7.0}, {"tipo": "rotulo", "desde": 8, "hasta": 9}]}
    corta = {"n": 2}
    durs = {id(larga): 15.0, id(corta): 5.0}
    assert sin_cambio_visual([larga, corta], durs) == (8.0, 1)   # de 7 a 15 s: el rótulo no cambia la imagen


def test_bitrate_topeado_por_duracion():
    from render import bitrate_para
    assert bitrate_para(20) == 25_000                       # corto: sin tope práctico
    kbps = bitrate_para(90)
    assert (kbps + 192) * 90 / 8000 <= 92 and kbps > 7_000  # 90 s: entra en 92 MB y sigue alto


def test_subtitulos_de_la_transcripcion_entera():
    from armar_pop import palabras_del_tramo
    palabras = [{"w": "honesto,", "ini": 77.22, "fin": 77.76}, {"w": "se", "ini": 78.06, "fin": 78.16},
                {"w": "podría", "ini": 78.16, "fin": 78.38}]
    assert [w["w"] for w in palabras_del_tramo(palabras, 70.85, 77.95)] == ["honesto,"]   # entera en la toma que arranca
    tramo = palabras_del_tramo(palabras, 77.95, 81.30)
    assert [w["w"] for w in tramo] == ["se", "podría"] and tramo[0]["ini"] == 0.11


def test_subtitulos_de_dos_fuentes(tmp_path):
    from armar_pop import transcripcion_de
    (tmp_path / "analisis").mkdir()
    (tmp_path / "analisis" / "ana.json").write_text('{"palabras": [{"w": "sorteo", "ini": 10.6, "fin": 11.5}]}', encoding="utf-8")
    (tmp_path / "analisis" / "yami.json").write_text('{"palabras": [{"w": "uñitas", "ini": 10.6, "fin": 11.0}]}', encoding="utf-8")
    fuentes = {"entrada/crudos/ana.mp4": "analisis/ana.json", "yami.mp4": "analisis/yami.json"}
    assert transcripcion_de(tmp_path, fuentes, "entrada/crudos/ana.mp4")[0]["w"] == "sorteo"
    # la toma la nombra desde la raíz del repo; la clave, desde el pedido (así falló en el primer borrador)
    assert transcripcion_de(tmp_path, fuentes, "pedidos/x/entrada/crudos/ana.mp4")[0]["w"] == "sorteo"
    assert transcripcion_de(tmp_path, fuentes, "pedidos/x/entrada/crudos/yami.mp4")[0]["w"] == "uñitas"  # por nombre
    assert transcripcion_de(tmp_path, fuentes, "otra.mp4") is None
    assert transcripcion_de(tmp_path, fuentes, "pedidos/x/entrada/crudos/otra-ana.mp4") is None  # no por sufijo suelto
    assert transcripcion_de(tmp_path, "analisis/ana.json", "cualquiera.mp4")[0]["w"] == "sorteo"  # una sola fuente


def test_voz_pareja_entre_tomas():
    import numpy as np
    from audio import SR, ganancia_pareja
    t = np.arange(SR * 2) / SR
    baja = 0.06 * np.sin(2 * np.pi * 220 * t)       # una toma dicha más bajo
    alta = 0.30 * np.sin(2 * np.pi * 220 * t)
    assert ganancia_pareja(baja) > 1.5 and ganancia_pareja(alta) < 0.7
    assert ganancia_pareja(0.001 * baja) == 1.0       # silencio: no se toca
    assert ganancia_pareja(0.03 * np.sin(2 * np.pi * 220 * t)) <= 10 ** (6 / 20) + 1e-9   # tope de +6 dB


# ---------------------------------------------------------------- armar_pop.tarjetas

def _tarjetas(tmp_path, n, alto, ancho, **toma):
    import re

    import cv2
    from armar_pop import tarjetas
    rutas = []
    for i in range(n):
        ruta = tmp_path / f"t{i}.png"
        cv2.imwrite(str(ruta), np.zeros((alto, ancho, 3), np.uint8))
        rutas.append(str(ruta))
    tw = []
    capa = tarjetas(tmp_path, {"n": 3, "tarjetas": rutas, **toma}, 10.0, 4.0, 0.6, tw)
    cajas = [tuple(map(float, m)) for m in re.findall(r"top:(-?\d+)px; left:(-?\d+)px; width:(\d+)px", capa)]
    return cajas, tw


def test_collage_en_grilla_sin_superponerse(tmp_path):
    cajas, tw = _tarjetas(tmp_path, 4, 1195, 1080, columnas=2, cada=0.5, zona=[27, 84])
    (y0, x0, w), (y1, x1, _), (y2, x2, _), _ = cajas
    assert y0 == y1 and x0 == x2 and x1 - x0 == w + 30   # dos columnas, misma fila
    assert y2 - y0 >= w * 1195 / 1080                     # la segunda fila empieza debajo de la primera
    assert abs((x0 + x1 + w) / 2 - 540) <= 1              # centrada
    assert "10.35" in tw[1]                               # entra a medio beat (0,3 s) de la primera


def test_tarjetas_en_foco_una_por_vez_y_el_repaso(tmp_path):
    cajas, tw = _tarjetas(tmp_path, 3, 688, 2192, foco=True, foco_beats=2, zona=[30.5, 70])
    assert len(cajas) == 3 and len(tw) == 3 * 4           # entrada, respiro, salida y repaso por tarjeta
    assert "10.05" in tw[0] and "11.25" in tw[4]          # la segunda entra 2 beats después
    assert all("immediateRender: false" in t for k, t in enumerate(tw) if k % 4)  # seek-safe


from armar_historia import BASE, lado_firma  # noqa: E402


def test_firma_de_historia_no_pisa_el_titulo():
    # título arriba: la firma baja, aunque el sticker también vaya abajo
    for plantilla in ("novedad", "detras", "teaser"):
        assert lado_firma(BASE[plantilla], "abajo") == "abajo"
        assert lado_firma(BASE[plantilla], None) == "abajo"
    # título al medio o abajo: la firma queda arriba, salvo que el sticker vaya arriba
    assert lado_firma(BASE["turno"], "abajo") == "arriba"
    assert lado_firma(BASE["resultado"], "arriba") == "abajo"
    assert lado_firma("68%", "abajo") == "arriba"


# ---------------------------------------------------------------- analizar_audio.necesita_extraer

def test_audio_de_un_video_se_extrae_antes():
    from analizar_audio import necesita_extraer
    assert necesita_extraer("entrada/referencia.mp4")
    assert necesita_extraer("x.MOV")
    assert not necesita_extraer("musica/tema.wav")
    assert not necesita_extraer("instrucciones.ogg")


# ---------------------------------------------------------------- analizar_referencia.bpm_por_cortes

# Cortes reales de la referencia Ddws-dDhTK2 («Pump It», ~156 bpm): librosa dio 103,4.
CORTES_PUMP_IT = [1.533, 3.067, 4.167, 6.1, 7.567]


def test_tempo_que_explica_los_cortes():
    from analizar_referencia import bpm_por_cortes, desajuste
    assert desajuste(CORTES_PUMP_IT, 156.5) < 0.1 < desajuste(CORTES_PUMP_IT, 103.4)
    assert bpm_por_cortes(CORTES_PUMP_IT, [103.4, 152.0, 156.5]) == 156.5


def test_tempo_sin_cortes_suficientes_queda_el_de_librosa():
    from analizar_referencia import bpm_por_cortes
    assert bpm_por_cortes([1.5, 3.0], [103.4, 156.5]) == 103.4
    # cortes en la grilla de librosa: no cambia por una mejora mínima
    assert bpm_por_cortes([0.0, 2.4, 4.8, 7.2], [100.0, 150.0]) == 100.0


def test_tempo_afinado_con_los_cortes():
    from analizar_referencia import afinar
    assert 155 <= afinar(CORTES_PUMP_IT, 152.0) <= 158   # 4 beats = 1,533 s → ~156,5


# ---------------------------------------------------------------- audio.nombre_salida

def test_borrador_no_pisa_el_final_en_modo_instagram():
    from audio import nombre_salida
    assert nombre_salida("salida/borrador.mp4", "instagram") == "salida/borrador.mp4"
    assert nombre_salida(None, "instagram") == "salida/reel-efectos.mp4"
    assert nombre_salida(None, "archivo") == "salida/reel-con-audio.mp4"


# ---------------------------------------------------------------- preparar_clips.realce · estilo.de_marca(ajustes)

def test_realce_enfoca_y_satura_sin_tocar_el_tono():
    assert preparar_clips.realce(1080) == []
    assert preparar_clips.realce(478) == ["unsharp=5:5:0.6:5:5:0.0"]
    filtros = preparar_clips.realce(1080, True)
    assert any(f.startswith("unsharp") for f in filtros) and "eq=saturation=1.08" in filtros
    assert not any("hue" in f or "colorbalance" in f for f in filtros)


def test_ajustes_del_guion_pisan_el_estilo_de_la_marca():
    marca = {"estilo": {"grano": 0.14, "titulo": {"familia": "Bebas Neue", "archivo": "b.woff2", "peso": 400}}}
    e = de_marca(marca, {"grano": 0.04, "titulo": {"familia": "Cormorant Garamond", "peso": 500}})
    assert e.grano == 0.04
    assert e.titulo["familia"] == "Cormorant Garamond" and e.titulo["peso"] == 500
    assert e.titulo["archivo"] == "b.woff2"            # lo que el ajuste no nombra queda de la marca
    assert de_marca(marca).grano == 0.14               # sin ajustes, la marca tal cual



# ---------------------------------------------------------------- caras.UMBRAL

def test_umbral_de_caras_entre_falsos_y_reales():
    from caras import UMBRAL
    # medidos: la mano con un cepillo de «la obra de arte» dio 0,83; caras reales de perfil, 0,90-0,93
    assert 0.83 < UMBRAL < 0.87


# ---------------------------------------------------------------- mapa (insertos de tipo mapa)

def test_mapa_proyecta_oeste_a_la_izquierda_y_norte_arriba():
    import mapa
    v = mapa.vista((-115, 15), centro_lat=20)
    tenochtitlan, lisboa = mapa.proyectar(-99.13, 19.43, v), mapa.proyectar(-9.14, 38.72, v)
    assert 0 < tenochtitlan[0] < lisboa[0] < 1080
    assert lisboa[1] < tenochtitlan[1]  # más al norte, más arriba
    assert mapa.proyectar(-50, 20, v)[1] == pytest.approx(960)  # la latitud del centro, a mitad del alto


def test_mapa_tierra_solo_lo_que_se_ve():
    import mapa
    atlantico = mapa.tierra(mapa.vista((-115, 15), 20))
    pacifico = mapa.tierra(mapa.vista((150, 200), 0))
    assert atlantico.count("M") > pacifico.count("M") > 0


def test_mapa_ruta_curva_y_largo():
    import mapa
    v = mapa.vista((-115, 15), 20)
    d, largo, fin = mapa.ruta([-99.13, 19.43], [-9.14, 38.72], v)
    (x0, y0), (x1, y1) = mapa.proyectar(-99.13, 19.43, v), mapa.proyectar(-9.14, 38.72, v)
    import math
    assert d.startswith("M") and "Q" in d
    assert fin == pytest.approx((x1, y1))
    assert largo > math.dist((x0, y0), (x1, y1))  # la curva es más larga que la recta


def test_inserto_mapa_dibuja_las_rutas_y_apaga():
    from armar_pop import capa_mapa
    tw = []
    ins = {"tipo": "mapa", "desde": 0, "hasta": 4,
           "rutas": [{"de": [-6.9, 37.2], "a": [-74.5, 24.0], "color": "claro", "dibujar": [0.2, 1.8], "apagar": 2.4},
                     {"de": [-99.13, 19.43], "a": [-9.14, 38.72], "dibujar": [2.5, 4.0]}],
           "lugares": [{"nombre": "Tenochtitlan", "en": [-99.13, 19.43], "desde": 2.4, "lado": "izq"}]}
    capa = capa_mapa(ins, "in1-0", 'data-start="10" data-duration="4"', 10.0,
                     {"acento": "#F2C230", "claro": "#FFFFFF", "secundario": "#3F6E9E"}, tw)
    assert 'id="in1-0-r0"' in capa and 'stroke="#FFFFFF"' in capa and 'stroke="#F2C230"' in capa
    assert "Tenochtitlan" in capa and "mapa-lugar izq" in capa
    tiempos = " ".join(tw)
    assert "strokeDashoffset: 0" in tiempos and ", 10.200);" in tiempos and ", 12.500);" in tiempos  # tiempos desde la toma
    assert "opacity: 0, duration: 0.4" in tiempos  # la primera ruta se apaga


def test_inserto_mapa_lugar_que_se_apaga_y_arriba():
    from armar_pop import capa_mapa
    tw = []
    ins = {"lugares": [{"nombre": "Colón · 1492", "en": [-6.9, 37.2], "desde": 0.1, "hasta": 2.5, "lado": "arriba"}]}
    capa = capa_mapa(ins, "in1-0", "", 0.0, {"acento": "#F2C230", "claro": "#FFF", "secundario": "#3F6E9E"}, tw)
    assert "mapa-lugar arriba" in capa
    assert any('"#in1-0-l0 .ml", { opacity: 1 }, { opacity: 0' in x and "2.500" in x for x in tw)


# ---------------------------------------------------------------- armar_pop.caja_cuadro y encabezado

def test_cuadro_con_subtitulos_termina_arriba_de_su_franja():
    from armar_pop import caja_cuadro
    from estilo import SUBTITULO_FRANJA
    # una tapa vertical con acercamiento ×1,08: ni creciendo entra en la franja de los subtítulos
    cw, ch, x, y, rotulo = caja_cuadro(1080, 1599, SUBTITULO_FRANJA, 1.08)
    centro = y + ch / 2
    assert centro + ch * 1.08 / 2 <= SUBTITULO_FRANJA[0] * 1920
    assert x == pytest.approx((1080 - cw) / 2)
    assert float(rotulo.rstrip("%")) / 100 * 1920 <= y + 1  # el rótulo, arriba del cuadro


def test_cuadro_sin_subtitulos_usa_la_caja_grande():
    from armar_pop import caja_cuadro
    _, ch, _, y, rotulo = caja_cuadro(1080, 1599)
    assert ch == pytest.approx(0.42 * 1920) and rotulo == "64%"
    assert y == pytest.approx(0.29 * 1920)


def test_encabezado_una_placa_con_la_palabra_destacada():
    from armar_pop import encabezado
    tw = []
    capa = encabezado({"texto": "¿Y si fue al revés?", "destacar": "revés"}, "x-fijo", 8.5, 108.0, tw)
    assert 'class="clip encabezado"' in capa and "<b>revés?</b>" in capa
    assert capa.count("<span>") == 1  # una sola placa, no un bloque por palabra
    assert 'data-start="8.500"' in capa and len(tw) == 1


def test_mapa_que_se_dibuja_cuenta_como_cambio_de_imagen():
    from verificar import sin_cambio_visual
    gancho = {"n": 1, "insertos": [{"tipo": "mapa", "desde": 0.0, "hasta": 8.5,
                                    "rutas": [{"dibujar": [0.15, 2.0], "apagar": 3.0}, {"dibujar": [3.3, 6.7]}],
                                    "lugares": [{"desde": 0.1, "hasta": 3.0}, {"desde": 6.4}]}]}
    quieto, _ = sin_cambio_visual([gancho], {id(gancho): 8.5})
    assert quieto < 7  # sin contar las rutas eran 8,5 s "quietos"


def test_toma_cubierta_por_insertos():
    from armar_pop import cubierta
    mapa = {"insertos": [{"tipo": "mapa", "desde": 0.0, "hasta": 8.5}]}
    assert cubierta(mapa, 8.5)
    assert not cubierta({"insertos": [{"tipo": "imagen", "desde": 1.0, "hasta": 8.5}]}, 8.5)   # el primer segundo se ve la cara
    assert not cubierta({"insertos": [{"tipo": "rotulo", "desde": 0.0, "hasta": 8.5}]}, 8.5)   # un rótulo no tapa
    assert cubierta({"insertos": [{"desde": 0.0, "hasta": 4.0}, {"tipo": "placa", "desde": 4.0, "hasta": 8.5}]}, 8.5)
    assert not cubierta({}, 8.5)


def test_zoom_de_una_placa_acerca_alrededor_del_foco():
    from armar_foto import estilo_foto
    assert estilo_foto({}) == "object-position: 50% 45%"
    assert estilo_foto({"foco": "45% 30%", "zoom": 1.3}) == "object-position: 45% 30%; transform: scale(1.3); transform-origin: 45% 30%"
    assert "transform" not in estilo_foto({"zoom": 0.8})   # nunca aleja: quedarían bordes vacíos


def test_una_foto_como_toma_no_lleva_velocidad_ni_estabilizacion():
    assert preparar_clips.es_foto("entrada/crudos/antes.JPG") and preparar_clips.es_foto("x.webp")
    assert not preparar_clips.es_foto("entrada/crudos/obra.mp4")
    f = preparar_clips.filtros_foto({"espejar": True, "realce": True}, "720:1280:240:0", 720)
    assert f[:2] == ["hflip", "crop=720:1280:240:0"] and "crop=1080:1920" in f and "eq=saturation=1.08" in f
    assert not any(x.startswith(("setpts", "minterpolate", "vidstab", "fps")) for x in f)


def test_fotograma_de_una_toma_pegada_al_final_no_se_pasa_del_video():
    from analizar_referencia import instante
    assert instante(2.0, 4.0, 11.1) == 3.0
    assert instante(11.067, 11.1, 11.1) == pytest.approx(10.95)   # «C2vREQ1xmgg»: pedía 11,084 s y ffmpeg no devolvía cuadro
    assert instante(0.0, 0.1, 0.1) == 0.0


def test_encabezado_largo_va_en_dos_lineas():
    from armar_pop import encabezado
    corto = encabezado({"texto": "¿Y si fue al revés?"}, "x-a", 0.0, 5.0, [])
    largo = encabezado({"texto": "Yo misma me saqué turno a Salón Demo"}, "x-b", 0.0, 5.0, [])   # 37 caracteres: se salía por los costados
    assert 'class="clip encabezado"' in corto and 'class="clip encabezado largo"' in largo


def test_la_sombra_de_un_titulo_entra_con_el_texto():
    from armar_pop import entrada_sombra
    tw = entrada_sombra("x-gancho", 2.0)
    assert '"--sombra": 0' in tw and '"--sombra": 1' in tw and tw.endswith(", 2.030);")


def test_encabezado_con_tam_propio():
    from armar_pop import encabezado
    assert 'style="font-size: 58px"' in encabezado({"texto": "Yo misma me saqué turno a Salón Demo", "tam": 58}, "x", 0.0, 5.0, [])
    assert "font-size" not in encabezado({"texto": "¿Y si fue al revés?"}, "x", 0.0, 5.0, [])


# ---------------------------------------------------------------- retoque.afinar

def barra(ancho=200, alto=200, x0=60, x1=140):
    """Una barra blanca vertical sobre negro: el «brazo» de los tests."""
    im = np.zeros((alto, ancho, 3), np.uint8)
    im[:, x0:x1] = 255
    return im


def test_afinar_angosta_la_barra_y_no_toca_lo_lejano():
    from retoque import afinar
    im = barra()
    # el borde derecho (x=140) se corre 10 px a la izquierda a la altura del centro
    out = afinar(im, [{"x": 0.7, "y": 0.5, "radio": 0.2, "dx": -0.05, "dy": 0}])
    blancos = lambda fila: int((out[fila, :, 0] > 127).sum())
    assert blancos(100) <= 80 - 8          # en el centro, ~10 px menos
    assert blancos(0) == 80                # fuera del radio, igual que antes
    assert (out[100, :50] == 0).all()      # el otro borde no se movió


def test_afinar_frena_si_la_imagen_se_pliega():
    from retoque import afinar
    with pytest.raises(SystemExit, match="se pliega"):
        afinar(barra(), [{"x": 0.7, "y": 0.5, "radio": 0.1, "dx": -0.05, "dy": 0}])   # 10 px con radio 20


# ---------------------------------------------------------------- armar_pop.transicion

def test_temblor_es_un_solo_tween_que_vuelve_al_centro_sin_mostrar_bordes():
    import math
    from armar_pop import TEMBLOR, transicion
    tw = []
    assert transicion(3, "temblor", 2.0, tw) == ""
    assert len(tw) == 1 and tw[0].startswith('tl.fromTo("#t3"')      # uno solo: varios se pisaban (hyperframes check)
    assert "x: 0, y: 0, rotation: 0" in tw[0] and "elastic.out" in tw[0]
    # el rebote llega hasta la sacudida inicial: la escala tiene que cubrir ese corrimiento y el giro
    giro = math.radians(abs(TEMBLOR["giro"]))
    hace_falta = 1 + 2 * abs(TEMBLOR["x"]) / 1080 + (1920 / 1080) * math.sin(giro)
    assert TEMBLOR["escala"] >= hace_falta


def test_humo_tapa_el_corte_con_su_capa():
    from armar_pop import transicion
    tw = []
    capa = transicion(4, "humo", 5.0, tw)
    assert 'id="humo4"' in capa and capa.count("<i ") == 5
    assert any('"#humo4"' in t and t.endswith(", 4.700);") for t in tw)   # aparece antes del corte


def test_entrada_desconocida_frena():
    from armar_pop import transicion
    with pytest.raises(SystemExit, match="entrada desconocida"):
        transicion(1, "humito", 0.0, [])


def test_foto_acostada_por_exif_se_mide_parada(tmp_path):
    # el celular guarda 4000×3000 con orientación 6: ffmpeg la endereza y el recorte se mide sobre 3000×4000
    from PIL import Image
    src = tmp_path / "foto.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (400, 300)).save(src, exif=exif)
    assert preparar_clips.dimensiones(src) == (300, 400)
    assert preparar_clips.recorte_manual(src, {"arriba": 0, "abajo": 1, "centro_x": 0.5}) == "224:400:38:0"
