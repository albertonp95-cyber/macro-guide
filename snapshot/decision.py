# -*- coding: utf-8 -*-
"""DECISION STATE: la capa intermedia comun (SPEC 2).

    DATA -> SIGNALS -> DECISION STATE -> { HTML renderer, PDF renderer }

POR QUE EXISTE. Los renderers no pueden decidir nada. Antes de esta capa el
render calculaba, por ejemplo, que clases DISCREPAN de sus analogos: comparaba
la direccion del analogo con la inclinacion de la clase y aplicaba un umbral de
mayoria que vivia en el propio render. Eso es una decision de inversion dentro
de una plantilla, y significa que un segundo renderer (el PDF) podria llegar a
una conclusion distinta del HTML con los mismos datos.

REGLAS DE LA CAPA
  - Aqui vive la decision; en el render, solo como se escribe.
  - HTML y PDF consumen EXACTAMENTE este objeto.
  - Si un renderer necesita un calculo que no esta aqui, el calculo se anade
    aqui, no en la plantilla.
  - Los umbrales son de config, nunca del render.

QUE NO ESTA TODAVIA. Postura/conviccion/timing/horizonte como dimensiones
independientes, regimen vs tactico, expresion preferida, triggers y what-changed
llegan en fases posteriores. Esta fase levanta la capa y le pasa lo que el
sistema ya calcula, sin cambiar nada visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import re

import numpy as np
import pandas as pd

import config


# --------------------------------------------------------------- estructuras
@dataclass(frozen=True)
class Eje:
    """Un eje con el MISMO valor que se publica en todas partes."""
    key: str
    label: str
    nivel: float            # nivel suavizado 0-100 (el que ve el panel Y el grafico)
    hist_pct: float
    estado: str | None
    d1m: float
    d3m: float


@dataclass(frozen=True)
class Discrepancia:
    """Una clase cuyo desenlace historico tipico va CONTRA su inclinacion de hoy."""
    clave: str
    nombre: str
    lectura: str
    signo: int              # +1 el analogo subio, -1 cayo


@dataclass(frozen=True)
class DecisionState:
    asof: Any
    ejes: dict[str, Eje]
    regimen_riesgo: str | None
    regimen_ciclo: str | None
    postura_general: dict[str, Any]
    postura: list[dict[str, Any]]
    tension: dict[str, Any] | None
    tension_dominante: dict[str, Any] | None = None
    analogos: dict[str, Any] = field(default_factory=dict)
    horizontes: dict[str, Any] = field(default_factory=dict)
    guia: dict[str, Any] = field(default_factory=dict)

    # Que valores TIENEN que existir para poder afirmar que los dos formatos
    # comparten estado, y cuales pueden faltar legitimamente (SPEC-2P 12). Una
    # tension puede no existir --que no haya contradiccion persistente es una
    # lectura valida-- y los analogos pueden no tener muestra. Lo demas no: sin
    # postura o sin regimen no hay nada que comparar, y decir "ok" ahi seria
    # firmar una comprobacion que no se hizo.
    REQUERIDOS = ("riesgo_nivel", "riesgo_pct", "ciclo_nivel", "regimen_riesgo",
                  "postura", "conviccion")
    OPCIONALES = ("tension", "analogos_n")

    def cobertura(self) -> dict[str, Any]:
        """Que parte del estado compartido esta realmente poblada."""
        vc = self.valores_compartidos()
        faltan_req = [k for k in self.REQUERIDOS if vc.get(k) is None]
        faltan_opt = [k for k in self.OPCIONALES if vc.get(k) is None]
        return dict(total=len(vc), validados=len(vc) - len(faltan_req) - len(faltan_opt),
                    faltan_requeridos=faltan_req, faltan_opcionales=faltan_opt,
                    completo=not faltan_req)

    # --- valores compartidos: lo que HTML y PDF deben mostrar identico
    def valores_compartidos(self) -> dict[str, Any]:
        return {
            "riesgo_nivel": self.ejes["riesgo"].nivel if "riesgo" in self.ejes else None,
            "riesgo_pct": self.ejes["riesgo"].hist_pct if "riesgo" in self.ejes else None,
            "ciclo_nivel": self.ejes["ciclo"].nivel if "ciclo" in self.ejes else None,
            "regimen_riesgo": self.regimen_riesgo,
            "postura": self.postura_general.get("palabra"),
            "conviccion": self.postura_general.get("conviccion"),
            "tension": (self.tension or {}).get("key"),
            "analogos_n": self.analogos.get("n_comparables"),
        }


# ------------------------------------------------------------ analogos: decision
# El nombre de cada clase para la frase de discrepancia. Vive aqui, no en el
# render: el render solo escribe.
ANALOG_NOMBRE = {
    "rv": "renta variable", "dur": "duración", "oro": "oro",
    "mp": "materias primas", "cicl": "lo cíclico", "usd": "el dólar",
}
ANALOG_CLAVES = ["rv", "dur", "oro", "mp", "cicl", "usd"]


def discrepancias_analogos(analogos: dict, postura: list[dict]) -> list[Discrepancia]:
    """Que clases discrepan de sus analogos, POR DIRECCION.

    Con muestras pequenas el signo es mas estable que la media, asi que la
    comparacion es de signo. Solo puede discrepar una clase con patron
    consistente: si el desenlace historico no tuvo direccion, no contradice nada.
    """
    cons = {c["clave"]: c for c in (analogos or {}).get("consistencia") or []}
    post = {p["key"]: p for p in (postura or [])}
    out: list[Discrepancia] = []
    for clave in ANALOG_CLAVES:
        c, p = cons.get(clave), post.get(clave)
        if not c or not p or not c["patron"] or c["signo"] == 0:
            continue
        if max(c["n_up"], c["n_dn"]) / c["n"] < config.ANALOG_DISC_FRAC:
            continue                      # mayoria no lo bastante clara
        esperado = (+1 if p["dir_tipo"] == "mas"
                    else -1 if p["dir_tipo"] == "menos" else 0)
        if esperado == c["signo"]:
            continue                      # el analogo coincide con la inclinacion
        out.append(Discrepancia(
            clave=clave, nombre=ANALOG_NOMBRE[clave],
            lectura=("neutral" if p["dir_tipo"] == "neutral" else p["direccion"]),
            signo=c["signo"]))
    return out


# ------------------------------------------------------------------ construccion
def build(snap: dict, ctx=None, grupos=None, postura_en=None, recalc=None) -> DecisionState:
    """Construye el DecisionState desde el snapshot ya calculado."""
    ejes = {}
    for e in snap.get("ejes", []):
        ejes[e["key"]] = Eje(
            key=e["key"], label=e["label"], nivel=e["level"],
            hist_pct=e["hist_pct"], estado=e.get("estado"),
            d1m=e.get("d1m"), d3m=e.get("d3m"))

    analogos = dict(snap.get("analogos") or {})
    analogos["discrepancias"] = discrepancias_analogos(analogos, snap.get("postura") or [])

    horizontes = {h: [d["key"] for d in config.INDICATORS if d["horizon"] == h]
                  for h in config.HORIZONS}

    # postura general: ya la calcula build (_tilt) y se publica en la sintesis
    tl = snap.get("postura_general") or {}

    setup = setup_tactico(snap)
    tim, tim_nota = timing_global(snap, setup)
    # «Que cambio» se calcula una vez: la lista de texto que consume el
    # brief y la misma lista con su ancla, que es por donde navega el HTML.
    _wc = what_changed(snap, snap.get("cambios") or {})
    _wc_ref = snap.pop("_what_changed_ref", [])
    fase2 = dict(
        # SPEC-2P 3: el metodo se PUBLICA, no se infiere del texto. Los tres
        # campos viajan con el estado y los dos formatos escriben desde aqui.
        direction_method=config.METODOLOGIA["direction_method"],
        cluster_role=config.METODOLOGIA["cluster_role"],
        conviction_method=config.METODOLOGIA["conviction_method"],
        coherencia=snap.get("coherencia"),
        metodologia_breve=list(config.METODOLOGIA_BREVE),
        metodologia_txt=dict(config.METODOLOGIA_TXT),
        percentil_def=dict(config.METODOLOGIA_PERCENTIL),
        setup=setup, timing=tim, timing_nota=tim_nota,
        horizontes_lectura=lectura_por_horizonte(snap),
        horizonte_dominante=horizonte_dominante(snap),
        temas=(_temas := temas(snap, setup, tim)),
        familia=familia_comun(_temas),
        bottom_line="",          # se rellena abajo: necesita el estado montado

        triggers=(triggers(ctx, snap, setup, recalc) if ctx is not None else {}),
        path=(path_dependency(ctx, snap, postura_en, grupos)
              if (ctx is not None and postura_en is not None) else dict(disponible=False)),
        historia=(historia_posturas(ctx, snap, postura_en, grupos)
                  if (ctx is not None and postura_en is not None)
                  else dict(disponible=False)),
        # SEMANTIC-PASS 3: quien va en contra de la señal tactica global.
        senal_detalle=senal_detalle(snap),
        what_changed=_wc,
        # el mismo cambio, con el ancla a donde lleva (punto 10)
        what_changed_ref=_wc_ref,
        cluster_score=(cluster_score(snap, grupos or {})),
        cluster_comparacion=comparacion_cluster(cluster_score(snap, grupos or {})),
        mandate=config.MANDATE_TRANSLATION,
    )
    # La frase de conclusion necesita el estado ya montado (temas incluidos), asi
    # que se calcula despues y se inyecta. Deriva; no decide.
    _prov = type("X", (), {"guia": fase2})()
    fase2["bottom_line"] = bottom_line(dict(snap, decision=_prov))
    fase2["linea_regimen"] = linea_regimen(fase2["historia"], snap)

    # lo que consume el PM Brief: se calcula aqui, no en el template
    fase2["brief"] = dict(
        confirmaciones=confirmaciones(snap),
        contradicciones=contradicciones_top(snap),
        divergencias=divergencias_clave(snap),
        evidencia=evidencia_clave(snap),
    )
    return DecisionState(
        asof=snap.get("asof"),
        ejes=ejes,
        regimen_riesgo=(snap.get("titular") or {}).get("estado"),
        regimen_ciclo=next((e.get("estado") for e in snap.get("ejes", [])
                            if e["key"] == "ciclo"), None),
        postura_general=tl,
        postura=snap.get("postura") or [],
        tension=snap.get("tension_principal"),
        tension_dominante=snap.get("tension_dominante"),
        analogos=analogos,
        horizontes=horizontes,
        guia=fase2,
    )


# ============================================================================
# TENSION DOMINANTE (estructural) vs INDICADOR QUE MAS CONTRADICE
# ============================================================================
# Son dos cosas distintas y el documento las confundia en una sola linea.
#
#   - La TENSION DOMINANTE es una contradiccion ESTRUCTURAL: dos bloques que no
#     dicen lo mismo (el peso de la evidencia tecnico contra el macro, dos
#     pilares divergentes, los dos ejes apuntando a lados distintos). Es lo que
#     explica por que la lectura no es unanime, y por eso encabeza.
#   - El INDICADOR QUE MAS CONTRADICE es un dato suelto: el extremo persistente
#     que mas se opone a la inclinacion de su propia clase. Es evidencia, no
#     diagnostico, y va debajo.
#
# Un indicador en p99 puede ser espectacular y no ser la tension de fondo; y la
# tension de fondo puede no tener ningun indicador en extremo.

_REL_TENSION = {"contradice": 3, "atempera": 1}


def _contrae(t: str) -> str:
    """«frente a el crédito» no existe: en español «a el» es «al» y «de el» es
    «del». Los nombres de pilar llegan con articulo, asi que la contraccion hay
    que hacerla al componer la frase."""
    return (t.replace(" a el ", " al ").replace(" de el ", " del ")
             .replace(" a El ", " al ").replace(" de El ", " del "))


def tension_dominante(snap: dict) -> dict | None:
    """La contradiccion estructural de hoy, o None si los bloques concuerdan."""
    cands: list[dict] = []

    comps = snap.get("composites") or {}
    rel = comps.get("relacion")
    tec, mac = comps.get("tecnico") or {}, comps.get("macro") or {}
    nt, nm = tec.get("nivel", np.nan), mac.get("nivel", np.nan)
    # Solo cuenta como tension si estan en LADOS OPUESTOS de lo normal. Dos
    # bloques flojos y otro mas flojo no se contradicen: coinciden con matiz.
    if np.isfinite(nt) and np.isfinite(nm) and (nt - 50.0) * (nm - 50.0) < 0:
        cands.append(dict(
            tipo="bloques", peso=_REL_TENSION.get(rel, 1) * 10 + abs(nt - nm),
            alto_label=("el mercado" if nt >= nm else "el macro"),
            bajo_label=("el macro" if nt >= nm else "el mercado"),
            alto_score=max(nt, nm), bajo_score=min(nt, nm), brecha=abs(nt - nm),
            texto="el mercado y el macro apuntan a lados distintos",
            detalle=(f"mercado {nt:.0f}/100 frente a macro {nm:.0f}/100"),
            semanas=None))

    # SPEC 3.1: posicionamiento e inflacion NO entran en ningun eje, asi que no
    # pueden ser la mitad de la tension dominante. Si la divergencia mas ancha
    # los involucra, se reporta como CONTEXTO y se busca la siguiente que sí sea
    # de eje. Una divergencia con un pilar de contexto describe el mercado, no
    # el regimen.
    de_eje = {p for e in config.AXES.values() for p in e["weights"]}
    conc = getattr(config, "CONCEPTO_PILAR", {})
    contexto: list[dict] = []
    for d in (snap.get("divergencias") or []):
        if d["alto"] not in de_eje or d["bajo"] not in de_eje:
            na = conc.get(d["alto"], d["alto_label"].lower())
            nb = conc.get(d["bajo"], d["bajo_label"].lower())
            contexto.append(dict(
                tipo="pilares", de_eje=False, peso=d["gap"],
                alto_label=na, bajo_label=nb, alto_score=d["alto_score"],
                bajo_score=d["bajo_score"], brecha=d["gap"],
                texto=f"{na} y {nb} apuntan a lados distintos",
                detalle=(f"{na} {d['alto_score']:.0f}/100 frente a "
                         f"{nb} {d['bajo_score']:.0f}/100, {d['duracion']}"),
                semanas=d.get("semanas")))
            continue
        # El nombre corto del pilar, no su titulo: "Posicionamiento y valor
        # relativo y Credito y condiciones financieras" no se puede leer.
        na = conc.get(d["alto"], d["alto_label"].lower())
        nb = conc.get(d["bajo"], d["bajo_label"].lower())
        cands.append(dict(
            tipo="pilares", peso=20 + d["gap"],
            alto_label=na, bajo_label=nb,
            alto_score=d["alto_score"], bajo_score=d["bajo_score"],
            brecha=d["gap"],
            texto=f"{na} y {nb} apuntan a lados distintos",
            detalle=(f"{na} {d['alto_score']:.0f}/100 frente a "
                     f"{nb} {d['bajo_score']:.0f}/100, {d['duracion']}"),
            semanas=d.get("semanas")))

    ejes = {e["key"]: e for e in snap.get("ejes", [])}
    er, ec = ejes.get("riesgo"), ejes.get("ciclo")
    if er and ec and np.isfinite(er.get("level", np.nan)) \
            and np.isfinite(ec.get("level", np.nan)):
        gap = abs(er["level"] - ec["level"])
        if (er["level"] - 50) * (ec["level"] - 50) < 0 and gap >= config.DIVERGENCE_GAP:
            alto = er if er["level"] >= ec["level"] else ec
            bajo = ec if er["level"] >= ec["level"] else er
            na, nb = f"el {alto['label'].lower()}", f"el {bajo['label'].lower()}"
            cands.append(dict(
                tipo="ejes", peso=15 + gap,
                alto_label=na, bajo_label=nb,
                alto_score=alto["level"], bajo_score=bajo["level"], brecha=gap,
                texto=f"{na} y {nb} apuntan a lados distintos",
                detalle=(f"{na} {alto['level']:.0f}/100 frente a "
                         f"{nb} {bajo['level']:.0f}/100"),
                semanas=None))

    # CAMBIO DE METODOLOGIA (SPEC 3.1, excepcion). Un pilar de contexto puede
    # formar la tension dominante cuando la divergencia es EXTREMA y
    # PERSISTENTE. Sigue sin votar direccion; lo que se admite es que un pilar
    # que no vota lleve meses en desacuerdo fuerte con los que si votan, porque
    # eso es informacion y la regla anterior la escondia.
    fuertes = [c for c in contexto
               if c["brecha"] >= config.CONTEXTO_TENSION_BRECHA
               and (c.get("semanas") or 0) >= config.CONTEXTO_TENSION_SEMANAS]
    if fuertes:
        mejor_ctx = max(fuertes, key=lambda c: c["peso"])
        # La excepcion NO desplaza a una tension de eje: si hay pilares que
        # votan y estan en desacuerdo, esa es la tension del regimen. La
        # excepcion existe para el caso en que no hay ninguna --2021-11-01--,
        # donde la regla anterior dejaba la pagina en blanco teniendo algo que
        # decir. Dejarla ganar por ser mas ancha convertia el posicionamiento en
        # la tension dominante de la semana de Lehman, que es justo el sesgo de
        # extremidad que SPEC 3.1 prohibe.
        if not cands:
            mejor_ctx["texto"] = _contrae(mejor_ctx["texto"])
            mejor_ctx["detalle"] = _contrae(mejor_ctx["detalle"])
            mejor_ctx["etiqueta"] = config.TENSION_DOMINANTE_CONTEXTO
            mejor_ctx["por_que"] = (
                "una fuerza que no vota dirección lleva meses en desacuerdo fuerte "
                "con los que sí votan, y eso no deja de ser información")
            return mejor_ctx
    if not cands:
        # Sin divergencia de eje y sin una de contexto que llegue al umbral, no
        # hay tension dominante. Una divergencia de contexto floja describe el
        # mercado, no el regimen.
        if contexto:
            c = max(contexto, key=lambda c: c["peso"])
            c["texto"] = _contrae(c["texto"])
            c["detalle"] = _contrae(c["detalle"]) + ", fuerza de contexto"
            return c
        return None
    mejor = max(cands, key=lambda c: c["peso"])
    mejor["de_eje"] = True
    mejor["etiqueta"] = config.TENSION_DOMINANTE
    mejor["texto"] = _contrae(mejor["texto"])
    mejor["detalle"] = _contrae(mejor["detalle"])
    return mejor


# ============================================================================
# FASE 2 - TIMING, HORIZONTES, SETUP TACTICO, TEMAS Y TRIGGERS
# ============================================================================

def _horizonte_de() -> dict[str, str]:
    return {d["key"]: d["horizon"] for d in config.INDICATORS}


def filas_de(snap: dict) -> list[dict]:
    return [f for pil in snap.get("tablero", []) for f in pil["filas"]]


def filas_tacticas(snap: dict) -> list[dict]:
    """Los UNICOS indicadores que pueden mover el timing (SPEC 3.2). Si un
    indicador de regimen pudiera moverlo, el timing seria una copia lenta de la
    conviccion -- justo lo contrario de para lo que sirve."""
    H = _horizonte_de()
    return [f for f in filas_de(snap)
            if H.get(f["key"]) == config.HORIZON_TIMING
            and np.isfinite(f.get("pct", np.nan))]


def _extremo(f: dict) -> bool:
    return f["pct"] <= config.CONTRA_PCT_LOW or f["pct"] >= config.CONTRA_PCT_HIGH


# ------------------------------------------------------------- setup tactico
def setup_tactico(snap: dict) -> dict:
    """Regimen dominante frente a SETUP TACTICO (SPEC 4.4).

    Un setup tactico es una condicion de CORTO plazo que puede ir CONTRA el
    regimen, y que NO lo cambia. Se detecta combinando las dos familias
    tacticas, que se leen al reves entre si:

      - CONTRARIAS (posicionamiento): op alto = barato/sobrevendido,
        op bajo = caro/sobreextendido.
      - DE ESTRES (volatilidad, amplitud): op bajo = miedo, op alto = calma.

    Sobreventa sin miedo es una caida ordenada; miedo sin sobreventa es un susto
    caro. El setup pide LAS DOS, que es lo que separa un suelo de un tramo mas
    de caida. Calibrado contra los dos casos de libro (2008-09 y 2020-03) y su
    espejo (2021-11).
    """
    pil_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    tac = filas_tacticas(snap)
    contr = [f for f in tac if pil_de.get(f["key"]) == "posicionamiento"]
    estres = [f for f in tac if pil_de.get(f["key"]) != "posicionamiento"]

    barato = [f for f in contr if f["op"] >= 90]
    caro = [f for f in contr if f["op"] <= 10]
    miedo = [f for f in estres if f["op"] <= 10]
    calma = [f for f in estres if f["op"] >= 90]

    regimen = (snap.get("postura_general") or {}).get("palabra")

    def corto(fs):
        """Los nombres cortos, y si alguno esta en un extremo RECIENTE se dice.

        Una senal tactica se apoya, por definicion, en extremos frescos: eso es
        lo que la hace tactica. Pero no puede presentarlos como si llevaran
        meses, porque entonces el lector no distingue un susto de un regimen.
        """
        nombres = ", ".join(config.SHORT.get(f["key"], f["key"]) for f in fs)
        if any(es_reciente(snap, f["key"]) for f in fs):
            nombres += " — extremos recientes"
        return nombres

    if barato and miedo and (len(barato) + len(miedo)) >= config.TACTICO_MIN_EXTREMOS:
        return dict(
            existe=True, direccion="rebote",
            contra_regimen=(regimen == "defensiva"),
            **_clase_senal(regimen == "defensiva"),
            titulo="Rebote contrario favorable",
            texto=("las medidas contrarias marcan sobreventa "
                   f"({corto(barato)}) con el estrés en su extremo "
                   f"({corto(miedo)}): condición de rebote, no cambio de régimen"),
            texto_breve=("las medidas de posicionamiento marcan sobreventa y el "
                         "estrés está en su extremo, que es la condición de un "
                         "rebote contrario"),
            evidencia=[f["key"] for f in barato + miedo])
    if caro and calma and (len(caro) + len(calma)) >= config.TACTICO_MIN_EXTREMOS:
        return dict(
            existe=True, direccion="reversion",
            contra_regimen=(regimen == "pro-riesgo"),
            **_clase_senal(regimen == "pro-riesgo"),
            titulo="Riesgo de reversión táctica",
            texto=("las medidas contrarias marcan sobreextensión "
                   f"({corto(caro)}) con la calma en su extremo "
                   f"({corto(calma)}): el tramo está maduro"),
            texto_breve=("las medidas de posicionamiento marcan sobreextensión y "
                         "la calma está en su extremo, que es la condición de una "
                         "reversión táctica"),
            evidencia=[f["key"] for f in caro + calma])
    return dict(existe=False, direccion=None, contra_regimen=False,
                clase=None, clase_titulo="Sin señal táctica", clase_nota="",
                titulo="Sin setup táctico",
                texto="ninguna medida táctica está en un extremo que contradiga al régimen",
                evidencia=[])


def _clase_senal(contra: bool) -> dict:
    """SPEC-2P 9: una señal que acompaña al régimen y una que va en su contra no
    son la misma cosa y no pueden llamarse igual."""
    k = "overlay" if contra else "direccional"
    return dict(clase=k, clase_titulo=config.SENAL_TACTICA[k],
                clase_nota=config.SENAL_TACTICA_NOTA[k])


# -------------------------------------------------------------------- timing
def _clasifica_timing(favor, contra, ex_favor, ex_contra, setup, alineado):
    """La tabla de decision del timing. Pequena y reusable (SPEC 5.3)."""
    if setup.get("existe") and alineado:
        if setup["direccion"] == "rebote":
            return "paciente", "el mercado está sobrevendido: no perseguir la debilidad"
        return "extendido", "el tramo está maduro: riesgo de reversión táctica"
    if len(ex_contra) >= config.TACTICO_MIN_EXTREMOS:
        return "paciente", "las tácticas en contra están en su extremo"
    if len(ex_favor) >= config.TACTICO_MIN_EXTREMOS:
        return "extendido", "las tácticas a favor ya están en su extremo"
    if ex_contra:
        return "contrario", "una táctica en contra está en su extremo"
    if not favor and not contra:
        return "neutral", "sin evidencia táctica sobre este tema"
    if len(favor) > len(contra):
        if not contra:
            return "confirmado", "las tácticas acompañan sin estar estiradas"
        return "favorable", "las tácticas acompañan, con alguna en contra"
    if len(contra) > len(favor):
        return "esperar", "las tácticas todavía no acompañan"
    return "esperar", "las tácticas se reparten"


def timing_tema(snap, ck, dir_tipo, setup, alineado):
    if dir_tipo == "neutral":
        return "neutral", "sin dirección que cronometrar"
    quiere = +1 if dir_tipo == "mas" else -1
    tac = filas_tacticas(snap)
    favor = [f for f in tac if f["votos"].get(ck, 0) == quiere]
    contra = [f for f in tac if f["votos"].get(ck, 0) == -quiere]
    return _clasifica_timing(favor, contra,
                             [f for f in favor if _extremo(f)],
                             [f for f in contra if _extremo(f)],
                             setup, alineado)


def senal_detalle(snap, ck=None, dir_tipo=None, setup=None, alineado=True) -> dict:
    """Quien sostiene la señal tactica y quien va en contra, con nombres.

    Las mismas listas que usa `_clasifica_timing` para decidir; aqui se
    publican para que la etiqueta pueda nombrar su reserva (SEMANTIC-PASS 3).
    No decide nada: describe la decision ya tomada.
    """
    tac = filas_tacticas(snap)
    if ck is not None and dir_tipo not in (None, "neutral"):
        quiere = +1 if dir_tipo == "mas" else -1
        favor = [f for f in tac if f["votos"].get(ck, 0) == quiere]
        contra = [f for f in tac if f["votos"].get(ck, 0) == -quiere]
    else:
        pg = snap.get("postura_general") or {}
        sgn = {"pro-riesgo": 1, "defensiva": -1}.get(pg.get("palabra"), 0)
        if sgn == 0:
            return dict(favor=[], contra=[], extremos_contra=[], n_contra=0)

        def lado(f):
            return 1 if f["op"] >= 60 else -1 if f["op"] <= 40 else 0

        favor = [f for f in tac if lado(f) == sgn]
        contra = [f for f in tac if lado(f) == -sgn]
    ex_contra = [f for f in contra if _extremo(f)]

    return dict(favor=[config.SHORT.get(f["key"], f["label"]) for f in favor],
                contra=[config.SHORT.get(f["key"], f["label"]) for f in contra],
                # El nombre entero para las frases: «sobreext. S&P» cabe en una
                # tabla pero no se lee dentro de una oracion.
                contra_largo=[f["label"] for f in contra],
                extremos_contra=[config.SHORT.get(f["key"], f["label"])
                                 for f in ex_contra],
                n_contra=len(contra))


def senal_txt(estado: str, detalle: dict | None) -> tuple[str, str]:
    """La señal tactica como la lee un gestor: estado y RESERVA (SEMANTIC-PASS 2-3).

    Devuelve (estado, reserva). La reserva nunca se omite cuando la hay: es lo
    que convierte «acompaña con reservas» --que no dice nada-- en «acompaña, y
    la sobreextension del S&P es lo que va en contra».
    """
    txt = config.SENAL_ESTADO.get(estado, estado or "—")
    plantilla = config.SENAL_RESERVA.get(estado)
    if not plantilla:
        return txt, ""
    d = detalle or {}
    n = int(d.get("n_contra") or 0)
    contra = d.get("contra_largo") or d.get("contra") or []
    if contra:
        uno = len(contra) == 1
        quien = (contra[0] if uno
                 else f"{contra[0]}, y {len(contra) - 1} señal más"
                 if len(contra) == 2
                 else f"{contra[0]}, y {len(contra) - 1} señales más")
        verbo = "es lo que apunta" if uno else "apuntan"
        if estado in ("favorable", "contrario"):
            return txt, f"{quien} {verbo} en contra"
        return txt, f"{plantilla.format(n=n)}: {quien.lower()}"
    return txt, plantilla.format(n=n or 1)


def timing_global(snap, setup):
    """El timing de la lectura agregada, sobre el eje de riesgo."""
    pg = snap.get("postura_general") or {}
    sgn = {"pro-riesgo": 1, "defensiva": -1}.get(pg.get("palabra"), 0)
    if sgn == 0:
        return "neutral", "la postura es mixta: no hay señal que cronometrar"
    tac = filas_tacticas(snap)

    def lado(f):
        return 1 if f["op"] >= 60 else -1 if f["op"] <= 40 else 0

    favor = [f for f in tac if lado(f) == sgn]
    contra = [f for f in tac if lado(f) == -sgn]
    return _clasifica_timing(favor, contra,
                             [f for f in favor if _extremo(f)],
                             [f for f in contra if _extremo(f)],
                             setup, True)


# ---------------------------------------------------------------- horizontes
def lectura_por_horizonte(snap: dict) -> dict[str, dict]:
    """La misma lectura vista a cada plazo. Cuando hay conflicto temporal, esto
    es lo que lo ensena: «Régimen: defensiva · Táctico: rebote contrario»."""
    H = _horizonte_de()
    out = {}
    for h in config.HORIZONS:
        fs = [f for f in filas_de(snap)
              if H.get(f["key"]) == h and np.isfinite(f.get("op", np.nan))]
        if not fs:
            out[h] = dict(nivel=None, lectura="sin dato", n=0)
            continue
        niv = float(np.mean([f["op"] for f in fs]))
        out[h] = dict(nivel=niv, n=len(fs),
                      lectura=("pro-riesgo" if niv >= 55 else
                               "defensiva" if niv <= 45 else "neutral"))
    return out


def horizonte_dominante(snap: dict) -> str:
    """El plazo del que viene la evidencia que sostiene la lectura: el horizonte
    con mas indicadores FUERA de su banda neutral (los que realmente votan)."""
    H = _horizonte_de()
    cuenta = {h: 0 for h in config.HORIZONS}
    for f in filas_de(snap):
        h = H.get(f["key"])
        if h and np.isfinite(f.get("pct", np.nan)) and (
                f["pct"] >= config.VOTE_HIGH or f["pct"] <= config.VOTE_LOW):
            cuenta[h] += 1
    return max(cuenta, key=cuenta.get) if any(cuenta.values()) else "intermediate"


# --------------------------------------------------------- expresion preferida
VACIA = dict(text="—", supported_by=[], supported_labels=[],
             confidence=None, source_type=None)


def _apoyos_de(snap: dict, ck: str, dir_tipo: str, propios: bool = True) -> list[dict]:
    """Los indicadores que HOY votan por esa clase en esa direccion.

    SPEC 3.1, RELEVANCIA PRIMERO: una fila solo cita evidencia de SU tema. El
    diferencial de alto rendimiento vota sobre la duracion --y es un voto
    legitimo-- pero no es con lo que se explica la duracion; eso son las tasas
    y la compensacion por inflacion. Sin este filtro las siete filas citaban el
    mismo parentesis, que como formato es ruido y como dato es otra cosa: que
    una sola familia sostiene la lectura entera. Eso se dice UNA vez, debajo de
    la tabla, no diez veces dentro.

    La extremidad solo DESEMPATA entre los candidatos ya relevantes.
    """
    if dir_tipo == "neutral":
        return []
    quiere = +1 if dir_tipo == "mas" else -1
    pil_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    mios = set(config.CLASE_PILARES.get(ck, []))
    ap = [f for f in filas_de(snap)
          if f["votos"].get(ck, 0) == quiere and np.isfinite(f.get("pct", np.nan))
          and (not propios or pil_de.get(f["key"]) in mios)
          and not es_reciente(snap, f["key"])]
    ap.sort(key=lambda f: -abs(f["pct"] - 50.0))
    return ap[:config.EXPRESION_APOYOS_MAX]


def familia_comun(temas: list[dict]) -> dict:
    """Si un mismo puñado de indicadores sostiene muchas clases a la vez, eso no
    es un detalle de formato: es que la lectura entera descansa sobre una sola
    familia de riesgo, y el lector tiene que saberlo (SPEC 10).

    Se mira sobre los apoyos COMPLETOS --sin filtrar por pilar-- porque la
    pregunta es justamente cuantas inclinaciones dependen de los mismos datos.
    """
    cuenta: dict[str, set] = {}
    for t in temas:
        for k in (t.get("apoyos_todos") or []):
            cuenta.setdefault(k, set()).add(t["key"])
    fuertes = {k: cs for k, cs in cuenta.items()
               if len(cs) >= config.FAMILIA_MIN_CLASES}
    if not fuertes:
        return dict(existe=False)
    # la familia es el grupo de indicadores que cubre MAS clases juntos
    clases: set = set()
    for cs in fuertes.values():
        clases |= cs
    keys = sorted(fuertes, key=lambda k: (-len(fuertes[k]), k))
    pil_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    pilares = sorted({pil_de.get(k) for k in keys if pil_de.get(k)})
    nombres = [config.SHORT.get(k, k) for k in keys]
    concepto = " y ".join(config.PILLARS[p]["label"].split(" y ")[0].lower()
                          for p in pilares) or "un mismo grupo"
    n = len(clases)
    return dict(existe=True, keys=keys, labels=nombres, clases=sorted(clases),
                n_clases=n, pilares=pilares,
                texto=(f"El {concepto} ({', '.join(nombres)}) sostiene "
                       f"{_num_es(n)} de las {_num_es(len(temas))} inclinaciones."))


_NUM_ES = {1: "una", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis",
           7: "siete", 8: "ocho", 9: "nueve", 10: "diez"}


def _num_es(n: int) -> str:
    return _NUM_ES.get(n, str(n))


def _expresion(tabla: dict, snap: dict, ck: str, dir_tipo: str,
               conviccion) -> dict:
    """SPEC-2P 7: toda expresion viaja con su PROCEDENCIA.

    El texto sale de una tabla fija --eso es lo que declara `source_type`-- pero
    lo que decide si se publica son los votos de hoy. Una expresion preferida
    sin ninguna senal detras es una recomendacion sin evidencia, y eso no se
    ensena: se ensena «—».
    """
    if dir_tipo == "neutral" or not conviccion:
        return dict(VACIA)
    txt = tabla.get(ck, {}).get(dir_tipo)
    apoyos = _apoyos_de(snap, ck, dir_tipo)
    if not txt or not apoyos:
        return dict(VACIA)
    return dict(text=txt,
                supported_by=[f["key"] for f in apoyos],
                supported_labels=[config.SHORT.get(f["key"], f["label"])
                                  for f in apoyos],
                confidence=conviccion, source_type=config.EXPRESION_FUENTE)


def expresion_preferida(snap: dict, ck: str, dir_tipo: str,
                        conviccion) -> dict:
    """Expresion RELATIVA, y solo con evidencia que la sostenga (SPEC 5.5)."""
    return _expresion(config.EXPRESION_PREFERIDA, snap, ck, dir_tipo, conviccion)


def evitar(snap: dict, ck: str, dir_tipo: str, conviccion) -> dict:
    """El otro lado de la expresion preferida: que se reduce o se evita."""
    return _expresion(config.EVITAR_EXPOSICION, snap, ck, dir_tipo, conviccion)


# ------------------------------------------------------------------- temas
def temas(snap: dict, setup: dict, timing_glob: str | None = None) -> list[dict]:
    """El Positioning Guide (SPEC 4.2): una fila por tema, con postura,
    conviccion, timing, horizonte, que favorecer y que evitar. Nada
    hardcodeado: todo sale del estado."""
    post = {p["key"]: p for p in snap.get("postura", [])}
    regimen = (snap.get("postura_general") or {}).get("palabra")
    H = _horizonte_de()
    out = []
    for ck in config.TEMAS_ORDEN:
        p = post.get(ck)
        if not p:
            continue
        # alineado con el regimen = su paso de riesgo va del lado de la postura
        paso = _paso_riesgo(ck, p["dir_tipo"])
        sgn = {"pro-riesgo": 1, "defensiva": -1}.get(regimen, 0)
        alineado = bool(sgn) and ((paso > 0) - (paso < 0)) == sgn
        tim, tim_nota = timing_tema(snap, ck, p["dir_tipo"], setup, alineado)
        # horizonte del tema: de donde viene la evidencia que lo sostiene
        quiere = 0 if p["dir_tipo"] == "neutral" else (+1 if p["dir_tipo"] == "mas" else -1)
        cuenta = {h: 0 for h in config.HORIZONS}
        for f in filas_de(snap):
            if quiere and f["votos"].get(ck, 0) == quiere:
                h = H.get(f["key"])
                if h:
                    cuenta[h] += 1
        hz = max(cuenta, key=cuenta.get) if any(cuenta.values()) else "—"
        # SPEC-2P 6: el timing es una propiedad del MOMENTO, no del tema, y el
        # que manda es el GLOBAL. Un tema solo se sale de el con un OVERRIDE, y
        # un override exige evidencia tactica PROPIA: indicadores de horizonte
        # tactico que voten sobre esta clase. Sin eso, una fila con timing
        # distinto es ruido de recuento disfrazado de lectura.
        propias = [f for f in filas_tacticas(snap) if f["votos"].get(ck, 0) != 0]
        override = None
        if (timing_glob and tim != timing_glob and p["dir_tipo"] != "neutral"
                and len(propias) >= config.TIMING_OVERRIDE_MIN):
            override = tim
        timing_pub = override or timing_glob or tim
        conv = p.get("conviccion")
        out.append(dict(
            key=ck, label=p["label"], timing_difiere=bool(override),
            postura=("neutral" if p["dir_tipo"] == "neutral" else p["direccion"]),
            dir_tipo=p["dir_tipo"], conviccion=conv,
            timing=timing_pub, timing_global=timing_glob,
            timing_override=override, timing_propio=tim,
            timing_apoyos=[f["key"] for f in propias],
            # Si el tema hereda el estado global, la reserva que lo explica es
            # la del global: la suya explicaria una etiqueta que no es la que
            # se le muestra.
            senal_detalle=(senal_detalle(snap, ck, p["dir_tipo"], setup, alineado)
                           if override else senal_detalle(snap)),
            timing_nota=(tim_nota if override else None),
            horizonte=hz, alineado=alineado, paso=paso,
            favorecer=expresion_preferida(snap, ck, p["dir_tipo"], conv),
            evitar=evitar(snap, ck, p["dir_tipo"], conv),
            sesgo=sesgo(ck, p["dir_tipo"]),
            apoyos_propios=[f["key"] for f in _apoyos_de(snap, ck, p["dir_tipo"])],
            apoyos_todos=[f["key"] for f in _apoyos_de(snap, ck, p["dir_tipo"],
                                                       propios=False)],
        ))
    # SPEC 3.1: una clase sin evidencia de su propio pilar se sostiene solo con
    # la familia comun, y eso hay que decirlo en su fila. Si ademas no le rebaja
    # la conviccion, es un hallazgo que merece reporte, no un silencio.
    for t in out:
        # SPEC-4P 9: «Evitar» solo se publica si no es el inverso mecanico de
        # «Favorecer». Decir «evitar sesgo defensivo» debajo de «alta beta >
        # baja beta» es ocupar una columna para repetirse.
        fav, evi = t["favorecer"], t["evitar"]
        t["evitar_util"] = bool(
            evi.get("supported_by") and evi.get("text") not in (None, "", "—")
            and not _inversa(fav.get("text") or "", evi.get("text") or ""))
        t["sin_evidencia_propia"] = bool(
            t["dir_tipo"] != "neutral" and t["apoyos_todos"] and not t["apoyos_propios"])
    return out


def espectro_lados(t: dict) -> dict:
    """Las dos puntas del espectro de un tema, ORDENADAS POR RIESGO.

    Izquierda = expresión defensiva, derecha = pro-riesgo, en las siete filas y
    en LOS DOS DOCUMENTOS. El orden no se escribe a mano: sale del beta de la
    clase frente a su eje, que es lo único que define cuál de sus dos lados es
    el pro-riesgo. Vive aquí, en la capa común, porque el brief y el HTML
    dibujan la misma fila y con la regla duplicada ya se separaron una vez.
    """
    ck = t.get("key")
    _ax, beta = config.CLASS_AXIS.get(ck, (None, 1))
    pro = "mas" if (beta or 1) > 0 else "menos"
    off = "menos" if pro == "mas" else "mas"
    et = dict(config.SESGO_PRESENTACION.get(ck, {}),
              **config.ESPECTRO_EXTREMOS.get(ck, {}))
    return dict(izq=et.get(off, ""), der=et.get(pro, ""), pro=pro, off=off)


def _paso_riesgo(ck: str, dir_tipo: str) -> int:
    if dir_tipo in (None, "neutral"):
        return 0
    _ax, beta = config.CLASS_AXIS.get(ck, (None, 1))
    return (1 if dir_tipo == "mas" else -1) * (beta or 1)


# ============================================================================
# FASE 2 (b) - TRIGGERS, PERSISTENCIA, PATH DEPENDENCY, WHAT CHANGED
# ============================================================================

def _umbral_en_pct(ctx, key: str, asof, pct_obj: float) -> float:
    """El VALOR al que ese indicador alcanza ese percentil, en la misma ventana
    de cinco anos que usa el tablero."""
    try:
        w = ctx.panel[key].loc[:asof].dropna().tail(config.PCT_WINDOW)
    except Exception:
        return float("nan")
    if len(w) < 30:
        return float("nan")
    return float(w.quantile(max(0.0, min(1.0, pct_obj / 100.0))))


def _sigma_diaria(ctx, key: str, asof) -> float:
    """Desviacion tipica de los cambios DIARIOS recientes del indicador."""
    try:
        s = ctx.panel[key].loc[:asof].dropna().tail(config.TRIGGER_SIGMA_WIN)
    except Exception:
        return float("nan")
    d = s.diff().dropna()
    return float(d.std()) if len(d) >= 10 else float("nan")


def _alcanzabilidad(ctx, key: str, asof, actual: float, umbral: float,
                    horizonte: str = "intermediate") -> dict:
    """SPEC 6: la distancia de cada trigger en desviaciones tipicas de su propio
    indicador. Un trigger que exige un movimiento que ese indicador no hace no
    invalida nada en la practica, y hay que decirlo."""
    sg = _sigma_diaria(ctx, key, asof)
    if not np.isfinite(sg) or sg == 0 or not np.isfinite(actual) or not np.isfinite(umbral):
        return dict(sigmas=None, alcanzable=None, texto="sin dato")
    dias = config.TRIGGER_DIAS_HORIZONTE.get(horizonte, 63)
    sg_h = sg * np.sqrt(dias)                      # sigma del horizonte del trigger
    d = float(abs(umbral - actual) / sg_h)
    # bool NATIVO: numpy.bool_(False) no es False, y el filtro del brief se
    # apoya en una comparacion de identidad.
    alc = bool(d <= config.TRIGGER_SIGMA_MAX)
    plazo = {"tactical": "un mes", "intermediate": "un trimestre",
             "estructural": "nueve meses"}.get(horizonte, "un trimestre")
    return dict(sigmas=float(d), alcanzable=alc,
                texto=(f"{es_num_local(d)} σ a {plazo}" +
                       ("" if alc else "; fuera de alcance práctico")))


def es_num_local(x: float) -> str:
    return f"{x:.1f}"


def _persistencia(key: str) -> str:
    H = {d["key"]: d["horizon"] for d in config.INDICATORS}
    return config.PERSISTENCIA_TXT.get(H.get(key, "intermediate"), "2 semanas")


def _fila_trigger(ctx, snap, bloque, key, label, actual_txt, actual, umbral,
                  sentido, afecta, efecto, ya=False, pct_obj=None,
                  pct_actual=None, afecta_keys=None):
    d = config.INDICATOR_BY_KEY.get(key, {})
    H = {x["key"]: x["horizon"] for x in config.INDICATORS}
    alc = _alcanzabilidad(ctx, key, snap["asof"], actual, umbral,
                          H.get(key, "intermediate"))
    return dict(
        bloque=bloque, key=key, label=label,
        variable=config.SHORT.get(key, label),
        actual=actual_txt,
        condicion=f"{sentido} {_fmt_local(d, umbral)}",
        umbral=umbral, afecta=afecta, efecto=efecto,
        afecta_keys=list(afecta_keys or []),
        pct_obj=pct_obj, pct_actual=pct_actual,
        pct_cf=(_pct_cruzado(pct_obj, pct_actual)
                if (pct_obj is not None and pct_actual is not None) else None),
        horizonte=H.get(key, "intermediate"),
        persistencia=_persistencia(key),
        sigmas=alc["sigmas"], alcanzable=alc["alcanzable"], alcance=alc["texto"],
        ya=ya)


def _pct_cruzado(pct_obj: float, pct_actual: float) -> float:
    """El percentil con el que se SIMULA el cruce.

    Quedarse exactamente en el umbral no es cruzarlo: p60 exacto sigue votando.
    Se simula el umbral ya pasado, medio punto al otro lado, en el sentido del
    que viene el indicador."""
    if not (np.isfinite(pct_obj) and np.isfinite(pct_actual)):
        return float("nan")
    eps = 0.5
    v = pct_obj - eps if pct_actual > pct_obj else pct_obj + eps
    return float(max(0.0, min(100.0, v)))


def _fmt_local(d: dict, v: float) -> str:
    if not np.isfinite(v):
        return "—"
    try:
        txt = d["fmt"].format(v)
        u = d.get("unit", "")
        return f"{txt} {u}".strip() if u else txt
    except Exception:
        return f"{v:.2f}"


def es_reciente(snap: dict, key: str) -> bool:
    """SPEC 7.1: un extremo que aun no lleva tiempo suficiente es RECIENTE.

    La persistencia se calcula una sola vez, en build, como propiedad del
    indicador; esto solo la consulta. Ningun selector puede usar un indicador
    reciente como evidencia, tension, disparador, confirmacion o contradiccion:
    solo puede aparecer como contexto, dicho como contexto.
    """
    p = (snap.get("persistencia") or {}).get(key)
    return bool(p and p.get("reciente"))


def _persistente(snap: dict, key: str) -> bool:
    return not es_reciente(snap, key)


def triggers(ctx, snap: dict, setup: dict, recalc=None) -> dict[str, list[dict]]:
    """Los cuatro bloques de SPEC 6. Cada disparador trae variable, valor
    actual, condicion, a quien afecta, efecto esperado, horizonte, persistencia
    exigida y ALCANZABILIDAD en sigmas de su propio indicador."""
    out = {"confirma": [], "debilita": [], "invalida": [], "tactico": []}
    filas = {f["key"]: f for f in filas_de(snap)}
    post = {p["key"]: p for p in snap.get("postura", [])}
    clabel = {ck: m["label"] for ck, m in config.ASSET_CLASSES.items()}

    # --- CONFIRMA: la contradiccion destacada saliendo de su extremo ---------
    for c in (snap.get("contradicciones") or [])[:2]:
        f = filas.get(c["key"])
        if not f or not np.isfinite(c.get("pct", np.nan)):
            continue
        obj = config.EXTREME_HIGH if c["pct"] >= 50 else config.EXTREME_LOW
        umb = _umbral_en_pct(ctx, c["key"], snap["asof"], obj)
        sent = "vuelve por debajo de" if c["pct"] >= 50 else "vuelve por encima de"
        clases = [x["clase_label"] for x in c.get("frentes", [])]
        cks = [x.get("clase") for x in c.get("frentes", []) if x.get("clase")]
        out["confirma"].append(_fila_trigger(
            ctx, snap, "confirma", c["key"], c["label"], f["valor"],
            f.get("valor_raw", np.nan), umb, sent, clases,
            "sube la convicción: deja de contradecir",
            pct_obj=float(obj), pct_actual=float(c["pct"]), afecta_keys=cks))

    # --- DEBILITA: un apoyo en extremo que vuelve a la normalidad ------------
    vistos = set()
    for ck, p in post.items():
        if p["dir_tipo"] == "neutral":
            continue
        quiere = +1 if p["dir_tipo"] == "mas" else -1
        apoyos = [f for f in filas.values()
                  if f["votos"].get(ck, 0) == quiere and np.isfinite(f["pct"])
                  and (f["pct"] >= config.CONTRA_PCT_HIGH or f["pct"] <= config.CONTRA_PCT_LOW)]
        apoyos.sort(key=lambda f: -abs(f["pct"] - 50))
        for f in apoyos[:1]:
            if f["key"] in vistos:
                continue
            vistos.add(f["key"])
            obj = config.EXTREME_HIGH if f["pct"] >= 50 else config.EXTREME_LOW
            umb = _umbral_en_pct(ctx, f["key"], snap["asof"], obj)
            sent = "vuelve por debajo de" if f["pct"] >= 50 else "vuelve por encima de"
            out["debilita"].append(_fila_trigger(
                ctx, snap, "debilita", f["key"], f["label"], f["valor"],
                f.get("valor_raw", np.nan), umb, sent, [clabel[ck]],
                "baja la convicción: pierde su apoyo más marcado",
                pct_obj=float(obj), pct_actual=float(f["pct"]),
                afecta_keys=[ck]))

    # --- INVALIDA: el regimen cambia de banda --------------------------------
    r = snap["riesgo"]
    hp, d1 = r.get("hist_pct"), r.get("d1m")
    if np.isfinite(hp):
        edges = sorted({e for b in config.STATE_BANDS for e in (b[0], b[1])})
        if np.isfinite(d1) and d1 != 0:
            cand = [e for e in edges if e < hp][::-1] if d1 < 0 else [e for e in edges if e > hp]
        else:
            cand = sorted(edges, key=lambda e: abs(e - hp))
        est_hoy = (snap.get("titular") or {}).get("estado")
        for nb in cand:
            nom = scoring_band(nb, d1)
            if not nom or nom == est_hoy:
                continue
            out["invalida"].append(dict(
                bloque="invalida", key="_eje_riesgo", label="Eje de riesgo",
                variable="eje de riesgo",
                actual=f"p{hp:.0f} ({est_hoy})",
                condicion=f"cruza p{nb:.0f}",
                umbral=float(nb), afecta=["todas las clases"],
                efecto=f"el régimen pasa a «{nom}»",
                horizonte="intermediate",
                # El rotulo «confirmación» lo pone quien lo imprime: llevarlo
                # aqui dentro producia «confirmación 5 días hábiles de
                # confirmación».
                persistencia=f"{config.STATE_PERSISTENCE} días hábiles",
                sigmas=None, alcanzable=None, afecta_keys=[],
                pct_obj=None, pct_actual=None, pct_cf=None,
                regimen_nuevo=nom, regimen_previo=est_hoy,
                alcance=f"{abs(nb - hp):.0f} puntos en esa escala", ya=False))
            break

    # por tema: el apoyo mas fuerte dejando de votar deja la clase sin mayoria
    vistos_inv: set = set()
    for ck, p in post.items():
        if p["dir_tipo"] == "neutral" or p.get("conviccion") not in ("alta", "media"):
            continue
        quiere = +1 if p["dir_tipo"] == "mas" else -1
        apoyos = [f for f in filas.values()
                  if f["votos"].get(ck, 0) == quiere and np.isfinite(f["pct"])]
        if len(apoyos) < 2:
            continue
        apoyos.sort(key=lambda f: -abs(f["pct"] - 50))
        f = next((x for x in apoyos if x["key"] not in vistos_inv), None)
        if f is None:
            continue
        vistos_inv.add(f["key"])
        obj = config.VOTE_HIGH if f["pct"] >= 50 else config.VOTE_LOW
        umb = _umbral_en_pct(ctx, f["key"], snap["asof"], obj)
        sent = "vuelve por debajo de" if f["pct"] >= 50 else "vuelve por encima de"
        out["invalida"].append(_fila_trigger(
            ctx, snap, "invalida", f["key"], f["label"], f["valor"],
            f.get("valor_raw", np.nan), umb, sent, [clabel[ck]],
            f"deja de votar: {clabel[ck].lower()} pierde su apoyo principal",
            pct_obj=float(obj), pct_actual=float(f["pct"]), afecta_keys=[ck]))
        if len(out["invalida"]) >= 4:
            break

    # --- TACTICO: la oportunidad contra el regimen ---------------------------
    if setup.get("existe"):
        out["tactico"].append(dict(
            bloque="tactico", key="_setup", label=setup["titulo"],
            variable=setup["titulo"].lower(),
            actual="activo hoy", condicion="ya activado",
            umbral=None, afecta=["contra el régimen dominante"],
            efecto=setup["texto"], horizonte="tactical",
            persistencia=config.PERSISTENCIA_TXT["tactical"],
            afecta_keys=[], pct_obj=None, pct_actual=None, pct_cf=None,
            sigmas=0.0, alcanzable=True, alcance="ya activado", ya=True))
    else:
        pil_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
        contr = [f for f in filas_tacticas(snap)
                 if pil_de.get(f["key"]) == "posicionamiento"]
        contr.sort(key=lambda f: -abs(f["op"] - 50))
        for f in contr[:1]:
            lejos_arriba = f["op"] < 90
            obj = config.EXTREME_HIGH if lejos_arriba else config.EXTREME_LOW
            umb = _umbral_en_pct(ctx, f["key"], snap["asof"], obj)
            sent = "alcanza" if lejos_arriba else "cae a"
            out["tactico"].append(_fila_trigger(
                ctx, snap, "tactico", f["key"], f["label"], f["valor"],
                f.get("valor_raw", np.nan), umb, sent, ["contra el régimen"],
                "abre un setup táctico contrario",
                pct_obj=float(obj), pct_actual=float(f["pct"])))
    return _reclasifica(out, snap, recalc, setup)


# ---------------------------------------------- RECOMPUTACION CONTRAFACTUAL
# Un disparador no vale por la frase que lo acompana, sino por lo que le pasa a
# la lectura cuando se cumple. Hasta aqui el bloque de cada disparador lo fijaba
# la REGLA QUE LO GENERO ("este sale de un extremo -> confirma"), que es una
# suposicion. Lo que sigue la sustituye por una medicion: se simula el cruce, se
# rehace el recuento con las mismas funciones que producen la postura publicada
# y se compara. El bloque lo decide el resultado, no la regla de origen.

_SEVERIDAD = {"none": 0, "confirm": 1, "tactical": 1,
              "weaken": 2, "neutralize": 3, "reverse": 4}
_EFECTO_BLOQUE = {"confirm": "confirma", "weaken": "debilita",
                  "neutralize": "invalida", "reverse": "invalida",
                  "tactical": "tactico"}
_RANGO_CONV = {"baja": 1, "media": 2, "alta": 3}


VOCES_TXT = "las señales que no se repiten entre sí"
APOYOS_TXT = "los indicadores que la apoyan"


def _estado_tema(postura: list[dict], ck: str) -> dict:
    p = next((x for x in (postura or []) if x["key"] == ck), None)
    if p is None:
        return dict(existe=False)
    return dict(existe=True, direccion=p.get("dir_tipo"),
                palabra=p.get("direccion"), conviccion=p.get("conviccion"),
                fuerza=p.get("fuerza_n") or 0,
                voces=round((p.get("e_favor") or 0) - (p.get("e_contra") or 0), 1),
                v_favor=round(p.get("e_favor") or 0, 1),
                v_contra=round(p.get("e_contra") or 0, 1),
                apoyos=(p.get("n_a") or 0) - (p.get("n_c") or 0),
                n_a=p.get("n_a") or 0, n_c=p.get("n_c") or 0)


def _estado_gen(snap_like: dict) -> dict:
    g = snap_like.get("postura_general") or {}
    return dict(existe=True, direccion=g.get("palabra"), palabra=g.get("palabra"),
                conviccion=g.get("conviccion"), fuerza=abs(g.get("score") or 0),
                voces=None, apoyos=None)


# Que se compara, en orden, y con que palabra se explica el cambio. La etiqueta
# publicada (direccion, conviccion) va primero porque es lo que decide; pero si
# no se mueve hay que seguir mirando, porque una clase puede perder un apoyo sin
# que cambie ninguna palabra, y eso sigue siendo perder apoyo.
_DIMS = [("fuerza", "la fuerza de la inclinación"),
         ("voces", VOCES_TXT),
         ("apoyos", APOYOS_TXT)]


def _compara(antes: dict, despues: dict, neutro: str) -> tuple[str, str]:
    """La taxonomia de SPEC 6, aplicada a un par de estados comparables.

    Devuelve (efecto, motivo). El motivo dice EN QUE se midio el cambio, que es
    lo que luego permite escribir la frase sin inventarse el porque.
    """
    if not (antes.get("existe") and despues.get("existe")):
        return "none", "sin lectura"
    a, b = antes.get("direccion"), despues.get("direccion")
    if a != b:
        if a != neutro and b != neutro:
            return "reverse", "dirección"
        if a != neutro and b == neutro:
            return "neutralize", "dirección"
        return "confirm", "dirección"      # de sin direccion a direccion
    if a == neutro:
        return "none", "sigue sin dirección"
    ca = _RANGO_CONV.get(antes.get("conviccion"), 0)
    cb = _RANGO_CONV.get(despues.get("conviccion"), 0)
    if cb != ca:
        return ("confirm" if cb > ca else "weaken"), "convicción"
    for campo, motivo in _DIMS:
        va, vb = antes.get(campo), despues.get(campo)
        if va is None or vb is None or va == vb:
            continue
        return ("confirm" if vb > va else "weaken"), motivo
    return "none", "nada se mueve"


def _txt_estado(st: dict, es_global: bool) -> str:
    """La etiqueta publicada de un estado: lo que se lee en el documento."""
    if not st.get("existe"):
        return "sin lectura"
    d = st.get("direccion")
    if not es_global and d == "neutral":
        return "neutral"
    if es_global and d == "mixta":
        return "mixta"
    pal = st.get("palabra") or d or "-"
    conv = st.get("conviccion")
    return (f"{pal}, {config.CONVICCION_PM.lower()} {conv}" if conv
            else str(pal))


def _frase_efecto(ef: str, sujeto: str, a: dict, b: dict, es_glob: bool,
                  motivo: str) -> str:
    """El efecto medido, dicho como se diria en voz alta.

    Cuando la etiqueta no se mueve --misma direccion, misma conviccion-- la
    frase NO puede insinuar que se movio: dice que se mantiene y ensena lo unico
    que cambio, el recuento que la sostiene."""
    ta, tb = _txt_estado(a, es_glob), _txt_estado(b, es_glob)
    if ef == "reverse":
        return f"{sujeto} da la vuelta: de {ta} a {tb}"
    if ef == "neutralize":
        return f"{sujeto} se queda sin dirección: de {ta} a {tb}"
    if ef == "tactical":
        return f"no cambia la postura; mueve el timing: de {ta} a {tb}"
    if motivo in (VOCES_TXT, APOYOS_TXT):
        verbo = "pierde" if ef == "weaken" else "gana"
        if motivo == VOCES_TXT:
            det = (f"de {es_num_local(a.get('voces') or 0)} a "
                   f"{es_num_local(b.get('voces') or 0)} señales netas")
        else:
            det = (f"de {a.get('n_a')} a {b.get('n_a')} indicadores a favor")
        return (f"{sujeto} {verbo} apoyo sin cambiar de lado: sigue {ta}; "
                f"{det}")
    if ef == "weaken":
        return f"{sujeto} pierde apoyo: de {ta} a {tb}"
    if ef == "confirm":
        return f"{sujeto} gana apoyo: de {ta} a {tb}"
    return f"{sujeto} no cambia: sigue {ta}"


def _contrafactual(t: dict, snap: dict, recalc, setup: dict,
                   timing_base: str) -> dict:
    """Simula el cruce del umbral y devuelve el efecto MEDIDO."""
    # El cruce de banda del eje de riesgo no se simula con un percentil: lo que
    # cambia es la etiqueta publicada del regimen, y eso ya es su propio efecto.
    if t.get("key") == "_eje_riesgo":
        prev, nuevo = t.get("regimen_previo"), t.get("regimen_nuevo")
        # El centro de cada banda dice de que lado esta y como de lejos. Cruzar a
        # la banda contraria REVIERTE; caer en la banda neutral NEUTRALIZA; y
        # moverse a una banda mas extrema del MISMO lado no invalida nada:
        # confirma lo que ya se lee. Esto ultimo es justo lo que SPEC 6 exige
        # sacar de "invalida": "apetito de riesgo -> euforia" no invalida una
        # lectura pro-riesgo.
        centro = {b[2]: (b[0] + b[1]) / 2 for b in config.STATE_BANDS}
        ca, cb = centro.get(prev, 50.0), centro.get(nuevo, 50.0)
        la = 1 if ca > 70 else -1 if ca < 30 else 0
        lb = 1 if cb > 70 else -1 if cb < 30 else 0
        if la * lb < 0:
            ef = "reverse"
        elif lb == 0 and la != 0:
            ef = "neutralize"
        elif la == 0 and lb != 0:
            ef = "confirm"
        else:
            ef = "confirm" if abs(cb - 50) > abs(ca - 50) else "weaken"
        return dict(effect_type=ef, affected_dimension="regimen",
                    affected_theme=None, effect_motivo="banda del régimen",
                    before_state=dict(regimen=prev),
                    after_state=dict(regimen=nuevo),
                    efecto=f"el régimen pasa de «{prev}» a «{nuevo}»")
    if t.get("key") == "_setup":
        return dict(effect_type="tactical", affected_dimension="timing",
                    affected_theme=None,
                    before_state=dict(timing=timing_base),
                    after_state=dict(timing=timing_base), efecto=t.get("efecto"))
    cf = t.get("pct_cf")
    if recalc is None or cf is None or not np.isfinite(cf):
        return dict(effect_type=None, affected_dimension=None, affected_theme=None,
                    before_state={}, after_state={}, efecto=t.get("efecto"))

    snap2 = recalc({t["key"]: float(cf)})
    setup2 = setup_tactico(snap2)
    timing2, _n = timing_global(snap2, setup2)

    cands = []
    for ck in (t.get("afecta_keys") or []):
        a = _estado_tema(snap.get("postura") or [], ck)
        b = _estado_tema(snap2.get("postura") or [], ck)
        e, mo = _compara(a, b, "neutral")
        cands.append((e, "tema", ck, a, b, mo))
    ag, bg = _estado_gen(snap), _estado_gen(snap2)
    e, mo = _compara(ag, bg, "mixta")
    cands.append((e, "postura_general", None, ag, bg, mo))

    ef, dim, ck, a, b, motivo = max(cands, key=lambda c: _SEVERIDAD.get(c[0], 0))
    if ef == "none" and timing2 != timing_base:
        ta = config.TIMING_CABEZA.get(timing_base, timing_base).lower()
        tb = config.TIMING_CABEZA.get(timing2, timing2).lower()
        return dict(effect_type="tactical", affected_dimension="timing",
                    affected_theme=None, effect_motivo="timing",
                    before_state=dict(timing=timing_base),
                    after_state=dict(timing=timing2),
                    efecto=("no cambia la postura; mueve el momento: "
                            f"de «{ta}» a «{tb}»"))

    es_glob = dim == "postura_general"
    sujeto = ("la postura general" if es_glob
              else config.ASSET_CLASSES.get(ck, {}).get("label", ck).lower())
    return dict(effect_type=ef, affected_dimension=dim, affected_theme=ck,
                effect_motivo=motivo,
                before_state=dict(a, timing=timing_base),
                after_state=dict(b, timing=timing2),
                efecto=_frase_efecto(ef, sujeto, a, b, es_glob, motivo))


def _reclasifica(out: dict, snap: dict, recalc, setup: dict) -> dict:
    """Reparte los disparadores por EFECTO MEDIDO, no por la regla que los
    genero. Solo `neutralize` y `reverse` pueden aparecer bajo «invalida»."""
    timing_base, _ = timing_global(snap, setup)
    nuevos: dict = {"confirma": [], "debilita": [], "invalida": [], "tactico": []}
    descartados: list[dict] = []
    for bloque, filas in out.items():
        for t in filas:
            if t.get("key", "").startswith("_") is False and not _persistente(snap, t["key"]):
                t["descartado_por"] = "persistencia"
                descartados.append(t)
                continue
            r = _contrafactual(t, snap, recalc, setup, timing_base)
            t.update(r)
            t["bloque_origen"] = bloque
            ef = r.get("effect_type")
            if ef is None:                     # no se pudo medir: se respeta
                nuevos[bloque].append(t)
                continue
            if ef == "none":
                t["bloque"] = None
                descartados.append(t)
                continue
            dest = "tactico" if bloque == "tactico" else _EFECTO_BLOQUE[ef]
            t["bloque"] = dest
            nuevos[dest].append(t)
    # un indicador, un disparador: si dos reglas generaron el mismo, se queda el
    # de mas efecto medido. Repetirlo cuatro veces no lo hace mas probable.
    # Un indicador, un disparador: gana el de MAS efecto medido y, a igualdad de
    # efecto, el MAS CERCA de cumplirse. Quedarse con el primero que apareciera
    # publicaba el umbral a 5.6 sigmas teniendo el mismo efecto a 2.3.
    def _dist(t):
        sg = t.get("sigmas")
        return sg if sg is not None else 99.0

    mejor: dict = {}
    for b in ("invalida", "debilita", "confirma", "tactico"):
        for t in nuevos[b]:
            k = t["key"]
            sev = _SEVERIDAD.get(t.get("effect_type") or "none", 0)
            if k not in mejor:
                mejor[k] = (sev, t)
                continue
            sev0, t0 = mejor[k]
            if sev > sev0 or (sev == sev0 and _dist(t) < _dist(t0)):
                mejor[k] = (sev, t)
    vivos = {id(t) for _sv, t in mejor.values()}
    for b in list(nuevos):
        nuevos[b] = sorted(
            [t for t in nuevos[b] if id(t) in vivos],
            key=lambda t: (-_SEVERIDAD.get(t.get("effect_type") or "none", 0),
                           t.get("sigmas") if t.get("sigmas") is not None else 99)
        )[:4]
    nuevos["descartados"] = descartados
    return nuevos


# ============================================================================
# PRESENTACION (cuarta pasada). Nada de aqui decide: todo se DERIVA del estado
# ya calculado. Si una de estas funciones tuviera que consultar un umbral,
# estaria en el sitio equivocado.
# ============================================================================

def sesgo(ck: str, dir_tipo: str) -> str:
    """La etiqueta del sesgo en lenguaje portable.

    «Sobreponderar» arrastra una lectura de peso frente a un indice, y este
    documento no tiene ni pesos ni indice. La senal es la misma; cambia como se
    nombra. El mapeo se publica en la metodologia.
    """
    return config.SESGO_PRESENTACION.get(ck, {}).get(dir_tipo or "neutral", "Neutral")


def _inversa(a: str, b: str) -> bool:
    """Si «Evitar» solo dice, al reves, lo que ya dijo «Favorecer».

    Se compara por palabras significativas: si Evitar no aporta ninguna que
    Favorecer no tenga ya, es el inverso mecanico y no merece una columna.
    """
    def pal(t):
        t = re.sub(r"[^\wáéíóúñü ]+", " ", (t or "").lower())
        return {w for w in t.split() if len(w) > 3}

    def sec(t):
        t = re.sub(r"[^\wáéíóúñü ]+", " ", (t or "").lower())
        return [w for w in t.split() if len(w) > 3]

    # SPEC-7P 13: contar palabras nuevas no basta. «Duración larga y bonos de
    # vencimiento lejano» trae tres palabras que «Duración corta > larga» no
    # tiene, y aun asi no dice nada: ABRE nombrando el lado perdedor, y lo que
    # viene detras solo lo adorna. Si las dos primeras palabras con peso de
    # «Evitar» ya estaban en «Favorecer», es el inverso mecanico.
    cab = sec(b)[:2]
    if cab and all(w in pal(a) for w in cab):
        return True
    nuevas = pal(b) - pal(a)
    return len(nuevas) < config.EVITAR_MIN_PALABRAS_NUEVAS


def bottom_line(snap: dict) -> str:
    """UNA frase: el estado entero traducido a lenguaje de gestor.

    Combina postura, conviccion, timing, las dos o tres expresiones que mas
    pesan y la restriccion principal. No introduce ningun juicio nuevo: cada
    pieza sale del DecisionState. El lector tiene que poder leer solo el titular
    y esta frase y quedarse con la conclusion.
    """
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    pg = snap.get("postura_general") or {}
    palabra = pg.get("palabra")
    if not palabra:
        return ""
    temas = g.get("temas") or []
    # las expresiones que mas pesan: por conviccion y por cuanto se separan de
    # neutral, que es el orden en que las mira un gestor
    orden = {"alta": 3, "media": 2, "baja": 1}
    fuertes = sorted([t for t in temas if t["dir_tipo"] != "neutral"],
                     key=lambda t: (-orden.get(t["conviccion"], 0), -abs(t["paso"])))
    frases = [expresion_corta(t["key"], t["dir_tipo"]) for t in fuertes[:3]]
    expr = _lista_es(frases) if frases else "sin expresión con convicción"

    # SPEC-7P 11: la cabecera ya dice postura, conviccion y timing, en grande y
    # tres centimetros mas arriba. Repetirlos aqui gastaba la primera linea de
    # la conclusion en algo que el lector acababa de leer. Esta frase empieza
    # donde termina la cabecera: como se expresa y que la limita.
    # la restriccion: el indicador que mas contradice, si lo hay; si no, la
    # tension dominante
    ten = snap.get("tension_principal")
    dom = snap.get("tension_dominante")
    if ten:
        lim = (f"la principal restricción es {config.SHORT.get(ten['key'], ten['label'])} "
               f"en {ten['valor']} (p{ten['pct']:.0f})")
    elif dom:
        lim = f"la tensión de fondo es que {dom['texto']}"
    else:
        lim = "sin contradicción persistente que la limite"
    return f"Se expresa por {expr}; {lim}."


def implicacion_cartera(key: str, pct) -> str:
    """Hacia que lado de cada dimension empuja un indicador, hoy.

    Es una lectura del mapa de votos, no una presentacion, asi que vive en la
    capa y no en el template: si el template la compusiera, habria logica de
    inversion en un sitio donde SPEC 2 no la admite.

    El mapa dice hacia donde empuja cada clase cuando el indicador esta ALTO,
    asi que hace falta el percentil CRUDO y no el orientado: el orientado ya
    lleva dentro el signo del indicador y aplicarlo otra vez lo cancela.
    """
    import numpy as _np

    m = config.INDICATOR_ASSET_MAP.get(key) or {}
    if pct is None or not _np.isfinite(pct):
        return ""
    lado = 1 if pct >= 50 else -1
    xs = [expresion_corta(ck, "mas" if v * lado > 0 else "menos")
          for ck, v in m.items() if v]
    return " · ".join(xs[:4])


def expresion_corta(key: str, dir_tipo: str) -> str:
    """La inclinacion de un tema dicha en tres palabras: «duracion corta».

    Vive aqui, en la capa comun, porque la escriben la conclusion del HTML y la
    seccion de evidencia del semanal, y con la regla duplicada ya se separaron
    una vez las etiquetas de un mismo campo.

    La regla del nucleo existe por una errata real: "el dolar" + "dolar debil"
    salia "el dolar dolar debil". Cuando la etiqueta del sesgo YA nombra la
    clase, la frase es solo la etiqueta. Lo detecto el QA de erratas de la
    prosa en 2021-11-01 y 2022-06-15.
    """
    corto = config.CLASS_CORTO.get(key, key)
    sg = sesgo(key, dir_tipo).lower()
    nucleo = corto.split()[-1]
    return sg if nucleo in sg.split() else f"{corto} {sg}"


def _lista_es(xs: list[str]) -> str:
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " y " + xs[-1]


def cambios_decision(snap: dict) -> list[str]:
    """Los cambios que afectan a una DECISION, para la linea de pagina 1.

    Es el mismo `what_changed` que ya calcula el estado; aqui solo se recorta a
    lo que cabe en una linea y se le pone la flecha.
    """
    g = (getattr(snap.get("decision"), "guia", {}) or {})
    return list(g.get("what_changed") or [])


def scoring_band(nb: float, d1: float) -> str | None:
    from snapshot import scoring
    return scoring.band_label(nb - 0.1 if (d1 or 0) < 0 else nb + 0.1)


# ------------------------------------------------------------ path dependency
def path_dependency(ctx, snap: dict, postura_en, grupos: dict,
                    meses: int = 18) -> dict:
    """SPEC 7.2: cuanto lleva la postura actual, cuando cambio por ultima vez y
    si mejora o se deteriora. Se DERIVA recalculando la postura hacia atras --
    nunca de texto manual-- para que funcione en cualquier fecha, tenga o no
    snapshots guardados."""
    pg = snap.get("postura_general") or {}
    hoy = pg.get("palabra")
    if not hoy:
        return dict(disponible=False)
    asof = snap["asof"]
    cambio = None
    previa = None
    pasos = list(range(1, meses + 1))
    for m in pasos:
        D = asof - pd.DateOffset(months=m)
        try:
            ant = postura_en(ctx, D, grupos)
        except Exception:
            break
        if not ant:
            break
        lst = [dict(key=k, dir_tipo=v["dir_tipo"], conviccion=v["conviccion"],
                    direccion=v["direccion"], label=k, tier=v.get("tier"))
               for k, v in ant.items()]
        pal = _tilt_palabra(lst)
        if pal and pal != hoy:
            cambio = D
            previa = pal
            break
    # estado: comparando el nivel del eje de riesgo con hace un mes
    r = snap["riesgo"]
    d1 = r.get("d1m")
    if not np.isfinite(d1) or abs(d1) < 2:
        est = "estable"
    else:
        mejora = d1 > 0
        pro = hoy == "pro-riesgo"
        est = "reforzándose" if (mejora == pro) else "debilitándose"
    dur = None
    if cambio is not None:
        dur = max(1, int(round((asof - cambio).days / 30.44)))
    return dict(disponible=True, postura=hoy, previa=previa,
                desde=cambio, meses=dur, estado=est,
                busqueda_meses=meses)


def historia_posturas(ctx, snap: dict, postura_en, grupos: dict,
                      meses: int = 12) -> dict:
    """La postura de cada tema mes a mes, hacia atras.

    NO es una capa nueva ni un metodo nuevo: es la MISMA funcion que ya usan la
    columna «mes anterior» y `path_dependency` para reconstruir la postura en
    una fecha pasada. Aqui solo se llama doce veces en vez de una, para poder
    ensenar si la lectura de hoy es nueva, lleva meses o se esta dando la
    vuelta. Recalcular hacia atras es lo que permite que funcione en cualquier
    fecha, haya o no snapshots guardados.

    Lo que NO trae: el timing. El timing necesita el snapshot completo, y
    reconstruir doce snapshots enteros para una fila de color seria pagar
    demasiado por un dato que en el pasado tampoco se publico. Se dice en el
    tooltip en vez de inventarlo.
    """
    asof = snap["asof"]
    cols, faltan = [], 0
    for m in range(meses, -1, -1):
        D = asof - pd.DateOffset(months=m)
        try:
            ant = postura_en(ctx, D, grupos or {})
        except Exception:
            faltan += 1
            continue
        if not ant:
            faltan += 1
            continue
        idx = ctx.panel.index
        real = idx[idx <= pd.Timestamp(D)]
        cols.append(dict(
            fecha=(real[-1] if len(real) else pd.Timestamp(D)),
            temas={k: dict(dir_tipo=v["dir_tipo"], conviccion=v["conviccion"],
                           direccion=v["direccion"])
                   for k, v in ant.items()}))
    if not cols:
        return dict(disponible=False, motivo="no hay historia suficiente")
    return dict(disponible=True, columnas=cols, meses=meses, sin_dato=faltan,
                temas=list(config.TEMAS_ORDEN))


def linea_regimen(historia: dict, snap: dict) -> dict:
    """Los CAMBIOS de postura agregada, no la serie entera.

    Una linea de tiempo que dibujara los doce puntos seria ruido: lo que importa
    es cuando cambio y a que. Se agrega con la misma regla que publica la
    postura de hoy.
    """
    if not historia.get("disponible"):
        return dict(disponible=False)
    tramos = []
    for c in historia["columnas"]:
        lst = [dict(key=k, dir_tipo=v["dir_tipo"], conviccion=v["conviccion"],
                    direccion=v["direccion"], label=k)
               for k, v in c["temas"].items()]
        pal = _tilt_palabra(lst)
        if not pal:
            continue
        if tramos and tramos[-1]["palabra"] == pal:
            tramos[-1]["hasta"] = c["fecha"]
        else:
            tramos.append(dict(palabra=pal, desde=c["fecha"], hasta=c["fecha"]))
    hoy = (snap.get("postura_general") or {}).get("palabra")
    if tramos and hoy and tramos[-1]["palabra"] != hoy:
        tramos.append(dict(palabra=hoy, desde=snap["asof"], hasta=snap["asof"]))
    elif tramos and hoy:
        tramos[-1]["hasta"] = snap["asof"]
    return dict(disponible=bool(tramos), tramos=tramos)


def _tilt_palabra(postura_lst: list[dict]) -> str | None:
    score = 0
    for p in postura_lst:
        if p["dir_tipo"] == "neutral":
            continue
        ro = {"rv": +1, "cred": +1, "cicl": +1, "mp": +1}.get(p["key"])
        if ro is None:
            continue
        signo = +1 if p["dir_tipo"] == "mas" else -1
        score += signo * ro * config.CONV_ORDEN.get(p["conviccion"], 0)
    return "pro-riesgo" if score > 0 else "defensiva" if score < 0 else "mixta"


# --------------------------------------------------------------- what changed
def what_changed(snap: dict, cambios: dict) -> list[str]:
    """SPEC 8: se priorizan los cambios que AFECTAN DECISIONES, no los
    numericos. «VIX +4» no es un cambio; que el timing pase de confirmado a
    paciente, si.

    SPEC-7P 5: y salen YA ORDENADOS por lo que mueve una decision. Con una
    lista larga, las dos primeras lineas son las unicas que se leen, asi que el
    orden no es cosmetico: si un giro de postura sale detras de un extremo que
    entro, la pagina 1 cuenta lo segundo y calla lo primero.
    """
    if not (cambios or {}).get("disponible"):
        return []
    out: list[tuple[int, str, str]] = []
    # SPEC-7P B10: cada cambio sabe A DONDE lleva. Sin eso, «qué cambió» es una
    # lista que se lee y se olvida; con eso es el indice por el que se entra al
    # documento. El ancla se guarda aparte para no tocar el contrato de
    # `what_changed`, que el brief consume como texto.
    por_clase = {p["label"]: p["key"] for p in (snap.get("postura") or [])}
    por_ind = {d["label"]: d["key"] for d in config.INDICATORS}

    def add(rango: int, txt: str, flecha: str = "", ancla: str = ""):
        out.append((rango, f"{flecha}{txt}" if flecha else txt, ancla))

    # 1 · la postura de una clase cambia de lado
    for d in cambios.get("dir_cambios", []) or []:
        add(1, f"{d['clase']}: la inclinación pasa de {d['de']} a {d['a']}",
            ancla=f"#theme-{por_clase.get(d['clase'], '')}")
    # 2 · el regimen de riesgo cambia de banda
    if cambios.get("estado_de") and cambios["estado_de"] != cambios.get("estado_a"):
        add(2, f"el régimen pasa de «{cambios['estado_de']}» a "
               f"«{cambios['estado_a']}»", ancla="#sec-ahora")
    # 3 · el timing global no entra: el estado persistido no lo guarda, asi que
    #     no hay con que compararlo. Se declara aqui para que se vea que falta.
    # 4 · la conviccion de una clase
    for d in cambios.get("conv_cambios", []) or []:
        add(4, f"{d['clase']}: {config.CONVICCION_PM.lower()} "
               f"{d['de'] or 'neutral'} → "
               f"{d['a'] or 'neutral'}", "↑ " if d.get("subio") else "↓ ",
            ancla=f"#theme-{por_clase.get(d['clase'], '')}")
    # 5 · disparadores que se activan: un umbral cruzado mueve la lectura antes
    #     que cualquier otra cosa de esta lista
    g_hoy = (getattr(snap.get("decision"), "guia", {}) or {})
    for bloque, items in (g_hoy.get("triggers") or {}).items():
        if bloque == "descartados":
            continue
        for x in items:
            if x.get("ya"):
                add(5, f"disparador activo: {x.get('variable')} "
                       f"({x.get('condicion')})",
                    ancla=f"#ind-{x.get('key', '')}")
    # 6 · contradicciones de alto perfil
    for c in (snap.get("contradicciones") or [])[:1]:
        if c.get("destacada"):
            add(6, f"{c.get('label')} contradice la lectura",
                ancla=f"#ind-{c.get('key', '')}")
    # 7 · la expresion preferida de una clase
    # 8 · extremos que entran o salen, y las divergencias que abren o cierran
    for e in (cambios.get("entraron") or [])[:2]:
        add(8, f"nuevo extremo: {e['label']}",
            ancla=f"#ind-{por_ind.get(e['label'], '')}")
    for e in (cambios.get("salieron") or [])[:2]:
        add(8, f"{e['label']} sale de su extremo",
            ancla=f"#ind-{por_ind.get(e['label'], '')}")
    for d in (cambios.get("div_nac") or [])[:2]:
        add(8, f"nueva divergencia: {d}", ancla="#sec-vigilar")
    for d in (cambios.get("div_mur") or [])[:2]:
        add(8, f"se cierra la divergencia: {d}", ancla="#sec-vigilar")
    out.sort(key=lambda r: r[0])
    snap["_what_changed_ref"] = [dict(texto=t, ancla=a or "#sec-historia")
                                 for _r, t, a in out]
    return [txt for _r, txt, _a in out]


# ----------------------------------- 10. cluster-adjusted directional score
def cluster_score(snap: dict, grupos: dict) -> list[dict]:
    """METRICA PARALELA, solo para el tablero de auditoria (SPEC 10).

    NO se usa para decidir nada. Existe para poder comparar el sistema actual
    (un indicador, un voto) con el potencial (un cluster, un voto) antes de
    tomar una decision de metodologia que podria mover DIRECCIONES y con ellas
    invalidar las validaciones historicas ya hechas.
    """
    filas = filas_de(snap)
    post = {p["key"]: p for p in snap.get("postura", [])}
    out = []
    for ck in config.TEMAS_ORDEN:
        p = post.get(ck)
        if not p:
            continue
        # voto CRUDO: un indicador, un voto
        crudo = sum(np.sign(f["votos"].get(ck, 0)) for f in filas)
        # voto por CLUSTER: cada grupo de correlacion aporta el signo de su media
        porg: dict[int, list[float]] = {}
        for f in filas:
            v = f["votos"].get(ck, 0)
            if not v:
                continue
            g = grupos.get(f["key"], -1) if isinstance(grupos, dict) else -1
            porg.setdefault(g, []).append(np.sign(v))
        clu = sum(np.sign(np.mean(v)) for v in porg.values())
        dir_crudo = "mas" if crudo > 0 else "menos" if crudo < 0 else "neutral"
        dir_clu = "mas" if clu > 0 else "menos" if clu < 0 else "neutral"
        out.append(dict(key=ck, label=p["label"],
                        crudo=int(crudo), cluster=float(clu),
                        n_grupos=len(porg),
                        dir_actual=p["dir_tipo"], dir_crudo=dir_crudo,
                        dir_cluster=dir_clu,
                        cambiaria=(dir_clu != p["dir_tipo"]),
                        tipo_dif=_tipo_diferencia(p["dir_tipo"], dir_clu)))
    return out


# --------------------------------------------------- comparacion de sistemas
# SPEC-2P 14: la decision de cambiar de sistema de recuento no se toma con una
# tabla de una fecha. Lo que sigue NO decide nada --la direccion publicada
# sigue saliendo del voto por indicador-- pero deja medido, fecha a fecha, EN
# QUE se diferencian los dos sistemas, que es lo unico que permitiria decidirlo
# con datos mas adelante.
#
# La distincion que importa no es "cuantos difieren" sino DE QUE TIPO:
#
#   giro            mas <-> menos. Cambiaria el lado de una recomendacion. Es
#                   el unico tipo que invalidaria las validaciones historicas.
#   gana_direccion  neutral -> mas/menos. El cluster se moja donde el voto
#                   crudo se calla. Casi todas las diferencias son de este tipo,
#                   y se explican porque el recuento por cluster NO pasa por el
#                   filtro de conviccion.
#   pierde_direccion  mas/menos -> neutral. El cluster se calla donde el crudo
#                   decide.
#
# Contar los tres juntos daria una cifra alarmante y falsa.

TIPOS_DIF = ("ninguna", "giro", "gana_direccion", "pierde_direccion")


def _tipo_diferencia(actual: str, cluster: str) -> str:
    if actual == cluster:
        return "ninguna"
    if actual != "neutral" and cluster != "neutral":
        return "giro"
    return "gana_direccion" if actual == "neutral" else "pierde_direccion"


def comparacion_cluster(cs: list[dict]) -> dict:
    """El resumen de una fecha, por TIPO de diferencia."""
    cuenta = {t: 0 for t in TIPOS_DIF}
    for c in cs:
        cuenta[c.get("tipo_dif", "ninguna")] += 1
    n = len(cs)
    return dict(temas=n, **cuenta,
                difieren=n - cuenta["ninguna"],
                # lo unico que obligaria a revalidar la historia
                giros=cuenta["giro"],
                promovible=False,
                nota=("métrica paralela: la dirección publicada sigue saliendo "
                      "del voto por indicador"))


def comparar_fechas(ctx, fechas, build_snapshot=None) -> dict:
    """Corre la comparacion sobre varias fechas y agrega por tipo.

    Es la infraestructura que pide SPEC-2P 14: sin esto, "promover el cluster"
    seria una decision de gusto. Con esto es una decision con una tasa de giros
    medida sobre la historia. No se llama desde el pipeline --es una
    herramienta de analisis-- y por eso recibe el builder como parametro, para
    no crear una dependencia circular con build.
    """
    if build_snapshot is None:
        from snapshot.build import build_snapshot as _bs
        build_snapshot = _bs
    total = {t: 0 for t in TIPOS_DIF}
    filas, n_temas = [], 0
    for f in fechas:
        snap = build_snapshot(ctx, f)
        cs = (getattr(snap.get("decision"), "guia", {}) or {}).get("cluster_score") or []
        r = comparacion_cluster(cs)
        for t in TIPOS_DIF:
            total[t] += r[t]
        n_temas += r["temas"]
        filas.append(dict(fecha=str(f), **{t: r[t] for t in TIPOS_DIF}))
    return dict(fechas=len(filas), tema_fechas=n_temas, total=total, por_fecha=filas,
                tasa_giro=(total["giro"] / n_temas if n_temas else None))


# ============================================================================
# FASE 3 - lo que el PM Brief necesita. Se calcula AQUI, nunca en el template.
# ============================================================================

def confirmaciones(snap: dict, n: int = 4) -> list[dict]:
    """Las confirmaciones mas fuertes: la evidencia que SOSTIENE la postura.

    Sigue la regla de selectores (SPEC 3.1): solo indicadores del pilar del que
    habla la afirmacion --los compuestos ya vienen acotados a sus pilares-- y la
    extremidad solo desempata. Los extremos recientes ya vienen despriorizados
    desde `_bloque`, asi que un extremo de dos dias no encabeza la lista.
    """
    comps = snap.get("composites") or {}
    pg = (snap.get("postura_general") or {}).get("palabra")
    out, vistos = [], set()
    for nom, blk in (("técnico", comps.get("tecnico")), ("macro", comps.get("macro"))):
        for f in (blk or {}).get("lead") or []:
            if f["key"] in vistos or es_reciente(snap, f["key"]):
                continue
            vistos.add(f["key"])
            out.append(dict(key=f["key"], label=f["label"],
                            corto=config.SHORT.get(f["key"], f["label"]),
                            valor=f["valor"], pct=f["pct"], bloque=nom,
                            sostiene=pg))
    return out[:n]


def contradicciones_top(snap: dict, n: int = 3) -> list[dict]:
    """Las contradicciones mas fuertes, ya ordenadas por relevancia (pilar de
    eje primero), persistencia y extremidad."""
    out = []
    frescas = [c for c in (snap.get("contradicciones") or [])
               if not es_reciente(snap, c["key"])]
    for c in frescas[:n]:
        out.append(dict(key=c["key"], label=c["label"],
                        corto=config.SHORT.get(c["key"], c["label"]),
                        valor=c["valor"], pct=c["pct"], pilar=c["pilar_label"],
                        eje=c.get("eje"), persistente=c.get("persistente"),
                        dias=c.get("dias"), n_frentes=c.get("n_frentes"),
                        clases=[x["clase_label"] for x in c.get("frentes", [])]))
    return out


def divergencias_clave(snap: dict, n: int = 3) -> list[dict]:
    """Las divergencias entre pilares mas amplias y persistentes."""
    out = []
    for d in (snap.get("divergencias") or [])[:n]:
        out.append(dict(alto=d["alto_label"], bajo=d["bajo_label"],
                        alto_score=d["alto_score"], bajo_score=d["bajo_score"],
                        gap=d["gap"], duracion=d["duracion"]))
    return out


def evidencia_clave(snap: dict, n: int = 10) -> list[dict]:
    """Los indicadores DETERMINANTES para la lectura de hoy: los que estan mas
    lejos de su normalidad y votan sobre alguna clase. No son los 42 --eso vive
    en el HTML--, son los que mueven la conclusion."""
    filas = [f for f in filas_de(snap)
             if np.isfinite(f.get("pct", np.nan)) and f.get("votos")
             and not es_reciente(snap, f["key"])]
    filas.sort(key=lambda f: -abs(f["pct"] - 50.0))
    return [dict(key=f["key"], label=f["label"],
                 corto=config.SHORT.get(f["key"], f["label"]),
                 valor=f["valor"], pct=f["pct"], lectura=f["lectura"],
                 extremo=bool(f.get("extremo")))
            for f in filas[:n]]


def valores_brief(snap: dict) -> dict:
    """Los valores que HTML y PDF deben mostrar IDENTICOS. Es el contrato que
    comprueba el check de consistencia: si divergen, uno de los dos miente."""
    ds = snap.get("decision")
    g = getattr(ds, "guia", {}) or {}
    pg = snap.get("postura_general") or {}
    ten = snap.get("tension_principal")
    riesgo = ds.ejes.get("riesgo") if ds else None
    ciclo = ds.ejes.get("ciclo") if ds else None
    return {
        "regimen_riesgo": (snap.get("titular") or {}).get("estado"),
        "riesgo_pct": round(riesgo.hist_pct, 1) if riesgo else None,
        "riesgo_nivel": round(riesgo.nivel, 1) if riesgo else None,
        "ciclo_nivel": round(ciclo.nivel, 1) if ciclo else None,
        "postura": pg.get("palabra"),
        "conviccion": pg.get("conviccion"),
        "timing": g.get("timing"),
        "horizonte": g.get("horizonte_dominante"),
        "tension": (ten or {}).get("key"),
        "setup": (g.get("setup") or {}).get("titulo"),
        # La etiqueta PUBLICADA, que es la que los dos documentos escriben. El
        # contrato es «dicen lo mismo», no «guardan el mismo string interno».
        "temas": {t["key"]: (t.get("sesgo") or t["postura"], t.get("conviccion"),
                             t["horizonte"])
                  for t in (g.get("temas") or [])},
        "triggers": {b: len(v) for b, v in (g.get("triggers") or {}).items()},
    }


def estado_canonico(snap: dict) -> dict:
    """EL estado canonico (HTML-POLISH 1). Dieciseis campos, uno por linea.

    Es la lista literal que el punto 1 exige que HTML y PDF compartan. No
    calcula nada: recoge lo que el DecisionState ya publica y lo normaliza a
    tipos serializables, para que el documento pueda llevarlo escrito y un test
    pueda compararlo contra el estado sin pasar por el texto.

    Orden y nombres, como en el punto 1:
      1 overall stance            9  positioning by theme
      2 overall conviction        10 conviction by theme
      3 global timing             11 timing overrides
      4 dominant horizon          12 triggers
      5 confirmed risk regime     13 affected themes
      6 candidate risk regime     14 What Changed events
      7 confirmation status       15 dominant tension
      8 cycle regime              16 contradictory indicator
    """
    ds = snap.get("decision")
    g = getattr(ds, "guia", {}) or {}
    pg = snap.get("postura_general") or {}
    t = snap.get("titular") or {}
    tr = t.get("transicion") or {}
    ciclo = ds.ejes.get("ciclo") if ds else None
    temas = g.get("temas") or []
    ind = snap.get("tension_principal") or snap.get("tension_contexto")
    dom = snap.get("tension_dominante") or {}

    disparadores, afectados = [], {}
    for bloque, items in (g.get("triggers") or {}).items():
        if bloque == "descartados":
            continue
        for x in items:
            disparadores.append(dict(
                key=x.get("key"), bloque=bloque, variable=x.get("variable"),
                condicion=x.get("condicion"),
                umbral=_num(x.get("umbral")), sigmas=_num(x.get("sigmas")),
                efecto=x.get("effect_type")))
            if x.get("affected_theme"):
                afectados.setdefault(x["affected_theme"], []).append(x.get("key"))

    return {
        "stance": pg.get("palabra"),
        "conviction": pg.get("conviccion"),
        "timing": g.get("timing"),
        "horizon": g.get("horizonte_dominante"),
        "regime_confirmed": t.get("estado"),
        "regime_candidate": tr.get("destino"),
        "regime_confirmation": (
            None if not tr.get("destino") else
            dict(confirmando=bool(tr.get("confirmando")),
                 dias=int(tr.get("dias") or 0),
                 dias_requeridos=int(tr.get("dias_requeridos") or 0),
                 pct=_num(tr.get("pct")), banda_pct=tr.get("banda_pct"))),
        "cycle_regime": (_estado_ciclo_txt(ciclo.nivel) if ciclo is not None
                         else None),
        "positioning": {x["key"]: x.get("dir_tipo") for x in temas},
        "conviction_by_theme": {x["key"]: x.get("conviccion") for x in temas},
        "timing_overrides": {x["key"]: x.get("timing") for x in temas
                             if x.get("timing_override")},
        "triggers": sorted(disparadores, key=lambda d: (d["bloque"], d["key"] or "")),
        "affected_themes": {k: sorted(v) for k, v in sorted(afectados.items())},
        "what_changed": list(g.get("what_changed") or []),
        "dominant_tension": (dict(alto=dom.get("alto_label"), bajo=dom.get("bajo_label"),
                                  tipo=dom.get("tipo")) if dom else None),
        "contradictory_indicator": (dict(key=ind.get("key"), valor=str(ind.get("valor")),
                                         pct=_num(ind.get("pct")),
                                         contexto=not snap.get("tension_principal"))
                                    if ind else None),
    }


def _num(v):
    """Float serializable, o None. Un NaN en un JSON no sobrevive al viaje."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 6) if f == f else None


