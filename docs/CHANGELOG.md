# Change log

## Cierre del PM Brief

### METODOLOGÍA
- **Tensión dominante de pilar de contexto.** Inflación y posicionamiento siguen
  sin votar dirección. Pero una divergencia contra ellos pasa a poder ser la
  tensión dominante si es **extrema** (≥70 puntos de brecha) y **persistente**
  (≥3 meses), con etiqueta propia —«Tensión dominante (pilar de contexto)»— y una
  línea que explica por qué importa. No desplaza a una tensión de eje: solo actúa
  cuando no hay ninguna. Precedente: 2021-11-01, crédito 88/100 contra inflación
  2/100 durante diez meses, la única señal de las cuatro fechas de validación que
  avisaba de 2022. Documentado en SPEC.md §3.1.
- **Persistencia como propiedad del indicador**, no como comprobación de cada
  selector. Cambia qué evidencia puede citarse: un extremo reciente ya no entra
  como evidencia, tensión, disparador, confirmación ni contradicción. Afecta a la
  evidencia citada por clase (en 2008 el oro dejó de apoyarse en la liquidez neta
  de dos días) y a los leads de los compuestos.

### LÓGICA
- La viñeta de coherencia (SPEC §12, «Postura general vs clases») se publica en
  el DecisionState y la escriben los dos formatos desde ahí. Antes vivía solo en
  la caja de síntesis del HTML.
- `_bloque` excluye los extremos recientes del lead en vez de solo degradarlos en
  el orden.

### PRESENTACIÓN
- El extremo que limita la convicción dice «, reciente» cuando lo es.
- El setup táctico dice «— extremos recientes» cuando se apoya en ellos.

### QA
- Check nuevo: «Postura general vs clases, escrita en ambos» — verifica el
  OUTPUT renderizado, no que el campo exista. El check anterior pasaba mientras
  la viñeta faltaba en el PDF.
- Check nuevo: «Indicadores recientes usados fuera de contexto» — recorre el
  documento renderizado, no los selectores uno por uno.
