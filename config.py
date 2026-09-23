# -*- coding: utf-8 -*-
"""
Snapshot Macro y de Mercado - configuracion.

QUE ES: una guia de lectura del estado macro y de mercado.
QUE NO ES: un modelo. No optimiza, no asigna porcentajes, no genera ordenes,
no rebalancea. Produce SENALES y LECTURAS.

REGLA DE GOBIERNO
-----------------
Este proyecto LEE datos de fuentes publicas (FRED, Yahoo) con su propia cache.
NUNCA escribe en el proyecto del modelo de ETFs. Si hace falta un indicador
nuevo, se anade AQUI.

PRINCIPIO DE CONSTRUCCION
-------------------------
Descomponer, no colapsar. Cada indicador se muestra en sus propias unidades,
con su percentil y su lectura (favorable / adverso). Los agregados por pilar
y los dos ejes existen solo para ordenar la lectura, nunca para sustituirla.
"""

from __future__ import annotations

# --------------------------------------------------------------- horizontes
DATA_START = "1999-01-01"   # descarga de historia
PCT_WINDOW = 1260           # ventana de percentil del tablero: 5 anos habiles
PCT_MINP = 504              # minimo para publicar un percentil: 2 anos
HIST_MINP = 756             # minimo para el percentil historico de los ejes: 3 anos

DELTA_1M = 1                # meses de calendario, no dias habiles
DELTA_3M = 3

# Suavizado de los deltas. El punto de comparacion de un delta NO puede ser un
# unico cierre: ese cierre se cae de la ventana de un dia para otro y mueve un
# delta trimestral varios puntos sin que el mercado se haya movido -- y entonces
# el "rumbo" cambia de "sin rumbo claro" a "deteriorandose" sin que pase nada, y
# el lector deja de creerle al rumbo. Se compara contra la MEDIA de una ventana
# de dias habiles alrededor de la fecha de referencia; y el extremo ACTUAL de
# los agregados (ejes, pilares, puntuacion) tambien se promedia. Los indicadores
# sueltos se quedan en su cierre.
DELTA_REF_WIN = 5           # dias habiles alrededor de la fecha de comparacion
DELTA_ACTUAL_WIN = 3        # dias habiles del extremo actual, solo agregados
# Giro de un delta respecto al snapshot anterior que se marca como inestable si
# no lo acompana un movimiento equivalente del nivel.
DELTA_GIRO_AVISO = 3.0

# ------------------------------------------------------------- series FRED
# id: (etiqueta, frecuencia, dias de retardo de publicacion)
# El retardo evita el sesgo de anticipacion: la serie solo se considera
# conocida `lag` dias naturales despues del CIERRE de su periodo de
# referencia. Sin esto, un snapshot de septiembre de 2008 leeria datos que
# no se publicaron hasta octubre.
FRED_SERIES: dict[str, tuple[str, str, int]] = {
    # credito y condiciones financieras
    #
    # Se usan los diferenciales de Moody's (Baa y Aaa frente al tesoro a 10
    # anos), diarios desde 1986. Los indices ICE BofA (BAMLH0A0HYM2,
    # BAMLC0A0CM), que serian la primera opcion por cubrir high yield, salen
    # de FRED recortados a los ultimos 3 anos por licencia: con esa historia
    # no se puede calcular un percentil a 5 anos ni generar el snapshot de
    # 2008, asi que quedan fuera. Baa-Aaa cubre lo esencial -- el precio del
    # riesgo de impago -- con 40 anos de historia.
    "BAA10Y":       ("Diferencial Baa - tesoro 10a",    "D",  1),
    "AAA10Y":       ("Diferencial Aaa - tesoro 10a",    "D",  1),
    "NFCI":         ("Condiciones financieras Chicago", "W",  4),
    # curva y tipos
    "T10Y3M":       ("Pendiente 10a-3m",                "D",  1),
    "T10Y2Y":       ("Pendiente 10a-2a",                "D",  1),
    "DGS2":         ("Tesoro 2a",                       "D",  1),
    "DFII10":       ("Tasa real 10a (TIPS)",            "D",  1),
    "DFF":          ("Tasa de referencia efectiva",           "D",  1),
    # inflacion
    "T5YIE":        ("Breakeven inflacion 5a",          "D",  1),
    "T10YIE":       ("Breakeven inflacion 10a",         "D",  1),
    "CPIAUCSL":     ("IPC general",                     "M", 13),
    "PCEPILFE":     ("PCE subyacente",                  "M", 30),
    "PPIACO":       ("Precios al productor",            "M", 14),
    # actividad
    "ICSA":         ("Peticiones de desempleo",         "W",  5),
    "SAHMREALTIME": ("Regla de Sahm",                   "M",  8),
    "PAYEMS":       ("Nominas no agricolas",            "M",  8),
    "INDPRO":       ("Produccion industrial",           "M", 17),
    "PERMIT":       ("Permisos de construccion",        "M", 19),
    "RRSFS":        ("Ventas minoristas reales",        "M", 16),
    "UMCSENT":      ("Confianza del consumidor",        "M", 12),
    # liquidez y divisa
    "WALCL":        ("Balance de la Fed",               "W",  2),
    "RRPONTSYD":    ("Repo inverso a un dia",           "D",  1),
    "WTREGEN":      ("Cuenta del Tesoro (TGA)",         "W",  2),
    "DTWEXBGS":     ("Dolar (indice amplio)",           "D",  1),
}

# Unidades de FRED que hay que homogeneizar antes de operar con ellas.
# WALCL y WTREGEN vienen en MILLONES de dolares; RRPONTSYD en MILES DE
# MILLONES. Mezclarlas sin convertir convierte la liquidez neta en el saldo
# de la TGA con el signo cambiado.
FRED_SCALE_TO_BILLIONS = {"WALCL": 1e-3, "WTREGEN": 1e-3, "RRPONTSYD": 1.0}

# --------------------------------------------------------------- cotizadas
TICKERS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ",
    "XLK", "XLY", "XLF", "XLI", "XLB", "XLE", "XLP", "XLU", "XLV",
    "TLT", "IEF", "SHY", "LQD", "HYG", "GLD", "DBC", "UUP",
    "^VIX", "HG=F", "GC=F",
]

# Cesta de "activos de riesgo" para amplitud y momentum agregado.
RISK_BASKET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ",
               "XLK", "XLY", "XLF", "XLI", "XLB", "XLE", "HYG", "DBC"]

# ----------------------------------------------------------------- pilares
# SEMANTIC-PASS 5 y 9: el nombre dice QUE MIDE y la glosa responde a las tres
# preguntas --que mide, que dice hoy, por que importa--. Los nombres anteriores
# eran del modelo, no del oficio: «Posicionamiento y valor relativo» no es
# posicionamiento de inversores (no hay CFTC, ni flujos, ni encuestas), y
# «Liquidez y política monetaria» mezclaba cantidad de dinero con su precio.
PILLARS: dict[str, dict] = {
    "credito": dict(
        label="Condiciones de crédito",
        pregunta="¿Es fácil o caro financiarse?",
        desc="El precio que pide el mercado por prestar.",
        importa="Cuando financiarse se encarece, el riesgo se paga peor en "
                "todos los activos a la vez."),
    "volatilidad": dict(
        label="Estrés de mercado",
        pregunta="¿Cuánto miedo o tensión está descontando el mercado?",
        desc="El nerviosismo que cotiza ahora mismo.",
        importa="El estrés alto adelanta ventas forzadas; el estrés bajo "
                "deja menos margen para una sorpresa."),
    "tendencia": dict(
        label="Tendencia de mercado",
        pregunta="¿Los precios confirman o contradicen el régimen?",
        desc="Hacia dónde se han movido los precios.",
        importa="Una lectura que el precio no acompaña suele llegar pronto."),
    "posicionamiento": dict(
        label="Extensión y valor relativo",
        pregunta="¿La operación ya está estirada o sigue teniendo espacio?",
        desc="Cuánto se ha pagado ya por esa tendencia. Se lee al revés: "
             "caro = frena riesgo.",
        importa="No mide posicionamiento de inversores —no hay flujos ni "
                "encuestas—: mide cuánto recorrido se ha consumido."),
    "crecimiento": dict(
        label="Crecimiento",
        pregunta="¿La actividad acelera, se mantiene o se deteriora?",
        desc="Qué hace la economía real, y qué implica el mercado sobre ella.",
        importa="Es el suelo de los beneficios y de la capacidad de pagar "
                "deuda."),
    "inflacion": dict(
        label="Inflación",
        pregunta="¿La inflación añade presión o alivio al entorno?",
        desc="A qué ritmo suben los precios, y qué ritmo se descuenta.",
        importa="Su signo depende del régimen, por eso no vota dirección: "
                "la misma subida es reflación sana o estanflación."),
    "liquidez": dict(
        label="Condiciones monetarias",
        pregunta="¿El costo y la disponibilidad del dinero ayudan o frenan?",
        desc="El costo del dinero y cuánto hay en el sistema.",
        importa="Un costo de capital alto limita múltiplos y castiga a los "
                "activos de larga duración."),
}

# ------------------------------------------------------------------- ejes
#
# DOS PILARES SE QUEDAN FUERA DE LOS EJES, A PROPOSITO:
#
#   INFLACION. Su signo para el ciclo depende del regimen: la misma subida de
#   precios es reflacion sana o estanflacion segun lo que haga el crecimiento.
#   Promediarla dentro del eje borraria justamente la divergencia que
#   interesa ver.
#
#   POSICIONAMIENTO. Mide lo contrario que el resto del eje de riesgo por
#   construccion: cuando todo se desploma, las cosas se abaratan y este pilar
#   mejora. Dentro del eje amortiguaba la senal precisamente en las caidas
#   -- en la prueba de marzo de 2020 subia el eje unos 11 puntos y convertia
#   un estres severo en simple tension. Fuera del eje, esa misma tension entre
#   "la tendencia es fuerte" y "ya se ha pagado por ella" aparece como
#   divergencia, que es donde se lee.
#
# Pesos iguales dentro del eje de riesgo: aqui no hay ninguna calibracion, y
# afinar los pesos seria fingir un modelo. En el eje de ciclo la actividad
# pesa mas que la liquidez porque la liquidez condiciona el ciclo pero no es
# el ciclo.
AXES: dict[str, dict] = {
    "riesgo": dict(
        label="Eje de riesgo",
        sub="Apetito frente a aversión en los mercados",
        weights={"credito": 1 / 3, "volatilidad": 1 / 3, "tendencia": 1 / 3},
        high="apetito", low="aversión",
    ),
    "ciclo": dict(
        label="Eje de ciclo",
        sub="Actividad económica e impulso monetario",
        weights={"crecimiento": 0.65, "liquidez": 0.35},
        high="expansión", low="contracción",
    ),
}

# Pilares que se muestran pero no agregan a ningun eje.
CONTEXT_PILLARS = [p for p in PILLARS
                   if not any(p in a["weights"] for a in AXES.values())]

# ------------------------------------------------------------ estado general
# Bandas sobre el percentil historico del eje de riesgo.
#
# Cinco estados, no siete. Con bandas mas estrechas el estado cambiaba cada
# 13 dias de mediana (446 veces en 22 anos) y la frase "lleva X asi" del
# titular no informaba de nada. Ademas, ninguna banda puede ser mas estrecha
# que el doble de la histeresis, o se vuelve inalcanzable.
STATE_BANDS = [
    (0,   10,  "estrés severo"),
    (10,  30,  "tensión"),
    (30,  70,  "neutral"),
    (70,  90,  "apetito de riesgo"),
    (90,  101, "euforia"),
]
# Explicacion llana de cada estado, para el titular: que significa ese clima
# de riesgo. El estado es la banda del percentil historico del eje de riesgo.
STATE_GLOSS = {
    "estrés severo":     "los mercados están en pánico, en máxima aversión al riesgo",
    "tensión":           "hay miedo en los mercados, con aversión al riesgo",
    "neutral":           "ni miedo ni euforia: el riesgo se toma con calma",
    "apetito de riesgo": "los mercados están cómodos tomando riesgo",
    "euforia":           "apetito de riesgo extremo, euforia",
}

# Para abandonar el estado actual hay que rebasar su limite por este margen,
# en puntos de percentil. Evita el parpadeo en los bordes.
# Tope de la extrapolacion del clima. Mas alla de esto el ritmo del ultimo mes
# no dice nada util sobre el plazo: no se proyecta.
CLIMA_MAX_SEMANAS = 26

STATE_HYSTERESIS = 5
# Y ademas, solo para MEJORAR, aguantar N dias habiles. El deterioro se
# reconoce el mismo dia (ver scoring.state_series).
# Calibrado sobre 1999-hoy: 138 cambios en 22 anos, racha mediana de 42 dias.
STATE_PERSISTENCE = 5

# ------------------------------------------------------ umbrales de lectura
EXTREME_LOW = 10      # percentil a 5 anos por debajo del cual se marca extremo
EXTREME_HIGH = 90
CLEAR_LOW = 25        # senal "clara" (umbral del perfil moderado, seccion 5)
CLEAR_HIGH = 75

DIVERGENCE_GAP = 35   # puntos de percentil entre dos pilares para llamarlo divergencia
DIVERGENCE_MINW = 2   # semanas minimas para reportarla

