# SPEC.md — Investment Decision Guide

Especificación del proyecto. Fuente de verdad del diseño.
Los prompts de cada fase referencian este documento; no se implementa nada que
lo contradiga sin actualizarlo primero.

---

## 0. Principio final

El sistema NO debe decir: *"aquí está el portafolio que deberías tener"*.

Debe decir: *"este es el régimen que observamos, estos son los riesgos que
favorece y desfavorece la evidencia, esta es nuestra confianza, este es el
horizonte relevante, este es el timing, estas son las expresiones relativas
preferidas, y estas son las condiciones que confirmarían, debilitarían o
invalidarían la lectura"*.

El gestor decide después cómo traducirlo a su mandato y a su nivel de riesgo.

---

## 1. Objetivo general

El pipeline genera **dos outputs desde el mismo estado de datos y la misma
lógica**:

1. **HTML maestro** — Investment Decision Guide (research, análisis, auditoría)
2. **PDF ejecutivo** — PM Brief (4–6 páginas, lectura rápida)

El sistema NO produce portfolio model, asset allocation ni pesos de cartera.
Produce una guía capaz de responder: *¿qué riesgos favorece actualmente la
evidencia, cuáles desfavorece, con qué convicción, en qué horizonte, cuál es el
timing, cómo conviene expresar relativamente esa visión, y qué tendría que
cambiar para modificarla?*

Debe servir a mandatos distintos: aggressive growth, opportunistic, hedge fund,
long-only, balanced, capital preservation. **El modelo genera la postura; el
mandato determina cuánto riesgo se asigna.**

### No incluir
pesos de cartera · asset allocation porcentual · risk budgets · posiciones
nominales · recomendaciones personalizadas por mandato

### Sí incluir
postura · convicción · timing · horizonte · expresión relativa preferida ·
riesgos a evitar · confirmaciones · debilitamientos · invalidaciones ·
oportunidades tácticas contrarias al régimen

---

## 2. Arquitectura

```
DATA
 ↓
SIGNALS
 ↓
DECISION STATE          ← capa intermedia común
 ↓
 ├── Full HTML renderer
 └── Executive PDF renderer
```

- HTML y PDF consumen **exactamente el mismo DecisionState**
- Cero lógica de inversión dentro de los templates
- El PDF nunca produce conclusiones distintas al HTML
- Si el PDF necesita un cálculo que no está en el DecisionState, el cálculo va
  al DecisionState, no al template

---

## 3. Reglas transversales

### 3.1 Selectores — elegir por relevancia, no por extremidad

El sistema tiene varios selectores: tensión principal, confirmaciones más
fuertes, contradicciones más fuertes, evidencia clave, triggers más cercanos,
divergencias clave. **Todos siguen la misma regla, sin excepción:**

> El selector elige por **relevancia al enunciado** que acompaña. El percentil
> extremo **desempata** entre candidatos relevantes; nunca selecciona por sí
> solo.
>
> Un indicador solo puede sostener una afirmación si **pertenece al pilar** del
> que habla esa afirmación. Posicionamiento e inflación no entran en ningún
> eje: no pueden ser evidencia de los ejes ni tensión principal. Pueden citarse
> como contexto, dicho como contexto.

*Precedente:* en el snapshot de la semana de Lehman el sistema declaró que la
tensión dominante era la sobreextensión del S&P (p0), teniendo HY OAS en 8,70 pp
y VIX en 31,7 en el mismo tablero. Eligió el percentil más extremo, no lo
relevante.

#### Excepción: divergencia extrema y persistente contra un pilar de contexto

**Cambio de METODOLOGÍA (no de lógica).** Inflación y posicionamiento siguen sin
votar dirección: su signo depende del régimen, y por eso no entran en ningún eje.
Eso no cambia. Lo que cambia es que una **divergencia contra ellos** sí puede ser
la tensión dominante cuando cumple **las dos** condiciones:

- **extrema** — brecha de al menos **70 puntos** de percentil entre los dos pilares
- **persistente** — al menos **3 meses**

Cuando ocurre, la etiqueta es explícita y distinta —«**Tensión dominante (pilar de
contexto)**»— y la acompaña una línea que dice por qué importa: que un pilar que
no vota dirección lleva meses en desacuerdo fuerte con los que sí votan.

