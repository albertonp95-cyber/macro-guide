# -*- coding: utf-8 -*-
"""PM BRIEF (SPEC 11) — el segundo output, para comité, CIO y morning meeting.

NO es el HTML impreso. Es un TEMPLATE PROPIO: otra retícula, otra jerarquía,
otro nivel de detalle. El HTML es para auditar; esto es para decidir en cuatro
minutos. Los 42 indicadores no entran aquí: viven en el HTML.

DE DONDE SALE. Del MISMO DecisionState que el HTML. Aquí no se decide nada, no
se recalcula nada y no se aplica ningún umbral: si el brief necesitara un
cálculo que no está en la capa, el cálculo va a la capa (SPEC 2).

PAGINACION. SPEC pide "cuatro páginas excelentes antes que seis artificialmente
llenas" y fija el criterio: si una página quedaría por debajo de DOS TERCIOS de
contenido, se funde con la anterior. Para poder aplicarlo hay que medir, así que
cada bloque declara su altura estimada en LINEAS y `paginar()` las empaqueta.
No se rellena nada para cuajar una página.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

import numpy as np

import config

# Altura UTIL de una A4 con los margenes de este template, EN PIXELES CSS
# (297mm - 15 - 13 de margen, a 96 dpi). Las alturas de cada bloque se estiman
# tambien en pixeles, con coeficientes MEDIDOS sobre el render real --no
# inventados--, porque el criterio de SPEC ("por debajo de dos tercios se funde")
# solo significa algo si se mide contra la pagina de verdad.
CAP = 1017
FRAC_MIN = 2 / 3          # por debajo de esto, la pagina se funde con la anterior

_HZ = {"tactical": "táctico", "intermediate": "intermedio", "estructural": "estructural",
       "—": "—", "sin dato": "sin dato"}


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def _cap(t: str) -> str:
    return (t[0].upper() + t[1:]) if t else t


def num(x) -> str:
    """Formato del proyecto: punto decimal, coma de millares."""
    return str(x)


@dataclass
class Bloque:
    """Un bloque de contenido con su altura estimada, en lineas."""
    titulo: str
    html: str
    lineas: int
    seccion: str


@dataclass
class Pagina:
    n: int
    bloques: list[Bloque] = field(default_factory=list)
    fundida: bool = False

    @property
    def lineas(self) -> int:
        """Altura estimada de la pagina, en pixeles CSS."""
        return sum(b.lineas for b in self.bloques)

    @property
    def fraccion(self) -> float:
        return self.lineas / CAP


# ---------------------------------------------------------------- paginacion
def paginar(bloques: list[Bloque]) -> tuple[list[Pagina], list[str]]:
    """Empaqueta las secciones en paginas y aplica el criterio de SPEC 11.

    Primero una seccion por pagina, que es la estructura que pide el spec.
    Despues, de atras hacia delante, cualquier pagina por debajo de dos tercios
    se funde con la anterior SI cabe entera. Se devuelve tambien el registro de
    por que salio cada pagina, que es lo que hay que poder reportar.
    """
    paginas: list[Pagina] = []
    for b in bloques:
        if not paginas or paginas[-1].bloques[0].seccion != b.seccion:
            paginas.append(Pagina(n=len(paginas) + 1, bloques=[b]))
        else:
            paginas[-1].bloques.append(b)

    log: list[str] = []
    for p in paginas:
        log.append(f"«{p.bloques[0].seccion}»: {p.lineas} px "
                   f"({100 * p.fraccion:.0f}% de la página)")

    # Fusion. SPEC dice "se funde con la ANTERIOR", asi que ese es el primer
    # intento. Pero si la anterior ya va llena, fundir hacia atras es imposible y
    # la pagina flaca se quedaria sola --el caso real: un «What Changed» de tres
    # lineas ocupando una hoja al 9%--. Cuando la anterior no admite, se prueba
    # con la SIGUIENTE, que es la unica forma de cumplir el proposito de la regla:
    # no dejar hojas casi vacias.
    i = len(paginas) - 1
    while i > 0:
        p = paginas[i]
        if p.fraccion >= FRAC_MIN:
            i -= 1
            continue
        ant = paginas[i - 1]
        sig = paginas[i + 1] if i + 1 < len(paginas) else None
        if (ant.lineas + p.lineas) <= CAP:
            log.append(f"  → «{p.bloques[0].seccion}» ({100 * p.fraccion:.0f}%) "
                       f"se funde con «{ant.bloques[0].seccion}»: por debajo de "
                       f"dos tercios y cabe entera")
            ant.bloques.extend(p.bloques)
            paginas.pop(i)
        elif sig is not None and (sig.lineas + p.lineas) <= CAP:
            log.append(f"  → «{p.bloques[0].seccion}» ({100 * p.fraccion:.0f}%) "
                       f"se funde con «{sig.bloques[0].seccion}»: la anterior ya "
                       f"va llena y quedaría una hoja casi vacía")
            sig.bloques[:0] = p.bloques
            paginas.pop(i)
        else:
            log.append(f"  → «{p.bloques[0].seccion}» ({100 * p.fraccion:.0f}%) "
                       f"se queda sola: no cabe ni con la anterior ni con la siguiente")
        i -= 1
    for k, p in enumerate(paginas, 1):
        p.n = k
    return paginas, log


# ------------------------------------------------------------------ bloques
# ===========================================================================
# GRAFICOS DEL BRIEF (sexta pasada)
# ===========================================================================
# El problema de la version anterior no era falta de contenido: era que media
# pagina estaba vacia mientras la otra media pedia leer cuatro parrafos. Estos
# cuatro graficos ocupan ese hueco haciendo trabajo, no decorandolo.
#
# Todos se dibujan en SVG en linea, con las mismas tintas del documento. Nada
# de gauges, tartas ni iconos: son graficos de research en blanco y negro con
# tres tintas de estado.

_TINTA = {"fav": "#3f6b4a", "adv": "#9b3a3a", "neu": "#b9b2a5",
          "warn": "#8a6d1f", "ink": "#1b1a17", "rule": "#e2ddd4",
          "faint": "#9a948a", "muted": "#6d685f"}


def _g_fuerzas(snap) -> str:
    """Que empuja al regimen y que lo frena.

    Son los niveles de PILAR que el tablero ya publica, todos en la misma
    escala orientada 0-100 con 50 = neutral. Es lo unico que se puede poner en
    un mismo eje: mezclar aqui un diferencial en puntos porcentuales no
    significaria nada. Responde de un vistazo por que la conviccion no es mas
    alta --se ve quien tira en contra-- sin tener que leer siete filas.
    """
    pil = [p for p in snap.get("tablero", []) if np.isfinite(p.get("score", np.nan))]
    if not pil:
        return ""
    pil = sorted(pil, key=lambda p: -p["score"])
    # La columna de etiquetas necesita sitio de verdad: «Posicionamiento» no
    # cabe en 36 px, y recortarla deja «...miento», que no se lee.
    # SPEC-6P 28: a 15 px por fila el grafico cabia en 121 px y no se leia; el
    # hueco estaba justo debajo. Las barras respiran y ocupan el sitio que ya
    # era suyo.
    W, FILA, TOP = 337, 32, 26
    H = TOP + FILA * len(pil) + 8
    LAB = 92.0                      # ancho reservado a los nombres
    cx, semi = LAB + (W - 28 - LAB) / 2.0, (W - 28 - LAB) / 2.0
    cuerpo = ""
    for i, p in enumerate(pil):
        y = TOP + i * FILA
        v = float(p["score"])
        x = cx + (v - 50.0) * semi / 50.0
        x0, w = (cx, x - cx) if v >= 50 else (x, cx - x)
        col = _TINTA["fav"] if p["lectura"] == "favorable" else (
            _TINTA["adv"] if p["lectura"] == "adverso" else _TINTA["neu"])
        ctx = "" if p.get("eje") else "\u2009\u00b7\u2009ctx"
        cuerpo += (f'<rect x="{x0:.1f}" y="{y - 7:.1f}" width="{max(w, 1.0):.1f}" '
                   f'height="13" fill="{col}" opacity=".85"/>'
                   f'<text x="0" y="{y + 3:.1f}" class="g-l">'
                   f'{esc(_pil_corto(p))}{ctx}</text>'
                   f'<text x="{W - 1}" y="{y + 3:.1f}" class="g-v">{v:.0f}</text>')
    hay_ctx = any(not p.get("eje") for p in pil)
    return (f'<div class="g"><div class="g-h">Qué está impulsando el régimen'
            + (f'<span class="g-k">ctx = {esc(config.CTX_NOTA)}</span>'
               if hay_ctx else "") + f'</div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" '
            f'role="img" aria-label="Qué está impulsando el régimen. Cada '
            f'fuerza con su nota de 0 a 100; 50 es neutral.">'
            f'<line x1="{cx}" y1="10" x2="{cx}" y2="{H - 4}" stroke="{_TINTA["rule"]}"/>'
            f'<text x="{cx}" y="{TOP - 13:.0f}" class="g-c" text-anchor="middle">'
            f'50 · neutral</text>{cuerpo}</svg></div>')


def _pil_corto(p: dict) -> str:
    """El nombre canonico del pilar (SPEC-7P 8), no un recorte de su etiqueta.

    Partir «Liquidez y política monetaria» por el « y » funcionaba, pero dejaba
    el nombre del grafico a merced de como estuviera redactada la etiqueta, y
    sin relacion con el que usa la prosa. Ahora los dos salen del mismo sitio.
    """
    return config.PILAR_NOMBRE.get(p.get("key"), (p.get("label") or "").split(" y ")[0])


def _g_trayectoria(snap) -> str:
    """Los dos ejes en los ultimos doce meses.

    Responde a si el regimen de hoy es nuevo, lleva tiempo o se esta dando la
    vuelta. Doce meses y no cinco años: en el PDF el detalle largo no se lee, y
    la pregunta es sobre el regimen vigente, no sobre la historia.
    """
    sp = snap.get("serie_puntuacion") or {}
    ser = sp.get("series") or {}
    r, c = ser.get("riesgo") or [], ser.get("ciclo") or []
    if len(r) < 4:
        return ""
    r, c = r[-13:], c[-13:]
    # Misma altura que «Fuerzas del régimen»: los dos graficos de la pagina 1
    # se leen como un par, y si no coinciden la rejilla se nota rota.
    W, H = 337, 256
    L, T, B = 30, 16, 22
    ancho, alto = W - L - 4, H - T - B

    def px(i, n):
        return L + (ancho * i / max(1, n - 1))

    def py(v):
        return T + alto * (1 - max(0.0, min(100.0, v)) / 100.0)

    bandas = ""
    for lo, hi, _n in config.STATE_BANDS:
        if lo in (0,) or hi >= 101:
            continue
        bandas += (f'<line x1="{L}" y1="{py(lo):.1f}" x2="{W - 4}" y2="{py(lo):.1f}" '
                   f'stroke="{_TINTA["rule"]}" stroke-dasharray="1.5 2.5"/>')

    def linea(serie, col, ancho_t):
        d = " ".join(f'{"M" if i == 0 else "L"}{px(i, len(serie)):.1f},'
                     f'{py(v):.1f}' for i, (_d, v) in enumerate(serie))
        return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{ancho_t}"/>'

    ult_r, ult_c = r[-1], c[-1]
    marcas = (f'<circle cx="{px(len(r) - 1, len(r)):.1f}" cy="{py(ult_r[1]):.1f}" r="3.4" '
              f'fill="{_TINTA["ink"]}"/>'
              f'<circle cx="{px(len(c) - 1, len(c)):.1f}" cy="{py(ult_c[1]):.1f}" r="3.4" '
              f'fill="{_TINTA["muted"]}"/>')
    ejes = (f'<text x="{L - 4}" y="{py(100) + 3:.1f}" class="g-a" text-anchor="end">100</text>'
            f'<text x="{L - 4}" y="{py(50) + 3:.1f}" class="g-a" text-anchor="end">50</text>'
            f'<text x="{L - 4}" y="{py(0) + 3:.1f}" class="g-a" text-anchor="end">0</text>'
            f'<text x="{L}" y="{H - 4}" class="g-a">'
            f'{esc(_MES[r[0][0].month - 1])} {r[0][0].year}</text>'
            f'<text x="{W - 4}" y="{H - 4}" class="g-a" text-anchor="end">'
            f'{esc(_MES[r[-1][0].month - 1])} {r[-1][0].year}</text>')
    return (f'<div class="g"><div class="g-h">Trayectoria · 12 meses'
            f'<span class="g-k"><i class="k-r"></i>riesgo '
            f'<b>{ult_r[1]:.0f}</b><i class="k-c"></i>ciclo '
            f'<b>{ult_c[1]:.0f}</b></span></div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" '
            f'aria-label="Trayectoria de los ejes de riesgo y ciclo en doce meses. '
            f'Riesgo termina en {ult_r[1]:.0f}, ciclo en {ult_c[1]:.0f}.">'
            f'{bandas}{linea(c, _TINTA["muted"], 1.3)}'
            f'{linea(r, _TINTA["ink"], 2.1)}{marcas}{ejes}</svg></div>')


_MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
        "nov", "dic"]


def _espectro_lados(t: dict) -> dict:
    """Las puntas del espectro. La REGLA vive en la capa común (SPEC-7P B6):
    el brief y el HTML dibujan la misma fila, y con la regla duplicada en dos
    plantillas ya se separaron una vez."""
    from snapshot import decision as _d
    return _d.espectro_lados(t)


def _qa_espectro(temas: list) -> list[str]:
    """SPEC-7P 3: el punto tiene que caer en el lado que dice el sesgo publicado.

    Es la comprobacion que hace fiable al grafico. Si el marcador y la etiqueta
    se separaran --y ya paso una vez, con duracion marcada «corta» y el punto
    sobre «larga»-- el documento estaria afirmando lo contrario de su propia
    tabla, y eso no puede salir impreso.
    """
    malas = []
    for t in temas:
        lados = _espectro_lados(t)
        rsg = float(t.get("paso") or 0)
        lado = (rsg > 0) - (rsg < 0)
        dt = t.get("dir_tipo") or "neutral"
        esperado = 0 if dt == "neutral" else (1 if dt == lados["pro"] else -1)
        if lado != esperado:
            malas.append(f"{t.get('label')}: sesgo «{t.get('sesgo')}» "
                         f"({dt}) pero el marcador cae a "
                         f"{'la derecha' if lado > 0 else 'la izquierda' if lado < 0 else 'el centro'}")
    return malas


def _g_espectro(t: dict) -> str:
    """El espectro de UNA dimension, con sus propias palabras en las puntas.

    Una sola convencion para toda la pagina --defensivo a la izquierda,
    pro-riesgo a la derecha-- y cada tema nombra sus dos lados. La punta del
    lado en el que cae el punto va en tinta; la otra, apagada: asi la direccion
    se ve antes de leer ninguna palabra.
    """
    lados = _espectro_lados(t)
    rsg = float(t.get("paso") or 0)
    lado = (rsg > 0) - (rsg < 0)
    fuerza = {"alta": 2.0, "media": 1.35, "baja": 0.75}.get(t.get("conviccion"), 0.0)
    pos = 50 + lado * (fuerza if lado else 0.0) * 22.0
    col = _TINTA["fav"] if lado > 0 else (_TINTA["adv"] if lado < 0 else _TINTA["neu"])
    W, H = 170, 20
    x = W * pos / 100.0
    ticks = "".join(f'<line x1="{W * (50 + k * 22) / 100:.1f}" y1="6" '
                    f'x2="{W * (50 + k * 22) / 100:.1f}" y2="12" '
                    f'stroke="{_TINTA["rule"]}"/>' for k in (-2, -1, 0, 1, 2))
    ci = " on" if lado < 0 else ""
    cd = " on" if lado > 0 else ""
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" class="esp" '
            f'role="img" aria-label="{esc(t.get("sesgo") or "Neutral")}, '
            f'de {esc(lados["izq"])} a {esc(lados["der"])}">'
            f'<line x1="0" y1="9" x2="{W}" y2="9" stroke="{_TINTA["rule"]}"/>'
            f'{ticks}<circle cx="{x:.1f}" cy="9" r="4.2" fill="{col}"/></svg>'
            f'<div class="esp-e"><span class="l{ci}">{esc(lados["izq"])}</span>'
            f'<span class="r{cd}">{esc(lados["der"])}</span></div>')


def _g_proximidad(snap) -> str:
    """Que umbral esta mas cerca de cumplirse: un punto sobre una escala.

    SPEC-7P 6. La version de barras obligaba a saber que la barra LARGA era la
    CERCANA --una convencion inventada, y del reves respecto al numero que la
    acompanaba--. Un punto sobre un eje de sigmas no necesita convencion: se
    lee donde cae, y cae mas a la izquierda cuanto menos le falta.

    La distancia va ESTANDARIZADA en sigmas del propio indicador, que es lo
    unico comparable entre variables con unidades distintas. El cruce de banda
    del eje no tiene sigmas, asi que no entra aqui y se queda en la tabla:
    inventarle una medida para que salga en el grafico seria peor que omitirlo.
    """
    from snapshot import decision as _d
    trg = [t for t in _d.triggers_brief(snap) if t.get("sigmas") is not None]
    if not trg:
        return ""
    trg = sorted(trg, key=lambda t: t["sigmas"])
    tope = config.BRIEF_SIGMA_MAX
    W, FILA, TOP = 688, 30, 40
    A0, A1 = 208.0, 636.0                       # 0 sigma .. tope sigma
    H = TOP + FILA * len(trg) + 6

    def xs(sig):
        return A0 + (A1 - A0) * max(0.0, min(1.0, sig / tope))

    # La escala, una sola vez y arriba: ticks enteros y las dos palabras que
    # dicen hacia donde se lee.
    eje = (f'<text x="{A0}" y="{TOP - 27:.0f}" class="g-c">CERCA</text>'
           f'<text x="{A1:.0f}" y="{TOP - 27:.0f}" class="g-c" '
           f'text-anchor="end">LEJOS</text>')
    for k in range(0, int(tope) + 1):
        x = xs(k)
        eje += (f'<line x1="{x:.1f}" y1="{TOP - 22:.0f}" x2="{x:.1f}" '
                f'y2="{H - 4}" stroke="{_TINTA["rule"]}" '
                f'stroke-dasharray="1.5 3"/>'
                f'<text x="{x:.1f}" y="{TOP - 13:.0f}" class="g-a" '
                f'text-anchor="middle">{k}σ{"+" if k == int(tope) else ""}</text>')
    eje += (f'<line x1="{A0}" y1="{TOP - 9:.0f}" x2="{A1:.0f}" '
            f'y2="{TOP - 9:.0f}" stroke="{_TINTA["ink"]}" stroke-width="0.8"/>')

    cuerpo = ""
    for i, t in enumerate(trg):
        y = TOP + i * FILA
        x = xs(t["sigmas"])
        col = {"invalida": _TINTA["adv"], "debilita": _TINTA["warn"],
               "confirma": _TINTA["fav"]}.get(t.get("bloque"), _TINTA["neu"])
        # El valor pegado al punto, no en una columna lejana: asi la cifra y su
        # posicion se leen de una vez.
        # `.g-v` lleva text-anchor:end en la hoja de estilo, y una regla CSS
        # gana a un atributo de presentacion: poniendo anchor="start" en el
        # atributo, la cifra seguia dibujandose a la izquierda y se montaba
        # encima de su propio punto. La clase lo resuelve en el mismo lenguaje.
        lejos = x > (A0 + A1) / 2
        vx, cls = (x - 9, "g-v") if lejos else (x + 9, "g-v ini")
        cuerpo += (f'<text x="0" y="{y + 3:.0f}" class="g-l">{esc(t["variable"])}</text>'
                   f'<line x1="{A0}" y1="{y:.0f}" x2="{A1:.0f}" y2="{y:.0f}" '
                   f'stroke="{_TINTA["rule"]}"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.0f}" r="4.6" fill="{col}"/>'
                   f'<text x="{vx:.1f}" y="{y + 3:.0f}" class="{cls}">'
                   f'{t["sigmas"]:.1f}σ</text>')
    return (f'<div class="g gw"><div class="g-h">Distancia al umbral'
            f'<span class="g-k">en desviaciones típicas del propio '
            f'indicador</span></div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" '
            f'aria-label="Distancia de cada disparador a su umbral, en '
            f'desviaciones típicas: cuanto menor, más cerca">'
            f'{eje}{cuerpo}</svg></div>')


def _b_regimen(snap) -> Bloque:
    """Página 1 — ¿QUÉ PIENSO?

    Cuatro niveles de peso visual y dos gráficos. La versión anterior dejaba
    media página en blanco mientras la otra media pedía leer cuatro párrafos;
    ese hueco lo ocupan ahora las fuerzas del régimen y la trayectoria, que
    responden «por qué esta postura» y «¿es nueva?» sin una línea de prosa.
    """
    ds = snap["decision"]
    g = ds.guia
    pg = snap.get("postura_general") or {}
    t = snap["titular"]
    r, c = ds.ejes.get("riesgo"), ds.ejes.get("ciclo")

    # SEMANTIC-PASS 2, 3 y 13: el mismo vocabulario que el HTML. La reserva
    # va debajo, porque el punto 3 prohíbe la etiqueta sin su motivo.
    from snapshot import decision as _d
    sen, reserva = _d.senal_txt(g.get("timing"), g.get("senal_detalle"))
    hz = _HZ.get(g.get("horizonte_dominante"), "—")
    n1 = (f'<div class="e1">{esc((pg.get("palabra") or "—").upper())}</div>'
          f'<div class="e2">{esc(config.CONVICCION_PM)} '
          f'{esc(pg.get("conviccion", "—"))} · {esc(config.SENAL_ETIQUETA)}: '
          f'{esc(sen)} · Horizonte {esc(hz)}</div>'
          + (f'<div class="e3">Reserva: {esc(reserva)}</div>' if reserva else ""))
    # SPEC-7P 1: si la etiqueta y la banda del percentil discrepan, se dice en
    # la misma línea. La frase la escribe el estado, no este template.
    tr = t.get("transicion_txt") or ""
    n3 = (f'<div class="regs">'
          f'<span><b>Riesgo</b> {esc(t["estado"])} · p{r.hist_pct:.0f}'
          + (f'<span class="trn">candidato: {esc(tr)}</span>' if tr else "")
          + f'</span>'
          f'<span><b>Ciclo</b> {esc(_estado_ciclo(c.nivel))} · {c.nivel:.0f}/100</span>'
          f'</div>')

    dom = snap.get("tension_dominante")
    if dom:
        dur = _dur_corta(dom.get("detalle") or "")
        d_txt = (f'{esc(_cap(dom["alto_label"]))} <b>{dom["alto_score"]:.0f}</b>'
                 f'<span class="vs">↔</span>'
                 f'{esc(_cap(dom["bajo_label"]))} <b>{dom["bajo_score"]:.0f}</b>'
                 + (f'<span class="dur">· {esc(dur)}</span>' if dur else ""))
        et = dom.get("etiqueta") or config.TENSION_DOMINANTE
        if dom.get("por_que"):
            d_txt += f'<span class="porq">{esc(dom["por_que"])}</span>'
    else:
        d_txt, et = "sin tensión dominante", config.TENSION_DOMINANTE
    ind = snap.get("tension_principal") or snap.get("tension_contexto")
    if ind:
        ctxt = "" if snap.get("tension_principal") else ' <span class="p">(contexto)</span>'
        i_txt = (f'{esc(config.SHORT.get(ind["key"], ind["label"]))} '
                 f'<b>{esc(str(ind["valor"]))}</b> '
                 f'<span class="p">· p{ind["pct"]:.0f}</span>{ctxt}')
    else:
        i_txt = "ninguno en extremo persistente"
    n4 = (f'<div class="tens2">'
          f'<div class="tcel"><span class="k">{esc(et)}</span>'
          f'<span class="v">{d_txt}</span></div>'
          f'<div class="tcel"><span class="k">{esc(config.TENSION_INDICADOR)}</span>'
          f'<span class="v">{i_txt}</span></div></div>')

    bl = g.get("bottom_line") or ""
    take = (f'<div class="take"><span class="k">{esc(config.TITULOS["takeaway"])}'
            f'</span><p>{esc(bl)}</p></div>') if bl else ""

    # SPEC 12: cuando renta variable o duración van al contrario que la postura
    # general, se dice en la pagina 1. Vivia en el resumen de cuatro bloques que
    # esta pagina sustituyo, y al recomponerla se fue con el: el check miraba el
    # campo del estado, no el documento, y por eso no lo vio la primera vez.
    coh = g.get("coherencia")
    coh_html = (f'<div class="coh"><span class="k">Coherencia</span>{esc(coh)}</div>'
                if coh else "")

    # SPEC-7P 4 y 5: hasta tres, y los que más mueven una decisión primero.
    # Concatenados con puntos medios no se escaneaban; en renglones, sí.
    wc = g.get("what_changed") or []
    cam = snap.get("cambios") or {}
    if not cam.get("disponible"):
        cam_txt = '<span class="c1l">sin snapshot anterior con el que comparar</span>'
    elif not wc:
        cam_txt = (f'<span class="c1l">↔ nada que afecte a una decisión desde '
                   f'{esc(_fprev(cam))}</span>')
    else:
        cam_txt = "".join(f'<span class="c1l">{esc(x)}</span>' for x in wc[:3])
    cam_html = (f'<div class="cambio1"><span class="k">'
                f'{esc(config.TITULOS["cambios"])}</span>'
                f'<span class="c1d">desde {esc(_fprev(cam))}</span>{cam_txt}</div>'
                if cam.get("disponible") else
                f'<div class="cambio1"><span class="k">'
                f'{esc(config.TITULOS["cambios"])}</span>{cam_txt}</div>')

    h = (f'<div class="estado">{n1}</div>{n3}{n4}{take}{coh_html}{cam_html}'
         f'{_lectura_corta(snap)}'
         f'<div class="dosg">{_g_fuerzas(snap)}{_g_trayectoria(snap)}</div>'
         f'<p class="escalas">{config.ESCALAS_CORTA}</p>')
    n = 860
    return Bloque(config.TITULOS["regimen"], h, n, "regimen")


def _fprev(cam: dict) -> str:
    """La fecha del snapshot anterior. Llega como texto ISO desde el estado
    persistido, no como Timestamp: sin convertirla, `fecha_corta` fallaba y la
    página imprimía «desde el anterior», que no dice desde cuándo."""
    try:
        import pandas as _pd
        from snapshot.build import fecha_corta as _fc
        return _fc(_pd.Timestamp(cam["fecha_prev"]))
    except (KeyError, ValueError, TypeError):
        return "el anterior"


def _lectura_corta(snap) -> str:
    """Mercado, macro y riesgo principal: una frase y una cifra cada uno.

    El argumento largo vive en el HTML. Aquí el lector necesita saber de qué
    lado está cada bloque y con qué fuerza, no releer el razonamiento.
    """
    c = snap.get("composites") or {}
    tec, mac = c.get("tecnico") or {}, c.get("macro") or {}
    ind = snap.get("tension_principal") or snap.get("tension_contexto")
    es_ctx = not snap.get("tension_principal")

    def b(k, estado, frase, cifra):
        return (f'<div class="lb"><div class="lb-h">{esc(k)}'
                f'<span class="lb-e">{esc(estado)}</span></div>'
                f'<p>{esc(frase)}</p><div class="lb-n">{cifra}</div></div>')

    b1 = b("Mercado", tec.get("lect", "—"),
           f'{tec.get("fav", 0)} de {tec.get("n", 0)} señales de tendencia, '
           f'volatilidad y crédito del mismo lado.',
           f'<b>{tec.get("nivel", 0):.0f}</b> compuesto técnico')
    rel = c.get("relacion")
    b2 = b("Macro",
           mac.get("lect", "—") + (f' · {config.RELACION_TXT[rel].split(" al ")[0]}'
                                   if rel in config.RELACION_TXT else ""),
           f'{mac.get("fav", 0)} de {mac.get("n", 0)} señales de '
           f'{config.pilar_prosa("crecimiento")} y {config.pilar_prosa("liquidez")} acompañan'
           + (f'; {config.RELACION_GLOSA[rel]}.' if rel in config.RELACION_GLOSA
              else '.'),
           f'<b>{mac.get("nivel", 0):.0f}</b> compuesto macro')
    if ind:
        b3 = b("Riesgo principal", "en contra" + (", contexto" if es_ctx else ""),
               f'{config.SHORT.get(ind["key"], ind["label"])} contradice a '
               f'{_clases(ind.get("n_frentes"))}.',
               f'<b>{esc(str(ind["valor"]))}</b> · p{ind["pct"]:.0f}')
    else:
        b3 = b("Riesgo principal", "ninguno",
               "Ningún indicador persistente contradice la lectura.", "")
    return f'<div class="lect3">{b1}{b2}{b3}</div>'


def _clases(n) -> str:
    """«1 clase», no «1 clases»: en un brief de comité la concordancia se nota."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "varias clases"
    return "una clase" if n == 1 else f"{n} clases"


