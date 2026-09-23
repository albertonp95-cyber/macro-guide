# -*- coding: utf-8 -*-
"""CROSS-ASSET TAPE (SEMANTIC-PASS 13-21).

Qué hicieron los mercados en los últimos doce meses, panel por panel, con la
visión histórica del modelo dibujada debajo.

NO es un backtest. No calcula acierto, ni alfa, ni P&L: pone el precio y la
postura en el mismo eje de tiempo para que el lector vea qué hacía el mercado
mientras la lectura evolucionaba, y saque sus conclusiones. Cualquier métrica
de rendimiento del modelo exigiría un diseño propio --ventanas, costes,
rebalanceo-- que este proyecto no tiene y que no se improvisa en un gráfico.

QUÉ SE DIBUJA. Un panel por decisión de cartera, no por activo:

    equity        SPY                      cuánta beta de renta variable
    rates         TLT                      tramo corto o duración larga
    credit        HYG / LQD                IG o HY
    style         XLY / XLP                defensivo o cíclico
    commodities   DBC                      materias primas
    gold          GLD                      oro como refugio
    usd           UUP                      overlay de divisa

Las relativas van como COCIENTE --crédito y estilo-- porque la decisión es
relativa: comparar HYG contra LQD en niveles de precio no significa nada.

NORMALIZACION. Todo se rebasa a 100 en el primer día de la ventana, incluidos
los cocientes. Es la única forma de poner siete series de escalas distintas en
paneles comparables (SEMANTIC-PASS 15).

TRAMO CORTO. No hay una serie de tramo corto en el pipeline, así que el panel
de tasas muestra la duración larga (TLT) y lo DICE. Inventar un «front-end
performance» a partir de lo que hay seria fabricar un dato.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

# Un panel por decisión. `serie` es la expresión sobre las columnas de precios;
# `sobre` la divide cuando la decisión es relativa. `tema` conecta el panel con
# la dimensión del DecisionState cuya historia se dibuja debajo.
# `alza` es el dir_tipo que expresa que la LINEA SUBA, y se escribe a mano
# panel por panel porque es lo unico que da sentido al color de la banda: con
# TLT dibujado, que el modelo prefiriera duracion corta es una postura EN
# CONTRA de la linea, no a favor. Hoy las siete salen "mas" porque las siete
# series se construyeron en esa direccion; queda escrito para que invertir un
# cociente manana no vuelva el color mentira en silencio.
PANELES: list[dict] = [
    dict(id="equity", alza="mas", titulo="Renta variable", tema="rv",
         serie="SPY", sobre=None, nota="SPY"),
    dict(id="rates", alza="mas", titulo="Tasas y duración", tema="dur",
         serie="TLT", sobre=None, nota="Duración larga · TLT",
         aviso="No hay serie de tramo corto en el pipeline: se muestra la "
               "duración larga, que es el otro lado de la misma decisión."),
    dict(id="credit", alza="mas", titulo="Crédito", tema="cred",
         serie="HYG", sobre="LQD", nota="HY frente a IG · HYG/LQD"),
    dict(id="style", alza="mas", titulo="Estilo", tema="cicl",
         serie="XLY", sobre="XLP", nota="Cíclico frente a defensivo · XLY/XLP"),
    dict(id="commodities", alza="mas", titulo="Materias primas", tema="mp",
         serie="DBC", sobre=None, nota="DBC"),
    dict(id="gold", alza="mas", titulo="Oro", tema="oro", serie="GLD", sobre=None,
         nota="GLD"),
    dict(id="usd", alza="mas", titulo="Dólar", tema="usd", serie="UUP", sobre=None,
         nota="Overlay de divisa · UUP"),
]

MESES = 12
_BD_3M = 63


def _serie(px: pd.DataFrame, p: dict) -> pd.Series | None:
    """La serie del panel, ya como cociente si la decisión es relativa."""
    if px is None or p["serie"] not in px.columns:
        return None
    s = px[p["serie"]].dropna()
    if p["sobre"]:
        if p["sobre"] not in px.columns:
            return None
        d = px[p["sobre"]].dropna()
        s = (s / d).dropna()
    return s if len(s) > 10 else None


def _banda(historia: dict, tema: str) -> list[dict]:
    """La visión del modelo mes a mes, de la MISMA reconstrucción que usa el
    mapa de calor. No se infiere del precio (SEMANTIC-PASS 17)."""
    if not (historia or {}).get("disponible"):
        return []
    out = []
    for c in historia["columnas"]:
        v = (c.get("temas") or {}).get(tema)
        if not v:
            out.append(dict(fecha=c["fecha"], dir_tipo=None, etiqueta="sin dato"))
            continue
        out.append(dict(fecha=c["fecha"], dir_tipo=v.get("dir_tipo"),
                        conviccion=v.get("conviccion"),
                        etiqueta=config.SESGO_PRESENTACION.get(tema, {}).get(
                            v.get("dir_tipo") or "neutral", "Neutral")))
    return out


def construir(ctx, asof, historia: dict) -> dict:
    """Los siete paneles, con la MISMA ventana de doce meses para todos.

    La ventana la fija `asof`, no cada serie: el punto 16 exige que el lector
    pueda trazar una vertical y ver qué hacía cada mercado ese día.
    """
    px = getattr(ctx, "prices", None)
    ini = asof - pd.DateOffset(months=MESES)
    paneles = []
    for p in PANELES:
        s = _serie(px, p)
        if s is None:
            paneles.append(dict(p, disponible=False,
                                motivo="serie no disponible en el pipeline",
                                puntos=[], banda=_banda(historia, p["tema"])))
            continue
        v = s.loc[(s.index >= ini) & (s.index <= asof)].dropna()
        if len(v) < 20:
            paneles.append(dict(p, disponible=False,
                                motivo="menos de 20 observaciones en la ventana",
                                puntos=[], banda=_banda(historia, p["tema"])))
            continue
        base = float(v.iloc[0])
        idx = (v / base) * 100.0 if base else v * 0.0
        r12 = float(idx.iloc[-1] - 100.0)
        prev3 = v.loc[:asof].tail(_BD_3M)
        r3 = (float(v.iloc[-1] / prev3.iloc[0] - 1.0) * 100.0
              if len(prev3) > 5 and prev3.iloc[0] else float("nan"))
        paneles.append(dict(
            p, disponible=True, motivo="",
            puntos=[(d, float(x)) for d, x in idx.items()],
            desde=v.index[0], hasta=v.index[-1], n=len(v),
            ultimo=float(v.iloc[-1]), r3m=r3, r12m=r12,
            banda=_banda(historia, p["tema"])))
    # Los cortes trimestrales del eje comun. Se calculan una vez sobre la
    # ventana, no por serie: es lo que hace que la vertical del lector caiga en
    # el mismo sitio en los siete paneles (SEMANTIC-PASS 16, 38).
    cortes = [ini + pd.DateOffset(months=k) for k in (3, 6, 9)]
    return dict(disponible=any(p["disponible"] for p in paneles),
                desde=ini, hasta=asof, meses=MESES, paneles=paneles,
                cortes=cortes, resumen=_resumen(paneles))


def _resumen(paneles: list[dict]) -> list[dict]:
    """Tres observaciones, DESCRIPTIVAS (SEMANTIC-PASS 21).

    No se dice «confirma» ni «diverge»: eso exigiría una regla documentada que
    empareje dirección de mercado con dirección del modelo, y esa regla no
    existe en el proyecto. Inventarla aquí seria fabricar una conclusión con
    aspecto de medida. Lo que sí se puede afirmar sin inventar nada es qué hizo
    el precio, y eso es lo que se escribe.
    """
    vivos = [p for p in paneles if p["disponible"] and np.isfinite(p.get("r3m", np.nan))]
    if not vivos:
        return []
    ordenados = sorted(vivos, key=lambda p: -p["r3m"])
    arriba = [p for p in ordenados if p["r3m"] > 1.0][:3]
    abajo = [p for p in ordenados if p["r3m"] < -1.0][-2:]
    out = []
    if arriba:
        out.append(dict(k="Al alza en 3 meses",
                        v=" · ".join(f'{p["titulo"]} {p["r3m"]:+.1f} %'
                                     for p in arriba)))
    if abajo:
        out.append(dict(k="A la baja en 3 meses",
                        v=" · ".join(f'{p["titulo"]} {p["r3m"]:+.1f} %'
                                     for p in reversed(abajo))))
    planos = [p for p in vivos if abs(p["r3m"]) <= 1.0]
    if planos:
        out.append(dict(k="Sin movimiento apreciable",
                        v=" · ".join(p["titulo"] for p in planos[:3])))
    return out[:3]