# Divergencias DENTRO de un mismo pilar. El detector de arriba compara pilar
# contra pilar y por eso es ciego a la contradiccion mas informativa que suele
# haber: dos indicadores del mismo pilar diciendo cosas opuestas -- el IPC de
# tres meses anualizado en un extremo favorable conviviendo con los precios al
# productor en la mitad alta de su rango. Importa sobre todo en inflacion y
# posicionamiento, que no entran en ningun eje: ahi la comparacion entre
# pilares nunca va a capturarlas.
DIVERGENCE_INTRA_GAP = 40    # puntos de percentil ORIENTADO entre los dos
DIVERGENCE_INTRA_MINW = 2    # semanas minimas de persistencia

# ------------------------------------------------- redundancia entre senales
# Cuantos indicadores hay no es cuanta informacion hay. El VIX, el VIX frente a
# su media, la volatilidad realizada y la caida desde maximos son casi la misma
# senal contada cuatro veces, y un pilar con mas filas pesa mas solo por tener
# mas filas. Se agrupan por correlacion y se reporta el recuento EFECTIVO junto
# al crudo. Solo informa: no corrige ningun voto (ver snapshot/senales.py).
CLUSTER_WINDOW = 1260   # misma ventana que el percentil del tablero: 5 anos
CLUSTER_MINOBS = 504
CLUSTER_RHO = 0.60      # |correlacion| a partir de la cual dos son el mismo cluster
# Aviso permanente: un pilar que aporta mas del 40% de los indicadores que
# votan una dimensión de posicionamiento pero menos del 20% de sus senales independientes
# esta mandando en el recuento sin aportar informacion nueva.
REDUND_SHARE_IND = 0.40
REDUND_SHARE_SIG = 0.20

# ------------------------------------------- contradicciones de alto perfil
# Un indicador en percentil extremo apuntando en contra de la inclinacion de
# su propia clase es exactamente el caso donde una mayoria por recuento puede
# equivocarse por redundancia. No se esconde en el detalle: sale en la 1.
CONTRA_PCT_LOW, CONTRA_PCT_HIGH = 5, 95

# ------------------------------------- nota de research: peso de la evidencia
# LA EVIDENCIA SE ELIGE POR PERTINENCIA, NO POR LO EXTREMA QUE ESTE. Cada
# afirmacion de la caja de sintesis y de la prosa se refiere a un pilar (o
# pilares) y SOLO puede citar indicadores de ese pilar; lo extremo desempata
# dentro del pilar, no selecciona de todo el tablero. "La economia real" no
# puede sostenerse con un dato de inflacion o de posicionamiento solo porque
# esten mas extremos que los de crecimiento.
AFIRMACION_PILARES: dict[str, list[str]] = {
    "economia_real":  ["crecimiento"],
    "cond_fin":       ["credito"],
    "costo_capital":  ["liquidez"],
    "apetito_riesgo": ["volatilidad", "tendencia"],
}
# Los dos compuestos, al estilo weight-of-the-evidence. El TECNICO es el eje de
# riesgo; el MACRO/FUNDAMENTAL es el eje de ciclo -- los dos pilares macro que
# SI entran en un eje. Inflacion y posicionamiento quedan fuera a proposito
# (ver AXES): no se citan como evidencia de los ejes, solo como contexto.
WOE_TECNICO_PILARES = ["credito", "volatilidad", "tendencia"]
WOE_MACRO_PILARES = ["crecimiento", "liquidez"]
# GRAMATICA CON UMBRAL EXPLICITO. El segundo bloque, medido por su acuerdo con
# el primero (0-100, 100 = coincide del todo, 50 = neutral):
#   > 65 y en la misma direccion   -> CONFIRMA   (la conviccion puede ser alta)
#   entre 45 y 65                   -> ATEMPERA   (techo media)
#   < 45 y en direccion contraria  -> CONTRADICE (techo baja; baja conviccion)
# La palabra sale de la regla, no de la redaccion, y la conviccion agregada no
# puede ser la misma si atempera que si confirma.
WOE_CONFIRMA = 65.0
WOE_ATEMPERA = 45.0
WOE_TECHO = {"confirma": "alta", "atempera": "media",
             "contradice": "baja", "acompaña": "media"}
# El concepto de cada pilar, para nombrar el lado que arrastra un compuesto
# partido sin repetir el indicador exacto de la tension.
CONCEPTO_PILAR: dict[str, str] = {
    # SEMANTIC-PASS 11: "la liquidez" era el nombre viejo del pilar. La barra
    # del grafico y la cabecera ya decian "Condiciones monetarias" mientras la
    # prosa seguia diciendo "la liquidez pesa en contra": el mismo compuesto con
    # dos nombres se lee como dos variables distintas.
    "liquidez":        "las condiciones monetarias",
    "crecimiento":     "el crecimiento",
    "credito":         "el crédito",
    "volatilidad":     "la volatilidad",
    "tendencia":       "la tendencia",
    "inflacion":       "la inflación",
    "posicionamiento": "el posicionamiento",
}

# SPEC-7P 8: UN nombre por pilar, el mismo en la prosa, en la tension dominante
# y en el grafico de fuerzas. La pagina 1 llegaba a decir «el costo del capital
# 40» en la celda de tension y «Liquidez 40» en la barra de al lado: son el
# MISMO compuesto, y dos nombres para un numero identico se leen como dos
# variables distintas que casualmente coinciden.
PILAR_NOMBRE: dict[str, str] = {
    "credito":         "Condiciones de crédito",
    "volatilidad":     "Estrés de mercado",
    "tendencia":       "Tendencia de mercado",
    "posicionamiento": "Extensión y valor relativo",
    "crecimiento":     "Crecimiento",
    "inflacion":       "Inflación",
    "liquidez":        "Condiciones monetarias",
}

# Que concepto de pilar es PLURAL. Existe porque la prosa concuerda el verbo con
# el: al pasar "la liquidez" a "las condiciones monetarias" la frase quedo en
# "las condiciones monetarias pesa en contra" (SEMANTIC-PASS 11).
CONCEPTO_PLURAL: frozenset[str] = frozenset({"liquidez"})


def concepto_verbo(pilar: str, singular: str, plural: str) -> str:
    """El verbo que concuerda con CONCEPTO_PILAR[pilar]."""
    return plural if pilar in CONCEPTO_PLURAL else singular


def dimension_breve(key: str, label: str = "") -> str:
    """El nombre de la dimension SIN el parentesis explicativo.

    El brief y el HTML tienen que llamar la fila igual (SEMANTIC-PASS 40), pero
    en una celda de PDF no cabe "(overlay de divisa)". Se quita el parentesis,
    no se inventa otro nombre.
    """
    return DIMENSION_NOMBRE.get(key, label or key).split(" (")[0]


def pilar_prosa(p: str) -> str:
    """El nombre del pilar tal como se escribe DENTRO de una frase.

    Existe para que la prosa no tenga que repetir la cadena a mano: cambiar
    PILAR_NOMBRE cambia tambien lo que dice el parrafo. Es lo que fallo con
    "la liquidez", que sobrevivio en el texto despues de que el pilar pasara a
    llamarse "Condiciones monetarias" (SEMANTIC-PASS 11).
    """
    return PILAR_NOMBRE.get(p, p).lower()


# Version corta, para la barra del grafico y las frases donde el nombre largo
# no cabe. Dice lo mismo; no es otro nombre.
PILAR_BREVE: dict[str, str] = {
    "credito":         "Crédito",
    "volatilidad":     "Estrés",
    "tendencia":       "Tendencia",
    "posicionamiento": "Extensión",
    "crecimiento":     "Crecimiento",
    "inflacion":       "Inflación",
    "liquidez":        "Cond. monetarias",
}

# ===== SEMANTIC-PASS 10 · tres estados, y dicen para qué lado =============
# «favorable / adverso» obliga a preguntarse «¿favorable para qué?». Research
# conserva el par tecnico; la vista PM usa estos tres.
LECTURA_PM = {"favorable": "Apoya riesgo", "adverso": "Frena riesgo",
              "neutral": "Neutral", "sin dato": "Sin dato"}
# La tension dominante se nombra por el pilar en el que vive, para que el
# enunciado no diga "la liquidez" cuando la tension esta en otro sitio.
# SPEC-7P 8: el sujeto de cada frase es el NOMBRE CANONICO del pilar, el mismo
# que lleva su barra en el grafico de fuerzas.
TENSION_FRASE: dict[str, str] = {
    # Esto nombra al INDICADOR QUE MAS CONTRADICE, no a la tension dominante.
    # Llamar "tension dominante" a un indicador suelto --mientras la cabecera
    # llamaba igual a una divergencia entre pilares-- es lo que hacia que la
    # pagina 1 dijera dos cosas distintas con el mismo nombre.
    "liquidez": "Las condiciones monetarias son lo que más contradice la lectura",
    "credito": "El crédito es lo que más contradice la lectura",
    "volatilidad": "La volatilidad es lo que más contradice la lectura",
    "tendencia": "La tendencia es lo que más contradice la lectura",
    "crecimiento": "El crecimiento es lo que más contradice la lectura",
    "inflacion": "La inflación es lo que más contradice la lectura",
    "posicionamiento": "El posicionamiento es lo que más contradice la lectura",
}

# Alias legible de cada tema, para poder mandar «#theme-duracion» en un mensaje
# (punto 24). La clave corta sigue siendo el id de la fila; esto es un ancla
# adicional, no un renombrado: los dos resuelven.
TEMA_ALIAS: dict[str, str] = {
    "rv": "renta-variable", "dur": "duracion", "cred": "credito",
    "cicl": "ciclico", "usd": "dolar", "mp": "materias-primas", "oro": "oro",
}


# ------------------------------------------------ LAS ESCALAS, DICHAS (D2 a)
# El documento usa cinco cifras con la misma pinta y tres significados. Sin una
# linea que las separe, «p75», «58/100» y «1.7σ» se leen como si midieran lo
# mismo, y no miden ni parecido.
ESCALAS_NOTA = (
    "Tres escalas distintas, con la misma pinta. <b>p75</b> dice <b>dónde está "
    "ese dato frente a su propia historia</b> de cinco años: p75 es más alto "
    "que el 75 % de los días. <b>58/100</b> y los niveles de las fuerzas son "
    "<b>notas de 0 a 100</b> en las que 50 es neutral y 100 es lo más "
    "favorable para tomar riesgo —no «mucho» ni «poco»—. <b>1.7σ</b> es "
    "<b>cuánto tendría que moverse</b> un dato para cruzar su umbral, medido "
    "en su propia variabilidad.")

# La misma advertencia en una línea, para el pie de la página 1 del PDF, donde
# la versión larga costaba un 9 % de la hoja y empujaba a una cuarta página.
ESCALAS_CORTA = ("<b>p75</b> más alto que el 75 % de su historia · "
                 "<b>58/100</b> nota, 50 neutral · <b>1.7σ</b> cuánto le "
                 "falta para cruzar el umbral")

# «ctx» junto a un pilar en el gráfico de fuerzas (D2 b).
CTX_NOTA = "contexto — no vota dirección"

# La relación del bloque macro con el técnico (D2 d). La regla ya existe
# --_relacion(), con sus umbrales-- pero la palabra se perdió al comprimir la
# prosa en tarjetas, y con ella la explicación de por qué la convicción es
# media y no alta.
RELACION_TXT = {
    "confirma":   "confirma al técnico",
    "atempera":   "atempera al técnico",
    "contradice": "contradice al técnico",
    "acompaña":   "acompaña al técnico",
}
RELACION_GLOSA = {
    "confirma":   "la macro empuja del mismo lado y con fuerza parecida",
    "atempera":   ("la macro va del mismo lado pero con menos fuerza: por eso "
                   "la confianza no llega a alta"),
    "contradice": "la macro apunta al lado contrario del técnico",
    "acompaña":   "no hay lectura suficiente para medir el acuerdo",
}


# ------------------------------------------------- SEVERIDAD DEL QA (punto 18)
# ERROR   el documento afirma algo falso, o dos partes se contradicen. No sale.
# AVISO   algo que el gestor tiene que ponderar antes de fiarse de la lectura.
# INFO    el MERCADO discrepa, o falta un dato de contexto. No es un fallo del
#         documento: es el estado del mundo, y el documento lo esta contando
#         bien. Marcarlo en rojo entrena a ignorar el rojo.
#
# La regla dura: una divergencia del modelo o un indicador en contra NUNCA son
# ERROR. Que el mercado no se ponga de acuerdo consigo mismo es informacion, y
# de hecho es la informacion que mas veces mueve la conviccion.
QA_INFO = {
    "Contradicciones de alto perfil",
    "Divergencias dentro de un mismo pilar",
    "Divergencias entre pilares",
    "Indicadores en extremo",
    "Variables de entorno sin dato",
    "Dirección del eje frente a su etiqueta",
    "Cobertura de indicadores",
}
QA_SEV_TXT = {"error": "ERROR", "aviso": "AVISO", "info": "INFO", "ok": "OK",
              "nd": "INFO"}


