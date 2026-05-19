# QA-03 — Prueba end-to-end del pipeline técnico ampliado a 17 pasos

**Fecha:** 2026-05-18  
**Expediente de prueba:** copia temporal de EIA-2026-RECIMETAL-NAVE-222  
**Ruta temporal:** `tmp/qa03_pipeline_17steps_20260518_171345`  
**Estado:** COMPLETADO ✓

---

## 1. Expediente usado

**EIA-2026-RECIMETAL-NAVE-222**

Motivo: mismo expediente que QA-02, con los inputs necesarios disponibles
(incluido `fase4/phase4_result.json`, copiado desde la copia temporal de QA-02
ya que el NAVE-222 original no dispone de este archivo). PARCELA no se usa
porque tampoco tiene `fase4/phase4_result.json`.

La carpeta `fase4/phase4_result.json` es obligatoria para el paso INVENTORY_BUILD.
El expediente original NAVE-222 no incluye esta carpeta; fue generada en una
sesión anterior de Fase 4. La copia de QA-02 la conserva y se usa como fuente
para QA-03.

---

## 2. Ruta de copia temporal

```
C:\Users\KitDigital\proyecto-eia\tmp\qa03_pipeline_17steps_20260518_171345\
```

Creada copiando `expediente-EIA-2026-RECIMETAL-NAVE-222` completo, más el
archivo `fase4/phase4_result.json` desde la copia QA-02.

---

## 3. Comando ejecutado

```
python run_expediente.py tmp\qa03_pipeline_17steps_20260518_171345 run-technical-pipeline --write --continue-on-error
```

---

## 4. Resultado general

| Campo | Valor |
|-------|-------|
| Pipeline status | **SUCCESS** |
| Pasos OK | **17 / 17** |
| Pasos fallidos | 0 |
| Pasos bloqueados | 0 |
| Pasos omitidos | 0 |
| Audit status | NO_CONFORME (esperado: datos de prueba incompletos) |

Primera ejecución (sin `fase4/phase4_result.json`):
- INVENTORY_BUILD → WARNING
- INVENTORY_GATE → BLOCKED
- Resto → SKIPPED (15 pasos)

Tras añadir `fase4/phase4_result.json` desde copia QA-02:
- **17/17 OK** sin correcciones de código.

---

## 5. Tabla de los 17 pasos

| # | step_id | status | Salidas generadas | Notas |
|---|---------|--------|-------------------|-------|
| 1 | INVENTORY_BUILD | SUCCESS | `inventario/inventory_summary.json`, fichas FI-001…FI-016 | 16 factores |
| 2 | INVENTORY_GATE | SUCCESS | `inventario/phase5_gate_result.json`, `.md` | APTO_FASE6_CON_CAUTELAS |
| 3 | PHASE6_ACTIONS | SUCCESS | `impactos/phase6_actions.json`, `phase6_model_base.json` | 1 acción |
| 4 | PHASE6_IDENTIFY_IMPACTS | SUCCESS | `impactos/phase6_model_with_impacts.json` | 2 impactos |
| 5 | PHASE6_ASSIGN_CONESA | SUCCESS | `impactos/phase6_model_with_conesa.json` | 2 asignaciones |
| 6 | PHASE6_GENERATE_MEASURES | SUCCESS | `impactos/phase6_model_with_measures.json` | medidas generadas |
| 7 | PHASE6_GENERATE_PVA | SUCCESS | `impactos/phase6_model_with_pva.json` | PVA generado |
| 8 | PHASE6_VALIDATE_PVA | SUCCESS | `impactos/pva_coverage_result.json`, `.md` | cobertura OK |
| 9 | PHASE6_CUMULATIVE | SUCCESS | `impactos/cumulative_synergistic_result.json`, `C5_acumulativos_sinergicos.md` | 2 grupos acumulativos |
| 10 | AUDIT_ART45 | WARNING | `auditoria/art45_checklist_result.json`, `.md` | advertencias esperadas |
| 11 | AUDIT_PRUDENCE | WARNING | `auditoria/prudence_validation_result.json`, `.md` | observaciones esperadas |
| 12 | AUDIT_TRACEABILITY | WARNING | `auditoria/traceability_validation_result.json`, `.md` | trazabilidad incompleta (esperado) |
| 13 | AUDIT_BLOCK_CONSISTENCY | WARNING | `auditoria/block_consistency_result.json`, `.md` | sin bloques completos |
| 14 | AUDIT_CONESA | SUCCESS | `auditoria/conesa_check_result.json`, `.md` | cobertura Conesa OK |
| 15 | AUDIT_DIAGNOSTIC_MEASURES | SUCCESS | `auditoria/diagnostic_measure_validation_result.json`, `.md` | sin medidas diagnósticas problemáticas |
| 16 | AUDIT_PRL_MEASURES | WARNING | `auditoria/prl_measure_validation_result.json`, `.md` | observaciones EIA/PRL (esperado) |
| 17 | AUDIT_FINAL | WARNING | `auditoria/final_audit_result.json`, `.md` | NO_CONFORME (esperado) |