def _dur_corta(detalle: str) -> str:
    """La duración que ya trae el detalle, sin repetir los niveles.

    El orden de la alternancia importa: con «semana» delante, la expresión casa
    el singular dentro de «semanas» y el texto sale «4 semana».
    """
    m = re.search(r"(\d+\s+(?:semanas|semana|meses|mes|años|año|días|día))", detalle or "")
    return m.group(1) if m else ""


def fecha_prev(cam: dict) -> str:
    try:
        return fecha_larga(cam["fecha_prev"])
    except Exception:
        return "el anterior"


def _b_positioning(snap) -> Bloque:
    """Página 2 — ¿CÓMO SE EXPRESA?

    Un espectro por dimensión, con LAS ETIQUETAS DE ESA DIMENSIÓN. El objetivo
    es que las siete se lean de un vistazo, sin traducir «sobreponderar» a lo
    que significa en duración o en crédito.
    """
    g = snap["decision"].guia
    temas = g.get("temas") or []
    # SPEC-7P 3: antes de componer nada. Un espectro que contradiga al sesgo de
    # su propia fila no puede llegar al PDF: el documento estaria afirmando lo
    # contrario de su propia tabla.
    from snapshot import decision as _d
    malas = _qa_espectro(temas)
    if malas:
        raise AssertionError("espectro contra sesgo publicado: " + "; ".join(malas))
    hz_dom = g.get("horizonte_dominante")
    filas = ""
    for t in temas:
        cn = {"alta": "c3", "media": "c2", "baja": "c1"}.get(t.get("conviccion"), "c0")
        # SPEC-7P 21: fuera la columna de timing. Por construcción, el timing de
        # una fila es el GLOBAL salvo que tenga override, así que cuatro de las
        # siete filas repetían la cabecera y las otras tres decían su valor y el
        # global otra vez: una columna que se contaba a sí misma. El global va
        # arriba, una sola vez, y aquí solo se marca la EXCEPCIÓN, debajo del
        # tema, que es de quien es propiedad. No se pierde nada: lo que no lleva
        # marca sigue al general.
        exc = ""
        if t.get("timing_override"):
            exc += (f'<span class="th-n">su señal táctica: '
                    f'{esc(_d.senal_txt(t.get("timing"), t.get("senal_detalle"))[0])}'
                    f'</span>')
        if t["horizonte"] != hz_dom:
            exc += (f'<span class="th-n">horizonte '
                    f'{esc(_HZ.get(t["horizonte"], t["horizonte"]))}</span>')
        fav = t.get("favorecer") or {}
        drv = ", ".join((fav.get("supported_labels") or [])[:3])
        expr = (f'<span class="ex1">{esc(fav.get("text") or "—")}</span>'
                + (f'<span class="ex2">Drivers: {esc(drv)}</span>' if drv else ""))
        if t.get("evitar_util"):
            # «Riesgo» se leía como el riesgo de la lectura. Lo que dice esta
            # línea es qué EVITAR, que no es lo mismo.
            expr += (f'<span class="ex3">{esc(config.EVITAR_ETIQUETA)}: '
                     f'{esc((t.get("evitar") or {}).get("text") or "")}</span>')
        nota = ('<span class="tm2">sin evidencia propia</span>'
                if t.get("sin_evidencia_propia") else "")
        # SEMANTIC-PASS 40: la fila se llama igual en los dos documentos.
        nom = config.dimension_breve(t["key"], t["label"])
        filas += (f'<tr><td class="th">{esc(nom)}{exc}</td>'
                  f'<td class="spc">{_g_espectro(t)}</td>'
                  f'<td class="sesgo">{esc(t.get("sesgo") or "Neutral")}</td>'
                  f'<td class="cvc"><span class="cv {cn}">'
                  f'{esc(t.get("conviccion") or "—")}</span>{nota}</td>'
                  f'<td class="ex">{expr}</td></tr>')
    fam = g.get("familia") or {}
    nota_fam = (f'<div class="hallazgo"><span class="k">Voces independientes'
                f'</span><p>{esc(fam["texto"])} <b>No suman {len(temas)} '
                f'confirmaciones independientes.</b></p></div>'
                if fam.get("existe") else "")
    cab = (f'<div class="pg-top"><span>Horizonte dominante: '
           f'<b>{esc(_HZ.get(hz_dom, "—"))}</b></span>'
           f'<span>{esc(config.SENAL_ETIQUETA)}, en general: '
           f'<b>{esc(_d.senal_txt(g.get("timing"), g.get("senal_detalle"))[0])}</b>'
           f'<em>, salvo donde la fila diga otra cosa</em></span>'
           f'</div>')
    h = (f'{cab}<table class="pg"><thead><tr><th>Dimensión</th><th>Espectro</th>'
         f'<th>Sesgo</th><th>{esc(config.CONVICCION_PM)}</th>'
         f'<th>Expresión preferida</th></tr></thead>'
         f'<tbody>{filas}</tbody></table>{nota_fam}'
         f'<p class="nota">Cada dimensión usa sus propias etiquetas. El punto marca '
         f'el lado que la evidencia favorece hoy; su distancia al centro es la '
         f'{config.CONVICCION_PM.lower()}, y su color, si ese lado es el '
         f'pro-riesgo —por eso «corta» '
         f'en duración y «menor calidad» en crédito se pintan del mismo color que '
         f'«favorable» en renta variable—. «Favorecer» es una expresión relativa '
         f'dentro del tema, no una orden ni un peso de cartera. '
         f'<b>«{config.EVITAR_ETIQUETA}»</b> es {config.EVITAR_GLOSA}, no un '
         f'riesgo de la lectura.</p>')
    # 105 px por fila, medidos: con la expresion, sus drivers y la linea de
    # «menos atractivo», una fila no cabe en 84 desde hace varias pasadas.
    n = 150 + 105 * len(temas) + (30 if nota_fam else 0)
    return Bloque(config.TITULOS["positioning"], h, n, "positioning")


