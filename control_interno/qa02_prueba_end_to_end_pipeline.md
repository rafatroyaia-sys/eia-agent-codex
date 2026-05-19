# QA-02 — Prueba end-to-end del pipeline técnico

**Fecha:** 2026-05-15  
**Expediente de prueba:** copia temporal de EIA-2026-RECIMETAL-NAVE-222  
**Ruta temporal:** `tmp/qa02_pipeline_20260515_180207/expediente-EIA-2026-RECIMETAL-NAVE-222`  
**Estado:** COMPLETADO ✓

---

## Objetivo

Ejecutar `run-technical-pipeline --write --continue-on-error` sobre una copia temporal del
piloto Recimetal NAVE-222 y verificar que los 13 pasos se completan sin errores fatales,
producen los archivos de salida esperados, y no introducen regresiones en la suite de tests.

---

## Resultado del pipeline

| Campo | Valor |
|-------|-------|
| Pipeline status | SUCCESS |
| Pasos OK | 13/13 |
| Pasos fallidos | 0 |
| Pasos bloqueados | 0 |
| Audit status | NO_CONFORME (esperado: datos de prueba incompletos) |
| Duración total | ~1 s |

### Detalle por paso

| Paso | Estado | Notas |
|------|--------|-------|
| INVENTORY_BUILD | SUCCESS | 16 factores |
| INVENTORY_GATE | SUCCESS | APTO_FASE6_CON_CAUTELAS (15 factores no listos) |
| PHASE6_ACTIONS | SUCCESS | 1 acción detectada |
| PHASE6_IDENTIFY_IMPACTS | SUCCESS | 2 impactos identificados |
| PHASE6_ASSIGN_CONESA | SUCCESS | 2 asignaciones |
| PHASE6_GENERATE_MEASURES | SUCCESS | 2 medidas generadas |
| PHASE6_GENERATE_PVA | SUCCESS | 3 programas PVA |
| PHASE6_VALIDATE_PVA | SUCCESS | Cobertura PVA OK |
| PHASE6_CUMULATIVE | SUCCESS | 2 grupos acumulativos, 0 sinérgicos |
| AUDIT_ART45 | WARNING | Checklist estructural con advertencias (esperado) |
| AUDIT_PRUDENCE | WARNING | Análisis de prudencia con observaciones (esperado) |
| AUDIT_TRACEABILITY | WARNING | Análisis de trazabilidad con observaciones (esperado) |
| AUDIT_FINAL | WARNING | NO_CONFORME por datos incompletos (esperado) |

Los 4 pasos con WARNING son esperables: el expediente temporal tiene datos mínimos
(inventario parcial, sin bloques redactados completos, sin HC/DA trazados).

---

## Archivos generados

### `inventario/` (21 ficheros)
- FI-001 a FI-016 (fichas MD) — 16 factores ambientales
- `inventory_summary.json` (35,9 KB)
- `indice_inventario.json`
- `resumen_inventario.md`
- `phase5_gate_result.json` + `phase5_gate_result.md`

### `impactos/` (20 ficheros)
- `phase6_model_base.json` → `phase6_model_with_pva.json` (cadena completa)
- `impactos.json`, `medidas.json`, `pva.json`
- `conesa_assignment_result.json`, `impact_identification_result.json`
- `measure_generation_result.json`, `pva_generation_result.json`
- `pva_coverage_result.json` + `pva_coverage_result.md`
- `cumulative_synergistic_result.json`
- `AG09_valoracion.md`, `AG09_medidas.md`, `AG09_PVA.md`, `C5_acumulativos_sinergicos.md`

### `auditoria/` (10 ficheros)
- `art45_checklist_result.json` + `.md`
- `prudence_validation_result.json` + `.md`
- `traceability_validation_result.json` + `.md`
- `final_audit_result.json` (1,14 MB) + `final_audit_result.md`
- `technical_pipeline_result.json` + `technical_pipeline_result.md`

---

## Bugs encontrados y corregidos

### Bug 1 — PHASE6_CUMULATIVE: atributo incorrecto en CumulativeSynergyResult
- **Archivo:** `src/eia_agent/core/technical_pipeline.py`, `_run_phase6_cumulative`
- **Error:** `AttributeError: 'CumulativeSynergyResult' object has no attribute 'sections'`
- **Causa:** El mensaje de éxito usaba `result.sections` que no existe.
- **Fix:** Reemplazado por `result.cumulative_groups` y `result.synergistic_groups`.

### Bug 2 — INVENTORY_BUILD: atributo incorrecto en InventoryBuildResult
- **Archivo:** `src/eia_agent/core/technical_pipeline.py`, `_run_inventory_build`
- **Error:** `AttributeError: 'InventoryBuildResult' object has no attribute 'total_factors'`
- **Causa:** El mensaje usaba `result.total_factors`; el campo real es `result.factor_count`.
- **Fix:** Cambiado a `result.factor_count`.

### Bug 3 — inventory_climate_change_builder: tipo incorrecto en dry_months_gaussen
- **Archivo:** `src/eia_agent/core/inventory_climate_change_builder.py`, `_extract_climate_summary`
- **Error:** `TypeError: '>' not supported between instances of 'list' and 'int'`
- **Causa:** `dry_months_gaussen` en el JSON de phase4 de NAVE-222 es una lista de meses
  (e.g. `[7, 8]`), pero el código esperaba un entero (conteo de meses secos).
- **Fix inicial:** `len(cc.get("dry_months_gaussen") or [])` — correcto para listas.
- **Regresión detectada:** Tests en `test_inventory_risk_builder` pasan un entero directamente.
- **Fix definitivo:** `(lambda v: v if isinstance(v, int) else len(v) if v else 0)(cc.get("dry_months_gaussen"))`
  — maneja int, lista, y None.

---

## Suite de tests tras QA-02

```
Ran 4875 tests in ~44s
OK (skipped=155)
0 failures, 0 errors
```

Sin regresiones respecto a QA-01 (4875 tests OK, 155 skipped).

---

## Notas sobre el resultado NO_CONFORME

El estado final `NO_CONFORME` del audit AU-04 es **esperado y correcto** para este caso:

1. El expediente NAVE-222 es un piloto de prueba con inventario incompleto
   (15 de 16 factores marcados como "no listos" para Fase 6).
2. No hay bloques A-K redactados → la validación de prudencia y trazabilidad
   trabaja sobre contenido mínimo o vacío.
3. El objetivo de QA-02 es verificar que el pipeline no tiene errores fatales,
   no que el expediente esté en condiciones de presentación.

Un expediente real con inventario completo y bloques redactados produciría
un resultado `CONFORME_CON_OBSERVACIONES` o `CONFORME` en el audit final.

---

## Conclusión

QA-02 **SUPERADO**. El pipeline técnico automático:
- Ejecuta los 13 pasos en orden sin parada fatal.
- Genera todos los archivos de salida esperados en `inventario/`, `impactos/` y `auditoria/`.
- Detecta correctamente el estado del expediente (NO_CONFORME por datos incompletos).
- No introduce regresiones en la suite de 4875 tests.

PIPE-01 queda validado como funcional en entorno real (datos de piloto).