# ------------------------------------------------------ analogos historicos
# El "vector de estado" de una fecha son sus 7 pilares (0-100). El parecido
# entre dos fechas es la raiz del error cuadratico medio entre sus vectores,
# en puntos de percentil: 0 = identicas, y cada punto es la diferencia media
# por pilar. Se buscan las fechas mas parecidas a hoy y se mira que paso
# DESPUES de ellas -- lo cual es legitimo porque son pasado, no futuro.
#
# CRITERIO POR UMBRAL, NO "LOS 5 MAS CERCANOS". Se toman TODOS los episodios por
# debajo de un umbral en las DOS distancias (dinamica y entorno), uno por
# episodio y con doce meses de separacion. En un estado comun eso da 8-15
# episodios; con 5 fechas no habia nada que promediar, y un intervalo sobre 5
# observaciones seriadas seria falsa precision. La salida no es mas estadistica,
# es mas muestra -- y cuando califican pocos, ESO es el dato (estado inusual).
ANALOG_DIST_MAX = 20.0          # umbral de distancia DINAMICA para entrar
ANALOG_ENV_INCLUDE = 2.00       # umbral de distancia de ENTORNO (sigmas) para entrar
ANALOG_N_MAX = 20               # techo estructural: ~20 episodios independientes en 21 anos
# Por debajo de tantos episodios comparables, no se promedia: se escribe "estado
# inusual" con la causa (normalmente el nivel de tasas reales o de inflacion).
ANALOG_MIN_REPORT = 5
# Por debajo de esta ventana ELEGIBLE no hay con que comparar: los analogos no
# son informativos y se dice ARRIBA, no en letra pequena. En 2008 la ventana son
# 2.5 anos (2005-2007): promediar ahi seria fingir una muestra.
ANALOG_VENTANA_MIN_ANOS = 5.0
# Consistencia direccional por clase: hay patron si una direccion reune al menos
# esta fraccion de los episodios. Con muestras pequenas el signo es mucho mas
# estable que la media; sin mayoria clara no hay patron (el rango, que se
# muestra, ya ensena la dispersion). Reemplaza al criterio de ancho de rango,
# que no escalaba: con 14 episodios en 21 anos casi todo cruza cero.
ANALOG_PATRON_FRAC = 0.65
# Mayoria minima para que una clase con patron DISCREPE de su inclinacion. Vive
# aqui y no en el render: es una decision de inversion, no de presentacion.
ANALOG_DISC_FRAC = 0.65
# Separacion minima entre analogos: DOCE MESES. Con noventa dias, varios
# analogos podian ser el mismo episodio muestreado varias veces, y la dispersion
# parecia estrecha por correlacion en serie, no por estabilidad del desenlace.
ANALOG_MIN_GAP_DAYS = 365
ANALOG_FWD_MIN_DAYS = 365       # el candidato necesita 12m de futuro para "que paso"
ANALOG_HORIZONS = [3, 6, 12]    # meses hacia delante que se reportan
# Si ni el mas parecido baja de este umbral, hoy no tiene ningun comparable.
ANALOG_NEAR_MAX = 14.0
# Etiqueta de calidad por distancia (RMS en puntos): (umbral, palabra). Alineada
# con el umbral de inclusion: lo que entra se etiqueta "parecido" o mejor.
ANALOG_QUALITY = [(12.0, "muy parecido"), (20.0, "parecido")]  # por encima: "lejano"

# TRAYECTORIA, NO SOLO NIVEL. Al vector de dinamica se le anaden los cambios a
# 1 y 3 meses de cada pilar, con la mitad de peso que el nivel: un estado
# identico al que se llega desde arriba no es el mismo que si se llega desde
# abajo.
ANALOG_DELTA_WEIGHT = 0.5

# ------------------------------------------------------ entorno (nivel real)
# La segunda distancia. La de dinamica dice si el mercado se comporta parecido;
# esta dice si el mundo es parecido. Va sobre NIVELES ABSOLUTOS estandarizados
# sobre toda la historia conocida en la fecha del snapshot -- sin percentil
# movil, que es lo que borra el nivel. Ver snapshot/entorno.py.
# (clave, etiqueta, fuente, id, formato, unidad)
ENV_VARS = [
    ("real_10y", "Tasa real a 10 años",           "panel", "real_10y",     "{:+.2f}", "%"),
    ("infl",     "Inflación subyacente (PCE)",    "panel", "core_pce",     "{:.1f}",  "%"),
    ("ffr",      "Tasa de referencia",            "macro", "DFF",          "{:.2f}",  "%"),
    ("curva",    "Curva 10a−3m",                  "panel", "curve_10y3m",  "{:+.2f}", " pp"),
    ("val_rv",   "Valuación de la bolsa (PER adelantado)",
                                                  "bbg",   "spx_fwd_pe",   "{:.1f}",  "x"),
    ("balance",  "Balance de la Fed (cambio 6m)", "calc",  "walcl_6m",     "{:+.1f}", "%"),
]
# Minimo de variables con dato para que la distancia de entorno sea publicable.
ENV_MIN_VARS = 4
# Calidad del entorno por distancia (RMS en desviaciones tipicas), alineada con
# el umbral de inclusion de entorno.
ANALOG_ENV_QUALITY = [(1.00, "muy parecido"), (2.00, "parecido")]  # arriba: "muy distinto"
# Un episodio nuevo empieza cuando el entorno se ha movido mas de esto respecto
# al inicio del episodio en curso. Sigue usandose para segmentar la muestra.
ANALOG_EPISODE_STEP = 1.50

# Un ETF (o par) que representa cada dimensión de posicionamiento, para ver qué pasó DESPUÉS
# de cada análogo. (clave, sigla, etiqueta, ticker, ticker2). Si hay ticker2 se
# muestra el diferencial ticker − ticker2 (cíclico vs. defensivo). Crédito va
# en dos: grado de inversión (LQD) y alto rendimiento (HYG), que se comportan
# distinto -- LQD carga más duración, HYG más riesgo de crédito.
ANALOG_ETFS = [
    ("rv",   "RV",   "Renta variable (SPY)",         "SPY", None),
    ("dur",  "Dur",  "Duración (TLT)",               "TLT", None),
    ("ig",   "IG",   "Grado de inversión (LQD)",     "LQD", None),
    ("hy",   "HY",   "Alto rendimiento (HYG)",       "HYG", None),
    ("cicl", "Cícl", "Cíclico − defensivo (XLY−XLP)", "XLY", "XLP"),
    ("mp",   "MP",   "Materias primas (DBC)",        "DBC", None),
    ("oro",  "Oro",  "Oro (GLD)",                    "GLD", None),
    ("usd",  "USD",  "Dólar (UUP)",                  "UUP", None),
]
# El horizonte de la matriz por análogo (meses). El resto de horizontes sigue
# en ANALOG_HORIZONS para otros usos, pero la tabla por análogo usa este.
ANALOG_MATRIX_H = 12

