# -*- coding: utf-8 -*-
"""QA SEMANTICO (SPEC-2P 11).

El QA que ya existia comprueba que los NUMEROS cuadren. Esto comprueba que lo
que el documento AFIRMA sea cierto: que no llame favorable a un percentil alto
por el hecho de ser alto, que diga el mismo metodo en los dos formatos, que un
disparador este en el bloque que le corresponde por su efecto medido, que
ninguna expresion preferida se publique sin evidencia detras y que el
condicional de cierre no este escrito al reves.

Son ocho comprobaciones y ninguna mira el texto exacto: miran la RELACION entre
lo que el estado calcula y lo que el documento dice. Un test contra una frase
literal se rompe al reescribir la frase; uno contra la relacion se rompe solo
cuando la relacion deja de ser cierta, que es cuando queremos que se rompa.

Cada comprobacion devuelve (estado, detalle):
  "ok"    la relacion se cumple
  "aviso" no se cumple, con el detalle de por que
  "nd"    no habia con que comprobarla (falta el documento, falta el dato)

SEVERIDAD (SPEC-7P 18). Un aviso no vale lo mismo que otro: que el marcador de
un espectro contradiga a su propia fila hace que el documento AFIRME algo
falso, y eso no puede salir; que un indicador lleve tres dias en extremo es
informacion que el lector tiene que ponderar. Cada comprobacion declara con
que severidad se lee su fallo --"error", "aviso" o "info"-- y `revisar` la
aplica. Lo que pasa nunca cambia de color: solo el fallo.
"""

from __future__ import annotations

import re
import unicodedata

import config


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    return re.sub(r"\s+", " ", t).strip().lower()


def _texto_docs(html_doc, brief_doc):
    from snapshot import consistencia
    h = consistencia.texto(html_doc) if html_doc else None
    b = consistencia.texto(brief_doc) if brief_doc else None
    return h, b


def solo_lectura(html_doc: str | None) -> str | None:
    """El HTML SIN las capas de evidencia y auditoria.

    Research y Auditoria listan los 42 indicadores por construccion, asi que
    buscar ahi un indicador reciente daria un falso positivo siempre. Lo que se
    revisa es la LECTURA --lo que el documento afirma-- no el rastro que la
    respalda.

    El corte se busca por varias marcas porque la arquitectura del HTML cambio:
    antes todo el rastro vivia dentro de un solo `<details class="tablero">` y
    ahora son dos secciones. Si ninguna marca aparece se revisa el documento
    entero, que es el lado conservador: prefiere un falso positivo a callarse.
    """
    if html_doc is None:
        return None
    from snapshot import consistencia
    doc = re.sub(r"<nav.*?</nav>", " ", html_doc, flags=re.S | re.I)
    for marca in ('<section id="sec-research"', '<details class="tablero">'):
        i = doc.find(marca)
        if i >= 0:
            doc = doc[:i]
            break
    # Y lo que vive detras de un desplegable CERRADO no es lo que el documento
    # afirma: es rastro que el lector pide. Un `<details open>` si cuenta.
    doc = re.sub(r"<details(?![^>]*open)[^>]*>.*?</details>", " ", doc,
                 flags=re.S | re.I)
    return consistencia.texto(doc)


