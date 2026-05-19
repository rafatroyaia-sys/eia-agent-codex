# INPUT_INDEXER — IN-05

## Qué hace

`input_indexer` escanea la carpeta `inputs/` de un expediente, cataloga cada documento disponible y genera un `InputsIndex` en memoria. Opcionalmente puede parsear DOCX con la cadena IN-01 + IN-02 + IN-03 para obtener un resumen de extracción por documento.

Modo: **solo lectura** salvo llamada explícita a `write_inputs_index()`. No modifica ningún archivo del expediente. No escribe automáticamente.

## Qué es `inputs_index.json`

Es el catálogo de todos los documentos de entrada de un expediente: qué existe, de qué tipo es, si ya ha sido procesado y cuántas entidades/hechos candidatos se detectaron.

Estructura:
```json
{
  "expediente_id": "expediente-EIA-2026-RECIMETAL-PARCELA",
  "base_path": "/ruta/al/expediente",
  "documents": [
    {
      "doc_id": "DOC-001",
      "filename": "Documento_Ambiental_RECIMETAL_Parcela_v6.docx",
      "relative_path": "inputs/memorias/Documento_Ambiental_RECIMETAL_Parcela_v6.docx",
      "extension": ".docx",
      "size_bytes": 123456,
      "sha256": "abc123...",
      "detected_type": "memoria",
      "status": "PROCESADO",
      "parser": "docx_parser",
      "notes": [],
      "extracted_summary": {
        "text_chars": 56708,
        "tables_count": 18,
        "entities_count": 42,
        "candidate_facts_count": 35,
        "entity_types": ["LER", "OPERACION", "PROMOTOR", "REFERENCIA_CATASTRAL"]
      }
    }
  ],
  "warnings": []
}
```

## Diferencia entre registrar y procesar

| Estado | Significado |
|--------|-------------|
| `PROCESADO` | DOCX parseado con IN-01/IN-02/IN-03. `extracted_summary` relleno. |
| `ERROR` | DOCX inválido o ilegible. `notes` contiene el error. |
| `PENDIENTE_PARSER_PDF` | PDF catalogado, pero sin parser activo hasta IN-04. |
| `REGISTRADO_SIN_PARSER` | Imagen u otro formato sin soporte de extracción. |

**Registrar** significa que el documento aparece en el índice con sus metadatos básicos (nombre, tamaño, hash, tipo detectado). **Procesar** significa que la cadena IN-01+IN-02+IN-03 se ejecutó sobre él y se extrajeron entidades y hechos candidatos.

## Por qué PDF queda pendiente hasta IN-04

Los PDFs requieren extracción de texto estructurado o incluso OCR para documentos escaneados. Este trabajo está en P2 (ítem IN-04). Hasta que IN-04 exista:
- Los PDFs se **registran** con `status="PENDIENTE_PARSER_PDF"` y `parser="pdf_parser_pendiente"`.
- No se intenta ninguna extracción de texto.
- El índice los incluye en el catálogo para que IN-05 sea consciente de su existencia.

## Relación con IN-01, IN-02 e IN-03

```
inputs/                  ← carpeta escaneada por IN-05
  *.docx → parse_docx()  ← IN-01
         → extract_entities_from_docx()  ← IN-02
         → classify_entities_from_docx() ← IN-03
         → extracted_summary
  *.pdf  → solo registro (hasta IN-04)
  imágenes → solo registro
```

El `extracted_summary` es un resumen ligero derivado de la cadena IN-01/IN-02/IN-03. No sustituye la capa `hechos_confirmados.json` del expediente: IN-05 produce el índice de entradas, no la capa de hechos.

## API

### `build_inputs_index(expediente_path, inputs_dir, parse_docx) -> InputsIndex`

```python
from eia_agent.core.input_indexer import build_inputs_index

index = build_inputs_index(
    "expediente-EIA-2026-RECIMETAL-PARCELA",
    inputs_dir="inputs",
    parse_docx=True,
)
print(index.summary())
```

- Si `inputs/` no existe → índice vacío con warning.
- Ignora `~$*.docx`, `.DS_Store`, `Thumbs.db`.
- Asigna `DOC-001`, `DOC-002`... en orden alfabético de ruta.
- **No escribe nada**.

### `write_inputs_index(index, output_path) -> Path`

```python
from eia_agent.core.input_indexer import write_inputs_index

write_inputs_index(index, "expediente/.../inputs/inputs_index.json")
```

Escribe JSON UTF-8 indentado. Crea directorio si no existe.

### `load_inputs_index(path) -> InputsIndex`

```python
from eia_agent.core.input_indexer import load_inputs_index

index = load_inputs_index("expediente/.../inputs/inputs_index.json")
```

Reconstruye `InputsIndex` y `InputDocument` desde JSON. Lanza `FileNotFoundError` o `ValueError` si el archivo no existe o está malformado.

### `InputsIndex` — métodos

| Método | Descripción |
|--------|-------------|
| `document_count()` | Número de documentos en el índice |
| `by_type(detected_type)` | Documentos del tipo indicado |
| `by_extension(extension)` | Documentos con la extensión indicada (con o sin punto) |
| `summary()` | String con total, tipos, estados y avisos |
| `to_dict()` | Serializable a JSON |

### Funciones auxiliares

| Función | Descripción |
|---------|-------------|
| `detect_document_type(path)` | Tipo documental por nombre/ruta heurística |
| `detect_parser(extension)` | Parser asignado a la extensión |
| `sha256_file(path)` | Hash SHA-256 hex del archivo |

## Tipos documentales detectados

| Tipo | Palabras clave (en nombre/ruta) |
|------|---------------------------------|
| `proyecto_tecnico` | memoria técnica, proyecto técnico |
| `memoria` | documento ambiental, memoria, estudio |
| `cartografia` | shp, geotiff, kml, geojson |
| `plano` | plano, mapa, cartografia |
| `certificado` | certificado, autorización, licencia |
| `catastro` | catastro, catastral |
| `normativa` | normativa, ley, decreto, boe, boc |
| `fotografia` | foto, imagen, photo |
| `desconocido` | sin coincidencia |

Orden de aplicación: de más específico a más general. El primero que coincide gana.

## Cómo se usará en Fase 1 real

```python
# Fase 1: AG-1 + AG-2 + AG-3
index = build_inputs_index(expediente_path, parse_docx=True)
write_inputs_index(index, expediente_path / "inputs" / "inputs_index.json")

# El orquestador puede consultar cobertura de gates
docx_procesados = index.by_type("memoria")
for doc in docx_procesados:
    if doc.status == "PROCESADO":
        # extracted_summary ya tiene entities_count, candidate_facts_count
        pass
```

El índice permite al orquestador (NL-03) saber qué documentos existen y cuáles han sido procesados antes de evaluar el gate de Fase 1.

## Limitaciones conocidas

- **PDF sin parseo**: hasta IN-04, los PDFs solo se catalogan.
- **Imágenes**: sin extracción de texto. Se registran como `REGISTRADO_SIN_PARSER`.
- **Ordenación**: los `DOC-00N` se asignan por orden alfabético de ruta, no por relevancia documental.
- **Tipo detectado**: heurístico. Falsos positivos posibles en nombres ambiguos.
- **SHA-256**: calcula el hash completo del archivo. En archivos muy grandes puede ser lento.
- **Documentos en subcarpetas**: se rastrean recursivamente sin límite de profundidad.

## Ejecutar tests

```bash
# Solo IN-05
venv\Scripts\python -m unittest tests.test_input_indexer

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
