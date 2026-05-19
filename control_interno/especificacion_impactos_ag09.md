# Especificación técnica — AG-09: Impactos, medidas y PVA
**Versión**: 2.1  
**Estado**: VALIDADO  
**Fecha**: 2026-04-15  
**Baseline**: piloto-recimetal + criterios P2

---

## §1. Propósito y posición en el flujo

AG-09 es el agente de análisis ambiental. Recibe el inventario probatorio cerrado de AG-08 y produce la cadena completa:

```
Acción del proyecto → Factor receptor → Impacto identificado
→ Valoración Conesa simplificada → Significancia sin medidas
→ Medidas correctoras/preventivas → Significancia residual
→ Indicadores PVA + umbrales de control
```

AG-09 **no inventa** datos del proyecto ni del inventario. Lee las capas y fichas generadas por las fases anteriores. Si los datos son insuficientes, registra INDETERMINADO y abre GAP, no imputa valoraciones.

**Prerrequisito**: Fase 5 (AG-08) cerrada con gate satisfecho.  
**Output principal**: `impactos/identificacion_valoracion_impactos.json`, `impactos/medidas_correctoras.json`, `impactos/pva.json`, `bloques/C_impactos.md`.

---

## §2. Estructura de identificación de impactos

### 2.1 Cadena mínima por impacto

Cada impacto identificado debe tener:

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `id` | Sí | IMP-01, IMP-02... (correlativo) |
| `denominacion` | Sí | Nombre técnico del impacto |
| `accion_causante` | Sí | Uno o varios códigos de acción (A-XX) |
| `factor_receptor` | Sí | FR-XX del inventario AG-08 |
| `tipo` | Sí | `nuclear_EIA` / `condicionante_transversal` / `positivo` |
| `estado_inventario_base` | Sí | Estado semáforo de la ficha AG-08 correspondiente |
| `listo_para_ag09` | Sí | Propagado directamente desde la ficha AG-08 |

Sin estos campos, el impacto no puede incluirse en la matriz.

### 2.2 Definición de acciones del proyecto

Las acciones del proyecto se extraen del objeto evaluado cerrado en AG-04 y de los documentos del promotor (DOC-XXX). Se codifican como A-XX y se agrupan por fase:

- **Fase instalación/construcción** (si aplica): preparación del terreno, instalación de instalaciones auxiliares
- **Fase explotación ordinaria**: operaciones de la actividad principal
- **Fase cese y abandono**: desmantelamiento, limpieza, restauración

Cada acción debe tener:
- `id`: A-00, A-01, A-02... (la acción A-00 siempre es el primer transporte o acceso)
- `descripcion`: qué produce físicamente la acción
- `fase`: instalacion / explotacion / cese
- `fuente`: DOC-XXX o INFERIDO si no está explícita en documentación del promotor

### 2.3 Definición de factores receptores

Los factores receptores se derivan directamente de las 16 fichas de AG-08. No se pueden crear factores que no aparezcan en el inventario cerrado.

**Factores excluibles**: si AG-08 marcó un factor como `listo_para_ag09: false` por información insuficiente, el factor debe registrarse en la matriz con `estado: INDETERMINADO` y referencia al gap correspondiente.

**Factores excluidos del scope**: si AG-04 excluyó explícitamente un ámbito del objeto evaluado (ej: operaciones de trituración no incluidas), los factores afectados exclusivamente por esas operaciones se excluyen de la matriz con justificación.

### 2.4 Diferencia entre impactos nucleares y condicionantes transversales

| Tipo | Definición | Tratamiento en EIA |
|------|------------|-------------------|
| `nuclear_EIA` | Impacto ambiental sensu stricto (Ley 21/2013) | Valoración Conesa, medidas, PVA |
| `condicionante_transversal` | Afección cuyo marco regulador es ajeno a la EIA (PRL, seguridad vial) | Registrar, no valorar en escala EIA, señalar instrumento competente |
| `positivo` | Impacto benéfico real sobre factor ambiental o social | Documentar con criterios reales, no post-racionalizar |

