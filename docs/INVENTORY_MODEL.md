# INVENTORY_MODEL — IV-00  
## Modelo base de inventario ambiental

Módulo: `src/eia_agent/core/inventory_model.py`  
Ítem: IV-00 | Estado: **COMPLETADO**  
Tests: `tests/test_inventory_model.py` (139 tests)

---

## Qué hace

Define los tipos y funciones que representan los 16 factores ambientales del
inventario ambiental (Fase 5) de un expediente EIA simplificada en Canarias.

No genera fichas markdown. No consulta fuentes externas. No valora impactos.
No usa IA. Es la capa de datos que IV-01 y posteriores usan como contrato.

---

## Factores ambientales (FI-001...FI-016)

| ID      | Nombre                        | Tipo          |
|---------|-------------------------------|---------------|
| FI-001  | Clima                         | fisico        |
| FI-002  | Geología                      | fisico        |
| FI-003  | Suelos                        | fisico        |
| FI-004  | Hidrología                    | fisico        |
| FI-005  | Inundabilidad                 | fisico        |
| FI-006  | Calidad del aire              | fisico        |
| FI-007  | Flora                         | biologico     |
| FI-008  | Fauna                         | biologico     |
| FI-009  | Espacios Naturales Protegidos | biologico     |
| FI-010  | Red Natura 2000               | biologico     |
| FI-011  | Paisaje                       | perceptual    |
| FI-012  | Patrimonio cultural           | socioeconomico|
| FI-013  | Socioeconomía                 | socioeconomico|
| FI-014  | Ruido                         | fisico        |
| FI-015  | Cambio climático              | fisico        |
| FI-016  | Riesgos naturales             | fisico        |

La notación es siempre `FI-NNN` con 3 dígitos (cero-padding). `FI-01` o `FI-1` son inválidos.

---

## Constantes exportadas

### `FACTOR_NAMES: dict[str, str]`
Diccionario ID → nombre canónico de los 16 factores.

### `FACTOR_TYPES: dict[str, list[str]]`
Agrupa factor_ids por categoría:
- `fisico`: 9 factores (FI-001...006, FI-014, FI-015, FI-016)
- `biologico`: 4 factores (FI-007...010)
- `perceptual`: 1 factor (FI-011)
- `socioeconomico`: 2 factores (FI-012, FI-013)
- `integracion`: reservado, vacío actualmente

### `EVIDENCE_STATUS_VALUES: frozenset[str]`
Todos los valores válidos de `EvidenceState` (NL-05), extraídos dinámicamente.
Se mantiene alineado con `evidence_state.py` sin duplicar valores.

### `FIELD_MODES: frozenset[str]`
Necesidad de trabajo de campo:
- `GABINETE_SUFICIENTE`: datos de gabinete suficientes para EIA simplificada
- `CAMPO_RECOMENDADO`: prospección conveniente pero no bloqueante en modo test
- `CAMPO_NECESARIO`: sin campo no se puede valorar la afección
- `NO_CONSTA`: no se ha podido determinar el modo necesario

### `INVENTORY_SEMAPHORES: frozenset[str]`
Estado de completitud del inventario para un factor:
- `VERDE`: factor completamente caracterizado
- `VERDE_AMARILLO`: mayormente caracterizado, gaps menores
- `AMARILLO`: parcialmente caracterizado, gaps moderados
- `ROJO_AMARILLO`: gaps significativos, datos insuficientes
- `ROJO`: sin caracterización suficiente; bloquea gate 5
- `NO_CONSTA`: factor no evaluado; bloquea siempre

### `GAP_CRITICALITIES`, `GAP_RESOLUTION_MODES`, `GAP_STATUSES`
```python
GAP_CRITICALITIES   = frozenset({"ALTA", "MEDIA", "BAJA"})
GAP_RESOLUTION_MODES = frozenset({"GABINETE", "CAMPO", "IRRESOLUBLE_OFFLINE"})
GAP_STATUSES        = frozenset({"PENDIENTE", "CUBIERTO", "CONDICIONADO", "DESCARTADO"})
```

---

## Clases de datos

### `InventoryGap`

Representa un gap de información para un factor ambiental.

```python
@dataclass
class InventoryGap:
    gap_id: str           # Identificador único (ej. "GAP-FI-001-01")
    factor_id: str        # FI-001...FI-016
    field: str            # Campo afectado (ej. "precipitacion_anual")
    description: str      # Descripción del gap
    criticality: str      # ALTA / MEDIA / BAJA
    resolution_mode: str  # GABINETE / CAMPO / IRRESOLUBLE_OFFLINE
    status: str           # PENDIENTE (default) / CUBIERTO / CONDICIONADO / DESCARTADO
```