La excepción **no desplaza a una tensión de eje**. Si hay pilares que votan y
están en desacuerdo, esa es la tensión del régimen; la excepción solo actúa
cuando no hay ninguna. Dejar que ganara por ser más ancha convertía el
posicionamiento en la tensión dominante de la semana de Lehman, que es
exactamente el sesgo de extremidad que esta sección prohíbe.

*Precedente:* en **2021-11-01** el crédito estaba en 88/100 con la inflación en
2/100, y llevaba diez meses así. No había ninguna divergencia entre pilares de
eje, así que la regla anterior dejaba la cabecera sin tensión dominante —y
escondía la única señal, de las cuatro fechas de validación, que avisaba de 2022
antes de que ocurriera.

### 3.2 Timing ≠ Horizonte

- El **horizonte** es propiedad del **indicador** (el VIX habla de semanas, la
  regla de Sahm de trimestres). Se **declara** en la configuración de cada
  indicador; no se infiere.
- El **timing** es propiedad de la **decisión**.
- **El timing se calcula únicamente con indicadores de horizonte táctico.** Un
  indicador de horizonte de régimen no puede influir en el timing.

### 3.3 "Favorecer" no significa "comprar"

Favorecer = dentro de un universo de riesgo, qué lado relativo está mejor
alineado con la evidencia. No implica necesariamente una posición larga. Debe
quedar explícito en la metodología del documento.

### 3.4 Fallbacks — la ausencia de evidencia es una salida válida

Si no hay información suficiente, **no se inventa**:
- `Timing: evidencia insuficiente`
- `Expresión preferida: —`
- `Comparación histórica: no disponible`
- `Cambio desde el anterior: no hay snapshot previo`

---

## 4. HTML maestro

### 4.1 Se mantiene todo lo actual
indicadores · percentiles · gráficos · eje de riesgo · eje de ciclo · pilares ·
extremos · divergencias · técnico vs macro · voces independientes · análogos ·
metodología · checks · fuentes · auditoría · detalle completo

### 4.2 Nueva estructura de la parte superior

**1) Investment Decision Guide** — legible en menos de un minuto:
régimen de riesgo · régimen de ciclo · postura general · convicción · timing ·
horizonte dominante · principal tensión

**2) Executive Read / peso de la evidencia** — 3 a 5 puntos:
qué domina · qué pilares sostienen la lectura · cuál es la principal
contradicción · si existe setup táctico contra el régimen · qué implica para
posicionamiento. Evitar lenguaje de certeza excesiva.

**3) Positioning Guide** — tabla principal:

| Tema | Postura | Convicción | Timing | Horizonte | Favorecer | Evitar / reducir |

Temas: Equity · Duration · Credit Quality · Cyclical vs Defensive · USD ·
Commodities · Gold. Contenido dinámico, nada hardcodeado.

**4) Régimen vs táctica** — dos bloques explícitos:
*Dominant regime* (lectura de mediano plazo) y *Tactical setup* (riesgos u
oportunidades de corto plazo que pueden ir contra el régimen).
Una condición contraria **no** es un cambio automático de régimen.

**5) Decision triggers** — cuatro bloques: Confirma · Debilita · Invalida /
Revierte · Tactical Opportunity

**6) What changed since last snapshot** — cuando exista histórico

**7) Mandate translation** — tabla **fija y metodológica**

---

## 5. Taxonomías

### 5.1 Postura
Favorable · Neutral · Defensive · Underweight bias · Overweight bias · Long
duration · Short duration · Raise quality · Lower quality · Defensive >
Cyclical · etc. Respetar la terminología existente del sistema.

### 5.2 Convicción
High · Medium · Low · Neutral / insuficiente.
Mantener la metodología actual siempre que sea razonable. **Si se modifica,
documentar exactamente qué cambió.** Nunca en silencio.

### 5.3 Timing
Dimensión **independiente** de dirección y convicción. Responde: *¿conviene
perseguir esta señal ahora, o hay una condición táctica que aconseja paciencia?*

