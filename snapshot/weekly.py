# -*- coding: utf-8 -*-
"""ESTRATEGIA SEMANAL — el documento que sustituye al PM Brief de tres páginas.

SIETE SECCIONES FIJAS, NUMERO DE PAGINAS LIBRE. Cada seccion ocupa lo que
necesita. No se rellena para cuadrar una pagina ni se comprime para ahorrarla:
por eso aqui no hay empaquetador de bloques como el que tenia `brief.py`, sino
un flujo continuo con cortes prohibidos dentro de cada tarjeta. Si una seccion
no tiene nada que decir en una fecha, lo dice en una linea y ocupa una linea;
no se omite, porque su ausencia tambien es informacion.

DE DONDE SALE. Del MISMO DecisionState que el HTML. Aqui no se decide nada, no
se recalcula nada y no se aplica ningun umbral: si el documento necesitara un
calculo que no esta en la capa, el calculo va a la capa (SPEC 2).

TRES DECISIONES QUE CONDICIONAN ESTE DOCUMENTO
----------------------------------------------
1. EQUITY BETA y EQUITY STYLE son dos filas, porque `rv` y `cicl` son dos
   dimensiones publicadas del estado y SEMANTIC-PASS 18 las nombra asi. Pero
   NO son dos votos independientes: los 27 indicadores que votan `cicl` son un
   subconjunto de los 40 que votan `rv`, con el mismo signo, y en ninguna fecha
   probada han caido en lados opuestos. El bloque de renta variable lo dice,
   porque presentarlas como dos confirmaciones seria publicar mas granularidad
   que la que tiene la evidencia (SEMANTIC-PASS 19).

2. CORPORATIVO FRENTE A TESORO no se implementa. Seria un eje nuevo --mezcla
   exposicion a diferencial con exposicion a tasas-- y no existe ni la clase ni
   el mapeo de indicadores. Se publica como DIMENSION FUTURA, que es lo que
   SEMANTIC-PASS 21 prescribe para un hueco de arquitectura.

3. EL HUECO DE CONFIRMACION SE ESCRIBE DESCRIPTIVO. Se ponen los dos hechos
   --hacia que lado se inclina el modelo y que hizo el precio relativo-- uno al
   lado del otro, y no se dice "confirma" ni "no confirma". Emparejar direccion
   de mercado con direccion de modelo exigiria una regla documentada que este
   proyecto no tiene; inventarla aqui seria fabricar una conclusion con aspecto
   de medida (SEMANTIC-PASS 26).
"""

from __future__ import annotations

import html as _html

import numpy as np

import config
from snapshot import decision as _d
from snapshot.build import fecha_corta, fecha_larga, minus
from snapshot.render import es_num

# Los bloques de la seccion 2. El dolar va aparte, como overlay, por
# SEMANTIC-PASS 17: no es una clase mas de la cartera.
BLOQUES = [
    ("Renta variable", ["rv", "cicl"]),
    ("Renta fija", ["dur", "cred"]),
    ("Activos reales", ["mp", "oro"]),
]
OVERLAY = "usd"

# Las puntas de la seccion 2, por dimension. Salen de `espectro_lados`, que es
# la misma regla que usa el HTML.
_PANEL_DE = {"rv": "equity", "cicl": "style", "dur": "rates", "cred": "credit",
             "mp": "commodities", "oro": "gold", "usd": "usd"}


def esc(x) -> str:
    return _html.escape(str(x), quote=True)


