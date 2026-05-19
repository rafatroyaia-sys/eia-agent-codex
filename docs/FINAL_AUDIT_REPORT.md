# FINAL_AUDIT_REPORT — AU-04

Módulo: `src/eia_agent/core/final_audit_report.py`  
CLI: `python run_expediente.py <expediente> audit-final [--write]`  
Tests: `tests/test_final_audit_report.py` (104 + nuevos RD-04/RD-06 tests)

---

## Qué hace AU-04

Combina los resultados de las auditorías previas en un **informe final ejecutivo**:

| Fuente | Módulo | Archivo JSON |
|--------|--------|--------------|
| AU-01 | art45_checklist | `auditoria/art45_checklist_result.json` |
| AU-02 | prudence_validator | `auditoria/prudence_validation_result.json` |
| AU-03 | traceability_validator | `auditoria/traceability_validation_result.json` |
| RD-04 | block_consistency_validator | `auditoria/block_consistency_result.json` |
| RD-06 | conesa_checker | `auditoria/conesa_check_result.json` |
| RD-08 | diagnostic_measure_validator | `auditoria/diagnostic_measure_validation_result.json` |
| RD-09 | prl_measure_validator | `auditoria/prl_measure_validation_result.json` |

RD-04, RD-06, RD-08 y RD-09 son opcionales: si el archivo no existe, no se genera ninguna incidencia adicional (retrocompatible con expedientes que solo tienen AU-01/02/03).

Emite una calificación final (`CONFORME`, `CONFORME_CON_OBSERVACIONES`, `NO_CONFORME`, `INCOMPLETO`) y un informe en JSON y Markdown con incidencias ordenadas por severidad.

---

## Qué NO hace AU-04

- **No ejecuta AU-01, AU-02, AU-03, RD-04, RD-06, RD-08 ni RD-09 automáticamente.** Solo combina sus resultados existentes.
- **No corrige textos** del expediente.
- **No declara aptitud administrativa.** La calificación es interna.
- **No sustituye la revisión técnica ni jurídica** del Documento Ambiental.
- **No valora impactos** ni genera medidas ni PVA.
- **No usa IA** ni consulta fuentes externas.
- **No modifica** ningún archivo previo.

---

## Cómo combina AU-01 + AU-02 + AU-03 + RD-04 + RD-06 + RD-08 + RD-09

### De AU-01 (Checklist art.45):

| Situación | Severidad final |
|-----------|----------------|
| Auditoría no disponible | ALTA + estado INCOMPLETO |
| Requisito `NO_CUBIERTO` | ALTA |
| Requisito `PARCIAL` | MEDIA |
| Issue `ERROR` de AU-01 | ALTA |
| Issue `WARNING` de AU-01 | BAJA |

### De AU-02 (Prudencia metodológica):

| Situación | Severidad final |
|-----------|----------------|
| Auditoría no disponible | ALTA + estado INCOMPLETO |
| `ERROR` con frase de cierre grave (ver lista) | BLOQUEANTE |
| `ERROR` con otra frase prohibida | ALTA |
| `WARNING` | MEDIA |
| `INFO` | INFO |

**Frases de cierre indebido grave → BLOQUEANTE:**  
`sin afeccion`, `cumple limites`, `no hay red natura`, `sin especies protegidas`, `sin afeccion patrimonial`, `sin afeccion significativa`, `sin afeccion apreciable`, `fuera de red natura`, `no afecta a red natura`

### De AU-03 (Trazabilidad):

| Situación | Severidad final |
|-----------|----------------|
| Auditoría no disponible | ALTA + estado INCOMPLETO |
| Afirmaciones no trazadas > 5 | BLOQUEANTE |
| Issue `ERROR` (afirmación no trazada) | ALTA |
| Issue `WARNING` (afirmación parcial) | MEDIA |
| `INFO` | INFO |

### De RD-04 (Coherencia entre bloques):

| Situación | Severidad final |
|-----------|----------------|
| No disponible (None) | Sin incidencia — sin cambio de estado |
| Resultado corrupto | ALTA (AU04-E401) |
| `SIN_DATOS` | MEDIA (AU04-W402) |
| Issue `ERROR` de RD-04 | ALTA |
| Issue `WARNING` de RD-04 | MEDIA |

