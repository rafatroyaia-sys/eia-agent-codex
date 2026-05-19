# SESSION_RECOVERY — NL-07

## Qué problema resuelve

Un expediente EIA puede quedar en estado inconsistente cuando:

- La sesión se interrumpe (error de contexto LLM, corte de conexión, CTRL+C) con una fase en `IN_PROGRESS`.
- El archivo `orchestrator_state.json` existe pero el `orchestrator_log.json` se perdió o corrompió.
- El log registra un `PHASE_STARTED` sin `PHASE_COMPLETED` correspondiente.
- Una fase quedó `BLOCKED` y nadie la ha desbloqueado antes de volver a trabajar.

Sin un módulo de diagnóstico, reanudar el trabajo a ciegas puede sobreescribir estado válido o ignorar fases incompletas.

`SessionRecovery` lee el expediente, detecta estas situaciones y devuelve una recomendación segura antes de continuar. **No ejecuta fases ni repara contenido técnico.**

## Relación con interrupciones / errores de sesión

| Escenario | Qué detecta SessionRecovery |
|---|---|
| Contexto LLM cortado con fase en marcha | `PHASE_IN_PROGRESS` → `REVISAR_FASE_EN_PROGRESO` |
| Estado borrado accidentalmente | `STATE_MISSING_LOG_EXISTS` → `RECREAR_ESTADO_DESDE_LOG_MANUALMENTE` |
| Log JSON corrompido | `LOG_CORRUPTED` → `REVISAR_LOG_CORRUPTO` |
| Fase bloqueada por gap crítico | `PHASE_BLOCKED` → `RESOLVER_BLOQUEO` |
| Expediente nuevo (nunca iniciado) | `NO_STATE_NO_LOG` → `INICIAR_FASE_1` |
| Log con evento ERROR/BLOCKED genérico | `LOG_BLOCKING_ERROR` → `NO_CONTINUAR` |
| Estado dice COMPLETED pero log sin evento | `STATE_LOG_DISCREPANCY` → WARNING |
| Log con PHASE_STARTED sin cierre | `LOG_STARTED_NOT_CLOSED` → WARNING |

## Qué detecta

- Ausencia de `orchestrator_state.json` y/o `orchestrator_log.json`.
- Fases en estado `IN_PROGRESS` (sesión interrumpida).
- Fases en estado `BLOCKED` con razón registrada.
- Eventos bloqueantes en el log (`EventStatus.ERROR` o `EventStatus.BLOCKED`).
- Log corrupto (JSON inválido) — detectado por `OrchestratorLog.load_error`.
- Estado corrupto (JSON inválido).
- Discrepancia: estado dice `COMPLETED` pero el log no tiene `PHASE_COMPLETED`.
- Discrepancia: log tiene `PHASE_STARTED` sin `PHASE_COMPLETED` ni `PHASE_BLOCKED`.
- Última fase completada (`last_phase`).
- Fase interrumpida (`interrupted_phase`).

## Qué NO hace

- No ejecuta fases ni agentes.
- No modifica `orchestrator_state.json` ni `orchestrator_log.json`.
- No repara automáticamente el estado.
- No comprueba la calidad técnica del contenido del expediente (eso es NL-04 GateChecker y M-12).
- No crea el estado inicial (eso lo hace `EIAOrchestrator.__init__`).

## Uso básico

```python
from eia_agent.core.session_recovery import SessionRecovery

sr = SessionRecovery("expediente-EIA-NAVE-222")
report = sr.analyze()

print(report.summary())
# → PUEDE CONTINUAR | acción: CONTINUAR_SIGUIENTE_FASE | 0 errores, 0 avisos

if not report.can_continue:
    print("Acción:", report.suggested_action)
    for issue in report.issues:
        if issue.severity == "ERROR":
            print(" →", issue)

# Guardar informe en control_interno/recovery_report.json
path = sr.write_recovery_report(report)
```

## Clases principales

### RecoveryIssue

```python
@dataclass
class RecoveryIssue:
    severity: str           # ERROR / WARNING / INFO
    code: str               # ver tabla de códigos
    message: str
    phase: Optional[str]    # fase afectada, si aplica
    recommendation: Optional[str]
```

### RecoveryReport

```python
@dataclass
class RecoveryReport:
    expediente_path: Path
    can_continue: bool
    suggested_action: str
    issues: list[RecoveryIssue]
    last_phase: Optional[str]       # última fase COMPLETED
    interrupted_phase: Optional[str] # fase IN_PROGRESS detectada

    def error_count(self) -> int
    def warning_count(self) -> int
    def is_clean(self) -> bool      # True si sin errores ni avisos
    def summary(self) -> str
```

### SessionRecovery

