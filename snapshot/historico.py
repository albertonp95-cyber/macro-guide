# -*- coding: utf-8 -*-
"""Memoria entre snapshots: guarda un resumen de cada ejecucion y compara la de
hoy con la anterior.

De aqui salen dos cosas del documento:
  - La seccion "Que cambio desde el anterior" (lo mas util de un producto
    semanal: nadie va a cotejar 42 filas contra la semana pasada a mano).
  - La comprobacion de estabilidad de los deltas: si un delta trimestral gira
    mas que un umbral sin que el nivel se haya movido, es ruido de metodo, no
    del mercado, y hay que decirlo.

Se guarda un JSON compacto por fecha en data/historico/. Solo el snapshot real
lo escribe; las fechas de control (2008, 2020...) no ensucian la memoria. La
comparacion usa el ultimo guardado ESTRICTAMENTE anterior a la fecha de hoy, asi
que regenerar el mismo dia compara contra el dia previo, no contra si mismo.
"""

from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "historico")


def _n(x):
    """float JSON-seguro, o None."""
    return float(x) if x is not None and np.isfinite(x) else None


def resumen_estado(snap: dict) -> dict:
    """El minimo para poder comparar dos snapshots. No es el snapshot entero:
    solo lo que la seccion de cambios necesita mirar."""
    postura = {p["key"]: dict(direccion=p["direccion"], dir_tipo=p["dir_tipo"],
                              conviccion=p.get("conviccion"))
               for p in snap["postura"]}
    extremos = {}
    for e in snap["extremos"]:
        k = next((d["key"] for d in config.INDICATORS if d["label"] == e["label"]), None)
        if k:
            extremos[k] = dict(pct=_n(e["pct"]), tipo=e["tipo"])
    ejes = {e["key"]: dict(level=_n(e["level"]), hist_pct=_n(e["hist_pct"]),
                           d1m=_n(e["d1m"]), d3m=_n(e["d3m"]))
            for e in snap["ejes"]}
    pilares = {pil["key"]: dict(score=_n(pil["score"]), d3m=_n(pil["d3m"]))
               for pil in snap["tablero"]}
    divs = sorted("|".join(sorted((d["alto"], d["bajo"]))) for d in snap["divergencias"])
    docs = sorted(d["id"] for d in snap["documentos"]["documentos"])
    return dict(
        asof=snap["asof"].strftime("%Y-%m-%d"),
        estado=snap["titular"]["estado"],
        score=_n(snap["riesgo"]["score"]),
        postura=postura, extremos=extremos, ejes=ejes, pilares=pilares,
        divergencias=divs, documentos=docs,
    )


