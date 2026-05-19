# MITIGATION_MEASURE_GENERATOR — IM-05

Generador de medidas ambientales por tipo de impacto para Fase 6.

**Módulo**: `src/eia_agent/core/mitigation_measure_generator.py`  
**ID de productización**: IM-05  
**Completado**: 2026-05-06  
**Dependencias**: IM-00 (`impact_model`), IM-03 (`impact_identifier`), IM-04 (`conesa_attribute_assigner`)

---

## Qué hace IM-05

Genera medidas ambientales tipológicas a partir de los impactos valorados por IM-04,
usando tablas de reglas (MGEN-A a MGEN-P). A diferencia de IM-04 (primera regla gana),
IM-05 aplica **todas las reglas que coincidan** con cada impacto, generando una medida
por cada coincidencia (con deduplicación por nombre + tipo).

1. **`MeasureGenerationRule`** — Regla tipológica: `matches(impact)` decide si aplica.
2. **`MeasureGenerationResult`** — Resultado con modelo actualizado, conteos y trazabilidad.
3. **`default_measure_generation_rules()`** — 16 reglas canónicas (MGEN-A a MGEN-P).
4. **`generate_measures_for_impact(impact, rules, start_index)`** — Medidas para un impacto.
5. **`generate_measures_for_model(model, rules)`** — Medidas para todo el modelo.
6. **`merge_measures_into_model(model, measures)`** — Integración de medidas externas.

## Qué NO hace IM-05

| Capacidad | Estado |
|-----------|--------|
| Crear impactos | No — IM-03 |
| Asignar atributos Conesa | No — IM-04 |
| Modificar significancia sin medidas | No — solo IM-01 |
| Calcular significancia con medidas | No — IM-01 (con_measures=True), post IM-05 |
| Generar fichas PVA | No — IM-06 |
| Compensar impactos positivos con negativos | No — restricción metodológica |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Escribir archivos desde el módulo | No — responsabilidad de la CLI |

---

## Principio metodológico: todas las reglas aplican

Cada impacto puede recibir varias medidas simultáneas. Un impacto de ruido (FR-014)
puede recibir en la misma ejecución:
- MGEN-A: Estudio acústico previo (DIAGNOSTICA, CONDICION_PREVIA)
- MGEN-B: Insonorización y barreras (CORRECTORA)
- MGEN-C: Limitación horaria de operaciones (PREVENTIVA)
- MGEN-D: Equipos de protección individual (PRL_NO_EIA)

La deduplicación evita que dos reglas con idéntico `(measure_name, measure_type)`
generen medidas duplicadas en el mismo impacto.

---

## Tipos de medidas

| Tipo | Significado | Reduce significancia |
|------|-------------|----------------------|
| `PREVENTIVA` | Evita o reduce el impacto antes de que se produzca | Sí |
| `CORRECTORA` | Corrige el impacto una vez generado | Sí |
| `PROTECTORA` | Protege el receptor (barreras, coberturas) | Sí |
| `COMPENSATORIA` | Compensa pérdidas netas (solo si norma obliga) | Sí |
| `DIAGNOSTICA` | Obtiene datos para dimensionar medidas posteriores | **No** |
| `DOCUMENTAL` | Acredita cumplimiento de un requisito administrativo | Sí (documental) |
| `PRL_NO_EIA` | Obligación PRL ajena al procedimiento EIA | **No** |

Los tipos `DIAGNOSTICA` y `PRL_NO_EIA` están en `_NON_REDUCING_MEASURE_TYPES`
en `impact_model.py` y no reducen la significancia Conesa.

---

## Estados de medidas

| Estado | Significado |
|--------|-------------|
| `PROPUESTA` | Medida pendiente de valoración de eficacia |
| `CONDICION_PREVIA` | Debe acreditarse antes de presentar el Documento Ambiental |
| `CONDICIONADA` | Su eficacia depende de cumplir otra condición |
| `NO_EIA` | Medida fuera del procedimiento EIA (ej. PRL) |
| `DESCARTADA` | Medida descartada por inaplicable o redundante |

