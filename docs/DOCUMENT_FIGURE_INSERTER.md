# DOCUMENT_FIGURE_INSERTER — DOC-03

Módulo: `src/eia_agent/core/document_figure_inserter.py`  
CLI: `python run_expediente.py <expediente> document-insert-figures [--write]`  
Tests: `tests/test_document_figure_inserter.py` (89 tests)

---

## Qué hace DOC-03

Localiza imágenes ya existentes en el expediente (mapas, climogramas, fotografías,
gráficos) y las inserta en el DOCX generado por DOC-02, produciendo un documento
enriquecido con un Anexo gráfico y cartográfico.

Cadena completa:  
DOC-00 → DOC-01 → DOC-02 → **DOC-03** → documento con figuras

---

## Qué NO hace DOC-03

- **No genera mapas.** Solo inserta los que ya existen en `cartografia/mapas/`.
- **No genera climogramas.** Solo inserta los que ya existen en `clima/`.
- **No valida cartografía oficial.** Inserta sin verificar validez institucional.
- **No declara aptitud administrativa.** Incluye disclaimer explícito.
- **No genera PDF.** Eso es DOC-04 (pendiente).
- **No modifica el DOCX base** (`documento_ambiental_borrador.docx`).
- **No modifica impactos, medidas, PVA ni auditorías.**
- **No inventa figuras.**

---

## Carpetas donde busca figuras

```
cartografia/
cartografia/mapas/
clima/
documento/figuras/
inputs/fotos/
inputs/imagenes/
assets/brand/
```

Solo incluye extensiones `.png`, `.jpg`, `.jpeg`.
Ignora archivos de tamaño 0, archivos temporales y cachés.

---

## Tipos de figura y clasificación

| Tipo | Keywords de clasificación |
|------|--------------------------|
| `MAPA` | mapa, map, cartografia, situacion, emplazamiento, parcela, red_natura, inundabilidad, usos_suelo, catastral, ortofoto, geologia, litologia, espacios, zonificacion, ubicacion |
| `CLIMOGRAMA` | climograma, climate, clima, aemet, koppen, martonne, precipitacion, temperatura, gaussen |
| `FOTOGRAFIA` | foto, fotografia, photo, imagen, image, img, vista, panoramica |
| `LOGO` | logo, brand, marca, ecogestion |
| `GRAFICO` | grafico, chart, plot, figura, diagrama, esquema |
| `OTRO` | todo lo que no encaja |

**Orden de inserción:** MAPA > CLIMOGRAMA > FOTOGRAFIA > GRAFICO > LOGO > OTRO

**Nota sobre logos:** Los logos de `assets/brand/` se excluyen del Anexo (ya
aparecen en la portada), excepto si están en `documento/figuras/` o si no hay
ninguna otra figura.

---

## Outputs generados (con `--write`)

```
documento/
├── documento_ambiental_borrador.docx          ← (DOC-02, no modificado)
├── documento_ambiental_borrador_con_figuras.docx  ← NUEVO — con Anexo
├── document_figures_result.json               ← NUEVO — metadatos
└── document_figures_result.md                 ← NUEVO — informe
```

---

## Estructura del DOCX enriquecido

El DOCX base de DOC-02 se abre y se le añade al final:

1. **Salto de página**
2. **Heading "Anexo gráfico y cartográfico"** (nivel 1)
3. Por cada figura (ordenadas por tipo):
   - Imagen insertada (ancho máximo 15 cm)
   - Caption: `Figura FIG-NNN. [Título]. Tipo: [TIPO]. Fuente: expediente técnico.`
   - Espacio entre figuras
4. Si no hay figuras: párrafo de aviso visible

---

## API pública

### `discover_document_figures(expediente_path) -> list[DocumentFigure]`
Escanea los directorios estándar del expediente. No modifica nada.

### `detect_figure_type(path) -> str`
Clasifica una imagen por su nombre y ruta.

### `build_figure_title(path, figure_type) -> str`
Genera título legible desde el nombre del archivo.

### `build_figure_caption(figure_id, title, figure_type) -> str`
Genera caption estándar: `Figura FIG-NNN. Título. Tipo: X. Fuente: expediente técnico.`

### `validate_image_file(path) -> bool`
Comprobación básica: existe, extensión soportada, tamaño > 0.

### `add_figures_annex_to_docx(input_docx_path, output_docx_path, figures, title) -> FigureInsertionResult`
Añade el anexo al DOCX. No modifica el archivo de entrada.

### `insert_figures_into_document(expediente_path, write_outputs=False) -> FigureInsertionResult`
Punto de entrada principal. Requiere `documento/documento_ambiental_borrador.docx`.

### `build_figure_result_markdown(result) -> str`
Genera informe Markdown del proceso.

### `write_figure_insertion_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe JSON + Markdown del resultado.

---

## Dataclasses

### `DocumentFigure`
```python
@dataclass
class DocumentFigure:
    figure_id: str        # FIG-001, FIG-002, ...
    figure_type: str      # MAPA, CLIMOGRAMA, ...
    title: str
    source_path: str
    relative_path: str
    caption: str
    section_hint: str
    file_size_bytes: int
    warnings: list[str]
    notes: list[str]
```

### `FigureInsertionResult`
```python
@dataclass
class FigureInsertionResult:
    expediente_id: str
    input_docx_path: str
    output_docx_path: str | None
    figures_found: list[DocumentFigure]
    figures_inserted: list[str]
    figures_skipped: list[str]
    generated: bool
    warnings: list[str]
    notes: list[str]
```

Métodos: `found_count()`, `inserted_count()`, `skipped_count()`,
`warning_count()`, `is_success()`, `to_dict()`, `summary()`.

---

## CLI

```
python run_expediente.py <expediente> document-insert-figures [--write]
```

| Opción | Descripción |
|--------|-------------|
| (sin opción) | Descubre figuras, imprime summary, no escribe |
| `--write` | Genera DOCX enriquecido + JSON + MD |

**Códigos de salida:**
- `0` → éxito (con `--write`) o descubrimiento OK (sin `--write`)
- `1` → falta `documento/documento_ambiental_borrador.docx` o error grave

---

## Flujo completo recomendado

```bash
# Cadena completa
python run_expediente.py <exp> run-technical-pipeline --write
python run_expediente.py <exp> document-manifest --write
python run_expediente.py <exp> document-build-md --write
python run_expediente.py <exp> document-build-docx --write
python run_expediente.py <exp> document-insert-figures --write
```

---

## Cómo ejecutar los tests

```
python -m unittest tests.test_document_figure_inserter
python -m unittest discover -s tests
```

Tests 100% offline: usan `tempfile`, PNG mínimo sintético (base64), sin red, sin IA.

---

## Relación con DOC-02

DOC-03 requiere el DOCX generado por DOC-02:
```
documento/documento_ambiental_borrador.docx
```
El DOCX original NO es modificado. DOC-03 genera un nuevo archivo
`documento_ambiental_borrador_con_figuras.docx`.

---

## Siguiente paso: DOC-04

DOC-04 (pendiente) añadirá control de calidad del DOCX final y/o
generación del paquete de presentación (posiblemente ZIP con todos
los outputs, o conversión a PDF si se decide).
