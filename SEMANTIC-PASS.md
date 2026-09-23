# SEMANTIC-PASS.md

SEMANTIC REWRITE + CROSS-ASSET FRAMEWORK PASS

The current HTML product architecture and visual design are broadly APPROVED.

Do NOT redesign the interface from scratch.

The main problem now is not layout. It is comprehension.

The current report still exposes too much internal model language and asks the
reader to understand the model architecture before understanding the investment
message.

This pass should make the product read like an experienced CIO / PM explaining
the market environment and its portfolio implications.

Primary goals:
1. radically improve language clarity;
2. give every model pillar explicit economic context;
3. remove confusing user-facing "Timing" terminology;
4. reframe USD as an FX overlay for USD-based portfolios;
5. improve the cross-asset framework;
6. connect historical regime evolution with actual cross-asset market behavior;
7. distinguish clearly between: what is happening economically; what markets are
   doing; what the portfolio implication is; what could change the view.

Do NOT optimize signals or change investment conclusions merely to improve the
narrative.

---

## 1. CORE COMMUNICATION PRINCIPLE

The reader should NOT have to understand the model in order to understand the
conclusion.

The hierarchy should be:

WHAT IS HAPPENING → WHAT MARKETS ARE CONFIRMING → WHAT IT MEANS FOR PORTFOLIO
POSITIONING → WHAT COULD CHANGE THE VIEW → HOW THE MODEL CALCULATED IT

Internal model terminology belongs mostly in Research / Audit.

Primary PM view should use normal investment language.

---

## 2. REMOVE "TIMING" FROM PRIMARY USER-FACING LANGUAGE

The word "Timing" is too ambiguous.

Do not use user-facing labels such as: Timing favorable · Timing mixto ·
Acompaña con reservas · Timing propio — without explaining exactly what they
mean.

Keep the existing internal timing methodology and enum if required for
compatibility. But replace the presentation layer with: **SEÑAL TÁCTICA**

The user-facing tactical states should be explicit.

**A. ACOMPAÑA**
Meaning: short-term / tactical evidence supports the intermediate view and there
is no material tactical signal pointing the other way.
Display: `Señal táctica: acompaña`

**B. ACOMPAÑA, PERO HAY UNA SEÑAL EN CONTRA**
Do not call this "mixed". Display explicitly:
`Señal táctica: mayormente a favor · 1 señal en contra`
or `Señal táctica: acompaña · con una condición en contra`

Whenever possible name the relevant opposing condition. Example:
`Señal táctica: acompaña · VIX confirma, pero el posicionamiento está estirado`

**C. NO CONFIRMA AÚN**
Meaning: the intermediate view exists, but short-term evidence does not yet
support acting aggressively in that direction.
Display: `Señal táctica: no confirma aún`

**D. CONTRADICE**
Meaning: short-term evidence is pointing against the intermediate view.
Display: `Señal táctica: contradice la lectura intermedia`

**E. SIN SEÑAL TÁCTICA**
Meaning: there is no meaningful short-term setup either way.

---

## 3. DO NOT HIDE THE REASON BEHIND A TACTICAL LABEL

Never display only "acompaña con reservas" without explaining the reservation.

BAD:
```
Señal táctica: acompaña con reservas
```

GOOD:
```
Señal táctica: mayormente a favor
Reserva: 1 condición táctica todavía apunta en contra.
```

BETTER:
```
Señal táctica: mayormente a favor
Reserva: el oro todavía no confirma el régimen risk-on.
```

Use actual DecisionState evidence, not hardcoded examples.

---

## 4. SEPARATE HORIZON FROM TACTICAL CONFIRMATION

Keep `Horizonte dominante: intermedio` separate from
`Señal táctica: acompaña / no confirma / contradice`.

The first answers: "How long is this view intended to matter?"
The second answers: "Are shorter-term conditions supporting it right now?"

Never combine these concepts.

---

## 5. REWRITE THE PILLAR TAXONOMY

The current pillar names are too model-centric and in some cases misleading.
Review them from the perspective of an investment professional.

