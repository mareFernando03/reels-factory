"""Duraciones de las tomas, efectos de sonido y ritmo del guion."""

import json

import pytest
import yaml

from audio import eventos
from comun import CIERRE, duraciones
from verificar import chequear_ritmo


# ---------------------------------------------------------------- comun.duraciones

def test_grilla_pareja():
    g = {"bpm": 120, "tomas": [{"n": 1, "beats": 2}, {"n": 2, "beats": 1}]}
    assert duraciones(g) == [1.0, 0.5]


def test_desfase_alarga_la_primera_toma():
    g = {"bpm": 120, "desfase": 0.3, "tomas": [{"n": 1, "beats": 2}, {"n": 2, "beats": 1}]}
    assert duraciones(g) == pytest.approx([1.3, 0.5])


def test_cierre_sin_beats_dura_lo_fijo():
    g = {"bpm": 100, "tomas": [{"n": 1, "beats": 4}, {"n": 2, "cierre": True}]}
    assert duraciones(g) == pytest.approx([2.4, CIERRE])


def test_cierre_con_beats_respeta_el_guion():
    g = {"bpm": 105, "tomas": [{"n": 1, "beats": 2}, {"n": 2, "cierre": True, "beats": 3.5}]}
    assert duraciones(g)[-1] == pytest.approx(2.0)


def test_escenas_cuentan_como_tomas():
    g = {"bpm": 100, "escenas": [{"n": 1, "beats": 5}, {"n": 2, "beats": 4}]}
    assert duraciones(g) == pytest.approx([3.0, 2.4])


def _con_beats(tmp_path, beats, inicio=0):
    (tmp_path / "audio.json").write_text(json.dumps({"beats": beats}), encoding="utf-8")
    return {"bpm": 120, "musica": {"analisis": "audio.json", "inicio": inicio}}


def test_cortes_en_los_beats_reales(tmp_path):
    g = _con_beats(tmp_path, [0.02, 0.5, 1.02, 1.49, 2.0])
    g["tomas"] = [{"n": 1, "beats": 2}, {"n": 2, "beats": 2}]
    # la canción no es pareja: el segundo corte cae en 1,02 s, no en 1,0
    assert duraciones(g, tmp_path) == pytest.approx([1.02, 0.98])


def test_primer_beat_tarde_alarga_la_primera_toma(tmp_path):
    # el primer beat está a 0,3 s (más de medio beat): la primera toma lo incluye
    g = _con_beats(tmp_path, [0.3, 0.8, 1.3, 1.8])
    g["tomas"] = [{"n": 1, "beats": 2}, {"n": 2, "beats": 1}]
    assert duraciones(g, tmp_path) == pytest.approx([0.8, 0.5])


def test_inicio_de_la_cancion_corre_la_grilla(tmp_path):
    g = _con_beats(tmp_path, [9.0, 10.0, 10.5, 11.0, 11.5], inicio=10.0)
    g["tomas"] = [{"n": 1, "beats": 2}]
    assert duraciones(g, tmp_path) == pytest.approx([1.0])


def test_mas_alla_de_la_cancion_sigue_la_grilla_teorica(tmp_path):
    g = _con_beats(tmp_path, [0.0, 0.5])
    g["tomas"] = [{"n": 1, "beats": 1}, {"n": 2, "beats": 3}]
    assert duraciones(g, tmp_path) == pytest.approx([0.5, 1.5])


def test_medio_beat_se_interpola_en_la_grilla_real(tmp_path):
    # cierre de 3,5 beats (pochoclos): termina a mitad de camino entre el 5.º y el 6.º beat real
    g = _con_beats(tmp_path, [0.0, 0.5, 1.0, 1.6, 2.0, 2.4, 3.0])
    g["tomas"] = [{"n": 1, "beats": 2}, {"n": 2, "cierre": True, "beats": 3.5}]
    assert duraciones(g, tmp_path) == pytest.approx([1.0, 1.7])


def test_cierre_sin_beats_con_cancion(tmp_path):
    g = _con_beats(tmp_path, [0.0, 0.5, 1.0])
    g["tomas"] = [{"n": 1, "beats": 2}, {"n": 2, "cierre": True}]
    assert duraciones(g, tmp_path) == pytest.approx([1.0, CIERRE])


# ---------------------------------------------------------------- audio.eventos

