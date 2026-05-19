# Especificación metodológica — AG-10 / Bloque D
## Medidas Preventivas, Correctoras y de Gestión

**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-16  
**Baseline**: piloto EIA-2026-RECIMETAL-PARCELA  

---

## §1. Qué es un Bloque D válido en este sistema

El Bloque D traduce `medidas_correctoras.json` de AG-09 a narrativa técnica. Es el eslabón entre la valoración de impactos (Bloque C / AG-09) y el seguimiento (Bloque E / PVA). Un Bloque D válido cumple cinco condiciones:

1. **Trazable**: cada medida está vinculada a uno o más impactos (IMP-XX) y a una o más fichas de seguimiento (PVA-XX). La trazabilidad es bidireccional: se puede ir de la medida al impacto y del impacto al seguimiento.

2. **Subordinado**: el Bloque D no inventa medidas ni modifica las propuestas por AG-09. Su función es describir y estructurar, no proponer.

3. **Prudente en la expresión de eficacia**: las medidas reducen, controlan o minimizan impactos. No los eliminan salvo que AG-09 lo establezca explícitamente. Las cifras de eficacia son estimaciones, no garantías.

4. **Completo en la tipología**: clasifica correctamente cada medida entre preventiva, correctora, compensatoria (si existe) o de gestión/cierre. Las compensatorias solo aparecen si hay impactos de significancia Severo o Crítico que no puedan reducirse a Compatible con medidas preventivas y correctoras.

5. **Conectado hacia adelante**: la tabla D.4 (impacto → medida → significancia residual → PVA) cierra la cadena hacia Bloque E. Un Bloque D sin puntero al PVA es un bloque incompleto.

---

## §2. Relación exacta entre AG-09 y Bloque D

El Bloque D es una traducción fiel de `medidas_correctoras.json`. No tiene datos propios.

| Campo del Bloque D | Origen en AG-09 | Restricción |
|-------------------|-----------------|-------------|
| ID de la medida (M-XX) | `medidas[].id` | Idéntico — no renombrar |
| Tipo (preventiva/correctora/etc.) | `medidas[].tipo` | Idéntico |
| Denominación | `medidas[].denominacion` | Puede parafrasearse para fluidez; no cambiar alcance |
| Impacto asociado | `medidas[].impacto_asociado` | Idéntico — no añadir ni quitar IMPs |
| Descripción técnica | `medidas[].descripcion` | Puede desarrollarse; no ampliar el alcance de la medida |
| Criterio de activación | `medidas[].criterio_activacion` | Idéntico si existe en JSON — no inventar si no está |
| Eficacia estimada | `medidas[].eficacia_estimada` | Con qualifier "estimada" obligatorio; no presentar como garantía |
| Condicionante (gap) | `medidas[].condicionante` | Visible con código GAP-XXX |
| Fase de aplicación | `medidas[].fase_aplicacion` | Idéntico |
| Responsable | `medidas[].responsable_implementacion` | Idéntico si está disponible |
| Coste relativo | `medidas[].coste_relativo` | Idéntico si está disponible |

**Tabla de cierre** (`tabla_impacto_medida`):
- La tabla D.4 reproduce `tabla_impacto_medida` de AG-09 con sus significancias residuales exactas.
- No recalcular. No reasignar medidas. No cambiar significancias.
- Añadir columna de PVA asociado para completar la trazabilidad hacia Bloque E.

**Regla de no-adición**: si en el proceso de redacción se detecta que falta una medida evidente para un impacto dado, no se añade en el Bloque D. Se documenta como issue para AG-09 (issue M-XX-gap) y se declara en el Bloque D con una nota. La adición de medidas es competencia de AG-09, no del redactor.

---

## §3. Cómo expresar la eficacia de una medida

### La distinción fundamental: reducción ≠ eliminación

Las medidas del expediente típico de EIA simplificada **reducen o controlan** impactos. Solo en casos excepcionales y con base técnica explícita puede afirmarse que una medida elimina un impacto.

| Nivel de afirmación sobre eficacia | Cuándo está permitido | Formulación estándar |
|-----------------------------------|----------------------|---------------------|
| "reduce", "minimiza", "controla" | En la gran mayoría de medidas | "La medida M-XX **reduce** la [variable] en un [rango] estimado" |
| "elimina" | Solo si AG-09 lo establece explícitamente Y la medida actúa en la causa raíz del impacto de forma verificable | "La medida M-XX **elimina** [causa específica]" — con nota de justificación |
| Cifra de eficacia numérica (ej: "60%") | Solo si proviene de `eficacia_estimada` en el JSON de AG-09, reproducida con el qualifier "estimada" | "Eficacia estimada: reducción de X en ~60% (estimación técnica)" |
| Cifra sin qualifier | Nunca | — |

