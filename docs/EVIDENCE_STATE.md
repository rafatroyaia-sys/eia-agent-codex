# EvidenceState — referencia técnica

Módulo: `src/eia_agent/core/evidence_state.py`  
Ítem canónico: **NL-05**

---

## Qué es

`EvidenceState` es el enum Python que representa los estados de evidencia del sistema EIA-Agent.
Todo dato del expediente lleva uno de estos estados. Están definidos en la Regla de Evidencia
del CLAUDE.md:

> _"Todo dato del documento final lleva uno de estos estados: CONFIRMADO, DECLARADO, INFERIDO,
> ESTIMADO, PENDIENTE, DESCARTADO."_

El enum amplía esa lista base con variantes de detalle necesarias para la trazabilidad técnica.

---

## Estados disponibles

| Estado | Rango | ¿Apto doc. admin.? | ¿Requiere cualificador? |
|---|---|---|---|
| `CONFIRMADO_CAMPO` | 100 | Si | No |
| `CONFIRMADO_GABINETE` | 90 | Si | No |
| `CONFIRMADO` | 80 | Si | No |
| `DECLARADO` | 60 | No | Si |
| `INFERIDO_TECNICO` | 50 | No | Si |
| `INFERIDO` | 40 | No | Si |
| `ESTIMADO` | 40 | No | Si |
| `LIMITADO_ESCALA` | 30 | No | Si |
| `PROVISIONAL` | 30 | No | Si |
| `ASUNCION_TEST` | 25 | **Nunca** | Si |
| `PENDIENTE_VERIFICACION` | 20 | No | Si |
| `PENDIENTE` | 10 | No | Si |
| `NO_CONSTA` | 10 | No | Si |
| `DESCARTADO` | 5 | No | No |
| `ERROR` | 0 | No | No |

`DESCARTADO` se mantiene por compatibilidad con `tools/validate_expediente.py`.

---

## Métodos

### `is_confirmed() -> bool`
`True` para `CONFIRMADO_CAMPO`, `CONFIRMADO_GABINETE`, `CONFIRMADO`.

### `is_test_assumption() -> bool`
`True` solo para `ASUNCION_TEST`.

### `is_pending() -> bool`
`True` para `PENDIENTE_VERIFICACION`, `PENDIENTE`, `NO_CONSTA`.

### `requires_qualifier() -> bool`
`True` cuando el estado obliga a incluir un cualificador en redacción técnica (todos los no confirmados excepto `DESCARTADO` y `ERROR`).

### `can_support_final_admin_document() -> bool`
`True` solo para los tres estados confirmados. Cualquier otro estado bloquea la aptitud administrativa.

### `qualifier_label() -> str`
Etiqueta de texto para insertar en redacción. Ejemplo: `DECLARADO` → `"declarado por el promotor"`.

### `confidence_rank() -> int`
Entero 0-100. Permite comparar estados: mayor rango = mayor certeza probatoria.

### `is_valid_transition(old, new, allow_downgrade=False) -> bool`
Valida cambios de estado.

Regla especial: **`ASUNCION_TEST` → cualquier estado confirmado está siempre bloqueado**,
incluso con `allow_downgrade=True`. Una asunción de test nunca puede convertirse en
dato probado: requiere un dato real independiente.

### `from_string(value: str) -> EvidenceState`
Constructor alternativo con normalización (minúsculas, espacios → `_`, guiones → `_`)
y alias históricos. Lanza `ValueError` con el nombre del estado desconocido en el mensaje.

---

## Alias aceptados en `from_string`

| Alias | Estado resultante |
|---|---|
| `CONF` | `CONFIRMADO` |
| `CONF_CAMPO` | `CONFIRMADO_CAMPO` |
| `CONF_GAB` | `CONFIRMADO_GABINETE` |
| `DECL` | `DECLARADO` |
| `AT` | `ASUNCION_TEST` |
| `INF` | `INFERIDO` |
| `INF_TEC` | `INFERIDO_TECNICO` |
| `LIM` | `LIMITADO_ESCALA` |
| `EST` | `ESTIMADO` |
| `PROV` | `PROVISIONAL` |
| `PV` | `PENDIENTE_VERIFICACION` |
| `PEND` | `PENDIENTE` |
| `NC` | `NO_CONSTA` |
| `DESC` | `DESCARTADO` |

---

## Regla AT — bloqueo permanente

`ASUNCION_TEST` activa `impide_aptitud_administrativa: true` en el expediente.
El estado nunca puede transicionar a ningún estado confirmado:

```python
EvidenceState.is_valid_transition(
    EvidenceState.ASUNCION_TEST,
    EvidenceState.CONFIRMADO,           # False
    allow_downgrade=True,               # no importa -- sigue siendo False
)
```

Para resolver un AT se necesita un dato real que lo sustituya desde cero.
Ver `especificacion_asunciones_test.md` para el proceso completo.

---

## Uso básico

```python
from eia_agent.core.evidence_state import EvidenceState

estado = EvidenceState.from_string("DECLARADO")

if estado.requires_qualifier():
    print(f"[{estado.qualifier_label()}]")

if not estado.can_support_final_admin_document():
    print("AVISO: este dato no es apto para el documento administrativo final")

# Validar una transicion
ok = EvidenceState.is_valid_transition(
    EvidenceState.DECLARADO,
    EvidenceState.CONFIRMADO_GABINETE,
)
# ok == True
```

---

## Tests

```
venv/Scripts/python -m unittest discover -s tests
```

58 tests, 8 clases (`TestFromString`, `TestIsConfirmed`, `TestIsPending`,
`TestIsTestAssumption`, `TestRequiresQualifier`, `TestCanSupportFinalAdminDocument`,
`TestConfidenceRank`, `TestIsValidTransition`).
