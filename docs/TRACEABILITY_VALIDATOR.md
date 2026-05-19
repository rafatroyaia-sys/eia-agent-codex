# TRACEABILITY_VALIDATOR — AU-03

Módulo: `src/eia_agent/core/traceability_validator.py`  
CLI: `python run_expediente.py <expediente> audit-traceability [--write]`  
Tests: `tests/test_traceability_validator.py` (117 tests)

---

## Qué hace AU-03

Valida la **trazabilidad entre los textos del Documento Ambiental y las capas de datos del expediente**: hechos confirmados, inventario, impactos, medidas, PVA, cartografía y normativa.

Para cada afirmación técnica extraída de los markdowns del expediente, determina si está respaldada por alguna referencia cargable desde los JSONs disponibles.

---

## Qué NO hace AU-03

- **No corrige textos** del expediente.
- **No sustituye la revisión técnica o jurídica** del Documento Ambiental.
- **No declara aptitud administrativa**. La clasificación del expediente corresponde al órgano ambiental.
- **No valora impactos** ni genera medidas ni PVA.
- **No usa IA** ni consulta fuentes externas.
- **No modifica** ningún archivo del expediente.

---

## Estados de trazabilidad

| Estado | Significado |
|--------|-------------|
| `TRAZADO` | La afirmación contiene un ID explícito del sistema (FI-xxx, IMP-xxx, MED-xxx…) que existe en las referencias cargadas, o hay coincidencia textual fuerte. |
| `PARCIAL` | La afirmación hace referencia a un tema ambiental reconocible (flora, ruido, Red Natura…) pero sin ID explícito verificado; o contiene un ID del sistema pero el JSON origen no está cargado. |
| `NO_TRAZADO` | La afirmación es técnicamente concreta (contiene mediciones, unidades, datos específicos) pero no se puede vincular a ninguna referencia ni tema conocido. → **ERROR** |
| `NO_APLICA` | La afirmación es puramente metodológica, un título genérico o una advertencia de alcance. No genera incidencia. |

---

## Fuentes de referencias cargadas

El módulo busca estos archivos (carga lo que exista, ignora lo ausente):

**Capas y control:**
- `capas/hechos_confirmados.json` → HECHO_CONFIRMADO
- `capas/inferencias_y_gaps.json` → GAP
- `capas/normativa_aplicable.json` → NORMATIVA
- `capas/cartografia_trace.json` → CARTOGRAFIA
- `control_interno/phase2_result.json` → TEXTO
- `control_interno/phase3_result.json` → NORMATIVA

**Inventario:**
- `inventario/inventory_summary.json` → INVENTARIO
- `inventario/phase5_gate_result.json` → INVENTARIO

**Impactos (del más completo al más básico):**
- `impactos/phase6_model_with_pva.json` → IMPACTO
- `impactos/phase6_model_with_measures.json` → IMPACTO
- `impactos/phase6_model_with_conesa.json` → IMPACTO
- `impactos/phase6_model_with_impacts.json` → IMPACTO
- `impactos/cumulative_synergistic_result.json` → IMPACTO
- `impactos/pva_coverage_result.json` → PVA

**Auditoría:**
- `auditoria/art45_checklist_result.json` → NORMATIVA
- `auditoria/prudence_validation_result.json` → TEXTO

Si un JSON está corrupto, se registra una referencia especial `ERR-<nombre>` y el proceso continúa.

---

## Reglas de detección (claim_has_traceability)

El algoritmo opera por prioridad:

1. **NO_APLICA** si la afirmación tiene < 15 caracteres normalizados o contiene indicadores metodológicos (`el presente documento`, `a continuacion`, `esta auditoria no`…).

2. **TRAZADO** si la afirmación contiene un ID del sistema (`FI-xxx`, `FR-xxx`, `IMP-xxx`, `MED-xxx`, `PVA-xxx`, `HC-xxx`, `GAP-xxx`, `CT-xxx`, `NJ-xxx`) Y ese ID existe en las referencias cargadas.

3. **PARCIAL** si contiene IDs del sistema pero ninguno está en referencias (expediente incompleto — el autor usa el convenio de IDs pero los JSONs aún no están generados).

4. **PARCIAL** si hay coincidencia con palabras clave de un factor ambiental conocido:
   - `ruido`, `acustico`, `nivel sonoro` → FI-014
   - `flora`, `vegetacion`, `habitats` → FI-007
   - `red natura`, `natura 2000`, `LIC`, `ZEPA` → FI-010
   - `patrimonio`, `yacimiento`, `arqueolog` → FI-012
   - … (16 factores FI-001 a FI-016)

