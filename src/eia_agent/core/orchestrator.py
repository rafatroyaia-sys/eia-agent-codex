"""
orchestrator -- NL-03
EIAOrchestrator básico: coordinador de estado de fases de un expediente EIA-Agent v2.1.

No ejecuta agentes reales. No implementa gate-checks avanzados (NL-04).
Gestiona el ciclo NOT_STARTED → IN_PROGRESS → COMPLETED / BLOCKED para
cada una de las 9 fases y registra todos los eventos en OrchestratorLog (NL-06).

Uso:
    from eia_agent.core.orchestrator import EIAOrchestrator

    orch = EIAOrchestrator("expediente-EIA-2026-RECIMETAL-NAVE-222")
    orch.start_phase("1", agent="AG-01")
    orch.complete_phase("1", generated_files=["capas/hechos_confirmados.json"])
    print(orch.summary())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.orchestrator_log import (
    EventStatus,
    EventType,
    OrchestratorLog,
    now_iso,
)
from eia_agent.core.schema_validator import ValidationResult, validate_expediente


# ---------------------------------------------------------------------------
# Fases
# ---------------------------------------------------------------------------

class Phase:
    """Constantes y helpers para las 9 fases del expediente EIA."""

    FASE_1 = "1"
    FASE_2 = "2"
    FASE_3 = "3"
    FASE_4 = "4"
    FASE_5 = "5"
    FASE_6 = "6"
    FASE_7 = "7"
    FASE_8 = "8"
    FASE_9 = "9"

    _ORDERED = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

    _NAMES = {
        "1": "Ingesta documental",
        "2": "Objeto evaluado",
        "3": "Triaje jurídico-normativo",
        "4": "Cartografía y clima",
        "5": "Inventario ambiental",
        "6": "Impactos, medidas y PVA",
        "7": "Redacción bloques A-K",
        "8": "Ensamblaje DOCX",
        "9": "Auditoría M-12",
    }

    @classmethod
    def is_valid(cls, phase: str) -> bool:
        return phase in cls._ORDERED

    @classmethod
    def name_of(cls, phase: str) -> str:
        return cls._NAMES.get(phase, f"Fase {phase}")

    @classmethod
    def previous(cls, phase: str) -> Optional[str]:
        """Devuelve el ID de la fase anterior, o None si es la primera."""
        try:
            idx = cls._ORDERED.index(phase)
        except ValueError:
            return None
        return cls._ORDERED[idx - 1] if idx > 0 else None

    @classmethod
    def next_of(cls, phase: str) -> Optional[str]:
        """Devuelve el ID de la siguiente fase, o None si es la última."""
        try:
            idx = cls._ORDERED.index(phase)
        except ValueError:
            return None
        return cls._ORDERED[idx + 1] if idx < len(cls._ORDERED) - 1 else None


# ---------------------------------------------------------------------------
# Estados de fase
# ---------------------------------------------------------------------------

class PhaseStatusValue:
    """Constantes de estado de una fase."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    BLOCKED     = "BLOCKED"

    _ALL = {NOT_STARTED, IN_PROGRESS, COMPLETED, BLOCKED}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._ALL


# ---------------------------------------------------------------------------
# Excepción propia
# ---------------------------------------------------------------------------

class OrchestratorError(Exception):
    """Error del orquestador EIA-Agent.

    Se lanza en situaciones claras:
    - fase desconocida
    - precondición de fase no satisfecha
    - fase no en el estado requerido para la operación
    - estado persistido corrupto
    """


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PhaseStatus:
    """Estado de una fase individual del expediente."""
    phase: str
    name: str
    status: str                      # PhaseStatusValue
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    blocked_reason: Optional[str] = None
    warnings: list = field(default_factory=list)
    generated_files: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "phase":           self.phase,
            "name":            self.name,
            "status":          self.status,
            "started_at":      self.started_at,
            "completed_at":    self.completed_at,
            "blocked_reason":  self.blocked_reason,
            "warnings":        list(self.warnings),
            "generated_files": list(self.generated_files),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseStatus":
        return cls(
            phase=data.get("phase", ""),
            name=data.get("name", ""),
            status=data.get("status", PhaseStatusValue.NOT_STARTED),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            blocked_reason=data.get("blocked_reason"),
            warnings=data.get("warnings", []),
            generated_files=data.get("generated_files", []),
        )


