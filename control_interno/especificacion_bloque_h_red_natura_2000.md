# Especificación técnica — AG-10 / Bloque H: Red Natura 2000
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Qué es un Bloque H válido en este sistema

El Bloque H es el análisis de posible afección a la Red Natura 2000, exigido por el Anexo VI y el Anexo III (criterios de significatividad) de la Ley 21/2013, en relación con el art. 46 de la Ley 42/2007 de patrimonio natural y biodiversidad (y su modificación por Ley 33/2015) y el art. 6 de la Directiva Hábitats 92/43/CEE.

El Bloque H tiene un doble cometido:

1. **Técnico**: analizar si el proyecto puede generar afección sobre los espacios Natura 2000, directa o indirectamente, a través de los vectores plausibles de transmisión.
2. **Jurídico**: documentar que se ha realizado el análisis exigido por la normativa, con las limitaciones del análisis explícitamente declaradas, de forma que el órgano ambiental pueda valorar la suficiencia del análisis y, en su caso, requerir información adicional.

Un Bloque H es válido si:

1. **Usa el estándar jurídico correcto**: el concepto es "afección apreciable" (art. 6 Directiva Hábitats / art. 46 Ley 42/2007). No "significativa", no "notable", no "relevante". La conclusión siempre es sobre si "se aprecia o no afección apreciable" — esa es la terminología del umbral legal.
2. **Diferencia niveles de certeza**: la localización fuera de los espacios es un hecho verificable cartográficamente (CONFIRMADO gabinete). La ausencia de afección indirecta es una inferencia técnica (INFERIDO) basada en análisis de vectores sin modelización ni campo.
3. **No invade el papel del órgano ambiental**: la conclusión del DA es que "no se aprecia afección apreciable según el análisis realizado". La resolución definitiva sobre si existe o no afección apreciable que active la Evaluación de Repercusiones sobre la Red Natura 2000 corresponde al órgano ambiental.
4. **Mantiene coherencia con Bloque B y Bloque J**: las distancias, los espacios, las limitaciones del análisis y el nivel de certeza declarados en H.2 son consistentes con lo que se dijo en B.10-B.11 y con el nivel de prudencia mantenido en J.7.
5. **Analiza los tres vectores de afección indirecta** siempre que la distancia no descarte por completo la posibilidad de transmisión: dispersión de partículas / contaminantes, drenaje / vectores hídricos, fauna móvil y conectividad ecológica.
6. **Declara las limitaciones del análisis en modo gabinete**: ausencia de modelización de dispersión, ausencia de análisis GIS con geometrías oficiales, ausencia de prospección de campo.

Lo que el Bloque H **no es**:
- No es el lugar donde el DA "cierra" la cuestión Natura 2000
- No puede decir "el proyecto no afecta a Natura 2000" — eso lo resuelve el órgano ambiental
- No puede usar distancia como prueba absoluta de ausencia de afección
- No puede usar contexto industrial como prueba de ausencia de riesgo sobre fauna protegida
- No puede ser más concluyente que los mapas MAP-004/MAP-005 de AG-06 y las fichas AG-08

---

## §2. El estándar jurídico: "afección apreciable"

### 2.1 Por qué esta terminología es no negociable

El umbral de la Directiva Hábitats y de la Ley 42/2007 para activar la Evaluación de Repercusiones (ER) es la "afección apreciable" sobre los objetivos de conservación del espacio. Este umbral es intencionalmente bajo — la ER se activa ante la mera posibilidad de afección apreciable, no ante la certeza de afección significativa.

Usar "significativa" en lugar de "apreciable" cambia el umbral legalmente relevante. Si el bloque dice "no hay afección significativa" cuando la norma pregunta por "afección apreciable", el análisis puede ser cuestionado por no haber evaluado el umbral correcto.

### 2.2 Terminología obligatoria en las conclusiones

