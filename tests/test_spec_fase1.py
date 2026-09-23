# -*- coding: utf-8 -*-
"""Tests de la fase 1 de SPEC.md.

Sobre DATOS ESTRUCTURADOS, nunca sobre el texto narrativo exacto (SPEC 15): si
manana cambia una palabra de la prosa, estos tests no deben romperse; si cambia
una DECISION o vuelve uno de los tres bugs, si.

    python tests/test_spec_fase1.py        (o: python -m pytest tests/)
"""

from __future__ import annotations

import io
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                    # noqa: E402
from snapshot import build, data, decision, indicators, scoring  # noqa: E402

FECHAS = config.VALIDATION_DATES                  # 2008 / 2020 / 2021 / 2022
CONTEXT_PILLARS = set(config.CONTEXT_PILLARS)

_cache: dict = {}


def _ctx():
    if "ctx" not in _cache:
        macro, _ = data.load_macro()
        px = data.load_prices()
        panel = indicators.build_panel(macro, px)
        _cache["ctx"] = build.Context(panel, prices=px, macro=macro)
    return _cache["ctx"]


def _snap(fecha):
    if fecha not in _cache:
        _cache[fecha] = build.build_snapshot(_ctx(), fecha)
    return _cache[fecha]


# ------------------------------------------------- horizontes (SPEC 3.2 / 5.4)
def test_los_42_indicadores_declaran_horizonte():
    assert len(config.INDICATORS) == 42
    for d in config.INDICATORS:
        assert d.get("horizon") in config.HORIZONS, f"{d['key']} sin horizonte valido"


def test_el_timing_solo_puede_usar_indicadores_tacticos():
    tact = [d["key"] for d in config.INDICATORS
            if d["horizon"] == config.HORIZON_TIMING]
    assert tact, "no hay indicadores tacticos: el timing de la fase 2 no tendria insumo"
    assert config.HORIZON_TIMING == "tactical"
    # un indicador de regimen nunca puede colarse como tactico
    assert "sahm" not in tact and "cpi_yoy" not in tact
    assert "vix" in tact, "el VIX habla de semanas: debe ser tactico"


# --------------------------------------------------- DecisionState (SPEC 2)
def test_decision_state_se_construye_en_todas_las_fechas():
    for f in FECHAS:
        ds = _snap(f)["decision"]
        assert isinstance(ds, decision.DecisionState)
        assert "riesgo" in ds.ejes and "ciclo" in ds.ejes
        assert isinstance(ds.postura, list) and ds.postura
        assert set(ds.horizontes) == set(config.HORIZONS)


def test_valores_compartidos_coinciden_con_el_snapshot():
    """Lo que consumiran HTML y PDF es el mismo numero que publica el tablero."""
    for f in FECHAS:
        snap = _snap(f)
        vc = snap["decision"].valores_compartidos()
        eje = next(e for e in snap["ejes"] if e["key"] == "riesgo")
        assert abs(vc["riesgo_nivel"] - eje["level"]) < 1e-9
        assert vc["regimen_riesgo"] == snap["titular"]["estado"]
        assert vc["postura"] == snap["postura_general"]["palabra"]


def test_el_render_no_decide_quien_discrepa():
    """La decision vive en la capa, no en la plantilla (SPEC 2)."""
    src = io.open("snapshot/render.py", encoding="utf-8").read()
    assert "ANALOG_DISC_FRAC" not in src, "un umbral de inversion vive en el render"
    dec = io.open("snapshot/decision.py", encoding="utf-8").read()
    assert "config.ANALOG_DISC_FRAC" in dec


# ------------------------------------------- BUG 2: risk axis direction
def test_band_label_no_invierte_el_sentido_fuera_de_rango():
    """Un percentil por DEBAJO del suelo no puede etiquetarse euforia."""
    suelo = config.STATE_BANDS[0][2]
    techo = config.STATE_BANDS[-1][2]
    assert scoring.band_label(-0.1) == suelo
    assert scoring.band_label(-50) == suelo
    assert scoring.band_label(101) == techo
    assert scoring.band_label(1e6) == techo


def test_la_proyeccion_del_clima_sigue_la_direccion_del_movimiento():
    for f in FECHAS:
        snap = _snap(f)
        r = snap["riesgo"]
        i_hoy = scoring.band_index(r["hist_pct"])
        for e in snap.get("que_puede_pasar") or []:
            if e.get("tipo") != "clima":
                continue
            assert "~0 semanas" not in e["texto"], f"{f}: proyeccion a ~0 semanas"
            destino = next((b[2] for b in config.STATE_BANDS if b[2] in e["texto"]), None)
            i_dst = next((k for k, b in enumerate(config.STATE_BANDS)
                          if b[2] == destino), None)
            if i_hoy is None or i_dst is None or not np.isfinite(r["d1m"]):
                continue
            if r["d1m"] < 0:
                assert i_dst < i_hoy, f"{f}: el eje cae y proyecta hacia arriba"
            elif r["d1m"] > 0:
                assert i_dst > i_hoy, f"{f}: el eje sube y proyecta hacia abajo"


