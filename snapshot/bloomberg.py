# -*- coding: utf-8 -*-
"""Bloomberg como PROVEEDOR de datos, no como validador.

La Terminal es la mejor fuente para varias series que las fuentes gratuitas
dan mal o recortadas -- sobre todo los diferenciales de crédito de alto
rendimiento, que FRED sirve a solo tres años.

Principio de diseño: Bloomberg ENRIQUECE, no es una dependencia dura. Todo lo
que baja se cachea a disco igual que FRED y Yahoo, así que una vez traído, el
snapshot se reproduce en cualquier máquina y sin terminal. Si no hay terminal
ni caché, el resto del proyecto sigue funcionando con su fuente de reserva.

Acceso: la Desktop API escucha en localhost:8194 cuando la Terminal está
abierta y con sesión iniciada. Requiere el paquete `blpapi`. Las noticias y
los blogs (MLIV incluido) NO salen por esta API sin permisos especiales: para
esos titulares, se pegan a mano en docs/registro.json.

POLITICA DE DATOS -- IMPORTANTE
-------------------------------
Bloomberg no limita consultar datos DENTRO de la terminal, pero sí extraerlos
a ficheros o plataformas externas; volcar a CSV es justo eso. Por eso aquí:
  - Solo se extraen las series que las fuentes gratuitas no dan bien (hoy, 2:
    los diferenciales OAS de alto rendimiento y de grado de inversion).
  - La historia completa se baja UNA vez y se cachea. Despues solo se
    actualiza la cola (`update_tail`, ~12 dias), nunca toda la serie.
  - Nada de BQL ni de peticiones masivas.
  - El snapshot LEE la cache; jamas llama a la terminal al generarse. La
    extraccion es siempre un paso manual y deliberado.
"""

from __future__ import annotations

import os
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

HOST, PORT = "localhost", 8194

# Series que se traen de Bloomberg. id_local -> (ticker, campo, descripcion).
# El id_local es el nombre del fichero de cache y de la columna.
SECURITIES: dict[str, tuple[str, str, str]] = {
    "hy_oas": ("LF98OAS Index", "PX_LAST", "Bloomberg US Corporate High Yield OAS (pb/100)"),
    "ig_oas": ("LUACOAS Index", "PX_LAST", "Bloomberg US Agg Corporate OAS (pb/100)"),
    # Valuacion de la bolsa, para la DISTANCIA DE ENTORNO de los analogos (ver
    # snapshot/entorno.py). No entra en el tablero ni vota nada: solo sirve
    # para decir si dos fechas parecidas vivian en el mismo mundo. No hay
    # equivalente gratuito con historia; sin esta serie el entorno se calcula
    # con las otras cinco variables y el snapshot lo declara en sus
    # comprobaciones. Una serie mas, una sola vez, dentro de la politica de
    # arriba.
    "spx_fwd_pe": ("SPX Index", "BEST_PE_RATIO", "S&P 500, PER adelantado (consenso)"),
}


def _cache_path(local_id: str) -> str:
    return os.path.join(CACHE_DIR, f"bbg_{local_id}.csv")


