# INVENTORY_CLIMATE_CHANGE_BUILDER — IV-08

Constructor de factor FI-015 Cambio climático desde Fase 2/Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_climate_change_builder.py`  
**ID de productización**: IV-08  
**Completado**: 2026-05-01  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), CL-06 (`phase4_climate_pipeline`), OB-06 (`phase2_pipeline`, opcional)

---

## Qué hace IV-08

- Integra los datos climáticos de CL-06 (clasificación Koppen-Geiger, temperatura, precipitación, índice de aridez de Martonne) con la descripción de actividad/equipos de Fase 2 para construir FI-015.
- Detecta posibles fuentes de GEI a partir de términos en la descripción de actividad declarada: diesel, gasoil, combustión, generador, carretilla, camión, caldera, quemador, horno, etc.
- Detecta términos de vulnerabilidad climática en los datos disponibles: DANA, inundabilidad, sequía, aridez, altas temperaturas, etc.
- Construye la descripción de FI-015 con contexto climático del emplazamiento (estación de referencia, Koppen, temperatura, precipitación, Martonne, meses secos).
- Genera GAP-FI-015-001 (caracterización GEI) y GAP-FI-015-002 (análisis adaptación/vulnerabilidad).
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-08

| Capacidad | Estado |
|-----------|--------|
| Cuantificar emisiones GEI | No — requiere datos de consumo del promotor |
| Calcular huella de carbono | No |
| Verificar consumos energéticos o combustibles | No |
| Consultar inventarios de emisiones (PRTR, IPCC) | No — sin acceso web |
| Valorar el impacto climático | No — Fase 6 |
| Uso de IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### Funciones de detección y extracción

**`extract_climate_change_context(phase2_data, phase4_result, climate_result) → str`**  
Extrae texto relacionado con cambio climático/GEI de todos los datos disponibles. Devuelve cadena en minúsculas con el contenido relevante.

**`detect_ghg_relevant_sources(text) → list[str]`**  
Detecta términos de fuentes potenciales de GEI en texto de actividad. Devuelve lista sin duplicados en orden de aparición.

Términos detectados: `diesel`, `gasoil`, `combustion/combustión`, `motor`, `generador`, `carretilla`, `transporte`, `camion/camión`, `electricidad`, `potencia`, `consumo`, `compresor`, `maquinaria`, `furgoneta`, `vehiculo/vehículo`, `caldera`, `quemador`, `horno`, `incineracion/incineración`.

Términos de alta intensidad (→ ROJO_AMARILLO + GAP ALTA): `diesel`, `gasoil`, `combustion/combustión`, `generador`, `carretilla`, `camion/camión`, `caldera`, `quemador`, `horno`, `incineracion/incineración`.

**`detect_climate_vulnerability_terms(text) → list[str]`**  
Detecta términos de vulnerabilidad climática. Devuelve lista sin duplicados.

Términos: `dana`, `inundabilidad`, `sequia/sequía`, `aridez`, `altas temperaturas`, `calor extremo`, `precipitacion intensa`, `riesgo natural`, `escorrentia/escorrentía`, `ola de calor`, `tormenta`, `viento fuerte`, `granizo`, `inundacion/inundación`.

---

### `build_climate_change_factor_from_phase_data(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status |
|-----------|-----------------|
| Clima CL-06 + actividad declarada | DECLARADO |
| Solo clima CL-06 O solo actividad | ESTIMADO |
| Ni clima ni actividad | PENDIENTE |

**Lógica de semáforo:**

| Condición | inventory_semaphore |
|-----------|---------------------|
| PENDIENTE | NO_CONSTA |
| Términos de alta combustión (diesel/generador/caldera...) | ROJO_AMARILLO |
| Clima o actividad sin combustión de alta intensidad | AMARILLO |
| Nunca | VERDE |

**Lógica de field_mode:**

| Condición | field_mode |
|-----------|------------|
| PENDIENTE | NO_CONSTA |
| GHG terms detectados | CAMPO_RECOMENDADO |
| Clima + actividad sin GHG directo | GABINETE_SUFICIENTE |

**Gap GAP-FI-015-001**: criticidad ALTA si hay términos de alta combustión, MEDIA en otro caso. Resolución GABINETE. Siempre presente.

**Gap GAP-FI-015-002**: análisis adaptación/vulnerabilidad. MEDIA / GABINETE. Siempre presente.

**ready_for_impact_assessment**: `False` siempre. **Semáforo**: nunca VERDE.

---

### `build_climate_change_inventory_factor_from_phase4(...) → ClimateChangeInventoryBuildResult`

Construye FI-015 y lo devuelve como `ClimateChangeInventoryBuildResult`. Genera warnings si PENDIENTE o solo actividad disponible.

---

### `merge_climate_change_factor_into_summary(summary, factor) → InventorySummary`

Sustituye FI-015 en el summary sin mutar el original. `factor` es singular (`FactorInventory`, no lista). Preserva orden canónico.

---

## Integración con IV-02

Bloque añadido en `build_inventory_from_phase4_data()` tras IV-07:

```python
cc_result = build_climate_change_inventory_factor_from_phase4(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
    climate_result=effective_climate,
)
summary = merge_climate_change_factor_into_summary(summary, cc_result.factor)
summary.warnings.extend(cc_result.warnings)
summary.notes.extend(cc_result.notes)
```

Con datos climáticos de CL-06, FI-015 se enriquece a ESTIMADO o DECLARADO automáticamente.

---

## Por qué FI-015 no se marca VERDE en modo offline

- La caracterización de cambio climático requiere inventario de GEI con datos de consumo energético y combustibles aportados por el promotor.
- No puede concluirse "sin emisiones" ni "carbono neutro" sin datos cuantificados.
- El análisis de vulnerabilidad y adaptación requiere consulta al PNACC y normativa autonómica aplicable.
- La presencia de términos de combustión en la descripción de actividad genera un gap de ALTA criticidad que bloquea el semáforo VERDE.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-015-001 | FI-015 | ALTA (con combustión) o MEDIA | GABINETE | Siempre |
| GAP-FI-015-002 | FI-015 | MEDIA | GABINETE | Siempre |

---

## Reglas de prudencia aplicadas

- No se cuantifican emisiones ni huella de carbono.
- No se afirma "sin emisiones", "carbono neutro", "emisiones despreciables".
- No se afirma "impacto climático compatible", "riesgo climático bajo".
- No se usan términos de valoración de impacto: COMPATIBLE, MODERADO, SEVERO, CRÍTICO.
- `ready_for_impact_assessment` = `False` siempre.
- `inventory_semaphore` nunca `VERDE`.

---

## Tests

**Archivo**: `tests/test_inventory_climate_change_builder.py`  
**Tests**: 126 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestAuxiliaries` | 20 | `extract_climate_change_context`, `detect_ghg_relevant_sources`, `detect_climate_vulnerability_terms`: detección de diesel/generador/dana/sequía, sin crash con None |
| `TestBuildFI015FullData` | 17 | DECLARADO con clima + actividad + GHG: ROJO_AMARILLO, CAMPO_RECOMENDADO, 2 gaps, GAP-FI-015-001 ALTA, GAP-FI-015-002 MEDIA, ready=False |
| `TestBuildFI015ClimateOnly` | 14 | ESTIMADO con solo clima: AMARILLO, GABINETE_SUFICIENTE, descripción con Koppen/temperatura/precipitación/Martonne |
| `TestBuildFI015ActivityOnly` | 7 | ESTIMADO con solo actividad + GHG: ROJO_AMARILLO, CAMPO_RECOMENDADO |
| `TestBuildFI015HighGHG` | 5 | ROJO_AMARILLO con generador/caldera/camión, GAP ALTA con combustión, electricidad → MEDIA |
| `TestBuildFI015NoData` | 7 | PENDIENTE/NO_CONSTA/NO_CONSTA sin datos, 2 gaps, sin data_sources |
| `TestBuildFI015Description` | 9 | Koppen/Martonne/GHG disclaimer/vulnerabilidad/disclaimer preliminar en descripción |
| `TestClimateChangeResult` | 11 | `ClimateChangeInventoryBuildResult`: to_dict, JSON serializable, summary(), IV-08 en notes |
| `TestBuildWrapper` | 5 | Warning si PENDIENTE, note si solo clima, embedded climate desde phase4, warning si solo actividad sin clima |
| `TestMerge` | 9 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 15 | FI-015 DECLARADO, ROJO_AMARILLO, 2 gaps, IV-08 en notes, 16 factores, orden canónico, JSON serializable |
| `TestPrudenceLexical` | 8 | Ausencia de 14 patrones prohibidos, ready=False, semáforo nunca VERDE, sin términos de valoración de impacto |

---

*Generado por EIA-Agent v2.1 — IV-08 — 2026-05-01*