def _n(x, dec=0, signo=False) -> str:
    """Un numero, o una raya si no lo hay. Nunca un `nan` impreso."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(v):
        return "—"
    s = f"{v:+.{dec}f}" if signo else f"{v:.{dec}f}"
    return es_num(s)


def _cap(t: str) -> str:
    """Mayuscula SOLO en la primera letra. Estas frases se generan para ir
    dentro de otra y llegan en minuscula; `.capitalize()` entero convertiria
    «tasa real 10a» en «Tasa real 10a»."""
    return (t[0].upper() + t[1:]) if t else t


def _guia(snap):
    return snap["decision"].guia


# ============================ 1 · LA LECTURA ================================
def _s1_lectura(snap) -> str:
    g = _guia(snap)
    pg = snap.get("postura_general") or {}
    t = snap["titular"]
    r = snap.get("riesgo") or {}
    sen, reserva = _d.senal_txt(g.get("timing"), g.get("senal_detalle"))
    hz = {"tactical": "táctico", "intermediate": "intermedio",
          "estructural": "estructural"}.get(g.get("horizonte_dominante"), "—")

    # El espectro del eje de riesgo: aversion a la izquierda, apetito a la
    # derecha, y el percentil marcando donde cae hoy.
    pct = r.get("hist_pct")
    pos = max(2.0, min(98.0, float(pct))) if pct is not None and np.isfinite(
        pct or np.nan) else 50.0

    cand = t.get("transicion_txt")
    regimen = (f'<div class="kv"><span class="k">Régimen confirmado</span>'
               f'<span class="v">{esc(t.get("estado") or "—")}</span></div>')
    if cand:
        regimen += (f'<div class="kv"><span class="k">Candidato</span>'
                    f'<span class="v">{es_num(esc(cand))}</span></div>')
    else:
        regimen += ('<div class="kv"><span class="k">Candidato</span>'
                    '<span class="v vx">ninguno: el régimen no está en '
                    'transición</span></div>')

    c = snap.get("composites") or {}
    tec, mac = c.get("tecnico") or {}, c.get("macro") or {}
    rel = c.get("relacion")

    def bloque_comp(titulo, b, coh):
        return (f'<div class="comp"><div class="comp-t">{esc(titulo)}</div>'
                f'<div class="comp-n">{_n(b.get("nivel"))}<span>/100</span></div>'
                f'<div class="comp-c">{esc(coh)}</div></div>')

    coh_t = (f'{b_fav(tec)} de {tec.get("n", 0)} señales del mismo lado'
             if tec else "sin datos")
    coh_m = (f'{b_fav(mac)} de {mac.get("n", 0)} señales del mismo lado'
             + (f' · {minus(config.RELACION_TXT[rel])}'
                if rel in config.RELACION_TXT else "")
             if mac else "sin datos")

    ind = snap.get("tension_principal")
    if ind:
        restr = (f'<div class="rest-n">{esc(config.SHORT.get(ind["key"], ind["label"]))}'
                 f'</div><div class="rest-v">{es_num(esc(str(ind["valor"])))} · '
                 f'p{_n(ind.get("pct"))}</div>')
    else:
        restr = ('<div class="rest-n vx">ninguna</div><div class="rest-v vx">'
                 'ningún indicador en contra con persistencia suficiente</div>')

    # La ultima conclusion del estado es la que cierra el argumento; el
    # `bottom_line` dice COMO se expresa, que es otra cosa y va debajo.
    cs = snap.get("conclusiones") or []
    bl = g.get("bottom_line") or ""
    concl = ""
    if cs:
        concl = (f'<div class="blk"><div class="blk-t">Conclusión de la semana'
                 f'</div><p>{es_num(esc(cs[-1]))}</p>'
                 + (f'<p class="sub">{es_num(esc(bl))}</p>' if bl else "")
                 + '</div>')

    wc = g.get("what_changed") or []
    cam = (f'<div class="blk"><div class="blk-t">Qué cambió</div>'
           f'<p>{es_num(esc(_cap(wc[0])))}.</p>'
           + (f'<p class="sub">Y {len(wc) - 1} cambio(s) más, en la sección 5.</p>'
              if len(wc) > 1 else "") + '</div>'
           if wc else
           '<div class="blk"><div class="blk-t">Qué cambió</div>'
           '<p class="vx">Nada que afecte a una decisión desde el snapshot '
           'anterior. Que no cambie nada también es información.</p></div>')

    st = g.get("setup") or {}
    if st.get("existe"):
        setup = (f'<div class="kv"><span class="k">Medida táctica</span>'
                 f'<span class="v">{es_num(esc(st.get("titulo") or ""))}</span>'
                 f'</div>')
    else:
        setup = ('<div class="kv"><span class="k">Medida táctica</span>'
                 '<span class="v vx">sin setup táctico: ninguna medida está en '
                 'un extremo que contradiga al régimen</span></div>')

    dom = snap.get("tension_dominante") or {}
    at = (f'<div class="blk"><div class="blk-t">Qué merece atención</div>'
          f'<p>{es_num(esc(_cap(dom.get("texto") or "")))}. '
          f'{es_num(esc(_cap(dom.get("detalle") or "")))}.</p></div>'
          if dom.get("texto") else
          '<div class="blk"><div class="blk-t">Qué merece atención</div>'
          '<p class="vx">Ninguna tensión de fondo entre pilares de eje.</p></div>')

    return f"""
<section class="sec" id="s1">
  <h2><span class="sn">01</span> La lectura</h2>
  <div class="postura">
    <div class="p-big">{esc((pg.get("palabra") or "—").upper())}</div>
    <div class="p-kv">
      <span><b>{esc(config.CONVICCION_PM)}</b> {esc(pg.get("conviccion") or "—")}</span>
      <span><b>Horizonte</b> {esc(hz)}</span>
      <span><b>{esc(config.SENAL_ETIQUETA)}</b> {esc(sen)}</span>
    </div>
    {f'<p class="p-res">{es_num(esc(reserva))}.</p>' if reserva else ''}
  </div>

  <div class="rejilla-3">
    <div class="card">
      <div class="card-t">Compuesto de riesgo</div>
      <div class="big">{_n(r.get("score"))}<span>/100</span></div>
      <div class="sub">percentil histórico p{_n(pct)} · cinco años</div>
      <div class="esp">
        <span class="esp-i">aversión</span>
        <span class="esp-b"><i style="left:{pos:.1f}%"></i></span>
        <span class="esp-d">apetito</span>
      </div>
      {regimen}{setup}
    </div>
    <div class="card">
      <div class="card-t">De dónde viene la lectura</div>
      {bloque_comp("Mercado / técnico", tec, coh_t)}
      {bloque_comp("Macro / fundamental", mac, coh_m)}
    </div>
    <div class="card">
      <div class="card-t">Restricción principal</div>
      {restr}
      <p class="sub">Es el indicador que más contradice la lectura con
         persistencia suficiente para sostenerla.</p>
    </div>
  </div>

  <div class="rejilla-3">{concl}{cam}{at}</div>
