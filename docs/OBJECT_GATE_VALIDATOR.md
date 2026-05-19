# OBJECT_GATE_VALIDATOR — OB-02

**Módulo**: `src/eia_agent/core/object_gate_validator.py`  
**Tests**: `tests/test_object_gate_validator.py` — 79 tests OK  
**Dependencias**: `object_scope_builder.py` (OB-01)  
**Regla de oro**: Solo valida. No escribe. No resuelve contradicciones. No usa IA.

---

## Propósito

Evalúa si un `ObjectScope` (generado por OB-01) tiene información suficiente
para considerar cerrado el objeto evaluado (Gate 2).

La diferencia respecto a `ObjectScope.estado_gate2` (que es una clasificación
rápida APTO/PENDIENTE/BLOQUEADO basada en presencia de campos) es que
`evaluate_gate_2` aplica un conjunto de reglas más rico: verifica formatos,
detecta valores provisionales, evalúa coherencia entre campos y distingue
entre modo test y producción.

---

## API pública

### `evaluate_gate_2(scope, test_mode=True, context=None) → ObjectGateResult`

```python
from eia_agent.core.object_gate_validator import evaluate_gate_2

result = evaluate_gate_2(scope, test_mode=True)
print(result.summary())
```

**`context`** — dict opcional con claves:

| Clave | Tipo | Descripción |
|-------|------|-------------|
| `rc_verificada` | bool | Si la RC ha sido verificada en Catastro |
| `cont_abiertos` | bool | Si hay contradicciones abiertas sin resolver |
| `uso_catastral` | str | Uso según Catastro (e.g. "almacén agrario") |
| `uso_declarado` | str | Uso declarado por el promotor (e.g. "industrial") |

### `evaluate_gate_2_from_json(path, test_mode=True, context=None) → ObjectGateResult`

Carga `ObjectScope` desde JSON (generado por OB-01) y evalúa. No escribe nada.
Lanza `FileNotFoundError` si el JSON no existe.

### `ObjectGateIssue` — dataclass

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | str | ERROR / WARNING / INFO |
| `code` | str | Código único (OB02-E001, OB02-W001, OB02-I001...) |
| `message` | str | Descripción de la incidencia |
| `field` | str\|None | Campo del ObjectScope afectado |
| `recommendation` | str\|None | Acción recomendada |

### `ObjectGateResult` — dataclass

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente evaluado |
| `passed` | bool | True solo si no hay ningún ERROR |
| `test_mode` | bool | Modo en que se evaluó |
| `issues` | list[ObjectGateIssue] | Lista completa de incidencias |

Métodos: `error_count()`, `warning_count()`, `info_count()`, `is_blocked()`, `summary()`

### Funciones auxiliares

```python
looks_like_referencia_catastral(value: str) -> bool
contains_high_or_critical_gap(text: str) -> bool
```

---

## Reglas de validación del Gate 2

### 1. Titular — `OB02-E001`, `OB02-W001`
- Falta titular → **ERROR** (siempre bloquea).
- Gap de titularidad en `scope.gaps` → **WARNING** en test / **ERROR** en producción.

### 2. Referencia catastral — `OB02-E002`, `OB02-E003`, `OB02-W002`
- Falta RC → **ERROR**.
- Formato inválido (≠ 20 caracteres alfanuméricos) → **ERROR**.
- RC no verificada (`rc_verificada=False`) → **WARNING** en test / **ERROR** en producción.

### 3. Coordenadas — `OB02-E004`, `OB02-W003`
- Sin WGS84 ni UTM → **ERROR**.
- Coordenada contiene PENDIENTE, ESTIMADO, NO_DECLARADO → **WARNING** en test / **ERROR** en producción.

### 4. Operaciones incluidas — `OB02-E005`
- Sin operaciones incluidas → **ERROR**.

### 5. Operaciones excluidas y contradicciones — `OB02-E006`, `OB02-I001`
- `cont_abiertos=True` sin excluidas ni AT activos → **ERROR**.
- Excluidas declaradas → **INFO** (no bloquea).

### 6. Modo de trabajo — `OB02-E007`, `OB02-I002`
- `NO_DECLARADO` → **ERROR**.
- `GABINETE` → **INFO** (aviso de limitación, no bloquea).
- `CAMPO` → sin incidencia.