def available() -> bool:
    """True si hay terminal accesible y blpapi instalado."""
    try:
        import blpapi  # noqa: F401
    except Exception:
        return False
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((HOST, PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()


def _fetch_history(tickers: list[tuple[str, str]], start: str, end: str) -> dict[str, pd.Series]:
    """Descarga historia diaria. tickers = [(ticker, campo), ...]."""
    import blpapi

    opts = blpapi.SessionOptions()
    opts.setServerHost(HOST)
    opts.setServerPort(PORT)
    s = blpapi.Session(opts)
    if not s.start():
        raise RuntimeError("no arranca la sesion de Bloomberg")
    try:
        if not s.openService("//blp/refdata"):
            raise RuntimeError("no abre //blp/refdata")
        svc = s.getService("//blp/refdata")
        req = svc.createRequest("HistoricalDataRequest")
        for tk, _f in tickers:
            req.append("securities", tk)
        campos = sorted({f for _t, f in tickers})
        for f in campos:
            req.append("fields", f)
        req.set("periodicitySelection", "DAILY")
        req.set("startDate", start)
        req.set("endDate", end)
        req.set("nonTradingDayFillOption", "NON_TRADING_WEEKDAYS")
        req.set("nonTradingDayFillMethod", "PREVIOUS_VALUE")
        s.sendRequest(req)

        out: dict[str, pd.Series] = {}
        while True:
            ev = s.nextEvent(15000)
            for msg in ev:
                if not msg.hasElement("securityData"):
                    continue
                sd = msg.getElement("securityData")
                tk = sd.getElementAsString("security")
                fd = sd.getElement("fieldData")
                fechas, vals = [], []
                for i in range(fd.numValues()):
                    row = fd.getValueAsElement(i)
                    campo = campos[0]
                    if row.hasElement(campo):
                        fechas.append(pd.Timestamp(row.getElementAsString("date")))
                        vals.append(row.getElementAsFloat(campo))
                out[tk] = pd.Series(vals, index=fechas).sort_index()
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        return out
    finally:
        s.stop()


def refresh(start: str = "2000-01-01", force: bool = False) -> list[str]:
    """Baja de Bloomberg lo declarado en SECURITIES y lo cachea a CSV.

    Devuelve la lista de series realmente actualizadas. Si no hay terminal,
    no toca nada y devuelve lista vacia (el snapshot usara la caché previa o
    la fuente de reserva)."""
    if not available():
        print("  [bloomberg] terminal no accesible; se usa la cache existente")
        return []

    pendientes = {lid: (tk, f) for lid, (tk, f, _d) in SECURITIES.items()
                  if force or not os.path.exists(_cache_path(lid))}
    if not pendientes:
        print("  [bloomberg] cache al dia")
        return []

    print(f"  [bloomberg] DESCARGA COMPLETA de {len(pendientes)} serie(s) a CSV "
          f"(extraccion externa; se hace una sola vez). Para el dia a dia usa "
          f"update_tail().")
    end = time.strftime("%Y%m%d")
    series = _fetch_history([(tk, f) for tk, f in pendientes.values()],
                            start.replace("-", ""), end)
    tk_to_lid = {tk: lid for lid, (tk, _f) in pendientes.items()}

    hechas = []
    for tk, s in series.items():
        lid = tk_to_lid.get(tk)
        if lid is None or s.empty:
            continue
        df = s.rename(lid).to_frame()
        df.index.name = "date"
        df.to_csv(_cache_path(lid))
        hechas.append(lid)
        print(f"  [bloomberg] {lid} <- {tk}: {len(s)} obs, "
              f"{s.index.min().date()} a {s.index.max().date()}")
    return hechas


def update_tail(days: int = 12, force: bool = False) -> list[str]:
    """Refresco BARATO: solo trae la cola reciente de las series ya cacheadas
    y la pega. Pensado para el uso diario, para no gastar datos de Bloomberg
    volviendo a bajar toda la historia.

    Bloomberg cobra por volumen de datos: una historia diaria completa se baja
    UNA vez (refresh) y a partir de ahi solo se actualizan los ultimos dias.
    """
    if not available():
        return []
    existentes = {lid: (tk, f) for lid, (tk, f, _d) in SECURITIES.items()
                  if os.path.exists(_cache_path(lid))}
    if not existentes:
        return []

    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y%m%d")
    end = time.strftime("%Y%m%d")
    series = _fetch_history([(tk, f) for tk, f in existentes.values()], start, end)
    tk_to_lid = {tk: lid for lid, (tk, _f) in existentes.items()}

    hechas = []
    for tk, s in series.items():
        lid = tk_to_lid.get(tk)
        if lid is None or s.empty:
            continue
        viejo = load(lid)
        junto = pd.concat([viejo, s.rename(lid)])
        junto = junto[~junto.index.duplicated(keep="last")].sort_index()
        df = junto.to_frame()
        df.index.name = "date"
        df.to_csv(_cache_path(lid))
        hechas.append(lid)
    return hechas


def load(local_id: str) -> pd.Series:
    """Serie cacheada de Bloomberg, o serie vacia si no existe."""
    path = _cache_path(local_id)
    if not os.path.exists(path):
        return pd.Series(dtype=float, name=local_id)
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.iloc[:, 0].rename(local_id).sort_index()


def load_all() -> pd.DataFrame:
    """Todas las series cacheadas de Bloomberg, en un DataFrame diario."""
    cols = {lid: load(lid) for lid in SECURITIES}
    cols = {k: v for k, v in cols.items() if not v.empty}
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def live(tickers: dict[str, str]) -> pd.DataFrame:
    """Instantanea en directo (para cotejar, no para el snapshot).

    tickers = {etiqueta: 'TICKER Index'}. Devuelve valor y nombre. Solo para
    uso interactivo; el snapshot nunca depende de esto."""
    if not available():
        return pd.DataFrame()
    import blpapi
    opts = blpapi.SessionOptions()
    opts.setServerHost(HOST)
    opts.setServerPort(PORT)
    s = blpapi.Session(opts)
    s.start()
    try:
        s.openService("//blp/refdata")
        svc = s.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")
        for tk in tickers.values():
            req.append("securities", tk)
        for f in ("PX_LAST", "NAME"):
            req.append("fields", f)
        s.sendRequest(req)
        rows = {}
        inv = {v: k for k, v in tickers.items()}
        while True:
            ev = s.nextEvent(8000)
            for msg in ev:
                if not msg.hasElement("securityData"):
                    continue
                sd = msg.getElement("securityData")
                for i in range(sd.numValues()):
                    e = sd.getValueAsElement(i)
                    tk = e.getElementAsString("security")
                    fd = e.getElement("fieldData")
                    px = fd.getElementAsFloat("PX_LAST") if fd.hasElement("PX_LAST") else float("nan")
                    rows[inv.get(tk, tk)] = px
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        return pd.Series(rows, name="PX_LAST").to_frame()
    finally:
        s.stop()


__all__ = ["available", "refresh", "load", "load_all", "live", "SECURITIES"]