</section>"""


def b_fav(b) -> int:
    return int(b.get("fav") or 0)


# ====================== 2 · POSICIONAMIENTO CROSS-ASSET =====================
def _precio_relativo(snap, key) -> str:
    """Lo que hizo el precio, AL LADO de lo que dice el modelo, sin juzgar.

    Descriptivo a proposito: se ponen los dos hechos y el lector saca la
    conclusion. Decir "confirma" o "no confirma" exigiria una regla documentada
    que empareje direccion de mercado con direccion de modelo, y no existe
    (SEMANTIC-PASS 26).
    """
    pan = {p["id"]: p for p in ((snap.get("tape") or {}).get("paneles") or [])}
    p = pan.get(_PANEL_DE.get(key, ""))
    if not p or not p.get("disponible") or not np.isfinite(p.get("r3m", np.nan)):
        return ""
    return (f'<div class="pr"><span class="pr-k">Precio · 3 meses</span>'
            f'<span class="pr-v">{esc(p["nota"])} {_n(p["r3m"], 1, True)} %</span>'
            f'</div>')


def _fila_tema(snap, t) -> str:
    lados = _d.espectro_lados(t)
    paso = t.get("paso") or 0
    pos = 50.0 + max(-1.0, min(1.0, paso / 3.0)) * 46.0
    sen = _d.senal_txt(t.get("timing"), t.get("senal_detalle"))[0]
    fav = t.get("favorecer") or {}
    porque = fav.get("text") or ""
    drv = ", ".join((fav.get("supported_labels") or [])[:3])
    return f"""
    <div class="fila">
      <div class="f-n">{esc(config.dimension_breve(t["key"], t["label"]))}</div>
      <div class="f-e">
        <span class="e-i">{esc(lados["izq"])}</span>
        <span class="e-b"><i style="left:{pos:.1f}%"></i></span>
        <span class="e-d">{esc(lados["der"])}</span>
      </div>
      <div class="f-s">{esc(t.get("sesgo") or "Neutral")}</div>
      <div class="f-c">{esc(t.get("conviccion") or "—")}</div>
      <div class="f-t">{esc(sen)}</div>
      <div class="f-p">{es_num(esc(porque)) if porque else
        '<span class="vx">sin expresión con evidencia que la sostenga</span>'}
        {f'<span class="f-d">{esc(drv)}</span>' if drv else ''}
        {_precio_relativo(snap, t["key"])}</div>
    </div>"""


def _s2_posicionamiento(snap) -> str:
    g = _guia(snap)
    temas = {t["key"]: t for t in (g.get("temas") or [])}
    cuerpo = ""
    for titulo, claves in BLOQUES:
        filas = "".join(_fila_tema(snap, temas[k]) for k in claves if k in temas)
        nota = ""
        if titulo == "Renta variable":
            nota = ('<p class="nota-bloque"><b>Las dos filas no son dos '
                    'confirmaciones.</b> Los indicadores que votan el estilo son '
                    'un subconjunto de los que votan la beta, con el mismo signo: '
                    'el estilo no puede apuntar al lado contrario que la beta. '
                    'Son dos lecturas de la misma evidencia, no dos votos '
                    'independientes.</p>')
        elif titulo == "Renta fija":
            nota = ('<p class="nota-bloque"><b>Corporativo frente a tesoro: '
                    'dimensión futura.</b> Sería un eje distinto del de calidad '
                    '—mezcla exposición a diferencial con exposición a tasas— y '
                    'el modelo no tiene ni la clase ni el mapeo de indicadores '
                    'que haría falta. No se publica una inclinación que la '
                    'evidencia no sostiene.</p>')
        cuerpo += (f'<div class="bloque"><div class="b-t">{esc(titulo)}</div>'
                   f'<div class="tabla">{_cab_tabla()}{filas}</div>{nota}</div>')

    usd = temas.get(OVERLAY)
    if usd:
        est = usd.get("dir_tipo") or "neutral"
        cuerpo += (
            f'<div class="bloque"><div class="b-t">Overlay de divisa</div>'
            f'<div class="tabla">{_cab_tabla()}{_fila_tema(snap, usd)}</div>'
            f'<p class="nota-bloque"><b>{esc(config.USD_ESTADO.get(est, "—"))}.</b> '
            f'{es_num(esc(config.USD_IMPLICACION.get(est, "")))} '
            f'{es_num(esc(config.USD_NOTA))}</p></div>')

    return f"""
<section class="sec" id="s2">
  <h2><span class="sn">02</span> Posicionamiento cross-asset</h2>
  <p class="intro">Cada fila responde una decisión relativa de cartera: los dos
     lados de una misma decisión, no clases de activo sueltas. La columna de
     precio dice qué hizo el mercado en esos tres meses, al lado de lo que dice
     el modelo, para que el lector vea si van juntos. No es una medida de
     acierto.</p>
  {cuerpo}