**Ejemplo piloto**: IMP-08 (exposición a polvo metálico de los trabajadores) es condicionante PRL. Se registra porque las medidas ambientales tienen co-beneficio sobre la salud laboral, pero no entra en la escala Conesa.

---

## §3. Metodología Conesa simplificada

### 3.1 Versión aplicable

Se aplica la metodología de Conesa Fernández-Vítora, versión simplificada para EIA simplificada (art. 7.2 Ley 21/2013). No se aplica el índice de importancia numérico completo de Conesa; se usa valoración cualitativa por parámetros con escala de significancia de 5 niveles.

### 3.2 Parámetros de valoración

| Parámetro | Criterios |
|-----------|-----------|
| **Signo** | Positivo / Negativo / Sinérgico |
| **Intensidad** | Muy baja / Baja / Media / Alta / Muy alta |
| **Extensión** | Puntual (parcela) / Local (entorno inmediato) / Regional / Global |
| **Persistencia** | Temporal (cesa con la acción) / Permanente (continúa durante la actividad) / Irreversible |
| **Reversibilidad** | Reversible a corto plazo / Reversible con medidas / Reversible a largo plazo / Irreversible |

Cada parámetro debe justificarse con referencia a los datos del inventario (ficha AG-08 correspondiente) o a la descripción del proyecto (AG-04). No se asignan valores por defecto ni por analogía con otros expedientes.

### 3.3 Escala de significancia

| Nivel | Criterio general | Implicaciones para el expediente |
|-------|-----------------|----------------------------------|
| **Compatible residual** | Impacto negativo mínimo, con medidas eficaces ya aplicadas | Seguimiento básico en PVA |
| **Compatible** | Impacto negativo con efecto limitado, reversible | Medidas preventivas estándar, seguimiento en PVA |
| **Moderado** | Impacto apreciable, requiere medidas específicas | Al menos 1 medida correctora obligatoria + PVA específico |
| **Severo** | Afección significativa sobre un factor de alta sensibilidad | Medidas de alta eficacia, puede requerir medidas compensatorias |
| **Crítico** | Afección irreversible o sobre espacio/especie protegida | Bloquea el expediente hasta que se justifique viabilidad |

### 3.4 Significancia sin medidas y significancia residual

**Regla obligatoria**: todo impacto nuclear debe tener:
1. `significancia_sin_medidas`: valoración del impacto en ausencia de medidas
2. `significancia_residual`: valoración tras la aplicación de medidas propuestas

La significancia residual **no puede ser nunca menor que la significancia sin medidas** (las medidas reducen, no invierten el impacto). Si la significancia residual es igual a la significancia sin medidas, se justifica explícitamente que las medidas propuestas no reducen la significancia sino que mantienen la situación controlable.

### 3.5 Tratamiento de la incertidumbre del inventario

El estado del semáforo AG-08 condiciona directamente la valoración:

| Estado semáforo AG-08 | `listo_para_ag09` | Tratamiento en AG-09 |
|-----------------------|-------------------|----------------------|
| CONFIRMADO_CAMPO | true | Valoración normal con plena certeza |
| CONFIRMADO_GABINETE | true | Valoración normal; anotar modo gabinete si relevante |
| INFERIDO_TECNICO | true | Valoración con qualifier: "según análisis gabinete" |
| LIMITADO_ESCALA | true (si gap no crítico) | Valoración con reserva: "escala cartográfica insuficiente para confirmar" |
| PENDIENTE_VERIFICACION | false | INDETERMINADO — no valorar hasta cierre del gap |
| NO_CONSTA | false | INDETERMINADO — abrir GAP de criticidad ALTA |

**Regla absoluta**: cuando `listo_para_ag09: false`, el impacto se registra como `significancia: INDETERMINADO` con referencia al gap bloqueante. No se imputa una valoración provisional para no bloquear el avance.

**Propagación de qualifiers**: si la ficha AG-08 usa qualifier en su estado (ej: "no se detecta en fuentes consultadas"), ese qualifier debe reproducirse literalmente en la valoración del impacto correspondiente.

---

## §4. Impactos positivos

### 4.1 Criterios para registrar un impacto positivo

