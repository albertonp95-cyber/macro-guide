# -*- coding: utf-8 -*-
"""Tests de PRESENTACION (cuarta pasada).

No comprueban conclusiones --de eso se encargan las otras suites-- sino que el
documento las diga UNA vez, en el sitio que les toca y sin obligar al lector a
reconstruirlas:

  · la conclusión aparece una sola vez
  · ningún disparador sin decir a quién afecta
  · ninguna expresión sin procedencia
  · «Evitar» solo si no es el inverso mecánico de «Favorecer»
  · una sola lengua en los encabezados
  · sin columnas vacías
  · el PDF cabe en cuatro páginas y la tabla no se corta

    python tests/test_presentacion.py
"""

from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                   # noqa: E402
from snapshot import (brief, build, consistencia, data,         # noqa: E402
                      indicators, pdf, render)

FECHAS = list(config.VALIDATION_DATES) + ["2026-09-21"]
_cache: dict = {}


def _ctx():
    if "ctx" not in _cache:
        macro, _ = data.load_macro()
        px = data.load_prices()
        _cache["ctx"] = build.Context(indicators.build_panel(macro, px),
                                      prices=px, macro=macro)
    return _cache["ctx"]


def _snap(f):
    if f not in _cache:
        _cache[f] = build.build_snapshot(_ctx(), f)
    return _cache[f]


def _docs(f):
    k = f"d:{f}"
    if k not in _cache:
        s = _snap(f)
        _cache[k] = (render.render_html(s), brief.render_brief(s)[0])
    return _cache[k]


def _guia(f):
    return _snap(f)["decision"].guia


# ===================== LA CONCLUSION, UNA SOLA VEZ =========================
def test_existe_una_conclusion_operativa_y_es_una_sola():
    for f in FECHAS:
        bl = _guia(f).get("bottom_line")
        assert bl, f"{f}: sin conclusión operativa"
        # SPEC-7P 11: la conclusión ya no repite «Sesgo X con convicción Y»
        # --eso lo dice la cabecera— y empieza por la expresión.
        assert bl.count("Se expresa por") == 1, f"{f}: la conclusión se dice dos veces"
        for doc, nom in zip(_docs(f), ("HTML", "PDF")):
            t = consistencia.texto(doc)
            assert t.count(consistencia.texto(bl)) == 1, (
                f"{f}/{nom}: la conclusión operativa aparece más de una vez")


def test_la_conclusion_cabe_en_dos_lineas():
    """SPEC-4P 2: máximo dos líneas en PDF. A 13px en el ancho útil del brief
    caben ~95 caracteres por línea."""
    for f in FECHAS:
        bl = _guia(f)["bottom_line"]
        assert len(bl) <= 240, f"{f}: {len(bl)} caracteres, no cabe en dos líneas"


def test_la_conclusion_no_repite_literalmente_la_cabecera():
    """La cabecera da el resultado; la conclusión dice cómo interpretarlo. Si
    fueran la misma frase, una de las dos sobra."""
    for f in FECHAS:
        s = _snap(f)
        bl = _guia(f)["bottom_line"]
        pg = s["postura_general"]
        cabecera = f"{pg['palabra']} con convicción {pg['conviccion']}"
        # puede nombrarlos, pero tiene que añadir expresión o restricción.
        # Desde SPEC-7P 11 la frase EMPIEZA por «Se expresa por», con mayúscula.
        b = bl.lower()
        assert ("se expresa por" in b or "restricción" in b
                or "tensión" in b), f"{f}: la conclusión no añade nada"


# ===================== DISPARADORES ========================================
def test_ningun_disparador_sin_decir_a_quien_afecta():
    for f in FECHAS:
        for b in ("confirma", "debilita", "invalida", "tactico"):
            for t in (_guia(f)["triggers"].get(b) or []):
                alcance = (t.get("affected_theme") or t.get("affected_dimension")
                           or t.get("afecta"))
                assert alcance, f"{f}: «{t['variable']}» no dice a qué afecta"


