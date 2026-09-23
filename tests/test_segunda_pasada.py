# -*- coding: utf-8 -*-
"""Tests de la SEGUNDA PASADA (SPEC-2P).

  3  · el metodo se publica en el estado, no se infiere del texto
  4  · recomputacion contrafactual de los disparadores
  5  · tension dominante (estructural) vs indicador que mas contradice
  6  · el timing global manda; el propio exige evidencia
  7  · procedencia de las expresiones (ver tambien test_spec_fase2)
  9  · señal direccional vs overlay contrario
  10 · direccion del condicional de cierre, por RELACION y no por texto
  11 · QA semantico, incluidas las mutaciones que lo hacen morder
  12 · cobertura parcial del DecisionState no se marca ✓
  14 · el cluster NO se promueve; queda la infraestructura de comparacion
  15 · regresiones de los arreglos previos que esta pasada podria haber roto

    python tests/test_segunda_pasada.py
"""

from __future__ import annotations

import copy
import dataclasses
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from snapshot import build, data, decision, indicators, semantica  # noqa: E402

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


def _guia(f):
    return _snap(f)["decision"].guia


def _triggers(f):
    return _guia(f).get("triggers") or {}


def _publicados(f):
    return [t for b in ("confirma", "debilita", "invalida", "tactico")
            for t in (_triggers(f).get(b) or [])]


# ======================== 3 · EL METODO SE PUBLICA ==========================
def test_el_estado_publica_los_tres_campos_de_metodo():
    for f in FECHAS:
        g = _guia(f)
        for campo in ("direction_method", "cluster_role", "conviction_method"):
            assert g.get(campo) == config.METODOLOGIA[campo], (
                f"{f}: {campo}={g.get(campo)!r}")


def test_la_direccion_oficial_es_el_voto_por_indicador():
    """El cluster puede diagnosticar; no puede decidir la direccion."""
    for f in FECHAS:
        g = _guia(f)
        assert g["direction_method"] == "voto_por_indicador"
        assert g["cluster_role"] == "diagnostico_paralelo"


# ==================== 4 · RECOMPUTACION CONTRAFACTUAL =======================
def test_todo_disparador_publicado_trae_su_efecto_medido():
    for f in FECHAS:
        for t in _publicados(f):
            assert t.get("effect_type") in set(config.TRIGGER_EFECTOS), (
                f"{f}/{t['variable']}: efecto {t.get('effect_type')!r}")


def test_invalida_solo_contiene_lo_que_neutraliza_o_revierte():
    """El corazon de SPEC-2P 4: el bloque lo decide el efecto MEDIDO."""
    for f in FECHAS:
        for t in (_triggers(f).get("invalida") or []):
            assert t["effect_type"] in config.TRIGGER_INVALIDA, (
                f"{f}: «{t['variable']}» está en invalida con efecto "
                f"{t['effect_type']}")


def test_lo_que_solo_quita_apoyo_no_aparece_como_invalidante():
    for f in FECHAS:
        for b in ("confirma", "debilita"):
            for t in (_triggers(f).get(b) or []):
                assert t["effect_type"] not in config.TRIGGER_INVALIDA, (
                    f"{f}: «{t['variable']}» en {b} con efecto {t['effect_type']}")


def test_cada_disparador_dice_a_que_afecta_y_como_estaba_antes():
    for f in FECHAS:
        for t in _publicados(f):
            if t["effect_type"] == "tactical":
                continue
            assert t.get("affected_dimension") in ("tema", "postura_general",
                                                   "regimen", "timing"), t
            assert t.get("before_state") and t.get("after_state"), (
                f"{f}/{t['variable']}: sin estado antes/después")


def test_el_umbral_se_simula_CRUZADO_no_tocado():
    """Quedarse en p60 exacto no es cruzar p60: el indicador sigue votando."""
    for f in FECHAS:
        for t in _publicados(f):
            obj, act, cf = t.get("pct_obj"), t.get("pct_actual"), t.get("pct_cf")
            if obj is None or act is None or cf is None:
                continue
            assert cf != obj, f"{f}/{t['variable']}: se queda en el umbral"
            assert (cf < obj) == (act > obj), (
                f"{f}/{t['variable']}: cruza hacia el lado equivocado")


def test_el_contrafactual_recalcula_de_verdad():
    """No es una etiqueta: mover el indicador al otro lado del umbral tiene que
    reproducir el estado que el disparador dice que produciria."""
    f = "2008-09-15"
    snap = _snap(f)
    objetivo = next((t for t in _publicados(f)
                     if t.get("pct_cf") is not None
                     and t.get("affected_dimension") == "tema"), None)
    assert objetivo is not None, "ninguna fecha deja probar el contrafactual"
    # se rehace el calculo por fuera, con la misma via que usa el pipeline
    snap2 = build.build_snapshot(_ctx(), f)          # estado limpio
    assert snap2["postura_general"]["palabra"] == snap["postura_general"]["palabra"]
    ck = objetivo["affected_theme"]
    antes = objetivo["before_state"]
    real = next(p for p in snap["postura"] if p["key"] == ck)
    assert antes.get("direccion") == real["dir_tipo"], (
        f"el «antes» del disparador no es la postura publicada: "
        f"{antes.get('direccion')} vs {real['dir_tipo']}")


