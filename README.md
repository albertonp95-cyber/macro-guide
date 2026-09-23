# Snapshot macro y de mercado

Guía de lectura del estado macro y de mercado, para tomar posiciones con criterio
propio y para tener conversaciones informadas con clientes.

**No es un modelo.** No optimiza, no asigna porcentajes, no genera órdenes, no tiene
presupuesto de riesgo y no rebalancea. Produce señales y lecturas, no carteras.

Un modelo colapsa muchas variables en una decisión. Esto hace lo contrario:
descompone, muestra qué está tensionado, qué está tranquilo y, sobre todo, dónde
discrepan las señales entre sí. **La divergencia es la información, no el consenso.**

---

## El sitio publicado

Las lecturas publicadas viven en [`site/`](site/) y se sirven con GitHub Pages.
`python publicar_sitio.py` las genera; `--verificar` comprueba sin escribir.

**Las páginas publicadas son una COPIA PÚBLICA, no el documento interno.** La
diferencia está acotada y es siempre la misma: los valores de los indicadores que
provienen de una terminal Bloomberg están retenidos, y las fichas de research de
fuente Bloomberg no se reproducen. La licencia de la terminal permite consultar
esos datos dentro de ella, no redistribuirlos fuera, y una página pública es
exactamente «fuera».

Lo que **no** cambia: la lectura. Postura, confianza, señal táctica y conclusiones
son las mismas que en la copia interna, porque se calculan con los 42 indicadores.
Lo que falta es la cifra de cuatro de ellos, y cada fila lo dice en su sitio.

El mecanismo está en [`snapshot/publicar.py`](snapshot/publicar.py): qué se retiene
se **deriva** del campo `src` de cada indicador, no de una lista escrita a mano, y
la redacción se **verifica** sobre el documento ya generado —si sobrevive un ticker,
un valor junto al nombre de su serie o un extracto retenido, el proceso aborta y no
escribe nada—. Por la misma razón, el repositorio no incluye `data/cache/`,
`data/historico/`, `docs/registro.json` ni los PDF de `research/`.

Consecuencia práctica: **un clon de este repositorio no reproduce las páginas tal
cual**. Reconstruye las series públicas desde FRED y Yahoo, pero no las de terminal
ni el archivo histórico de estados.

---

## Regla de gobierno

Este proyecto **lee** datos de fuentes públicas (FRED, Yahoo Finance) con su propia
caché en `data/cache/`. **Nunca escribe** en el proyecto del modelo de ETFs. Si hace
falta un indicador nuevo, se añade aquí, nunca en el pipeline de calibración del
modelo.

No hay ninguna importación de código del otro repositorio: `snapshot/data.py` baja
sus propias series.

---

## Uso

```bash
pip install -r requirements.txt
python run_snapshot.py                     # snapshot de hoy
python run_snapshot.py --fecha 2020-03-16  # una fecha histórica
python run_snapshot.py --validar           # las cuatro fechas de control
python run_snapshot.py --force             # ignora la caché y vuelve a descargar
```

Salida en `output/`: `snapshot-AAAA-MM-DD.html` (una página, autocontenido,
imprimible) y `.md` (para archivo). `output/snapshot.html` es siempre el último.

---

## Qué hay dentro

| Fichero | Qué hace |
|---|---|
| `config.py` | Series, indicadores, pilares, ejes, umbrales. Todo lo ajustable. |
| `snapshot/data.py` | Descarga y caché de FRED y Yahoo. |
| `snapshot/bloomberg.py` | Proveedor opcional: crédito real (HY/IG OAS) y PER adelantado del S&P vía Desktop API, cacheado. |
| `snapshot/indicators.py` | Panel diario de 42 indicadores, en sus propias unidades. |
| `snapshot/scoring.py` | Percentiles, orientación, pilares, ejes, estado. |
| `snapshot/senales.py` | Redundancia: agrupa por correlación y cuenta **voces independientes** (un grupo, una voz). |
| `snapshot/historico.py` | Memoria entre snapshots: guarda cada ejecución y compara con la anterior (sección «Qué cambió» y estabilidad de deltas). |
| `snapshot/entorno.py` | La segunda distancia de los análogos: niveles absolutos y episodios de entorno. |
| `snapshot/build.py` | Ensambla el snapshot de una fecha, incluidas las comprobaciones permanentes. |
| `snapshot/documentos.py` | Capa documental: lee `docs/registro.json`. |
| `snapshot/render.py` | HTML y markdown. |
| `run_snapshot.py` | Línea de órdenes. |

Separar `indicators` de `scoring` es deliberado: permite mirar el dato crudo sin
pasar por ninguna transformación.

---

## Cómo está construido

**Percentiles hacia atrás.** El del tablero usa ventana móvil de 5 años; el de los
ejes, toda la historia disponible. Ninguno usa datos posteriores a la fecha del
documento, así que el snapshot de una fecha pasada es el que se habría visto ese día.

**Retardo de publicación.** Cada serie macro entra en la fecha en que realmente se
publicó, no en la de su periodo de referencia. Sin esto, el snapshot de septiembre de
2008 leería datos de octubre.

**Orientación.** Cada indicador lleva un signo. El signo no cambia el valor ni su
percentil: solo produce un percentil orientado en el que alto = favorable para
activos de riesgo. Es el único convenio que permite comparar pilares entre sí, que es
de donde salen las divergencias.

**Pesos iguales dentro de cada pilar.** Aquí no hay calibración, y afinar los pesos
sería fingir un modelo.

### Los siete pilares y los dos ejes

