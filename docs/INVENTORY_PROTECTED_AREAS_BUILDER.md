# INVENTORY_PROTECTED_AREAS_BUILDER — IV-06

Constructor de factores FI-009 Espacios Naturales Protegidos y FI-010 Red Natura 2000 desde Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_protected_areas_builder.py`  
**ID de productización**: IV-06  
**Completado**: 2026-04-30  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), CA-10 (`cartography_plan`), CA-11 (`schematic_maps`)

---

## Qué hace IV-06

- Detecta si el plan cartográfico offline incluye MAP-004 (Red Natura 2000 / ENP) o capas `red_natura_2000` / `espacios_naturales_protegidos`.
- Construye FI-009 Espacios Naturales Protegidos con ESTIMADO/AMARILLO si hay plan cartográfico, PENDIENTE/NO_CONSTA si no hay datos.
- Construye FI-010 Red Natura 2000 con ESTIMADO/AMARILLO si hay plan cartográfico, PENDIENTE/NO_CONSTA si no hay datos.
- Deja en ambos factores el gap de verificación oficial obligatorio (ALTA/GABINETE) siempre visible.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-06

| Capacidad | Estado |
|-----------|--------|
| Consulta WMS/WMTS oficial (Grafcan, MITERD, IECA, REDIAM) | No — sin acceso web |
| Verificación de presencia/ausencia real de ENP | No — requiere fuente oficial |
| Verificación de presencia/ausencia real de Red Natura 2000 | No — requiere WMS/WMTS oficial |
| Conclusión de ausencia de afección apreciable | No — prohibido explícitamente |
| Activar o descartar evaluación de repercusiones | No — corresponde al órgano ambiental |
| Valoración de impactos | No — Fase 6 |
| Uso de IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### `has_red_natura_map_planned(cartography_plan) → bool`

Devuelve `True` si el plan cartográfico contiene un mapa de Red Natura 2000. Detecta:
- `map_type == "red_natura_enp"`
- `map_id == "MAP-004"`
- `required_layers` contiene `"red_natura_2000"`

### `has_enp_map_planned(cartography_plan) → bool`

Devuelve `True` si el plan cartográfico contiene un mapa de ENP. Detecta:
- `map_type == "red_natura_enp"`
- `map_id == "MAP-004"`
- `required_layers` contiene `"espacios_naturales_protegidos"`

### `extract_protected_area_context(phase4_result, cartography_plan) → str`

Extrae texto relacionado con ENP/Red Natura de los datos de Fase 4. Busca menciones a: Red Natura, LIC, ZEC, ZEPA, ENP, espacio natural/protegido, parque natural/nacional, reserva natural, MAP-004. Devuelve cadena en minúsculas.

---

### `build_enp_factor_from_phase4(phase4_result, cartography_plan) → FactorInventory`

Construye FI-009 Espacios Naturales Protegidos.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin plan cartográfico | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Con plan (sin MAP-004) | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Con plan y MAP-004 | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |

**Gap fijo**: `GAP-FI-009-001` — criticidad ALTA, resolución GABINETE, status PENDIENTE.  
**ready_for_impact_assessment**: siempre `False`.  
**Semáforo**: nunca VERDE.

---

### `build_red_natura_factor_from_phase4(phase4_result, cartography_plan) → FactorInventory`

Construye FI-010 Red Natura 2000.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin plan cartográfico | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Con plan (sin MAP-004) | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Con plan y MAP-004 | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |

**Gap fijo**: `GAP-FI-010-001` — criticidad ALTA, resolución GABINETE, status PENDIENTE.  
**ready_for_impact_assessment**: siempre `False`.  
**Semáforo**: nunca VERDE.

---

### `build_protected_areas_inventory_factors_from_phase4(...) → ProtectedAreasInventoryBuildResult`

Construye ambos factores. Si `cartography_plan` es `None`, busca el plan embebido en `phase4_result.cartography_plan`.

---

### `merge_protected_area_factors_into_summary(summary, protected_factors) → InventorySummary`

Sustituye FI-009 y/o FI-010 en un `InventorySummary` sin mutar el original. Preserva orden canónico. Propaga warnings/notes del summary original.

---

## Dataclass `ProtectedAreasInventoryBuildResult`

```python
@dataclass
class ProtectedAreasInventoryBuildResult:
    factors: list[FactorInventory]   # [FI-009, FI-010]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict        # serializable a JSON
    def summary(self) -> str         # resumen legible para CLI/logs
