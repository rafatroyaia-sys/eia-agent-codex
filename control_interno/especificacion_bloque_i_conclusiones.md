# Especificación metodológica — AG-10 / Bloque I
## Conclusiones del Documento Ambiental

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque I válido en este sistema

El Bloque I es el **cierre técnico del promotor**. No es el IIA (que corresponde al órgano ambiental), no es un resumen popular (eso es el Bloque J), y no es una valoración de viabilidad ambiental (eso lo hace el órgano ambiental, art. 47 Ley 21/2013).

Un Bloque I válido cumple seis condiciones:

1. **Subordinado a los bloques técnicos**: no puede ser más concluyente que ninguno de los bloques A, B, C, D, E, H que sintetiza. Todo qualifier que exista en esos bloques debe aparecer en Bloque I.

2. **Completo**: abarca el encuadre jurídico, la síntesis del análisis ambiental, las medidas y el PVA, el análisis de Natura 2000, y los pendientes activos.

3. **Transparente sobre limitaciones**: el modo de elaboración (gabinete / campo), los gaps activos y las incertidumbres están visibles con sus códigos. No se absorben en la narrativa.

4. **Jurídicamente limpio**: no anticipa la resolución del órgano ambiental. No dice qué "debería" hacer el órgano. Solo presenta lo que el promotor ha analizado y concluye en su propio ámbito.

5. **Sin lenguaje triunfalista**: el Bloque I no comercializa el proyecto ni interpreta el balance ambiental con frases de marketing. Describe hechos técnicos documentados.

6. **Consistente en modo test**: si el expediente está en modo test, el Bloque I lo declara explícitamente y distingue qué pendientes son propios del modo test vs cuáles existen también en modo real.

---

## §2. Relación exacta entre bloques previos y Bloque I

El Bloque I sintetiza en una sola vista todo lo que los bloques técnicos han establecido. Cada campo del Bloque I tiene un origen preciso que no puede contradecir:

| Campo del Bloque I | Origen | Restricción |
|-------------------|--------|-------------|
| Denominación del proyecto y RC | AG-04 / Bloque A | Literal — no parafrasear de forma que cambie el scope |
| Superficie y capacidades | AG-04 / Bloque A | Mismas cifras, mismo estado de evidencia (DECLARADO si no hay plano formal) |
| Operaciones incluidas / excluidas | AG-04 / Bloque A | Misma lista; las excluidas deben permanecer excluidas en I |
| Procedimiento aplicable | AG-05 / Bloque A.6 | Misma articulación legal |
| Factores sin afección directa apreciable | Bloque B + AG-09 | Con mismo nivel de certeza — no elevar de INFERIDO a CONFIRMADO |
| Significancias de impactos | AG-09 → Bloque C | Reproducir tabla exacta, sin agregaciones ni recálculos |
| Medidas | AG-09 / Bloque D | Listar las mismas medidas (M-01 a M-NN), referencias cruzadas |
| PVA | AG-09 / Bloque E | Confirmar que existe; pendientes del PVA (p.ej. Responsable Ambiental) visibles |
| Análisis Natura 2000 | Bloque H → AG-06 | Copiar conclusión de H.4 con sus tres partes; no simplificar a "no afecta" |
| Gaps activos | `inferencias_y_gaps.json` | Reproducir con código GAP-XXX, sin borrar ni minimizar |

**Regla de lectura antes de escribir**: antes de redactar el Bloque I, leer los bloques A, B, C, D, E y H en su estado actual. No escribir de memoria ni parafrasear sin verificar.

---

## §3. Cómo resumir cada área de contenido

### 3.1. Objeto evaluado (I.1-I.2)

- Reproducir la denominación exacta del proyecto tal como aparece en AG-04 / Bloque A.
- Confirmar el RC, la superficie y el municipio.
- Confirmar el encuadre en el Anexo II de la Ley 21/2013 (o el procedimiento aplicable verificado por AG-05).
- Señalar qué operaciones **no** están incluidas en el objeto evaluado (tabla de exclusiones).
- Si algún dato de identificación tiene estado DECLARADO, mantenerlo así.

### 3.2. Inventario (resumen en I.3.1)