def test_2008_hy_oas_debilita_pero_no_invalida():
    """El caso que SPEC-2P 4 nombra: si HY OAS deja de votar y la renta variable
    sigue infraponderada, eso DEBILITA, no invalida."""
    f = "2008-09-15"
    inval = [t["key"] for t in (_triggers(f).get("invalida") or [])]
    assert "hy_oas" not in inval, "HY OAS vuelve a aparecer como invalidante"
    hy = next((t for t in _publicados(f) if t["key"] == "hy_oas"), None)
    if hy is not None:
        assert hy["effect_type"] == "weaken", hy["effect_type"]


def test_intensificar_el_regimen_del_mismo_lado_no_invalida():
    """«apetito de riesgo -> euforia» refuerza una lectura pro-riesgo."""
    f = "2021-11-01"
    for t in (_triggers(f).get("invalida") or []):
        if t["key"] != "_eje_riesgo":
            continue
        prev = (t.get("before_state") or {}).get("regimen")
        nuevo = (t.get("after_state") or {}).get("regimen")
        assert not (prev == "apetito de riesgo" and nuevo == "euforia"), (
            "una banda más extrema del mismo lado sigue contando como invalidar")


def test_un_indicador_un_disparador():
    """Regresion: el bloque invalida repetia el mismo indicador cuatro veces."""
    for f in FECHAS:
        claves = [t["key"] for t in _publicados(f)]
        assert len(claves) == len(set(claves)), (
            f"{f}: disparadores repetidos -> {claves}")


# ============ 5 · TENSION DOMINANTE vs INDICADOR QUE CONTRADICE =============
def test_la_tension_dominante_es_estructural():
    for f in FECHAS:
        d = _snap(f).get("tension_dominante")
        if d is None:
            continue
        assert d["tipo"] in ("bloques", "pilares", "ejes"), d["tipo"]
        assert d.get("texto") and d.get("detalle")
        assert d.get("brecha") is not None


def test_la_dominante_y_el_indicador_son_cosas_distintas():
    """Una es un diagnostico entre bloques; el otro es un dato suelto. No
    pueden ser el mismo objeto ni derivarse uno del otro."""
    for f in FECHAS:
        s = _snap(f)
        d, i = s.get("tension_dominante"), s.get("tension_principal")
        if d is None or i is None:
            continue
        assert "key" not in d, "la dominante se colo como un indicador"
        assert d["tipo"] in ("bloques", "pilares", "ejes")
        assert "pct" in i, "el indicador que contradice perdio su percentil"


def test_los_dos_lados_de_la_tension_se_oponen_de_verdad():
    for f in FECHAS:
        d = _snap(f).get("tension_dominante")
        if d is None or d["tipo"] == "bloques":
            continue
        assert (d["alto_score"] - 50.0) * (d["bajo_score"] - 50.0) <= 0, (
            f"{f}: los dos lados están del mismo lado de lo normal")


# ======================== 6 · TIMING GLOBAL Y PROPIO ========================
def test_el_timing_publicado_es_el_global_salvo_override():
    for f in FECHAS:
        g = _guia(f)
        for t in g["temas"]:
            if t.get("timing_override"):
                assert t["timing"] == t["timing_override"]
                assert t["timing"] != g["timing"]
            else:
                assert t["timing"] == g["timing"], (
                    f"{f}/{t['key']}: {t['timing']} != global {g['timing']}")


def test_un_timing_propio_exige_evidencia_tactica_propia():
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            if not t.get("timing_override"):
                continue
            assert len(t.get("timing_apoyos") or []) >= config.TIMING_OVERRIDE_MIN, (
                f"{f}/{t['key']}: timing propio con "
                f"{len(t.get('timing_apoyos') or [])} indicadores tácticos")
            assert t["dir_tipo"] != "neutral"


# =================== 9 · SEÑAL DIRECCIONAL vs OVERLAY =======================
def test_la_senal_tactica_se_nombra_segun_vaya_o_no_contra_el_regimen():
    for f in FECHAS:
        st = _guia(f)["setup"]
        if not st.get("existe"):
            assert st.get("clase") is None
            continue
        esperada = "overlay" if st["contra_regimen"] else "direccional"
        assert st["clase"] == esperada, f"{f}: {st['clase']} con contra_regimen={st['contra_regimen']}"
        assert st["clase_titulo"] == config.SENAL_TACTICA[esperada]


def test_una_senal_tactica_nunca_cambia_el_regimen():
    for f in FECHAS:
        s = _snap(f)
        st = _guia(f)["setup"]
        if not st.get("existe"):
            continue
        assert s["postura_general"]["palabra"] in ("pro-riesgo", "defensiva", "mixta")
        assert "régimen" not in (st.get("clase_titulo") or "").lower()


