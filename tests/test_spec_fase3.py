# -*- coding: utf-8 -*-
"""Tests del SEGUNDO OUTPUT: la Estrategia semanal, y su consistencia con el
HTML (SPEC 12).

Sustituye a los tests del PM Brief de tres páginas. Los que medían su
empaquetador de bloques --dos tercios de pagina, no rellenar, no dejar una
pagina casi vacia-- ya no describen nada: el documento nuevo tiene numero de
paginas LIBRE y cada seccion ocupa lo que necesita. En su lugar se comprueba lo
que si es exigible con paginacion libre: que esten las siete secciones, que una
seccion sin contenido lo diga en vez de desaparecer, y que el documento no
crezca sin limite.

    python tests/test_spec_fase3.py
"""

from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from snapshot import (build, consistencia, data, indicators,     # noqa: E402
                      pdf, render, weekly)

FECHAS = config.VALIDATION_DATES
_cache: dict = {}

# Las siete, por su numero y su titulo tal como se imprimen.
SECCIONES = [("01", "La lectura"), ("02", "Posicionamiento cross-asset"),
             ("03", "Qué sostiene la lectura"), ("04", "Evidencia de mercado"),
             ("05", "Qué cambió esta semana"),
             ("06", "Lo que aporta el research externo"),
             ("07", "Riesgos de la decisión")]


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
        b, log = weekly.render_weekly(s, render._tape_html(s))
        _cache[k] = (render.render_html(s), b, log)
    return _cache[k]


# ================== EL SEMANAL SALE DE LA MISMA CAPA ========================
def test_el_semanal_no_contiene_logica_de_inversion():
    """Cero lógica de inversión en el template (SPEC 2): el documento no puede
    aplicar un umbral ni contar votos por su cuenta."""
    src = io.open("snapshot/weekly.py", encoding="utf-8").read()
    src = re.sub(r'"""(.*?)"""', " ", src, flags=re.S)     # sin docstrings
    src = "\n".join(l.split("#")[0] for l in src.splitlines())
    # Y sin las cadenas que el documento IMPRIME: la nota que explica que el
    # estilo y la beta no son dos votos independientes es texto publicado, no
    # aritmética de votos, y buscar la palabra la prohibía también ahí. Lo que
    # sí delata lógica de inversión es que el template toque estas tablas.
    src = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", " ", src)
    for prohibido in ("CONV_CLARA", "CONV_EMPATE", "POSTURA_MIN_DEPTH",
                      "STATE_BANDS", "TRIGGER_SIGMA", "INDICATOR_ASSET_MAP",
                      "SESGO_PRESENTACION"):
        assert prohibido not in src, (
            f"el semanal usa {prohibido}: eso es lógica de inversión y va en "
            f"la capa, no en el template")


def test_el_semanal_lee_del_decision_state():
    for f in FECHAS:
        s = _snap(f)
        assert s.get("decision") is not None
        assert (s["decision"].guia.get("temas") or []), f"{f}: sin temas"


def test_las_siete_secciones_estan_y_en_orden():
    """Ninguna se omite. Si una no tiene nada que decir, lo dice."""
    for f in FECHAS:
        tx = consistencia.texto(_docs(f)[1])
        pos = []
        for n, titulo in SECCIONES:
            i = tx.find(consistencia._norm(titulo))
            assert i >= 0, f"{f}: falta la sección {n} · {titulo}"
            pos.append(i)
        assert pos == sorted(pos), f"{f}: las secciones salen desordenadas"


def test_una_seccion_sin_contenido_lo_dice_en_una_linea():
    """La ausencia también es información: la sección se queda, con su frase.

    Se comprueba sobre 2008-09-15, que no tiene snapshot anterior y por tanto
    no tiene nada que contar en «Qué cambió esta semana».
    """
    s = _snap("2008-09-15")
    doc = _docs("2008-09-15")[1]
    tx = consistencia.texto(doc)
    assert consistencia._norm("Qué cambió esta semana") in tx, (
        "la sección desapareció en vez de declararse vacía")
    if not (s.get("cambios") or {}).get("disponible"):
        assert consistencia._norm("no hay un snapshot anterior") in tx, (
            "no dice por qué la sección está vacía")