- No reproducir el inventario completo — referenciar Bloque B.
- Solo declarar, para los factores relevantes, el resultado del análisis: factor sin afección apreciable identificada / factor con afección analizada / factor con limitaciones de análisis.
- Cada afirmación sobre ausencia de afección lleva el qualifier del modo de elaboración:
  - Correcto: "no se identifica afección apreciable directa según el análisis realizado en modo gabinete"
  - Prohibido: "sin afección directa significativa" (terminología incorrecta + ausencia de qualifier)
- Los factores con semáforo PENDIENTE_VERIFICACION o NO_CONSTA en AG-08 aparecen con esa limitación declarada.

### 3.3. Impactos y significancias (I.3.2)

- Reproducir la tabla de impactos de Bloque C / AG-09 con sus significancias antes y después de medidas.
- No recalcular, no agregar, no interpretar la tabla.
- IMP-08 (condicionante transversal PRL) aparece con su tratamiento correcto: fuera de la escala de significancia nuclear EIA, condicionante de gestión.
- Los impactos INDETERMINADO (si existen) deben figurar como tales — no se puede sustituir por estimación.
- Frase resumen permitida: "El impacto de mayor significancia es [IMP-XX], que [alcanza / no supera] la categoría [X] con las medidas propuestas. Ningún impacto negativo alcanza la categoría Severo ni Crítico [si es cierto según la tabla]."

### 3.4. Medidas y PVA (I.3.3-I.3.4)

- Listar las medidas M-01 a M-NN con descripción sucinta. No proponer medidas nuevas.
- Si alguna medida está condicionada a un dato pendiente, declararlo.
- Confirmar que el PVA cubre los impactos de categoría Compatible o superior.
- Declarar el pendiente del Responsable Ambiental si no está designado (GAP-PVA-001 en el piloto).

### 3.5. Análisis de Natura 2000 y ENP (I.3.5)

- Reproducir la conclusión de H.4 con sus tres partes: localización + vectores + limitación.
- No simplificar a "no afecta" ni a "el proyecto es compatible con Natura 2000".
- Mantener los qualifiers "estimada" en distancias, "gabinete" en el análisis.
- Formulación correcta de referencia:
  > "El análisis realizado en modo gabinete no aprecia afección apreciable sobre los espacios Red Natura 2000 del ámbito a través de los vectores analizados (dispersión de partículas, drenaje, fauna móvil), con las limitaciones declaradas en Bloque H."

### 3.6. Limitaciones y gaps (I.5)

- Listar todos los gaps de criticidad ALTA del `inferencias_y_gaps.json` con su código, descripción y criticidad.
- No omitir ninguno por ser "conocido" o "habitual en modo test".
- Diferenciar: gaps que bloquean la presentación del DA (criticidad ALTA estructural) vs gaps que el promotor puede resolver antes de presentar.
- No presentar los gaps como "aspectos a mejorar" ni como "incidencias menores". Si el sistema los marcó como criticidad ALTA, así aparecen.

---

## §4. Distinción promotor / órgano ambiental

Esta es la frontera más crítica del Bloque I. El Bloque I es el cierre técnico del **promotor**. El **Informe de Impacto Ambiental** es el pronunciamiento del **órgano ambiental** (art. 47 Ley 21/2013).

### Lo que el promotor SÍ puede formular en el Bloque I

- Qué impactos ha identificado y con qué significancias, según la metodología aplicada.
- Que ningún impacto negativo supera la categoría [X] según el análisis realizado.
- Que propone determinadas medidas para reducir los impactos.
- Que el proyecto está encuadrado en el Anexo II de la Ley 21/2013 (EIA simplificada).
- Que presenta el DA al órgano sustantivo para que este lo traslade al órgano ambiental.
- Que los pendientes listados deberán resolverse durante la tramitación.

### Lo que el promotor NO puede formular en el Bloque I

| Formulación prohibida | Por qué está prohibida | Alternativa permitida |
|----------------------|----------------------|----------------------|
| "el proyecto no requiere EIA ordinaria" | Esa determinación corresponde al órgano ambiental (art. 47.3) | "El promotor considera que el proyecto está encuadrado en EIA simplificada y presenta el DA al efecto" |
| "el proyecto no debería requerir EIA ordinaria" | Mismo motivo — la forma condicional no elimina la usurpación | Misma alternativa |
| "el proyecto es viable ambientalmente" | La viabilidad ambiental la determina el IIA, no el DA | "El promotor concluye que los impactos son de bajo-medio rango y propone las medidas descritas" |
| "el proyecto cumple la normativa ambiental" | El DA documenta el encuadre normativo; el órgano evalúa el cumplimiento | "El promotor entiende que el proyecto cumple los requisitos del art. 45 y Anexo VI de la Ley 21/2013" |
| "la Red Natura 2000 queda protegida" | El órgano ambiental es quien determina suficiencia de protección | "No se aprecia afección apreciable según el análisis de gabinete" |
| "el balance ambiental es positivo" | La valoración de balance global excede el ámbito del DA | No usar esta formulación; describir la escala de impactos negativos y la existencia de impactos positivos por separado |