| Pilar | Eje |
|---|---|
| Crédito y condiciones financieras | Riesgo |
| Volatilidad y estrés | Riesgo |
| Tendencia y momentum | Riesgo |
| Crecimiento y actividad | Ciclo (0,65) |
| Liquidez y política monetaria | Ciclo (0,35) |
| Posicionamiento y valor relativo | — contexto |
| Inflación y precios | — contexto |

**Dos pilares se quedan fuera de los ejes, a propósito.**

*Inflación*: su signo para el ciclo depende del régimen. La misma subida de precios es
reflación sana o estanflación según lo que haga el crecimiento. Promediarla dentro
borraría justo la divergencia que interesa ver.

*Posicionamiento*: mide lo contrario que el resto del eje de riesgo por construcción
—cuando todo se desploma, las cosas se abaratan y este pilar mejora—. Dentro del eje
amortiguaba la señal precisamente en las caídas: en la prueba de marzo de 2020 subía
el eje unos 11 puntos y convertía un estrés severo en simple tensión. Fuera del eje,
esa misma tensión entre «la tendencia es fuerte» y «ya se ha pagado por ella» aparece
como divergencia, que es donde se lee.

### Estado general

Cinco bandas sobre el percentil histórico del eje de riesgo, con histéresis de 5
puntos y confirmación **asimétrica**: el deterioro se reconoce el mismo día, la mejora
tiene que aguantar 5 días hábiles.

La asimetría no es un adorno. Con confirmación en ambos sentidos, el 15 de septiembre
de 2008 —con el eje de riesgo en el percentil 1,5 de su historia— el documento seguía
diciendo «tensión» porque el estrés aún no había cumplido los cinco días.

Calibración: 138 cambios de estado en 22 años, racha mediana de 42 días. Con bandas
más estrechas y sin histéresis eran 446 cambios y 13 días, y la frase «lleva X así»
del titular no informaba de nada.

---

## Decisiones de datos que conviene conocer

**Los diferenciales de crédito son de Bloomberg (HY/IG OAS), con reserva a Moody's.**
FRED sirve los índices ICE BofA recortados a 3 años, así que el crédito se toma de
Bloomberg: `LF98OAS` (alto rendimiento) y `LUACOAS` (grado de inversión), diarios
desde 2000 y cacheados en `data/cache/bbg_*.csv`. Es el diferencial de *high yield* de
verdad, que es la señal de estrés: en el otoño de 2008 casi dobló entre la semana de
Lehman y fin de octubre, un recorrido que el proxy de Moody's aplanaba por completo.
(Los niveles concretos no se reproducen aquí: son datos de terminal.) Si no hay
terminal ni caché, se cae a `BAA10Y`/`AAA10Y` de FRED como proxy consistente.

**Unidades de la liquidez neta.** `WALCL` y `WTREGEN` vienen en millones de dólares;
`RRPONTSYD` en miles de millones. Se homogeneiza en `data.load_macro` antes de operar
(`config.FRED_SCALE_TO_BILLIONS`). Sin esa conversión, la «liquidez neta» acaba siendo
el saldo de la cuenta del Tesoro con el signo cambiado.

**Todo cambio «a N meses» es por calendario, no por número de filas.** Una serie
mensual arrastrada a rejilla diaria es escalonada, y además hay huecos reales —al IPC
le falta octubre de 2025—, así que 252 filas atrás no caen doce meses atrás. Con
desplazamiento posicional el IPC interanual de julio de 2026 salía 2,95 % cuando es
3,54 %. Las ventanas móviles (volatilidad, medias, percentiles) sí se cuentan en días
de mercado, que es lo correcto para ellas.

**Momentum a 12 meses, sin saltarse el último mes.** La convención 12-1 del factor
momentum existe para evitar la reversión de corto plazo al construir carteras. Aquí
describiríamos el mercado ignorando el mes más informativo, que en una caída es justo
el que importa.

---

## Bloomberg como proveedor de datos

La Terminal es la mejor fuente para lo que las fuentes gratuitas dan mal. Hoy se usa
para los diferenciales de crédito (arriba) y para el **PER adelantado del S&P 500**
(`SPX Index`, `BEST_PE_RATIO`), que es la variable de valuación de la distancia de
entorno de los análogos y no tiene equivalente gratuito con historia. Se conecta por la
Desktop API (`localhost:8194`, requiere `blpapi` y la Terminal abierta).

El PER no entra en el tablero ni vota nada: solo sirve para decir si dos fechas
parecidas vivían en el mismo mundo. **Mientras no esté en caché, el entorno se calcula
con las otras cinco variables y el snapshot lo declara** en sus comprobaciones (fila
«Variables de entorno sin dato»). Para traerlo, basta un `bb.refresh()` con la Terminal
abierta: descarga solo lo que falte.

**Política de datos.** Bloomberg no limita consultar dentro de la Terminal, pero sí
extraer a ficheros o plataformas externas; volcar a CSV es eso. Por tanto:

- Solo se extraen las series que las gratuitas no dan bien (hoy, 3).
- La historia completa se baja **una vez** y se cachea; después solo se actualiza la
  cola (`bloomberg.update_tail`, ~12 días). Nunca BQL ni descargas masivas.
- El snapshot **lee la caché; jamás llama a la Terminal** al generarse. La extracción
  es un paso manual y deliberado.

```python
from snapshot import bloomberg as bb
bb.refresh()        # descarga completa (una vez); si ya hay caché, no hace nada
bb.update_tail()    # refresco barato: solo los últimos días
```

Las noticias y MLIV no salen por esta API sin permisos especiales: esos titulares se
pegan a mano en `docs/registro.json` (sección `titulares`).

## Dos capas: la nota y el tablero

