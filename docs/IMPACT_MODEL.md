# IMPACT_MODEL — IM-00

Gate de apertura de Fase 6 / Modelo base de impactos, medidas y PVA.

**Módulo**: `src/eia_agent/core/impact_model.py`  
**ID de productización**: IM-00  
**Completado**: 2026-05-03  
**Dependencias**: IV-00 (`inventory_model`)

---

## Qué hace IM-00

Define los tipos Python y funciones auxiliares para representar en Fase 6:

1. **Acciones del proyecto** (`ProjectAction`) — operaciones del promotor que generan presión ambiental (R1201, R1202, etc.).
2. **Factores receptores** (`ReceptorFactor`) — los 16 factores FI-001...FI-016 del inventario de Fase 5, convertidos en receptores de impacto con su estado proveniente del inventario.
3. **Impactos ambientales** (`EnvironmentalImpact`) — registro de cada impacto acción × factor, con naturaleza, estado, significancias y atributos Conesa pendientes de valorar.
4. **Atributos de valoración Conesa** (`ConesaAttributes`) — los 10 atributos (IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc), cada uno `int | None`.
5. **Medidas ambientales** (`MitigationMeasure`) — preventivas, correctoras, diagnósticas o PRL, con reglas metodológicas AG09-13 y AG09-14.
6. **Programas de vigilancia ambiental** (`PVAProgram`) — con indicador, umbral, frecuencia y responsable.
7. **Paquete de Fase 6** (`Phase6Model`) — contenedor estructurado con validación referencial cruzada.

## Qué NO hace IM-00

| Capacidad | Estado |
|-----------|--------|
| Valorar impactos (calcular índice Conesa) | No — Fase 6 / IM-01 |
| Calcular I = ±(3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc) | No — IM-01 |
| Clasificar significancia (COMPATIBLE/MODERADO/SEVERO/CRÍTICO) | No — IM-01 |
| Generar medidas reales para un expediente | No — IM-02 |
| Generar fichas PVA reales | No — IM-03 |
| Redactar bloques del Documento Ambiental | No — Fase 7 |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| CLI propio | No — se añadirá en IM-01 |
| Escribir archivos desde el módulo | No |

---

## Relación con Fase 5

`InventorySummary` (Fase 5 / IV-00) → `build_receptor_factors_from_inventory()` → `list[ReceptorFactor]`

El helper copia de cada `FactorInventory`:
- `inventory_semaphore` → estado del semáforo de inventario.
- `ready_for_impact_assessment` → `ready_from_inventory`.
- gaps con `criticality=ALTA` y `status=PENDIENTE|CONDICIONADO` → `critical_gaps`.

Los factores no listos para Fase 6 conservan visibilidad en `notes`.

## Relación con futuros IM-01, IM-02, IM-03

```
IM-00 (tipos + reglas)
  └── IM-01 (constructor matriz Conesa offline)
            ├── IM-02 (constructor medidas correctoras)
            │         ├── IM-03 (constructor fichas PVA)
            │         │         └── IM-05 (validador cobertura PVA)
            │         ├── RD-08 (check diagnóstico≠reductor)
            │         └── RD-09 (check EIA/PRL separator)
            └── RD-06 (Conesa 10 atributos checker)
```

---

## Estructura del modelo: acción → receptor → impacto → medida → PVA

```
ProjectAction (AC-001...)
    │
    ▼
EnvironmentalImpact (IMP-001...)
    │ action_id → AC-001
    │ receptor_id → FR-001
    │ nature: NEGATIVO / POSITIVO / MIXTO / INDETERMINADO
    │ status: PENDIENTE_DATOS / IDENTIFICADO / VALORADO...
    │ significance_without_measures: NO_VALORADO (hasta IM-01)
    │ significance_with_measures:    NO_VALORADO (hasta IM-01)
    │ conesa_attributes: ConesaAttributes (int | None × 10)
    ▼
MitigationMeasure (MED-001...)
    │ measure_type: PREVENTIVA / CORRECTORA / DIAGNOSTICA / PRL_NO_EIA...
    │ target_impact_ids → [IMP-001...]
    ▼
PVAProgram (PVA-001...)
    │ factor_id → FI-001...
    │ target_impact_ids → [IMP-001...]
    │ target_measure_ids → [MED-001...]
    ▼
ReceptorFactor (FR-001...)
    │ inventory_factor_id → FI-001...FI-016
    │ inventory_semaphore → estado desde Fase 5
    │ ready_from_inventory → bool
    │ critical_gaps → [GAP-IDs ALTA pendientes]
```