# ===========================================================================
# 1 · percentile_definition_consistent
# ===========================================================================
def percentil(snap, H, B):
    """Ningun texto puede afirmar que un percentil alto es, por si mismo,
    favorable. El percentil es estadistica; la orientacion economica es otra
    capa. La excepcion legitima son los EJES y los PILARES, que si van
    orientados, y se reconoce por el contexto de la frase."""
    docs = [("HTML", H), ("PDF", B)]
    if all(d is None for _n, d in docs):
        return "nd", "no hay documentos renderizados que revisar"
    problemas = []
    for nombre, doc in docs:
        if doc is None:
            continue
        for mala in config.PERCENTIL_PROHIBIDO:
            if mala in doc:
                problemas.append(f"{nombre}: «{mala}»")
        # «100 = favorable» solo vale hablando de un eje, un pilar o un nivel.
        # La ventana se corta en el final de la ORACION anterior: si se mira un
        # bloque fijo de caracteres, cualquier «eje» de la frase de al lado
        # absuelve a la frase mala.
        for m in re.finditer(r"100\s*=\s*favorable", doc):
            atras = doc[max(0, m.start() - 200):m.start()]
            # solo finales de ORACION: los dos puntos introducen la misma
            # frase («Nivel del eje: 100 = favorable») y cortar ahi dejaria
            # fuera justo al sujeto que la hace legitima.
            corte = max(atras.rfind(". "), atras.rfind("; "))
            ventana = (atras[corte + 2:] if corte >= 0 else atras) + doc[m.start():m.end() + 60]
            if not any(p in ventana for p in config.PERCENTIL_CONTEXTO_OK):
                problemas.append(f"{nombre}: «100 = favorable» sin decir de qué")
        marca = config.METODOLOGIA_MARCA["percentil"]
        if marca not in doc:
            problemas.append(f"{nombre}: no publica la definición oficial del percentil")
    if problemas:
        return "aviso", "; ".join(problemas)
    return "ok", ("el percentil se define como posición frente a su propia "
                  "historia, y la orientación económica se enuncia aparte")


# ===========================================================================
# 2, 3, 4 · direction_method / cluster_role / conviction_method consistent
# ===========================================================================
def _metodo(snap, H, B, campo):
    """El campo viaja en el estado Y se enuncia igual en los dos formatos."""
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    esperado = config.METODOLOGIA[campo]
    if g.get(campo) != esperado:
        return "aviso", (f"el estado publica «{g.get(campo)}» y la configuración "
                         f"dice «{esperado}»")
    marca = config.METODOLOGIA_MARCA[campo]
    faltan = [n for n, d in (("HTML", H), ("PDF", B)) if d is not None and marca not in d]
    if faltan:
        return "aviso", (f"el estado lo publica, pero no aparece enunciado en: "
                         f"{', '.join(faltan)}")
    if H is None and B is None:
        return "nd", f"el estado publica «{esperado}»; sin documentos que contrastar"
    return "ok", f"«{esperado}», enunciado igual en los dos formatos"


def direccion_metodo(snap, H, B):
    return _metodo(snap, H, B, "direction_method")


def cluster_rol(snap, H, B):
    return _metodo(snap, H, B, "cluster_role")


def conviccion_metodo(snap, H, B):
    return _metodo(snap, H, B, "conviction_method")


# ===========================================================================
# 5 · trigger_classification_valid
# ===========================================================================
def triggers(snap, H, B):
    """Un disparador solo puede estar bajo «invalida» si el contrafactual midio
    que NEUTRALIZA o REVIERTE. Lo que solo quita apoyo va a «debilita»."""
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    trg = g.get("triggers") or {}
    if not trg:
        return "nd", "no se construyeron disparadores"
    problemas, medidos, sin_medir = [], 0, 0
    for bloque in ("confirma", "debilita", "invalida", "tactico"):
        for t in (trg.get(bloque) or []):
            ef = t.get("effect_type")
            if ef is None:
                sin_medir += 1
                continue
            medidos += 1
            if bloque == "invalida" and ef not in config.TRIGGER_INVALIDA:
                problemas.append(f"«{t['variable']}» en invalida con efecto {ef}")
            if bloque in ("confirma", "debilita") and ef in config.TRIGGER_INVALIDA:
                problemas.append(f"«{t['variable']}» en {bloque} con efecto {ef}")
            if ef != "tactical" and not (t.get("before_state") and t.get("after_state")):
                problemas.append(f"«{t['variable']}» sin estado antes/después")
    if problemas:
        return "aviso", "; ".join(problemas)
    cola = f"; {sin_medir} sin contrafactual" if sin_medir else ""
    return "ok", (f"{medidos} disparadores clasificados por el efecto medido al "
                  f"simular el cruce, no por la regla que los generó{cola}")