### La nota de rol

El Bloque I abre con una nota de rol que declara explícitamente esta distinción. No puede omitirse ni reducirse a una nota al pie.

Formulación estándar:
> Las conclusiones de este bloque son las del **promotor**, formuladas a través del Documento Ambiental. El Informe de Impacto Ambiental (IIA) es el documento que formula el **órgano ambiental competente** (art. 47 Ley 21/2013) tras el trámite de consultas previsto en el art. 46. La determinación de si existen efectos significativos sobre el medio ambiente y si procede EIA ordinaria corresponde exclusivamente al órgano ambiental.

---

## §5. Modo test vs expediente real

El Bloque I en modo test es válido metodológicamente. No baja el umbral de las reglas no negociables.

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Nota de modo | Visible en cabecera y en I.5 | Solo si el expediente se presenta en estado provisional |
| Gaps de campo (fauna, flora, patrimonio) | Declarados como tales; el análisis es de gabinete | Requieren resolución antes o durante tramitación |
| Pendientes de identificación (RC, coordenadas, plano) | Declarados DECLARADO o PENDIENTE con su criticidad | Deben estar CONFIRMADO para presentar |
| Gaps de gestión (Responsable Ambiental) | Declarados como condición para operar | Deben estar resueltos antes del inicio de actividad |
| Formulación de la valoración global | Con qualifier de modo test | Sin qualifier si todos los datos están confirmados |

La línea de cierre de la sección I.4 en modo test debe incluir:
> "Las conclusiones anteriores corresponden a un análisis realizado en modo gabinete con la documentación disponible. Para el expediente presentable ante el órgano ambiental, los pendientes listados en I.5 deben resolverse previamente."

---

## §6. Estructura mínima obligatoria del Bloque I

```
I.1. Objeto y alcance de las conclusiones
     — denominación exacta del proyecto
     — RC, superficie, municipio, operaciones incluidas/excluidas
     — referencia al procedimiento aplicable

I.2. Encuadre jurídico — confirmación del promotor
     — encuadre en Anexo II Ley 21/2013
     — exclusión del Anexo I
     — exclusión de AAI (si aplica)
     — capacidad técnica del redactor

I.3. Síntesis del análisis ambiental
     I.3.1. Factores sin afección apreciable identificada
            — tabla con factor, resultado, fundamento y qualifier
     I.3.2. Impactos identificados y significancias
            — tabla reproducida de Bloque C
     I.3.3. Medidas propuestas
            — listado M-01 a M-NN
     I.3.4. Programa de Vigilancia Ambiental
            — confirmación de existencia; pendientes del PVA
     I.3.5. Análisis de afección a Red Natura 2000 y ENP
            — conclusión de H.4 con sus tres partes y qualifiers

I.4. Valoración global del promotor
     — formulación prudente de la posición del promotor
     — sin usurpación del papel del órgano ambiental
     — nota de modo test si aplica

I.5. Pendientes declarados para expediente real
     — tabla con ID, descripción y criticidad
     — todos los gaps de criticidad ALTA del inferencias_y_gaps.json
```

No se puede omitir ninguna sección. Si una sección no tiene contenido sustantivo, se declara así y se indica la causa.

---

## §7. Fórmulas permitidas y fórmulas prohibidas

### Fórmulas de cierre del Bloque I — permitidas

| Contexto | Formulación estándar |
|----------|---------------------|
| Síntesis de impactos negativos | "El promotor ha identificado [N] impactos negativos. El de mayor significancia es [IMP-XX] ([significancia sin medidas] → [significancia con medidas]). Ningún impacto negativo alcanza la categoría Severo ni Crítico según el análisis realizado." |
| Síntesis de Natura 2000 | "El análisis realizado en modo gabinete no aprecia afección apreciable sobre los espacios Red Natura 2000 del ámbito a través de los vectores analizados, con las limitaciones declaradas en el Bloque H." |
| Encuadre del promotor | "El promotor entiende que el proyecto se encuadra en EIA simplificada (art. 7.2.a Ley 21/2013) y presenta el presente Documento Ambiental al efecto, sin perjuicio de la valoración que el órgano ambiental realice en el marco del art. 47." |
| Cierre final del promotor | "Sobre la base del análisis desarrollado en el presente Documento Ambiental, el promotor somete el proyecto a la evaluación del órgano ambiental competente, con la documentación técnica y los compromisos de medidas descritos." |