---

## 6. Outputs encontrados

### `inventario/`
- `inventory_summary.json` ✓
- `phase5_gate_result.json` ✓
- `phase5_gate_result.md` ✓
- Fichas FI-001 … FI-016 ✓

### `impactos/`
- `phase6_actions.json` ✓
- `phase6_model_base.json` ✓
- `phase6_model_with_impacts.json` ✓
- `phase6_model_with_conesa.json` ✓ (nombre real del paso ASSIGN_CONESA)
- `phase6_model_with_measures.json` ✓
- `phase6_model_with_pva.json` ✓
- `pva_coverage_result.json` ✓
- `cumulative_synergistic_result.json` ✓
- `C5_acumulativos_sinergicos.md` ✓

### `auditoria/`
- `art45_checklist_result.json` ✓
- `prudence_validation_result.json` ✓
- `traceability_validation_result.json` ✓
- `block_consistency_result.json` ✓
- `conesa_check_result.json` ✓
- `diagnostic_measure_validation_result.json` ✓ (nuevo, RD-08)
- `prl_measure_validation_result.json` ✓ (nuevo, RD-09)
- `final_audit_result.json` ✓
- `final_audit_result.md` ✓
- `technical_pipeline_result.json` ✓
- `technical_pipeline_result.md` ✓

---

## 7. Outputs faltantes

| Archivo | Motivo |
|---------|--------|
| `impactos/phase6_model_scored.json` | No es un output real. El paso PHASE6_ASSIGN_CONESA genera `phase6_model_with_conesa.json`. El nombre "scored" era incorrecto en la especificación de QA-03. No es un bug. |

---

## 8. Incidencias detectadas

### I-1 — Input faltante: `fase4/phase4_result.json`

- **Tipo:** a) falta de input real
- **Paso afectado:** INVENTORY_BUILD
- **Descripción:** NAVE-222 original no incluye `fase4/phase4_result.json` (output de la fase offline). Sin este archivo, INVENTORY_BUILD falla con FileNotFoundError → WARNING sin escribir `inventory_summary.json` → INVENTORY_GATE BLOCKED.
- **Resolución:** Input copiado desde la copia de QA-02 (que sí lo tenía). No se modifica código.
- **Nota:** `fase4/phase4_result.json` es generado por el comando `phase4-offline`, que precede al pipeline técnico. En un expediente real, este archivo existe siempre antes de ejecutar PIPE-01.

### I-2 — Nombre de output en spec: `phase6_model_scored.json`

- **Tipo:** e) comportamiento correcto, error en especificación
- **Paso afectado:** PHASE6_ASSIGN_CONESA
- **Descripción:** El archivo real generado por PHASE6_ASSIGN_CONESA se llama `phase6_model_with_conesa.json`, no `phase6_model_scored.json`.
- **Resolución:** Ninguna. Es correcto por diseño. La especificación de QA-03 usaba un nombre alternativo.

---

## 9. Correcciones aplicadas

Ninguna corrección de código fue necesaria. El pipeline de 17 pasos funciona correctamente. La única incidencia (I-1) se resuelve copiando el input de Fase 4.

---

## 10. Resultado de suite final

```
Ran 5482 tests in ~81s
OK (skipped=12)
0 failures, 0 errors
```

Sin regresiones respecto al baseline de PIPE-03.

---

## 11. Conclusión

QA-03 **COMPLETADO ✓**

El pipeline técnico ampliado a 17 pasos:
- Ejecuta los 17 pasos en orden, sin parada fatal, sin regresiones.
- Los pasos 15 (AUDIT_DIAGNOSTIC_MEASURES) y 16 (AUDIT_PRLMEASURES) se integran correctamente con el resto del pipeline.
- Genera todos los archivos de salida esperados en `inventario/`, `impactos/` y `auditoria/`.
- Los dos nuevos outputs de RD-08 y RD-09 (`diagnostic_measure_validation_result.json/md`, `prl_measure_validation_result.json/md`) son generados y recogidos por AUDIT_FINAL.
- El estado NO_CONFORME del audit final es **correcto y esperado** para un expediente de prueba sin bloques redactados ni datos completos.
- Suite completa: 5482 tests OK, 12 skipped, 0 failures.
