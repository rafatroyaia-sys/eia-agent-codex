# CONESA_ATTRIBUTE_ASSIGNER — IM-04

Asignador prudente de atributos Conesa para impactos identificados en Fase 6.

**Módulo**: `src/eia_agent/core/conesa_attribute_assigner.py`  
**ID de productización**: IM-04  
**Completado**: 2026-05-06  
**Dependencias**: IM-00 (`impact_model`), IM-01 (`conesa_engine`), IM-03 (`impact_identifier`)

---

## Qué hace IM-04

Asigna los 10 atributos Conesa (IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc) a los
impactos identificados por IM-03, usando tablas tipológicas para proyectos R12/R13
en Canarias. Opcionalmente aplica la valoración Conesa (IM-01) tras la asignación.

1. **`ConesaAssignmentRule`** — Regla tipológica: `matches(impact, action_lookup)` decide si aplica.
2. **`ConesaAssignmentResult`** — Resultado con modelo actualizado, conteos y trazabilidad.
3. **`default_conesa_assignment_rules()`** — 10 reglas canónicas (CASSIGN-A a CASSIGN-J).
4. **`assign_conesa_attributes_to_impact(impact, rules, action_lookup, score)`** — Asignación a un impacto.
5. **`assign_conesa_attributes_to_model(model, rules, score)`** — Asignación a todo el modelo.

## Qué NO hace IM-04

| Capacidad | Estado |
|-----------|--------|
| Crear impactos | No — IM-03 |
| Valorar sin atributos completos | No — deja INDETERMINADO |
| Generar medidas correctoras | No — IM-05 |
| Generar fichas PVA | No — IM-06 |
| Asignar atributos subjetivos sin tabla tipológica | No |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Escribir archivos desde el módulo | No — responsabilidad de la CLI o el llamador |

---

## Principio de prudencia gabinete

En modo gabinete (sin prospección de campo), los receptores que requieren
inventario biológico o consulta a inventarios específicos reciben **todos los
atributos a None** (INDETERMINADO). No se asigna ningún valor numérico sin
evidencia de campo.

| Receptor | Regla | Resultado |
|----------|-------|-----------|
| FR-007 Flora | CASSIGN-F | INDETERMINADO |
| FR-008 Fauna | CASSIGN-F | INDETERMINADO |
| FR-009 ENP | CASSIGN-E | INDETERMINADO |
| FR-010 Red Natura 2000 | CASSIGN-E | INDETERMINADO |
| FR-011 Paisaje | CASSIGN-I | INDETERMINADO |
| FR-012 Patrimonio cultural | CASSIGN-G | INDETERMINADO |
| FR-015 Cambio climático | CASSIGN-H | INDETERMINADO (RV, SI, Mc son None) |

---

## Reglas por defecto (CASSIGN-A a CASSIGN-J)

| Regla | Receptor(es) | Tipos de acción | Naturaleza | Completo | I típico | Significancia |
|-------|-------------|-----------------|-----------|----------|----------|---------------|
| CASSIGN-A | FR-014 (Ruido) | OPERACION, TRANSPORTE, AUXILIAR | cualquiera | ✅ | 33 | MODERADO |
| CASSIGN-B | FR-006 (Calidad del aire) | OPERACION, TRANSPORTE, AUXILIAR | cualquiera | ✅ | 31 | MODERADO |
| CASSIGN-C | FR-003 (Suelos) | cualquiera | cualquiera | ✅ | 29 | MODERADO |
| CASSIGN-D | FR-004 (Hidrología) | cualquiera | cualquiera | ✅ | 23 | COMPATIBLE |
| CASSIGN-E | FR-009, FR-010 (ENP + RN2000) | cualquiera | cualquiera | ❌ | — | INDETERMINADO |
| CASSIGN-F | FR-007, FR-008 (Flora + Fauna) | cualquiera | cualquiera | ❌ | — | INDETERMINADO |
| CASSIGN-G | FR-012 (Patrimonio) | cualquiera | cualquiera | ❌ | — | INDETERMINADO |
| CASSIGN-H | FR-015 (Cambio climático) | OPERACION, TRANSPORTE, AUXILIAR | cualquiera | ❌ (parcial) | — | INDETERMINADO |
| CASSIGN-I | FR-011 (Paisaje) | cualquiera | cualquiera | ❌ | — | INDETERMINADO |
| CASSIGN-J | FR-013 (Socioeconomía) | cualquiera | **POSITIVO** | ✅ | 33 | MODERADO |

**Receptores cubiertos**: FR-003/004/006/007/008/009/010/011/012/013/014/015  
**No cubiertos** (no generados por IM-03): FR-001 (Clima), FR-002 (Geología), FR-005 (Inundabilidad), FR-016 (Riesgos naturales)

