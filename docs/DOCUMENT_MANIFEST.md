# DOCUMENT_MANIFEST — DOC-00

Módulo: `src/eia_agent/core/document_manifest.py`  
CLI: `python run_expediente.py <expediente> document-manifest [--write]`  
Tests: `tests/test_document_manifest.py` (63 tests)

---

## Qué hace DOC-00

Construye el manifest del Documento Ambiental: relaciona cada bloque (A-K)
con los archivos ya generados por el pipeline técnico y determina qué bloques
están listos para redacción, cuáles parciales y cuáles no tienen inputs suficientes.

Es el primer paso del proceso de ensamblado del Documento Ambiental: inventaria
lo que existe antes de intentar escribir nada.

---

## Qué NO hace DOC-00

- **No redacta el Documento Ambiental.** Solo verifica inputs.
- **No genera DOCX.** Eso es DOC-02 (fase de ensamblado).
- **No corrige outputs del pipeline.** Comprueba existencia, no contenido.
- **No carga JSON.** Solo hace `Path.exists()` sobre cada archivo.
- **No declara aptitud administrativa.** La calificación la determina el órgano ambiental.
- **No modifica expediente** salvo escritura del manifest con `--write`.

---

## Bloques A-K del Documento Ambiental

| Bloque | Título |
|--------|--------|
| A | Identificación y descripción del proyecto |
| B | Inventario ambiental |
| C | Identificación y valoración de impactos |
| D | Medidas preventivas, correctoras, protectoras, diagnósticas y documentales |
| E | Programa de vigilancia ambiental |
| F | Vulnerabilidad ante riesgos y catástrofes |
| G | Alternativas y justificación de solución adoptada |
| H | Red Natura 2000 y espacios naturales protegidos |
| I | Conclusiones técnicas |
| J | Resumen no técnico |
| K | Anexos y documentación complementaria |

---

## Inputs esperados por bloque

Los inputs son archivos o directorios generados por el pipeline técnico.
Todos los nombres de archivo usan el nombre real del output del pipeline.

| Bloque | Inputs requeridos |
|--------|------------------|
| A | `impactos/phase6_actions.json`, `capas/hechos_confirmados.json` |
| B | `inventario/inventory_summary.json`, `inventario/phase5_gate_result.json` |
| C | `impactos/phase6_model_with_conesa.json`, `impactos/phase6_model_with_impacts.json`, `impactos/cumulative_synergistic_result.json`, `auditoria/conesa_check_result.json` |
| D | `impactos/phase6_model_with_measures.json`, `auditoria/diagnostic_measure_validation_result.json`, `auditoria/prl_measure_validation_result.json` |
| E | `impactos/phase6_model_with_pva.json`, `impactos/pva_coverage_result.json` |
| F | `inventario/inventory_summary.json`, `impactos/phase6_model_with_conesa.json` |
| G | `capas/normativa_aplicable.json`, `capas/hechos_confirmados.json` |
| H | `inventario/inventory_summary.json`, `impactos/phase6_model_with_conesa.json`, `auditoria/block_consistency_result.json` |
| I | `auditoria/final_audit_result.json`, `impactos/cumulative_synergistic_result.json` |
| J | `auditoria/final_audit_result.json`, `impactos/phase6_model_with_pva.json` |
| K | `inputs/` (dir), `capas/` (dir), `clima/` (dir) |

**Nota importante:** el archivo del paso PHASE6_ASSIGN_CONESA se llama
`phase6_model_with_conesa.json`, NO `phase6_model_scored.json`.

---

## Estado por bloque

| Estado | Condición |
|--------|-----------|
| `READY` | Todos los inputs requeridos existen |
| `PARTIAL` | Algunos inputs existen pero no todos |
| `MISSING` | No hay inputs requeridos disponibles |

`is_ready_for_markdown_generation()` devuelve `True` si ningún bloque está en MISSING.
Puede haber bloques PARTIAL — el manifest los advierte pero no bloquea.

---

## Relación con el pipeline técnico (PIPE-03)

El manifest consume los outputs generados por los 17 pasos del pipeline técnico:

| Output del pipeline | Bloque(s) |
|--------------------|-----------|
| `inventario/inventory_summary.json` | B, F, H |
| `inventario/phase5_gate_result.json` | B |
| `impactos/phase6_actions.json` | A |
| `impactos/phase6_model_with_conesa.json` | C, F, H |
| `impactos/phase6_model_with_impacts.json` | C |
| `impactos/phase6_model_with_measures.json` | D |
| `impactos/phase6_model_with_pva.json` | E, J |
| `impactos/pva_coverage_result.json` | E |
| `impactos/cumulative_synergistic_result.json` | C, I |
| `auditoria/conesa_check_result.json` | C |
| `auditoria/diagnostic_measure_validation_result.json` | D |
| `auditoria/prl_measure_validation_result.json` | D |
| `auditoria/block_consistency_result.json` | H |
| `auditoria/final_audit_result.json` | I, J |
| `capas/hechos_confirmados.json`, `capas/normativa_aplicable.json` | A, G |

---

## CLI

```
python run_expediente.py <expediente> document-manifest [--write]
```

| Opción | Descripción |
|--------|-------------|
| `--write` | Escribe `documento/document_manifest.json` y `documento/document_manifest.md` |

**Códigos de salida:**
- `0` → ningún bloque MISSING (todos READY o PARTIAL)
- `1` → hay bloques MISSING o el expediente no existe

---

## API pública

### `build_document_manifest(expediente_path) -> DocumentManifestResult`
Construye el manifest comprobando existencia de archivos. No carga JSON.
Lanza `FileNotFoundError` si el directorio del expediente no existe.

### `build_document_manifest_markdown(result) -> str`
Genera informe markdown con 6 secciones: resumen, estado por bloque, archivos
existentes, archivos faltantes, advertencias, siguiente paso.

### `write_document_manifest_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `document_manifest.json` y `document_manifest.md` en `output_dir`.

---

## Ejecución de tests

```
python -m unittest tests.test_document_manifest
python -m unittest discover -s tests
```

Tests 100% offline: usan `tempfile`, sin red, sin IA, sin APIs.

---

## Relación con QA-03

QA-03 verificó que el pipeline de 17 pasos genera todos los outputs necesarios
para que los bloques A-K queden en estado READY o PARTIAL. El manifest DOC-00
formaliza esa relación como código determinista y ejecutable.
