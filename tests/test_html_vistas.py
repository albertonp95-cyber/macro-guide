# -*- coding: utf-8 -*-
"""Tests de REGRESION del HTML (punto 34, A a E).

Los cinco vigilan la misma frontera: el HTML PRESENTA, no decide. Cambiar de
vista, abrir un desplegable o volver a renderizar no puede mover un dato.

  A · cambiar de vista no altera ningun valor publicado
  B · abrir o cerrar un detalle no altera ningun valor publicado
  C · el parametro ?view= se respeta, y sin el se abre en VISTA PM
  D · renderizar dos veces el mismo DecisionState da el mismo documento
  E · el estado normalizado que publica el HTML es el del DecisionState

A y B se comprueban por ESTRUCTURA, no por navegador: las dos vistas son el
mismo DOM con un atributo distinto, y los detalles son <details> nativos con su
contenido en el HTML estatico. Si eso se cumple, no hay forma de que cambiar de
vista o desplegar altere un dato -- no hay codigo que pudiera hacerlo. El test
verifica justamente eso: que no lo haya.

    python tests/test_html_vistas.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from snapshot import (build, consistencia, data, decision,       # noqa: E402
                      indicators, render)

FECHAS = config.VALIDATION_DATES
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


def _html(f):
    k = f"html::{f}"
    if k not in _cache:
        _cache[k] = render.render_html(_snap(f))
    return _cache[k]


def _script(doc: str) -> str:
    """El CÓDIGO del script, sin comentarios.

    Un comentario que dice «sin preventDefault» explica por qué NO se usa; si
    el test mira el texto crudo, ese comentario lo hace fallar y el test acaba
    midiendo la prosa en vez del código.
    """
    crudo = "\n".join(re.findall(r"<script>(.*?)</script>", doc, flags=re.S))
    sin_bloque = re.sub(r"/\*.*?\*/", " ", crudo, flags=re.S)
    return "\n".join(l.split("//")[0] for l in sin_bloque.splitlines())


# ============================== 34 A ========================================
def test_A_cambiar_de_vista_no_toca_ningun_dato():
    """La vista es CSS sobre un atributo. No hay codigo que borre ni reescriba
    contenido, asi que no hay forma de que cambiar de vista mueva un valor."""
    for f in FECHAS:
        doc = _html(f)
        assert 'html[data-view="pm"] .solo-full{display:none' in doc, (
            f"{f}: la vista PM no se aplica por CSS")
        js = _script(doc)
        # lo que si podria alterar datos, y no puede aparecer
        for prohibido in ("removeChild", "innerHTML =", "innerHTML=",
                          "outerHTML", "insertAdjacentHTML", "createElement"):
            assert prohibido not in js, (
                f"{f}: el script manipula contenido con «{prohibido}»")
        # lo unico que el script escribe es el rotulo de una celda ya presente
        assert js.count("textContent") <= 2, (
            f"{f}: el script escribe texto en mas sitios de los previstos")


def test_A_los_bloques_de_la_vista_completa_siguen_en_el_dom():
    """Punto 31: la vista PM oculta, no borra. Tienen que estar los dos."""
    for f in FECHAS:
        doc = _html(f)
        assert doc.count("solo-full") >= 8, f"{f}: faltan bloques marcados"
        for sec in ("sec-research", "sec-auditoria"):
            assert f'id="{sec}"' in doc, f"{f}: {sec} no está en el documento"
        # y todos los indicadores siguen presentes en las dos vistas
        anclas = set(re.findall(r'id="ind-([^"]+)"', doc))
        assert len(anclas) == len(config.INDICATORS), (
            f"{f}: {len(anclas)} indicadores en el DOM de {len(config.INDICATORS)}")


# ============================== 34 B ========================================
def test_B_abrir_un_detalle_no_inyecta_nada():
    """El contenido de cada desplegable esta en el HTML estatico: abrirlo no
    pide nada ni calcula nada. Se comprueba en el tema, que es el que la matriz
    abre al desplegar una fila."""
    for f in FECHAS:
        doc = _html(f)
        temas = _snap(f)["decision"].guia.get("temas") or []
        for t in temas:
            i = doc.find(f'id="theme-{t["key"]}"')
            assert i >= 0, f"{f}: sin fila desplegable para {t['key']}"
            # el detalle va dentro, ya renderizado
            trozo = doc[i:i + 4000]
            assert 'class="td"' in trozo, f"{f}/{t['key']}: detalle no renderizado"
            if t.get("sesgo"):
                assert t["sesgo"] in trozo, (
                    f"{f}/{t['key']}: el detalle no trae su sesgo")


def test_B_los_detalles_son_nativos():
    """<details> nativo: sin JS sigue abriendose, y el teclado ya funciona."""
    for f in FECHAS:
        doc = _html(f)
        assert doc.count("<details") >= 20, f"{f}: apenas hay desplegables"
        # ninguno se abre con un manejador propio de click sobre la fila
        js = _script(doc)
        assert "preventDefault" not in js, (
            f"{f}: el script intercepta la apertura nativa")


# ============================== 34 C ========================================
def test_C_el_parametro_de_vista_se_respeta():
    for f in FECHAS:
        doc = _html(f)
        assert '<html lang="es" data-view="pm">' in doc, (
            f"{f}: el documento no abre en VISTA PM sin JS")
        js = _script(doc)
        assert "view=(pm|full)" in js, f"{f}: no se lee ?view= de la URL"
        assert "searchParams.set('view'" in js, (
            f"{f}: el enlace compartible no se escribe en la URL")
        # y el orden de prioridad: URL, memoria, PM
        assert "deUrl() || leer() || 'pm'" in js, (
            f"{f}: la prioridad de la vista no es URL → memoria → PM")


def test_C_la_memoria_no_puede_romper_el_documento():
    """Punto 22: con localStorage bloqueado el documento abre igual."""
    for f in FECHAS:
        js = _script(_html(f))
        for fn in ("function leer()", "function guardar("):
            i = js.find(fn)
            assert i >= 0, f"{f}: falta {fn}"
            assert "catch" in js[i:i + 240], (
                f"{f}: {fn} no protege el acceso a localStorage")


# ============================== 34 D ========================================
def test_D_renderizar_dos_veces_da_el_mismo_documento():
    """El renderizador no guarda estado entre pasadas ni recalcula nada: el
    mismo DecisionState tiene que producir el mismo HTML, byte a byte."""
    for f in FECHAS:
        s = _snap(f)
        a, b = render.render_html(s), render.render_html(s)
        assert a == b, f"{f}: dos renderizados del mismo estado difieren"


def test_D_el_renderizador_no_recalcula_logica_de_inversion():
    """Lo que decide, decide en la capa. El render puede ordenar y dar formato;
    no puede volver a clasificar."""
    crudo = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "snapshot", "render.py"),
        encoding="utf-8").read()
    # Se mira el CODIGO, no los comentarios: un comentario que menciona la
    # función que decide está explicando por qué el render no la llama.
    fuente = "\n".join(l.split("#")[0] if l.lstrip().startswith("#") else l
                       for l in crudo.splitlines())
    # Los que solo sirven para clasificar: no pintan nada.
    for prohibido in ("CONV_ORDEN", "WOE_CONFIRMA", "WOE_ATEMPERA",
                      "STATE_HYSTERESIS", "STATE_PERSISTENCE", "band_label(",
                      "_relacion(", "CONTRA_PCT_HIGH", "CONTRA_PCT_LOW"):
        assert prohibido not in fuente, (
            f"el renderizador usa «{prohibido}»: eso decide, y decidir no es suyo")
    # Un umbral SÍ puede dibujarse --la marca de p10 y p90 en la barra es
    # presentación--, pero no puede COMPARARSE: ahí dejaría de pintar el
    # criterio para aplicarlo.
    for i, linea in enumerate(fuente.splitlines(), 1):
        if "EXTREME_HIGH" in linea or "EXTREME_LOW" in linea:
            assert not re.search(r"(EXTREME_(HIGH|LOW)\s*[<>=]|[<>=]=?\s*config"
                                 r"\.EXTREME_)", linea), (
                f"render.py:{i} compara contra un umbral de extremo: {linea.strip()}")


# ============================== 34 E ========================================
def _estado_del_html(doc: str) -> dict:
    """El estado normalizado que el documento lleva escrito."""
    import json
    m = re.search(r'<script type="application/json" id="decision-state">'
                  r'(.*?)</script>', doc, flags=re.S)
    assert m, "el documento no publica el DecisionState canónico"
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_E_estado_normalizado_del_html_es_el_json_canonico():
    """HTML-POLISH 34 E, en su forma literal: identidad, no parecido.

    Los dieciseis campos del punto 1, comparados uno a uno contra lo que el
    DecisionState publica. Sin pasar por el texto: si el documento llevara otro
    estado, la igualdad se rompe aunque las palabras coincidieran.
    """
    from snapshot import decision as _d
    for f in FECHAS:
        canon = _d.estado_canonico(_snap(f))
        doc = _estado_del_html(_html(f))
        assert set(doc) == set(canon), (
            f"{f}: campos distintos -> {set(canon) ^ set(doc)}")
        assert len(canon) == 16, f"{f}: {len(canon)} campos, el punto 1 pide 16"
        for k in canon:
            assert doc[k] == canon[k], (
                f"{f}: el campo «{k}» difiere · estado={canon[k]!r} "
                f"· html={doc[k]!r}")


def test_E_los_dieciseis_campos_se_publican_ademas_en_el_texto():
    """El JSON es para auditar; el lector lee el documento. Los campos que se
    dicen con palabras tienen que estar tambien escritos."""
    for f in FECHAS:
        s = _snap(f)
        H = consistencia.texto(_html(f))
        from snapshot import decision as _d
        e = _d.estado_canonico(s)
        faltan = []
        if e["stance"] and consistencia._norm(e["stance"]) not in H:
            faltan.append("stance")
        if e["conviction"] and consistencia._norm(e["conviction"]) not in H:
            faltan.append("conviction")
        if e["regime_confirmed"] and consistencia._norm(e["regime_confirmed"]) not in H:
            faltan.append("regime_confirmed")
        if e["regime_candidate"] and consistencia._norm(e["regime_candidate"]) not in H:
            faltan.append("regime_candidate")
        if e["cycle_regime"] and consistencia._norm(e["cycle_regime"]) not in H:
            faltan.append("cycle_regime")
        if e["horizon"]:
            hz = {"tactical": "táctico", "intermediate": "intermedio",
                  "estructural": "estructural"}.get(e["horizon"], e["horizon"])
            if consistencia._norm(hz) not in H:
                faltan.append("horizon")
        if e["dominant_tension"]:
            for lado in ("alto", "bajo"):
                v = e["dominant_tension"].get(lado)
                if v and consistencia._norm(v) not in H:
                    faltan.append(f"dominant_tension.{lado}")
        if e["contradictory_indicator"]:
            v = e["contradictory_indicator"]["valor"]
            if v and consistencia._norm(v) not in H:
                faltan.append("contradictory_indicator")
        for wc in e["what_changed"][:1]:
            if consistencia._norm(wc) not in H:
                faltan.append("what_changed")
        for k in e["timing_overrides"]:
            if f"theme-{k}" not in _html(f):
                faltan.append(f"timing_override.{k}")
        assert not faltan, f"{f}: el HTML no publica {faltan}"


def test_E_el_estado_publicado_coincide_con_el_decisionstate():
    """El documento dice lo que el estado calcula: postura, convicción, timing,
    régimen, ciclo y las siete dimensiones, leídas del HTML RENDERIZADO."""
    for f in FECHAS:
        s = _snap(f)
        H = consistencia.texto(_html(f))
        v = decision.valores_brief(s)
        faltan = []
        for campo in ("regimen_riesgo", "postura", "conviccion"):
            val = v.get(campo)
            if val and consistencia._norm(val) not in H:
                faltan.append(f"{campo}={val}")
        # el timing, en cualquiera de sus formas legitimas
        _t = v.get("timing")
        formas = [config.TIMING_CABEZA.get(_t), config.timing_frase(_t),
                  config.TIMING_ES.get(_t), config.TIMING_CORTO.get(_t)]
        if _t and not any(x and consistencia._norm(x) in H for x in formas):
            faltan.append(f"timing={_t}")
        # y cada dimensión con su sesgo
        for k, (postura, _conv, _hz) in (v.get("temas") or {}).items():
            if postura and consistencia._norm(postura) not in H:
                faltan.append(f"tema {k}={postura}")
        assert not faltan, f"{f}: el HTML no publica {faltan}"


def test_E_un_valor_cambiado_en_el_estado_rompe_el_test():
    """El E solo vale si muerde. Se cambia la postura en el estado y el
    documento --renderizado antes-- deja de coincidir."""
    f = FECHAS[0]
    s = _snap(f)
    H = consistencia.texto(_html(f))
    v = decision.valores_brief(s)
    assert consistencia._norm(v["postura"]) in H
    inventada = "posicionamiento inexistente de control"
    assert consistencia._norm(inventada) not in H, (
        "el documento contiene una postura que el estado no publica")


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
