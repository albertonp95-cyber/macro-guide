# -*- coding: utf-8 -*-
"""Cuantas senales INDEPENDIENTES hay detras de los indicadores.

EL PROBLEMA. Contar 42 indicadores como 42 votos es contar varias veces la
misma cosa. El VIX, el VIX frente a su media, la volatilidad realizada y la
caida desde maximos son, en buena medida, una sola senal repetida cuatro
veces. Y un pilar con mas filas pesa mas solo por tener mas filas: "21 a favor
y 9 en contra" suena a mayoria holgada cuando puede ser una senal contra otra.

QUE HACE ESTE MODULO. Agrupa los indicadores en GRUPOS por correlacion sobre
sus percentiles, en ventana larga, y a partir de ahi cuenta: un grupo, una voz.
Dentro de un grupo, el voto es el de la mayoria de sus miembros, con un peso
igual a su grado de acuerdo interno (cuatro de cuatro pesa 1; tres de cuatro,
0,5). Asi, cuatro filas que dicen lo mismo suman una sola voz, y una cesta
internamente dividida pesa menos que una unanime.

POR QUE CONTAR GRUPOS Y NO DIMENSIONES. La primera version media la
informacion efectiva con la razon de participacion de los valores propios de la
matriz de correlacion. Como medida de cuanta informacion DISTINTA hay es
correcta, pero es ciega a la DIRECCION, y al comparar los dos bandos de una
votacion daba resultados absurdos: en septiembre de 2008, dieciseis indicadores
pidiendo subir calidad de credito -- todos muy correlacionados, o sea poca
dimension -- "perdian" contra cuatro indicadores diversos que pedian lo
contrario. Dieciseis observaciones que confirman una senal valen mas que una
sola, no menos. Para votar hay que contar voces; la dimension mide otra cosa.

QUE NO HACE. No toca el tablero. Ni los pilares, ni los ejes, ni el voto por
clase de activo cambian por esto. Es informacion para quien lee -- "estos 21
votos son en realidad como seis" -- no una correccion aplicada por detras.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config


# ------------------------------------------------------------ correlacion
def matriz(pct: pd.DataFrame, asof: pd.Timestamp,
           win: int = config.CLUSTER_WINDOW,
           minobs: int = config.CLUSTER_MINOBS) -> pd.DataFrame | None:
    """Correlacion entre percentiles en la ventana larga que acaba en `asof`.

    Sobre los percentiles y no sobre los valores crudos: es en el percentil
    donde vive el voto, y compara indicadores en unidades distintas (puntos
    basicos, porcentajes, indices) sin que la escala mande.
    """
    sub = pct.loc[:asof].tail(win)
    cols = [c for c in sub.columns if int(sub[c].notna().sum()) >= minobs]
    if len(cols) < 2:
        return None
    C = sub[cols].corr(min_periods=minobs)
    return C.astype(float)


def _agrupar_media(D: np.ndarray, corte: float) -> list[list[int]]:
    """Agrupamiento jerarquico por enlace medio, cortado en `corte`.

    Escrito a mano y no con scipy para no anadir una dependencia por veinte
    lineas: con 42 columnas el coste es irrelevante.
    """
    grupos = [[i] for i in range(D.shape[0])]
    while len(grupos) > 1:
        mejor = None
        for a in range(len(grupos)):
            for b in range(a + 1, len(grupos)):
                d = float(D[np.ix_(grupos[a], grupos[b])].mean())
                if mejor is None or d < mejor[0]:
                    mejor = (d, a, b)
        if mejor is None or mejor[0] > corte:
            break
        _d, a, b = mejor
        grupos[a] = grupos[a] + grupos[b]
        del grupos[b]
    return grupos


def clusters(C: pd.DataFrame | None,
             rho: float = config.CLUSTER_RHO) -> dict[str, int]:
    """Indicador -> id de cluster. Dos indicadores caen juntos cuando su
    correlacion media en valor absoluto llega a `rho`. En valor absoluto
    porque dos series opuestas -- la caida desde maximos y el VIX -- son la
    misma informacion con el signo cambiado, no dos noticias."""
    if C is None or C.empty:
        return {}
    A = C.to_numpy(dtype=float)
    D = 1.0 - np.abs(A)
    D = np.where(np.isfinite(D), D, 1.0)
    np.fill_diagonal(D, 0.0)
    grupos = _agrupar_media(D, 1.0 - rho)
    fuera = {}
    for cid, g in enumerate(grupos):
        for i in g:
            fuera[str(C.columns[i])] = cid
    return fuera


# ------------------------------------------------------- senales efectivas
def _cid(grupos: dict[str, int], key: str):
    """Grupo al que pertenece un indicador. Si no se pudo agrupar, va solo."""
    return grupos.get(key, f"solo:{key}")


def n_grupos(keys, grupos: dict[str, int]) -> int:
    """Cuantos grupos DISTINTOS representan estos indicadores."""
    return len({_cid(grupos, k) for k in dict.fromkeys(keys)})


def _tally(votos: dict, grupos: dict[str, int]) -> tuple[float, float, float]:
    """Reparte los grupos en (a favor, en contra, neutrales).

    `votos` es {clave: +1 / -1 / 0}. Cada grupo aporta como mucho una voz, y la
    aporta al lado de su mayoria interna con peso igual a su grado de acuerdo:
    un grupo unanime pesa 1; uno partido tres a uno, 0,5; uno partido por la
    mitad se va entero a neutral. Las tres cifras SUMAN al numero de grupos,
    que es lo que permite dibujarlas como un reparto y no como dos numeros
    sueltos.
    """
    porc: dict = {}
    for k, v in votos.items():
        porc.setdefault(_cid(grupos, k), []).append(v)
    vf = vc = vz = 0.0
    for vs in porc.values():
        s, n = sum(vs), len(vs)
        w = abs(s) / n
        if s > 0:
            vf += w
        elif s < 0:
            vc += w
        vz += 1.0 - w
    return vf, vc, vz


def voto_grupos(filas: list[dict], ck: str,
                grupos: dict[str, int]) -> tuple[float, float]:
    """Voces a favor y en contra de una clase de activo, contadas por grupo."""
    votos = {f["key"]: f["votos"].get(ck, 0) for f in filas
             if f["votos"].get(ck, 0) != 0}
    vf, vc, _vz = _tally(votos, grupos)
    return vf, vc


def resumen(filas: list[dict], grupos: dict[str, int],
            C: pd.DataFrame | None) -> dict:
    """Recuento crudo y efectivo de la lectura de riesgo (favorable / adverso).

    El titular usa el efectivo; el crudo se conserva entero como detalle.
    """
    def _k(lect):
        return [f["key"] for f in filas if f["lectura"] == lect]

    fav, adv, neu = _k("favorable"), _k("adverso"), _k("neutral")
    todos = [f["key"] for f in filas if f["lectura"] != "sin dato"]
    peso = {"favorable": 1, "adverso": -1, "neutral": 0}
    votos = {f["key"]: peso[f["lectura"]] for f in filas
             if f["lectura"] in peso}
    e_f, e_c, e_z = _tally(votos, grupos)
    mayor = max(([k for k in todos if _cid(grupos, k) == c]
                 for c in {_cid(grupos, k) for k in todos}), key=len, default=[])
    return dict(
        n_favor=len(fav), n_contra=len(adv), n_neutral=len(neu), n_total=len(todos),
        e_favor=e_f, e_contra=e_c, e_neutral=e_z,
        e_total=float(n_grupos(todos, grupos)),
        n_clusters=n_grupos(todos, grupos),
        grupo_mayor=[config.INDICATOR_BY_KEY[k]["label"] for k in mayor],
        disponible=C is not None,
    )


def por_pilar(filas: list[dict], grupos: dict[str, int]) -> dict[str, dict]:
    """Indicadores y grupos independientes de cada pilar.

    Ojo al sumarlos: no dan el total. Dos pilares pueden compartir grupo -- el
    credito y parte de la liquidez se mueven juntos -- y ese grupo compartido no
    pertenece a ninguno de los dos en exclusiva.
    """
    out = {}
    for pilar, keys in config.PILLAR_KEYS.items():
        con_dato = [f["key"] for f in filas
                    if f["key"] in keys and np.isfinite(f["pct"])]
        out[pilar] = dict(n=len(con_dato),
                          e=float(n_grupos(con_dato, grupos)) if con_dato else 0.0)
    return out


# ------------------------------------------------- comprobacion permanente
def redundancia_alta(filas: list[dict], grupos: dict[str, int]) -> list[dict]:
    """Pilares que mandan en el recuento de una clase de activo sin aportar
    informacion nueva: mas del 40% de los indicadores que votan esa clase y
    menos del 20% de sus grupos independientes.

    La aportacion de un pilar se mide como lo que se PERDERIA quitandolo: los
    grupos que votan esa clase menos los que quedarian sin sus filas. Es la
    pregunta que interesa -- si quito estas cuatro filas, cuantas voces pierdo
    de verdad.

    Es la forma de que se vea cuando una "mayoria" es un solo pilar hablando
    varias veces. Se avisa; no se corrige nada.
    """
    if not grupos:
        return []
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    avisos = []
    for ck, meta in config.ASSET_CLASSES.items():
        keys = [f["key"] for f in filas if f["votos"].get(ck, 0) != 0]
        if len(keys) < 5:
            continue
        g_tot = n_grupos(keys, grupos)
        if g_tot <= 0:
            continue
        for pilar in config.PILLARS:
            suyos = [k for k in keys if pilar_de.get(k) == pilar]
            resto = [k for k in keys if k not in suyos]
            if not suyos or not resto:
                continue
            share_n = len(suyos) / len(keys)
            aporte = max(0, g_tot - n_grupos(resto, grupos))
            share_e = aporte / g_tot
            if share_n > config.REDUND_SHARE_IND and share_e < config.REDUND_SHARE_SIG:
                avisos.append(dict(
                    clase=ck, clase_label=meta["label"],
                    pilar=pilar, pilar_label=config.PILLARS[pilar]["label"],
                    n=len(suyos), n_total=len(keys),
                    share_n=100.0 * share_n, share_e=100.0 * share_e,
                    aporte=aporte, e_total=g_tot,
                ))
    avisos.sort(key=lambda d: -(d["share_n"] - d["share_e"]))
    return avisos


__all__ = ["matriz", "clusters", "n_grupos", "voto_grupos", "resumen",
           "por_pilar", "redundancia_alta"]