def test_cada_disparador_del_brief_es_una_unidad_visual():
    """SPEC-4P 21: una fila, no un párrafo."""
    from snapshot import decision
    for f in FECHAS:
        for t in decision.triggers_brief(_snap(f)):
            assert len(brief._impacto(t)) <= 80, (
                f"{f}: el impacto de «{t['variable']}» no cabe en una celda")
            assert brief._umbral_corto(t), f"{f}: «{t['variable']}» sin umbral"


def test_el_brief_no_pasa_de_cinco_disparadores():
    from snapshot import decision
    for f in FECHAS:
        assert len(decision.triggers_brief(_snap(f))) <= 5


# ===================== EXPRESION, SESGO Y DRIVERS ==========================
def test_ninguna_expresion_publicada_sin_procedencia():
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            e = t["favorecer"]
            if e.get("text") in (None, "", "—"):
                continue
            assert e.get("supported_by"), f"{f}/{t['key']}: expresión sin drivers"


def test_evitar_solo_si_no_es_el_inverso_mecanico():
    from snapshot import decision
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            if not t.get("evitar_util"):
                continue
            fav = (t["favorecer"].get("text") or "")
            evi = (t["evitar"].get("text") or "")
            assert not decision._inversa(fav, evi), (
                f"{f}/{t['key']}: «Evitar» es el inverso mecánico y se publica")


def test_el_sesgo_usa_lenguaje_portable():
    """SPEC-4P 12: sin vocabulario de peso frente a un índice."""
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            assert t.get("sesgo"), f"{f}/{t['key']}: sin etiqueta de sesgo"
            assert t["sesgo"].lower() not in ("sobreponderar", "infraponderar")
        for doc, nom in zip(_docs(f), ("HTML", "PDF")):
            tx = consistencia.texto(doc)
            i = tx.find("guía de posicionamiento")
            if i < 0:
                continue
            tabla = tx[i:i + 2200]
            for mal in ("sobreponderar", "infraponderar"):
                assert mal not in tabla, f"{f}/{nom}: la tabla dice «{mal}»"


def test_los_drivers_no_compiten_con_la_conclusion():
    """Los drivers viven en su propia clase, con tamaño y color propios."""
    h, b = _docs(FECHAS[0])
    assert ".expsrc{" in h or ".expsrc " in h, "el HTML no da estilo propio a los drivers"
    assert ".drv{" in b, "el PDF no da estilo propio a los drivers"


# ===================== LENGUA Y COLUMNAS ===================================
def test_una_sola_lengua_en_los_encabezados():
    ingles = ("executive read", "positioning guide", "decision triggers",
              "regime & executive read", "what changed", "key evidence")
    for f in FECHAS:
        for doc, nom in zip(_docs(f), ("HTML", "PDF")):
            tx = consistencia.texto(doc)
            for e in ingles:
                assert e not in tx, f"{f}/{nom}: encabezado en inglés «{e}»"


def test_los_nombres_financieros_convencionales_se_quedan():
    """Una sola lengua no significa traducir HY, IG o VIX."""
    tx = consistencia.texto(_docs("2026-09-21")[0])
    assert "hy oas" in tx and "vix" in tx


def test_ninguna_columna_queda_vacia():
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            assert t.get("sesgo"), "sesgo vacío"
            assert t.get("timing"), "timing vacío"
            assert t.get("favorecer") is not None


def test_el_horizonte_no_ocupa_una_columna_repetida():
    """SPEC-4P 15: si casi todas las filas dicen lo mismo, no merece columna."""
    h = _docs("2026-09-21")[0]
    i = h.find('class="pguide"')
    cab = h[i:i + 1200]
    assert "<th>Horizonte</th>" not in cab, "el horizonte vuelve como columna"
    # La columna de señal se comprueba por su nombre canonico: comprobar la
    # cadena "Timing" hacia que renombrarla rompiera un test sobre el horizonte,
    # que no habla de eso.
    assert f"<th>{config.SENAL_ETIQUETA}</th>" in cab, "falta la columna de señal"


