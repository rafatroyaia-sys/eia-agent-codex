# IMPACT_IDENTIFIER — IM-03

Identificador preliminar de impactos acción × receptor desde Fase 6.

**Módulo**: `src/eia_agent/core/impact_identifier.py`  
**ID de productización**: IM-03  
**Completado**: 2026-05-05  
**Dependencias**: IM-00 (`impact_model`), IM-02 (`project_action_builder`)

---

## Qué hace IM-03

Aplica un conjunto de reglas deterministas sobre los pares (acción, receptor) del
`Phase6Model` para generar una lista de `EnvironmentalImpact` preliminares.

1. **`ImpactIdentificationRule`** — Regla de identificación: `matches(action, receptor)` decide si aplica.
2. **`ImpactIdentificationResult`** — Resultado con impactos, avisos y notas de trazabilidad.
3. **`default_impact_identification_rules()`** — 10 reglas canónicas (RULE-A a RULE-J).
4. **`build_minimal_receptor_factors()`** — 16 ReceptorFactor con valores por defecto (sin inventario).
5. **`identify_impacts_from_model(model, rules)`** — Identificador principal. Devuelve `ImpactIdentificationResult`.
6. **`merge_identified_impacts_into_model(model, impacts)`** — Sustituye impactos sin mutar el original.
7. **`build_phase6_model_with_identified_impacts(model, rules)`** — Combina los dos anteriores.

## Qué NO hace IM-03

| Capacidad | Estado |
|-----------|--------|
| Valorar impactos con Conesa | No — IM-01 |
| Asignar significancia | No — siempre `NO_VALORADO` |
| Generar medidas correctoras | No — IM-04 |
| Generar fichas PVA | No — IM-05 |
| Redactar bloques del Documento Ambiental | No — Fase 7 |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Escribir archivos desde el módulo | No — responsabilidad de la CLI o el llamador |

---

## Reglas por defecto (RULE-A a RULE-J)

| Regla | Acción(es) | Keywords | Receptor(es) | Nature | Status |
|-------|-----------|----------|--------------|--------|--------|
| RULE-A | ALMACENAMIENTO | — | FR-003, FR-004 | NEGATIVO | PENDIENTE_DATOS |
| RULE-B | OPERACION | tratamiento, trituraci, cizalla, molino, prensa, compactaci, cribado, mecanico | FR-006, FR-014 | NEGATIVO | PENDIENTE_DATOS |
| RULE-C | TRANSPORTE | — | FR-006, FR-014, FR-015 | NEGATIVO | PENDIENTE_DATOS |
| RULE-D | OPERACION | clasificaci, separaci, selecci, triaje | FR-003 | NEGATIVO | PENDIENTE_DATOS |
| RULE-E | OPERACION, ALMACENAMIENTO, TRANSPORTE | — | FR-009, FR-010 | NEGATIVO | **INDETERMINADO** |
| RULE-F | *cualquier tipo* | — | FR-007, FR-008 | NEGATIVO | **INDETERMINADO** |
| RULE-G | MANTENIMIENTO | — | FR-003, FR-004 | NEGATIVO | PENDIENTE_DATOS |
| RULE-H | OPERACION, AUXILIAR | — | FR-011 | NEGATIVO | PENDIENTE_DATOS |
| RULE-I | CESE | — | FR-003, FR-012 | NEGATIVO | PENDIENTE_DATOS |
| RULE-J | ALMACENAMIENTO, OPERACION | — | FR-013 | **POSITIVO** | PENDIENTE_DATOS |

**Receptores cubiertos**: FR-003/004/006/007/008/009/010/011/012/013/014/015  
**No cubiertos**: FR-001 (Clima), FR-002 (Geología), FR-005 (Inundabilidad), FR-016 (Riesgos naturales)

### Regla de no compensación (RULE-J)

RULE-J genera un impacto `POSITIVO` sobre FR-013 (Socioeconomía). Este impacto
**no compensa** los negativos. Cada impacto se registra y evalúa de forma independiente.
La nota explícita en `RULE-J.notes` recuerda esta regla metodológica.

---

## Lógica de `matches(action, receptor)`

