# CLIMOGRAM_DOCX_INSERTER — CL-05

Módulo `src/eia_agent/core/climogram_docx_inserter.py`  
Inserta un climograma PNG ya existente en un archivo DOCX, con encabezado y pie de figura opcionales.

---

## Qué hace

- Abre un DOCX de entrada con python-docx.
- Inserta opcionalmente un salto de página antes.
- Inserta opcionalmente un heading de nivel 2.
- Inserta la imagen PNG centrada (o alineada a la izquierda).
- Inserta opcionalmente un pie de figura.
- Inserta opcionalmente un salto de página después.
- Guarda el resultado en `output_docx`.
- Crea los directorios intermedios si no existen.
- Devuelve `ClimogramDocxInsertResult` con metadatos de la operación.

## Qué NO hace

- **No genera climogramas** — eso es CL-04 (`climogram_generator.py`).
- **No llama a AEMET** ni a ningún servicio externo.
- **No calcula clasificaciones climáticas** — eso es CL-03 (`climate_indices.py`).
- **No selecciona estaciones** — eso es CL-02 (`climate_station_selector.py`).
- **No ensambla el Documento Ambiental completo** — eso es M-11 (`ensamblar_docx.py`).
- **No modifica el DOCX original** si `output_docx` es distinto de `input_docx`.
- **No usa LibreOffice** ni conversión SVG→PNG.
- **No usa IA**.

---

## Relación con otros módulos

| Módulo | Rol | Depende de |
|--------|-----|------------|
| CL-04 `climogram_generator.py` | Genera el PNG del climograma | — |
| **CL-05** `climogram_docx_inserter.py` | Inserta el PNG en el DOCX | CL-04 (PNG ya generado) |
| M-11 `ensamblar_docx.py` | Ensambla el DA completo con todos los bloques | CL-05 (si el climograma forma parte del DA) |

El flujo en la Fase 4 es:
```
AEMETClient (CL-01)
  → find_nearest_station (CL-02)
  → parse_monthly_climate_from_aemet_normals (CL-03)
  → generate_climogram → clima/climograma.png  (CL-04)
  → insert_climogram_in_docx → docx con climograma  (CL-05)
  → ensamblar_docx.py → DA_final.docx  (M-11)
```

---

## Cómo insertar un climograma

```python
from eia_agent.core.climogram_docx_inserter import (
    insert_climogram_in_docx,
    default_climogram_caption,
    ClimogramDocxInsertConfig,
)

# Generar caption automático
caption = default_climogram_caption(
    station_name="Lanzarote Aeropuerto",
    period="1991-2020",
)
# → "Figura. Climograma de la estación Lanzarote Aeropuerto, periodo 1991-2020."

# Configurar inserción
cfg = ClimogramDocxInsertConfig(
    heading="Climograma",
    caption=caption,
    image_width_inches=5.8,
    insert_page_break_before=False,
)

# Insertar
result = insert_climogram_in_docx(
    input_docx="bloques/bloque_b.docx",
    png_path="clima/climograma.png",
    output_docx="bloques/bloque_b_con_climo.docx",
    config=cfg,
)
print(result.summary())
```

---

## API

### ClimogramDocxInsertConfig

| Campo | Tipo | Por defecto | Descripción |
|-------|------|-------------|-------------|
| `heading` | `str \| None` | `"Climograma"` | Heading nivel 2 antes de la imagen. `None` para omitirlo |
| `caption` | `str \| None` | `None` | Pie de figura. `None` para omitirlo |
| `image_width_inches` | `float` | `5.8` | Ancho de la imagen en el DOCX |
| `insert_page_break_before` | `bool` | `False` | Salto de página antes de la imagen |
| `insert_page_break_after` | `bool` | `False` | Salto de página después de la imagen |
| `caption_style` | `str \| None` | `None` | Estilo Word para el caption. Si no existe en el DOCX, usa Normal + registra aviso |
| `center_image` | `bool` | `True` | Centrar imagen y caption. `False` alinea a la izquierda |

Métodos: `to_dict()`, `ClimogramDocxInsertConfig.from_dict(data)`

### ClimogramDocxInsertResult

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `input_docx` | `str` | Ruta del DOCX de entrada |
| `output_docx` | `str` | Ruta del DOCX de salida |
| `png_path` | `str` | Ruta del PNG insertado |
| `inserted` | `bool` | `True` si la inserción fue exitosa |
| `caption` | `str \| None` | Caption efectivo usado (puede ser `None`) |
| `warnings` | `list[str]` | Avisos no bloqueantes (p.ej. estilo de caption no encontrado) |
| `notes` | `list[str]` | Notas informativas |

