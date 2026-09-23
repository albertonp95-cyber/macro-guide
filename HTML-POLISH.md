# HTML-POLISH.md

FINAL HTML PRODUCT POLISH — DEPTH CONTROL / NAVIGATION / SHAREABLE PM VIEW

The current HTML architecture is APPROVED.

Do NOT redesign the product from scratch.

Keep:
- six-section architecture;
- desktop navigation;
- mobile navigation;
- Decision Cockpit;
- Regime Forces;
- Cross-Asset Positioning Matrix;
- Trigger Proximity;
- 12-month positioning heatmap;
- Research pillars;
- QA section;
- full auditability.

This pass is about:
1. reducing redundant layers;
2. improving progressive disclosure;
3. making the positioning matrix actionable;
4. improving What Changed;
5. making QA actionable;
6. introducing a clean PM / Full view switch;
7. synchronizing the HTML with the canonical DecisionState after the regression pass.

No new investment methodology.

---

## 1. CANONICAL DECISIONSTATE FIRST

This HTML must render from the reconciled canonical DecisionState.

Do not preserve stale values from an older HTML build.

The HTML must consume the same normalized DecisionState used by the latest PDF.

Required agreement:
- overall stance;
- overall conviction;
- global timing;
- dominant horizon;
- confirmed risk regime;
- candidate risk regime;
- confirmation status;
- cycle regime;
- positioning by theme;
- conviction by theme;
- timing overrides;
- triggers;
- affected themes;
- What Changed events;
- dominant tension;
- contradictory indicator.

The renderer must not recompute investment logic.

---

## 2. DO NOT REDESIGN THE VISUAL LANGUAGE

Preserve:
- typography;
- restrained color palette;
- editorial style;
- thin rules;
- current chart language;
- institutional appearance.

No:
- dashboard redesign;
- large cards everywhere;
- gradients;
- gauges;
- decorative illustrations;
- new chart types unless explicitly requested below.

---

## 3. POSITIONING — COLLAPSE DETAIL BY DEFAULT

The Cross-Asset Positioning Matrix should remain the primary overview.

The current detailed table must NOT be open by default.

Use `<details>`, not `<details open>`.

Summary: "Ver detalle por dimensión"

Default experience: Matrix → optional detail
Not: Matrix → full table immediately.

---

## 4. REMOVE REDUNDANT POSITIONING LAYERS

The positioning section currently contains multiple representations of the same
conclusion.

Keep in the main Positioning section:
A. Cross-Asset Positioning Matrix
B. Detailed per-theme view