```python
def matches(self, action, receptor) -> bool:
    # 1. Tipo de acción (lista vacía = cualquier tipo)
    if self.action_types and action.action_type not in self.action_types:
        return False
    # 2. Receptor objetivo
    if receptor.receptor_id not in self.target_receptor_ids:
        return False
    # 3. Keywords en texto normalizado (lista vacía = sin filtro)
    if self.operation_keywords:
        text = _normalize(action.name + " " + action.description)
        if not any(kw in text for kw in self.operation_keywords):
            return False
    return True
```

La normalización usa `unicodedata.normalize("NFKD") + encode("ascii","ignore").lower()`,
igual que en IM-02, para detectar "trituración" → "trituraci" sin variantes acentuadas.

---

## Estado de los impactos generados

| Campo | Valor fijo |
|-------|-----------|
| `significance_without_measures` | `NO_VALORADO` |
| `significance_with_measures` | `NO_VALORADO` |
| `measure_ids` | `[]` (vacío) |
| `pva_ids` | `[]` (vacío) |
| `conesa_attributes` | todos `None` |
| `status` | `PENDIENTE_DATOS` o `INDETERMINADO` |

**Elevación a INDETERMINADO**: si la regla define `status="PENDIENTE_DATOS"` pero el
receptor tiene `critical_gaps` no vacíos, el status se eleva a `INDETERMINADO`.

---

## Asignación de IDs IMP-NNN

Los IDs son correlativos comenzando en `IMP-001`, en el orden de iteración:
`actions × receptor_factors × rules`.

No se generan duplicados por la clave `(action_id, receptor_id, rule_id)`.

---

## API pública

### `ImpactIdentificationRule`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `rule_id` | `str` | Identificador único (ej. "RULE-A") |
| `action_types` | `list[str]` | Tipos de acción que disparan la regla; `[]` = cualquier tipo |
| `operation_keywords` | `list[str]` | Keywords normalizados en nombre+descripción de la acción; `[]` = sin filtro |
| `target_receptor_ids` | `list[str]` | Receptores objetivo (ej. ["FR-003", "FR-004"]) |
| `impact_name_template` | `str` | Template con `{action_name}` y `{receptor_name}` |
| `nature` | `str` | `"NEGATIVO"` (default) o `"POSITIVO"` |
| `status` | `str` | `"PENDIENTE_DATOS"` (default) o `"INDETERMINADO"` |
| `default_gaps` | `list[str]` | GAPs que se copian al `EnvironmentalImpact.data_gaps` |
| `notes` | `list[str]` | Notas metodológicas de la regla |

Métodos: `matches(action, receptor) -> bool`, `to_dict() -> dict`.

### `ImpactIdentificationResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `impacts` | `list[EnvironmentalImpact]` | Impactos identificados |
| `warnings` | `list[str]` | Avisos (sin acciones, sin receptores, sin impactos) |
| `notes` | `list[str]` | Notas de trazabilidad |

Métodos: `to_dict()`, `summary()` (ASCII-safe).

### `identify_impacts_from_model(model, rules=None)`

```python
identify_impacts_from_model(
    model: Phase6Model,
    rules: list[ImpactIdentificationRule] | None = None,
) -> ImpactIdentificationResult
```

Función pura sin efectos secundarios. Si `rules=None` usa las 10 reglas por defecto.

### `merge_identified_impacts_into_model(model, impacts)`

```python
merge_identified_impacts_into_model(
    model: Phase6Model,
    impacts: list[EnvironmentalImpact],
) -> Phase6Model
```

Devuelve nueva instancia de `Phase6Model` (no muta el original).
Conserva `actions`, `receptor_factors`, `measures`, `pva_programs`.

### `build_phase6_model_with_identified_impacts(model, rules=None)`

```python
build_phase6_model_with_identified_impacts(
    model: Phase6Model,
    rules: list[ImpactIdentificationRule] | None = None,
) -> Phase6Model
```

Combina `identify_impacts_from_model` + `merge_identified_impacts_into_model`.

### `build_minimal_receptor_factors()`

```python
build_minimal_receptor_factors() -> list[ReceptorFactor]
```

Crea los 16 ReceptorFactor (FR-001…FR-016) con `ready_from_inventory=False` y
`inventory_semaphore="NO_CONSTA"`. Sin critical_gaps. Útil para tests y CLI sin inventario.

---

## CLI

```bash
# Solo lectura (no escribe nada)
python run_expediente.py <expediente> phase6-identify-impacts

# Escribe impact_identification_result.json y phase6_model_with_impacts.json
python run_expediente.py <expediente> phase6-identify-impacts --write
```