### De RD-06 (Cobertura Conesa):

| Situación | Severidad final |
|-----------|----------------|
| No disponible (None) | Sin incidencia — sin cambio de estado |
| Resultado corrupto | ALTA (AU04-E501) |
| `SIN_DATOS` | MEDIA (AU04-W502) |
| Impactos sin Conesa | ALTA (AU04-E502) |
| Issue `ERROR` de RD-06 | ALTA |
| Issue `WARNING` de RD-06 | MEDIA |

### De RD-08 (Medidas diagnósticas vs reductoras):

| Situación | Severidad final |
|-----------|----------------|
| No disponible (None) | Sin incidencia — sin cambio de estado |
| Resultado corrupto | ALTA (AU04-E601) |
| `SIN_DATOS` | MEDIA (AU04-W602) |
| `problematic_measures` no vacío | ALTA (AU04-E603) |
| Issue `ERROR` de RD-08 | ALTA |
| Issue `WARNING` de RD-08 | MEDIA |

### De RD-09 (Separación EIA / PRL):

| Situación | Severidad final |
|-----------|----------------|
| No disponible (None) | Sin incidencia — sin cambio de estado |
| Resultado corrupto | ALTA (AU04-E701) |
| `SIN_DATOS` | MEDIA (AU04-W702) |
| `problematic_measures` no vacío | ALTA (AU04-E703) |
| Issue `ERROR` de RD-09 | ALTA |
| Issue `WARNING` de RD-09 | MEDIA |

---

## Estados finales

| Estado | Condición |
|--------|-----------|
| `INCOMPLETO` | Falta alguna de las tres auditorías AU-01/AU-02/AU-03 (RD-04/RD-06/RD-08/RD-09 son opcionales) |
| `NO_CONFORME` | Hay incidencias BLOQUEANTE o ALTA |
| `CONFORME_CON_OBSERVACIONES` | Hay incidencias MEDIA o BAJA (sin BLOQUEANTE ni ALTA) |
| `CONFORME` | Solo incidencias INFO o ninguna |

**Prioridad:** INCOMPLETO > NO_CONFORME > CONFORME_CON_OBSERVACIONES > CONFORME

---

## Severidades

| Severidad | Significado |
|-----------|-------------|
| `BLOQUEANTE` | Incidencia grave que impide calificación positiva — cierre indebido o volumen excesivo de no-trazados |
| `ALTA` | Incidencia que requiere corrección — requisito no cubierto, error de prudencia, afirmación no trazada |
| `MEDIA` | Observación a mejorar — requisito parcial, lenguaje débil, afirmación parcialmente trazada |
| `BAJA` | Aviso menor — warning de AU-01 |
| `INFO` | Informativo — frase en contexto metodológico |

---

## API pública

### `load_audit_json(path) -> dict | None`
Carga un JSON si existe. Devuelve `None` si no existe. Si está corrupto, devuelve `{"corrupt": True, "error": "..."}`.

### `extract_final_issues_from_art45(data) -> list[FinalAuditIssue]`
Extrae incidencias del checklist AU-01.

### `extract_final_issues_from_prudence(data) -> list[FinalAuditIssue]`
Extrae incidencias del validador de prudencia AU-02.

### `extract_final_issues_from_traceability(data) -> list[FinalAuditIssue]`
Extrae incidencias del validador de trazabilidad AU-03.

### `extract_final_issues_from_block_consistency(data) -> list[FinalAuditIssue]`
Extrae incidencias del validador de coherencia RD-04. Si `data is None`, devuelve `[]` (retrocompatible).

### `extract_final_issues_from_conesa_check(data) -> list[FinalAuditIssue]`
Extrae incidencias del checker Conesa RD-06. Si `data is None`, devuelve `[]` (retrocompatible).

### `determine_final_audit_status(issues) -> str`
Determina el estado final a partir de la lista de incidencias consolidadas.