def test_2008_no_proyecta_euforia():
    """Regression: cayendo desde p0.6 no se llega a euforia."""
    txt = " ".join(e["texto"] for e in _snap("2008-09-15")["que_puede_pasar"])
    assert "euforia" not in txt.lower()


# ------------------------------------------ BUG 3: risk score inconsistency
def test_grafico_y_panel_muestran_el_mismo_nivel():
    for f in FECHAS:
        snap = _snap(f)
        ser = snap["serie_puntuacion"]["series"]
        for e in snap["ejes"]:
            pts = ser.get(e["key"]) or []
            assert pts, f"{f}: {e['key']} sin serie"
            fecha, valor = pts[-1]
            assert abs(valor - e["level"]) < 0.5, (
                f"{f}: {e['key']} panel={e['level']:.1f} grafico={valor:.1f}")
            assert fecha == snap["asof"], (
                f"{f}: el grafico termina en {fecha}, no en {snap['asof']}")


# ------------------------------------------- BUG 1: historical analog window
def test_la_ventana_de_analogos_no_esta_hardcodeada():
    src = io.open("snapshot/render.py", encoding="utf-8").read()
    assert "21 años" not in src, "la ventana sigue escrita a mano en el render"


def test_la_ventana_sale_del_dato_y_respeta_el_futuro_exigido():
    for f in FECHAS:
        snap = _snap(f)
        m = (snap["analogos"] or {}).get("muestra") or {}
        if not m.get("anos"):
            continue
        tope = snap["asof"] - pd.Timedelta(days=config.ANALOG_FWD_MIN_DAYS)
        assert m["hasta"] <= tope, f"{f}: la ventana no deja 12 meses de futuro"
        assert m["desde"] < m["hasta"]
        assert 0 < m["anos"] < 40


def test_2008_declara_su_ventana_real_no_21_anos():
    m = _snap("2008-09-15")["analogos"]["muestra"]
    assert m["anos"] < 4, f"la ventana real de 2008 es corta (es {m['anos']:.1f})"
    assert m["desde"].year == 2005 and m["hasta"].year == 2007


# ------------------------------------------- selector por relevancia (SPEC 3.1)
def test_la_tension_principal_nunca_sale_de_un_pilar_de_contexto():
    """Posicionamiento e inflacion no entran en ningun eje: no pueden ser la
    tension principal (el bug de la semana de Lehman)."""
    for f in FECHAS:
        ten = _snap(f).get("tension_principal")
        if ten is None:
            continue
        assert ten["pilar"] not in CONTEXT_PILLARS, (
            f"{f}: tension principal en pilar de contexto ({ten['pilar']})")


def test_2008_elige_una_tension_relevante():
    ten = _snap("2008-09-15").get("tension_principal")
    assert ten is not None and ten["pilar"] not in CONTEXT_PILLARS
    assert ten["key"] != "spx_ext_3y", "vuelve a elegir por extremidad"


# --------------------------------------------------- QA checks (SPEC 12)
NUEVOS = ["Mismo concepto, mismo valor",
          "Dirección del eje frente a su etiqueta",
          "Ventana histórica: narrativa frente a dato",
          "Disparadores posibles y no activados",
          "La narrativa cita los mismos números que el estado",
          "HTML y PDF sobre el mismo DecisionState"]


def test_los_checks_de_qa_existen_y_pasan_en_las_cuatro_fechas():
    for f in FECHAS:
        comp = {c["label"]: c for c in _snap(f)["comprobaciones"]}
        for lab in NUEVOS:
            assert lab in comp, f"{f}: falta el check {lab}"
            assert comp[lab]["estado"] != "aviso", (
                f"{f}: {lab} en aviso -- {comp[lab]['nota']}")


def test_check_de_selector_sigue_en_cero():
    for f in FECHAS:
        comp = {c["label"]: c for c in _snap(f)["comprobaciones"]}
        c = comp.get("Afirmaciones que citan indicadores fuera de su pilar")
        assert c and c["valor"] == "0", f"{f}: hay citas fuera de pilar"


# ------------------------------------ clasificaciones y casos sin datos
def test_postura_y_conviccion_respetan_su_taxonomia():
    for f in FECHAS:
        for p in _snap(f)["postura"]:
            assert p["conviccion"] in (None, "alta", "media", "baja")
            assert p["dir_tipo"] in ("mas", "menos", "neutral")
            if p["dir_tipo"] == "neutral":
                assert p["conviccion"] is None, "neutral no puede traer conviccion"
            else:
                assert p["conviccion"] is not None


def test_primer_snapshot_sin_historico_no_rompe():
    """SPEC 3.4: la ausencia de evidencia es una salida valida."""
    snap = build.build_snapshot(_ctx(), "2008-09-15", previo=None)
    assert snap["cambios"]["disponible"] is False
    assert snap["comprobaciones"]


def test_estado_inusual_cuando_no_hay_muestra():
    """2008 no tiene comparables: se dice, no se promedia."""
    a = _snap("2008-09-15")["analogos"]
    assert a.get("sin_analogos") or a.get("inusual")
    assert not a.get("promedio"), "no puede publicarse media sin muestra"


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
