# -*- coding: utf-8 -*-
"""El ENTORNO de una fecha: en que mundo pasaba lo que pasaba.

POR QUE EXISTE ESTE MODULO. Los analogos se buscaban solo por el vector de
percentiles de los siete pilares. El percentil normaliza cada serie contra su
propia historia movil de cinco anos, y al hacerlo borra el NIVEL ABSOLUTO: un
apetito de riesgo en el percentil 67 con la tasa real en -1% y el balance de la
Fed creciendo NO es el mismo mundo que un percentil 67 con la tasa real en
+2,4% y la inflacion en 3,3%. La primera distancia mide si el mercado se
COMPORTA parecido; sin la segunda, se confunde con que el mundo SEA parecido.

Aqui se calcula la segunda: media docena de variables en nivel absoluto,
estandarizadas sobre toda la historia disponible -- no sobre ventana movil,
que es justo lo que borraria el nivel otra vez.

UNA PRECISION SOBRE LA ESTANDARIZACION. "Toda la historia disponible" se
entiende siempre HASTA LA FECHA DEL SNAPSHOT, nunca hasta hoy. Con la media y
la desviacion de la muestra completa, el snapshot de 2008 se estandarizaria con
la inflacion de 2022, que en 2008 nadie conocia. La regla del proyecto -- nada
mira al futuro -- se respeta tambien aqui, y la escala sigue siendo fija (no
movil), que era el objetivo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
from snapshot.indicators import hace


# ---------------------------------------------------------- construccion
def construir(panel: pd.DataFrame, macro: pd.DataFrame | None = None,
              bbg: pd.DataFrame | None = None) -> pd.DataFrame:
    """Las variables de entorno, en sus unidades naturales, sobre el indice
    del panel. Lo que no haya disponible sale como columna vacia: el modulo
    no inventa un sustituto, y quien informe dira que falta."""
    idx = panel.index
    M = (macro.reindex(macro.index.union(idx)).ffill().reindex(idx)
         if macro is not None else pd.DataFrame(index=idx))
    B = (bbg.reindex(bbg.index.union(idx)).ffill().reindex(idx)
         if bbg is not None and not bbg.empty else pd.DataFrame(index=idx))

    vacio = pd.Series(np.nan, index=idx)
    out: dict[str, pd.Series] = {}
    for clave, _lab, fuente, sid, _fmt, _u in config.ENV_VARS:
        if fuente == "panel":
            s = panel[sid] if sid in panel.columns else vacio
        elif fuente == "macro":
            s = M[sid] if sid in M.columns else vacio
        elif fuente == "bbg":
            s = B[sid] if sid in B.columns else vacio
        elif fuente == "calc" and sid == "walcl_6m":
            w = M["WALCL"] if "WALCL" in M.columns else vacio
            s = (w / hace(w, 6) - 1.0) * 100.0
        else:
            s = vacio
        out[clave] = pd.Series(s, index=idx).astype(float)
    return pd.DataFrame(out, index=idx)[[c[0] for c in config.ENV_VARS]]


def estandarizar(env: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """z de cada variable con la media y la desviacion de toda la historia
    conocida en `asof`. Escala fija, no movil: el nivel se conserva."""
    ref = env.loc[:asof]
    mu, sd = ref.mean(), ref.std()
    sd = sd.replace(0.0, np.nan)
    return (env - mu) / sd


def disponibles(env: pd.DataFrame, asof: pd.Timestamp) -> tuple[list[str], list[str]]:
    """(variables con dato en `asof`, variables sin dato)."""
    fila = env.loc[asof] if asof in env.index else env.iloc[-1]
    hay = [c for c in env.columns if np.isfinite(fila[c])]
    no = [c for c in env.columns if c not in hay]
    return hay, no


# ------------------------------------------------------------- distancia
def distancia(Z: pd.DataFrame, asof: pd.Timestamp,
              min_vars: int = config.ENV_MIN_VARS) -> pd.Series:
    """Distancia de entorno de cada fecha a `asof`, en desviaciones tipicas.

    Es la raiz del error cuadratico medio entre los dos vectores de z. 0 es el
    mismo mundo; 1, una desviacion tipica de diferencia media por variable; 2 o
    mas, otro mundo. Solo se comparan las variables que existen en AMBAS
    fechas, y si quedan menos de `min_vars` la distancia sale vacia en vez de
    salir barata.
    """
    if Z.empty or asof not in Z.index:
        return pd.Series(np.nan, index=Z.index)
    hoy = Z.loc[asof]
    dif = Z.sub(hoy, axis=1)
    n = dif.notna().sum(axis=1)
    d = np.sqrt((dif ** 2).mean(axis=1))
    return d.where(n >= min_vars)


def descomponer(Z: pd.DataFrame, env: pd.DataFrame,
                asof: pd.Timestamp, dt: pd.Timestamp) -> list[dict]:
    """Variable a variable, cuanto separa a `dt` de `asof`. Ordenado por lo
    que mas separa: es la respuesta a "y por que no es comparable"."""
    if asof not in Z.index or dt not in Z.index:
        return []
    fmt = {c[0]: (c[1], c[4], c[5]) for c in config.ENV_VARS}
    out = []
    for c in Z.columns:
        za, zb = Z.loc[asof, c], Z.loc[dt, c]
        if not (np.isfinite(za) and np.isfinite(zb)):
            continue
        lab, spec, unit = fmt[c]
        out.append(dict(
            clave=c, label=lab, gap=abs(float(za - zb)),
            hoy=float(env.loc[asof, c]), entonces=float(env.loc[dt, c]),
            hoy_txt=f"{spec.format(env.loc[asof, c])}{unit}",
            entonces_txt=f"{spec.format(env.loc[dt, c])}{unit}",
        ))
    out.sort(key=lambda d: -d["gap"])
    return out


def calidad(d: float) -> str:
    if not np.isfinite(d):
        return "sin dato"
    for u, palabra in config.ANALOG_ENV_QUALITY:
        if d <= u:
            return palabra
    return "muy distinto"


# -------------------------------------------------------------- episodios
def episodios(Z: pd.DataFrame, paso: float = config.ANALOG_EPISODE_STEP,
              min_vars: int = config.ENV_MIN_VARS) -> pd.Series:
    """Segmenta la historia en EPISODIOS de entorno.

    Un episodio empieza cuando el entorno se ha alejado mas de `paso`
    desviaciones tipicas del punto en que empezo el episodio en curso. Es una
    segmentacion contigua y determinista: cada fecha pertenece a uno y solo un
    episodio, y dos fechas del mismo episodio son, para lo que aqui importa,
    una sola observacion.

    De aqui salen las dos cosas que hay que reportar: cuantos episodios
    DISTINTOS hay entre los analogos elegidos (cinco fechas del mismo tramo
    son una, no cinco) y cuantos contiene la muestra entera.
    """
    if Z.empty:
        return pd.Series(dtype=int)
    A = Z.to_numpy(dtype=float)
    ids = np.zeros(len(Z), dtype=int)
    ancla, cur = None, 0
    for i in range(len(Z)):
        fila = A[i]
        ok = np.isfinite(fila)
        if ok.sum() < min_vars:
            ids[i] = cur
            continue
        if ancla is None:
            ancla = fila.copy()
            ids[i] = cur
            continue
        comun = ok & np.isfinite(ancla)
        if comun.sum() < min_vars:
            ids[i] = cur
            continue
        d = float(np.sqrt(np.mean((fila[comun] - ancla[comun]) ** 2)))
        if d > paso:
            cur += 1
            ancla = fila.copy()
        ids[i] = cur
    return pd.Series(ids, index=Z.index, dtype=int)


__all__ = ["construir", "estandarizar", "disponibles", "distancia",
           "descomponer", "calidad", "episodios"]