# ------------------------------------------------------------- indicadores
# signo: +1 -> valor alto es FAVORABLE para activos de riesgo / expansion
#        -1 -> valor alto es ADVERSO
# El signo NO altera el valor mostrado ni su percentil: solo su lectura.
INDICATORS: list[dict] = [
    # ---------------------------------------------------- credito
    # Diferenciales OAS reales de Bloomberg (LF98OAS, LUACOAS), diarios desde
    # 2000 y cacheados. Sustituyen al proxy de Moody's Baa/Aaa que se usaba
    # porque FRED recorta los indices ICE a 3 anos: ahora el credito es el
    # diferencial de alto rendimiento de verdad, que es la senal de estres.
    dict(key="hy_oas", pillar="credito", horizon="intermediate", sign=-1,
         label="Diferencial de alto rendimiento (OAS)", unit="pp", fmt="{:.2f}", dfmt="{:+.2f}",
         src="Bloomberg LF98OAS"),
    dict(key="ig_oas", pillar="credito", horizon="intermediate", sign=-1,
         label="Diferencial de grado de inversión (OAS)", unit="pp", fmt="{:.2f}", dfmt="{:+.2f}",
         src="Bloomberg LUACOAS"),
    dict(key="hy_minus_ig", pillar="credito", horizon="intermediate", sign=-1,
         label="Prima del alto rendimiento sobre el grado de inversión", unit="pp", fmt="{:.2f}", dfmt="{:+.2f}",
         src="Bloomberg, diferencia"),
    dict(key="nfci", pillar="credito", horizon="intermediate", sign=-1,
         label="Condiciones financieras (NFCI)", unit="", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED NFCI"),
    dict(key="hyg_vs_ief", pillar="credito", horizon="intermediate", sign=+1,
         label="Crédito frente a tesoro (HYG/IEF, 3m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo HYG, IEF"),

    # ---------------------------------------------------- volatilidad
    dict(key="vix", pillar="volatilidad", horizon="tactical", sign=-1,
         label="VIX", unit="", fmt="{:.1f}", dfmt="{:+.1f}",
         src="Yahoo ^VIX"),
    dict(key="vix_vs_3m", pillar="volatilidad", horizon="tactical", sign=-1,
         label="VIX frente a su media de 3 meses", unit="%", fmt="{:+.0f}", dfmt="{:+.0f}",
         src="Yahoo ^VIX"),
    dict(key="rvol_spx", pillar="volatilidad", horizon="tactical", sign=-1,
         label="Volatilidad realizada del S&P (60d)", unit="%", fmt="{:.1f}", dfmt="{:+.1f}",
         src="Yahoo SPY"),
    dict(key="dd_spx", pillar="volatilidad", horizon="tactical", sign=+1,
         label="Caída desde máximos del S&P", unit="%", fmt="{:.1f}", dfmt="{:+.1f}",
         src="Yahoo SPY"),
    dict(key="gold_vs_spx", pillar="volatilidad", horizon="intermediate", sign=-1,
         label="Oro frente a bolsa (3m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo GLD, SPY"),

    # ---------------------------------------------------- tendencia
    dict(key="breadth_200", pillar="tendencia", horizon="tactical", sign=+1,
         label="Cesta de riesgo sobre su media de 200 días", unit="%", fmt="{:.0f}", dfmt="{:+.0f}",
         src="Yahoo, 14 activos"),
    # Momentum a 12 meses SIN saltarse el ultimo mes. La convencion 12-1 del
    # factor momentum existe para evitar la reversion de corto plazo al
    # construir carteras; aqui describiriamos el mercado ignorando el mes mas
    # informativo, que en una caida es justo el que importa.
    dict(key="spx_12m", pillar="tendencia", horizon="estructural", sign=+1,
         label="Momentum del S&P a 12 meses", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo SPY"),
    dict(key="risk_6m", pillar="tendencia", horizon="intermediate", sign=+1,
         label="Momentum mediano de la cesta de riesgo (6m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo, 14 activos"),
    dict(key="spx_vs_200", pillar="tendencia", horizon="intermediate", sign=+1,
         label="S&P frente a su media de 200 días", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo SPY"),
    dict(key="bonds_vs_spx", pillar="tendencia", horizon="intermediate", sign=-1,
         label="Bonos largos frente a bolsa (3m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo TLT, SPY"),

    # ---------------------------------------------------- posicionamiento
    dict(key="spx_ext_3y", pillar="posicionamiento", horizon="tactical", sign=-1,
         label="Sobreextensión del S&P sobre su tendencia de 3 años", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo SPY"),
    dict(key="eq_vs_bonds", pillar="posicionamiento", horizon="estructural", sign=-1,
         label="Bolsa frente a bonos, acumulado de 3 años", unit="%", fmt="{:+.0f}", dfmt="{:+.0f}",
         src="Yahoo SPY, IEF"),
    dict(key="eq_vs_gold", pillar="posicionamiento", horizon="estructural", sign=-1,
         label="Bolsa frente a oro, acumulado de 3 años", unit="%", fmt="{:+.0f}", dfmt="{:+.0f}",
         src="Yahoo SPY, GLD"),
    dict(key="credit_comp", pillar="posicionamiento", horizon="intermediate", sign=+1,
         label="Compensación del crédito por unidad de riesgo", unit="x", fmt="{:.3f}", dfmt="{:+.3f}",
         src="Bloomberg HY OAS / vol. S&P"),
    # El oro vive en este pilar y no en tendencia a proposito: metido en
    # tendencia, con signo de refugio, arrastraba el eje de riesgo hacia abajo
    # cada vez que el oro subia acompanando a la bolsa, que es lo que lleva
    # pasando. Aqui no toca ningun eje y se lee por lo que es: cuanto se ha
    # pagado ya. Los dos indicadores se contradicen a proposito -- uno mide
    # tendencia y otro cuanto lleva estirada -- y esa tension se ve en el voto.
    dict(key="gold_12m", pillar="posicionamiento", horizon="estructural", sign=-1,
         label="Momentum del oro a 12 meses", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo GC=F"),
    dict(key="gold_ext_200", pillar="posicionamiento", horizon="tactical", sign=-1,
         label="Oro frente a su media de 200 días", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo GC=F"),

    # ---------------------------------------------------- crecimiento
    dict(key="claims_4w", pillar="crecimiento", horizon="intermediate", sign=-1,
         label="Peticiones de desempleo (media de 4 semanas)", unit="mil", fmt="{:.0f}", dfmt="{:+.0f}",
         src="FRED ICSA"),
    dict(key="sahm", pillar="crecimiento", horizon="estructural", sign=-1,
         label="Regla de Sahm", unit="pp", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED SAHMREALTIME"),
    dict(key="payems_3m", pillar="crecimiento", horizon="estructural", sign=+1,
         label="Nóminas, ritmo de 3 meses anualizado", unit="%", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED PAYEMS"),
    dict(key="indpro_yoy", pillar="crecimiento", horizon="estructural", sign=+1,
         label="Producción industrial interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED INDPRO"),
    dict(key="permits_yoy", pillar="crecimiento", horizon="estructural", sign=+1,
         label="Permisos de construcción interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED PERMIT"),
    dict(key="retail_yoy", pillar="crecimiento", horizon="estructural", sign=+1,
         label="Ventas minoristas reales interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED RRSFS"),
    dict(key="umcsent", pillar="crecimiento", horizon="intermediate", sign=+1,
         label="Confianza del consumidor (Michigan)", unit="", fmt="{:.1f}", dfmt="{:+.1f}",
         src="FRED UMCSENT"),
    dict(key="copper_gold", pillar="crecimiento", horizon="intermediate", sign=+1,
         label="Cobre frente a oro (6m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo HG=F, GC=F"),
    dict(key="cyc_vs_def", pillar="crecimiento", horizon="intermediate", sign=+1,
         label="Cíclico frente a defensivo (XLY/XLP, 3m)", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="Yahoo XLY, XLP"),
    dict(key="curve_10y3m", pillar="crecimiento", horizon="estructural", sign=+1,
         label="Curva de tasas, 10 años menos 3 meses", unit="pp", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED T10Y3M"),

    # ---------------------------------------------------- inflacion
    dict(key="cpi_yoy", pillar="inflacion", horizon="estructural", sign=-1,
         label="IPC general interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED CPIAUCSL"),
    dict(key="cpi_3m", pillar="inflacion", horizon="intermediate", sign=-1,
         label="IPC, ritmo de 3 meses anualizado", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED CPIAUCSL"),
    dict(key="core_pce", pillar="inflacion", horizon="estructural", sign=-1,
         label="PCE subyacente interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED PCEPILFE"),
    dict(key="ppi_yoy", pillar="inflacion", horizon="estructural", sign=-1,
         label="Precios al productor interanual", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED PPIACO"),
    dict(key="be5y", pillar="inflacion", horizon="intermediate", sign=-1,
         label="Inflación implícita a 5 años", unit="%", fmt="{:.2f}", dfmt="{:+.2f}",
         src="FRED T5YIE"),
    dict(key="be10y", pillar="inflacion", horizon="estructural", sign=-1,
         label="Inflación implícita a 10 años", unit="%", fmt="{:.2f}", dfmt="{:+.2f}",
         src="FRED T10YIE"),

    # ---------------------------------------------------- liquidez
    dict(key="real_10y", pillar="liquidez", horizon="intermediate", sign=-1,
         label="Tasa real a 10 años", unit="%", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED DFII10"),
    dict(key="dgs2", pillar="liquidez", horizon="intermediate", sign=-1,
         label="Bono del Tesoro a 2 años", unit="%", fmt="{:.2f}", dfmt="{:+.2f}",
         src="FRED DGS2"),
    dict(key="dff_12m", pillar="liquidez", horizon="estructural", sign=-1,
         label="Tasa de referencia, cambio en 12 meses", unit="pp", fmt="{:+.2f}", dfmt="{:+.2f}",
         src="FRED DFF"),
    dict(key="netliq_3m", pillar="liquidez", horizon="intermediate", sign=+1,
         label="Liquidez neta de la Fed, cambio en 3 meses", unit="mm$", fmt="{:+.0f}", dfmt="{:+.0f}",
         src="FRED WALCL-RRP-TGA"),
    dict(key="dollar_3m", pillar="liquidez", horizon="intermediate", sign=-1,
         label="Dólar amplio, cambio en 3 meses", unit="%", fmt="{:+.1f}", dfmt="{:+.1f}",
         src="FRED DTWEXBGS"),
]

# ------------------------------------------------------------- horizontes
# TIMING != HORIZONTE (SPEC 3.2). El HORIZONTE es propiedad del INDICADOR y se
# DECLARA aqui, nunca se infiere: el VIX habla de semanas y la regla de Sahm de
# trimestres. El TIMING es propiedad de la DECISION, y se calcula UNICAMENTE con
# indicadores de horizonte tactico -- un indicador de regimen no puede moverlo.
HORIZONS = {
    "tactical":     "dias a ~1 mes",
    "intermediate": "~1-3 meses",
    "estructural":  "~6-12 meses",
}
# Solo estos pueden influir en el timing (ver SPEC 5.3).
HORIZON_TIMING = "tactical"

INDICATOR_BY_KEY = {d["key"]: d for d in INDICATORS}

# Invariante: los 42 indicadores declaran horizonte, y es uno de la taxonomia.
_sin_h = [d["key"] for d in INDICATORS if d.get("horizon") not in HORIZONS]
assert not _sin_h, f"indicadores sin horizonte valido: {_sin_h}"

PILLAR_KEYS = {p: [d["key"] for d in INDICATORS if d["pillar"] == p] for p in PILLARS}

# Nombre CORTO de cada indicador, para citarlo como evidencia en la lectura
# ("cobre/oro p99, curva +0.88pp"). El label completo es demasiado largo para
# una linea; esto es lo que se muestra junto a su nivel.
SHORT: dict[str, str] = {
    "hy_oas": "HY OAS", "ig_oas": "IG OAS", "hy_minus_ig": "prima HY−IG",
    "nfci": "NFCI", "hyg_vs_ief": "HYG/IEF",
    "vix": "VIX", "vix_vs_3m": "VIX vs 3m", "rvol_spx": "vol. realizada",
    "dd_spx": "caída desde máx.", "gold_vs_spx": "oro/bolsa",
    "breadth_200": "amplitud 200d", "spx_12m": "momentum 12m",
    "risk_6m": "momentum 6m", "spx_vs_200": "S&P vs 200d",
    "bonds_vs_spx": "bonos/bolsa",
    "spx_ext_3y": "sobreext. S&P", "eq_vs_bonds": "bolsa/bonos 3a",
    "eq_vs_gold": "bolsa/oro 3a", "credit_comp": "comp. crédito",
    "gold_12m": "oro 12m", "gold_ext_200": "oro vs 200d",
    "claims_4w": "paro semanal", "sahm": "regla de Sahm", "payems_3m": "nóminas 3m",
    "indpro_yoy": "prod. industrial", "permits_yoy": "permisos",
    "retail_yoy": "ventas minoristas", "umcsent": "Michigan",
    "copper_gold": "cobre/oro", "cyc_vs_def": "cícl/def", "curve_10y3m": "curva 10a−3m",
    "cpi_yoy": "IPC interanual", "cpi_3m": "IPC 3m", "core_pce": "PCE subyacente",
    "ppi_yoy": "PPI", "be5y": "breakeven 5a", "be10y": "breakeven 10a",
    "real_10y": "tasa real 10a", "dgs2": "tesoro 2a", "dff_12m": "tasa ref. 12m",
    "netliq_3m": "liquidez neta", "dollar_3m": "dólar 3m",
}

# Cobertura minima: si menos de esta fraccion de los indicadores de un pilar
# tiene dato, el pilar sale vacio en vez de salir sesgado por los que quedan.
MIN_PILLAR_COVERAGE = 0.50

# --------------------------------------------------------- fechas de control
VALIDATION_DATES = ["2008-09-15", "2020-03-16", "2021-11-01", "2022-06-15"]


# ============================================================================
# CLASES DE ACTIVO
# ============================================================================
# Cada indicador, segun este ALTO o BAJO, empuja a favor o en contra de cada
# exposicion. Esto no es una cartera: es la traduccion de una senal suelta a
# la exposicion sobre la que habla. Sumarlas da un recuento de votos, no un
# peso.
ASSET_CLASSES: dict[str, dict] = {
    "rv":   dict(label="Renta variable",              short="RV",
                 mas="sobreponderar",  menos="infraponderar", mas_s="sobre",      menos_s="infra"),
    "dur":  dict(label="Duración",                    short="DUR",
                 mas="larga",          menos="corta",         mas_s="larga",      menos_s="corta"),
    "cred": dict(label="Calidad de crédito",          short="CRÉD",
                 mas="bajar calidad",  menos="subir calidad", mas_s="bajar cal.", menos_s="subir cal."),
    "cicl": dict(label="Cíclico vs. defensivo",       short="CÍCL",
                 mas="cíclico",        menos="defensivo",     mas_s="cíclico",    menos_s="defensivo"),
    "usd":  dict(label="Dólar",                       short="USD",
                 mas="sobreponderar",  menos="infraponderar", mas_s="sobre",      menos_s="infra"),
    "mp":   dict(label="Materias primas",             short="MP",
                 mas="sobreponderar",  menos="infraponderar", mas_s="sobre",      menos_s="infra"),
    "oro":  dict(label="Oro",                         short="ORO",
                 mas="sobreponderar",  menos="infraponderar", mas_s="sobre",      menos_s="infra"),
}

# ------------------------------------------------------- postura por clase
# La señal de cada clase se resume en un score de 0 a 100 (50 = neutral, alto
# = favorable a la clase). La clase se inclina solo si el voto no está dividido
# y la señal supera un mínimo; la fuerza (leve/clara/fuerte) sale de cuán
# extrema es. Un solo mensaje por clase, no tres.
POSTURA_MIN_DEPTH = 10        # por debajo de esto, neutral (señal demasiado floja)
POSTURA_TIERS = [(40, "fuerte"), (25, "clara"), (10, "leve")]

# Cohesión de voto (|a favor − en contra| / total) por debajo de la cual la
# clase se considera "dividida" -> neutral, sin dirección clara.
POSTURA_CONSENSO_MIN = 0.34

# Razón en lenguaje llano de cada inclinación, para el documento informativo.
# No nombra indicadores técnicos: da el porqué estructural de esa clase.
# Razones en lenguaje llano. Son DESCRIPTIVAS -- dicen qué señal domina, no
# defienden una cadena causal discutible. Evitan comprometerse de más: donde
# hay una fuerza en contra (tasas reales para la duración, diferenciales
# estrechos para el crédito) se dice que la señal no es unánime en vez de
# afirmar un porqué de un solo lado.
CLASS_REASONS: dict[str, dict[str, str]] = {
    "rv":   dict(mas="la tendencia y el apetito de riesgo acompañan",
                 menos="el riesgo pesa más que la tendencia",
                 neutral="la tendencia empuja, pero ya se ha pagado caro: señal mixta"),
    "dur":  dict(mas="pesan las señales de refugio o de recortes de tasas",
                 menos="el pulso del ciclo inclina a menos plazo; la señal no es unánime",
                 neutral="crecimiento y tasas no coinciden: señal mixta"),
    "cred": dict(mas="crédito tranquilo, poco estrés; es señal de entorno, no de que esté barato",
                 menos="el crédito muestra estrés: pesa más la calidad",
                 neutral="el crédito no da una señal clara"),
    "cicl": dict(mas="el ciclo acompaña a lo que sube con la economía",
                 menos="la economía flaquea: pesa lo defensivo",
                 neutral="el ciclo no manda en una dirección clara"),
    "usd":  dict(mas="la aversión al riesgo y las tasas altas tienden a apoyar al dólar",
                 menos="las condiciones holgadas y el apetito de riesgo le restan",
                 neutral="las fuerzas sobre el dólar se equilibran"),
    "mp":   dict(mas="la demanda cíclica y la inflación al alza acompañan",
                 menos="ciclo e inflación flojos no las apoyan",
                 neutral="ciclo e inflación no dan una señal clara"),
    "oro":  dict(mas="tasas reales bajas o demanda de refugio lo empujan",
                 menos="las tasas reales altas le restan",
                 neutral="tasas reales en contra, refugio a favor: en equilibrio"),
}

# Razon CORTA para la lectura: maximo 8 palabras, sobre el MERCADO, nunca sobre
# el documento. Es lo unico que se muestra en la seccion 1 junto a cada
# inclinacion. La version larga de arriba y el rastro (que la limita, que
# indicadores pesan) viven en el tablero.
CLASS_REASONS_CORTAS: dict[str, dict[str, str]] = {
    "rv":   dict(mas="tendencia y apetito acompañan",
                 menos="el riesgo pesa más que la tendencia",
                 neutral="tendencia y precio tiran en contra"),
    "dur":  dict(mas="refugio y recortes de tasas pesan",
                 menos="el ciclo pide menos plazo",
                 neutral="crecimiento y tasas no coinciden"),
    "cred": dict(mas="crédito tranquilo, sin estrés",
                 menos="el crédito muestra estrés",
                 neutral="el crédito no da señal clara"),
    "cicl": dict(mas="el ciclo acompaña",
                 menos="la economía flaquea",
                 neutral="el ciclo no manda"),
    "usd":  dict(mas="aversión y tasas altas lo apoyan",
                 menos="condiciones holgadas y apetito le restan",
                 neutral="fuerzas sobre el dólar en equilibrio"),
    "mp":   dict(mas="demanda cíclica e inflación acompañan",
                 menos="ciclo e inflación flojos",
                 neutral="ciclo e inflación sin señal clara"),
    "oro":  dict(mas="tasas reales bajas o refugio",
                 menos="las tasas reales altas le restan",
                 neutral="refugio y tasas reales se compensan"),
}

# Eje relevante para el RUMBO de cada clase y el signo de su inclinacion "mas"
# respecto a ese eje: (eje, beta). beta=+1 si la direccion "mas" de la clase se
# beneficia de que el eje SUBA. Sirve para bajar (o subir) la conviccion cuando
# el eje se mueve fuerte en contra (o a favor) de la inclinacion -- la
# diferencia entre "las senales coinciden" y "coinciden y no se estan dando la
# vuelta".
# Nombre corto de pilar (para la causa del clima: "por volatilidad y momentum",
# no "por volatilidad y estrés y tendencia y momentum").
# SPEC-7P 8: DERIVADO del nombre canonico, no una segunda lista. Era una lista
# aparte y decia "momentum" donde el grafico decia "Tendencia": dos nombres para
# el mismo pilar, que es justo lo que esta pasada viene a quitar.
PILAR_CORTO: dict[str, str] = {k: v.lower() for k, v in PILAR_NOMBRE.items()}

CLASS_AXIS: dict[str, tuple[str, int]] = {
    "rv":   ("riesgo", +1),
    "cred": ("riesgo", +1),
    "cicl": ("ciclo",  +1),
    "mp":   ("ciclo",  +1),
    "dur":  ("ciclo",  -1),
    "usd":  ("riesgo", -1),
    "oro":  ("riesgo", -1),
}

# Nombre corto de cada clase, para nombrarlas en la coherencia de la sintesis
# ("la postura pro-riesgo se expresa por credito, lo ciclico y materias primas").
CLASS_CORTO: dict[str, str] = {
    "rv":   "renta variable", "dur": "duración", "cred": "crédito",
    "cicl": "lo cíclico",     "usd": "el dólar", "mp":   "materias primas",
    "oro":  "oro",
}

# ------------------------------------------------------ conviccion por clase
# UNA CONTRADICCION NO SE ELIMINA: SE RESUELVE DENTRO DE LA CONCLUSION.
#
# El documento enunciaba una inclinacion y ponia su refutacion al lado, con el
# mismo peso visual, y quien leia se quedaba sin saber que se concluia. La
# divergencia sigue siendo la informacion que distingue a este producto; lo que
# cambia es DONDE vive: dentro de la conclusion, como conviccion, no junto a
# ella como contra-argumento.
#
# La regla es MECANICA, no de ojo. Se evalua en este orden:
#   1. si el voto ya estaba dividido o era muy flojo    -> NEUTRAL
#   2. cohesion efectiva por debajo de CONV_EMPATE      -> NEUTRAL (no alcanza)
#   3. un extremo la contradice, o cohesion < REPARTIDA -> BAJA
#   4. cohesion < CONV_CLARA, o una divergencia entre pilares que parte a esta
#      clase                                            -> MEDIA
#   5. resto                                            -> ALTA
#
# "Cohesion efectiva" = (a favor - en contra) / (a favor + en contra) contado en
# SENALES INDEPENDIENTES, no en indicadores. Es lo que evita que una clase salga
# con conviccion alta porque cuatro filas del mismo pilar dicen lo mismo.
#
# VA CON SIGNO, Y ESO IMPORTA. Puede salir NEGATIVA: el voto crudo apunta a un
# lado y las senales distintas al otro. Pasa mas de lo que uno esperaria -- en
# septiembre de 2008 la duracion salia "larga" por 23 votos contra 9 y en
# senales independientes era 2,7 contra 3,4, o sea al reves. Cuando eso ocurre
# la conclusion es NEUTRAL: el documento no inventa la direccion contraria, pero
# tampoco afirma una que sus propias senales no sostienen.
#
# El paso 2 es el que hace consistente el documento: si la evidencia no alcanza
# para una direccion, la conclusion es NEUTRAL dicha claramente. No existe
# "sobreponderar con conviccion muy baja".
#
# Umbrales calibrados sobre las cinco fechas (35 casos): mediana 0,15, p75 0,29,
# p90 0,39. Con ellos salen unas dos convicciones altas de cada 35, que es lo que
# debe ser: alta conviccion tiene que ser rara para significar algo.
CONV_EMPATE = 0.10        # por debajo (o negativa): no alcanza -> neutral
CONV_REPARTIDA = 0.18     # por debajo: repartidas casi por igual -> baja
CONV_CLARA = 0.35         # por debajo: mayoria clara pero no unanime -> media
CONV_ORDEN = {"alta": 3, "media": 2, "baja": 1}
# SEMANTIC-PASS 13: en la vista PM se llama CONFIANZA. «Convicción» es el
# termino tecnico y se queda en Research y en la metodologia.
CONVICCION_PM = "Confianza"

# La ANTIGUEDAD del extremo modula su peso en la conviccion. Un extremo recien
# llegado es una advertencia; uno que lleva doce semanas en su sitio sin que la
# tendencia se rompa es informacion que el mercado ya absorbio, y no deberia
# arrastrar cuatro clases a conviccion baja el. Se traduce en cuanto puede
# rebajar la conviccion de la clase que contradice:
#   < 4 semanas  -> pesa completo: puede llevarla hasta BAJA (como antes)
#   4 a 12 sem   -> pesa la mitad:  puede llevarla como mucho a MEDIA
#   > 12 semanas -> pesa un tercio: no la rebaja, solo se anota
# Y se dice en el documento: "lleva 12 semanas en p99 sin que la tendencia se
# rompa, asi que pesa menos" es en si misma una lectura util.
EXTREMO_EDAD_PESO = [(4, 1.0), (12, 0.5)]   # (semanas_max, peso)
EXTREMO_PESO_MIN = 1.0 / 3.0                 # por encima de la ultima banda
# Techo de conviccion segun el peso del extremo. REGLA DURA: un extremo en
# contra, por viejo que sea, NUNCA deja llegar a "alta". Un extremo reciente
# (peso alto) ademas la limita a "baja". "Alta" queda reservada para clases sin
# NINGUN extremo en contra, ni reciente ni antiguo.
EXTREMO_TECHO = [(0.9, "baja")]     # (peso_min, techo); por debajo -> "media"
EXTREMO_TECHO_DEFECTO = "media"

# La conviccion mira el RUMBO, no solo el corte de hoy. Si el eje relevante para
# una clase se movio mas de esto (en puntos, un mes) EN CONTRA de la
# inclinacion, la conviccion baja un nivel; a favor, puede subir uno (sujeto al
# techo del extremo).
CONV_RUMBO_PTS = 8.0

# Un pilar con mas de esta fraccion de sus pares posibles en contradiccion no
# tiene una lectura unificada: su agregado se calcula pero se marca, y una clase
# que depende sobre todo de el no puede tener conviccion alta.
CONV_PILAR_INCOHERENTE = 0.30

# Si mas de estas clases salen "alta" el mismo dia, la etiqueta deja de
# significar algo (es la mayoria): se avisa en las comprobaciones.
CONV_ALTA_MAX = 3

# "Que cambio desde el anterior": un pilar tiene que moverse al menos esto (en
# puntos de su score 0-100) para que el cambio se reporte como relevante.
CAMBIO_PILAR_PTS = 8.0

# --------------------------------------- contradicciones: que estaria en juego
# Cuando un indicador en percentil extremo apunta al contrario que la
# inclinacion de su clase, no basta con senalarlo: hay que decir QUE IMPLICARIA
# si resulta que el que tiene razon es el que va solo, y QUE HABRIA QUE VER para
# saberlo. Lo segundo se calcula (el valor al que dejaria de ser extremo); lo
# primero se escribe aqui.
#
# UNA FRASE POR INDICADOR, NO UNA POR CLASE. La version anterior repetia una
# plantilla por cada clase afectada -- "el dolar se fortaleceria en contra de la
# lectura general" -- que es la definicion de contradecir, no informacion. La
# frase tiene que decir algo que NO se deduzca del enunciado: por que ese
# indicador podria ir por delante del resto, o que mecanismo se estaria pasando
# por alto. Lo que no este aqui usa un respaldo calculado (ver build.py) que
# nombra el pilar que quedaria por delante.
CONTRA_IMPLICA: dict[str, str] = {
    "real_10y":
        "el costo del dinero manda sobre el crecimiento. La bolsa y la tasa real llevan "
        "subiendo juntas, que es lo normal cuando el motor es el crecimiento; si el motor "
        "fuera la prima de plazo, lo mismo que hoy acompaña pasaría a comprimir múltiplos",
    "hy_oas":
        "el crédito estaría girando antes que la bolsa, que es el orden habitual. Con el "
        "diferencial tan estrecho el margen para amortiguar es mínimo: casi todo el "
        "movimiento tendría que venir del precio, no del carry",
    "ig_oas":
        "el deterioro empezaría por la parte de más calidad, que es lo contrario del guion "
        "de siempre y suele señalar un problema de tasas más que de solvencia",
    "nfci":
        "las condiciones financieras son el canal por el que la política monetaria llega a "
        "los precios; si se tensan desde este nivel, aprieta a la vez a crédito, bolsa y "
        "ciclo, no a uno solo",
    "vix":
        "la calma sería precio y no ausencia de riesgo. Cubrirse nunca ha sido tan barato "
        "como justo antes de necesitarlo, y desde niveles así el movimiento suele ser "
        "rápido más que grande",
    "spx_ext_3y":
        "el recorrido ya estaría pagado. La tendencia seguiría intacta y aun así quedaría "
        "poco por delante, que es la situación que suele preceder a una digestión larga "
        "más que a una caída",
    "eq_vs_bonds":
        "el liderazgo cambiaría de manos. Tres años de ventaja acumulada de la bolsa sobre "
        "los bonos se revierten en trimestres, no en años, y el punto de giro nunca se "
        "reconoce desde la tendencia",
    "eq_vs_gold":
        "lo que se estaría agotando no es la bolsa sino la moneda en la que se mide: el "
        "oro lleva ganando terreno y eso suele ir antes que un cambio de régimen monetario",
    "cpi_3m":
        "el dato corto va por delante del interanual por construcción. Si acierta, lo que "
        "el tablero lee como inflación viva es arrastre estadístico, y la política "
        "monetaria tendría más margen del que descuenta el resto de indicadores",
    "cpi_yoy":
        "el interanual sería el dato real y el corto, ruido de meses sueltos. Eso deja a "
        "la política monetaria sin el margen que el resto del tablero le supone",
    "be5y":
        "el mercado de bonos ligados a inflación cotiza el régimen, no el dato. Si acierta, "
        "lo que hoy se lee como un ciclo de precios es un cambio de expectativas de fondo",
    "be10y":
        "las expectativas largas son las que anclan todo lo demás. Moverse aquí implica "
        "que lo que cambia no es el ciclo sino el suelo sobre el que se calcula",
    "sahm":
        "el mercado laboral avisa tarde pero no se equivoca: cuando esta regla se activa, "
        "el resto de indicadores de actividad todavía se ve bien, y ese es justo el patrón",
    "claims_4w":
        "las peticiones semanales son el dato de actividad más rápido que hay. Si se "
        "separan del resto, lo que el tablero lee como ciclo sano es una foto vieja",
    "curve_10y3m":
        "la curva se adelanta con meses de sobra y por eso casi siempre parece equivocada "
        "cuando más importa. Si acierta ella, lo que se ve hoy en precios todavía no ha "
        "empezado a reflejarlo",
    "netliq_3m":
        "la liquidez es la marea de fondo: cuando se retira lo hace para todos a la vez, y "
        "los precios son lo último en enterarse. No cambia qué activo gana, cambia si "
        "alguno gana",
    "copper_gold":
        "el cobre frente al oro es la apuesta de la industria sobre el ciclo, y se mueve "
        "antes que cualquier encuesta. Si se separa del resto de la actividad, el que suele "
        "tener razón es él",
    "gold_ext_200":
        "el oro estaría respondiendo a algo que no es la tasa real —refugio, bancos "
        "centrales, desconfianza en la divisa—, y ese motor no aparece en ningún otro sitio "
        "del tablero",
    "gold_12m":
        "un año de subida del oro sin estrés visible en ningún otro indicador suele indicar "
        "que el comprador no busca rendimiento, y ese comprador no se cansa por precio",
    "dgs2":
        "el tramo corto cotiza lo que va a hacer el banco central, no lo que ya hizo. Si "
        "acierta, el tablero está leyendo la política monetaria con un trimestre de retraso",
    "dff_12m":
        "lo que importa de la política monetaria no es el nivel sino la velocidad del "
        "cambio, y esa llega a la economía real con año y medio de desfase: el efecto de "
        "lo ya hecho todavía no está en los datos",
}

# Segunda condicion observable, cualitativa, ademas del valor calculado al que
# el indicador dejaria de estar en su extremo.
# Frases de mecanismo que ASUMEN una tendencia de bolsa alcista o en máximos.
# Solo son ciertas con la tendencia al alza; en un mercado bajista o lateral se
# omiten -- es preferible el silencio a una frase falsa (ver _mecanismo_ok).
CONTRA_OBSERVAR_ALCISTA = {"real_10y", "hy_oas", "spx_ext_3y"}
CONTRA_OBSERVAR: dict[str, dict[str, str]] = {
    # Cada frase de mecanismo AFIRMA algo sobre el mercado, asi que se declara
    # por VARIANTES segun el lado del extremo del propio indicador ("alto" o
    # "bajo" en su percentil crudo). Si el estado de hoy no tiene variante, la
    # frase SE OMITE: el silencio es preferible a una frase falsa.
    "real_10y": {
        "alto": "y si la bolsa deja de subir con la tasa real subiendo: mientras "
                "suban juntas, manda el crecimiento; cuando se separan, manda la tasa"},
    "hy_oas": {
        "bajo": "y si el diferencial se abre con la bolsa todavía en máximos: esa es "
                "la secuencia que suele avisar primero",
        "alto": "y si el diferencial deja de ampliarse antes que la bolsa deje de "
                "caer: el crédito suele girar primero"},
    "vix": {
        "bajo": "y si el índice de volatilidad deja de caer en los rebotes: dejar de "
                "relajarse es más informativo que subir un día",
        "alto": "y si la volatilidad cede sin que la bolsa recupere: la calma llega "
                "antes que el precio"},
    "spx_ext_3y": {
        "alto": "y si los nuevos máximos empiezan a hacerse con menos activos "
                "participando",
        "bajo": "y si la sobreventa se corrige con tiempo en vez de con precio: un "
                "lateral largo agota la señal sin rebote"},
    "cpi_3m": {
        "bajo": "y si los precios al productor y el dato interanual acompañan al dato "
                "corto en los próximos meses"},
    "curve_10y3m": {
        "alto": "y si el empinamiento viene del tramo largo subiendo o del corto "
                "bajando: no significan lo mismo",
        "bajo": "y si la inversión se profundiza o se corrige por el tramo corto"},
    "netliq_3m": {
        "bajo": "y si la caída de liquidez continúa una vez pasados los vencimientos "
                "fiscales del trimestre",
        "alto": "y si la inyección se sostiene una vez pasados los vencimientos "
                "fiscales del trimestre"},
    "eq_vs_bonds": {
        "bajo": "y si los bonos empiezan a aguantar las caídas de la bolsa: mientras "
                "caigan juntos, el problema es de tasas y no de ciclo"},
    "be5y": {
        "alto": "y si la inflación implícita se mueve sin que la tasa nominal la "
                "acompañe: eso separa el cambio de expectativas del de política",
        "bajo": "y si la implícita cae sin que la nominal la siga: ahí se ve si el "
                "mercado descuenta desinflación o demanda débil"},
    "be10y": {
        "alto": "y si la brecha entre la implícita a 5 y a 10 años se abre: ahí se ve "
                "si lo que cambia es el ciclo o el suelo",
        "bajo": "y si la brecha entre la implícita a 5 y a 10 años se cierra por el "
                "tramo largo: sería un cambio de suelo, no de ciclo"},
    "sahm": {
        "alto": "y si las peticiones semanales de desempleo confirman en las próximas "
                "cuatro lecturas; es el dato que llega antes"},
    "copper_gold": {
        "alto": "y si la producción industrial acompaña en los próximos dos meses",
        "bajo": "y si la producción industrial confirma la señal del precio en los "
                "próximos dos meses"},
    "gold_ext_200": {
        "alto": "y si el oro sube en días en que también sube la tasa real: ahí se ve "
                "que el comprador no busca rendimiento"},
}

# Un indicador vota cuando su percentil a 5 anos sale de esta banda central.
VOTE_LOW, VOTE_HIGH = 40, 60

# Que defiende un valor ALTO de cada indicador. Un valor BAJO defiende lo
# contrario. Se define sobre el valor CRUDO, no sobre la lectura orientada,
# porque no todo lo adverso para la bolsa es adverso para todo: la inflacion
# alta perjudica a bolsa y duracion y beneficia a las materias primas, y eso
# se perderia si se colgara del signo de riesgo.
INDICATOR_ASSET_MAP: dict[str, dict[str, int]] = {
    # --- credito ---------------------------------------------------------
    "hy_oas":          dict(rv=-1, dur=+1, cred=-1, cicl=-1, usd=+1, mp=-1, oro=+1),
    "ig_oas":          dict(rv=-1, dur=+1, cred=-1, cicl=-1),
    "hy_minus_ig":     dict(rv=-1, dur=+1, cred=-1, cicl=-1, usd=+1),
    "nfci":            dict(rv=-1, dur=+1, cred=-1, cicl=-1, usd=+1, mp=-1, oro=+1),
    "hyg_vs_ief":      dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    # --- volatilidad -----------------------------------------------------
    "vix":             dict(rv=-1, dur=+1, cred=-1, cicl=-1, usd=+1, oro=+1),
    "vix_vs_3m":       dict(rv=-1, dur=+1, cred=-1, cicl=-1),
    "rvol_spx":        dict(rv=-1, dur=+1, cred=-1, cicl=-1),
    "dd_spx":          dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    "gold_vs_spx":     dict(rv=-1, dur=+1, cred=-1, cicl=-1, oro=+1),
    # --- tendencia -------------------------------------------------------
    "breadth_200":     dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    "spx_12m":         dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    "risk_6m":         dict(rv=+1, dur=-1, cred=+1, cicl=+1, mp=+1),
    "spx_vs_200":      dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    "bonds_vs_spx":    dict(rv=-1, dur=+1, cred=-1, cicl=-1),
    # --- posicionamiento (contrarian: caro hoy = menos recorrido) --------
    "spx_ext_3y":      dict(rv=-1, cicl=-1),
    "eq_vs_bonds":     dict(rv=-1, dur=+1),
    "eq_vs_gold":      dict(rv=-1, mp=+1, oro=+1),
    "credit_comp":     dict(rv=+1, cred=+1),
    "gold_12m":        dict(rv=-1, oro=+1),
    "gold_ext_200":    dict(rv=+1, oro=-1),
    # --- crecimiento -----------------------------------------------------
    "claims_4w":       dict(rv=-1, dur=+1, cred=-1, cicl=-1, mp=-1, oro=+1),
    "sahm":            dict(rv=-1, dur=+1, cred=-1, cicl=-1, mp=-1, oro=+1),
    "payems_3m":       dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    "indpro_yoy":      dict(rv=+1, dur=-1, cicl=+1, mp=+1),
    "permits_yoy":     dict(rv=+1, dur=-1, cicl=+1),
    "retail_yoy":      dict(rv=+1, dur=-1, cicl=+1),
    "umcsent":         dict(rv=+1, cicl=+1),
    "copper_gold":     dict(rv=+1, dur=-1, cicl=+1, mp=+1, oro=-1),
    "cyc_vs_def":      dict(rv=+1, dur=-1, cicl=+1),
    "curve_10y3m":     dict(rv=+1, dur=-1, cred=+1, cicl=+1),
    # --- inflacion -------------------------------------------------------
    "cpi_yoy":         dict(rv=-1, dur=-1, mp=+1, oro=+1),
    "cpi_3m":          dict(rv=-1, dur=-1, mp=+1, oro=+1),
    "core_pce":        dict(rv=-1, dur=-1, mp=+1, oro=+1),
    "ppi_yoy":         dict(rv=-1, dur=-1, mp=+1, oro=+1),
    "be5y":            dict(dur=-1, mp=+1, oro=+1),
    "be10y":           dict(dur=-1, mp=+1, oro=+1),
    # --- liquidez --------------------------------------------------------
    # Tipos altos castigan a la bolsa y, a la vez, hacen mas atractivo entrar
    # en duracion: son dos cosas distintas y aqui van separadas.
    "real_10y":        dict(rv=-1, dur=+1, usd=+1, mp=-1, oro=-1),
    "dgs2":            dict(rv=-1, dur=+1, usd=+1, oro=-1),
    "dff_12m":         dict(rv=-1, dur=+1, cred=-1, usd=+1, oro=-1),
    "netliq_3m":       dict(rv=+1, cred=+1, mp=+1, usd=-1, oro=+1),
    "dollar_3m":       dict(rv=-1, cicl=-1, usd=+1, mp=-1, oro=-1),
}

_faltan = [d["key"] for d in INDICATORS if d["key"] not in INDICATOR_ASSET_MAP]
if _faltan:
    raise ValueError(f"indicadores sin mapa de clases de activo: {_faltan}")
_sobran = set(INDICATOR_ASSET_MAP) - {d["key"] for d in INDICATORS}
if _sobran:
    raise ValueError(f"mapa de clases con claves inexistentes: {sorted(_sobran)}")


# ============================================================================
# FASE 2 - GUIA DE DECISION (SPEC 5, 6, 7, 9)
# ============================================================================

# ---------------------------------------------------------------- 5.3 TIMING
# Dimension INDEPENDIENTE de direccion y conviccion: "conviene perseguir esta
# senal AHORA, o hay una condicion tactica que aconseja paciencia?".
#
# REGLA DURA (SPEC 3.2): el timing se deriva UNICAMENTE de indicadores de
# horizonte tactico. Un indicador de regimen no puede moverlo -- si pudiera, el
# timing seria un duplicado lento de la conviccion, que es justo lo contrario de
# para lo que sirve.
TIMING_ESTADOS = {
    "confirmado":   "Confirmed",
    "favorable":    "Favorable",
    "paciente":     "Patient",
    "esperar":      "Wait for confirmation",
    "extendido":    "Extended",
    "contrario":    "Contrarian risk elevated",
    "reversion":    "Tactical reversal risk",
    "neutral":      "Neutral",
}
# Glosa corta en castellano, que es el idioma del documento.
TIMING_ES = {
    "confirmado": "confirmado",
    "favorable":  "favorable",
    "paciente":   "paciente: no perseguir la debilidad",
    "esperar":    "esperar confirmacion",
    "extendido":  "extendido",
    "contrario":  "riesgo contrario elevado",
    "reversion":  "riesgo de reversion tactica",
    "neutral":    "neutral",
}
# Cuantos indicadores TACTICOS en extremo hacen falta para hablar de un setup
# tactico contra el regimen. Dos, para que un solo indicador no lo dispare.
TACTICO_MIN_EXTREMOS = 2

# ------------------------------ 7.1 PERSISTENCIA EN EL SELECTOR DE TENSION
# Un extremo de dos dias habiles no es una tension dominante: es ruido. Antes de
# que un indicador pueda ENCABEZAR nada --tension principal, contradiccion o
# confirmacion mas fuerte, evidencia clave-- tiene que llevar un minimo en su
# extremo.
#
# El minimo NO es universal (SPEC 7.1): depende de la FRECUENCIA NATIVA del
# indicador, que se infiere del propio dato. Una serie diaria necesita mas dias
# para decir algo que una mensual, donde cada publicacion ya resume un mes.
FREQ_CORTE_DIAS = {"diaria": 1.5, "semanal": 7.0}      # por encima: "mensual"
PERSIST_EXTREMO_MIN = {"diaria": 10, "semanal": 5, "mensual": 2}   # dias habiles

# ------------------------------------------------ 7.1 PERSISTENCIA (anti-whipsaw)
# "No usar una ventana universal: la persistencia respeta la frecuencia y
# naturaleza de cada indicador." La ventana sale del HORIZONTE declarado.
PERSISTENCIA_DIAS = {
    "tactical":     3,     # dias habiles
    "intermediate": 10,
    "estructural":  21,
}
PERSISTENCIA_TXT = {
    "tactical":     "3 dias habiles",
    "intermediate": "2 semanas",
    "estructural":  "un mes",
}

# --------------------------------------------------- 6. ALCANZABILIDAD DE TRIGGERS
# Ventana para la desviacion tipica de los cambios diarios de cada indicador.
TRIGGER_SIGMA_WIN = 60
# La distancia a un umbral se mide en sigmas DEL HORIZONTE del trigger, no de un
# solo dia: exigirle a un diferencial que se mueva 5 pp "en una sigma diaria" lo
# declara imposible siempre. sigma_h = sigma_diaria * raiz(dias del horizonte).
TRIGGER_DIAS_HORIZONTE = {"tactical": 21, "intermediate": 63, "estructural": 189}
# Por encima de estas sigmas, el trigger no invalida nada en la practica: exige
# un movimiento que ese indicador no hace.
TRIGGER_SIGMA_MAX = 6.0

# ------------------------------------------------------- 5.5 EXPRESION PREFERIDA
# Expresiones RELATIVAS por clase. Solo se publican cuando la evidencia del
# sistema las sostiene; si no, "-" (SPEC 3.4). El mapa es clase -> lado -> frase.
EXPRESION_PREFERIDA = {
    "rv":   {"mas":   "Alta beta > baja beta; cíclico > defensivo",
             "menos": "Calidad > baja calidad; baja beta > alta beta; grandes > pequeñas"},
    "cred": {"mas":   "Alto rendimiento > grado de inversión",
             "menos": "Grado de inversión > alto rendimiento; mayor > menor calidad"},
    # SEMANTIC-PASS 20: el mismo llamado, dicho como se usa en una cartera.
    # No se dice «efectivo»: el modelo no compara liquidez contra bonos, compara
    # PLAZO contra plazo, y meter efectivo seria afirmar algo que no calcula.
    "dur":  {"mas":   "Duración larga > tramo corto",
             "menos": "Tramo corto > duración larga"},
    "cicl": {"mas":   "Cíclico > defensivo",
             "menos": "Defensivo > cíclico"},
    # SEMANTIC-PASS 14-16: la cartera de un cliente con base en dólar sigue
    # siendo en dólar, opine lo que opine la macro. La pregunta no es «¿salgo
    # del dólar?» sino qué hace el dólar con la exposición internacional y con
    # el costo de cubrirla.
    "usd":  {"mas":   "Cubrir divisa en la exposición internacional gana atractivo",
             "menos": "La exposición internacional sin cubrir recibe viento de cola"},
    "mp":   {"mas":   "Materias primas > bonos nominales",
             "menos": "Bonos nominales > materias primas"},
    "oro":  {"mas":   "Oro > bonos nominales como cobertura",
             "menos": "Bonos nominales > oro"},
}
# Que se reduce o se evita. No es la frase inversa de la anterior --eso no
# anadiria nada--: es la exposicion concreta que sobra si la lectura es correcta.
# En castellano llano y diciendo POR QUE, no solo que. «Duración de crédito
# larga en nombres fragiles» describe una exposicion a quien ya sabe lo que es;
# a quien no, no le dice nada y encima se lee como si fuera un riesgo del
# documento. Cada linea nombra la exposicion y el motivo por el que sobra.
# SEMANTIC-PASS 33: «Evitar» suena mas prescriptivo de lo que es. Esto no es
# una orden: es lo que queda del lado menos favorecido si la lectura acierta.
EVITAR_ETIQUETA = "Menos atractivo"
EVITAR_GLOSA = "lo que queda del lado menos favorecido si esta lectura acierta"
EVITAR_EXPOSICION = {
    "rv":   {"mas":   "Pagar caro por protegerse, o quedarse demasiado defensivo",
             "menos": "Lo más volátil y de peor calidad: alta beta y empresas "
                      "que no ganan dinero"},
    "cred": {"mas":   "Bonos largos de emisores frágiles: si algo se tuerce, "
                      "son los que más caen",
             "menos": "Alto rendimiento y deuda de peor calidad"},
    "dur":  {"mas":   "Plazos muy cortos: al vencer hay que reinvertir a lo "
                      "que haya entonces",
             "menos": "Bonos de vencimiento lejano: los que más sufren si "
                      "suben las tasas"},
    "cicl": {"mas":   "Defensivas que ya cotizan caras",
             "menos": "Sectores que dependen del ciclo económico"},
    "usd":  {"mas":   "Exposición internacional sin cubrir, mientras el dólar "
                      "se fortalece",
             "menos": "Cubrir la divisa cuando el viento va a favor: se paga "
                      "el costo sin el beneficio"},
    "mp":   {"mas":   "Bonos nominales de plazo largo",
             "menos": "Materias primas, que siguen al ciclo"},
    "oro":  {"mas":   "Coberturas que solo funcionan con tasas reales altas",
             "menos": "Concentrar la cartera en oro"},
}

# ------------------------------------------------------- 9. MANDATE TRANSLATION
# TABLA FIJA Y METODOLOGICA. No se genera por snapshot, no se personaliza, no
# cambia con los datos, y no se convierte en pesos. Es de referencia: dice como
# se traduce una misma senal a mandatos distintos.
MANDATE_TRANSLATION = [
    ("Defensiva + convicción media",  "Reducir beta / valor relativo / cobertura",
                                      "Reducir riesgo / subir calidad"),
    ("Defensiva + sobreventa",        "Oportunidades tácticas / vender fuerza",
                                      "Evitar capitulación / ajuste gradual"),
    ("Pro-riesgo + convicción media", "Añadir selectivamente",
                                      "Mover gradualmente hacia neutral"),
    ("Pro-riesgo + convicción alta",  "Aumentar participación",
                                      "Relajar defensas"),
    ("Neutral / divergente",          "Idiosincrático / valor relativo",
                                      "Mantener disciplina estratégica"),
]

# ------------------------------------------------------------ 4.2 TEMAS (orden)
# Los siete temas del Positioning Guide, en el orden en que se leen.
TEMAS_ORDEN = ["rv", "dur", "cred", "cicl", "usd", "mp", "oro"]


# ============================================================================
# SEGUNDA PASADA - METODOLOGIA DECLARADA (fuente unica para HTML y PDF)
# ============================================================================

# --------------------------------------------- definicion oficial de percentil
# DOS COSAS DISTINTAS, y confundirlas fue un error real: el PDF llego a decir
# que "100 es siempre lo favorable", con el HY OAS en p100 clasificado --bien--
# como adverso.
#
#   A. PERCENTIL ESTADISTICO. Donde esta el indicador frente a SU PROPIA
#      historia de cinco anos. p100 = mas alto que en ningun momento del
#      lustro; p0 = el minimo. NO dice si eso es bueno o malo.
#
#   B. ORIENTACION ECONOMICA. Despues se aplica la direccion economica de ESE
#      indicador para decidir favorable / adverso / neutral.
#
#   Ejemplo: HY OAS en p100 esta estadisticamente muy alto y economicamente es
#   adverso para el riesgo.
#
# Los EJES y PILARES son otra cosa: su nivel 0-100 ya viene orientado, y ahi si
# 100 es lo favorable, porque la direccion economica ya esta incorporada.
METODOLOGIA_PERCENTIL = dict(
    corta=("El percentil dice dónde está cada indicador frente a su propia "
           "historia de cinco años: p100 es su máximo del lustro y p0 su mínimo. "
           "Eso es estadística, no juicio. La etiqueta favorable o adverso sale "
           "después, al aplicar la dirección económica de ese indicador: el "
           "diferencial de alto rendimiento en p100 está muy alto y es adverso "
           "para el riesgo."),
    ejes=("Los ejes y los pilares sí van orientados: su nivel de 0 a 100 ya "
          "incorpora esa dirección, y ahí 100 es lo favorable para activos de "
          "riesgo."),
)

# ------------------------------------------- metodologia de direccion/conviccion
# Se declara UNA vez y la consumen HTML y PDF. El voto por cluster sigue siendo
# diagnostico paralelo: no decide ninguna direccion publicada (SPEC 10).
METODOLOGIA = dict(
    direction_method="voto_por_indicador",
    cluster_role="diagnostico_paralelo",
    conviction_method="cohesion_de_voces_independientes_con_techos_por_contradiccion",
)
METODOLOGIA_TXT = dict(
    direction_method=("La dirección de cada tema sale del VOTO POR INDICADOR: "
                      "cada indicador que está fuera de su banda neutral vota "
                      "sobre las clases a las que afecta, y la mayoría decide el "
                      "lado."),
    cluster_role=("El recuento por CLUSTER de correlación es un diagnóstico "
                  "paralelo de redundancia: mide cuánta señal independiente hay "
                  "detrás del voto. No decide ninguna dirección publicada."),
    conviction_method=("La CONVICCIÓN sí usa la independencia: se mide la "
                       "cohesión entre voces independientes —un grupo de "
                       "indicadores correlacionados cuenta como una voz— y se le "
                       "aplican techos cuando un extremo contradice a la clase, "
                       "cuando una divergencia la parte o cuando el eje se mueve "
                       "en contra."),
)

# ------------------------------------ 4. clasificacion de triggers por efecto
# La etiqueta NO sale del bloque en que se genero el disparador, sino de lo que
# pasa de verdad al cruzarlo: se recalcula el estado y se compara.
TRIGGER_EFECTOS = {
    "confirm":    "Confirma",
    "weaken":     "Debilita",
    "neutralize": "Neutraliza",
    "reverse":    "Revierte",
    "tactical":   "Táctico",
    "none":       "Sin efecto medible",
}
# Solo estos dos pueden figurar bajo "Invalida / revierte".
TRIGGER_INVALIDA = ("neutralize", "reverse")

# ------------------------------------------------------ TIMING PROPIO (2P 6)
# El timing es del MOMENTO, no del tema: vive en la cabecera. Un tema solo puede
# llevar el suyo si tiene evidencia tactica PROPIA que lo sostenga --indicadores
# de horizonte tactico que voten sobre esa clase--. Sin eso, una fila con timing
# distinto al global seria ruido de recuento, no una lectura.
TIMING_OVERRIDE_MIN = 2

# ------------------------------------------- SENAL TACTICA vs OVERLAY (2P 9)
# Dos cosas distintas que compartian el nombre "setup tactico": una senal que
# apunta en la misma direccion que el regimen (lo cronometra) y una que va en su
# contra (lo matiza sin cambiarlo). Se nombran distinto porque se usan distinto.
SENAL_TACTICA = {
    "direccional": "Señal direccional táctica",
    "overlay": "Overlay contrario",
}
# La frase entera, con su articulo: componerla con «una {titulo}» producia
# «una overlay contrario», mal de genero y de concordancia.
SENAL_TACTICA_FRASE = {
    "direccional": "una señal direccional táctica",
    "overlay": "un overlay contrario",
}
SENAL_TACTICA_NOTA = {
    "direccional": ("Acompaña al régimen: no lo cambia, dice si el momento "
                    "acompaña."),
    "overlay": ("Va contra el régimen dominante: no lo cambia, cambia el "
                "momento de actuar."),
}

# -------------------------------------------- PROCEDENCIA DE LA EXPRESION (7)
# Una expresion preferida sin senales que la sostengan no se publica. El texto
# sale de una tabla fija; lo que decide si SE ENSENA son los votos de hoy.
EXPRESION_FUENTE = "tabla_de_expresion"
EXPRESION_APOYOS_MAX = 3

# ------------------------------------------- MARCAS DE METODO PARA EL QA (11)
# Fragmento CORTO y estable de cada enunciado de metodo. El HTML y el PDF los
# escriben desde METODOLOGIA_TXT / METODOLOGIA_PERCENTIL, y el QA semantico
# busca estas marcas en los dos documentos renderizados. Una sola fuente: si se
# cambia la redaccion, se cambia aqui y el check sigue valiendo.
METODOLOGIA_MARCA = {
    "percentil": "eso es estadística, no juicio",
    "direction_method": "voto por indicador",
    "cluster_role": "diagnóstico paralelo",
    "conviction_method": "cohesión entre voces independientes",
}

# Formulaciones PROHIBIDAS sobre el percentil: atan un percentil alto a que sea
# favorable, que es justo lo que 2P 2 separa. La excepcion legitima --los ejes y
# los pilares SI van orientados-- se reconoce por el contexto, no por la frase.
PERCENTIL_PROHIBIDO = [
    "percentil alto es favorable",
    "p100 es favorable",
    "cuanto más alto el percentil, mejor",
    "un percentil alto siempre es",
]
PERCENTIL_CONTEXTO_OK = ("eje", "ejes", "nivel", "pilar", "pilares", "orientad",
                         "compuesto")

# =========================================================================
# TERCERA PASADA
# =========================================================================

# --------------------------------------------- PILARES PROPIOS DE CADA CLASE
# SPEC 3.1: una afirmacion solo puede citar indicadores del pilar del que habla.
# Para las expresiones de la Positioning Guide eso significa que cada tema cita
# lo SUYO: la duracion se explica con tasas e inflacion implicita, no con el
# diferencial de alto rendimiento, aunque el diferencial vote sobre ella.
#
# El mapa se declara sobre los pilares que ya existen, y POSICIONAMIENTO e
# INFLACION quedan fuera de los temas de riesgo porque no entran en ningun eje
# --salvo donde la inflacion ES el tema (duracion, materias primas, oro).
CLASE_PILARES: dict[str, list[str]] = {
    "rv":   ["tendencia", "volatilidad"],          # su propio mercado
    "dur":  ["liquidez", "inflacion"],             # tasas y compensacion por inflacion
    "cred": ["credito"],                           # diferenciales y condiciones
    "cicl": ["crecimiento", "tendencia"],          # el ciclo y como lo cotiza la bolsa
    "usd":  ["liquidez", "credito"],               # tasas relativas y aversion al riesgo
    "mp":   ["crecimiento", "inflacion"],          # demanda y precios
    "oro":  ["liquidez", "inflacion"],             # tasa real y compensacion
}

# Cuantas clases tiene que sostener un mismo conjunto de indicadores para que
# deje de ser un detalle y pase a ser un HALLAZGO sobre la lectura: que las
# siete filas descansan sobre una sola familia de riesgo.
FAMILIA_MIN_CLASES = 3

# ------------------------------------------- ALCANCE DE LO QUE VIGILA EL BRIEF
# El pie del PM Brief afirma que solo lista lo que esta al alcance de un
# movimiento normal del indicador. Con el techo anterior --6 sigmas, el limite
# de lo que se considera "medible"-- entraban umbrales a 5.6 y 5.9 sigmas, que
# no estan al alcance de nada. El pie decia una cosa y la lista hacia otra.
BRIEF_SIGMA_MAX = 3.0

# --------------------------------------------------- LOS DOS NOMBRES, FIJOS
# Dos conceptos distintos que compartian el nombre "tension principal", y esa
# ambiguedad puso una divergencia entre pilares en la cabecera y un indicador
# suelto en la prosa, sin que coincidieran. Un nombre para cada uno, y el viejo
# queda PROHIBIDO en todo texto publicado.
TENSION_DOMINANTE = "Tensión dominante"      # divergencia entre pilares DE EJE
TENSION_INDICADOR = "Indicador en contra"    # el indicador persistente que mas contradice
TENSION_PROHIBIDO = ("tensión principal", "tension principal")

# ------------------- TENSION DOMINANTE DE PILAR DE CONTEXTO (metodologia)
# CAMBIO DE METODOLOGIA, no de logica. Inflacion y posicionamiento siguen sin
# VOTAR direccion --su signo depende del regimen, y por eso no entran en ningun
# eje--, pero eso no implica que una divergencia persistente CONTRA ellos no sea
# informativa. En 2021-11-01 el credito estaba en 88/100 con la inflacion en
# 2/100 durante diez meses: la regla anterior escondia la unica senal de las
# cuatro fechas de validacion que avisaba de 2022 antes de que ocurriera.
#
# Solo cuando la divergencia es EXTREMA y PERSISTENTE, y siempre con etiqueta
# distinta: no se confunde con una tension entre pilares que si votan.
CONTEXTO_TENSION_BRECHA = 70.0     # puntos de percentil entre los dos pilares
CONTEXTO_TENSION_SEMANAS = 13.0    # ~3 meses
TENSION_DOMINANTE_CONTEXTO = "Tensión dominante (fuerza de contexto)"

# =========================================================================
# CUARTA PASADA — PRESENTACION
# Nada de aqui cambia una senal. Son etiquetas, orden y vocabulario: la misma
# conclusion, dicha de forma que no haya que reconstruirla al leer.
# =========================================================================

# ---------------------------------------------------- SESGO, EN LENGUAJE PORTABLE
# "Sobreponderar" e "infraponderar" son vocabulario de cartera frente a un
# benchmark, y este documento NO es un model portfolio: no tiene pesos ni
# indice de referencia. La senal es la misma; lo que cambia es como se nombra,
# para que nadie la lea como una instruccion de peso relativo.
#
# El mapeo con la direccion interna (mas/menos) se mantiene EXPLICITO y se
# publica en la metodologia: es presentacion, no una capa nueva.
# SEMANTIC-PASS 17-18: el dólar no es una clase de activo más. Se decide una
# vez, arriba, y afecta a COMO se mantiene lo demás, no a qué se mantiene.
DIMENSION_GRUPO = {
    "rv": "núcleo", "cicl": "núcleo", "dur": "núcleo", "cred": "núcleo",
    "mp": "núcleo", "oro": "núcleo", "usd": "overlay",
}
DIMENSION_NOMBRE = {
    "rv": "Riesgo de renta variable", "cicl": "Estilo: cíclico o defensivo",
    "dur": "Tasas y duración", "cred": "Crédito: calidad",
    "mp": "Materias primas", "oro": "Oro",
    "usd": "Entorno del dólar (overlay de divisa)",
}
# §15: los estados del dólar se dicen como lo que son --un movimiento del
# dólar-- y despues su implicacion para una cartera con base en dólar.
USD_ESTADO = {"mas": "Dólar fortaleciéndose", "menos": "Dólar debilitándose",
              "neutral": "Dólar neutral"}
USD_IMPLICACION = {
    "mas": ("La fortaleza del dólar resta retorno a los activos "
            "internacionales medidos en dólar: sube el valor de cubrir la "
            "divisa."),
    "menos": ("La exposición internacional sin cobertura cambiaria recibe un "
              "viento de cola relativo."),
    "neutral": ("Sin señal direccional del dólar: la decisión de cobertura se "
                "resuelve por costo, no por vista."),
}
USD_NOTA = ("No implica cambiar la moneda base de la cartera. Es un overlay: "
            "habla de la exposición internacional y de si conviene cubrirla.")

SESGO_PRESENTACION: dict[str, dict[str, str]] = {
    "rv":   {"mas": "Favorable",      "menos": "Desfavorable",  "neutral": "Neutral"},
    "dur":  {"mas": "Larga",          "menos": "Corta",         "neutral": "Neutral"},
    "cred": {"mas": "Menor calidad",  "menos": "Mayor calidad", "neutral": "Neutral"},
    "cicl": {"mas": "Cíclico",        "menos": "Defensivo",     "neutral": "Neutral"},
    "usd":  {"mas": "Dólar fuerte",   "menos": "Dólar débil",   "neutral": "Neutral"},
    "mp":   {"mas": "Favorable",      "menos": "Desfavorable",  "neutral": "Neutral"},
    "oro":  {"mas": "Favorable",      "menos": "Desfavorable",  "neutral": "Neutral"},
}
# El nombre largo de cada lado sale de la MISMA tabla que la etiqueta publicada:
# derivarlo evita que vuelvan a separarse. `_s` son las formas cortas para las
# tablas compactas, que no caben en «desfavorable».
for _ck, _sp in SESGO_PRESENTACION.items():
    if _ck in ASSET_CLASSES:
        ASSET_CLASSES[_ck]["mas"] = _sp["mas"].lower()
        ASSET_CLASSES[_ck]["menos"] = _sp["menos"].lower()
ASSET_CLASSES["rv"].update(mas_s="favor.", menos_s="desfav.")
ASSET_CLASSES["usd"].update(mas_s="favor.", menos_s="desfav.")
ASSET_CLASSES["mp"].update(mas_s="favor.", menos_s="desfav.")
ASSET_CLASSES["oro"].update(mas_s="favor.", menos_s="desfav.")
ASSET_CLASSES["cred"].update(mas_s="menor cal.", menos_s="mayor cal.")
# SEMANTIC-PASS 5 y 40: y el NOMBRE de la fila, tambien de una sola tabla. El
# comprobador HTML/PDF busca cada tema por su label, asi que dos nombres para
# la misma fila no son solo ruido de lectura: hacen que el mismo tema parezca
# ausente de uno de los dos documentos.
for _ck in ASSET_CLASSES:
    ASSET_CLASSES[_ck]["label"] = dimension_breve(_ck, ASSET_CLASSES[_ck]["label"])

SESGO_MAPEO_NOTA = ("«Favorable / Desfavorable» y «Larga / Corta» describen el lado "
                    "que la evidencia favorece dentro de cada tema. No son pesos "
                    "frente a un índice: este documento no contiene pesos de cartera.")

# SPEC-7P 2: las puntas del espectro, cuando el nombre corto del sesgo resulta
# ambiguo fuera de su fila. «Favorable» en el dolar no dice favorable A QUE, y
# en el oro no distingue entre el metal y su papel de refugio. El ORDEN de las
# puntas no se escribe aqui: sale del beta de la clase frente a su eje, que es
# lo unico que define cual de sus dos lados es el pro-riesgo. A mano se
# desincronizaria en cuanto se tocara un beta.
ESPECTRO_EXTREMOS: dict[str, dict[str, str]] = {
    "usd": {"mas": "Dólar fortaleciéndose", "menos": "Dólar debilitándose"},
    "oro": {"mas": "Más atractivo como refugio",
            "menos": "Menos atractivo como refugio"},
    # SEMANTIC-PASS 5: el eje de credito se nombra por sus dos tramos. "Mayor /
    # menor calidad" describe la direccion, pero la punta del espectro tiene que
    # decir QUE se compra: IG o HY.
    "cred": {"mas": "Alto rendimiento (HY)",
             "menos": "Grado de inversión (IG)"},
}

# ------------------------------------------------- TIMING, EN UNA SOLA PALABRA
# La cabecera y la tabla necesitan una etiqueta corta; la explicacion larga vive
# en la nota. TIMING_ES no se toca: se usa donde hay sitio.
TIMING_CORTO = {
    "confirmado": "Confirmado", "favorable": "Favorable", "paciente": "Paciente",
    "esperar": "Esperar", "extendido": "Extendido", "contrario": "Contrario",
    "reversion": "Reversión", "neutral": "Neutral",
}

# --------------------------------------------- EL TIMING, DICHO COMO UN MENSAJE
# «Timing: confirmado» nombra un estado interno y no comunica nada a quien abre
# el documento: hay que saberse la escala para traducirlo. La escala no cambia
# --las ocho claves son las mismas y las decide la misma tabla-- pero lo que se
# IMPRIME deja de ser el nombre del estado y pasa a ser lo que ese estado dice.
#
# Dos registros, porque hay dos sitios donde aparece:
#   CABEZA  una o dos palabras, la respuesta a «¿acompaña el momento?». Cabe en
#           una celda estrecha y sirve tambien en linea, tras «Timing:».
#   MATIZ   el porque, en gris debajo. Es la razon que la tabla de decision ya
#           calculaba y que el documento tiraba.
# Los dos documentos usan las mismas palabras: si el HTML dijera «confirmado» y
# el PDF «acompaña», la comprobacion de consistencia estaria comparando dos
# vocabularios en vez de una conclusion.
# Los OCHO estados tienen que sonar distintos. Si «confirmado» y «favorable»
# se escribieran los dos «acompaña», una fila con timing propio diria «acompaña
# · el global: acompaña» y la diferencia que justifica el override --que es toda
# la razon de que esa fila se salga-- se volveria invisible.
# SEMANTIC-PASS 2: «Timing» es ambiguo --¿el momento de qué?-- y las etiquetas
# no decian nada sin saberse la escala. La dimension interna no cambia: cambia
# como se presenta. Cinco estados explicitos, y el punto 3 obliga a que el
# motivo se vea SIEMPRE que no sea un «acompaña» limpio.
SENAL_ESTADO = {
    "confirmado": "acompaña",
    "favorable":  "mayormente a favor",
    "extendido":  "acompaña, pero el tramo está maduro",
    "contrario":  "acompaña, con una condición en contra",
    "paciente":   "no confirma aún",
    "esperar":    "no confirma aún",
    "reversion":  "contradice la lectura intermedia",
    "neutral":    "sin señal táctica",
}
SENAL_ETIQUETA = "Señal táctica"
# La reserva, cuando la hay: qué es exactamente lo que apunta en contra. El
# punto 3 prohíbe mostrar el estado sin ella.
SENAL_RESERVA = {
    "favorable":  "{n} condición táctica todavía apunta en contra",
    "extendido":  "las tácticas a favor ya están en su extremo",
    "contrario":  "{n} condición táctica está en su extremo, en contra",
    "paciente":   "las tácticas en contra están en su extremo",
    "esperar":    "las tácticas todavía no confirman",
    "reversion":  "sobreextensión y calma en su extremo",
}

TIMING_CABEZA = {
    "confirmado": "Acompaña sin reservas",
    "favorable":  "Acompaña con reservas",
    "extendido":  "Acompaña, pero estirado",
    "contrario":  "Riesgo contrario",
    "paciente":   "No acompaña, estirado",
    "esperar":    "No acompaña todavía",
    "reversion":  "Riesgo de reversión",
    "neutral":    "Sin lectura",
}
TIMING_MATIZ = {
    "confirmado": "ninguna táctica en contra",
    "favorable":  "alguna táctica en contra",
    "extendido":  "el tramo ya está maduro",
    "contrario":  "una táctica en contra, en su extremo",
    "paciente":   "las de en contra, en su extremo",
    "esperar":    "las tácticas todavía no confirman",
    "reversion":  "sobreextensión y calma en su extremo",
    "neutral":    "sin evidencia táctica propia",
}
# En prosa corrida no cabe una celda de dos pisos, y la conclusion tiene un
# techo duro de dos lineas (SPEC-4P 2): aqui va la version corta, sin el matiz.
TIMING_PROSA = {
    "confirmado": "el momento acompaña sin reservas",
    "favorable":  "el momento acompaña con reservas",
    "extendido":  "el momento acompaña, estirado",
    "contrario":  "hay riesgo contrario",
    "paciente":   "el momento no acompaña, estirado",
    "esperar":    "el momento no acompaña todavía",
    "reversion":  "hay riesgo de reversión táctica",
    "neutral":    "",
}


def timing_frase(estado: str) -> str:
    """Cabeza y matiz en una sola linea, para donde no hay dos pisos."""
    cab = TIMING_CABEZA.get(estado)
    if not cab:
        return estado or "—"
    mat = TIMING_MATIZ.get(estado)
    return f"{cab}, {mat}" if mat else cab

# ------------------------------------------------------ AVOID: SOLO SI APORTA
# No se publica el inverso mecanico de «Favorecer». Si «Evitar» solo dice lo
# contrario de lo que ya se dijo, ocupa una columna sin anadir nada.
EVITAR_MIN_PALABRAS_NUEVAS = 2

# --------------------------------------------------------- METODOLOGIA CORTA
# La version de seis lineas para el PDF. El detalle vive en el HTML.
METODOLOGIA_BREVE = [
    "El percentil dice dónde está cada indicador frente a su propia historia: "
    "eso es estadística, no juicio. La orientación económica se aplica aparte.",
    "La dirección de cada tema sale del voto por indicador.",
    "La convicción mide la cohesión entre voces independientes, con techos por contradicción.",
    "El recuento por cluster es un diagnóstico paralelo: no decide dirección.",
    "Cada disparador se clasifica simulando el cruce y rehaciendo el recuento.",
    "Un extremo sin persistencia no se usa como evidencia; solo como contexto.",
]

# -------------------------------------------------------- TITULOS, EN ESPANOL
# Una sola lengua visual: encabezados en espanol, y solo se dejan en ingles los
# nombres financieros convencionales (HY, IG, VIX, PM Brief).
TITULOS = {
    "regimen": "Resumen ejecutivo",
    "positioning": "Guía de posicionamiento",
    "tactica": "Régimen y táctica",
    "triggers": "Disparadores de decisión",
    "cambios": "Qué cambió",
    "metodo": "Metodología",
    "fuentes": "Fuentes",
    "takeaway": "Conclusión operativa",
    "vigilar": "Qué vigilar",
}
