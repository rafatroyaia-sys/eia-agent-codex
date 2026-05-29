# DOCUMENT_PRESENTATION_PREPARER — DOC-08

## Que hace este modulo

`document_presentation_preparer.py` prepara el documento y el paquete para
revision tecnica y presentacion administrativa, anadiendo elementos formales
y metadatos controlados **sin alterar el contenido tecnico de fondo**.

Dado un expediente con el pipeline documental DOC-00→DOC-07 ejecutado, este
modulo produce:

1. **Metadatos documentales** (obligatorios si `--write`):
   - `documento/document_metadata.json`
   - `documento/document_metadata.md`

2. **Hoja de firmas** (obligatoria si `--write`):
   - `documento/hoja_firmas.md`

3. **Checklist de presentacion/revision** (obligatorio si `--write`):
   - `documento/checklist_presentacion.json`
   - `documento/checklist_presentacion.md`

4. **DOCX final revisable** (best-effort, solo si `--write` y DOCX fuente existe):
   - `documento/documento_ambiental_final_revisable.docx`

---

## Que NO hace este modulo

- **No declara aptitud administrativa.** `administrative_ready=False` siempre.
- **No presenta nada ante la Administracion.**
- **No firma digitalmente** ni genera firmas electronicas.
- **No corrige documentos.** No modifica impactos, medidas, PVA ni auditorias.
- **No genera PDF obligatorio.** El DOCX final es opcional; su falta no da exit 1.
- **No modifica ninguna fuente existente** (DOCX, Markdown, paquete_entrega/).
- **No usa IA ni llama a servicios externos.**
- **No declara el expediente listo para presentar.**

`PREPARADO_PARA_REVISION` significa preparado para revision tecnica interna,
no para presentacion administrativa.

---

## Estructura de salida

```
documento/
├── document_metadata.json        ← metadatos documentales
├── document_metadata.md          ← resumen de metadatos
├── hoja_firmas.md                ← hoja de firmas en blanco
├── checklist_presentacion.json   ← checklist de revision
├── checklist_presentacion.md     ← checklist legible
└── documento_ambiental_final_revisable.docx  ← best-effort (opcional)
```

---

## Constantes publicas

| Constante | Valor | Descripcion |
|-----------|-------|-------------|
| `METADATA_JSON` | `document_metadata.json` | JSON de metadatos |
| `METADATA_MD` | `document_metadata.md` | Markdown de metadatos |
| `SIGNATURE_SHEET_MD` | `hoja_firmas.md` | Hoja de firmas MD |
| `PRESENTATION_CHECKLIST_JSON` | `checklist_presentacion.json` | JSON del checklist |
| `PRESENTATION_CHECKLIST_MD` | `checklist_presentacion.md` | Markdown del checklist |
| `FINAL_REVIEW_DOCX` | `documento_ambiental_final_revisable.docx` | DOCX final |

---

## Estados de presentacion

| Estado | Descripcion |
|--------|-------------|
| `PREPARADO_PARA_REVISION` | Sin errores ni advertencias: listo para revision tecnica |
| `PENDIENTE_REVISION_TECNICA` | Sin errores pero con advertencias |
| `PENDIENTE_DOCUMENTACION` | Sin DOCX ni documentos fuente |
| `NO_PREPARADO` | Hay errores que deben resolverse |

---

## Metadatos documentales

El modulo lee los siguientes JSONs si existen (no falla si faltan):

| Archivo | Dato extraido |
|---------|---------------|
| `auditoria/final_audit_result.json` | `final_audit_status` |
| `documento/document_quality_result.json` | `document_qc_status` |
| `documento/package_build_result.json` | `package_status` |
| `documento/document_export_result.json` | `export_status` |
| `auditoria/conditional_chain_result.json` | `conditional_chain_status` (IM-09, DOC-09) |

`administrative_ready` es siempre `False` en los metadatos generados,
independientemente de lo que digan los JSONs de entrada.

---

## Hoja de firmas

La hoja de firmas (`hoja_firmas.md`) contiene:

1. Datos del expediente (ID, fecha de generacion)
2. Documento revisado (DOCX, Markdown, ZIP)
3. Campos en blanco: Nombre y apellidos, Titulacion, N. colegiado, Entidad, Cargo
4. Fecha de revision y lugar
5. Espacio para firma manuscrita
6. Advertencia de alcance:
   _"Esta hoja no acredita por si sola la aptitud administrativa del expediente."_

---

## Checklist de presentacion/revision (13 items)

| ID | Descripcion | ERROR si... | WARNING si... |
|----|-------------|-------------|---------------|
| CHK-001 | DOCX final/revisable existe | No existe ningun DOCX | Solo existe DOCX sin figuras |
| CHK-002 | Markdown fuente existe | — | Markdown no encontrado |
| CHK-003 | QC documental existe | — | QC no ejecutado |
| CHK-004 | QC documental sin ERROR | QC=NO_CONFORME | QC no ejecutado o estado inesperado |
| CHK-005 | Auditoria final existe | — | Auditoria no ejecutada |
| CHK-006 | Auditoria final no oculta NO_CONFORME | — | Auditoria=NO_CONFORME |
| CHK-007 | Paquete ZIP existe | — | ZIP no generado |
| CHK-008 | README_ENTREGA en paquete | — | Paquete no generado |
| CHK-009 | No consta administrative_ready=True | Algun JSON dice administrative_ready=True | — |
| CHK-010 | Hoja de firmas generable | — | Metadata insuficiente |
| CHK-011 | Figuras documentadas si existen | — | document_figures_result indica generated=False |
| CHK-012 | Sin frases de aptitud administrativa | — | Frases prohibidas en MD |
| CHK-013 | IM-09 cadenas condicionales revisado | — | conditional_chain_result.json ausente o NO_CONFORME |

---

## DOCX final revisable

`append_signature_sheet_to_docx` copia el DOCX fuente y le anade:

- Salto de pagina
- Heading "Hoja de firmas y revision tecnica"
- Campos en blanco para tecnico redactor/revisor
- Fecha y lugar
- Espacio para firma manuscrita
- Advertencia de alcance

No modifica el DOCX original. Si falla (python-docx no disponible, DOCX
invalido), emite WARNING y el resto de outputs siguen siendo validos.

---

## API principal

### `prepare_document_for_presentation(expediente_path, write_outputs=False, create_final_docx=True)`

Funcion principal. Devuelve `PresentationPreparationResult`.

- `write_outputs=False` (default): dry-run. No escribe nada.
- `write_outputs=True`: escribe los 5 archivos + DOCX final si procede.
- `create_final_docx=False`: no crea el DOCX final revisable.

### `write_presentation_outputs(result, output_dir)`

Escribe los 5 outputs (JSON+MD metadatos, hoja firmas, checklist JSON+MD).
Devuelve lista de rutas escritas.

### `build_document_metadata(expediente_path)`

Lee JSONs de resultado del pipeline y construye `DocumentMetadata`.
`administrative_ready=False` siempre.

### `build_signature_sheet_markdown(metadata)`

Genera la hoja de firmas en Markdown.

### `build_presentation_checklist(expediente_path, metadata)`

Construye los 13 items del checklist. No modifica el expediente.

### `append_signature_sheet_to_docx(input_docx_path, output_docx_path, signature_markdown)`

Crea DOCX final con hoja de firmas. No modifica el input.

### `safe_load_json(path)`

Carga JSON tolerante. Devuelve dict o None.

---

## Clase PresentationPreparationResult

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente |
| `status` | str | Estado global (ver PRESENTATION_STATUS) |
| `metadata` | DocumentMetadata | Metadatos del documento |
| `checklist_items` | list[PresentationChecklistItem] | 13 items del checklist |
| `issues` | list[PresentationIssue] | Incidencias detectadas |
| `generated_files` | list[str] | Archivos escritos (si write_outputs=True) |

### Metodos

- `is_success()`: True si `error_count()==0`. La falta de PDF/DOCX final no bloquea.
- `error_count()`: numero de issues con severity=ERROR.
- `warning_count()`: numero de issues con severity=WARNING.
- `checklist_ok_count()`: items con status=OK.
- `checklist_error_count()`: items con status=ERROR.