| Concepto jurídico | Formulación correcta en el Bloque H |
|-------------------|-------------------------------------|
| No se supera el umbral de afección apreciable | "No se aprecia afección apreciable, directa ni indirecta, sobre los espacios Natura 2000 [XXX], según el análisis realizado en modo gabinete" |
| Incertidumbre residual | "No obstante, el análisis presenta las limitaciones propias del modo gabinete, por lo que no puede descartarse que el órgano ambiental requiera información adicional" |
| Fuera del espacio | "El proyecto no se ubica en el interior ni en el área de influencia inmediata de ningún espacio Natura 2000 [según la cartografía consultada]" |

Formulaciones **prohibidas** en las conclusiones:

| Formulación prohibida | Por qué |
|-----------------------|---------|
| "El proyecto no afecta a Natura 2000" | Conclusión que corresponde al órgano ambiental |
| "No hay riesgo de afección" | Elimina la incertidumbre que existe en todo análisis de gabinete |
| "Se descarta afección significativa" | Usa el umbral equivocado ("significativa" vs "apreciable") |
| "La distancia garantiza la ausencia de afección" | La distancia no es prueba jurídica suficiente |
| "El entorno industrial descarta presencia de fauna protegida" | Contexto industrial ≠ ausencia de fauna protegida (ver Bloque B, Regla B-3) |
| "La afección es despreciable" | Adjetivo que supera lo que el análisis de gabinete puede demostrar |
| "No se prevé afección" sin qualifier | Formulación sin limitación epistémica visible |

---

## §3. Relaciones con AG-06, AG-08, Bloque B y Bloque J

### 3.1 AG-06 → Bloque H

AG-06 generó los mapas WMS de ENP (MAP-005) y Natura 2000 (MAP-004). Estos mapas son la fuente primaria de la relación espacial entre el proyecto y los espacios. El Bloque H referencia exactamente los mapas que AG-06 generó — no inventa datos cartográficos ni usa fuentes no registradas en `cartografia_trace.json`.

Las distancias estimadas en Bloque H deben ser coherentes con lo que se dice en Bloque B (B.10, B.11). Si Bloque B dijo ">12 km al ENP más próximo" y ">15 km al Natura 2000 más próximo", el Bloque H usa los mismos valores — con el mismo qualifier "estimada".

Si AG-06 registró que la cuantificación exacta de distancias está pendiente de análisis GIS con geometrías oficiales del MITECO, el Bloque H lo declara explícitamente.

### 3.2 AG-08 → Bloque H

Las fichas de inventario AG-08 para FI-09 (ENP) y FI-10 (Natura 2000) determinan el nivel de certeza del análisis espacial. Si esas fichas tienen semáforo CONFIRMADO_GABINETE, el Bloque H puede usar ese nivel. Si tienen LIMITADO_ESCALA o INFERIDO_TECNICO, el Bloque H debe reflejar esa limitación.

Las fichas de flora (FI-07) y fauna (FI-08) condicionan el análisis del vector de afección sobre fauna móvil. Si FI-08 tiene semáforo PENDIENTE_VERIFICACION (sin prospección de campo), el análisis del vector de fauna en H.3.3 no puede concluir con certeza — solo con INFERIDO y las limitaciones explícitas.

### 3.3 Bloque B ↔ Bloque H (coherencia obligatoria)

El Bloque B (B.10 ENP, B.11 Natura 2000) hizo declaraciones sobre la relación espacial entre el proyecto y los espacios protegidos. El Bloque H no puede contradecir esas declaraciones ni ser más concluyente sobre ellas.

**Verificación de coherencia**: antes de redactar H.2, releer B.10 y B.11. Las distancias estimadas, los espacios catalogados, y el nivel de certeza ("CONFIRMADO gabinete, no superposición directa; cuantificación exacta pendiente") deben ser idénticos o coherentes.

### 3.4 Bloque H ↔ Bloque J (paridad de certeza, OBS-002)

El Bloque J (RNT, J.7) debe mantener el mismo nivel de certeza que el Bloque H. La regla J-7 del prompt bloque_J dice que el RNT debe conservar los cinco elementos del análisis Natura 2000: 1) espacios listados, 2) distancia con qualifier, 3) vectores analizados, 4) conclusión prudente, 5) limitaciones visibles.

Si el Bloque H dice "no se aprecia afección apreciable según análisis gabinete" y el Bloque J dice simplemente "no hay afección a Natura 2000", se ha producido el patrón OBS-002 (elevación de certeza al trasladar al RNT). El Bloque H es la referencia; el Bloque J no puede superarla en categoricidad.