**Comportamiento**:
- Lee `impactos/phase6_model_base.json` (output de IM-02). Si no existe, intenta reconstruir desde `control_interno/phase2_result.json`.
- Si el modelo no tiene `receptor_factors`, usa los 16 por defecto con aviso.
- Sin `--write`: imprime resumen de impactos, exit 0.
- Con `--write`: escribe los dos JSONs en `impactos/`, crea el directorio si no existe.

---

## Relación con IM-00, IM-01, IM-02 y Fase 5

```
Fase 2 (phase2_result.json)
    │
    ▼
IM-02 (project_action_builder)
    │   build_phase6_model_with_actions()
    ▼
Phase6Model.actions
    │
    ▼
IM-03 (impact_identifier)
    │   identify_impacts_from_model(model, rules)
    ▼
Phase6Model.impacts [status=PENDIENTE_DATOS/INDETERMINADO, significance=NO_VALORADO]
    │
    ├── IM-01 (conesa_engine) → score_phase6_impacts()  [siguiente paso]
    ├── IM-04 (medidas) [futuro]
    └── IM-05 (PVA) [futuro]

Fase 5 (InventorySummary) → receptor_factors con critical_gaps
    │   → eleva status PENDIENTE_DATOS → INDETERMINADO si hay gaps
    ▼
Phase6Model.receptor_factors
```

---

## Cómo ejecutar los tests

```bash
# Solo IM-03
venv\Scripts\python -m unittest tests.test_impact_identifier

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_impact_identifier.py`  
**Tests**: 96 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestImpactIdentificationRule` | 13 | matches() con tipo/receptor/keywords/acentos/vacíos, defaults, to_dict() |
| `TestDefaultImpactIdentificationRules` | 15 | Count=10, IDs únicos, receptores cubiertos, RULE-A/B/C/E/F/J targets, INDETERMINADO, POSITIVO, prudencia, no compensación, gaps |
| `TestImpactIdentificationResult` | 6 | to_dict(), summary() ASCII-safe, count, warnings |
| `TestBuildMinimalReceptorFactors` | 6 | 16 factores, todos FR-NNN presentes, FI mapping correcto, ready=False |
| `TestIdentifyImpactsFromModel` | 22 | Sin acciones/receptores→warning, ALMACENAMIENTO→FR-003/004, mecánico→FR-006/014, transporte→FR-015, clasificación→FR-003, ENP/Natura→INDETERMINADO, flora/fauna→INDETERMINADO, mantenimiento, auxiliar, cese, POSITIVO socioeconomía, sin duplicados, IDs consecutivos, NO_VALORADO, critical_gaps→INDETERMINADO, notas, data_gaps, source_refs |
| `TestMergeIdentifiedImpactsIntoModel` | 7 | Sustituye impacts, preserva actions/receptors/measures/pva, no muta original, lista vacía |
| `TestBuildPhase6ModelWithIdentifiedImpacts` | 7 | Phase6Model, impacts>0, expediente_id, measures/pva vacíos, no mutación, reglas personalizadas |
| `TestCLIPhase6IdentifyImpacts` | 7 | Sin --write no crea archivos, con --write crea 2 JSONs, JSON válido, sin model_base→exit 0, crea impactos/ dir |
| `TestMethodologicalRules` | 13 | Sin palabras de significancia en descripciones, POSITIVO→NO_VALORADO, status válido, nature válida, RULE-J no compensación, source_refs, IMP-NNN, RULE-F gabinete, RULE-E cartografía, sin Conesa, sin measure_ids/pva_ids |

---

## Decisión de ID canónico

Al implementar IM-03, el backlog canónico tenía:
- IM-02: Constructor de acciones ✅ (recién completado)
- IM-03: Constructor medidas correctoras (sin código)
- IM-04: Fichas PVA (sin código)
- IM-05: PVA Compatible genérico (sin código)
- IM-06: Validador cobertura PVA (sin código)

El "Identificador preliminar de impactos" es el paso lógico siguiente tras construir las
acciones (IM-02) y antes de valorarlas con Conesa (IM-01) o generar medidas (ex-IM-03).
Se insertó como IM-03 y se reasignaron los IDs existentes sin código implementado:
IM-03→IM-04, IM-04→IM-05, IM-05→IM-06, IM-06→IM-07.

---

*Generado por EIA-Agent v2.1 — IM-03 — 2026-05-05*