**Regla**: `administrative_ready=False` siempre en `to_dict()`.

---

## Clase DocumentMetadata

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente |
| `generated_at` | str | ISO 8601 UTC |
| `source_docx` | str|None | DOCX fuente detectado |
| `source_markdown` | str|None | Markdown fuente detectado |
| `package_zip` | str|None | ZIP del paquete |
| `final_audit_status` | str|None | Estado de auditoria final |
| `document_qc_status` | str|None | Estado del QC documental |
| `package_status` | str|None | Estado del paquete |
| `export_status` | str|None | Estado de la exportacion |
| `conditional_chain_status` | str|None | Estado IM-09 cadenas condicionales (DOC-09) |
| `administrative_ready` | bool | Siempre False (propiedad) |

---

## Codigos de incidencia

| Codigo | Severidad | Descripcion |
|--------|-----------|-------------|
| `PP-W001` | WARNING | Archivo fuente no encontrado (DOCX, MD) |
| `PP-W002` | WARNING | No se pudo generar el DOCX final revisable |
| `PP-E-CHK-NNN` | ERROR | Item NNN del checklist en estado ERROR |
| `PP-W-CHK-NNN` | WARNING | Item NNN del checklist en estado WARNING |

---

## CLI

### Sintaxis

```bash
python run_expediente.py <expediente> document-prepare-presentation [--write] [--no-final-docx]
```

### Opciones

| Opcion | Descripcion |
|--------|-------------|
| (sin --write) | Dry-run: muestra que generaria, no escribe nada |
| `--write` | Escribe metadatos, hoja de firmas, checklist y (si procede) DOCX final |
| `--no-final-docx` | No crear documento_ambiental_final_revisable.docx |

### Codigos de salida

| Codigo | Condicion |
|--------|-----------|
| 0 | Sin errores (`result.is_success()=True`) |
| 1 | Hay items ERROR en checklist (ej. CHK-001: falta DOCX, CHK-009: administrative_ready=True) |

La falta del DOCX final revisable NO da exit 1 si el DOCX fuente existe.

### Ejemplos

```bash
# Dry-run: muestra que se generaria
python run_expediente.py expediente-EIA-NAVE-222 document-prepare-presentation

# Generar todo (metadatos + hoja firmas + checklist + DOCX final)
python run_expediente.py expediente-EIA-NAVE-222 document-prepare-presentation --write

# Sin DOCX final revisable
python run_expediente.py expediente-EIA-NAVE-222 document-prepare-presentation --write --no-final-docx
```

---

## Flujo completo del pipeline documental

```
DOC-00: document-manifest           → estado de bloques A-K
DOC-01: document-build-md           → documento_ambiental_borrador.md
DOC-02: document-build-docx         → documento_ambiental_borrador.docx
DOC-03: document-insert-figures     → documento_ambiental_borrador_con_figuras.docx
DOC-04: document-qc                 → control de calidad
DOC-05: (integrado en DOC-01/DOC-04) → visibilidad estado auditoria
DOC-06: document-package            → paquete_entrega/ (4 secciones)
DOC-07: document-export             → paquete_entrega.zip + PDF best-effort
DOC-08: document-prepare-presentation → metadatos + hoja firmas + checklist  ← ESTE MODULO
```

---

## Ejecutar tests

```bash
# Solo tests DOC-08
python -m unittest tests.test_document_presentation_preparer -v

# Suite completa
python -m unittest discover -s tests
```

Los tests son completamente offline:
- No se llama a ninguna API externa.
- No se modifican expedientes piloto.
- Aislamiento con `tempfile.TemporaryDirectory()`.
- python-docx se usa directamente para crear DOCX sinteticos.
- Los tests que requieren python-docx se saltan si no esta instalado (`skipTest`).

---

## Siguiente paso sugerido

- **DOC-09** (COMPLETADO): IM-09 cadenas condicionales visible en documento, QC, paquete y checklist.