---

## §4. Cómo tratar la noción de "afección apreciable"

### 4.1 La afección apreciable no es solo la directa

El error más común es reducir el análisis a "el proyecto no está dentro del espacio → no hay afección". La Directiva Hábitats y la jurisprudencia del TJUE son claras: la afección puede producirse a distancia, a través de vectores indirectos, sobre los objetivos de conservación del espacio (hábitats y especies para los que fue designado), aunque el proyecto esté fuera del perímetro.

Los tres vectores mínimos a analizar:
1. **Dispersión de contaminantes**: partículas, emisiones atmosféricas, contaminantes en agua
2. **Vectores hídricos**: conexión de la red de drenaje del proyecto con cuencas que alcanzan el espacio
3. **Fauna móvil y conectividad ecológica**: si el espacio alberga fauna con áreas de campeo que pueden incluir el entorno del proyecto

Para cada vector: describir el mecanismo potencial, evaluar su intensidad a la distancia real, y concluir con el nivel de certeza correcto.

### 4.2 La distancia como factor atenuante, no como prueba

La distancia es relevante para evaluar la plausibilidad de los vectores, pero no es por sí sola prueba de ausencia de afección apreciable. La formulación correcta:

> "La distancia estimada de [X] km al espacio más próximo reduce significativamente la probabilidad de que los vectores identificados generen afección apreciable a esa escala, especialmente con las medidas de control previstas. Sin embargo, esta evaluación está basada en un análisis de gabinete sin modelización de [dispersión / drenaje / campeo] y sin datos de campo."

Lo que no puede decirse: "la distancia de X km garantiza que no hay afección" ni "a X km es imposible que haya afección".

### 4.3 El contexto industrial no descarta fauna protegida

El contexto de polígono industrial reduce la probabilidad de presencia de fauna protegida en el entorno inmediato. No la elimina. Algunas especies protegidas tienen altas capacidades de adaptación a entornos periurbanos o industriales. El análisis de fauna debe basarse en las fichas AG-08 y en los datos disponibles, no en la inferencia de que "el polígono industrial no puede albergar fauna protegida".

---

## §5. Cómo redactar cada componente del Bloque H

### 5.1 Tabla de espacios Natura 2000 (H.1)

Lista de espacios en el ámbito geográfico del proyecto. Para Canarias: espacios LIC/ZEC y ZEPA por isla. Para la Península: los espacios en la provincia o comunidad autónoma relevante, filtrados por los que tienen relevancia geográfica potencial.

Obligatorio:
- Código europeo (ES + número)
- Denominación oficial
- Tipo (LIC, ZEC, ZEPA)
- Localización relativa al proyecto (dirección y posición general)
- Fuente: MITECO + MAP-XXX

### 5.2 Relación espacial (H.2)

Dos elementos distintos con estados de evidencia separados:

**A. No superposición directa** (generalmente CONFIRMADO_GABINETE si la cartografía WMS es clara):
> "El proyecto no se ubica en el interior de ningún espacio Natura 2000 de [ámbito], según la cartografía consultada (MAP-XXX)."

**B. Distancias al espacio más próximo** (siempre ESTIMADO salvo análisis GIS con geometrías oficiales):
> "La distancia estimada al espacio más próximo ([código]) es de aproximadamente [X] km, según lectura visual de los mapas [MAP-XXX]. Esta estimación no ha sido cuantificada mediante análisis GIS con las geometrías oficiales del MITECO."

La nota sobre la pendencia del análisis GIS es obligatoria siempre que las distancias sean estimadas visualmente. No se puede omitir aunque la distancia parezca suficiente.

### 5.3 Vectores de afección indirecta (H.3)

Cada vector debe tener:
1. Descripción del mecanismo potencial de transmisión de la afección
2. Evaluación de la intensidad a la distancia real (con datos de AG-07 si aplica para dispersión)
3. Referencia a las medidas del expediente que reducen el vector (si aplica)
4. Conclusión con estado INFERIDO y limitaciones explícitas