def _expr(e, con_fuente: bool = True) -> str:
    """La expresión con su procedencia. Sin señales que la sostengan, «—».

    La procedencia se imprime UNA sola vez por fila, en «Favorecer». Repetirla
    en «Evitar» no añade nada --es la misma evidencia leída del otro lado-- y
    convertía la columna en ruido.
    """
    if not isinstance(e, dict) or not e.get("supported_by"):
        return "—"
    if not con_fuente:
        return esc(e["text"])
    apo = ", ".join(e.get("supported_labels") or [])
    return f'{esc(e["text"])} <span class="src">({esc(apo)})</span>'



# --- pagina 3: que vigilar -------------------------------------------------
_COND = [
    ("vuelve por debajo de ", "bajar de "),
    ("vuelve por encima de ", "subir por encima de "),
    ("cruza ", "cruzar "),
    ("alcanza ", "alcanzar "),
    ("cae a ", "caer a "),
]
# El verbo de cada disparador sale de su BLOQUE, y el bloque sale del efecto que
# midió el contrafactual. Nunca se elige por redacción: una frase que dijera
# "debilitar" sobre un umbral que invalida estaría contando algo distinto de lo
# que dice el HTML sobre el mismo umbral.
_EFECTO = {
    "confirma": "reforzar la lectura",
    "debilita": "debilitar la lectura",
    "invalida": "invalidar la lectura",
    "tactico": "abrir una oportunidad táctica contra el régimen",
}