El documento son dos cosas distintas y **están separadas**. La **NOTA** es lo que se ve al
abrir —dos o tres páginas de argumento, en el registro de una nota de research (referencia
de formato: la nota mensual del VanEck/NDR Managed Allocation Fund y el *weight of the
evidence* de Ned Davis Research)—; el **TABLERO DE AUDITORÍA** es todo lo demás, plegado
(`<details>`) por defecto y expandido al imprimir. Nada se elimina; solo cambia qué se ve
primero.

El principio que ordena la nota: habla del **mercado**, nunca del documento. No explica
cómo se calcula nada ni qué significa una etiqueta; la prosa hace ese trabajo sola.

**La nota**:

- **En síntesis** — una caja arriba con tres o cuatro conclusiones completas, cada una una
  afirmación que se sostiene sola (el clima, la economía real, la tensión dominante y la
  conclusión). La última es la inclinación agregada. **Coherencia:** si renta variable o
  duración —las dos clases que definen cómo se lee una postura— van al contrario que la
  postura general («¿pro-riesgo pero neutral en bolsa?»), una viñeta extra lo explica antes
  de que el lector lo pregunte, y una comprobación permanente lo exige (`_postura_divergencias`).
- **El peso de la evidencia** — tres o cuatro párrafos **en prosa**, encadenados: qué dicen
  los indicadores técnicos (tendencia, volatilidad, crédito) y cuántos de cuántos apuntan a
  lo mismo; qué dice el bloque macro/fundamental y si **confirma o atempera** al anterior
  —esa es la gramática de las divergencias: no dos bloques enfrentados, sino cuál manda y
  cuál modera—; la tensión principal con su mecanismo; y la conclusión, *deducida* de la
  cadena («el peso de la evidencia, por tanto, sostiene…»). Cada párrafo nombra indicadores
  concretos con su nivel. Dos reglas gobiernan la prosa:
    - **La evidencia se elige por pertinencia, no por lo extrema que esté.** Cada afirmación
      se refiere a un pilar y **solo cita indicadores de ese pilar** («la economía real» →
      crecimiento; «el costo del capital» → liquidez; «el apetito de riesgo» → volatilidad y
      tendencia). Lo extremo ordena dentro del pilar, no selecciona de todo el tablero.
      Inflación y posicionamiento no entran en ningún eje: se citan como contexto, nunca como
      evidencia de los ejes. Una comprobación permanente cuenta las citas fuera de su pilar;
      debe ser 0 (`AFIRMACION_PILARES`).
    - **Confirma / atempera / contradice salen de un umbral, no de la redacción.** El bloque
      macro se mide por su acuerdo con el técnico (0–100): por encima de 65 confirma; entre 45
      y 65 atempera; por debajo de 45 contradice. La palabra elegida cae sobre la convicción:
      si atempera, la conclusión no puede quedar en «alta» (`WOE_CONFIRMA`, `WOE_ATEMPERA`).
- **Gráfico** — la puntuación de riesgo y la de ciclo en el tiempo (cinco años), con franjas
  favorable / neutral / adverso. SVG inline, sin dependencias. Es lo que pone el número de
  hoy en contexto: si 71 es alto, si viene cayendo y cuántas veces ha estado ahí.
- **Posicionamiento** — una rejilla, una fila por clase, pensada para escanearse en
  vertical (referencia estructural: el *NDR Indicator Summary* de la nota de VanEck):
    - **Posición** — un carril de adverso (izquierda) a favorable (derecha), cinco pasos,
      con una marca en la posición de hoy y otra en gris en la del mes anterior si cambió.
      Es universal: corta duración e infra dólar son posiciones PRO-riesgo, y el sentido lo
      da la beta de cada clase frente a su eje (`CLASS_AXIS`). El ojo lee el carril sin
      traducir.
    - **Sesgo** — la palabra propia de la clase (corta, bajar calidad, cíclico…), en
      secundario; acompaña a la posición, no la sustituye.
    - **Convicción** — tres puntos (●●● / ●●○ / ●○○), columna propia.
    - **Nota** — columna estrecha, solo se llena cuando la conclusión no se deduce de las
      señales o cuando las técnicas y las macro **discrepan** («técnicas y macro discrepan»,
      «limitado por tasa real 10a en p100»).
  Las dos columnas de señales (técnicas y macro) desaparecen como texto: cuando coinciden
  son ruido, y cuando discrepan es información y va en la nota. La tabla completa, con las
  señales por separado, se conserva en el tablero.
- **Qué puede pasar** — tres o cuatro líneas de *condición observable → consecuencia*, las
  más cercanas a cruzarse (ver abajo).
- **Análogos** — más muestra y **consistencia direccional**, no un promedio de tres casos:
    - **Criterio por umbral, no «los 5 más cercanos».** Entran *todas* las fechas por debajo
      de un umbral en las **dos** distancias —dinámica (`ANALOG_DIST_MAX`) y entorno
      (`ANALOG_ENV_INCLUDE`)—, con doce meses de separación entre sí como unidad de
      independencia. En un estado común da más de diez; en uno raro, pocas.
    - **Cuando califican pocas, ESO es el dato.** Menos de `ANALOG_MIN_REPORT` → «estado
      inusual: solo N episodios comparables en 21 años», y **qué** lo hace inusual (la
      variable de entorno más lejos de su norma, normalmente tasas reales o inflación). Sin
      comparables, se distingue si es que el comportamiento no tiene precedente (dinámica) o
      si los parecidos vivían en otro mundo (entorno). Esa frase informa más que un promedio.
    - **El signo antes que la magnitud.** Con muestras pequeñas el signo es más estable que
      la media, así que el titular de cada clase es la consistencia («renta variable: 12 de
      14 al alza»), y la magnitud va después como rango, nunca como media sola.
    - **Decisión por clase, no para la sección.** Si una dirección no reúne mayoría clara
      (`ANALOG_PATRON_FRAC`), se escribe «sin patrón consistente» y esa clase no reporta
      rango ni puede discrepar de nada.
    - **La discrepancia, combinada** y solo entre clases con patrón: «los análogos discrepan
      en renta variable y oro: en ambos nuestra lectura es neutral y en episodios parecidos
      subieron». La advertencia de que no es pronóstico va una sola vez.
  Sin intervalos de confianza ni pruebas de significancia: con 5-15 observaciones seriadas
  darían una apariencia de rigor que los datos no sostienen.