### `extract_final_issues_from_diagnostic_measures(data) -> list[FinalAuditIssue]`
Extrae incidencias del validador de medidas diagnósticas RD-08. Si `data is None`, devuelve `[]` (retrocompatible).

### `extract_final_issues_from_prl_measures(data) -> list[FinalAuditIssue]`
Extrae incidencias del validador de separación EIA/PRL RD-09. Si `data is None`, devuelve `[]` (retrocompatible).

### `build_final_audit_result(expediente_id, art45_data, prudence_data, traceability_data, block_consistency_data=None, conesa_check_data=None, diagnostic_measure_data=None, prl_measure_data=None) -> FinalAuditResult`
Construye el resultado final combinando hasta 7 fuentes de auditoría (RD-04/RD-06/RD-08/RD-09 opcionales).

### `build_final_audit_from_files(expediente_path) -> FinalAuditResult`
Construye el resultado leyendo los JSONs desde `auditoria/`. Lanza `FileNotFoundError` si el expediente no existe. No lanza excepción por ausencia de archivos individuales.

### `build_final_audit_report_markdown(result) -> str`
Genera el informe en markdown con 13 secciones (incluye secciones 5 RD-04, 6 RD-06, 7 RD-08 y 8 RD-09).

### `write_final_audit_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `final_audit_result.json` y `final_audit_result.md`.

---

## Modelos de datos

### `FinalAuditIssue`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | str | BLOQUEANTE / ALTA / MEDIA / BAJA / INFO |
| `source` | str | AU-01_ART45 / AU-02_PRUDENCE / AU-03_TRACEABILITY / RD-04_BLOCK_CONSISTENCY / RD-06_CONESA_CHECK / SISTEMA |
| `code` | str | AU04-E001, AU04-M001… |
| `message` | str | Descripción de la incidencia |
| `recommendation` | str | Acción recomendada |
| `related_requirement` | str \| None | Requisito afectado (ART45-xx) |
| `related_file` | str \| None | Archivo fuente original |

### `FinalAuditResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente |
| `status` | str | Estado final |
| `administrative_ready` | bool | **Siempre False** |
| `art45_summary` | dict | Resumen de AU-01 |
| `prudence_summary` | dict | Resumen de AU-02 |
| `traceability_summary` | dict | Resumen de AU-03 |
| `block_consistency_summary` | dict | Resumen de RD-04 (vacío si no disponible) |
| `conesa_check_summary` | dict | Resumen de RD-06 (vacío si no disponible) |
| `diagnostic_measure_summary` | dict | Resumen de RD-08 (vacío si no disponible) |
| `prl_measure_summary` | dict | Resumen de RD-09 (vacío si no disponible) |
| `issues` | list | Incidencias consolidadas |
| `blocking_count` | int | Número de BLOQUEANTE |
| `high_count` | int | Número de ALTA |
| `medium_count` | int | Número de MEDIA |
| `low_count` | int | Número de BAJA |

Métodos: `error_count()` (= blocking + high), `has_blocking_issues()`, `is_conforme()`, `to_dict()`, `summary()`.

---

## CLI

```
python run_expediente.py <expediente> audit-final [--write]
```

**Sin `--write`**: imprime el resumen. No crea archivos.  
**Con `--write`**: escribe `auditoria/final_audit_result.json` y `.md`.

**Códigos de salida:**
- `0` — CONFORME o CONFORME_CON_OBSERVACIONES
- `1` — NO_CONFORME, INCOMPLETO, o expediente no encontrado

**Importante:** AU-04 **no ejecuta** las auditorías previas. Para un informe completo, ejecutar primero:
```
python run_expediente.py <exp> audit-art45 --write
python run_expediente.py <exp> audit-prudence --write
python run_expediente.py <exp> audit-traceability --write
python run_expediente.py <exp> audit-final --write
```

---

## Ejecución de tests

```
python -m unittest tests.test_final_audit_report
python -m unittest discover -s tests
```

Los tests son 100% offline: no requieren web, IA ni APIs. Usan `tempfile` para expedientes temporales con JSONs de auditoría simulados.