**Validación en dos niveles:**
- `__post_init__`: levanta `ValueError` para errores estructurales (criticality/resolution_mode/status inválidos)
- `validate() -> list[str]`: devuelve warnings semánticos (factor_id desconocido, campos vacíos)

**Métodos:**
- `to_dict() -> dict`
- `summary() -> str`: línea resumen con gap_id, factor, criticidad, campo y estado

**Gaps activos**: solo los con `status` en `{"PENDIENTE", "CONDICIONADO"}` se
consideran activos para semáforos y métricas.

---

### `FactorInventory`

Representa el estado de inventario de un único factor ambiental.

```python
@dataclass
class FactorInventory:
    factor_id: str
    evidence_status: str
    inventory_semaphore: str
    field_mode: str
    data_sources: list[str]
    gaps: list[InventoryGap]
    notes: str
    ready_for_impact_assessment: bool
    factor_name: Optional[str]   # None → se infiere de FACTOR_NAMES
    factor_type: Optional[str]   # None → se infiere de _FACTOR_ID_TO_TYPE
    validation_warnings: list[str]  # poblado por __post_init__
```

**Reglas aplicadas en `__post_init__`:**
- Infiere `factor_name` y `factor_type` si son `None`
- Añade warning si `factor_id` no está en `FACTOR_NAMES`
- Ejecuta `validate()` y acumula warnings en `validation_warnings`

**`validate() -> list[str]` aplica:**
1. **Regla de coherencia** (AVISO FUERTE): `ready_for_impact_assessment=True` con semáforo ROJO o NO_CONSTA
2. **Regla de prudencia** (CLAUDE.md Regla 4): descripción contiene frases del tipo "no existe", "no hay", "ausencia de"... cuando `field_mode != GABINETE_SUFICIENTE`

**Métodos:**
- `active_gaps() -> list[InventoryGap]`: gaps con status PENDIENTE o CONDICIONADO
- `to_dict() -> dict`

---

### `InventorySummary`

Agrega todos los factores de un expediente. Todos los campos son `@property` (ninguno se almacena, todo se deriva).

```python
@dataclass
class InventorySummary:
    expediente_id: str
    factors: list[FactorInventory]
    warnings: list[str]
```

**Properties:**
| Property | Tipo | Descripción |
|----------|------|-------------|
| `factor_count` | `int` | Número de factores en la lista |
| `ready_count` | `int` | Factores con `ready_for_impact_assessment=True` |
| `factors_by_semaphore` | `dict[str, int]` | Conteo por semáforo |
| `all_gaps` | `list[InventoryGap]` | Todos los gaps de todos los factores |
| `active_gaps` | `list[InventoryGap]` | Solo gaps activos (PENDIENTE/CONDICIONADO) |
| `gap_count_by_criticality` | `dict[str, int]` | Conteo de gaps activos por criticidad |
| `has_critical_gaps` | `bool` | True si hay gaps activos con criticidad ALTA |
| `missing_factor_ids` | `list[str]` | FI-001...016 no presentes en la lista |
| `all_ready_for_phase6` | `bool` | True si cumple todos los requisitos del gate 5 |

**Requisitos de `all_ready_for_phase6`:**
1. Exactamente 16 factores (FI-001...FI-016, todos presentes)
2. Todos los factores con `ready_for_impact_assessment=True`
3. Ningún factor con semáforo ROJO o NO_CONSTA
4. Sin gaps activos de criticidad ALTA

---

## `classify_semaphore_from_evidence()`

Función pura que infiere el semáforo a partir del estado de evidencia y los gaps activos.

```python
def classify_semaphore_from_evidence(
    evidence_status: str,
    gaps: list[InventoryGap],
) -> str: ...
```

**Tabla de clasificación:**

