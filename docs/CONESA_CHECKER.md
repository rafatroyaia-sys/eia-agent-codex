# CONESA_CHECKER.md — RD-06

**Modulo:** `src/eia_agent/core/conesa_checker.py`  
**CLI:** `python run_expediente.py <expediente> audit-conesa [--write]`  
**Tests:** `tests/test_conesa_checker.py` (89 tests OK)

---

## Que hace RD-06

Verifica que todos los impactos ambientales del expediente disponen de cobertura
Conesa suficiente: tabla de atributos completa o justificacion expresa de indeterminacion.

Regla canonica (OBS-M12 / RD-06):
> Todos los impactos del Documento Ambiental deben tener tabla/atributos Conesa
> o justificacion expresa de indeterminacion. Sin excepcion.

---

## Que NO hace RD-06

- **No recalcula la formula Conesa.** La formula `I = 3·IN + 2·EX + MO + ...` es IM-01.
- **No cambia la formula Conesa.** Los umbrales y la clasificacion son inmutables.
- **No corrige textos.** Solo detecta y reporta.
- **No valora impactos nuevos.** No genera valoraciones.
- **No modifica el expediente** salvo escritura del informe (--write).
- **No declara aptitud administrativa.** Solo el organo ambiental emite el IIA.

---

## Regla de tabla/atributos Conesa obligatorios

Un impacto tiene cobertura Conesa suficiente si cumple UNA de estas condiciones:

1. **Tiene los 10 atributos Conesa** con valor entero positivo
   (intensidad, extension, momento, persistencia, reversibilidad, sinergia,
   acumulacion, efecto, periodicidad, recuperabilidad).

2. **Tiene justificacion expresa de indeterminacion**:
   - `status == INDETERMINADO` o `PENDIENTE_DATOS` + `data_gaps` no vacio.
   - `significance_without_measures == INDETERMINADO` + `data_gaps` no vacio.
   - `notes` o `warnings` contienen keywords de incertidumbre (gap, at activa,
     consulta pendiente, campo necesario, etc.).

Un impacto `DESCARTADO_JUSTIFICADO` no necesita Conesa completo pero si
description/notes con la justificacion del descarte.

---

## Tratamiento de impactos indeterminados

- `INDETERMINADO` con `data_gaps` → cobertura OK (INFO en markdown).
- `INDETERMINADO` sin `data_gaps` ni notas → ERROR.
- `PENDIENTE_DATOS` con `data_gaps` → cobertura OK.
- `PENDIENTE_DATOS` sin nada → ERROR.

El objetivo es que cada impacto tenga una razon documentada de por que no
se puede valorar Conesa todavia, no que Conesa sea obligatorio en todos
los casos sin excepcion.

---

## Tratamiento de impactos positivos

Un impacto `POSITIVO` no usa la misma escala Conesa negativa. Pero debe tener:
- Una nota que indique que no compensa impactos negativos (regla de no compensacion).
- Si no tiene esa nota → WARNING (no ERROR).

---

## Validacion de markdowns

El checker busca, ademas del modelo JSON, markdowns en `bloques/` e `impactos/`.

Para cada IMP-NNN esperado:
- `ERROR` si no aparece en ningun markdown.
- `WARNING` si aparece pero sin vocabulario Conesa (ni tabla, ni keywords de atributos).
- `INFO` si aparece con seccion/tabla Conesa (≥3 keywords).
- `INFO` si aparece con indicador de indeterminacion/pendiente.

---

## API implementada

```python
def has_complete_conesa_attributes(impact: EnvironmentalImpact) -> bool: ...
def missing_conesa_attributes(impact: EnvironmentalImpact) -> list[str]: ...
def impact_has_valid_conesa_explanation(impact: EnvironmentalImpact) -> bool: ...
def validate_impact_conesa_coverage(impact: EnvironmentalImpact) -> list[ConesaCheckIssue]: ...
def validate_phase6_conesa_coverage(model: Phase6Model) -> ConesaCheckResult: ...

def extract_impact_ids_from_markdown(markdown: str) -> list[str]: ...
def detect_conesa_table_like_sections(markdown: str) -> dict[str, list[str]]: ...
def validate_markdown_conesa_coverage(
    markdown: str,
    expected_impact_ids: list[str],
    source: str = "markdown",
) -> list[ConesaCheckIssue]: ...

def validate_conesa_coverage_from_files(
    expediente_path: str | Path,
) -> ConesaCheckResult: ...

def build_conesa_check_report_markdown(result: ConesaCheckResult) -> str: ...
def write_conesa_check_outputs(
    result: ConesaCheckResult,
    output_dir: str | Path,
) -> tuple[Path, Path]: ...
```

---

## Codigos de incidencia

| Codigo | Severidad | Descripcion |
|--------|-----------|-------------|
| CC-A001 | ERROR | VALORADO sin 10 atributos Conesa |
| CC-A002 | ERROR | VALORADO con significance NO_VALORADO o INDETERMINADO |
| CC-B001 | ERROR | Significancia conocida sin atributos Conesa |
| CC-C001 | WARNING | Atributos completos pero significance NO_VALORADO |
| CC-D001 | ERROR/WARNING | INDETERMINADO/PENDIENTE sin data_gaps ni notas |
| CC-E001 | WARNING | POSITIVO sin nota de no compensacion |
| CC-F001 | WARNING | DESCARTADO_JUSTIFICADO sin justificacion |
| CC-MD-001 | ERROR | IMP esperado no aparece en markdown |
| CC-MD-002 | WARNING | IMP en markdown sin vocabulario Conesa |
| CC-MD-003 | WARNING | IMP en modelo no aparece en markdown |
| CC-MD-OK | INFO | IMP con tabla/seccion Conesa correcta |
| CC-MD-INDET | INFO | IMP con indicador de indeterminacion |

---

## Estados del resultado

| Estado | Descripcion |
|--------|-------------|
| `OK` | Todos los impactos tienen cobertura Conesa |
| `CON_OBSERVACIONES` | Solo warnings |
| `NO_CONFORME` | Al menos un ERROR |
| `SIN_DATOS` | Sin modelo ni markdowns |

`is_valid()` devuelve True solo si no hay ERRORs.
`administrative_ready` siempre False.

---

## CLI audit-conesa

```
python run_expediente.py <expediente> audit-conesa [--write]
```

Busca modelo en (por orden de prioridad):
1. `impactos/phase6_model_with_pva.json`
2. `impactos/phase6_model_with_measures.json`
3. `impactos/phase6_model_with_conesa.json`
4. `impactos/phase6_model_with_impacts.json`

Busca markdowns en: `bloques/*.md` e `impactos/*.md`.

**Sin `--write`:** imprime summary, exit 0/1.  
**Con `--write`:** escribe `auditoria/conesa_check_result.json` + `.md`.

---

## Como ejecutar los tests

```bash
venv\Scripts\python -m unittest tests.test_conesa_checker
venv\Scripts\python -m unittest discover -s tests
```

89 tests en `test_conesa_checker.py`, 0 fallos esperados.

---

*RD-06 completado 2026-05-17. EIA-Agent v2.1 — Productizacion P1.*
