# INVENTORY_PHYSICAL_BUILDER — IV-07

Constructor de factores FI-002 Geología, FI-003 Suelos y FI-004 Hidrología desde Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_physical_builder.py`  
**ID de productización**: IV-07  
**Completado**: 2026-05-01  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), CA-10 (`cartography_plan`), CA-11 (`schematic_maps`), OB-06 (`phase2_pipeline`, opcional)

---

## Qué hace IV-07

- Detecta si el plan cartográfico offline incluye fuentes geológicas (IGME/GEODE via MAP-006 source_candidates), cartografía de usos del suelo (MAP-005, capa `usos_suelo`) e información hidrológica/de drenaje (MAP-006, capas `inundabilidad`/`drenaje`).
- Construye FI-002 Geología con ESTIMADO/AMARILLO si hay plan cartográfico o ubicación disponible.
- Construye FI-003 Suelos con ESTIMADO/AMARILLO si hay plan o ubicación disponible.
- Construye FI-004 Hidrología con ESTIMADO/AMARILLO si hay plan o ubicación; el gap sube a criticidad ALTA si hay fuente hidrológica planificada (MAP-006).
- Deja en los tres factores los gaps de verificación oficial visibles.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-07

| Capacidad | Estado |
|-----------|--------|
| Consulta IGME / GEODE | No — sin acceso web |
| Consulta SIGPAC / catastro | No — sin acceso web |
| Consulta SNCZI / red hidrológica oficial | No — sin acceso web |
| Verificar cartografía geológica oficial | No |
| Verificar estado real del suelo | No — requiere inspección visual |
| Verificar presencia/ausencia de cauces o barrancos | No — requiere fuente oficial |
| Acreditar contaminación o impermeabilización del suelo | No |
| Valoración de impactos | No — Fase 6 |
| Uso de IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### Funciones de detección

**`has_geology_source_planned(cartography_plan) → bool`**  
Detecta en los MapSpec del plan fuentes o capas con términos: `geolog*`, `litolog*`, `igme`, `geode`, `riesgos geol*`.

**`has_soil_source_planned(cartography_plan) → bool`**  
Detecta: `usos_suelo`, `sigpac`, `corine`, `siose`, `edafolog*`, `map-005`.

**`has_hydrology_source_planned(cartography_plan) → bool`**  
Detecta: `inundab*`, `drenaje`, `hidrol*`, `cauce`, `barranco`, `escorrent*`, `snczi`, `map-006`.

**`extract_physical_context(phase2_data, phase4_result, cartography_plan) → str`**  
Extrae texto relacionado con los tres dominios físicos de todos los datos disponibles. Devuelve cadena en minúsculas.

---

### `build_geology_factor_from_phase4(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin plan ni ubicación | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Con plan o ubicación | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |

**Gap**: `GAP-FI-002-001` — MEDIA, GABINETE, siempre.  
**ready_for_impact_assessment**: `False` siempre. **Semáforo**: nunca VERDE.

---

### `build_soil_factor_from_phase4(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin plan ni ubicación | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Con plan o ubicación | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |

**Gap**: `GAP-FI-003-001` — MEDIA, **CAMPO**, siempre (requiere inspección visual).  
**ready_for_impact_assessment**: `False` siempre. **Semáforo**: nunca VERDE.

---

### `build_hydrology_factor_from_phase4(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin plan ni ubicación | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Con plan o ubicación | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |

**Gap**: `GAP-FI-004-001` — **ALTA** si hay fuente hidrológica planificada (MAP-006/inundabilidad/drenaje); MEDIA en otro caso. GABINETE siempre.  
**ready_for_impact_assessment**: `False` siempre. **Semáforo**: nunca VERDE.

---

### `build_physical_inventory_factors_from_phase4(...) → PhysicalInventoryBuildResult`

Construye los tres factores. Si `cartography_plan` es `None`, busca el plan embebido en `phase4_result.cartography_plan`.

---

### `merge_physical_factors_into_summary(summary, physical_factors) → InventorySummary`

Sustituye FI-002, FI-003 y/o FI-004 en el summary sin mutar el original. Preserva orden canónico.

---

## Integración con IV-02

Bloque añadido en `build_inventory_from_phase4_data()` tras IV-06:

```python
physical_result = build_physical_inventory_factors_from_phase4(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
    cartography_plan=effective_cart,
)
summary = merge_physical_factors_into_summary(summary, physical_result.factors)
```

Con cualquier plan cartográfico disponible (incluyendo el embebido en `phase4_result`), FI-002, FI-003 y FI-004 se enriquecen automáticamente a ESTIMADO/AMARILLO.

---

## Por qué FI-002, FI-003 y FI-004 no se marcan VERDE en modo offline

- **FI-002**: La caracterización geológica requiere consulta al Mapa Geológico de España (IGME/GEODE) o equivalente autonómico. Los mapas de riesgos geológicos del plan offline son orientativos.
- **FI-003**: El estado real del suelo (sellado, degradación, contaminación) requiere inspección visual o fuente oficial actualizada (SIGPAC, Corine LC). No puede determinarse solo desde cartografía de usos del suelo offline.
- **FI-004**: La red de drenaje, cauces y escorrentía requiere verificación con el SNCZI o el organismo de cuenca competente. No puede concluirse la ausencia de cauces o conectividad hídrica sin fuente oficial.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-002-001 | FI-002 | MEDIA | GABINETE | Siempre |
| GAP-FI-003-001 | FI-003 | MEDIA | CAMPO | Siempre |
| GAP-FI-004-001 | FI-004 | ALTA (con hidrología) o MEDIA | GABINETE | Siempre |

---

## Reglas de prudencia aplicadas

- FI-002: no se afirma "geología sin interés", "terreno estable" ni "sin afección geológica".
- FI-003: no se afirma "suelo sin afección", "sin contaminación" ni "suelo impermeabilizado".
- FI-004: no se afirma "no hay cauces", "sin escorrentía", "sin conectividad hídrica" ni "sin afección hidrológica".
- Ninguna descripción contiene términos de valoración de impacto: "moderado", "severo", "crítico".
- `ready_for_impact_assessment` = `False` siempre.
- `inventory_semaphore` nunca `VERDE`.

---

## Tests

**Archivo**: `tests/test_inventory_physical_builder.py`  
**Tests**: 119 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestAuxiliaries` | 19 | `extract_physical_context`, `has_geology/soil/hydrology_source_planned`: detección de MAP-005/MAP-006/IGME, sin crash con None |
| `TestBuildGeologyFactor` | 17 | FI-002: ESTIMADO con plan/ubicación, PENDIENTE sin datos, AMARILLO, nunca VERDE, gap MEDIA/GABINETE, ready=False |
| `TestBuildSoilFactor` | 15 | FI-003: idem + gap MEDIA/CAMPO, mención de SIGPAC/Corine |
| `TestBuildHydrologyFactor` | 17 | FI-004: gap ALTA con MAP-006, gap MEDIA sin hidrología, GABINETE, mención de SNCZI/drenaje |
| `TestPhysicalBuildResult` | 11 | `to_dict`, JSON serializable, `summary()`, 3 factores en orden |
| `TestBuildCombined` | 7 | 3 factores, warnings si PENDIENTE, IV-07 en notas, plan embebido |
| `TestMerge` | 9 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 15 | FI-001/FI-002/FI-003/FI-004 enriquecidos, gaps presentes, IV-07 en notas, 16 factores, orden |
| `TestPrudenceLexical` | 9 | Ausencia de 17 patrones prohibidos en todas las variantes |

---

*Generado por EIA-Agent v2.1 — IV-07 — 2026-05-01*
