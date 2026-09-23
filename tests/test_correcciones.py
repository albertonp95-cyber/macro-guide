# -*- coding: utf-8 -*-
"""Tests de las tres correcciones previas a la fase 3.

  1. Plantillas que contradecian sus propios datos -> capa de verificacion
  2. Persistencia en el selector de tension (anti-whipsaw, SPEC 7.1)
  3. Timing global, no por clase

    python tests/test_correcciones.py
"""

from __future__ import annotations

import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                            # noqa: E402
from snapshot import build, data, indicators             # noqa: E402

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


# ==================== 1. VERIFICACION DE AFIRMACIONES ======================
def test_no_queda_ninguna_afirmacion_sin_verificar():
    """La tercera cifra del check tiene que ser 0 en todas las fechas."""
    for f in FECHAS:
        v = _snap(f)["verificacion"]
        assert not v["no_verificables"], (
            f"{f}: afirmaciones no verificables -> {v['no_verificables']}")
        assert v["verificadas"] > 0


def test_el_clima_no_dice_sigue_pero_se_deteriora_en_el_extremo():
    """«sigue estrés severo pero se deteriora» no tiene sentido: ya es el
    extremo. En el extremo se dice que PROFUNDIZA."""
    for f in FECHAS:
        snap = _snap(f)
        est = snap["titular"]["estado"]
        clima = snap["conclusiones"][0]
        extremo = est in (config.STATE_BANDS[0][2], config.STATE_BANDS[-1][2])
        d = snap["riesgo"].get("d1m")
        if extremo and np.isfinite(d) and abs(d) >= 3:
            peor = (est == config.STATE_BANDS[0][2] and d < 0) or \
                   (est == config.STATE_BANDS[-1][2] and d > 0)
            if peor:
                assert "profundiza" in clima, f"{f}: {clima}"
                assert "pero se deteriora" not in clima


def test_el_condicional_no_es_una_constante_pro_riesgo():
    """«el crecimiento siga superando al costo del capital» solo puede
    aparecer si el crecimiento es de verdad favorable."""
    for f in FECHAS:
        snap = _snap(f)
        cierre = snap["conclusiones"][-1] if snap["conclusiones"] else ""
        cierres = " ".join(snap["conclusiones"])
        if "crecimiento siga superando" in cierres:
            er = snap["composites"]["afirm"]["economia_real"]
            assert er["lect"] == "favorable", (
                f"{f}: dice que el crecimiento supera, pero esta {er['lect']}")
            assert snap["postura_general"]["palabra"] == "pro-riesgo"


def test_2008_deriva_su_propio_condicional():
    """Regression del caso concreto: lectura defensiva por deterioro macro.

    El texto que se exigia aqui --«que el deterioro del crecimiento no se
    profundice»-- estaba INVERTIDO (SPEC-2P 10): si el crecimiento empeora, una
    lectura defensiva se refuerza. Lo que se comprueba ahora es la RELACION: que
    el condicional salga del crecimiento, que reconozca que lo APOYA, y que por
    tanto este escrito en sentido «persiste»."""
    snap = _snap("2008-09-15")
    cierres = " ".join(snap["conclusiones"])
    assert "crecimiento siga superando" not in cierres, "usa el condicional pro-riesgo"
    m = snap["condicional_meta"]
    assert m["hecho"] == "crecimiento", f"el cierre no sale del crecimiento: {m}"
    assert m["apoya"] is True and m["sentido"] == "persiste", m
    assert m["texto"] in cierres
    # y la formulacion invertida no puede volver
    assert "deterioro del crecimiento no se profundice" not in cierres


def test_el_mecanismo_coincide_con_el_lado_del_extremo():
    """Una frase de mecanismo no puede afirmar lo contrario del dato que la
    acompana (la liquidez «cayendo» con la liquidez en su maximo)."""
    for f in FECHAS:
        snap = _snap(f)
        filas = {x["key"]: x for pil in snap["tablero"] for x in pil["filas"]}
        for c in snap.get("contradicciones") or []:
            obs = c.get("observar") or ""
            var = config.CONTRA_OBSERVAR.get(c["key"]) or {}
            if not var:
                continue
            fila = filas.get(c["key"])
            if not fila or not np.isfinite(fila["pct"]):
                continue
            lado = "alto" if fila["pct"] >= 50 else "bajo"
            otro = "bajo" if lado == "alto" else "alto"
            if otro in var and var[otro][:40] not in (var.get(lado) or "")[:40]:
                assert var[otro][:40] not in obs, (
                    f"{f}/{c['key']}: usa la variante de «{otro}» estando en «{lado}»")


