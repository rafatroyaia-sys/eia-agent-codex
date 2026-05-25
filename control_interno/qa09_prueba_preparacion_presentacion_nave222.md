# QA-09 — Prueba real de preparacion para revision y firmas sobre NAVE-222

**Fecha:** 2026-05-25
**Modulo probado:** DOC-08 (`document_presentation_preparer.py`)
**Expediente probado:** qa09_presentacion_nave222_20260525_200755
**Origen de la copia:** tmp/qa08_export_zip_pdf_nave222_20260525_192039 (QA-08, con paquete_entrega.zip y todos los JSONs de resultado)
**Resultado:** PASS — sin errores, 6 archivos generados correctamente

---

## 1. Entorno

| Parametro | Valor |
|-----------|-------|
| Plataforma | Windows 11 Pro 10.0.22631 |
| Python | venv\Scripts\python |
| Directorio de trabajo | C:\Users\KitDigital\proyecto-eia |
| Rama git | master |
| Ultimo commit | 56a72ab (DOC-08) |
| Suite baseline | 6214 OK, 12 skipped |

---

## 2. Copia de trabajo

```
tmp/qa09_presentacion_nave222_20260525_200755/
```

Creada por copia directa desde QA-08, que ya contenia:
- `documento/documento_ambiental_borrador_con_figuras.docx` (1.756.453 bytes, DOCX con 6 figuras)
- `documento/documento_ambiental_borrador.md`
- `documento/document_quality_result.json` (QC status: OK)
- `auditoria/final_audit_result.json` (status: NO_CONFORME — esperado en piloto de prueba)
- `documento/package_build_result.json` (generated: true)
- `documento/document_export_result.json` (zip_generated: true)
- `documento/paquete_entrega.zip` (3.2 MB, 21 archivos)
- `documento/paquete_entrega/README_ENTREGA.md`

No se ejecuto document-package ni document-export de nuevo; se reutilizo el paquete validado en QA-08.

---

## 3. Verificacion previa: prerequisitos

| Archivo | Estado |
|---------|--------|
| `documento/documento_ambiental_borrador_con_figuras.docx` | OK |
| `documento/documento_ambiental_borrador.md` | OK |
| `documento/document_quality_result.json` | OK |
| `auditoria/final_audit_result.json` | OK |
| `documento/package_build_result.json` | OK |
| `documento/document_export_result.json` | OK |
| `documento/paquete_entrega.zip` | OK |

---

## 4. Dry-run: document-prepare-presentation (sin --write)

```
python run_expediente.py tmp\qa09_... document-prepare-presentation
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| Status | PENDIENTE_REVISION_TECNICA |
| Errores | 0 |
| Advertencias | 1 (CHK-006: auditoria NO_CONFORME) |
| Checklist OK | 11/12 |
| Checklist ERROR | 0 |
| Archivos generados | 0 (dry-run) |

**Resultado:** PASS — dry-run correcto. Ninguna escritura. Exit 0.

**WARNING CHK-006 esperado:** La auditoria de NAVE-222 tiene status NO_CONFORME porque es un piloto de prueba en modo TEST. El comportamiento del checklist es correcto: informa el estado real sin bloquearlo como ERROR.

---

## 5. Exportacion con --write

```
python run_expediente.py tmp\qa09_... document-prepare-presentation --write
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| Status | PENDIENTE_REVISION_TECNICA |
| Errores | 0 |
| Advertencias | 1 (CHK-006) |
| Archivos generados | 6 |

**Archivos generados:**
- `documento/document_metadata.json` (0.9 KB)
- `documento/document_metadata.md` (1.1 KB)
- `documento/hoja_firmas.md` (1.5 KB)
- `documento/checklist_presentacion.json` (3.3 KB)
- `documento/checklist_presentacion.md` (3.0 KB)
- `documento/documento_ambiental_final_revisable.docx` (1.715 MB)

**Resultado:** PASS — exit 0, 6 archivos generados.

---

## 6. Exportacion con --write --no-final-docx

