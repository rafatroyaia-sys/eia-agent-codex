# INVENTORY_CONTEXT_BUILDER — IV-04

Constructor de factores FI-011 Paisaje y FI-013 Socioeconomía desde Fase 2/Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_context_builder.py`  
**ID de productización**: IV-04  
**Completado**: 2026-04-30  
**Dependencias**: IV-00 (`inventory_model`), OB-06 (`phase2_pipeline`), F4-01 (`phase4_offline_pipeline`), CA-10 (`cartography_plan`)

---

## Qué hace IV-04

- Construye FI-011 Paisaje con evidencia ESTIMADO/PENDIENTE a partir de coordenadas y plan cartográfico offline.
- Construye FI-013 Socioeconomía con evidencia DECLARADO/PENDIENTE a partir de los datos del promotor en Fase 2.
- Deja en ambos factores los gaps de seguimiento obligatorios visibles.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-04

| Capacidad | Estado |
|-----------|--------|
| Análisis paisajístico oficial | No — requiere inspección visual o cartografía de paisaje |
| Consulta de visores de paisaje o catálogos regionles | No — sin acceso web |
| Verificación de compatibilidad urbanística | No — requiere consulta del planeamiento municipal |
| Cuantificación de empleo o renta | No — sin datos estadísticos |
| Valoración de impactos paisajísticos o socioeconómicos | No — Fase 6 |
| Compensación de impactos ambientales con factor socioeconómico | No — prohibido explícitamente |
| Consulta WMS/WMTS | No |
| Llamadas a APIs externas | No |
| Uso de IA | No |

---

## API pública

### `build_landscape_factor_from_phase_data(phase2_data, phase4_result, cartography_plan) → FactorInventory`

Construye FI-011 Paisaje.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| has_coords AND has_plan | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| has_coords XOR has_plan | ESTIMADO | CAMPO_RECOMENDADO | NO_CONSTA |
| Sin coords ni plan | PENDIENTE | NO_CONSTA | NO_CONSTA |

**Detección de coordenadas (`_has_location`)** — en orden:
1. `phase2_data.object_scope.coordenadas_wgs84` no vacío
2. `phase4_result.cartography_plan.center.lat` presente
3. `phase4_result.climate.selected_station` presente (proxy)

**Detección de plan** (`_get_effective_plan`): argumento externo → embebido en `phase4_result`.

**Mapas en plan** (`_has_maps_in_plan`): si `maps` es lista no vacía → se menciona CA-11 en `data_sources`.

**Gap fijo**: `GAP-FI-011-001` — criticidad MEDIA, resolución CAMPO, status PENDIENTE.  
**ready_for_impact_assessment**: siempre `False`.  
**Semáforo**: nunca VERDE.

---

### `build_socioeconomic_factor_from_phase_data(phase2_data, phase4_result) → FactorInventory`

Construye FI-013 Socioeconomía.

**Extracción de datos desde `phase2_data.object_scope`:**
- `titular` → has_promoter
- `operaciones_incluidas` → has_activity
- `coordenadas_wgs84` + fallback `_has_location(None, phase4_result)` → has_location

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore | ready |
|-----------|-----------------|------------|---------------------|-------|
| has_promoter AND has_activity AND has_location | DECLARADO | GABINETE_SUFICIENTE | AMARILLO | True |
| has_promoter AND has_activity, sin ubicación | DECLARADO | NO_CONSTA | AMARILLO | False |
| Sin promoter o sin actividad | PENDIENTE | NO_CONSTA | NO_CONSTA | False |

**Gaps:**
- `GAP-FI-013-001`: compatibilidad urbanística — siempre presente, criticidad MEDIA, GABINETE
- `GAP-FI-013-002`: datos promotor/actividad — solo si faltan, criticidad ALTA, GABINETE

**Semáforo**: manualmente AMARILLO si DECLARADO, NO_CONSTA si PENDIENTE. Nunca VERDE.

---

### `build_context_inventory_factors_from_phase_data(phase2_data, phase4_result, cartography_plan) → ContextInventoryBuildResult`

Construye ambos factores y los devuelve como `ContextInventoryBuildResult([FI-011, FI-013], warnings, notes)`.

---

### `merge_context_factors_into_summary(summary, context_factors) → InventorySummary`

Sustituye FI-011 y/o FI-013 en un `InventorySummary` sin mutar el original. Preserva orden canónico. Propaga warnings/notes del summary original.

---

## Dataclass `ContextInventoryBuildResult`

```python
@dataclass
class ContextInventoryBuildResult:
    factors: list[FactorInventory]   # [FI-011, FI-013]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict        # serializable a JSON
    def summary(self) -> str         # resumen legible para CLI/logs