| Current | Preferred | Question answered |
|---|---|---|
| Crédito y condiciones financieras | **CONDICIONES DE CRÉDITO** | "¿Es fácil o caro financiarse?" |
| Volatilidad y estrés | **ESTRÉS DE MERCADO** | "¿Cuánto miedo o tensión está descontando el mercado?" |
| Crecimiento y actividad | **CRECIMIENTO** | "¿La actividad económica está acelerando, estable o deteriorándose?" |
| Tendencia y momentum | **TENDENCIA DE MERCADO** | "¿Los precios están confirmando o contradiciendo el régimen?" |
| Liquidez y política monetaria | **CONDICIONES MONETARIAS** | "¿El costo y disponibilidad del dinero ayudan o frenan a los activos de riesgo?" |
| Inflación y precios | **INFLACIÓN** | "¿La inflación está añadiendo presión o alivio al entorno?" |
| Posicionamiento y valor relativo | **EXTENSIÓN Y VALOR RELATIVO** | "¿La operación ya está demasiado estirada o sigue teniendo espacio?" |

Interpretation language: Apoya riesgo · Neutral · Frena riesgo

**Inflación:** keep explicitly marked as CONTEXT if it does not vote directly
into the directional axes.

**Extensión y valor relativo:** this is NOT traditional investor positioning. Do
not call it "Posicionamiento" unless the model eventually includes actual
positioning information such as: futures positioning, CFTC, options, flows, CTA
exposure, surveys / sentiment.

---

## 6. REVIEW "LIQUIDITY" CONCEPTUALLY

The current "Liquidez y política monetaria" pillar includes variables such as:
real 10Y yield, Treasury 2Y, dollar-related measures, monetary variables.

This can confuse **quantity of liquidity** with **cost of capital**.

For this pass: rename the existing pillar to **CONDICIONES MONETARIAS** unless
the underlying variables genuinely measure system liquidity.

Use plain-language interpretation. Example:
```
CONDICIONES MONETARIAS · 40 / 100 · Frena riesgo
"Tasas reales elevadas y un costo del dinero restrictivo compensan parte de la
fortaleza de crecimiento y crédito."
```

Generate from actual evidence.

Do NOT make a methodological split in this pass unless the existing model
already supports it cleanly.

---

## 7. DOCUMENT A FUTURE METHODOLOGY SPLIT

If appropriate, note as FUTURE WORK: potentially separate **COSTO DEL DINERO**
from **LIQUIDEZ DEL SISTEMA**.

Possible Cost of Money inputs: real yields · policy rate · Treasury 2Y · term
structure.

Possible System Liquidity inputs: Fed balance sheet · reserves · RRP · TGA ·
other explicitly defined liquidity measures.

Do NOT implement this split casually. Report it as a methodology enhancement if
the existing inputs do not support it safely.

---

## 8. REWRITE "REGIME FORCES"

Rename **FUERZAS DEL RÉGIMEN** to **QUÉ ESTÁ IMPULSANDO EL RÉGIMEN** or another
equally clear Spanish phrase.

Each row should communicate: pillar · score · meaning

```
Condiciones de crédito      85    Apoya riesgo
Estrés de mercado           74    Apoya riesgo
Crecimiento                 69    Apoya riesgo
Tendencia de mercado        63    Apoya riesgo
Inflación                   53    Neutral · contexto
Extensión / valor relativo  53    Neutral · contexto
Condiciones monetarias      40    Frena riesgo
```

Do not force the reader to infer whether a high/low score is good or bad.

---

## 9. ADD CONTEXT TO EVERY PILLAR

Every pillar summary must answer:
1. What does this measure?
2. What is it saying now?
3. Why does it matter?

Example structure:
```
CONDICIONES MONETARIAS · 40 / 100 · FRENA RIESGO

Qué mide: El costo y disponibilidad del dinero.
Qué dice hoy: Las tasas reales siguen restrictivas.
Por qué importa: Un costo de capital alto puede limitar múltiplos y activos de
larga duración.
```

Use actual current evidence. Do not hardcode this exact conclusion.

---

## 10. USE THREE PRIMARY STATES FOR PILLARS

Instead of favorable / adverse, prefer in the primary PM view:
**APOYA RIESGO · NEUTRAL · FRENA RIESGO**

Research may still retain favorable / adverse where required by the underlying
signal framework.

---

## 11. REWRITE THE ENTIRE PRIMARY PM LANGUAGE

Perform a complete editorial rewrite of: Decision Cockpit · pillar descriptions ·
positioning descriptions · tactical-confirmation descriptions · trigger
explanations · What Changed · historical summaries.

Use concise PM language. Avoid internal jargon where possible. Avoid phrases
that require knowledge of implementation.

Internal language to minimize in PM view: cluster · independent voice · oriented
composite · pilar · vote · counterfactual · percentile mechanics.

Those concepts remain available in Research, Audit and Methodology.

---

## 12. PRIMARY POSITIONING LANGUAGE