---

## Reglas por defecto (MGEN-A a MGEN-P)

| Regla | Receptor(es) | Tipo | Estado | Diagnóstica | PRL | Condición previa |
|-------|-------------|------|--------|-------------|-----|-----------------|
| MGEN-A | FR-014 (Ruido) | DIAGNOSTICA | CONDICION_PREVIA | ✅ | — | ✅ |
| MGEN-B | FR-014 | CORRECTORA | PROPUESTA | — | — | — |
| MGEN-C | FR-014 | PREVENTIVA | PROPUESTA | — | — | — |
| MGEN-D | FR-014 | PRL_NO_EIA | NO_EIA | — | ✅ | — |
| MGEN-E | FR-006 (Aire) | CORRECTORA | CONDICION_PREVIA | — | — | ✅ |
| MGEN-F | FR-006 | PREVENTIVA | PROPUESTA | — | — | — |
| MGEN-G | FR-003 (Suelos) | PROTECTORA | PROPUESTA | — | — | — |
| MGEN-H | FR-003 | PREVENTIVA | PROPUESTA | — | — | — |
| MGEN-I | FR-004 (Hidrología) | PROTECTORA | CONDICION_PREVIA | — | — | ✅ |
| MGEN-J | FR-005 + FR-016 (Inundabilidad + Riesgos) | DOCUMENTAL | CONDICION_PREVIA | — | — | ✅ |
| MGEN-K | FR-009 + FR-010 (ENP + Red Natura) | DOCUMENTAL | CONDICION_PREVIA | — | — | ✅ |
| MGEN-L | FR-007 + FR-008 (Flora + Fauna) | DIAGNOSTICA | CONDICION_PREVIA | ✅ | — | ✅ |
| MGEN-M | FR-012 (Patrimonio) | DOCUMENTAL | CONDICION_PREVIA | — | — | ✅ |
| MGEN-N | FR-011 (Paisaje) | PREVENTIVA | PROPUESTA | — | — | — |
| MGEN-O | FR-015 (Cambio climático) | DOCUMENTAL | PROPUESTA | — | — | — |
| MGEN-P | FR-013 (Socioeconomía) | DOCUMENTAL | PROPUESTA | — | — | — |

**Nota MGEN-P**: solo aplica a impactos de naturaleza POSITIVO. No genera medida
compensatoria ni de corrección sobre impactos positivos.

**Nota MGEN-J**: FR-005 y FR-016 raramente generan impactos en IM-03 (receptores
sin cadena acción→impacto en tablas tipológicas). La regla existe para cubrir
impactos añadidos manualmente.

---

## Lógica de `matches(impact)`

```python
def matches(self, impact: EnvironmentalImpact) -> bool:
    # 1. DESCARTADO_JUSTIFICADO nunca recibe medidas
    if impact.status == "DESCARTADO_JUSTIFICADO":
        return False
    # 2. Receptor obligatorio
    if impact.receptor_id not in self.target_receptor_ids:
        return False
    # 3. Naturaleza (si la regla filtra)
    if self.target_natures and impact.nature not in self.target_natures:
        return False
    # 4. Palabras clave en nombre/descripción (si la regla filtra)
    if self.impact_keywords:
        text = f"{impact.name} {impact.description}".lower()
        if not any(kw.lower() in text for kw in self.impact_keywords):
            return False
    # 5. Significancia (si la regla filtra)
    if self.significance_levels:
        if impact.significance_without_measures not in self.significance_levels:
            return False
    return True
```

---

## Numeración global de medidas

`generate_measures_for_model` asigna IDs correlativos `MED-001`, `MED-002`... a
través de todos los impactos del modelo (no reinicia por impacto). El orden sigue
el de `model.impacts`.

