# DOCUMENT_QUALITY_CHECKER — DOC-04

## Que hace

`document_quality_checker.py` es el validador de calidad del paquete documental
final del Documento Ambiental. Verifica que los archivos generados por DOC-00
a DOC-03 esten completos, sean coherentes y revisables antes de pasar a
revision tecnica o juridica.

No es una herramienta de correccion. Es un semaforo que detecta problemas
para que el operador pueda resolverlos.

## Que NO hace

- **No corrige el DOCX ni el Markdown.** Solo lee.
- **No modifica ningun archivo del expediente.**
- **No genera PDF.**
- **No declara el expediente apto para presentacion administrativa.**
- **No usa IA, no consulta fuentes externas, no hace llamadas a APIs.**
- **No modifica impactos, medidas, PVA ni auditorias.**
- **No sustituye la auditoria M-12.**

## Checks realizados

### 1. Existencia de archivos requeridos

| Archivo | Severidad si falta |
|---------|-------------------|
| `documento/documento_ambiental_borrador.docx` | ERROR |
| `documento/documento_ambiental_borrador.md` | ERROR |
| `documento/document_manifest.json` | WARNING |
| `documento/document_manifest.md` | INFO |
| `documento/document_build_result.json` | WARNING |
| `documento/docx_build_result.json` | WARNING |

Si `document_figures_result.json` indica `generated=True` pero el DOCX
enriquecido no existe → WARNING.

### 2. Estructura del DOCX

- El DOCX se puede abrir con python-docx → ERROR si no.
- Contiene la advertencia `No declara aptitud administrativa` → ERROR si no.
- Contiene indice o tabla de contenidos → WARNING si no.
- Contiene todos los bloques A-K → ERROR por cada bloque ausente.
- Bloque G en estado PARTIAL → WARNING (esperado en modo gabinete).

### 3. Figuras y captions

- Si `document_figures_result.json` no existe → WARNING.
- Si `figures_inserted` no vacio pero DOCX enriquecido no existe → ERROR.
- Si alguna figura insertada no tiene caption en el DOCX → ERROR.
- Si hay figuras omitidas (`figures_skipped`) → WARNING.

### 4. Auditoria final

- Si `auditoria/final_audit_result.json` no existe → WARNING.
- Si `status == NO_CONFORME` y el documento no lo menciona → ERROR.
- Si cualquier JSON del paquete tiene `administrative_ready: true` → ERROR.

### 5. Frases prohibidas

Detecta frases que impliquen aptitud administrativa:
- `apto administrativamente`
- `apto para presentacion administrativa`
- `expediente apto`
- `conforme para presentar`
- `sin condicionantes`
- `listo para presentar`
- `validado administrativamente`

Las formas negativas (`no declara aptitud administrativa`, `no apto`) estan
permitidas y no generan incidencia.

## Codigos de incidencia

| Codigo | Severidad | Significado |
|--------|-----------|-------------|
| QC-E001 | ERROR | Archivo requerido no encontrado |
| QC-E002 | ERROR | DOCX no se puede abrir |
| QC-E003 | ERROR | Bloque A-K ausente en DOCX |
| QC-E004 | ERROR | Disclaimer de no aptitud ausente |
| QC-E005 | ERROR | Caption de figura ausente o DOCX enriquecido faltante |
| QC-E006 | ERROR | Auditoria NO_CONFORME no visible en documento |
| QC-E007 | ERROR | administrative_ready=True en algun JSON |
| QC-E008 | ERROR | Frase que declara aptitud administrativa |
| QC-W001 | WARNING | Archivo recomendado no encontrado |
| QC-W002 | WARNING | Indice/TOC no encontrado |
| QC-W003 | WARNING | Sin figuras insertadas o resultado de figuras ausente |
| QC-W004 | WARNING | Figuras omitidas durante insercion |
| QC-W005 | WARNING | Auditoria final no encontrada |
| QC-W006 | WARNING | Bloque G en estado PARTIAL |
| QC-I001 | INFO | Archivo opcional no presente |

