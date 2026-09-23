# -*- coding: utf-8 -*-
"""Capa documental: lee docs/registro.json y lo prepara para el render.

REGLAS DURAS DE ESTA CAPA
-------------------------
1. El texto NUNCA se convierte en un numero que se sume a las senales
   cuantitativas. No hay puntuacion de sentimiento y no la va a haber. Si se
   mezclan, se pierde la capacidad de ver cuando discrepan, que es todo el
   valor de tener la capa.
2. Se distingue siempre entre lo que el documento DICE (con cita y fecha) y
   lo que se INFIERE de el. En el HTML son dos tipografias distintas.
3. Toda afirmacion lleva documento y fecha de origen. Sin trazabilidad, no
   entra.
4. VENTANA DE VIGENCIA. Por defecto, un documento de mas de dos semanas NO se
   usa: describe otro mercado. Solo un documento estructural (una guia
   trimestral, unas minutas) puede pedir mas vida declarando `vigencia_dias`,
   y aun asi aparece con la edad bien visible.
5. No se hacen predicciones a partir del texto. Esta capa describe el debate,
   no lo resuelve. Un objetivo de precio de un tercero se puede CITAR ("la casa
   X proyecta Y"), pero no se convierte en senal ni en pronostico propio.
6. Si dos documentos de calidad dicen cosas opuestas, se muestran los dos.

Y una de higiene: un documento publicado DESPUES de la fecha del snapshot no
aparece. Si no, el snapshot de 2008 se leeria con research de 2026.

DOS FORMATOS
------------
- "titulares": entradas cortas, estilo MLIV -- una frase, fuente, fecha. Es
  el formato de un feed de titulares de mercado. Se pegan tal cual.
- "documentos": research con tesis, lo que dice (con referencias) y contraste
  con los indicadores del tablero.
Ambos respetan la ventana de vigencia y el corte por fecha del snapshot.
"""

from __future__ import annotations

import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(ROOT, "docs", "registro.json")

# Ventana de vigencia, en dias naturales. Es la regla del usuario: nada de
# mas de dos semanas, salvo que el propio documento declare otra cosa.
VIGENCIA_DIAS = 14
FRESCO_DIAS = 7        # por debajo de esto, "reciente"; por encima, "esta semana"

TIPOS = {
    "bancos-centrales": "Bancos centrales",
    "research": "Research",
    "datos-economicos": "Datos económicos",
    "prensa": "Prensa",
    "mliv": "Bloomberg MLIV",
    "titular": "Titular",
}


def _clasificar(fecha, asof, vigencia):
    """Devuelve (edad_dias, estado). Estado: 'futuro', 'caducado', 'reciente',
    'semana'."""
    edad = int((asof - fecha).days)
    if fecha > asof:
        return edad, "futuro"
    if edad > vigencia:
        return edad, "caducado"
    return edad, ("reciente" if edad <= FRESCO_DIAS else "semana")


def cargar(asof) -> dict:
    """Titulares y documentos vigentes a `asof`."""
    asof = pd.Timestamp(asof)
    vacio = dict(documentos=[], titulares=[], total=0, n_titulares=0,
                 futuros=0, caducados=0, contrastes=[])
    if not os.path.exists(REGISTRO):
        return vacio

    with open(REGISTRO, encoding="utf-8") as f:
        raw = json.load(f)

    futuros = caducados = 0

    # ------------------------------------------------------ titulares
    titulares = []
    for h in raw.get("titulares", []):
        fecha = pd.Timestamp(h["fecha"])
        edad, estado = _clasificar(fecha, asof, h.get("vigencia_dias", VIGENCIA_DIAS))
        if estado == "futuro":
            futuros += 1
            continue
        if estado == "caducado":
            caducados += 1
            continue
        h = dict(h)
        h.update(fecha_ts=fecha, edad=edad, frescura=estado,
                 tipo_label=TIPOS.get(h.get("tipo"), h.get("tipo") or "Titular"))
        titulares.append(h)
    titulares.sort(key=lambda x: x["fecha_ts"], reverse=True)

    # ------------------------------------------------------ documentos
    docs = []
    for d in raw.get("documentos", []):
        fecha = pd.Timestamp(d["fecha"])
        edad, estado = _clasificar(fecha, asof, d.get("vigencia_dias", VIGENCIA_DIAS))
        if estado == "futuro":
            futuros += 1
            continue
        if estado == "caducado":
            caducados += 1
            continue
        d = dict(d)
        d.update(fecha_ts=fecha, edad=edad, frescura=estado,
                 vigencia=d.get("vigencia_dias", VIGENCIA_DIAS),
                 tipo_label=TIPOS.get(d.get("tipo"), d.get("tipo") or "—"))
        docs.append(d)
    docs.sort(key=lambda x: x["fecha_ts"], reverse=True)

    # Relación de cada fuente con un indicador. 'resuelve' (choque irrefutable
    # ya adjudicado) va primero por ser lo más accionable; luego 'complementa'
    # (la fuente añade una lectura). Lo más reciente, antes.
    contrastes = []
    for d in docs:
        for c in d.get("contrasta", []):
            contrastes.append(dict(
                doc_id=d["id"], fuente=d["fuente"], titulo=d["titulo"],
                fecha_ts=d["fecha_ts"], edad=d["edad"], frescura=d["frescura"],
                indicador=c["indicador"], postura=c.get("postura", "complementa"),
                texto=c["texto"], veredicto=c.get("veredicto"),
            ))
    _orden = {"resuelve": 0, "complementa": 1}
    contrastes.sort(key=lambda c: (_orden.get(c["postura"], 2),
                                   -c["fecha_ts"].toordinal()))

    return dict(documentos=docs, titulares=titulares,
                total=len(docs), n_titulares=len(titulares),
                futuros=futuros, caducados=caducados, contrastes=contrastes)


def enriquecer(reg: dict, tablero: list[dict]) -> dict:
    """Pega a cada contraste el valor vivo del indicador con el que habla.

    Asi el contraste no se queda congelado en el texto: la frase es fija, pero
    la cifra con la que se compara es siempre la de hoy.
    """
    por_clave = {f["key"]: (f, pil["label"])
                 for pil in tablero for f in pil["filas"]}
    for c in reg["contrastes"]:
        fila, pilar = por_clave.get(c["indicador"], (None, None))
        c["fila"] = fila
        c["pilar"] = pilar
    reg["contrastes"] = [c for c in reg["contrastes"] if c["fila"] is not None]
    return reg


__all__ = ["cargar", "enriquecer", "VIGENCIA_DIAS", "FRESCO_DIAS"]
