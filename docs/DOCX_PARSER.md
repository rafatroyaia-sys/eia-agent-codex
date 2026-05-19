# DOCX_PARSER — IN-01

## Qué hace

`docx_parser` extrae texto plano, tablas y metadatos de archivos `.docx` del promotor. Es el primer eslabón del pipeline de ingesta documental: sin él no es posible extraer entidades (IN-02) ni clasificar evidencias (IN-03).

Modo: **solo lectura**. No escribe nada en disco. No usa IA. No interpreta el contenido jurídico.

## Qué NO hace

- No lee PDFs (eso sería IN-04, P2, requiere OCR).
- No extrae entidades jurídicas (LER, RC, coordenadas) — eso es IN-02.
- No clasifica evidencias — eso es IN-03.
- No escribe en capas JSON ni en `inputs_index.json` — eso es IN-05.
- No usa IA ni LLM para interpretar el contenido.
- No genera documentos de salida.

## API

### `parse_docx(ruta: str | Path) -> DocxContent`

Parsea un archivo `.docx` y devuelve su contenido estructurado.

```python
from eia_agent.core.docx_parser import parse_docx

content = parse_docx("inputs/memorias/Documento_Ambiental.docx")
print(content.texto[:500])
print(f"Tablas encontradas: {len(content.tablas)}")
print(f"Páginas estimadas: {content.num_paginas_estimadas}")
```

**Errores:**
- `FileNotFoundError` — el archivo no existe.
- `ValueError` — la extensión no es `.docx`, o el archivo no es un DOCX válido.

### `extract_tables_raw(ruta: str | Path) -> list[list[list[str]]]`

Extrae tablas sin interpretar cabeceras. Cada tabla es una lista de filas; cada fila es una lista de strings. Útil cuando la primera fila no tiene estructura de cabecera.

```python
from eia_agent.core.docx_parser import extract_tables_raw

tablas = extract_tables_raw("inputs/memorias/memoria.docx")
for tabla in tablas:
    for fila in tabla:
        print(fila)  # ['valor1', 'valor2', ...]
```

### `DocxContent` (dataclass)

| Campo | Tipo | Descripción |
|---|---|---|
| `texto` | `str` | Texto plano de todos los párrafos no vacíos, unido por `\n` |
| `tablas` | `list[list[dict]]` | Tablas como lista de filas; cada fila es `{cabecera: valor}` |
| `metadatos` | `dict` | `author`, `created`, `modified`, `title`, `subject` |
| `num_paginas_estimadas` | `int` | `max(1, len(texto) // 2500 + 1)` |

**Extracción de tablas:**
- La primera fila del DOCX se usa como cabecera.
- Si todos los valores de la primera fila están vacíos, se generan claves `col_0`, `col_1`...
- Las celdas vacías se representan como strings vacíos `""`.

**Metadatos:**
- Proceden de `core_properties` del DOCX.
- Los campos ausentes se incluyen como `None`.
- `created` y `modified` son objetos `datetime` con timezone UTC, o `None`.

## Cómo se usará en IN-02

IN-02 (Extractor de entidades) recibirá un `DocxContent` y buscará en `texto` y `tablas` los patrones de:
- Códigos LER (6 dígitos, formato `XX XX XX`)
- Referencias catastrales (20 caracteres alfanuméricos)
- Coordenadas WGS84/UTM28N
- Operaciones R/D (R12, R13, D15…)

El flujo previsto:

```python
content = parse_docx(ruta_docx)
entidades = extraer_entidades(content)   # IN-02 (futuro)
hechos    = clasificar_evidencias(entidades)  # IN-03 (futuro)
```

## Limitaciones conocidas

- **Tablas con celdas fusionadas:** python-docx replica el contenido de celdas fusionadas en cada celda del rango. El parser no las colapsa — IN-02 debe ser tolerante a duplicados.
- **Párrafos en cajas de texto o encabezados/pies:** python-docx no los expone en `doc.paragraphs`. El texto en headers/footers/textboxes no se extrae.
- **Imágenes:** no se extraen ni se referencian.
- **Estimación de páginas:** `len(texto) // 2500 + 1` es una aproximación basada en caracteres, no en el layout real del documento.
- **Encoding:** python-docx gestiona internamente la codificación UTF-8 del XML del DOCX. Caracteres especiales (tildes, ñ) se extraen correctamente.

## Fixture real disponible

`expediente-EIA-2026-RECIMETAL-PARCELA/inputs/memorias/Documento_Ambiental_RECIMETAL_Parcela_v6.docx`

- 56.708 caracteres de texto
- 18 tablas
- 23 páginas estimadas
- Contiene tabla de operaciones R/D y tabla LER

> NAVE-222 no tiene DOCX en `inputs/` — solo PDFs. La fixture correcta para tests es PARCELA.

## Ejecutar tests

```bash
# Solo IN-01
venv\Scripts\python -m unittest tests.test_docx_parser

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