# Un brief se lee EN VOZ ALTA. El sujeto de cada frase necesita su articulo, y
# la etiqueta tiene que perder la notacion tecnica: "(OAS)", "(NFCI)" y las
# coletillas del tipo ", cambio en 3 meses" son de auditoria, no de lectura.
_ART = {
    "condiciones": "las", "peticiones": "las", "ventas": "las", "nóminas": "las",
    "materias": "las", "permisos": "los", "precios": "los",
    "prima": "la", "regla": "la", "curva": "la", "tasa": "la", "liquidez": "la",
    "inflación": "la", "confianza": "la", "producción": "la", "volatilidad": "la",
    "caída": "la", "amplitud": "la", "sobreextensión": "la", "bolsa": "la",
    "compensación": "la", "cesta": "la",
}


def _sujeto(label: str) -> str:
    lab = re.sub(r"\s*\([^)]*\)", "", label or "").strip()
    lab = lab.split(",")[0].strip()
    if not lab:
        return "el indicador"
    prim = lab.split()[0].lower()
    art = _ART.get(prim, "el")
    # las siglas se quedan como estan; lo demas baja a minuscula
    cuerpo = lab if lab.split()[0].isupper() and len(lab.split()[0]) > 1 else         lab[0].lower() + lab[1:]
    return f"{art} {cuerpo}"