# ===========================================================================
# 6 · preferred_expression_has_provenance
# ===========================================================================
def expresiones(snap, H, B):
    """Ninguna expresion se publica sin al menos una señal que la sostenga."""
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    temas = g.get("temas") or []
    if not temas:
        return "nd", "no hay temas en el estado"
    problemas, con_apoyo = [], 0
    for t in temas:
        for campo in ("favorecer", "evitar"):
            e = t.get(campo)
            if not isinstance(e, dict):
                problemas.append(f"{t['label']}/{campo}: no lleva procedencia")
                continue
            if e.get("text") in (None, "", "—"):
                continue
            if not e.get("supported_by"):
                problemas.append(f"{t['label']}/{campo}: «{e['text']}» sin señales")
            else:
                con_apoyo += 1
    if problemas:
        return "aviso", "; ".join(problemas)
    return "ok", (f"{con_apoyo} expresiones publicadas, todas con al menos una "
                  f"señal que las apoya; el resto se deja en «—»")


# ===========================================================================
# 7 · narrative_direction_valid
# ===========================================================================
def direccion_narrativa(snap, H, B):
    """El condicional de cierre tiene que apuntar al lado correcto: un hecho que
    APOYA la postura la sostiene mientras persista; uno que la CONTRADICE,
    mientras no se imponga. Se comprueba la relacion, no la frase."""
    m = snap.get("condicional_meta")
    if not m:
        return "nd", "la prosa no registró de qué depende la lectura"
    if m.get("apoya") is None:
        return "ok", "la lectura no se apoya hoy en un hecho con dirección propia"
    esperado = "persiste" if m["apoya"] else "no_se_impone"
    if m.get("sentido") != esperado:
        return "aviso", (f"«{m['texto']}»: el hecho "
                         f"{'apoya' if m['apoya'] else 'contradice'} a la postura "
                         f"{m.get('postura')} y la frase está escrita en sentido "
                         f"«{m.get('sentido')}»")
    # y que el apoyo declarado coincida con el tablero, no solo consigo mismo
    if m.get("hecho") == "crecimiento":
        pg = (snap.get("postura_general") or {}).get("palabra")
        lect = (((snap.get("composites") or {}).get("afirm") or {})
                .get("economia_real") or {}).get("lect")
        real = ((lect == "favorable" and pg == "pro-riesgo") or
                (lect == "adverso" and pg == "defensiva"))
        if real != bool(m["apoya"]):
            return "aviso", (f"dice que el crecimiento {'apoya' if m['apoya'] else 'contradice'}, "
                             f"pero está {lect} con postura {pg}")
    return "ok", (f"«{m['texto']}»: la condición es la que, de incumplirse, "
                  f"debilitaría la lectura")


# ===========================================================================
# 8 · html_pdf_semantics_match
# ===========================================================================
def html_pdf(snap, H, B):
    """Los dos formatos tienen que enunciar el MISMO metodo y la MISMA
    definicion de percentil. La consistencia de cifras se comprueba aparte."""
    if H is None or B is None:
        return "nd", "hacen falta los dos documentos renderizados"
    faltan = []
    for k, marca in config.METODOLOGIA_MARCA.items():
        en_h, en_b = marca in H, marca in B
        if en_h != en_b:
            faltan.append(f"{k}: solo en {'HTML' if en_h else 'PDF'}")
    if faltan:
        return "aviso", "; ".join(faltan)
    return "ok", (f"las {len(config.METODOLOGIA_MARCA)} marcas de método "
                  f"aparecen en los dos documentos o en ninguno")


