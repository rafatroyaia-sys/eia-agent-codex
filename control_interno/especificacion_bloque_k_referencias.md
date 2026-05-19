# Especificación metodológica — AG-10 / Bloque K
## Referencias normativas, documentales y técnicas

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque K válido en este sistema

El Bloque K es el índice trazable de todas las fuentes en que se apoya el Documento Ambiental. No es una lista bibliográfica decorativa ni una recopilación exhaustiva de normativa ambiental existente. Es la respuesta auditada a la pregunta: ¿de dónde viene cada dato que aparece en el DA?

Un Bloque K válido cumple cuatro condiciones:

1. **Derivado, no redactado de nuevo**: las normas de K.1 se copian de `normativa_aplicable.json` (AG-05), con su estado de evidencia. La cartografía de K.3 se copia de `cartografia_trace.json` (AG-06). Los datos climáticos de K.4 se copian de los archivos de AG-07. El Bloque K no genera datos nuevos — los transcribe desde las capas autorizadas del sistema.

2. **Con estado de verificación visible**: para cada fuente normativa, el estado VERIFICADA ONLINE / REFERENCIADA / PENDIENTE_VERIFICACION aparece en la tabla. Esta distinción ya existe en `normativa_aplicable.json` — el Bloque K no puede perderla al transcribirla.

3. **Sin fuentes inventadas o decorativas**: una referencia aparece en el Bloque K solo si algún agente del sistema la usó efectivamente. Las fuentes que el sistema "conoce" pero no consultó no aparecen — o aparecen con estado CITADA_CONTEXTO y con nota declarando que no fueron consultadas para este expediente.

4. **Auditable por M-12**: cada afirmación del DA debe poder trazarse hasta su fuente. K.8 (documentos internos del expediente) cierra este circuito: los outputs del sistema son las fuentes de los bloques redactados, y K.8 los lista con sus fases de generación.

---

## §2. Tipos de fuentes y su tratamiento

### §2.1. Normativa aplicable (K.1 + K.2)

**Fuente autoritativa**: `capas/normativa_aplicable.json` generado por AG-05.

El Bloque K no reescribe la normativa aplicable desde cero. Lee el JSON y transcribe cada entrada con sus campos en la tabla correspondiente. La adición de una norma al Bloque K que no esté en el JSON es una anomalía — se documenta como issue para AG-05 antes de continuar.

**Campos obligatorios en la tabla**: ID del JSON / Norma / Referencia BOE o BOC / Estado de verificación (del campo `estado` del JSON) / Relevancia en el expediente.

**Estado de verificación**: el campo `estado` del JSON tiene estos valores posibles:

| Estado en JSON | Significado | Representación en K.1/K.2 |
|---------------|-------------|---------------------------|
| `VERIFICADA ONLINE` | La norma fue consultada online; su texto y vigencia se verificaron | ✓ VERIFICADA — fecha de verificación |
| `REFERENCIADA` | La norma aparece en las fuentes del expediente pero no fue consultada directamente en texto completo | REFERENCIADA — texto no consultado directamente |
| `PENDIENTE_VERIFICACION` | La vigencia o contenido necesita verificación pendiente de completar | ⚠ PENDIENTE |

Esta distinción no puede desaparecer en la tabla del Bloque K. Una norma REFERENCIADA no puede presentarse con la misma columna que una norma VERIFICADA ONLINE.

**Normativa viva — tratamiento obligatorio**: las normas publicadas en BOE/BOC son documentos vivos. La versión verificada es la que consta en el campo `fecha_verificacion_online` del JSON. La tabla incluye esta fecha. El lector del DA sabe que la verificación se hizo en esa fecha y que modificaciones posteriores requieren nueva consulta.

Formulación estándar para normas vivas en el encabezado de K.1:
> "Las normas de esta tabla han sido verificadas en sus versiones vigentes a las fechas indicadas. La normativa publicada en BOE/BOC es de actualización continua; el promotor debe verificar la existencia de modificaciones posteriores a las fechas de consulta antes de la presentación definitiva del DA."

---

### §2.2. Documentación del promotor (K.2)