El conteo de señales sigue existiendo con todo su rigor —«N de M indicadores, ≈K voces
independientes»— pero en el tablero; en la prosa se dice «10 de 15 se leen del mismo lado»,
que comunica lo mismo y se lee. Las dos cosas, cada una en su capa.

### Qué puede pasar

El bloque prospectivo. No son escenarios narrativos: cada línea sale de un **umbral que el
sistema ya usa**, invertido para decir qué está cerca de cruzarse. Tres fuentes: un
extremo que hoy tapa una clase y, al salir del extremo (cruzar su valor de p95/p5),
liberaría su convicción; un indicador cerca de su frontera de voto (p40/p60) cuyo cruce
cambiaría la dirección de una clase; y la extrapolación del percentil del eje de riesgo al
ritmo del último mes hasta la siguiente banda de estado — dicho como extrapolación, «al
ritmo actual, no es pronóstico». Se ordenan por proximidad al umbral y se muestran las
más cercanas.

**El tablero** (plegado): ejes · de dónde sale cada inclinación · dónde discrepan las
señales · qué cambió en detalle · qué dicen las fuentes · el detalle de los 42
indicadores · los análogos · cómo leer / metodología · las comprobaciones.

### Qué cambió desde el anterior

Lo más útil de un producto semanal, y lo que faltaba: nadie va a cotejar 42 filas contra
la semana pasada a mano. Cada ejecución del snapshot real guarda un resumen en
`data/historico/`; la siguiente compara contra el último guardado **estrictamente
anterior**. Se reporta solo lo que se movió: inclinaciones que cambiaron de dirección,
convicciones que subieron o bajaron, indicadores que entraron o salieron de extremo,
divergencias que nacieron o murieron, pilares que se movieron más de
`CAMBIO_PILAR_PTS` puntos, y fuentes nuevas. Si no cambió nada relevante, lo dice en una
línea —eso también es información, y es la lectura más común—. Sin snapshot anterior,
se omite y se declara. Las fechas de control no escriben memoria ni se comparan.

### Deltas estables

El punto de comparación de un delta ya **no es un único cierre**: es la media de una
ventana de días hábiles alrededor de la fecha de referencia (`DELTA_REF_WIN`), y el valor
actual de los agregados (ejes, puntuación) es la media de los últimos `DELTA_ACTUAL_WIN`
días. Un cierre suelto se caía de la ventana de un día para otro y movía un delta
trimestral varios puntos sin que el mercado se moviera —el rumbo pasaba de «sin rumbo
claro» a «deteriorándose» sin que pasara nada, y eso enseña al lector a no creerle al
rumbo—. El suavizado reduce a la mitad el giro diario del delta trimestral del eje de
riesgo (medio 4.3 → 2.3 puntos, máximo 15 → 7). Los indicadores sueltos conservan su
cierre; solo los agregados se suavizan. Y una comprobación permanente reporta **el mayor
giro de un delta respecto al anterior**, marcándolo si superó el umbral sin que el nivel
se moviera de forma equivalente (inestabilidad de método, no de mercado).

### El documento concluye: una contradicción se resuelve dentro de la conclusión

El principio que ordena todo lo demás. Una contradicción **no se elimina, se resuelve
dentro de la conclusión**:

- Si debería cambiar la lectura, que la cambie: baja la convicción o lleva la clase a
  neutral.
- Si no debería cambiarla, es una nota al pie de esa clase.
- Lo que nunca se hace es enunciar una conclusión y ponerle al lado su refutación con
  el mismo peso visual. Eso deja a quien lee sin saber qué se concluye.

La divergencia sigue siendo la información que distingue a este producto. Lo que cambió
es **dónde vive**: dentro de la conclusión como convicción, no junto a ella como
contra-argumento. Por eso las contradicciones están en el tablero y no en la lectura.

### Cuántas señales hay de verdad

Contar 42 indicadores como 42 votos es contar varias veces lo mismo: el VIX, la
volatilidad realizada, la amplitud y el momentum se mueven casi como uno solo, y un
pilar con diez filas pesa más que uno con cuatro solo por tener más filas.

Los indicadores se agrupan por correlación (percentiles, ventana de 5 años, enlace
medio, corte en |ρ| ≥ 0.6) y **un grupo es una voz**. Dentro de un grupo el voto es el
de su mayoría interna, con peso igual a su grado de acuerdo: cuatro de cuatro pesa 1;
tres de cuatro, 0.5. Hoy los 42 indicadores son **19 grupos**.

El recuento se publica siempre en **dos unidades**: voces independientes (el titular) e
indicadores (el detalle). El crudo no desaparece; deja de ser el titular.

**Por qué se cuentan grupos y no dimensiones.** La primera versión medía la información
efectiva con la razón de participación de los valores propios de la matriz de
correlación. Como medida de cuánta información *distinta* hay es correcta, pero es
ciega a la **dirección**, y al comparar los dos bandos de una votación daba resultados
absurdos: en septiembre de 2008, dieciséis indicadores pidiendo subir calidad de
crédito —todos muy correlacionados, o sea poca dimensión— «perdían» contra cuatro
indicadores diversos que pedían lo contrario. Dieciséis observaciones que confirman una
señal valen más que una sola, no menos. Para votar hay que contar voces; la dimensión
mide otra cosa.