def guardar(snap: dict) -> str:
    os.makedirs(DIR, exist_ok=True)
    est = resumen_estado(snap)
    ruta = os.path.join(DIR, f"estado-{est['asof']}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=2)
    return ruta


def cargar_previo(asof) -> dict | None:
    """El ultimo estado guardado con fecha ESTRICTAMENTE anterior a `asof`."""
    if not os.path.isdir(DIR):
        return None
    asof = pd.Timestamp(asof)
    cand = []
    for ruta in glob.glob(os.path.join(DIR, "estado-*.json")):
        try:
            f = pd.Timestamp(os.path.basename(ruta)[7:-5])
        except Exception:
            continue
        if f < asof:
            cand.append((f, ruta))
    if not cand:
        return None
    _f, ruta = max(cand, key=lambda t: t[0])
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------- comparacion
def comparar(snap: dict, previo: dict | None) -> dict:
    """Que cambio de `previo` a `snap`. Devuelve siempre un dict; si no hay
    anterior, disponible=False y la seccion lo dice en una linea."""
    if not previo:
        return dict(disponible=False)

    hoy = resumen_estado(snap)
    fecha_prev = previo.get("asof")

    # --- inclinaciones que cambiaron de direccion
    dir_cambios = []
    conv_cambios = []
    labels = {p["key"]: p["label"] for p in snap["postura"]}
    for ck, ah in hoy["postura"].items():
        an = previo["postura"].get(ck)
        if not an:
            continue
        # Por dir_tipo y no por la palabra: la etiqueta publicada puede
        # cambiar de vocabulario --y cambio-- sin que la inclinacion se mueva,
        # y comparar el texto haria aparecer siete giros que no existen.
        if ah.get("dir_tipo") != an.get("dir_tipo"):
            dir_cambios.append(dict(clase=labels.get(ck, ck),
                                    de=_palabra(ck, an), a=_palabra(ck, ah)))
        elif ah["conviccion"] != an["conviccion"]:
            conv_cambios.append(dict(clase=labels.get(ck, ck),
                                     de=an["conviccion"], a=ah["conviccion"],
                                     subio=_orden_conv(ah["conviccion"]) >
                                     _orden_conv(an["conviccion"])))

    # --- extremos que entraron o salieron
    ex_prev, ex_hoy = set(previo["extremos"]), set(hoy["extremos"])
    ilbl = {d["key"]: d["label"] for d in config.INDICATORS}
    entraron = [dict(label=ilbl.get(k, k), pct=hoy["extremos"][k]["pct"],
                     tipo=hoy["extremos"][k]["tipo"]) for k in ex_hoy - ex_prev]
    salieron = [dict(label=ilbl.get(k, k)) for k in ex_prev - ex_hoy]
    entraron.sort(key=lambda e: -abs((e["pct"] or 50) - 50))

    # --- divergencias que nacieron o murieron
    dv_prev, dv_hoy = set(previo["divergencias"]), set(hoy["divergencias"])
    plbl = config.PILLARS

    def _dvtxt(key):
        a, b = key.split("|")
        return f"{plbl[a]['label'].lower()} frente a {plbl[b]['label'].lower()}"
    div_nac = [_dvtxt(k) for k in dv_hoy - dv_prev]
    div_mur = [_dvtxt(k) for k in dv_prev - dv_hoy]

    # --- pilares que se movieron mas del umbral
    pil_mov = []
    for pk, ph in hoy["pilares"].items():
        pa = previo["pilares"].get(pk)
        if not pa or ph["score"] is None or pa["score"] is None:
            continue
        d = ph["score"] - pa["score"]
        if abs(d) >= config.CAMBIO_PILAR_PTS:
            pil_mov.append(dict(pilar=plbl[pk]["label"], de=pa["score"],
                                a=ph["score"], delta=d))
    pil_mov.sort(key=lambda x: -abs(x["delta"]))

    # --- fuentes nuevas
    docs_prev = set(previo.get("documentos", []))
    docs_nuevos = [d["titulo"] for d in snap["documentos"]["documentos"]
                   if d["id"] not in docs_prev]

    # --- estabilidad de los deltas: giro respecto al anterior
    giro = _giros(hoy, previo)

    algo = bool(dir_cambios or conv_cambios or entraron or salieron or
                div_nac or div_mur or pil_mov or docs_nuevos)
    return dict(
        disponible=True, fecha_prev=fecha_prev, algo=algo,
        estado_de=previo.get("estado"), estado_a=hoy["estado"],
        score_de=previo.get("score"), score_a=hoy["score"],
        dir_cambios=dir_cambios, conv_cambios=conv_cambios,
        entraron=entraron, salieron=salieron,
        div_nac=div_nac, div_mur=div_mur, pil_mov=pil_mov,
        docs_nuevos=docs_nuevos, giro=giro,
    )


def _palabra(ck: str, est: dict) -> str:
    """La etiqueta de la inclinación EN EL VOCABULARIO DE HOY.

    El estado persistido guarda la palabra con la que se escribió aquel día, y
    el vocabulario cambió: los estados de 2011 dicen «sobreponderar», que es
    lenguaje de peso frente a un índice y este documento ya no usa. Lo que no
    cambia es `dir_tipo`, así que la palabra se vuelve a derivar de él.
    """
    dt = est.get("dir_tipo")
    if dt in ("mas", "menos"):
        return config.ASSET_CLASSES.get(ck, {}).get(dt) or est.get("direccion") or dt
    return est.get("direccion") or "neutral"


def _orden_conv(c):
    return config.CONV_ORDEN.get(c, 0)


def _giros(hoy: dict, previo: dict) -> dict:
    """El mayor giro de un delta respecto al anterior, y si el nivel lo
    acompana. Un giro grande sin movimiento del nivel es inestabilidad de
    metodo, no del mercado."""
    peor = None
    for grp, campos in (("ejes", ("d1m", "d3m")), ("pilares", ("d3m",))):
        for k, ah in hoy[grp].items():
            an = previo.get(grp, {}).get(k)
            if not an:
                continue
            nivel_h = ah.get("level", ah.get("score"))
            nivel_a = an.get("level", an.get("score"))
            nivel_mov = (abs(nivel_h - nivel_a)
                         if nivel_h is not None and nivel_a is not None else None)
            for c in campos:
                if ah.get(c) is None or an.get(c) is None:
                    continue
                g = abs(ah[c] - an[c])
                if peor is None or g > peor["giro"]:
                    lbl = (config.AXES[k]["label"] if grp == "ejes"
                           else config.PILLARS[k]["label"])
                    peor = dict(giro=g, serie=lbl, campo=c, nivel_mov=nivel_mov)
    if peor is None:
        return dict(disponible=False)
    # Inestable = el delta salto mas que el umbral MIENTRAS el nivel casi no se
    # movio. Si el nivel tambien se movio, el giro del delta es consecuencia del
    # mercado, no del metodo -- y no se marca.
    peor["inestable"] = bool(
        peor["giro"] > config.DELTA_GIRO_AVISO and
        (peor["nivel_mov"] is None or peor["nivel_mov"] < config.DELTA_GIRO_AVISO))
    peor["disponible"] = True
    return peor


__all__ = ["guardar", "cargar_previo", "comparar", "resumen_estado", "DIR"]