Los documentos aportados por el promotor son las fuentes de los hechos confirmados (HCs). Se listan con:
- ID del documento (DOC-001, DOC-002, etc.)
- Denominación exacta del archivo
- Autor o autores
- Fecha de redacción
- Estado en el expediente (PROCESADO = analizado por AG-01/02/03; CATALOGADO = identificado pero uso limitado)

**Documentos del promotor ≠ fuentes oficiales**: no se mezclan en la misma tabla. Los documentos del promotor son fuentes DECLARADAS — contienen la declaración del promotor. Las fuentes oficiales son verificación independiente.

---

### §2.3. Cartografía y geodatos (K.3)

**Fuente autoritativa**: `capas/cartografia_trace.json` generado por AG-06.

La tabla K.3 no se escribe de memoria — se extrae del JSON de trazabilidad cartográfica. Para cada mapa o capa:
- ID del producto cartográfico
- Recurso / tipo de capa
- Servicio WMS/WFS o fuente
- Escala o resolución
- Fecha de generación o consulta
- Estado (GENERADO, PENDIENTE, con notas de cautela)

La nota de trazabilidad al final de K.3 debe indicar explícitamente que la trazabilidad completa consta en `cartografia_trace.json`. No se duplica el detalle técnico en el Bloque K — se remite al JSON.

---

### §2.4. Datos climáticos (K.4)

Derivado de los outputs de AG-07:
- Estación AEMET: código, nombre, período de referencia
- Variables extraídas
- Archivos generados
- Si la estación no tiene datos completos para el período estándar: declararlo con estado ESTIMADO o LIMITADO

No se añaden en K.4 referencias climáticas que no hayan sido consultadas por AG-07 para este expediente.

---

### §2.5. Sistemas de información y bases de datos (K.5)

Los visores y APIs consultados efectivamente por AG-06 (cartografía) y AG-07 (clima). Para cada sistema:
- Denominación del sistema / visor / API
- Entidad responsable
- Consulta realizada (qué se buscó)
- URL base si es pública y estable

Las bases de datos que el sistema "conoce" pero no consultó para este expediente no aparecen en K.5.

---

### §2.6. Metodología técnica aplicada (K.6)

El sistema aplica metodologías de valoración de impactos (adaptación del método Conesa, escalas de significancia) que están codificadas en AG-09 y en `SYSTEM_BASE.md`. Estas metodologías tienen referencias bibliográficas de origen, pero el sistema no "consulta" las obras originales — aplica la metodología como la tiene implementada.

La distinción obligatoria:

| Tipo de referencia | Tratamiento correcto |
|--------------------|--------------------|
| Metodología aplicada cuya base bibliográfica es conocida | Citar la obra con la nota: "Metodología aplicada según adaptación del sistema. La obra de referencia es [cita completa]; el sistema aplica una versión simplificada proporcional a la EIA simplificada, no una implementación completa de la metodología original." |
| Obra bibliográfica que describe contexto técnico general | Solo incluir si fue efectivamente consultada para este expediente — no como referencia decorativa |
| Normativa que describe metodologías (ej: Guías de la CE) | Incluir en K.1/K.2 con estado de verificación; no en K.6 |

**Riesgo principal de K.6**: los LLMs generan referencias bibliográficas plausibles pero incorrectas (año equivocado, edición equivocada, editorial equivocada). Una referencia de bibliografía técnica en el Bloque K debe ser verificable exactamente o no aparecer.

Formulación estándar para metodología aplicada:
> "Conesa Fernández-Vítora, V. — Guía metodológica para la evaluación del impacto ambiental. [Obra de referencia — el sistema aplica una adaptación simplificada de esta metodología proporcional a la escala del proyecto, no la implementación completa de la obra original. La escala de significancia usada — Compatible residual / Compatible / Moderado / Severo / Crítico — está definida en `impactos/identificacion_valoracion_impactos.json`.]"

No se incluye en esta sección el año ni la editorial si no pueden verificarse para el expediente concreto. La metodología aplicada está trazada en el JSON de impactos — esa es la fuente auditable, no la referencia bibliográfica.

---

### §2.7. Documentos internos del expediente (K.7)