Un impacto positivo es real si:
1. Produce un beneficio ambiental o socioeconómico **verificable** sobre un factor receptor
2. El factor receptor está identificado en el inventario (AG-08)
3. El beneficio no depende de condiciones futuras inciertas
4. No es la mera ausencia de un impacto negativo

**No son impactos positivos**:
- "No se genera ruido" (ausencia de impacto negativo, no impacto positivo)
- "Contribuye al desarrollo sostenible" (frase genérica sin factor receptor concreto)
- "Genera empleo" sin cuantificar ni vincular a un factor receptor socioeconómico

### 4.2 Parámetros de impactos positivos

Los impactos positivos usan los mismos parámetros que los negativos, con `signo: Positivo`. La significancia positiva se expresa en la misma escala (Compatible / Moderado / Severo / Crítico) con sentido inverso (mayor nivel = mayor beneficio).

**No tienen PVA de alarma** (no hay umbral de control), pero pueden tener **indicadores de eficacia positiva** (ej: toneladas de residuos valorizadas por año).

### 4.3 Ejemplos piloto válidos

- **IMP-09**: generación de empleo directo e indirecto en el sector del reciclaje — factor receptor FR-09 (socioeconomía), intensidad Baja-Media, extensión Local-Regional, verificable por datos del promotor
- **IMP-10**: reducción de CO₂ por sustitución de materia virgen — factor receptor FR-10 (cambio climático / huella de carbono), verificable con ratios de reciclaje de materiales metálicos
- **IMP-11**: restauración del suelo en fase de cese — factor receptor FR-11 (suelo, largo plazo), significancia positiva en fase cese/abandono

---

## §5. Medidas correctoras, preventivas y compensatorias

### 5.1 Tipología de medidas

| Tipo | Definición | Momento de aplicación |
|------|------------|----------------------|
| **Preventiva** | Evita que el impacto se produzca o reduce su probabilidad | Antes o durante la acción causante |
| **Correctora** | Reduce o elimina el impacto una vez que se produce | Durante la explotación |
| **Compensatoria** | Compensa un impacto que no puede evitarse ni corregirse | Paralelamente o a posteriori |
| **Gestión / Cierre** | Medidas específicas para la fase de cese y abandono | Fase de cese |

### 5.2 Campos mínimos por medida

```json
{
  "id": "M-XX",
  "tipo": "Preventiva | Correctora | Compensatoria | Gestión/Cierre",
  "denominacion": "...",
  "impacto_asociado": "IMP-XX",
  "descripcion": "...",
  "fase_aplicacion": "...",
  "responsable_implementacion": "...",
  "coste_relativo": "Nulo | Muy bajo | Bajo | Bajo-medio | Medio | Alto"
}
```

### 5.3 Tabla impacto-medida

Todo el bloque de impactos debe incluir una `tabla_impacto_medida` que muestre:
- Impacto → medidas asociadas → significancia residual tras medidas

Esta tabla es la fuente de verdad para el bloque de redacción (AG-10/bloque_E y bloque_F).

### 5.4 Reglas de asignación de medidas

- Todo impacto de significancia **Moderado o superior** debe tener al menos una medida correctora o preventiva específica.
- Las medidas no pueden ser genéricas del tipo "buenas prácticas ambientales" sin descripción operativa concreta.
- Si una medida ya está exigida por normativa sectorial (ej: plan PRL exigido por Ley 31/1995, registro de residuos exigido por RD 553/2020), se registra con referencia normativa explícita y se nota que el expediente no la crea sino que la incorpora.
- Una medida puede asociarse a múltiples impactos (co-beneficio), pero cada asociación debe estar documentada.

---

## §6. Programa de Vigilancia Ambiental (PVA)

### 6.1 Proporcionalidad

El PVA debe ser proporcional a la escala del proyecto y al tipo de procedimiento (EIA simplificada, art. 7.2 Ley 21/2013). Un PVA desproporcionadamente oneroso puede ser rechazado por el órgano ambiental. Un PVA insuficiente tampoco es aceptable.

Criterio: el PVA cubre los impactos con significancia **Compatible o superior** tras medidas. Los impactos reducidos a Compatible residual pueden tener seguimiento básico.

### 6.2 Estructura mínima del PVA