Los IDs de las medidas generadas se añaden a `impact.measure_ids` de cada impacto
(inmutable: usa `dataclasses.replace()`). Las medidas preexistentes se **reemplazan**,
no se acumulan.

---

## Regla de no compensación

IM-05 no genera medidas compensatorias para equilibrar impactos positivos con negativos.
MGEN-P (socioeconomía) aplica solo a impactos POSITIVO y genera documentación; no
corrige ni neutraliza impactos positivos. No existe ninguna regla que asigne
`measure_type="COMPENSATORIA"`.

---

## Contadores del resultado

| Contador | Descripción |
|----------|-------------|
| `generated_count` | Total de medidas creadas en el modelo |
| `diagnostic_count` | Medidas de tipo DIAGNOSTICA |
| `prl_only_count` | Medidas de tipo PRL_NO_EIA |
| `condition_before_submission_count` | Medidas con `condition_before_submission=True` |

---

## API pública

### `MeasureGenerationRule`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `rule_id` | `str` | Identificador único (ej. "MGEN-A") |
| `target_receptor_ids` | `list[str]` | Receptores objetivo |
| `impact_keywords` | `list[str]` | Palabras clave en nombre/descripción; `[]` = sin filtro |
| `significance_levels` | `list[str]` | Significancias objetivo; `[]` = sin filtro |
| `measure_name` | `str` | Nombre de la medida generada |
| `measure_description` | `str` | Descripción de la medida |
| `measure_type` | `str` | Tipo de medida (PREVENTIVA, CORRECTORA, etc.) |
| `status` | `str` | Estado inicial (por defecto "PROPUESTA") |
| `is_diagnostic` | `bool` | True si es DIAGNOSTICA |
| `is_prl_only` | `bool` | True si es PRL_NO_EIA |
| `condition_before_submission` | `bool` | True si es condición previa |
| `target_natures` | `list[str]` | Naturalezas objetivo; `[]` = cualquiera |
| `notes` | `list[str]` | Notas metodológicas |

Métodos: `matches(impact) -> bool`, `to_dict() -> dict`.

### `MeasureGenerationResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `model` | `Phase6Model` | Modelo con medidas generadas |
| `generated_count` | `int` | Total de medidas generadas |
| `diagnostic_count` | `int` | Medidas DIAGNOSTICA |
| `prl_only_count` | `int` | Medidas PRL_NO_EIA |
| `condition_before_submission_count` | `int` | Medidas CONDICION_PREVIA |
| `warnings` | `list[str]` | Avisos |
| `notes` | `list[str]` | Notas de trazabilidad |

Métodos: `to_dict()`, `summary()` (ASCII-safe para consola Windows cp1252).

### `generate_measures_for_impact(impact, rules=None, start_index=1)`

```python
generate_measures_for_impact(
    impact: EnvironmentalImpact,
    rules: list[MeasureGenerationRule] | None = None,
    start_index: int = 1,
) -> list[MitigationMeasure]
```

Función pura. Aplica **todas** las reglas coincidentes. Deduplica por `(name, measure_type)`.

### `generate_measures_for_model(model, rules=None)`

```python
generate_measures_for_model(
    model: Phase6Model,
    rules: list[MeasureGenerationRule] | None = None,
) -> MeasureGenerationResult
```

Reemplaza `model.measures` con todas las medidas generadas. Actualiza `impact.measure_ids`.
No muta el modelo original.

### `merge_measures_into_model(model, measures)`

```python
merge_measures_into_model(
    model: Phase6Model,
    measures: list[MitigationMeasure],
) -> Phase6Model
```

Sustituye las medidas del modelo y reconstruye `impact.measure_ids` desde `target_impact_ids`.
Útil para integrar medidas generadas externamente o modificadas manualmente.

---

## CLI

