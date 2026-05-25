# QA-07 — Prueba real del paquete de entrega sobre NAVE-222

**Fecha de ejecución**: 2026-05-25  
**Expediente de origen**: `tmp/qa05_figuras_reales_nave222_20260520_183517/`  
**Copia de trabajo QA-07**: `tmp/qa07_paquete_entrega_nave222_20260525_183246/`  
**Módulo bajo prueba**: `src/eia_agent/core/document_package_builder.py` (DOC-06)  
**Hito asociado en backlog**: QA-07  

---

## Objetivo

Verificar que el módulo `document_package_builder.py` (DOC-06) produce un paquete de entrega
correcto sobre un expediente real — el piloto NAVE-222 — con todos los outputs del pipeline
DOC-00 a DOC-05 presentes.

---

## Restricciones de seguridad aplicadas

- Expediente piloto original NAVE-222 (`expediente-EIA-2026-RECIMETAL-NAVE-222/`) no modificado.
- Trabajo sobre copia temporal `tmp/qa07_paquete_entrega_nave222_20260525_183246/` copiada de QA-05.
- Outputs conservados hasta completar este informe.
- Sin cambios de código (no se detectaron bugs).
- No incluidos en Git: DOCX, PNG, JPG, PDF, ZIP, outputs pesados, ni directorio `tmp/`.
- Solo se commitean archivos de control interno/documentacion.

---

## Fuente de la copia

Se usa `tmp/qa05_figuras_reales_nave222_20260520_183517/` como base (QA-06 no generó directorio
propio — reutilizó QA-05). Esta copia contiene todos los outputs acumulados hasta DOC-05:

| Output | Presente | Tamaño |
|--------|----------|--------|
| `documento/documento_ambiental_borrador.docx` | SI | 1.35 MB |
| `documento/documento_ambiental_borrador.md` | SI | 23,039 B |
| `documento/documento_ambiental_borrador_con_figuras.docx` | SI | 1.68 MB |
| `documento/document_quality_result.json` | SI | 1,520 B |
| `documento/document_quality_result.md` | SI | presente |
| `documento/document_manifest.json` | SI | 7,957 B |
| `documento/document_figures_result.json` | SI | 4,386 B |
| `documento/document_build_result.json` | SI | 6,877 B |
| `documento/docx_build_result.json` | SI | 712 B |
| `auditoria/final_audit_result.json` | SI | 403,931 B |
| `auditoria/final_audit_result.md` | SI | presente |
| `auditoria/art45_checklist_result.json` | SI | presente |
| `auditoria/block_consistency_result.json` | SI | presente |
| `auditoria/conesa_check_result.json` | SI | presente |
| `auditoria/diagnostic_measure_validation_result.json` | SI | presente |
| `auditoria/prl_measure_validation_result.json` | SI | presente |
| `auditoria/prudence_validation_result.json` | SI | presente |
| `auditoria/traceability_validation_result.json` | SI | presente |
| `mapas/MAP-001..MAP-006.png` | SI (6 PNGs) | presente |

---

## Paso 1 — Verificacion de QC (document-qc --write)

**Comando ejecutado**:
```
venv\Scripts\python run_expediente.py tmp\qa07_paquete_entrega_nave222_20260525_183246 document-qc --write
```

**Resultado**:
```
Control de calidad: OK
  Errores: 0  Advertencias: 0  Info: 0
  Archivos revisados: 11  Faltantes: 0
  Bloques A-K: 11/11  Figuras: 6  Captions: 6
  RESULTADO: VALIDO (sin ERRORs)
  AVISO: Este QC no declara el expediente apto para presentacion administrativa.
```

**Estado**: CORRECTO — 0 errores, 0 advertencias. Fix DOC-05 aplicado correctamente.

---

## Paso 2 — Dry-run del paquete (document-package sin --write)

**Comando ejecutado**:
```
venv\Scripts\python run_expediente.py tmp\qa07_paquete_entrega_nave222_20260525_183246 document-package
```

**Resultado**:
```
Empaquetado: NO_GENERADO (dry-run)
  Expediente : qa07_paquete_entrega_nave222_20260525_183246
  Archivos copiados : 0
  Requeridos faltantes: 0
  Opcionales faltantes: 0
  RESULTADO: SIN ARCHIVOS ESCRITOS
  AVISO: Este paquete no declara aptitud para presentacion administrativa.
```

**Exit code**: 0 (requeridos faltantes = 0)

**Estado**: CORRECTO — dry-run no escribe archivos, exit 0 confirmado.

---

## Paso 3 — Generacion real del paquete (document-package --write)

**Comando ejecutado**:
```
venv\Scripts\python run_expediente.py tmp\qa07_paquete_entrega_nave222_20260525_183246 document-package --write
```

**Resultado**:
```
Empaquetado: GENERADO
  Expediente : qa07_paquete_entrega_nave222_20260525_183246
  Archivos copiados : 20
  Requeridos faltantes: 0
  Opcionales faltantes: 0
  Directorio : .../documento/paquete_entrega
  RESULTADO: OK
  AVISO: Este paquete no declara aptitud para presentacion administrativa.
Outputs escritos:
  .../documento/paquete_entrega
  .../documento/package_build_result.json
  .../documento/package_build_result.md
```

