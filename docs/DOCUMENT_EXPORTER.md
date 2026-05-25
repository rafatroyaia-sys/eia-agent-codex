# DOCUMENT_EXPORTER — DOC-07

## Que hace este modulo

`document_exporter.py` implementa la exportacion final del paquete documental del
Documento Ambiental EIA simplificada. Dado un expediente con `documento/paquete_entrega/`
ya generado por DOC-06, este modulo produce:

1. **ZIP obligatorio** (`documento/paquete_entrega.zip`):
   - Comprime el contenido de `documento/paquete_entrega/` con rutas relativas limpias.
   - Excluye automaticamente archivos temporales, caches y residuos de sistema.
   - No incluye el propio ZIP ni el PDF (estan fuera del directorio fuente).

2. **PDF best-effort** (`documento/documento_ambiental_borrador_con_figuras.pdf`):
   - Intenta convertir el DOCX enriquecido (DOC-03) a PDF.
   - Si LibreOffice/soffice esta disponible en el sistema, lo usa primero.
   - Si Microsoft Word via COM esta disponible en Windows, lo usa como alternativa.
   - Si no hay conversor: WARNING claro, el ZIP sigue siendo valido.
   - La ausencia de PDF NO bloquea el resultado ni el exit code.

---

## Que NO hace este modulo

- No corrige documentos.
- No genera contenido nuevo (bloques, impactos, medidas, etc.).
- No modifica `paquete_entrega/` ni los archivos fuente DOCX/Markdown.
- No declara el expediente apto para presentacion administrativa.
- No llama APIs externas ni usa IA.
- No genera indices, firmas ni metadatos (eso es DOC-08).

---

## Estructura de salida

```
documento/
├── paquete_entrega/          ← fuente (generado por DOC-06, no modificado)
│   ├── 01_documento_ambiental/
│   ├── 02_auditorias/
│   ├── 03_anexos_graficos/
│   ├── 04_trazabilidad/
│   └── README_ENTREGA.md
├── paquete_entrega.zip       ← generado por DOC-07 (obligatorio)
├── documento_ambiental_borrador_con_figuras.pdf  ← best-effort (opcional)
├── document_export_result.json  ← resultado del proceso
└── document_export_result.md    ← informe en markdown
```

---

## Constantes publicas

| Constante | Valor | Descripcion |
|-----------|-------|-------------|
| `EXPORT_RESULT_JSON` | `document_export_result.json` | JSON de resultado |
| `EXPORT_RESULT_MD` | `document_export_result.md` | Markdown de resultado |
| `PACKAGE_ZIP_FILENAME` | `paquete_entrega.zip` | Nombre del ZIP |
| `PDF_OUTPUT_FILENAME` | `documento_ambiental_borrador_con_figuras.pdf` | Nombre del PDF |
| `DEFAULT_PACKAGE_DIR` | `documento/paquete_entrega` | Directorio fuente del ZIP |
| `DEFAULT_DOCX_SOURCE` | `documento/documento_ambiental_borrador_con_figuras.docx` | DOCX fuente para PDF |

---

## API principal

### `export_document_package(expediente_path, write_outputs=False, generate_pdf=True, overwrite=True)`

Funcion principal. Devuelve `DocumentExportResult`.

- `write_outputs=False` (default): dry-run. No crea ZIP ni PDF.
- `write_outputs=True`: crea ZIP, intenta PDF, escribe JSONs/MD.
- `generate_pdf=False`: solo ZIP, `pdf_status=NOT_REQUESTED`.
- `overwrite=True`: sobreescribe ZIP si ya existe.

### `write_export_result_outputs(result, output_dir)`

Escribe `document_export_result.json` y `.md` en `output_dir`.
Devuelve `(json_path, md_path)`.

### `find_soffice_executable()`

Busca LibreOffice/soffice en PATH y rutas tipicas de Windows.
Devuelve ruta (str) o None.

### `can_use_word_com()`

True si plataforma Windows y pywin32 disponible. No lanza excepcion.

### `create_zip_from_directory(source_dir, output_zip_path, exclude_patterns=None)`

Crea ZIP con rutas relativas. Excluye `__pycache__`, `.pytest_cache`,
`thumbs.db`, `desktop.ini`, archivos `~$*`.
Lanza `FileNotFoundError` si `source_dir` no existe.

### `convert_docx_to_pdf_with_soffice(docx_path, output_pdf_path, soffice_path=None, timeout_seconds=120)`

Convierte DOCX a PDF con LibreOffice. Devuelve True/False.

### `convert_docx_to_pdf_with_word_com(docx_path, output_pdf_path)`

Convierte DOCX a PDF con Word COM. Devuelve True/False.
Garantiza que Word no queda abierto si falla.

### `export_pdf_best_effort(docx_path, output_pdf_path, prefer='soffice')`

Intenta PDF con el mejor conversor disponible.
Devuelve `(pdf_status, issues)`.

---

