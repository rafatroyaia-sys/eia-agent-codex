# ART45_CHECKLIST — AU-01

Checklist programático del art. 45.1 Ley 21/2013 para EIA simplificada.

**Módulo**: `src/eia_agent/core/art45_checklist.py`  
**ID de productización**: AU-01  
**Completado**: 2026-05-14  
**Dependencias**: IM-00 (`impact_model` — solo tipado)

---

## Advertencia de alcance (obligatoria)

> **Este checklist es una verificación estructural interna. No declara aptitud
> administrativa ni sustituye revisión técnica o jurídica. No revisa la
> legislación autonómica específica (BOC, normativa de Canarias u otras CCAA).
> La clasificación final del expediente corresponde al órgano ambiental
> mediante el Informe de Impacto Ambiental (art. 47 Ley 21/2013).**
>
> `administrative_ready` = False — AU-01 nunca declara aptitud administrativa.

---

## Qué hace AU-01

- Lee outputs disponibles de fases 1 a 6 del expediente.
- Mapea los 12 requisitos del art. 45.1 Ley 21/2013 a evidencias internas.
- Clasifica cada requisito como: CUBIERTO / PARCIAL / NO_CUBIERTO / NO_APLICA.
- Genera incidencias ERROR (NO_CUBIERTO) y WARNING (PARCIAL).
- Produce informe JSON y markdown.
- Se expone como comando CLI `audit-art45 [--write]`.

---

## Qué NO hace AU-01

| Capacidad | Estado |
|-----------|--------|
| Declarar aptitud administrativa | No — `administrative_ready` siempre False |
| Sustituir revisión técnica o jurídica | No |
| Revisar legislación autonómica específica | No |
| Modificar el expediente | No |
| Valorar impactos | No |
| Crear impactos, medidas ni PVA | No |
| Usar IA | No |
| Consultar fuentes externas | No |
| Llamadas a APIs | No |
| Reemplazar la auditoría M-12 | No — AU-01 es un pre-checklist estructural |

---

## Requisitos evaluados (ART45-01 a ART45-12)

| ID | Título | Evaluación |
|----|--------|-----------|
| ART45-01 | Motivación del procedimiento EIA simplificada | `metadata.procedure_motivation` o triaje Fase 3 |
| ART45-02 | Definición, características y ubicación del proyecto | `phase6_model.actions` + `object_scope` |
| ART45-03 | Alternativas estudiadas y justificación de la solución | `metadata.alternatives_analysis` / `alternativa_cero` |
| ART45-04 | Efectos previsibles directos e indirectos | `phase6_model.impacts` |
| ART45-05 | Efectos acumulativos y sinérgicos | `cumulative_result` (IM-08) |
| ART45-06 | Factores ambientales afectados | `phase6_model.receptor_factors` (16 factores) |
| ART45-07 | Medidas preventivas, correctoras y compensatorias | `phase6_model.measures` |
| ART45-08 | Programa de Vigilancia Ambiental | `phase6_model.pva_programs` + `pva_coverage_result` (IM-07) |
| ART45-09 | Vulnerabilidad ante riesgos de accidentes / catástrofes | FR-016/FR-005 en receptor_factors e impacts |
| ART45-10 | Cartografía y ubicación suficiente | `cartography_plan` o mapas en cartografia/ |
| ART45-11 | Incertidumbres, gaps y limitaciones declaradas | `data_gaps` en impactos + gaps IM-07/IM-08 |
| ART45-12 | Resumen no técnico o base para generarlo | `metadata.non_technical_summary` / material base |

---

## Estados de cobertura

| Estado | Condición | Incidencia generada |
|--------|-----------|-------------------|
| `CUBIERTO` | Evidencia suficiente | — |
| `PARCIAL` | Evidencia parcial o incompleta | WARNING |
| `NO_CUBIERTO` | Sin evidencia | **ERROR** |
| `NO_APLICA` | Requisito no aplicable al proyecto | INFO |

`is_structurally_complete()` = True solo si no hay NO_CUBIERTO y no hay ERRORs.

---

## Reglas de evaluación por requisito

### ART45-01 — Motivación

- CUBIERTO: `metadata.procedure_motivation` no vacío.
- PARCIAL: Fase 3 (triaje normativo) detectada pero sin texto de motivación.
- NO_CUBIERTO: Sin datos.

### ART45-02 — Proyecto

- CUBIERTO: `phase6_model.actions` + `object_scope` o `phase5_gate_result`.
- PARCIAL: Actions pero sin ubicación confirmada.
- NO_CUBIERTO: Sin actions.

### ART45-03 — Alternativas