5. **NO_TRAZADO** si la afirmación contiene patrones de medición técnica concreta (m², dBA, °C, ppm, mg/l, PM10…) sin ningún tema ni ID.

6. **NO_APLICA** como fallback para texto genérico sin contenido técnico medible.

---

## API pública

### `normalize_traceability_text(text) -> str`
Normaliza texto: sin tildes, minúsculas, espacios normalizados. Conserva códigos FI-xxx, IMP-xxx, etc.

### `extract_traceability_references_from_dict(data, source_type, prefix_hint) -> list[TraceabilityReference]`
Traversal recursivo de JSON. Extrae referencias de campos: `factor_id`, `impact_id`, `measure_id`, `pva_id`, `gap_id`, `hecho_id`, `action_id`, `requirement_id`, `id`, `code`. Tolerante con claves ausentes y tipos inesperados.

### `load_traceability_references(expediente_path) -> list[TraceabilityReference]`
Carga todas las referencias disponibles del expediente. Sin excepción por archivos ausentes.

### `extract_claims_from_markdown(markdown) -> list[str]`
Extrae afirmaciones de: encabezados, bullets, listas ordenadas, filas de tabla, párrafos. Filtra líneas vacías, separadores, bloques de código y claims muy cortos.

### `claim_has_traceability(claim, references) -> tuple[str, list[str]]`
Devuelve `(status, candidate_refs)`.

### `validate_markdown_traceability(markdown, references, source) -> TraceabilityResult`
Valida un markdown completo. TRAZADO → sin incidencia; PARCIAL → WARNING; NO_TRAZADO → ERROR.

### `validate_traceability_from_files(expediente_path) -> TraceabilityResult`
Carga referencias + revisa markdowns de `bloques/`, `inventario/`, `impactos/`, `auditoria/`. Lanza `FileNotFoundError` si el expediente no existe. Devuelve WARNING si no hay markdowns.

### `build_traceability_report_markdown(result) -> str`
Informe en 9 secciones: resumen, fuentes, referencias, trazadas, parciales, no trazadas, incidencias, recomendaciones, advertencia de alcance.

### `write_traceability_validation_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `traceability_validation_result.json` y `.md` en el directorio indicado.

---

## Modelos de datos

### `TraceabilityReference`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ref_id` | str | ID de la referencia: FI-007, IMP-001, MED-003… |
| `source_type` | str | INVENTARIO / IMPACTO / MEDIDA / PVA / GAP / HECHO_CONFIRMADO / NORMATIVA / CARTOGRAFIA / CLIMA / TEXTO |
| `label` | str | Etiqueta corta (nombre del factor, impacto, etc.) |
| `text` | str | Texto libre asociado (descripción, notas) |
| `metadata` | dict | Metadatos adicionales (fuente JSON, ruta) |

### `TraceabilityIssue`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | str | `ERROR` / `WARNING` / `INFO` |
| `code` | str | `AU03-E001` (no trazado) / `AU03-W001` (parcial) / `AU03-I001` (info) |
| `source` | str | Ruta relativa del markdown donde se detectó |
| `claim` | str | Afirmación problemática (máx. 120 chars) |
| `message` | str | Descripción de la incidencia |
| `recommendation` | str | Acción recomendada |
| `candidate_refs` | list[str] | IDs o factores candidatos encontrados |

### `TraceabilityResult`

Métodos: `error_count()`, `warning_count()`, `info_count()`, `is_valid()`, `to_dict()`, `summary()`.

`is_valid()` → True solo si `error_count() == 0`.

---

## CLI

```
python run_expediente.py <expediente> audit-traceability [--write]
```

**Sin `--write`**: imprime el resumen. No crea archivos.  
**Con `--write`**: además escribe `auditoria/traceability_validation_result.json` y `.md`.

**Códigos de salida:**
- `0` — sin incidencias ERROR (`is_valid() == True`)
- `1` — hay incidencias ERROR, o el expediente no existe

---

## Ejecución de tests

```
python -m unittest tests.test_traceability_validator
python -m unittest discover -s tests
```

Los tests son completamente offline: no requieren web, IA ni APIs. Usan `tempfile.TemporaryDirectory` para expedientes temporales.

---

## Limitaciones conocidas

- La detección de `NO_TRAZADO` solo actúa sobre patrones de medición explícitos (m², dBA, °C, mg/l…). Afirmaciones técnicas sin unidades de medida se clasifican como `NO_APLICA` por defecto.
- La coincidencia por keywords es aproximada: puede generar `PARCIAL` para frases que mencionan términos ambientales en contexto no técnico.
- Sin JSONs de referencias cargados, todos los IDs del sistema se clasifican como `PARCIAL` (se usa el convenio de nomenclatura pero no se puede verificar la existencia del objeto).
