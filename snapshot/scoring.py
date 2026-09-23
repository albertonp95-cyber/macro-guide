# -*- coding: utf-8 -*-
"""Percentiles, orientacion, pilares y ejes.

Tres convenios, y conviene tenerlos presentes al leer cualquier numero:

1. PERCENTIL. Todo percentil es de ventana movil y hacia atras. El percentil
   de una fecha solo usa datos anteriores a esa fecha. Por eso el snapshot de
   2008 se puede generar sin contaminacion: no sabe nada de 2009.

2. ORIENTACION. Cada indicador lleva un signo en config. El signo no cambia
   el valor ni su percentil: solo produce un "percentil orientado" en el que
   ALTO = FAVORABLE para activos de riesgo. Es el unico convenio que permite
   comparar pilares entre si, que es de donde salen las divergencias.

3. AGREGACION. Los pilares son la media de sus indicadores orientados, y los
   ejes la media ponderada de sus pilares. Pesos iguales dentro de cada
   pilar: no hay aqui ninguna calibracion, y fingir precision en los pesos
   seria fingir un modelo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------- percentiles
def trailing_pct(panel: pd.DataFrame,
                 win: int = config.PCT_WINDOW,
                 minp: int = config.PCT_MINP) -> pd.DataFrame:
    """Percentil (0-100) de cada valor dentro de su ventana movil hacia atras."""
    return panel.rolling(win, min_periods=minp).rank(pct=True) * 100.0


def expanding_pct(s: pd.Series, minp: int = config.HIST_MINP) -> pd.Series:
    """Percentil historico: toda la historia disponible hasta esa fecha."""
    return s.expanding(min_periods=minp).rank(pct=True) * 100.0


def orient(pct: pd.DataFrame) -> pd.DataFrame:
    """Percentil orientado: alto = favorable para activos de riesgo."""
    out = pct.copy()
    for d in config.INDICATORS:
        if d["sign"] < 0 and d["key"] in out.columns:
            out[d["key"]] = 100.0 - out[d["key"]]
    return out


# ------------------------------------------------------------ agregacion
def _wmean(df: pd.DataFrame, weights: dict[str, float], min_cov: float) -> pd.Series:
    """Media ponderada tolerante a huecos, con exigencia de cobertura.

    Si falta tanto dato que lo que queda ya no representa al conjunto, el
    resultado es NaN. Preferimos una casilla vacia a un numero que parece
    informado y no lo esta.
    """
    cols = [c for c in weights if c in df.columns]
    if not cols:
        return pd.Series(np.nan, index=df.index)
    W = pd.Series({c: weights[c] for c in cols}, dtype=float)
    sub = df[cols]
    mask = sub.notna()
    wsum = mask.mul(W, axis=1).sum(axis=1)
    num = sub.fillna(0.0).mul(W, axis=1).sum(axis=1)
    total = float(W.sum())
    res = num / wsum.replace(0.0, np.nan)
    return res.where(wsum >= min_cov * total)


def pillar_scores(oriented: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for pillar, keys in config.PILLAR_KEYS.items():
        w = {k: 1.0 for k in keys}
        out[pillar] = _wmean(oriented, w, config.MIN_PILLAR_COVERAGE)
    return pd.DataFrame(out, index=oriented.index)[list(config.PILLARS)]


def axis_scores(pillars: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for axis, spec in config.AXES.items():
        out[axis] = _wmean(pillars, spec["weights"], 0.50)
    return pd.DataFrame(out, index=pillars.index)[list(config.AXES)]


# ---------------------------------------------------------------- estado
def band_label(p: float) -> str | None:
    if p is None or not np.isfinite(p):
        return None
    for lo, hi, name in config.STATE_BANDS:
        if lo <= p < hi:
            return name
    # Fuera de rango: se ancla al extremo QUE CORRESPONDE. Devolver siempre la
    # ultima banda hacia que un percentil por DEBAJO del suelo (p.ej. -0.1, al
    # extrapolar hacia abajo) se etiquetara "euforia" -- el sentido invertido.
    return (config.STATE_BANDS[0][2] if p < config.STATE_BANDS[0][0]
            else config.STATE_BANDS[-1][2])


def band_index(p: float) -> int | None:
    if p is None or not np.isfinite(p):
        return None
    for i, (lo, hi, _name) in enumerate(config.STATE_BANDS):
        if lo <= p < hi:
            return i
    return len(config.STATE_BANDS) - 1


def state_series(hist_pct: pd.Series,
                 persistence: int = config.STATE_PERSISTENCE,
                 hysteresis: float = config.STATE_HYSTERESIS) -> pd.Series:
    """Estado con histeresis de nivel y confirmacion ASIMETRICA en el tiempo.

    Para salir del estado actual hay que rebasar su limite por `hysteresis`
    puntos de percentil. Ademas, la MEJORA tiene que aguantar `persistence`
    dias habiles; el DETERIORO se reconoce el mismo dia.

    La simetria seria mas elegante y estaria mal. Con confirmacion en ambos
    sentidos, el 15 de septiembre de 2008 -- con el eje de riesgo en el
    percentil 1,5 de su historia -- este documento seguia diciendo "tension"
    porque el estres todavia no habia cumplido los cinco dias. Un panel que
    tarda una semana en admitir una crisis no sirve para nada. Al estres se
    reacciona; la calma se confirma.
    """
    out = [e for e, _c, _n in _recorrido(hist_pct, persistence, hysteresis)]
    bands = config.STATE_BANDS
    return pd.Series([bands[i][2] if i is not None else None for i in out],
                     index=hist_pct.index, dtype=object)


def _recorrido(hist_pct, persistence: int, hysteresis: float):
    """El recorrido de la maquina de estados, fecha a fecha.

    UNA sola implementacion. La serie publicada y el detalle de la transicion
    a medio confirmar salen de aqui: si el detalle se calculara aparte, los dos
    podrian discrepar, que es justo lo que no puede pasar con el regimen.
    Devuelve, por fecha, (estado, candidato, dias_del_candidato).
    """
    bands = config.STATE_BANDS
    cur, cand, cnt = None, None, 0
    for p in hist_pct:
        b = band_index(p)
        if b is None:
            yield cur, cand, cnt
            continue
        if cur is None:
            cur, cand, cnt = b, None, 0
        elif b == cur:
            cand, cnt = None, 0
        else:
            lo, hi, _ = bands[cur]
            if b < cur and p < lo - hysteresis:          # empeora: sin esperas
                cur, cand, cnt = b, None, 0
            elif b > cur and p > hi + hysteresis:        # mejora: se confirma
                cnt = cnt + 1 if cand == b else 1
                cand = b
                if cnt >= persistence:
                    cur, cand, cnt = b, None, 0
            else:
                cand, cnt = None, 0
        yield cur, cand, cnt


def estado_detalle(hist_pct: pd.Series,
                   persistence: int = config.STATE_PERSISTENCE,
                   hysteresis: float = config.STATE_HYSTERESIS) -> dict:
    """El regimen de la ultima fecha, y la transicion pendiente si la hay.

    El regimen publicado lleva histeresis: para subir de banda hay que rebasar
    el borde por `hysteresis` puntos y aguantar `persistence` dias. Eso hace que
    la ETIQUETA y la BANDA DEL PERCENTIL puedan discrepar legitimamente durante
    unos dias, y un documento que imprima los dos juntos sin decirlo se
    contradice a si mismo. Esta funcion es la unica fuente de esa explicacion.
    """
    est = cand = None
    dias = 0
    for est, cand, dias in _recorrido(hist_pct, persistence, hysteresis):
        pass
    p = float(hist_pct.iloc[-1]) if len(hist_pct) else float("nan")
    bandas = config.STATE_BANDS
    etiqueta = bandas[est][2] if est is not None else None
    banda_pct = band_label(p)
    # Sin candidato vivo, un deterioro tambien puede estar «entre bandas»: el
    # percentil ya cayo pero no lo bastante para romper la histeresis.
    destino = bandas[cand][2] if cand is not None else (
        banda_pct if banda_pct != etiqueta else None)
    return dict(
        etiqueta=etiqueta, pct=p, banda_pct=banda_pct,
        coincide=(banda_pct == etiqueta),
        destino=destino,
        dias=int(dias) if cand is not None else 0,
        dias_requeridos=int(persistence),
        confirmando=cand is not None,
        histeresis=float(hysteresis),
    )


def run_start(s: pd.Series, upto: pd.Timestamp):
    """Fecha en que empezo la racha actual de `s` (valor constante) y su
    longitud en dias habiles. Devuelve (None, 0) si no hay dato."""
    sub = s.loc[:upto].dropna()
    if sub.empty:
        return None, 0
    last = sub.iloc[-1]
    neq = sub.ne(last)
    if not neq.any():
        return sub.index[0], len(sub)
    start_pos = int(np.argmax(neq.to_numpy()[::-1]))
    # posicion (desde el final) del ultimo valor distinto
    idx_last_diff = len(sub) - 1 - start_pos
    return sub.index[idx_last_diff + 1], len(sub) - idx_last_diff - 1


def bool_run_start(s: pd.Series, upto: pd.Timestamp):
    """Fecha en que empezo la racha actual de True. (None, 0) si hoy es False."""
    sub = s.loc[:upto].dropna()
    if sub.empty or not bool(sub.iloc[-1]):
        return None, 0
    return run_start(sub, upto)


# ---------------------------------------------------------------- deltas
def _media_ventana(sub: pd.Series, fecha, dias: int) -> float:
    """Media de la serie en una ventana de `dias` dias habiles CENTRADA en la
    observacion mas cercana a `fecha`.

    Es el punto de comparacion estable de los deltas. Un solo cierre a `fecha`
    puede caerse de la ventana de un dia para otro; la media de cinco no da
    esos saltos. `sub` ya viene recortada a <= upto, asi que la ventana (unos
    dos dias a cada lado de una fecha que esta meses atras) no mira al futuro.
    """
    if sub.empty:
        return np.nan
    pos = sub.index.get_indexer([pd.Timestamp(fecha)], method="nearest")
    p = int(pos[0])
    if p < 0:
        return np.nan
    lado = dias // 2
    v = sub.iloc[max(0, p - lado): p + lado + 1]
    return float(v.mean()) if len(v) else np.nan


def delta(s: pd.Series, meses: int, upto: pd.Timestamp,
          suave_actual: int = 0, ventana_ref: int = config.DELTA_REF_WIN) -> float:
    """Cambio del valor en los ultimos `meses` meses de CALENDARIO.

    Por fecha, no por numero de filas: en una serie mensual arrastrada a
    rejilla diaria, contar filas no cae donde uno cree (ver indicators.hace).

    El punto de comparacion es la MEDIA de `ventana_ref` dias habiles alrededor
    de la fecha de referencia (upto - meses), no un unico cierre: asi el delta
    deja de moverse sin motivo cuando ese cierre sale de la ventana.

    `suave_actual`: si > 1, el extremo ACTUAL tambien se promedia (media de los
    ultimos `suave_actual` dias habiles). Lo usan los agregados -- ejes, pilares,
    puntuacion --; los indicadores sueltos se quedan en su cierre (0)."""
    sub = s.loc[:upto].dropna()
    if sub.empty:
        return np.nan
    a = (float(sub.iloc[-suave_actual:].mean()) if suave_actual and suave_actual > 1
         else float(sub.iloc[-1]))
    antes = pd.Timestamp(upto) - pd.DateOffset(months=meses)
    if sub.loc[:antes].empty:
        return np.nan
    b = _media_ventana(sub, antes, ventana_ref)
    if not (np.isfinite(a) and np.isfinite(b)):
        return np.nan
    return a - b


def nivel(s: pd.Series, upto: pd.Timestamp, suave: int = config.DELTA_ACTUAL_WIN) -> float:
    """Valor ACTUAL suavizado: media de los ultimos `suave` dias habiles. Para
    los agregados que se muestran (ejes, puntuacion), por la misma razon que los
    deltas: un solo cierre salta y el numero de portada no deberia."""
    sub = s.loc[:upto].dropna()
    if sub.empty:
        return np.nan
    return float(sub.iloc[-max(1, suave):].mean())


def delta_series(df, meses: int):
    """Lo mismo que `delta`, pero para TODA la serie de una vez.

    Hace falta para los analogos: comparar trayectorias exige el cambio de cada
    pilar en cada fecha del pasado, no solo en la de hoy. Mismo convenio de
    calendario, y misma precaucion con el indice duplicado que en
    indicators.hace -- desplazar por frecuencia puede pisar fechas.
    """
    prev = df.shift(freq=pd.DateOffset(months=meses))
    prev = prev[~prev.index.duplicated(keep="last")]
    return df - prev.reindex(df.index, method="ffill")


__all__ = [
    "trailing_pct", "expanding_pct", "orient", "pillar_scores", "axis_scores",
    "band_label", "state_series", "run_start", "bool_run_start", "delta",
    "delta_series", "nivel",
]