---

## Separación entre medidas EIA, diagnósticas y PRL_NO_EIA

### DIAGNOSTICA (AG09-13)
- Tipo `DIAGNOSTICA` en `MitigationMeasure.measure_type`.
- Flag `is_diagnostic=True`.
- **No puede actuar como medida reductora de significancia.**
- No aparece en la tabla de impacto-medida EIA como reductora.
- Ejemplo: "Monitoreo de polvo en período de obras."

### PRL_NO_EIA (AG09-14)
- Tipo `PRL_NO_EIA` en `MitigationMeasure.measure_type`.
- Flag `is_prl_only=True`.
- **No reduce significancia ambiental.**
- No tiene `residual_significance` (campo no existe en este modelo).
- Ejemplo: "Uso de EPIs por trabajadores."
- `validate()` detecta incoherencias entre `is_prl_only` y `measure_type`.

### Medidas EIA convencionales
- Tipos: `PREVENTIVA`, `CORRECTORA`, `PROTECTORA`, `COMPENSATORIA`.
- Deben referenciar al menos un impacto objetivo (`target_impact_ids`).
- `validate()` genera aviso si `target_impact_ids` está vacío para estos tipos.

---

## Regla de no compensación de impactos positivos

Un impacto POSITIVO no compensa uno NEGATIVO. Cada impacto se registra y evalúa de forma independiente.

`Phase6Model.validate()` detecta si una medida apunta simultáneamente a impactos POSITIVOS y NEGATIVOS y genera aviso metodológico.

Esta regla es coherente con la metodología Conesa-Fernández Vítora y con el principio de evidencia de EIA-Agent v2.1.

---

## API pública

### Constantes

| Constante | Tipo | Descripción |
|-----------|------|-------------|
| `ACTION_TYPES` | `frozenset[str]` | 7 tipos de acción (OPERACION, AUXILIAR, etc.) |
| `RECEPTOR_FACTOR_IDS` | `dict[str, str]` | Mapping FR-001...FR-016 → FI-001...FI-016 |
| `RECEPTOR_FACTOR_NAMES` | `dict[str, str]` | Nombres canónicos de receptores |
| `IMPACT_NATURES` | `frozenset[str]` | NEGATIVO, POSITIVO, MIXTO, INDETERMINADO |
| `IMPACT_STATUS` | `frozenset[str]` | IDENTIFICADO, VALORADO, PENDIENTE_DATOS, ... |
| `IMPACT_SIGNIFICANCE` | `frozenset[str]` | COMPATIBLE...CRITICO + NO_VALORADO + INDETERMINADO |
| `MEASURE_TYPES` | `frozenset[str]` | PREVENTIVA, CORRECTORA, DIAGNOSTICA, PRL_NO_EIA, ... |
| `MEASURE_STATUS` | `frozenset[str]` | PROPUESTA, CONDICION_PREVIA, CONDICIONADA, ... |
| `PVA_FREQUENCIES` | `frozenset[str]` | DIARIA, SEMANAL...ANUAL, UNICA_PREVIA, ... |
| `CONESA_ATTRIBUTE_NAMES` | `tuple[str, ...]` | Los 10 atributos Conesa en orden canónico |

### `ConesaAttributes`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `intensidad` | `int \| None` | IN — pendiente si None |
| `extension` | `int \| None` | EX |
| `momento` | `int \| None` | MO |
| `persistencia` | `int \| None` | PE |
| `reversibilidad` | `int \| None` | RV |
| `sinergia` | `int \| None` | SI |
| `acumulacion` | `int \| None` | AC |
| `efecto` | `int \| None` | EF |
| `periodicidad` | `int \| None` | PR |
| `recuperabilidad` | `int \| None` | Mc |

Métodos: `is_complete()`, `missing_attributes()`, `validate()`, `to_dict()`.

La fórmula `I = ±(3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc)` y la clasificación de significancia se implementan en IM-01.

### `ProjectAction`

Campos: `action_id` (AC-NNN), `name`, `description`, `action_type`, `operation_code`, `source_refs`, `notes`.  
`validate()` verifica patrón de ID, nombre no vacío y tipo en `ACTION_TYPES`.

### `ReceptorFactor`

Campos: `receptor_id` (FR-NNN), `inventory_factor_id` (FI-NNN), `name`, `inventory_semaphore`, `ready_from_inventory`, `critical_gaps`, `notes`.  
`validate()` verifica patrones de ID y visibilidad del motivo de no-readiness.

