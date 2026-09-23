# Estado de las fases 1 y 2 — Investment Decision Guide

Documento de situación. Qué se implementó, qué se encontró, qué quedó abierto.
Fuente de verdad del diseño: `SPEC.md`.

---

## Resumen en una pantalla

| | Fase 1 | Fase 2 |
|---|---|---|
| **Objetivo** | Capa `DecisionState`, 3 bugs de origen, QA, tests | Guía de decisión en el HTML |
| **Estado** | Cerrada | Implementada, con 3 correcciones en curso |
| **Tests** | 19 ✓ | 17 ✓ |
| **Archivos nuevos** | `snapshot/decision.py`, `tests/test_spec_fase1.py` | `tests/test_spec_fase2.py` |
| **Regeneración** | Limpia en las 5 fechas | Limpia en las 5 fechas |

**36 tests, 0 fallidos.** Generación sin warnings.

---

## FASE 1 — Refactor invisible + tres correcciones

### Lo que había

Pipeline de ~7.800 líneas, sin git, sin tests. Flujo:

```
data.py → indicators.py → scoring.py → senales.py / entorno.py
                                              ↓
                                          build.py
                                   ┌──────────┴──────────┐
                              decision.py            render.py
                              (capa nueva)
```

Dos hallazgos de la inspección:

1. **El render decidía.** `render.py` calculaba qué clases discrepan de sus
   análogos: comparaba la dirección del análogo contra la inclinación y aplicaba
   un umbral (`ANALOG_DISC_FRAC = 0.65`) declarado *dentro de la plantilla*. Con
   un segundo renderer (el PDF), eso son dos conclusiones distintas del mismo
   dato — justo lo que SPEC §2 prohíbe.
2. **El proyecto estaba roto.** `run_snapshot.py` lanzaba `TypeError`: una ronda
   anterior había quedado cortada a mitad de refactor.

### La capa DecisionState

`snapshot/decision.py`. Dataclasses `Eje`, `Discrepancia`, `DecisionState`, más
`build(snap, ctx, grupos, postura_en)` y `valores_compartidos()` — el contrato
que HTML y PDF no podrán contradecir.

La decisión de análogos se movió del render a la capa; el umbral vive en
`config`. Hay un test que lo vigila (`test_el_render_no_decide_quien_discrepa`).

### Los tres bugs, corregidos en origen

| Bug | Causa raíz | Corrección |
|---|---|---|
| **Analog window** | `"21 años"` **hardcodeado** en 3 sitios del render. La ventana real es dinámica: en 2008 son **2.5 años (2005-03-08 → 2007-09-14, 659 fechas, 4 episodios)**. El "21" venía de mezclar la base histórica del panel con la ventana de elegibles | El texto se deriva de `muestra` (`_analog_ventana()`) |
| **Risk axis direction** | Tres defectos apilados. El de fondo: **`scoring.band_label` devolvía la ÚLTIMA banda para cualquier valor fuera de rango**, así que `band_label(-0.1)` → **"euforia"**. Con el eje en p0.64 cayendo, extrapolaba a un suelo ya pisado → *"euforia en ~0 semanas"* | `band_label` ancla al extremo correcto; la extrapolación solo va en la dirección del movimiento, exige ≥1 semana y tope de 26 |
| **Risk score** | El gráfico usaba `resample("ME").last()` → cierre **crudo** sellado a **fin de mes** (2008-09-30, *posterior* al snapshot); el panel usa el nivel **suavizado** en `asof`. 5.4 vs 9.6 | El último punto se ancla a `asof` con el mismo `scoring.nivel()` del panel |

### QA automático — los 6 checks de SPEC §12

Visibles en el tablero. Cada uno vigila la clase de fallo que dejó pasar un bug:

`Mismo concepto, mismo valor` · `Dirección del eje frente a su etiqueta` ·
`Ventana histórica: narrativa frente a dato` · `Disparadores posibles y no
activados` · `La narrativa cita los mismos números que el estado` · `HTML y PDF
sobre el mismo DecisionState`

*(Selector consistency y postura-vs-clases ya existían de rondas anteriores.)*

### Horizontes — los 42 declarados

`tactical 7 · intermediate 20 · regime 15`, con invariante en `config` y
`HORIZON_TIMING = "tactical"`.

### Verificación 2008 campo por campo

**Cambió:** la línea de *euforia ~0 semanas* (bug 2), la ventana *21 años → 2.5
años* (bug 1), el final del gráfico *5 → 10* (bug 3), y +6 filas de QA.

**No cambió nada que no debiera:** paneles de eje, síntesis (5 viñetas
idénticas), posicionamiento (7 clases: sesgo, convicción y posición idénticos).
El refactor no introdujo ningún error.

---

## FASE 2 — Guía de decisión

### Estructura nueva del HTML (SPEC §4.2)