**Comprobación permanente:** si un pilar aporta más del 40% de los indicadores que
votan una clase de activo y menos del 20% de sus voces —medido como lo que se perdería
quitándolo entero—, sale un aviso en el tablero.

### La convicción, y la regla que la decide

Cada inclinación lleva su convicción, y la regla es **mecánica**, no de ojo. Se evalúa
en orden, con `cohesión = (voces a favor − voces en contra) / (total)`:

La escalera tiene cuatro frenos, en orden. Primero la **base** por cohesión
(`cohesión = (voces a favor − voces en contra) / total`, con signo): ≥0.35 → alta, ≥0.18
→ media, ≥0.10 → baja, por debajo (o negativa) → neutral. Luego tres frenos que solo
pueden BAJAR:

- **Techo por extremo que contradice A ESA CLASE.** Un extremo que vota en contra de la
  clase —no uno que exista en cualquier parte del tablero— **nunca la deja llegar a
  alta**: su techo es media. Reciente (menos de 4 semanas) la limita a baja; la antigüedad
  *reduce* el castigo (de baja a media), no lo elimina. «Alta» queda reservada para clases
  **sin ningún extremo en contra**. El alcance por clase es clave: si el techo se aplicara
  por existir cualquier extremo en el tablero, «alta» sería inalcanzable por construcción.
- **Techo por divergencia** que parte a la clase, y **techo por pilar sin lectura
  unificada** del que la clase depende: ambos, media.
- **Rumbo.** Si el eje relevante para la clase se movió más de 8 puntos en un mes **en
  contra** de la inclinación, baja un nivel; a favor, sube uno (sin pasar del techo). Es
  la diferencia entre «las señales coinciden» y «coinciden y no se están dando la vuelta».
  Hoy el eje de riesgo cayó ~10 puntos: las llamadas pro-riesgo que coincidían se quedan
  en baja, no en alta.

El resultado: **«alta» es rara pero alcanzable**. Sobre los últimos seis meses
(muestreados por semana) la distribución es alta 22% · media 28% · baja 4% · neutral 46%,
con una o dos clases en alta en una semana normal y ninguna en días ambiguos como hoy
(el eje de riesgo cayendo diez puntos). El tablero muestra esa distribución cada vez: si
«alta» no apareciera nunca —o apareciera siempre—, la escala estaría mal calibrada, y
ahí se vería. Si más de tres clases salen alta el mismo día, una comprobación lo avisa.

La cohesión **va con signo y puede salir negativa**: el voto crudo apunta a un lado y
las voces al otro (en septiembre de 2008 la duración salía «larga» por 23 votos contra 9
y en voces era 2.7 contra 3.4, al revés). Ahí la conclusión es neutral. **Si la evidencia
no alcanza para una dirección, se dice «neutral», claramente** —no «sobreponderar con
convicción muy baja»—.

Los umbrales de cohesión están calibrados sobre las cinco fechas de control.

### Pilares sin lectura unificada

Un número limpio no es una lectura si sale de indicadores que se contradicen. Cuando más
del 30% de los pares posibles de un pilar están en contradicción (uno favorable, otro
adverso), el pilar se marca **sin lectura unificada**: su agregado se sigue calculando y
alimentando al eje, pero el eje lo señala, y una clase cuya inclinación depende sobre todo
de ese pilar no puede tener convicción alta. Hoy «crecimiento y actividad» (14 de 45
pares) y «liquidez» (4 de 10) están así, y por eso el eje de ciclo lo advierte.

### Una sola vez y en un solo sitio

Cada hecho aparece una vez. La tasa real en p100 llegó a estar en seis sitios del mismo
documento y a la sexta ya no informa, cansa. Ahora la contradicción se desarrolla **una
vez**, en «dónde discrepan» (en el tablero): qué implicaría si tiene razón (una frase por
indicador, no una plantilla por clase) y qué habría que ver, con el número al que dejaría
de ser extremo. En la lectura no aparece: solo la línea «qué rompería esta lectura» la
nombra, con su número. El detalle de los 42 indicadores no cuenta para la regla: es el
libro mayor.

### El oro

Tiene lectura propia: una clase de activo en el voto y tres indicadores en
el pilar de posicionamiento —momentum a 12 meses, distancia a su media de 200 días, y
oro frente a bolsa—. No entra en ningún eje, porque su papel es de refugio y de
cobertura, no de riesgo ni de ciclo. Su motor principal en el voto es el tipo real: por
eso hoy, con el tipo real a 10 años alto, el voto sale cauto aunque el relato externo
sea alcista, y esa tensión aparece señalada entre las fuentes.

### Divergencias dentro de un mismo pilar

El detector clásico compara pilar contra pilar, así que es ciego a la contradicción que
suele ser más informativa: **dos indicadores del mismo pilar diciendo cosas opuestas**.
Hoy el IPC de tres meses anualizado está en p1 —extremo favorable— conviviendo con los
precios al productor en p72: una desinflación abrupta en el dato corto que no aparece ni
en el largo ni en producción.

Criterio: dos indicadores del mismo pilar con **etiquetas opuestas** (uno favorable, uno
adverso), separados por **40 puntos** de lectura o más, durante al menos **2 semanas**.
Se publica el par más amplio de cada pilar y el recuento completo va a las
comprobaciones. Importa sobre todo en **inflación y posicionamiento**, que no entran en
ningún eje: ahí la comparación entre pilares nunca las va a capturar, y se marcan con un
distintivo.