**Elementos estructurales obligatorios**:
- `responsable_general`: cargo responsable del PVA (si no designado, registrar como GAP)
- `informe_organo_ambiental`: periodicidad y destinatario de informes, condicionado al IIA

**Por cada ficha PVA**:

| Campo | Obligatorio | Descripción |
|-------|-------------|-------------|
| `id` | Sí | PVA-01, PVA-02... |
| `impacto_asociado` | Sí | IMP-XX |
| `denominacion_impacto` | Sí | Nombre del impacto |
| `medidas_asociadas` | Sí | M-XX que se vigilan |
| `indicador` | Sí | Descripción operativa del indicador (qué se mide, cómo, dónde) |
| `umbral_de_control` | Sí | Valor o situación que activa acción correctora |
| `accion_si_umbral_superado` | Sí | Qué se hace cuando se supera el umbral |
| `frecuencia_seguimiento` | Sí | Periodicidad concreta (semanal, mensual, trimestral, etc.) |
| `responsable` | Sí | Quién realiza el seguimiento |
| `registro` | Sí | Qué documentación se genera |
| `periodo` | Sí | Durante qué tiempo de la actividad |

### 6.3 Indicadores operativos

Los indicadores del PVA deben ser **observacionales y verificables** sin necesidad de laboratorio, a menos que el órgano ambiental lo exija expresamente. La regla: cualquier inspector ambiental debe poder verificar el cumplimiento del indicador sin equipamiento especializado en una visita de inspección.

**Indicadores válidos** (ejemplos piloto):
- Paños de tela blanca para detección de partículas metálicas (PVA-01): visual, fotografiable, trazable
- Inspección visual de arqueta de retención (PVA-02): observable, cuantificable por % de llenado
- Certificados de empresa de control de plagas (PVA-05): documental, verificable

**Indicadores no válidos**:
- "Cumplimiento de la normativa": no es observable directamente
- "Ausencia de impacto": no es un indicador, es el objetivo final
- "Control periódico de la instalación": demasiado genérico

### 6.4 Impactos positivos en el PVA

Los impactos positivos pueden tener **indicadores de eficacia positiva** (no de control/alarma) que se incluyen en el PVA para demostrar ante el órgano ambiental que el beneficio se está produciendo. Estos indicadores aprovechan registros ya obligatorios por normativa sectorial cuando sea posible (ej: datos del Registro de Producción y Gestión de Residuos para IMP-10).

### 6.5 PVA y obligaciones pre-existentes

El PVA no duplica obligaciones normativas existentes; las integra. Cuando un indicador se basa en un registro ya obligatorio por normativa sectorial, se referencia explícitamente para no aumentar la carga administrativa del promotor.

### 6.6 Condicionamiento al IIA

Las obligaciones de remisión de informes al órgano ambiental dependen de las condiciones que fije el Informe de Impacto Ambiental (IIA). El expediente no asume automáticamente una obligación de reporte periódico al órgano ambiental; la registra como condicionada al IIA.

---

## §7. Gaps de criticidad abiertos en AG-09

Los gaps que AG-09 identifica o hereda de AG-08 se registran en `inferencias_y_gaps.json` con:
- `origen`: "AG-09" o "heredado_AG-08"
- `afecta_a`: lista de IMP-XX afectados
- `criticidad`: ALTA / MEDIA / BAJA
- `bloquea_gate_6`: true si impide cerrar la fase

Los gaps que producen `significancia: INDETERMINADO` en uno o más impactos son automáticamente criticidad ALTA y bloquean el gate 6.

**Gaps específicos que el piloto evidenció**:
- GAP-008: estado de impermeabilización de la parcela (desconocido) → IMP-02 valorado a la baja pero con reserva
- GAP-002: anejo de drenaje no aportado → IMP-03 valorado a la baja con precaución
- GAP-INV-001/002: flora y fauna por prospección de campo no realizada → IMP-06 con precaución y nota explícita

---

## §8. Relaciones con otros agentes

### AG-08 → AG-09

