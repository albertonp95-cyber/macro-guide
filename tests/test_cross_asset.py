# -*- coding: utf-8 -*-
"""SEMANTIC-PASS · tests ESTRICTOS de lo que el documento DICE (27-33, 40).

La pasada anterior se reporto como implementada sin que el DOM existiera. Estos
tests no comprueban intenciones ni nombres de funcion: abren el documento
renderizado y buscan el texto y los elementos que el lector veria. Si el Tape
no esta dibujado, fallan; si esta dibujado pero con la banda al reves, fallan;
si el vocabulario se separa entre el HTML y el PDF, fallan.

    python tests/test_cross_asset.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                               # noqa: E402

import config                                                    # noqa: E402
from snapshot import (brief, build, data, indicators,            # noqa: E402
                      render, tape)

FECHAS = config.VALIDATION_DATES
IDS = [p["id"] for p in tape.PANELES]
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
    k = f"h::{f}"
    if k not in _cache:
        _cache[k] = render.render_html(_snap(f))
    return _cache[k]


def _brief(f):
    k = f"b::{f}"
    if k not in _cache:
        _cache[k] = brief.render_brief(_snap(f))[0]
    return _cache[k]


def _pm(doc: str) -> str:
    """El documento TAL COMO LO VE la vista PM: sin los bloques solo-full.

    No es exacto al pixel --un <details> cerrado sigue en el texto-- pero quita
    lo unico que la vista PM realmente oculta, que es lo que hay que comprobar
    cuando el punto dice "fuera de la capa PM"."""
    return re.sub(r'<(\w+)[^>]*class="[^"]*solo-full[^"]*".*?</\1>', "",
                  doc, flags=re.S)


def _seccion_tape(doc: str) -> str:
    i = doc.find('id="cross-asset-tape"')
    assert i > 0, "no existe la seccion #cross-asset-tape"
    j = doc.find("<h3", i + 10)
    return doc[i:j if j > i else len(doc)]


# ======================= 29 · el Tape existe, y son siete ===================
def test_el_tape_existe_con_sus_siete_paneles():
    """El requisito literal: id=cross-asset-tape con paneles identificables
    para equity, rates, credit, style, commodities, gold y usd. 7 de 7."""
    for f in FECHAS:
        doc = _html(f)
        assert doc.count('id="cross-asset-tape"') == 1, f"{f}: la seccion no existe"
        sec = _seccion_tape(doc)
        vistos = [i for i in IDS if f'id="tp-{i}"' in sec]
        assert len(vistos) == 7, (
            f"{f}: {len(vistos)}/7 paneles — faltan "
            f"{sorted(set(IDS) - set(vistos))}")


def test_cada_panel_dibuja_una_serie_o_dice_que_no_hay_dato():
    """Un panel vacio y sin explicacion es peor que no tenerlo."""
    for f in FECHAS:
        sec = _seccion_tape(_html(f))
        for pid in IDS:
            blk = re.search(rf'id="tp-{pid}".*?</figure>', sec, re.S)
            assert blk, f"{f}/{pid}: el panel no esta en el DOM"
            cuerpo = blk.group(0)
            dibuja = 'class="tp-l"' in cuerpo
            lo_dice = "DATOS NO DISPONIBLES" in cuerpo
            assert dibuja or lo_dice, (
                f"{f}/{pid}: ni dibuja serie ni declara que falta el dato")
            if dibuja:
                d = re.search(r'<path d="([^"]+)" class="tp-l"', cuerpo)
                assert d and d.group(1).count("L") >= 20, (
                    f"{f}/{pid}: la linea tiene menos de 20 puntos")


def test_los_siete_paneles_comparten_exactamente_la_misma_ventana():
    """16: el lector traza una vertical. Si cada serie usa su propia ventana,
    esa vertical no significa nada."""
    for f in FECHAS:
        t = _snap(f).get("tape") or {}
        vivos = [p for p in t.get("paneles", []) if p["disponible"]]
        assert vivos, f"{f}: ningun panel con datos"
        ventanas = {(str(p["desde"].date()), str(p["hasta"].date())) for p in vivos}
        assert len(ventanas) == 1, f"{f}: {len(ventanas)} ventanas distintas: {ventanas}"


def test_todas_las_series_empiezan_en_cien():
    """15: sin rebase, siete escalas distintas no son comparables."""
    for f in FECHAS:
        for p in (_snap(f).get("tape") or {}).get("paneles", []):
            if not p["disponible"]:
                continue
            assert abs(p["puntos"][0][1] - 100.0) < 1e-6, (
                f'{f}/{p["id"]}: empieza en {p["puntos"][0][1]:.2f}, no en 100')


# ================== 17 y 30 · la banda es del modelo, no del precio =========
def test_la_banda_sale_de_la_historia_del_modelo():
    """17: la postura dibujada es la reconstruccion mensual, la MISMA que el
    mapa de calor. No se infiere del precio."""
    for f in FECHAS:
        snap = _snap(f)
        hist = (snap["decision"].guia.get("historia") or {})
        if not hist.get("disponible"):
            continue
        cols = {c["fecha"]: c for c in hist["columnas"]}
        for p in (snap.get("tape") or {}).get("paneles", []):
            for b in p.get("banda") or []:
                c = cols.get(b["fecha"])
                assert c is not None, f'{f}/{p["id"]}: mes que no esta en la historia'
                esperado = (c.get("temas") or {}).get(p["tema"], {}).get("dir_tipo")
                assert b["dir_tipo"] == esperado, (
                    f'{f}/{p["id"]} {b["fecha"]}: banda {b["dir_tipo"]}, '
                    f'historia {esperado}')


def test_el_color_de_la_banda_se_decide_contra_la_linea_dibujada():
    """Con TLT en el panel, que el modelo prefiriera duracion CORTA es una
    postura EN CONTRA de la linea. Pintarla del color "a favor" diria lo
    contrario de lo que paso."""
    for f in FECHAS:
        sec = _seccion_tape(_html(f))
        for p in (_snap(f).get("tape") or {}).get("paneles", []):
            if not p["disponible"]:
                continue
            blk = re.search(rf'id="tp-{p["id"]}".*?</figure>', sec, re.S).group(0)
            rects = re.findall(r'class="(tp-b[0pd])"><title>[^·]*· ([^<]*)</title>', blk)
            assert rects, f'{f}/{p["id"]}: la banda no tiene segmentos con titulo'
            alza = p["alza"]
            etq = config.SESGO_PRESENTACION.get(p["tema"], {})
            contra = "menos" if alza == "mas" else "mas"
            for cls, texto in rects:
                if texto == etq.get(alza):
                    assert cls == "tp-bp", f'{f}/{p["id"]}: «{texto}» no es a favor'
                elif texto == etq.get(contra):
                    assert cls == "tp-bd", f'{f}/{p["id"]}: «{texto}» no es en contra'
                elif texto in ("Neutral", "sin dato"):
                    assert cls == "tp-b0", f'{f}/{p["id"]}: «{texto}» no es neutral'


def test_el_tape_declara_que_no_es_una_prueba_de_rendimiento():
    """21: poner precio y postura en el mismo eje invita a puntuar al modelo a
    ojo. Si no se dice que no es un backtest, el grafico lo insinua."""
    for f in FECHAS:
        sec = _seccion_tape(_html(f))
        assert "No es una prueba de rendimiento" in sec, (
            f"{f}: el Tape no declara que no es un backtest")


def test_el_panel_de_tasas_dice_que_no_hay_tramo_corto():
    """20: se muestra lo que hay --duracion larga-- y se dice. Fabricar un
    'front-end performance' con lo que hay seria inventarse el dato."""
    for f in FECHAS:
        sec = _seccion_tape(_html(f))
        blk = re.search(r'id="tp-rates".*?</figure>', sec, re.S)
        assert blk, f"{f}: no hay panel de tasas"
        assert "no hay serie de tramo corto" in blk.group(0).lower(), (
            f"{f}: el panel de tasas no declara que falta el tramo corto")


def test_el_resumen_describe_y_no_puntua():
    """21: sin una regla documentada que empareje mercado y modelo, "confirma"
    y "diverge" son conclusiones fabricadas."""
    prohibidas = ("confirma", "diverge", "acerto", "acierta", "se equivoco",
                  "valido", "valida el modelo")
    for f in FECHAS:
        for r in (_snap(f).get("tape") or {}).get("resumen", []):
            txt = f'{r["k"]} {r["v"]}'.lower()
            for mala in prohibidas:
                assert mala not in txt, f"{f}: el resumen del Tape dice «{mala}»"


# ================= 31 · disponibilidad de la banda del modelo ===============
def test_reporte_de_disponibilidad_de_la_banda():
    """No es un test de umbral: es el INFORME que el punto 31 pide. Falla solo
    si un panel dibuja banda de un tema que el modelo no publica."""
    lineas = []
    for f in FECHAS:
        for p in (_snap(f).get("tape") or {}).get("paneles", []):
            banda = p.get("banda") or []
            con = sum(1 for b in banda if b.get("dir_tipo") is not None)
            lineas.append(f'        {f} {p["id"]:12s} {len(banda):3d} meses, '
                          f'{con:3d} con postura publicada')
            assert p["tema"] in config.ASSET_CLASSES, (
                f'{f}/{p["id"]}: el panel se ata a un tema que no existe')
    print("\n".join(lineas))


# ============ 32 · el marco de posicionamiento, tal como se publica =========
def test_las_siete_dimensiones_se_publican_con_sus_tres_campos():
    """Sesgo, confianza y señal tactica son tres cosas distintas y las tres
    tienen que estar en cada fila.

    Con una excepcion que NO es una carencia: una fila sin lado no tiene de que
    estar segura, asi que su confianza esta vacia por construccion. Lo que se
    exige entonces es que la celda diga "—" y no se quede en blanco, que es la
    diferencia entre "no hay inclinacion" y "se me olvido publicarlo".
    """
    for f in FECHAS:
        temas = (_snap(f)["decision"].guia.get("temas") or [])
        claves = [t["key"] for t in temas]
        assert set(claves) == set(config.ASSET_CLASSES), (
            f"{f}: las dimensiones publicadas no son las siete: {claves}")
        neutrales = 0
        for t in temas:
            assert t.get("sesgo") or t.get("postura"), f'{f}/{t["key"]}: sin sesgo'
            assert t.get("timing"), f'{f}/{t["key"]}: sin señal tactica'
            if (t.get("dir_tipo") or "neutral") == "neutral":
                neutrales += 1
                assert not t.get("conviccion"), (
                    f'{f}/{t["key"]}: fila sin lado con confianza publicada')
            else:
                assert t.get("conviccion"), f'{f}/{t["key"]}: sin confianza'
        if neutrales:
            doc = _html(f)
            assert doc.count('class="ineu">—') >= neutrales, (
                f"{f}: {neutrales} filas sin lado y menos celdas con «—»")


def test_cada_fila_dice_para_que_lado_es_cada_punta():
    """Las dos puntas del espectro, ordenadas por riesgo, en la fila."""
    from snapshot import decision as _d
    for f in FECHAS:
        for t in (_snap(f)["decision"].guia.get("temas") or []):
            lados = _d.espectro_lados(t)
            assert lados["izq"] and lados["der"], f'{f}/{t["key"]}: punta vacia'
            assert lados["izq"] != lados["der"], f'{f}/{t["key"]}: dos puntas iguales'


# ====================== 28 · el dolar, como overlay ========================
def test_el_dolar_se_publica_como_overlay_y_con_su_implicacion():
    """28: el dolar no es una clase mas de la cartera; es un overlay, y lo que
    importa de el es que le hace a lo demas."""
    assert config.DIMENSION_GRUPO["usd"] == "overlay"
    for f in FECHAS:
        doc = _html(f)
        assert "overlay" in doc.lower(), f"{f}: no se dice que el dolar es overlay"
        temas = (_snap(f)["decision"].guia.get("temas") or [])
        usd = next((t for t in temas if t["key"] == "usd"), None)
        assert usd, f"{f}: no hay fila de dolar"
        imp = config.USD_IMPLICACION.get(usd.get("dir_tipo") or "neutral", "")
        assert imp, f'{f}: el estado «{usd.get("dir_tipo")}» del dolar no tiene implicacion'
        clave = imp.split(":")[0].split(",")[0][:40]
        assert clave in doc, f"{f}: la implicacion del dolar no se publica"


def test_el_dolar_no_se_nombra_con_el_vocabulario_de_otra_fila():
    """"Sobreponderar el dolar" no significa nada en una cartera: lo que se
    dice es si se fortalece o se debilita."""
    for f in FECHAS:
        doc = _pm(_html(f)).lower()
        for mala in ("dólar sobreponderar", "sobreponderar el dólar"):
            assert mala not in doc, f"{f}: «{mala}»"


# ================== 40 · un solo vocabulario en los dos documentos ==========
def test_cada_dimension_se_llama_igual_en_el_html_y_en_el_pdf():
    for f in FECHAS:
        h, b = _html(f), _brief(f)
        for k in config.ASSET_CLASSES:
            nom = config.dimension_breve(k)
            assert nom in h, f"{f}/{k}: «{nom}» no esta en el HTML"
            assert nom in b, f"{f}/{k}: «{nom}» no esta en el brief"


def test_el_vocabulario_viejo_no_sobrevive_en_ninguno_de_los_dos():
    """Las palabras que esta pasada retiro. Si reaparecen, es que un template
    las tenia escritas a mano en vez de leerlas de config."""
    viejas = ["Calidad de crédito", "Cíclico vs. defensivo", "Tasas: plazo",
              "la liquidez pesa", "superando a la liquidez"]
    for f in FECHAS:
        for nom, doc in (("html", _html(f)), ("brief", _brief(f))):
            for v in viejas:
                assert v not in doc, f"{f}/{nom}: sobrevive «{v}»"


def test_la_capa_pm_no_usa_jerga_de_procedencia():
    """9: "· global" y "· propio del tema" obligan al lector a aprender de
    donde sale un campo antes de poder leerlo."""
    for f in FECHAS:
        pm = _pm(_html(f))
        for jerga in ("· global", "propio del tema", "tm-hered", "tm-propio"):
            assert jerga not in pm, f"{f}: la vista PM dice «{jerga}»"


def test_la_señal_tactica_se_dice_de_una_sola_forma_en_la_capa_pm():
    """La matriz resumia la fila con "acompaña con reservas" --el vocabulario
    viejo-- y el detalle de esa MISMA fila, dos clics mas abajo, decia
    "mayormente a favor". Es un solo campo: una sola forma."""
    for f in FECHAS:
        pm = _pm(_html(f))
        # El indice lateral escribia la etiqueta vieja EN MINUSCULAS, que es
        # como se le escapo a la primera comprobacion: se busca sin distinguir
        # mayusculas. Se excluye "Riesgo de reversion" porque no es solo una
        # etiqueta de timing: es el principio del titulo de un setup tactico
        # --"Riesgo de reversion tactica"-- que es otra cosa y se publica
        # legitimamente en "Que vigilar".
        bajo = pm.lower()
        for viejo in set(config.TIMING_CABEZA.values()):
            if viejo == config.TIMING_CABEZA["reversion"]:
                continue
            assert viejo.lower() not in bajo, (
                f"{f}: la vista PM usa la etiqueta vieja de timing «{viejo}»")
        temas = (_snap(f)["decision"].guia.get("temas") or [])
        for t in temas:
            nuevo = config.SENAL_ESTADO.get(t.get("timing"))
            assert nuevo and nuevo in pm, (
                f'{f}/{t["key"]}: la señal «{nuevo}» no se publica en la vista PM')


def test_la_tabla_antigua_no_esta_en_el_flujo_pm():
    """4 y 34: la matriz sustituye a la tabla; no se queda debajo."""
    for f in FECHAS:
        doc = _html(f)
        assert 'class="pguide"' in doc, f"{f}: la tabla de trabajo desaparecio"
        assert 'class="pguide"' not in _pm(doc), (
            f"{f}: la tabla antigua sigue en el flujo PM")
        i = doc.find('class="pguide"')
        assert doc.rfind('id="sec-research"', 0, i) > 0, (
            f"{f}: la tabla de trabajo no esta en Research")


def test_cada_fuerza_dice_que_mide_y_por_que_importa():
    """12: el grafico dice "Condiciones monetarias 40" y da por sabido que hay
    dentro de ese 40. Las tres columnas ya existian; faltaba publicarlas."""
    for f in FECHAS:
        pm = _pm(_html(f))
        assert 'class="pc-f"' in pm, f"{f}: no hay contexto de pilares en la vista PM"
        n = pm.count('class="pc-f"')
        vivos = [p for p in _snap(f).get("tablero", [])
                 if np.isfinite(p.get("score", np.nan))]
        assert n == len(vivos), f"{f}: {n} fichas para {len(vivos)} fuerzas"
        for p in vivos:
            imp = (config.PILLARS.get(p["key"], {}).get("importa") or "")[:40]
            assert imp and imp in pm, f'{f}/{p["key"]}: falta «por que importa»'


def test_la_matriz_dice_que_cada_fila_es_una_decision_relativa():
    """7: sin esa frase, siete filas se leen como siete activos sueltos."""
    for f in FECHAS:
        pm = _pm(_html(f))
        assert "decisión relativa de cartera" in pm, (
            f"{f}: falta la entrada de la matriz")


# =========== 33 · proteccion contra inflacion: el veredicto explicito =======
def test_la_proteccion_contra_inflacion_no_es_una_dimension_y_se_dice():
    """33 · VEREDICTO: NO IMPLEMENTADA como dimension de cartera.

    El tablero tiene un pilar de inflacion, pero es un pilar de CONTEXTO: no
    vota direccion, y no existe una fila "proteccion contra inflacion" con su
    sesgo, su confianza y su señal. Lo que este test exige no es que se
    implemente --eso seria otra decision de cartera, con su propia evidencia--
    sino que el documento no deje creer que esta cubierta.
    """
    assert "inflacion" not in config.ASSET_CLASSES, (
        "si se implementa como dimension, este test hay que reescribirlo")
    assert "inflacion" in config.CONTEXT_PILLARS, (
        "la inflacion dejo de ser un pilar de contexto")
    for f in FECHAS:
        pm = _pm(_html(f))
        assert "contexto" in pm, f"{f}: no se dice que pilares son de contexto"
        assert 'class="pc-ctx"' in pm, (
            f"{f}: los pilares de contexto no se marcan en la capa PM")


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