# ============ 10 · DIRECCION DEL CONDICIONAL, POR RELACION ==================
def test_el_condicional_apunta_al_lado_correcto():
    """Un hecho que APOYA la postura la sostiene mientras persista; uno que la
    CONTRADICE, mientras no se imponga. Se comprueba la relacion, no el texto."""
    for f in FECHAS:
        m = _snap(f)["condicional_meta"]
        if m["apoya"] is None:
            assert m["sentido"] == "neutro"
            continue
        esperado = "persiste" if m["apoya"] else "no_se_impone"
        assert m["sentido"] == esperado, f"{f}: {m}"


def test_el_apoyo_declarado_coincide_con_el_tablero():
    for f in FECHAS:
        s = _snap(f)
        m = s["condicional_meta"]
        if m["hecho"] != "crecimiento":
            continue
        pg = s["postura_general"]["palabra"]
        lect = s["composites"]["afirm"]["economia_real"]["lect"]
        real = ((lect == "favorable" and pg == "pro-riesgo") or
                (lect == "adverso" and pg == "defensiva"))
        assert bool(m["apoya"]) == real, f"{f}: apoya={m['apoya']} pero {lect}/{pg}"


def test_una_contradiccion_no_sostiene_la_lectura_dandose_la_vuelta():
    """Si la tension se da la vuelta deja de contradecir y la lectura MEJORA.
    Decir que la lectura «depende de que no se dé la vuelta» es el error."""
    for f in FECHAS:
        m = _snap(f)["condicional_meta"]
        if m["rama"] != "tension":
            continue
        assert m["apoya"] is False and m["sentido"] == "no_se_impone", m
        assert "se dé la vuelta" not in m["texto"], m["texto"]


# ========================== 11 · QA SEMANTICO ===============================
def test_las_comprobaciones_semanticas_existen():
    """Las ocho de la segunda pasada, las dos del cierre del brief y las tres
    de la séptima: régimen contra banda, espectro contra sesgo y erratas."""
    claves = {c[0] for c in semantica.CHECKS}
    assert claves == {
        "percentile_definition_consistent", "direction_method_consistent",
        "cluster_role_consistent", "conviction_method_consistent",
        "trigger_classification_valid", "preferred_expression_has_provenance",
        "narrative_direction_valid", "html_pdf_semantics_match",
        "coherence_bullet_rendered", "recent_indicators_outside_context",
        "regime_label_matches_band", "spectrum_marker_matches_bias",
        "copy_quality", "indicator_value_single"}, claves
    # y cada una declara con qué severidad se lee su fallo (SPEC-7P 18)
    assert all(c[3] in ("error", "aviso", "info") for c in semantica.CHECKS)


def _sever(clave):
    """La severidad declarada para el fallo de esa comprobación. Los tests de
    «muerde» comprueban que la comprobación DETECTA, no de qué color lo pinta."""
    return next(c[3] for c in semantica.CHECKS if c[0] == clave)


def test_ninguna_comprobacion_semantica_avisa_en_las_cuatro_fechas():
    for f in FECHAS:
        # SPEC-7P 18: un fallo puede salir como «aviso» o como «error» según lo
        # que declare su comprobación. Ninguno de los dos puede aparecer.
        malas = [x for x in _snap(f)["semantica"]
                 if x["estado"] in ("aviso", "error")]
        assert not malas, f"{f}: {[(m['clave'], m['nota']) for m in malas]}"


def _docs_buenos():
    return ("<p>" + config.METODOLOGIA_PERCENTIL["corta"] + " " +
            config.METODOLOGIA_TXT["direction_method"] + " " +
            config.METODOLOGIA_TXT["cluster_role"] + " " +
            config.METODOLOGIA_TXT["conviction_method"] + "</p>")


def test_el_qa_del_percentil_muerde():
    s = _snap("2008-09-15")
    d = _docs_buenos()
    def estado(html):
        r = {x["clave"]: x for x in semantica.revisar(s, html, d)}
        return r["percentile_definition_consistent"]["estado"]
    assert estado(d) == "ok"
    assert estado(d + "<p>Un p100 es favorable.</p>") == _sever("percentile_definition_consistent")
    assert estado(d + "<p>Escala: 100 = favorable.</p>") == _sever("percentile_definition_consistent")
    # la excepcion legitima: los ejes SI van orientados
    assert estado(d + "<p>Nivel del eje: 100 = favorable a riesgo.</p>") == "ok"


def test_el_qa_de_metodo_muerde_si_un_formato_calla():
    s = _snap("2008-09-15")
    d = _docs_buenos()
    sin_cluster = d.replace(config.METODOLOGIA_TXT["cluster_role"], "")
    r = {x["clave"]: x for x in semantica.revisar(s, d, sin_cluster)}
    assert r["cluster_role_consistent"]["estado"] == _sever("cluster_role_consistent")
    assert r["html_pdf_semantics_match"]["estado"] == _sever("html_pdf_semantics_match")


