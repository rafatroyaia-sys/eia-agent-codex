# Especificación metodológica — AG-10 / Bloque F
## Análisis de Alternativas

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque F válido en este sistema

El Bloque F es el análisis de las principales alternativas consideradas y la justificación de la elección efectuada (art. 45 Ley 21/2013, Anexo VI). Tiene un propósito específico y acotado: documentar qué opciones se compararon y por qué se eligió la que se eligió, con criterios ambientales visibles.

Un Bloque F válido cumple cinco condiciones:

1. **Honesto sobre su fuente**: distingue explícitamente entre alternativas que el promotor ha presentado y analizado formalmente, y alternativas que el redactor ha reconstruido metodológicamente para cumplir el mínimo del Anexo VI. Las reconstruidas llevan estado INFERIDO. Las del promotor llevan DECLARADO o CONFIRMADO según la evidencia.

2. **Ambiental en su análisis**: la comparación entre alternativas se hace en términos de efectos ambientales — no de viabilidad económica o conveniencia operativa del promotor. Los factores económicos y técnicos pueden aparecer como contexto, pero no como sustituto del análisis ambiental.

3. **Proporcional a la escala del proyecto**: el nivel de detalle del análisis de alternativas es proporcional a la naturaleza del proyecto. Un pequeño proyecto en polígono industrial sin sustancias peligrosas no requiere el mismo nivel de análisis que una gran infraestructura en entorno sensible. La proporcionalidad se declara explícitamente en F.1.

4. **No circular en su justificación**: la alternativa elegida no puede justificarse solo por cumplir los objetivos del promotor. La justificación ambiental debe explicar por qué esta opción es ambientalmente preferible (o no peor) que las alternativas evaluadas.

5. **Transparente sobre las limitaciones del análisis**: si el promotor no ha aportado análisis formal de alternativas, se declara. Si el análisis de alternativas se basa en inferencias del redactor, se marca. El análisis de alternativas más honesto que puede hacer el sistema cuando el expediente es escaso es: declarar lo que no se analizó y reconstruir lo que puede inferirse, con los marcadores de estado correctos.

---

## §2. Relación AG-04 / AG-06 / AG-08 → Bloque F

El Bloque F no genera datos propios. Los toma de:

| Fuente | Qué aporta al Bloque F |
|--------|------------------------|
| `capas/hechos_confirmados.json` + ficha AG-04 | Qué es exactamente el proyecto evaluado: operaciones, equipos, exclusiones, dependencias funcionales. Determina qué es alternativa de diseño real vs variante menor. |
| `capas/hechos_confirmados.json` — campo "alternativas_analizadas" (si existe) | Qué alternativas ha presentado formalmente el promotor. Si este campo está vacío o ausente, el promotor no ha presentado análisis formal de alternativas. |
| `capas/cartografia_trace.json` + AG-06 | Contexto espacial del emplazamiento: uso del suelo en el entorno, distancias a espacios sensibles, disponibilidad de suelo alternativo en la zona. Sirve para contextualizar las alternativas de emplazamiento. |
| `fichas_inventario/` (AG-08) | Estado ambiental de referencia (Alternativa 0): cuál es la situación sin proyecto. Los factores ambientales caracterizados por AG-08 son el punto de partida para evaluar qué cambiaría si el proyecto no se ejecuta. |
| `impactos/identificacion_valoracion_impactos.json` (AG-09) | Significancias de los impactos del proyecto elegido — útiles para contrastar con las alternativas descartadas cuando se puedan estimar. |

**Regla de acceso**: antes de redactar F.3 (emplazamiento), leer la ficha AG-04 completa para conocer las dependencias funcionales que restringen el emplazamiento. Antes de redactar F.2 (Alternativa 0), leer las fichas de AG-08 para saber cuál es el estado ambiental de la parcela sin proyecto.

**Qué NO aporta al Bloque F**:
- AG-09 no proporciona significancias para alternativas no elegidas salvo que las haya calculado explícitamente. No se puede afirmar que "la alternativa X hubiera producido impactos Moderados" sin base en AG-09.
- AG-07 no proporciona bases para comparar emplazamientos alternativos que no estén en el expediente.

---

## §3. Tipos de alternativas: cómo tratar cada una

### §3.1. Alternativa 0 — No actuación

La alternativa 0 es el escenario de no ejecución del proyecto. Su análisis debe responder a una pregunta ambiental concreta: **¿qué ocurre con el medio si el proyecto no se ejecuta?**