def _frase_trigger(t: dict) -> str:
    """Un disparador, dicho como se diría en voz alta."""
    cond = t.get("condicion") or ""
    for a, b in _COND:
        if cond.startswith(a):
            cond = b + cond[len(a):]
            break
    efecto = _EFECTO.get(t.get("bloque"), "cambiar la lectura")
    if t.get("key") == "_eje_riesgo":
        # También aquí el verbo sale del BLOQUE: decir «para que el régimen
        # cambie» era elegir el verbo por redacción, y dejaba este disparador
        # fuera de la comprobación que cruza los dos documentos.
        nuevo = (t.get("after_state") or {}).get("regimen")
        cola = f' —pasaría a «{esc(nuevo)}»—' if nuevo else ""
        return (f'El eje de riesgo tendría que {esc(cond)} para {efecto}{cola}; '
                f'hoy está en {esc(str(t["actual"]))}.')
    suj = esc(_sujeto(t["label"]))
    suj = suj[0].upper() + suj[1:]
    return (f'{suj} tendría que {esc(cond)} para {efecto}; '
            f'hoy está en {esc(str(t["actual"]))}.')


def _b_vigilar(snap) -> Bloque:
    """Página 3 — QUÉ ME HARÍA CAMBIAR DE OPINIÓN.

    Dos frases de régimen y táctica, y después una TABLA: qué vigilar, dónde
    está hoy, qué umbral y qué pasaría. En texto corrido había que leer cada
    frase entera para saber si importaba; en tabla se escanea.
    """
    from snapshot import decision as _d

    g = snap["decision"].guia
    pg = snap.get("postura_general") or {}
    setup = g.get("setup") or {}
    path = g.get("path") or {}

    _EST = {"reforzándose": "se está reforzando",
            "debilitándose": "se está debilitando",
            "estable": "se mantiene estable"}
    if path.get("disponible") and path.get("meses"):
        m = path["meses"]
        dur = (f'lleva {m} {"mes" if m == 1 else "meses"} y '
               f'{_EST.get(path["estado"], esc(path["estado"]))}')
    elif path.get("disponible"):
        dur = "no ha cambiado en los últimos dieciocho meses"
    else:
        dur = "no hay histórico con el que medir su antigüedad"
    f1 = (f'La lectura dominante es <b>{esc(pg.get("palabra", "—"))}</b> con '
          f'{esc(config.CONVICCION_PM.lower())} '
          f'{esc(pg.get("conviccion", "—"))}: {dur}.')
    if setup.get("existe"):
        cual = esc(config.SENAL_TACTICA_FRASE.get(
            setup.get("clase"), "una señal táctica"))
        f2 = (f'Hay {cual} —<b>{esc(setup["titulo"].lower())}</b>—: '
              f'{esc(setup.get("texto_breve") or setup.get("texto", ""))}. No cambia '
              f'el régimen; cambia el momento de actuar.')
    else:
        f2 = 'Sin overlay contrario: el momento acompaña a la dirección.'

    # SPEC-4P 17: tabla, no texto corrido
    trg = _d.triggers_brief(snap)
    if trg:
        fil = ""
        for t in trg:
            fil += (f'<tr><td class="th">{esc(t["variable"])}</td>'
                    f'<td class="r">{esc(str(t["actual"]))}</td>'
                    f'<td class="r">{esc(_umbral_corto(t))}</td>'
                    f'<td class="tem">{esc(_tema_afectado(t))}</td>'
                    f'<td class="imp">{esc(_impacto(t))}</td></tr>')
        tabla = (_g_proximidad(snap) +
                 f'<table class="watch"><thead><tr><th>Qué vigilar</th>'
                 f'<th class="r">Hoy</th><th class="r">Umbral</th>'
                 f'<th>Tema</th><th>Qué pasaría</th></tr></thead>'
                 f'<tbody>{fil}</tbody></table>')
    else:
        tabla = ('<p class="none">Ningún umbral está al alcance de un movimiento '
                 'normal de su indicador, y los extremos recientes no llevan tiempo '
                 'suficiente para contar. Hoy no hay nada cercano que cambie la lectura.</p>')

    h = (f'<div class="prosa"><p>{f1}</p><p>{f2}</p></div>'
         f'<h2>{esc(config.TITULOS["triggers"])}</h2>{tabla}'
         f'<p class="nota">El bloque de cada disparador no lo decide la regla que '
         f'lo generó: se simula el cruce y se rehace el recuento con las mismas '
         f'funciones que producen esta lectura. Solo se listan los que están al '
         f'alcance de un movimiento normal; el resto, y el detalle de auditoría, '
         f'en el informe completo.</p>')
    n = 210 + 40 * max(len(trg), 1)
    return Bloque(config.TITULOS["tactica"], h, n, "vigilar")


