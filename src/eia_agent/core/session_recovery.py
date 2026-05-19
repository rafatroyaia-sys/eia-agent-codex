"""
session_recovery -- NL-07
Diagnóstico y recuperación de sesiones interrumpidas o inconsistentes.

Lee el expediente SIN modificarlo (salvo crear control_interno/recovery_report.json).
No ejecuta fases ni repara contenido técnico.

Uso:
    from eia_agent.core.session_recovery import SessionRecovery

    sr = SessionRecovery("expediente-EIA-2026-RECIMETAL-NAVE-222")
    report = sr.analyze()
    print(report.summary())
    if not report.can_continue:
        print("Acción recomendada:", report.suggested_action)
    sr.write_recovery_report(report)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.orchestrator_log import EventType, OrchestratorLog
from eia_agent.core.gate_checker import GateChecker


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_STATE_FILENAME  = "orchestrator_state.json"
_LOG_FILENAME    = "orchestrator_log.json"
_RECOVERY_FILE   = "recovery_report.json"
_CONTROL_DIR     = "control_interno"
_PHASES_ORDERED  = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

# Acciones canónicas que puede devolver suggest_next_action
ACTION_INICIAR_FASE_1                    = "INICIAR_FASE_1"
ACTION_CONTINUAR_SIGUIENTE_FASE          = "CONTINUAR_SIGUIENTE_FASE"
ACTION_REVISAR_FASE_EN_PROGRESO          = "REVISAR_FASE_EN_PROGRESO"
ACTION_RESOLVER_BLOQUEO                  = "RESOLVER_BLOQUEO"
ACTION_REVISAR_LOG_CORRUPTO              = "REVISAR_LOG_CORRUPTO"
ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE = "RECREAR_ESTADO_DESDE_LOG_MANUALMENTE"
ACTION_NO_CONTINUAR                      = "NO_CONTINUAR"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RecoveryIssue:
    """Incidencia detectada durante el análisis de recuperación."""
    severity: str                        # ERROR / WARNING / INFO
    code: str
    message: str
    phase: Optional[str] = None
    recommendation: Optional[str] = None

    def __str__(self) -> str:
        phase_str = f" [fase {self.phase}]" if self.phase else ""
        return f"[{self.severity}] {self.code}{phase_str}: {self.message}"


@dataclass
class RecoveryReport:
    """Resultado del análisis de recuperación de sesión."""
    expediente_path: Path
    can_continue: bool
    suggested_action: str
    issues: list[RecoveryIssue] = field(default_factory=list)
    last_phase: Optional[str] = None
    interrupted_phase: Optional[str] = None

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def is_clean(self) -> bool:
        """True si no hay errores ni avisos (solo INFO o ninguna incidencia)."""
        return self.error_count() == 0 and self.warning_count() == 0

    def summary(self) -> str:
        status = "PUEDE CONTINUAR" if self.can_continue else "NO PUEDE CONTINUAR"
        return (
            f"{status} | acción: {self.suggested_action} | "
            f"{self.error_count()} errores, {self.warning_count()} avisos"
        )


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class SessionRecovery:
    """Diagnóstico de sesiones interrumpidas o inconsistentes.

    NO ejecuta fases, NO modifica el estado del expediente (salvo
    write_recovery_report, que solo crea recovery_report.json).

    test_mode afecta a GateChecker si se invoca para checks auxiliares.
    El análisis de estado/log es el mismo en ambos modos.
    """

    def __init__(
        self,
        expediente_path: "str | Path",
        test_mode: bool = True,
    ) -> None:
        self.expediente_path = Path(expediente_path).resolve()
        self.test_mode       = test_mode
        self._state_path     = self.expediente_path / _CONTROL_DIR / _STATE_FILENAME
        self._log_path       = self.expediente_path / _CONTROL_DIR / _LOG_FILENAME

    # -----------------------------------------------------------------------
    # Análisis principal
    # -----------------------------------------------------------------------

    def analyze(self) -> RecoveryReport:
        """Analiza el estado del expediente y devuelve un RecoveryReport.

        Lee orchestrator_state.json y orchestrator_log.json sin modificarlos.
        Detecta: sesión inexistente, IN_PROGRESS, BLOCKED, log corrupto,
        errores bloqueantes, discrepancias estado/log.
        """
        issues: list[RecoveryIssue] = []
        state: Optional[dict] = None
        log: Optional[OrchestratorLog] = None

        state_exists = self._state_path.exists()
        log_exists   = self._log_path.exists()

        # ---- Cargar log ----
        if log_exists:
            log = OrchestratorLog(self.expediente_path)
            if log.load_error:
                issues.append(RecoveryIssue(
                    severity="ERROR",
                    code="LOG_CORRUPTED",
                    message=log.load_error,
                    recommendation=ACTION_REVISAR_LOG_CORRUPTO,
                ))
        else:
            if not state_exists:
                issues.append(RecoveryIssue(
                    severity="INFO",
                    code="NO_STATE_NO_LOG",
                    message=(
                        "No existe orchestrator_state.json ni orchestrator_log.json. "
                        "El expediente no ha sido iniciado con el orquestador."
                    ),
                    recommendation=ACTION_INICIAR_FASE_1,
                ))
            else:
                issues.append(RecoveryIssue(
                    severity="WARNING",
                    code="LOG_MISSING",
                    message=(
                        "Existe orchestrator_state.json pero no hay "
                        "orchestrator_log.json. El log se perdió o nunca se creó."
                    ),
                    recommendation=ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE,
                ))

        # ---- Cargar estado ----
        if state_exists:
            state = self._load_state_raw(issues)
        else:
            if log_exists and (log is None or not log.load_error):
                issues.append(RecoveryIssue(
                    severity="WARNING",
                    code="STATE_MISSING_LOG_EXISTS",
                    message=(
                        "Existe orchestrator_log.json pero no hay "
                        "orchestrator_state.json. El estado se perdió."
                    ),
                    recommendation=ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE,
                ))

        # ---- Errores bloqueantes en log ----
        if log is not None and not log.load_error and log.has_blocking_errors():
            issues.append(RecoveryIssue(
                severity="ERROR",
                code="LOG_BLOCKING_ERROR",
                message="El log contiene eventos con status ERROR o BLOCKED.",
                recommendation=ACTION_NO_CONTINUAR,
            ))

        # ---- Fases problemáticas en el estado ----
        in_progress_phase: Optional[str] = None
        blocked_phase: Optional[str]     = None
        if state is not None:
            in_progress_phase, blocked_phase = self._check_phase_states(
                state, issues
            )

        # ---- Discrepancias estado/log ----
        if state is not None and log is not None and not log.load_error:
            issues.extend(self._check_discrepancies(state, log))

        # ---- Valores derivados ----
        last_phase       = self._compute_last_phase(state)
        interrupted_ph   = in_progress_phase
        if interrupted_ph is None and log is not None and not log.load_error:
            interrupted_ph = self._find_interrupted_in_log(log)

        can_continue    = not any(i.severity == "ERROR" for i in issues)
        suggested_action = self._determine_action(issues, last_phase, can_continue)

        return RecoveryReport(
            expediente_path=self.expediente_path,
            can_continue=can_continue,
            suggested_action=suggested_action,
            issues=issues,
            last_phase=last_phase,
            interrupted_phase=interrupted_ph,
        )

    # -----------------------------------------------------------------------
    # Métodos públicos auxiliares
    # -----------------------------------------------------------------------

    def suggest_next_action(self, report: RecoveryReport) -> str:
        """Deriva la acción recomendada desde un RecoveryReport ya calculado."""
        return self._determine_action(
            report.issues, report.last_phase, report.can_continue
        )

    def last_completed_phase(self) -> Optional[str]:
        """Devuelve la última fase COMPLETED según el estado, o None."""
        state = self._read_state_silent()
        return self._compute_last_phase(state)

    def interrupted_phase(self) -> Optional[str]:
        """Devuelve la fase que quedó IN_PROGRESS, o None."""
        state = self._read_state_silent()
        if state is not None:
            phases_data = state.get("phases", {})
            for ph in _PHASES_ORDERED:
                if phases_data.get(ph, {}).get("status") == "IN_PROGRESS":
                    return ph
        if self._log_path.exists():
            log = OrchestratorLog(self.expediente_path)
            if not log.load_error:
                return self._find_interrupted_in_log(log)
        return None

    def write_recovery_report(self, report: RecoveryReport) -> Path:
        """Escribe control_interno/recovery_report.json y devuelve su ruta.

        No modifica orchestrator_state.json ni orchestrator_log.json.
        """
        ci_dir = self.expediente_path / _CONTROL_DIR
        ci_dir.mkdir(parents=True, exist_ok=True)
        out_path = ci_dir / _RECOVERY_FILE

        payload = {
            "expediente_path":   str(report.expediente_path),
            "can_continue":      report.can_continue,
            "suggested_action":  report.suggested_action,
            "last_phase":        report.last_phase,
            "interrupted_phase": report.interrupted_phase,
            "error_count":       report.error_count(),
            "warning_count":     report.warning_count(),
            "is_clean":          report.is_clean(),
            "issues": [
                {
                    "severity":       i.severity,
                    "code":           i.code,
                    "message":        i.message,
                    "phase":          i.phase,
                    "recommendation": i.recommendation,
                }
                for i in report.issues
            ],
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return out_path

    # -----------------------------------------------------------------------
    # Helpers privados
    # -----------------------------------------------------------------------

    def _load_state_raw(self, issues: list[RecoveryIssue]) -> Optional[dict]:
        """Lee orchestrator_state.json en crudo; añade ERROR a issues si falla."""
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            issues.append(RecoveryIssue(
                severity="ERROR",
                code="STATE_CORRUPTED",
                message=f"orchestrator_state.json no se puede parsear: {exc}",
                recommendation=ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE,
            ))
            return None

    def _read_state_silent(self) -> Optional[dict]:
        """Lee orchestrator_state.json sin efectos secundarios."""
        if not self._state_path.exists():
            return None
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _check_phase_states(
        self,
        state: dict,
        issues: list[RecoveryIssue],
    ) -> "tuple[Optional[str], Optional[str]]":
        """Detecta fases IN_PROGRESS y BLOCKED. Añade issues; devuelve (ip, bp)."""
        in_progress = None
        blocked     = None
        phases_data = state.get("phases", {})
        for ph in _PHASES_ORDERED:
            ps     = phases_data.get(ph, {})
            status = ps.get("status", "NOT_STARTED")
            if status == "IN_PROGRESS":
                in_progress = ph
                issues.append(RecoveryIssue(
                    severity="ERROR",
                    code="PHASE_IN_PROGRESS",
                    message=(
                        f"La fase {ph} quedó en estado IN_PROGRESS. "
                        "La sesión se interrumpió antes de completarla."
                    ),
                    phase=ph,
                    recommendation=ACTION_REVISAR_FASE_EN_PROGRESO,
                ))
            elif status == "BLOCKED":
                blocked = ph
                reason = ps.get("blocked_reason") or "(sin razón registrada)"
                issues.append(RecoveryIssue(
                    severity="ERROR",
                    code="PHASE_BLOCKED",
                    message=f"La fase {ph} está BLOCKED: {reason}",
                    phase=ph,
                    recommendation=ACTION_RESOLVER_BLOQUEO,
                ))
        return in_progress, blocked

    def _check_discrepancies(
        self,
        state: dict,
        log: OrchestratorLog,
    ) -> list[RecoveryIssue]:
        """Detecta discrepancias entre orchestrator_state y el log de eventos."""
        issues: list[RecoveryIssue] = []
        phases_data = state.get("phases", {})

        completed_in_log: set[str] = {
            ev.phase
            for ev in log.events_by_type(EventType.PHASE_COMPLETED)
            if ev.phase
        }
        started_in_log: set[str] = {
            ev.phase
            for ev in log.events_by_type(EventType.PHASE_STARTED)
            if ev.phase
        }
        closed_in_log: set[str] = completed_in_log | {
            ev.phase
            for ev in log.events_by_type(EventType.PHASE_BLOCKED)
            if ev.phase
        }

        for ph in _PHASES_ORDERED:
            ps_status = phases_data.get(ph, {}).get("status", "NOT_STARTED")

            # Estado COMPLETED pero log sin PHASE_COMPLETED
            if ps_status == "COMPLETED" and ph not in completed_in_log:
                issues.append(RecoveryIssue(
                    severity="WARNING",
                    code="STATE_LOG_DISCREPANCY",
                    message=(
                        f"El estado dice fase {ph} COMPLETED pero el log no contiene "
                        f"evento PHASE_COMPLETED para esa fase."
                    ),
                    phase=ph,
                    recommendation="VERIFICAR_MANUALMENTE",
                ))

            # Log con PHASE_STARTED sin cierre, y estado no lo refleja
            if (
                ph in started_in_log
                and ph not in closed_in_log
                and ps_status not in ("IN_PROGRESS", "BLOCKED")
            ):
                issues.append(RecoveryIssue(
                    severity="WARNING",
                    code="LOG_STARTED_NOT_CLOSED",
                    message=(
                        f"El log tiene PHASE_STARTED para fase {ph} sin evento de cierre, "
                        f"pero el estado no la marca como IN_PROGRESS ni BLOCKED."
                    ),
                    phase=ph,
                    recommendation="VERIFICAR_MANUALMENTE",
                ))

        return issues

    def _compute_last_phase(self, state: Optional[dict]) -> Optional[str]:
        """Devuelve la última fase en estado COMPLETED, o None."""
        if state is None:
            return None
        phases_data = state.get("phases", {})
        last = None
        for ph in _PHASES_ORDERED:
            if phases_data.get(ph, {}).get("status") == "COMPLETED":
                last = ph
        return last

    def _find_interrupted_in_log(self, log: OrchestratorLog) -> Optional[str]:
        """Busca en el log fases con PHASE_STARTED pero sin cierre (COMPLETED o BLOCKED)."""
        started: set[str] = set()
        closed:  set[str] = set()
        for ev in log.all_events():
            if ev.phase is None:
                continue
            if ev.event_type == EventType.PHASE_STARTED:
                started.add(ev.phase)
            elif ev.event_type in (EventType.PHASE_COMPLETED, EventType.PHASE_BLOCKED):
                closed.add(ev.phase)
        interrupted = started - closed
        for ph in reversed(_PHASES_ORDERED):
            if ph in interrupted:
                return ph
        return None

    def _determine_action(
        self,
        issues: list[RecoveryIssue],
        last_phase: Optional[str],
        can_continue: bool,
    ) -> str:
        """Selecciona la acción recomendada según las incidencias detectadas."""
        codes = {i.code for i in issues}

        if "LOG_CORRUPTED" in codes:
            return ACTION_REVISAR_LOG_CORRUPTO
        if "STATE_CORRUPTED" in codes:
            return ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE
        if "STATE_MISSING_LOG_EXISTS" in codes:
            return ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE
        if "PHASE_BLOCKED" in codes:
            return ACTION_RESOLVER_BLOQUEO
        if "PHASE_IN_PROGRESS" in codes:
            return ACTION_REVISAR_FASE_EN_PROGRESO
        if "LOG_BLOCKING_ERROR" in codes:
            return ACTION_NO_CONTINUAR
        if "NO_STATE_NO_LOG" in codes:
            return ACTION_INICIAR_FASE_1
        if not can_continue:
            return ACTION_NO_CONTINUAR
        if last_phase is None:
            return ACTION_INICIAR_FASE_1
        return ACTION_CONTINUAR_SIGUIENTE_FASE