def test_eventos_por_entrada_de_toma():
    g = {"bpm": 120, "tomas": [
        {"n": 1, "beats": 2, "entrada": "corte"},
        {"n": 2, "beats": 2, "entrada": "golpe"},
        {"n": 3, "beats": 2, "entrada": "barrido"},
        {"n": 4, "beats": 2, "entrada": "luz"},
        {"n": 5, "cierre": True},
    ], "textos": [{"id": "p", "tipo": "sticker", "tomas": [2]}]}
    ev = sorted(eventos(g, 0.5))
    assert ("tic", 1.0) in ev              # golpe común: un tic (el impacto se guarda)
    assert ("whoosh", pytest.approx(1.65)) in ev   # barrido: 0,35 s antes del corte
    assert ("brillo", pytest.approx(2.95)) in ev   # luz: apenas antes
    assert ("pop", 1.0) in ev              # sticker de la toma 2
    assert {t for t, _ in ev} >= {"subida", "brillo", "pop"}   # cierre


def test_primer_corte_no_lleva_whoosh():
    g = {"bpm": 120, "tomas": [{"n": 1, "beats": 2, "entrada": "barrido"}]}
    assert eventos(g, 0.5) == []


def test_sonidos_contados_desde_la_escena():
    g = {"bpm": 100, "escenas": [{"n": 1, "beats": 5}, {"n": 2, "beats": 4}],
         "sonidos": [{"escena": 2, "beat": 1, "tipo": "pop"}, {"beat": 2, "tipo": "pop", "ajuste": 0.1}]}
    beat = 0.6
    ev = eventos(g, beat)
    assert ("pop", pytest.approx(3.0 + beat)) in ev     # escena 2 arranca a los 3 s
    assert ("pop", pytest.approx(2 * beat + 0.1)) in ev  # sin escena: desde el principio


# ---------------------------------------------------------------- verificar.chequear_ritmo

def _pedido(tmp_path, guion):
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "guion.yaml").write_text(yaml.safe_dump(guion, allow_unicode=True), encoding="utf-8")
    return tmp_path


def test_ritmo_en_rango(tmp_path):
    # proceso: 18-25 s, tomas de 1-2 s, revelado 3-4 s, 100-115 bpm
    tomas = [{"n": i, "beats": 3} for i in range(1, 12)] + [{"n": 12, "beats": 6, "rol": "revelado"}, {"n": 13, "cierre": True}]
    r = {n.split()[0]: ok for n, ok, _ in chequear_ritmo(_pedido(tmp_path, {"marca": "salon-demo", "formato": "proceso", "bpm": 105, "tomas": tomas}))}
    assert r == {"R2": True, "R3": True, "O12": True}


def test_ritmo_apurado_falla(tmp_path):
    tomas = [{"n": i, "beats": 1} for i in range(1, 14)] + [{"n": 14, "cierre": True, "beats": 4}]
    r = {n.split()[0]: ok for n, ok, _ in chequear_ritmo(_pedido(tmp_path, {"marca": "salon-demo", "formato": "proceso", "bpm": 120, "tomas": tomas}))}
    assert r == {"R2": False, "R3": True, "O12": False}   # 4 beats a 120 bpm = 2,0 s


def test_cierre_largo_falla_r3(tmp_path):
    tomas = [{"n": 1, "beats": 30}, {"n": 2, "cierre": True, "beats": 4}]
    r = {n.split()[0]: (ok, v) for n, ok, v in chequear_ritmo(_pedido(tmp_path, {"marca": "salon-demo", "formato": "proceso", "bpm": 100, "tomas": tomas}))}
    assert r["R3"] == (False, "2.40 s")


def test_guion_viejo_se_informa_sin_romperse(tmp_path):
    g = {"marca": "salon-demo", "formato": "transformacion", "bpm": 123, "ritmo": "3-3-2-2-2-1-1 beats: …",
         "tomas": [{"n": 1, "beats": 3}]}
    (resultado,) = chequear_ritmo(_pedido(tmp_path, g))
    assert resultado[1] is False and "formato viejo" in resultado[0]


def test_formato_sin_preset(tmp_path):
    (resultado,) = chequear_ritmo(_pedido(tmp_path, {"marca": "salon-demo", "formato": "inventado", "bpm": 100, "tomas": []}))
    assert resultado[1] is False and "sin preset" in resultado[0]


def test_impacto_solo_en_el_revelado_o_si_el_guion_lo_pide():
    g = {"bpm": 120, "tomas": [
        {"n": 1, "beats": 2},
        {"n": 2, "beats": 2, "entrada": "golpe", "rol": "revelado"},
        {"n": 3, "beats": 2, "entrada": "golpe", "sonido": "whoosh"},
        {"n": 4, "beats": 2, "entrada": "golpe"},
    ]}
    ev = eventos(g, 0.5)
    assert ("impacto", 1.0) in ev and ("whoosh", 2.0) in ev and ("tic", 3.0) in ev
    assert sum(1 for t, _ in ev if t == "impacto") == 1