### El problema de las cifras sin fuente

Las cifras de eficacia en `medidas_correctoras.json` son estimaciones técnicas reconocidas. En el Bloque D se reproducen literalmente del JSON pero siempre con el qualifier "estimada" o "en torno a". No se presentan como resultados medidos ni como garantías contractuales.

Formulación correcta:
> "Eficacia estimada: reducción de dispersión de PM10 en torno al 60% sobre los acopios cubiertos, según estimación técnica."

Formulación incorrecta:
> "Eficacia: reducción de dispersión de PM10 en más del 60%."

La diferencia no es estética — la primera es una proyección técnica; la segunda es un compromiso de resultado.

### Qué sucede cuando no hay cifra de eficacia en AG-09

Si `eficacia_estimada` no está en el JSON, no se inventa. Se usa:
> "La eficacia exacta de esta medida depende de la correcta implementación del protocolo. No se dispone de estimación cuantitativa de referencia para este tipo de instalación."

---

## §4. Cómo redactar cada tipo de medida

### Medidas preventivas
Actúan antes de que el impacto se produzca. Descripción centrada en qué evitan y cuándo se activan. El criterio de activación es obligatorio si está en el JSON.

Estructura de ficha:
- Tipo y impacto asociado
- Descripción de la acción preventiva
- Criterio de activación (si existe)
- Responsable
- Fase de aplicación
- Referencia a PVA-XX que supervisa la implementación

### Medidas correctoras
Actúan sobre el impacto una vez generado, reduciéndolo. Descripción centrada en el mecanismo de reducción y la eficacia estimada.

Estructura de ficha: igual que preventivas + eficacia estimada con qualifier.

### Medidas de gestión / organizativas
No implican obra ni instalación — son procedimientos, protocolos o restricciones operativas. Descripción concisa del protocolo. No inflar.

Nota importante: las medidas organizativas (como M-08 restricción de horario) tienen coste nulo o muy bajo. No presentarlas como "costosas" ni como equivalentes a medidas de ingeniería.

### Medidas de gestión / cierre
Aplican en la fase de cese. Descripción de las acciones de restauración. Si el plan de cierre no está desarrollado en detalle, declararlo así en lugar de inventar contenido.

### Medidas compensatorias
Solo se incluyen si existen en AG-09 (impactos Severo o Crítico que no pueden reducirse suficientemente). Si no hay impactos de esa escala, declarar explícitamente:
> "No se proponen medidas compensatorias al no existir impactos de significancia Severo ni Crítico en el análisis realizado."

Esta declaración es obligatoria siempre que no haya medidas compensatorias, para que quede constancia de que la omisión es intencionada.

---

## §5. Relación entre Bloque D y Bloque E (PVA)

El Bloque D y el Bloque E forman una unidad funcional: D propone → E supervisa. La trazabilidad entre ambos es un requisito de auditoría (M-12, EJE 3).

### Trazabilidad obligatoria D → E

Cada medida (M-XX) debe tener una ficha PVA (PVA-XX) que supervise su implementación o los indicadores del impacto que controla. Si una medida no tiene PVA asociado, declararlo como GAP-PVA-XXX en el Bloque D con la nota correspondiente.

La tabla D.4 incorpora una columna "PVA asociado":

| Impacto | Medidas | Significancia residual | PVA asociado |
|---------|---------|----------------------|--------------|
| IMP-01 — Calidad del aire | M-01, M-02, M-03 | Compatible | PVA-01 |
| IMP-02 — Suelo | M-04, M-06 | Compatible residual | PVA-02 |
| ... | ... | ... | ... |

Si el PVA-XX no existe o está pendiente de desarrollo, la celda dice "PVA-XX — pendiente de desarrollo" con nota de gap.

### Lo que el Bloque D no puede hacer respecto al PVA

- No puede diseñar indicadores del PVA (eso es competencia de AG-09 / Bloque E)
- No puede declarar que una medida está siendo supervisada si no hay ficha PVA que lo acredite
- No puede usar la existencia del PVA como argumento para subir la significancia residual más allá de lo que AG-09 estableció

