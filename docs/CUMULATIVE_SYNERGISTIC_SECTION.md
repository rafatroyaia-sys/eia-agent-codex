# CUMULATIVE_SYNERGISTIC_SECTION — IM-08

Generador determinístico de la sección C.5 de efectos acumulativos y sinérgicos.

**Módulo**: `src/eia_agent/core/cumulative_synergistic_section.py`  
**ID de productización**: IM-08  
**Completado**: 2026-05-12  
**Dependencias**: IM-00 (`impact_model`)

---

## Decisión de ID (2026-05-12)

| ID | Función | Estado |
|----|---------|--------|
| IM-06 | Generador de fichas PVA (`pva_generator.py`) | COMPLETADO ✅ |
| IM-07 | Validador de cobertura PVA (`pva_coverage_validator.py`) | COMPLETADO ✅ |
| **IM-08** | **Generador C.5 acumulativos/sinérgicos (este módulo)** | **COMPLETADO ✅** |

El template C.5 era "IM-06 código" en el Área 14 del backlog original (Etapa 1 corta). Se implementa ahora con ID canónico IM-08 por asignación del usuario.

---

## Qué hace IM-08

- Lee un `Phase6Model` con impactos, factores receptores y gaps.
- Detecta grupos de impactos con potencial efecto acumulativo (2+ impactos en el mismo receptor).
- Detecta pares de factores con potencial interacción sinérgica (5 pares implementados).
- Extrae los gaps sin resolver relevantes para el análisis.
- Genera la sección C.5 completa en markdown (subsecciones C.5.1 a C.5.5).
- Se expone como comando CLI `phase6-cumulative [--write]`.

---

## Qué NO hace IM-08

| Capacidad | Estado |
|-----------|--------|
| Crear impactos nuevos | No |
| Modificar valoraciones Conesa | No |
| Modificar medidas | No |
| Modificar PVA | No |
| Cerrar impactos INDETERMINADO | No — la incertidumbre se declara |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Redactar bloques A-K completos | No — solo la sección C.5 |

---

## Diferencia entre acumulativo y sinérgico

| Concepto | Definición | Detección |
|----------|-----------|-----------|
| **Acumulativo** | Un mismo factor ambiental recibe presión de 2+ acciones del mismo proyecto → el efecto se suma en el tiempo o en el espacio | 2+ impactos con nature NEGATIVO/MIXTO/INDETERMINADO sobre el mismo receptor FR-XXX |
| **Sinérgico** | Dos factores distintos interactúan de forma que el efecto combinado puede superar la suma de los efectos individuales | Par de receptores activos en ambos lados de las reglas definidas |

---

## Reglas de acumulación implementadas

Un receptor forma un grupo acumulativo si:
- Tiene **2 o más** impactos con `nature` en {NEGATIVO, MIXTO, INDETERMINADO}.
- O bien es un receptor sensible (FR-007/008/009/010/012) con al menos 1 impacto INDETERMINADO/PENDIENTE_DATOS.

Los impactos `DESCARTADO_JUSTIFICADO` no cuentan. Los impactos `POSITIVO` no generan acumulación.

---

## Reglas de sinergia implementadas (5 pares)

| Clave | Lados A y B | Descripción |
|-------|-------------|-------------|
| `aire_ruido` | FR-006 + FR-014 | Calidad del aire y ruido — operaciones de tratamiento mecánico y maquinaria |
| `suelo_hidrologia` | FR-003 + FR-004 | Suelos e hidrología — riesgo de propagación de contaminantes al sistema hídrico |
| `hidrologia_red_natura` | FR-004 + (FR-009 o FR-010) | Vectores hídricos hacia espacios protegidos |
| `biodiversidad_red_natura` | (FR-007 o FR-008) + (FR-009 o FR-010) | Presión sobre flora/fauna con implicaciones en Red Natura/ENP |
| `clima_riesgos` | FR-015 + FR-016 | Cambio climático amplifica exposición a riesgos naturales |

Un par de sinergia se activa si ambos lados tienen al menos 1 impacto no descartado.

---

## Reglas de prudencia aplicadas

1. **Nunca** usar "no existen efectos acumulativos".
2. **Nunca** usar "se descartan efectos acumulativos".
3. **Nunca** usar "no existen sinergias".
4. **Nunca** usar "se descartan sinergias".
5. Si sin datos suficientes → "No se dispone de información suficiente para cerrar el análisis; se mantiene como cautela metodológica."
6. Los impactos INDETERMINADO no quedan cerrados: su incertidumbre se declara y se propaga.
7. El análisis no modifica la valoración individual de ningún impacto.
8. Limitación de gabinete declarada explícitamente en C.5.1.

