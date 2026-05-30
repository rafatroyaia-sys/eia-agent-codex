# DOCUMENT_TOC_MANAGER — EN-05

## Qué hace

`document_toc_manager.py` gestiona el índice automático (TOC) del DOCX final
del Documento Ambiental. Permite:

1. **Detectar** si un DOCX contiene un campo TOC Word (mediante inspección ZIP).
2. **Insertar o reemplazar** un campo TOC en una copia del DOCX.
3. **Habilitar updateFields** en `word/settings.xml` para que Word/LibreOffice
   actualice el índice al abrir el documento.
4. **Generar informe** JSON y Markdown del resultado.
5. **No modificar el DOCX original** en ningún caso.

## Qué NO hace

- No modifica el DOCX original.
- No calcula números de página (eso lo hace Word/LibreOffice al abrir).
- No llama a Word COM, LibreOffice, ni ningún conversor externo.
- No declara aptitud administrativa.
- No usa IA, no llama a APIs externas.
- No genera PDF.
- No reordena párrafos ni secciones.

## Advertencia clave

python-docx **inserta el campo TOC** en el XML del DOCX pero **NO puede
actualizar los números de página**. El índice quedará vacío o con números
de página erróneos hasta que el documento se abra en Word o LibreOffice
Writer y se actualicen los campos (Ctrl+A, F9 en Word).

Si `word/settings.xml` contiene `<w:updateFields w:val="true"/>`, Word
actualiza automáticamente todos los campos al abrir el documento.
EN-05 añade esta instrucción a la copia de salida.

## Diferencia entre analizar y aplicar

| Operación | Modifica el DOCX | Crea nuevo archivo | Inserta TOC |
|-----------|-----------------|-------------------|-------------|
| `analyze_toc` | No | No | No |
| `detect_toc_in_docx` | No | No | No |
| `insert_or_replace_toc` | No (copia) | Sí (con_toc.docx) | Sí |
| `process_document_toc(apply_toc=False)` | No | No | No |
| `process_document_toc(apply_toc=True)` | No | Sí | Sí |

## Detección de TOC

### Inspección de `word/document.xml`

Se buscan dos patrones XML mediante expresiones regulares sobre el texto
del archivo (lectura via `zipfile.ZipFile`, sin modificar el DOCX):

| Patrón | Qué detecta |
|--------|-------------|
| `<w:instrText[^>]*>([^<]*)</w:instrText>` con "TOC" | Campo TOC complejo |
| `<w:fldSimple[^>]+w:instr="([^"]*)"` con "TOC" | Campo TOC simple |

### Inspección de `word/settings.xml`

Se busca `<w:updateFields[^>]+w:val="(true|1|on)"` (insensible a mayúsculas)
para determinar si Word actualizará los campos al abrir.

## Detección de placeholders de TOC

`find_toc_placeholder_paragraphs` busca párrafos candidatos a ser reemplazados
por el campo TOC. Criterios de selección:

| Criterio | Valor |
|----------|-------|
| Longitud máxima | 80 caracteres |
| Keywords (case-insensitive) | `índice`, `indice`, `tabla de contenido`, `tabla de contenidos`, `toc` |

Si se encuentra un placeholder, se reemplaza su contenido con el campo TOC
sin eliminar el párrafo (conserva atributos de estilo del párrafo original).
Si no hay placeholder, el TOC se inserta como primer elemento del documento.

## Instrucción TOC por defecto

```
TOC \o "1-3" \h \z \u
```

| Modificador | Significado |
|-------------|-------------|
| `\o "1-3"` | Incluye encabezados de nivel 1-3 |
| `\h` | Inserta hipervínculos |
| `\z` | Oculta números de página en vista web |
| `\u` | Usa estilos de título aplicados al documento |

## Orden de preferencia de DOCX

```
1. documento/documento_ambiental_numerado.docx        (output EN-04)
2. documento/documento_ambiental_final_revisable.docx (output DOC-08)
3. documento/documento_ambiental_estructurado.docx    (output EN-02)
4. documento/documento_ambiental_borrador_con_figuras.docx (output DOC-03)
5. documento/documento_ambiental_borrador.docx        (output DOC-02)
```

