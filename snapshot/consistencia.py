# -*- coding: utf-8 -*-
"""Consistencia HTML <-> PM Brief (SPEC 12).

Que los dos salgan del mismo DecisionState es una propiedad del CODIGO. Esta
comprobacion no se fia de eso: coge los DOS DOCUMENTOS YA RENDERIZADOS y
verifica que cada conclusion aparece, literalmente, en ambos. Es la unica forma
de detectar que un template se dejo un valor, lo redondeo distinto o lo escribio
con otra palabra.

Si un valor esta en uno y no en el otro, uno de los dos miente, y hay que
saberlo antes de mandar el PDF al comite.
"""

from __future__ import annotations

import re
import unicodedata

import config


def texto(doc: str) -> str:
    """Texto visible de un documento HTML, normalizado para comparar."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", doc, flags=re.S | re.I)
    # Una etiqueta que cierra justo antes de un signo de puntuacion no separa
    # palabras: «distintas</b>:» es «distintas:», no «distintas :». Meterle un
    # espacio ahi inventaba una errata que no existe en la pagina.
    t = re.sub(r"(?:<[^>]+>)+(?=\s*[,;:.!?)\]»])", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
          .replace("–", "-").replace("—", "-"))
    t = unicodedata.normalize("NFKC", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def _norm(v) -> str:
    return unicodedata.normalize("NFKC", str(v)).strip().lower()


# El verbo que a cada bloque le corresponde en el brief. Sale del BLOQUE, que a
# su vez sale del efecto medido: si el brief escribiera otro, estaria contando
# algo distinto del HTML sobre el mismo umbral.
# Cada formato conjuga a su manera --el HTML en infinitivo dentro de una frase,
# la tabla del PDF en tercera persona-- y las dos son correctas. Lo que no puede
# variar es el VERBO: si un umbral se presenta como «debilita» en un sitio y
# «invalida» en otro, los documentos cuentan cosas distintas.
# El cruce de banda del eje enuncia su efecto nombrando el régimen nuevo --«el
# régimen pasa a X»--, que es mas informativo que el verbo generico y vale para
# cualquier bloque: el bloque lo sigue llevando el estado.
_REGIMEN = "el régimen pasa a"
_VERBO = {"confirma": ("reforzar la lectura", "refuerza la lectura", "refuerza",
                       "gana apoyo", "gana un apoyo", _REGIMEN),
          "debilita": ("debilitar la lectura", "debilita la lectura", "debilita",
                       "pierde apoyo", "pierde un apoyo", _REGIMEN),
          "invalida": ("invalidar la lectura", "invalida la lectura", "invalida",
                       "se queda sin dirección", "pasa a ", _REGIMEN)}

# El brief, cuando el contrafactual midio un salto de conviccion concreto, lo
# escribe en vez del verbo generico: «convicción media -> baja» dice mas que
# «debilita» y no toca a la lectura entera. Es la misma conclusion conjugada de
# otra manera, asi que vale como verbo SIEMPRE QUE VAYA EN EL SENTIDO DEL
# BLOQUE: un disparador que debilita no puede aparecer subiendo la conviccion.
# El brief dice «confianza» desde el pase semántico; el término técnico
# sigue vivo en Research. Se aceptan los dos: es la misma conclusión.
_SALTO = re.compile(r"(?:convicción|confianza) (alta|media|baja|neutral) → "
                    r"(alta|media|baja|neutral)")
_SENTIDO = {"confirma": 1, "debilita": -1, "invalida": -1}


def _dice_lo_mismo(bloque: str, ventana: str) -> bool:
    """El brief enuncia el efecto de ESTE bloque, en cualquiera de sus formas."""
    if any(v in ventana for v in _VERBO.get(bloque, ())):
        return True
    esperado = _SENTIDO.get(bloque)
    if esperado is None:
        return False
    orden = dict(config.CONV_ORDEN, neutral=0)
    for a, d in _SALTO.findall(ventana):
        salto = orden.get(d, 0) - orden.get(a, 0)
        if salto and (salto > 0) == (esperado > 0):
            return True
    return False


def _valor_umbral(cond: str) -> str:
    """El VALOR de la condición, sin el verbo que la introduce.

    «vuelve por debajo de 3.76 pp» -> «3.76 pp». Es lo que tiene que coincidir
    literalmente entre los dos documentos; el verbo lo pone cada formato con su
    propia redacción."""
    if not cond:
        return ""
    t = _norm(cond)
    for pref in ("vuelve por debajo de ", "vuelve por encima de ", "alcanza ",
                 "cae a ", "cruza "):
        if t.startswith(pref):
            return t[len(pref):]
    return t


# ---------------------------------------------- un indicador, un valor (A1)
# Un indicador tiene UN valor publicado. Si un sitio del documento lo escribe
# con otra cifra, el lector no tiene forma de saber cual es la buena, y la
# comprobacion que existia miraba el DecisionState --donde el valor es uno por
# construccion-- en vez del DOCUMENTO RENDERIZADO, que es donde puede romperse.
#
# Solo se revisan los indicadores con UNIDAD: la unidad ancla el numero. Sin
# ella («1.05») cualquier cifra del parrafo valdria como candidata y el check
# se llenaria de falsos positivos, que es peor que no tenerlo.
_UNIDADES = ("%", "pp", "x", "mil", "mm$")


def _valores_en(doc: str, nombres, unidad: str, ventana: int = 40) -> set[float]:
    """Las cifras que el documento escribe para ese indicador, con su unidad.

    Dos exclusiones, las dos necesarias para que el check no mienta:

    · El numero no puede EMPEZAR dentro de otro. Sin esa frontera, «+29.3 %»
      produce tambien «9.3 %» y el check se denuncia a si mismo.
    · Se descarta lo precedido de «<», «>» o «de », que introduce un UMBRAL:
      «cobre/oro +29.3 % <-3.7 %» publica el valor de hoy y su umbral, y los
      dos son correctos.
    """
    rx = re.compile(r"(?<![\d.,+-])([+-]?\d+(?:[.,]\d+)?)\s*" + re.escape(unidad)
                    + r"(?![\w])")
    out: set[float] = set()
    for nom in nombres:
        if not nom:
            continue
        i = doc.find(nom)
        while i >= 0:
            seg = doc[i + len(nom):i + len(nom) + ventana]
            for m in rx.finditer(seg):
                pre = seg[max(0, m.start() - 3):m.start()]
                if pre.endswith(("<", ">")) or pre.endswith("de "):
                    continue
                try:
                    out.add(round(float(m.group(1).replace(",", ".")), 4))
                except ValueError:
                    continue
            i = doc.find(nom, i + 1)
    return out


def valores_indicadores(snap: dict, html_doc: str, brief_doc: str) -> list[dict]:
    """Recorre los DOS documentos ya renderizados y exige un solo valor.

    Del HTML se mira la capa de LECTURA, no el documento entero: la sección de
    fuentes cita textos externos con su propia fecha --«la tasa real a 10 años
    sigue en +2.4 %», de un informe del 8 de septiembre-- y esa cifra es del
    autor citado, no de este tablero. Exigirle que coincida seria exigir que la
    prensa se corrija sola.
    """
    from snapshot import semantica
    filas = []
    docs = [(n, d) for n, d in (("HTML", semantica.solo_lectura(html_doc)),
                                ("brief", texto(brief_doc) if brief_doc else None))
            if d]
    if not docs:
        return filas
    for pil in (snap.get("tablero") or []):
        for f in pil.get("filas", []):
            unidad = (config.INDICATOR_BY_KEY.get(f["key"], {}) or {}).get("unit") or ""
            if unidad not in _UNIDADES:
                continue
            canon = _norm(str(f.get("valor") or ""))
            m = re.search(r"[+-]?\d+(?:[.,]\d+)?", canon)
            if not m:
                continue
            bueno = round(float(m.group(0).replace(",", ".")), 4)
            nombres = {_norm(config.SHORT.get(f["key"], "")), _norm(f["label"])}
            for nom_doc, doc in docs:
                malos = sorted(v for v in _valores_en(doc, nombres, unidad)
                               if v != bueno)
                if malos:
                    filas.append(dict(
                        indicador=f["label"], doc=nom_doc, publicado=bueno,
                        otros=malos, unidad=unidad))
    return filas


def _cerca(doc: str, ancla: str, valor: str, ventana: int = 320) -> bool:
    """`valor` aparece cerca de `ancla`, en alguna de sus apariciones.

    Buscar «media» suelta en un documento que la usa veinte veces no comprueba
    nada. Buscarla dentro de la fila de su tema, si.
    """
    if not doc or not ancla or not valor:
        return False
    i = doc.find(ancla)
    while i >= 0:
        if valor in doc[i:i + ventana]:
            return True
        i = doc.find(ancla, i + 1)
    return False


def comparar(snap: dict, html_doc: str, brief_doc: str) -> dict:
    """Compara las conclusiones que ambos formatos DEBEN compartir."""
    from snapshot import decision

    v = decision.valores_brief(snap)
    H, B = texto(html_doc), texto(brief_doc)
    filas: list[dict] = []

    def chk(campo, valor):
        if valor in (None, "", "—"):
            return
        s = _norm(valor)
        filas.append(dict(campo=campo, valor=str(valor),
                          html=s in H, brief=s in B))

    chk("régimen de riesgo", v["regimen_riesgo"])
    chk("postura", v["postura"])
    chk("convicción", v["conviccion"])
    # El timing tiene varias etiquetas legitimas --la frase explica, la cabeza
    # cabe en una cabecera-- y cada formato usa la que le sirve. Lo que no puede
    # variar es CUAL es: se acepta cualquiera de ellas, nunca otra.
    _t = v["timing"]
    # SEMANTIC-PASS 40: la primera forma de la lista es la que los dos
    # documentos publican hoy --SENAL_ESTADO--. Faltaba, y el comprobador
    # buscaba solo el vocabulario viejo: en 2008-09-15 ninguna de las cuatro
    # formas antiguas aparecia en el brief y la fila salia como divergencia
    # cuando los dos documentos decian exactamente lo mismo.
    _formas = [config.SENAL_ESTADO.get(_t), config.TIMING_CABEZA.get(_t),
               config.timing_frase(_t), config.TIMING_ES.get(_t, _t),
               config.TIMING_CORTO.get(_t, _t)]
    _formas = [x for x in _formas if x]
    if _formas:
        filas.append(dict(campo="timing", valor=" / ".join(_formas),
                          html=any(_norm(x) in H for x in _formas),
                          brief=any(_norm(x) in B for x in _formas)))
    # El titulo del setup solo se compara cuando HAY setup: "Sin setup táctico"
    # es un centinela de ausencia, y cada formato dice la ausencia a su manera
    # --el PDF en prosa--. Lo que no puede diferir es que exista o no, y eso se
    # comprueba aparte.
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    st = g.get("setup") or {}
    if st.get("existe"):
        chk("setup táctico", v["setup"])
    else:
        # Cada formato dice la AUSENCIA a su manera --el PDF en una linea, el
        # HTML en prosa--; lo que no puede diferir es que exista o no.
        _neg = ("sin setup", "sin overlay", "no hay ninguna condición táctica",
                "ninguna medida táctica")
        neg_h = any(x in H for x in _neg)
        neg_b = any(x in B for x in _neg)
        filas.append(dict(campo="ausencia de setup táctico", valor="sin setup",
                          html=neg_h, brief=neg_b))
    ten = snap.get("tension_principal")
    if ten:
        chk(config.TENSION_INDICADOR.lower(),
            config.SHORT.get(ten["key"], ten["label"]))
    # cada tema: postura y conviccion. SPEC-7P 17: la conviccion no se busca
    # suelta --«media» aparece veinte veces en cualquiera de los dos
    # documentos-- sino CERCA de su tema. Es lo que convierte la comprobacion
    # en una comparacion de campos y no en un buscar-palabra.
    for k, (postura, conv, _hz) in (v["temas"] or {}).items():
        lab = config.ASSET_CLASSES[k]["label"]
        chk(f"tema · {lab}", postura)
        if conv:
            filas.append(dict(campo=f"tema · {lab} · convicción", valor=conv,
                              html=_cerca(H, _norm(lab), _norm(conv)),
                              brief=_cerca(B, _norm(lab), _norm(conv))))
    # el ciclo, la tension dominante y el primer «que cambio»: los tres se
    # imprimen en los dos formatos y los tres pueden perderse en un template.
    ciclo = next((e for e in (snap.get("ejes") or []) if e.get("key") == "ciclo"), None)
    if ciclo is not None:
        nivel = ciclo.get("nivel")
        if nivel is not None and nivel == nivel:
            spec = config.AXES["ciclo"]
            chk("régimen de ciclo",
                spec["high"] if nivel >= 55 else spec["low"] if nivel <= 45 else "neutral")
    # La tension dominante se compara por sus DOS LADOS, que es como la
    # escriben los dos formatos («El crédito 84 ↔ La liquidez 40»). La frase
    # larga solo aparece cuando la conclusión la cita, así que compararla
    # marcaría una divergencia donde solo hay dos registros del mismo hecho.
    dom = snap.get("tension_dominante") or {}
    if dom.get("alto_label") and dom.get("bajo_label"):
        filas.append(dict(
            campo="tensión dominante",
            valor=f"{dom['alto_label']} ↔ {dom['bajo_label']}",
            html=all(_norm(x) in H for x in (dom["alto_label"], dom["bajo_label"])),
            brief=all(_norm(x) in B for x in (dom["alto_label"], dom["bajo_label"]))))
    wc = g.get("what_changed") or []
    if wc:
        chk("qué cambió", wc[0])
    # los valores numericos principales
    r = (snap.get("riesgo") or {})
    if r.get("hist_pct") is not None:
        chk("percentil del eje de riesgo", f"p{r['hist_pct']:.0f}")

    # --- los disparadores: el brief NO los recalcula ni los reetiqueta --------
    # Cada uno tiene que existir en el estado con el MISMO bloque, el MISMO
    # umbral y la MISMA distancia, y su umbral tiene que aparecer escrito en el
    # HTML. Si el brief dijera "debilitar" sobre un umbral que el HTML publica
    # como invalidante, los dos documentos estarian contando cosas distintas
    # sobre el mismo numero, que es exactamente lo que esta comprobacion existe
    # para impedir.
    estado = {}
    for bloque, items in (g.get("triggers") or {}).items():
        if bloque == "descartados":
            continue
        for t in items:
            estado[t["key"]] = (bloque, t.get("umbral"), t.get("sigmas"),
                                t.get("condicion"))
    for t in decision.triggers_brief(snap):
        k = t["key"]
        ref = estado.get(k)
        campo = f"disparador · {t['variable']}"
        if ref is None:
            filas.append(dict(campo=campo, valor="no está en el estado",
                              html=False, brief=True))
            continue
        bloque, umbral, sigmas, cond = ref
        # El umbral, tal como se escribe, tiene que aparecer en LOS DOS
        # documentos ya renderizados. Comparar el brief contra el estado del que
        # sale seria tautologico; lo que puede divergir es el texto publicado.
        val = _valor_umbral(cond)
        en_html = (val in H) if val else True
        en_brief = (val in B) if val else True
        # y el verbo del brief tiene que ser el de SU bloque, no otro
        verbo_ok = True
        if bloque in _VERBO and val and val in B:
            i = B.find(val)
            verbo_ok = _dice_lo_mismo(bloque, B[max(0, i - 260):i + 260])
        filas.append(dict(campo=campo,
                          valor=f"{bloque} · {cond} · "
                                f"{'—' if sigmas is None else f'{sigmas:.1f}σ'}",
                          html=bool(en_html),
                          brief=bool(en_brief and verbo_ok)))
        if t.get("sigmas") is not None and t["sigmas"] > config.BRIEF_SIGMA_MAX:
            filas.append(dict(campo=f"{campo} · al alcance",
                              valor=f"{t['sigmas']:.1f}σ supera el techo de "
                                    f"{config.BRIEF_SIGMA_MAX:.0f}σ del brief",
                              html=False, brief=False))

    malas = [f for f in filas if not (f["html"] and f["brief"])]
    return dict(filas=filas, total=len(filas), coinciden=len(filas) - len(malas),
                divergen=malas, ok=not malas)


def informe(res: dict) -> str:
    if res["ok"]:
        return (f"consistencia HTML/PDF: {res['coinciden']}/{res['total']} "
                f"conclusiones presentes en ambos")
    det = "; ".join(
        f"{f['campo']}=«{f['valor']}»"
        f" (falta en {'HTML' if not f['html'] else 'brief'})"
        for f in res["divergen"])
    return (f"consistencia HTML/PDF: DIVERGEN {len(res['divergen'])} de "
            f"{res['total']} -> {det}")