Each positioning dimension should answer five plain questions:
1. WHAT SIDE?
2. HOW STRONG IS THE EVIDENCE?
3. DOES THE TACTICAL TAPE CONFIRM?
4. HOW WOULD THE VIEW BE EXPRESSED?
5. WHAT WOULD CHANGE IT?

Example:
```
DURACIÓN
Sesgo: Corta
Confianza: Media
Señal táctica: Acompaña
Expresión: Preferir vencimientos cortos frente a duración larga
Qué cambiaría la lectura: Tasa real 10a por debajo de 2.22 %
```

Use actual DecisionState.

---

## 13. RENAME "CONVICTION" USER-FACING

Prefer **CONFIANZA** instead of CONVICCIÓN in the primary PM view.

Allowed: Alta · Media · Baja

Research / methodology may retain the technical term conviction if required.

---

## 14. RETHINK THE USD DIMENSION

The current framing — "Dólar desfavorable", "Activos no denominados en dólar >
dólar", "Evitar concentrar la cartera en dólar" — is not appropriate for a
USD-based private-banking client.

The client's base currency may remain USD regardless of the macro USD view.

Reframe USD as **FX OVERLAY** or **ENTORNO DEL DÓLAR**.

The question is: "How should the USD backdrop affect international exposures and
FX hedging?"

NOT: "Should the client leave USD?"

---

## 15. USD USER-FACING STATES

Preferred states: **USD FORTALECIÉNDOSE · NEUTRAL · USD DEBILITÁNDOSE**

Then state portfolio implication.

When USD weakens:
```
ENTORNO DEL DÓLAR · Debilitamiento
Implicación para una cartera base USD:
La exposición internacional sin cobertura cambiaria recibe un viento de cola
relativo.
```

This does NOT mean sell USD cash or change the portfolio's base currency.

When USD strengthens:
```
Implicación: La fortaleza del dólar puede restar retorno a activos
internacionales en moneda local; aumenta la relevancia de evaluar cobertura FX.
```

Generate dynamically.

---

## 16. REMOVE BAD USD LANGUAGE

Do NOT say "Activos no denominados en dólar > dólar".

Do NOT say "Evitar concentrar la cartera en dólar" — unless the model genuinely
has a portfolio currency-allocation mandate.

Instead discuss: unhedged international exposure · FX translation effect ·
relative benefit/cost of hedging · USD sensitivity.

---

## 17. MOVE USD OUT OF CORE ASSET-ALLOCATION CALLS

Treat USD primarily as **FX OVERLAY**, not as a standard asset class.

Positioning hierarchy:

**CORE POSITIONING** — Equity · Rates · Credit · Equity style · Inflation
protection · Commodities · Gold

**OVERLAYS** — FX / USD · Tactical hedging / volatility if applicable

Do not force the USD view into every client's strategic base-currency decision.

---

## 18. REVIEW CROSS-ASSET DIMENSIONS

Target long-term framework:

**CORE**

1. **EQUITY BETA** — More or less equity risk?

2. **EQUITY STYLE** — Cyclical or defensive?

3. **RATES** — Front-end / cash vs duration? This is more portfolio-relevant
   than simply "Duration short".
   Preferred expressions: `Front-end > long duration` · `Neutral` ·
   `Long duration > front-end`

4. **CREDIT RISK** — IG vs HY / higher vs lower quality?

5. **INFLATION PROTECTION** — Nominal bonds vs inflation-linked / real-asset
   protection?
   Potential expressions: `Nominal > TIPS` · `Neutral` ·
   `TIPS / inflation protection > nominal`
   ONLY implement if existing indicators support this dimension. Otherwise
   classify as: FUTURE DIMENSION — insufficient signal architecture.

6. **COMMODITIES**

7. **GOLD** — Keep separate from broad commodities. Gold has a different macro
   function.

**OVERLAY**

8. **FX / USD**

---

## 19. DO NOT ADD UNSUPPORTED ASSET CALLS

Do NOT automatically add: Emerging Markets · Developed ex-US · Europe · Japan ·
Small Caps · Growth vs Value · REITs · Crypto.

Only create a new positioning dimension when: there is a coherent signal set ·
there is a defined vote mapping · conviction can be measured · there is a
meaningful trigger framework.

**The granularity of the output must not exceed the granularity of the
evidence.**

---

## 20. CASH / FRONT-END VS DURATION

Evaluate whether the current Duration signal can be presented more practically
as **RATES: Front-end / cash ↔ Duration**, without changing its underlying
logic.