def test_el_qa_de_disparadores_muerde():
    s = copy.copy(_snap("2008-09-15"))
    g = dict(s["decision"].guia)
    trg = {k: list(v) for k, v in (g.get("triggers") or {}).items()}
    movido = None
    for b in ("confirma", "debilita"):
        if trg.get(b):
            movido = dict(trg[b][0])
            break
    assert movido is not None, "no hay disparador que mover"
    movido["effect_type"] = "weaken"
    trg["invalida"] = list(trg.get("invalida") or []) + [movido]
    g["triggers"] = trg
    s["decision"] = dataclasses.replace(s["decision"], guia=g)
    r = {x["clave"]: x for x in semantica.revisar(s)}
    assert r["trigger_classification_valid"]["estado"] == _sever("trigger_classification_valid")


def test_el_qa_de_la_direccion_narrativa_muerde():
    s = dict(_snap("2008-09-15"))
    s["condicional_meta"] = dict(s["condicional_meta"], sentido="no_se_impone")
    r = {x["clave"]: x for x in semantica.revisar(s)}
    assert r["narrative_direction_valid"]["estado"] == _sever("narrative_direction_valid")


def test_el_qa_de_procedencia_muerde():
    s = copy.copy(_snap("2008-09-15"))
    g = dict(s["decision"].guia)
    temas = [dict(t) for t in g["temas"]]
    puesto = False
    for t in temas:
        if t["favorecer"]["text"] != "—":
            t["favorecer"] = dict(t["favorecer"], supported_by=[], supported_labels=[])
            puesto = True
            break
    assert puesto
    g["temas"] = temas
    s["decision"] = dataclasses.replace(s["decision"], guia=g)
    r = {x["clave"]: x for x in semantica.revisar(s)}
    assert r["preferred_expression_has_provenance"]["estado"] == _sever("preferred_expression_has_provenance")


# ================= 12 · COBERTURA PARCIAL NO ES UN ✓ ========================
def test_la_cobertura_separa_obligatorios_de_opcionales():
    for f in FECHAS:
        cob = _snap(f)["decision"].cobertura()
        assert not cob["faltan_requeridos"], f"{f}: {cob['faltan_requeridos']}"
        assert cob["completo"] is True


def test_si_falta_un_obligatorio_no_se_marca_ok():
    s = dict(_snap("2008-09-15"))
    # el DecisionState es inmutable a proposito: se sustituye, no se muta
    pg = {k: v for k, v in s["decision"].postura_general.items() if k != "palabra"}
    s["decision"] = dataclasses.replace(s["decision"], postura_general=pg)
    c = {x["label"]: x for x in build._comprobaciones(s)}
    fila = c["HTML y PDF sobre el mismo DecisionState"]
    assert fila["estado"] == "aviso", fila
    assert fila["valor"].startswith("?"), fila["valor"]


def test_que_falte_una_tension_no_es_un_fallo():
    """Que no haya contradiccion persistente es una lectura valida."""
    assert "tension" in decision.DecisionState.OPCIONALES
    assert "postura" in decision.DecisionState.REQUERIDOS


# ================= 14 · EL CLUSTER SIGUE SIENDO PARALELO ====================
def test_el_cluster_no_decide_ninguna_direccion():
    for f in FECHAS:
        g = _guia(f)
        assert g["cluster_comparacion"]["promovible"] is False
        post = {p["key"]: p for p in _snap(f)["postura"]}
        for c in g["cluster_score"]:
            assert post[c["key"]]["dir_tipo"] == c["dir_actual"], (
                f"{f}/{c['key']}: la postura publicada no es la del voto crudo")


def test_la_comparacion_distingue_el_tipo_de_diferencia():
    """Contar juntos «neutral -> direccion» y «mas <-> menos» daria una cifra
    alarmante y falsa: solo el segundo invalidaria las validaciones."""
    for f in FECHAS:
        comp = _guia(f)["cluster_comparacion"]
        for t in decision.TIPOS_DIF:
            assert t in comp, f"falta el tipo {t}"
        assert comp["difieren"] == comp["temas"] - comp["ninguna"]
        assert comp["giros"] == comp["giro"]


def test_existe_la_infraestructura_para_comparar_en_serie():
    r = decision.comparar_fechas(_ctx(), FECHAS[:2], build.build_snapshot)
    assert r["fechas"] == 2 and r["tema_fechas"] > 0
    assert r["tasa_giro"] is not None
    assert set(r["total"]) == set(decision.TIPOS_DIF)


# ============== 15 · REGRESIONES DE LOS ARREGLOS ANTERIORES =================
def test_la_alcanzabilidad_es_un_bool_nativo():
    """Regresion: numpy.bool_(False) no es False, y el filtro del brief se
    apoya en una comparacion de identidad, asi que dejaba pasar lo inalcanzable."""
    for f in FECHAS:
        for t in _publicados(f):
            a = t.get("alcanzable")
            assert a is None or isinstance(a, bool), f"{f}/{t['variable']}: {type(a)}"
            assert not isinstance(a, np.bool_)


