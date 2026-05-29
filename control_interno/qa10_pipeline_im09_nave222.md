# QA-10 — Prueba real del pipeline completo con IM-09 integrado

**Fecha:** 2026-05-29  
**Ítem validado:** PIPE-04 — Integrar IM-09 en pipeline técnico y auditoría final  
**Estado:** QA-10 COMPLETADO

---

## 1. Expediente probado

- **Origen:** `expediente-EIA-2026-RECIMETAL-NAVE-222`
- **Expediente de prueba (copia temporal):** `tmp/qa10_pipeline_im09_nave222_20260529_072941/`
- **Input adicional copiado:** `fase4/phase4_result.json` — reutilizado desde `tmp/qa03_pipeline_17steps_20260518_171345/fase4/phase4_result.json` (mismo procedimiento que QA-03; NAVE-222 original no incluye este archivo porque `phase4-offline` es previo al pipeline técnico).

---

## 2. Ruta de copia temporal

```
C:\Users\KitDigital\proyecto-eia\tmp\qa10_pipeline_im09_nave222_20260529_072941\
```

No se ha modificado el expediente piloto original.

---

## 3. Comando ejecutado

```
python run_expediente.py tmp\qa10_pipeline_im09_nave222_20260529_072941 run-technical-pipeline --write
```

**Exit code:** 0 (SUCCESS)

---

## 4. Resultado general del pipeline

| Campo | Valor |
|-------|-------|
| final_status | SUCCESS |
| final_audit_status | NO_CONFORME |
| total_steps | 18 |
| success_count | 18 |
| failed_count | 0 |
| blocked_count | 0 |
| skipped_count | 0 |
| administrative_ready | False |

La calificación NO_CONFORME es resultado real esperado: los bloques de NAVE-222 contienen frases de cierre indebido (AU-02), afirmaciones no trazadas (AU-03), incoherencias entre bloques (RD-04) y medidas PRL mezcladas con EIA (RD-09). IM-09 reporta CONFORME (sin errores de cadena condicional).

---

## 5. Tabla de los 18 pasos

| # | step_id | status | Salidas principales | Notas |
|---|---------|--------|---------------------|-------|
| 1 | INVENTORY_BUILD | SUCCESS | `inventario/inventory_summary.json`, fichas FI-001…FI-016 | 16 factores |
| 2 | INVENTORY_GATE | SUCCESS | `inventario/phase5_gate_result.json`, `.md` | APTO_FASE6_CON_CAUTELAS |
| 3 | PHASE6_ACTIONS | SUCCESS | `impactos/phase6_actions.json`, `phase6_model_base.json` | 1 acción |
| 4 | PHASE6_IDENTIFY_IMPACTS | SUCCESS | `impactos/phase6_model_with_impacts.json` | 2 impactos |
| 5 | PHASE6_ASSIGN_CONESA | SUCCESS | `impactos/phase6_model_with_conesa.json` | Conesa asignado |
| 6 | PHASE6_GENERATE_MEASURES | SUCCESS | `impactos/phase6_model_with_measures.json` | 2 medidas |
| 7 | PHASE6_GENERATE_PVA | SUCCESS | `impactos/phase6_model.json` | 3 PVA |
| 8 | PHASE6_VALIDATE_PVA | SUCCESS | `impactos/pva_coverage_result.json`, `.md` | Cobertura validada |
| 9 | AUDIT_CONDITIONAL_CHAINS | SUCCESS | `auditoria/conditional_chain_result.json`, `.md` | IM-09 OK — sin errores |
| 10 | PHASE6_CUMULATIVE | SUCCESS | `impactos/cumulative_section.json`, `.md` | Acumulativos generados |
| 11 | AUDIT_ART45 | WARNING | `auditoria/art45_checklist_result.json`, `.md` | Requisitos parciales/no cubiertos |
| 12 | AUDIT_PRUDENCE | WARNING | `auditoria/prudence_validation_result.json`, `.md` | Frases de cierre detectadas |
| 13 | AUDIT_TRACEABILITY | WARNING | `auditoria/traceability_validation_result.json`, `.md` | 26 afirmaciones no trazadas |
| 14 | AUDIT_BLOCK_CONSISTENCY | WARNING | `auditoria/block_consistency_result.json`, `.md` | 16 errores de coherencia |
| 15 | AUDIT_CONESA | SUCCESS | `auditoria/conesa_check_result.json`, `.md` | Conesa OK |
| 16 | AUDIT_DIAGNOSTIC_MEASURES | SUCCESS | `auditoria/diagnostic_measure_validation_result.json`, `.md` | Sin medidas diagnósticas como reductoras |
| 17 | AUDIT_PRL_MEASURES | WARNING | `auditoria/prl_measure_validation_result.json`, `.md` | 2 errores PRL/EIA |
| 18 | AUDIT_FINAL | WARNING | `auditoria/final_audit_result.json`, `.md` | NO_CONFORME — esperado |

---

