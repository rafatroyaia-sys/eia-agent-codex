# INVENTORY_PRESSURE_BUILDER — IV-05

Constructor de factores FI-006 Calidad del aire y FI-014 Ruido desde Fase 2/Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_pressure_builder.py`  
**ID de productización**: IV-05  
**Completado**: 2026-04-30  
**Dependencias**: IV-00 (`inventory_model`), OB-06 (`phase2_pipeline`), F4-01 (`phase4_offline_pipeline`)

---

## Qué hace IV-05

- Extrae texto de actividad desde `operaciones_incluidas` de Fase 2 (y fallback en Fase 4).
- Detecta mediante coincidencia de términos las operaciones con potencial de emisión de polvo/gases (FI-006) y con potencial de generación de ruido (FI-014).
- Construye FI-006 Calidad del aire con semáforo ROJO_AMARILLO si alta presión sin filtración, AMARILLO en otros casos con operaciones detectadas.
- Construye FI-014 Ruido con semáforo ROJO_AMARILLO y `field_mode=CAMPO_NECESARIO` si maquinaria de alto impacto acústico, AMARILLO con `field_mode=CAMPO_RECOMENDADO` si ruido moderado.
- Deja en ambos factores los gaps de seguimiento obligatorios visibles.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-05

| Capacidad | Estado |
|-----------|--------|
| Medición real de emisiones o niveles sonoros | No — requiere instrumental de campo |
| Verificación de cumplimiento normativo (emisiones/ruido) | No — requiere normativa sectorial y medición |
| Consulta WMS/WMTS | No |
| Llamadas a APIs externas | No |
| Uso de IA | No |
| Valoración de impactos (moderado/severo/crítico) | No — Fase 6 |
| Afirmar "sin emisiones", "sin ruido", "sin afección acústica" | Prohibido explícitamente |

---

## API pública

### `extract_activity_text(phase2_data, phase4_result) → str`

Extrae texto de actividad en minúsculas para detección de términos.

**Prioridad de extracción:**
1. `phase2_data.object_scope.operaciones_incluidas` (lista o string)
2. `phase2_data.object_scope.descripcion_actividad`
3. `phase2_data.object_scope.denominacion`
4. Fallback: `phase4_result.object_scope.operaciones_incluidas`

Devuelve `""` si todo es `None` o vacío.

---

### `detect_air_quality_relevant_operations(text) → list[str]`

Detecta términos de emisión de polvo/gases en el texto de actividad.

**Términos de alta presión** (activan ROJO_AMARILLO si no hay filtración):
`tritura`, `cribado`, `criba`, `machaca`, `molino`, `molienda`, `corte`, `cortar`, `serrar`, `aserrado`, `demolic`, `voladura`

**Términos de filtración** (mitigan la clasificación):
`filtro`, `filtracion`, `aspiracion`, `extraccion`, `captacion de polvo`, `depurador`, `scrubber`, `ciclone`, `manga`, `electrostatico`, `biofiltro`

---

### `detect_noise_relevant_operations(text) → list[str]`

Detecta términos de generación de ruido en el texto de actividad.

**Términos de alta presión acústica** (activan ROJO_AMARILLO/CAMPO_NECESARIO):
`tritura`, `molino`, `molienda`, `cizalla`, `prensa`, `compresor`, `generador`, `diesel`, `gasoil`, `maquinaria pesada`, `percusion`, `impacto`, `martillo`, `demolic`, `voladura`

---

### `build_air_quality_factor_from_phase_data(phase2_data, phase4_result) → FactorInventory`

Construye FI-006 Calidad del aire.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin términos detectados | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Términos detectados, sin alta presión | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Alta presión + filtración | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Alta presión sin filtración | ESTIMADO | CAMPO_RECOMENDADO | ROJO_AMARILLO |

**Gaps:**
- `GAP-FI-006-001`: medición de calidad del aire — siempre, ALTA, CAMPO
- `GAP-FI-006-002`: sistema de control de emisiones — solo si alta presión sin filtro, ALTA, GABINETE

**ready_for_impact_assessment**: siempre `False`.  
**Semáforo**: nunca VERDE.

---

### `build_noise_factor_from_phase_data(phase2_data, phase4_result) → FactorInventory`

Construye FI-014 Ruido.

**Lógica de evidencia:**

| Condición | evidence_status | field_mode | inventory_semaphore |
|-----------|-----------------|------------|---------------------|
| Sin términos detectados | PENDIENTE | NO_CONSTA | NO_CONSTA |
| Términos sin alta presión acústica | ESTIMADO | CAMPO_RECOMENDADO | AMARILLO |
| Alta presión acústica | ESTIMADO | CAMPO_NECESARIO | ROJO_AMARILLO |

**Gaps:**
- `GAP-FI-014-001`: medición acústica — siempre; ALTA/CAMPO si alta presión; MEDIA/CAMPO si media
- `GAP-FI-014-002`: horario operación y receptores — solo si alta presión, MEDIA, GABINETE

**ready_for_impact_assessment**: siempre `False`.  
**Semáforo**: nunca VERDE.

---

### `build_pressure_inventory_factors_from_phase_data(phase2_data, phase4_result) → PressureInventoryBuildResult`

Construye ambos factores y los devuelve como `PressureInventoryBuildResult([FI-006, FI-014], warnings, notes)`.

---

### `merge_pressure_factors_into_summary(summary, pressure_factors) → InventorySummary`

Sustituye FI-006 y/o FI-014 en un `InventorySummary` sin mutar el original. Preserva orden canónico. Propaga warnings/notes del summary original.

---

## Dataclass `PressureInventoryBuildResult`

```python
@dataclass
class PressureInventoryBuildResult:
    factors: list[FactorInventory]   # [FI-006, FI-014]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict        # serializable a JSON
    def summary(self) -> str         # resumen legible para CLI/logs