| evidence_status | Sin gaps activos | Gap ALTA | Gap MEDIA | Solo BAJA |
|-----------------|-----------------|----------|-----------|-----------|
| CONFIRMADO_* / CONFIRMADO | VERDE | VERDE_AMARILLO | VERDE_AMARILLO | VERDE_AMARILLO |
| INFERIDO_TECNICO | VERDE_AMARILLO | AMARILLO | VERDE_AMARILLO | VERDE_AMARILLO |
| INFERIDO | VERDE_AMARILLO | ROJO_AMARILLO | ROJO_AMARILLO | VERDE_AMARILLO |
| DECLARADO | AMARILLO | ROJO_AMARILLO | AMARILLO | AMARILLO |
| ESTIMADO / LIMITADO_ESCALA | AMARILLO | ROJO | ROJO_AMARILLO | AMARILLO |
| PROVISIONAL / ASUNCION_TEST | ROJO_AMARILLO | ROJO | ROJO_AMARILLO | ROJO_AMARILLO |
| PENDIENTE_VERIFICACION / PENDIENTE | NO_CONSTA (sin gaps activos) | ROJO | ROJO_AMARILLO | ROJO_AMARILLO |
| NO_CONSTA / ERROR / DESCARTADO | NO_CONSTA | NO_CONSTA | NO_CONSTA | NO_CONSTA |
| Valor desconocido | NO_CONSTA | NO_CONSTA | NO_CONSTA | NO_CONSTA |

---

## Funciones de construcción

### `validate_factor_id(factor_id) -> bool`
True si el factor_id está en FI-001...FI-016.

### `validate_inventory_semaphore(value) -> bool`
True si value es un semáforo válido.

### `validate_field_mode(value) -> bool`
True si value es un modo de campo válido.

### `factor_type_for(factor_id) -> str`
Devuelve el tipo de factor ("fisico", "biologico", etc.) o "desconocido".

### `build_empty_factor_inventory(factor_id) -> FactorInventory`
Crea un FactorInventory vacío para el factor indicado (PENDIENTE, NO_CONSTA, GABINETE_SUFICIENTE).
Levanta `ValueError` si `factor_id` no está en `FACTOR_NAMES`.

### `build_all_empty_factors() -> list[FactorInventory]`
Devuelve los 16 factores vacíos en orden FI-001...FI-016.

### `build_inventory_summary(expediente_id, factors) -> InventorySummary`
Crea un `InventorySummary`. Añade warning si algún factor canónico no está en la lista.

---

## Uso típico

```python
from eia_agent.core.inventory_model import (
    build_all_empty_factors,
    build_inventory_summary,
    classify_semaphore_from_evidence,
    InventoryGap,
    FactorInventory,
)

# Construir inventario vacío de un expediente
factors = build_all_empty_factors()
summary = build_inventory_summary("EIA-2024-001", factors)
print(summary.factor_count)          # 16
print(summary.all_ready_for_phase6)  # False

# Añadir un gap y reclasificar semáforo
gap = InventoryGap(
    gap_id="GAP-FI-007-01",
    factor_id="FI-007",
    field="inventario_especies",
    description="No se dispone de inventario florístico de campo",
    criticality="ALTA",
    resolution_mode="CAMPO",
    status="PENDIENTE",
)
semaforo = classify_semaphore_from_evidence("DECLARADO", [gap])
# → "ROJO_AMARILLO" (DECLARADO + gap ALTA activo)
```

---

## Dependencias

| Módulo | Ítem | Estado |
|--------|------|--------|
| `evidence_state.py` | NL-05 | COMPLETADO |
| `dataclasses` (stdlib) | — | — |
| `typing` (stdlib) | — | — |

Sin dependencias de IA, web, WMS ni piloto.

---

## Tests

Fichero: `tests/test_inventory_model.py` — **139 tests en 8 clases**

| Clase | Tests | Cobertura |
|-------|-------|-----------|
| TestConstants | 17 | FACTOR_NAMES, FACTOR_TYPES, EVIDENCE_STATUS_VALUES, helpers |
| TestInventoryGap | 13 | Creación válida, to_dict, summary, ValueError estructurales |
| TestFactorInventory | 23 | Inferencia nombre/tipo, warnings coherencia/prudencia, validate |
| TestInventorySummary | 22 | Todas las properties, all_ready_for_phase6, missing_factors |
| TestValidators | 14 | FI-001 OK, FI-01 KO, FI-017 KO, semáforos y field_modes |
| TestClassifySemaphore | 19 | Todas las ramas de classify_semaphore_from_evidence |
| TestBuildHelpers | 11 | build_empty, build_all_empty, build_inventory_summary |
| TestFixtureLanzarote | 14 | Fixture realista FI-001 Clima CONFIRMADO_GABINETE, round-trip |

---

*Generado por IV-00 — Modelo base de inventario ambiental.*  
*Prerequisito de IV-01 (plantillas de fichas) y de toda la Fase 5.*