Los outputs generados por el sistema en las fases 2-6 son la fuente de los bloques redactados en la Fase 7. Listarlos en K.7 con:
- Nombre del archivo
- Fase que lo generó
- Descripción breve de su contenido
- Si hay versión actualizada o archivada: solo la versión final

K.7 es la sección que permite a M-12 verificar que los bloques del DA tienen fuente trazable en los outputs de las fases anteriores.

---

## §3. Diferencia entre fuente consultada y fuente citada

| Tipo | Definición | Estado en el bloque |
|------|------------|---------------------|
| **Fuente consultada** | Un agente del sistema leyó, extrajo datos o verificó su contenido en este expediente | VERIFICADA ONLINE (normativa) / CONSULTADA (otros tipos) |
| **Fuente referenciada** | Aparece en los documentos del promotor o es de conocimiento general del sistema, pero no fue consultada directamente | REFERENCIADA — con nota |
| **Fuente pendiente** | Debería consultarse pero no se ha podido en el modo actual | PENDIENTE — con GAP-XXX si bloquea |
| **Fuente citada por contexto** | El sistema la conoce y la considera relevante para el contexto pero no la consultó para este expediente | CITADA_CONTEXTO — solo incluir si aporta algo; si no, excluir |

Una fuente REFERENCIADA o CITADA_CONTEXTO no puede presentarse con el mismo formato que una fuente VERIFICADA ONLINE. La diferencia es auditable y debe ser visible.

---

## §4. Tratamiento de URLs, fechas de consulta y versiones

**Para normativa (BOE/BOC)**:
- Identificador oficial (BOE-A-XXXX-XXXXX o BOC XXXX/XXX) — este es el identificador estable
- Fecha de verificación del `normativa_aplicable.json`
- No incluir URL completa del BOE/BOC en la tabla del bloque — el identificador oficial es suficiente y más estable

**Para cartografía**:
- La trazabilidad completa (servicio WMS, endpoint, bbox, CRS, fecha) consta en `cartografia_trace.json`
- En K.3 basta con el nombre del servicio y el estado — la referencia al JSON de trazabilidad es suficiente

**Para sistemas de información (K.5)**:
- URL base del servicio si es pública y estable
- Fecha de consulta si está disponible en los logs del sistema
- Si la URL no es estable o el servicio no tiene URL pública: denominación oficial del servicio + entidad

**Para bibliografía técnica (K.6)**:
- Solo incluir si la referencia puede verificarse exactamente
- Si no se puede verificar la edición, año o editorial: no incluir como referencia completa — usar "según la metodología de Conesa Fernández-Vítora" sin la cita formal

---

## §5. Modo test vs expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Normativa verificada | Solo las normas que AG-05 marcó VERIFICADA ONLINE; el resto como REFERENCIADA | Todas las normas de aplicación directa verificadas antes de la presentación |
| Cartografía | Los mapas generados en Fase 4A con sus estados; algunos con cautelas activas | Todos los mapas con trazabilidad completa y cautelas resueltas o declaradas |
| Fechas de consulta | Las registradas en los JSONs de las fases correspondientes | Ídem, actualizadas a la fecha de presentación definitiva |
| Bibliografía metodológica | Referencia general al método Conesa con nota de adaptación | Ídem — no requiere consulta bibliográfica adicional para EIA simplificada |
| Datos AEMET | Normales 1981-2010 de la estación más próxima | Ídem, con nota de si hay estación más representativa para el emplazamiento |

---

## §6. Estructura mínima obligatoria del Bloque K