</section>"""


def _cab_tabla() -> str:
    return (f'<div class="fila cab"><div class="f-n">Dimensión</div>'
            f'<div class="f-e">Espectro</div><div class="f-s">Sesgo</div>'
            f'<div class="f-c">{esc(config.CONVICCION_PM)}</div>'
            f'<div class="f-t">{esc(config.SENAL_ETIQUETA)}</div>'
            f'<div class="f-p">Por qué</div></div>')


# ======================= 3 · QUE SOSTIENE LA LECTURA ========================
def _s3_pilares(snap) -> str:
    pil = [p for p in snap.get("tablero", [])
           if np.isfinite(p.get("score", np.nan))]
    voces = ((snap.get("senales") or {}).get("por_pilar") or {})
    ejes = [p for p in pil if p.get("eje")]
    ctx = [p for p in pil if not p.get("eje")]

    def tarjeta(p):
        v = voces.get(p["key"]) or {}
        n, e = v.get("n"), v.get("e")
        indep = (f'<div class="voces">{n} indicadores → ≈{e:.0f} voces '
                 f'independientes</div>' if n and e else "")
        meta = config.PILLARS.get(p["key"], {})
        return (f'<div class="pil">'
                f'<div class="pil-h"><span class="pil-n">'
                f'{esc(config.PILAR_NOMBRE.get(p["key"], p["label"]))}</span>'
                f'<span class="pil-s">{_n(p["score"])}</span>'
                f'<span class="pil-d">{_n(p.get("d3m"), 0, True)} / 3m</span>'
                f'<span class="pil-l {_cls(p["lectura"])}">'
                f'{esc(config.LECTURA_PM.get(p["lectura"], p["lectura"]))}</span>'
                f'</div>'
                f'<p class="pil-q">{esc(meta.get("desc") or "")} '
                f'{esc(meta.get("importa") or "")}</p>'
                f'{indep}</div>')

    resumen = _lectura_en_voz_alta(snap)
    ctx_html = "".join(
        f'<div class="pil ctx"><div class="pil-h">'
        f'<span class="pil-n">{esc(config.PILAR_NOMBRE.get(p["key"], p["label"]))}'
        f'</span><span class="pil-s">{_n(p["score"])}</span></div>'
        f'<p class="pil-q">No vota dirección. '
        f'{esc((config.PILLARS.get(p["key"], {}) or {}).get("desc") or "")}</p>'
        f'</div>' for p in ctx)

    return f"""
<section class="sec" id="s3">
  <h2><span class="sn">03</span> Qué sostiene la lectura</h2>
  <div class="voz"><div class="voz-t">Para leer en voz alta</div>{resumen}</div>
  <div class="sub-t">Pilares que votan dirección</div>
  <div class="pilares">{"".join(tarjeta(p) for p in ejes)}</div>
  <div class="sub-t">Pilares de contexto</div>
  <div class="pilares ctx-g">{ctx_html or
    '<p class="vx">Ninguno con dato hoy.</p>'}</div>
</section>"""


def _cls(lect) -> str:
    return {"favorable": "ok", "adverso": "mal"}.get(lect, "neu")


def _lectura_en_voz_alta(snap) -> str:
    """El argumento dicho entero, sin cifras sueltas que no se puedan decir.

    No compone nada nuevo: usa el pilar mas alto, el mas bajo, la relacion
    entre los dos compuestos y la conviccion publicada. Si el argumento no se
    sostiene dicho en voz alta, es que no se sostiene.
    """
    pil = sorted([p for p in snap.get("tablero", [])
                  if np.isfinite(p.get("score", np.nan)) and p.get("eje")],
                 key=lambda p: -p["score"])
    if not pil:
        return '<p class="vx">Sin pilares con dato suficiente.</p>'
    pg = (snap.get("postura_general") or {})
    alto, bajo = pil[0], pil[-1]
    nom = lambda p: minus(config.PILAR_NOMBRE.get(p["key"], p["label"]))  # noqa: E731
    rel = (snap.get("composites") or {}).get("relacion")
    frase_rel = {"confirma": "y el bloque macro empuja del mismo lado",
                 "atempera": "y el bloque macro va del mismo lado pero con "
                             "menos fuerza",
                 "contradice": "aunque el bloque macro apunta al lado contrario",
                 }.get(rel, "")
    caidas = [p for p in pil if (p.get("d3m") or 0) < -3]
    matiz = (f' Lo que resta comodidad es {nom(caidas[0])}, que ha cedido '
             f'{_n(abs(caidas[0]["d3m"]))} puntos en tres meses.'
             if caidas else "")
    return (f'<p>La postura es <b>{esc(pg.get("palabra") or "—")}</b> con '
            f'{esc(config.CONVICCION_PM.lower())} '
            f'<b>{esc(pg.get("conviccion") or "—")}</b>. '
            f'La sostiene sobre todo {esc(nom(alto))}, en '
            f'{_n(alto["score"])} sobre 100, {esc(frase_rel)}. '
            f'El freno es {esc(nom(bajo))}, en {_n(bajo["score"])}.'
            f'{es_num(matiz)}</p>')


# ========================= 4 · EVIDENCIA DE MERCADO =========================
def _s4_evidencia(snap, tape_svg: str) -> str:
    ev = snap.get("evidencia") or []
    prosa = "".join(f'<p>{es_num(esc(x))}</p>' for x in ev[:3])
    filas = ""
    for f in _indicadores_clave(snap):
        filas += (f'<div class="ind">'
                  f'<div class="ind-n">{esc(config.SHORT.get(f["key"], f["label"]))}'
                  f'</div>'
                  f'<div class="ind-v">{es_num(esc(str(f.get("valor") or "—")))}'
                  f'<span class="ind-p">p{_n(f.get("pct"))}</span></div>'
                  f'<div class="ind-i">{es_num(esc(_implicacion(f)))}</div></div>')
    return f"""