### 7. Asunciones de test activas — `OB02-W004`, `OB02-E008`
- AT activos en **test_mode=True** → **WARNING** (no bloquea).
- AT activos en **test_mode=False** → **ERROR** (bloquea).

### 8. Gaps de criticidad alta — `OB02-W005`, `OB02-E009`, `OB02-I003`
- Gap con ALTA / CRÍTICA / CRITICA / BLOQUEANTE / CRITICAL → **WARNING** en test / **ERROR** en producción.
- Gap sin términos de criticidad alta → **INFO**.

### 9. Uso catastral vs uso declarado — `OB02-W006`, `OB02-W007`, `OB02-E010`
- Discrepancia sin AT ni CONT/gap documentado → **WARNING** en test / **ERROR** en producción.
- Discrepancia cubierta por AT activo o gap relacionado → **WARNING** (siempre, independiente del modo).

---

## test_mode vs producción

| Condición | test_mode=True | test_mode=False |
|-----------|----------------|-----------------|
| AT activos | WARNING | ERROR |
| Gap ALTA | WARNING | ERROR |
| RC no verificada | WARNING | ERROR |
| Coordenada provisional | WARNING | ERROR |
| Gap de titularidad | WARNING | ERROR |
| Discrepancia uso (sin AT) | WARNING | ERROR |
| Discrepancia uso (con AT) | WARNING | WARNING |

En **test_mode=True**, solo los ERRORs bloquean (`passed=False`). Los WARNINGs
son visibles pero el expediente puede avanzar en entorno de pruebas.

En **test_mode=False**, se aplican todas las condiciones adicionales. Un
expediente con AT activos, gaps altos o datos no verificados no puede avanzar.

---

## Cómo trata ASUNCION_TEST

OB-02 detecta asunciones de test mirando `scope.at_activos`. No interpreta
el contenido de los AT ni valida su estructura — eso corresponde a OB-05 (futuro).

- Si `at_activos` es no vacío en test_mode=True → WARNING.
- Si `at_activos` es no vacío en test_mode=False → ERROR.
- Si AT cubre una discrepancia uso_catastral/uso_declarado → atenúa el issue a WARNING.

---

## Cómo trata gaps ALTA

El texto de cada gap en `scope.gaps` se analiza con `contains_high_or_critical_gap()`.
Si contiene ALTA, CRÍTICA, CRITICA, BLOQUEANTE o CRITICAL (insensible a mayúsculas
y acentos) → el gap es de criticidad alta. El resto → INFO.

---

## Cómo trata uso catastral vs uso declarado

Solo se activa si `context` incluye ambas claves `uso_catastral` y `uso_declarado`
con valores diferentes (comparación insensible a mayúsculas y espacios).

Si hay AT activos o algún gap que mencione "uso", "catastral" o "cont", la
discrepancia se considera documentada → WARNING en lugar de ERROR.

---

## Qué NO hace OB-02

- **No consulta Catastro**: `looks_like_referencia_catastral` solo verifica formato.
- **No resuelve contradicciones**: detecta `cont_abiertos=True` pero no cierra CONTs.
- **No confirma datos**: todos los datos siguen siendo DECLARADO tras la validación.
- **No genera ficha**: no produce markdown ni JSON de salida.
- **No escribe en expedientes**: ni en piloto ni en producción.
- **No crea sistema AT**: la estructura avanzada de AT corresponde a OB-05.

---

## Cómo ejecutar tests

```bash
# Solo OB-02
venv\Scripts\python -m unittest tests.test_object_gate_validator

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

## Relación con otros módulos

```
IN-02 (EntityExtractor)
  ↓
IN-03 (EvidenceClassifier)  →  ClassificationResult
                                    ↓
                          OB-01 (ObjectScopeBuilder)  →  ObjectScope
                                                              ↓
                                                   OB-02 (ObjectGateValidator)  →  ObjectGateResult
```

OB-02 no puede ejecutarse sin un `ObjectScope` previo. El `ObjectScope` puede
provenir de `build_object_scope()` (flujo normal) o de `load_object_scope_json()`
(flujo desde JSON persistido).