def _umbral_corto(t: dict) -> str:
    """El VALOR del umbral, sin el verbo: la tabla ya dice que es un umbral."""
    cond = t.get("condicion") or ""
    for pref, signo in (("vuelve por debajo de ", "<"), ("vuelve por encima de ", ">"),
                        ("cae a ", "<"), ("alcanza ", ">"), ("cruza ", "")):
        if cond.startswith(pref):
            return f"{signo}{cond[len(pref):]}"
    return cond


_IMPACTO = {"confirma": "refuerza", "debilita": "debilita",
            "invalida": "invalida", "tactico": "abre táctico"}


def _tema_afectado(t: dict) -> str:
    """A QUIEN afecta, en su propia columna."""
    if t.get("key") == "_eje_riesgo":
        return "Global"
    ck = t.get("affected_theme")
    if ck:
        return config.ASSET_CLASSES.get(ck, {}).get("label", ck)
    return ", ".join(t.get("afecta") or []) or "—"


def _impacto(t: dict) -> str:
    """Que PASARIA, sin repetir a quien: eso ya va en la columna de al lado.

    Y sin decir «debilita la lectura» cuando solo toca a un tema: la lectura
    entera no se mueve porque la duracion pierda un apoyo. Cuando el
    contrafactual midio un cambio de conviccion concreto, se dice ese.
    """
    if t.get("key") == "_eje_riesgo":
        nuevo = (t.get("after_state") or {}).get("regimen")
        return f"el régimen pasa a «{nuevo}»" if nuevo else "cambia el régimen"
    a, d = (t.get("before_state") or {}), (t.get("after_state") or {})
    ca, cd = a.get("conviccion"), d.get("conviccion")
    if ca and cd and ca != cd:
        return f"{config.CONVICCION_PM.lower()} {ca} → {cd}"
    # `direccion` en el estado comparable es el dir_tipo crudo («mas»/«menos»),
    # no la etiqueta publicada: imprimirlo daba «sigue mas». La palabra es la
    # del sesgo de esa clase, que es la que aparece en la tabla de la página 2.
    ck = t.get("affected_theme")

    def lado(st):
        dt = st.get("direccion")
        if ck and dt in ("mas", "menos"):
            return (config.SESGO_PRESENTACION.get(ck, {}).get(dt) or "").lower()
        return (st.get("palabra") or "").lower()

    da, dd = lado(a), lado(d)
    if da and dd and da != dd:
        return f"pasa a {dd}"
    # SPEC-7P 7: «pierde apoyo» a secas deja al lector sin saber si el tema
    # sigue en pie. Si la direccion aguanta, se dice: es la mitad del mensaje.
    sigue = dd or da
    if t.get("bloque") in ("confirma", "debilita") and sigue:
        verbo = "gana" if t["bloque"] == "confirma" else "pierde"
        return f"{verbo} un apoyo; sigue {sigue}"
    return {"confirma": "gana un apoyo", "debilita": "pierde un apoyo",
            "invalida": "se queda sin dirección",
            "tactico": "abre una táctica contraria"}.get(t.get("bloque"), "cambia")


def _estado_ciclo(nivel) -> str:
    spec = config.AXES["ciclo"]
    if nivel is None or not np.isfinite(nivel):
        return "sin dato"
    return spec["high"] if nivel >= 55 else spec["low"] if nivel <= 45 else "neutral"

# ------------------------------------------------------------------ render


def _b_cierre(snap) -> Bloque:
    """Cierre: qué cambió en detalle, método en seis líneas, fuentes y aviso.

    La metodología completa vive en el HTML. Aquí caben seis líneas: lo justo
    para que nadie tenga que fiarse, y no tanto como para ocupar media página.
    """
    g = snap["decision"].guia
    wc = g.get("what_changed") or []
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        cambio = ('<p>No hay un snapshot anterior con el que comparar: esta '
                  'sección aparece a partir del segundo.</p>')
    elif not wc:
        cambio = ('<p>Desde el snapshot anterior no ha cambiado nada que afecte '
                  'a una decisión. Que no cambie nada también es información.</p>')
    else:
        # SPEC-7P 5: cinco en la página 3, tres en la 1, y las tres de la 1 son
        # las tres primeras de estas: los dos sitios no pueden contradecirse.
        cambio = '<ul class="vig">' + "".join(f"<li>{esc(x)}</li>" for x in wc[:5]) + "</ul>"

    met = "".join(f"<li>{esc(x)}</li>" for x in (g.get("metodologia_breve") or []))
    # La regla de confirmacion del regimen va aqui y no en la pagina 1: alli el
    # espacio esta al 90% y esto es metodologia, no titular.
    regla = (snap.get("titular") or {}).get("transicion_regla")
    if regla:
        met += f"<li>{esc(regla)}</li>"
    prov: dict[str, int] = {}
    for d in config.INDICATORS:
        k = d["src"].split()[0].rstrip(",")
        prov[k] = prov.get(k, 0) + 1
    fuentes = ", ".join(f"{k} ({v})" for k, v in sorted(prov.items(), key=lambda x: -x[1]))

    # El titulo del bloque ya dice «Qué cambió»: repetirlo debajo como
    # «Qué cambió - detalle» era un tartamudeo de dos lineas seguidas.
    h = (f'{cambio}'
         f'<h2>{esc(config.TITULOS["metodo"])}</h2><ul class="met">{met}</ul>'
         f'<p class="nota"><b>{esc(config.TITULOS["fuentes"])}.</b> {esc(fuentes)}. '
         f'{len(config.INDICATORS)} indicadores, percentil móvil de cinco años. '
         f'Todo el dato se lee dentro de la terminal; no se exporta. '
         f'<b>Aviso.</b> Lectura del estado macro y de mercado, no una '
         f'recomendación de inversión. Sin pesos de cartera, precios objetivo ni '
         f'órdenes: las decisiones de posicionamiento son del gestor.</p>')
    n = 120 + 42 * min(len(wc), 4) + 22 * len(config.METODOLOGIA_BREVE) + 80
    return Bloque(config.TITULOS["cambios"], h, n, "cierre")