Estados conceptuales: Confirmed · Favorable · Patient · Wait for confirmation ·
Extended · Contrarian risk elevated · Tactical reversal risk · Neutral.
Taxonomía pequeña, coherente y reusable.

Se deriva de: positioning · overextension · momentum · breadth · volatility ·
extremos técnicos · divergencias. **Solo indicadores de horizonte táctico.**

*Ejemplo:* Postura Defensive · Convicción Medium · Timing Patient / do not chase
weakness — porque la estructura es negativa pero el mercado está extremadamente
sobrevendido.

### 5.4 Horizontes
- **Tactical** — días a ~1 mes
- **Intermediate** — ~1–3 meses
- **Regime** — ~6–12 meses

Declarados por indicador en configuración. Cuando haya conflicto temporal, debe
poder mostrarse:
`Regime: Defensive · Intermediate: Defensive · Tactical: rebote contrario
favorable`

### 5.5 Expresión preferida
Cuando exista evidencia suficiente, una expresión **relativa** por clase:

- *Equity:* Quality > Low Quality · Low Beta > High Beta · Defensive > Cyclical ·
  Large > Small · Profitable > Unprofitable
- *Credit:* IG > HY · Higher > Lower Quality
- *Rates:* Long > Short Duration · Nominal > Inflation-linked (solo con soporte)
- *Cross asset:* Bonds > Equities · Gold favorable · USD favorable / neutral /
  adverso

**No inventar expresiones que los datos no soporten.** Sin evidencia: `—`

---

## 6. Decision triggers

Cada trigger debe contener, cuando sea posible:
variable · valor actual · condición o umbral · activo/postura afectada · efecto
esperado sobre postura, convicción y timing · horizonte · persistencia requerida

**Bloques:**
- **Confirma** — qué reforzaría la postura actual
- **Debilita** — qué reduciría convicción sin cambiar aún la dirección
- **Invalida / Revierte** — qué neutralizaría o revertiría la postura
- **Tactical Opportunity** — qué crea una oportunidad contra el régimen dominante

**Verificación de alcanzabilidad:** reportar la distancia de cada trigger en
unidades de la desviación típica reciente de su indicador. Un trigger que exige
40 puntos de percentil no invalida nada en la práctica.

---

## 7. Persistencia y path dependency

### 7.1 Anti-whipsaw
Una sola observación marginal no puede cambiar las señales. Confirmación por:
varios días · varias observaciones · más de una señal independiente · cambio
suficiente de percentil · salida clara de zona extrema.

**No usar una ventana universal:** la persistencia respeta la frecuencia y
naturaleza de cada indicador.

### 7.2 Path dependency
Con histórico suficiente, mostrar: duración de la postura actual · fecha del
último cambio · dirección del cambio · estado (improving / deteriorating /
stabilizing / unchanged).

Ejemplo: `Defensive · 4 months · stabilizing`
Derivado de snapshots históricos, nunca de texto manual.

---

## 8. What changed

Priorizar cambios que **afecten decisiones**, no cambios numéricos:
posture change · conviction change · timing change · trigger activado · nueva
divergencia · divergencia resuelta · indicador entra/sale de extremo · setup
táctico aparece/desaparece · régimen se refuerza/debilita

Preferir: *"Equity remains defensive, but timing moves from confirmed to patient
as positioning reaches a contrarian extreme."*
Sobre: *"VIX +4."*

---

## 9. Mandate translation

Sección pequeña y claramente separada: *cómo interpretar la misma señal según el
mandato*. **Tabla fija y metodológica** — no se genera por snapshot, no se
personaliza, no cambia con los datos.

| Señal | Growth / Opportunistic | Capital Preservation |
|---|---|---|
| Defensive + Medium | Reduce beta / relative value / hedge | Reduce risk / improve quality |
| Defensive + Oversold | Oportunidades tácticas / vender fuerza | Evitar capitulación / ajuste gradual |
| Pro-risk + Medium | Añadir selectivamente | Mover gradualmente hacia neutral |
| Pro-risk + High | Aumentar participación | Relajar defensas |
| Neutral / Divergente | Idiosincrático / relative value | Mantener disciplina estratégica |

No convertir en recomendaciones de pesos.

---