El análisis correcto de la alternativa 0 describe:
1. El estado actual del ámbito sin proyecto (derivado de AG-08): uso actual del suelo, estado de la parcela, actividades presentes.
2. Qué no ocurriría si el proyecto no se ejecuta: los impactos negativos identificados en Bloque C no se producirían; los impactos positivos tampoco.
3. Si la no ejecución tiene consecuencias ambientales propias (ej: un solar sin uso que podría convertirse en vertedero informal, una necesidad de gestión de residuos no cubierta), esas consecuencias se describen con sus propios estados de evidencia.

**Lo que la alternativa 0 NO es**:
- Un argumentario del promotor sobre los beneficios perdidos.
- Una suma de impactos evitados presentada como argumento para ejecutar el proyecto.
- Una frase vacía del tipo "la no actuación no contribuye a los objetivos de la política de residuos".

La alternativa 0 puede concluir que es ambientalmente peor, equivalente o mejor que el proyecto propuesto, según los datos. No hay una respuesta obligatoria. La conclusión lleva su estado de evidencia.

**Formulación correcta de la conclusión de la Alternativa 0**:
> "La alternativa 0 implica el mantenimiento de la parcela en su estado actual [descripción del estado actual]. Ambientalmente, la no ejecución evitaría los impactos identificados en el análisis (IMP-01 a IMP-XX), todos de significancia [Y]. Dado el bajo nivel de impactos residuales con las medidas propuestas, la diferencia ambiental entre la alternativa 0 y el proyecto propuesto es [pequeña / moderada / significativa — con razón]. [Estado: ESTIMADO / INFERIDO según la base disponible]"

**Formulación incorrecta**:
> "La alternativa 0 no es ambientalmente preferible al proyecto propuesto, dado el balance neto positivo del reciclaje de metales respecto a la extracción de materias primas vírgenes."

Por qué es incorrecta: introduce un argumento de política de residuos (valorización vs extracción primaria) que no es un análisis de los efectos ambientales del proyecto en su emplazamiento concreto. Ese argumento puede aparecer en Bloque A (descripción del proyecto y su contexto sectorial) o en Bloque I (conclusiones del promotor) si el promotor lo aporta, pero no es el análisis ambiental de la Alternativa 0.

---

### §3.2. Alternativas de emplazamiento

Las alternativas de emplazamiento responden a la pregunta: ¿podría el proyecto haberse ubicado en otro lugar con efectos ambientales diferentes?

**Cuando el promotor ha analizado formalmente emplazamientos alternativos** (consta en HC del expediente):
- Describir los emplazamientos comparados con sus características relevantes para el análisis ambiental (distancia a espacios sensibles, uso del suelo, estado ambiental previo).
- Presentar los criterios de comparación y la razón de la elección.
- Estado de evidencia: CONFIRMADO o DECLARADO según la calidad de la documentación.

**Cuando el promotor NO ha analizado formalmente emplazamientos alternativos** (caso más común en proyectos pequeños):
- Declarar explícitamente que no constan en la documentación del expediente análisis de emplazamientos alternativos.
- Identificar las restricciones que determinan el emplazamiento: dependencias funcionales, disponibilidad de suelo, condicionantes normativos. Estas restricciones son el contexto que explica por qué el análisis de emplazamientos alternativos es reducido o inexistente.
- Si las restricciones son verificables (ej: dependencia funcional documentada en HC), llevan estado CONFIRMADO o DECLARADO.
- Si se reconstruye una comparación metodológica (ej: "en el polígono existen otros solares, pero carecerían de la dependencia funcional necesaria"), llevar estado INFERIDO con nota explícita de que es reconstrucción metodológica.

**Formulación correcta cuando no hay análisis formal**:
> "El promotor no ha aportado en la documentación del expediente un análisis formal de emplazamientos alternativos. La elección del emplazamiento está determinada por las siguientes restricciones verificadas: [lista de restricciones con estado]. Desde el punto de vista ambiental, el emplazamiento en el Polígono Industrial de [X] presenta las siguientes características relevantes: [distancia a espacios sensibles, uso del suelo industrial preexistente, etc.]. [Estado general de la sección: DECLARADO]"

