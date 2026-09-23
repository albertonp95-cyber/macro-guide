# -*- coding: utf-8 -*-
"""Tests de la fase 2 de SPEC.md: guia de decision.

Sobre datos estructurados (SPEC 15). El test central es el de la regla dura:
el TIMING no puede moverse por un indicador de horizonte de regimen.

    python tests/test_spec_fase2.py
"""

from __future__ import annotations

import copy
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                             # noqa: E402
from snapshot import build, data, decision, indicators     # noqa: E402

FECHAS = config.VALIDATION_DATES
_cache: dict = {}


def _ctx():
    if "ctx" not in _cache:
        macro, _ = data.load_macro()
        px = data.load_prices()
        panel = indicators.build_panel(macro, px)
        _cache["ctx"] = build.Context(panel, prices=px, macro=macro)
    return _cache["ctx"]


def _snap(f):
    if f not in _cache:
        _cache[f] = build.build_snapshot(_ctx(), f)
    return _cache[f]


def _guia(f):
    return _snap(f)["decision"].guia


# ============================ REGLA DURA: TIMING = SOLO TACTICO =============
def test_timing_solo_usa_indicadores_tacticos():
    """Si alteramos TODOS los indicadores que NO son tacticos, el timing no
    puede moverse. Es la regla de SPEC 3.2, y sin este test se degrada sola."""
    H = {d["key"]: d["horizon"] for d in config.INDICATORS}
    for f in FECHAS:
        snap = _snap(f)
        setup = decision.setup_tactico(snap)
        antes, _ = decision.timing_global(snap, setup)

        mut = copy.deepcopy(snap)
        tocados = 0
        for pil in mut["tablero"]:
            for fila in pil["filas"]:
                if H.get(fila["key"]) == config.HORIZON_TIMING:
                    continue
                fila["op"] = 100.0 - (fila["op"] if np.isfinite(fila["op"]) else 50.0)
                fila["pct"] = 100.0 - (fila["pct"] if np.isfinite(fila["pct"]) else 50.0)
                fila["votos"] = {k: -v for k, v in fila["votos"].items()}
                tocados += 1
        assert tocados > 0
        setup_m = decision.setup_tactico(mut)
        despues, _ = decision.timing_global(mut, setup_m)
        assert antes == despues, (
            f"{f}: el timing cambio ({antes} -> {despues}) al tocar {tocados} "
            f"indicadores NO tacticos")


def test_el_timing_de_cada_tema_tambien_ignora_lo_no_tactico():
    H = {d["key"]: d["horizon"] for d in config.INDICATORS}
    tac = {k for k, v in H.items() if v == config.HORIZON_TIMING}
    snap = _snap("2008-09-15")
    usados = {f["key"] for f in decision.filas_tacticas(snap)}
    assert usados and usados <= tac, "el timing mira indicadores no tacticos"


# ============================ DIMENSIONES SEPARADAS =========================
def test_timing_no_es_una_copia_de_la_conviccion():
    """SPEC 5.3: el timing es una dimension INDEPENDIENTE. Si en las cuatro
    fechas se moviera con la conviccion, seria redundante."""
    pares = []
    for f in FECHAS:
        pg = _snap(f)["postura_general"]
        pares.append((pg["conviccion"], _guia(f)["timing"]))
    convs = {c for c, _ in pares}
    tims = {t for _, t in pares}
    # misma conviccion con timings distintos en algun punto
    por_conv: dict = {}
    for c, t in pares:
        por_conv.setdefault(c, set()).add(t)
    assert any(len(v) > 1 for v in por_conv.values()) or len(tims) > 1, (
        f"timing y conviccion se mueven juntos siempre: {pares}")


def test_postura_conviccion_y_timing_son_campos_distintos():
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            assert "postura" in t and "conviccion" in t and "timing" in t
            assert t["timing"] in config.TIMING_ESTADOS


# ============================ SETUP TACTICO =================================
def test_el_setup_tactico_aparece_en_los_dos_casos_de_libro():
    """SPEC 14 / pregunta (b): si en 2008-09 y 2020-03 no marca rebote
    contrario con sobreventa extrema, el detector no funciona."""
    for f in ("2008-09-15", "2020-03-16"):
        s = _guia(f)["setup"]
        assert s["existe"], f"{f}: no detecta setup tactico"
        assert s["direccion"] == "rebote", f"{f}: deberia ser rebote contrario"
        assert s["contra_regimen"], f"{f}: el rebote va contra un regimen defensivo"


def test_el_espejo_de_2021_marca_reversion():
    s = _guia("2021-11-01")["setup"]
    assert s["existe"] and s["direccion"] == "reversion"
    assert _guia("2021-11-01")["timing"] == "extendido"


def test_un_setup_tactico_no_cambia_el_regimen():
    """Una condicion contraria NO es un cambio de regimen (SPEC 4.4)."""
    for f in FECHAS:
        g = _guia(f)
        if g["setup"]["existe"] and g["setup"]["contra_regimen"]:
            pg = _snap(f)["postura_general"]["palabra"]
            # el regimen sigue siendo el suyo pese al setup contrario
            assert pg in ("pro-riesgo", "defensiva", "mixta")
            assert g["setup"]["direccion"] in ("rebote", "reversion")


# ============================ TRIGGERS ======================================
def test_los_cuatro_bloques_existen():
    for f in FECHAS:
        trg = _guia(f)["triggers"]
        for b in ("confirma", "debilita", "invalida", "tactico"):
            assert b in trg, f"{f}: falta el bloque {b}"


def test_ningun_trigger_futuro_esta_ya_activado():
    """SPEC 12: un trigger no puede mostrarse como futuro si ya esta activado."""
    for f in FECHAS:
        for b, items in _guia(f)["triggers"].items():
            for t in items:
                if t.get("ya"):
                    assert "ya activado" in (t.get("alcance") or "") or b == "tactico"