```
Investment Decision Guide  → régimen riesgo · régimen ciclo · postura ·
                             convicción · timing · horizonte · tensión
Executive read             → caja de síntesis + peso de la evidencia + gráfico
Positioning guide          → tabla de los 7 temas
Régimen y táctica          → régimen dominante vs setup táctico
Decision triggers          → Confirma · Debilita · Invalida · Oportunidad
Qué cambió                 → cambios que afectan decisiones
Qué puede pasar            → umbrales cercanos
Traducción por mandato     → tabla FIJA
Tablero de auditoría       → todo lo anterior, auditable
```

### Timing como dimensión independiente

Tabla de decisión pequeña (8 estados de SPEC §5.3). **Regla dura**: se deriva
solo de indicadores de horizonte táctico.

El test central mutila **los 35 indicadores no tácticos** (invierte percentil,
`op` y votos) y exige que el timing no se mueva. Sin ese test la regla se
degrada sola.

### Persistencia, path dependency, mandato

- **Persistencia** por horizonte, no ventana universal (3 días / 2 semanas / 1 mes).
- **Path dependency** recalculando la postura 18 meses hacia atrás, así que
  funciona en cualquier fecha aunque no haya snapshots guardados.
- **Mandato**: tabla fija en `config`, con test de que no cambia entre fechas.

### Las cuatro fechas

| | Titular | Tensión principal | Timing + setup | Análogos |
|---|---|---|---|---|
| **2008-09-15** | estrés severo p1, defensiva | `liquidez neta p99` | **paciente** + rebote contrario | 0 (ventana 2.5a) |
| **2020-03-16** | p0, caída vertical (−69 pts/mes) | `tesoro 2a p0` | **paciente** + rebote contrario | 0 (ventana 14a) |
| **2021-11-01** | apetito p77, expansión | sin tensión de eje → contexto | **extendido** + reversión | 1 (ventana 15.6a) |
| **2022-06-15** | tensión p10, defensiva | sin tensión de eje → contexto | **paciente** + rebote contrario | 0 (ventana 16.3a) |

**2020 destapó el conflicto temporal** que SPEC §5.4 quería ver:
`táctico: defensiva(24) · intermedio: defensiva(34) · régimen: pro-riesgo(57)`
— los indicadores lentos aún no habían visto el COVID.

### Las tres preguntas de diseño

**(a) ¿El timing aporta algo?** Sí. Misma convicción `media` → timing `paciente`
(2008) y `extendido` (2021). Mismo timing `paciente` → convicción `media` y
`baja`. No se mueven juntos.

**(b) ¿Aparece el setup táctico?** En los dos casos de libro, sí. El detector
exige **las dos familias tácticas a la vez**: contrarias baratas *y* estrés en su
extremo. Sobreventa sin miedo es una caída ordenada; miedo sin sobreventa es un
susto caro.

**(c) ¿Son alcanzables los "invalida"?** Encontré un error propio: medía la
distancia en **sigmas diarias**, y eso declaraba imposible todo (44σ, 30σ…).
Escalada al horizonte del trigger (σ·√días), los rangos quedan **1.1σ–7.0σ** y
solo 1 de 12 se marca fuera de alcance.

### Independent voices — análisis, sin implementar

32 fechas × 7 temas = **224 direcciones** (2011-2025):

- **87 diferirían (38.8 %)** — pero **cero giros `mas↔menos`**. Ni uno.
- Las 87 son *todas* `neutral → dirección`.

**La razón importa**: la métrica de cluster es un signo crudo que **no pasa por
el filtro de convicción**, mientras la dirección publicada sí. Ese 38.8 % mide
sobre todo el filtro que falta, no el clustering.

**Conclusión provisional**: el riesgo que temía SPEC (que el clustering mueva
direcciones) **no aparece como giro de lado en 15 años**. Antes de decidir habría
que repetirlo aplicando el mismo filtro a ambos sistemas. **No se implementó el
cambio**; la métrica está en el tablero con esa advertencia.

---

## Abierto — tres correcciones antes de la fase 3

1. **Plantillas que contradicen sus datos.** En 2008: *"el crecimiento siga
   superando al costo del capital"* (frase pro-riesgo en lectura defensiva),
   *"sigue estrés severo pero se deteriora"* (sin variante para el extremo), y
   *"la caída de liquidez continúa"* con la liquidez en p99. Falta una capa de
   verificación que cubra **todas** las secciones.
2. **Persistencia en el selector de tensión.** En 2008 la tensión lleva **dos
   días hábiles** en extremo: es ruido. La regla anti-whipsaw no se aplica a este
   selector.
3. **Timing global, no por clase.** El análisis de las cuatro fechas: 10 de 28
   filas difieren del global, **pero las 10 son clases sin dirección**
   (`neutral`, nada que cronometrar). Ninguna clase con dirección tuvo nunca un
   timing distinto → se elimina la columna.

---

## Archivos

| Archivo | Qué es |
|---|---|
| `SPEC.md` | Especificación. Fuente de verdad |
| `snapshot/decision.py` | Capa DecisionState (fases 1 y 2) |
| `tests/test_spec_fase1.py` | 19 tests |
| `tests/test_spec_fase2.py` | 17 tests |
| `baseline/2008-09-15.BASELINE.*` | Base para la comparación campo por campo |

No implementado (fases posteriores): PDF PM Brief.
