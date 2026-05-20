# DOCUMENT_DOCX_BUILDER — DOC-02

Módulo: `src/eia_agent/core/document_docx_builder.py`  
CLI: `python run_expediente.py <expediente> document-build-docx [--write]`  
Tests: `tests/test_document_docx_builder.py` (99 tests)

---

## Qué hace DOC-02

Convierte el borrador Markdown generado por DOC-01 en un documento DOCX
profesional con portada, índice (campo TOC Word), estilos, tablas y avisos.

Es el tercer paso del proceso de ensamblado del Documento Ambiental:
DOC-00 (manifest) → DOC-01 (Markdown) → **DOC-02 (DOCX)**

---

## Qué NO hace DOC-02

- **No genera Markdown.** Requiere `documento/documento_ambiental_borrador.md` ya generado por DOC-01.
- **No inventa datos.** Transcribe el contenido del Markdown fielmente.
- **No corrige outputs técnicos.** Si el Markdown tiene gaps o avisos, los conserva en el DOCX.
- **No declara aptitud administrativa.** La portada incluye el disclaimer obligatorio.
- **No genera PDF.** Eso es DOC-03 (pendiente).
- **No modifica el Markdown fuente.** El archivo .md no se toca.
- **No modifica impactos, medidas, PVA ni auditorías.**

---

## Estructura del DOCX generado

### 1. Portada
- Logo `assets/brand/logo_ecogestion.png` (opcional — no falla si no existe)
- Título del documento
- Subtítulo
- ID del expediente
- Fecha de generación
- Disclaimer: _"Documento generado automáticamente a partir de outputs técnicos. Requiere revisión técnica/jurídica. **No declara aptitud administrativa.**"_
- Salto de página

### 2. Índice
- Encabezado "Índice"
- Campo Word TOC (`\o "1-3" \h \z \u`) para actualización con Ctrl+A + F9
- Nota de instrucciones de actualización
- Salto de página

### 3. Contenido (bloques A-K)
Bloques convertidos desde el Markdown:

| Elemento Markdown | Conversión DOCX |
|-------------------|-----------------|
| `# Heading` | Heading 1 (Calibri 16pt, azul oscuro) |
| `## Heading` | Heading 2 (Calibri 14pt, azul medio) |
| `### Heading` | Heading 3 (Calibri 12pt, bold) |
| `#### Heading` | Heading 4 (Calibri 11pt, bold) |
| Párrafo normal | Normal (Calibri 11pt) |
| `- item` / `* item` | List Bullet |
| `1. item` | List Number |
| `> texto` | Párrafo con indentación izquierda + itálica |
| `\| tabla \|` | Tabla Word con estilo Table Grid |
| ` ``` código ``` ` | Courier New 9pt |
| `---` | Separador horizontal con borde inferior |

---

## Elementos Markdown soportados

```
heading, paragraph, bullet_list, numbered_list, table,
blockquote, horizontal_rule, code_block, blank_line
```

---

## Dependencia con DOC-01

DOC-02 requiere que exista:
```
<expediente>/documento/documento_ambiental_borrador.md
```

Si este archivo no existe, el comando falla con `FileNotFoundError` y exit 1.
No ejecuta DOC-01 automáticamente.

---

## Outputs generados (con `--write`)

```
documento/
├── documento_ambiental_borrador.md    ← (ya existía, no se modifica)
├── document_build_result.json         ← (ya existía, no se modifica)
├── documento_ambiental_borrador.docx  ← NUEVO — borrador DOCX
└── docx_build_result.json             ← NUEVO — metadatos del build
```

---

## CLI

```
python run_expediente.py <expediente> document-build-docx [--write]
```

| Opción | Descripción |
|--------|-------------|
| (sin opción) | Parsea el Markdown, imprime summary, no escribe |
| `--write` | Genera el DOCX y el JSON de resultado |

**Códigos de salida:**
- `0` → generación exitosa (con `--write`) o parseo OK (sin `--write`)
- `1` → falta el Markdown, o error durante la generación

---

## API pública

### `safe_read_markdown(path) -> str`
Lee un Markdown. Lanza `FileNotFoundError` si no existe, `ValueError` si está vacío.

### `parse_markdown_blocks(markdown) -> list[dict]`
Parsea Markdown línea a línea. Nunca lanza excepción. Devuelve lista de bloques tipados.

### `create_docx_document(title, subtitle) -> Document`
Crea un Document() con márgenes y estilos configurados.

### `add_cover_page(doc, expediente_id, title, subtitle, generated_note, logo_path=None)`
Añade portada. No falla si el logo no existe.

### `add_table_of_contents_placeholder(doc)`
Añade encabezado "Índice" + campo TOC Word + nota de actualización + salto de página.

### `add_markdown_block_to_docx(doc, block) -> dict`
Añade un bloque al DOCX. Devuelve conteos `{paragraph_added, heading_added, table_added, image_added}`.

### `build_docx_from_markdown(markdown_path, output_docx_path, expediente_id, title, subtitle, logo_path) -> DocumentDocxBuildResult`
Pipeline completo desde un archivo Markdown a DOCX.

### `build_docx_from_expediente(expediente_path, write_outputs=False) -> DocumentDocxBuildResult`
Punto de entrada principal. Sin `write_outputs`: parsea sin escribir. Con `write_outputs`: genera DOCX y JSON.

### `validate_docx_basic(path) -> bool`
Comprueba: existe, extensión `.docx`, tamaño > 0, abre sin error con python-docx.

### `write_docx_build_result(result, output_path) -> Path`
Escribe JSON UTF-8 indentado del resultado.

---

## Dataclasses

### `DocxBuildWarning`
```python
@dataclass
class DocxBuildWarning:
    code: str
    message: str
    source_line: int | None
    recommendation: str
```

### `DocumentDocxBuildResult`
```python
@dataclass
class DocumentDocxBuildResult:
    expediente_id: str
    input_markdown_path: str
    output_docx_path: str | None
    generated: bool
    paragraph_count: int
    heading_count: int
    table_count: int
    image_count: int
    warnings: list[DocxBuildWarning]
    notes: list[str]
```

Métodos: `warning_count()`, `is_success()`, `to_dict()`, `summary()`.

---

## Limitación del índice automático en Word

El índice se inserta como un campo Word `TOC \o "1-3" \h \z \u`. Este campo:
- Requiere **actualización manual** en Word: abrir el archivo y presionar **Ctrl+A → F9**.
- No se actualiza automáticamente al abrir el documento.
- En LibreOffice/OnlyOffice puede comportarse de forma diferente.

El módulo añade una nota visible en el documento con estas instrucciones.

---

## Cómo ejecutar los tests

```
python -m unittest tests.test_document_docx_builder
python -m unittest discover -s tests
```

Tests 100% offline: usan `tempfile`, sin red, sin IA, sin APIs.

---

## Flujo completo recomendado

```bash
# 1. Pipeline técnico completo
python run_expediente.py <expediente> run-technical-pipeline --write

# 2. Manifest DOC-00
python run_expediente.py <expediente> document-manifest --write

# 3. Borrador Markdown DOC-01
python run_expediente.py <expediente> document-build-md --write

# 4. DOCX DOC-02
python run_expediente.py <expediente> document-build-docx --write

# 5. Abrir en Word y actualizar índice: Ctrl+A → F9
```

---

## Siguiente paso: DOC-03

DOC-03 (pendiente) añadirá conversión a PDF desde el DOCX y/o pipeline de ensamblado final con revisión de calidad.
