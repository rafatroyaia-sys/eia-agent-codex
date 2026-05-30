# DOCUMENT_NUMBERING_MANAGER — EN-04

## Qué hace

`document_numbering_manager.py` analiza y aplica estilos de numeración
en el DOCX final del Documento Ambiental. Detecta si el DOCX contiene
definiciones de numeración (`word/numbering.xml`), identifica párrafos
candidatos a lista (numerada o viñetas) y puede crear una copia del DOCX
con estilos de lista Word aplicados de forma conservadora.

Este módulo resuelve la incidencia OBS-004 del piloto Nave 222
(referencia huérfana a `numbering.xml` en `document.xml.rels`):
al generar un DOCX numerado mediante `--apply`, `word/numbering.xml`
se crea de forma controlada por python-docx, eliminando la referencia
huérfana en la copia de salida.

## Qué NO hace

- No modifica el DOCX original.
- No reordena párrafos ni secciones.
- No cambia contenido textual, tablas ni imágenes.
- No declara aptitud administrativa.
- No usa IA, no llama a APIs externas.
- No genera PDF.
- No reescribe el documento desde cero.

## Diferencia entre analizar y aplicar

| Operación | Modifica el DOCX | Crea nuevo archivo | Aplica estilos |
|-----------|-----------------|-------------------|----------------|
| `analyze_docx_numbering` | No | No | No |
| `apply_list_styles_to_docx` | No (copia) | Sí (numerado.docx) | Sí |
| `process_document_numbering(apply_styles=False)` | No | No | No |
| `process_document_numbering(apply_styles=True)` | No | Sí | Sí |

## Detección de candidatos a lista

### Lista numerada (`is_numbered_list_candidate`)

Detecta al inicio del texto (tras strip):

| Patrón | Ejemplo |
|--------|---------|
| `\d+\.\s+\S` | "1. texto" |
| `\d+\)\s+\S` | "1) texto" |
| `\d+\.-\s+\S` | "1.- texto" |
| `[a-z]\)\s+\S` | "a) texto" |
| `[A-Z]\.\s+\S` | "A. texto" |
| `[a-zA-Z]\)\s+\S` | "i) texto", "I) texto" |

**No detecta**: `1.5 kg` (decimal), `01/01/2026` (fecha con /),
`1.250 euros` (separador de miles), `28.123456N` (coordenada).
La clave es el separador seguido de espacio: `1.5` tiene dígito después
del punto, no espacio.

### Lista de viñetas (`is_bullet_list_candidate`)

Detecta al inicio del texto: `- texto`, `• texto`, `* texto`,
`– texto`, `— texto`. Requiere espacio inmediato después del carácter
de viñeta. No detecta guiones internos (`texto-con-guion`).

## Limitaciones de python-docx y numbering.xml

python-docx puede aplicar estilos de lista predefinidos (`List Number`,
`List Bullet`, etc.) que crean `word/numbering.xml` automáticamente.
Sin embargo:

1. **Estilos disponibles**: no todos los DOCXs tienen los estilos
   `List Number`/`List Bullet` en su tabla de estilos. Si el estilo
   no existe, se registra un WARNING y el párrafo no se modifica.
2. **Numeración continua**: python-docx no garantiza la continuidad
   automática de numeración entre párrafos separados por contenido.
3. **Reordenación**: reordenar secciones vía XML directo conlleva
   riesgo de corrupción de referencias. EN-04 no lo hace.

Para control profesional completo de numeración, la solución canónica
es crear el DOCX desde una plantilla Word con estilos predefinidos
(futuro EN-07).

## Orden de preferencia de DOCX

```
1. documento/documento_ambiental_final_revisable.docx
2. documento/documento_ambiental_estructurado.docx
3. documento/documento_ambiental_borrador_con_figuras.docx
4. documento/documento_ambiental_borrador.docx
```

## Estilos Word usados

| Nivel | Lista numerada | Lista viñetas |
|-------|---------------|---------------|
| 1 | `List Number` | `List Bullet` |
| 2 | `List Number 2` | `List Bullet 2` |
| 3 | `List Number 3` | `List Bullet 3` |

## Códigos de incidencia

| Código | Severidad | Condición |
|--------|-----------|-----------|
| EN04-E001 | ERROR | DOCX no puede abrirse o está corrupto |
| EN04-E002 | ERROR | Error al guardar el DOCX numerado |
| EN04-W001 | WARNING | Error al aplicar un estilo a un párrafo |
| EN04-W002 | WARNING | Estilo de lista no disponible en el DOCX |

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
python run_expediente.py <expediente> document-numbering

# Analizar y escribir JSON/MD
python run_expediente.py <expediente> document-numbering --write

# Analizar y crear copia con estilos aplicados
python run_expediente.py <expediente> document-numbering --apply

# Todo: analizar + aplicar + escribir
python run_expediente.py <expediente> document-numbering --write --apply
```

### Exit codes

| Código | Significado |
|--------|-------------|
| 0 | Sin errores (is_valid=True) |
| 1 | Hay errores, DOCX no encontrado, o error de ejecución |

Warnings no afectan al exit code.

## API Python

```python
from eia_agent.core.document_numbering_manager import (
    analyze_docx_numbering,
    apply_list_styles_to_docx,
    process_document_numbering,
    is_numbered_list_candidate,
    is_bullet_list_candidate,
    docx_has_numbering_definitions,
    validate_docx_file,
    build_numbering_report_markdown,
    write_numbering_outputs,
    select_numbered_style,
    select_bullet_style,
)

# Solo analizar
result = analyze_docx_numbering("documento/borrador.docx")
print(result.summary())

# Aplicar estilos en copia
result = apply_list_styles_to_docx(
    "documento/borrador.docx",
    "documento/numerado.docx",
    apply_numbered=True,
    apply_bullets=True,
)

# Función principal
result = process_document_numbering(
    "expediente-EIA-2026-TEST",
    write_outputs=True,
    apply_styles=True,
)

# Utilidades
print(is_numbered_list_candidate("1. texto"))  # True
print(is_bullet_list_candidate("- texto"))      # True
print(docx_has_numbering_definitions("doc.docx"))  # bool
```

## Relación con otros módulos

| Módulo | Relación |
|--------|----------|
| DOC-02 (`document_docx_builder`) | Genera el DOCX base que EN-04 analiza/copia |
| EN-02 (`document_structure_manager`) | Valida estructura del DOCX; EN-04 analiza estilos de lista |
| DOC-03 (`document_figure_inserter`) | Enriquece el DOCX antes de que EN-04 lo procese |
| DOC-08 (`document_presentation_preparer`) | Añade hoja de firmas; EN-04 puede aplicarse antes |

EN-04 es posterior a DOC-02 y anterior a la entrega final. La copia
normalizada de EN-02 (`documento_ambiental_estructurado.docx`) tiene
prioridad 2 en la selección automática de DOCX de EN-04.

## Tests

```bash
# Solo EN-04
venv\Scripts\python -m unittest tests.test_document_numbering_manager

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

127 tests en 15 clases. 100% offline. Sin DOCX reales (usa DOCXs
sintéticos generados con python-docx en memoria dentro de
`tempfile.TemporaryDirectory`).