```

---

## Integración con IV-02

`inventory_builder.build_inventory_from_phase4_data()` invoca IV-06 automáticamente tras IV-05:

```python
protected_result = build_protected_areas_inventory_factors_from_phase4(
    phase4_result=phase4_result,
    cartography_plan=effective_cart,
)
summary = merge_protected_area_factors_into_summary(summary, protected_result.factors)
```

Si hay `cartography_plan` (incluido el plan embebido en `phase4_result`), FI-009 y FI-010 se enriquecen automáticamente a ESTIMADO/AMARILLO.

---

## CLI

IV-06 no añade comando nuevo. Los factores enriquecidos se generan vía:

```bash
python run_expediente.py expediente-EIA-NAVE-222 inventory-build
python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
```

Con `--write`, los archivos en `inventario/` incluyen las fichas FI-009 y FI-010 con sus gaps visibles.

---

## Por qué FI-009 y FI-010 no se marcan VERDE en modo offline

La verificación de ENP y Red Natura 2000 requiere consulta a fuentes oficiales actualizadas (Grafcan IdeCAN, IECA, REDIAM, Banco de Datos de la Naturaleza del MITERD). Los mapas esquemáticos offline de CA-10/CA-11 son orientativos y no sustituyen esas fuentes. La decisión sobre la necesidad de evaluación de repercusiones corresponde al órgano ambiental, no al promotor ni al sistema. El semáforo máximo offline es AMARILLO.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-009-001 | FI-009 | ALTA | GABINETE | Siempre |
| GAP-FI-010-001 | FI-010 | ALTA | GABINETE | Siempre |

---

## Reglas de prudencia aplicadas

- FI-009: no se afirma "no hay ENP", "fuera de espacios protegidos" ni "sin afección".
- FI-010: no se afirma "no hay Red Natura", "sin afección apreciable" ni "sin afección significativa".
- Ninguna descripción contiene términos de valoración de impacto: "moderado", "severo", "crítico".
- La decisión sobre evaluación de repercusiones (art. 46 Ley 21/2013) corresponde al órgano ambiental competente.
- `ready_for_impact_assessment` = `False` siempre para ambos factores.
- `inventory_semaphore` nunca `VERDE` para ninguno de los dos factores.

---

## Tests

**Archivo**: `tests/test_inventory_protected_areas_builder.py`  
**Tests**: 108 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestDetectors` | 12 | `has_red_natura_map_planned` y `has_enp_map_planned`: MAP-004, map_type, capas, None, vacío |
| `TestExtractContext` | 10 | Extracción de texto, LIC/ZEC/ZEPA, minúsculas, sin crash con None/vacío |
| `TestBuildEnpFactor` | 17 | FI-009: ESTIMADO con plan, PENDIENTE sin plan, AMARILLO, nunca VERDE, gap ALTA, ready=False, fuente oficial en descripción |
| `TestBuildRedNaturaFactor` | 16 | FI-010: ESTIMADO con plan, PENDIENTE sin plan, AMARILLO, nunca VERDE, gap ALTA, órgano ambiental en descripción |
| `TestProtectedAreasResult` | 9 | `to_dict`, JSON serializable, `summary()`, warnings/notes |
| `TestBuildCombined` | 8 | 2 factores, FI-009 primero, FI-010 segundo, warnings si PENDIENTE, plan embebido en phase4 |
| `TestMerge` | 8 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original, preserva warnings |
| `TestIntegrationWithIV02` | 15 | FI-001/FI-009/FI-010 enriquecidos, FI-001 por clima, gaps presentes, IV-06 en notas |
| `TestPrudenceLexical` | 13 | Ausencia de patrones prohibidos, órgano ambiental, sin términos de valoración, nunca VERDE |

---

*Generado por EIA-Agent v2.1 — IV-06 — 2026-04-30*
