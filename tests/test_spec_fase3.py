# -*- coding: utf-8 -*-
"""Tests de la fase 3: PM Brief (SPEC 11), consistencia HTML/PDF (SPEC 12).

    python tests/test_spec_fase3.py
"""

from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from snapshot import (brief, build, consistencia, data,          # noqa: E402
                      indicators, pdf, render)

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


def _docs(f):
    k = f"docs:{f}"
    if k not in _cache:
        s = _snap(f)
        b, log = brief.render_brief(s)
        _cache[k] = (render.render_html(s), b, log)
    return _cache[k]


# ======================= EL BRIEF SALE DE LA MISMA CAPA =====================
def test_el_brief_no_contiene_logica_de_inversion():
    """Cero logica de inversion en el template (SPEC 2): el brief no puede
    aplicar umbrales ni recalcular direcciones."""
    src = io.open("snapshot/brief.py", encoding="utf-8").read()
    for prohibido in ("CONV_ORDEN", "VOTE_HIGH", "VOTE_LOW", "CONTRA_PCT",
                      "ANALOG_DISC_FRAC", "TACTICO_MIN_EXTREMOS",
                      "WOE_CONFIRMA", "PERSIST_EXTREMO_MIN"):
        assert prohibido not in src, f"el brief aplica el umbral {prohibido}"
    assert "votos" not in src, "el brief cuenta votos"


def test_el_brief_lee_del_decision_state():
    for f in FECHAS:
        s = _snap(f)
        assert s.get("decision") is not None
        assert (s["decision"].guia.get("brief") or {}).get("confirmaciones") is not None


# ============================ PAGINACION (SPEC 11) ==========================
def test_el_numero_de_paginas_esta_en_el_rango_del_spec():
    for f in FECHAS:
        _h, _b, log = _docs(f)
        paginas = sum(1 for l in log if not l.strip().startswith("→"))
        fusiones = sum(1 for l in log if "se funde" in l)
        total = paginas - fusiones
        assert 3 <= total <= 4, f"{f}: {total} páginas, fuera de 3-4"


def test_no_queda_ninguna_pagina_casi_vacia_que_pudiera_fundirse():
    """El criterio de SPEC: por debajo de dos tercios se funde. Si una pagina
    queda por debajo, tiene que ser porque NO cabia en ningun vecino."""
    for f in FECHAS:
        s = _snap(f)
        bloques = [brief._b_regimen(s), brief._b_positioning(s),
                   brief._b_vigilar(s), brief._b_cierre(s)]
        paginas, _log = brief.paginar(bloques)
        for i, p in enumerate(paginas):
            if p.fraccion >= brief.FRAC_MIN:
                continue
            ant = paginas[i - 1] if i > 0 else None
            sig = paginas[i + 1] if i + 1 < len(paginas) else None
            cabe = ((ant and ant.lineas + p.lineas <= brief.CAP) or
                    (sig and sig.lineas + p.lineas <= brief.CAP))
            assert not cabe, (
                f"{f}: página {p.n} al {100 * p.fraccion:.0f}% y cabía en un vecino")


def test_el_criterio_de_fusion_es_dos_tercios():
    assert abs(brief.FRAC_MIN - 2 / 3) < 1e-9


def test_ninguna_pagina_se_rellena_artificialmente():
    """Ninguna pagina puede superar la altura util: eso seria desbordar, no
    llenar."""
    for f in FECHAS:
        s = _snap(f)
        bl = [brief._b_regimen(s), brief._b_positioning(s)]
        for b in bl:
            assert b.lineas <= brief.CAP * 1.2


# ============================ CONSISTENCIA (SPEC 12) ========================
def test_ninguna_conclusion_difiere_entre_html_y_brief():
    for f in FECHAS:
        h, b, _ = _docs(f)
        res = consistencia.comparar(_snap(f), h, b)
        assert res["ok"], f"{f}: {consistencia.informe(res)}"
        assert res["total"] >= 10, f"{f}: solo compara {res['total']} valores"


def test_la_comprobacion_de_consistencia_detecta_una_divergencia():
    """Si no muerde, no sirve."""
    f = "2008-09-15"
    h, b, _ = _docs(f)
    s = _snap(f)
    postura = s["postura_general"]["palabra"]
    otra = "pro-riesgo" if postura == "defensiva" else "defensiva"
    # La página 1 escribe la postura en mayúsculas y el comparador normaliza
    # antes de comparar; la mutación tiene que alcanzar las dos formas.
    mutado = b.replace(postura, otra).replace(postura.upper(), otra.upper())
    res = consistencia.comparar(s, h, mutado)
    assert not res["ok"], "no detecta que el brief cambie la postura"


def test_el_tablero_publica_el_resultado_de_consistencia():
    for f in FECHAS:
        h, b, _ = _docs(f)
        s = dict(_snap(f))
        s["consistencia"] = consistencia.comparar(s, h, b)
        comp = {c["label"]: c for c in build._comprobaciones(s)}
        c = comp.get("HTML y PDF: mismas conclusiones")
        assert c is not None and c["estado"] == "ok"


# ============================ CONTENIDO DEL BRIEF ===========================
def test_el_brief_no_lleva_los_42_indicadores():
    """SPEC 11: el detalle completo pertenece al HTML."""
    for f in FECHAS:
        _h, b, _ = _docs(f)
        t = consistencia.texto(b)
        n = sum(1 for d in config.INDICATORS
                if d["label"].lower() in t)
        assert n <= 20, f"{f}: el brief nombra {n} indicadores"


def test_el_brief_no_contiene_pesos_de_cartera():
    """SPEC 17: ni pesos, ni asignacion, ni target returns, ni stop loss."""
    for f in FECHAS:
        _h, b, _ = _docs(f)
        t = consistencia.texto(b)
        for prohibido in ("% de la cartera", "asignación del", "peso objetivo",
                          "stop loss", "target return", "sobreponderar un "):
            assert prohibido not in t, f"{f}: aparece «{prohibido}»"


def test_el_brief_trae_las_secciones_que_pide_el_spec():
    for f in FECHAS:
        _h, b, _ = _docs(f)
        t = consistencia.texto(b)
        # SPEC-4P 19: una sola lengua visual. Los encabezados van en español.
        for sec in ("resumen ejecutivo", "guía de posicionamiento",
                    "disparadores de decisión", "metodología"):
            assert sec in t, f"{f}: falta la sección «{sec}»"


def test_cada_pagina_lleva_numero_y_aviso():
    for f in FECHAS:
        _h, b, _ = _docs(f)
        assert "lectura, no recomendación" in consistencia.texto(b)
        assert b.count('class="ft"') >= 3


# ============================ PDF REAL ======================================
def test_el_pdf_existe_y_tiene_las_paginas_planificadas():
    for f in FECHAS:
        ruta = f"output/snapshot-{f}-brief.pdf"
        assert os.path.isfile(ruta), f"{f}: no se generó PDF"
        n = pdf.paginas(ruta)
        assert n is not None and 3 <= n <= 4, f"{f}: {n} páginas"


def test_una_sola_ejecucion_genera_ambos():
    """El pipeline no tiene un comando aparte para el PDF."""
    src = io.open("run_snapshot.py", encoding="utf-8").read()
    assert "brief.render_brief" in src and "pdf.imprimir" in src
    assert "consistencia.comparar" in src


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