```

---

## Integración con IV-02

`inventory_builder.build_inventory_from_phase4_data()` invoca IV-05 automáticamente tras IV-04:

```python
pressure_result = build_pressure_inventory_factors_from_phase_data(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
)
summary = merge_pressure_factors_into_summary(summary, pressure_result.factors)
```

Si no hay `phase2_data`, FI-006 y FI-014 quedan en estado PENDIENTE/NO_CONSTA.

---

## CLI

IV-05 no añade comando nuevo. Los factores enriquecidos se generan vía:

```bash
python run_expediente.py expediente-EIA-NAVE-222 inventory-build
python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
```

Con `--write`, los archivos en `inventario/` incluyen las fichas FI-006 y FI-014 enriquecidas con sus gaps visibles. Si existe `control_interno/phase2_result.json` con `operaciones_incluidas`, ambos factores se enriquecen automáticamente.

---

## Por qué FI-006 y FI-014 nunca se marcan VERDE en modo offline

La caracterización de la calidad del aire y del entorno acústico requiere mediciones instrumentales de campo (analizadores de partículas, sonómetros). Los términos detectados en texto de operaciones son orientativos y no permiten descartar afección. El semáforo máximo offline es AMARILLO.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-006-001 | FI-006 | ALTA | CAMPO | Siempre |
| GAP-FI-006-002 | FI-006 | ALTA | GABINETE | Solo si alta presión sin filtro |
| GAP-FI-014-001 | FI-014 | ALTA o MEDIA | CAMPO | Siempre (ALTA si alta presión) |
| GAP-FI-014-002 | FI-014 | MEDIA | GABINETE | Solo si alta presión acústica |

---

## Reglas de prudencia aplicadas

- FI-006: no se afirma "sin emisiones", "no hay polvo", "sin afección a la calidad del aire".
- FI-014: no se afirma "sin ruido", "cumple límites", "sin afección acústica", "impacto compatible".
- Ninguna descripción contiene términos de valoración de impacto: "moderado", "severo", "crítico".
- `ready_for_impact_assessment` = `False` siempre para ambos factores.
- `inventory_semaphore` nunca `VERDE` para ninguno de los dos factores.
- La detección de filtración reduce el semáforo de ROJO_AMARILLO a AMARILLO en FI-006, pero no elimina el gap ni marca el factor como apto para evaluación.

---

## Tests

**Archivo**: `tests/test_inventory_pressure_builder.py`  
**Tests**: 120 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestExtractActivityText` | 10 | Extracción de texto desde phase2/phase4, minúsculas, fallbacks, ops como string |
| `TestDetectAirQualityOperations` | 10 | Detección de términos de emisión, sin falsos positivos, sin duplicados |
| `TestDetectNoiseOperations` | 10 | Detección de términos de ruido, sin falsos positivos, sin duplicados |
| `TestBuildAirQualityFactor` | 20 | FI-006: sin ops → PENDIENTE, alta presión sin filtro → ROJO_AMARILLO, con filtro → AMARILLO, gaps, ready=False, nunca VERDE |
| `TestBuildNoiseFactor` | 20 | FI-014: sin ops → PENDIENTE, alta presión → ROJO_AMARILLO/CAMPO_NECESARIO, media → AMARILLO/CAMPO_RECOMENDADO, gaps, ready=False, nunca VERDE |
| `TestPressureInventoryBuildResult` | 8 | `to_dict`, JSON serializable, `summary()`, warnings/notes |
| `TestBuildPressureInventory` | 7 | 2 factores, FI-006 primero, FI-014 segundo, warnings si PENDIENTE |
| `TestMergePressureFactors` | 8 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original, preserva warnings |
| `TestIntegrationWithIV02` | 13 | FI-001/FI-006/FI-014 enriquecidos, filtro reduce riesgo, notas IV-05 en resultado |
| `TestPrudenceLexical` | 14 | Ausencia de patrones prohibidos en todas las variantes de entrada |

---

*Generado por EIA-Agent v2.1 — IV-05 — 2026-04-30*