## Archivos esperados del paquete

```
expediente/
  documento/
    document_manifest.json       <- DOC-00
    document_manifest.md         <- DOC-00
    documento_ambiental_borrador.md          <- DOC-01
    document_build_result.json   <- DOC-01
    documento_ambiental_borrador.docx        <- DOC-02
    docx_build_result.json       <- DOC-02
    documento_ambiental_borrador_con_figuras.docx  <- DOC-03 (opcional)
    document_figures_result.json <- DOC-03 (opcional)
    document_figures_result.md   <- DOC-03 (opcional)
    document_quality_result.json <- DOC-04 (generado por este modulo)
    document_quality_result.md   <- DOC-04 (generado por este modulo)
  auditoria/
    final_audit_result.json      <- AU-04 (pipeline tecnico)
    final_audit_result.md        <- AU-04
```

## Bloques A-K

El validador comprueba la presencia de los 11 bloques en el DOCX:

| Bloque | Contenido |
|--------|-----------|
| A | Identificacion y descripcion del proyecto |
| B | Inventario ambiental |
| C | Identificacion y valoracion de impactos |
| D | Medidas preventivas, correctoras, protectoras, diagnosticas y documentales |
| E | Programa de vigilancia ambiental |
| F | Vulnerabilidad ante riesgos y catastrofes |
| G | Alternativas y justificacion de solucion adoptada |
| H | Red Natura 2000 y espacios naturales protegidos |
| I | Conclusiones tecnicas |
| J | Resumen no tecnico |
| K | Anexos y documentacion complementaria |

La deteccion es tolerante a distintos formatos de titulo:
- `A — Identificacion...`
- `## A`
- `Bloque A`
- `A. Identificacion...`

## Relacion con audit-final

El QC lee `auditoria/final_audit_result.json` pero NO modifica ningun resultado
de auditoria. Si la auditoria es `NO_CONFORME`, el QC verifica que el documento
lo menciona, pero no cambia el estado.

## Uso CLI

```bash
# Revision sin escritura (solo imprime resumen)
python run_expediente.py <expediente> document-qc

# Revision con escritura de outputs
python run_expediente.py <expediente> document-qc --write
```

**Codigos de salida:**
- `0` si no hay ERRORs (OK o CON_OBSERVACIONES)
- `1` si hay ERRORs o excepcion

**Outputs generados con --write:**
- `documento/document_quality_result.json`
- `documento/document_quality_result.md`

Ambos archivos son de solo lectura para el usuario. No modifican el DOCX ni
el Markdown fuente.

## Como ejecutar los tests

```bash
# Solo DOC-04
python -m unittest tests.test_document_quality_checker -v

# Suite completa
python -m unittest discover -s tests
```

Los tests son 100% offline: usan `tempfile` y `python-docx` para crear DOCXes
sinteticos. No modifican expedientes piloto ni archivos del proyecto.

## API publica

```python
from eia_agent.core.document_quality_checker import (
    run_document_quality_check,
    write_document_quality_outputs,
    build_document_quality_report_markdown,
    check_required_document_files,
    check_docx_structure,
    check_figures_and_captions,
    check_final_audit_visibility,
    check_no_administrative_ready_claim,
    detect_blocks_in_text,
    select_best_docx_for_qc,
    validate_docx_opens,
    extract_docx_text,
    safe_load_json,
    DocumentQualityResult,
    DocumentQualityIssue,
    DOCUMENT_QC_STATUS,
    DOCUMENT_QC_SEVERITY,
    REQUIRED_BLOCKS,
    REQUIRED_DOCUMENT_FILES,
)

result = run_document_quality_check("/ruta/al/expediente")
print(result.summary())
# result.is_valid() -> True si no hay ERRORs
# result.status    -> "OK" | "CON_OBSERVACIONES" | "NO_CONFORME" | "SIN_DATOS"
```