**Exit code**: 0

**Estado**: CORRECTO — 20 archivos copiados, 0 faltantes (requeridos u opcionales).

---

## Paso 4 — Verificacion de la estructura del paquete

### Secciones generadas

| Seccion | Archivos |
|---------|----------|
| `01_documento_ambiental/` | `documento_ambiental_borrador_con_figuras.docx` (1.68 MB), `documento_ambiental_borrador.docx` (1.35 MB), `documento_ambiental_borrador.md` |
| `02_auditorias/` | `final_audit_result.json/md`, `document_quality_result.json/md`, `art45_checklist_result.json`, `prudence_validation_result.json`, `traceability_validation_result.json`, `block_consistency_result.json`, `conesa_check_result.json`, `diagnostic_measure_validation_result.json`, `prl_measure_validation_result.json` (11 archivos) |
| `03_anexos_graficos/` | `document_figures_result.md` |
| `04_trazabilidad/` | `document_manifest.json/md`, `document_build_result.json`, `docx_build_result.json`, `document_figures_result.json` (5 archivos) |
| `README_ENTREGA.md` | Generado en raiz del paquete |

**Total**: 20 archivos copiados + 1 README generado = 21 archivos en paquete.

### Asignacion de seccion correcta

- `document_figures_result.md` → `03_anexos_graficos/` (CORRECTO — bug de ordenacion _FILE_TO_SECTION corregido en DOC-06)
- `document_figures_result.json` → `04_trazabilidad/` (CORRECTO)

---

## Paso 5 — Verificacion del package_build_result.json

```json
{
  "expediente_id": "qa07_paquete_entrega_nave222_20260525_183246",
  "generated": true,
  "required_missing": [],
  "optional_missing": [],
  "warnings": []
}
```

**Estado**: CORRECTO — `generated=true`, sin faltantes, sin advertencias.

---

## Paso 6 — Verificacion de DOCX

| Archivo | Tamaño en paquete | Estado |
|---------|-------------------|--------|
| `documento_ambiental_borrador_con_figuras.docx` | 1,756,453 B (1.68 MB) | CORRECTO |
| `documento_ambiental_borrador.docx` | 1,413,771 B (1.35 MB) | CORRECTO |

El DOCX enriquecido (con figuras) es significativamente mayor que el base, lo que confirma
que las 6 figuras (MAP-001..MAP-006) estan correctamente incluidas.

---

## Paso 7 — Verificacion de seguridad

- Archivos sensibles (`.env`, `*secret*`, `*password*`, `*credential*`, `*.key`, `*.pem`): **NO detectados**.
- El paquete NO contiene `inputs/`, `capas/`, `bloques/` ni otras carpetas del expediente.
- El paquete NO contiene ZIP, PDF ni ficheros comprimidos.
- El directorio `tmp/` no se ha committeado al repositorio.

**Estado**: SEGURIDAD OK.

---

## Paso 8 — Verificacion de README_ENTREGA.md

El README incluye:
1. Cabecera con expediente_id, estado y numero de archivos
2. Tabla de contenido por seccion
3. Lista de archivos del documento principal
4. Lista de auditorias internas
5. Lista de anexos graficos y trazabilidad
6. Bloque de advertencia de alcance

**Disclaimer presente**: "Este paquete no declara el expediente apto para presentacion administrativa."

**Estado**: CORRECTO.

---

## Paso 9 — Suite de tests post-QA

**Comando**: `venv\Scripts\python -m pytest tests/ -q --tb=no`

**Resultado**: `6036 passed, 12 skipped, 333 subtests passed in 132.45s`

**Estado**: CORRECTO — sin regresiones.

---

## Resumen de resultados

| Check | Resultado |
|-------|-----------|
| QC documental (DOC-04+DOC-05) | OK — 0 errores |
| Dry-run document-package | OK — exit 0, 0 archivos escritos |
| document-package --write | OK — 20 archivos copiados, exit 0 |
| Estructura 4 secciones | OK |
| Seccion 03 contiene `.md` figuras | OK |
| Seccion 04 contiene `.json` figuras | OK |
| README_ENTREGA.md presente | OK |
| package_build_result.json/md | OK |
| DOCX con figuras en seccion 01 | OK (1.68 MB) |
| DOCX base en seccion 01 | OK (1.35 MB) |
| Seguridad: sin sensibles | OK |
| Sin ZIP, sin PDF, sin compresion | OK |
| Suite de tests | 6036 passed, 12 skipped |
| Expediente piloto original intacto | OK — sin modificaciones |

**Veredicto**: **COMPLETADO** — DOC-06 genera un paquete de entrega correcto, seguro
y trazable sobre el expediente real NAVE-222.

---

## Bugs detectados durante QA-07

Ninguno. El codigo DOC-06 funciona correctamente sobre datos reales.

---

## Pendiente post-QA-07

- **DOC-07**: Compresion ZIP y exportacion PDF del paquete de entrega (siguiente hito P1).