## 10. Independent voices — revisión metodológica

**Problema:** si 10 señales altamente correlacionadas apuntan al mismo lado,
pueden dominar el voto bruto aunque conceptualmente sean una sola familia de
riesgo.

**Sistemas a comparar:**
- *Actual:* indicator vote → direction → independence adjustment → conviction
- *Potencial:* indicator signals → correlation clusters → cluster/factor signal
  → direction → conviction

**Procedimiento obligatorio:** correr el análisis de impacto (cuántas
direcciones cambiarían, en qué clases, en qué fechas), reportarlo, y **parar
ahí**. No implementar el cambio en una sesión de implementación.

*Razón:* pasar a voto por cluster puede mover **direcciones**, no solo
convicciones, y eso invalidaría las validaciones históricas ya hechas.

**Sí implementar** la métrica paralela `cluster-adjusted directional score`,
visible solo en el tablero de auditoría, para poder comparar ambos sistemas.

---

## 11. PDF — PM Brief

4–6 páginas. **No es "print HTML to PDF"**: template propio, diseñado para
lectura rápida, comité de inversión, CIO, PM, morning meeting.

| Página | Contenido |
|---|---|
| 1 | Regime & Executive Read: fecha, régimen, eje de riesgo, eje de ciclo, postura, convicción, timing, tensión principal, 3–5 bullets |
| 2 | Positioning Guide: tabla compacta (Theme · Stance · Conviction · Timing · Horizon · Prefer · Avoid) |
| 3 | Regime vs Tactical: régimen dominante, setup táctico, confirmaciones y contradicciones más fuertes, divergencias clave |
| 4 | Decision Triggers: Confirms · Weakens · Invalidates · Tactical Opportunity |
| 5 | What Changed (si hay snapshot previo); si no, Key Evidence o se compacta |
| 6 (opcional) | Key Evidence / Methodology: 8–12 indicadores determinantes, nota metodológica, fuentes, disclaimer |

**Criterio de páginas:** si una página quedaría con menos de dos tercios de
contenido, se fusiona con la anterior. Cuatro páginas excelentes antes que seis
artificialmente llenas.

**No incluir** los 40+ indicadores completos: eso pertenece al HTML.

---

## 12. QA automático

Checks que se muestran en el tablero de auditoría del HTML (no hace falta
mostrarlos todos en el PDF):

- **Value consistency** — el mismo concepto no puede mostrar dos valores
  incompatibles
- **Direction consistency** — un deterioro del risk score no puede etiquetarse
  como "euforia"
- **Historical window consistency** — la narrativa coincide con la ventana
  realmente usada
- **Trigger consistency** — un trigger no puede ser imposible, ni mostrarse como
  futuro si ya está activado, ni tener el signo invertido
- **Narrative consistency** — la narrativa es compatible con los scores
  subyacentes
- **HTML/PDF consistency** — ambos muestran el mismo DecisionState
- **Selector consistency** — ninguna afirmación cita indicadores fuera de su
  pilar
- **Postura general vs clases** — si la postura declarada difiere de la
  inclinación de equity o duración, la síntesis debe mencionarlo

---

## 13. Bugs conocidos a corregir en el origen

Usar el snapshot **2008-09-15** como regression test.

1. **Historical analog window** — el documento afirma "sin episodios comparables
   en 21 años" mientras la sección de análogos parece usar ~2005–2007, 659
   fechas elegibles, 4 regímenes macro. Determinar el universo real, las fechas
   elegibles, el origen del "21 años", y si hay mezcla entre base histórica y
   ventana de análogos elegibles. **Corregir la fuente, no el texto.**

2. **Risk axis direction** — "si el eje de riesgo sigue al ritmo mensual (−12
   puntos de percentil) → euforia en ~0 semanas". Si un score más bajo implica
   más estrés, el sentido está invertido. Auditar fórmula, signo, umbral y
   etiqueta semántica. Añadir test lógico.

3. **Risk score inconsistency** — el gráfico termina cerca de 5 mientras otro
   panel muestra 10/100. Determinar si son raw vs suavizado, ventana distinta,
   compuesto distinto, bug de gráfico, valor obsoleto o problema de renderizado.
   Si son métricas distintas, etiquetarlas claramente; si deberían coincidir,
   corregirlo.