```python
class SessionRecovery:
    def __init__(self, expediente_path: str | Path, test_mode: bool = True)
    def analyze(self) -> RecoveryReport
    def suggest_next_action(self, report: RecoveryReport) -> str
    def last_completed_phase(self) -> str | None
    def interrupted_phase(self) -> str | None
    def write_recovery_report(self, report: RecoveryReport) -> Path
```

## Códigos de incidencia

| Código | Severidad | Descripción | Acción recomendada |
|---|---|---|---|
| `NO_STATE_NO_LOG` | INFO | Sin estado ni log. Expediente no iniciado. | `INICIAR_FASE_1` |
| `LOG_MISSING` | WARNING | Estado existe pero no hay log. | `RECREAR_ESTADO_DESDE_LOG_MANUALMENTE` |
| `STATE_MISSING_LOG_EXISTS` | WARNING | Log existe pero no hay estado. | `RECREAR_ESTADO_DESDE_LOG_MANUALMENTE` |
| `LOG_CORRUPTED` | ERROR | `orchestrator_log.json` no parseable. | `REVISAR_LOG_CORRUPTO` |
| `STATE_CORRUPTED` | ERROR | `orchestrator_state.json` no parseable. | `RECREAR_ESTADO_DESDE_LOG_MANUALMENTE` |
| `LOG_BLOCKING_ERROR` | ERROR | Evento ERROR o BLOCKED en el log. | `NO_CONTINUAR` |
| `PHASE_IN_PROGRESS` | ERROR | Fase quedó IN_PROGRESS (sesión cortada). | `REVISAR_FASE_EN_PROGRESO` |
| `PHASE_BLOCKED` | ERROR | Fase está BLOCKED con razón registrada. | `RESOLVER_BLOQUEO` |
| `STATE_LOG_DISCREPANCY` | WARNING | Estado COMPLETED sin evento PHASE_COMPLETED en log. | Verificar manualmente |
| `LOG_STARTED_NOT_CLOSED` | WARNING | PHASE_STARTED en log sin cierre. | Verificar manualmente |

## Acciones canónicas

| Acción | Cuándo |
|---|---|
| `INICIAR_FASE_1` | Sin estado ni log, o estado limpio sin fases completadas |
| `CONTINUAR_SIGUIENTE_FASE` | Todo limpio, hay fases completadas |
| `REVISAR_FASE_EN_PROGRESO` | Fase quedó IN_PROGRESS |
| `RESOLVER_BLOQUEO` | Fase en BLOCKED |
| `REVISAR_LOG_CORRUPTO` | Log JSON inválido |
| `RECREAR_ESTADO_DESDE_LOG_MANUALMENTE` | Estado corrupto o desaparecido con log disponible |
| `NO_CONTINUAR` | Error bloqueante genérico en log |

## Estructura del informe (recovery_report.json)

```json
{
  "expediente_path": "/ruta/expediente-EIA-NAVE-222",
  "can_continue": false,
  "suggested_action": "REVISAR_FASE_EN_PROGRESO",
  "last_phase": "3",
  "interrupted_phase": "4",
  "error_count": 1,
  "warning_count": 0,
  "is_clean": false,
  "issues": [
    {
      "severity": "ERROR",
      "code": "PHASE_IN_PROGRESS",
      "message": "La fase 4 quedó en estado IN_PROGRESS. La sesión se interrumpió antes de completarla.",
      "phase": "4",
      "recommendation": "REVISAR_FASE_EN_PROGRESO"
    }
  ]
}
```

El archivo se escribe en `control_interno/recovery_report.json`. No modifica ningún otro archivo del expediente.

## Cómo se usará en CLI-01

CLI-01 invocará `SessionRecovery.analyze()` antes de `EIAOrchestrator.start_phase()`:

```python
# Flujo previsto en CLI-01
sr = SessionRecovery(expediente_path)
report = sr.analyze()

if not report.can_continue:
    print(f"No se puede continuar: {report.suggested_action}")
    sr.write_recovery_report(report)
    sys.exit(1)

orch = EIAOrchestrator(expediente_path)
gate = GateChecker(expediente_path)
gate_result = gate.check_phase(target_phase)

if gate_result.is_blocked():
    print("Gate no superado")
    sys.exit(1)

orch.start_phase(target_phase)
```

## Relación con otros módulos

| Módulo | Relación |
|---|---|
| NL-03 EIAOrchestrator | SessionRecovery lee `orchestrator_state.json` que EIAOrchestrator escribe |
| NL-06 OrchestratorLog | SessionRecovery usa `OrchestratorLog` para leer eventos sin modificarlos |
| NL-04 GateChecker | Complementario: GateChecker valida condiciones de contenido; SessionRecovery valida estado de sesión |
| CLI-01 (futuro) | CLI-01 llamará `analyze()` antes de cada `start_phase()` |

## Ejecutar tests

```bash
# Solo NL-07
venv\Scripts\python -m unittest tests.test_session_recovery

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