---

## §6. Modo test vs expediente real

| Aspecto | Modo test | Expediente real |
|---------|-----------|-----------------|
| Medidas sin anejo técnico | Declaradas con nota; condicionante GAP visible | Anejo técnico desarrollado o en tramitación |
| Responsable no designado | GAP-PVA-001 visible en D.3 y tabla D.4 | Designado antes de inicio de actividad |
| Plan de cierre sin detalle | Estructura básica declarada como en desarrollo | Desarrollado con hitos, costes y verificación |
| Eficacia sin fuente externa | "Estimación técnica" — sin cita | Igual o con referencia bibliográfica si disponible |
| GAP condicionante en medidas | Visible con código | Resuelto o en tramitación documentada |

---

## §7. Estructura mínima obligatoria del Bloque D

```
D.1. Criterios de selección de medidas
     — proporcionalidad al proyecto
     — tipología de medidas presentes
     — declaración expresa de ausencia de medidas compensatorias (si no hay impactos Severo/Crítico)

D.2. Tabla resumen de medidas
     — columnas: ID / tipo / denominación / IMP asociado / fase / coste relativo

D.3. Descripción detallada de cada medida
     — una ficha por medida con: tipo, IMP asociado, descripción, criterio activación (si existe),
       eficacia estimada con qualifier (si existe), responsable, fase, referencia PVA-XX

D.4. Tabla impacto — medidas — significancia residual — PVA asociado
     — reproducción exacta de tabla_impacto_medida de AG-09
     — añadir columna PVA asociado
     — significancias idénticas a AG-09 — sin recalcular
```

D.2 y D.4 son obligatorias. D.3 puede omitirse solo si el número de medidas es muy bajo y D.2 ya contiene descripción suficiente — lo que en la práctica nunca ocurre en un expediente completo.

---

## §8a. Reglas incorporadas tras Nave 222 (OBS-M12 — 2026-04-19)

Las siguientes reglas se formalizaron a partir de las observaciones de la auditoría M-12 del expediente NAVE-222. Complementan las especificaciones anteriores.

### D-9 — Medida diagnóstica ≠ medida reductora de significancia (RD-08 — OBS-M12-005)

**Problema identificado en Nave 222**: Un estudio acústico (diagnóstico) se incluyó junto a medidas materiales (insonorización, restricción horaria) en la cadena de reducción de significancia. Aunque el estudio no actúa sobre la causa del impacto, su presencia en la tabla D.4 podía interpretarse como que sí contribuía a la reducción.

**Regla**: Toda medida en `medidas_correctoras.json` tiene un campo `tipo`. Las medidas con `tipo: diagnostico` **no reducen la significancia del impacto** y **no se incluyen en la tabla D.4** de la misma forma que las medidas reductoras.

| Tipo en JSON | Papel en el expediente | Columna D.4 |
|-------------|----------------------|-------------|
| `preventiva`, `correctora`, `compensatoria`, `gestion_cierre` | Actúa sobre la causa o el efecto — **reduce** significancia | Sí — en la cadena de reducción |
| `diagnostico` | Estudio, medición, verificación — **no reduce** significancia | Sección aparte en D.3; nota en D.4 indicando "función diagnóstica, no reductora" |
| `prl` | Protección del trabajador — ámbito laboral, no ambiental | Sección propia D.3.X; **no** en D.4 |

**En D.3**: las medidas diagnósticas tienen ficha en una subsección específica con nota explícita de que su función es verificar, no reducir.

**En D.4**: si existe una medida diagnóstica asociada a un impacto, se añade una nota bajo la fila correspondiente:
> "Nota: [M-XX — denominación] es una medida diagnóstica (estudio / medición). No contribuye a la reducción de la significancia indicada. La significancia residual se calcula solo sobre [M-YY, M-ZZ]."

**Ejemplo canónico (Nave 222)**:
- M-estudio acústico = diagnóstico → no entra en la significancia residual de IMP-04
- M-insonorización + M-restricción horaria = correctoras → sí entran en la significancia residual de IMP-04

**Autochequeo D-9**: ¿Alguna medida diagnóstica (estudio, medición, verificación) aparece en la columna de reducción de significancia en D.4? → Si sí, reclasificarla y añadir la nota explicativa.

---

### D-10 — Separación de medidas EIA y medidas PRL (RD-09 — OBS-M12-005)