def test_el_numero_de_paginas_es_libre_pero_no_infinito():
    """Paginas LIBRES no es lo mismo que sin control: un documento de veinte
    paginas no lo lee nadie, y uno de una no puede llevar siete secciones."""
    for f in FECHAS:
        _h, b, _log = _docs(f)
        p = _paginas(f, b)
        assert 3 <= p <= 12, f"{f}: {p} páginas, fuera de un rango razonable"


def _paginas(f, doc) -> int:
    k = f"pag:{f}"
    if k not in _cache:
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f"_t-{f}.html")
        pdfp = tmp[:-5] + ".pdf"
        io.open(tmp, "w", encoding="utf-8").write(doc)
        ok, _det = pdf.imprimir(tmp, pdfp)
        _cache[k] = pdf.paginas(pdfp) if ok else 0
        for x in (tmp, pdfp):
            try:
                os.remove(x)
            except OSError:
                pass
    return _cache[k]


# ===================== CONSISTENCIA CON EL HTML =============================
def test_ninguna_conclusion_difiere_entre_html_y_el_semanal():
    for f in FECHAS:
        h, b, _ = _docs(f)
        res = consistencia.comparar(_snap(f), h, b)
        assert res["ok"], f"{f}: {consistencia.informe(res)}"


def test_la_comprobacion_de_consistencia_detecta_una_divergencia():
    """Un comprobador que siempre dice que sí no comprueba nada."""
    f = FECHAS[0]
    h, b, _ = _docs(f)
    pg = (_snap(f).get("postura_general") or {}).get("palabra") or ""
    otra = "defensiva" if pg == "pro-riesgo" else "pro-riesgo"
    # Sin distinguir mayúsculas: la postura se imprime también en grande y en
    # versalitas, y sustituir sólo la minúscula dejaba la otra en pie.
    roto = re.sub(re.escape(pg), otra, b, flags=re.I)
    res = consistencia.comparar(_snap(f), h, roto)
    assert not res["ok"], "no detecta que el semanal cambie la postura"


def test_el_tablero_publica_el_resultado_de_consistencia():
    for f in FECHAS:
        h, b, _ = _docs(f)
        res = consistencia.comparar(_snap(f), h, b)
        assert "total" in res and res["total"] > 0
        assert consistencia.informe(res)


# ========================= LO QUE NO PUEDE LLEVAR ===========================
def test_el_semanal_no_lleva_los_42_indicadores():
    """No es el tablero: los 42 viven en el HTML."""
    for f in FECHAS:
        tx = consistencia.texto(_docs(f)[1])
        n = sum(1 for k in config.INDICATORS
                if consistencia._norm(k["label"]) in tx)
        assert n < 20, f"{f}: {n} indicadores; esto es el tablero, no el semanal"


def test_el_semanal_no_contiene_pesos_de_cartera():
    """Y tampoco el lenguaje que suena a orden (SEMANTIC-PASS 32)."""
    malas = ("sobreponderar", "infraponderar", "asignación de", "% de cartera",
             "peso objetivo", "comprar", "vender")
    for f in FECHAS:
        tx = consistencia.texto(_docs(f)[1])
        for m in malas:
            assert consistencia._norm(m) not in tx, f"{f}: dice «{m}»"


def test_el_pie_lleva_la_huella_de_los_datos():
    """Dos copias del mismo día generadas antes y después de una revisión
    tienen que distinguirse mirando el documento."""
    for f in FECHAS:
        s, doc = _snap(f), _docs(f)[1]
        h = s.get("huella") or {}
        assert h.get("codigo"), f"{f}: el estado no trae huella"
        assert h["codigo"] in doc, f"{f}: el pie no publica la huella"
        assert "Lectura, no recomendación" in doc, f"{f}: falta el aviso del pie"


def test_una_sola_ejecucion_genera_ambos():
    """El pipeline no tiene un comando aparte para el PDF."""
    src = io.open("run_snapshot.py", encoding="utf-8").read()
    assert "weekly.render_weekly" in src and "pdf.imprimir" in src
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
        except Exception as e:                                   # noqa: BLE001
            print(f"  ERROR {n}\n        {type(e).__name__}: {e}")
            fallos += 1
    print(f"\n{ok} pasados, {fallos} fallidos, {len(fns)} totales")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_run())
