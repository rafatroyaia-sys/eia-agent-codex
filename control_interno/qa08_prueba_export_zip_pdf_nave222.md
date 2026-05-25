# QA-08 — Prueba real de exportacion ZIP/PDF sobre NAVE-222

**Fecha:** 2026-05-25
**Modulo probado:** DOC-07 (`document_exporter.py`)
**Expediente piloto:** qa08_export_zip_pdf_nave222_20260525_192039
**Origen de la copia:** tmp/qa07_paquete_entrega_nave222_20260525_183246 (QA-07, con paquete_entrega/ ya generado)
**Resultado:** PASS — sin errores, ZIP generado correctamente

---

## 1. Entorno

| Parametro | Valor |
|-----------|-------|
| Plataforma | Windows 11 Pro 10.0.22631 |
| Python | venv\Scripts\python |
| Directorio de trabajo | C:\Users\KitDigital\proyecto-eia |
| Rama git | master |
| Ultimo commit | b44a43c (DOC-07) |
| Suite baseline | 6128 OK, 12 skipped |

---

## 2. Copia de trabajo

```
tmp/qa08_export_zip_pdf_nave222_20260525_192039/
```

Creada por copia directa desde QA-07, que ya contenia:
- `documento/paquete_entrega/` (4 secciones, 21 archivos — generado en QA-07)
- `documento/documento_ambiental_borrador_con_figuras.docx`

No se ejecuto document-package de nuevo; se reuso el paquete ya validado en QA-07.

---

## 3. Verificacion previa: paquete_entrega/

| Check | Resultado |
|-------|-----------|
| `documento/paquete_entrega/` existe | OK |
| Seccion 01_documento_ambiental | OK |
| Seccion 02_auditorias | OK |
| Seccion 03_anexos_graficos | OK |
| Seccion 04_trazabilidad | OK |
| README_ENTREGA.md | OK |

---

## 4. Dry-run: document-export (sin --write)

```
python run_expediente.py tmp\qa08_... document-export
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| ZIP | NO_GENERADO (dry-run) |
| Archivos detectados | 21 |
| PDF | SKIPPED_NO_CONVERTER |
| Errores | 0 |
| Advertencias | 0 |

**Resultado:** PASS — dry-run correcto. El 0 de salida se debe a `error_count()==0` (no a `is_success()`), comportamiento esperado.

---

## 5. Exportacion con --write

```
python run_expediente.py tmp\qa08_... document-export --write
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| ZIP | GENERADO |
| Archivos en ZIP | 21 |
| PDF | SKIPPED_NO_CONVERTER |
| Errores | 0 |
| Advertencias | 1 (EXP-W002: sin conversor PDF) |
| RESULTADO | OK |

**Archivos generados:**
- `documento/paquete_entrega.zip` (3.2 MB)
- `documento/document_export_result.json`
- `documento/document_export_result.md`

**No generado (esperado):** `documento_ambiental_borrador_con_figuras.pdf` — LibreOffice/soffice no disponible en el sistema Windows, ni pywin32 instalado.

---

## 6. Exportacion con --write --no-pdf

```
python run_expediente.py tmp\qa08_... document-export --write --no-pdf
```

| Campo | Valor |
|-------|-------|
| Exit code | 0 |
| ZIP | GENERADO |
| Archivos en ZIP | 21 |
| PDF | NOT_REQUESTED |
| Errores | 0 |
| Advertencias | 0 |

---

## 7. Verificacion del ZIP

| Check | Resultado |
|-------|-----------|
| Archivo `paquete_entrega.zip` existe | OK |
| Tamano | 3.201 MB (3.277.897 bytes) |
| Total archivos | 21 |
| Rutas absolutas (deben ser 0) | 0 |
| ZIP dentro del ZIP (recursion) | Ninguno |
| Directorios raiz | 01_documento_ambiental, 02_auditorias, 03_anexos_graficos, 04_trazabilidad, README_ENTREGA.md |

