# QA-06 — Prueba real del control de calidad documental sobre DOCX enriquecido

**Fecha:** 2026-05-21
**Hito:** DOC-04 document_quality_checker.py — validacion sobre paquete documental real
**Estado:** COMPLETADO — QC funciona correctamente; 1 incidencia real detectada (comportamiento esperado)

---

## 1. Expediente probado

**Expediente base:** EIA-2026-RECIMETAL-PARCELA (alias NAVE-222, modo test congelado)
**Fuente del paquete:** copia de QA-05 (DOC-00+DOC-01+DOC-02+DOC-03 completados)

---

## 2. Ruta de copia temporal

**Reutilizada de QA-05:** `tmp/qa05_figuras_reales_nave222_20260520_183517`

No fue necesario crear nueva copia ni regenerar ningún output del pipeline documental.
La copia contenia el paquete completo:
- manifest (DOC-00)
- Markdown (DOC-01)
- DOCX base (DOC-02)
- DOCX enriquecido con 6 figuras reales (DOC-03)
- auditoria final (pipeline tecnico AU-04)

---

## 3. Verificacion inicial

| Check | Resultado |
|-------|-----------|
| `git status --short` | LIMPIO (sin cambios pendientes) |
| Suite completa | 5960 tests OK, 12 skipped, 0 failures, 0 errors |

---

## 4. Comando ejecutado

```
python run_expediente.py tmp\qa05_figuras_reales_nave222_20260520_183517 document-qc --write
```

---

## 5. Resultado de `document-qc`

```
Control de calidad: NO_CONFORME
  Errores: 1  Advertencias: 0  Info: 0
  Archivos revisados: 11  Faltantes: 0
  Bloques A-K: 11/11  Figuras: 6  Captions: 6
  RESULTADO: NO VALIDO (hay ERRORs que deben resolverse antes de revision)
  AVISO: Este QC no declara el expediente apto para presentacion administrativa.
```

---

## 6. Status final del QC

**NO_CONFORME** — 1 error detectado (ver sección 10).

---

## 7. Archivos revisados

El QC encontró los 11 archivos del paquete y 0 faltantes:

| Archivo | Presente |
|---------|---------|
| `documento/document_manifest.json` | SI |
| `documento/document_manifest.md` | SI |
| `documento/documento_ambiental_borrador.md` | SI |
| `documento/document_build_result.json` | SI |
| `documento/documento_ambiental_borrador.docx` | SI |
| `documento/docx_build_result.json` | SI |
| `documento/documento_ambiental_borrador_con_figuras.docx` | SI |
| `documento/document_figures_result.json` | SI |
| `documento/document_figures_result.md` | SI |
| `auditoria/final_audit_result.json` | SI |
| `auditoria/final_audit_result.md` | SI |

**DOCX seleccionado para revision:** `documento_ambiental_borrador_con_figuras.docx` (correcto: prioridad al DOCX enriquecido).

---

## 8. Bloques A-K detectados

**Todos 11 bloques detectados correctamente:**

A, B, C, D, E, F, G, H, I, J, K

Bloques faltantes: ninguno.

---

## 9. Figuras y captions detectadas

**Figuras encontradas en `document_figures_result.json`:** 6

**Captions verificados en DOCX enriquecido:** 6/6

| ID | Caption en DOCX |
|----|----------------|
| FIG-001 | SI |
| FIG-002 | SI |
| FIG-003 | SI |
| FIG-004 | SI |
| FIG-005 | SI |
| FIG-006 | SI |

---

## 10. Incidencias ERROR

### QC-E006 — Auditoria NO_CONFORME no visible en documento

**Codigo:** QC-E006
**Severidad:** ERROR
**Mensaje:** La auditoria final es NO_CONFORME pero el documento no refleja esta advertencia.
**Evidencia:** `audit_status=NO_CONFORME` en `auditoria/final_audit_result.json`

**Analisis:**
- `auditoria/final_audit_result.json` tiene `status: NO_CONFORME` (modo test, esperado para NAVE-222).
- El DOCX enriquecido y el Markdown NO contienen ninguna mencion a "no conforme",
  "con observaciones" ni "observacion" en el contexto del estado de auditoria.
- Busqueda en ambos archivos: `no conforme`, `noconforme`, `con observaciones`,
  `observacion` → NOT FOUND en texto del documento.

**Conclusion sobre la incidencia:**
Esta incidencia es **COMPORTAMIENTO CORRECTO del QC**. El validador detecto un gap
real del pipeline: DOC-01 (document_markdown_builder.py) no incluye el estado
de la auditoria final (`final_audit_result.status`) en el texto del Documento Ambiental.
El QC actua correctamente al flagear esto como ERROR.

**No es un bug de DOC-04.** Es una limitacion documentada de DOC-01: el builder
genera el documento a partir de los JSON del pipeline pero no propaga el estado
de la auditoria final al cuerpo del documento.

**Futura mejora (fuera del scope de QA-06):** DOC-01 podria añadir al bloque I
(Conclusiones tecnicas) o al disclaimer una nota con el estado de la auditoria
final si `final_audit_result.json` existe.

---

## 11. Incidencias WARNING

**Ninguna advertencia detectada.**

---

## 12. Correcciones aplicadas

**Ninguna corrección de código.** La incidencia QC-E006 es comportamiento correcto
del QC, no un bug. No se modifico ningun modulo.

---

## 13. Verificacion de no modificacion de archivos fuente

| Archivo | Timestamp antes | Timestamp despues | Modificado |
|---------|-----------------|-------------------|------------|
| `documento_ambiental_borrador.md` | 2026-05-20 17:04:25 | 2026-05-20 17:04:25 | NO |
| `documento_ambiental_borrador.docx` | 2026-05-20 17:08:38 | 2026-05-20 17:08:38 | NO |
| `documento_ambiental_borrador_con_figuras.docx` | 2026-05-20 18:55:11 | 2026-05-20 18:55:11 | NO |

**El QC no modifico ningun archivo del expediente.**

---

## 14. Outputs generados

| Archivo | Tamano | Generado |
|---------|--------|---------|
| `documento/document_quality_result.json` | 2 KB | SI |
| `documento/document_quality_result.md` | 1,9 KB | SI |

---

## 15. Resultado suite final

**Comando:** `venv\Scripts\python -m unittest discover -s tests`
**Resultado:** 5960 tests OK, 12 skipped, 0 failures, 0 errors

---

## 16. Conclusion

**Estado QA-06: COMPLETADO**

DOC-04 (`document_quality_checker.py`) funciona correctamente sobre un paquete
documental real con DOCX enriquecido:

- Selecciono el DOCX enriquecido (con figuras) como DOCX de revision.
- Detecto los 11 bloques A-K correctamente.
- Verifico el disclaimer de no aptitud administrativa (presente).
- Verifico el indice (presente).
- Verifico los 6 captions FIG-001..FIG-006 en el DOCX enriquecido.
- Encontro todos los 11 archivos del paquete sin faltantes.
- Detecto un gap real del pipeline: la auditoria NO_CONFORME no esta reflejada en
  el documento (QC-E006) — comportamiento correcto del validador.
- No modifico ningun archivo fuente.

**Gap documentado:** DOC-01 no propagaba el estado de `final_audit_result.status`
al cuerpo del Documento Ambiental. Esta limitacion fue corregida en DOC-05 (2026-05-21).

**Correccion DOC-05:** `build_block_i` ahora escribe "NO CONFORME" (con espacio, detectable por
`check_final_audit_visibility`) + aviso prescrito para cada estado de auditoria. La prueba real
post-DOC-05 devuelve QC status OK (0 errores, 0 advertencias).