**Para el vector de dispersión de partículas**: si AG-07 tiene datos de viento (dirección dominante, velocidad, días de rachas), usarlos para identificar la dirección preferente de dispersión y qué espacios están en esa dirección. No hacer afirmaciones cuantitativas sobre concentraciones si no hay modelización.

**Para el vector de drenaje**: si no hay análisis de cuenca ni trazado de la red de drenaje (situación habitual en modo gabinete), declarar explícitamente que la conexión entre la red de drenaje del proyecto y posibles receptores naturales no ha sido trazada en detalle.

**Para el vector de fauna móvil**: si FI-08 tiene semáforo PENDIENTE_VERIFICACION (sin prospección de campo), el análisis se hace con las fuentes disponibles (bases de datos de distribución, contexto territorial) y la conclusión debe reflejar esa limitación.

### 5.4 Conclusión (H.4)

La conclusión del Bloque H tiene una estructura de tres partes:

**Parte 1 — Localización** (hecho):
> "El proyecto no se ubica en el interior ni en el área de influencia inmediata de ningún espacio Red Natura 2000 de [ámbito]."

**Parte 2 — Análisis de vectores** (inferencia):
> "Los vectores de afección indirecta analizados ([dispersión, drenaje, fauna]) no presentan, según el análisis realizado en modo gabinete, mecanismos de transmisión con intensidad suficiente para generar afección apreciable en los espacios Natura 2000 de [ámbito] a la escala de distancia involucrada."

**Parte 3 — Limitación explícita y remisión al órgano ambiental**:
> "No obstante, el presente análisis está basado en fuentes de gabinete sin modelización de dispersión ni análisis GIS con geometrías oficiales del MITECO. El órgano ambiental podrá requerir información adicional si lo considera necesario para la valoración de la suficiencia del análisis."

Las tres partes son obligatorias. La conclusión no puede limitarse a la Parte 1.

---

## §6. Diferencia modo test vs expediente real

| Aspecto | Modo TEST | Expediente REAL |
|---------|-----------|-----------------|
| Distancias estimadas visualmente | Aceptadas con qualifier | Verificar con análisis GIS + geometrías MITECO |
| FI-08 sin prospección de campo | Análisis de fauna con INFERIDO y limitación visible | Prospección de campo y/o consulta bases de datos de biodiversidad |
| Drenaje sin anejo técnico | Análisis hidrológico cualitativo con limitación visible | Trazado de red de drenaje y destino de efluentes |
| Tabla de espacios sin verificación de objetivos de conservación | Aceptable con referencia a ficha MITECO | Consultar ficha oficial del espacio en MITECO para verificar hábitats y especies objeto de conservación |
| Nota de art. 7.2.b) Ley 21/2013 | Obligatoria si aplica al encuadre | Ídem |

En modo TEST, el gate 7 (bloque H) se considera satisfecho si:
- Los espacios Natura 2000 del ámbito están catalogados en H.1
- H.2 tiene la nota sobre estimación de distancias y pendencia GIS
- Los tres vectores están analizados en H.3
- La conclusión H.4 tiene las tres partes: localización + vectores + limitación
- Ninguna formulación dice "no hay afección", "no hay riesgo" o "la distancia garantiza..."

---

## §7. Estructura mínima obligatoria

```markdown
# BLOQUE H — Análisis de afección a la Red Natura 2000

## H.1. Espacios Natura 2000 de referencia en [ámbito geográfico]
[Tabla: código / denominación / tipo / localización relativa / fuente MAP-XXX]

## H.2. Relación espacial entre el proyecto y los espacios Natura 2000
[No superposición directa — CONFIRMADO gabinete]
[Tabla de distancias estimadas — ESTIMADO con nota de pendencia GIS]

## H.3. Evaluación de la posible afección indirecta
### H.3.1. [Vector 1 — dispersión de partículas / contaminantes]
[Mecanismo + evaluación + medidas reductoras + conclusión INFERIDO con limitaciones]

### H.3.2. [Vector 2 — drenaje / vectores hídricos]
[Mecanismo + evaluación + medidas reductoras + conclusión INFERIDO con limitaciones]

### H.3.3. [Vector 3 — fauna móvil y conectividad ecológica]
[Mecanismo + evaluación + limitaciones FI-08 si aplica + conclusión INFERIDO con limitaciones]

## H.4. Conclusión del análisis de afección a Red Natura 2000
[Parte 1: localización] + [Parte 2: análisis de vectores] + [Parte 3: limitación + remisión al órgano ambiental]
[Nota art. 7.2.b) Ley 21/2013 si aplica al tipo de encuadre del expediente]
```