## Códigos de incidencia

| Código | Severidad | Condición |
|--------|-----------|-----------|
| EN05-E001 | ERROR | DOCX no encontrado, corrupto o no abrible |
| EN05-E002 | ERROR | Error al guardar el DOCX con TOC |

Los avisos (warnings) se registran en `result.warnings` sin código propio:
- Fallo al habilitar updateFields (no es crítico)

## Estados del resultado

| Estado | Condición |
|--------|-----------|
| `OK` | Sin incidencias |
| `CON_OBSERVACIONES` | Solo warnings |
| `NO_CONFORME` | Hay errores |
| `SIN_DATOS` | No se encontró DOCX |

## Uso CLI

```bash
# Solo analizar (sin escribir outputs ni crear DOCX)
python run_expediente.py <expediente> document-toc

# Analizar y escribir JSON/MD
python run_expediente.py <expediente> document-toc --write

# Analizar y crear copia con TOC aplicado
python run_expediente.py <expediente> document-toc --apply

# Todo: analizar + aplicar + escribir
python run_expediente.py <expediente> document-toc --write --apply

# No reemplazar placeholder; insertar TOC al inicio
python run_expediente.py <expediente> document-toc --apply --no-replace
```

### Exit codes

| Código | Significado |
|--------|-------------|
| 0 | Sin errores (is_valid=True) |
| 1 | Hay errores, DOCX no encontrado, o error de ejecución |

Warnings no afectan al exit code.

## API Python

```python
from eia_agent.core.document_toc_manager import (
    analyze_toc,
    build_toc_field_paragraph,
    build_toc_report_markdown,
    detect_toc_in_docx,
    enable_update_fields_on_open,
    find_toc_placeholder_paragraphs,
    insert_or_replace_toc,
    process_document_toc,
    validate_docx_file,
    write_toc_outputs,
)

# Solo detectar TOC (lectura)
detection = detect_toc_in_docx("documento/borrador.docx")
print(detection.summary())

# Analizar sin modificar
result = analyze_toc("documento/borrador.docx")
print(result.summary())

# Insertar/reemplazar TOC en copia
result = insert_or_replace_toc(
    "documento/borrador.docx",
    "documento/con_toc.docx",
    replace_placeholder=True,
)

# Habilitar updateFields en copia existente
enable_update_fields_on_open("documento/con_toc.docx", "documento/con_toc.docx")

# Función principal
result = process_document_toc(
    "expediente-EIA-2026-TEST",
    write_outputs=True,
    apply_toc=True,
    replace_placeholder=True,
)

# Informe Markdown
md = build_toc_report_markdown(result)
print(md)

# Escribir outputs
json_path, md_path = write_toc_outputs(result, "expediente/documento")
```

## Relación con otros módulos

| Módulo | Relación |
|--------|----------|
| DOC-02 (`document_docx_builder`) | Genera el DOCX base que EN-05 analiza. Contiene `add_table_of_contents_placeholder()` que usa el mismo patrón OxmlElement |
| EN-02 (`document_structure_manager`) | Normaliza la estructura del DOCX; EN-05 puede aplicarse sobre su output |
| EN-04 (`document_numbering_manager`) | Aplica estilos de numeración; EN-05 tiene prioridad 1 sobre su output (`documento_ambiental_numerado.docx`) |
| DOC-08 (`document_presentation_preparer`) | Añade hoja de firmas; EN-05 se aplica antes de la entrega final |

El orden recomendado de la cadena de enriquecimiento DOCX es:
```
DOC-02 → DOC-03 → EN-02 → EN-04 → EN-05 → DOC-08
```

## Tests

```bash
# Solo EN-05
venv\Scripts\python -m unittest tests.test_document_toc_manager

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

142 tests en 19 clases. 100% offline. Sin DOCX reales (usa DOCXs
sintéticos generados con python-docx en memoria dentro de
`tempfile.TemporaryDirectory`).
