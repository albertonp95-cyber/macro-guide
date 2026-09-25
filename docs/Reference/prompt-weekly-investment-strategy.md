# Prompt — Weekly Investment Strategy

```
Lee SPEC.md, SEMANTIC-PASS.md y el mock
Weekly_Investment_Strategy_V5_Mock_Regenerated.pdf (guárdalo en
docs/reference/).

EL MOCK ES UN OBJETIVO DE FORMATO, NO DE CONTENIDO.

Sus números son inventados y no coinciden con ningún snapshot real. No
los copies, no los tomes como referencia de valores, y no ajustes nada
para parecerte a ellos. Lo que se toma del mock es la ESTRUCTURA, la
jerarquía y el registro de escritura.

═══════════════════════════════════════════════════════
QUÉ SE CONSTRUYE
═══════════════════════════════════════════════════════

El PM Brief actual de 3 páginas se sustituye por este documento.

Secciones fijas, número de páginas LIBRE. Cada sección ocupa lo que
necesite: si una da para media página, media; si da para dos, dos. No
rellenes para cuadrar y no comprimas para ahorrar.

Si una sección no tiene nada que decir en una fecha concreta, lo dice en
una línea y ocupa una línea. No se omite: su ausencia también es
información.

SECCIONES:

  1 · INVESTMENT VIEW
      Postura, confianza, horizonte, señal táctica. Compuesto de riesgo
      con su percentil y el espectro aversión/apetito. Régimen
      confirmado y candidato. Mercado/técnico y macro/fundamental con
      su score y su cohesión. Restricción principal.
      Más: conclusión de la semana, qué cambió, qué merece atención.

  2 · CROSS-ASSET POSITIONING
      Una fila por dimensión, agrupadas en bloques (renta variable,
      renta fija, activos reales y FX). Cada una con: espectro con sus
      dos extremos etiquetados, sesgo, confianza, confirmación táctica,
      y una frase de por qué.
      El USD va como overlay al final del bloque, con el encuadre de
      SEMANTIC-PASS puntos 14 a 17.

  3 · WHAT DRIVES THE VIEW
      Resumen para leer en voz alta, y después los pilares con
      contexto: score, cambio a 3m, interpretación en una línea, y —
      esto es importante — "N indicadores → ~M voces independientes"
      junto al score, no en letra pequeña.
      Pilares direccionales y pilares de contexto, separados.

  4 · MARKET EVIDENCE
      Aquí van los gráficos: el Cross-Asset Tape de SEMANTIC-PASS
      puntos 22 a 29, más los indicadores que sostienen la lectura, con
      su implicación de inversión al lado de cada uno.
      Puede ocupar una página o tres. Lo que haga falta.

  5 · WHAT CHANGED THIS WEEK
      Desde el snapshot anterior, con causa y con lectura: no "VIX +4"
      sino qué significa para la postura.

  6 · RESEARCH PERSPECTIVES
      Dónde el research externo añade información. Regla intacta: el
      research externo NO vota en la señal sistemática. Su trabajo es
      añadir contexto que falta, desafiar una conclusión, o mostrar que
      el mismo dato admite una segunda lectura.
      Cada entrada con fuente y fecha visibles, y una línea de "por qué
      importa".

  7 · DECISION RISKS & WATCHPOINTS
      Qué debilitaría la postura, qué la reforzaría, y la distancia a
      cada watchpoint en sigmas con su etiqueta (cerca / moderado /
      remoto).

═══════════════════════════════════════════════════════
LO QUE EL MOCK RESUELVE BIEN Y HAY QUE CONSERVAR
═══════════════════════════════════════════════════════

  · El "read-aloud summary" al frente de la sección 3. Es el mejor
    recurso del documento: obliga a que el argumento se sostenga dicho
    en voz alta.
  · "N indicadores → ~M voces independientes" junto al score. Resuelve
    la redundancia mejor que la nota al pie que tenemos hoy.
  · Las advertencias dentro de la evidencia, no fuera: "supportive is
    not the same as cheap", "low stress also means less cushion". El
    matiz va pegado al dato que lo produce.
  · Nombrar el hueco de confirmación cuando existe: si el modelo dice
    cíclico y el precio relativo no lo confirma, se dice con el número.
  · El research externo con su "por qué importa" explícito.

═══════════════════════════════════════════════════════
DOS COSAS QUE HAY QUE RESOLVER ANTES DE IMPLEMENTAR
═══════════════════════════════════════════════════════

1 · EQUITY BETA vs EQUITY STYLE — ¿presentación o voto nuevo?

El mock separa "equity risk" y "equity style" en dos filas con sesgo y
confianza propios.

Dime cuál de las dos cosas es sobre el DecisionState actual:
  a) un mapeo de presentación de lo que hoy son "renta variable" y
     "cíclico vs defensivo" — entonces adelante, es semántica
  b) un voto nuevo que exige mapeo de indicadores propio — entonces NO
     lo implementes: hace falta el análisis de independencia primero,
     según SEMANTIC-PASS punto 39 y punto 19

Lo mismo con "Corporates > Treasuries" como lente secundaria del bloque
de crédito.

Repórtame las dos antes de seguir.

2 · HUELLA DE DATOS VISIBLE

Ya hay tres renders del 22/09/2026 con cifras distintas, y la
explicación conocida es que son construcciones separadas por revisiones
de datos de Yahoo. Eso es legítimo, pero hoy no hay forma de
distinguirlas mirando el documento.

Añade al pie de la primera página la huella de los datos con los que se
generó, junto a la fecha del snapshot. Si mañana hay dos versiones del
mismo día, que se distingan a simple vista en vez de parecer una
contradicción.

═══════════════════════════════════════════════════════
REGLAS QUE NO CAMBIAN
═══════════════════════════════════════════════════════

  · Todo sale del DecisionState. El renderizador no recalcula lógica de
    inversión.
  · Terminología de SEMANTIC-PASS en todo el documento: señal táctica,
    confianza, condiciones monetarias, extensión y valor relativo,
    apoya/neutral/frena riesgo.
  · Sin pesos de cartera, sin asignación, sin órdenes.
  · Nada de "sobreponderar/infraponderar" (SEMANTIC-PASS punto 32).
  · Cada afirmación sobre el mercado verificada contra los datos del
    propio documento antes de emitirse.
  · Los selectores eligen por relevancia; el extremo desempata.
  · Un extremo sin persistencia solo aparece como contexto.

El HTML se queda como está en esta sesión. No lo toques: decidiremos su
papel cuando veamos este PDF funcionando.

═══════════════════════════════════════════════════════
VERIFICACIÓN
═══════════════════════════════════════════════════════

Genera el documento para 22/09/2026 y para las cuatro fechas de
validación. Repórtame por cada una:
  - cuántas páginas salieron y qué sección ocupó cada una
  - qué secciones quedaron con una línea por no tener contenido
  - si alguna afirmación no pudo verificarse contra los datos

Y léelo en voz alta mentalmente: sigue siendo la prueba. Si una frase no
se puede decir en una junta, no va.
```

---

## Lo que este cambio resuelve

Llevabas semanas intentando que un mismo documento fuera legible **y** auditable.
El mock demuestra que no hacía falta: son dos productos, y el bueno es este.

Eso también explica por qué el HTML se resistía tanto. No estaba mal construido —
estaba intentando hacer dos trabajos incompatibles a la vez.

## Sobre la decisión del HTML

Dijiste decidirla después de ver el PDF nuevo, y es lo correcto. Cuando lo tengas,
la pregunta concreta es: **¿abriste el HTML alguna vez esa semana?** Si la
respuesta es no durante tres o cuatro semanas seguidas, ya está decidido —
pasa a ser rastro de auditoría y todo HTML-POLISH se archiva salvo el punto 31
(auditabilidad) y el 34 (tests).