---

## 14. Validación

Cuatro fechas obligatorias:

| Fecha | Qué debe revelar |
|---|---|
| 2008-09-15 | Estrés severo. Regression test principal |
| 2020-03-16 | Caída vertical, distinta a 2008 |
| 2021-11-01 | Euforia. Espejo de 2008: destapa plantillas que asumen mercado cayendo. Debería marcar timing extendido con riesgo contrario elevado |
| 2022-06-15 | Pico inflacionario: bonos y bolsa cayendo juntos |

Por cada una reportar: si el titular describe correctamente lo que pasaba · si
la tensión principal elegida es la correcta · qué frases suenan falsas para ese
estado · si timing y setup táctico describen bien el momento · cuántos episodios
análogos califican.

**Tres preguntas de diseño que solo se responden con las cuatro fechas juntas:**
1. ¿El timing aporta algo distinto de la convicción? Si se mueven juntos
   siempre, la dimensión es redundante.
2. ¿El setup táctico aparece alguna vez? Si en 2008-09 y 2020-03 no marca
   rebote contrario con sobreventa extrema, el detector no funciona.
3. ¿Los triggers de "invalida" son alcanzables?

---

## 15. Tests

Sobre datos estructurados, no sobre texto narrativo exacto:
DecisionState generation · posture classification · conviction classification ·
timing classification · trigger generation · horizon assignment · comparación
con snapshot previo · consistency checks · valores compartidos HTML/PDF · casos
sin datos suficientes · primer snapshot sin histórico · regímenes
neutrales/divergentes

---

## 16. Lenguaje y diseño

**Tono:** institucional · analítico · conciso · orientado a PM/CIO ·
probabilístico · no promocional.

**Evitar:** sensacionalismo · lenguaje de certeza · "esto va a pasar" ·
pseudo-precisión · recomendaciones específicas sin respaldo · frases sobre el
propio documento.

**Preferir:** "la evidencia favorece" · "el sesgo sigue siendo" · "el riesgo es
elevado" · "el setup es consistente con" · "se debilitaría si" · "requiere
confirmación".

**Diseño:** sobrio, institucional, editorial, claro, imprimible, responsive, PDF
limpio. No un dashboard fintech. El color solo para: favorable · adverso ·
neutral · contradicción · cambio material. Jerarquía visual fuerte.

---

## 17. No hacer

No añadir pesos de cartera · no crear portafolios agresivo/defensivo · no
asignar capital · no introducir target returns · no inventar stop losses · no
inventar probabilidades · no hardcodear 2008 · no duplicar lógica entre PDF y
HTML · no reconstruir cálculos que ya funcionan · no añadir indicadores para
llenar secciones · no editar solo el HTML final · no tratar el PDF como una
captura larga del HTML.

---

## 18. Criterios de aceptación

1. Una sola ejecución del pipeline genera HTML + PDF
2. Ambos provienen de la misma lógica
3. El HTML mantiene toda la auditabilidad actual
4. El PDF resume únicamente lo relevante para decisiones
5. Postura, convicción y timing están separados
6. Existe régimen vs tactical setup
7. Existen decision triggers
8. Existe manejo explícito de horizontes
9. Existe What Changed cuando hay histórico
10. Los bugs están corregidos o explícitamente documentados
11. No existe portfolio allocation
12. El output se reutiliza para cualquier fecha sin hardcoding

---

## 19. Entregables

1. Código modificado (pipeline genera ambos outputs)
2. HTML generado para 2008-09-15
3. PDF PM Brief generado para la misma fecha
4. Change log separado en: **presentación** / **lógica** / **metodología**
5. Impacto metodológico: qué alteró stance, conviction, direction, cálculo de
   análogos o interpretación histórica
6. Resultados de QA: tests pasados, checks pasados, warnings, pendientes
7. Comparación con el snapshot anterior: qué señal cambió y por qué
8. Confirmación explícita de que HTML y PDF comparten DecisionState, que no se
   añadieron pesos, que no se generaron portafolios por mandato, y que no hay
   conclusiones hardcodeadas para 2008