- CUBIERTO: `metadata.alternatives_analysis` presente.
- PARCIAL: `alternativa_cero=True` o `justificacion_solucion` presente.
- NO_CUBIERTO: Sin datos.

### ART45-04 — Efectos directos/indirectos

- CUBIERTO: `phase6_model.impacts` no vacío.
- PARCIAL: Hay actions + receptor_factors pero no impacts.
- NO_CUBIERTO: Sin modelo de impactos.

### ART45-05 — Acumulativos/sinérgicos

- CUBIERTO: `cumulative_result` con markdown o grupos detectados.
- PARCIAL: Hay impacts pero sin C.5 generada.
- NO_CUBIERTO: Sin impacts.

### ART45-06 — Factores ambientales

- CUBIERTO: 16 receptor_factors o phase5_gate con 16 factores.
- PARCIAL: Algunos factores.
- NO_CUBIERTO: Sin factores.

### ART45-07 — Medidas

- CUBIERTO: `phase6_model.measures` no vacío.
- PARCIAL: Impacts pero sin medidas.
- NO_CUBIERTO: Sin impacts ni medidas.

### ART45-08 — PVA

- CUBIERTO: pva_programs + pva_coverage_result válido.
- PARCIAL: pva_programs con cobertura con warnings o sin verificar.
- NO_CUBIERTO: Sin PVA.

### ART45-09 — Vulnerabilidad/riesgos

- CUBIERTO: FR-016 en impacts.
- PARCIAL: FR-016 en receptor_factors sin impacts valorados.
- PARCIAL: Sin información suficiente (documentar o justificar NO_APLICA).

### ART45-10 — Cartografía

- CUBIERTO: `cartography_plan` o mapas PNG en cartografia/.
- PARCIAL: Solo coordenadas en object_scope.
- NO_CUBIERTO: Sin datos.

### ART45-11 — Incertidumbres/gaps

- CUBIERTO: `data_gaps` en impactos o gaps en gate Fase 5.
- PARCIAL: Solo warnings.
- NO_CUBIERTO: Sin gaps documentados.

### ART45-12 — Resumen no técnico

- CUBIERTO: `metadata.non_technical_summary` presente.
- PARCIAL: Material base suficiente (actions + impacts + measures + PVA).
- NO_CUBIERTO: Sin material base.

---

## Relación con módulos anteriores

| Módulo | Qué aporta a AU-01 |
|--------|-------------------|
| IM-02 | Actions → ART45-02 |
| IM-03 | Impacts → ART45-04, ART45-07, ART45-12 |
| IM-05 | Measures → ART45-07 |
| IM-06 | PVA programs → ART45-08 |
| IM-07 | pva_coverage_result → ART45-08 |
| IM-08 | cumulative_result → ART45-05 |
| F5-01 | phase5_gate_result → ART45-06, ART45-11 |

---

## Uso CLI

```bash
# Solo mostrar summary (no escribe archivos)
python run_expediente.py <expediente> audit-art45

# Con escritura de outputs
python run_expediente.py <expediente> audit-art45 --write
```

**Archivos de entrada buscados:**
- `impactos/phase6_model_with_pva.json` (o fallbacks)
- `impactos/cumulative_synergistic_result.json`
- `impactos/pva_coverage_result.json`
- `inventario/phase5_gate_result.json`
- `control_interno/phase2_result.json`
- `control_interno/phase3_result.json`
- `cartografia/cartografia_plan.json`
- `cartografia/*.png`

**Archivos de salida (con --write):**
- `auditoria/art45_checklist_result.json`
- `auditoria/art45_checklist_result.md`

**Exit codes:**
- `0`: `is_structurally_complete() == True` (no hay NO_CUBIERTO ni ERRORs)
- `1`: Hay NO_CUBIERTO, ERRORs, o no se pudo cargar el expediente

---

## Cómo ejecutar los tests

```bash
# Solo AU-01
python -m pytest tests/test_art45_checklist.py -v

# Suite completa
python -m pytest tests/ -q
```

**Cobertura de tests (81 tests):**
- Dataclasses: to_dict, summary, valores
- evaluate_art45_checklist_from_model: 25 casos (todos los requisitos, variantes)
- evaluate_art45_checklist_from_files: 6 casos (expediente vacío, con modelo, path inexistente)
- build_art45_checklist_markdown: 10 casos (secciones, advertencia de alcance)
- write_art45_checklist_outputs: 6 casos
- CLI audit-art45: 6 casos
- Constantes: 5 casos

---

*Módulo generado por EIA-Agent v2.1 — P1 código — 2026-05-14*