### Valores tipológicos de las reglas completas (R12/R13)

Fórmula: `I = 3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc`

| Regla | IN | EX | MO | PE | RV | SI | AC | EF | PR | Mc | I |
|-------|----|----|----|----|----|----|----|----|----|----|---|
| CASSIGN-A (Ruido) | 2 | 2 | 4 | 2 | 2 | 1 | 4 | 4 | 4 | 2 | **33** |
| CASSIGN-B (Aire) | 2 | 1 | 4 | 2 | 2 | 1 | 4 | 4 | 4 | 2 | **31** |
| CASSIGN-C (Suelos) | 2 | 1 | 2 | 4 | 4 | 1 | 1 | 4 | 1 | 4 | **29** |
| CASSIGN-D (Hidrología) | 2 | 1 | 2 | 2 | 2 | 1 | 1 | 4 | 1 | 2 | **23** |
| CASSIGN-J (Socioeconomía +) | 2 | 2 | 4 | 4 | 4 | 1 | 1 | 1 | 4 | 4 | **33** |

---

## Lógica de `matches(impact, action_lookup)`

```python
def matches(self, impact, action_lookup=None) -> bool:
    # 1. Receptor objetivo (obligatorio)
    if impact.receptor_id not in self.target_receptor_ids:
        return False
    # 2. Naturaleza del impacto (si la regla filtra)
    if self.target_natures and impact.nature not in self.target_natures:
        return False
    # 3. Tipo de acción (solo si action_lookup disponible Y regla filtra)
    if self.action_types and action_lookup is not None:
        action = action_lookup.get(impact.action_id)
        if action is None or action.action_type not in self.action_types:
            return False
    return True
```

**Sin action_lookup**: si la regla filtra por tipo de acción pero no se proporciona
lookup, la comprobación se omite y la regla puede coincidir por receptor+naturaleza.
`assign_conesa_attributes_to_model` siempre construye el lookup desde `model.actions`.

---

## Comportamiento de no sobreescritura

Si un impacto ya tiene los **10 atributos completos** antes de llamar a IM-04,
la regla no se aplica. El impacto se cuenta como `skipped`.

Con `score=True`, los impactos ya completos se re-valoran igualmente (actualiza
`significance_without_measures`).

---

## Contadores del resultado

| Contador | Descripción |
|----------|-------------|
| `assigned_count` | Impactos a los que se aplicó una regla (scored + indeterminate) |
| `scored_count` | De los asignados: 10 atributos completos, significancia calculada |
| `indeterminate_count` | De los asignados: atributos incompletos, INDETERMINADO |
| `skipped_count` | Ya tenían atributos completos (no sobreescritos) |
| `no_rule_count` | Sin regla CASSIGN aplicable |

Invariante: `assigned_count = scored_count + indeterminate_count`  
Invariante: `total_impacts = assigned_count + skipped_count + no_rule_count`

---

## API pública

### `ConesaAssignmentRule`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `rule_id` | `str` | Identificador único (ej. "CASSIGN-A") |
| `target_receptor_ids` | `list[str]` | Receptores objetivo (ej. ["FR-014"]) |
| `conesa_attributes` | `ConesaAttributes` | Atributos a asignar; None = INDETERMINADO |
| `action_types` | `list[str]` | Tipos de acción que activan la regla; `[]` = cualquiera |
| `target_natures` | `list[str]` | Naturalezas de impacto; `[]` = cualquiera |
| `notes` | `list[str]` | Notas metodológicas |

Métodos: `matches(impact, action_lookup=None) -> bool`, `to_dict() -> dict`.

### `ConesaAssignmentResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `model` | `Phase6Model` | Modelo actualizado |
| `assigned_count` | `int` | Impactos con regla aplicada |
| `scored_count` | `int` | Con significancia calculada |
| `indeterminate_count` | `int` | Con significancia INDETERMINADO |
| `skipped_count` | `int` | Ya tenían atributos completos |
| `no_rule_count` | `int` | Sin regla aplicable |
| `warnings` | `list[str]` | Avisos |
| `notes` | `list[str]` | Notas de trazabilidad |

Métodos: `to_dict()`, `summary()` (ASCII-safe).

### `assign_conesa_attributes_to_impact(impact, rules=None, action_lookup=None, score=True)`

```python
assign_conesa_attributes_to_impact(
    impact: EnvironmentalImpact,
    rules: list[ConesaAssignmentRule] | None = None,
    action_lookup: dict[str, ProjectAction] | None = None,
    score: bool = True,
) -> EnvironmentalImpact
```

Función pura sin efectos secundarios. Primera regla coincidente gana.

### `assign_conesa_attributes_to_model(model, rules=None, score=True)`