def test_la_alcanzabilidad_se_reporta_en_sigmas():
    """SPEC 6: hay que poder ver que un trigger exige un movimiento imposible."""
    vistos = 0
    for f in FECHAS:
        for b, items in _guia(f)["triggers"].items():
            for t in items:
                if t.get("sigmas") is not None:
                    vistos += 1
                    assert t["sigmas"] >= 0
                    assert t["alcanzable"] == (t["sigmas"] <= config.TRIGGER_SIGMA_MAX)
    assert vistos > 0, "ningun trigger reporta alcanzabilidad"


def test_cada_trigger_declara_persistencia_y_horizonte():
    for f in FECHAS:
        for b, items in _guia(f)["triggers"].items():
            for t in items:
                assert t.get("persistencia")
                assert t.get("horizonte")


# ============================ HORIZONTES / EXPRESION ========================
def test_hay_lectura_por_cada_horizonte():
    for f in FECHAS:
        hz = _guia(f)["horizontes_lectura"]
        assert set(hz) == set(config.HORIZONS)
        for h, v in hz.items():
            assert v["lectura"] in ("pro-riesgo", "defensiva", "neutral", "sin dato")


def test_expresion_preferida_no_se_inventa_sin_evidencia():
    """SPEC 3.4 / 5.5, ahora con procedencia (SPEC-2P 7): sin direccion o sin
    conviccion, «—»; y publicada SOLO si hay senales que la sostengan."""
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            fav, evi = t["favorecer"], t["evitar"]
            assert isinstance(fav, dict) and isinstance(evi, dict), (
                f"{f}/{t['key']}: la expresion no viaja con su procedencia")
            if t["dir_tipo"] == "neutral" or not t["conviccion"]:
                assert fav["text"] == "—" and evi["text"] == "—", (
                    f"{f}/{t['key']}: inventa expresion sin evidencia")
                assert not fav["supported_by"] and not evi["supported_by"]
            else:
                # publicada si y solo si tiene apoyo: no hay un tercer caso
                for campo, e in (("favorecer", fav), ("evitar", evi)):
                    publicada = e["text"] != "—"
                    assert publicada == bool(e["supported_by"]), (
                        f"{f}/{t['key']}/{campo}: publicada={publicada} pero "
                        f"apoyos={e['supported_by']}")


def test_la_expresion_declara_de_donde_sale():
    """SPEC-2P 7: texto, senales que lo apoyan, conviccion y tipo de fuente."""
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            for campo in ("favorecer", "evitar"):
                e = t[campo]
                for k in ("text", "supported_by", "confidence", "source_type"):
                    assert k in e, f"{f}/{t['key']}/{campo}: falta «{k}»"
                if e["supported_by"]:
                    assert e["source_type"] == config.EXPRESION_FUENTE
                    assert e["confidence"] in ("alta", "media", "baja")
                    assert len(e["supported_labels"]) == len(e["supported_by"])


def test_la_expresion_es_relativa():
    """Una expresion preferida compara dos lados; no es una orden de compra.

    SEMANTIC-PASS 17: el dólar queda fuera. Dejó de ser una dimensión de
    asignación --donde «A > B» es la forma correcta-- y pasó a ser un overlay
    de divisa: lo que publica es la IMPLICACIÓN para la exposición
    internacional, no una preferencia entre dos activos. Exigirle un «>» le
    obligaría a volver a decir «no dólar > dólar», que es justo la frase que el
    pase vino a quitar.
    """
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            if config.DIMENSION_GRUPO.get(t["key"]) == "overlay":
                continue
            txt = t["favorecer"]["text"]
            if txt != "—":
                assert ">" in txt, f"{txt} no es relativa"


# ============================ MANDATO (FIJO) ================================
def test_la_tabla_de_mandato_es_fija():
    """No se genera por snapshot, no cambia con los datos (SPEC 9)."""
    tablas = [tuple(map(tuple, _snap(f)["decision"].guia["mandate"])) for f in FECHAS]
    assert len(set(tablas)) == 1, "la tabla de mandato cambia entre fechas"
    assert tablas[0] == tuple(map(tuple, config.MANDATE_TRANSLATION))


def test_no_hay_pesos_de_cartera_en_el_documento():
    """SPEC 17: ni pesos, ni asignacion, ni target returns."""
    html = io.open("output/snapshot-2008-09-15.html", encoding="utf-8").read().lower()
    for prohibido in ("% de la cartera", "asignación del", "peso objetivo",
                      "stop loss", "target return"):
        assert prohibido not in html, f"aparece «{prohibido}»"


# ============================ CLUSTER (PARALELO) ============================
def test_el_cluster_score_es_solo_paralelo():
    """SPEC 10: la metrica existe para comparar, pero NO decide."""
    for f in FECHAS:
        cs = _guia(f)["cluster_score"]
        assert cs, f"{f}: sin metrica paralela"
        post = {p["key"]: p for p in _snap(f)["postura"]}
        for c in cs:
            # la direccion publicada sigue siendo la del voto por indicador
            assert post[c["key"]]["dir_tipo"] == c["dir_actual"]


# ------------------------------------------------------------------ runner
def _run():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    ok = fallos = 0
    for n, f in fns:
        try:
            f()
            print(f"  PASS  {n}")
            ok += 1
        except AssertionError as e:
            print(f"  FAIL  {n}\n        {e}")
            fallos += 1
        except Exception as e:                      # noqa: BLE001
            print(f"  ERROR {n}\n        {type(e).__name__}: {e}")
            fallos += 1
    print(f"\n{ok} pasados, {fallos} fallidos, {len(fns)} totales")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_run())