**Problema identificado en Nave 222**: Las medidas de Protección de Riesgos Laborales (EPIs auditivos, protocolos de trabajo seguro) podían confundirse con medidas ambientales en la lista principal del Bloque D. Aunque el expediente los separaba implícitamente, no había una sección estructurada para ello.

**Regla**: Las medidas PRL (campo `tipo: prl` en AG-09) tienen su propia sección en D.3, separada de las medidas EIA. No aparecen en la tabla D.4.

**Formato estándar para medidas PRL en D.3**:
```
### D.3.X. [Nombre medida PRL]

**Tipo**: CONDICIONANTE TRANSVERSAL — Protección de Riesgos Laborales (PRL)
**Marco normativo**: [RD 286/2006 para ruido / RD 374/2001 para agentes químicos / etc.]
**Nota**: Esta medida es una obligación del promotor en el ámbito laboral, exigible con 
independencia del procedimiento EIA. No reduce la emisión acústica al exterior de la 
instalación ni la inmisión en el límite de parcela. No se incluye en la tabla de reducción 
de significancias ambientales (D.4). Su control corresponde a la autoridad laboral, no al 
órgano ambiental.
```

**En D.4**: si existe un impacto con una medida PRL asociada (ej: IMP-08 en Nave 222), la fila de D.4 dice:

| IMP-08 — [denominación] | N/A | N/A — ámbito PRL; plan de PRL externo a EIA | N/A |

No se calcula significancia residual para condicionantes transversales PRL.

**Autochequeo D-10**: ¿Hay medidas PRL mezcladas con medidas EIA en la lista principal de D.3? → Si sí, extraerlas a su propia subsección con el formato estándar.

---

## §8. Lecciones del piloto RECIMETAL incorporadas

### Qué funcionó bien en el piloto y debe protegerse

1. **Tabla D.2 con todas las columnas** (ID, tipo, denominación, IMP, coste, fase): estructura completa y directamente auditable.
2. **Fichas D.3 con criterio de activación** (M-01, M-02): concreto y operativo. Buen modelo.
3. **GAP-008 visible en M-04**: condicionante técnico declarado en la propia ficha de la medida. Correcto.
4. **IMP-08 correctamente separado** en tabla D.4 como "N/A — ámbito PRL": el condicionante transversal no recibe medida de la EIA — solo el plan de PRL externo. Modelo correcto.
5. **Declaración de ausencia de medidas compensatorias** en D.1: explícita y justificada. Obligatoria en todos los expedientes donde se aplique.
6. **Registro RD 553/2020 como soporte de seguimiento de M-08**: reutilizar registros obligatorios como soporte del PVA — eficiencia metodológica correcta.

### Riesgos detectados (a corregir en siguiente expediente)

1. **Cifras de eficacia sin qualifier de estimación en la narrativa** (D.3 M-01, M-02): el JSON tiene `eficacia_estimada` correctamente. La narrativa de D.3 usó "Eficacia estimada: Reducción de dispersión de PM10 en más del 60% sobre los acopios cubiertos." — correcto, pero frágil. El "más del" puede leerse como promesa de superación del umbral. Formulación mejor: "en torno al 60%, según estimación técnica".

2. **D.1 usa "eficacia demostrada"** para el criterio de selección: "eficacia demostrada o ampliamente reconocida". "Demostrada" es un término fuerte que puede crear expectativas de prueba formal. Sustituir por "eficacia reconocida en contextos similares" o simplemente "eficacia técnica reconocida".

3. **Tabla D.4 sin columna PVA**: la tabla de cierre del piloto no vinculaba explícitamente cada IMP-XX al PVA-XX que lo supervisa. Esto obligaba a M-12 a reconstruir la cadena. La columna debe añadirse.

4. **IMP-06 (flora/fauna) asociado a M-01/M-02/M-03** sin explicar el mecanismo: la conexión existe (menos polvo = menos afección sobre vegetación periférica) pero no estaba explicada. En el siguiente expediente, cuando la medida actúa sobre un factor de forma indirecta, debe explicarse el mecanismo de transmisión en D.3.

5. **M-10 (plan de cierre) con descripción muy escueta**: los tres puntos del plan de cierre son correcto en modo test, pero en expediente real necesitan hitos, plazos y verificación. En modo test: declarar explícitamente que el plan está en nivel básico y necesita desarrollo.

---

*Especificación redactada en P2 — 2026-04-16*