<section class="sec" id="s4">
  <h2><span class="sn">04</span> Evidencia de mercado</h2>
  <div class="sub-t">Qué hicieron los mercados · doce meses</div>
  <p class="intro">Qué hizo el mercado mientras la lectura evolucionaba. La
     banda bajo cada línea es la postura del modelo ese mes, de la misma
     reconstrucción que el mapa de calor. <b>No es una prueba de
     rendimiento.</b></p>
  {tape_svg}
  <div class="sub-t">Los indicadores que sostienen la lectura</div>
  <div class="inds">{filas or '<p class="vx">Sin indicadores destacados hoy.</p>'}</div>
  <div class="sub-t">Cómo se lee la evidencia</div>
  <div class="prosa">{prosa}</div>
</section>"""


def _indicadores_clave(snap, tope: int = 6) -> list:
    """Los que llevan la lectura: los `lead` de cada compuesto, sin repetir."""
    c = snap.get("composites") or {}
    vistos, out = set(), []
    for b in ("tecnico", "macro"):
        for f in ((c.get(b) or {}).get("lead") or []):
            if f["key"] in vistos:
                continue
            vistos.add(f["key"])
            out.append(f)
    return out[:tope]


def _implicacion(f) -> str:
    """Qué implica ese indicador PARA LA CARTERA, en los términos del modelo.

    La compone la capa de decisión; aquí sólo se le pone la frase alrededor.
    """
    xs = _d.implicacion_cartera(f["key"], f.get("pct"))
    return f"Empuja hacia {xs}." if xs else "no vota sobre ninguna dimensión"


# ========================== 5 · QUE CAMBIO ==================================
def _s5_cambios(snap) -> str:
    g = _guia(snap)
    c = snap.get("cambios") or {}
    if not c.get("disponible"):
        return """
<section class="sec" id="s5">
  <h2><span class="sn">05</span> Qué cambió esta semana</h2>
  <p class="vx">No hay un snapshot anterior con el que comparar: éste es el
     primero con memoria.</p>
</section>"""
    wc = g.get("what_changed") or []
    if not wc:
        return f"""
<section class="sec" id="s5">
  <h2><span class="sn">05</span> Qué cambió esta semana</h2>
  <p class="vx">Nada que afecte a una decisión desde el
     {esc(fecha_corta(c.get("fecha_prev")))}. Que no cambie nada también es
     información: la lectura de la semana pasada sigue en pie.</p>
</section>"""
    items = "".join(f'<li>{es_num(esc(_cap(x)))}.</li>' for x in wc)
    return f"""
<section class="sec" id="s5">
  <h2><span class="sn">05</span> Qué cambió esta semana</h2>
  <p class="intro">Desde el {esc(fecha_corta(c.get("fecha_prev")))}, y sólo lo
     que mueve una decisión. Cada línea dice qué pasó y qué significa para la
     postura, no sólo qué número se movió.</p>
  <ul class="cambios">{items}</ul>
</section>"""


# ====================== 6 · LO QUE APORTA EL RESEARCH =======================
def _s6_research(snap) -> str:
    reg = snap.get("documentos") or {}
    docs = reg.get("documentos") or []
    if not docs:
        return """
<section class="sec" id="s6">
  <h2><span class="sn">06</span> Lo que aporta el research externo</h2>
  <p class="vx">Ninguna pieza vigente hoy. La ventana es de dos semanas, salvo
     un documento estructural que declare más vida.</p>
</section>"""
    cuerpo = ""
    for d in docs:
        aporta = (d.get("aporta") or [])
        porque = aporta[0] if aporta else (d.get("tesis") or "")
        dice = "".join(f'<li>{es_num(esc(x["texto"]))}</li>'
                       for x in (d.get("dice") or [])[:2])
        cuerpo += (
            f'<div class="doc">'
            f'<div class="doc-t">{esc(d["titulo"])}</div>'
            f'<div class="doc-m">{esc(d["fuente"])}'
            f'{" · " + esc(d["autor"]) if d.get("autor") else ""} · '
            f'{esc(fecha_corta(d["fecha_ts"]))} · {d["edad"]} días</div>'
            f'<p class="doc-x">{es_num(esc(d.get("tesis") or ""))}</p>'
            + (f'<ul class="doc-d">{dice}</ul>' if dice else "")
            + f'<p class="doc-p"><b>Por qué importa.</b> '
              f'{es_num(esc(porque))}</p></div>')
    return f"""
<section class="sec" id="s6">
  <h2><span class="sn">06</span> Lo que aporta el research externo</h2>
  <p class="intro"><b>El research externo no vota en la señal sistemática.</b>
     Su trabajo es añadir el contexto que al tablero le falta, desafiar una
     conclusión, o enseñar que el mismo dato admite una segunda lectura.</p>
  {cuerpo}
