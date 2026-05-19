"""
orchestrator_log -- NL-06
Log estructurado de ejecucion del orquestador EIA-Agent v2.1.

Persiste los eventos de fases, gates y validaciones en
control_interno/orchestrator_log.json dentro del expediente.

Uso:
    from eia_agent.core.orchestrator_log import OrchestratorLog, EventType

    log = OrchestratorLog(expediente_path)
    log.record_event(
        event_type=EventType.PHASE_STARTED,
        phase="Fase 2",
        agent="AG-04",
        status="OK",
        message="Iniciando cierre del objeto evaluado",
    )
    print(log.summary())
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Tipos de evento
# ---------------------------------------------------------------------------

class EventType:
    """Constantes para los tipos de evento registrables."""
    PHASE_STARTED      = "PHASE_STARTED"
    PHASE_COMPLETED    = "PHASE_COMPLETED"
    PHASE_BLOCKED      = "PHASE_BLOCKED"
    GATE_PASSED        = "GATE_PASSED"
    GATE_FAILED        = "GATE_FAILED"
    VALIDATION_PASSED  = "VALIDATION_PASSED"
    VALIDATION_FAILED  = "VALIDATION_FAILED"
    FILE_GENERATED     = "FILE_GENERATED"
    WARNING_RECORDED   = "WARNING_RECORDED"
    ERROR_RECORDED     = "ERROR_RECORDED"
    MANUAL_NOTE        = "MANUAL_NOTE"

    _ALL = {
        PHASE_STARTED, PHASE_COMPLETED, PHASE_BLOCKED,
        GATE_PASSED, GATE_FAILED,
        VALIDATION_PASSED, VALIDATION_FAILED,
        FILE_GENERATED,
        WARNING_RECORDED, ERROR_RECORDED,
        MANUAL_NOTE,
    }

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls._ALL


# Valores de status
class EventStatus:
    OK      = "OK"
    WARNING = "WARNING"
    ERROR   = "ERROR"
    BLOCKED = "BLOCKED"
    INFO    = "INFO"

    _BLOCKING = {ERROR, BLOCKED}

    @classmethod
    def is_blocking(cls, value: str) -> bool:
        return value in cls._BLOCKING


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Devuelve el timestamp actual en formato ISO 8601 con timezone UTC."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_event_id(events: "list[OrchestratorEvent]") -> str:
    """Genera el siguiente ID correlativo en formato EV-NNNN.

    Si la lista esta vacia devuelve EV-0001.
    Busca el maximo ID existente e incrementa en 1.
    """
    if not events:
        return "EV-0001"
    max_n = 0
    for ev in events:
        try:
            n = int(ev.event_id.split("-", 1)[1])
            if n > max_n:
                max_n = n
        except (IndexError, ValueError):
            pass
    return f"EV-{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# Dataclass de evento
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorEvent:
    """Evento individual del log del orquestador."""
    event_id: str
    timestamp: str
    expediente_id: str
    event_type: str
    status: str
    message: str
    phase: Optional[str] = None
    agent: Optional[str] = None
    details: dict = field(default_factory=dict)
    files: list = field(default_factory=list)

    def is_blocking(self) -> bool:
        """True si el estado del evento es ERROR o BLOCKED."""
        return EventStatus.is_blocking(self.status)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorEvent":
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", ""),
            expediente_id=data.get("expediente_id", ""),
            event_type=data.get("event_type", ""),
            status=data.get("status", ""),
            message=data.get("message", ""),
            phase=data.get("phase"),
            agent=data.get("agent"),
            details=data.get("details", {}),
            files=data.get("files", []),
        )


# ---------------------------------------------------------------------------
# Clase principal del log
# ---------------------------------------------------------------------------

_LOG_FILENAME = "orchestrator_log.json"
_CONTROL_INTERNO_DIR = "control_interno"


@dataclass
class OrchestratorLog:
    """Log estructurado de ejecucion en JSON para un expediente.

    Crea `control_interno/orchestrator_log.json` si no existe.
    Carga los eventos existentes al inicializarse.

    Si el archivo existe pero esta corrupto (JSON invalido), NO lo sobreescribe:
    crea una copia de seguridad `orchestrator_log.corrupt.YYYYMMDD_HHMMSS.json`
    y registra el error en `load_error`. En ese caso `has_blocking_errors()`
    devuelve True y `summary()` muestra una advertencia explicita.
    """
    expediente_path: Path
    _events: list = field(default_factory=list, init=False, repr=False)
    _log_path: Path = field(init=False, repr=False)
    load_error: Optional[str] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.expediente_path = Path(self.expediente_path).resolve()
        self._log_path = (
            self.expediente_path / _CONTROL_INTERNO_DIR / _LOG_FILENAME
        )
        self.load_error = None  # debe inicializarse antes de llamar a load()
        self._events = self.load()

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def expediente_id(self) -> str:
        return self.expediente_path.name

    # -----------------------------------------------------------------------
    # Persistencia
    # -----------------------------------------------------------------------

    def load(self) -> "list[OrchestratorEvent]":
        """Carga los eventos desde el archivo JSON.

        Si el archivo no existe devuelve lista vacia sin error.
        Si el JSON esta corrupto: crea una copia de seguridad junto al archivo
        original con nombre `orchestrator_log.corrupt.YYYYMMDD_HHMMSS.json`,
        registra el error en `self.load_error` y devuelve lista vacia.
        Nunca sobreescribe silenciosamente un archivo corrupto.
        """
        if not self._log_path.exists():
            return []
        try:
            raw = json.loads(self._log_path.read_text(encoding="utf-8"))
            events_data = raw if isinstance(raw, list) else raw.get("events", [])
            return [OrchestratorEvent.from_dict(e) for e in events_data]
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"orchestrator_log.corrupt.{ts}.json"
            backup_path = self._log_path.parent / backup_name
            try:
                shutil.copy2(self._log_path, backup_path)
                self.load_error = (
                    f"Log corrupto: no se pudo parsear '{self._log_path.name}'. "
                    f"Copia de seguridad creada: '{backup_name}'. Error: {exc}"
                )
            except OSError as backup_exc:
                self.load_error = (
                    f"Log corrupto y no se pudo crear copia de seguridad: "
                    f"{exc} / {backup_exc}"
                )
            return []

    def save(self) -> None:
        """Guarda todos los eventos en el archivo JSON (UTF-8, indentado)."""
        ci_dir = self._log_path.parent
        ci_dir.mkdir(parents=True, exist_ok=True)
        payload = [ev.to_dict() for ev in self._events]
        self._log_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # -----------------------------------------------------------------------
    # Escritura de eventos
    # -----------------------------------------------------------------------

    def add_event(self, event: OrchestratorEvent) -> None:
        """Añade un evento a la lista en memoria (no persiste hasta save())."""
        self._events.append(event)

    def record_event(
        self,
        event_type: str,
        status: str,
        message: str,
        phase: Optional[str] = None,
        agent: Optional[str] = None,
        details: Optional[dict] = None,
        files: Optional[list] = None,
        timestamp: Optional[str] = None,
    ) -> OrchestratorEvent:
        """Crea un evento, lo añade al log y lo persiste inmediatamente.

        Args:
            event_type: uno de los valores de EventType.
            status:     uno de los valores de EventStatus (OK/WARNING/ERROR/BLOCKED/INFO).
            message:    descripcion legible del evento.
            phase:      fase del expediente (ej. 'Fase 2', 'Fase 4').
            agent:      agente que genera el evento (ej. 'AG-04', 'M-11').
            details:    dict con informacion adicional especifica del evento.
            files:      lista de rutas de archivos generados o afectados.
            timestamp:  ISO string; si es None se usa now_iso().

        Returns:
            El OrchestratorEvent creado y persistido.
        """
        event = OrchestratorEvent(
            event_id=generate_event_id(self._events),
            timestamp=timestamp or now_iso(),
            expediente_id=self.expediente_id,
            event_type=event_type,
            status=status,
            message=message,
            phase=phase,
            agent=agent,
            details=details or {},
            files=files or [],
        )
        self.add_event(event)
        self.save()
        return event

    # -----------------------------------------------------------------------
    # Lectura y consulta
    # -----------------------------------------------------------------------

    def last_event(self) -> Optional[OrchestratorEvent]:
        """Devuelve el ultimo evento registrado, o None si el log esta vacio."""
        return self._events[-1] if self._events else None

    def events_by_phase(self, phase: str) -> "list[OrchestratorEvent]":
        """Devuelve todos los eventos de una fase concreta."""
        return [e for e in self._events if e.phase == phase]

    def events_by_type(self, event_type: str) -> "list[OrchestratorEvent]":
        """Devuelve todos los eventos de un tipo concreto."""
        return [e for e in self._events if e.event_type == event_type]

    def has_blocking_errors(self) -> bool:
        """True si existe algun evento con status ERROR o BLOCKED,
        o si el log anterior estaba corrupto al cargar."""
        if self.load_error is not None:
            return True
        return any(e.is_blocking() for e in self._events)

    def all_events(self) -> "list[OrchestratorEvent]":
        """Devuelve copia de la lista de eventos."""
        return list(self._events)

    def summary(self) -> str:
        """Devuelve un texto legible con el estado actual del log."""
        total = len(self._events)
        errors = sum(1 for e in self._events if e.status == EventStatus.ERROR)
        blocked = sum(1 for e in self._events if e.status == EventStatus.BLOCKED)
        warnings = sum(1 for e in self._events if e.status == EventStatus.WARNING)
        ok = sum(1 for e in self._events if e.status == EventStatus.OK)

        estado = "CON ERRORES" if self.has_blocking_errors() else "OK"

        lines = [
            f"Expediente : {self.expediente_id}",
            f"Log        : {self._log_path}",
            f"Estado     : {estado}",
            f"Eventos    : {total} total "
            f"({ok} OK, {errors} errores, {blocked} bloqueados, {warnings} avisos)",
        ]

        if self.load_error:
            lines.append("")
            lines.append(f"ADVERTENCIA DE CARGA : {self.load_error}")

        if self._events:
            lines.append("")
            lines.append("Ultimos eventos:")
            for ev in self._events[-5:]:
                fase_str = f" [{ev.phase}]" if ev.phase else ""
                agent_str = f" ({ev.agent})" if ev.agent else ""
                lines.append(
                    f"  {ev.event_id} {ev.timestamp} "
                    f"[{ev.status}]{fase_str}{agent_str} {ev.message}"
                )

        return "\n".join(lines)