# ===========================================================================
# 9 · coherence_bullet_rendered  (SPEC 12, «Postura general vs clases»)
# ===========================================================================
def coherencia(snap, H, B):
    """Que la viñeta EXISTA en el estado no basta: tiene que estar ESCRITA en
    los dos documentos. El check anterior miraba el campo, y por eso no vio que
    al reescribir la página 1 del brief la viñeta había desaparecido del PDF."""
    linea = (getattr(snap.get("decision"), "guia", {}) or {}).get("coherencia")
    if not linea:
        return "ok", ("la postura general no difiere de renta variable ni de "
                      "duración: no hay nada que explicar")
    if H is None and B is None:
        return "nd", "sin documentos renderizados que revisar"
    marca = "se expresa hoy por"
    faltan = [n for n, d in (("HTML", H), ("PDF", B))
              if d is not None and marca not in d]
    if faltan:
        return "aviso", (f"la síntesis explica por qué difieren, pero la viñeta "
                         f"no aparece en: {', '.join(faltan)}")
    return "ok", f"«{linea[:80]}…» escrita en los dos formatos"


# ===========================================================================
# 10 · recent_indicators_outside_context  (SPEC 7.1)
# ===========================================================================
def recientes(snap, H, B):
    """Ningún indicador RECIENTE puede aparecer en la lectura salvo dicho como
    contexto. Se recorre el OUTPUT RENDERIZADO, no los selectores uno por uno:
    aplicar la regla selector a selector falló tres veces seguidas --tensión,
    disparadores, evidencia-- porque siempre quedaba uno sin ella."""
    pers = snap.get("persistencia") or {}
    recs = [k for k, v in pers.items() if v.get("reciente")]
    if not recs:
        return "ok", "ningún indicador está en un extremo demasiado reciente"
    if H is None and B is None:
        return "nd", f"{len(recs)} indicadores recientes; sin documentos que revisar"
    malos = []
    for nombre, doc in (("HTML", H), ("PDF", B)):
        if doc is None:
            continue
        for k in recs:
            corto = _norm(config.SHORT.get(k, k))
            i = doc.find(corto)
            while i >= 0:
                ventana = doc[max(0, i - 200):i + 200]
                if "contexto" not in ventana and "reciente" not in ventana:
                    malos.append(f"{nombre}: {config.SHORT.get(k, k)}")
                    break
                i = doc.find(corto, i + 1)
    if malos:
        return "aviso", ("usados fuera de contexto -> " + "; ".join(sorted(set(malos))))
    return "ok", (f"{len(recs)} indicadores en extremo reciente; ninguno se usa "
                  f"en la lectura salvo dicho como contexto")

def regimen_banda(snap, H, B):
    """SPEC-7P 1: la etiqueta del regimen y la banda de su percentil.

    Pueden discrepar legitimamente: el regimen lleva histeresis y una mejora
    tarda unos dias en confirmarse. Lo que NO puede pasar es que discrepen y el
    documento no lo diga, porque entonces imprime «neutral · p75» y el lector
    lee que p75 es neutral. Si discrepan sin transicion que lo explique, es un
    error del clasificador.
    """
    t = (snap.get("titular") or {})
    tr = t.get("transicion") or {}
    if not tr or tr.get("banda_pct") is None:
        return "nd", "sin percentil del eje con el que comparar"
    if tr.get("coincide"):
        return "ok", (f"«{t.get('estado')}» es la banda de p{tr['pct']:.0f}")
    txt = t.get("transicion_txt") or ""
    if not txt:
        return "error", (f"el estado dice «{t.get('estado')}» y p{tr['pct']:.0f} "
                         f"cae en «{tr['banda_pct']}», sin transición que lo explique")
    for doc, nom in ((H, "HTML"), (B, "brief")):
        if doc and _norm(txt)[:40] not in _norm(doc):
            return "error", f"la transición de régimen no está escrita en el {nom}"
    return "ok", (f"«{t.get('estado')}» y p{tr['pct']:.0f} discrepan por la "
                  f"histéresis, y los dos documentos lo dicen: {txt}")