**Restricciones de hecho ≠ bondades ambientales**:
"La parcela es contigua a las naves vinculadas, lo que hace inviable otro emplazamiento" es una restricción factual, no una justificación ambiental. La justificación ambiental del emplazamiento en el polígono sería: "La ubicación en suelo industrial ya consolidado evita la transformación de suelo virgen y reduce la fragmentación de hábitats naturales respecto a una hipotética ubicación alternativa en zona no industrial." Estas son afirmaciones ambientales que deben ir con su estado de evidencia.

---

### §3.3. Alternativas de diseño o implantación

Las alternativas de diseño responden a la pregunta: ¿podría el proyecto haberse configurado de forma diferente con efectos ambientales distintos?

**Cuando el promotor ha presentado alternativas de diseño** (constan en HC): describir con referencia a las diferencias de impacto ambiental, referenciando los IMPs de AG-09 cuando sea posible.

**Cuando el redactor reconstruye alternativas de diseño** desde la descripción del proyecto:
- Marcar cada alternativa reconstruida como INFERIDO con la nota: "Esta alternativa no figura formalmente en la documentación del expediente. Se presenta como reconstrucción metodológica a partir de la descripción del proyecto para cumplir el contenido mínimo del Anexo VI Ley 21/2013."
- La reconstrucción es legítima cuando existen razones técnicas documentadas que justifican la exclusión de una configuración alternativa (ej: exclusión de operaciones R1203 documentada en HC).
- No es legítima cuando el redactor inventa configuraciones alternativas sin ninguna base en el expediente.

**Variante ≠ alternativa autónoma**:
Una variante menor (cambiar el tamaño de un contenedor, usar un tipo diferente de vallado) no es una alternativa de diseño en el sentido del Anexo VI. Solo se presenta como alternativa si la diferencia de configuración produce efectos ambientales distintos verificables. Si se presenta una variante como si fuera alternativa, se añade una nota: "Se presenta esta variante de diseño como alternativa de análisis porque produce diferencias en [IMP-XX] según [razón]."

---

### §3.4. Alternativas operativas o tecnológicas

Las alternativas operativas responden a la pregunta: ¿podría el proyecto haber usado una tecnología o proceso distinto con efectos ambientales diferentes?

Aplica el mismo esquema que §3.3: alternativas formalmente presentadas vs reconstruidas metodológicamente, con marcadores de estado. El análisis compara las diferencias de impacto esperadas con referencia a los IMPs del bloque C.

---

## §4. Qué hacer cuando el expediente no aporta alternativas reales

La situación más común en proyectos de EIA simplificada es que el promotor presenta un único proyecto sin análisis formal de alternativas. En este caso, el Bloque F:

1. **Declara explícitamente la ausencia de análisis formal** en la cautela metodológica de F.1 y en cada sección que corresponda.

2. **Analiza la Alternativa 0** de todas formas — esta es obligatoria con independencia de lo que aporte el promotor.

3. **Reconstruye metodológicamente las alternativas principales** desde la descripción del proyecto, las exclusiones documentadas y las restricciones identificadas, marcando todo como INFERIDO.

4. **No inventa alternativas sin base documental**. Si no hay ninguna pista sobre alternativas de emplazamiento en el expediente, la sección dice: "El promotor no ha presentado alternativas de emplazamiento. Las restricciones que determinan el emplazamiento actual son: [X, Y, Z — con estado]. No se dispone de información suficiente para reconstruir una comparación de emplazamientos alternativos. [GAP-ALT-001]" — no se rellena la sección con texto genérico.

5. **No fuerza una calificación global**. Si el análisis es escaso porque el promotor no ha aportado información, la justificación de la alternativa elegida (F.5) refleja esta escasez: "La justificación de la solución adoptada se basa en la documentación del expediente, que no incluye análisis formal de alternativas. Los elementos disponibles que orientan la elección son: [lista]." No se añade una valoración global que el análisis no sustenta.

---

## §5. Cómo diferenciar: analizada / inferida / variante

| Tipo | Definición | Marcador obligatorio | Fuente |
|------|------------|----------------------|--------|
| **Alternativa analizada** | Figura explícitamente en los documentos del promotor con descripción y razones de descarte o elección | DECLARADO o CONFIRMADO | HCs del expediente |
| **Alternativa reconstruida** | El redactor la deriva de la descripción del proyecto, exclusiones documentadas o restricciones verificadas | INFERIDO + nota explícita de reconstrucción | Razonamiento técnico basado en HCs |
| **Variante no constitutiva** | Cambio menor de un parámetro de diseño sin efectos ambientales verificablemente distintos | No se presenta como alternativa — se puede mencionar como "variante no analizada como alternativa independiente porque [razón]" | — |

