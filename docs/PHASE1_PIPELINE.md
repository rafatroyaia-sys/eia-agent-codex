# PHASE1_PIPELINE — IN-06

Pipeline programático de Fase 1. Integra IN-01 + IN-02 + IN-03 + IN-05
en una sola llamada determinista sin IA.

## Módulo

`src/eia_agent/core/phase1_pipeline.py`

## API pública

```python
from eia_agent.core.phase1_pipeline import run_phase1

# Solo lectura (recomendado para diagnóstico)
result = run_phase1("expediente-EIA-2026-RECIMETAL-PARCELA")
print(result.summary())

# Con escritura de outputs en control_interno/
result = run_phase1("expediente-EIA-2026-RECIMETAL-PARCELA", write_outputs=True)
```

### run_phase1

```python
def run_phase1(
    expediente_path: str | Path,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase1Result
```

Pasos internos:
1. `build_inputs_index(parse_docx=False)` — índice de documentos. DOCX marcados como PROCESADO (optimista).
2. Contabilizar PDFs pendientes (sin parser disponible, IN-04).
3. Para cada DOCX: `classify_entities_from_docx()` → `ClassificationResult`.
4. `merge_candidate_facts()` — concatena sin deduplicar ni resolver conflictos.
5. Si `write_outputs=True`: escribe `phase1_result.json` y `phase1_result.md`.

### Phase1Result

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | Nombre del directorio del expediente |
| `inputs_index` | dict | Índice de documentos (de `build_inputs_index`) |
| `candidate_facts` | list[dict] | Hechos candidatos de todos los DOCX |
| `documents_processed` | int | Total documentos encontrados |
| `docx_processed` | int | DOCX procesados por el pipeline |
| `pdf_pending` | int | PDFs detectados sin parser |
| `warnings` | list[str] | Avisos del indexador y del clasificador |
| `notes` | list[str] | Notas operativas |

Métodos: `summary() -> str`, `to_dict() -> dict`.

### merge_candidate_facts

```python
def merge_candidate_facts(results: list[ClassificationResult]) -> list[dict]
```

Concatena hechos de múltiples resultados. No deduplica. No resuelve conflictos.
No eleva estados. Conserva fuentes.

### detect_phase1_basic_conflicts

```python
def detect_phase1_basic_conflicts(candidate_facts: list[dict]) -> list[dict]
```

Detecta valores múltiples para campos críticos:
`referencia_catastral`, `nombre_promotor`, `titular`, `capacidad`,
`superficie_parcela`, `superficie_catastral`, `superficie_construida`,
`superficie_util`, `superficie_nave`, `superficie_no_clasificada`.

Devuelve lista de `{"tipo": "valor_multiple", "campo", "valores", "fuentes", "n_hechos"}`.
Comparación case-insensitive. Valores `None` ignorados.

## CLI

```bash
# Solo lectura — imprime summary, no escribe nada
python run_expediente.py <expediente> phase1

# Con escritura de outputs
python run_expediente.py <expediente> phase1 --write
```

Salida `--write`:
- `control_interno/phase1_result.json` — resultado completo JSON
- `control_interno/phase1_result.md` — resumen markdown

## Garantías

- No usa IA.
- No procesa PDFs (los cuenta como `pdf_pending`).
- `write_outputs=False` (default): no escribe ningún archivo.
- No modifica `inputs/`.
- No crea `hechos_confirmados.json` ni modifica capas.
- Errores por DOCX individual quedan en `warnings`, no abortan el pipeline.

## Tests

`tests/test_phase1_pipeline.py` — 57 tests, 10 clases.

Cobertura:
- `Phase1Result`: estructura, `summary()`, `to_dict()`, serialización JSON
- `merge_candidate_facts`: vacío, un resultado, múltiples resultados, no-dedup, `None`/numeric
- `detect_phase1_basic_conflicts`: todos los campos monitoreados, case-insensitive, fuentes
- `run_phase1` con directorio vacío, con DOCX sintético, con PDF
- `write_outputs`: crea JSON y MD, directorio personalizado
- CLI: exit codes, no escritura sin `--write`, con `--write` crea archivos
- Pilots PARCELA y NAVE-222: solo lectura, no modifica inputs ni `control_interno/`
