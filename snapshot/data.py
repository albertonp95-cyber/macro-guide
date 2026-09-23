# -*- coding: utf-8 -*-
"""Descarga y cache propias. Este modulo NO lee ni escribe nada del proyecto
del modelo de ETFs: tiene su propia carpeta data/cache."""

from __future__ import annotations

import os
import time
import urllib.request

import pandas as pd

import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_TTL_HOURS = 12.0
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def _fresh(path: str, ttl_hours: float = CACHE_TTL_HOURS) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl_hours * 3600


# ------------------------------------------------------------------- FRED
def fred_series(series_id: str, force: bool = False) -> pd.Series:
    """Serie de FRED indexada por su fecha de REFERENCIA (sin retardo aun)."""
    path = os.path.join(CACHE_DIR, f"fred_{series_id}.csv")
    if force or not _fresh(path):
        try:
            req = urllib.request.Request(
                FRED_URL.format(sid=series_id),
                headers={"User-Agent": "macro-snapshot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=40) as r:
                txt = r.read().decode("utf-8", errors="replace")
            if "," in txt.splitlines()[0]:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt)
        except Exception as exc:                       # sin red -> usar cache
            print(f"  [aviso] FRED {series_id}: {exc}")
    if not os.path.exists(path):
        return pd.Series(dtype=float, name=series_id)

    raw = pd.read_csv(path)
    date_col, val_col = raw.columns[0], raw.columns[1]
    s = pd.Series(
        pd.to_numeric(raw[val_col], errors="coerce").to_numpy(),
        index=pd.to_datetime(raw[date_col], errors="coerce"),
        name=series_id,
    ).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def load_macro(force: bool = False) -> tuple[pd.DataFrame, dict[str, pd.Timestamp]]:
    """Series de FRED con el retardo de publicacion aplicado, en rejilla
    diaria de dias habiles.

    Devuelve tambien la fecha de referencia del ultimo dato de cada serie,
    que es lo que hace falta para informar de la frescura sin mentir: una
    serie mensual arrastrada 40 dias sigue siendo un dato de hace 40 dias.
    """
    out, last_ref = {}, {}
    for sid, (_label, freq, lag) in config.FRED_SERIES.items():
        s = fred_series(sid, force=force)
        if s.empty:
            print(f"  [aviso] serie vacia: {sid}")
            continue
        last_ref[sid] = s.index.max()
        # FRED fecha las mensuales el dia 1 del mes de REFERENCIA y los
        # retardos se cuentan desde el FIN del periodo: hay que llevar la
        # fecha al cierre de mes ANTES de sumar el retardo. Las semanales y
        # diarias ya vienen fechadas al cierre de su periodo.
        if freq == "M":
            s.index = s.index + pd.offsets.MonthEnd(0)
        s.index = s.index + pd.Timedelta(days=int(lag))
        scale = config.FRED_SCALE_TO_BILLIONS.get(sid)
        if scale is not None:
            s = s * scale
        out[sid] = s

    df = pd.DataFrame(out).sort_index()
    start = max(df.index.min(), pd.Timestamp(config.DATA_START))
    idx = pd.date_range(start, pd.Timestamp.today().normalize(), freq="B")
    df = df.reindex(df.index.union(idx)).ffill().reindex(idx)
    return df, last_ref


# ----------------------------------------------------------------- precios
def load_prices(force: bool = False) -> pd.DataFrame:
    """Cierres ajustados por dividendos y splits, en dias habiles."""
    import yfinance as yf

    tickers = config.TICKERS
    path = os.path.join(CACHE_DIR, "prices.csv")

    px = None
    if not force and _fresh(path):
        cached = pd.read_csv(path, index_col=0, parse_dates=True)
        if set(tickers).issubset(cached.columns):
            px = cached[tickers].sort_index()

    if px is None:
        print(f"  descargando {len(tickers)} series de Yahoo Finance...")
        raw = yf.download(
            tickers, start=config.DATA_START, auto_adjust=True,
            progress=False, threads=True, group_by="column",
        )
        px = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        px = px.reindex(columns=tickers)
        missing = [c for c in px.columns if px[c].notna().sum() == 0]
        if missing:
            print(f"  [aviso] sin datos: {missing}")
        px = px.dropna(how="all").sort_index()
        px.to_csv(path)

    idx = pd.date_range(px.index.min(), px.index.max(), freq="B")
    return px.reindex(idx).ffill()


__all__ = ["fred_series", "load_macro", "load_prices", "CACHE_DIR"]
