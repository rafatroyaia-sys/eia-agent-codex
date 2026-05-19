# INVENTORY_RISK_BUILDER — IV-03

Constructor de factores FI-005 Inundabilidad y FI-016 Riesgos naturales desde Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_risk_builder.py`  
**ID de productización**: IV-03  
**Completado**: 2026-04-30  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), CA-10 (`cartography_plan`)

---

## Principio rector

IV-03 nunca afirma que un riesgo es inexistente ni que puede descartarse.  
Todo output lleva un gap de criticidad ALTA y `ready_for_impact_assessment=False`.  
El semáforo nunca es VERDE en modo offline.

---

## API pública

### `build_flood_risk_factor_from_phase4(phase4_result, cartography_plan=None) → FactorInventory`

Construye FI-005 Inundabilidad desde los outputs de Fase 4 offline.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Plan con mapa inundabilidad (MAP-006 o `"inundab"` en title/purpose/layers) | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Plan existe pero sin mapa inundabilidad | PENDIENTE | CAMPO_RECOMENDADO | NO_CONSTA |
| Sin plan | PENDIENTE | NO_CONSTA | NO_CONSTA |

**Detección del mapa**: `map_type == "inundabilidad_riesgos"` ó raíz `"inundab"` en title + purpose + required_layers (case-insensitive).  
**Gap fijo**: `GAP-FI-005-001` — criticidad ALTA, resolución GABINETE, status PENDIENTE.  
**ready_for_impact_assessment**: siempre `False`.

---

### `build_natural_risks_factor_from_phase4(phase4_result, cartography_plan=None) → FactorInventory`

Construye FI-016 Riesgos naturales desde los outputs de Fase 4 offline.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| has_coords + has_plan | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| has_coords, sin plan | ESTIMADO | CAMPO_RECOMENDADO | NO_CONSTA |
| Sin coords | PENDIENTE | NO_CONSTA | NO_CONSTA |

**Detección de coordenadas (`_has_coordinates`)** — comprueba en orden:
1. `cartography_plan.center.lat` (argumento externo)
2. `phase4_result.cartography_plan.center.lat` (embebido)
3. `phase4_result.climate.selected_station` (proxy: coordenadas se usaron para seleccionar la estación)

**Riesgos mínimos siempre mencionados en la descripción:**
1. Inundabilidad — SNCZI/RIESGOMAP
2. Incendio forestal — clasificación forestal
3. Sismicidad — NCSE-02
4. Episodios meteorológicos extremos — AEMET
5. Riesgo volcánico — si el ámbito territorial lo requiere

**Gap fijo**: `GAP-FI-016-001` — criticidad ALTA, resolución GABINETE, status PENDIENTE.  
**ready_for_impact_assessment**: siempre `False`.

---

### `build_risk_inventory_factors_from_phase4(phase4_result, cartography_plan=None) → RiskInventoryBuildResult`

Construye ambos factores (FI-005 y FI-016) y los devuelve como `RiskInventoryBuildResult`.  
Si no hay plan cartográfico en ninguna fuente, añade un warning de nivel de expediente.

---

### `merge_risk_factors_into_summary(summary, risk_factors) → InventorySummary`

Sustituye FI-005 y/o FI-016 en un `InventorySummary` existente sin mutar el original.

- Preserva el orden canónico de 16 factores.
- Propaga `summary.warnings` y `summary.notes` al nuevo summary.
- No introduce duplicados.

---

## Dataclass `RiskInventoryBuildResult`

```python
@dataclass
class RiskInventoryBuildResult:
    factors: list[FactorInventory]   # [FI-005, FI-016]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict        # serializable a JSON
    def summary(self) -> str         # resumen legible para CLI/logs
```

---

## Integración con IV-02

`inventory_builder.build_inventory_from_phase4_data()` invoca IV-03 automáticamente tras construir los 16 factores base:

```python
risk_result = build_risk_inventory_factors_from_phase4(phase4_result, effective_cart)
summary = merge_risk_factors_into_summary(summary, risk_result.factors)
summary.warnings.extend(risk_result.warnings)
summary.notes.extend(risk_result.notes)
```

No es necesario invocar IV-03 directamente desde el CLI; `inventory-build` ya lo incluye.

---

## CLI

IV-03 no añade comando nuevo. Los factores enriquecidos se generan vía:

```bash
python run_expediente.py expediente-EIA-NAVE-222 inventory-build
python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
```

Con `--write`, los archivos generados en `inventario/` incluyen las fichas FI-005 e FI-016 enriquecidas, con los gaps GAP-FI-005-001 y GAP-FI-016-001 visibles.

---

## Reglas de prudencia aplicadas

- Ninguna descripción afirma "sin riesgo", "riesgo nulo", "no existe riesgo" ni cierra ningún riesgo como inexistente.
- La verificación con SNCZI, RIESGOMAP, IGME, AEMET y organismos autonómicos siempre queda pendiente.
- `ready_for_impact_assessment` es siempre `False` hasta verificación oficial.
- `inventory_semaphore` nunca es `VERDE` en modo offline.

---

## Restricciones de diseño

- No consulta SNCZI, WMS, WMTS ni ninguna API externa.
- No verifica riesgo real.
- No valora impactos ni genera outputs de Fase 6.
- No usa IA ni llamadas a modelos de lenguaje.
- Determinista: mismo input → mismo output.

---

## Tests

**Archivo**: `tests/test_inventory_risk_builder.py`  
**Tests**: 99 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestBuildFloodRiskFactor` | 26 | FI-005: con/sin plan, con/sin mapa inundabilidad, nunca VERDE, gap ALTA, prudencia léxica |
| `TestBuildNaturalRisksFactor` | 23 | FI-016: con coords+plan / solo coords / sin coords, 5 riesgos mínimos en descripción |
| `TestRiskInventoryBuildResult` | 8 | `to_dict`, JSON serializable, `summary()` |
| `TestBuildRiskInventory` | 8 | 2 factores, FI-005 primero, FI-016 segundo |
| `TestMergeRiskFactors` | 10 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 13 | FI-005/FI-016 enriquecidos en el pipeline completo, gaps visibles en `--write` |
| `TestPrudenceLexical` | 11 | Ausencia de "sin riesgo"/"riesgo nulo"/"no existe riesgo" en todas las salidas |

---

*Generado por EIA-Agent v2.1 — IV-03 — 2026-04-30*
