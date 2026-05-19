# DIAGNOSTIC_MEASURE_VALIDATOR — RD-08

Módulo: `src/eia_agent/core/diagnostic_measure_validator.py`  
CLI: `python run_expediente.py <expediente> audit-diagnostic-measures [--write]`  
Tests: `tests/test_diagnostic_measure_validator.py` (97 tests)

---

## Qué hace RD-08

Verifica que ninguna medida diagnóstica se utilice como medida reductora material
de la significancia ambiental de un impacto.

Una medida diagnóstica (estudio acústico, prospección de flora, consulta patrimonial,
verificación cartográfica, etc.) aporta información para confirmar, dimensionar o
justificar medidas materiales posteriores. **No reduce significancia por sí misma.**

---

## Qué NO hace RD-08

- **No corrige medidas.** Solo detecta; no modifica nombre, descripción ni tipo.
- **No cambia significancias.** Los valores `significance_without_measures` y
  `significance_with_measures` no se modifican.
- **No valora impactos.** No calcula índices Conesa ni reclasifica impactos.
- **No declara aptitud administrativa.** La calificación es interna al sistema.
- **No usa IA.** Lógica determinista sobre el modelo de datos.
- **No consulta fuentes externas.** Solo opera sobre archivos locales del expediente.
- **No modifica** ningún archivo previo salvo los de auditoría (con `--write`).

---

## Diferencia entre medida diagnóstica y medida reductora material

| Concepto | Medida diagnóstica | Medida reductora material |
|----------|-------------------|--------------------------|
| Función | Obtener información | Cambiar el estado real del factor |
| Ejemplo | Estudio acústico | Pantalla acústica perimetral |
| Ejemplo | Prospección de flora | Balizamiento y exclusión de zona sensible |
| Ejemplo | Consulta patrimonial | Modificación de trazado o diseño |
| Reduce significancia | **No** | Sí (puede) |
| Puede ser condición previa | Sí | Sí |

Una medida diagnóstica puede ser obligatoria antes de la presentación del expediente
(condición previa), pero eso no la convierte en reductora de significancia. El resultado
del estudio puede revelar que se necesitan medidas adicionales — que son las reductoras.

---

## Detección de medidas diagnósticas

Una medida se clasifica como diagnóstica si cumple **cualquiera** de estas condiciones:

1. `is_diagnostic == True`
2. `measure_type == "DIAGNOSTICA"`
3. El nombre, descripción o notas contienen alguna de las palabras clave:

| Palabra clave |
|---------------|
| estudio |
| medicion / medición |
| modelizacion / modelización |
| consulta |
| verificacion / verificación |
| prospeccion / prospección |
| caracterizacion / caracterización |
| diagnostico / diagnóstico |
| informe previo |
| analisis previo / análisis previo |

La comparación es insensible a tildes y mayúsculas.

---

## Reglas de validación

### RD08-E001 — Texto afirma reducción material
La medida diagnóstica contiene palabras de reducción activa (no precedidas de negación):

| Keyword detectado |
|------------------|
| reduce |
| reduccion |
| disminuye |
| mitiga |
| corrige |
| elimina |
| evita completamente |
| baja la significancia |
| reduce la significancia |
| pasa a compatible |
| se considera compatible tras |
| queda corregido |

Las ocurrencias precedidas por "no", "sin", "nunca", "jamás", "ni" o "tampoco"
**no se cuentan** como afirmación de reducción.

### RD08-E002 — Única medida en impacto con significancia mejorada
La medida diagnóstica es la **única** medida vinculada a un impacto cuya
`significance_with_measures` es menos severa que `significance_without_measures`
y no hay ninguna medida correctora/preventiva enlazada al mismo impacto.

### RD08-W001 — Vinculada a impacto con significancia mejorada (no exclusiva)
La medida diagnóstica está vinculada a un impacto con mejora de significancia,
pero existen también medidas correctoras/preventivas enlazadas. Warning: verificar
que la mejora la producen esas otras medidas, no la diagnóstica.

### RD08-W002 — Única medida de impacto de alta significancia sin mejora
La medida diagnóstica es la única medida para un impacto SEVERO o CRITICO
cuya significancia no ha mejorado. Un impacto de alta significancia requiere
medidas materiales reales, no solo diagnósticas.

---

## Estado del resultado