```

---

## Integración con IV-02

`inventory_builder.build_inventory_from_phase4_data()` acepta ahora un parámetro opcional `phase2_data` e invoca IV-04 automáticamente tras IV-03:

```python
context_result = build_context_inventory_factors_from_phase_data(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
    cartography_plan=effective_cart,
)
summary = merge_context_factors_into_summary(summary, context_result.factors)
```

`build_inventory_from_phase4()` (cargador desde disco) busca automáticamente `control_interno/phase2_result.json` si existe y lo pasa como `phase2_data`.

---

## CLI

IV-04 no añade comando nuevo. Los factores enriquecidos se generan vía:

```bash
python run_expediente.py expediente-EIA-NAVE-222 inventory-build
python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
```

Con `--write`, los archivos en `inventario/` incluyen las fichas FI-011 y FI-013 enriquecidas con sus gaps visibles. Si existe `control_interno/phase2_result.json`, FI-013 se enriquece automáticamente con datos del promotor.

---

## Por qué FI-011 no se marca VERDE en modo offline

La evaluación del paisaje requiere análisis visual del entorno y consulta de cartografía de paisaje (catálogos de paisaje, atlas del paisaje, estudios de visibilidad). Los mapas esquemáticos offline de CA-10/CA-11 son orientativos y no sustituyen esas fuentes. El semáforo máximo offline es AMARILLO.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-011-001 | FI-011 | MEDIA | CAMPO | Siempre |
| GAP-FI-013-001 | FI-013 | MEDIA | GABINETE | Siempre |
| GAP-FI-013-002 | FI-013 | ALTA | GABINETE | Solo si faltan promotor o actividad |

---

## Reglas de prudencia aplicadas

- FI-011: no se formula juicio sobre calidad paisajística, fragilidad ni magnitud de alteración visual.
- FI-013: no se afirma generación de empleo ni cuantificación económica salvo que conste en documentación.
- FI-013: el factor socioeconómico no sustituye ni anula la valoración de impactos ambientales negativos.
- Ninguna descripción contiene: "sin afección", "sin impacto", "inexistente", "beneficio económico neto", "compensa".
- `ready_for_impact_assessment` de FI-011 siempre `False`.
- `inventory_semaphore` nunca `VERDE` para ninguno de los dos factores.

---

## Tests

**Archivo**: `tests/test_inventory_context_builder.py`  
**Tests**: 105 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestBuildLandscapeFactor` | 26 | FI-011: con/sin coords/plan, nunca VERDE, gap MEDIA CAMPO, data_sources |
| `TestBuildSocioeconomicFactor` | 25 | FI-013: con/sin promotor/actividad/coords, ready lógica, gaps, nunca VERDE |
| `TestContextInventoryBuildResult` | 8 | `to_dict`, JSON serializable, `summary()` |
| `TestBuildContextInventory` | 8 | 2 factores, FI-011 primero, FI-013 segundo |
| `TestMergeContextFactors` | 10 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 14 | FI-001/FI-005/FI-016/FI-011/FI-013 enriquecidos, write genera fichas con gaps |
| `TestPrudenceLexical` | 14 | Ausencia de patrones prohibidos en todas las variantes de entrada |

---

*Generado por EIA-Agent v2.1 — IV-04 — 2026-04-30*