---

## §6. Cómo debe justificarse la alternativa seleccionada

La justificación de la solución adoptada (F.5) sigue esta estructura:

1. **Criterios de evaluación**: qué dimensiones se compararon (ambiental, técnica, económica). Si solo se dispone de comparación ambiental, declararlo.

2. **Base comparativa**: con qué se compara la solución adoptada. Si solo hay Alternativa 0 y alternativas reconstruidas, la comparación es explícitamente limitada.

3. **Resultado de la comparación**: qué ventajas ambientales ofrece la solución adoptada respecto a las alternativas evaluadas, con referencia a los IMPs cuando sea posible.

4. **Qualifier de la conclusión**: si la comparación es INFERIDA (alternativas reconstruidas, no formalmente analizadas), la conclusión no puede ser más sólida que ESTIMADO.

**Formulación correcta**:
> "La solución adoptada se justifica ambientalmente respecto a las alternativas analizadas por las siguientes razones: [lista con referencias a impactos]. Esta justificación tiene estado [INFERIDO/DECLARADO] dado que [razón: alternativas reconstruidas / análisis formal del promotor limitado]. [Estado: INFERIDO / DECLARADO]"

**Formulación incorrecta**:
> "La solución adoptada es la que mejor equilibra proporcionalidad, viabilidad técnica y económica, minimización de impactos y compatibilidad con el encuadre jurídico." 

Por qué es incorrecta: cuatro criterios sin una tabla de comparación, sin datos que soporten el superlativo "mejor equilibra", sin referencia a qué alternativas se compararon.

---

## §7. Tratamiento de los límites del análisis

El Bloque F debe declarar explícitamente sus limitaciones metodológicas. La cautela metodológica de F.1 debe cubrir:

- Si el promotor no ha aportado análisis formal de alternativas: declararlo.
- Si el análisis es modo gabinete sin acceso a datos de campo sobre emplazamientos alternativos: declararlo.
- Si la comparación de impactos entre alternativas se basa en extrapolación técnica y no en cálculo de AG-09: declararlo con estado ESTIMADO.
- Si hay alternativas que no pueden analizarse por falta de información (ej: no hay datos sobre otros suelos disponibles en el polígono): declarar el gap como GAP-ALT-XXX.

**La cautela no es un descargo**: declarar las limitaciones no exime al bloque de analizar lo que sí puede analizarse. Declarar la limitación y luego hacer el análisis con lo disponible es la conducta correcta. Declarar la limitación y no hacer ningún análisis no es aceptable.

---

## §8. Modo test vs expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Análisis de Alternativa 0 | Basado en estado actual de la parcela según HC y AG-08 disponibles | Incluye visita de campo y caracterización directa del estado previo |
| Alternativas de emplazamiento | Reconstruidas desde HC + restricciones funcionales; sin análisis de suelo disponible en polígono | Incluye análisis de parcelas disponibles en el mismo polígono o entornos equivalentes, con datos catastrales y urbanísticos |
| Alternativas de diseño | Reconstruidas desde exclusiones documentadas en HC | Incluye comparación de opciones realmente consideradas por el promotor con documentación de respaldo |
| Comparación de impactos entre alternativas | Estimada por extrapolación técnica sin cálculo AG-09 para alternativas no elegidas | AG-09 puede ejecutarse en modo comparativo si el promotor ha aportado descripción suficiente de las alternativas |
| Justificación de la solución adoptada | ESTIMADO / INFERIDO | DECLARADO / CONFIRMADO si el promotor ha aportado análisis formal |

---

## §9. Estructura mínima obligatoria del Bloque F

```
F.1. Base normativa y alcance del análisis de alternativas
     — art. 45 Ley 21/2013 + Anexo VI
     — proporcionalidad al tipo y escala del proyecto
     — cautela metodológica (si el análisis es inferido/limitado)
     — declaración sobre si el promotor ha presentado análisis formal de alternativas

F.2. Alternativa 0 — No actuación
     — estado actual del ámbito sin proyecto (desde AG-08)
     — efectos ambientales que no ocurrirían (impactos evitados)
     — consecuencias propias de la no ejecución (si las hay)
     — conclusión con estado de evidencia

F.3. Alternativas de emplazamiento
     — si hay análisis formal: descripción + comparación ambiental + estado
     — si no hay: declaración explícita + restricciones que determinan el emplazamiento + estado
     — si hay reconstrucción metodológica: con marcador INFERIDO y nota

F.4. Alternativas de diseño e implantación
     — una subsección por tipo de alternativa de diseño evaluada
     — cada alternativa con: descripción, diferencia ambiental esperada, razón de descarte/elección, estado de evidencia
     — alternativas reconstruidas con marcador INFERIDO y nota explícita

F.5. Justificación de la solución adoptada
     — criterios de evaluación usados
     — tabla comparativa si hay múltiples alternativas formales (o nota de ausencia)
     — conclusión con qualifier proporcional a la solidez del análisis
     — estado de evidencia global del bloque
```