| Campo AG-08 | Uso en AG-09 |
|-------------|-------------|
| `semaforo_evidencia` de cada ficha | Determina certeza de la valoración Conesa |
| `listo_para_ag09` | true = valorar normalmente; false = INDETERMINADO |
| `semaforo_campo.md` | Indica qué factores pueden mejorar con campo; registrar en PVA si aplica |
| `afirmaciones_cualificadas` | Deben reproducirse como qualifiers en la valoración |
| `gaps_criticos` del inventario | Se propagan a gaps de AG-09 y pueden bloquear el gate |

### AG-09 → AG-10

AG-09 produce los inputs directos de los bloques de redacción:
- `bloque_C_impactos.md` (o equivalente según estructura EIA del expediente): redacción de la identificación y valoración
- `bloque_E_impactos.md`: tabla de impactos con significancia
- `bloque_F_medidas.md`: descripción de medidas correctoras
- `bloque_G_pva.md`: programa de vigilancia ambiental

Las valoraciones de AG-09 son los únicos datos que AG-10 puede usar para redactar la sección de impactos. AG-10 no puede elevar la significancia ni omitir qualifiers presentes en las fichas AG-09.

---

## §9. Test vs producción

| Aspecto | Modo TEST | Modo PRODUCCIÓN |
|---------|-----------|-----------------|
| Número de impactos mínimo | No hay mínimo — los que correspondan al expediente | Los que correspondan |
| Significancia permitida | Cualquier nivel, incluyendo Severo y Crítico | Ídem |
| Indicadores PVA | Operativos pero simplificados | Completos y verificables |
| Gaps INDETERMINADO | Aceptable si se documenta | Aceptable si se documenta |
| Bloque C_impactos.md | Puede estar incompleto si hay INDETERMINADOS | Completo o con gaps explícitos |
| `listo_para_ag10` | Puede ser false si hay gaps abiertos | Idealmente true para todos |

En modo TEST, el gate 6 pasa si:
- La cadena acción→factor→impacto está completa para todos los impactos identificados
- No hay impactos nucleares con significancia Severo o Crítico sin al menos una medida registrada (aunque sea provisional)
- El PVA tiene al menos una ficha por impacto Compatible o superior
- Los gaps INDETERMINADO están registrados en `inferencias_y_gaps.json`

---

## §10a. Reglas incorporadas tras Nave 222 (OBS-M12 — 2026-04-19)

Las siguientes reglas se formalizaron a partir de las observaciones de la auditoría M-12 del expediente NAVE-222. No modifican las reglas anteriores — las completan para cubrir lagunas detectadas en la práctica.

### AG09-10 — Tabla Conesa para TODOS los impactos (RD-06 — OBS-M12-003)

**Origen del gap**: En Nave 222, los impactos de significancia Compatible no tenían tabla Conesa completa — solo descripción cualitativa. Esto redujo la trazabilidad y dificultó la auditoría.

**Regla**: La tabla Conesa (con los 10 parámetros: In, Ex, Mo, Pe, Rv, Si, Ac, Ef, Pr, Mc) es **obligatoria para todos los impactos nucleares**, con independencia de su nivel de significancia. No hay exención para impactos Compatible.

**Justificación**: La auditabilidad y coherencia del expediente requieren que la significancia sea derivable de los parámetros en todos los casos, no solo en los más altos. Además, el órgano ambiental puede revisar cualquier impacto, no solo los Moderados o superiores.

**Implementación en el JSON**:
```json
"valoracion_conesa": {
  "In": "...", "Ex": "...", "Mo": "...", "Pe": "...", "Rv": "...",
  "Si": "...", "Ac": "...", "Ef": "...", "Pr": "...", "Mc": "...",
  "formula": "IMP = ±[3·In + 2·Ex + Mo + Pe + Rv + Si + Ac + Ef + Pr + Mc]",
  "resultado_numerico": X,
  "significancia": "Compatible | Moderado | Severo | Crítico"
}
```

**Autochequeo AG09-10**: ¿Todos los impactos nucleares tienen los 10 parámetros Conesa en el JSON? → Si alguno los omite, completar antes de cerrar AG-09.

---

### AG09-11 — Sección obligatoria de efectos acumulativos y sinérgicos (IM-06 — OBS-M12-004)

