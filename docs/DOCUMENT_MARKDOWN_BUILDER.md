# DOCUMENT_MARKDOWN_BUILDER — DOC-01

Módulo: `src/eia_agent/core/document_markdown_builder.py`  
CLI: `python run_expediente.py <expediente> document-build-md [--write]`  
Tests: `tests/test_document_markdown_builder.py` (108 tests)

---

## Qué hace DOC-01

Genera un borrador Markdown completo del Documento Ambiental (bloques A-K) a
partir del manifest DOC-00 y de los outputs técnicos ya generados por el pipeline.

Es el segundo paso del proceso de ensamblado del Documento Ambiental: primero
DOC-00 inventaría lo que existe, y DOC-01 lee esos archivos y genera el texto.

### Principio

**Determinista**: el mismo expediente siempre produce el mismo output.  
**Trazable**: cada dato del documento proviene de un archivo JSON del pipeline.  
**Prudente**: si un dato falta, lo dice claramente. No inventa contenido.

---

## Qué NO hace DOC-01

- **No genera DOCX.** Eso es DOC-02 (siguiente paso pendiente).
- **No inventa datos.** Si falta un archivo fuente, el bloque queda PARTIAL o MISSING con aviso visible.
- **No corrige outputs técnicos.** El módulo transcribe; no evalúa ni modifica impactos, medidas, PVA ni auditorías.
- **No declara aptitud administrativa.** La calificación la determina el órgano ambiental.
- **No cierra gaps.** Los gaps activos del inventario y de los impactos se mantienen visibles en el documento.
- **No modifica el expediente** salvo escritura de `documento/` con `--write`.

---

## Bloques A-K

| Bloque | Título | Fuentes principales |
|--------|--------|---------------------|
| A | Identificación y descripción del proyecto | `control_interno/phase2_result.json`, `impactos/phase6_actions.json` |
| B | Inventario ambiental | `inventario/inventory_summary.json`, `inventario/phase5_gate_result.json`, fichas FI-*.md |
| C | Identificación y valoración de impactos | `impactos/phase6_model_with_conesa.json`, `impactos/cumulative_synergistic_result.json`, `auditoria/conesa_check_result.json` |
| D | Medidas preventivas, correctoras, protectoras, diagnósticas y documentales | `impactos/phase6_model_with_measures.json`, `auditoria/diagnostic_measure_validation_result.json`, `auditoria/prl_measure_validation_result.json` |
| E | Programa de vigilancia ambiental | `impactos/phase6_model_with_pva.json`, `impactos/pva_coverage_result.json` |
| F | Vulnerabilidad ante riesgos y catástrofes | `inventario/inventory_summary.json`, `impactos/phase6_model_with_conesa.json` |
| G | Alternativas y justificación de solución adoptada | `control_interno/phase3_result.json` (siempre PARTIAL: requiere datos del promotor) |
| H | Red Natura 2000 y espacios naturales protegidos | `inventario/inventory_summary.json`, `impactos/phase6_model_with_conesa.json`, `auditoria/block_consistency_result.json` |
| I | Conclusiones técnicas | `auditoria/final_audit_result.json`, `impactos/cumulative_synergistic_result.json` |
| J | Resumen no técnico | `auditoria/final_audit_result.json`, `impactos/phase6_model_with_pva.json` (+ datos de A/B/C/D/E) |
| K | Anexos y documentación complementaria | Listado de archivos en `cartografia/`, `clima/`, `inputs/`, `auditoria/`, `inventario/`, `impactos/` |

---

## Estados de bloque

| Estado | Significado |
|--------|-------------|
| `GENERATED` | Todas las fuentes principales encontradas; contenido generado |
| `PARTIAL` | Algunas fuentes presentes; contenido parcialmente generado con avisos |
| `MISSING` | Sin fuentes principales; bloque no puede generarse |
| `SKIPPED` | Bloque explícitamente omitido (reservado para uso futuro) |

`is_complete_draft()` devuelve `True` solo si no hay bloques `MISSING`.
Bloques `PARTIAL` no bloquean el borrador, pero quedan advertidos.

---

## Outputs generados (con `--write`)

```
documento/
├── documento_ambiental_borrador.md    ← Borrador Markdown completo
└── document_build_result.json         ← Metadatos del proceso de generación
```

Sin `--write`, el módulo opera completamente en memoria y no escribe nada.

---

## CLI

```
python run_expediente.py <expediente> document-build-md [--write]
```

| Opción | Descripción |
|--------|-------------|
| (sin opción) | Genera en memoria, imprime summary, no escribe |
| `--write` | Escribe `documento/documento_ambiental_borrador.md` y `documento/document_build_result.json` |