@dataclass
class OrchestratorState:
    """Estado completo del orquestador serializable a JSON."""
    expediente_id: str
    current_phase: Optional[str]
    phases: dict                     # str → PhaseStatus
    last_updated: str
    test_mode: bool

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "current_phase": self.current_phase,
            "phases":        {k: v.to_dict() for k, v in self.phases.items()},
            "last_updated":  self.last_updated,
            "test_mode":     self.test_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorState":
        phases_raw = data.get("phases", {})
        phases = {k: PhaseStatus.from_dict(v) for k, v in phases_raw.items()}
        return cls(
            expediente_id=data.get("expediente_id", ""),
            current_phase=data.get("current_phase"),
            phases=phases,
            last_updated=data.get("last_updated", ""),
            test_mode=data.get("test_mode", True),
        )


# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

_STATE_FILENAME       = "orchestrator_state.json"
_CONTROL_INTERNO_DIR  = "control_interno"


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------

class EIAOrchestrator:
    """Coordinador de estado de fases del expediente EIA-Agent v2.1.

    Responsabilidades:
    - Mantener y persistir el estado de las 9 fases en orchestrator_state.json.
    - Verificar que la secuencia de fases se respeta antes de iniciar cada una.
    - Registrar todos los eventos en OrchestratorLog (NL-06).
    - Invocar la validación de schemas (NL-02) bajo demanda.

    NO hace:
    - Ejecutar agentes reales de IA.
    - Evaluar gates específicos por campos del expediente (NL-04).
    - Proveer CLI (CLI-01).
    - Modificar prompts ni expedientes cerrados.

    test_mode=True no significa que se ignoren errores estructurales.
    Significa que el expediente está en modo prueba (se registra en el estado).
    """

    def __init__(
        self,
        expediente_path: "str | Path",
        test_mode: bool = True,
    ) -> None:
        self.expediente_path = Path(expediente_path).resolve()
        self.expediente_id   = self.expediente_path.name
        self.test_mode       = test_mode

        self._state_path = (
            self.expediente_path / _CONTROL_INTERNO_DIR / _STATE_FILENAME
        )

        # Crear control_interno/ si no existe
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        # OrchestratorLog (NL-06) — carga automáticamente eventos existentes
        self.log = OrchestratorLog(self.expediente_path)

        # Cargar estado existente o crear uno nuevo
        if self._state_path.exists():
            self.state = self.load_state()
            self.state.test_mode = test_mode  # respetar el parámetro del constructor
        else:
            self.state = self.initialize_state()
            self.save_state()

    # -----------------------------------------------------------------------
    # Gestión de estado
    # -----------------------------------------------------------------------

    def initialize_state(self) -> OrchestratorState:
        """Crea un OrchestratorState nuevo con las 9 fases en NOT_STARTED."""
        phases = {
            ph: PhaseStatus(
                phase=ph,
                name=Phase.name_of(ph),
                status=PhaseStatusValue.NOT_STARTED,
            )
            for ph in Phase._ORDERED
        }
        return OrchestratorState(
            expediente_id=self.expediente_id,
            current_phase=None,
            phases=phases,
            last_updated=now_iso(),
            test_mode=self.test_mode,
        )

    def load_state(self) -> OrchestratorState:
        """Carga el estado desde orchestrator_state.json.

        Raises:
            OrchestratorError: si el archivo no puede parsearse.
        """
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            return OrchestratorState.from_dict(raw)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise OrchestratorError(
                f"Estado del orquestador corrupto en '{self._state_path}': {exc}"
            ) from exc

    def save_state(self) -> None:
        """Persiste el estado actual en orchestrator_state.json (UTF-8, indentado)."""
        self.state.last_updated = now_iso()
        self._state_path.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get_phase_status(self, phase: str) -> PhaseStatus:
        """Devuelve el PhaseStatus de la fase indicada.

        Raises:
            OrchestratorError: si la fase no existe.
        """
        if not Phase.is_valid(phase):
            raise OrchestratorError(f"Fase desconocida: {phase!r}")
        return self.state.phases[phase]

    def previous_phase(self, phase: str) -> Optional[str]:
        """Devuelve el ID de la fase anterior, o None para la fase 1.

        Raises:
            OrchestratorError: si la fase no existe.
        """
        if not Phase.is_valid(phase):
            raise OrchestratorError(f"Fase desconocida: {phase!r}")
        return Phase.previous(phase)

    def can_start_phase(self, phase: str) -> "tuple[bool, str]":
        """Evalúa si una fase puede iniciarse en el estado actual.

        Orden de comprobación:
        1. Fase existe.
        2. Fase no está ya COMPLETED.
        3. Fase no está ya IN_PROGRESS.
        4. Fase no está BLOCKED.
        5. La fase anterior (si la hay) está COMPLETED.
        6. El log no tiene eventos bloqueantes.

        Returns:
            (True, "")          si puede empezar.
            (False, razón_str)  si no puede.
        """
        if not Phase.is_valid(phase):
            return False, f"Fase desconocida: {phase!r}"

        ps = self.state.phases[phase]

        if ps.status == PhaseStatusValue.COMPLETED:
            return False, f"Fase {phase} ya está COMPLETED."

        if ps.status == PhaseStatusValue.IN_PROGRESS:
            return False, f"Fase {phase} ya está IN_PROGRESS."

        if ps.status == PhaseStatusValue.BLOCKED:
            return False, (
                f"Fase {phase} está BLOCKED: "
                f"{ps.blocked_reason or '(sin razón registrada)'}."
            )

        prev = Phase.previous(phase)
        if prev is not None:
            prev_ps = self.state.phases[prev]
            if prev_ps.status != PhaseStatusValue.COMPLETED:
                return (
                    False,
                    f"Fase {phase} requiere que la fase {prev} esté COMPLETED "
                    f"(estado actual: {prev_ps.status}).",
                )

        if self.log.has_blocking_errors():
            return False, "El log del orquestador tiene errores bloqueantes."

        return True, ""

    # -----------------------------------------------------------------------
    # Acciones de fase
    # -----------------------------------------------------------------------

    def start_phase(
        self,
        phase: str,
        agent: Optional[str] = None,
    ) -> PhaseStatus:
        """Marca la fase como IN_PROGRESS, registra PHASE_STARTED y persiste.

        Raises:
            OrchestratorError: si la fase no existe o no puede iniciarse.
        """
        if not Phase.is_valid(phase):
            raise OrchestratorError(f"Fase desconocida: {phase!r}")

        can, reason = self.can_start_phase(phase)
        if not can:
            self.log.record_event(
                event_type=EventType.PHASE_BLOCKED,
                status=EventStatus.WARNING,
                message=f"No se puede iniciar la fase {phase}: {reason}",
                phase=phase,
                agent=agent,
            )
            raise OrchestratorError(
                f"No se puede iniciar la fase {phase}: {reason}"
            )

        ps = self.state.phases[phase]
        ps.status     = PhaseStatusValue.IN_PROGRESS
        ps.started_at = now_iso()
        self.state.current_phase = phase

        self.log.record_event(
            event_type=EventType.PHASE_STARTED,
            status=EventStatus.OK,
            message=f"Iniciando fase {phase}: {Phase.name_of(phase)}",
            phase=phase,
            agent=agent,
        )
        self.save_state()
        return ps

    def complete_phase(
        self,
        phase: str,
        generated_files: Optional[list] = None,
        warnings: Optional[list] = None,
        agent: Optional[str] = None,
        allow_direct_complete: bool = False,
    ) -> PhaseStatus:
        """Marca la fase como COMPLETED, registra PHASE_COMPLETED y persiste.

        Por defecto exige que la fase esté IN_PROGRESS.
        Con allow_direct_complete=True permite completar desde NOT_STARTED.

        Raises:
            OrchestratorError: si la fase no existe, ya está COMPLETED,
                               o no está IN_PROGRESS (sin allow_direct_complete).
        """
        if not Phase.is_valid(phase):
            raise OrchestratorError(f"Fase desconocida: {phase!r}")

        ps = self.state.phases[phase]

        if ps.status == PhaseStatusValue.COMPLETED:
            raise OrchestratorError(f"Fase {phase} ya está COMPLETED.")

        if ps.status != PhaseStatusValue.IN_PROGRESS and not allow_direct_complete:
            raise OrchestratorError(
                f"Fase {phase} no está IN_PROGRESS (estado: {ps.status}). "
                f"Use allow_direct_complete=True para completar directamente."
            )

        ps.status       = PhaseStatusValue.COMPLETED
        ps.completed_at = now_iso()
        if generated_files:
            ps.generated_files = list(generated_files)
        if warnings:
            ps.warnings = list(warnings)
        self.state.current_phase = phase

        self.log.record_event(
            event_type=EventType.PHASE_COMPLETED,
            status=EventStatus.OK,
            message=f"Fase {phase} completada: {Phase.name_of(phase)}",
            phase=phase,
            agent=agent,
            files=generated_files or [],
        )

        for archivo in generated_files or []:
            self.log.record_event(
                event_type=EventType.FILE_GENERATED,
                status=EventStatus.OK,
                message=f"Archivo generado: {archivo}",
                phase=phase,
                agent=agent,
                files=[archivo],
            )

        self.save_state()
        return ps

    def block_phase(
        self,
        phase: str,
        reason: str,
        agent: Optional[str] = None,
    ) -> PhaseStatus:
        """Marca la fase como BLOCKED, registra PHASE_BLOCKED y persiste.

        Raises:
            OrchestratorError: si la fase es desconocida.
        """
        if not Phase.is_valid(phase):
            raise OrchestratorError(f"Fase desconocida: {phase!r}")

        ps = self.state.phases[phase]
        ps.status         = PhaseStatusValue.BLOCKED
        ps.blocked_reason = reason

        self.log.record_event(
            event_type=EventType.PHASE_BLOCKED,
            status=EventStatus.BLOCKED,
            message=f"Fase {phase} bloqueada: {reason}",
            phase=phase,
            agent=agent,
        )
        self.save_state()
        return ps

    # -----------------------------------------------------------------------
    # Validación de schemas
    # -----------------------------------------------------------------------

    def validate_model(self) -> ValidationResult:
        """Valida el expediente contra los schemas v2.1 usando NL-02.

        Registra VALIDATION_PASSED si no hay errores,
        o VALIDATION_FAILED si los hay.

        No bloquea ni completa fases. Eso corresponde a NL-04.

        Returns:
            ValidationResult con todos los issues encontrados.
        """
        result = validate_expediente(self.expediente_path)

        if result.is_valid():
            self.log.record_event(
                event_type=EventType.VALIDATION_PASSED,
                status=EventStatus.OK,
                message=(
                    f"Validación OK: {result.error_count()} errores, "
                    f"{result.warning_count()} avisos"
                ),
                details={
                    "error_count":   result.error_count(),
                    "warning_count": result.warning_count(),
                },
            )
        else:
            self.log.record_event(
                event_type=EventType.VALIDATION_FAILED,
                status=EventStatus.WARNING,
                message=(
                    f"Validación con errores: {result.error_count()} errores, "
                    f"{result.warning_count()} avisos"
                ),
                details={
                    "error_count":   result.error_count(),
                    "warning_count": result.warning_count(),
                    "issues":        [str(i) for i in result.issues],
                },
            )

        return result

    # -----------------------------------------------------------------------
    # Resumen
    # -----------------------------------------------------------------------

    def summary(self) -> str:
        """Resumen legible del estado actual del orquestador."""
        s = self.state

        completed   = [ph for ph, ps in s.phases.items() if ps.status == PhaseStatusValue.COMPLETED]
        in_progress = [ph for ph, ps in s.phases.items() if ps.status == PhaseStatusValue.IN_PROGRESS]
        blocked     = [ph for ph, ps in s.phases.items() if ps.status == PhaseStatusValue.BLOCKED]

        # Siguiente fase que puede iniciarse
        next_suggestion = None
        for ph in Phase._ORDERED:
            if s.phases[ph].status == PhaseStatusValue.NOT_STARTED:
                can, _ = self.can_start_phase(ph)
                if can:
                    next_suggestion = ph
                    break

        lines = [
            f"Expediente : {self.expediente_id}",
            f"Modo test  : {'SI' if self.test_mode else 'NO'}",
            f"Fase actual: {s.current_phase or '—'}",
            f"Completadas: {', '.join(completed) if completed else '—'}",
            f"En progreso: {', '.join(in_progress) if in_progress else '—'}",
            f"Bloqueadas : {', '.join(blocked) if blocked else '—'}",
            f"Errores log: {'SI' if self.log.has_blocking_errors() else 'NO'}",
            (
                f"Siguiente  : Fase {next_suggestion} — {Phase.name_of(next_suggestion)}"
                if next_suggestion else
                "Siguiente  : —"
            ),
            f"Actualizado: {s.last_updated}",
        ]
        return "\n".join(lines)