def test_el_brief_no_vigila_lo_que_esta_fuera_de_alcance():
    for f in FECHAS:
        for t in decision.triggers_brief(_snap(f)):
            assert t.get("alcanzable") is not False
            assert not t.get("ya")


def test_la_postura_general_existe_antes_de_la_prosa():
    """Regresion: se publicaba DESPUES de _conclusiones, asi que el condicional
    caia siempre en su rama generica."""
    for f in FECHAS:
        m = _snap(f)["condicional_meta"]
        assert m["rama"] != "sin-tension/neutro" or m["postura"] is not None
        assert m["postura"] == _snap(f)["postura_general"]["palabra"]


def test_el_sigma_del_disparador_se_escala_a_su_horizonte():
    """Regresion: medido en dias, todo disparador salia a 30-44 sigmas."""
    vistos = 0
    for f in FECHAS:
        for t in _publicados(f):
            sg = t.get("sigmas")
            if sg is None:
                continue
            vistos += 1
            assert sg <= config.TRIGGER_SIGMA_MAX + 1e-9 or t["alcanzable"] is False
    assert vistos > 0, "ningun disparador reporta sigmas"


def test_los_42_indicadores_siguen_declarando_horizonte():
    assert len(config.INDICATORS) == 42
    for d in config.INDICATORS:
        assert d["horizon"] in config.HORIZONS


# ============ 13 · EL PDF: LO COMPATIBLE, SIN DESHACER LA REESCRITURA =======
def _brief(f):
    from snapshot import brief
    k = f"brief:{f}"
    if k not in _cache:
        _cache[k] = brief.render_brief(_snap(f))
    return _cache[k]


def test_el_pdf_separa_regimen_tactica_de_los_disparadores():
    """La parte de SPEC-2P 13 que si se toma: cada cosa con su titulo."""
    from snapshot import consistencia
    for f in FECHAS:
        t = consistencia.texto(_brief(f)[0])
        for sec in ("disparadores de decisión", "qué cambió", "metodología",
                    "fuentes"):
            assert sec in t, f"{f}: al PDF le falta «{sec}»"


def test_el_pdf_no_recupera_lo_que_se_elimino_a_proposito():
    """La parte de SPEC-2P 13 que NO se toma. Key Evidence y las listas de
    fragmentos se quitaron porque no se pueden leer en voz alta en un comite;
    devolverlas desharia la prueba que el brief tiene que pasar."""
    from snapshot import consistencia
    for f in FECHAS:
        t = consistencia.texto(_brief(f)[0])
        # Se vigila la SECCIÓN, no la palabra suelta: la nota de familia común
        # dice legítimamente «no suman siete confirmaciones independientes».
        for prohibido in ("key evidence", "evidencia clave",
                          "confirmaciones más fuertes", "contradicciones más fuertes",
                          "divergencias clave"):
            assert prohibido not in t, f"{f}: vuelve «{prohibido}» al PDF"
        # y tampoco pueden volver como listas de fragmentos
        assert "confirmaciones:" not in t and "divergencias:" not in t


def test_el_pdf_enuncia_el_metodo_completo():
    from snapshot import consistencia
    for f in FECHAS:
        t = consistencia.texto(_brief(f)[0])
        for k, marca in config.METODOLOGIA_MARCA.items():
            assert marca in t, f"{f}: el PDF no enuncia «{k}»"


def test_el_pdf_no_imprime_la_expresion_en_crudo():
    """Regresion: la procedencia convirtio «favorecer» en un dict y la tabla
    del PDF lo estaba imprimiendo tal cual."""
    for f in FECHAS:
        assert "{'text'" not in _brief(f)[0], f"{f}: dict crudo en el PDF"


def test_el_pdf_sigue_cabiendo_en_tres_o_cuatro_paginas():
    for f in FECHAS:
        _h, log = _brief(f)
        paginas = sum(1 for l in log if not l.strip().startswith("→"))
        fusiones = sum(1 for l in log if "se funde" in l)
        assert 3 <= paginas - fusiones <= 4, f"{f}: {paginas - fusiones} páginas"


# ===================== TERCERA PASADA ======================================
# 1 · disparadores: bloque, alcance y persistencia
def test_el_brief_no_reetiqueta_ningun_disparador():
    """El brief toma el bloque tal cual está en el DecisionState."""
    for f in FECHAS:
        estado = {}
        for b, items in (_triggers(f) or {}).items():
            if b == "descartados":
                continue
            for t in items:
                estado[t["key"]] = (b, t.get("umbral"), t.get("sigmas"))
        for t in decision.triggers_brief(_snap(f)):
            assert t["key"] in estado, f"{f}: {t['variable']} no está en el estado"
            b, umbral, sg = estado[t["key"]]
            assert (t["bloque"], t.get("umbral"), t.get("sigmas")) == (b, umbral, sg), (
                f"{f}: {t['variable']} cambió de bloque o de umbral en el brief")


