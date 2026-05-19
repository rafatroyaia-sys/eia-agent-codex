# Orchestrator Log — referencia tecnica

Item canonico: **NL-06**  
Modulo: `src/eia_agent/core/orchestrator_log.py`

---

## Que es

El log estructurado de orquestador es el registro persistente en JSON de todos los
eventos de ejecucion del sistema EIA-Agent: fases iniciadas, gates evaluados,
validaciones ejecutadas, archivos generados, errores y notas manuales.

Se escribe en `control_interno/orchestrator_log.json` dentro del expediente.

---

## Diferencia con `log_orquestador.md`

| | `log_orquestador.md` | `orchestrator_log.json` (NL-06) |
|---|---|---|
| Formato | Markdown legible por humanos | JSON estructurado legible por maquinas |
| Origen | Redactado manualmente o por LLM | Escrito por codigo Python |
| Consumidor | Revisor humano, auditoría | NL-03 orquestador, NL-04 gates, AU-04 informe |
| Filtrado | No posible programaticamente | Por fase, tipo, status |
| Deteccion de bloqueos | Visual | `has_blocking_errors()` |

Ambos coexisten. NL-06 no reemplaza ni modifica `log_orquestador.md`.

---

## Por que JSON

- Permite al orquestador NL-03 consultar si una fase anterior se completó sin errores
- Permite al gate-checker NL-04 verificar que los campos requeridos fueron registrados
- Permite filtrado por fase, tipo de evento o status sin parsear markdown
- Facilita la generacion del informe de auditoria AU-04

---

## Estructura de un evento

```json
{
  "event_id": "EV-0003",
  "timestamp": "2026-04-20T10:15:22Z",
  "expediente_id": "expediente-EIA-2026-RECIMETAL-NAVE-222",
  "event_type": "GATE_PASSED",
  "status": "OK",
  "message": "Gate 2 superado: objeto evaluado cerrado",
  "phase": "Fase 2",
  "agent": "AG-04",
  "details": {
    "campos_verificados": ["coordenadas", "referencia_catastral", "operaciones"],
    "asunciones_activas": ["AT-001", "AT-002"]
  },
  "files": ["control_interno/ficha_objeto_evaluado.md"]
}
```

### Campos

| Campo | Tipo | Descripcion |
|---|---|---|
| `event_id` | `str` | ID correlativo `EV-NNNN` |
| `timestamp` | `str` | ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`) |
| `expediente_id` | `str` | Nombre del directorio del expediente |
| `event_type` | `str` | Tipo del evento (ver tabla abajo) |
| `status` | `str` | OK / WARNING / ERROR / BLOCKED / INFO |
| `message` | `str` | Descripcion legible del evento |
| `phase` | `str\|null` | Fase del expediente (opcional) |
| `agent` | `str\|null` | Agente que genera el evento (opcional) |
| `details` | `dict` | Datos adicionales especificos del evento |
| `files` | `list[str]` | Archivos generados o afectados |

### Tipos de evento

| Constante | Significado |
|---|---|
| `PHASE_STARTED` | Inicio de una fase del expediente |
| `PHASE_COMPLETED` | Fase completada con exito |
| `PHASE_BLOCKED` | Fase bloqueada por gaps o errores |
| `GATE_PASSED` | Gate de fase superado |
| `GATE_FAILED` | Gate de fase no superado |
| `VALIDATION_PASSED` | Validacion de schemas OK |
| `VALIDATION_FAILED` | Validacion de schemas con errores |
| `FILE_GENERATED` | Archivo generado por un agente |
| `WARNING_RECORDED` | Aviso no bloqueante registrado |
| `ERROR_RECORDED` | Error registrado |
| `MANUAL_NOTE` | Nota manual del operador |

---

## Uso desde Python

```python
from pathlib import Path
from eia_agent.core.orchestrator_log import OrchestratorLog, EventType, EventStatus

expediente = Path("expediente-EIA-2026-RECIMETAL-NAVE-222")
log = OrchestratorLog(expediente)

# Registrar inicio de fase
log.record_event(
    event_type=EventType.PHASE_STARTED,
    status=EventStatus.OK,
    message="Iniciando Fase 2 -- cierre del objeto evaluado",
    phase="Fase 2",
    agent="AG-04",
)

# Registrar gate fallido
log.record_event(
    event_type=EventType.GATE_FAILED,
    status=EventStatus.BLOCKED,
    message="Gate 2 bloqueado: GAP-001 critico sin resolver",
    phase="Fase 2",
    details={"gaps_bloqueantes": ["GAP-001", "GAP-003"]},
)

# Consultar estado
if log.has_blocking_errors():
    print("El expediente tiene bloqueos activos")

# Ver eventos de una fase
for ev in log.events_by_phase("Fase 2"):
    print(ev.event_id, ev.status, ev.message)

# Resumen textual
print(log.summary())
```

---

## Como lo usara NL-03

El orquestador `EIAOrchestrator` (NL-03) usara `OrchestratorLog` para:

1. Registrar el inicio y fin de cada fase con `record_event()`
2. Antes de ejecutar la fase N, leer el log y verificar que la fase N-1 se completó
   con `events_by_phase("Fase N-1")` y sin eventos `PHASE_BLOCKED`
3. Registrar el resultado de cada gate con `GATE_PASSED` o `GATE_FAILED`
4. Consultar `has_blocking_errors()` para decidir si puede avanzar

El log actua como **checkpoint persistente**: si la sesion se interrumpe,
el orquestador puede leer el log y retomar desde la fase correcta (NL-07).

---

## Como ejecutar los tests

```bash
# Solo NL-06
venv/Scripts/python -m unittest tests.test_orchestrator_log -v

# Suite completa (NL-05 + NL-01 + NL-02 + NL-06)
venv/Scripts/python -m unittest discover -s tests
```

Resultado esperado: `Ran 162 tests in ~1.3s -- OK`

Los tests de NL-06 cubren:
- `now_iso()` formato, tipo y longitud
- `generate_event_id()` primer evento, incremento, maximo y formato invalido
- `OrchestratorEvent` is_blocking, to_dict, from_dict, defaults
- `OrchestratorLog` creacion sin eventos, creacion de `control_interno/` automatica
- Persistencia: archivo JSON valido, UTF-8, ruta correcta
- Eventos: record_event, acumulacion, IDs incrementales, recarga desde disco
- Consultas: events_by_phase, has_blocking_errors, last_event
- summary(): estado, conteo, expediente_id, ultimos eventos
