# PVA_COVERAGE_VALIDATOR — IM-07

Validador determinístico de cobertura PVA para Fase 6 EIA.

**Módulo**: `src/eia_agent/core/pva_coverage_validator.py`  
**ID de productización**: IM-07  
**Completado**: 2026-05-10  
**Dependencias**: IM-00 (`impact_model`), IM-06 (`pva_generator` — precondición de uso, no de importación)

---

## Decisión de ID (2026-05-10)

| ID | Función | Estado |
|----|---------|--------|
| IM-06 | Generador de fichas PVA (`pva_generator.py`) | COMPLETADO ✅ |
| **IM-07** | **Validador de cobertura PVA (este módulo)** | **COMPLETADO ✅** |
| IM-08 | Reservado — template C.5 efectos acumulativos/sinérgicos | PENDIENTE |

El ítem "cadenas condicionales código" (IM-07 en el backlog original, IM-07 en la matriz maestra) queda pendiente de re-asignación de ID por el usuario. Este módulo ocupa la posición IM-07 por decisión explícita.

---

## Qué hace IM-07

- Lee un `Phase6Model` con impactos, medidas y `pva_programs`.
- Determina si cada impacto requiere cobertura PVA según reglas metodológicas.
- Busca cobertura: directa (en `target_impact_ids`), por factor (mismo FI), transversal (nota declarada).
- Clasifica cada impacto en: cubierto / sin cobertura / cobertura condicional / ignorado.
- Genera incidencias tipificadas (ERROR / WARNING / INFO) con recomendaciones.
- Produce un informe JSON y un markdown estructurado.
- Se expone como comando CLI `phase6-validate-pva [--write]`.

---

## Qué NO hace IM-07

| Capacidad | Estado |
|-----------|--------|
| Generar fichas PVA | No — eso es IM-06 |
| Modificar impactos o sus significancias | No — función pura |
| Modificar medidas | No |
| Valorar impactos (Conesa) | No — eso es IM-01 |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Redactar bloques A-K | No |
| Modificar expedientes piloto | No |

---

## API pública

### `impact_requires_pva(impact: EnvironmentalImpact) -> bool`

Determina si un impacto necesita cobertura PVA.

**Reglas (en orden de precedencia):**

| Condición | Resultado |
|-----------|-----------|
| `status == DESCARTADO_JUSTIFICADO` | False siempre |
| `nature == NEGATIVO` + status relevante + significancia relevante | **True** |
| `status == INDETERMINADO` + receptor sensible (FR-007/008/009/010/012) | **True** |
| `nature == POSITIVO` | False (genera WARNING si hay data_gaps) |
| `nature == MIXTO` + status y significancia relevantes | **True** |
| Otros casos | False |

**Status relevantes**: IDENTIFICADO, VALORADO, INDETERMINADO, PENDIENTE_DATOS.  
**Significancias relevantes**: COMPATIBLE, MODERADO, SEVERO, CRITICO, INDETERMINADO, NO_VALORADO.

---

### `find_pva_coverage_for_impact(impact, pva_programs) -> list[PVAProgram]`

Devuelve los PVAs que proporcionan cobertura para el impacto.

**Tipos de cobertura detectados:**

| Tipo | Condición |
|------|-----------|
| `DIRECT` | `impact.impact_id` en `pva.target_impact_ids` (PVA no es revisión anual) |
| `BY_FACTOR` | `pva.factor_id == FI-equivalente(receptor)` e impacto no en targets |
| `TRANSVERSAL` | PVA con nota de cobertura global + factor coincide |

**La revisión anual global NO cuenta como cobertura específica.** Se detecta por `"revision" + "anual"` en el nombre del PVA.

---

### `validate_pva_coverage(model: Phase6Model) -> PVACoverageResult`

Función principal. Clasifica cada impacto:

| Resultado | Condición | Severidad |
|-----------|-----------|-----------|
| `covered_impact_ids` | Cobertura DIRECT no condicionada | — |
| `conditional_coverage_ids` | Solo DIRECT condicionado (CONT) o BY_FACTOR | WARNING |
| `uncovered_impact_ids` | Sin ninguna cobertura | **ERROR** |
| `ignored_impact_ids` | DESCARTADO o POSITIVO sin data_gaps | INFO |

`is_valid()` devuelve `True` si `error_count() == 0`.

---

### `build_pva_coverage_markdown(result) -> str`

Genera informe markdown con 7 secciones:
1. Resumen
2. Impactos cubiertos
3. Impactos sin cobertura (GAP-PVA)
4. Coberturas condicionadas
5. Impactos ignorados
6. Incidencias y recomendaciones
7. Notas de trazabilidad

---

### `validate_pva_coverage_from_json(path) -> PVACoverageResult`

Carga un JSON de Phase6Model y ejecuta la validación.

```python
result = validate_pva_coverage_from_json(
    "expediente-EIA-XXX/impactos/phase6_model_with_pva.json"
)
```

Lanza `FileNotFoundError` si el archivo no existe, `ValueError` si el JSON es inválido.