```bash
# Solo lectura (no escribe nada)
python run_expediente.py <expediente> phase6-generate-measures

# Escribe phase6_model_with_measures.json y measure_generation_result.json
python run_expediente.py <expediente> phase6-generate-measures --write
```

**Comportamiento**:
- Lee `impactos/phase6_model_with_conesa.json` (output de IM-04). Si no existe,
  usa `impactos/phase6_model_with_impacts.json` como fallback.
- Si ninguno existe: error y exit 1.
- Sin `--write`: imprime resumen, exit 0.
- Con `--write`: escribe dos JSONs en `impactos/`, crea el directorio si no existe.

**Outputs**:
- `impactos/phase6_model_with_measures.json` — Modelo completo con medidas integradas.
- `impactos/measure_generation_result.json` — Resultado con conteos y lista de medidas.

---

## Relación con IM-00, IM-03, IM-04

```
IM-03 (impact_identifier)
    │   identify_impacts_from_model()
    ▼
Phase6Model.impacts [status=PENDIENTE_DATOS, measures=[]]
    │
    ▼
IM-04 (conesa_attribute_assigner)
    │   assign_conesa_attributes_to_model(model, score=True)
    ▼
Phase6Model.impacts [conesa_attributes asignados, significance_without_measures calculada]
    │
    ▼
IM-05 (mitigation_measure_generator)
    │   generate_measures_for_model(model, rules)
    ▼
Phase6Model.impacts [measure_ids=[MED-001, MED-002, ...]]
Phase6Model.measures [MED-001 ... MED-N, todos tipológicos]
    │
    ├── IM-06 (fichas PVA) → siguiente paso
    └── IM-01 (conesa_engine, with_measures=True) → significancia con medidas
```

---

## Cómo ejecutar los tests

```bash
# Solo IM-05
venv\Scripts\python -m unittest tests.test_mitigation_measure_generator

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_mitigation_measure_generator.py`  
**Tests**: 93 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestMeasureGenerationRule` | 14 | to_dict(), matches() por receptor/keyword/significancia/naturaleza/descartado, defaults |
| `TestDefaultMeasureGenerationRules` | 15 | Count=16, IDs MGEN-A a MGEN-P presentes, IDs únicos, tipos y estados válidos, regla PRL, Red Natura DOCUMENTAL, patrimonio, socioeconomía solo POSITIVO |
| `TestGenerateMeasuresForImpact` | 18 | FR-014 genera acústico+correctora+preventiva+PRL, FR-006/FR-003/FR-004/FR-009+010/FR-012/FR-013, IDs correlativos, no mutación, deduplicación, DESCARTADO_JUSTIFICADO vacío |
| `TestGenerateMeasuresForModel` | 16 | Múltiples impactos, measure_ids actualizados, sin PVA, conserva acciones/receptores, sin modificar significancia, conteos, no mutación, modelo vacío, IDs globales correlativos, JSON serializable, summary() |
| `TestMergeMeasuresIntoModel` | 8 | Reemplaza medidas, actualiza impact.measure_ids, conserva PVA, conserva acciones/receptores, no mutación, medidas vacías limpian measure_ids |
| `TestMethodologicalRules` | 11 | PRL no es CORRECTORA, diagnóstica tiene is_diagnostic=True, diagnóstica no cambia significancia, positiva no es COMPENSATORIA, sin compensación cruzada, ENP/Flora/Fauna solo DOCUMENTAL/DIAGNOSTICA, patrimonio no afirma compatibilidad, PRL tiene NO_EIA, independencia positivo/negativo, MGEN-B no es PRL, MGEN-A en _NON_REDUCING_MEASURE_TYPES |
| `TestCLIPhase6GenerateMeasures` | 8 | Sin modelo→exit 1, sin --write no crea archivos, con --write crea 2 JSONs, JSON contiene measures, modelo JSON válido, sin PVA, fallback a impacts model, múltiples impactos |

---

*Generado por EIA-Agent v2.1 — IM-05 — 2026-05-06*