BRIEF_CSS = """
/* --- cuarta pasada: jerarquia de la pagina 1 --- */
.estado{margin:2px 0 9px}
.estado .e1{font:700 30px/1.05 -apple-system,"Segoe UI",sans-serif;letter-spacing:-.01em}
.estado .e2{font:400 12.5px/1.3 -apple-system,sans-serif;color:#4a463f;margin-top:3px}
.regs{display:flex;gap:18px;font-size:11px;color:#4a463f;
  border-top:1px solid #e2ddd4;border-bottom:1px solid #e2ddd4;padding:5px 0;margin-bottom:8px}
.regs b{font-weight:600;color:#6d685f}
.tens2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:9px}
.tcel{border:1px solid #e2ddd4;padding:7px 10px}
.tcel .k{display:block;font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-bottom:3px}
.tcel .v{font-size:12px;line-height:1.4}
.lado b{font-weight:600}
.vs{color:#9a948a;margin:0 6px}
.dur{color:#9a948a;margin-left:5px;font-size:11px}
.porq{display:block;color:#9a948a;font-size:10px;line-height:1.35;margin-top:2px}
.take{border-left:3px solid #1b1a17;padding:6px 0 6px 11px;margin:0 0 8px}
.take .k{display:block;font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-bottom:2px}
.take p{font-size:13px;line-height:1.45;margin:0}
.cambio1{font-size:11px;color:#4a463f;margin-bottom:4px}
.cambio1 .k{font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-right:6px}
.exec{margin-top:2px}
.exb{margin-bottom:7px}
.exb .exk{display:block;font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-bottom:1px}
.exb p{margin:0;font-size:12px;line-height:1.45;text-align:justify;hyphens:auto}
/* --- pagina 2: tres niveles por fila --- */
td.sesgo{font-weight:600;white-space:nowrap}
td.tim{white-space:nowrap;font-size:11.5px}
td.ex{font-size:11.5px;line-height:1.35}
td.ex .drv{display:block;font-size:9.5px;color:#9a948a;margin-top:2px}
td.ex .riesgo{display:block;font-size:10px;color:#8a6d1f;margin-top:2px}
.cv{font-size:11.5px}
.cv.c3{font-weight:600;color:#1b1a17}
.cv.c2{color:#4a463f} .cv.c1{color:#8a847a} .cv.c0{color:#9a948a}
/* --- pagina 3: tabla de disparadores --- */
table.watch td{padding:6px 6px}
table.watch td.imp{font-size:11px;color:#4a463f}
ul.met{margin:0;padding-left:15px;font-size:11px;line-height:1.55;color:#4a463f}
ul.met li{margin-bottom:2px}

@page { size: A4 portrait; margin: 15mm 14mm 13mm 14mm; }
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font:13.6px/1.5 "Iowan Old Style",Georgia,"Times New Roman",serif;
  color:#1b1a17;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{page-break-after:always;position:relative;min-height:269mm}
.page:last-child{page-break-after:auto}
/* cabecera y pie */
.hd{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:1.5px solid #1b1a17;padding-bottom:5px;margin-bottom:11px}
.hd .t{font:600 15px/1.2 -apple-system,"Segoe UI",sans-serif;letter-spacing:.01em}
.hd .d{font:400 10.5px/1.2 -apple-system,sans-serif;color:#6d685f;letter-spacing:.04em;
  text-transform:uppercase}
.ft{position:absolute;bottom:0;left:0;right:0;display:flex;justify-content:space-between;
  border-top:1px solid #e2ddd4;padding-top:5px;
  font:400 9.5px/1.2 -apple-system,sans-serif;color:#9a948a;letter-spacing:.03em}
h2{font:600 10.5px/1.2 -apple-system,sans-serif;letter-spacing:.09em;text-transform:uppercase;
  color:#6d685f;margin:13px 0 6px;padding-bottom:3px;border-bottom:1px solid #e2ddd4}
.sec{font:600 12px/1.2 -apple-system,sans-serif;letter-spacing:.09em;text-transform:uppercase;
  color:#1b1a17;margin:0 0 9px}
.ch{font:600 10px/1.2 -apple-system,sans-serif;letter-spacing:.07em;text-transform:uppercase;
  color:#6d685f;margin:9px 0 4px}
p{margin:0 0 5px}
.p{color:#6d685f}
/* rejilla de regimen */
.rgrid{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #d9d3c8}
.kv{padding:9px 11px;border-right:1px solid #eee7dc;border-bottom:1px solid #eee7dc}
.kv:nth-child(3n){border-right:0}
.kv:nth-child(n+4){border-bottom:0}
.kv.wide{border:1px solid #d9d3c8;border-top:0;padding:9px 11px}
.kv .k{display:block;font:600 9px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-bottom:2px}
.kv .v{font-size:15px}
.kv .v b{font-weight:600}
ul.bul{margin:0;padding-left:14px}
ul.bul li{margin:0 0 7px}
/* tablas */
table{width:100%;border-collapse:collapse;font-size:12px}
th{font:600 9px/1.2 -apple-system,sans-serif;letter-spacing:.06em;text-transform:uppercase;
  color:#9a948a;text-align:left;padding:0 5px 4px;border-bottom:1px solid #1b1a17}
td{padding:8px 6px;border-bottom:1px solid #eee7dc;vertical-align:top}
tr:last-child td{border-bottom:0}
td.th{font-weight:600;white-space:nowrap}
td.r,th.r{text-align:right;white-space:nowrap}
td.sm{font-size:11px;color:#4a463f;line-height:1.35}
.tdif{color:#8a6d1f;font-size:9.5px;white-space:nowrap}
/* tarjetas */
.dos{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px}
.card{border:1px solid #e2ddd4;padding:11px 13px}
.card.on{border-color:#c8a94e;background:#fdfbf4}
.card .sub{font-size:10.5px;color:#6d685f;margin:0}
.tres{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:8px}
.tres ul{margin:0;padding-left:14px;font-size:11px;line-height:1.5}
.tres li{margin-bottom:5px}
/* triggers */
.trg{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tcol{border:1px solid #e2ddd4;padding:9px 11px}
.tcol ul{margin:0;padding:0;list-style:none}
.tcol li{font-size:11px;line-height:1.5;padding:6px 0;border-bottom:1px solid #f2ede4}
.tcol li:last-child{border-bottom:0}
.t-confirma .ch{color:#3f6b4a} .t-invalida .ch{color:#9b3a3a}
.t-tactico .ch{color:#8a6d1f}
.cond,.ef{display:block}
.ef{color:#4a463f}
.meta{display:block;font-size:9.5px;color:#9a948a;margin-top:1px}
.meta.bad{color:#9b3a3a}
.none{color:#9a948a;font-style:italic}
.prosa p{margin:0 0 9px;text-align:justify;hyphens:auto}
.prosa p:last-child{margin-bottom:0}
ul.vig{margin:0 0 9px;padding-left:16px}
ul.vig li{margin:0 0 7px;line-height:1.5}
.cambio{font-size:12px;color:#4a463f;border-left:2px solid #d9d3c8;padding-left:9px;
  margin:10px 0 0}
.src{color:#8a8578;font-size:.86em}
.met{margin-top:6px}
.nota{font-size:10.5px;line-height:1.5;color:#6d685f;margin-top:7px}
.ev td{padding:7px 6px}

/* ============ SEXTA PASADA — graficos y composicion del brief ============ */
/* Cuatro graficos pequeños, en las tintas del documento. Ocupan el hueco que
   antes quedaba en blanco, y cada uno responde una pregunta. */
.dosg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:11px}
.g{min-width:0}
.g-h{font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-bottom:4px;
  display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.g-k{letter-spacing:0;text-transform:none;font-weight:400;color:#6d685f}
.g-k i{display:inline-block;width:9px;height:2px;margin:0 3px 0 7px;
  vertical-align:middle}
.g-k i.k-r{background:#1b1a17} .g-k i.k-c{background:#6d685f}
.g-k b{font-weight:600;color:#1b1a17}
.g svg{display:block}
.g-l{font:400 8px -apple-system,sans-serif;fill:#1b1a17}
.g-v{font:600 8px -apple-system,sans-serif;fill:#6d685f;text-anchor:end}
.g-c{font:400 7px -apple-system,sans-serif;fill:#9a948a}
.g-a{font:400 7px -apple-system,sans-serif;fill:#9a948a}
/* --- pagina 1: los tres bloques de lectura --- */
.lect3{display:grid;grid-template-columns:repeat(3,1fr);gap:11px;margin-top:10px}
.lb{border-top:1.5px solid #1b1a17;padding-top:5px}
.lb-h{font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.06em;
  text-transform:uppercase;display:flex;justify-content:space-between;gap:5px}
.lb-e{color:#6d685f;font-weight:400;letter-spacing:0;text-transform:none}
.lb p{margin:4px 0 3px;font-size:10.5px;line-height:1.4}
.lb-n{font-size:10px;color:#6d685f}
.lb-n b{color:#1b1a17;font-size:12.5px}
/* --- pagina 2: espectros --- */
.pg-top{display:flex;gap:20px;font-size:10.5px;color:#6d685f;
  border-bottom:1px solid #e2ddd4;padding-bottom:5px;margin-bottom:6px}
.pg-top b{color:#1b1a17;font-weight:600}
.pg-top em{font-style:normal;color:#9a948a}
td.spc{width:132px;padding-top:6px}
svg.esp{display:block}
.esp-e{display:flex;justify-content:space-between;font-size:7.5px;color:#9a948a;
  margin-top:-2px;width:128px}
td.sesgo{font-weight:600;white-space:nowrap}
td.tim .tm{display:block;font-size:11px;line-height:1.3}
/* El ocre es para lo que avisa --las líneas de «Riesgo:»--. Que esta fila
   difiera del timing general es una referencia cruzada, no una advertencia. */
td.tim .tm2{display:block;font-size:9px;color:#9a948a;line-height:1.3;margin-top:3px}
td.ex .ex1{display:block;font-size:11.5px;line-height:1.4}
td.ex .ex2{display:block;font-size:9.5px;color:#9a948a;margin-top:3px}
td.ex .ex3{display:block;font-size:10px;color:#8a6d1f;margin-top:3px}
.pg td{padding:7px 6px}
/* --- pagina 3 --- */
table.watch td.tem{font-size:10.5px;color:#4a463f;white-space:nowrap}
.tens2 .porq{display:block;color:#9a948a;font-size:9.5px;line-height:1.3;
  margin-top:2px}

/* ============ SEXTA PASADA 28 — ritmo vertical y tamaño de gráfico ========= */
/* La pagina 1 terminaba a 526 px de 1017: el contenido ocupaba la mitad
   superior y debajo quedaban 12 cm de blanco mudo. No se añade material. Se le
   da a cada nivel de la jerarquia el aire que le toca y a los dos graficos el
   tamaño al que de verdad se leen, que es el trabajo que ese hueco tenia que
   estar haciendo. */
.estado{margin:6px 0 16px}
.estado .e1{font-size:38px}
.estado .e2{font-size:13.5px;margin-top:6px}
/* §3 · la reserva nunca se omite: es lo que hace legible la etiqueta. */
.estado .e3{font-size:10.5px;line-height:1.4;color:#6d685f;margin-top:3px}
.regs{gap:26px;font-size:11.5px;padding:9px 0;margin-bottom:15px;align-items:baseline}
.regs .trn{display:block;font-size:9.5px;color:#8a6d1f;line-height:1.35;margin-top:2px}
.tens2{gap:12px;margin-bottom:15px}
.tcel{padding:10px 12px}
.tcel .v{font-size:12.5px;line-height:1.5}
.take{padding:9px 0 9px 13px;margin:0 0 14px}
.take p{font-size:13.5px;line-height:1.55}
.cambio1 .c1d{font-size:9.5px;color:#9a948a;margin-right:8px}
.cambio1 .c1l{display:block;font-size:11px;line-height:1.45;margin-top:3px}
.coh{font-size:11px;line-height:1.45;color:#4a463f;margin:0 0 11px}
/* D2 c: el hallazgo sobre las voces independientes es una conclusión sobre la
   lectura, no una nota al pie. Lleva rótulo y peso propios. */
.hallazgo{border-left:3px solid #8a6d1f;padding:7px 0 7px 11px;margin:10px 0 0}
.hallazgo .k{display:block;font:600 8.5px/1.2 -apple-system,sans-serif;
  letter-spacing:.07em;text-transform:uppercase;color:#8a6d1f;margin-bottom:2px}
.hallazgo p{margin:0;font-size:11.5px;line-height:1.45}
/* D2 a: las tres escalas, una vez, donde termina la primera página. */
.escalas{font-size:8.5px;line-height:1.4;color:#9a948a;margin:9px 0 0;
  border-top:1px solid #e2ddd4;padding-top:5px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.escalas b{color:#6d685f;font-weight:600}
.coh .k{font:600 8.5px/1.2 -apple-system,sans-serif;letter-spacing:.07em;
  text-transform:uppercase;color:#9a948a;margin-right:6px}
.cambio1{margin-bottom:0;padding-bottom:13px;border-bottom:1px solid #e2ddd4}
.lect3{gap:14px;margin-top:15px}
.lb{padding-top:7px}
.lb p{margin:6px 0 5px;font-size:11px;line-height:1.5}
.lb-n b{font-size:13.5px}
.dosg{gap:14px;margin-top:22px}
/* Los rotulos de los graficos van a escala 1:1 en el PDF: 8 px era tamaño de
   pantalla, no de papel. */
.g-h{font-size:9px;margin-bottom:7px}
.g-l{font-size:9.5px}
.g-v{font-size:9.5px}
.g-v.ini{text-anchor:start}
.g-c{font-size:8px}
.g-a{font-size:8px}
/* --- pagina 2: la tabla respira, y el espectro es legible --- */
/* 13 px de aire por celda dejaban la tabla en 833 px MEDIDOS y la pagina en
   1059 de 1017: se desbordaba a una cuarta pagina en cuanto un nombre de
   dimension ocupaba dos lineas. 9 px la devuelven a 1003 sin tocar ningun
   tamano de letra. Medido sobre el render real a 182 mm, no estimado. */
.pg td{padding:9px 7px}
/* El reparto de ancho de la tabla, explicito: la columna de timing dejo de ser
   una palabra y hay que darle sitio SIN quitarselo a la expresion, que es la
   que de verdad se lee. Tema y expresion se quedan con lo que sobra. */
td.spc,th.spc{width:186px}
td.th,th:first-child{width:132px}
td.sesgo{width:96px}
td.cvc{width:64px}
/* SPEC-7P 21: la excepción de timing u horizonte va debajo del tema, que es
   de quien es propiedad. La columna de timing ya no existe. */
td.th .th-n{display:block;font:400 9px/1.3 -apple-system,sans-serif;
  color:#8a6d1f;margin-top:2px;white-space:normal}
.esp-e{width:170px;font-size:8.5px;margin-top:0}
/* La punta del lado en el que cae el punto, en tinta; la otra, apagada: la
   dirección se ve antes de leer ninguna palabra. */
.esp-e .on{color:#1b1a17;font-weight:600}
/* --- pagina 3: proximidad a ancho completo --- */
.g.gw{margin-bottom:8px}
table.watch td{padding:8px 6px}
"""