**Códigos de salida:**
- `0` → ningún bloque MISSING (`is_complete_draft() == True`). Puede haber PARTIAL.
- `1` → hay bloques MISSING o error de ejecución.

Los bloques PARTIAL muestran avisos pero **no bloquean** el exit 0.

---

## API pública

### `build_document_markdown(expediente_path, write_outputs=False) -> DocumentMarkdownBuildResult`

Función principal. Construye el manifest (DOC-00), genera los 11 bloques A-K y
ensambla el markdown final. Si `write_outputs=True`, escribe los outputs en
`documento/`.

### `assemble_document_markdown(blocks) -> str`

Ensambla el markdown completo a partir de una lista de `DocumentBlockBuildResult`.
Incluye portada, advertencia de no-aptitud, índice y bloques en orden A-K.

### `safe_read_text(path) -> str | None`

Lee un archivo de texto. Devuelve `None` si no existe o no es legible.

### `safe_load_json(path) -> dict | list | None`

Carga un JSON. Devuelve `None` si no existe, no es legible o está corrupto.

### `format_missing_notice(block_id, missing_files) -> str`

Genera un aviso visible para archivos faltantes. Devuelve `""` si la lista está vacía.

### `build_block_X(expediente_path, manifest_item) -> DocumentBlockBuildResult`

Funciones `build_block_a` a `build_block_k`. Cada una genera el markdown de un
bloque a partir de los archivos disponibles. Nunca lanza excepción por ausencia
de archivos (devuelve MISSING/PARTIAL con aviso).

---

## Dataclasses

### `DocumentBlockBuildResult`

```python
@dataclass
class DocumentBlockBuildResult:
    block_id: str
    title: str
    status: str          # GENERATED / PARTIAL / MISSING / SKIPPED
    source_files: list[str]
    missing_files: list[str]
    markdown: str
    warnings: list[str]
    notes: list[str]
```

Métodos: `to_dict()`, `summary()`.

### `DocumentMarkdownBuildResult`

```python
@dataclass
class DocumentMarkdownBuildResult:
    expediente_id: str
    output_markdown_path: str | None
    blocks: list[DocumentBlockBuildResult]
    generated_blocks: list[str]
    partial_blocks: list[str]
    missing_blocks: list[str]
    warnings: list[str]
    notes: list[str]
```

Métodos: `generated_count()`, `partial_count()`, `missing_count()`,
`is_complete_draft()`, `to_dict()`, `summary()`.

---

## Reglas metodológicas

1. **No inventar datos**: si el archivo fuente no existe, el bloque muestra un aviso.
2. **No cerrar impactos indeterminados**: los `INDETERMINADO` permanecen visibles.
3. **No cerrar afección a Red Natura**: si hay gaps activos en FI-009/FI-010, se mantienen.
4. **Medidas diagnósticas ≠ reductoras**: el Bloque D advierte explícitamente.
5. **PRL separado de EIA**: el Bloque D mantiene la separación PRL/EIA.
6. **Bloque J sin frases prohibidas**: el resumen no técnico no contiene:
   - "sin afección"
   - "apto administrativamente"
   - "se descarta"
   - "todos compatibles"
7. **Bloque G siempre PARTIAL**: en modo gabinete las alternativas requieren datos del promotor.

---

## Cómo ejecutar los tests

```
python -m unittest tests.test_document_markdown_builder
python -m unittest discover -s tests
```

Tests 100% offline: usan `tempfile`, sin red, sin IA, sin APIs.

---

## Relación con DOC-00

DOC-00 (`document_manifest.py`) comprueba qué archivos existen (solo `Path.exists()`).
DOC-01 (`document_markdown_builder.py`) lee y procesa esos archivos para generar el markdown.

DOC-01 siempre llama a `build_document_manifest()` internamente para obtener el estado
actual del expediente antes de construir los bloques.

---

## Siguiente paso: DOC-02

DOC-02 (pendiente) tomará el markdown generado por DOC-01 y lo convertirá en DOCX
profesional con python-docx, portada, TOC, estilos y mapas.

---

## Ejecución típica

```bash
# Ver estado sin escribir
python run_expediente.py expediente-EIA-NAVE-222 document-build-md

# Generar borrador Markdown
python run_expediente.py expediente-EIA-NAVE-222 document-build-md --write

# Flujo completo sugerido
python run_expediente.py expediente-EIA-NAVE-222 run-technical-pipeline --write
python run_expediente.py expediente-EIA-NAVE-222 document-manifest --write
python run_expediente.py expediente-EIA-NAVE-222 document-build-md --write
```
