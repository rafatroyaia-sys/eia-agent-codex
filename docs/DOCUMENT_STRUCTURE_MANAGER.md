# DOCUMENT_STRUCTURE_MANAGER — EN-02

## Qué hace

`document_structure_manager.py` valida y normaliza la estructura física del DOCX
final del Documento Ambiental. Comprueba que las secciones principales aparecen
en el orden canónico establecido, y permite reforzar la estructura con saltos
de página sin reordenar contenido de forma destructiva.

## Orden canónico

```
PORTADA → INDICE → A → B → C → D → E → F → G → H → I → J → K
         → ANEXO_GRAFICO → HOJA_FIRMAS
```

Total: 15 posiciones (PORTADA + INDICE + 11 bloques A-K + ANEXO + FIRMAS).

## Qué valida

| Regla | Código | Severidad |
|-------|--------|-----------|
| PORTADA presente | EN02-E001 | ERROR |
| INDICE presente | EN02-E002 | ERROR |
| Bloques A-K presentes | EN02-E003 | ERROR (uno por bloque ausente) |
| Orden de bloques A-K correcto | EN02-E004 | ERROR |
| HOJA_FIRMAS al final si existe | EN02-E005 | ERROR |
| ANEXO_GRAFICO antes que K si existe | EN02-E006 | ERROR |
| Sección duplicada | EN02-W001 | WARNING |
| ANEXO_GRAFICO ausente | EN02-W002 | WARNING |
| HOJA_FIRMAS ausente | EN02-W003 | WARNING |

**Ausencia de ANEXO y FIRMAS son warnings, no errores** — ambas son opcionales
en la validación estructural base (el anexo se añade con DOC-03, las firmas con DOC-08).

## Qué normaliza

La normalización es **conservadora** por diseño. Reordenar secciones complejas
con python-docx implica riesgo de corrupción del XML interno (referencias de
numeración, imágenes embebidas, campos de formulario).

La normalización:
- Crea una **copia** del DOCX (`documento_ambiental_estructurado.docx`).
- Refuerza `page_break_before=True` en headings de nivel 1 principales cuando falta.
- **No reordena secciones**.
- **No modifica contenido textual, tablas ni imágenes**.
- **No toca el DOCX original**.

## Qué NO hace

- No reescribe el contenido del Documento Ambiental.
- No regenera bloques desde cero.
- No llama a servicios externos.
- No inventa datos.
- No declara aptitud administrativa.

## Detección de secciones

La detección usa python-docx para iterar los párrafos del DOCX y clasificarlos:

| Sección | Criterio de detección |
|---------|----------------------|
| PORTADA | Párrafos con texto antes del primer Heading 1 |
| INDICE | Heading 1 con texto que contenga "indice" o "índice" |
| A…K | Heading 1 que comienza exactamente con la letra + separador (`—`, `-`, `.`, `:`) o espacio + mayúscula |
| ANEXO_GRAFICO | Heading 1 con texto que contenga "anexo grafico", "anexo gráfico", etc. |
| HOJA_FIRMAS | Heading 1 con texto que contenga "hoja de firmas", "firmas y revision", etc. |

El detector no se rompe si faltan secciones. Secciones no encontradas
tienen `found=False` y `paragraph_index=None`.

## Limitaciones de python-docx para reordenación

python-docx expone el documento como una lista plana de párrafos y tablas.
Reordenar una "sección" (que puede contener párrafos, imágenes, tablas,
listas, notas al pie, referencias de campo) exige manipular el XML subyacente
directamente, con riesgo de romper:

- Campos de numeración (`numbering.xml`)
- Referencias a imágenes (`_rels/document.xml.rels`)
- Campos TOC (`w:fldChar`, `w:instrText`)
- Estilos heredados

Por este motivo, EN-02 opta por validación + refuerzo de page breaks en lugar
de reordenación agresiva. Si el DOCX está mal montado estructuralmente, la
solución correcta es regenerarlo (DOC-01 + DOC-02 + DOC-03 + DOC-08).

## Diferencia entre validar y normalizar

| Operación | Modifica el DOCX | Crea nuevo archivo | Valida |
|-----------|-----------------|-------------------|--------|
| `validate_document_structure` | No | No | Sí |
| `normalize_document_structure` | No (copia) | Sí (estructurado.docx) | Sí (sobre la copia) |

## Relación con otros módulos

| Módulo | Relación |
|--------|----------|
| DOC-02 (`document_docx_builder`) | Genera el DOCX base con portada, índice y bloques A-K |
| DOC-03 (`document_figure_inserter`) | Añade el ANEXO_GRAFICO al final del DOCX base |
| DOC-08 (`document_presentation_preparer`) | Añade la HOJA_FIRMAS al final del DOCX |
| DOC-04 (`document_quality_checker`) | Valida contenido textual; EN-02 valida estructura física |

EN-02 es posterior a DOC-08: valida el DOCX final ya enriquecido con figuras y firmas.

## Selección automática del DOCX

El CLI selecciona el mejor DOCX disponible en este orden de preferencia:

1. `documento/documento_ambiental_final.docx`
2. `documento/documento_ambiental_borrador_con_firmas.docx`
3. `documento/documento_ambiental_borrador_con_figuras.docx`
4. `documento/documento_ambiental_borrador.docx`

## Uso CLI

```bash
# Solo validar (dry-run)
python run_expediente.py <expediente> document-structure

# Validar y escribir informe JSON + MD
python run_expediente.py <expediente> document-structure --write

# Crear copia normalizada
python run_expediente.py <expediente> document-structure --normalize

# Validar + normalizar + escribir informe
python run_expediente.py <expediente> document-structure --write --normalize
```

### Exit codes

| Código | Significado |
|--------|-------------|
| 0 | Estructura válida (sin errores EN02-E*) |
| 1 | Estructura con errores, DOCX no encontrado, o error de ejecución |

Warnings (EN02-W*) no afectan al exit code.

## API Python

```python
from eia_agent.core.document_structure_manager import (
    detect_document_sections,
    validate_document_structure,
    normalize_document_structure,
    write_document_structure_outputs,
    build_document_structure_markdown,
    find_best_available_docx,
    CANONICAL_DOCUMENT_ORDER,
    BLOCK_IDS,
)

# Detección
sections = detect_document_sections("documento/borrador.docx")

# Validación
result = validate_document_structure("documento/borrador.docx")
print(result.summary())
print(result.is_valid())

# Normalización (conservadora)
result = normalize_document_structure(
    "documento/borrador_con_figuras.docx",
    "documento/estructurado.docx",
    include_page_breaks=True,
)

# Outputs
paths = write_document_structure_outputs(result, "documento/")
```

## Tests

```bash
# Solo EN-02
venv\Scripts\python -m unittest tests.test_document_structure_manager

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

100 tests en 10 clases. 100% offline. Sin DOCX reales (usa DOCXs sintéticos
generados con python-docx en memoria dentro de `tempfile.TemporaryDirectory`).