# ------------------------------------------------------------------ render
def render_brief(snap: dict) -> tuple[str, list[str]]:
    """El PM Brief completo. Devuelve (html, registro de paginacion)."""
    # Tres secciones. El detalle de auditoria --los 42 indicadores, la notacion
    # sigma, las ventanas de confirmacion-- vive en el HTML, no aqui.
    bloques = [_b_regimen(snap), _b_positioning(snap), _b_vigilar(snap),
               _b_cierre(snap)]

    paginas, log = paginar(bloques)
    fecha = snap["asof"].strftime("%d/%m/%Y")
    total = len(paginas)
    cuerpo = ""
    for p in paginas:
        secs = ""
        for k, b in enumerate(p.bloques):
            secs += f'<div class="sec">{esc(b.titulo)}</div>{b.html}'
        cuerpo += (f'<section class="page">'
                   f'<div class="hd"><span class="t">PM Brief · Investment Decision Guide</span>'
                   f'<span class="d">{fecha}</span></div>'
                   f'{secs}'
                   f'<div class="ft"><span>Lectura, no recomendación. Sin pesos de '
                   f'cartera ni asignación.</span><span>{p.n} / {total}</span></div>'
                   f'</section>')
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
           f'<title>PM Brief {fecha}</title><style>{BRIEF_CSS}</style></head>'
           f'<body>{cuerpo}</body></html>')
    return doc, log