### Contradicciones de alto perfil

Cuando un indicador en percentil extremo (fuera de p5/p95) apunta en contra de la
inclinación resultante de su clase, pasan dos cosas. Primero, **baja la convicción de
esa clase** —ahí es donde la contradicción se resuelve—. Segundo, la más extrema de
todas se desarrolla en «dónde discrepan» del tablero, junto a las divergencias, porque son lo mismo:
señales que no coinciden.

**Solo una**, la del indicador más extremo. Las demás ya están reflejadas como
convicción baja en su clase y no se repiten; el documento dice cuántas hay y dónde
mirarlas. Y en dos párrafos, no en una lista por clase:

- **Qué implicaría si tiene razón** — una frase por indicador (`config.CONTRA_IMPLICA`),
  que tiene que decir algo que *no* se deduzca del enunciado. La versión anterior
  repetía una plantilla por cada clase afectada («el dólar se fortalecería en contra de
  la lectura general»), que es la definición de contradecir, no información.
- **Qué habría que ver** — calculado: el valor al que el indicador dejaría de estar en
  su extremo, sobre la misma ventana de cinco años que usa el tablero, más una
  observación de mecanismo (`CONTRA_OBSERVAR`).

### Análogos históricos

Se buscan fechas del pasado parecidas a hoy y se mira qué pasó después. Solo entran
fechas con al menos un año de futuro por delante, para no inventar el «qué pasó», y
**ningún par de análogos puede estar a menos de doce meses** uno de otro.

Se miden **dos parecidos distintos**, y no es lo mismo fallar en uno que en el otro:

- **Dinámica** — el vector de los siete pilares **más su trayectoria** (el cambio a 1 y
  a 3 meses de cada uno, con medio peso). Mide si el mercado *se comportaba* igual. Un
  estado idéntico al que se llega desde arriba no es el mismo que si se llega desde
  abajo.
- **Entorno** — media docena de variables en **nivel absoluto** (tasa real a 10 años,
  inflación subyacente, tasa de referencia, curva 10a−3m, valuación de la bolsa,
  dirección del balance de la Fed), estandarizadas sobre **toda la historia conocida en
  la fecha del snapshot** —no sobre ventana móvil, que es justo lo que borraría el
  nivel—. Mide si el *mundo* era el mismo.

Hace falta la segunda porque el percentil, al normalizar cada serie contra su propia
historia móvil de cinco años, **borra el nivel**: un apetito de riesgo en p67 con la tasa
real en −1% y el balance creciendo no es el mismo sitio que ese p67 con la tasa real en
+2.4% y la inflación en 3.3%. Las dos se combinan en una etiqueta legible: *análogo
fuerte*, *mismo comportamiento, otro mundo* o *no es análogo*.

Por cada análogo se muestran además **los dos pilares en los que más se parece y los dos
en los que más difiere**: un análogo que coincide en seis pilares y es el opuesto en el
séptimo no es un análogo, es una coincidencia parcial, y hay que poder verlo.

**Nulo honesto.** Si tras la separación mínima quedan **menos de 3 episodios de entorno
distintos**, o si la **distancia de entorno del mejor análogo** supera `ANALOG_ENV_MAX`,
no se publica la media ni las barras de dispersión, y se dice por qué en una línea
(normalmente: tasas reales, inflación, o ambas). Las fechas sí se quedan: un desenlace
concreto sigue informando; una media de una sola observación disfrazada de cinco, no. El
snapshot de control de noviembre de 2021 entra en este caso.

Y si ni la más parecida baja del umbral de dinámica (`ANALOG_NEAR_MAX`, hoy 14), se
escribe **«sin análogos cercanos»** en vez de forzar cinco fechas: septiembre de 2008
(distancia 22) y marzo de 2020 (22) son estados sin precedente y así se dicen.

**Episodios.** La historia se segmenta en *episodios de entorno*: empieza uno nuevo
cuando el entorno se ha alejado más de `ANALOG_EPISODE_STEP` (1.5σ) del punto en que
empezó el que está en curso. De ahí salen los dos números que se reportan siempre —
cuántos episodios distintos hay entre las cinco fechas elegidas, y cuántos contiene la
muestra entera. Con datos desde 2005 son ~21 años que contienen **9 entornos macro
distintos**, no 21 años de situaciones diferentes; el lector debe saberlo antes de leer
cualquier promedio.

Por cada análogo se da el rendimiento a 3, 6 y 12 meses de cada clase de activo (un ETF
cada una: SPY, TLT, LQD, HYG, XLY−XLP, DBC, GLD, UUP; crédito va en dos, grado de
inversión y alto rendimiento) y la volatilidad realizada del S&P; y, cuando el nulo
honesto no aplica, el promedio de cada clase con una **barra de rango**
(peor–media–mejor) por horizonte. La advertencia es fija y visible: un análogo no es un
pronóstico —el desenlace fue distinto cada vez—.

### Comprobaciones de esta ejecución

Al final de cada snapshot, siempre, un bloque discreto con el resultado de las
comprobaciones permanentes: grupos independientes frente a indicadores, pilares con
redundancia alta, divergencias intra-pilar, contradicciones de alto perfil, análogos y
episodios, distancia de entorno del mejor análogo, series con dato de más de 40 días y
fuentes descartadas. Y tres de consistencia:

- **Conclusiones enunciadas y contradichas sin resolver: debe ser 0.** Un extremo en
  contra nunca deja pasar de media; si una clase sale por encima de ese techo, el
  documento enuncia y desmiente a la vez, y hay que decirlo.