def valores(snap, H, B):
    """SPEC-7P A1: un indicador, UN valor publicado, en los dos documentos.

    La comprobacion que existia miraba el DecisionState, donde el valor es uno
    por construccion: no podia cazar nada. Esta recorre el DOCUMENTO
    RENDERIZADO, que es donde el valor puede romperse --un template que
    recalcula, una ventana distinta, un suavizado mezclado con un cierre--.
    """
    from snapshot import consistencia
    # H y B llegan aqui como los documentos EN CRUDO (ver `revisar`): esta
    # comprobacion necesita el HTML sin extraer para poder quitarle la capa de
    # fuentes, que cita cifras ajenas con su propia fecha.
    if not H and not B:
        return "nd", "sin documentos renderizados que revisar"
    malas = consistencia.valores_indicadores(snap, H, B)
    if malas:
        det = "; ".join(f"{m['doc']}: {m['indicador']} publica {m['publicado']}"
                        f"{m['unidad']} y también {m['otros']}" for m in malas[:4])
        return "error", det
    n = sum(1 for pil in (snap.get("tablero") or []) for f in pil.get("filas", [])
            if (config.INDICATOR_BY_KEY.get(f["key"], {}) or {}).get("unit")
            in consistencia._UNIDADES)
    return "ok", (f"{n} indicadores con unidad; cada uno aparece con un solo "
                  f"valor en los dos documentos")


def espectro_sesgo(snap, H, B):
    """SPEC-7P 3: el marcador del espectro, del lado que dice el sesgo."""
    from snapshot import brief as _b
    temas = ((getattr(snap.get("decision"), "guia", {}) or {}).get("temas") or [])
    if not temas:
        return "nd", "sin temas publicados"
    malas = _b._qa_espectro(temas)
    if malas:
        return "error", "; ".join(malas)
    return "ok", f"las {len(temas)} filas marcan el lado de su sesgo publicado"


# Lo que la redaccion generada rompe cuando se concatena sola. No es estilo:
# son erratas que delatan una frase compuesta por partes.
_COPIA = [
    (r"\ba el\b", "«a el» en vez de «al»"),
    (r"\bde el\b", "«de el» en vez de «del»"),
    (r"\b([a-záéíóúñü]{4,})\s+\1\b", "palabra repetida"),
    (r"[ \t]{2,}", "espacio doble"),
    # Exige una PALABRA antes del hueco: la marca de bloque «¶» que introduce
    # `prosa()` tambien va seguida de espacio, y no es una errata.
    (r"[\wáéíóúñü][ \t]+[,;:.]", "espacio antes de puntuación"),
    (r"\b([a-záéíóúñü]{3,})\s+de\s+\1\b", "«X de X»"),
    (r"confirmaci[oó]n[^.;]{0,30}confirmaci[oó]n", "«confirmación» dos veces seguidas"),
    (r"\b1 (clases|semanas|meses|días|puntos)\b", "singular con sustantivo plural"),
    (r"«[^»]{0,120}$", "comilla angular sin cerrar"),
    (r"\b(el|la|los|las) (el|la|los|las)\b", "artículo duplicado"),
]


def prosa(doc: str | None) -> str | None:
    """El texto del documento con una MARCA en cada borde de bloque o celda.

    Sin ella, «Desfavorable» en una celda y «Favorable» en la siguiente se leen
    como una frase seguida, y dos celdas con el mismo valor producen una
    «palabra repetida» que no existe. Las erratas que se buscan aqui son de
    prosa: solo tienen sentido DENTRO de un mismo bloque de texto.
    """
    if doc is None:
        return None
    from snapshot import consistencia
    t = re.sub(r"<(script|style|nav|select)\b[^>]*>.*?</\1>", " ", doc,
               flags=re.S | re.I)
    t = re.sub(r"</(td|th|li|p|div|h[1-6]|span|tr|option|summary)\s*>", " ¶ ",
               t, flags=re.I)
    return consistencia.texto(t)


def copia(snap, H, B):
    """SPEC-7P 15: erratas de la prosa generada, en los dos documentos."""
    if not B:
        return "nd", "sin documentos con los que comprobar"
    malos = []
    for doc, nom in ((H, "HTML"), (B, "brief")):
        if not doc:
            continue
        for pat, que in _COPIA:
            m = re.search(pat, doc)
            if m:
                frag = doc[max(0, m.start() - 30):m.end() + 30].strip()
                malos.append(f"{nom}: {que} -> …{frag}…")
    if malos:
        return "aviso", "; ".join(malos[:4])
    return "ok", f"{len(_COPIA)} patrones de errata, ninguno presente"