Si el proyecto está a menos de 5 km de un espacio Natura 2000, o si el espacio alberga hábitats o especies que pueden ser sensibles a los vectores de la actividad: añadir sección H.5 con análisis específico de los hábitats y especies objeto de conservación del espacio afectado.

---

## §8. Lecciones del piloto Recimetal

### L-01: Lo que funcionó bien y se codifica como obligatorio

**Nota sobre estimación de distancias en H.2**: texto explícito que dice que las distancias son estimaciones por lectura visual de mapas, no análisis GIS con geometrías exactas. Declara que se recomienda la cuantificación exacta en el expediente real. Patrón obligatorio.

**Estado INFERIDO en cada conclusión de vector** con descripción de las limitaciones específicas. No hay una sola conclusión del bloque que diga simplemente "no hay afección" — todas van acompañadas de "[Estado: INFERIDO — sin modelización / sin análisis hidrológico de cuenca / sin prospección de campo]". Patrón obligatorio.

**Nota art. 7.2.b) Ley 21/2013 al final de H.4**: precisa la vía de sujeción aplicable al expediente y explica por qué el análisis de Natura 2000 sigue siendo exigible aunque el proyecto esté encuadrado por Anexo II. Correcta. Patrón a mantener.

**Estructura de tres vectores**: dispersión de partículas (conectando con IMP-01 y datos de AG-07), drenaje (conectando con IMP-03 y GAP-002), fauna móvil (conectando con FI-08 y la ausencia de campo). Cada vector conecta explícitamente con los datos del inventario y los impactos identificados. Patrón correcto.

### L-02: Riesgos de deriva identificados en el piloto y correcciones en v2.1

**"indetectable" en H.3.1**: "la concentración de PM10 de origen metálico en el entorno de Los Ajaches es, en términos prácticos, indetectable" — afirmación cuantitativa sin modelización. En v2.1: "no se aprecia un mecanismo de afección apreciable por dispersión de partículas a la escala de distancia involucrada, según el análisis de gabinete y sin modelización de dispersión."

**"órdenes de magnitud superior" por calima en H.3.1**: uso de la comparación con la calima como argumento de minimización de la emisión del proyecto. En v2.1: la calima es contexto que informa la línea base de PM10; no es argumento para reducir la obligación de control de emisiones propias ni para suavizar la valoración del vector de dispersión.

**"intensidad despreciable" en H.4.2**: adjetivo que supera lo que el análisis de gabinete puede demostrar. En v2.1: "intensidad muy reducida a esa escala" + limitación explícita.

**"afección indirecta significativa" en H.3.3**: usa el umbral equivocado. En v2.1: siempre "afección apreciable" — la terminología del art. 6 de la Directiva Hábitats y del art. 46 de la Ley 42/2007.

**"La actividad es compatible con el contexto industrial preexistente" en H.3.3**: aplica el argumento de contexto industrial como prueba de ausencia de riesgo sobre fauna. En v2.1: el contexto industrial es un factor que reduce la probabilidad pero no elimina la obligación de análisis. Reformular: "El contexto de polígono industrial reduce la probabilidad de presencia de fauna protegida en el entorno inmediato, pero no puede descartarse formalmente sin prospección de campo (GAP-INV-001)."

### L-03: Coherencia entre bloques (lección estructural)

El piloto Recimetal no tuvo incidencia OBS-002 en bloque_H → bloque_J porque el bloque_J fue escrito con conciencia de esta regla. En expedientes futuros, el riesgo es que bloque_H se redacte correctamente (con todos los qualifiers) y bloque_J después los elimine al hacer el resumen. El blindaje es el autochequeo del prompt bloque_J que exige leer literalmente H.4 antes de escribir J.7.