| Estado | Condición |
|--------|-----------|
| `OK` | No hay incidencias, o solo incidencias INFO |
| `CON_OBSERVACIONES` | Solo hay incidencias WARNING |
| `NO_CONFORME` | Hay incidencias ERROR |
| `SIN_DATOS` | No hay modelo de impactos/medidas disponible |

`is_valid()` devuelve `True` cuando no hay incidencias ERROR (OK y CON_OBSERVACIONES).

---

## Ejemplos correctos e incorrectos

### Correcto — estudio bien declarado

```json
{
  "measure_id": "MED-042",
  "name": "Estudio acústico previo",
  "description": "Permite dimensionar la pantalla acústica necesaria. No reduce por sí sola la significancia.",
  "measure_type": "DIAGNOSTICA",
  "is_diagnostic": true,
  "condition_before_submission": true
}
```
→ Sin incidencias. Texto prudente, no afirma reducción.

### Incorrecto — E001 — afirma reducción

```json
{
  "measure_id": "MED-043",
  "name": "Estudio acústico",
  "description": "Con esta medida el impacto acústico pasa a compatible.",
  "measure_type": "DIAGNOSTICA",
  "is_diagnostic": true
}
```
→ **RD08-E001**: "pasa a compatible" detectado.

### Incorrecto — E002 — única medida reductora

```json
{
  "measures": [
    {
      "measure_id": "MED-044",
      "name": "Estudio acústico",
      "measure_type": "DIAGNOSTICA",
      "is_diagnostic": true,
      "target_impact_ids": ["IMP-014"]
    }
  ],
  "impacts": [
    {
      "impact_id": "IMP-014",
      "significance_without_measures": "SEVERO",
      "significance_with_measures": "MODERADO",
      "measure_ids": ["MED-044"]
    }
  ]
}
```
→ **RD08-E002**: El estudio acústico es la única medida para IMP-014 y la
significancia mejora de SEVERO a MODERADO. Falta medida correctora real.

---

## Orden de búsqueda de modelo

```
impactos/phase6_model_with_pva.json       ← prioridad 1
impactos/phase6_model_with_measures.json  ← prioridad 2
impactos/phase6_model_with_conesa.json    ← prioridad 3
impactos/phase6_model_with_impacts.json   ← prioridad 4
```

Si ninguno existe: `status = SIN_DATOS`.

---

## CLI

```
python run_expediente.py <expediente> audit-diagnostic-measures [--write]
```

| Opción | Descripción |
|--------|-------------|
| `--write` | Escribe `auditoria/diagnostic_measure_validation_result.json` y `.md` |

**Códigos de salida:**
- `0` → sin errores (`is_valid() == True`): OK o CON_OBSERVACIONES
- `1` → hay errores (NO_CONFORME) o expediente no existe

---

## API pública

### `is_diagnostic_measure(measure) -> bool`
True si la medida es diagnóstica por flag, tipo o palabras clave.

### `measure_claims_material_reduction(measure) -> bool`
True si el texto de la medida contiene lenguaje de reducción material
(con detección de negación).

### `validate_diagnostic_measure(measure, related_impacts=None) -> list[DiagnosticMeasureIssue]`
Valida una medida en aislamiento o con sus impactos vinculados.

### `validate_diagnostic_measures_in_model(model) -> DiagnosticMeasureValidationResult`
Valida todas las medidas del Phase6Model. No muta el modelo.

### `validate_diagnostic_measures_from_json(path) -> DiagnosticMeasureValidationResult`
Carga JSON y valida.

### `validate_diagnostic_measures_from_files(expediente_path) -> DiagnosticMeasureValidationResult`
Busca el modelo en `impactos/` y valida.

### `build_diagnostic_measure_report_markdown(result) -> str`
Genera informe markdown con 6 secciones.

### `write_diagnostic_measure_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `diagnostic_measure_validation_result.json` y `.md`.

---

## Ejecución de tests

```
python -m unittest tests.test_diagnostic_measure_validator
python -m unittest discover -s tests
```

Los tests son 100% offline: usan `tempfile`, `unittest` y objetos en memoria.
No requieren web, IA ni APIs externas.

---

## Advertencia de alcance

Una medida diagnóstica no reduce por sí sola la significancia ambiental.
Solo aporta información para confirmar, dimensionar o justificar medidas
materiales posteriores.

Si un impacto tiene significancia SEVERO o CRITICO, la reducción de esa
significancia debe provenir de medidas correctoras, preventivas o compensatorias
reales, no de estudios, prospecciones, consultas o verificaciones.