### Contenido completo del ZIP

| Ruta relativa |
|---------------|
| 01_documento_ambiental/documento_ambiental_borrador.docx |
| 01_documento_ambiental/documento_ambiental_borrador.md |
| 01_documento_ambiental/documento_ambiental_borrador_con_figuras.docx |
| 02_auditorias/art45_checklist_result.json |
| 02_auditorias/block_consistency_result.json |
| 02_auditorias/conesa_check_result.json |
| 02_auditorias/diagnostic_measure_validation_result.json |
| 02_auditorias/document_quality_result.json |
| 02_auditorias/document_quality_result.md |
| 02_auditorias/final_audit_result.json |
| 02_auditorias/final_audit_result.md |
| 02_auditorias/prl_measure_validation_result.json |
| 02_auditorias/prudence_validation_result.json |
| 02_auditorias/traceability_validation_result.json |
| 03_anexos_graficos/document_figures_result.md |
| 04_trazabilidad/document_build_result.json |
| 04_trazabilidad/document_figures_result.json |
| 04_trazabilidad/document_manifest.json |
| 04_trazabilidad/document_manifest.md |
| 04_trazabilidad/docx_build_result.json |
| README_ENTREGA.md |

---

## 8. Estado PDF

| Escenario | pdf_status | Comportamiento |
|-----------|-----------|----------------|
| `--write` (sin --no-pdf) | `SKIPPED_NO_CONVERTER` | EXP-W002 WARNING, exit 0 |
| `--write --no-pdf` | `NOT_REQUESTED` | sin warning, exit 0 |

**LibreOffice/soffice:** no disponible en PATH ni en rutas tipicas de Windows.
**Word COM (pywin32):** no disponible.
**Impacto:** ninguno. La ausencia de PDF no bloquea el ZIP ni el exit code. Comportamiento correcto segun especificacion DOC-07.

---

## 9. Verificacion de document_export_result.json

| Campo | Valor |
|-------|-------|
| `zip_generated` | `true` |
| `pdf_status` | `"NOT_REQUESTED"` (ultimo run: --no-pdf) |
| `files_zipped_count` | `21` |
| `error_count` | `0` |
| `warning_count` | `0` |
| `is_success` | `true` |
| `notes` | disclaimer correcto |

---

## 10. Seguridad del expediente piloto

| Check | Resultado |
|-------|-----------|
| `expediente-EIA-NAVE-222/` sin modificaciones | CONFIRMADO |
| git status limpio | OK (sin cambios no commitados) |
| `tmp/` no en git | OK (en .gitignore) |
| ZIP/DOCX/PDF/PNG no commiteados | OK |
| `paquete_entrega/` de la copia no modificado | OK (document-export solo lee, no escribe en paquete_entrega/) |

---

## 11. Suite completa final

| Suite | Resultado |
|-------|-----------|
| Baseline antes de QA-08 | 6128 OK, 12 skipped |
| Tras QA-08 (sin cambios de codigo) | 6128 OK, 12 skipped |

No hubo bugs. No se modifico codigo.

---

## 12. Incidencias / Bugs

**Ninguno.** El modulo DOC-07 funciono correctamente en todos los escenarios probados.

---

## 13. Conclusion

| Item | Resultado |
|------|-----------|
| ZIP generado correctamente | PASS |
| Rutas relativas sin absolutas | PASS |
| Sin recursion ZIP-en-ZIP | PASS |
| 4 secciones presentes | PASS |
| PDF best-effort: SKIPPED_NO_CONVERTER (sin conversor) | PASS (comportamiento esperado) |
| Exit 0 con PDF ausente | PASS |
| Exit 0 dry-run con paquete presente | PASS |
| document_export_result.json correcto | PASS |
| paquete_entrega/ no modificado | PASS |
| Piloto NAVE-222 intacto | PASS |
| Suite: 6128 OK | PASS |

**Veredicto: QA-08 SUPERADO. DOC-07 validado sobre expediente real.**