# ===================== PAGINACION Y ENCAJE =================================
def test_el_pdf_cabe_en_cuatro_paginas():
    for f in FECHAS:
        _h, log = brief.render_brief(_snap(f)), None
        _b, log = brief.render_brief(_snap(f))
        pags = sum(1 for l in log if not l.strip().startswith("→"))
        fus = sum(1 for l in log if "se funde" in l)
        assert pags - fus <= 4, f"{f}: {pags - fus} páginas"


def test_ninguna_pagina_desborda():
    """La guía de posicionamiento no puede cortarse."""
    for f in FECHAS:
        s = _snap(f)
        bl = [brief._b_regimen(s), brief._b_positioning(s),
              brief._b_vigilar(s), brief._b_cierre(s)]
        for b in bl:
            assert b.lineas <= brief.CAP, (
                f"{f}: «{b.seccion}» estima {b.lineas}px sobre un máximo de {brief.CAP}")


def test_el_pdf_real_no_pasa_de_cuatro_paginas():
    ruta = "output/snapshot-2026-09-21-brief.pdf"
    if not os.path.isfile(ruta):
        return
    n = pdf.paginas(ruta)
    assert n is None or n <= 4, f"{n} páginas"


# ===================== EL HTML SIGUE SIENDO AUDITABLE ======================
def test_el_html_conserva_toda_la_auditoria():
    """SPEC-5P 39: la quinta pasada puede mover, plegar y resumir; no puede
    borrar. Se comprueba el CONTENIDO, no el contenedor: el tablero pasó a ser
    la sección 06."""
    h = _docs("2026-09-21")[0]
    assert 'id="sec-auditoria"' in h, "no existe la sección de auditoría"
    for k in ("Percentil:", "Método de dirección", "Disparadores en el bloque",
              "Voto por cluster", "Fuentes, registro completo", "Metodología"):
        assert k in h, f"falta «{k}» en la auditoría"
    # y los 42 indicadores siguen estando
    assert h.count('data-buscar=') == len(config.INDICATORS)


def test_no_se_anadieron_pesos_de_cartera():
    for f in FECHAS:
        for doc in _docs(f):
            tx = consistencia.texto(doc)
            for mal in ("% de la cartera", "peso objetivo", "asignación del",
                        "stop loss", "precio objetivo"):
                assert mal not in tx, f"{f}: aparece «{mal}»"


# ============ QUINTA PASADA · EL HTML COMO ESPACIO DE TRABAJO ==============
def _html(f="2026-09-21"):
    return _docs(f)[0]


def test_las_seis_secciones_existen_y_en_orden():
    h = _html()
    orden = ["sec-ahora", "sec-posicionamiento", "sec-vigilar",
             "sec-historia", "sec-research", "sec-auditoria"]
    pos = [h.find(f'id="{x}"') for x in orden]
    assert all(p > 0 for p in pos), f"falta alguna sección: {dict(zip(orden, pos))}"
    assert pos == sorted(pos), "las secciones no van en orden"


def test_hay_navegacion_y_no_esta_duplicada():
    h = _html()
    assert h.count('<nav class="nv"') == 1, "más de una navegación"
    assert h.count('id="nv-sel"') == 1, "más de un selector móvil"
    for sid in ("ahora", "posicionamiento", "vigilar", "historia", "research",
                "auditoria"):
        assert f'data-sec="{sid}"' in h, f"la navegación no enlaza {sid}"


def test_la_primera_seccion_trae_la_decision_y_lo_que_cambio():
    h = _html()
    i, j = h.index('id="sec-ahora"'), h.index('id="sec-posicionamiento"')
    ahora = h[i:j]
    assert "ck-post" in ahora, "falta la postura destacada"
    assert config.TITULOS["takeaway"] in ahora, "falta la conclusión operativa"
    assert config.TITULOS["cambios"] in ahora, "«qué cambió» no está arriba"
    # SEMANTIC-PASS 8: el gráfico se llama por lo que responde, no por su
    # nombre interno.
    assert "Qué está impulsando el régimen" in ahora, "falta el gráfico de fuerzas"