```python
assign_conesa_attributes_to_model(
    model: Phase6Model,
    rules: list[ConesaAssignmentRule] | None = None,
    score: bool = True,
) -> ConesaAssignmentResult
```

Construye internamente el action_lookup desde `model.actions`. No muta el modelo original.

---

## CLI

```bash
# Solo lectura (no escribe nada)
python run_expediente.py <expediente> phase6-assign-conesa

# Escribe phase6_model_with_conesa.json y conesa_assignment_result.json
python run_expediente.py <expediente> phase6-assign-conesa --write

# Asigna atributos sin aplicar la valoración Conesa
python run_expediente.py <expediente> phase6-assign-conesa --write --no-score
```

**Comportamiento**:
- Lee `impactos/phase6_model_with_impacts.json` (output de IM-03).
- Si no existe: aviso y exit 0 (no es un error — puede que IM-03 no se haya ejecutado aún).
- Sin `--write`: imprime resumen de asignación, exit 0.
- Con `--write`: escribe los dos JSONs en `impactos/`, crea el directorio si no existe.
- Con `--no-score`: asigna atributos pero no calcula la significancia Conesa.

---

## Relación con IM-00, IM-01, IM-03

```
IM-03 (impact_identifier)
    │   identify_impacts_from_model()
    ▼
Phase6Model.impacts [status=PENDIENTE_DATOS/INDETERMINADO, significance=NO_VALORADO,
                     conesa_attributes=ConesaAttributes(all None)]
    │
    ▼
IM-04 (conesa_attribute_assigner)
    │   assign_conesa_attributes_to_model(model, score=True)
    │     → llama internamente a IM-01: apply_conesa_to_impact(with_measures=False)
    ▼
Phase6Model.impacts [conesa_attributes asignados por CASSIGN-A…J]
    │   status=VALORADO (si atributos completos)
    │   significance_without_measures=COMPATIBLE/MODERADO/SEVERO/CRITICO (si completo)
    │   significance_without_measures=NO_VALORADO (si INDETERMINADO)
    │
    ├── IM-05 (medidas correctoras) → siguiente paso
    └── IM-06 (fichas PVA) → después de IM-05
```

---

## Cómo ejecutar los tests

```bash
# Solo IM-04
venv\Scripts\python -m unittest tests.test_conesa_attribute_assigner

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_conesa_attribute_assigner.py`  
**Tests**: 86 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestConesaAssignmentRule` | 13 | matches() con receptor/naturaleza/acción/lookup/sin-lookup, defaults, to_dict() |
| `TestDefaultConesaAssignmentRules` | 18 | Count=10, IDs únicos, prefijo CASSIGN-, cobertura de receptores, INDETERMINADO E/F/G/I, completos A/B/C/D/J, parcial H, action_types, notas |
| `TestConesaAssignmentResult` | 7 | to_dict() con claves, serializable JSON, summary() ASCII-safe, counts, warnings |
| `TestAssignConesaAttributesToImpact` | 14 | FR-014→CASSIGN-A, FR-006→CASSIGN-B, FR-009→INDETERMINADO, FR-013+POSITIVO→CASSIGN-J, FR-013+NEGATIVO→sin regla, no_rule, ya-completo, score=True/False, no mutación, reglas personalizadas |
| `TestAssignConesaAttributesToModel` | 12 | Tipo resultado, conteos correctos, conserva total impactos, no mutación, acciones/receptores conservados, score=True/False, modelo vacío, no_rule_count, skipped_count, JSON serializable |
| `TestCLIPhase6AssignConesa` | 7 | Sin --write no crea archivos, con --write crea 2 JSONs, JSON válido, sin model→exit 0, --no-score, crea impactos/ dir, conesa_result con counts |
| `TestMethodologicalRules` | 15 | No compensación POSITIVO/NEGATIVO, ENP/RN/Flora/Fauna/Paisaje/Patrimonio INDETERMINADO, CASSIGN-H parcial, sin frases de ausencia, scores canónicos A(33)/B(31)/C(29)/D(23)/J(33), IDs A-J presentes |

---

## Decisión de ID canónico

Al implementar IM-04, el backlog tenía:
- IM-04: Medidas correctoras (sin código)
- IM-05: Fichas PVA (sin código)
- IM-06: PVA Compatible genérico (sin código, P2)
- IM-07: Validador cobertura PVA (sin código)

El "Asignador prudente de atributos Conesa" es el paso lógico entre identificar
impactos (IM-03) y generar medidas (ex-IM-04). Se insertó como IM-04 y se
reasignaron los IDs existentes sin código implementado:
IM-04→IM-05, IM-05→IM-06, IM-06→IM-07, IM-07→IM-08.

---

*Generado por EIA-Agent v2.1 — IM-04 — 2026-05-06*