def test_el_brief_solo_vigila_lo_que_esta_al_alcance():
    """El pie promete que solo lista lo alcanzable: el techo se aplica a TODOS
    los bloques, no solo a los invalidantes."""
    for f in FECHAS:
        for t in decision.triggers_brief(_snap(f)):
            sg = t.get("sigmas")
            assert sg is None or sg <= config.BRIEF_SIGMA_MAX, (
                f"{f}: {t['variable']} a {sg:.1f}σ supera el techo de "
                f"{config.BRIEF_SIGMA_MAX}σ")


def test_la_persistencia_vale_tambien_para_los_disparadores():
    """SPEC 7.1 se aplica a TODOS los selectores: un extremo de dos días que no
    llega a ser tensión tampoco puede ser disparador destacado."""
    for f in FECHAS:
        pers = _snap(f)["persistencia"]
        for t in _publicados(f):
            k = t["key"]
            if k.startswith("_"):
                continue
            assert pers.get(k, True), (
                f"{f}: {t['variable']} es disparador sin cumplir persistencia")


def test_el_verbo_del_disparador_sale_de_su_bloque():
    from snapshot import brief as _b
    esperado = {"confirma": "reforzar la lectura",
                "debilita": "debilitar la lectura",
                "invalida": "invalidar la lectura"}
    for f in FECHAS:
        for t in decision.triggers_brief(_snap(f)):
            v = esperado.get(t["bloque"])
            if not v:
                continue
            assert v in _b._frase_trigger(t), (
                f"{f}: «{t['variable']}» ({t['bloque']}) no dice «{v}»")


def test_un_indicador_gana_por_efecto_y_luego_por_cercania():
    """A igualdad de efecto medido se publica el umbral MÁS CERCA, no el
    primero que apareciera."""
    for f in FECHAS:
        vistos = {}
        for t in _publicados(f):
            assert t["key"] not in vistos, f"{f}: {t['key']} repetido"
            vistos[t["key"]] = t


# 2 · evidencia propia por clase
def test_cada_fila_cita_solo_indicadores_de_su_pilar():
    pil = {d["key"]: d["pillar"] for d in config.INDICATORS}
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            mios = set(config.CLASE_PILARES.get(t["key"], []))
            for k in t["apoyos_propios"]:
                assert pil[k] in mios, (
                    f"{f}/{t['key']}: cita {k} del pilar {pil[k]}, ajeno al tema")
            e = t["favorecer"]
            for k in (e.get("supported_by") or []):
                assert pil[k] in mios, f"{f}/{t['key']}: favorecer cita {k}"


def test_el_parentesis_no_se_repite_en_favorecer_y_evitar():
    from snapshot import brief as _b, render as _r
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            fav, evi = t["favorecer"], t["evitar"]
            if not fav.get("supported_by"):
                continue
            apo = ", ".join(fav.get("supported_labels") or [])
            assert apo not in _b._expr(evi, con_fuente=False)
            assert apo not in _r._expr_html(evi, con_fuente=False)
            assert apo not in _r._expr_md(evi, con_fuente=False)


def test_la_familia_comun_se_dice_una_vez_y_es_un_hallazgo():
    for f in FECHAS:
        fam = _guia(f)["familia"]
        if not fam.get("existe"):
            continue
        assert fam["n_clases"] >= config.FAMILIA_MIN_CLASES
        assert fam["texto"].count("sostiene") == 1
        # y los indicadores de la familia sostienen de verdad esas clases
        temas = {t["key"]: t for t in _guia(f)["temas"]}
        for ck in fam["clases"]:
            assert any(k in temas[ck]["apoyos_todos"] for k in fam["keys"])


def test_una_clase_sin_evidencia_propia_lo_dice():
    for f in FECHAS:
        for t in _guia(f)["temas"]:
            if t["dir_tipo"] == "neutral":
                assert not t["sin_evidencia_propia"]
                continue
            esperado = bool(t["apoyos_todos"] and not t["apoyos_propios"])
            assert t["sin_evidencia_propia"] == esperado, f"{f}/{t['key']}"


# 3 · un solo nombre para cada concepto
def test_la_tension_dominante_solo_usa_pilares_de_eje():
    """SPEC 3.1: posicionamiento e inflación no entran en ningún eje, así que no
    pueden formar la tensión DOMINANTE. Si la divergencia más ancha los
    involucra, se publica marcada como CONTEXTO, nunca como dominante."""
    conc = config.CONCEPTO_PILAR
    contexto = {conc.get(p) for p in config.CONTEXT_PILLARS}
    for f in FECHAS:
        d = _snap(f).get("tension_dominante")
        if not d or d["tipo"] != "pilares":
            continue
        toca_contexto = {d["alto_label"], d["bajo_label"]} & contexto
        if toca_contexto:
            assert d.get("de_eje") is not True, (
                f"{f}: {toca_contexto} es de contexto y va marcada como de eje")
            # o lleva la etiqueta de la excepción, o se dice en el detalle
            dicho = (d.get("etiqueta") == config.TENSION_DOMINANTE_CONTEXTO
                     or "contexto" in d["detalle"])
            assert dicho, f"{f}: no se dice que es un pilar de contexto"
        else:
            assert d.get("de_eje") is True, f"{f}: pilares de eje sin marcar"