### `EnvironmentalImpact`

Campos: `impact_id` (IMP-NNN), `action_id` (AC-NNN), `receptor_id` (FR-NNN), `name`, `nature`, `status`, `significance_without_measures`, `significance_with_measures`, `conesa_attributes`, `data_gaps`, `source_refs`, `measure_ids`, `pva_ids`, `warnings`, `notes`.

`validate()` detecta:
- IDs con formato incorrecto.
- Valores fuera de las constantes de dominio.
- `status=VALORADO` con atributos Conesa incompletos → ERROR.
- `significance_without_measures=SEVERO|CRITICO` sin medidas → AVISO.

`is_indeterminate()`: True si nature o alguna significancia es INDETERMINADO.  
`requires_measures()`: True si significancia sin medidas es SEVERO o CRITICO.

### `MitigationMeasure`

Campos: `measure_id` (MED-NNN), `name`, `measure_type`, `status`, `target_impact_ids`, `is_diagnostic`, `is_prl_only`, `condition_before_submission`, `warnings`, `notes`.

`validate()` detecta:
- `is_prl_only=True` con `measure_type != PRL_NO_EIA` (AG09-14).
- `is_diagnostic=True` con `measure_type != DIAGNOSTICA` (AG09-13).
- `target_impact_ids` vacío para medidas reductoras.

### `PVAProgram`

Campos: `pva_id` (PVA-NNN), `name`, `factor_id` (FI-NNN), `indicator`, `threshold`, `frequency`, `target_impact_ids`, `target_measure_ids`, `responsible`, `records`, `warnings`, `notes`.

`validate()` genera aviso si `threshold` o `responsible` están vacíos.

### `Phase6Model`

Campos: `expediente_id`, `actions`, `receptor_factors`, `impacts`, `measures`, `pva_programs`, `warnings`, `notes`.

`validate()` detecta:
- IDs duplicados en cualquier lista.
- Referencias a acciones, receptores, impactos o medidas inexistentes.
- Impactos SEVERO/CRITICO sin medidas.
- Medida apuntando a POSITIVO y NEGATIVO (regla de no compensación).

Métodos de consulta: `impact_count_by_status()`, `impacts_by_receptor()`, `measures_by_impact()`, `pva_by_factor()`.

### `build_receptor_factors_from_inventory(summary)`

Crea `list[ReceptorFactor]` desde un `InventorySummary`.  
No modifica el summary. Copia semáforo, ready y gaps críticos.

### `build_empty_phase6_model(expediente_id, inventory_summary=None)`

Crea un `Phase6Model` vacío. Si se pasa `inventory_summary`, puebla `receptor_factors`.  
No crea impactos, medidas ni PVA.

---

## Cómo ejecutar los tests

```bash
# Solo IM-00
venv\Scripts\python -m unittest tests.test_impact_model

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_impact_model.py`  
**Tests**: 144 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestProjectAction` | 13 | creación, IDs, tipos, nombres, to_dict, summary, JSON |
| `TestReceptorFactor` | 11 | IDs FR/FI, ready, gaps, notas, to_dict, summary |
| `TestConesaAttributes` | 11 | completitud, missing_attributes, validación rangos, to_dict |
| `TestEnvironmentalImpact` | 20 | IDs, nature/status/significance, is_indeterminate, requires_measures, VALORADO+incompleto, SEVERO sin medidas, to_dict, JSON |
| `TestMitigationMeasure` | 15 | IDs, name, tipos, estados, PRL coherencia, DIAGNOSTICA coherencia, target vacío, to_dict, summary |
| `TestPVAProgram` | 12 | IDs, indicator vacío, frequency, threshold/responsible avisos, to_dict, JSON |
| `TestPhase6Model` | 22 | vacío, con datos, duplicados, referencias inválidas, regla no-compensación, métricas, to_dict, JSON |
| `TestBuildReceptorFactorsFromInventory` | 11 | 16 FR, FR↔FI, semáforo, ready, gaps críticos, no mutación |
| `TestBuildEmptyPhase6Model` | 11 | sin/con inventario, sin impactos/medidas/PVA, expediente_id, notas, JSON |
| `TestConstantsIntegrity` | 9 | completitud constantes, biyección FR↔FI, nombres Conesa |

---

*Generado por EIA-Agent v2.1 — IM-00 — 2026-05-03*