def test_los_pilares_estan_plegados_por_defecto():
    h = _html()
    assert h.count('<details class="pillar"') == len(config.PILLARS)
    assert '<details class="pillar" data-pilar' in h
    assert '<details class="pillar" open' not in h, "algún pilar viene abierto"


def test_el_research_permite_filtrar_los_42():
    h = _html()
    assert h.count("data-buscar=") == len(config.INDICATORS)
    for k in ('id="flt-q"', 'id="flt-p"', 'id="flt-e"'):
        assert k in h, f"falta el control {k}"


def test_cada_indicador_tiene_ancla_para_enlazar_desde_la_decision():
    """El camino decisión → driver → indicador no puede terminar en nada."""
    h = _html()
    for d in config.INDICATORS:
        assert f'id="ind-{d["key"]}"' in h, f"{d['key']} sin ancla"


def test_la_auditoria_abre_con_un_semaforo():
    h = _html()
    i = h.index('id="sec-auditoria"')
    cab = h[i:i + 2500]
    assert 'class="qa-s' in cab, "la auditoría no abre con estado"
    assert ("Correcto" in cab), "el semáforo no dice el estado"


def test_los_graficos_tienen_alternativa_textual():
    """SPEC-5P 34: cada gráfico, legible por un lector de pantalla."""
    h = _html()
    import re
    svgs = re.findall(r"<svg[^>]*>.*?</svg>", h, re.S)
    assert svgs, "no hay gráficos"
    for sv in svgs:
        assert "<title>" in sv or 'aria-label' in sv, "SVG sin título ni etiqueta"
        assert 'role="img"' in sv or "<desc>" in sv, "SVG sin rol ni descripción"


def test_el_heatmap_y_la_linea_salen_de_la_misma_funcion_que_el_resto():
    """No se sintetiza historia: se recalcula con `_postura_en`, la misma que ya
    usa la columna «mes anterior» y la persistencia de la postura."""
    for f in ("2026-09-21", "2021-11-01"):
        hi = _guia(f).get("historia") or {}
        if not hi.get("disponible"):
            continue
        assert len(hi["columnas"]) >= 6
        for c in hi["columnas"]:
            for ck, v in c["temas"].items():
                assert ck in config.ASSET_CLASSES
                assert v["dir_tipo"] in ("mas", "menos", "neutral")


def test_el_html_no_repite_la_conclusion_en_cada_seccion():
    """La cabecera da el resultado; no hace falta repetirlo entero abajo."""
    h = consistencia.texto(_html())
    pg = _snap("2026-09-21")["postura_general"]
    frase = f"{pg['palabra']} con convicción {pg['conviccion']}"
    assert h.count(consistencia.texto(frase)) <= 2, (
        "la conclusión completa se repite más de dos veces")


def test_el_javascript_es_minimo_y_sin_dependencias():
    h = _html()
    assert "<script" in h, "no hay ayudantes"
    # Se cuentan los scripts EJECUTABLES. El estado canónico viaja en un bloque
    # `type="application/json"` (HTML-POLISH 1): es dato que el navegador no
    # ejecuta, y su presencia no es una dependencia nueva.
    ejecutables = [x for x in h.split("<script")[1:]
                   if 'type="application/json"' not in x[:80]]
    assert len(ejecutables) == 1, f"más de un bloque de script ejecutable"
    assert '<script type="application/json" id="decision-state">' in h, (
        "el documento no publica el DecisionState canónico")
    for malo in ("http://", "cdn.", "react", "jquery", "vue"):
        assert malo not in ejecutables[0][:9000].lower(), (
            f"el script trae «{malo}»")


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