# ===========================================================================
# (clave, etiqueta, funcion, severidad del FALLO)
CHECKS = [
    ("regime_label_matches_band", "Régimen: etiqueta y banda del percentil",
     regimen_banda, "error"),
    ("spectrum_marker_matches_bias", "Espectro: marcador del lado del sesgo",
     espectro_sesgo, "error"),
    ("indicator_value_single", "Un indicador, un valor en el documento",
     valores, "error"),
    ("percentile_definition_consistent", "Percentil: estadística y orientación separadas",
     percentil, "error"),
    ("html_pdf_semantics_match", "HTML y PDF: mismo método enunciado", html_pdf, "error"),
    ("direction_method_consistent", "Método de dirección, igual en todas partes",
     direccion_metodo, "aviso"),
    ("cluster_role_consistent", "El cluster, declarado como diagnóstico paralelo",
     cluster_rol, "aviso"),
    ("conviction_method_consistent", "Método de convicción, igual en todas partes",
     conviccion_metodo, "aviso"),
    ("trigger_classification_valid", "Disparadores en el bloque de su efecto medido",
     triggers, "error"),
    ("preferred_expression_has_provenance", "Expresiones preferidas con procedencia",
     expresiones, "aviso"),
    ("narrative_direction_valid", "Dirección del condicional de cierre",
     direccion_narrativa, "error"),
    ("coherence_bullet_rendered", "Postura general vs clases, escrita en ambos",
     coherencia, "aviso"),
    ("copy_quality", "Erratas de la prosa generada", copia, "aviso"),
    ("recent_indicators_outside_context",
     "Indicadores recientes usados fuera de contexto", recientes, "aviso"),
]


def revisar(snap: dict, html_doc: str | None = None,
            brief_doc: str | None = None) -> list[dict]:
    """Corre las ocho. Nunca lanza: una comprobacion que revienta se reporta
    como aviso, porque un QA que se cae en silencio es peor que no tenerlo."""
    H, B = _texto_docs(html_doc, brief_doc)
    H_lect = solo_lectura(html_doc)
    out = []
    # Dos comprobaciones miran la LECTURA del HTML, no el documento entero: la
    # de indicadores recientes, porque en el tablero los 42 estan por
    # construccion; y la de erratas, porque el indice lateral repite los
    # nombres de las secciones y eso no es una errata de la prosa.
    _LECTURA = ("recent_indicators_outside_context",)
    for clave, etiqueta, fn, sever in CHECKS:
        try:
            if clave == "copy_quality":
                estado, detalle = fn(snap, prosa(html_doc), prosa(brief_doc))
            elif clave == "indicator_value_single":
                estado, detalle = fn(snap, html_doc, brief_doc)
            else:
                estado, detalle = fn(snap, H_lect if clave in _LECTURA else H, B)
        except Exception as e:                                   # noqa: BLE001
            estado, detalle = "error", f"la comprobación falló: {type(e).__name__}: {e}"
        # Un fallo se lee con la severidad que la comprobacion declara; lo que
        # pasa o no se puede calcular no cambia de color.
        if estado == "aviso":
            estado = sever
        elif estado == "nd":
            estado = "nd"
        out.append(dict(clave=clave, label=etiqueta, estado=estado,
                        severidad=sever, nota=detalle))
    return out


def resumen(filas: list[dict]) -> str:
    n_ok = sum(1 for f in filas if f["estado"] == "ok")
    n_er = sum(1 for f in filas if f["estado"] == "error")
    n_av = sum(1 for f in filas if f["estado"] == "aviso")
    n_nd = sum(1 for f in filas if f["estado"] == "nd")
    partes = [f"{n_ok} ok"]
    if n_er:
        partes.append(f"{n_er} ERROR")
    partes.append(f"{n_av} avisos")
    partes.append(f"{n_nd} sin datos")
    return ", ".join(partes) + f", de {len(filas)}"