def _estado_ciclo_txt(nivel) -> str | None:
    spec = config.AXES["ciclo"]
    if nivel is None or nivel != nivel:
        return None
    return spec["high"] if nivel >= 55 else spec["low"] if nivel <= 45 else "neutral"


# --------------------------------------- los disparadores que van al PM Brief
# Prioridad por EFECTO SOBRE LA POSTURA: lo que la revierte pesa mas que lo que
# solo le quita conviccion, y eso mas que lo que la refuerza.
_BRIEF_PRIO = {"invalida": 0, "debilita": 1, "confirma": 2, "tactico": 3}
BRIEF_MAX_TRIGGERS = 4


def triggers_brief(snap: dict, n: int = BRIEF_MAX_TRIGGERS) -> list[dict]:
    """Los tres o cuatro disparadores que IMPORTAN, para el brief.

    Dos reglas, y las dos son de decision, asi que viven aqui y no en el
    template:

      - Lo marcado FUERA DE ALCANCE PRACTICO no entra. Si exige un movimiento
        que ese indicador no hace, no vigila nada; se queda en el HTML, que es
        donde vive la auditoria.
      - Se ordenan por efecto sobre la postura y, dentro de eso, por cercania:
        primero lo que la revierte, y de eso, lo que esta mas cerca de pasar.

    Si hacen falta mas de cuatro, es que no se ha priorizado.
    """
    fuera = []
    for bloque, items in (snap.get("decision").guia.get("triggers") or {}).items():
        if bloque == "descartados":
            continue                          # sin efecto medible: no se vigila
        for t in items:
            if t.get("alcanzable") is False:
                continue                      # no invalida nada en la practica
            if t.get("ya"):
                continue                      # ya activado: no es algo que vigilar
            # El pie del brief promete que solo lista lo que esta al alcance de
            # un movimiento normal. El techo se aplica a TODOS los bloques, no
            # solo a los invalidantes: si no, el pie miente.
            sg = t.get("sigmas")
            if sg is not None and sg > config.BRIEF_SIGMA_MAX:
                continue
            fuera.append(dict(t, _prio=_BRIEF_PRIO.get(bloque, 9),
                              _dist=t.get("sigmas") if t.get("sigmas") is not None else 99))
    fuera.sort(key=lambda t: (t["_prio"], t["_dist"]))
    # un indicador, una linea: si aparece en dos bloques se queda el de mas
    # efecto, que es el que ya esta primero.
    vistos, out = set(), []
    for t in fuera:
        if t["key"] in vistos:
            continue
        vistos.add(t["key"])
        out.append(t)
    return out[:n]