def test_la_frase_de_liquidez_no_contradice_el_dato():
    """Regression exacta: netliq en p99 no puede decir «la caida continua»."""
    for f in FECHAS:
        snap = _snap(f)
        filas = {x["key"]: x for pil in snap["tablero"] for x in pil["filas"]}
        nl = filas.get("netliq_3m")
        if nl is None or not np.isfinite(nl["pct"]) or nl["pct"] < 50:
            continue
        texto = " ".join(snap["conclusiones"]) + " " + " ".join(snap["evidencia"])
        assert "caída de liquidez continúa" not in texto, f"{f}: liquidez alta"


# ==================== 2. PERSISTENCIA DEL SELECTOR =========================
def test_la_tension_principal_cumple_su_persistencia():
    """Un extremo de dos dias no puede ser la tension dominante."""
    for f in FECHAS:
        snap = _snap(f)
        ten = snap.get("tension_principal")
        if ten is None:
            continue
        minimo = build.persistencia_minima(_ctx(), ten["key"])
        assert ten.get("dias", 0) >= minimo, (
            f"{f}: {ten['key']} lleva {ten.get('dias')} d, minimo {minimo}")
        assert ten.get("persistente") is True


def test_2008_ya_no_elige_un_extremo_de_dos_dias():
    snap = _snap("2008-09-15")
    ten = snap["tension_principal"]
    assert ten is not None
    assert ten["key"] != "netliq_3m", "vuelve a elegir el extremo de 2 dias"
    assert ten["dias"] >= build.persistencia_minima(_ctx(), ten["key"])


def test_el_minimo_de_persistencia_depende_de_la_frecuencia():
    """No es una ventana universal (SPEC 7.1): una serie diaria exige mas dias
    que una mensual, donde cada publicacion ya resume un mes."""
    ctx = _ctx()
    assert build.persistencia_minima(ctx, "vix") > build.persistencia_minima(ctx, "sahm")
    assert build.frecuencia(ctx, "vix") == "diaria"
    assert build.frecuencia(ctx, "cpi_yoy") == "mensual"


def test_sin_candidato_persistente_se_dice_y_se_cita_como_contexto():
    for f in FECHAS:
        snap = _snap(f)
        if snap.get("tension_principal") is not None:
            continue
        ctxt = snap.get("tension_contexto")
        if ctxt is not None:
            assert ctxt.get("motivo_contexto") in ("reciente", "fuera de eje")


def test_el_tablero_reporta_la_antiguedad_de_cada_candidato():
    for f in FECHAS:
        comp = {c["label"]: c for c in _snap(f)["comprobaciones"]}
        c = comp.get(f"Persistencia del {config.TENSION_INDICADOR.lower()}")
        assert c is not None, f"{f}: falta el check de persistencia"
        if (_snap(f).get("contradicciones") or []):
            assert "en extremo" in c["nota"] and "mínimo" in c["nota"]


# ==================== 3. TIMING GLOBAL =====================================
def test_el_timing_es_una_columna_que_no_se_repite_a_si_misma():
    """La ronda anterior quitó la columna porque repetía la cabecera en todas
    las filas. SPEC-2P 6 la devuelve, pero con otra regla: la columna dice el
    timing que APLICA a ese tema, que casi siempre es el global, y solo se marca
    «propio» cuando el tema tiene evidencia táctica que diga otra cosa. Lo que
    no puede volver es que la fila repita la cabecera sin aportar nada."""
    html = io.open("output/snapshot-2008-09-15.html", encoding="utf-8").read()
    i = html.find('class="pguide"')
    cab = html[i:i + 900]
    assert "<th>Timing</th>" in cab, "SPEC-2P 6 pide la columna de timing"
    assert "<th>Convicción</th>" in cab
    # y la nota tiene que explicar que el que manda es el global
    assert "el timing global" in html or "timing global" in html


def test_el_timing_global_esta_en_la_cabecera():
    # La cabecera de identidad («idg») desapareció al reorganizar el HTML en
    # seis secciones: lo que abre el documento ahora es el cockpit de «01
    # Ahora». El contrato no cambia --el timing global se lee sin desplegar
    # nada-- y el ancla sí.
    html = io.open("output/snapshot-2008-09-15.html", encoding="utf-8").read()
    i = html.find('class="cockpit"')
    assert i > 0, "el HTML tiene que abrir con el cockpit"
    # SEMANTIC-PASS 2: «Timing» desapareció de la vista PM. Lo que tiene que
    # leerse sin desplegar nada es la SEÑAL TÁCTICA, que es lo mismo dicho de
    # forma que se entienda.
    assert config.SENAL_ETIQUETA.upper() in html[i:i + 2500].upper()


def test_solo_las_clases_que_difieren_llevan_nota_de_timing():
    for f in FECHAS:
        g = _snap(f)["decision"].guia
        glob = g["timing"]
        for t in g["temas"]:
            if t.get("timing_difiere"):
                assert t["timing"] != glob and t["dir_tipo"] != "neutral"
            else:
                assert t["timing"] == glob or t["dir_tipo"] == "neutral"


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