**Origen del gap**: El art. 45.1.f) Ley 21/2013 exige el análisis de efectos acumulativos y sinérgicos. En Nave 222, no había sección específica para ello — los efectos se trataban de forma dispersa o se omitían.

**Regla**: AG-09 debe incluir una sección `efectos_acumulativos_sinergicos` en el JSON de impactos (o un archivo aparte) con análisis de al menos 4 áreas:

| Área | Contenido mínimo |
|------|-----------------|
| Acumulación entre impactos del mismo proyecto | ¿Hay impactos de la misma instalación que se sumen sobre un factor? |
| Sinergia entre impactos | ¿Hay impactos que, combinados, producen un efecto mayor que la suma? |
| Acumulación con instalaciones del entorno | ¿Hay otras actividades en el entorno que amplifiquen algún impacto? |
| Tendencia temporal | ¿Algún impacto se acumula con el tiempo (ej: suelo, contaminantes persistentes)? |

**Si el análisis no es posible por falta de datos**: declarar explícitamente como gap con criticidad proporcional al tipo de impacto sin datos.

**El Bloque C (AG-10) tiene sección C.5 dedicada** que consume este análisis. AG-09 debe generarlo para que C.5 no quede vacío.

**Autochequeo AG09-11**: ¿El JSON incluye la sección de efectos acumulativos/sinérgicos con las 4 áreas mínimas? → Si no, añadir o declarar el gap.

---

### AG09-12 — Cadenas condicionales para CONTs no resueltos (IM-07 — OBS-M12-007)

**Origen del gap**: Cuando hay una contradicción no resuelta (CONT) entre documentos del promotor, los impactos, medidas y PVA asociados quedan en estado indeterminado. En Nave 222 no había un mecanismo sistemático para representar esta condición en los bloques de redacción.

**Regla**: Si existe un CONT no resuelto que afecta a la valoración de uno o varios impactos, AG-09 debe generar una **cadena condicional** con el siguiente formato en el JSON:

```json
"cadena_condicional": {
  "cont_ref": "CONT-XXX",
  "descripcion_cont": "descripción de la contradicción",
  "impactos_afectados": ["IMP-XX", "IMP-YY"],
  "medidas_adicionales_si_confirma": ["M-XX-cond"],
  "pva_condicionado": ["PVA-XX-cond"],
  "estado": "PENDIENTE_CONFIRMACION"
}
```

**Casos estándar que generan cadenas condicionales**:
- Vehículos fuera de uso (VFU) / LER 16 01 06 sin confirmar tipología exacta de residuos
- Maquinaria mencionada sin confirmar si es propia o de terceros (afecta a ruido, emisiones)
- Residuos peligrosos de proceso no confirmados documentalmente (afecta a suelo, aguas)
- Cambio de operación declarado en un documento pero no en otro (afecta al objeto evaluado)

**Propagación obligatoria**: las cadenas condicionales deben aparecer en los bloques C, D y E con notas visibles. AG-09 activa la cadena; AG-10 la reproduce en los bloques.

**Autochequeo AG09-12**: ¿Hay CONTs abiertos en `inferencias_y_gaps.json`? → Si sí, verificar que cada CONT tiene cadena condicional o declaración de por qué no aplica.

---

### AG09-13 — Medida diagnóstica ≠ medida reductora (RD-08 — OBS-M12-005)

**Origen del gap**: En Nave 222, un estudio acústico (medida diagnóstica) se incluyó en la cadena de reducción de significancia junto con medidas materiales (insonorización, restricción horaria). Esto inflaba artificialmente la reducción de significancia.

**Regla**: Las medidas se clasifican en dos categorías con campo `tipo` en `medidas_correctoras.json`:

| Tipo | Definición | ¿Reduce significancia? |
|------|------------|----------------------|
| `preventiva` / `correctora` / `compensatoria` / `gestion_cierre` | Medida material u operativa que actúa sobre la causa o el efecto del impacto | **Sí** — se incluye en el cálculo de significancia residual |
| `diagnostico` | Estudio, medición, modelización, verificación o auditoría que caracteriza el impacto pero no lo reduce | **No** — no puede justificar reducción de significancia |

