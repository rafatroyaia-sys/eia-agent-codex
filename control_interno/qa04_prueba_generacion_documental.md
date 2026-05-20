# QA-04 — Prueba end-to-end de generación documental Markdown + DOCX

**Fecha:** 2026-05-20  
**Expediente de prueba:** copia de EIA-2026-RECIMETAL-NAVE-222 (via QA-03)  
**Ruta temporal:** `tmp/qa04_document_output_20260520_165211`  
**Estado:** COMPLETADO ✓

---

## 1. Expediente usado

**EIA-2026-RECIMETAL-NAVE-222** (copia, no original)

Motivo: la copia QA-03 (`tmp/qa03_pipeline_17steps_20260518_171345`) ya
tenía el pipeline técnico ejecutado con los 17 pasos OK, incluyendo todos los
outputs requeridos por DOC-00/01/02. Se creó una nueva copia QA-04 a partir
de ella para no contaminar QA-03.

El expediente original `expediente-EIA-2026-RECIMETAL-NAVE-222/` no fue
modificado en ningún momento (confirmado: sin directorio `documento/`).

---

## 2. Ruta de copia temporal

```
C:\Users\KitDigital\proyecto-eia\tmp\qa04_document_output_20260520_165211\
```

Creada copiando `tmp/qa03_pipeline_17steps_20260518_171345` completo.
La copia QA-03 ya contenía:
- `inventario/` — 16 fichas FI-001…FI-016, `inventory_summary.json`, `phase5_gate_result.json`
- `impactos/` — todos los modelos phase6 con conesa/measures/pva + coverage + cumulative
- `auditoria/` — art45, prudence, traceability, block_consistency, conesa_check, diagnostic_measure, prl_measure, final_audit
- `capas/` — hechos_confirmados.json, normativa_aplicable.json
- `fase4/` — phase4_result.json

---

## 3. Comandos ejecutados

```
# Paso 1 — Manifest DOC-00
python run_expediente.py <ruta_copia> document-manifest --write

# Paso 2 — Markdown DOC-01
python run_expediente.py <ruta_copia> document-build-md --write

# Paso 3 — DOCX DOC-02
python run_expediente.py <ruta_copia> document-build-docx --write
```

---

## 4. Resultado document-manifest (DOC-00)

```
DOC-00 [qa04_document_output_20260520_165211]
  11 READY / 0 PARTIAL / 0 MISSING de 11 bloques
```

**Nota relevante:** 11/11 bloques READY (mejor que en QA-03 donde se esperaban algunos PARTIAL).
Todos los inputs requeridos por cada bloque están presentes.

Outputs escritos:
- `documento/document_manifest.json` (7 957 bytes)
- `documento/document_manifest.md` (3 430 bytes)

---

## 5. Resultado document-build-md (DOC-01)

```
DOC-01 [qa04_document_output_20260520_165211]
  10 GENERATED / 1 PARTIAL / 0 MISSING de 11 bloques — BORRADOR COMPLETO
```

**Bloque PARTIAL:** G (Alternativas) — esperado en modo gabinete sin datos
de alternativas del promotor. No es incidencia de código.

Outputs escritos:
- `documento/documento_ambiental_borrador.md` (22 911 bytes)
- `documento/document_build_result.json` (6 852 bytes)

Bloques A-K verificados en Markdown: **11/11 SI**

---

## 6. Resultado document-build-docx (DOC-02)

```
DOC-02 [qa04_document_output_20260520_165211] OK
  70 headings, 222 parrafos, 6 tablas
```

Outputs escritos:
- `documento/documento_ambiental_borrador.docx` (1 413 706 bytes = 1,35 MB)
- `documento/docx_build_result.json` (691 bytes)

El DOCX incluye el logo `assets/brand/logo_ecogestion.png` (1,37 MB comprimido a DOCX).

---

## 7. Outputs generados