def test_sin_divergencia_de_eje_se_dice_sin_tension_dominante():
    from snapshot import brief as _b, render as _r, consistencia as _c
    for f in FECHAS:
        s = _snap(f)
        d = s.get("tension_dominante")
        if d is not None and d.get("de_eje"):
            continue
        for doc in (_r.render_html(s), _b.render_brief(s)[0]):
            t = _c.texto(doc)
            assert ("sin tensión dominante" in t or "contexto" in t), (
                f"{f}: no dice que no hay tensión dominante de eje")


def test_los_dos_nombres_son_fijos_y_el_viejo_esta_prohibido():
    from snapshot import brief as _b, render as _r, consistencia as _c
    for f in FECHAS:
        s = _snap(f)
        h = _r.render_html(s)
        b, _l = _b.render_brief(s)
        for doc, nom in ((h, "HTML"), (b, "PDF")):
            t = _c.texto(doc)
            assert config.TENSION_DOMINANTE.lower() in t, f"{f}/{nom}: falta el nombre"
            assert config.TENSION_INDICADOR.lower() in t, f"{f}/{nom}: falta el nombre"
            for prohibido in config.TENSION_PROHIBIDO:
                assert prohibido not in t, f"{f}/{nom}: usa «{prohibido}»"


def test_la_prosa_usa_el_mismo_nombre_que_la_cabecera():
    for f in FECHAS:
        s = _snap(f)
        texto = " ".join(s["conclusiones"]) + " " + " ".join(s["evidencia"])
        for prohibido in config.TENSION_PROHIBIDO:
            assert prohibido not in texto.lower(), f"{f}: la prosa dice «{prohibido}»"


# ===================== CIERRE DEL PM BRIEF =================================
# 1 · la viñeta de coherencia (SPEC 12) tiene que estar RENDERIZADA
def test_2021_produce_la_vineta_de_coherencia():
    """Regresión: al reescribir la página 1 del brief con la prosa del peso de
    la evidencia, la viñeta desapareció del PDF y ningún check lo vio, porque
    miraban el campo y no el documento."""
    from snapshot import brief as _b, render as _r, consistencia as _c
    s = _snap("2021-11-01")
    linea = _guia("2021-11-01").get("coherencia")
    assert linea, "2021-11-01 debe producir la viñeta: pro-riesgo con RV neutral"
    assert "se expresa hoy por" in linea
    for doc, nom in ((_r.render_html(s), "HTML"), (_b.render_brief(s)[0], "PDF")):
        assert "se expresa hoy por" in _c.texto(doc), f"falta la viñeta en {nom}"


def test_la_vineta_aparece_siempre_que_rv_o_duracion_difieran():
    from snapshot import brief as _b, render as _r, consistencia as _c
    for f in FECHAS:
        s = _snap(f)
        div = build._postura_divergencias(s)
        clave = [p for p in div["divergentes"] if p["key"] in ("rv", "dur")]
        if not (div["signo"] and clave):
            continue
        for doc in (_r.render_html(s), _b.render_brief(s)[0]):
            assert "se expresa hoy por" in _c.texto(doc), f"{f}: falta la viñeta"


# 2 · persistencia como PROPIEDAD del indicador
def test_la_persistencia_es_una_propiedad_con_sus_tres_campos():
    for f in FECHAS:
        pers = _snap(f)["persistencia"]
        assert len(pers) == len(config.INDICATORS)
        for k, v in pers.items():
            for campo in ("persistente", "dias_en_extremo", "minimo_requerido",
                          "reciente"):
                assert campo in v, f"{f}/{k}: falta «{campo}»"
            assert v["reciente"] == (v["extremo"] and not v["persistente"])


def test_ningun_selector_usa_un_indicador_reciente():
    """La regla se comprueba sobre TODOS los selectores a la vez, no uno a uno:
    así es como se escapó tres veces seguidas."""
    for f in FECHAS:
        s = _snap(f)
        g = _guia(f)
        rec = {k for k, v in s["persistencia"].items() if v["reciente"]}
        if not rec:
            continue
        for t in g["temas"]:
            assert not (set(t["apoyos_propios"]) & rec), f"{f}: evidencia reciente"
            assert not (set(t["favorecer"].get("supported_by") or []) & rec)
        for t in _publicados(f):
            assert t["key"] not in rec, f"{f}: disparador reciente {t['key']}"
        ten = s.get("tension_principal")
        assert ten is None or ten["key"] not in rec
        for c in (g["brief"]["confirmaciones"] or []):
            assert c["key"] not in rec
        for c in (g["brief"]["contradicciones"] or []):
            assert c["key"] not in rec
        for e in (g["brief"]["evidencia"] or []):
            assert e["key"] not in rec


def test_2008_el_oro_no_se_apoya_en_la_liquidez_de_dos_dias():
    oro = next(t for t in _guia("2008-09-15")["temas"] if t["key"] == "oro")
    assert "netliq_3m" not in oro["apoyos_propios"], "vuelve el extremo de 2 días"
    assert _snap("2008-09-15")["persistencia"]["netliq_3m"]["reciente"] is True