## Clase DocumentExportResult

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente |
| `zip_path` | str\|None | Ruta del ZIP generado |
| `pdf_source_docx` | str\|None | DOCX fuente para PDF |
| `pdf_path` | str\|None | Ruta del PDF generado (si GENERATED) |
| `zip_generated` | bool | True si el ZIP se creo |
| `pdf_status` | str | Estado del PDF (ver PDF_EXPORT_STATUS) |
| `files_zipped` | list[str] | Rutas relativas incluidas en ZIP |
| `issues` | list[ExportIssue] | Incidencias del proceso |

### Metodos

- `is_success()`: True si `zip_generated=True` y `error_count()==0`. La ausencia de PDF no afecta.
- `error_count()`: numero de issues con severity=ERROR.
- `warning_count()`: numero de issues con severity=WARNING.

---

## Estados PDF

| Estado | Descripcion |
|--------|-------------|
| `GENERATED` | PDF generado correctamente |
| `SKIPPED_NO_CONVERTER` | No se encontro LibreOffice ni Word |
| `FAILED` | Conversor existe pero fallo |
| `NOT_REQUESTED` | `--no-pdf` activo o `generate_pdf=False` |
| `SOURCE_MISSING` | DOCX fuente no existe |

---

## Codigos de incidencia

| Codigo | Severidad | Descripcion |
|--------|-----------|-------------|
| `EXP-E001` | ERROR | `paquete_entrega/` no encontrado |
| `EXP-E002` | ERROR | Error al crear el ZIP |
| `EXP-W001` | WARNING | DOCX fuente no encontrado |
| `EXP-W002` | WARNING | Sin conversor PDF disponible |
| `EXP-W003` | WARNING | Conversor existe pero fallo |

---

## Dependencia opcional de LibreOffice y Word

### LibreOffice (recomendado, multiplataforma)

```bash
# Debian/Ubuntu
sudo apt install libreoffice

# Windows
# Descargar desde https://www.libreoffice.org
# El instalador lo anade al PATH o a la ruta tipica:
# C:\Program Files\LibreOffice\program\soffice.exe
```

### Microsoft Word via pywin32 (solo Windows)

```bash
pip install pywin32
```

Requiere Microsoft Word instalado en el sistema.

Si ninguno esta disponible, el modulo genera WARNING y el ZIP sigue siendo valido.

---

## CLI

### Sintaxis

```bash
python run_expediente.py <expediente> document-export [--write] [--no-pdf] [--overwrite]
```

### Opciones

| Opcion | Descripcion |
|--------|-------------|
| (sin --write) | Dry-run: muestra que exportaria, no crea nada |
| `--write` | Crea ZIP, intenta PDF, escribe JSONs/MD |
| `--no-pdf` | Solo ZIP, pdf_status=NOT_REQUESTED |
| `--overwrite` | Sobreescribe ZIP existente (por defecto activo) |

### Codigos de salida

| Codigo | Condicion |
|--------|-----------|
| 0 | Sin errores (paquete_entrega/ existe, sin EXP-E*) |
| 1 | paquete_entrega/ no existe, o error creando ZIP |

La falta de conversor PDF NO da exit 1 si el ZIP se genero correctamente.

### Ejemplos

```bash
# Dry-run: muestra que se exportaria
python run_expediente.py expediente-EIA-NAVE-222 document-export

# Crear ZIP y PDF (si LibreOffice disponible)
python run_expediente.py expediente-EIA-NAVE-222 document-export --write

# Solo ZIP, sin PDF
python run_expediente.py expediente-EIA-NAVE-222 document-export --write --no-pdf
```

---

## Flujo completo del pipeline documental

```
DOC-00: document-manifest     → estado de bloques A-K
DOC-01: document-build-md     → documento_ambiental_borrador.md
DOC-02: document-build-docx   → documento_ambiental_borrador.docx
DOC-03: document-insert-figures → documento_ambiental_borrador_con_figuras.docx
DOC-04: document-qc           → control de calidad
DOC-05: (integrado en DOC-01/DOC-04) → visibilidad estado auditoria
DOC-06: document-package      → paquete_entrega/ (4 secciones)
DOC-07: document-export       → paquete_entrega.zip + PDF  ← ESTE MODULO
```

---

## Ejecutar tests

```bash
# Solo tests DOC-07
python -m unittest tests.test_document_exporter -v

# Suite completa
python -m unittest discover -s tests
```

Los tests son completamente offline:
- No se llama a LibreOffice real (subprocess.run mockeado).
- No se usa pywin32 real (win32com mockeado via sys.modules).
- No se modifican expedientes piloto.
- Aislamiento con `tempfile.TemporaryDirectory()`.

---

## Siguiente paso sugerido

- **QA-08**: Prueba real del ZIP/PDF sobre NAVE-222 — verificar que el ZIP se genera
  correctamente sobre el expediente real y que el PDF se produce si LibreOffice esta disponible.
- **DOC-08**: Indice final, firmas, metadatos y preparacion para presentacion administrativa.
