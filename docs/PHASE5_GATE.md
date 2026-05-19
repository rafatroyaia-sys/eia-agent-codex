# PHASE5_GATE — F5-01

Gate de cierre de Fase 5 / Inventario ambiental offline.

**Módulo**: `src/eia_agent/core/phase5_gate.py`  
**ID de productización**: F5-01  
**Completado**: 2026-05-02  
**Dependencias**: IV-00 (`inventory_model`), IV-02 (`inventory_builder`)

---

## Qué hace F5-01

- Evalúa si el inventario ambiental construido (Fase 5) cumple los requisitos mínimos para avanzar a Fase 6 (valoración de impactos).
- Detecta errores estructurales: conteo incorrecto de factores, IDs duplicados, IDs no canónicos, factores canónicos ausentes.
- Detecta incoherencias por factor: `evidence_status`/`field_mode`/`inventory_semaphore` inválidos o vacíos; `ready=True` con semáforo bloqueante; `ready=True` con gap ALTA pendiente.
- Detecta problemas en gaps: `criticality`/`resolution_mode` inválidos; descripciones vacías.
- Produce una decisión: `APTO_FASE6`, `APTO_FASE6_CON_CAUTELAS` o `NO_APTO_FASE6`.
- Genera un informe markdown y un JSON estructurado.
- Se expone como comando CLI `inventory-gate [--write] [--prod]`.

## Qué NO hace F5-01

| Capacidad | Estado |
|-----------|--------|
| Valorar impactos | No — Fase 6 |
| Consultar fuentes externas | No — offline |
| Verificar coherencia con documentación del promotor | No — solo verifica el inventario JSON |
| Aprobar la tramitación administrativa | No — `administrative_ready` siempre False |
| Reemplazar la revisión del órgano ambiental | No |
| Usar IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### `evaluate_phase5_gate(summary, test_mode=True) → Phase5GateResult`

Evalúa el gate sobre un `InventorySummary` ya construido.

**Reglas aplicadas (en orden):**

**1. Estructura del resumen:**

| Condición | Tipo |
|-----------|------|
| `total_factors != 16` | ERROR: `WRONG_FACTOR_COUNT` |
| Factor duplicado | ERROR: `DUPLICATE_FACTOR` |
| `factor_id` fuera de FI-001...FI-016 | ERROR: `INVALID_FACTOR_ID` |
| Factor canónico ausente | ERROR: `MISSING_FACTOR` |

**2. Por factor:**

| Condición | Tipo |
|-----------|------|
| `evidence_status` vacío o inválido | ERROR: `INVALID_EVIDENCE_STATUS` |
| `field_mode` vacío o inválido | ERROR: `INVALID_FIELD_MODE` |
| `inventory_semaphore` vacío o inválido | ERROR: `INVALID_SEMAPHORE` |
| `description` vacía | WARNING: `EMPTY_DESCRIPTION` |
| `data_sources` vacío | WARNING: `NO_DATA_SOURCES` |
| `ready=True` con semáforo ROJO o NO_CONSTA | ERROR: `READY_WITH_BLOCKING_SEMAPHORE` |
| `ready=True` con gap ALTA PENDIENTE | ERROR: `READY_WITH_ALTA_GAP` |

**3. Por gap:**

| Condición | Tipo |
|-----------|------|
| `criticality` inválida | ERROR: `INVALID_GAP_CRITICALITY` |
| `resolution_mode` inválido | ERROR: `INVALID_GAP_RESOLUTION_MODE` |
| `description` vacía | WARNING: `EMPTY_GAP_DESCRIPTION` |
| `criticality=ALTA` + `status=PENDIENTE` | → se añade a `critical_gaps` |

**4. Decisión:**

| Condición | Decisión |
|-----------|----------|
| `error_count > 0` | `NO_APTO_FASE6` |
| Sin errores, pero hay `critical_gaps` o factores no-ready | `APTO_FASE6_CON_CAUTELAS` |
| Sin errores, todos ready, sin gaps ALTA, sin ROJO/NO_CONSTA | `APTO_FASE6` |

`administrative_ready` es siempre `False`.

`test_mode` no altera la lógica de este gate (diferente a los gates de Fases 2-4).

---

### `evaluate_phase5_gate_from_inventory_json(path, test_mode=True) → Phase5GateResult`

Carga `inventory_summary.json` y evalúa el gate.

```
Raises:
    FileNotFoundError — si el archivo no existe
    ValueError        — si el JSON es inválido o no contiene 'factors'
```

---

### `build_phase5_gate_markdown(result) → str`

Genera el informe markdown del gate. Incluye:
- Cabecera con decisión y métricas clave
- Sección de errores (si los hay)
- Sección de avisos (si los hay)
- Tabla de gaps ALTA pendientes
- Lista de factores no listos para Fase 6
- Lista de factores con semáforo ROJO o NO_CONSTA
- Notas (test_mode, administrative_ready)

---

