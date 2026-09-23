# -*- coding: utf-8 -*-
"""Construccion del panel de indicadores.

Cada indicador es una SERIE DIARIA EN SUS PROPIAS UNIDADES. Aqui no se
normaliza, no se puntua y no se agrega nada: eso vive en scoring.py. La
separacion es deliberada, para poder mirar el dato crudo sin pasar por
ninguna transformacion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

# Ventanas MOVILES, en dias habiles. Una ventana si se cuenta en dias de
# mercado; una comparacion "hace N meses" no (ver `hace`).
BD_3M = 63
BD_3Y = 756


# ------------------------------------------------------------- utilidades
def hace(s: pd.Series, meses: int) -> pd.Series:
    """Valor de la serie `meses` meses antes de cada fecha, por CALENDARIO.

    No se puede usar un desplazamiento por filas. Una serie mensual arrastrada
    a rejilla diaria es escalonada, asi que 252 filas atras no caen doce meses
    atras; y ademas hay huecos reales -- al IPC le falta octubre de 2025 --
    que descuadran cualquier conteo posicional. Con `shift(252)` el IPC
    interanual de julio de 2026 salia 2,95% cuando es 3,54%.
    """
    prev = s.shift(freq=pd.DateOffset(months=meses))
    prev = prev[~prev.index.duplicated(keep="last")]
    return prev.reindex(s.index, method="ffill")


def _ret(s: pd.Series, meses: int) -> pd.Series:
    """Rentabilidad simple a `meses` meses, en porcentaje."""
    return (s / hace(s, meses) - 1.0) * 100.0


def _yoy(s: pd.Series) -> pd.Series:
    return _ret(s, 12)


def _ann_3m(s: pd.Series) -> pd.Series:
    """Ritmo de 3 meses anualizado, en porcentaje."""
    return ((s / hace(s, 3)) ** 4 - 1.0) * 100.0


def _col(df: pd.DataFrame, name: str, idx: pd.Index) -> pd.Series:
    if name in df.columns:
        return df[name].reindex(idx)
    return pd.Series(np.nan, index=idx, name=name)


# ------------------------------------------------------------ panel diario
def build_panel(macro: pd.DataFrame, px: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DataFrame con una columna por indicador de config."""
    end = max(macro.index.max(), px.index.max())
    idx = pd.date_range(config.DATA_START, end, freq="B")

    M = macro.reindex(macro.index.union(idx)).ffill().reindex(idx)
    P = px.reindex(px.index.union(idx)).ffill().reindex(idx)

    m = lambda k: _col(M, k, idx)   # noqa: E731
    p = lambda k: _col(P, k, idx)   # noqa: E731

    out: dict[str, pd.Series] = {}

    # ------------------------------------------------------------ credito
    # Diferenciales OAS reales de Bloomberg (cacheados). Si no hay cache ni
    # terminal, se cae a Moody's Baa/Aaa como proxy consistente -- distinta
    # escala, pero una sola serie en toda la historia, asi que el percentil
    # sigue siendo valido.
    from snapshot import bloomberg as _bb
    bbg = _bb.load_all()
    if not bbg.empty:
        BB = bbg.reindex(bbg.index.union(idx)).ffill().reindex(idx)
        hy = BB["hy_oas"] if "hy_oas" in BB else pd.Series(np.nan, index=idx)
        ig = BB["ig_oas"] if "ig_oas" in BB else pd.Series(np.nan, index=idx)
    else:
        hy, ig = m("BAA10Y"), m("AAA10Y")   # proxy de reserva
    out["hy_oas"] = hy
    out["ig_oas"] = ig
    out["hy_minus_ig"] = hy - ig
    out["nfci"] = m("NFCI")
    out["hyg_vs_ief"] = _ret(p("HYG"), 3) - _ret(p("IEF"), 3)

    # -------------------------------------------------------- volatilidad
    vix = p("^VIX")
    spy = p("SPY")
    spy_ret = spy.pct_change()
    rvol = spy_ret.rolling(60, min_periods=40).std() * np.sqrt(252) * 100.0
    out["vix"] = vix
    out["vix_vs_3m"] = (vix / vix.rolling(BD_3M, min_periods=40).mean() - 1.0) * 100.0
    out["rvol_spx"] = rvol
    out["dd_spx"] = (spy / spy.cummax() - 1.0) * 100.0
    out["gold_vs_spx"] = _ret(p("GLD"), 3) - _ret(spy, 3)

    # ---------------------------------------------------------- tendencia
    basket = [t for t in config.RISK_BASKET if t in P.columns]
    B = P[basket]
    sma200 = B.rolling(200, min_periods=150).mean()
    above = (B > sma200).astype(float).where(B.notna() & sma200.notna())
    out["breadth_200"] = above.mean(axis=1) * 100.0

    out["spx_12m"] = _ret(spy, 12)
    out["risk_6m"] = B.apply(lambda c: _ret(c, 6)).median(axis=1)
    out["spx_vs_200"] = (spy / spy.rolling(200, min_periods=150).mean() - 1.0) * 100.0
    out["bonds_vs_spx"] = _ret(p("TLT"), 3) - _ret(spy, 3)

    # --------------------------------------------------- posicionamiento
    out["spx_ext_3y"] = (spy / spy.rolling(BD_3Y, min_periods=500).mean() - 1.0) * 100.0
    out["eq_vs_bonds"] = _ret(spy, 36) - _ret(p("IEF"), 36)
    out["eq_vs_gold"] = _ret(spy, 36) - _ret(p("GLD"), 36)
    out["credit_comp"] = hy / rvol.replace(0.0, np.nan)
    # Oro sobre el futuro (GC=F) y no sobre GLD: el ETF no cotiza hasta
    # finales de 2004 y con el no habria percentil a 5 anos en 2008.
    oro = p("GC=F")
    out["gold_12m"] = _ret(oro, 12)
    out["gold_ext_200"] = (oro / oro.rolling(200, min_periods=150).mean() - 1.0) * 100.0

    # -------------------------------------------------------- crecimiento
    out["claims_4w"] = (m("ICSA") / 1000.0).rolling(20, min_periods=5).mean()
    out["sahm"] = m("SAHMREALTIME")
    out["payems_3m"] = _ann_3m(m("PAYEMS"))
    out["indpro_yoy"] = _yoy(m("INDPRO"))
    out["permits_yoy"] = _yoy(m("PERMIT"))
    out["retail_yoy"] = _yoy(m("RRSFS"))
    out["umcsent"] = m("UMCSENT")
    out["copper_gold"] = _ret(p("HG=F"), 6) - _ret(p("GC=F"), 6)
    out["cyc_vs_def"] = _ret(p("XLY"), 3) - _ret(p("XLP"), 3)
    out["curve_10y3m"] = m("T10Y3M")

    # ---------------------------------------------------------- inflacion
    cpi = m("CPIAUCSL")
    out["cpi_yoy"] = _yoy(cpi)
    out["cpi_3m"] = _ann_3m(cpi)
    out["core_pce"] = _yoy(m("PCEPILFE"))
    out["ppi_yoy"] = _yoy(m("PPIACO"))
    out["be5y"] = m("T5YIE")
    out["be10y"] = m("T10YIE")

    # ----------------------------------------------------------- liquidez
    out["real_10y"] = m("DFII10")
    out["dgs2"] = m("DGS2")
    dff = m("DFF")
    out["dff_12m"] = dff - hace(dff, 12)
    # Ya homogeneizado a miles de millones de dolares en data.load_macro.
    netliq = m("WALCL") - m("RRPONTSYD") - m("WTREGEN")
    out["netliq_3m"] = netliq - hace(netliq, 3)
    out["dollar_3m"] = _ret(m("DTWEXBGS"), 3)

    panel = pd.DataFrame(out, index=idx)
    # Orden estable, el de config, y aviso si algo se ha quedado sin definir.
    missing = [d["key"] for d in config.INDICATORS if d["key"] not in panel.columns]
    if missing:
        raise KeyError(f"indicadores declarados en config y no construidos: {missing}")
    return panel[[d["key"] for d in config.INDICATORS]]


__all__ = ["build_panel"]