```
K.1. Normativa estatal aplicable
     — tabla derivada de normativa_aplicable.json (AG-05)
     — columnas: ID / Norma / Referencia BOE / Estado verificación + fecha / Relevancia
     — encabezado con nota de normativa viva

K.2. Normativa autonómica aplicable
     — tabla derivada de normativa_aplicable.json (AG-05)
     — misma estructura que K.1

K.3. Documentación técnica del promotor
     — tabla de documentos DOC-001 a DOC-XXX
     — columnas: ID / Documento / Autor / Fecha / Estado en el expediente

K.4. Cartografía y geodatos
     — tabla derivada de cartografia_trace.json (AG-06)
     — nota de trazabilidad → cartografia_trace.json
     — columnas: ID / Recurso / Servicio/fuente / Escala / Estado

K.5. Datos climáticos y meteorológicos
     — estación AEMET: código, período, variables, archivos
     — derivado de outputs de AG-07

K.6. Sistemas de información y bases de datos consultados
     — tabla de visores, APIs y sistemas usados efectivamente
     — columnas: Sistema / Entidad / Consulta realizada / URL base (si estable)

K.7. Metodología técnica aplicada
     — referencia al método Conesa con nota estándar de adaptación
     — escala de significancia con referencia al JSON de impactos

K.8. Documentos internos del expediente (outputs del sistema)
     — tabla de archivos generados en fases 2-6
     — columnas: Archivo / Fase / Descripción
```

---

## §7. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien y debe protegerse

1. **La estructura en 8 secciones temáticas**: la separación entre normativa, documentación del promotor, cartografía, datos climáticos, sistemas consultados, metodología y documentos internos es la organización correcta y debe preservarse.

2. **K.4 con referencia a `cartografia_trace.json`**: la nota "La trazabilidad completa de los productos cartográficos [...] consta en `cartografia_trace.json`" es el modelo correcto. El Bloque K no duplica la trazabilidad cartográfica — la apunta.

3. **K.5 con estación, período y archivos explícitos**: la granularidad de los datos climáticos (estación C029O, período 1981-2010, archivos individuales) es auditable y debe replicarse.

4. **K.8 (documentos generados)**: esta sección no existe en los DA convencionales pero es la que permite auditar la cadena outputs-del-sistema → bloques-redactados. Es el elemento diferencial del sistema y debe estar en todos los expedientes.

5. **Los identificadores BOE-A y BOC presentes**: los identificadores oficiales de cada norma son más estables y auditables que las URLs.

### Riesgos detectados en el piloto (a corregir)

1. **Estado de verificación normativa desaparece en K.1/K.2**: el `normativa_aplicable.json` distingue claramente `VERIFICADA ONLINE` (NJ-001, NJ-002, NJ-007, NJ-008) vs `REFERENCIADA` (NJ-003, NJ-004, NJ-005, NJ-006, NJ-009, NJ-010). Esta distinción no aparece en las tablas K.1 y K.2 del piloto — todas las normas parecen igualmente verificadas. Corrección: columna "Estado verificación + fecha" obligatoria en K.1/K.2.

2. **K.7 (Conesa) con cita bibliográfica completa no verificable**: "Conesa Fernández-Vítora, V. (2010). Guía metodológica para la evaluación del impacto ambiental (4ª ed.). Mundi-Prensa." — el sistema no leyó esta obra para este expediente. Aplica la metodología como la tiene implementada. La cita completa con año y editorial es un riesgo de error bibliográfico. Corrección: nota estándar declarando que es adaptación de la metodología, sin cita formal completa si no puede verificarse.

3. **K.6 sin fechas de consulta**: la tabla de sistemas de información no tiene fecha de consulta ni URL. Para los sistemas cartográficos esto está cubierto por `cartografia_trace.json`, pero para los demás (BDN, Sede Electrónica, BOE/BOC) no hay trazabilidad de cuándo se consultaron. Corrección: para los sistemas no cubiertos por el JSON de cartografía, añadir una nota de período de consulta al menos ("consultados entre [rango de fechas del expediente]").

4. **K.3 incluye DOC-004 y DOC-005 sin explicar qué aportaron**: el índice de talleres Rayna y el documento de "sitios web importantes" están en K.3 pero sin referencia a qué HC o análisis generaron. En un expediente real esta ambigüedad puede confundir al auditor. Corrección: la columna "Estado en el expediente" debe incluir lo que el documento aportó al análisis, no solo "PROCESADO".

5. **Riesgo latente de bibliografía decorativa en K.7**: el piloto no cayó en este error, pero la sección de metodología es el punto de entrada natural para que un LLM añada referencias estándar de EIA que no se consultaron. La regla de "solo fuentes que un agente del sistema usó efectivamente" debe aplicarse aquí con particular rigor.

---

*Especificación redactada en P2 — 2026-04-16*