---

## §10. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien y debe protegerse

1. **Cautela metodológica en F.1**: el blockquote con la advertencia de modo test, la declaración de estado INFERIDO/DECLARADO del bloque y la indicación de que el promotor no aportó análisis formal de emplazamientos alternativos. Esta estructura es el elemento más valioso del bloque — sin ella, F.3 y F.4 habrían sonado más sólidos de lo que son.

2. **Exclusión de R1203 como decisión de diseño con razonamiento ambiental** (F.4.1): "La exclusión de R1203 es una decisión de diseño con beneficio ambiental directo: permite mantener todos los impactos en la escala Compatible / Compatible residual." Este es el modelo correcto de análisis de alternativa de diseño: decisión documentada en HC, razonamiento ambiental explícito, conexión con IMPs.

3. **Referencias a los IMPs en F.4**: conectar las alternativas de diseño con los impactos específicos (IMP-01, IMP-04) hace el bloque auditable por M-12.

4. **Marcadores de estado [Estado: INFERIDO] / [Estado: DECLARADO]** en las secciones clave.

5. **Análisis F.4.2 (instalación techada)**: la comparación cubierta vs descubierta con el argumento de implicaciones procedimentales es metodológicamente correcto y bien razonado — aunque hubiera que marcarlo más explícitamente como reconstrucción metodológica.

### Riesgos detectados en el piloto (a corregir en siguiente expediente)

1. **Alternativa 0 analizada como argumentario del proyecto**: la conclusión "La alternativa 0 no es ambientalmente preferible al proyecto propuesto, dado el balance neto positivo del reciclaje de metales respecto a la extracción de materias primas vírgenes" introduce un argumento de política sectorial de residuos, no un análisis de efectos ambientales en el emplazamiento. El análisis correcto de la Alternativa 0 para este proyecto sería: "El estado actual de la parcela es solera hormigonada sin uso activo declarado en el expediente. La no ejecución mantendría este estado sin los impactos negativos identificados (todos de escala Compatible o Compatible residual con medidas), pero tampoco generaría los impactos positivos (IMP-09, IMP-10)."

2. **Alternativas de diseño presentadas sin marcador de reconstrucción**: F.4.1, F.4.2 y F.4.3 describen alternativas de diseño como si hubieran sido "consideradas" y "descartadas" por el promotor, cuando en realidad son inferencias del sistema desde la descripción del proyecto y las exclusiones documentadas. Deben ir marcadas explícitamente como alternativas reconstruidas metodológicamente con estado INFERIDO.

3. **Justificación circular en F.5**: "La solución adoptada —[lista]— es la que mejor equilibra proporcionalidad [...] viabilidad técnica y económica para una PYME del sector del reciclaje [...]" usa el superlativo "mejor equilibra" sin tabla comparativa. Cuatro criterios nombrados sin datos que los sustenten. Corrección: F.5 debe tener una tabla de comparación o, si no hay base para compararla, declarar que la justificación es limitada porque no se dispone de análisis formal de alternativas.

4. **"garantiza una separación >12 km"**: uso de "garantiza" para una distancia calculada desde coordenadas declaradas (no verificadas cartográficamente en Fase 4 al momento de redactar). Corrección: "la ubicación presenta una separación estimada de >12 km respecto a los espacios Natura 2000 más próximos, según las coordenadas declaradas y la cartografía consultada."

5. **Restricción funcional convertida en ventaja ambiental sin transición**: "dependencia funcional → emplazamiento correcto" pasa por alto el paso intermedio: qué significa ambientalmente estar en el polígono industrial (ya impermeabilizado, ya sin hábitats, ya con impactos acumulativos existentes) vs en otro suelo hipotético. El argumento ambiental correcto no es la dependencia funcional — es la naturaleza del suelo ya industrializado.

---

*Especificación redactada en P2 — 2026-04-16*