- **Clases con convicción alta** — cuántas; se avisa si son más de tres (la etiqueta deja
  de distinguir cuando es la mayoría).
- **Distribución de convicción, 6 meses** — la forma de la escala; se avisa si «alta» no
  aparece nunca o aparece siempre.
- **Pilares sin lectura unificada** — cuáles superan el umbral de pares en contradicción.
- **Clases en neutral por convicción insuficiente** — cuántas y por qué (empate, o
  mayoría que se invierte al agrupar).
- **Mayor giro de un delta respecto al anterior** — marcado si superó el umbral sin que
  el nivel se moviera de forma equivalente (inestabilidad de método).

Dos reglas: **ninguna corrige nada por detrás** —informan de dónde puede fallar lo de
arriba— y **si una falla o no se puede calcular, se dice ahí** en vez de omitirla, porque
una comprobación ausente se confunde con una comprobación pasada.

### Las fuentes aportan, no validan

Las fuentes están para lo que los indicadores **no ven** —una noticia, un análisis, el
porqué detrás de un dato—. Las fuentes **acompañan** al tablero; casi siempre añaden
*otra lectura* a un indicador (postura `complementa`). Solo cuando una fuente y un
indicador chocan de forma irrefutable se adjudica: postura `resuelve` con un campo
`veredicto` que dice qué criterio pesa más y por qué. Nunca se marca una simple
coincidencia. Nada del texto se convierte en un número que se sume al tablero. Ventana
de vigencia: **dos semanas** (`documentos.VIGENCIA_DIAS`); lo más viejo no se muestra,
se cuenta como descartado.

Formato: `titulares` (entradas cortas estilo MLIV) y `documentos` (research con
`tesis`, `aporta`, `dice` con referencia, `infiero` y `contrasta`).

### Idioma y formato de número

Español de México: *tasas* (no tipos), *costo* (no coste), y números a la mexicana
—punto decimal, coma de millares (1,234.56)—, igual que la terminal de Bloomberg. La
lectura resume todo en ~15 líneas; el tablero abre con una guía de «cómo leer una fila»
y la clave de las siglas de clase de activo.

## Validación

`python run_snapshot.py --validar` genera cuatro fechas de control y hay que
comprobar que la descripción coincide con lo que sabemos que pasaba:

| Fecha | Estado | Percentil | Inclinaciones que salen | Análogos |
|---|---|---:|---|---|
| 2008-09-15 | estrés severo | p1 | RV **infraponderar**, crédito **subir calidad**, **defensivo**, duración **larga**, oro **sobreponderar** | sin análogos cercanos (22) |
| 2020-03-16 | estrés severo | p0 | crédito **subir calidad**, **defensivo**, duración **larga**, oro **sobreponderar**, MP **infraponderar** | sin análogos cercanos (22) |
| 2021-11-01 | apetito de riesgo | p77 | dólar **infraponderar** (alta), MP **sobreponderar** (alta), crédito **bajar calidad** | **nulo honesto**: 5 fechas, entorno 2.14σ |
| 2022-06-15 | tensión | p10 | dólar **sobreponderar** (alta), RV **infraponderar**, **defensivo** | sin análogos cercanos (16) |

La columna de inclinaciones es la validación que importa desde la reestructura: el
documento tiene que **concluir**, y concluir lo correcto. En las dos fechas de crisis
sale defensivo en todo; en noviembre de 2021, reflación con el dólar corto; en junio de
2022, dólar largo con alta convicción, que fue exactamente el año del dólar.

La columna de análogos valida lo contrario —cuándo el documento se **niega** a hablar—:
en las tres fechas de estrés no da análogos en vez de forzarlos, y en noviembre de 2021
los da pero **sin media ni dispersión**, porque hasta el más parecido vivía en otro
mundo (inflación subyacente 1.8% entonces frente a 4.0% hoy).

Si el de septiembre de 2008 no describe estrés severo, el problema está en la
construcción, no en la interpretación.

---

## Contraste externo

El snapshot del 8 de septiembre de 2026 se cotejó contra la *Guide to the Markets*
de J.P. Morgan (datos a 4 de septiembre de 2026):

| Magnitud | Tablero | JPM GTM |
|---|---:|---:|
| IPC interanual | 3,30 % (desestacionalizado) | 3,4 % (sin desestacionalizar) |
| PCE subyacente interanual | 3,34 % | 3,3 % |
| Tesoro a 2 años | 4,37 % | 4,4 % |

Sirvió para encontrar el fallo de calendario descrito arriba, que es la razón de
tener el contraste.

---

## Secciones

1. **Lo esencial** — estado, puntuación de toma de riesgo y cuatro frases llanas.
2. **Ejes con dirección** — riesgo y ciclo, con nivel, percentil y deltas.
3. **Qué exposición defiende cada señal** — recuento de votos por clase de activo.
4. **Tablero** — los 40 indicadores por pilar, con señal y clases que defienden.
5. **Divergencias y extremos**.
6. **Contexto documental** — el look-through.

### La puntuación de toma de riesgo

Es el eje de riesgo (0-100), acompañado siempre del recuento que la sostiene: cuántos
indicadores favorecen tomar riesgo, cuántos están en contra y cuántos neutrales. El
número solo no vale: si 21 votan a favor y 10 en contra, eso es parte de la lectura.

### El voto por clase de activo

Cada indicador que sale de su banda central (p40-p60) vota por las exposiciones sobre
las que habla: renta variable, duración, riesgo de crédito, cíclico frente a
defensivo, dólar y materias primas. El mapa está en `config.INDICATOR_ASSET_MAP`.