For USD private-bank portfolios this is often a more actionable framing.

Example: `RATES · Front-end favored` instead of `Duration short`

Only do this if semantically equivalent to the current DecisionState.

---

## 21. INFLATION PROTECTION DIMENSION

Evaluate whether the existing signal architecture supports Nominal Treasury vs
TIPS / inflation-linked exposure.

Do not create the call unless evidence is sufficient.

If unsupported, document: "Inflation protection would improve the framework, but
current signals do not yet justify a standalone positioning call."

---

## 22. CROSS-ASSET HISTORY — MAJOR ENHANCEMENT

The current Risk / Cycle history chart is useful.

Extend the History section so the reader can see:
A. how the MODEL VIEW evolved
B. how CROSS-ASSET MARKETS actually behaved

This is context. It is NOT yet a performance backtest.

---

## 23. CREATE A "CROSS-ASSET TAPE" SECTION

Add: **CROSS-ASSET TAPE · 12 MONTHS**

Use already available market series where possible. Suggested series:

| Dimension | Series |
|---|---|
| Equity | SPY or broad equity proxy |
| Rates | IEF / TLT, potentially SHY if already available |
| Credit | HYG / LQD, or HY vs IG relative-performance series |
| Equity style | XLY / XLP |
| Commodities | DBC |
| Gold | GLD |
| USD | UUP or DXY proxy already used |
| Inflation-linked | TIP — ONLY if already available or added intentionally as context |

---

## 24. ALIGN ALL CROSS-ASSET CHARTS TO THE SAME TIME AXIS

Use the same 12-month x-axis. Preferred display: small multiples.

```
EQUITY              ──────── line
RATES               ──────── line
CREDIT RISK         ──────── line
CYCLICAL / DEFENSIVE ─────── line
COMMODITIES         ──────── line
GOLD                ──────── line
USD                 ──────── line
```

All aligned vertically. This makes regime transitions visually comparable across
markets.

---

## 25. NORMALIZE WHERE APPROPRIATE

For price series: index to 100 at the beginning of the selected window, or use
cumulative return.

For relative expressions: use ratio / relative-return series. Examples: Credit
`HYG / LQD` · Style `XLY / XLP`

Do not compare raw price levels with incompatible scales.

---

## 26. OVERLAY MODEL STATE WITHOUT CREATING A BACKTEST

Under each cross-asset chart, optionally show a thin band representing the model
stance through time.

Example: equity price series, below it `Neutral → Favorable → Favorable`

This allows the reader to see what the market did while the model view evolved.

Do NOT label this: performance · hit rate · alpha · success — unless a formal
backtest is later built.

---

## 27. CROSS-ASSET TAPE QUESTIONS

The historical visual should help answer:
- Is the current regime new or persistent?
- Did equity confirm the move?
- Did credit confirm?
- Did duration diverge?
- Are cyclicals confirming?
- Are commodities confirming?
- Is gold behaving like a hedge or risk asset?
- Is the USD helping or fighting international exposure?

These are more useful than simply showing model scores.

---

## 28. HISTORY LAYOUT

Preferred order:
1. Risk / Cycle trajectory
2. Cross-Asset Tape
3. Positioning heatmap
4. Analog summary
5. Full analog detail collapsed

This moves observable market behavior ahead of analog statistics.

---

## 29. ADD A SHORT INTERPRETIVE SUMMARY ABOVE CROSS-ASSET TAPE

Maximum 3 bullets. Example structure:

```
CROSS-ASSET CONFIRMATION
• Equity and credit confirm the pro-risk regime.
• Duration remains the main cross-asset exception.
• USD weakness supports unhedged international exposures.
```

Generate dynamically. No generic boilerplate.

---

## 30. DISTINGUISH THREE DIFFERENT THINGS

Do not blur: MACRO ENVIRONMENT · MARKET BEHAVIOR · PORTFOLIO VIEW

Example:
```
Macro: growth remains supportive.
Market behavior: credit spreads and equity trend confirm.
Portfolio implication: favor equity risk and HY over IG.
```

This structure should appear throughout the document.

---

## 31. REWRITE DECISION COCKPIT

Target language:
```
CURRENT VIEW · PRO-RISK
Confidence: Medium
Horizon: Intermediate
Tactical signals: Mostly supportive · 1 material condition against
Risk regime: Confirmed Neutral → Candidate Risk Appetite · 3 days until
confirmation

WHY
Supports risk: Credit · Market stress · Growth · Trend
Restrains: Monetary conditions · Real yields
```