| Archivo | Tamaño | Estado |
|---------|--------|--------|
| `documento/document_manifest.json` | 7 957 bytes | ✓ OK |
| `documento/document_manifest.md` | 3 430 bytes | ✓ OK |
| `documento/documento_ambiental_borrador.md` | 22 911 bytes | ✓ OK |
| `documento/document_build_result.json` | 6 852 bytes | ✓ OK |
| `documento/documento_ambiental_borrador.docx` | 1 413 706 bytes | ✓ OK |
| `documento/docx_build_result.json` | 691 bytes | ✓ OK |

**6/6 outputs presentes y con tamaño > 0.**

---

## 8. Validación básica del DOCX

| Verificación | Resultado |
|-------------|-----------|
| DOCX existe | ✓ SI |
| DOCX > 0 bytes | ✓ SI (1,35 MB) |
| DOCX abre con python-docx | ✓ SI |
| Total párrafos | 305 |
| Total tablas | 6 |
| Total headings | 71 |
| Portada: título presente | ✓ SI |
| Portada: expediente_id presente | ✓ SI |
| Portada: disclaimer aptitud administrativa | ✓ SI |
| Índice presente | ✓ SI |
| Párrafos con AVISO/CAUTELA | 8 |
| Bloque A presente | ✓ SI |
| Bloque B presente | ✓ SI |
| Bloque C presente | ✓ SI |
| Bloque D presente | ✓ SI |
| Bloque E presente | ✓ SI |
| Bloque F presente | ✓ SI |
| Bloque G presente | ✓ SI |
| Bloque H presente | ✓ SI |
| Bloque I presente | ✓ SI |
| Bloque J presente | ✓ SI |
| Bloque K presente | ✓ SI |
| Expediente original no modificado | ✓ SI |

---

## 9. Incidencias detectadas

### I-1 — UnicodeEncodeError en consola Windows (cosmético)

- **Tipo:** error de encoding de consola, no de código
- **Descripción:** Al imprimir caracteres Unicode (✓/✗) en la consola Windows
  con encoding cp1252, Python 3.13 lanza `UnicodeEncodeError`. No afecta
  al funcionamiento del módulo ni a los archivos generados.
- **Impacto:** Ninguno en el DOCX/MD. Solo en `print()` de scripts de
  diagnóstico ad-hoc en PowerShell.
- **Resolución:** No requiere cambio de código. El módulo usa texto ASCII
  internamente. El problema está en la consola del entorno de prueba.

### I-2 — Bloque G siempre PARTIAL (esperado)

- **Tipo:** comportamiento correcto documentado
- **Descripción:** El Bloque G (Alternativas y justificación) queda siempre
  PARTIAL en modo gabinete porque no hay datos de alternativas del promotor.
- **Impacto:** Ninguno. Documentado en `docs/DOCUMENT_MARKDOWN_BUILDER.md`.
- **Resolución:** No es un bug.

---

## 10. Correcciones aplicadas

**Ninguna corrección de código fue necesaria.**

Los tres comandos (document-manifest, document-build-md, document-build-docx)
funcionaron sin errores en la primera ejecución sobre la copia QA-04.

---

## 11. Resultado de suite final

```
Ran 5752 tests in 72.675s
OK (skipped=12)
0 failures, 0 errors
```

Sin regresiones respecto al baseline de DOC-02.

---

## 12. Conclusión

**QA-04 COMPLETADO ✓**

La cadena documental completa funciona de extremo a extremo:

```
Pipeline técnico (17 pasos)
    → DOC-00 document-manifest   → 11/11 bloques READY
    → DOC-01 document-build-md   → 10 GENERATED + 1 PARTIAL (G, esperado)
    → DOC-02 document-build-docx → DOCX 1,35 MB, 305 párrafos, 71 headings, 6 tablas
```

El DOCX generado:
- Contiene portada con logo, título, expediente, fecha y disclaimer.
- Contiene los 11 bloques A-K del Documento Ambiental.
- Contiene índice (campo TOC Word).
- Preserva 8 advertencias AVISO/CAUTELA del Markdown fuente.
- No declara aptitud administrativa.
- No fue modificado el expediente piloto original.
- Suite completa: 5752 tests OK, sin regresiones.