---

## API pública

### `group_impacts_by_receptor(model) -> dict[str, list[EnvironmentalImpact]]`
Agrupa impactos por receptor_id, excluyendo DESCARTADO_JUSTIFICADO.

### `detect_cumulative_impact_groups(model) -> dict[str, list[str]]`
Detecta grupos acumulativos. Returns: `{receptor_id: [impact_id, ...]}`.

### `detect_synergistic_impact_groups(model) -> dict[str, list[str]]`
Detecta grupos sinérgicos. Returns: `{"aire_ruido": [impact_id, ...], ...}`.

### `extract_unresolved_cumulative_gaps(model) -> list[str]`
Recopila gap IDs sin resolver relevantes (de impactos y de receptores).

### `build_cumulative_synergistic_markdown(model) -> str`
Genera la sección C.5 completa en markdown.

### `build_cumulative_synergistic_section(model) -> CumulativeSynergyResult`
Función principal. Orquesta todas las funciones y devuelve el resultado completo.

### `build_cumulative_synergistic_section_from_json(path) -> CumulativeSynergyResult`
Carga JSON y ejecuta el análisis. Lanza `FileNotFoundError` / `ValueError`.

### `write_cumulative_synergistic_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `cumulative_synergistic_result.json` y `C5_acumulativos_sinergicos.md`.

---

## Estructura de CumulativeSynergyResult

```python
CumulativeSynergyResult(
    markdown: str,                          # sección C.5 completa
    cumulative_groups: dict[str, list[str]], # receptor_id → [impact_ids]
    synergistic_groups: dict[str, list[str]], # synergy_key → [impact_ids]
    unresolved_gaps: list[str],              # gap IDs sin resolver
    issues: list[CumulativeSynergyIssue],    # INFO / WARNING (nunca ERROR)
    warnings: list[str],                     # avisos de proceso
    notes: list[str],                        # trazabilidad
)
```

**Este módulo nunca genera incidencias de severidad ERROR.**

---

## Códigos de incidencia

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| `CS-I001` | INFO | Grupo acumulativo detectado (datos completos) |
| `CS-W001` | WARNING | Grupo acumulativo con datos insuficientes (INDETERMINADO) |
| `CS-I002` | INFO | Grupo sinérgico potencial detectado |
| `CS-W002` | WARNING | Gaps activos que limitan el análisis |

---

## Uso CLI

```bash
# Solo mostrar summary (no escribe archivos)
python run_expediente.py <expediente> phase6-cumulative

# Con escritura de outputs
python run_expediente.py <expediente> phase6-cumulative --write
```

**Archivos de entrada buscados (en orden):**
1. `impactos/phase6_model_with_pva.json`
2. `impactos/phase6_model_with_measures.json`
3. `impactos/phase6_model_with_conesa.json`
4. `impactos/phase6_model_with_impacts.json`

**Archivos de salida (con --write):**
- `impactos/cumulative_synergistic_result.json`
- `impactos/C5_acumulativos_sinergicos.md`

**Exit code:** siempre 0 si el modelo se carga correctamente (el análisis no bloquea el expediente), 1 si no se encuentra ningún modelo.

---

## Cómo ejecutar los tests

```bash
# Solo IM-08
python -m pytest tests/test_cumulative_synergistic_section.py -v

# Suite completa
python -m pytest tests/ -q
```

**Cobertura de tests (91 tests):**
- CumulativeSynergyIssue: to_dict, summary, valores None
- CumulativeSynergyResult: conteos, to_dict, summary ASCII-safe
- group_impacts_by_receptor: agrupación, exclusión DESCARTADO, conservación INDETERMINADO
- detect_cumulative_impact_groups: 9 casos (FR-014/006/003, single, descartado, positivo, sensible)
- detect_synergistic_impact_groups: 11 casos (5 pares, single-side, descartado)
- extract_unresolved_cumulative_gaps: 6 casos (fuentes, deduplicación, exclusión)
- build_cumulative_synergistic_markdown: 16 casos (secciones, frases prohibidas, cautela)
- build_cumulative_synergistic_section: 10 casos (result completo, no-mutación)
- write_cumulative_synergistic_outputs: 7 casos
- CLI phase6-cumulative: 8 casos
- build_from_json: 3 casos

---

*Módulo generado por EIA-Agent v2.1 — P1 código — 2026-05-12*
