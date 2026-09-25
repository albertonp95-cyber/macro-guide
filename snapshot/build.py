# -*- coding: utf-8 -*-
"""Ensamblado del snapshot para una fecha.

Todo lo que sale de aqui es descriptivo. No hay ninguna decision de cartera,
ningun porcentaje de asignacion y ninguna orden. Solo lecturas y el rastro
para poder discutirlas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
from snapshot import (decision, documentos, entorno, historico, scoring,
                      semantica, senales)


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(ts) -> str:
    if ts is None or pd.isna(ts):
        return "sin dato"
    ts = pd.Timestamp(ts)
    return f"{ts.day} de {MESES[ts.month - 1]} de {ts.year}"


def fecha_corta(ts) -> str:
    if ts is None or pd.isna(ts):
        return "—"
    ts = pd.Timestamp(ts)
    return f"{ts.day:02d}/{ts.month:02d}/{ts.year}"


def minus(s: str) -> str:
    """Minuscula SOLO la primera letra. `.lower()` entero convertia «PCE
    subyacente» en «pce subyacente» y «S&P» en «s&p», y eso se lee como una
    errata."""
    return s[0].lower() + s[1:] if s else s


def _fmt(spec: str, unit: str, v) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    s = spec.format(v)
    return f"{s} {unit}".strip() if unit else s


def _duracion(n_bd: int) -> str:
    """Duracion legible a partir de dias habiles."""
    if n_bd <= 0:
        return "—"
    if n_bd == 1:
        return "1 día hábil"
    if n_bd < 15:
        return f"{n_bd} días hábiles"
    sem = round(n_bd / 5.0)
    if sem < 13:
        return "1 semana" if sem == 1 else f"{sem} semanas"
    mes = round(n_bd / 21.0)
    if mes < 24:
        return "1 mes" if mes == 1 else f"{mes} meses"
    return f"{n_bd / 252.0:.1f} años"


def _transicion_txt(t: dict) -> str:
    """La frase que reconcilia la etiqueta del regimen con su percentil.

    Vacia cuando coinciden, que es lo normal. Cuando no, dice POR QUE no, para
    que «neutral · p75» deje de leerse como «p75 es neutral». La escribe el
    estado, no el template: los dos documentos tienen que decir lo mismo.
    """
    if not t or t.get("coincide") or not t.get("destino"):
        return ""
    if t.get("confirmando"):
        faltan = max(0, t["dias_requeridos"] - t["dias"])
        cuantos = ("hoy se confirma" if faltan == 0 else
                   "a falta de 1 día hábil de confirmación" if faltan == 1 else
                   f"a falta de {faltan} días hábiles de confirmación")
        return f"«{t['destino']}», {cuantos}"
    return (f"el percentil ya cae en «{t['destino']}», pero no ha rebasado el "
            f"margen de {t['histeresis']:.0f} puntos que exige cambiar de régimen")


def _transicion_regla(t: dict) -> str:
    """LA REGLA, dicha entera y en llano.

    «Confirmación: 3 días hábiles restantes» no se entiende sin saber qué es lo
    que tiene que aguantar esos días. Esta frase lo dice: el umbral concreto,
    los días que exige y que el contador vuelve a cero si el eje se cae un solo
    día. Sin ella el lector no sabe si son tres días pase lo que pase.
    """
    if not t or t.get("coincide") or not t.get("destino"):
        return ""
    # El borde que hay que rebasar, con su margen: se deriva de la banda ACTUAL
    # y del margen publicado, no se escribe a mano.
    import config as _c
    bandas = _c.STATE_BANDS
    i = next((k for k, b in enumerate(bandas) if b[2] == t.get("etiqueta")), None)
    if i is None:
        return ""
    sube = t.get("confirmando")
    if sube:
        umbral = bandas[i][1] + t["histeresis"]
        return (f"Para que el cambio se confirme, la lectura de riesgo tiene "
                f"que mantenerse por encima de {umbral:.0f} —más alta que el "
                f"{umbral:.0f} % de su propia historia— durante "
                f"{t['dias_requeridos']} días hábiles seguidos. Lleva "
                f"{t['dias']}. Si baja un solo día, el contador vuelve a cero.")
    umbral = bandas[i][0] - t["histeresis"]
    return (f"El régimen no cambia mientras la lectura de riesgo no baje de "
            f"{umbral:.0f}: el margen existe para que un día suelto no mueva "
            f"la lectura.")


# --------------------------------------------------------------- contexto
class Context:
    """Series completas, calculadas una sola vez y reutilizables para
    cualquier fecha. Es lo que hace barato generar los snapshots de control."""

    def __init__(self, panel: pd.DataFrame, spy: pd.Series | None = None,
                 prices: pd.DataFrame | None = None,
                 macro: pd.DataFrame | None = None):
        self.panel = panel
        # Precios para las rentabilidades futuras de los analogos. Opcional:
        # sin ellos, los analogos salen sin la columna "que paso".
        self.prices = prices.reindex(panel.index).ffill() if prices is not None else None
        if spy is not None:
            self.spy = spy.reindex(panel.index).ffill()
        elif self.prices is not None and "SPY" in self.prices.columns:
            self.spy = self.prices["SPY"]
        else:
            self.spy = None
        self.pct = scoring.trailing_pct(panel)
        # Extremos de la misma ventana movil que el percentil: el valor que
        # marca p0 y p100. Sirven para poner numeros a los bordes de la barra.
        _w, _m = config.PCT_WINDOW, config.PCT_MINP
        self.roll_min = panel.rolling(_w, min_periods=_m).min()
        self.roll_max = panel.rolling(_w, min_periods=_m).max()
        # FRECUENCIA NATIVA de cada serie, inferida del dato: la mediana de
        # dias habiles entre CAMBIOS de valor. Es lo que decide cuanta
        # persistencia hay que exigirle a un extremo suyo (SPEC 7.1).
        self.freq_dias: dict[str, float] = {}
        for c in panel.columns:
            v = panel[c].dropna().tail(750)
            if len(v) < 30:
                self.freq_dias[c] = 1.0
                continue
            cambia = v.ne(v.shift()).to_numpy().nonzero()[0]
            self.freq_dias[c] = (float(np.median(np.diff(cambia)))
                                 if len(cambia) > 5 else 1.0)
        self.oriented = scoring.orient(self.pct)
        self.pillars = scoring.pillar_scores(self.oriented)
        # Cambio de cada pilar a 1 y 3 meses, para TODA la historia: los
        # analogos comparan trayectorias, no solo estados, y para eso hace
        # falta el delta de cada fecha pasada, no solo el de hoy.
        self.pillar_d1m = scoring.delta_series(self.pillars, config.DELTA_1M)
        self.pillar_d3m = scoring.delta_series(self.pillars, config.DELTA_3M)
        # Variables de entorno en NIVEL ABSOLUTO (la segunda distancia de los
        # analogos). Se estandarizan por fecha, dentro de _analogos.
        try:
            from snapshot import bloomberg as _bb
            _bbg = _bb.load_all()
        except Exception:
            _bbg = None
        self.env = entorno.construir(panel, macro, _bbg)
        self.axes = scoring.axis_scores(self.pillars)
        self.axes_hist = pd.DataFrame(
            {a: scoring.expanding_pct(self.axes[a]) for a in self.axes.columns},
            index=self.axes.index,
        )
        self.state = scoring.state_series(self.axes_hist["riesgo"])
        self.extreme = ((self.pct <= config.EXTREME_LOW) |
                        (self.pct >= config.EXTREME_HIGH)).where(self.pct.notna())
        # Ultima fecha en la que el dato subyacente se movio: es la antiguedad
        # real de la observacion, no la del arrastre en la rejilla diaria.
        self.last_move = {}
        for k in panel.columns:
            s = panel[k]
            moved = s.ne(s.shift()) & s.notna()
            self.last_move[k] = moved


def _last_move_date(ctx: Context, key: str, asof: pd.Timestamp):
    m = ctx.last_move[key].loc[:asof]
    m = m[m]
    return m.index[-1] if len(m) else None


# ------------------------------------------------------------- secciones
def frecuencia(ctx: "Context", key: str) -> str:
    d = (ctx.freq_dias or {}).get(key, 1.0)
    if d <= config.FREQ_CORTE_DIAS["diaria"]:
        return "diaria"
    if d <= config.FREQ_CORTE_DIAS["semanal"]:
        return "semanal"
    return "mensual"


def persistencia_minima(ctx: "Context", key: str) -> int:
    return config.PERSIST_EXTREMO_MIN[frecuencia(ctx, key)]


def extremo_persistente(ctx: "Context", key: str, dias) -> bool:
    """Un extremo solo cuenta como tension/confirmacion si lleva ya el minimo
    que exige la frecuencia de SU serie."""
    try:
        d = float(dias)
    except (TypeError, ValueError):
        return False
    return np.isfinite(d) and d >= persistencia_minima(ctx, key)


class Verificador:
    """TODA frase que afirme algo sobre el mercado pasa por aqui antes de
    emitirse -- este en la sintesis, en la prosa o en una nota de fila. No hay
    excepciones por seccion: ese fue justo el agujero por el que se colaron
    «la caida de liquidez continua» con la liquidez en su maximo, y «el
    crecimiento sigue superando al costo del capital» en una lectura defensiva.

    Una afirmacion se declara con VARIANTES por estado. Se emite la del estado
    real; si no hay variante para ese estado, SE OMITE. El silencio es
    preferible a una frase falsa, y la omision se cuenta.
    """

    def __init__(self, snap: dict):
        self.snap = snap
        self.verificadas: list[str] = []
        self.omitidas: list[str] = []
        self.no_verificables: list[str] = []

    # -- estados que se pueden verificar contra el tablero -------------------
    def trend(self) -> str:
        return self.snap.get("trend", "lateral")

    def lado_extremo(self, key: str) -> str | None:
        """En que lado de su rango esta el indicador, por percentil CRUDO."""
        for pil in self.snap.get("tablero", []):
            for f in pil["filas"]:
                if f["key"] == key and np.isfinite(f.get("pct", np.nan)):
                    return "alto" if f["pct"] >= 50 else "bajo"
        return None

    def clima_en_extremo(self) -> bool:
        est = (self.snap.get("titular") or {}).get("estado")
        return est in (config.STATE_BANDS[0][2], config.STATE_BANDS[-1][2])

    # -- emision -------------------------------------------------------------
    def elige(self, clave: str, variantes: dict, estado: str | None) -> str | None:
        if estado is None:
            self.no_verificables.append(clave)
            return None
        txt = (variantes or {}).get(estado)
        if not txt:
            self.omitidas.append(f"{clave} [{estado}]")
            return None
        self.verificadas.append(f"{clave} [{estado}]")
        return txt

    def registra(self, clave: str, estado: str) -> None:
        """Para frases que ya se construyen a partir del dato verificado."""
        self.verificadas.append(f"{clave} [{estado}]")

    def resumen(self) -> dict:
        return dict(verificadas=len(self.verificadas),
                    omitidas=self.omitidas,
                    no_verificables=self.no_verificables)


def _lectura(op: float) -> str:
    if not np.isfinite(op):
        return "sin dato"
    if op >= 60:
        return "favorable"
    if op <= 40:
        return "adverso"
    return "neutral"


def _votos(key: str, pct: float) -> dict[str, int]:
    """Que exposiciones defiende este indicador dado su nivel de hoy.

    Se decide sobre el percentil CRUDO, no sobre la lectura orientada. No
    todo lo adverso para la bolsa es adverso para todo: una inflacion alta
    perjudica a bolsa y duracion y beneficia a las materias primas, y colgar
    el voto del signo de riesgo borraria esa diferencia.
    """
    mapa = config.INDICATOR_ASSET_MAP.get(key, {})
    if not np.isfinite(pct):
        return {}
    if pct >= config.VOTE_HIGH:
        return dict(mapa)
    if pct <= config.VOTE_LOW:
        return {k: -v for k, v in mapa.items()}
    return {}


def huella_datos(ctx, asof) -> dict:
    """La HUELLA de los datos con los que se genero un documento.

    Existe porque ya hubo tres renders del 22/09/2026 con cifras distintas. La
    explicacion es legitima --Yahoo y FRED revisan series, y una reconstruccion
    posterior usa los datos corregidos-- pero mirando el documento no habia
    forma de saber cual era cual, y dos copias de la misma fecha con numeros
    distintos se leen como una contradiccion.

    La huella resume LO QUE ENTRO, no lo que salio: los valores del panel el
    dia de la lectura, mas hasta donde llega cada fuente. Si manana el mismo
    dia se reconstruye con datos revisados, el codigo cambia y las dos copias
    se distinguen a simple vista.

    No es un identificador criptografico ni pretende serlo: son seis digitos
    hexadecimales, suficientes para decir "estas dos no son la misma foto".
    """
    import hashlib

    # El digest cubre TODA la historia que alimenta la lectura, no solo la fila
    # del dia: el percentil es de cinco años, asi que una revision de hace tres
    # meses mueve la lectura sin tocar el valor de hoy. Por serie van su valor
    # en la fecha, cuantas observaciones hay y su suma: cualquier correccion en
    # cualquier punto cambia al menos una de las tres.
    hasta = ctx.panel.loc[:asof]
    partes = []
    for k in sorted(hasta.columns):
        col = hasta[k].dropna()
        ult = float(col.iloc[-1]) if len(col) else float("nan")
        partes.append(f"{k}={round(ult, 6)}:{len(col)}:{round(float(col.sum()), 4)}")
    codigo = hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:6]
    # Hasta donde llega cada fuente se PUBLICA, pero no entra en el codigo: una
    # lectura de 2008 no cambia porque hoy haya llegado un dato nuevo.
    fin_panel = ctx.panel.index[-1]
    px = getattr(ctx, "prices", None)
    fin_px = px.index[-1] if px is not None and len(px) else None
    return dict(codigo=codigo, n_series=int(ctx.panel.shape[1]),
                panel_hasta=fin_panel,
                precios_hasta=fin_px,
                generado=pd.Timestamp.now())


def build_snapshot(ctx: Context, asof, previo: dict | None = None) -> dict:
    asof = pd.Timestamp(asof)
    idx = ctx.panel.index
    if asof < idx[0]:
        raise ValueError(f"fecha anterior al inicio de los datos ({idx[0].date()})")
    asof = idx[idx <= asof][-1]

    snap: dict = {"asof": asof, "generated": pd.Timestamp.now()}
    # Con que datos se hizo esta lectura, para que dos copias de la misma
    # fecha generadas antes y despues de una revision se distingan.
    snap["huella"] = huella_datos(ctx, asof)

    # ---------------------------------------------------- 2. ejes
    # Nivel y deltas SUAVIZADOS: el valor actual es la media de los ultimos dias
    # habiles y el delta se compara contra una ventana, no contra un cierre
    # suelto. Sin esto el rumbo cambiaba de un dia para otro sin que el mercado
    # se moviera. El percentil historico (hist_pct) y el estado no se tocan: los
    # gobierna la maquina de estados, que ya trae su propia histeresis.
    ejes = []
    for a, spec in config.AXES.items():
        lvl = scoring.nivel(ctx.axes[a], asof)
        hp = ctx.axes_hist[a].loc[asof]
        hist_defined = ctx.axes_hist[a].loc[:asof].dropna()
        ejes.append(dict(
            key=a, label=spec["label"], sub=spec["sub"],
            high=spec["high"], low=spec["low"],
            level=lvl,
            hist_pct=float(hp) if np.isfinite(hp) else np.nan,
            hist_since=hist_defined.index[0] if len(hist_defined) else None,
            d1m=scoring.delta(ctx.axes[a], config.DELTA_1M, asof,
                              suave_actual=config.DELTA_ACTUAL_WIN),
            d3m=scoring.delta(ctx.axes[a], config.DELTA_3M, asof,
                              suave_actual=config.DELTA_ACTUAL_WIN),
            pillars=[(p, config.PILLARS[p]["label"]) for p in spec["weights"]],
        ))
    snap["ejes"] = ejes

    # ---------------------------------------------------- 1. titular
    riesgo = ejes[0]
    estado = ctx.state.loc[asof]
    st_start, st_len = scoring.run_start(ctx.state, asof)
    d3 = riesgo["d3m"]
    if not np.isfinite(d3) or abs(d3) < 3:
        rumbo = "sin rumbo claro en los últimos 3 meses"
    elif d3 > 0:
        rumbo = f"mejorando ({d3:+.0f} puntos en 3 meses)"
    else:
        rumbo = f"deteriorándose ({d3:+.0f} puntos en 3 meses)"
    # SPEC-7P 1: el regimen publicado lleva histeresis, asi que la ETIQUETA y la
    # BANDA DEL PERCENTIL pueden discrepar unos dias mientras se confirma un
    # cambio. Imprimir «neutral · p75» sin decirlo es una contradiccion a la
    # vista del lector: p75 cae en apetito de riesgo. El detalle sale de la
    # MISMA maquina de estados que la etiqueta, y de aqui lo leen los dos
    # documentos, los graficos, los disparadores y el QA.
    trans = scoring.estado_detalle(ctx.axes_hist["riesgo"].loc[:asof])
    snap["titular"] = dict(
        estado=estado or "sin dato",
        desde=st_start, dias=st_len, duracion=_duracion(st_len),
        hist_pct=riesgo["hist_pct"], rumbo=rumbo,
        hist_since=riesgo["hist_since"],
        banda_pct=trans["banda_pct"], transicion=trans,
        transicion_txt=_transicion_txt(trans),
        transicion_regla=_transicion_regla(trans),
    )

    # ---------------------------------------------------- 3. tablero
    en_eje = {}
    for a, spec in config.AXES.items():
        for p in spec["weights"]:
            en_eje[p] = spec["label"]

    tablero = []
    for pillar, meta in config.PILLARS.items():
        sc = ctx.pillars[pillar].loc[asof]
        filas = []
        for key in config.PILLAR_KEYS[pillar]:
            d = config.INDICATOR_BY_KEY[key]
            v = ctx.panel[key].loc[asof]
            p = ctx.pct[key].loc[asof]
            op = ctx.oriented[key].loc[asof]
            ext = bool(ctx.extreme[key].loc[asof]) if np.isfinite(p) else False
            ext_since, ext_len = scoring.bool_run_start(
                ctx.extreme[key].fillna(False).astype(bool), asof) if ext else (None, 0)
            lm = _last_move_date(ctx, key, asof)
            edad = int((asof - lm).days) if lm is not None else None
            filas.append(dict(
                key=key, label=d["label"], src=d["src"], sign=d["sign"],
                valor=_fmt(d["fmt"], d["unit"], v),
                valor_raw=float(v) if np.isfinite(v) else np.nan,
                pct=float(p) if np.isfinite(p) else np.nan,
                op=float(op) if np.isfinite(op) else np.nan,
                d1m=_fmt(d["dfmt"], d["unit"], scoring.delta(ctx.panel[key], config.DELTA_1M, asof)),
                d3m=_fmt(d["dfmt"], d["unit"], scoring.delta(ctx.panel[key], config.DELTA_3M, asof)),
                d1m_raw=scoring.delta(ctx.panel[key], config.DELTA_1M, asof),
                d3m_raw=scoring.delta(ctx.panel[key], config.DELTA_3M, asof),
                extremo=ext,
                extremo_tipo=("favorable" if np.isfinite(op) and op >= config.EXTREME_HIGH
                              else "adverso") if ext else None,
                extremo_desde=ext_since, extremo_dias=ext_len,
                lectura=_lectura(op),
                votos=_votos(key, p),
                # extremos de la ventana de 5 anos, en las unidades del dato
                rmin=_fmt(d["fmt"], "", ctx.roll_min[key].loc[asof]),
                rmax=_fmt(d["fmt"], "", ctx.roll_max[key].loc[asof]),
                edad=edad, dato_de=lm,
            ))
        # Dentro de cada pilar, primero lo mas alejado de su normalidad.
        filas.sort(key=lambda r: (-abs((r["pct"] if np.isfinite(r["pct"]) else 50.0) - 50.0)))
        tablero.append(dict(
            key=pillar, label=meta["label"], desc=meta["desc"],
            score=float(sc) if np.isfinite(sc) else np.nan,
            lectura=_lectura(sc if np.isfinite(sc) else np.nan),
            eje=en_eje.get(pillar),
            d1m=scoring.delta(ctx.pillars[pillar], config.DELTA_1M, asof,
                              suave_actual=config.DELTA_ACTUAL_WIN),
            d3m=scoring.delta(ctx.pillars[pillar], config.DELTA_3M, asof,
                              suave_actual=config.DELTA_ACTUAL_WIN),
            filas=filas,
            n_datos=sum(1 for f in filas if np.isfinite(f["pct"])),
            n_total=len(filas),
        ))
    snap["tablero"] = tablero

    # ------------------------------------- puntuacion de toma de riesgo
    #
    # El recuento se publica en DOS unidades: indicadores (crudo) y senales
    # independientes (efectivo). El titular usa el efectivo porque el crudo
    # cuenta cuatro veces la misma senal cuando un pilar tiene cuatro filas
    # parecidas. El crudo no se elimina: queda como detalle.
    todas = [f for pil in tablero for f in pil["filas"]]
    C = senales.matriz(ctx.pct, asof)
    grupos = senales.clusters(C)
    snap["senales"] = senales.resumen(todas, grupos, C)
    snap["senales"]["por_pilar"] = senales.por_pilar(todas, grupos)
    snap["redundancia"] = senales.redundancia_alta(todas, grupos)
    for pil in tablero:
        pil["senales_e"] = snap["senales"]["por_pilar"].get(pil["key"], {}).get("e")

    a_favor = [f for f in todas if f["lectura"] == "favorable"]
    en_contra = [f for f in todas if f["lectura"] == "adverso"]
    neutrales = [f for f in todas if f["lectura"] == "neutral"]
    snap["riesgo"] = dict(
        score=riesgo["level"], hist_pct=riesgo["hist_pct"],
        d1m=riesgo["d1m"], d3m=riesgo["d3m"], estado=estado,
        n_favor=len(a_favor), n_contra=len(en_contra), n_neutral=len(neutrales),
        n_total=len(todas),
        **{k: snap["senales"][k] for k in
           ("e_favor", "e_contra", "e_neutral", "e_total", "disponible")},
    )

    # ---------------------------------------------------- divergencias
    # Van ANTES que la postura: una divergencia que parte a una clase en dos
    # baja su conviccion, asi que hay que conocerlas para concluir.
    snap["divergencias"] = _divergencias(ctx, asof)
    snap["div_intra"] = _divergencias_intra(ctx, asof, tablero)
    snap["extremos"] = _extremos(tablero)
    # SPEC 7.1 vale para TODOS los selectores, no solo para la tensión. Se
    # publica la persistencia de cada indicador para que cualquier selector
    # --tensión, disparadores, evidencia-- use la misma y no cada uno la suya.
    # LA PERSISTENCIA ES UNA PROPIEDAD DEL INDICADOR, no una comprobacion de
    # cada selector (SPEC 7.1). Se calcula UNA vez, aqui, y todos los selectores
    # la consultan. Aplicarla selector por selector no funcionaba: el extremo de
    # dos dias de la liquidez neta se excluyo como tension, luego como
    # disparador, y aun asi reaparecio como evidencia del oro. Siempre habria un
    # selector nuevo sin la regla.
    snap["persistencia"] = {}
    for f in todas:
        ext = bool(f.get("extremo"))
        dias = int(f.get("extremo_dias") or 0)
        minimo = persistencia_minima(ctx, f["key"])
        ok = (extremo_persistente(ctx, f["key"], f.get("extremo_dias"))
              if ext else True)
        snap["persistencia"][f["key"]] = dict(
            persistente=bool(ok), dias_en_extremo=dias,
            minimo_requerido=int(minimo), extremo=ext,
            reciente=bool(ext and not ok))

    # ---- pilares sin lectura unificada: demasiados pares en contradiccion
    coh = _coherencia_pilares(ctx, asof, tablero)
    for pil in tablero:
        c = coh.get(pil["key"], {})
        pil["sin_lectura"] = c.get("sin_lectura", False)
        pil["pares_contra"] = c.get("pares", 0)
        pil["pares_posibles"] = c.get("posibles", 0)
    for e in ejes:
        e["sin_lectura"] = [config.PILLARS[p]["label"]
                            for p in config.AXES[e["key"]]["weights"]
                            if coh.get(p, {}).get("sin_lectura")]

    # ------------------------------------------- que clase de activo sale
    snap["clases"] = _clases(todas)

    # ------------------------------------- inclinación sugerida por clase
    _recientes = {k for k, v in snap["persistencia"].items() if v["reciente"]}
    snap["postura"], snap["postura_notas"] = _postura(
        todas, snap["clases"], grupos, snap["divergencias"], ejes, coh, _recientes)

    # tendencia de la bolsa, verificada contra el dato -- gobierna qué frases de
    # mecanismo son ciertas hoy (ver _mecanismo_ok).
    snap["trend"] = _trend(ctx, asof)

    # ------ un extremo que contradice la inclinacion de su propia clase
    snap["contradicciones"] = _contradicciones(ctx, asof, todas, snap["postura"],
                                               snap["trend"])

    # ------------------------------------- qué puede pasar (prospectivo)
    snap["que_puede_pasar"] = _que_puede_pasar(ctx, asof, snap)
    snap["distribucion"] = _distribucion_conviccion(ctx, asof, grupos)

    # De dónde viene el deterioro/mejora del clima: los pilares del eje de riesgo
    # que más se movieron en su contra, para nombrarlos en la línea de clima.
    d3 = riesgo["d3m"]
    axis_pilares = [p for p in config.AXES["riesgo"]["weights"]]
    movs = sorted(((config.PILAR_CORTO.get(p, p),
                    next((pl["d1m"] for pl in tablero if pl["key"] == p), np.nan))
                   for p in axis_pilares),
                  key=lambda t: (t[1] if np.isfinite(t[1]) else 0.0))
    if np.isfinite(d3) and d3 < 0:
        snap["clima_causa"] = [lbl for lbl, mv in movs[:2] if np.isfinite(mv) and mv < 0]
    elif np.isfinite(d3) and d3 > 0:
        snap["clima_causa"] = [lbl for lbl, mv in movs[::-1][:2] if np.isfinite(mv) and mv > 0]
    else:
        snap["clima_causa"] = []

    # ------------------------------------- nota de research: composites, prosa,
    # gráfico y tabla de posicionamiento (actual vs mes anterior)
    snap["composites"] = _composites(ctx, asof, tablero, snap["persistencia"])
    # La postura agregada y la tension se publican ANTES de la prosa: el
    # condicional ("la lectura depende de...") se deriva de ellas, y si no
    # existen todavia la frase cae en su rama generica.
    snap["postura_general"] = _tilt(snap["postura"],
                                    (snap.get("composites") or {}).get("relacion"))
    snap["tension_principal"] = _tension_eje(snap)
    snap["tension_contexto"] = _tension_contexto(snap)
    # La tension DOMINANTE es estructural (bloques, pilares, ejes); la principal
    # es el indicador que mas contradice. Encabezar con la segunda hacia pasar
    # un dato suelto por diagnostico de fondo.
    snap["tension_dominante"] = decision.tension_dominante(snap)
    # TODA frase que afirme algo sobre el mercado pasa por el verificador.
    V = Verificador(snap)
    snap["conclusiones"] = _conclusiones(snap, snap["composites"], V)
    snap["evidencia"] = _evidencia(snap, snap["composites"], V)
    snap["verificacion"] = V.resumen()
    snap["serie_puntuacion"] = _serie_puntuacion(ctx, asof)
    snap["posicionamiento"] = _posicionamiento(snap, ctx, asof, grupos)

    # ------------------------------------- análogos históricos
    snap["analogos"] = _analogos(ctx, asof)

    # ------------------------------------------------ capa documental
    # Solo documentos publicados en o antes de `asof`: si no, el snapshot de
    # 2008 se leeria con research de 2026.
    snap["documentos"] = documentos.enriquecer(documentos.cargar(asof), tablero)

    # ------------------------------------- qué cambió desde el anterior
    # SPEC-7P 4: ANTES del DecisionState. Estaba despues, y como `what_changed`
    # se calcula dentro de `decision.build`, siempre recibia un diccionario
    # vacio: el brief llevaba desde entonces diciendo «sin cambios que afecten
    # una decision» aunque los hubiera. Nada de esto depende de la decision, asi
    # que el sitio correcto es aqui.
    snap["cambios"] = historico.comparar(snap, previo)
    if snap["cambios"].get("disponible"):
        pmap = {p["label"]: p for p in snap["postura"]}
        for d in (snap["cambios"].get("dir_cambios", [])
                  + snap["cambios"].get("conv_cambios", [])):
            d["por"] = _causa_cambio(pmap.get(d["clase"]))

    # ---------------------------------------------- DECISION STATE (SPEC 2)
    # La capa comun. Lo que decide, decide aqui; el render solo escribe. Se
    # publican primero los dos hechos de decision que la capa necesita y que
    # hasta ahora se recalculaban sueltos en cada sitio.
    def _recalcular(patch: dict) -> dict:
        """RECOMPUTACION CONTRAFACTUAL (SPEC 6): devuelve el snapshot que
        habria si los indicadores de `patch` estuvieran en ese percentil.

        No es una heuristica sobre el trigger: se rehace el voto del indicador,
        el consenso de cada clase y la escalera de conviccion con LAS MISMAS
        funciones que producen la postura publicada. Es lo unico que permite
        distinguir «deja de apoyar» de «da la vuelta a la lectura».

        Lo que NO se recalcula, y por que: las divergencias entre pilares y la
        coherencia de cada pilar se leen del panel completo, no del percentil de
        un indicador; se mantienen en su valor observado. El contrafactual
        responde a «con este dato en ese nivel, ¿sigue en pie el recuento?», no
        a «como seria el mundo si el pilar entero se hubiera movido».
        """
        filas2 = [dict(f) for f in todas]
        for f in filas2:
            if f["key"] not in patch:
                continue
            pc = float(patch[f["key"]])
            f["pct"] = pc
            f["op"] = (100.0 - pc) if f["sign"] < 0 else pc
            f["lectura"] = _lectura(f["op"])
            f["votos"] = _votos(f["key"], pc)
        por_key = {f["key"]: f for f in filas2}
        tablero2 = [dict(pil, filas=[por_key[f["key"]] for f in pil["filas"]])
                    for pil in tablero]
        clases2 = _clases(filas2)
        post2, _n2 = _postura(filas2, clases2, grupos,
                              snap["divergencias"], ejes, coh, _recientes)
        gen2 = _tilt(post2, (snap.get("composites") or {}).get("relacion"))
        return dict(snap, tablero=tablero2, clases=clases2,
                    postura=post2, postura_general=gen2)

    snap["decision"] = decision.build(snap, ctx=ctx, grupos=grupos,
                                      postura_en=_postura_en, recalc=_recalcular)

    # ---------------------------------------------------- cobertura y edad
    total = len(config.INDICATORS)
    con_dato = int(ctx.pct.loc[asof].notna().sum())
    viejos = [(f["label"], f["dato_de"], f["edad"])
              for pil in tablero for f in pil["filas"]
              if f["edad"] is not None and f["edad"] > 40]
    viejos.sort(key=lambda t: -t[2])
    snap["cobertura"] = dict(con_dato=con_dato, total=total, viejos=viejos)

    # SEMANTIC-PASS 13: el Cross-Asset Tape. Se calcula aqui, con el estado ya
    # montado, porque necesita la historia de posturas del DecisionState.
    from snapshot import tape as _tape
    snap["tape"] = _tape.construir(
        ctx, asof, (snap["decision"].guia.get("historia") or {}))

    # Lo ultimo, porque resume todo lo anterior.
    snap["esencial"] = _esencial(snap)
    snap["menciones"] = _menciones(snap)
    snap["comprobaciones"] = _comprobaciones(snap)
    return snap


# --------------------------------------------------- comprobaciones fijas
def _comprobaciones(snap: dict) -> list[dict]:
    """Las comprobaciones que se ejecutan en CADA generacion, con su resultado.

    No son un log: van impresas en el documento. Y no corrigen nada -- si una
    detecta un problema, lo dice y ya; el tablero no se toca por detras. Cuando
    una no se puede calcular, se declara "no disponible" en vez de omitirla,
    porque una comprobacion ausente se confunde con una comprobacion pasada.
    """
    out = []

    def add(label, valor, estado="ok", nota=""):
        out.append(dict(label=label, valor=valor, estado=estado, nota=nota))

    s = snap["senales"]
    if s.get("disponible"):
        add("Grupos independientes frente a indicadores",
            f"{s['n_clusters']} de {s['n_total']}", "ok",
            f"agrupados por correlación; el mayor reúne "
            f"{len(s['grupo_mayor'])} indicadores que se mueven casi como uno")
    else:
        add("Grupos independientes frente a indicadores", "no disponible", "nd",
            "sin historia suficiente para calcular las correlaciones")

    red = snap["redundancia"]
    if red:
        add("Pilares con redundancia alta",
            "; ".join(f"{r['pilar_label'].lower()} en {r['clase_label'].lower()} "
                      f"({r['share_n']:.0f}% de los indicadores, "
                      f"{r['share_e']:.0f}% de las voces)" for r in red),
            "aviso",
            "ese pilar manda en el recuento de la clase sin aportar información nueva")
    else:
        add("Pilares con redundancia alta", "ninguno")

    di = snap["div_intra"]["lista"]
    pares = snap["div_intra"]["pares"]
    add("Divergencias dentro de un mismo pilar",
        f"{len(di)} en {len(di)} {'pilar' if len(di) == 1 else 'pilares'}",
        "aviso" if di else "ok",
        (f"de {pares} pares de indicadores en contradicción; se publica el más "
         f"amplio de cada pilar" if pares > len(di) else ""))

    co = snap["contradicciones"]
    nf = sum(c["n_frentes"] for c in co)
    add("Contradicciones de alto perfil", f"{len(co)}",
        "aviso" if co else "ok",
        (f"{nf} inclinaciones contradichas; se destaca la del indicador más "
         f"extremo: {co[0]['label']} (p{co[0]['pct']:.0f}). El resto ya está "
         f"reflejado en la convicción de su clase") if co else "")

    # ---- consistencia: ¿se concluye y se desmiente a la vez?
    #
    # La comprobación que importa. Una contradicción tiene que estar RESUELTA
    # dentro de la conclusión: si un extremo apunta al contrario de una clase,
    # esa clase no puede salir con convicción alta o media. Si sale, el
    # documento enuncia y desmiente a la vez, y hay que decirlo aquí.
    def _rank(c):
        return config.CONV_ORDEN.get(c, 0)
    # Una contradiccion esta "sin resolver" solo si el extremo que la causa
    # DEBIA rebajar la conviccion (techo aplicable por su edad) y aun asi la
    # clase quedo por encima de ese techo. Un extremo ya absorbido por edad
    # (sin techo) que deja la clase en alta NO cuenta: es el caso previsto.
    sin_resolver = [p for p in snap["postura"]
                    if p.get("contra_cap") and p.get("conviccion")
                    and _rank(p["conviccion"]) > _rank(p["contra_cap"])]
    add("Conclusiones enunciadas y contradichas sin resolver", f"{len(sin_resolver)}",
        "aviso" if sin_resolver else "ok",
        ("; ".join(f"{p['label']} ({p['conviccion']}) contra {p['contra_label']}"
                   for p in sin_resolver) if sin_resolver else
         "un extremo en contra nunca deja pasar de media; reciente, la limita a baja"))

    # correccion 2: "alta" tiene que ser rara para significar algo
    altas = [p for p in snap["postura"] if p.get("conviccion") == "alta"]
    add("Clases con convicción alta", f"{len(altas)}",
        "aviso" if len(altas) > config.CONV_ALTA_MAX else "ok",
        (("; ".join(p["label"] for p in altas) + " — demasiadas: la etiqueta deja "
          "de distinguir cuando es la mayoría") if len(altas) > config.CONV_ALTA_MAX
         else ("; ".join(p["label"] for p in altas) if altas else
               "ninguna clase sin ningún extremo en contra")))

    dist = snap.get("distribucion") or {}
    co_d = dist.get("conteo") or {}
    if co_d:
        tot_d = sum(co_d.values()) or 1
        alta_frac = co_d.get("alta", 0) / tot_d
        estado_d = ("aviso" if co_d.get("alta", 0) == 0 or alta_frac > 0.5 else "ok")
        add("Distribución de convicción, 6 meses",
            f"alta {co_d.get('alta', 0)} · media {co_d.get('media', 0)} · "
            f"baja {co_d.get('baja', 0)} · neutral {co_d.get('neutral', 0)}",
            estado_d,
            ("«alta» no aparece nunca: la escala está demasiado apretada"
             if co_d.get("alta", 0) == 0 else
             "«alta» es casi siempre: la escala no distingue" if alta_frac > 0.5 else
             f"«alta» aparece en su justa medida ({100 * alta_frac:.0f}% de las "
             f"clase-semanas); aproximada, ver el tablero"))

    # ¿sale una conclusión limpia? Si la inclinación agregada es "mixta", la
    # lectura no concluye y la prosa no debe fingir que sí -- se dice aquí. La
    # convicción va capada por la relación macro-técnico: atempera nunca da alta.
    comps = snap.get("composites") or {}
    rel = comps.get("relacion")
    tl = _tilt(snap["postura"], rel)
    add("Conclusión de la nota", tl["palabra"],
        "aviso" if tl["palabra"] == "mixta" else "ok",
        ("la evidencia no cuadra en una dirección: la prosa lo dice, no fuerza una "
         "conclusión" if tl["palabra"] == "mixta"
         else f"inclinación {tl['palabra']}, convicción {tl['conviccion']} "
              f"(el macro {rel} al técnico)"))

    # correccion (nota): la evidencia se elige por PERTINENCIA. Cada afirmación
    # solo puede citar indicadores de su pilar; inflación y posicionamiento no
    # se citan como evidencia de los ejes. Debe ser 0.
    pilar_de = comps.get("pilar_de", {})
    fuera = []
    for etiqueta, pilares, keys in comps.get("citas", []):
        malas = [k for k in keys if pilar_de.get(k) not in pilares]
        if malas:
            fuera.append(f"{etiqueta} → " + ", ".join(config.SHORT.get(k, k) for k in malas))
    add("Afirmaciones que citan indicadores fuera de su pilar", f"{len(fuera)}",
        "aviso" if fuera else "ok",
        ("; ".join(fuera) if fuera else
         "cada afirmación cita solo indicadores del pilar al que se refiere; "
         "inflación y posicionamiento quedan como contexto, no como evidencia de los ejes"))

    # --- verificacion de afirmaciones de mercado ----------------------------
    ver = snap.get("verificacion") or {}
    nv = ver.get("no_verificables") or []
    om = ver.get("omitidas") or []
    add("Afirmaciones de mercado verificadas",
        f"{ver.get('verificadas', 0)} verificadas · {len(om)} omitidas · "
        f"{len(nv)} no verificables",
        "aviso" if nv else "ok",
        ("NO VERIFICABLES: " + "; ".join(nv) if nv else
         ("toda frase que afirma algo sobre el mercado se comprobó contra el "
          "tablero antes de emitirse" +
          (". Omitidas por no tener variante para el estado de hoy: "
           + "; ".join(om) if om else
           ". Ninguna se omitió: todas tenían variante para el estado de hoy"))))

    # --- persistencia del selector de tension (SPEC 7.1) --------------------
    cands = (snap.get("contradicciones") or [])
    if not cands:
        add(f"Persistencia del {config.TENSION_INDICADOR.lower()}", "sin candidatos", "ok",
            "ningún indicador en extremo contradice la lectura de su clase")
    else:
        ten = snap.get("tension_principal")
        det = "; ".join(
            f"{config.SHORT.get(c['key'], c['label'])} "
            f"{_duracion(c.get('dias', 0))} en extremo "
            f"(mínimo {c.get('min_dias', '?')} d)"
            f"{' ✓' if c.get('persistente') else ' — descartado por reciente'}"
            f"{'' if c.get('eje') else ' · fuera de eje'}"
            for c in cands[:5])
        add(f"Persistencia del {config.TENSION_INDICADOR.lower()}",
            (config.SHORT.get(ten["key"], ten["label"]) if ten
             else "sin tensión persistente"),
            "ok" if ten else "aviso",
            det + ("" if ten else
                   ". Ningún candidato llega al mínimo de su frecuencia: se "
                   "publica «sin tensión persistente» y el extremo reciente se "
                   "cita como contexto"))

    # coherencia: clases cuya inclinacion difiere de la postura general. Si renta
    # variable o duracion divergen y la sintesis no lo explica, es un fallo.
    div = _postura_divergencias(snap)
    todas = div["divergentes"]
    rvdur = [p for p in todas if p["key"] in ("rv", "dur")]
    mencion = any("se expresa hoy por" in b for b in (snap.get("conclusiones") or []))
    if div["signo"] and rvdur and not mencion:
        estado_d = "aviso"
        det_d = ("la caja no explica por qué " +
                 _junta([p["label"].lower() for p in rvdur]) +
                 " difieren de la postura general")
    elif not div["signo"]:
        estado_d, det_d = "ok", "la postura es mixta: no hay dirección general de la que diferir"
    elif not todas:
        estado_d, det_d = "ok", "ninguna: todas las clases apuntan al lado de la postura"
    else:
        estado_d = "ok"
        det_d = ("; ".join(
            f"{p['label'].lower()} ({'neutral' if p['dir_tipo'] == 'neutral' else p['direccion']})"
            for p in todas) + (" — explicado en la síntesis" if rvdur else ""))
    add("Clases cuya inclinación difiere de la postura general", f"{len(todas)}", estado_d, det_d)

    # correccion 4: pilares sin lectura unificada
    incoh = [pil for pil in snap["tablero"] if pil.get("sin_lectura")]
    add("Pilares sin lectura unificada", f"{len(incoh)}",
        "aviso" if incoh else "ok",
        ("; ".join(f"{pil['label'].lower()} ({pil['pares_contra']} de "
                   f"{pil['pares_posibles']} pares en contradicción)" for pil in incoh)
         if incoh else "ningún pilar supera el umbral de pares en contradicción"))

    # correccion 1: la causa comun se dice UNA vez. Si un mismo indicador
    # aparece inline en 2+ filas de la tabla en vez de en una nota, esta mal.
    inline_cnt: dict[str, int] = {}
    for p in snap["postura"]:
        if p.get("contra_key") and not p.get("contra_comun"):
            inline_cnt[p["contra_key"]] = inline_cnt.get(p["contra_key"], 0) + 1
    repetida = [config.INDICATOR_BY_KEY[k]["label"] for k, n in inline_cnt.items() if n >= 2]
    add("Causa común repetida en la tabla de inclinaciones", f"{len(repetida)}",
        "aviso" if repetida else "ok",
        ("; ".join(repetida) if repetida else
         "cada indicador que rebaja varias clases va en una sola nota, no fila a fila"))

    neutras = [p for p in snap["postura"]
               if p.get("conv_motivo") in ("empate efectivo", "mayoría invertida")]
    add("Clases en neutral por convicción insuficiente", f"{len(neutras)}", "ok",
        ("; ".join(f"{p['label']} ({p['conv_motivo']})" for p in neutras) if neutras else
         "ninguna clase se quedó sin dirección por falta de evidencia"))

    men = snap.get("menciones") or {}
    repes = []
    for k, ms in men.items():
        secs = {s for s, _t in ms}
        cont = {s for s, t in ms if t == "contenido"}
        if len(secs) > 2 or len(cont) > 1:
            repes.append((k, sorted(secs), len(cont)))
    if repes:
        add("Indicadores mencionados en más de dos secciones",
            "; ".join(f"{config.INDICATOR_BY_KEY[k]['label']} "
                      f"(secciones {', '.join(str(s) for s in secs)})"
                      for k, secs, _c in repes),
            "aviso" if any(c > 1 for _k, _s, c in repes) else "ok",
            "el tablero de la 5 no cuenta: ahí están todos por construcción")
    else:
        add("Indicadores mencionados en más de dos secciones", "ninguno", "ok",
            "el tablero no cuenta: ahí están todos por construcción")

    # correccion 3: estabilidad de los deltas frente al snapshot anterior
    _campo = {"d1m": "a 1 mes", "d3m": "a 3 meses"}
    g = (snap.get("cambios") or {}).get("giro") or {}
    if g.get("disponible"):
        nm = (f"; el nivel se movió {g['nivel_mov']:.0f}"
              if g.get("nivel_mov") is not None else "")
        add("Mayor giro de un delta respecto al anterior",
            f"{g['giro']:.0f} puntos ({g['serie'].lower()}, {_campo.get(g['campo'], g['campo'])})",
            "aviso" if g.get("inestable") else "ok",
            (f"giro grande sin movimiento equivalente del nivel{nm}: posible "
             f"inestabilidad de método, no del mercado" if g.get("inestable")
             else f"coherente con el movimiento del nivel{nm}"))
    else:
        add("Mayor giro de un delta respecto al anterior", "no disponible", "nd",
            "no hay snapshot anterior para comparar")

    a = snap["analogos"]
    if not a.get("disponible"):
        add("Análogos", "no disponible", "nd", "sin historia suficiente de los pilares")
        add("Distancia de entorno del mejor análogo", "no disponible", "nd")
    elif a.get("sin_analogos"):
        motivo = ("el comportamiento no tiene precedente cercano" if a.get("motivo") == "dinamica"
                  else "los parecidos en dinámica vivían en otro entorno")
        add("Análogos", "sin episodios comparables", "aviso",
            f"{motivo}: el más cercano difiere {a['nearest']:.0f} puntos por fuerza, sobre "
            f"un umbral de {a['umbral']:.0f}")
        add("Distancia de entorno del mejor análogo", "no aplica", "nd")
    else:
        n = a.get("n_comparables", a.get("n", 0))
        add("Análogos", f"{n} episodios comparables (≥12 meses entre sí)",
            "aviso" if a.get("inusual") else "ok",
            "estado inusual: pocos comparables, no se publica consistencia por clase"
            if a.get("inusual") else "consistencia direccional por clase; el signo es más "
            "estable que la media con muestras pequeñas")
        de = a.get("env_mejor")
        if de is None or not np.isfinite(de):
            add("Distancia de entorno del mejor análogo", "no disponible", "nd",
                "faltan variables de entorno con dato en esas fechas")
        else:
            otro = a.get("n_otro_mundo", 0)
            add("Distancia de entorno del mejor análogo",
                f"{de:.2f} σ · {a['env_mejor_calidad']}",
                "aviso" if a["env_mejor_calidad"] == "muy distinto" else "ok",
                (f"{otro} de {a['n']} análogos se comportan igual pero en otro "
                 f"entorno" if otro else ""))
        falt = a.get("env_faltan") or []
        if falt:
            add("Variables de entorno sin dato", ", ".join(falt), "nd",
                f"el entorno se calcula con {a['env_n']} de "
                f"{len(config.ENV_VARS)} variables")

    viejos = snap["cobertura"]["viejos"]
    if viejos:
        add("Series con dato de más de 40 días",
            "; ".join(f"{l} ({a_} días)" for l, _d, a_ in viejos[:6])
            + (f"; y {len(viejos) - 6} más" if len(viejos) > 6 else ""),
            "aviso", "normal en series mensuales; se marca también en el tablero")
    else:
        add("Series con dato de más de 40 días", "ninguna")

    reg = snap["documentos"]
    fut = int(reg.get("futuros", 0))
    add("Fuentes descartadas por antigüedad", f"{reg.get('caducados', 0)}", "ok",
        (f"además, {fut} {'fuente' if fut == 1 else 'fuentes'} fuera por ser "
         f"posteriores a la fecha del snapshot") if fut else "")

    # ==================== QA automatico (SPEC 12) ====================
    # Estos seis existen porque los tres bugs de SPEC 13 pasaron sin que nada
    # los detectara. Cada uno vigila la clase de fallo que dejo pasar.

    # --- 1. Value consistency: un mismo concepto, un solo valor -------------
    # (bug 3: el grafico terminaba en 5 y el panel decia 10/100 el mismo dia)
    ser = (snap.get("serie_puntuacion") or {}).get("series") or {}
    malos = []
    for e in snap.get("ejes", []):
        pts = ser.get(e["key"]) or []
        if not pts:
            continue
        f_g, v_g = pts[-1]
        if abs(v_g - e["level"]) > 0.5:
            malos.append(f"{e['label'].lower()}: panel {e['level']:.0f} vs gráfico {v_g:.0f}")
        elif f_g != snap["asof"]:
            malos.append(f"{e['label'].lower()}: el gráfico termina en {fecha_corta(f_g)}, "
                         f"no en la fecha del snapshot")
    add("Mismo concepto, mismo valor", f"{len(malos)}",
        "aviso" if malos else "ok",
        ("; ".join(malos) if malos else
         "el nivel de cada eje coincide en el panel y en el gráfico, y ambos "
         "terminan en la fecha del snapshot"))

    # --- 2. Direction consistency: la etiqueta sigue al movimiento ----------
    # (bug 2: el eje caia y la proyeccion decia "euforia")
    r = snap["riesgo"]
    dhp_ = r.get("d1m")
    prob = []
    est_hoy = (snap.get("titular") or {}).get("estado")
    i_hoy = scoring.band_index(r.get("hist_pct"))
    for e in (snap.get("que_puede_pasar") or []):
        if e.get("tipo") != "clima":
            continue
        destino = next((b[2] for b in config.STATE_BANDS if b[2] in e["texto"]), None)
        i_dst = next((k for k, b in enumerate(config.STATE_BANDS) if b[2] == destino), None)
        if destino is None or i_hoy is None or i_dst is None:
            continue
        if np.isfinite(dhp_) and dhp_ < 0 and i_dst > i_hoy:
            prob.append(f"el eje cae ({dhp_:+.0f}) y se proyecta «{destino}», que está por encima")
        if np.isfinite(dhp_) and dhp_ > 0 and i_dst < i_hoy:
            prob.append(f"el eje sube ({dhp_:+.0f}) y se proyecta «{destino}», que está por debajo")
    # La etiqueta del estado tiene que ser la banda de su propio percentil, SALVO
    # mientras se confirma un cambio: el regimen lleva histeresis y esos dias de
    # desacuerdo son la regla funcionando, no un fallo. Lo que si seria un fallo
    # es que discreparan sin transicion que lo explique, y eso lo comprueba
    # `semantica.regimen_banda` con severidad de error.
    _tr = (snap.get("titular") or {}).get("transicion") or {}
    if (est_hoy and scoring.band_label(r.get("hist_pct")) != est_hoy
            and not _tr.get("destino")):
        prob.append(f"el estado dice «{est_hoy}» pero el percentil "
                    f"({r.get('hist_pct'):.0f}) cae en "
                    f"«{scoring.band_label(r.get('hist_pct'))}»")
    add("Dirección del eje frente a su etiqueta", f"{len(prob)}",
        "aviso" if prob else "ok",
        ("; ".join(prob) if prob else
         "la proyección del clima solo apunta hacia donde se mueve el eje, y el "
         "estado coincide con la banda de su percentil"))

    # --- 3. Historical window consistency -----------------------------------
    # (bug 1: "sin episodios comparables en 21 anos" con una ventana de 2.5)
    a_ = snap.get("analogos") or {}
    m_ = a_.get("muestra") or {}
    wprob = []
    if m_.get("hasta") is not None:
        tope = snap["asof"] - pd.Timedelta(days=config.ANALOG_FWD_MIN_DAYS)
        if m_["hasta"] > tope:
            wprob.append("la ventana llega más allá del límite que exige tener 12 "
                         "meses de futuro")
    vent = (f"{m_['anos']:.1f} años ({m_['desde'].year}–{m_['hasta'].year}), "
            f"{m_['n']} fechas elegibles, {m_['episodios']} episodios"
            if m_.get("anos") else "no disponible")
    add("Ventana histórica: narrativa frente a dato", vent,
        "aviso" if wprob else ("nd" if not m_.get("anos") else "ok"),
        ("; ".join(wprob) if wprob else
         "la ventana que cita el texto se calcula desde esta misma muestra, no "
         "desde una constante"))

    # --- 4. Trigger consistency ---------------------------------------------
    # ningun disparador puede estar ya activado ni proyectarse a "~0 semanas"
    tprob = []
    for e in (snap.get("que_puede_pasar") or []):
        if e.get("tipo") == "clima":
            if "~0 semanas" in e["texto"]:
                tprob.append("una proyección de clima a ~0 semanas: ya está cruzada")
            continue
        if e.get("ya"):
            tprob.append(f"condición ya cumplida presentada como futura: {e['texto'][:60]}")
    add("Disparadores posibles y no activados", f"{len(tprob)}",
        "aviso" if tprob else "ok",
        ("; ".join(tprob) if tprob else
         "cada condición está sin cruzar y en el sentido en que se mueve su indicador"))

    # --- 5. Narrative consistency -------------------------------------------
    # los numeros que cita la prosa son los del DecisionState, no otros
    nprob = []
    comps_ = snap.get("composites") or {}
    texto = " ".join(snap.get("conclusiones") or []) + " " + " ".join(snap.get("evidencia") or [])
    tl_ = snap.get("postura_general") or {}
    if tl_.get("palabra") and tl_["palabra"] not in texto:
        nprob.append(f"la síntesis no dice la postura calculada ({tl_['palabra']})")
    for nom, blk in (("técnico", comps_.get("tecnico")), ("macro", comps_.get("macro"))):
        if blk and np.isfinite(blk.get("nivel", np.nan)):
            if f"{blk['nivel']:.0f} sobre 100" not in texto:
                nprob.append(f"el compuesto {nom} vale {blk['nivel']:.0f} y la prosa no lo cita así")
    add("La narrativa cita los mismos números que el estado", f"{len(nprob)}",
        "aviso" if nprob else "ok",
        ("; ".join(nprob) if nprob else
         "postura, convicción y compuestos que aparecen en el texto salen del "
         "mismo cálculo que publica el tablero"))

    # --- 6. HTML / PDF consistency ------------------------------------------
    cons_ = snap.get("consistencia")
    if cons_ is not None:
        add("HTML y PDF: mismas conclusiones",
            f"{cons_['coinciden']} de {cons_['total']} presentes en ambos",
            "ok" if cons_["ok"] else "aviso",
            ("cada conclusión se buscó LITERALMENTE en los dos documentos ya "
             "renderizados, no se dio por hecho que comparten capa"
             if cons_["ok"] else
             "; ".join(f"{f['campo']}=«{f['valor']}»" for f in cons_["divergen"])))
    ds_ = snap.get("decision")
    if ds_ is None:
        add("HTML y PDF sobre el mismo DecisionState", "no disponible", "nd",
            "no se construyó la capa de decisión")
    else:
        # SPEC-2P 12: una cobertura parcial NO se marca ✓. Si falta un valor
        # obligatorio, la comprobación no se hizo entera y tiene que decirlo:
        # «? 6 de 8». Un ✓ sobre cobertura incompleta es peor que no comprobar,
        # porque el lector deja de mirar.
        cob = ds_.cobertura()
        req, opt = cob["faltan_requeridos"], cob["faltan_opcionales"]
        base = ("el HTML ya se sirve de esta capa; el PDF consume el mismo "
                "objeto, así que no pueden divergir")
        if req:
            add("HTML y PDF sobre el mismo DecisionState",
                f"? {cob['validados']} de {cob['total']} valores compartidos",
                "aviso",
                f"falta un valor obligatorio del estado ({', '.join(req)}): la "
                f"comprobación no cubre toda la lectura y no puede darse por "
                f"buena")
        else:
            add("HTML y PDF sobre el mismo DecisionState",
                f"{cob['validados']} de {cob['total']} valores compartidos",
                "ok",
                base + (f". Sin dato hoy, y puede faltar legítimamente: "
                        f"{', '.join(opt)}" if opt else ""))

    # --- 7. QA SEMANTICO (SPEC-2P 11) ---------------------------------------
    # Lo de arriba comprueba que las cifras cuadren. Esto comprueba que lo que
    # el documento AFIRMA sea cierto. Se guarda aparte para poder reportarlo
    # como bloque, y se vuelca aqui para que viaje en el mismo tablero.
    sem = semantica.revisar(snap, snap.get("_html_doc"), snap.get("_brief_doc"))
    snap["semantica"] = sem
    # SPEC-7P 18: el tablero del documento solo entiende ok/aviso/nd, asi que
    # un "error" entra como aviso PERO el valor lo dice: un fallo que hace que
    # el documento afirme algo falso no puede leerse igual que una redundancia.
    _VAL = {"ok": "ok", "error": "ERROR", "aviso": "revisar", "nd": "sin datos"}
    _sem_sev = {}
    for f in sem:
        add(f["label"], _VAL[f["estado"]],
            "ok" if f["estado"] == "ok" else ("nd" if f["estado"] == "nd" else "aviso"),
            f["nota"])
        _sem_sev[f["label"]] = f["estado"]

    # SPEC-7P 18: cada fila se clasifica en ERROR / AVISO / INFO. Las semanticas
    # traen la suya declarada; las demas son AVISO salvo las que solo cuentan que
    # el MERCADO discrepa, que son INFO. Lo que pasa no lleva severidad.
    for c in out:
        if c["estado"] == "ok":
            c["sev"] = "ok"
        elif c["label"] in _sem_sev:
            c["sev"] = _sem_sev[c["label"]]
        elif c["label"] in config.QA_INFO or c["estado"] == "nd":
            c["sev"] = "info"
        else:
            c["sev"] = "aviso"
    return out


def _esencial(snap: dict) -> str:
    """UNA línea: qué es lo que más tensiona la lectura de hoy.

    Antes eran dos frases, una de ellas el detalle de la divergencia entre
    pilares, que ya vive entera en la seccion 4. La seccion 1 tiene que caber en
    una pantalla y terminar en una conclusion, no en un parrafo de matices. Si
    lo mas tensionado es ademas la contradiccion destacada, esta linea la nombra
    y remite a la 4 en vez de volver a explicarla.
    """
    adversos = [e for e in snap["extremos"] if e["tipo"] == "adverso"]
    favorables = [e for e in snap["extremos"] if e["tipo"] == "favorable"]
    cs = snap.get("contradicciones") or []
    destacada = cs[0]["key"] if cs else None

    if adversos:
        e = adversos[0]
        resto = (f", y {len(adversos) - 1} más" if len(adversos) > 1 else "")
        ref = (" — la contradicción de hoy; el detalle, en la sección 4"
               if destacada and any(x["label"] == e["label"] for x in cs[:1]) else "")
        return (f"Lo que más tensiona la lectura: {minus(e['label'])} en "
                f"{e['valor']}, {'p%.0f' % e['pct']} a cinco años y "
                f"{e['duracion']} así{resto}{ref}.")
    if favorables:
        e = favorables[0]
        return (f"Nada tensiona la lectura: el extremo más marcado es favorable "
                f"—{minus(e['label'])} en {e['valor']}, {'p%.0f' % e['pct']}—.")
    return ("Ningún indicador está fuera de su banda normal de cinco años: todo "
            "se mueve dentro de lo corriente.")


# ------------------------------------------------- regla de no repetición
# Cada hecho aparece UNA vez. La tasa real en p99 llegó a estar en seis sitios
# del documento -- lo más tensionado, el bloque de contradicción, cuatro
# sub-entradas por clase, el detector de extremos y la tabla del pilar -- y a la
# sexta ya no informa, cansa.
#
# El tablero de la 5 no cuenta: es el libro mayor, y ahí está todo por
# construcción. Se cuentan las menciones NARRATIVAS, y se distingue entre
# desarrollar un hecho (`contenido`) y nombrarlo remitiendo a donde se
# desarrolla (`referencia`). Dos desarrollos del mismo hecho en secciones
# distintas es lo que hay que evitar.
def _menciones(snap: dict) -> dict[str, list[tuple[int, str]]]:
    reg: dict[str, list[tuple[int, str]]] = {}

    def add(key, sec, tipo):
        if key:
            reg.setdefault(key, []).append((sec, tipo))

    cs = snap.get("contradicciones") or []
    destacada = cs[0]["key"] if cs else None

    # 1 · lo esencial: una sola mención, y es referencia si remite a la 4
    adversos = [e for e in snap["extremos"] if e["tipo"] == "adverso"]
    if adversos:
        lbl = adversos[0]["label"]
        k = next((d["key"] for d in config.INDICATORS if d["label"] == lbl), None)
        add(k, 1, "referencia" if k == destacada else "contenido")
    # 1 · la razón de cada inclinación nombra el extremo que la contradice
    for p in snap["postura"]:
        add(p.get("contra_key"), 1, "referencia")
    # 4 · la contradicción destacada, desarrollada
    add(destacada, 4, "contenido")
    # 4 · divergencias intra-pilar y extremos
    for d in snap["div_intra"]["lista"]:
        add(d["alto"], 4, "contenido")
        add(d["bajo"], 4, "contenido")
    for e in snap["extremos"]:
        k = next((d["key"] for d in config.INDICATORS if d["label"] == e["label"]), None)
        add(k, 4, "referencia")
    return reg


def _clases(filas: list[dict]) -> list[dict]:
    """Recuento de votos por clase de activo.

    Es un RECUENTO, no un peso. Dice cuantos indicadores empujan en cada
    direccion y cuales; no dice cuanto comprar de nada, y el reparto entre
    clases no suma a nada.
    """
    out = []
    for ck, meta in config.ASSET_CLASSES.items():
        favor = [f for f in filas if f["votos"].get(ck, 0) > 0]
        contra = [f for f in filas if f["votos"].get(ck, 0) < 0]
        total = len(favor) + len(contra)
        neto = len(favor) - len(contra)
        if total == 0:
            direccion, fuerza = "sin señal", 0.0
        else:
            fuerza = neto / total
            if abs(fuerza) < 0.15:
                direccion = "en tablas"
            else:
                direccion = meta["mas"] if fuerza > 0 else meta["menos"]
        # los que mas pesan en la lectura: los mas alejados de su normalidad
        clave = lambda f: -abs(f["pct"] - 50.0)          # noqa: E731
        out.append(dict(
            key=ck, label=meta["label"], short=meta["short"],
            n_favor=len(favor), n_contra=len(contra), neto=neto,
            fuerza=fuerza, direccion=direccion,
            top_favor=[f["label"] for f in sorted(favor, key=clave)[:3]],
            top_contra=[f["label"] for f in sorted(contra, key=clave)[:3]],
        ))
    out.sort(key=lambda d: -abs(d["fuerza"]))
    return out


def _div_afecta(divs: list[dict], filas: list[dict], ck: str):
    """La divergencia entre pilares que parte a esta clase en dos.

    Una divergencia solo "afecta" a una clase si los dos pilares enfrentados
    votan sobre ella en direcciones opuestas. Que crecimiento y liquidez no
    coincidan es interesante siempre; que no coincidan SOBRE LA DURACION es lo
    que baja la conviccion de la duracion.
    """
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    for d in divs:
        na = sum(f["votos"].get(ck, 0) for f in filas
                 if pilar_de.get(f["key"]) == d["alto"])
        nb = sum(f["votos"].get(ck, 0) for f in filas
                 if pilar_de.get(f["key"]) == d["bajo"])
        if na * nb < 0:
            return d
    return None


def _peso_extremo(semanas: float) -> float:
    """Cuanto pesa un extremo segun cuanto lleva ahi. Uno recien llegado es una
    advertencia; uno de tres meses es informacion que el mercado ya absorbio."""
    for smax, w in config.EXTREMO_EDAD_PESO:
        if semanas <= smax:
            return w
    return config.EXTREMO_PESO_MIN


def _techo_extremo(peso: float) -> str:
    """Techo de conviccion que impone un extremo en contra, segun su peso.
    NUNCA devuelve None: un extremo, por viejo que sea, no deja llegar a alta.
    Reciente (peso alto) la limita a baja; el resto, a media."""
    for pmin, techo in config.EXTREMO_TECHO:
        if peso >= pmin:
            return techo
    return config.EXTREMO_TECHO_DEFECTO


def _min_conv(a: str, b: str) -> str:
    """La mas restrictiva (mas baja) de dos convicciones."""
    return a if config.CONV_ORDEN.get(a, 0) <= config.CONV_ORDEN.get(b, 0) else b


def _coherencia_pilares(ctx: Context, asof: pd.Timestamp,
                        tablero: list[dict]) -> dict[str, dict]:
    """Por pilar: cuantos pares de sus indicadores se contradicen HOY (uno
    favorable, otro adverso, separados por el umbral) frente a los pares
    posibles. Por encima de CONV_PILAR_INCOHERENTE el pilar NO tiene una lectura
    unificada: su agregado se sigue calculando, pero se marca, y una clase que
    depende sobre todo de el no puede tener conviccion alta. Un numero limpio no
    es una lectura si sale de catorce pares que se contradicen."""
    O = ctx.oriented.loc[asof]
    G = config.DIVERGENCE_INTRA_GAP
    out = {}
    for pilar, keys in config.PILLAR_KEYS.items():
        ks = [k for k in keys if k in ctx.oriented.columns and np.isfinite(O[k])]
        n = len(ks)
        posibles = n * (n - 1) // 2
        pares = 0
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                hi, lo = max(float(O[a]), float(O[b])), min(float(O[a]), float(O[b]))
                if hi >= 60 and lo <= 40 and (hi - lo) >= G:
                    pares += 1
        frac = (pares / posibles) if posibles else 0.0
        out[pilar] = dict(pares=pares, posibles=posibles, frac=frac,
                          sin_lectura=frac > config.CONV_PILAR_INCOHERENTE)
    return out


_CONV_LBL = {3: "alta", 2: "media", 1: "baja"}


def _nivel_conviccion(cohesion, consenso, depth, ex_techo, div, pilar_incoh,
                      axis_d1m, incl_sign):
    """El corazon mecanico de la conviccion, aislado para reusarlo en el reporte
    de distribucion. Devuelve (conv, techo, rumbo, motivo); conv None = neutral.

    Cuatro frenos en orden: base por cohesion; TECHO (extremo que contradice A
    ESTA CLASE, divergencia que la parte, pilar del que depende sin lectura
    unificada); RUMBO (el eje relevante moviendose fuerte a favor o en contra).
    El techo del extremo solo aplica si HAY un extremo en contra de esta clase
    -- no por que exista un extremo en cualquier parte del tablero.
    """
    if consenso < config.POSTURA_CONSENSO_MIN or depth < config.POSTURA_MIN_DEPTH:
        return None, None, None, "voto dividido"
    if cohesion < 0:
        return None, None, None, "mayoría invertida"
    if cohesion < config.CONV_EMPATE:
        return None, None, None, "empate efectivo"
    base = (3 if cohesion >= config.CONV_CLARA else
            2 if cohesion >= config.CONV_REPARTIDA else 1)
    techo = 3
    if div:
        techo = min(techo, 2)
    if ex_techo is not None:
        techo = min(techo, config.CONV_ORDEN[ex_techo])
    if pilar_incoh:
        techo = min(techo, 2)
    r = min(base, techo)
    rumbo = None
    if axis_d1m is not None and np.isfinite(axis_d1m) and abs(axis_d1m) > config.CONV_RUMBO_PTS:
        if axis_d1m * incl_sign < 0:
            r -= 1
            rumbo = "contra"
        elif axis_d1m * incl_sign > 0:
            r = min(r + 1, techo)
            rumbo = "favor"
    r = max(r, 1)
    return _CONV_LBL[r], _CONV_LBL[techo], rumbo, None


def _postura(filas: list[dict], clases: list[dict], grupos: dict,
             divs: list[dict], ejes: list[dict], coh: dict,
             recientes: set | None = None) -> tuple[list, list]:
    """Una sola inclinacion por clase de activo, CON SU CONVICCION.

    La escalera es mecanica y tiene cuatro frenos, en este orden:

      1. base por cohesion de VOCES (grupos correlacionados, con signo).
      2. TECHO: un extremo en contra no deja llegar a alta nunca (reciente ->
         baja; viejo -> media); una divergencia que parte la clase, techo media;
         un pilar sin lectura unificada del que la clase depende, techo media.
      3. RUMBO: si el eje relevante se movio fuerte EN CONTRA de la inclinacion,
         baja un nivel; a favor, sube uno (sin pasar del techo). Es la diferencia
         entre "las senales coinciden" y "coinciden y no se estan dando la vuelta".
      4. si nada de eso sostiene una direccion, neutral -- dicho claramente.

    La razon que se guarda aqui es la CORTA (<= 8 palabras, sobre el mercado): es
    lo unico que va a la lectura. El porque de la conviccion (que la limita, el
    rumbo, que indicadores pesan) vive en el tablero.
    """
    cons = {c["key"]: c for c in clases}
    filas_ok = [f for f in filas if np.isfinite(f["pct"])]
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    axis_d1m = {e["key"]: e["d1m"] for e in ejes}

    out = []
    for ck, meta in config.ASSET_CLASSES.items():
        consenso = abs(cons[ck]["fuerza"]) if ck in cons else 0.0
        favor = (cons[ck]["fuerza"] >= 0) if ck in cons else True
        alineados = [f for f in filas_ok
                     if f["votos"].get(ck, 0) != 0 and (f["votos"][ck] > 0) == favor]
        alineados.sort(key=lambda f: -abs(f["pct"] - 50.0))
        contrarios = [f for f in filas_ok
                      if f["votos"].get(ck, 0) != 0 and (f["votos"][ck] > 0) != favor]
        depth = (sum(abs(f["pct"] - 50.0) for f in alineados) / len(alineados)
                 if alineados else 0.0)

        vf, vc = senales.voto_grupos(filas_ok, ck, grupos)
        e_a, e_c = (vf, vc) if favor else (vc, vf)
        cohesion = (e_a - e_c) / (e_a + e_c) if (e_a + e_c) > 0 else 0.0

        extremo = next(
            (f for f in sorted(contrarios, key=lambda f: -abs(f["pct"] - 50.0))
             if f["pct"] <= config.CONTRA_PCT_LOW or f["pct"] >= config.CONTRA_PCT_HIGH),
            None)
        ex_sem = (extremo["extremo_dias"] / 5.0) if extremo is not None else np.nan
        ex_peso = _peso_extremo(ex_sem) if extremo is not None else np.nan
        ex_techo = _techo_extremo(ex_peso) if extremo is not None else None
        div = _div_afecta(divs, filas_ok, ck)

        # pilar dominante entre los alineados, y si no tiene lectura unificada
        cnt: dict[str, int] = {}
        for f in alineados:
            pl = pilar_de.get(f["key"])
            cnt[pl] = cnt.get(pl, 0) + 1
        dom_pilar = max(cnt, key=cnt.get) if cnt else None
        pilar_incoh = bool(dom_pilar and coh.get(dom_pilar, {}).get("sin_lectura"))

        ax, beta = config.CLASS_AXIS.get(ck, (None, 0))
        incl_sign = (beta if favor else -beta)
        axd = axis_d1m.get(ax)
        conv, techo, rumbo, motivo = _nivel_conviccion(
            cohesion, consenso, depth, ex_techo, div is not None, pilar_incoh,
            axd, incl_sign)
        rumbo_eje = ax if rumbo else None
        rumbo_d = float(axd) if rumbo and axd is not None else None

        # --- razon con EVIDENCIA: indicadores concretos con su nivel, no conceptos
        def _ev(f):
            return f"{config.SHORT.get(f['key'], f['label'])} p{f['pct']:.0f}"

        if conv is None:
            direccion, dir_tipo, tier, fuerza_n = "neutral", "neutral", None, 0
            ta = alineados[0] if alineados else None
            tc = contrarios[0] if contrarios else None
            if ta and tc:
                razon = f"{_ev(ta)} a favor, {_ev(tc)} en contra"
            elif ta:
                razon = f"{_ev(ta)}, pero el voto se reparte"
            else:
                razon = "señales repartidas, sin dirección"
        else:
            dir_tipo = "mas" if favor else "menos"
            direccion = meta["mas"] if favor else meta["menos"]
            tier = next((n for u, n in config.POSTURA_TIERS if depth >= u), "leve")
            fuerza_n = {"fuerte": 3, "clara": 2, "leve": 1}[tier]
            favs = ", ".join(_ev(f) for f in alineados[:2]) or "señal débil"
            # lo que la limita, en terminos concretos (prioridad: rumbo, extremo,
            # divergencia, pilar sin lectura). Solo cuando no es alta.
            lim = ""
            if rumbo == "contra" and ax:
                verbo = "cayó" if (rumbo_d or 0) < 0 else "subió"
                lim = (f"; el {config.AXES[ax]['label'].lower()} {verbo} "
                       f"{abs(rumbo_d):.0f} pts en un mes")
            elif extremo is not None:
                lim = f"; en contra: {_ev(extremo)}"
            elif div is not None:
                lim = (f"; {config.PILLARS[div['alto']]['label'].lower()} y "
                       f"{config.PILLARS[div['bajo']]['label'].lower()} no coinciden")
            elif pilar_incoh and dom_pilar:
                lim = f"; {config.PILLARS[dom_pilar]['label'].lower()} sin lectura unificada"
            elif conv != "alta" and contrarios:
                lim = f"; en contra: {_ev(contrarios[0])}"
            razon = favs + lim

        out.append(dict(
            key=ck, label=meta["label"], direccion=direccion, dir_tipo=dir_tipo,
            tier=tier, fuerza_n=fuerza_n, razon=razon,
            conviccion=conv, conv_motivo=motivo,
            e_favor=e_a, e_contra=e_c, cohesion=cohesion,
            techo=techo, rumbo=rumbo, rumbo_eje=rumbo_eje, rumbo_d=rumbo_d,
            contra_key=extremo["key"] if extremo is not None else None,
            contra_label=extremo["label"] if extremo is not None else None,
            contra_pct=extremo["pct"] if extremo is not None else np.nan,
            contra_semanas=ex_sem, contra_peso=ex_peso, contra_cap=ex_techo,
            contra_reciente=bool(extremo is not None and recientes
                                 and extremo["key"] in recientes),
            contra_comun=False,
            div_pilares=((config.PILLARS[div["alto"]]["label"],
                          config.PILLARS[div["bajo"]]["label"])
                         if div is not None else None),
            pilar_incoh=(config.PILLARS[dom_pilar]["label"] if pilar_incoh else None),
            n_favor=cons[ck]["n_favor"] if ck in cons else 0,
            n_contra=cons[ck]["n_contra"] if ck in cons else 0,
            n_a=len(alineados), n_c=len(contrarios),
            drivers=[f["label"] for f in alineados[:3]],
        ))

    # Causa comun: un mismo extremo que limita a 2+ clases se agrupa para el
    # tablero (una nota, no una por fila). La lectura ya no lo muestra.
    porcontra: dict[str, list[dict]] = {}
    for p in out:
        if p["contra_key"]:
            porcontra.setdefault(p["contra_key"], []).append(p)
    notas = []
    for ckey, miembros in porcontra.items():
        if len(miembros) >= 2:
            for p in miembros:
                p["contra_comun"] = True
            m0 = miembros[0]
            notas.append(dict(
                key=ckey, label=m0["contra_label"], pct=m0["contra_pct"],
                semanas=m0["contra_semanas"], peso=m0["contra_peso"],
                cap=m0["contra_cap"], clases=[p["label"] for p in miembros]))
    notas.sort(key=lambda n: -len(n["clases"]))
    return out, notas


def _causa_cambio(p: dict | None) -> str:
    """Clausula corta que nombra el indicador o eje responsable de un cambio de
    inclinacion o de conviccion, para «qué cambió»."""
    if not p:
        return ""
    if p.get("rumbo") and p.get("rumbo_eje"):
        v = "cayó" if (p.get("rumbo_d") or 0) < 0 else "subió"
        return (f"el {config.AXES[p['rumbo_eje']]['label'].lower()} {v} "
                f"{abs(p['rumbo_d'] or 0):.0f} pts en un mes")
    if p.get("contra_label"):
        return f"{minus(p['contra_label'])} en p{p['contra_pct']:.0f}"
    if p.get("div_pilares"):
        a, b = p["div_pilares"]
        return f"{a.lower()} y {b.lower()} no coinciden"
    if p.get("pilar_incoh"):
        return f"{p['pilar_incoh'].lower()} sin lectura unificada"
    return ""


def _junta(xs: list[str]) -> str:
    xs = list(xs)
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " y " + xs[-1]


def _que_puede_pasar(ctx: Context, asof: pd.Timestamp, snap: dict) -> list[dict]:
    """Condicion observable -> consecuencia concreta. NO son escenarios: todas las
    lineas salen de umbrales que el sistema YA usa (extremo, voto, banda de
    estado), invertidos para decir que esta cerca de cruzarse. La proximidad se
    mide en puntos de percentil por cruzar; la linea del clima extrapola el ritmo
    del ultimo mes y lo dice."""
    ev = []
    postura = {p["key"]: p for p in snap["postura"]}
    clabel = {ck: m["label"] for ck, m in config.ASSET_CLASSES.items()}
    filas = {f["key"]: f for pil in snap["tablero"] for f in pil["filas"]}
    win = config.PCT_WINDOW

    def short(k):
        return config.SHORT.get(k, config.INDICATOR_BY_KEY[k]["label"])

    def qval(k, q):
        w = ctx.panel[k].loc[:asof].dropna().tail(win)
        return _fmt(config.INDICATOR_BY_KEY[k]["fmt"], config.INDICATOR_BY_KEY[k]["unit"],
                    float(w.quantile(q / 100.0))) if len(w) else "—"

    # --- (1) SUBE: un extremo que hoy tapa una clase, al salir del extremo
    for c in snap.get("contradicciones") or []:
        capadas = [clabel[fr["clase"]] for fr in c["frentes"]
                   if postura.get(fr["clase"], {}).get("conviccion") in ("media", "baja")
                   and postura.get(fr["clase"], {}).get("contra_cap")]
        if not capadas or not c.get("umbral"):
            continue
        p = c["pct"]
        prox = (p - config.CONTRA_PCT_HIGH) if p >= config.CONTRA_PCT_HIGH else (config.CONTRA_PCT_LOW - p)
        sent = (c.get("sentido") or "").replace("volver ", "")
        ev.append(dict(prox=abs(prox), tipo="sube",
                       texto=(f"Si {short(c['key'])} vuelve {sent} {c['umbral']} "
                              f"(hoy {c['valor']}) → sube la convicción de {_junta(capadas)}")))

    # --- (3) GIRA: un indicador cerca de su frontera de voto (40/60) cuyo cruce
    # cambiaria el signo neto de una clase -> cambio de direccion.
    mapa = config.INDICATOR_ASSET_MAP
    for ck, pc in postura.items():
        net = sum(f["votos"].get(ck, 0) for f in filas.values())
        best = None
        for k, f in filas.items():
            if ck not in mapa.get(k, {}):
                continue
            p = f["pct"]
            if not np.isfinite(p):
                continue
            base = mapa[k][ck]
            cur = base if p >= config.VOTE_HIGH else (-base if p <= config.VOTE_LOW else 0)
            if p < config.VOTE_HIGH and (config.VOTE_HIGH - p) <= 8:
                nv, bnd, sube = base, config.VOTE_HIGH, True
            elif p > config.VOTE_LOW and (p - config.VOTE_LOW) <= 8:
                nv, bnd, sube = -base, config.VOTE_LOW, False
            else:
                continue
            newnet = net - cur + nv
            if newnet != 0 and (net == 0 or (newnet > 0) != (net > 0)):
                prox = abs(bnd - p)
                if best is None or prox < best[0]:
                    nueva = clabel[ck] and (config.ASSET_CLASSES[ck]["mas"] if newnet > 0
                                            else config.ASSET_CLASSES[ck]["menos"])
                    best = (prox, dict(prox=prox, tipo="gira",
                            texto=(f"Si {short(k)} {'sube de' if sube else 'baja de'} "
                                   f"p{bnd:.0f} ({qval(k, bnd)}) → {clabel[ck]} pasa a {nueva}")))
        if best:
            ev.append(best[1])

    # --- (4) CLIMA: extrapolacion del percentil del eje de riesgo a la siguiente
    # banda que implique un estado DISTINTO del actual (evita "neutral en 0
    # semanas" cuando ya estamos en neutral).
    clima = None
    hp = ctx.axes_hist["riesgo"]
    now = float(hp.loc[asof]) if np.isfinite(hp.loc[asof]) else np.nan
    dhp = scoring.delta(hp, config.DELTA_1M, asof)
    estado_hoy = ctx.state.loc[asof]
    if np.isfinite(now) and np.isfinite(dhp) and abs(dhp) >= 3:
        edges = sorted({e for b in config.STATE_BANDS for e in (b[0], b[1])})
        # SOLO umbrales en la DIRECCION del movimiento. Si el eje ya esta mas
        # alla del ultimo umbral hacia el que se mueve, no hay nada que
        # proyectar: cayendo desde p0.6 no se llega a ninguna banda nueva.
        cand = ([e for e in edges if e < now][::-1] if dhp < 0
                else [e for e in edges if e > now])
        for nb in cand:
            nombre = scoring.band_label(nb - 0.1 if dhp < 0 else nb + 0.1)
            if not nombre or nombre == estado_hoy:
                continue
            wks = (nb - now) / (dhp / 4.33)
            # nunca "~0 semanas": si el umbral ya esta cruzado o es inmediato no
            # es una proyeccion. Y por encima del tope no hay plazo estimable.
            if 1 <= wks <= config.CLIMA_MAX_SEMANAS:
                clima = dict(prox=abs(nb - now), tipo="clima",
                             texto=(f"Si el eje de riesgo sigue al ritmo del mes "
                                    f"({dhp:+.0f} pts de percentil) → {nombre} en "
                                    f"~{wks:.0f} semanas (al ritmo actual, no es pronóstico)"))
            break

    ev.sort(key=lambda e: e["prox"])
    vistos, out = set(), []
    for e in ev:
        if e["texto"] in vistos:
            continue
        vistos.add(e["texto"])
        out.append(e)
    # la linea de clima siempre entra, si existe: es la unica prospectiva de plazo
    if clima:
        out = out[:3] + [clima]
    else:
        out = out[:4]
    return out


def _distribucion_conviccion(ctx: Context, asof: pd.Timestamp, grupos: dict) -> dict:
    """Distribucion de convicciones de los ultimos 6 meses, muestreada por semana.
    Es la comprobacion de que la escala funciona: si "alta" no aparece nunca o
    aparece siempre, esta mal calibrada y hay que verlo.

    Aproximada a proposito, para que corra en cada generacion: reutiliza los
    grupos de correlacion de HOY (son estructurales), ignora las divergencias
    entre pilares y trata cualquier extremo en contra como techo "media". Sirve
    para ver la FORMA de la distribucion, no para reproducir cada dia al detalle.
    """
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    G = config.DIVERGENCE_INTRA_GAP
    O = ctx.oriented

    def coh_row(orow):
        out = {}
        for pilar, keys in config.PILLAR_KEYS.items():
            ks = [k for k in keys if k in O.columns and np.isfinite(orow[k])]
            n = len(ks)
            pos = n * (n - 1) // 2
            pares = sum(1 for i, a in enumerate(ks) for b in ks[i + 1:]
                        if max(orow[a], orow[b]) >= 60 and min(orow[a], orow[b]) <= 40
                        and abs(orow[a] - orow[b]) >= G)
            out[pilar] = bool(pos and pares / pos > config.CONV_PILAR_INCOHERENTE)
        return out

    fechas = ctx.pct.loc[:asof].index
    start = asof - pd.Timedelta(days=182)
    sample = [d for d in fechas if d >= start][::5]
    conteo = {"alta": 0, "media": 0, "baja": 0, "neutral": 0}
    por_sem = []
    for wk in sample:
        pr, orow = ctx.pct.loc[wk], O.loc[wk]
        filas = [dict(key=d["key"], label=d["label"], pct=float(pr[d["key"]]),
                      votos=_votos(d["key"], float(pr[d["key"]])))
                 for d in config.INDICATORS if np.isfinite(pr[d["key"]])]
        coh = coh_row(orow)
        clases = _clases(filas)
        cons = {c["key"]: c for c in clases}
        axd = {a: scoring.delta(ctx.axes[a], config.DELTA_1M, wk,
                                suave_actual=config.DELTA_ACTUAL_WIN) for a in config.AXES}
        na = 0
        for ck in config.ASSET_CLASSES:
            favor = (cons[ck]["fuerza"] >= 0) if ck in cons else True
            alin = [f for f in filas if f["votos"].get(ck, 0) != 0
                    and (f["votos"][ck] > 0) == favor]
            contra = [f for f in filas if f["votos"].get(ck, 0) != 0
                      and (f["votos"][ck] > 0) != favor]
            depth = (sum(abs(f["pct"] - 50) for f in alin) / len(alin)) if alin else 0.0
            vf, vc = senales.voto_grupos(filas, ck, grupos)
            e_a, e_c = (vf, vc) if favor else (vc, vf)
            cohv = (e_a - e_c) / (e_a + e_c) if (e_a + e_c) > 0 else 0.0
            exq = any(f["pct"] <= config.CONTRA_PCT_LOW or f["pct"] >= config.CONTRA_PCT_HIGH
                      for f in contra)
            cnt = {}
            for f in alin:
                cnt[pilar_de[f["key"]]] = cnt.get(pilar_de[f["key"]], 0) + 1
            dom = max(cnt, key=cnt.get) if cnt else None
            ax, beta = config.CLASS_AXIS.get(ck, (None, 0))
            conv, _t, _r, _m = _nivel_conviccion(
                cohv, abs(cons[ck]["fuerza"]) if ck in cons else 0.0, depth,
                "media" if exq else None, False, bool(dom and coh.get(dom)),
                axd.get(ax), beta if favor else -beta)
            conteo[conv or "neutral"] += 1
            if conv == "alta":
                na += 1
        por_sem.append(na)
    return dict(conteo=conteo, por_sem=por_sem, semanas=len(sample),
                aprox=True)


# ===================================================================
#  NOTA DE RESEARCH: composites, prosa, serie del gráfico, posicionamiento
# ===================================================================
# Dos compuestos, al estilo weight-of-the-evidence: el TECNICO (tendencia,
# volatilidad, credito -- el eje de riesgo) y el MACRO/FUNDAMENTAL (crecimiento,
# liquidez, inflacion, posicionamiento). El texto dice cual manda y cual
# atempera, no los pone a pelear.
TECNICO_PILARES = ["credito", "volatilidad", "tendencia"]
MACRO_PILARES = ["crecimiento", "liquidez", "inflacion", "posicionamiento"]
# El nombre del campo EN PROSA, el mismo que llevan sus etiquetas. Research
# conserva el termino tecnico; la prosa de la capa PM no puede llamarlo de
# otra manera que la columna que el lector acaba de leer.
_CONF = config.CONVICCION_PM.lower()
RISK_ON = {"rv": +1, "cred": +1, "cicl": +1, "mp": +1}  # que direccion es "tomar riesgo"


def _lab(estado_nivel: float) -> str:
    return ("favorable" if estado_nivel >= 55 else
            "adverso" if estado_nivel <= 45 else "neutral")


def _bloque(filas_de: dict, pilares: list[str], n: int = 3,
            no_persistentes: set | None = None) -> dict:
    """Un compuesto sobre un conjunto de pilares: nivel medio, cuántos
    favorables de cuántos, y los indicadores que MANDAN en su lado, para
    nombrarlos. Solo mira los pilares que se le pasan -- nunca todo el tablero,
    para que una afirmación no se sostenga con un indicador ajeno solo porque
    esté más extremo."""
    fs = [f for p in pilares for f in filas_de.get(p, []) if np.isfinite(f["pct"])]
    if not fs:
        return dict(n=0, fav=0, adv=0, nivel=np.nan, lead=[], lect="sin dato",
                    pilares=list(pilares))
    fav = [f for f in fs if f["lectura"] == "favorable"]
    adv = [f for f in fs if f["lectura"] == "adverso"]
    nivel = float(np.mean([f["op"] for f in fs]))
    # los que mandan en el lado del compuesto: si va favorable, los más
    # favorables; si adverso, los más adversos. Lo extremo ORDENA dentro del
    # pilar; no selecciona ni cuela el outlier en contra.
    # Un extremo RECIENTE no puede encabezar la evidencia (SPEC 7.1): se le
    # ordena como si estuviera en el borde de su banda, no en su extremo.
    # SPEC 7.1: un extremo RECIENTE no es evidencia. Degradarlo en el orden no
    # bastaba --seguia colandose en el lead--, asi que se excluye. Solo si TODOS
    # los candidatos fueran recientes se usan, y entonces se ordenan como si
    # estuvieran en el borde de su banda, no en su extremo.
    npers = no_persistentes or set()
    cand = [f for f in fs if f["key"] not in npers] or fs

    def clave(f):
        op = f["op"]
        if f["key"] in npers:
            op = min(max(op, config.EXTREME_LOW), config.EXTREME_HIGH)
        return op if nivel < 50 else -op

    lead = sorted(cand, key=clave)[:n]
    return dict(n=len(fs), fav=len(fav), adv=len(adv), nivel=nivel,
                lead=lead, lect=_lab(nivel), pilares=list(pilares))


def _relacion(tec_nivel: float, mac_nivel: float) -> str:
    """Confirma / atempera / contradice, por UMBRAL explícito. Se mide el
    acuerdo del bloque macro con el técnico -- cuánto apunta al mismo lado, en
    0-100 (100 = coincide del todo, 50 = neutral)."""
    if not (np.isfinite(tec_nivel) and np.isfinite(mac_nivel)):
        return "acompaña"
    acuerdo = mac_nivel if tec_nivel >= 50 else 100 - mac_nivel
    if acuerdo > config.WOE_CONFIRMA:
        return "confirma"
    if acuerdo >= config.WOE_ATEMPERA:
        return "atempera"
    return "contradice"


def _split_macro(filas_de: dict, pilares: list[str], n: int = 3) -> tuple:
    """Separa un compuesto en su lado favorable y su lastre A NIVEL DE PILAR (no
    de indicador suelto): solo hay lastre si un pilar entero está por debajo de
    50 y OTRO por encima -- un compuesto realmente partido. Devuelve (pilar del
    lastre o None, leads del lado favorable)."""
    op_pil = {}
    for p in pilares:
        ops = [f["op"] for f in filas_de.get(p, []) if np.isfinite(f["pct"])]
        if ops:
            op_pil[p] = float(np.mean(ops))
    fav_pilares = [p for p, v in op_pil.items() if v >= 50]
    drag_pilares = [(p, v) for p, v in op_pil.items() if v < 50]
    if not (fav_pilares and drag_pilares):
        return None, []
    drag = min(drag_pilares, key=lambda kv: kv[1])[0]
    fs = [f for p in fav_pilares for f in filas_de.get(p, []) if np.isfinite(f["pct"])]
    fav_leads = sorted(fs, key=lambda f: -f["op"])[:n]
    return drag, fav_leads


def _composites(ctx: Context, asof, tablero: list[dict],
                persistencia: dict | None = None) -> dict:
    """Lectura de cada compuesto y su relación, para el peso de la evidencia.
    Además, el lead PERTINENTE de cada afirmación: solo indicadores del pilar al
    que la afirmación se refiere. El técnico es el eje de riesgo; el macro, el
    eje de ciclo -- inflación y posicionamiento no entran (no son evidencia de
    los ejes, solo contexto)."""
    filas_de = {pil["key"]: pil["filas"] for pil in tablero}
    # extremos que aun no llevan bastante tiempo: no encabezan ninguna lista
    # La lista de RECIENTES no se recalcula aqui: es la propiedad que ya publico
    # el snapshot. Recalcularla en cada selector es como se escapo tres veces.
    npers = {k for k, v in (persistencia or {}).items() if v.get("reciente")}
    tec = _bloque(filas_de, config.WOE_TECNICO_PILARES, no_persistentes=npers)
    mac = _bloque(filas_de, config.WOE_MACRO_PILARES, no_persistentes=npers)
    mac["drag_pilar"], mac["fav_leads"] = _split_macro(filas_de, config.WOE_MACRO_PILARES)
    rel = _relacion(tec["nivel"], mac["nivel"])
    # una afirmación, un pilar: cada frase solo cita de lo suyo.
    afirm = {name: _bloque(filas_de, pil, no_persistentes=npers)
             for name, pil in config.AFIRMACION_PILARES.items()}
    # registro para la comprobación "citas fuera de su pilar".
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    citas = [("peso de la evidencia · técnico", list(config.WOE_TECNICO_PILARES),
              [f["key"] for f in tec["lead"]]),
             ("peso de la evidencia · macro", list(config.WOE_MACRO_PILARES),
              [f["key"] for f in mac["lead"]])]
    for name, pil in config.AFIRMACION_PILARES.items():
        citas.append((f"síntesis · {name}", list(pil),
                      [f["key"] for f in afirm[name]["lead"]]))
    return dict(tecnico=tec, macro=mac, relacion=rel, afirm=afirm,
                citas=citas, pilar_de=pilar_de, no_persistentes=sorted(npers))


def _tilt(postura: list[dict], rel: str | None = None) -> dict:
    """Inclinación agregada de la cartera: pro-riesgo, defensiva o mixta, y la
    convicción dominante entre las clases con dirección. Si el peso de la
    evidencia solo atempera (o contradice), la convicción agregada NO puede ser
    tan alta como si confirmara: la palabra y la convicción van juntas."""
    score = 0
    convs = []
    for p in postura:
        if p["dir_tipo"] == "neutral":
            continue
        signo = +1 if p["dir_tipo"] == "mas" else -1
        ro = RISK_ON.get(p["key"])
        if ro is None:
            continue
        score += signo * ro * config.CONV_ORDEN.get(p["conviccion"], 0)
        convs.append(p["conviccion"])
    palabra = ("pro-riesgo" if score > 0 else "defensiva" if score < 0 else "mixta")
    orden = ["alta", "media", "baja"]
    dom = next((c for c in orden if convs.count(c) == max(convs.count(x) for x in orden)),
               "media") if convs else "baja"
    techo = config.WOE_TECHO.get(rel) if rel else None
    if techo:
        rank = {"baja": 1, "media": 2, "alta": 3}
        if rank.get(dom, 2) > rank.get(techo, 3):
            dom = techo
    return dict(palabra=palabra, conviccion=dom, score=score, techo=techo)


def _postura_divergencias(snap: dict) -> dict:
    """Clases cuya inclinación difiere de la postura general (pro-riesgo /
    defensiva). Renta variable y duración son las dos que definen cómo se lee una
    postura -- «¿pro-riesgo pero neutral en bolsa?» es la primera pregunta del
    lector, y si ocurre la síntesis tiene que responderla."""
    comps = snap.get("composites") or {}
    tl = _tilt(snap["postura"], comps.get("relacion"))
    sgn = {"pro-riesgo": 1, "defensiva": -1}.get(tl["palabra"], 0)
    carriers, divergentes = [], []
    if sgn:
        for p in snap["postura"]:
            paso = _paso(p["key"], p["dir_tipo"], p.get("tier"))
            s = (paso > 0) - (paso < 0)          # lado de riesgo de la clase
            (carriers if s == sgn else divergentes).append(p)
    return dict(palabra=tl["palabra"], signo=sgn, conviccion=tl["conviccion"],
                carriers=carriers, divergentes=divergentes)


def _ev_prosa(f: dict) -> str:
    """Un indicador nombrado con su nivel, para la prosa."""
    s = config.SHORT.get(f["key"], f["label"])
    txt = f"{s} en {f['valor']}"
    if np.isfinite(f["pct"]) and (f["pct"] >= 95 or f["pct"] <= 5):
        txt += (" (máximo de cinco años)" if f["op"] >= 50 and f["pct"] >= 95
                else " (mínimo de cinco años)" if f["op"] >= 50
                else "")
    return txt


def _tension_contexto(snap: dict):
    """Cuando no hay tension principal, el mejor candidato descartado puede
    citarse -- DICHO COMO CONTEXTO (SPEC 3.1). Se descarta por dos motivos
    distintos y conviene no confundirlos: o el extremo es RECIENTE (no
    persistente), o vive en un pilar que no entra en ningun eje."""
    if _tension_eje(snap) is not None:
        return None
    cs = snap.get("contradicciones") or []
    # primero, un extremo de eje todavia sin persistencia: es lo mas relevante
    for c in cs:
        if c.get("eje") and not c.get("persistente"):
            return dict(c, motivo_contexto="reciente")
    for c in cs:
        if not c.get("eje"):
            return dict(c, motivo_contexto="fuera de eje")
    return None


def _tension_eje(snap: dict):
    """El INDICADOR EN CONTRA: la contradicción destacada, SIEMPRE de un pilar que
    entra en un eje (relevancia primero). Posicionamiento e inflación no pueden
    serlo -- por diseño no entran en ningún eje-- aunque sí
    aparezcan como contexto en el detalle."""
    for c in (snap.get("contradicciones") or []):
        if c.get("eje") and c.get("persistente"):
            return c
    return None


def _condicional(snap: dict, comps: dict, c: dict | None, V: "Verificador") -> str:
    """De que depende la lectura. Se DERIVA del mecanismo real de hoy, no es una
    constante: una lectura defensiva por deterioro macro no depende de lo mismo
    que una pro-riesgo con el costo del capital tensionando.

    REGLA DE DIRECCION (SPEC-2P 10). La condicion que se enuncia tiene que ser
    aquella cuyo INCUMPLIMIENTO debilitaria la lectura:

      - un hecho que APOYA la postura la sostiene mientras PERSISTA;
      - un hecho que la CONTRADICE la sostiene mientras NO SE IMPONGA.

    Decirlo al reves invierte el mecanismo. «La lectura defensiva depende de que
    el deterioro del crecimiento no se profundice» era exactamente eso: si el
    crecimiento empeora, una lectura defensiva se REFUERZA; lo que la tumbaria
    es que el crecimiento repunte.

    La rama elegida se publica en `snap["condicional_meta"]` con el hecho, si
    apoya o contradice y en que sentido esta escrita, para que la comprobacion
    verifique la RELACION y no el texto.
    """
    pg = (snap.get("postura_general") or {}).get("palabra")
    er = (comps.get("afirm") or {}).get("economia_real") or {}
    crec = er.get("lect")
    concepto = (config.CONCEPTO_PILAR.get(c["pilar"], config.TENSION_INDICADOR.lower())
                if c else None)

    def apoya(lect) -> bool:
        """Si ese hecho empuja hacia el mismo lado que la postura publicada."""
        return ((lect == "favorable" and pg == "pro-riesgo") or
                (lect == "adverso" and pg == "defensiva"))

    def sella(hecho, a, sentido, texto, rama) -> str:
        snap["condicional_meta"] = dict(hecho=hecho, apoya=a, sentido=sentido,
                                        texto=texto, rama=rama, postura=pg)
        V.registra("condicional", rama)
        return texto

    # 1 · el crecimiento, cuando tiene lectura clara: es el hecho que mas manda
    if crec in ("favorable", "adverso") and pg in ("pro-riesgo", "defensiva"):
        if apoya(crec):
            if pg == "pro-riesgo":
                txt = (f"que el crecimiento siga superando a {concepto}" if c
                       else "que el crecimiento siga firme")
            else:
                txt = "que el crecimiento no repunte"
            return sella("crecimiento", True, "persiste", txt,
                         f"{pg}/crecimiento-a-favor")
        txt = ("que la mejora del crecimiento no se consolide" if crec == "favorable"
               else "que la debilidad del crecimiento no se consolide")
        return sella("crecimiento", False, "no_se_impone", txt,
                     f"{pg}/crecimiento-en-contra")

    # 2 · la tension: por construccion CONTRADICE a su clase, asi que la lectura
    #     aguanta mientras no acabe imponiendose. «Que no se dé la vuelta» decia
    #     lo contrario: si una contradiccion se da la vuelta, deja de contradecir
    #     y la lectura MEJORA.
    if c:
        return sella(c["key"], False, "no_se_impone",
                     f"que {concepto} no acabe imponiéndose", "tension")

    # 3 · sin tension: el bloque tecnico, y solo si acompaña a la postura
    tec = (comps.get("tecnico") or {}).get("lect")
    if apoya(tec):
        return sella("tecnico", True, "persiste",
                     "que la tendencia y el crédito no se den la vuelta",
                     "sin-tension/tecnico")
    return sella(None, None, "neutro",
                 "que ninguna de las dos caras de la evidencia se imponga",
                 "sin-tension/neutro")


def _conclusiones(snap: dict, comps: dict, V: "Verificador") -> list[str]:
    """La caja de conclusiones: 3-4 afirmaciones completas, deducidas del
    tablero. Cada una se sostiene sola."""
    t, r = snap["titular"], snap["riesgo"]
    out = []

    # 1 · clima
    d = r.get("d1m")
    causa = snap.get("clima_causa") or []
    por = f", arrastrado por {_junta(causa)}" if causa else ""
    en_extremo = V.clima_en_extremo()
    peor = (t["estado"] == config.STATE_BANDS[0][2] and d < 0) or            (t["estado"] == config.STATE_BANDS[-1][2] and d > 0)
    if not np.isfinite(d) or abs(d) < 3:
        V.registra("clima", "estable")
        out.append(f"El clima de riesgo sigue {t['estado']} (p{r['hist_pct']:.0f}) y estable "
                   f"en el último mes.")
    elif en_extremo and peor:
        # "sigue X pero se deteriora" no vale cuando X ya ES el extremo: no hay
        # sitio al que deteriorarse. Se dice que PROFUNDIZA.
        V.registra("clima", "extremo-profundiza")
        out.append(f"El clima de riesgo profundiza el {t['estado']} "
                   f"(p{r['hist_pct']:.0f}): {abs(d):.0f} puntos más en un mes{por}.")
    elif en_extremo:
        V.registra("clima", "extremo-alivia")
        verbo = "empieza a aliviarse" if d > 0 else "empieza a enfriarse"
        out.append(f"El clima de riesgo sigue en {t['estado']} (p{r['hist_pct']:.0f}) "
                   f"pero {verbo}: {d:+.0f} puntos en un mes{por}.")
    else:
        V.registra("clima", "normal")
        verbo = "se deteriora" if d < 0 else "mejora"
        out.append(f"El clima de riesgo sigue {t['estado']} (p{r['hist_pct']:.0f}) pero "
                   f"{verbo}: {d:+.0f} puntos en un mes{por}.")

    # 2 · economía real -- SOLO crecimiento y actividad, no inflación ni
    # posicionamiento (que ni siquiera entran en ningún eje).
    er = comps["afirm"]["economia_real"]
    lead = ", ".join(_ev_prosa(f) for f in er["lead"][:3]) if er["lead"] else "señales mixtas"
    firme = ("firme" if er["lect"] == "favorable" else
             "floja" if er["lect"] == "adverso" else "en terreno mixto")
    sost = ("sostiene" if er["lect"] == "favorable" else
            "no sostiene" if er["lect"] == "adverso" else "solo acompaña a medias")
    out.append(f"La economía real sigue {firme} —{lead}— y {sost} la inclinación cíclica.")

    # 3 · el INDICADOR EN CONTRA -- nombrado por el pilar en el que vive.
    # RELEVANCIA primero: solo un pilar que entra en un eje puede darlo. No se
    # llama "tensión dominante": esa es la divergencia entre pilares, y son dos
    # cosas distintas que compartían nombre.
    ten = _tension_eje(snap)
    if ten:
        c = ten
        dur = _duracion(c.get("dias", 0))
        frase = config.TENSION_FRASE.get(
            c["pilar"], f"El {config.TENSION_INDICADOR.lower()}")
        lado = "máximo" if c["pct"] >= 50 else "mínimo"
        # La cola se VERIFICA contra la tendencia real (snap["trend"], calculada
        # sobre el S&P frente a su media de 200 dias). Decir "sin que la
        # tendencia se de la vuelta" el 16/03/2020 --con la bolsa un 30% abajo--
        # es falso: la plantilla asumia mercado alcista.
        cola = {
            "alcista": "sin que, de momento, la tendencia de la bolsa se dé la vuelta",
            "bajista": "con la tendencia de la bolsa ya girada a la baja",
            "lateral": "con la bolsa sin una tendencia clara",
        }.get(snap.get("trend", "lateral"), "con la bolsa sin una tendencia clara")
        out.append(f"{frase}: {config.SHORT.get(c['key'], c['label'])} lleva {dur} en su "
                   f"{lado} de cinco años ({c['valor']}) {cola}.")

    # 4 · conclusión, con la convicción coherente con el peso de la evidencia.
    tl = _tilt(snap["postura"], comps.get("relacion"))
    out.append(f"Mantenemos inclinación {tl['palabra']} con {_CONF} {tl['conviccion']}; "
               f"la lectura depende de {_condicional(snap, comps, ten, V)}.")

    # 5 · coherencia: si renta variable o duración -- las dos clases que definen
    # cómo se lee una postura -- van al contrario que la postura general, se dice
    # aquí, antes de que el lector lo pregunte.
    div = _postura_divergencias(snap)
    clave_def = [p for p in div["divergentes"] if p["key"] in ("rv", "dur")]
    if div["signo"] and clave_def:
        carriers = (_junta([config.CLASS_CORTO[p["key"]] for p in div["carriers"]])
                    or "el resto de las clases")
        neut = [p for p in clave_def if p["dir_tipo"] == "neutral"]
        opp = [p for p in clave_def if p["dir_tipo"] != "neutral"]
        partes = []
        if neut:
            partes.append(f"en {_junta([config.CLASS_CORTO[p['key']] for p in neut])} las "
                          f"señales no alcanzan el umbral de {_CONF} y quedamos neutrales")
        if opp:
            partes.append(f"en {_junta([config.CLASS_CORTO[p['key']] for p in opp])} la señal "
                          f"apunta al contrario")
        linea = (f"La postura {div['palabra']} se expresa hoy por {carriers}; "
                 f"{'; '.join(partes)}.")
        # SPEC 12: se publica en el estado para que HTML y PDF la escriban desde
        # el MISMO sitio. Vivia solo dentro de la caja de sintesis del HTML, y
        # al reescribir la pagina 1 del brief con la prosa del peso de la
        # evidencia se perdio sin que ningun check lo notara: el check miraba el
        # campo, no el documento.
        snap["coherencia"] = linea
        out.append(linea)
    return out


def _evidencia(snap: dict, comps: dict, V: "Verificador") -> list[str]:
    """El peso de la evidencia: 3-4 párrafos encadenados. Nombra indicadores con
    su nivel; nunca habla del documento, solo del mercado."""
    tec, mac, rel = comps["tecnico"], comps["macro"], comps["relacion"]
    P = []

    # P1 · técnico / tendencia y riesgo
    lead_t = _junta([_ev_prosa(f) for f in tec["lead"][:3]]) if tec["lead"] else "pocas señales limpias"
    lado = ("a tomar riesgo" if tec["lect"] == "favorable" else
            "a la defensiva" if tec["lect"] == "adverso" else "sin un sesgo claro")
    dom = max(tec["fav"], tec["adv"])
    P.append(
        f"Los indicadores de tendencia, volatilidad y crédito apuntan {lado}: "
        f"{dom} de {tec['n']} se leen del mismo lado, con {lead_t} a la cabeza. "
        f"El compuesto técnico está en un nivel {tec['lect']} ({tec['nivel']:.0f} sobre 100).")

    # P2 · macro / ciclo, y su relación con el técnico POR UMBRAL (65/45). El
    # número lleva el peso, y cuando solo atempera se nombra qué lo frena: no se
    # citan indicadores favorables y se dice "atempera" sin explicar por qué.
    lead_m = _junta([_ev_prosa(f) for f in mac["lead"][:3]]) if mac["lead"] else "señales dispersas"
    niv = mac["nivel"]
    if rel == "confirma":
        cuerpo = (f"con {lead_m}, el compuesto —en {niv:.0f} sobre 100— empuja del mismo "
                  f"lado que el técnico y refuerza la lectura")
    elif rel == "atempera":
        drag_pil = mac.get("drag_pilar")
        if drag_pil:  # compuesto realmente partido: un pilar tira, otro pesa
            fav = _junta([_ev_prosa(f) for f in (mac.get("fav_leads") or [])[:3]]) or lead_m
            drag = config.CONCEPTO_PILAR.get(drag_pil, "el otro lado")
            pesa = config.concepto_verbo(drag_pil, "pesa", "pesan")
            cuerpo = (f"{fav} empujan al lado favorable, pero {drag} {pesa} en contra y deja "
                      f"el compuesto en {niv:.0f} sobre 100: modera la lectura técnica en "
                      f"vez de confirmarla, y es la razón para no subir la {_CONF}")
        else:  # mismo lado que el técnico, pero más flojo
            cuerpo = (f"con {lead_m}, el compuesto —en {niv:.0f} sobre 100, del lado del "
                      f"técnico pero más flojo— modera la lectura en vez de reforzarla, y "
                      f"es la razón para no subir la {_CONF}")
    elif rel == "contradice":
        cuerpo = (f"con {lead_m}, el compuesto —en {niv:.0f} sobre 100— apunta al lado "
                  f"contrario que el técnico: abre la principal divergencia y obliga a "
                  f"bajar la {_CONF}")
    else:
        cuerpo = (f"con {lead_m}, el compuesto —en {niv:.0f} sobre 100— no manda en "
                  f"ninguna dirección")
    P.append(f"El bloque macro y fundamental {rel} esa lectura: {cuerpo}.")

    # P3 · el indicador en contra (de eje), con su mecanismo si es cierto hoy
    ten = _tension_eje(snap)
    if ten:
        c = ten
        # El mecanismo se elige por el LADO del extremo del propio indicador, y
        # se descarta si asume un mercado que hoy no es el que hay.
        mec = ""
        if _mecanismo_ok(c["key"], snap.get("trend", "lateral")):
            mec = V.elige(f"mecanismo:{c['key']}",
                          config.CONTRA_OBSERVAR.get(c["key"], {}),
                          V.lado_extremo(c["key"])) or ""
        else:
            V.omitidas.append(f"mecanismo:{c['key']} [asume mercado alcista]")
        mec = mec.replace("y si ", "").strip()
        mec = (mec[0].upper() + mec[1:]) if mec else ""
        # Dos conceptos, dos nombres, y los mismos en cabecera y prosa. Llamar
        # "tensión principal" a un indicador suelto mientras la cabecera llamaba
        # igual a una divergencia entre pilares es lo que hizo que la página 1
        # dijera dos cosas distintas.
        base = (f"El {config.TENSION_INDICADOR.lower()} es "
                f"{config.SHORT.get(c['key'], c['label'])}, hoy en "
                f"{c['valor']} (p{c['pct']:.0f}), que contradice la inclinación de "
                f"{c['n_frentes']} clase{'s' if c['n_frentes'] != 1 else ''}.")
        P.append(f"{base} {mec}." if mec else base)

    # P4 · conclusión deducida, con la convicción coherente con la relación.
    tl = _tilt(snap["postura"], rel)
    P.append(
        f"El peso de la evidencia, por tanto, sostiene una inclinación {tl['palabra']} "
        f"con {_CONF} {tl['conviccion']}: el compuesto técnico manda, el macro lo "
        f"{rel}, y la lectura se apoya en {_condicional(snap, comps, ten, V)}.")
    return P


def _serie_puntuacion(ctx: Context, asof: pd.Timestamp, anios: int = 5) -> dict:
    """Serie mensual del nivel de los ejes (riesgo y ciclo) para el gráfico, con
    los puntos justos para un SVG ligero. El nivel es 0-100, favorable arriba."""
    inicio = asof - pd.DateOffset(years=anios)
    out = {}
    for a in config.AXES:
        s = ctx.axes[a].loc[inicio:asof].dropna()
        if s.empty:
            out[a] = []
            continue
        # El remuestreo mensual sella cada punto a FIN DE MES. Para el mes en
        # curso eso cae DESPUES de la fecha del snapshot, y ademas devolvia el
        # cierre CRUDO mientras el panel del eje muestra el nivel SUAVIZADO: el
        # grafico terminaba en 5 y el panel decia 10/100 el mismo dia. El ultimo
        # punto se ancla a `asof` con el MISMO nivel que publica el panel.
        m = s.resample("ME").last().dropna()
        pts = [(d, float(v)) for d, v in m.items() if d <= asof]
        nivel = scoring.nivel(ctx.axes[a], asof)
        if np.isfinite(nivel):
            if pts and pts[-1][0] == asof:
                pts[-1] = (asof, float(nivel))
            else:
                pts.append((asof, float(nivel)))
        out[a] = pts
    return dict(series=out, desde=inicio, hasta=asof)


def _postura_en(ctx: Context, D, grupos: dict) -> dict:
    """Postura (dirección y convicción por clase) en una fecha pasada, para la
    columna «mes anterior». Aproximada de forma consistente con la distribución:
    reutiliza los grupos de hoy, la coherencia de la fecha, sin divergencias, y
    trata cualquier extremo en contra como techo media."""
    idx = ctx.panel.index
    prev = idx[idx <= pd.Timestamp(D)]
    if len(prev) == 0:
        return {}
    D = prev[-1]
    pr, orow = ctx.pct.loc[D], ctx.oriented.loc[D]
    filas = [dict(key=d["key"], label=d["label"], pct=float(pr[d["key"]]),
                  votos=_votos(d["key"], float(pr[d["key"]])))
             for d in config.INDICATORS if np.isfinite(pr[d["key"]])]
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    G = config.DIVERGENCE_INTRA_GAP
    coh = {}
    for pilar, keys in config.PILLAR_KEYS.items():
        ks = [k for k in keys if k in ctx.oriented.columns and np.isfinite(orow[k])]
        pos = len(ks) * (len(ks) - 1) // 2
        pares = sum(1 for i, a in enumerate(ks) for b in ks[i + 1:]
                    if max(orow[a], orow[b]) >= 60 and min(orow[a], orow[b]) <= 40
                    and abs(orow[a] - orow[b]) >= G)
        coh[pilar] = bool(pos and pares / pos > config.CONV_PILAR_INCOHERENTE)
    axd = {a: scoring.delta(ctx.axes[a], config.DELTA_1M, D,
                            suave_actual=config.DELTA_ACTUAL_WIN) for a in config.AXES}
    clases = _clases(filas)
    cons = {c["key"]: c for c in clases}
    out = {}
    for ck in config.ASSET_CLASSES:
        favor = (cons[ck]["fuerza"] >= 0) if ck in cons else True
        alin = [f for f in filas if f["votos"].get(ck, 0) != 0 and (f["votos"][ck] > 0) == favor]
        contra = [f for f in filas if f["votos"].get(ck, 0) != 0 and (f["votos"][ck] > 0) != favor]
        depth = (sum(abs(f["pct"] - 50) for f in alin) / len(alin)) if alin else 0.0
        vf, vc = senales.voto_grupos(filas, ck, grupos)
        e_a, e_c = (vf, vc) if favor else (vc, vf)
        cohv = (e_a - e_c) / (e_a + e_c) if (e_a + e_c) > 0 else 0.0
        exq = any(f["pct"] <= config.CONTRA_PCT_LOW or f["pct"] >= config.CONTRA_PCT_HIGH
                  for f in contra)
        cnt = {}
        for f in alin:
            cnt[pilar_de[f["key"]]] = cnt.get(pilar_de[f["key"]], 0) + 1
        dom = max(cnt, key=cnt.get) if cnt else None
        ax, beta = config.CLASS_AXIS.get(ck, (None, 0))
        conv, _t, _r, _m = _nivel_conviccion(
            cohv, abs(cons[ck]["fuerza"]) if ck in cons else 0.0, depth,
            "media" if exq else None, False, bool(dom and coh.get(dom)),
            axd.get(ax), beta if favor else -beta)
        meta = config.ASSET_CLASSES[ck]
        direccion = "neutral" if conv is None else (meta["mas"] if favor else meta["menos"])
        tier = (None if conv is None
                else next((n for u, n in config.POSTURA_TIERS if depth >= u), "leve"))
        out[ck] = dict(direccion=direccion, conviccion=conv, tier=tier,
                       dir_tipo=("neutral" if conv is None else ("mas" if favor else "menos")))
    return out


def _senal_bloque(filas: list[dict], ck: str, pilares: list[str], meta: dict) -> str:
    """Hacia dónde vota un grupo de pilares sobre una clase, EN LOS TÉRMINOS DE
    LA CLASE (corta/larga, sobre/infra...), con intensidad. Devuelve
    'texto|marcador' para que el render coloree. No dice «a favor/en contra»,
    que sería ambiguo respecto a qué."""
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATOR_BY_KEY.values()}
    fav = sum(1 for f in filas if pilar_de.get(f["key"]) in pilares and f["votos"].get(ck, 0) > 0)
    con = sum(1 for f in filas if pilar_de.get(f["key"]) in pilares and f["votos"].get(ck, 0) < 0)
    neto = fav - con
    if fav == 0 and con == 0:
        return "sin señal|0"
    if neto == 0:
        return "mixto|~"
    lado = meta["mas_s"] if neto > 0 else meta["menos_s"]
    fuerte = abs(neto) >= 2
    return f"{lado}|{'++' if neto > 0 and fuerte else '+' if neto > 0 else '--' if fuerte else '-'}"


def _sig_dir(cell: str) -> int:
    """El signo de una celda de señales 'texto|marcador': +1 hacia la clase,
    -1 en contra, 0 si mixto o sin señal."""
    m = (str(cell).split("|", 1) + ["0"])[1]
    return +1 if m in ("++", "+") else -1 if m in ("--", "-") else 0


def _freno_corto(p: dict) -> str:
    """Qué frena a una clase, en una línea: el extremo en contra si lo hay; si
    no, el rumbo del eje, la divergencia o el pilar sin lectura."""
    if p.get("contra_key") and np.isfinite(p.get("contra_pct", np.nan)):
        s = config.SHORT.get(p["contra_key"], p.get("contra_label") or p["contra_key"])
        cola = ", reciente" if p.get("contra_reciente") else ""
        return f"limitado por {s} en p{p['contra_pct']:.0f}{cola}"
    if p.get("rumbo") == "contra" and p.get("rumbo_eje"):
        dd = p.get("rumbo_d") or 0
        verbo = "cayó" if dd < 0 else "subió"
        return (f"el {config.AXES[p['rumbo_eje']]['label'].lower()} {verbo} "
                f"{abs(dd):.0f} pts en un mes")
    if p.get("div_pilares"):
        a, b = p["div_pilares"]
        return f"{a.lower()} y {b.lower()} no coinciden"
    if p.get("pilar_incoh"):
        return f"{p['pilar_incoh'].lower()} sin lectura unificada"
    return "señales por debajo del umbral de convicción"


def _nota_fila(p: dict, tec_cell: str, mac_cell: str) -> str:
    """La columna NOTA de la tabla de posicionamiento. Solo se llena cuando la
    conclusión no se deduce de las señales, o cuando las técnicas y las macro
    discrepan (que es información, no ruido). Si ambas coinciden y la conclusión
    sale sola, queda vacía."""
    ts, ms = _sig_dir(tec_cell), _sig_dir(mac_cell)
    # discrepancia entre bloques: una cosa dicen las técnicas y otra las macro.
    if ts and ms and ts != ms:
        return "técnicas y macro discrepan"
    # neutral pese a que alguna columna apunta claro.
    if p["dir_tipo"] == "neutral":
        return "señales por debajo del umbral de convicción" if (ts or ms) else ""
    # las dos columnas apuntan a la inclinación pero la convicción es baja.
    quiere = +1 if p["dir_tipo"] == "mas" else -1
    if p.get("conviccion") == "baja" and ts == quiere and ms == quiere:
        return _freno_corto(p)
    return ""


def _paso(ck: str, dir_tipo: str | None, tier: str | None) -> int:
    """La posición de una clase en un carril universal de −2 a +2: de adverso al
    riesgo (izquierda) a favorable (derecha). El sentido lo da la beta de la
    clase frente a su eje (corta duración e infra dólar son PRO-riesgo), y la
    intensidad, si el sesgo es fuerte. Neutral = 0, el centro."""
    if dir_tipo in (None, "neutral"):
        return 0
    _ax, beta = config.CLASS_AXIS.get(ck, (None, 1))
    signo = 1 if dir_tipo == "mas" else -1
    risk = signo * (beta or 1)
    return risk * (2 if tier == "fuerte" else 1)


def _mecanismo_ok(key: str, trend: str) -> bool:
    """Si una frase de mecanismo asume mercado alcista, solo es cierta con la
    tendencia al alza. Si no, se omite: es preferible el silencio a una frase
    falsa (en 2008 la bolsa llevaba un año girada)."""
    if key in config.CONTRA_OBSERVAR_ALCISTA:
        return trend == "alcista"
    return True


def _trend(ctx: Context, asof) -> str:
    """El estado de la tendencia de la bolsa, VERIFICADO contra el dato del
    tablero (S&P frente a su media de 200 días), no asumido. Es lo que decide
    qué frase de mecanismo es cierta hoy: en 2008 la tendencia llevaba un año
    girada y cualquier frase que asuma mercado alcista es falsa."""
    try:
        s = ctx.panel["spx_vs_200"].loc[:asof].dropna()
    except Exception:
        return "lateral"
    if s.empty:
        return "lateral"
    x = float(s.iloc[-1])
    return "alcista" if x > 3.0 else "bajista" if x < -3.0 else "lateral"


def _posicionamiento(snap: dict, ctx: Context, asof, grupos: dict) -> list[dict]:
    """Una fila por clase: señales técnicas, señales macro, inclinación actual y
    la de hace un mes. Sustituye a la lista de «qué cambió» por una tabla."""
    todas = [f for pil in snap["tablero"] for f in pil["filas"]]
    ant = _postura_en(ctx, asof - pd.DateOffset(months=1), grupos)
    post = {p["key"]: p for p in snap["postura"]}
    filas = []
    for ck, meta in config.ASSET_CLASSES.items():
        p = post[ck]
        a = ant.get(ck, {})
        tec_cell = _senal_bloque(todas, ck, TECNICO_PILARES, meta)
        mac_cell = _senal_bloque(todas, ck, MACRO_PILARES, meta)
        paso = _paso(ck, p["dir_tipo"], p.get("tier"))
        paso_ant = _paso(ck, a.get("dir_tipo"), a.get("tier")) if a else None
        filas.append(dict(
            key=ck, label=meta["label"],
            tecnico=tec_cell, macro=mac_cell,
            dir_actual=p["direccion"], conv_actual=p.get("conviccion"),
            dir_tipo=p["dir_tipo"],
            etiqueta=("neutral" if p["dir_tipo"] == "neutral" else p["direccion"]),
            paso=paso, paso_ant=paso_ant,
            dir_ant=a.get("direccion", "—"), conv_ant=a.get("conviccion"),
            cambio=(a.get("dir_tipo") not in (None, p["dir_tipo"])
                    or a.get("conviccion") != p.get("conviccion")),
            nota=_nota_fila(p, tec_cell, mac_cell),
        ))
    return filas


def _contradicciones(ctx: Context, asof: pd.Timestamp, filas: list[dict],
                     postura: list[dict], trend: str = "lateral") -> list[dict]:
    """Indicadores en percentil extremo que apuntan al contrario que la
    inclinacion de su propia clase.

    Es exactamente el caso en el que un recuento por mayoria puede equivocarse
    por redundancia: veinte indicadores parecidos empujando en una direccion y
    uno solo, en un extremo de cinco anos, empujando en la otra. Puede tener
    razon la mayoria; el punto es que quien lee lo VEA, no que el documento
    decida por el. Por eso ademas de senalarlo se dice que estaria en juego si
    el que va solo acierta, y que habria que observar para saberlo.
    """
    post = {p["key"]: p for p in postura}
    out = []
    for f in filas:
        p = f["pct"]
        if not np.isfinite(p):
            continue
        if config.CONTRA_PCT_LOW < p < config.CONTRA_PCT_HIGH:
            continue
        key = f["key"]
        d = config.INDICATOR_BY_KEY[key]
        for ck, v in f["votos"].items():
            pc = post.get(ck)
            if pc is None or pc["dir_tipo"] == "neutral":
                continue
            quiere = +1 if pc["dir_tipo"] == "mas" else -1
            if v == quiere:
                continue
            meta = config.ASSET_CLASSES[ck]

            # Que habria que ver: el valor al que dejaria de ser extremo. Se
            # calcula sobre la misma ventana de cinco anos del percentil, para
            # que sea el mismo listón que usa el tablero.
            w = ctx.panel[key].loc[:asof].dropna().tail(config.PCT_WINDOW)
            if p >= config.CONTRA_PCT_HIGH:
                lim = float(w.quantile(config.EXTREME_HIGH / 100.0)) if len(w) else np.nan
                sentido = "volver por debajo de"
            else:
                lim = float(w.quantile(config.EXTREME_LOW / 100.0)) if len(w) else np.nan
                sentido = "volver por encima de"
            umbral = _fmt(d["fmt"], d["unit"], lim)
            observar = (f"que «{d['label']}» salga de su extremo: hoy marca "
                        f"{f['valor']} y tendría que {sentido} {umbral} para volver a "
                        f"terreno normal")
            variantes = config.CONTRA_OBSERVAR.get(key) or {}
            lado = ("alto" if np.isfinite(p) and p >= 50 else
                    "bajo" if np.isfinite(p) else None)
            extra = variantes.get(lado) if lado else None
            if extra and not _mecanismo_ok(key, trend):
                extra = None          # asume mercado alcista y hoy no lo es
            if extra:
                observar = f"{observar}. {extra[0].upper()}{extra[1:]}"

            out.append(dict(
                key=key, label=d["label"], valor=f["valor"], pct=p,
                pilar=d["pillar"], pilar_label=config.PILLARS[d["pillar"]]["label"],
                clase=ck, clase_label=meta["label"],
                apunta=meta["mas"] if v > 0 else meta["menos"],
                inclinacion=pc["direccion"], tier=pc["tier"],
                conviccion=pc["conviccion"], observar=observar,
                umbral=umbral, sentido=sentido, dias=f["extremo_dias"],
            ))

    # Un mismo extremo suele contradecir a varias clases a la vez -- la tasa
    # real alta va contra bolsa y materias primas y a favor del dolar y del
    # plazo largo. Se agrupa por indicador: UNA contradiccion con sus frentes,
    # y UNA sola frase de que implicaria. La version por clase repetia la misma
    # plantilla cuatro veces y no decia nada que no estuviera ya en el
    # enunciado.
    orden = {"fuerte": 3, "clara": 2, "leve": 1}
    pilar_de = {d["key"]: d["pillar"] for d in config.INDICATORS}
    porind: dict[str, dict] = {}
    for c in out:
        g = porind.setdefault(c["key"], dict(
            key=c["key"], label=c["label"], valor=c["valor"], pct=c["pct"],
            pilar=c["pilar"], pilar_label=c["pilar_label"],
            observar=c["observar"], umbral=c.get("umbral"), sentido=c.get("sentido"),
            dias=c.get("dias", 0), frentes=[]))
        g["frentes"].append(dict(
            clase=c["clase"], clase_label=c["clase_label"], apunta=c["apunta"],
            inclinacion=c["inclinacion"], tier=c["tier"],
            conviccion=c["conviccion"]))

    grupos = list(porind.values())
    for g in grupos:
        g["frentes"].sort(key=lambda x: -orden.get(x["tier"], 0))
        g["n_frentes"] = len(g["frentes"])
        g["peso"] = max(orden.get(x["tier"], 0) for x in g["frentes"])
        # Techo por antiguedad del MISMO extremo (mismo calculo que en _postura),
        # para que la seccion 4 diga lo mismo que la nota de la seccion 1: si el
        # extremo ya esta absorbido, no "rebaja" nada.
        g["semanas"] = g["dias"] / 5.0
        g["cap"] = _techo_extremo(_peso_extremo(g["semanas"]))
        implica = config.CONTRA_IMPLICA.get(g["key"])
        if not implica:
            # Respaldo calculado: el pilar que hoy sostiene la lectura de las
            # clases contradichas quedaria por detras de este. Generico, pero
            # dice algo -- que es mas de lo que hacia la plantilla por clase.
            cks = {x["clase"] for x in g["frentes"]}
            peso: dict[str, int] = {}
            for f in filas:
                if not (set(f["votos"]) & cks) or f["key"] == g["key"]:
                    continue
                pl = pilar_de.get(f["key"])
                peso[pl] = peso.get(pl, 0) + 1
            peso.pop(g["pilar"], None)
            dom = max(peso, key=peso.get) if peso else None
            implica = (
                f"el que iría por delante es {g['pilar_label'].lower()}, y no "
                f"{config.PILLARS[dom]['label'].lower()}, que es el pilar que hoy "
                f"sostiene la lectura de esas clases" if dom else
                f"el que iría por delante es {g['pilar_label'].lower()}, contra el "
                f"orden de importancia que asume el resto del tablero")
            g["implica_generica"] = True
        else:
            g["implica_generica"] = False
        g["implica"] = implica
    # RELEVANCIA primero, extremidad de desempate: una contradicción de un pilar
    # que entra en un eje pesa más que una de posicionamiento o inflación (que no
    # entran en ninguno). Lo extremo ordena DENTRO de cada grupo, no selecciona.
    ctx_pilares = set(config.CONTEXT_PILLARS)
    for g in grupos:
        g["eje"] = g["pilar"] not in ctx_pilares
        # ANTI-WHIPSAW (SPEC 7.1): un extremo de dos dias no encabeza nada. El
        # minimo lo fija la FRECUENCIA de la propia serie, no una ventana unica.
        g["min_dias"] = persistencia_minima(ctx, g["key"])
        g["persistente"] = extremo_persistente(ctx, g["key"], g.get("dias"))
    # relevancia (eje) -> persistencia -> extremidad de desempate
    grupos.sort(key=lambda g: (not g["eje"], not g["persistente"],
                               -abs(g["pct"] - 50.0), -g["peso"]))
    return grupos


def _divergencias_intra(ctx: Context, asof: pd.Timestamp,
                        tablero: list[dict]) -> list[dict]:
    """Dos indicadores del MISMO pilar diciendo cosas opuestas.

    El detector de divergencias compara pilar contra pilar y por eso es ciego a
    esto. Importa sobre todo en inflacion y posicionamiento, que no entran en
    ningun eje: ahi la comparacion entre pilares nunca las va a capturar, y son
    justo los pilares donde la contradiccion interna es informacion -- una
    desinflacion abrupta en el dato de tres meses que no aparece ni en el
    interanual ni en el productor es una noticia, no un ruido.
    """
    O = ctx.oriented
    hoy = O.loc[asof]
    fila_de = {f["key"]: f for pil in tablero for f in pil["filas"]}
    G = config.DIVERGENCE_INTRA_GAP
    out = []
    for pilar, keys in config.PILLAR_KEYS.items():
        ks = [k for k in keys if k in O.columns and np.isfinite(hoy[k])]
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                ga, gb = float(hoy[a]), float(hoy[b])
                alto, bajo = (a, b) if ga > gb else (b, a)
                oa, ob = max(ga, gb), min(ga, gb)
                # etiquetas OPUESTAS, no solo distintas de intensidad
                if not (oa >= 60 and ob <= 40 and (oa - ob) >= G):
                    continue
                cond = ((O[alto] >= 60) & (O[bajo] <= 40) &
                        ((O[alto] - O[bajo]) >= G))
                desde, dias = scoring.bool_run_start(
                    cond.fillna(False).astype(bool), asof)
                if dias / 5.0 < config.DIVERGENCE_INTRA_MINW:
                    continue
                fa, fb = fila_de.get(alto, {}), fila_de.get(bajo, {})
                out.append(dict(
                    pilar=pilar, pilar_label=config.PILLARS[pilar]["label"],
                    en_eje=any(pilar in ax["weights"] for ax in config.AXES.values()),
                    alto=alto, alto_label=fa.get("label", alto),
                    alto_valor=fa.get("valor", "—"), alto_pct=fa.get("pct", np.nan),
                    alto_op=oa,
                    bajo=bajo, bajo_label=fb.get("label", bajo),
                    bajo_valor=fb.get("valor", "—"), bajo_pct=fb.get("pct", np.nan),
                    bajo_op=ob,
                    gap=oa - ob, desde=desde, dias=dias, semanas=dias / 5.0,
                    duracion=_duracion(dias),
                ))
    # Dentro de un pilar, un mismo indicador extremo choca con varios de sus
    # companeros y salen diez pares que cuentan una sola cosa. Se publica el
    # par mas amplio de cada pilar -- la contradiccion interna del pilar -- y
    # el recuento completo queda en las comprobaciones.
    out.sort(key=lambda d: -d["gap"])
    vistos, principales = set(), []
    for d in out:
        if d["pilar"] in vistos:
            continue
        vistos.add(d["pilar"])
        principales.append(d)
    for d in principales:
        d["pares_pilar"] = sum(1 for x in out if x["pilar"] == d["pilar"])
    return dict(lista=principales, pares=len(out))


def _analogos(ctx: Context, asof: pd.Timestamp) -> dict:
    """Fechas del pasado que se parecen a hoy, con DOS distancias distintas.

    DINAMICA. El vector de los siete pilares mas su trayectoria (el cambio a 1
    y a 3 meses de cada uno, con medio peso). Mide si el mercado se COMPORTA
    parecido. Un estado identico al que se llega desde arriba no es el mismo
    que si se llega desde abajo, y sin los deltas eso no se veia.

    ENTORNO. Media docena de variables en nivel absoluto -- tasa real,
    inflacion subyacente, tasa de referencia, pendiente de la curva, valuacion
    de la bolsa, direccion del balance de la Fed -- estandarizadas sobre toda
    la historia conocida en la fecha. Mide si el MUNDO es parecido. Hace falta
    porque el percentil, al normalizar cada serie contra su propia historia
    movil, borra el nivel: un apetito de riesgo en el percentil 67 con la tasa
    real en -1% y el balance creciendo no es el mismo sitio que ese mismo
    percentil con la tasa real en +2,4% y la inflacion en 3,3%.

    Y una separacion minima de DOCE meses entre analogos, porque con noventa
    dias cuatro de las cinco fechas podian ser el mismo episodio muestreado
    cuatro veces: la media "de cinco observaciones" era una, y la dispersion
    parecia estrecha por correlacion en serie, no por estabilidad del
    desenlace.

    NULO HONESTO. Si quedan menos de tres episodios de entorno distintos, o si
    el mejor analogo vive en otro mundo, no se publica la media ni las barras.
    Las fechas si: un desenlace concreto sigue informando; una media de una
    sola observacion disfrazada de cinco, no.
    """
    # ------------------------------------------------ vector de dinamica
    pil = list(config.PILLARS)
    P = ctx.pillars[pil]
    W = config.ANALOG_DELTA_WEIGHT
    base = pd.concat([P, ctx.pillar_d1m[pil].add_suffix("|d1"),
                      ctx.pillar_d3m[pil].add_suffix("|d3")], axis=1).dropna()
    pesos = np.array([1.0] * len(pil) + [W] * len(pil) + [W] * len(pil))

    sub = base.loc[:asof]
    if sub.empty:
        return dict(disponible=False)
    ref = sub.index[-1]                    # fecha de referencia efectiva
    hoy = sub.iloc[-1].to_numpy()

    limite = asof - pd.Timedelta(days=config.ANALOG_FWD_MIN_DAYS)
    cand = base.loc[:limite]
    if len(cand) < 60:
        return dict(disponible=False)

    dif = cand.to_numpy() - hoy
    dist = np.sqrt((dif ** 2 * pesos).sum(axis=1) / pesos.sum())

    # ------------------------------------------------- vector de entorno
    Z = entorno.estandarizar(ctx.env, ref).loc[:ref]
    env_d = entorno.distancia(Z, ref)
    eps = entorno.episodios(Z)
    env_hay, env_faltan = entorno.disponibles(ctx.env, ref)
    env_lab = {c[0]: c[1] for c in config.ENV_VARS}

    # QUE HACE HOY (POCO) COMPARABLE: la variable de entorno mas lejos de su
    # norma. Se calcula aqui para poder nombrarla tanto si no hay ningun analogo
    # como si hay pocos -- normalmente es el nivel de tasas reales o de inflacion.
    causa = None
    if ref in Z.index:
        zt = Z.loc[ref]
        env_fmt = {c[0]: (c[1], c[4], c[5]) for c in config.ENV_VARS}
        porz = sorted(((c, abs(float(zt[c]))) for c in Z.columns if np.isfinite(zt[c])),
                      key=lambda t: -t[1])
        if porz:
            ck0 = porz[0][0]
            lab, spec, unit = env_fmt[ck0]
            val = float(ctx.env.loc[ref, ck0]) if ref in ctx.env.index else np.nan
            causa = dict(clave=ck0, label=lab, z=float(zt[ck0]),
                         valor_txt=f"{spec.format(val)}{unit}" if np.isfinite(val) else "—")
    causa_txt = (f"por {minus(causa['label'])} ({causa['valor_txt']} hoy, "
                 f"{causa['z']:+.1f}σ sobre su media histórica)") if causa else \
        "por un nivel de tasas o de inflación sin precedente cercano"

    # ------------------------------------- cobertura de la muestra (4f)
    eps_c = eps.reindex(cand.index).dropna()
    muestra = dict(
        n=len(cand), desde=cand.index[0], hasta=cand.index[-1],
        anos=(cand.index[-1] - cand.index[0]).days / 365.25,
        episodios=int(eps_c.nunique()) if len(eps_c) else 0,
    )

    # Ventana elegible demasiado corta: la seccion de analogos no puede decir
    # nada util y hay que declararlo ARRIBA, no en letra pequena.
    ventana_corta = bool(muestra.get("anos") is not None
                         and muestra["anos"] < config.ANALOG_VENTANA_MIN_ANOS)

    orden = np.argsort(dist)
    fechas = cand.index

    # TODAS las fechas por debajo del umbral en las DOS distancias (dinámica Y
    # entorno), con doce meses de separación entre sí -- la separación es la
    # unidad de independencia (dos fechas a un año son observaciones distintas).
    # No "las N más cercanas": en un estado común esto da varias veces más
    # muestra, y cuando da pocas, ese es el dato (estado inusual).
    picks = []
    for i in orden:
        d_dyn = float(dist[i])
        if d_dyn > config.ANALOG_DIST_MAX:
            break                          # ordenado ascendente: el resto está más lejos
        dt = fechas[i]
        de = float(env_d.loc[dt]) if dt in env_d.index and np.isfinite(env_d.loc[dt]) else np.nan
        if not np.isfinite(de) or de > config.ANALOG_ENV_INCLUDE:
            continue                       # el mundo era otro (o sin dato de entorno): no entra
        if any(abs((dt - p["fecha"]).days) < config.ANALOG_MIN_GAP_DAYS for p in picks):
            continue                       # a menos de doce meses de otra ya elegida
        ep = int(eps.loc[dt]) if dt in eps.index else -1
        picks.append(dict(fecha=dt, dist=d_dyn, env=de, episodio=ep))
        if len(picks) >= config.ANALOG_N_MAX:
            break

    nearest = float(dist[orden[0]]) if len(orden) else float("inf")
    if not picks:
        # sin ninguno: distinguir si es que el COMPORTAMIENTO no tiene precedente
        # (dinamica lejana) o si lo hay pero en otro MUNDO (entorno demasiado
        # distinto). No es lo mismo, y la causa honesta es distinta.
        motivo = "dinamica" if nearest > config.ANALOG_DIST_MAX else "entorno"
        return dict(disponible=True, sin_analogos=True, nearest=nearest, motivo=motivo,
                    ventana_corta=ventana_corta,
                    umbral=config.ANALOG_DIST_MAX, muestra=muestra,
                    causa=causa, causa_txt=causa_txt,
                    env_faltan=[env_lab[c] for c in env_faltan],
                    env_n=len(env_hay))

    def calidad(d):
        for u, palabra in config.ANALOG_QUALITY:
            if d <= u:
                return palabra
        return "lejano"

    def etiqueta(dd, de):
        """Las dos distancias, en una sola frase que se pueda leer."""
        if calidad(dd) == "lejano":
            return "no es análogo", "no"
        if not np.isfinite(de):
            return "mismo comportamiento; entorno sin dato", "sd"
        if de <= config.ANALOG_ENV_QUALITY[-1][0]:
            return ("análogo fuerte", "fuerte") if calidad(dd) != "lejano" else ("análogo", "ok")
        return "mismo comportamiento, otro mundo", "otro"

    def fwd_serie(serie, dt, meses):
        if serie is None:
            return np.nan
        s = serie.dropna()
        base = s.loc[:dt]
        fut = s.loc[:dt + pd.DateOffset(months=meses)]
        if base.empty or fut.empty:
            return np.nan
        return (fut.iloc[-1] / base.iloc[-1] - 1.0) * 100.0

    def _serie(tk):
        if ctx.prices is not None and tk in ctx.prices.columns:
            return ctx.prices[tk]
        if tk == "SPY":
            return ctx.spy
        return None

    def fwd_etf(clave, tk, tk2, dt, meses):
        a = fwd_serie(_serie(tk), dt, meses)
        if tk2 is None:
            return a
        b = fwd_serie(_serie(tk2), dt, meses)          # diferencial (ciclico - defensivo)
        return a - b if (a == a and b == b) else np.nan

    spy = _serie("SPY")

    def realized_vol(dt, meses):
        """Volatilidad realizada anualizada del S&P en la ventana futura."""
        if spy is None:
            return np.nan
        w = spy.loc[dt:dt + pd.DateOffset(months=meses)]
        r = w.pct_change().dropna()
        if len(r) < 10:
            return np.nan
        return float(r.std() * np.sqrt(252) * 100.0)

    H = config.ANALOG_MATRIX_H          # horizonte de la matriz (meses)
    horizontes = config.ANALOG_HORIZONS  # [3, 6, 12]
    cols = config.ANALOG_ETFS           # (clave, sigla, etiqueta, tk, tk2)

    def _stats(valores):
        v = [x for x in valores if x == x]
        if not v:
            return dict(media=np.nan, min=np.nan, max=np.nan)
        return dict(media=sum(v) / len(v), min=min(v), max=max(v))

    # Una fila por analogo: las dos distancias, en que se parece y en que no,
    # y el rendimiento de cada activo con su vol realizada en cada horizonte.
    out = []
    for p in picks:
        dt = p["fecha"]
        de = float(env_d.loc[dt]) if dt in env_d.index and np.isfinite(env_d.loc[dt]) else np.nan
        txt, kind = etiqueta(p["dist"], de)
        difs = sorted(
            ((k, abs(float(P.loc[dt, k] - P.loc[ref, k])))
             for k in pil if np.isfinite(P.loc[dt, k]) and np.isfinite(P.loc[ref, k])),
            key=lambda t: t[1])
        out.append(dict(
            fecha=dt, dist=p["dist"], calidad=calidad(p["dist"]),
            env=de, env_calidad=entorno.calidad(de),
            etiqueta=txt, etiqueta_k=kind,
            episodio=int(eps.loc[dt]) if dt in eps.index else -1,
            estado=ctx.state.loc[:dt].iloc[-1] if len(ctx.state.loc[:dt]) else None,
            # en que se parece y en que no: dos pilares por lado
            iguales=[(config.PILLARS[k]["label"], g) for k, g in difs[:2]],
            distintos=[(config.PILLARS[k]["label"], g) for k, g in difs[-2:][::-1]],
            entorno=entorno.descomponer(Z, ctx.env, ref, dt)[:3],
            ret={m: {c[0]: fwd_etf(c[0], c[3], c[4], dt, m) for c in cols}
                 for m in horizontes},
            vol={m: realized_vol(dt, m) for m in horizontes},
        ))

    # ---------------------------------- estado inusual (pocos comparables)
    # Por construcción hay un episodio por fecha. Con menos comparables que el
    # mínimo no se promedia: eso es falsa precisión. Se dice qué lo hace inusual
    # -- normalmente el nivel de tasas reales o de inflación -- y eso informa más
    # que cualquier media sobre tres observaciones.
    n_episodios = len(out)
    inusual = n_episodios < config.ANALOG_MIN_REPORT
    env_mejor = out[0]["env"] if out else np.nan

    razones = [causa_txt] if inusual else []
    nulo = inusual
    nulo_por = "inusual" if inusual else None

    # Consistencia direccional por clase: con muestras pequeñas el SIGNO es mucho
    # más estable que la media, y es lo que un lector puede usar. Sin patrón si el
    # rango cruza cero con un ancho grande -- ahí no hay nada que reportar.
    consistencia = []
    if not inusual:
        for c in cols:
            vals = [o["ret"][H][c[0]] for o in out
                    if o["ret"][H][c[0]] == o["ret"][H][c[0]]]
            if not vals:
                continue
            n = len(vals)
            n_up = sum(1 for v in vals if v > 0)
            n_dn = n - n_up
            mn, mx = min(vals), max(vals)
            # Hay patrón si una dirección es clara mayoría. El signo es más
            # estable que la media con muestras pequeñas; sin mayoría clara, no
            # hay patrón que reportar (el rango, que se muestra, ya enseña la
            # dispersión de los episodios que fueron al contrario).
            maj = max(n_up, n_dn) / n
            patron = maj >= config.ANALOG_PATRON_FRAC
            consistencia.append(dict(
                clave=c[0], sigla=c[1], n=n, n_up=n_up, n_dn=n_dn, min=mn, max=mx,
                patron=patron, signo=(1 if n_up > n_dn else -1 if n_dn > n_up else 0)))

    # El analogo FUERTE (parecido en dinamica Y en entorno) sigue disponible para
    # el tablero.
    fuertes = [o for o in out if o["etiqueta_k"] == "fuerte"]
    fuerte = min(fuertes, key=lambda o: o["dist"]) if fuertes else None

    base_ret = dict(
        disponible=True, sin_analogos=False, nearest=nearest,
        horizonte=H, horizontes=horizontes,
        columnas=[(c[0], c[1], c[2]) for c in cols],
        lista=out, n=len(picks), fuerte=fuerte,
        n_otro_mundo=sum(1 for o in out if o["etiqueta_k"] in ("otro", "no")),
        n_episodios=n_episodios, n_comparables=n_episodios, muestra=muestra,
        ventana_corta=ventana_corta,
        inusual=inusual, causa=causa, consistencia=consistencia,
        env_mejor=env_mejor, env_mejor_calidad=entorno.calidad(env_mejor),
        env_faltan=[env_lab[c] for c in env_faltan], env_n=len(env_hay),
        nulo=nulo, nulo_por=nulo_por, nulo_razon=razones,
        trayectoria=None, promedio=None, promedio_vol=None, escala=None,
    )
    if nulo:
        # No se calcula la media: no es que se oculte, es que no significa nada.
        return base_ret

    # Trayectoria media: por horizonte, la media de cada activo (y su vol).
    trayectoria = []
    for m in horizontes:
        vals = {c[0]: _stats([o["ret"][m][c[0]] for o in out]) for c in cols}
        volm = _stats([o["vol"][m] for o in out])
        trayectoria.append(dict(horizonte=m, valores=vals, vol=volm))

    # Promedio a H meses de cada activo, con su rango (min-media-max) para el
    # rango visual.
    promedio = [dict(clave=c[0], sigla=c[1], etiqueta=c[2],
                     stats=_stats([o["ret"][H][c[0]] for o in out]))
                for c in cols]
    promedio_vol = _stats([o["vol"][H] for o in out])

    # Escala comun para las barras de rango (simetrica, en % de rentabilidad).
    # Cubre TODOS los horizontes, para que las barras sean comparables entre si.
    topes = [abs(x) for f in trayectoria for st in f["valores"].values()
             for x in (st["min"], st["max"]) if x == x]
    escala = max(20.0, (int(max(topes) / 5) + 1) * 5.0) if topes else 20.0

    base_ret.update(trayectoria=trayectoria, promedio=promedio,
                    promedio_vol=promedio_vol, escala=escala)
    return base_ret


def _divergencias(ctx: Context, asof: pd.Timestamp) -> list[dict]:
    """Pilares que se contradicen: uno por encima de neutral y otro por
    debajo, con una brecha material. Coincidir en direccion pero no en
    intensidad no es contradiccion, es matiz."""
    P = ctx.pillars
    hoy = P.loc[asof]
    keys = [k for k in P.columns if np.isfinite(hoy[k])]
    out = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ga, gb = float(hoy[a]), float(hoy[b])
            if (ga - 50.0) * (gb - 50.0) >= 0:
                continue
            gap = abs(ga - gb)
            if gap < config.DIVERGENCE_GAP:
                continue
            cond = (((P[a] - 50.0) * (P[b] - 50.0) < 0) &
                    ((P[a] - P[b]).abs() >= config.DIVERGENCE_GAP))
            desde, dias = scoring.bool_run_start(cond.fillna(False).astype(bool), asof)
            semanas = dias / 5.0
            if semanas < config.DIVERGENCE_MINW:
                continue
            alto, bajo = (a, b) if ga > gb else (b, a)
            out.append(dict(
                alto=alto, alto_label=config.PILLARS[alto]["label"],
                alto_score=max(ga, gb),
                bajo=bajo, bajo_label=config.PILLARS[bajo]["label"],
                bajo_score=min(ga, gb),
                gap=gap, desde=desde, dias=dias, semanas=semanas,
                duracion=_duracion(dias),
            ))
    out.sort(key=lambda d: -d["gap"])
    return out


def _extremos(tablero: list[dict]) -> list[dict]:
    out = []
    for pil in tablero:
        for f in pil["filas"]:
            if not f["extremo"]:
                continue
            out.append(dict(
                pilar=pil["label"], label=f["label"], valor=f["valor"],
                pct=f["pct"], tipo=f["extremo_tipo"],
                desde=f["extremo_desde"], dias=f["extremo_dias"],
                duracion=_duracion(f["extremo_dias"]),
            ))
    out.sort(key=lambda d: -abs(d["pct"] - 50.0))
    return out


__all__ = ["Context", "build_snapshot", "fecha_larga", "fecha_corta", "_duracion"]
