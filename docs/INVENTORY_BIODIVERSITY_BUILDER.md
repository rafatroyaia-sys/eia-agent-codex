# INVENTORY_BIODIVERSITY_BUILDER — IV-10

Constructor de factores FI-007 Flora y FI-008 Fauna desde Fase 2/Fase 4 offline.

**Módulo**: `src/eia_agent/core/inventory_biodiversity_builder.py`  
**ID de productización**: IV-10  
**Completado**: 2026-05-02  
**Dependencias**: IV-00 (`inventory_model`), F4-01 (`phase4_offline_pipeline`), CA-10 (`cartography_plan`), OB-06 (`phase2_pipeline`, opcional)

---

## Qué hace IV-10

- Detecta si la documentación del promotor (Fase 2) contiene menciones a flora, vegetación, hábitats, fauna, aves, reptiles, mamíferos, quirópteros, nidificación o especies protegidas.
- Detecta si el plan cartográfico incluye contexto de Red Natura 2000, ENP o usos del suelo (MAP-004, MAP-005, capas `red_natura_2000`, `espacios_naturales_protegidos`, `usos_suelo`).
- Construye FI-007 y FI-008 con DECLARADO/ROJO_AMARILLO si hay menciones explícitas; ESTIMADO/AMARILLO si hay ubicación; PENDIENTE/NO_CONSTA si no hay información.
- Eleva la criticidad del gap a ALTA cuando hay contexto de Red Natura/ENP o menciones de biodiversidad.
- Genera siempre GAP-FI-007-001 y GAP-FI-008-001 (prospección/consulta pendiente) y añade GAP-007-002 / GAP-008-002 si se detectan menciones explícitas.
- Se integra automáticamente en `inventory-build` (IV-02) sin comando nuevo.

## Qué NO hace IV-10

| Capacidad | Estado |
|-----------|--------|
| Consultar bancos de biodiversidad (GBIF, MITECO, IDE ambiental) | No — sin acceso web |
| Consultar WMS/WMTS de vegetación o fauna | No |
| Verificar presencia de especies protegidas | No |
| Realizar prospección botánica o faunística | No — requiere campo |
| Afirmar ausencia de flora, fauna o hábitats | No — prohibido sin verificación |
| Descartar afecciones a biodiversidad | No |
| Valorar impactos sobre flora o fauna | No — Fase 6 |
| Uso de IA | No |
| Llamadas a APIs externas | No |

---

## API pública

### Funciones de detección y extracción

**`extract_biodiversity_context(phase2_data, phase4_result, cartography_plan) → str`**  
Extrae texto relacionado con biodiversidad de todos los datos disponibles. Devuelve cadena en minúsculas.

**`detect_flora_mentions(text) → list[str]`**  
Detecta: `flora`, `vegetaci*`, `habitat`, `especie vegetal`, `vegetacion natural`, `matorral`, `arbolado`, `palmera`, `especie protegida`, `biodiversidad`.

**`detect_fauna_mentions(text) → list[str]`**  
Detecta: `fauna`, `avifauna`, `aves`, `reptil*`, `mamifer*`, `quiropter*`, `murcielago`, `especie protegida`, `nidificaci*`, `biodiversidad`.

**`has_biodiversity_related_context(phase4_result, cartography_plan) → bool`**  
Devuelve `True` si detecta Red Natura 2000, ENP, MAP-004, MAP-005 o capas de biodiversidad en el plan cartográfico.

---

### `build_flora_factor_from_phase_data(...) → FactorInventory`

**Lógica de evidencia:**

| Condición | evidence_status |
|-----------|-----------------|
| Promotor menciona flora/vegetación/hábitats | DECLARADO |
| Ubicación / contexto ENP/Red Natura / menciones en fase4 | ESTIMADO |
| Sin datos útiles | PENDIENTE |

**Lógica de semáforo:**

| Condición | inventory_semaphore |
|-----------|---------------------|
| PENDIENTE | NO_CONSTA |
| Menciones explícitas a flora/hábitats | ROJO_AMARILLO |
| Ubicación o contexto ENP/usos_suelo | AMARILLO |
| Nunca | VERDE |

**Lógica de field_mode:**

| Condición | field_mode |
|-----------|------------|
| Menciones a hábitats/especie protegida | CAMPO_NECESARIO |
| Ubicación o contexto ENP sin menciones | CAMPO_RECOMENDADO |
| Sin ubicación ni contexto | NO_CONSTA |

**GAP-FI-007-001**: ALTA si Red Natura/ENP o menciones; MEDIA en general. CAMPO si prospección necesaria; GABINETE si solo consulta. Siempre presente.

**GAP-FI-007-002**: ALTA/CAMPO. Solo si hay menciones explícitas de flora/hábitats.

---

### `build_fauna_factor_from_phase_data(...) → FactorInventory`

Misma lógica que FI-007 pero para fauna. Detecta: fauna, aves, reptiles, mamíferos, quirópteros, nidificación, especies protegidas.

**GAP-FI-008-001**: ALTA si Red Natura/ENP o menciones; MEDIA en general. Siempre presente.

**GAP-FI-008-002**: ALTA/CAMPO. Solo si hay menciones faunísticas explícitas.

---

### `build_biodiversity_inventory_factors_from_phase_data(...) → BiodiversityInventoryBuildResult`