Métodos: `to_dict()`, `summary()`

### insert_climogram_in_docx

```python
insert_climogram_in_docx(
    input_docx: str | Path,
    png_path: str | Path,
    output_docx: str | Path,
    config: ClimogramDocxInsertConfig | None = None,
) -> ClimogramDocxInsertResult
```

**Raises**:
- `FileNotFoundError` — si `input_docx` o `png_path` no existen
- `ValueError` — si `png_path` no tiene firma PNG válida (`\x89PNG\r\n\x1a\n`)
- `ValueError` — si `output_docx` no termina en `.docx`

### default_climogram_caption

```python
default_climogram_caption(
    station_name: str | None = None,
    period: str | None = None,
) -> str
```

| Llamada | Resultado |
|---------|-----------|
| `default_climogram_caption()` | `"Figura. Climograma de la estación climática de referencia."` |
| `default_climogram_caption("Las Palmas Aeropuerto")` | `"Figura. Climograma de la estación Las Palmas Aeropuerto."` |
| `default_climogram_caption("C029O Lanzarote", "1991-2020")` | `"Figura. Climograma de la estación C029O Lanzarote, periodo 1991-2020."` |

### validate_docx_contains_image

```python
validate_docx_contains_image(docx_path: str | Path) -> bool
```

Devuelve `True` si el DOCX existe, es un ZIP válido y contiene al menos un archivo en `word/media/`. Nunca lanza excepciones.

### count_docx_images

```python
count_docx_images(docx_path: str | Path) -> int
```

Cuenta el número de archivos en `word/media/` del DOCX. Devuelve 0 si el archivo no existe o no es un ZIP válido.

**Nota sobre deduplicación**: python-docx deduplica imágenes de contenido idéntico (mismo hash). Si se insertan dos PNGs byte a byte iguales, `count_docx_images` puede devolver 1 aunque visualmente aparezcan dos imágenes en el documento.

---

## Limitaciones conocidas

1. **Solo PNG** — el módulo valida la firma PNG (8 bytes). No acepta JPEG, SVG ni otros formatos.
2. **Deduplicación de imágenes idénticas** — python-docx almacena una sola copia si dos imágenes tienen el mismo contenido binario. La imagen aparece dos veces en el documento, pero `count_docx_images` devuelve 1.
3. **Estilo de heading** — se usa nivel 2 (`Heading 2`). Si el DOCX no tiene ese estilo, python-docx lo crea automáticamente.
4. **Estilos personalizados de caption** — si `caption_style` no existe en el DOCX, se usa el estilo Normal y se registra un aviso en `result.warnings`.
5. **Sin validación visual** — este módulo no verifica el aspecto final del DOCX. La verificación visual corresponde al ensamblador M-11 o a la auditoría M-12.
6. **Posición de inserción** — la imagen siempre se añade al final del DOCX. Para insertar en una posición específica del cuerpo (p.ej. dentro de un bloque existente), usar la API de paragraphs de python-docx directamente.

---

## Verificación de la inserción

```python
from eia_agent.core.climogram_docx_inserter import validate_docx_contains_image, count_docx_images

# ¿El DOCX tiene al menos una imagen?
ok = validate_docx_contains_image("output.docx")

# ¿Cuántas imágenes tiene?
n = count_docx_images("output.docx")
```

La verificación visual final del DOCX completo (correcta posición, pie de figura correcto, estilos conformes) corresponde al ensamblador (`ensamblar_docx.py` / M-11) o a la auditoría posterior (M-12).

---

## Tests

`tests/test_climogram_docx_inserter.py` — 56 tests en 7 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestClimogramDocxInsertConfig` | 11 | Defaults, `to_dict`, `from_dict` roundtrip, `heading=None` |
| `TestDefaultCaption` | 5 | Sin estación, con estación, con estación+periodo, `None` station |
| `TestBasicInsertion` | 12 | Output creado, validate/count, Result fields, nested dirs |
| `TestHeadingAndCaption` | 6 | Heading y caption en párrafos del DOCX, `heading=None` ausente |
| `TestErrors` | 10 | FileNotFoundError, ValueError PNG inválido/vacío, extensión incorrecta, original sin cambios |
| `TestConfiguration` | 10 | center, heading=None, caption=None, page breaks, width, estilo inválido, overwrite |
| `TestCL04Integration` | 3 | Climograma real CL-04, caption auto, dos climogramas distintos |

Tiempo típico: ~7 s (sin renders redundantes; PNGs sintéticos para 53 de los 56 tests).