## 6. Resultado de AUDIT_CONDITIONAL_CHAINS (paso 9)

- **step_id:** AUDIT_CONDITIONAL_CHAINS
- **status:** SUCCESS
- **Outputs generados:**
  - `auditoria/conditional_chain_result.json` ✓
  - `auditoria/conditional_chain_result.md` ✓

---

## 7. Extracto/summary de conditional_chain_result

```json
{
  "status": "OK",
  "administrative_ready": false,
  "checked_impacts": ["IMP-001", "IMP-002"],
  "checked_measures": ["MED-001", "MED-002"],
  "checked_pva_programs": ["PVA-001", "PVA-002", "PVA-003"],
  "conditioned_impacts": ["IMP-001", "IMP-002"],
  "conditioned_measures": ["MED-001", "MED-002"],
  "conditioned_pva_programs": ["PVA-001", "PVA-002", "PVA-003"],
  "issues": [],
  "warnings": [],
  "notes": [],
  "error_count": 0,
  "warning_count": 0,
  "info_count": 0
}
```

Todos los impactos y medidas están condicionados (marcados en datos de test), pero la propagación es coherente en toda la cadena: no hay errores CC-IMP-E001/E002 ni CC-MEA-E001. Resultado: OK.

---

## 8. Integración en audit-final

`conditional_chain_summary` en `final_audit_result.json`:

```json
{
  "available": true,
  "status": "OK",
  "checked_impacts": 2,
  "conditioned_impacts": 2,
  "conditioned_measures": 2,
  "conditioned_pva_programs": 3,
  "error_count": 0,
  "warning_count": 0,
  "is_valid": true
}
```

Sección 9 del markdown (`final_audit_result.md`):

```
## 9. Resultado IM-09 — Cadenas condicionales impacto-medida-PVA

- Estado: OK
- Impactos revisados: 2
- Impactos condicionados: 2
- Medidas condicionadas: 2
- PVA condicionados: 3
- Incidencias ERROR: 0
- Incidencias WARNING: 0
- Resultado: CONFORME
```

`administrative_ready: False` confirmado.

La calificación NO_CONFORME del audit-final NO proviene de IM-09 (que es CONFORME), sino de AU-02 (frases de cierre indebido), AU-03 (afirmaciones no trazadas), RD-04 (incoherencias bloques) y RD-09 (PRL/EIA). Resultado real y esperado para datos de NAVE-222 en modo gabinete.

---

## 9. Incidencias detectadas

### Incidencia de código — Bug en `_build_summary_from_conditional_chains`

- **Módulo:** `src/eia_agent/core/final_audit_report.py`
- **Descripción:** `_build_summary_from_conditional_chains` calculaba `is_valid` mediante `data.get("is_valid", False)`. El JSON generado por `ConditionalChainResult.to_dict()` no incluye la clave `is_valid`, por lo que el default `False` se aplicaba siempre, haciendo que el summary mostrara `is_valid: false` incluso cuando el resultado era OK.
- **Severidad:** Leve (no afecta a la calificación del audit-final, solo al campo informativo del summary).
- **Detección:** Primera ejecución real del pipeline con `--write`.

---

## 10. Correcciones aplicadas

### Corrección 1 — `final_audit_report.py`

**Archivo:** `src/eia_agent/core/final_audit_report.py`  
**Línea afectada:** función `_build_summary_from_conditional_chains`  
**Cambio:** `data.get("is_valid", False)` → `data.get("error_count", 1) == 0`

Alineado con el patrón de `_build_summary_from_prl_measures` (misma lógica).

### Corrección 2 — Test de regresión añadido

**Archivo:** `tests/test_final_audit_report.py`  
**Test:** `TestBuildFinalAuditResultWithIM09.test_summary_is_valid_true_when_no_errors_and_no_is_valid_key`  
**Propósito:** Verifica que `is_valid=True` cuando `error_count=0` aunque el JSON no contenga la clave `is_valid`.

---

## 11. Resultado suite completa

| Ejecución | Tests | Resultado |
|-----------|-------|-----------|
| Baseline inicial | 6340 | OK (skipped=12) |
| Tras corrección + test regresión | 6341 | OK (skipped=12) |

---

## 12. Conclusión

**QA-10 COMPLETADO**

- Pipeline de 18 pasos ejecutado correctamente sobre copia de NAVE-222.
- `AUDIT_CONDITIONAL_CHAINS` en posición 9 (entre `PHASE6_VALIDATE_PVA` y `PHASE6_CUMULATIVE`).
- `AUDIT_FINAL` en posición 18 (último).
- `conditional_chain_result.json` y `.md` generados correctamente.
- `final_audit_result.json` incorpora `conditional_chain_summary` con `is_valid: true`.
- Sección 9 IM-09 presente en `final_audit_result.md`.
- Un bug menor detectado y corregido durante QA (is_valid en summary).
- Suite: 6341 tests OK, 0 failures, 0 errors.
- No se han modificado expedientes piloto originales.
- No se han añadido módulos nuevos.
