# INVENTORY_HERITAGE_BUILDER — IV-09

Constructor de factor FI-012 Patrimonio cultural desde Fase 2/Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_heritage_builder.py`  
**ID de productización**: IV-09  
**Completado**: 2026-05-01  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), OB-06 (`phase2_pipeline`, opcional), CA-10 (`cartography_plan`, opcional)

---

## Qué hace IV-09

- Detecta si la documentación del promotor (Fase 2) contiene menciones a patrimonio, BIC, yacimientos arqueológicos, IGPC, catálogos o bienes históricos/etnográficos.
- Construye FI-012 con DECLARADO/ROJO_AMARILLO si el promotor ha declarado información patrimonial concreta; ESTIMADO/AMARILLO si hay ubicación sin menciones; PENDIENTE/NO_CONSTA si no hay información mínima.
- Genera siempre GAP-FI-012-001 (consulta oficial al órgano patrimonial competente — ALTA) y añade GAP-FI-012-002 si se detectan menciones explícitas.
- Deja visibles los gaps de consulta oficial al inventario patrimonial autonómico/municipal.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-09

| Capacidad | Estado |
|-----------|--------|
| Consultar inventario patrimonial autonómico (IGPC, IAPH, etc.) | No — sin acceso web |
| Consultar catálogo municipal o PGOU | No — sin acceso web |
| Verificar BIC o yacimientos registrados | No — sin acceso a bases de datos |
| Descartar afección patrimonial | No — prohibido sin consulta oficial |
| Afirmar ausencia de patrimonio | No — regla de prudencia estricta |
| Valoración de impactos sobre patrimonio | No — Fase 6 |
| Uso de IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### Funciones de detección y extracción

**`extract_heritage_context(phase2_data, phase4_result, cartography_plan) → str`**  
Extrae texto relacionado con patrimonio cultural de todos los datos disponibles. Recorre dicts y listas de forma segura. Devuelve cadena en minúsculas.

Términos buscados: `patrimonio`, `arqueolog*`, `yacimiento`, `bien de inter*`, `bic`, `catalog*`, `inventario patrimonial`, `proteccion cultural`, `historic*`, `etnografi*`, `igpc`, `pgou`, `planeamiento`, `rupestre`, `resto arqueolog*`, `zona arqueolog*`.

**`detect_heritage_mentions(text) → list[str]`**  
Detecta términos patrimoniales en texto. Sin duplicados, en orden de aparición. No interpreta más allá de presencia textual.

---

### `build_heritage_factor_from_phase_data(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status |
|-----------|-----------------|
| Promotor declara información patrimonial concreta | DECLARADO |
| Hay ubicación/coordenadas o menciones en datos de Fase 4/cartografía | ESTIMADO |
| Sin información mínima | PENDIENTE |

**Lógica de semáforo:**

| Condición | inventory_semaphore |
|-----------|---------------------|
| PENDIENTE | NO_CONSTA |
| Menciones patrimoniales explícitas detectadas | ROJO_AMARILLO |
| Ubicación disponible sin menciones patrimoniales | AMARILLO |
| Nunca | VERDE |

**Lógica de field_mode:**

| Condición | field_mode |
|-----------|------------|
| Hay ubicación/coordenadas | CAMPO_RECOMENDADO |
| Sin ubicación | NO_CONSTA |

**Gap GAP-FI-012-001**: consulta oficial al inventario/órgano patrimonial. ALTA / GABINETE. **Siempre presente.**

**Gap GAP-FI-012-002**: aclaración de menciones patrimoniales detectadas. ALTA / GABINETE. Solo si hay menciones.

**ready_for_impact_assessment**: `False` siempre. **Semáforo**: nunca VERDE.

---

### `build_heritage_inventory_factor_from_phase4(...) → HeritageInventoryBuildResult`

Construye FI-012 y lo devuelve como `HeritageInventoryBuildResult`. Genera warnings si PENDIENTE o si hay menciones patrimoniales sin resolver.

---

### `merge_heritage_factor_into_summary(summary, factor) → InventorySummary`

Sustituye FI-012 en el summary sin mutar el original. Preserva orden canónico.

---

## Integración con IV-02

Bloque añadido en `build_inventory_from_phase4_data()` tras IV-08:

```python
heritage_result = build_heritage_inventory_factor_from_phase4(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
    cartography_plan=effective_cart,
)
summary = merge_heritage_factor_into_summary(summary, heritage_result.factor)
summary.warnings.extend(heritage_result.warnings)
summary.notes.extend(heritage_result.notes)
```

Con cualquier ubicación disponible, FI-012 se enriquece automáticamente a ESTIMADO/AMARILLO.

---

## Por qué FI-012 no se marca VERDE en modo offline

- La caracterización del patrimonio cultural requiere consulta al inventario patrimonial autonómico (IGPC en Canarias, IAPH en Andalucía, etc.) y al catálogo municipal del instrumento de planeamiento vigente.
- No es posible descartar la existencia de bienes de interés cultural, yacimientos arqueológicos o bienes etnográficos sin consulta oficial.
- La presencia de menciones patrimoniales en la documentación del promotor genera un gap de ALTA criticidad que impide cerrar el semáforo.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-012-001 | FI-012 | ALTA | GABINETE | Siempre |
| GAP-FI-012-002 | FI-012 | ALTA | GABINETE | Si hay menciones patrimoniales detectadas |

---

## Reglas de prudencia aplicadas

- No se afirma "no hay patrimonio", "sin yacimientos" ni "sin afección patrimonial".
- No se descarta afección patrimonial sin consulta al órgano competente.
- No se usan términos de valoración de impacto: COMPATIBLE, MODERADO, SEVERO, CRÍTICO.
- `ready_for_impact_assessment` = `False` siempre.
- `inventory_semaphore` nunca `VERDE`.

---

## Tests

**Archivo**: `tests/test_inventory_heritage_builder.py`  
**Tests**: 119 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestAuxiliaries` | 20 | `extract_heritage_context`, `detect_heritage_mentions`: detección de patrimonio/yacimiento/BIC/IGPC/arqueolog/historic/etnografi, sin crash con None, sin falsos positivos |
| `TestBuildFI012Basic` | 17 | ESTIMADO con ubicación sin menciones: AMARILLO, CAMPO_RECOMENDADO, GAP-FI-012-001 ALTA/GABINETE, sin GAP-002, ready=False |
| `TestBuildFI012WithMention` | 11 | DECLARADO con menciones en promotor: ROJO_AMARILLO, GAP-FI-012-002 ALTA/GABINETE, ready=False |
| `TestBuildFI012WithBIC` | 5 | DECLARADO con BIC explícito: ROJO_AMARILLO, 2 gaps |
| `TestBuildFI012CartographyMention` | 5 | ROJO_AMARILLO si mapa patrimonial en plan, AMARILLO con plan básico, plan embebido en phase4 |
| `TestBuildFI012NoData` | 9 | PENDIENTE/NO_CONSTA sin datos, solo GAP-001, sin data_sources |
| `TestHeritageInventoryBuildResult` | 11 | `HeritageInventoryBuildResult`: to_dict, JSON serializable, summary(), IV-09 en notes |
| `TestBuildWrapper` | 5 | Warning si PENDIENTE, warning con menciones, IV-09 en notes, plan embebido |
| `TestMerge` | 9 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 17 | FI-012 enriquecido, ROJO_AMARILLO con menciones, 2 gaps con menciones, IV-09 en notes, 16 factores, orden canónico, JSON serializable |
| `TestPrudenceLexical` | 10 | Ausencia de 15 patrones prohibidos, ready=False, semáforo nunca VERDE |

---

*Generado por EIA-Agent v2.1 — IV-09 — 2026-05-01*