</section>"""


# =================== 7 · RIESGOS DE LA DECISION =============================
def _s7_riesgos(snap) -> str:
    g = _guia(snap)
    tr = g.get("triggers") or {}

    canon = {t["key"] for t in _d.triggers_brief(snap)}

    def lista(clave, vacio):
        xs = [t for t in (tr.get(clave) or []) if t["key"] in canon]
        if not xs:
            return f'<p class="vx">{vacio}</p>'
        out = ""
        for x in xs:
            out += (f'<div class="tg"><div class="tg-n">'
                    f'{es_num(esc(x["variable"]))} '
                    f'<span class="tg-a">{es_num(esc(str(x.get("actual") or "")))}'
                    f'</span></div>'
                    f'<div class="tg-c">{es_num(esc(x.get("condicion") or ""))}</div>'
                    f'<div class="tg-e">{es_num(esc(x.get("efecto") or ""))}</div>'
                    f'</div>')
        return out

    dist = ""
    for x in sorted([t for b in ("invalida", "debilita", "confirma", "tactico")
                     for t in (tr.get(b) or [])
                     if t.get("sigmas") is not None and not t.get("ya")],
                    key=lambda t: t["sigmas"])[:6]:
        s = x["sigmas"]
        et = "Cerca" if s <= 1.5 else "Moderado" if s <= 3.0 else "Remoto"
        dist += (f'<div class="ds"><span class="ds-n">'
                 f'{es_num(esc(x["variable"]))}</span>'
                 f'<span class="ds-v">{_n(s, 1)} σ · {et}</span></div>')

    return f"""
<section class="sec" id="s7">
  <h2><span class="sn">07</span> Riesgos de la decisión</h2>
  <div class="rejilla-2">
    <div class="card">
      <div class="card-t">Qué debilitaría la postura</div>
      {lista("debilita", "Ningún disparador identificado hoy que reste apoyo sin cambiar el lado.")}
      {lista("invalida", "") if (tr.get("invalida") or []) else ""}
    </div>
    <div class="card">
      <div class="card-t">Qué la reforzaría</div>
      {lista("confirma", "Ningún disparador identificado hoy que refuerce la lectura.")}
    </div>
  </div>
  <div class="sub-t">Distancia a cada punto de vigilancia</div>
  <div class="dists">{dist or '<p class="vx">Ningún disparador con distancia medible hoy.</p>'}</div>
  <p class="nota-bloque">La distancia va en desviaciones típicas del propio
     indicador, que es lo único comparable entre variables con unidades
     distintas. El bloque de cada disparador no lo decide la regla que lo
     generó: se simula el cruce del umbral y se rehacen los votos con las
     mismas funciones que producen la lectura publicada.</p>
</section>"""


# ============================== EL DOCUMENTO ================================
def render_weekly(snap: dict, tape_svg: str = "") -> tuple[str, list[str]]:
    """El documento entero. Devuelve (html, registro)."""
    log: list[str] = []
    asof = snap["asof"]
    h = snap.get("huella") or {}
    pie = (f'Modelo de señales propio y research citado. Lectura, no '
           f'recomendación. · Datos {esc(h.get("codigo", "—"))} · '
           f'{h.get("n_series", "—")} series · último dato '
           f'{esc(fecha_corta(h.get("panel_hasta")))} · generado '
           f'{esc(fecha_corta(h.get("generado")))}')
    secciones = [
        ("01", _s1_lectura(snap)),
        ("02", _s2_posicionamiento(snap)),
        ("03", _s3_pilares(snap)),
        ("04", _s4_evidencia(snap, tape_svg)),
        ("05", _s5_cambios(snap)),
        ("06", _s6_research(snap)),
        ("07", _s7_riesgos(snap)),
    ]
    for n, s in secciones:
        log.append(f"sección {n}: {len(s)} caracteres")
    cuerpo = "".join(s for _n_, s in secciones)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Estrategia semanal · {esc(fecha_corta(asof))}</title>
<style>{_CSS}</style></head>
<body>
<div class="run-h">
  <span class="rh-t">Estrategia semanal</span>
  <span class="rh-f">{esc(fecha_larga(asof)).upper()}</span>
</div>
<div class="run-p">{pie}</div>
<article>
  <header class="port">
    <div class="port-e">Estrategia semanal</div>
    <h1>{esc(fecha_larga(asof))}</h1>
    <p class="port-s">Lectura del estado macro y de mercado. No es un modelo:
       no optimiza, no asigna porcentajes y no genera órdenes.</p>
  </header>
  {cuerpo}
</article>
</body></html>""", log