This is clearer than presenting several unexplained scores first.

---

## 32. REMOVE LANGUAGE THAT SOUNDS LIKE PORTFOLIO ORDERS

Unless explicitly required, avoid: overweight · underweight · sell · buy · avoid
· add aggressively

Prefer: favor · less attractive · relative preference · supports · does not
support · front-end preferred · HY favored vs IG

This remains an investment-decision guide rather than a model portfolio.

---

## 33. "AVOID" SHOULD BE REWRITTEN

Current "Evitar" language can sound more prescriptive than intended.

Rename to **EXPOSICIÓN MENOS ATRACTIVA** or **QUÉ QUEDA DEL LADO MENOS
FAVORECIDO**.

Example: `Less attractive: expensive defensive equities` instead of `Avoid
expensive defensive equities`.

---

## 34. GLOSSARY SHOULD NOT BE REQUIRED

The PM view must be understandable without opening a glossary.

A glossary may remain in Research.

If the reader must look up pilar · voice · cluster · timing · oriented ·
counterfactual to understand the main view, the rewrite has failed.

---

## 35. RESEARCH MAY RETAIN TECHNICAL LANGUAGE

Research and Audit may continue to use: percentile · independent voices ·
clusters · indicator voting · counterfactual simulation — because those sections
exist for auditability.

But user-facing labels should always include plain-language equivalents.

---

## 36. AUDIT THE DOCUMENT FOR UNDEFINED TERMS

Search the entire generated HTML and list all concepts that appear in PM view
without an explanation. Examples: NFCI · OAS · real yield · risk axis · cycle
axis · percentile · independent voice.

For common professional abbreviations such as HY / IG / VIX: allow them.

For less intuitive items: use concise tooltip / parenthetical definition.

---

## 37. DO NOT ADD MORE PERMANENT TEXT

The solution is NOT more paragraphs.

Use: better labels · short descriptions · tooltips · progressive disclosure ·
clear hierarchy.

**The main PM view should become SHORTER after this rewrite.**

---

## 38. PDF CONSISTENCY

Do not redesign the PDF during this pass unless necessary.

But produce a report of all terminology changes that should later propagate to
the PDF. Examples:

| Old | New |
|---|---|
| Timing | Tactical signal |
| Liquidity | Monetary conditions |
| Positioning | Extension / relative value |
| USD | FX overlay |
| Conviction | Confidence |

Do not allow HTML and PDF to evolve into different vocabularies permanently.

---

## 39. DO NOT CHANGE DECISIONSTATE SILENTLY

This pass is primarily semantic.

If changing Duration → Rates / front-end vs duration is only a presentation
mapping, keep the underlying DecisionState unchanged.

If adding Inflation Protection requires a new signal model, do NOT add it in
this pass. Document it as a proposed methodology extension.

---

## 40. FINAL DELIVERABLES

Regenerate the HTML. Also produce:

**SEMANTIC CHANGES** — old term → new term → reason

**PILLAR CONTEXT** — for every pillar: question answered · current
interpretation · why it matters

**CROSS-ASSET FRAMEWORK** — current dimensions retained · dimensions reframed ·
dimensions proposed but not implemented

**USD / FX** — explicit confirmation that the USD signal no longer implies
changing a USD-based client's base currency

**HISTORY** — confirmation that Cross-Asset Tape was added and remains
observational, not a backtest

**DECISIONSTATE** — confirmation of any field that changed and why

---

## 41. ACCEPTANCE CRITERIA

PASS only if:

1. "Timing mixto" does not exist.
2. Primary PM view no longer requires understanding internal timing logic.
3. Tactical state is stated explicitly as: accompanies / does not confirm /
   contradicts / no signal, with the reason visible.
4. "Liquidity" is not used ambiguously.
5. "Positioning" is not used for extension/value-relative signals.
6. Every regime force tells the reader whether it supports risk / neutral /
   restrains risk.
7. USD is framed as an FX overlay for USD-based investors.
8. USD language does not imply abandoning the portfolio's base currency.
9. Cross-Asset Tape aligns observable asset behavior through time.
10. Model stance and market performance remain clearly separate.
11. Rates framing is more portfolio-relevant if semantically possible.
12. Inflation protection is only added if supported by the signal architecture.
13. PM view is shorter and easier to understand than before.
14. Research and Audit retain full technical depth.
15. No unsupported investment conclusion is introduced.

---

## FINAL PRINCIPLE

The reader should first understand the market.

Then understand the portfolio implication.

Only after that should they need to understand the model.