---

### `write_pva_coverage_outputs(result, output_dir) -> tuple[Path, Path]`

Escribe los resultados en el directorio indicado:
- `pva_coverage_result.json` — resultado estructurado
- `pva_coverage_result.md` — informe legible

---

## Códigos de incidencia

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| `PVA-COV-E001` | ERROR | Impacto negativo/mixto/sensible sin ninguna cobertura PVA |
| `PVA-COV-W001` | WARNING | Cobertura directa pero PVA CONDICIONADO por CONT (E-9) |
| `PVA-COV-W002` | WARNING | Cobertura solo por factor o transversal (no en target_impact_ids) |
| `PVA-COV-W003` | WARNING | Impacto POSITIVO con data_gaps activos (umbral posiblemente provisional) |
| `PVA-COV-I001` | INFO | Impacto ignorado: no requiere PVA (POSITIVO sin gaps, o no cumple reglas) |
| `PVA-COV-I002` | INFO | Impacto ignorado: DESCARTADO_JUSTIFICADO |
| `PVA-COV-I003` | INFO | Modelo sin impactos |
| `PVA-COV-I004` | INFO | Modelo sin fichas PVA |

---

## Cobertura directa vs por factor vs transversal

| Tipo | Fiabilidad | Ejemplo |
|------|-----------|---------|
| DIRECT | Alta — impacto listado en `target_impact_ids` | PVA-001 incluye IMP-003 en su lista |
| BY_FACTOR | Media — PVA del mismo factor FI-XXX cubre el FR-XXX del impacto | PVA de FI-014 cubre IMP en FR-014 |
| TRANSVERSAL | Baja — PVA con nota de cobertura global | PVA con "cubre indirectamente" en notes |

La cobertura BY_FACTOR y TRANSVERSAL generan WARNING (no ERROR): existen pero no están declaradas formalmente en `target_impact_ids`. La recomendación es siempre añadir el impacto a `target_impact_ids` de la ficha correspondiente.

---

## Tratamiento de impactos positivos

Los impactos `POSITIVO` no requieren PVA por defecto. Sin embargo:

- **Sin data_gaps**: ignorados con INFO.
- **Con data_gaps**: ignorados pero con WARNING `PVA-COV-W003`. Se recomienda verificar que el PVA de eficacia (si existe) incluya nota de incertidumbre E-10.

El impacto positivo **no se mueve a `uncovered_impact_ids`** incluso con data_gaps — la obligación PVA no aplica a positivos.

---

## Tratamiento de impactos indeterminados

Un impacto con `nature == INDETERMINADO` o `status == INDETERMINADO` en un receptor sensible (FR-007/008/009/010/012) **requiere PVA**. Si tiene cobertura CONDICIONADO (por CONT), va a `conditional_coverage_ids` (WARNING). Si no tiene cobertura, va a `uncovered_impact_ids` (ERROR).

---

## Relación con IM-06

IM-06 (`pva_generator`) **genera** las fichas PVA. IM-07 las **valida**. El flujo típico:

```
phase6-generate-pva --write    →  phase6_model_with_pva.json
phase6-validate-pva [--write]  →  pva_coverage_result.json / .md
```

IM-07 puede ejecutarse sobre cualquier modelo con pva_programs, aunque el output de IM-06 es la fuente canónica.

---

## Uso CLI

```bash
# Solo mostrar summary (no escribe archivos)
python run_expediente.py <expediente> phase6-validate-pva

# Con escritura de outputs
python run_expediente.py <expediente> phase6-validate-pva --write
```

**Exit codes:**
- `0`: cobertura válida (`is_valid() == True`, sin ERRORs)
- `1`: hay impactos sin cobertura o error de carga

**Archivos de entrada buscados (en orden):**
1. `impactos/phase6_model_with_pva.json` (output de IM-06)
2. `impactos/phase6_model_with_measures.json` (fallback)

**Archivos de salida (con --write):**
- `impactos/pva_coverage_result.json`
- `impactos/pva_coverage_result.md`

---

## Cómo ejecutar los tests

```bash
# Solo IM-07
python -m pytest tests/test_pva_coverage_validator.py -v

# Suite completa
python -m pytest tests/ -q
```

**Cobertura de tests (99 tests):**
- PVACoverageIssue: to_dict, summary, valores None
- PVACoverageResult: conteos, is_valid, to_dict, summary ASCII-safe
- impact_requires_pva: 18 casos (negativo, positivo, indeterminado, descartado, mixto, sensible)
- find_pva_coverage_for_impact: 8 casos (direct, by_factor, transversal, annual excluido)
- validate_pva_coverage: 18 casos (covered, uncovered, conditional, ignored, no-mutation)
- build_pva_coverage_markdown: 13 casos
- validate_pva_coverage_from_json: 5 casos (fixture temporal)
- write_pva_coverage_outputs: 6 casos
- CLI phase6-validate-pva: 8 casos

---

*Módulo generado por EIA-Agent v2.1 — P1 código — 2026-05-10*