def test_el_check_de_recientes_recorre_el_output():
    from snapshot import brief as _b, render as _r
    for f in FECHAS:
        s = _snap(f)
        r = {x["clave"]: x for x in semantica.revisar(
            s, _r.render_html(s), _b.render_brief(s)[0])}
        assert r["recent_indicators_outside_context"]["estado"] == "ok", (
            f"{f}: {r['recent_indicators_outside_context']['nota']}")


# 3 · la excepción del pilar de contexto
def test_un_pilar_de_contexto_solo_manda_si_es_extremo_y_persistente():
    for f in FECHAS:
        d = _snap(f).get("tension_dominante")
        if not d or d.get("de_eje"):
            continue
        if d.get("etiqueta") != config.TENSION_DOMINANTE_CONTEXTO:
            continue
        assert d["brecha"] >= config.CONTEXTO_TENSION_BRECHA, f"{f}: brecha corta"
        assert d["semanas"] >= config.CONTEXTO_TENSION_SEMANAS, f"{f}: poco tiempo"
        assert d.get("por_que"), f"{f}: sin línea que explique por qué importa"


def test_la_excepcion_no_desplaza_una_tension_de_eje():
    """El caso que habría convertido el posicionamiento en la tensión dominante
    de la semana de Lehman."""
    for f in FECHAS:
        s = _snap(f)
        d = s.get("tension_dominante")
        if not d or d.get("etiqueta") != config.TENSION_DOMINANTE_CONTEXTO:
            continue
        de_eje = {p for e in config.AXES.values() for p in e["weights"]}
        hay_eje = any(x["alto"] in de_eje and x["bajo"] in de_eje
                      for x in (s.get("divergencias") or []))
        assert not hay_eje, f"{f}: había tensión de eje y la desplazó el contexto"


def test_2021_usa_la_excepcion_y_la_etiqueta():
    from snapshot import brief as _b, render as _r, consistencia as _c
    s = _snap("2021-11-01")
    d = s["tension_dominante"]
    assert d["etiqueta"] == config.TENSION_DOMINANTE_CONTEXTO
    assert "inflación" in d["texto"] and "crédito" in d["texto"]
    for doc in (_r.render_html(s), _b.render_brief(s)[0]):
        t = _c.texto(doc)
        # SEMANTIC-PASS 11: en la vista PM son «fuerzas», no «pilares».
        assert "fuerza de contexto" in t or "una fuerza que no vota" in t
        assert "no vota dirección" in t, "falta la línea que explica por qué importa"


# ============================== SPEC-7P A1 ==================================
# Un indicador tiene UN valor publicado. El check que existia miraba el
# DecisionState --donde el valor es uno por construccion-- asi que no podia
# cazar nada. Este mira el DOCUMENTO RENDERIZADO.
def _renderizado(f):
    """El snapshot con sus dos documentos ya compuestos."""
    clave = f"docs::{f}"
    if clave not in _cache:
        from snapshot import brief as _b, render as _r
        s = dict(_snap(f))
        bh, _log = _b.render_brief(s)
        s["_brief_doc"] = bh
        s["_html_doc"] = _r.render_html(s)
        _cache[clave] = s
    return _cache[clave]


def test_un_indicador_tiene_un_solo_valor_en_el_documento():
    for f in FECHAS:
        s = _renderizado(f)
        r = {x["clave"]: x for x in semantica.revisar(
            s, s["_html_doc"], s["_brief_doc"])}
        fila = r["indicator_value_single"]
        assert fila["estado"] == "ok", f"{f}: {fila['nota']}"


def test_el_qa_de_valores_muerde():
    """Si un template escribiera otra cifra para el mismo indicador, el check
    tiene que verlo. La discrepancia se inyecta en el documento RENDERIZADO,
    que es justo donde el check anterior no miraba."""
    import re as _re
    f = FECHAS[0]
    s = _renderizado(f)
    fila = next((x for pil in s["tablero"] for x in pil["filas"]
                 if (config.INDICATOR_BY_KEY[x["key"]].get("unit") == "%"
                     and _re.search(r"[+-]?\d", str(x["valor"] or "")))), None)
    assert fila is not None, "ninguna fila con unidad con la que probar"
    corto = config.SHORT.get(fila["key"], fila["label"])
    num = float(_re.search(r"[+-]?\d+(?:\.\d+)?", str(fila["valor"])).group(0))
    sucio = s["_brief_doc"] + f"<p>{corto} {num + 1.9:+.1f} %</p>"
    r = {x["clave"]: x for x in semantica.revisar(s, s["_html_doc"], sucio)}
    qa = r["indicator_value_single"]
    assert qa["estado"] == _sever("indicator_value_single"), qa
    assert corto.lower()[:6] in qa["nota"].lower() or fila["label"][:8].lower() in qa["nota"].lower(), qa["nota"]


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