```
python run_expediente.py tmp\qa09_... document-prepare-presentation --write --no-final-docx
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| Errores | 0 |
| Archivos generados | 5 (sin DOCX final) |

**Resultado:** PASS — el flag `--no-final-docx` funciona correctamente.

---

## 7. Validacion de metadatos (document_metadata.json)

| Campo | Valor | Correcto |
|-------|-------|----------|
| `expediente_id` | qa09_presentacion_nave222_20260525_200755 | OK |
| `generated_at` | 2026-05-25T18:12:45Z | OK |
| `source_docx` | .../documento_ambiental_final_revisable.docx | OK* |
| `source_markdown` | .../documento_ambiental_borrador.md | OK |
| `package_zip` | .../paquete_entrega.zip | OK |
| `final_audit_status` | NO_CONFORME | OK (piloto TEST) |
| `document_qc_status` | OK | OK |
| `package_status` | GENERADO | OK |
| `export_status` | GENERADO | OK |
| `administrative_ready` | false | OK |

*Nota sobre `source_docx`: tras la primera ejecucion `--write`, el DOCX final revisable se creo. La segunda ejecucion (`--no-final-docx`) redetecto el DOCX final revisable y lo priorizó como fuente. Comportamiento correcto: el modulo prioriza `documento_ambiental_final_revisable.docx` > `con_figuras.docx` > `borrador.docx`.

---

## 8. Validacion del checklist (checklist_presentacion.json)

| ID | Descripcion | Estado |
|----|-------------|--------|
| CHK-001 | DOCX final/revisable existe | OK |
| CHK-002 | Markdown fuente existe | OK |
| CHK-003 | QC documental existe | OK |
| CHK-004 | QC documental sin ERROR | OK |
| CHK-005 | Auditoria final existe | OK |
| CHK-006 | Auditoria final: estado visible y no oculto | **WARNING** |
| CHK-007 | Paquete ZIP existe | OK |
| CHK-008 | README_ENTREGA existe en paquete | OK |
| CHK-009 | No consta administrative_ready=True | OK |
| CHK-010 | Hoja de firmas generable | OK |
| CHK-011 | Figuras/captions documentadas | OK (FIG-001..FIG-006) |
| CHK-012 | Sin frases aptitud administrativa indebida | OK |

**CHK-006 WARNING esperado:** Auditoria status NO_CONFORME. El expediente NAVE-222 es un piloto de prueba; la auditoria detecta gaps reales (modo gabinete, sin prospeccion de campo). El modulo lo informa correctamente sin bloquearlo como ERROR.

**CHK-011 detalle:** 6 figuras documentadas `['FIG-001', 'FIG-002', 'FIG-003', 'FIG-004', 'FIG-005', 'FIG-006']`. Correcto.

---

## 9. Validacion de hoja de firmas (hoja_firmas.md)

| Check | Resultado |
|-------|-----------|
| Heading "Hoja de firmas y revision tecnica" | OK |
| Seccion Expediente con ID | OK |
| Seccion Tecnico redactor/revisor | OK |
| Campo "Nombre y apellidos" en blanco | OK |
| Campo "Titulacion" en blanco | OK |
| Campo "N. colegiado, si procede" en blanco | OK |
| Campo "Entidad/empresa" en blanco | OK |
| Campo "Cargo" en blanco | OK |
| Seccion "Fecha de revision" | OK |
| Seccion "Firma" con espacio reservado | OK |
| Advertencia no acredita aptitud administrativa | OK |

---

## 10. Validacion DOCX final revisable

| Check | Resultado |
|-------|-----------|
| `documento_ambiental_final_revisable.docx` existe | OK |
| Tamano > 0 | OK (1.756.800 bytes) |
| Tamano > fuente original | OK (fuente: 1.756.453 bytes, final: 1.756.800 bytes — +347 bytes) |
| Abre con python-docx | OK |
| Total parrafos | 345 (fuente: 325, +20 parrafos de hoja de firmas) |
| Contiene "Hoja de firmas" | OK |
| Contiene advertencia admin | OK |
| DOCX fuente sin modificar | OK (1.756.453 bytes intactos antes y despues) |

El DOCX final tiene 20 parrafos adicionales respecto al fuente (salto de pagina, headings, campos, espacios, advertencia).

---

## 11. Seguridad del expediente piloto

| Check | Resultado |
|-------|-----------|
| `expediente-EIA-NAVE-222/` sin modificaciones | CONFIRMADO |
| git status limpio | OK |
| `tmp/` no en git | OK (en .gitignore) |
| DOCX/ZIP/PDF no commiteados | OK |
| Fuente `con_figuras.docx` no modificado | OK (1.756.453 bytes intactos) |

---

## 12. Incidencias detectadas

**Ninguna que requiera correccion de codigo.**

**Observacion documentada (comportamiento esperado):**
- CHK-006 WARNING: auditoria NO_CONFORME en NAVE-222 modo TEST. El modulo reporta el estado real sin bloquearlo como ERROR. Comportamiento correcto segun especificacion DOC-08.
- `source_docx` apunta a `documento_ambiental_final_revisable.docx` tras la primera ejecucion: correcto, el modulo prioriza el DOCX final revisable si existe.

---

## 13. Correcciones aplicadas

**Ninguna.** No se modifico codigo.

---

## 14. Suite completa final

| Suite | Resultado |
|-------|-----------|
| Baseline antes de QA-09 | 6214 OK, 12 skipped |
| Tras QA-09 (sin cambios de codigo) | 6214 OK, 12 skipped |

---

## 15. Conclusion

| Item | Resultado |
|------|-----------|
| Dry-run exit 0 | PASS |
| --write: 6 archivos generados | PASS |
| --write --no-final-docx: 5 archivos | PASS |
| Metadatos correctos (admin_ready=false) | PASS |
| Checklist CHK-001..CHK-012 | PASS (11 OK, 1 WARNING esperado) |
| Hoja de firmas: campos y advertencia | PASS |
| DOCX final: +20 parrafos, heading, advertencia | PASS |
| DOCX fuente intacto | PASS |
| Piloto NAVE-222 original intacto | PASS |
| 0 bugs de codigo | PASS |
| Suite 6214 OK | PASS |

**Veredicto: QA-09 SUPERADO. DOC-08 validado sobre expediente real NAVE-222.**