### Fórmulas prohibidas en cualquier sección del Bloque I

| Formulación prohibida | Motivo |
|----------------------|--------|
| "el proyecto no afecta a [factor/espacio]" | Ausencia sin evidencia; omite qualifier de modo |
| "la actividad es compatible con el medio ambiente" | Usurpa papel del órgano ambiental |
| "el balance ambiental neto es positivo" | Agregación no soportada por Conesa; lenguaje de marketing |
| "no debería requerir evaluación ordinaria" | Anticipa resolución del órgano |
| "los impactos son insignificantes" | Lenguaje fuera de la escala de significancias del sistema |
| "el proyecto cumple con toda la normativa ambiental" | El DA documenta; el órgano ambiental evalúa el cumplimiento |
| "vectores indirectos despreciables" | Cuantificación sin modelización |
| "sin afección directa significativa" | Terminología incorrecta ("apreciable" es el umbral de la Directiva Hábitats) |
| "el análisis demuestra que..." | El análisis indica, no demuestra — especialmente en modo gabinete |

---

## §8. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien en el piloto

1. **Nota de rol inicial** — la advertencia de apertura distinguía correctamente promotor/órgano ambiental. Es un elemento a mantener y proteger.
2. **Organización en tres planos**: encuadre jurídico + análisis ambiental + pendientes. Estructura clara y auditable.
3. **Tabla de impactos con significancias before/after**: reproducida de Bloque C sin recalcular. Correcto.
4. **IMP-08 correctamente separado**: fuera de la escala nuclear EIA, etiquetado como condicionante transversal PRL. Correcto.
5. **Tabla de pendientes con criticidad**: incluía GAP-001, GAP-002, GAP-003, GAP-INV-001, GAP-INV-002, etc. con sus criticidades. Buen modelo.
6. **Delegación explícita final**: "esta determinación corresponde en exclusiva al órgano ambiental competente en virtud del art. 47 de la Ley 21/2013." Correcto.

### Riesgos de deriva detectados en el piloto (a corregir en siguiente expediente)

1. **"el balance ambiental neto es positivo"** (I.4.4 del piloto): frase que aparece en la valoración global del promotor. El piloto usó esta formulación combinando impactos negativos de bajo rango con impactos positivos para llegar a un "balance positivo". Esto va más allá de lo que Conesa soporta y tiene sabor comercial. **PROHIBIDA en futuras versiones.**

2. **"el proyecto no debería requerir someterse a evaluación de impacto ambiental ordinaria"** (I.4 del piloto): aunque terminaba con la delegación al órgano, la frase "no debería requerir" anticipa la resolución. **PROHIBIDA en futuras versiones.**

3. **"Sin afección directa significativa"** en el encabezado de la sección I.3.1: usa el término "significativa" en lugar del legalmente correcto "apreciable". **Error terminológico a corregir.**

4. **"Vectores indirectos despreciables a esa escala"** en la tabla I.3.1: palabra "despreciables" es cuantitativa sin modelización. **Prohibida; sustituir por formulación de Bloque H con qualifier de gabinete.**

5. **Ausencia del qualifier de modo en la tabla I.3.1** para ENP: "Sin afección directa" en la celda "Resultado" sin el qualifier "según análisis en modo gabinete". Debe siempre llevar qualifier.

### Qué debe blindarse para el siguiente expediente

- La nota de rol de apertura: no puede reducirse, no puede eliminarse.
- La tabla de pendientes I.5: no puede quedar vacía si hay gaps activos de criticidad ALTA.
- La tabla de impactos I.3.2: debe ser reproducción fiel de Bloque C, no reinterpretación.
- La conclusión H.4 en I.3.5: debe tener sus tres partes con qualifiers — no puede simplificarse a "no afecta".
- La frase de cierre de la valoración global: el promotor somete, no concluye la viabilidad.

---

*Especificación redactada en P2 — 2026-04-16*
