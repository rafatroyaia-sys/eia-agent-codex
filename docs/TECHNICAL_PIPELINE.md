# TECHNICAL_PIPELINE — PIPE-01 + PIPE-02 + PIPE-03 + PIPE-04

Módulo: `src/eia_agent/core/technical_pipeline.py`  
CLI: `python run_expediente.py <expediente> run-technical-pipeline [--write] [--prod] [--continue-on-error]`  
Tests: `tests/test_technical_pipeline.py`

---

## Qué hace el pipeline

Ejecuta en un único flujo, en orden, los 18 módulos técnicos ya construidos, desde el inventario ambiental (Fase 5) hasta el informe final de auditoría (AU-04 con RD-04, RD-06, RD-08, RD-09 e IM-09).

```
python run_expediente.py <expediente> run-technical-pipeline --write
```

Los pasos se encadenan automáticamente: el output de cada paso es el input del siguiente.

---

## Qué NO hace PIPE-01

- **No crea metodología nueva.** Solo orquesta módulos ya existentes.
- **No declara el expediente apto para presentación administrativa.**
- **No sustituye la revisión técnica ni jurídica** del Documento Ambiental.
- **No llama APIs externas** ni usa IA ni red.
- **No duplica la lógica de negocio** de los módulos individuales.
- **No modifica expedientes piloto.**
- **No ejecuta fases previas** (Fase 1, 2, 3, 4). El punto de partida es Fase 5.

---

## Orden de pasos

| # | Paso | Módulo equivalente | Output principal |
|---|------|--------------------|-----------------|
| 1 | INVENTORY_BUILD | `inventory-build --write` | `inventario/inventory_summary.json` |
| 2 | INVENTORY_GATE | `inventory-gate --write` | `inventario/phase5_gate_result.json` |
| 3 | PHASE6_ACTIONS | `phase6-actions --write` | `impactos/phase6_model_base.json` |
| 4 | PHASE6_IDENTIFY_IMPACTS | `phase6-identify-impacts --write` | `impactos/phase6_model_with_impacts.json` |
| 5 | PHASE6_ASSIGN_CONESA | `phase6-assign-conesa --write` | `impactos/phase6_model_with_conesa.json` |
| 6 | PHASE6_GENERATE_MEASURES | `phase6-generate-measures --write` | `impactos/phase6_model_with_measures.json` |
| 7 | PHASE6_GENERATE_PVA | `phase6-generate-pva --write` | `impactos/phase6_model_with_pva.json` |
| 8 | PHASE6_VALIDATE_PVA | `phase6-validate-pva --write` | `impactos/pva_coverage_result.json` |
| 9 | AUDIT_CONDITIONAL_CHAINS | `audit-conditional-chains --write` | `auditoria/conditional_chain_result.json` |
| 10 | PHASE6_CUMULATIVE | `phase6-cumulative --write` | `impactos/cumulative_synergistic_result.json` |
| 11 | AUDIT_ART45 | `audit-art45 --write` | `auditoria/art45_checklist_result.json` |
| 12 | AUDIT_PRUDENCE | `audit-prudence --write` | `auditoria/prudence_validation_result.json` |
| 13 | AUDIT_TRACEABILITY | `audit-traceability --write` | `auditoria/traceability_validation_result.json` |
| 14 | AUDIT_BLOCK_CONSISTENCY | `audit-block-consistency --write` | `auditoria/block_consistency_result.json` |
| 15 | AUDIT_CONESA | `audit-conesa --write` | `auditoria/conesa_check_result.json` |
| 16 | AUDIT_DIAGNOSTIC_MEASURES | `audit-diagnostic-measures --write` | `auditoria/diagnostic_measure_validation_result.json` |
| 17 | AUDIT_PRL_MEASURES | `audit-prl-measures --write` | `auditoria/prl_measure_validation_result.json` |
| 18 | AUDIT_FINAL | `audit-final --write` | `auditoria/final_audit_result.json` |

---

## Estados de paso

| Estado | Significado |
|--------|-------------|
| `SUCCESS` | Paso completado sin errores |
| `WARNING` | Completado con observaciones no bloqueantes |
| `FAILED` | El paso lanzó un error |
| `BLOCKED` | El input requerido no existía |
| `SKIPPED` | Omitido por fallo en paso anterior (con stop_on_error=True) |

El pipeline devuelve `is_success() = True` solo si no hay pasos FAILED ni BLOCKED.

---

## Modo dry-run vs --write

**Sin `--write` (dry-run):**
- Los módulos se ejecutan en memoria.
- No se escriben archivos de fases intermedias.
- Si un paso necesita un archivo del paso anterior que no existe, se marca **BLOCKED**.
- Útil para comprobar qué pasos se pueden ejecutar con el estado actual del expediente.

**Con `--write`:**
- Cada paso escribe sus outputs en las rutas normales.
- Los pasos posteriores encuentran los archivos generados.
- Al final, `auditoria/technical_pipeline_result.json` y `.md` se generan si se pasa `--write`.

---

## Opciones CLI

```
python run_expediente.py <expediente> run-technical-pipeline [--write] [--prod] [--continue-on-error]
```

| Opción | Descripción |
|--------|-------------|
| `--write` | Escribe todos los outputs en sus rutas normales |
| `--prod` | Modo producción (mode=PROD). No cambia `administrative_ready`. |
| `--continue-on-error` | Continúa con pasos siguientes aunque un paso falle |

**Códigos de salida:**
- `0` → pipeline exitoso (`is_success() == True`)
- `1` → hay pasos FAILED o BLOCKED, o el expediente no existe

---

## Relación con fases 5, 6 y AU

```
Fase 4 offline (phase4-offline)
    │
    ▼
PIPE-01 punto de entrada
    │
    ├─▶ Fase 5: INVENTORY_BUILD + INVENTORY_GATE
    │
    ├─▶ Fase 6: ACTIONS → IMPACTS → CONESA → MEASURES → PVA → VALIDATE_PVA → CUMULATIVE
    │
    └─▶ Auditoría: AU-01 → AU-02 → AU-03 → RD-04 → RD-06 → RD-08 → RD-09 → AU-04 (informe final)
```

Los outputs de AU-04 (`final_audit_result.json` + `.md`) son el resultado ejecutivo del pipeline completo. AU-04 recibe los resultados de RD-04, RD-06, RD-08 y RD-09 como entradas opcionales (None → sin incidencia adicional, retrocompatible).

---

## Ejecución de tests

```
python -m unittest tests.test_technical_pipeline
python -m unittest discover -s tests
```

Los tests son 100% offline: usan `tempfile`, `unittest.mock` y `patch.dict` para simular los step runners sin necesidad de web, IA ni APIs.

---

## Limitaciones conocidas

- El pipeline asume que las Fases 1-4 ya se ejecutaron y sus outputs están disponibles en el expediente.
- En dry-run, los pasos de Fase 6 (3-9) quedan BLOCKED si no hay archivos intermedios de ejecuciones previas con `--write`.
- El informe de pipeline (`technical_pipeline_result.json/md`) solo se escribe con `--write`.