Construye FI-007 y FI-008 y los devuelve como `BiodiversityInventoryBuildResult` con `factors`, `warnings` y `notes`.

---

### `merge_biodiversity_factors_into_summary(summary, biodiversity_factors) → InventorySummary`

Sustituye FI-007 y FI-008 en el summary sin mutar el original. Preserva orden canónico.

---

## Integración con IV-02

Bloque añadido en `build_inventory_from_phase4_data()` tras IV-09:

```python
bio_result = build_biodiversity_inventory_factors_from_phase_data(
    phase2_data=phase2_data,
    phase4_result=phase4_result,
    cartography_plan=effective_cart,
)
summary = merge_biodiversity_factors_into_summary(summary, bio_result.factors)
summary.warnings.extend(bio_result.warnings)
summary.notes.extend(bio_result.notes)
```

Cadena completa: IV-03 → IV-04 → IV-05 → IV-06 → IV-07 → IV-08 → IV-09 → **IV-10** → return.

---

## Por qué FI-007 y FI-008 no se marcan VERDE en modo offline

- **FI-007**: La caracterización de vegetación y hábitats requiere prospección botánica de campo y consulta a los inventarios de hábitats de interés comunitario (Directiva 92/43/CEE) y a la cartografía de vegetación autonómica.
- **FI-008**: La caracterización faunística requiere prospección específica (aves, reptiles, mamíferos, quirópteros) y consulta al Catálogo Español de Especies Amenazadas y catalogos autonómicos.
- En ningún caso puede concluirse la ausencia de especies protegidas, nidificaciones o hábitats relevantes sin verificación sobre el terreno o consulta a fuentes oficiales de biodiversidad.

---

## Gaps que quedan abiertos

| Gap | Factor | Criticidad | Resolución | Condición |
|-----|--------|------------|------------|-----------|
| GAP-FI-007-001 | FI-007 | ALTA (con Red Natura/menciones) o MEDIA | CAMPO o GABINETE | Siempre |
| GAP-FI-007-002 | FI-007 | ALTA | CAMPO | Solo con menciones |
| GAP-FI-008-001 | FI-008 | ALTA (con Red Natura/menciones) o MEDIA | CAMPO o GABINETE | Siempre |
| GAP-FI-008-002 | FI-008 | ALTA | CAMPO | Solo con menciones |

---

## Reglas de prudencia aplicadas

- No se afirma "no hay flora", "sin vegetación", "sin hábitats", "sin especies protegidas", "sin afección a flora".
- No se afirma "no hay fauna", "sin fauna", "sin aves", "sin nidificación", "sin afección a fauna".
- No se descarta afección a biodiversidad sin prospección/fuente oficial.
- No se usan términos de valoración: COMPATIBLE, MODERADO, SEVERO, CRÍTICO.
- `ready_for_impact_assessment` = `False` siempre.
- `inventory_semaphore` nunca `VERDE`.

---

## Tests

**Archivo**: `tests/test_inventory_biodiversity_builder.py`  
**Tests**: 155 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestAuxiliaries` | 27 | `extract_biodiversity_context`, `detect_flora_mentions`, `detect_fauna_mentions`, `has_biodiversity_related_context`: detección de flora/fauna/hábitat/Red Natura/MAP-004/MAP-005, sin crash con None |
| `TestBuildFI007Basic` | 13 | ESTIMADO con ubicación sin menciones: AMARILLO, CAMPO_RECOMENDADO, GAP-001 MEDIA, sin GAP-002, ready=False |
| `TestBuildFI007WithMention` | 9 | DECLARADO con flora en promotor: ROJO_AMARILLO, CAMPO_NECESARIO, GAP-002 ALTA/CAMPO |
| `TestBuildFI007RedNatura` | 5 | GAP-001 ALTA con Red Natura, MEDIA solo con ubicación, plan embebido usado |
| `TestBuildFI007NoData` | 8 | PENDIENTE/NO_CONSTA sin datos, solo GAP-001, sin data_sources |
| `TestBuildFI008Basic` | 11 | Misma lógica que FI-007 para fauna |
| `TestBuildFI008WithMention` | 8 | DECLARADO con avifauna/nidificación: ROJO_AMARILLO, GAP-002 ALTA/CAMPO |
| `TestBuildFI008RedNatura` | 4 | GAP-001 ALTA con Red Natura, ROJO_AMARILLO con nidificación |
| `TestBuildFI008NoData` | 6 | PENDIENTE/NO_CONSTA sin datos |
| `TestBiodiversityBuildResult` | 11 | `BiodiversityInventoryBuildResult`: to_dict, JSON serializable, summary(), IV-10 en notes |
| `TestBuildCombined` | 5 | 2 factores, warnings, notas Red Natura, plan embebido, orden FI-007/FI-008 |
| `TestMerge` | 10 | Reemplaza sin duplicados, 16 factores, orden canónico, no muta original |
| `TestIntegrationWithIV02` | 20 | FI-007/FI-008 enriquecidos, ROJO_AMARILLO con menciones, GAP ALTA con Red Natura, IV-10 en notes, 16 factores, JSON serializable |
| `TestPrudenceLexical` | 12 | Ausencia de 15 patrones prohibidos, ready=False, semáforo nunca VERDE |

---

*Generado por EIA-Agent v2.1 — IV-10 — 2026-05-02*