### `write_phase5_gate_outputs(result, output_dir) → tuple[Path, Path]`

Escribe `phase5_gate_result.json` y `phase5_gate_result.md` en `output_dir`.

---

## Dataclasses

### `Phase5GateIssue`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | `str` | ERROR / WARNING / INFO |
| `code` | `str` | Código corto identificador |
| `message` | `str` | Descripción legible |
| `recommendation` | `str` | Acción sugerida |
| `factor_id` | `str \| None` | Factor afectado (o None si es issue global) |

Métodos: `to_dict()`, `summary()`.

### `Phase5GateResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | `str` | ID del expediente |
| `decision` | `str` | APTO_FASE6 / APTO_FASE6_CON_CAUTELAS / NO_APTO_FASE6 |
| `total_factors` | `int` | Número de factores evaluados |
| `ready_count` | `int` | Factores con `ready=True` |
| `not_ready_factors` | `list[str]` | IDs de factores no listos |
| `critical_gaps` | `list[dict]` | Gaps ALTA PENDIENTE |
| `red_or_no_consta_factors` | `list[str]` | IDs con semáforo ROJO o NO_CONSTA |
| `issues` | `list[Phase5GateIssue]` | Lista de issues |
| `administrative_ready` | `bool` | Siempre False |
| `warnings` | `list[str]` | Avisos del gate |
| `notes` | `list[str]` | Notas informativas |

Métodos: `error_count()`, `warning_count()`, `info_count()`, `is_blocked()`, `to_dict()`, `summary()`.

---

## Integración CLI

Comando: `inventory-gate [--write] [--prod]`

```
python run_expediente.py <expediente> inventory-gate
python run_expediente.py <expediente> inventory-gate --write
python run_expediente.py <expediente> inventory-gate --prod
```

- Lee `inventario/inventory_summary.json` (generado por `inventory-build --write`).
- Sin `--write`: imprime el resumen por stdout.
- Con `--write`: escribe `phase5_gate_result.json` y `.md` en `inventario/`.
- `--prod` desactiva `test_mode` (la lógica del gate es idéntica en ambos modos).
- Devuelve código 0 si no bloqueado; 1 si `NO_APTO_FASE6` o si falta el inventario.

---

## Comportamiento offline típico

Con un inventario generado por `inventory-build` en modo offline (sin campo), el resultado esperado es **APTO_FASE6_CON_CAUTELAS**:

- Sin errores estructurales (16 factores, IDs válidos).
- Todos los factores tienen `ready=False`.
- Muchos gaps ALTA PENDIENTE (prospección de campo).
- Muchos factores con semáforo NO_CONSTA.
- `administrative_ready=False`.

Esto es correcto y esperado: el inventario offline es una base de trabajo, no un inventario definitivo.

---

## Tests

**Archivo**: `tests/test_phase5_gate.py`  
**Tests**: 75 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestPhase5GateIssue` | 6 | to_dict, summary, severidad inválida, severidades válidas |
| `TestPhase5GateResult` | 11 | conteos, is_blocked, administrative_ready, to_dict, JSON, summary |
| `TestEvaluatePhase5GateStructure` | 5 | count=16 APTO; missing → NO_APTO; duplicate → NO_APTO; wrong count → NO_APTO; invalid ID → NO_APTO |
| `TestEvaluatePhase5GateFactorLevel` | 9 | ready+ROJO → ERROR; ready+NO_CONSTA → ERROR; ready+ALTA gap → ERROR; gap CUBIERTO no error; desc vacía WARNING; sources vacío WARNING; evidence inválido ERROR; field_mode inválido ERROR; semáforo inválido ERROR |
| `TestEvaluatePhase5GateGapLevel` | 5 | ALTA gap en critical_gaps; ALTA+not-ready → cautelas; MEDIA no critical; gap desc vacía WARNING |
| `TestPhase5GateDecision` | 8 | APTO_FASE6 full; cautelas not-ready; cautelas critical gap; NO_APTO estructural; admin_ready always False; not_ready listado; red_no_consta listado; test_mode en notas |
| `TestRealisticOfflineInventory` | 6 | cautelas; 16 critical gaps; 16 not ready; 0 errors; admin False; JSON serializable |
| `TestBuildPhase5GateMarkdown` | 10 | expediente_id; label APTO; label NO APTO; label CAUTELAS; sección errores; tabla gaps; sección not-ready; nota admin; footer F5-01; tipo str |
| `TestWritePhase5GateOutputs` | 5 | escribe json+md; nombres correctos; JSON válido; md con expediente_id; crea directorio |
| `TestEvaluateFromJson` | 5 | JSON válido; FileNotFoundError; JSON inválido; sin key factors; offline cautelas |
| `TestCLI` | 4 | sin inventario → 1; inventario OK → 0; NO_APTO → 1; --write escribe archivos |

---

*Generado por EIA-Agent v2.1 — F5-01 — 2026-05-02*