El voto se decide sobre el **valor crudo**, no sobre la lectura orientada de riesgo.
No todo lo adverso para la bolsa lo es para todo: una inflación alta castiga a bolsa y
duración y beneficia a las materias primas, y colgar el voto del signo de riesgo
borraría esa diferencia.

Es un **recuento, no un peso**. No dice cuánto comprar de nada y las clases no suman
a nada.

---

## La capa documental

`docs/registro.json` es el registro. Los ficheros van en `docs/bancos-centrales/`,
`docs/research/`, `docs/datos-economicos/` y `docs/prensa/`, con nomenclatura
`AAAA-MM-DD-fuente-titulo.ext`, donde la fecha es la de **publicación** y es
obligatoria. Los PDF sueltos que se dejen en `research/` se leen a mano y se resumen en
el registro (su `ruta` apunta al fichero); el PDF no se procesa automáticamente.

Registro actual (al 11 de septiembre de 2026): la lectura doble del crédito se apoya en
tres piezas —**Bloomberg Intelligence** (el diferencial leído como fracción del
rendimiento total, con sus paralelos históricos), la **JPM Guide to the Markets** (percentil
de 25 años) y, sobre la tasa real, la columna de **Deutsche Bank en el FT** («los bonos
vuelven a ser bonos»)—; la tensión de inflación la aporta un **First Word de Bloomberg**
sobre la reaceleración de los servicios subyacentes, que matiza el IPC corto en p1. La
pieza de oro de Goldman (25 de agosto) ya cayó fuera de la ventana de dos semanas y se
cuenta como descartada: el mecanismo funcionando.

Reglas duras, implementadas en `snapshot/documentos.py`:

1. El texto **nunca** se convierte en un número que se sume a las señales
   cuantitativas. No hay puntuación de sentimiento y no la va a haber. Si se
   mezclaran, se perdería la capacidad de ver cuándo discrepan, que es todo el valor.
2. Se distingue tipográficamente lo que el documento **dice** (filete continuo, con
   referencia) de lo que se **infiere** (cursiva, filete discontinuo).
3. Toda afirmación lleva documento y fecha. Sin trazabilidad, no entra.
4. La antigüedad se marca: `antiguo` a partir de 45 días, `obsoleto` a partir de 120.
5. No se hacen predicciones a partir del texto. La capa describe el debate, no lo
   resuelve.
6. Si dos documentos de calidad dicen cosas opuestas, se muestran los dos.
7. Un documento posterior a la fecha del snapshot **no aparece**. Sin esto, el
   snapshot de 2008 se leería con research de 2026.

Lo más valioso de la sección es el bloque «dónde el texto y los datos no dicen lo
mismo». Hoy, por ejemplo: el tablero lee el diferencial de crédito estrecho como
favorable porque mide estrés; JPM sitúa esos mismos diferenciales en el percentil 4-5 %
de veinticinco años. Mismo dato, lecturas opuestas según se mida estrés o valoración.

---

## Estado del proyecto

- [x] 1. Titular, con puntuación de toma de riesgo
- [x] 2. Ejes con dirección
- [x] 3. Voto por clase de activo
- [x] 4. Tablero de indicadores
- [x] 5. Divergencias y extremos
- [x] 6. Look-through documental
- [x] Inclinación sugerida por clase de activo (una postura, en lenguaje llano)
- [x] Análogos históricos (con «sin análogos cercanos» cuando el estado es inusual)
- [x] Voces independientes frente a indicadores, con aviso de redundancia por pilar
- [x] Divergencias dentro de un mismo pilar
- [x] Análogos con dos distancias (dinámica y entorno), episodios y nulo honesto
- [x] Bloque de comprobaciones permanentes al final de cada snapshot
- [x] **El documento concluye**: convicción mecánica por clase, contradicción resuelta
      dentro de la conclusión y no al lado, y neutral dicho claramente cuando la
      evidencia no alcanza
- [x] **Deltas estables**: media de ventana en vez de un cierre suelto; comprobación del
      mayor giro respecto al anterior
- [x] **Qué cambió desde el anterior**: memoria entre snapshots en `data/historico/`
- [x] **La lectura habla del mercado, no del documento**: cada línea carga evidencia o
      consecuencia; todo lo demás va al tablero plegado
- [x] **Cada inclinación lleva su evidencia**: indicadores concretos con su nivel, y lo
      que limita la convicción cuando no es alta
- [x] **Bloque «qué puede pasar»**: condición observable → consecuencia, de umbrales que
      el sistema ya usa; la extrapolación de plazo se marca como tal
- [x] **«Qué cambió» y la línea de clima dicen POR QUÉ**: nombran el indicador o eje
      responsable
- [x] **Techo de convicción por clase** (solo el extremo que contradice a esa clase);
      «alta» rara pero alcanzable, con distribución de 6 meses en el tablero
- [x] **La convicción mira el rumbo**; **pilares sin lectura unificada** marcados
- [x] **Análogo fuerte a la lectura**: una línea cuando hay un parecido en dinámica y
      entorno; si no, la lectura no menciona análogos

Pendiente (solo requiere la Terminal abierta una vez): `bb.refresh()` para traer el PER
adelantado del S&P y completar la sexta variable de la distancia de entorno. Mientras
tanto el documento funciona con cinco y lo declara.

Nota: los tres perfiles (conservador/moderado/agresivo) se probaron y se retiraron:
diluían el mensaje. Se sustituyeron por una sola inclinación por clase, más clara para
un documento informativo. La asignación con pesos concretos es trabajo del modelo de
ETFs, no de esta guía de lectura.

---

Fuentes: Federal Reserve Bank of St. Louis (FRED) y Yahoo Finance.
Documento descriptivo, sin recomendación de inversión.