**Ejemplo canónico (Nave 222)**:
- Estudio acústico → `tipo: diagnostico` → no reduce significancia
- Insonorización acústica → `tipo: correctora` → sí reduce significancia
- Restricción horaria → `tipo: preventiva` → sí reduce significancia

La significancia residual se calcula **solo** sobre las medidas `correctora` y `preventiva`. Las medidas `diagnostico` pueden ir en la tabla de medidas pero no en la columna de reducción.

**Autochequeo AG09-13**: ¿Alguna medida diagnóstica (estudio, medición, verificación) tiene `tipo` distinto de `diagnostico`? → Si sí, reclasificar y recalcular la significancia residual sin ella.

---

### AG09-14 — Medidas PRL separadas de medidas EIA (RD-09 — OBS-M12-005)

**Origen del gap**: Las medidas de Protección de Riesgos Laborales (EPIs, protocolos de seguridad) actúan sobre la exposición del trabajador, no sobre la emisión o inmisión ambiental. En Nave 222 hubo riesgo de mezclarlas con medidas EIA.

**Regla**: Las medidas PRL tienen campo `tipo: prl` en `medidas_correctoras.json` y **no aparecen en `tabla_impacto_medida`** junto a las medidas EIA. Se registran en AG-09 como condicionante transversal con:
- `tipo: prl`
- `marco_normativo`: referencia al RD aplicable (RD 286/2006 para ruido, RD 374/2001 para agentes químicos, etc.)
- `nota_alcance`: "Esta medida es una obligación en el ámbito laboral. No reduce la emisión al exterior ni la inmisión en el límite de parcela. No contribuye a la reducción de significancia EIA."

En el Bloque D (AG-10), las medidas PRL tienen **sección separada** con nota de ámbito. No aparecen en D.4 (tabla de significancias residuales).

**Autochequeo AG09-14**: ¿Alguna medida con `tipo: prl` está en `tabla_impacto_medida`? → Si sí, eliminar de esa tabla y mover a sección separada.

---

## §10. Lecciones del piloto Recimetal (L-AG09)

### L-01: IMP-08 como condicionante transversal
El piloto registró correctamente IMP-08 como condicionante PRL fuera de la escala EIA. Esta distinción es fundamental para no mezclar el análisis ambiental con el análisis de seguridad laboral. Patrón a mantener.

### L-02: Significancia uniforme en el piloto
Todos los impactos negativos del piloto resultaron Compatible o Compatible residual. Esto es coherente con la escala del proyecto (almacén de chatarra de 1.931 m² en polígono industrial sin receptores sensibles), pero **no debe asumirse por defecto**. Proyectos similares en entornos distintos (zonas húmedas, ENP, núcleos urbanos) producirán significancias más altas.

### L-03: Gaps no bloqueantes pero anotados
GAP-008 (impermeabilización) y GAP-002 (drenaje) no bloquearon la valoración porque la valoración a la baja (Compatible) era razonable incluso con los peores supuestos. Sin embargo, se anotaron explícitamente en la descripción de cada impacto. Este es el patrón correcto: no bloquear innecesariamente, pero nunca absorber silenciosamente la incertidumbre.

### L-04: Aprovechamiento de registros normativos obligatorios en el PVA
PVA-07 aprovecha el Registro de Producción y Gestión de Residuos (ya obligatorio por RD 553/2020) como fuente de datos para el indicador de impacto positivo IMP-10. Esto reduce la carga administrativa del promotor y hace el PVA más sostenible. Patrón replicable en otros expedientes.

### L-05: Impactos positivos con factor receptor concreto
Los tres impactos positivos del piloto (IMP-09, IMP-10, IMP-11) tienen factor receptor concreto y verificable. No se incluyó ningún "impacto positivo" genérico tipo "contribuye al medio ambiente". Este estándar debe mantenerse.

### L-06: Responsable Ambiental no designado
GAP-003 (no se indica nombre ni titulación del Responsable Ambiental) abrió GAP-PVA-001 de criticidad ALTA. La función existe pero la persona no está designada. El PVA no puede ejecutarse sin esta designación. Este tipo de gap debe registrarse siempre que el PVA dependa de un cargo no designado formalmente.