Move the technical-vs-macro diagnostic table ("Tabla completa, con las señales
técnicas y macro por separado") out of the primary positioning section.

Move it to: Research or Auditoría, under a label such as "Descomposición de
señales por tema".

Reason: this is evidence / model diagnostics, not primary positioning.

Do not delete it.

---

## 5. MAKE THE POSITIONING MATRIX ACTIONABLE

Every matrix row should be clickable / keyboard accessible.

Example: click Duración → opens / scrolls to the Duration detail.

The detailed theme block should show:

```
Duración
Sesgo: Corta
Convicción: Media
Timing: [canonical timing]
Expresión: Duración corta > larga

Drivers:
PPI
[...]

Relevant trigger:
Real yield 10y
2.68% → threshold 2.21%

Risk: only if non-redundant.
```

The interaction path should be:
POSITIONING OVERVIEW → THEME DETAIL → DRIVER / TRIGGER → RAW INDICATOR

---

## 6. THEME DETAILS — USE ONE COMPONENT

Do not maintain separate ad-hoc HTML structures for each theme.

Create one reusable theme-detail structure driven from DecisionState.

Suggested fields: theme · bias · conviction · timing · horizon override ·
preferred expression · drivers · key risk · relevant triggers · previous state

Hide fields when empty.

---

## 7. TIMING — SHOW INHERITED VS THEME-SPECIFIC

Make the distinction visually obvious.

Examples:
```
Timing
Acompaña con reservas
· global
```
```
Timing
Acompaña sin reservas
· propio del tema
```
```
Timing
No acompaña todavía
· propio del tema
```

Do not use vague labels like "propio" by themselves.

The reader should immediately understand: inherited global timing vs theme
override.

---

## 8. RISK REGIME — CONFIRMED VS CANDIDATE

If the canonical DecisionState distinguishes confirmed regime and candidate
regime, show them explicitly.

Preferred pattern:
```
RÉGIMEN DE RIESGO
Confirmado: Neutral
→ Candidato: Apetito de riesgo
Confirmación: 4 días hábiles restantes
```

Do not display "neutral p75" without explaining why the percentile already lies
inside another candidate band.

This is a state-transition concept, not a contradiction.

---

## 9. DECISION COCKPIT — KEEP IT TIGHT

The first viewport should remain concise.

Target hierarchy:
PRO-RIESGO · Convicción · Timing · Horizonte · Risk regime state · Decision
takeaway · What Changed · Regime Forces · Dominant tension / top contradiction

Do not add more permanent cards.

---

## 10. WHAT CHANGED — MAKE IT A PRIMARY NAVIGATION TOOL

What Changed should be generated entirely from structured change events.

Show maximum 3 items in the Decision Cockpit.

Prioritize:
1. stance; 2. confirmed regime; 3. timing; 4. conviction; 5. trigger
activation; 6. major contradiction; 7. preferred expression; 8. indicator
extreme.

Example:
```
QUÉ CAMBIÓ
↑ Crédito · Convicción media → alta
↑ Equity · Convicción baja → media
! Nuevo extremo · Bolsa / bonos 3a · p93
[Ver todos los cambios]
```

Each item should link to the affected theme, trigger, indicator or history
section.

---

## 11. FULL CHANGE LOG

Keep the complete comparison lower in the HTML, structured by category:

DECISIONES — stance · conviction · timing · expression
SEÑALES — extremes · pillar shifts
TRIGGERS — activated · deactivated · changed reachability

This is easier to audit than one long undifferentiated list.

---

## 12. HISTORY — KEEP THE HEATMAP PROMINENT

Keep the 12-month positioning heatmap visible by default.

It answers: "Is today's view persistent or new?"

Do not hide it.

---

## 13. HISTORY — COLLAPSE DEEP ANALOG CONTENT

After the heatmap, collapse by default:
- full analog matrix;
- dispersion tables;
- analog-by-asset tables;
- "similar / different" breakdowns;
- long historical methodology.

Visible by default: regime trajectory · positioning heatmap · short analog
summary.

Then: "Ver análisis completo de análogos"

The user should not encounter dozens of historical rows unless requested.

---

## 14. ANALOG SUMMARY

Default analog block should show only:
- number of comparable episodes;
- best analog environment distance;
- 2–3 high-level outcome statistics;
- major disagreement with current positioning if applicable.

Do not imply forecasts.

Detailed data remains expandable.

---

## 15. RESEARCH — KEEP PILLARS COLLAPSED

Maintain: Pillar name · Score · Direction · 3m change · Independent voices ·
Top drivers

Then: "Ver N indicadores"

Do not auto-open any pillar.

---

## 16. DRIVER LINKS

Every driver shown in Decision Cockpit, Positioning or Trigger details should
link to its raw Research indicator.

Example: NFCI → #ind-nfci · Real yield 10y → #ind-real_10y

This keeps the analytical chain transparent.

---

## 17. QA — MAKE WARNINGS ACTIONABLE

Keep the top QA summary. Example:
```
CLEAN WITH WARNINGS
32 correct · 6 warnings · 1 unavailable
```

For every warning add "Ver problema" linking to the affected component.

Examples:
- Risk-regime state warning → Decision Cockpit
- Credit redundancy → Credit pillar
- Indicator-context warning → affected narrative / indicator
- Divergence warning → divergence section

---

## 18. QA SEVERITY

Use: ERROR · WARNING · INFO

Top status: CLEAN · CLEAN WITH WARNINGS · FAILED

Do not treat model divergence or conflicting indicators as ERROR merely because
markets disagree.

Reserve ERROR for:
- inconsistent state;
- mismatched labels;
- HTML/PDF mismatch;
- deterministic regression failure;
- impossible trigger state.

---

## 19. ADD VIEW MODE SWITCH

Add a simple top-level view switch: VISTA PM · VISTA COMPLETA

Default: VISTA PM

The switch affects presentation only. It must NOT alter any data or
calculations.

---

## 20. VISTA PM

Show: 01 Ahora · 02 Posicionamiento · 03 Qué vigilar · 04 Historia resumida

Hide / collapse by default:
- full Research;
- long methodology;
- raw indicators;
- full analog tables;
- full QA checks;
- document research details.

Keep a clear option: "Ver informe completo"

---

## 21. VISTA COMPLETA

Expose: all six sections · Research · documents · indicators · analog detail ·
divergences · QA · methodology · sources.

Use the same page. Do NOT generate two independent HTML files.

One HTML. Two presentation modes.

---

## 22. VIEW MODE PERSISTENCE

Use localStorage if appropriate.

If the user selects Vista completa, remember it on that browser.

Default for a new visitor: Vista PM.

---

## 23. SHAREABLE LINK BEHAVIOR

Support URL parameters or hash state if simple.

Examples: `?view=pm` · `?view=full`

Optional: `#posicionamiento` · `#vigilar` · `#historia`

This allows sharing the concise PM view, the full research view, or a specific
section.

Do not require a backend.

---

## 24. OPTIONAL DIRECT THEME LINKS

If straightforward, support anchors such as:
`#theme-equity` · `#theme-duration` · `#theme-credit` · `#theme-usd` ·
`#theme-gold`

This allows sharing a direct link to "Why is duration short?" or "Why is gold
unfavorable?"

---

## 25. MOBILE VIEW MODE

On mobile, Vista PM should be especially compact.

Order: Ahora · Qué cambió · Posicionamiento · Qué vigilar · Historia

Research / QA only after "Ver informe completo".

Do not make mobile users scroll through audit content by default.

---

## 26. MOBILE POSITIONING

Keep positioning as cards. Each card: Theme · Bias · Conviction · Spectrum ·
Timing · Preferred expression

Then: "Ver drivers y triggers" collapsed.

Do not show all evidence permanently.

---

## 27. MOBILE HISTORY

Default: last 6 months heatmap, with control `6m | 12m` or "Ver 12 meses" if
the full heatmap becomes too compressed.

Do not shrink cell labels below useful readability.

---

## 28. NO HOVER-ONLY INFORMATION

Any essential information currently available via `title=""` or hover must also
be available through tap, focus or expansion.

Desktop hover may remain as enhancement.

---

## 29. COPY CLEANUP

Run a final editorial pass. Fix:
- "a el" → "al";
- duplicated words;
- inconsistent Timing terminology;
- inconsistent "asset class" vs "positioning dimension" language;
- "sobreponderar/infraponderar" in user-facing decision text when a neutral
  bias label is more appropriate;
- malformed generated strings.

Preferred framing: "sesgo favorable", not "sobreponderar", unless discussing
historical/internal model terminology.

---

## 30. TERMINOLOGY

Use "Guía de posicionamiento cross-asset" and "dimensiones de posicionamiento",
not "asset classes", when referring collectively to: equity · duration · credit
quality · style · USD · commodities · gold.

---

## 31. KEEP FULL AUDITABILITY

No information may disappear from the full view.

This pass may: move · collapse · reorganize · link · summarize.

It may NOT delete: indicators · analogs · sources · documents · QA checks ·
methodology · divergences.

---

## 32. ACCESSIBILITY

All clickable matrix rows must also work via keyboard.

Use button semantics or appropriate tabindex / aria-expanded.

Details components must retain native accessibility.

View mode switch must indicate selected state.

---

## 33. PERFORMANCE

Keep the HTML self-contained. No large JS framework.

Prefer HTML, CSS, small vanilla JS.

PM/full mode should be implemented by classes / attributes, not by duplicating
the DOM.

---

## 34. REGRESSION PROTECTION

Add UI-level tests:

A. switch PM/full → DecisionState hash unchanged.
B. open/close theme detail → DecisionState unchanged.
C. view parameter → same underlying data.
D. renderer update → no change to trigger affected theme.
E. HTML normalized state = canonical DecisionState JSON.

---

## 35. FINAL TEST — DESKTOP

At 1440px, the user should understand:
- stance in <10 sec
- positioning in <30 sec
- what changed in <20 sec
- what to watch in <30 sec

The user should not need to open Research to understand the decision.

---

## 36. FINAL TEST — MOBILE

At 390px, no horizontal scroll for: cockpit · positioning cards · trigger cards
· QA summary.

Only allow horizontal scroll for: historical heatmap · genuinely wide
historical tables.

---

## 37. DELIVERABLE

Regenerate the HTML. Provide a summary with these six blocks:

**SIMPLIFIED**
- redundant positioning layer moved
- deep history collapsed
- full research hidden in PM view

**INTERACTION**
- clickable positioning themes
- driver links
- QA links
- What Changed links

**VIEW MODES**
- PM
- Full

**MOBILE**
- improvements applied

**CONSISTENCY**
- canonical DecisionState hash
- confirmation that HTML matches the PDF state

**UNRESOLVED**
- anything requiring methodology changes.

---

## 38. ACCEPTANCE CRITERIA

PASS only if:

1. PM view is significantly shorter than full view;
2. the first screen communicates the current decision state;
3. detailed positioning is closed by default;
4. technical/macro diagnostic table is no longer in the main decision flow;
5. each positioning row leads to theme detail;
6. What Changed links to affected evidence;
7. History shows the heatmap before analog detail;
8. Research remains fully available;
9. QA warnings are actionable;
10. PM/full switching does not modify DecisionState;
11. mobile is usable without desktop-style tables;
12. HTML matches the canonical DecisionState used by the PDF.

---

## FINAL PRINCIPLE

Do not make the HTML shorter by deleting information.

Make it shorter by controlling when information appears.

The user should choose the depth:

PM view → decision
Full view → evidence
Research → raw data
Audit → trust