_CSS = """
:root{--ink:#1b1a17;--muted:#5a564e;--faint:#8b857a;--rule:#ddd8cf;
  --rule-soft:#eee9e2;--bg:#fff;--fav:#3f6b52;--adv:#a4483d;--neu:#b8b2a7;
  --warn:#8a6d1f;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --serif:Georgia,"Times New Roman",serif}
@page{size:A4 portrait;margin:17mm 15mm 16mm 15mm}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);background:var(--bg);
  font:400 10pt/1.5 var(--sans);-webkit-print-color-adjust:exact;
  print-color-adjust:exact}
/* Cabecera y pie fijos: en impresion, `position:fixed` se repite en cada
   pagina. Es la unica forma de tener rotulo corrido sin las cajas de margen
   de @page, que Chrome headless no rellena. */
.run-h{position:fixed;top:-11mm;left:0;right:0;display:flex;
  justify-content:space-between;font:600 7pt var(--sans);letter-spacing:.09em;
  text-transform:uppercase;color:var(--faint);
  border-bottom:.5pt solid var(--rule);padding-bottom:2mm}
.run-p{position:fixed;bottom:-11mm;left:0;right:0;font:400 6.5pt var(--sans);
  color:var(--faint);border-top:.5pt solid var(--rule);padding-top:2mm}
.port{margin-bottom:9mm}
.port-e{font:600 7.5pt var(--sans);letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint)}
h1{font:400 26pt/1.1 var(--serif);margin:2mm 0 2mm;letter-spacing:-.01em}
.port-s{font-size:9pt;color:var(--muted);margin:0;max-width:130mm}
.sec{margin:0 0 8mm;break-inside:auto}
h2{font:600 11pt var(--sans);letter-spacing:.02em;margin:0 0 3mm;
  padding-bottom:1.5mm;border-bottom:.75pt solid var(--ink);
  break-after:avoid}
.sn{color:var(--faint);font-size:8pt;margin-right:2mm}
.sub-t{font:600 7.5pt var(--sans);letter-spacing:.11em;text-transform:uppercase;
  color:var(--faint);margin:5mm 0 2mm;break-after:avoid}
.intro{font-size:9pt;color:var(--muted);margin:0 0 3mm;max-width:165mm}
.vx{color:var(--faint);font-style:italic}
/* ---- 1 ---- */
.postura{display:flex;align-items:baseline;gap:6mm;flex-wrap:wrap;
  margin-bottom:4mm;break-inside:avoid}
.p-big{font:700 24pt/1 var(--sans);letter-spacing:-.02em}
.p-kv{display:flex;gap:5mm;flex-wrap:wrap;font-size:9pt;color:var(--muted)}
.p-kv b{font-weight:600;color:var(--faint);font-size:7.5pt;
  letter-spacing:.08em;text-transform:uppercase;margin-right:1mm}
.p-res{width:100%;margin:1mm 0 0;font-size:8.5pt;color:var(--muted)}
.rejilla-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4mm;
  margin-bottom:4mm}
.rejilla-2{display:grid;grid-template-columns:1fr 1fr;gap:4mm}
.card{border:.75pt solid var(--rule);padding:3mm 3.5mm;break-inside:avoid}
.card-t{font:600 7pt var(--sans);letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:2mm}
.big{font:600 19pt/1 var(--sans)}
.big span{font-size:9pt;color:var(--faint);font-weight:400}
.sub{font-size:8pt;color:var(--muted);margin:1mm 0 0}
.esp{display:flex;align-items:center;gap:2mm;margin:2.5mm 0 2mm;
  font-size:6.5pt;color:var(--faint);text-transform:uppercase;
  letter-spacing:.06em}
.esp-b{position:relative;flex:1;height:1.2pt;background:var(--rule)}
.esp-b i{position:absolute;top:50%;width:2.4mm;height:2.4mm;border-radius:50%;
  background:var(--ink);transform:translate(-50%,-50%)}
.kv{display:flex;justify-content:space-between;gap:3mm;font-size:8.5pt;
  padding:1mm 0;border-top:.5pt solid var(--rule-soft)}
.kv .k{color:var(--faint)}
.kv .v{text-align:right;color:var(--ink)}
.comp{padding:1.5mm 0;border-top:.5pt solid var(--rule-soft)}
.comp:first-of-type{border-top:0}
.comp-t{font-size:8pt;color:var(--muted)}
.comp-n{font:600 15pt/1.1 var(--sans)}
.comp-n span{font-size:8pt;color:var(--faint);font-weight:400}
.comp-c{font-size:7.5pt;color:var(--faint)}
.rest-n{font:600 12pt var(--sans)}
.rest-v{font-size:9pt;color:var(--muted)}
.blk{border-left:1.5pt solid var(--rule);padding:0 0 0 3mm;break-inside:avoid}
.blk-t{font:600 7pt var(--sans);letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:1.5mm}
.blk p{margin:0;font-size:8.5pt;line-height:1.45}
.blk p.sub{margin-top:1mm}
/* ---- 2 ---- */
.bloque{margin-bottom:5mm;break-inside:avoid}
.b-t{font:600 8pt var(--sans);letter-spacing:.1em;text-transform:uppercase;
  color:var(--ink);margin-bottom:1.5mm}
.tabla{border-top:.75pt solid var(--ink)}
.fila{display:grid;grid-template-columns:26mm 40mm 20mm 14mm 24mm 1fr;
  gap:2mm 3mm;padding:2.5mm 0;border-bottom:.5pt solid var(--rule-soft);
  font-size:8.5pt;align-items:start;break-inside:avoid}
.fila.cab{font:600 6.5pt var(--sans);letter-spacing:.08em;
  text-transform:uppercase;color:var(--faint);padding:1.5mm 0}
.f-n{font-weight:600}
.f-e{display:flex;flex-direction:column;gap:1mm;font-size:6.5pt;
  color:var(--faint)}
.fila.cab .f-e{flex-direction:row}
.e-b{position:relative;height:1.2pt;background:var(--rule);margin:1mm 0}
.e-b i{position:absolute;top:50%;width:2.2mm;height:2.2mm;border-radius:50%;
  background:var(--ink);transform:translate(-50%,-50%)}
.e-i,.e-d{line-height:1.2}
.e-d{text-align:right}
.f-s{font-weight:600}
.f-p{font-size:8pt;color:var(--muted);line-height:1.4}
.f-d{display:block;font-size:6.5pt;color:var(--faint);margin-top:.5mm}
.pr{display:flex;gap:2mm;margin-top:1mm;font-size:7pt;color:var(--faint)}
.pr-k{letter-spacing:.06em;text-transform:uppercase}
.pr-v{color:var(--muted)}
.nota-bloque{font-size:7.5pt;color:var(--muted);margin:2mm 0 0;
  padding-left:3mm;border-left:1.5pt solid var(--rule);line-height:1.45}
/* ---- 3 ---- */
.voz{border:.75pt solid var(--ink);padding:3.5mm 4mm;margin-bottom:4mm;
  break-inside:avoid}
.voz-t{font:600 7pt var(--sans);letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:1.5mm}
.voz p{margin:0;font:400 10.5pt/1.55 var(--serif)}
.pilares{display:grid;grid-template-columns:1fr 1fr;gap:3mm}
.ctx-g{grid-template-columns:1fr 1fr 1fr}
.pil{border-top:.75pt solid var(--rule);padding:2mm 0 2.5mm;break-inside:avoid}
.pil-h{display:flex;align-items:baseline;gap:2mm;flex-wrap:wrap}
.pil-n{font:600 8.5pt var(--sans);flex:1}
.pil-s{font:600 13pt var(--sans)}
.pil-d{font-size:7.5pt;color:var(--faint)}
.pil-l{font-size:7pt;letter-spacing:.05em;text-transform:uppercase;
  font-weight:600}
.pil-l.ok{color:var(--fav)} .pil-l.mal{color:var(--adv)}
.pil-l.neu{color:var(--muted)}
.pil-q{font-size:8pt;color:var(--muted);margin:1mm 0 0;line-height:1.4}
.voces{font-size:7pt;color:var(--faint);margin-top:1mm;
  border-top:.5pt dotted var(--rule);padding-top:1mm}
.pil.ctx .pil-n{font-weight:400}
/* ---- 4 ---- */
.inds{border-top:.75pt solid var(--ink)}
.ind{display:grid;grid-template-columns:26mm 30mm 1fr;gap:3mm;padding:2mm 0;
  border-bottom:.5pt solid var(--rule-soft);font-size:8.5pt;break-inside:avoid}
.ind-n{font-weight:600}
.ind-p{color:var(--faint);margin-left:2mm;font-size:7.5pt}
.ind-i{color:var(--muted);font-size:8pt}
.prosa p{font-size:8.5pt;line-height:1.5;margin:0 0 2mm;color:var(--muted)}
/* el Tape, embebido tal cual del HTML */
.tp{display:grid;grid-template-columns:1fr 1fr;gap:4mm 6mm;margin:2mm 0 3mm}
.tp-p{margin:0;break-inside:avoid}
.tp-h{display:flex;align-items:baseline;gap:2mm;flex-wrap:wrap;
  margin-bottom:1mm;font-size:7pt}
.tp-t{font:600 8.5pt var(--sans)}
.tp-s{color:var(--faint)}
.tp-n{margin-left:auto;color:var(--muted)}
.tp-n b{color:var(--ink)}
.tp-l{fill:none;stroke:var(--ink);stroke-width:1.2}
.tp-100{stroke:var(--rule);stroke-dasharray:2 3}
.tp-q{stroke:var(--rule);stroke-width:.5;opacity:.6}
.tp-bp{fill:var(--fav);opacity:.75} .tp-bd{fill:var(--adv);opacity:.75}
.tp-b0{fill:var(--neu);opacity:.55}
.tp-ax{display:flex;justify-content:space-between;font-size:6pt;
  color:var(--faint);margin:.5mm 0 0}
.tp-av{font-size:7pt;color:var(--muted);margin:1mm 0 0}
.tp-sum,.tp-leg,.tp-nd{display:none}
/* La nota larga del Tape repite la entrada de la seccion, y la leyenda
   habla de pasar el cursor por encima: en papel no hay cursor. */
#s4 .note{display:none}
/* ---- 5 ---- */
.cambios{margin:0;padding-left:5mm;font-size:9pt;line-height:1.5}
.cambios li{margin-bottom:1.5mm}
/* ---- 6 ---- */
.doc{border-top:.75pt solid var(--rule);padding:2.5mm 0 3mm;break-inside:avoid}
.doc-t{font:600 9.5pt var(--sans)}
.doc-m{font-size:7pt;color:var(--faint);letter-spacing:.04em;margin:.5mm 0 1.5mm}
.doc-x{font-size:8.5pt;color:var(--muted);margin:0 0 1.5mm;line-height:1.45}
.doc-d{margin:0 0 1.5mm;padding-left:4mm;font-size:8pt;color:var(--muted)}
.doc-p{font-size:8.5pt;margin:0;line-height:1.45}
.doc-p b{color:var(--ink)}
/* ---- 7 ---- */
.tg{padding:1.5mm 0;border-top:.5pt solid var(--rule-soft);font-size:8pt}
.tg:first-child{border-top:0}
.tg-n{font-weight:600}
.tg-a{font-weight:400;color:var(--muted)}
.tg-c{color:var(--muted)}
.tg-e{color:var(--faint);font-size:7.5pt;line-height:1.35}
.dists{border-top:.75pt solid var(--ink)}
.ds{display:flex;justify-content:space-between;padding:1.5mm 0;
  border-bottom:.5pt solid var(--rule-soft);font-size:8.5pt}
.ds-n{font-weight:600}
.ds-v{color:var(--muted)}
"""
