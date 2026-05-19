"""tests/test_session_recovery.py — Suite de tests para SessionRecovery (NL-07).

Cubre los criterios de cierre del ítem:
- expediente sin estado ni log → INICIAR_FASE_1, can_continue=True
- expediente con estado limpio → can_continue=True
- fase 1 completada → sugiere CONTINUAR_SIGUIENTE_FASE
- fase IN_PROGRESS → can_continue=False, REVISAR_FASE_EN_PROGRESO
- fase BLOCKED → can_continue=False, RESOLVER_BLOQUEO
- log con evento ERROR/BLOCKED → can_continue=False, NO_CONTINUAR
- log corrupto → can_continue=False, REVISAR_LOG_CORRUPTO
- estado corrupto → can_continue=False, RECREAR_ESTADO_DESDE_LOG_MANUALMENTE
- discrepancia estado COMPLETED sin evento log → WARNING
- log PHASE_STARTED sin cierre → WARNING
- write_recovery_report crea JSON válido en control_interno/
- no modifica expedientes piloto reales (mtime invariante)
- funciona con expedientes PARCELA y NAVE-222 (solo lectura)
"""
import json
import sys
import time
import unittest
from pathlib import Path

# Asegurar que src/ está en el path antes de cualquier import del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tempfile

from eia_agent.core.session_recovery import (
    ACTION_CONTINUAR_SIGUIENTE_FASE,
    ACTION_INICIAR_FASE_1,
    ACTION_NO_CONTINUAR,
    ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE,
    ACTION_RESOLVER_BLOQUEO,
    ACTION_REVISAR_FASE_EN_PROGRESO,
    ACTION_REVISAR_LOG_CORRUPTO,
    RecoveryIssue,
    RecoveryReport,
    SessionRecovery,
)
from eia_agent.core.orchestrator import EIAOrchestrator, Phase, PhaseStatusValue
from eia_agent.core.orchestrator_log import EventStatus, EventType, OrchestratorLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exp(tmp: tempfile.TemporaryDirectory | str, name: str = "EIA-TEST-SR") -> Path:
    exp = Path(tmp) / name
    exp.mkdir(parents=True, exist_ok=True)
    return exp


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_clean_state(exp: Path, completed_phases: list[str] | None = None) -> dict:
    """Crea un orchestrator_state.json con fases completadas indicadas."""
    phases: dict = {}
    for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
        if completed_phases and ph in completed_phases:
            status = "COMPLETED"
        else:
            status = "NOT_STARTED"
        phases[ph] = {
            "phase": ph,
            "name": f"Fase {ph}",
            "status": status,
            "started_at": "2026-04-21T10:00:00Z" if status == "COMPLETED" else None,
            "completed_at": "2026-04-21T10:30:00Z" if status == "COMPLETED" else None,
            "blocked_reason": None,
            "warnings": [],
            "generated_files": [],
        }
    state = {
        "expediente_id": exp.name,
        "current_phase": completed_phases[-1] if completed_phases else None,
        "phases": phases,
        "last_updated": "2026-04-21T10:30:00Z",
        "test_mode": True,
    }
    ci = exp / "control_interno"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "orchestrator_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return state


def _make_clean_log(exp: Path, phase_events: list[tuple[str, str, str]] | None = None) -> None:
    """Crea un orchestrator_log.json con eventos opcionales.

    phase_events: list de (event_type, phase, status)
    """
    events = []
    for i, (etype, phase, estatus) in enumerate(phase_events or []):
        events.append({
            "event_id": f"EV-{i+1:04d}",
            "timestamp": "2026-04-21T10:00:00Z",
            "expediente_id": exp.name,
            "event_type": etype,
            "status": estatus,
            "message": f"Evento {etype} fase {phase}",
            "phase": phase,
            "agent": None,
            "details": {},
            "files": [],
        })
    ci = exp / "control_interno"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "orchestrator_log.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _corrupt_file(path: Path) -> None:
    """Escribe contenido inválido en un archivo JSON."""
    path.write_text("{ esto no es json válido !!!!", encoding="utf-8")


# Rutas a pilotos reales
NAVE_222 = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-NAVE-222"
PARCELA  = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-PARCELA"


# ---------------------------------------------------------------------------
# TestRecoveryIssue
# ---------------------------------------------------------------------------

class TestRecoveryIssue(unittest.TestCase):

    def test_str_con_phase(self):
        issue = RecoveryIssue(severity="ERROR", code="PHASE_BLOCKED",
                              message="bloqueada", phase="3")
        self.assertIn("ERROR", str(issue))
        self.assertIn("PHASE_BLOCKED", str(issue))
        self.assertIn("fase 3", str(issue))

    def test_str_sin_phase(self):
        issue = RecoveryIssue(severity="INFO", code="NO_STATE_NO_LOG",
                              message="no iniciado")
        self.assertIn("INFO", str(issue))
        self.assertNotIn("fase", str(issue))

    def test_fields_opcionales_none(self):
        issue = RecoveryIssue(severity="WARNING", code="X", message="m")
        self.assertIsNone(issue.phase)
        self.assertIsNone(issue.recommendation)


# ---------------------------------------------------------------------------
# TestRecoveryReport
# ---------------------------------------------------------------------------

class TestRecoveryReport(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def _report(self, can_continue=True, issues=None):
        return RecoveryReport(
            expediente_path=self.exp,
            can_continue=can_continue,
            suggested_action=ACTION_INICIAR_FASE_1,
            issues=issues or [],
        )

    def test_error_count(self):
        issues = [
            RecoveryIssue("ERROR", "A", "msg"),
            RecoveryIssue("WARNING", "B", "msg"),
            RecoveryIssue("ERROR", "C", "msg"),
        ]
        r = self._report(issues=issues)
        self.assertEqual(r.error_count(), 2)

    def test_warning_count(self):
        issues = [
            RecoveryIssue("WARNING", "A", "msg"),
            RecoveryIssue("INFO", "B", "msg"),
        ]
        r = self._report(issues=issues)
        self.assertEqual(r.warning_count(), 1)

    def test_is_clean_sin_issues(self):
        self.assertTrue(self._report().is_clean())

    def test_is_clean_solo_info(self):
        r = self._report(issues=[RecoveryIssue("INFO", "X", "ok")])
        self.assertTrue(r.is_clean())

    def test_is_clean_con_warning(self):
        r = self._report(issues=[RecoveryIssue("WARNING", "X", "aviso")])
        self.assertFalse(r.is_clean())

    def test_is_clean_con_error(self):
        r = self._report(issues=[RecoveryIssue("ERROR", "X", "error")])
        self.assertFalse(r.is_clean())

    def test_summary_contiene_accion(self):
        r = self._report()
        self.assertIn(ACTION_INICIAR_FASE_1, r.summary())

    def test_summary_puede_continuar(self):
        r = self._report(can_continue=True)
        self.assertIn("PUEDE CONTINUAR", r.summary())

    def test_summary_no_puede_continuar(self):
        r = self._report(can_continue=False)
        self.assertIn("NO PUEDE CONTINUAR", r.summary())


# ---------------------------------------------------------------------------
# TestSessionRecoveryInit
# ---------------------------------------------------------------------------

class TestSessionRecoveryInit(unittest.TestCase):

    def test_init_con_path_str(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            sr = SessionRecovery(str(exp))
            self.assertIsInstance(sr.expediente_path, Path)

    def test_init_con_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            sr = SessionRecovery(exp)
            self.assertEqual(sr.expediente_path, exp.resolve())

    def test_init_test_mode_default_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            sr = SessionRecovery(exp)
            self.assertTrue(sr.test_mode)

    def test_init_test_mode_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            sr = SessionRecovery(exp, test_mode=False)
            self.assertFalse(sr.test_mode)

    def test_init_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            SessionRecovery(exp)
            ci = exp / "control_interno"
            self.assertFalse(ci.exists())


# ---------------------------------------------------------------------------
# TestSinEstadoNiLog
# ---------------------------------------------------------------------------

class TestSinEstadoNiLog(unittest.TestCase):
    """Expediente sin orchestrator_state.json ni orchestrator_log.json."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        self.sr = SessionRecovery(self.exp)

    def test_analyze_can_continue_true(self):
        report = self.sr.analyze()
        self.assertTrue(report.can_continue)

    def test_analyze_action_iniciar_fase_1(self):
        report = self.sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_INICIAR_FASE_1)

    def test_analyze_issue_no_state_no_log(self):
        report = self.sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("NO_STATE_NO_LOG", codes)

    def test_analyze_no_errores(self):
        report = self.sr.analyze()
        self.assertEqual(report.error_count(), 0)

    def test_analyze_last_phase_none(self):
        report = self.sr.analyze()
        self.assertIsNone(report.last_phase)

    def test_analyze_interrupted_phase_none(self):
        report = self.sr.analyze()
        self.assertIsNone(report.interrupted_phase)

    def test_last_completed_phase_none(self):
        self.assertIsNone(self.sr.last_completed_phase())

    def test_interrupted_phase_none(self):
        self.assertIsNone(self.sr.interrupted_phase())

    def test_is_clean_true(self):
        report = self.sr.analyze()
        self.assertTrue(report.is_clean())


# ---------------------------------------------------------------------------
# TestEstadoLimpio
# ---------------------------------------------------------------------------

class TestEstadoLimpio(unittest.TestCase):
    """Expediente con estado limpio (fases NOT_STARTED, sin log)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        _make_clean_state(self.exp, completed_phases=[])
        # Sin log → LOG_MISSING warning pero aún puede continuar
        self.sr = SessionRecovery(self.exp)

    def test_analyze_can_continue_true(self):
        report = self.sr.analyze()
        self.assertTrue(report.can_continue)

    def test_analyze_no_errores(self):
        report = self.sr.analyze()
        self.assertEqual(report.error_count(), 0)


class TestEstadoLimpioConLog(unittest.TestCase):
    """Estado limpio + log limpio."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        _make_clean_state(self.exp, completed_phases=[])
        _make_clean_log(self.exp, [])
        self.sr = SessionRecovery(self.exp)

    def test_analyze_can_continue_true(self):
        report = self.sr.analyze()
        self.assertTrue(report.can_continue)

    def test_analyze_is_clean(self):
        report = self.sr.analyze()
        self.assertTrue(report.is_clean())

    def test_analyze_action_iniciar_fase_1(self):
        report = self.sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_INICIAR_FASE_1)


# ---------------------------------------------------------------------------
# TestFase1Completada
# ---------------------------------------------------------------------------

class TestFase1Completada(unittest.TestCase):
    """Fase 1 COMPLETED en estado y log coherente."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        _make_clean_state(self.exp, completed_phases=["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
        ])
        self.sr = SessionRecovery(self.exp)

    def test_last_completed_phase_es_1(self):
        self.assertEqual(self.sr.last_completed_phase(), "1")

    def test_analyze_last_phase_es_1(self):
        report = self.sr.analyze()
        self.assertEqual(report.last_phase, "1")

    def test_analyze_can_continue_true(self):
        report = self.sr.analyze()
        self.assertTrue(report.can_continue)

    def test_analyze_action_continuar_siguiente(self):
        report = self.sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_CONTINUAR_SIGUIENTE_FASE)

    def test_analyze_no_errores(self):
        report = self.sr.analyze()
        self.assertEqual(report.error_count(), 0)


class TestFases1a5Completadas(unittest.TestCase):
    """Fases 1-5 completadas."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        completed = ["1", "2", "3", "4", "5"]
        _make_clean_state(self.exp, completed_phases=completed)
        events = []
        for ph in completed:
            events.append((EventType.PHASE_STARTED,   ph, EventStatus.OK))
            events.append((EventType.PHASE_COMPLETED, ph, EventStatus.OK))
        _make_clean_log(self.exp, events)

    def test_last_completed_phase_es_5(self):
        sr = SessionRecovery(self.exp)
        self.assertEqual(sr.last_completed_phase(), "5")

    def test_action_continuar_siguiente(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_CONTINUAR_SIGUIENTE_FASE)


# ---------------------------------------------------------------------------
# TestFaseInProgress
# ---------------------------------------------------------------------------

class TestFaseInProgress(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def _set_phase_in_progress(self, phase: str, completed_before: list[str] = None):
        state_data = {
            "expediente_id": self.exp.name,
            "current_phase": phase,
            "phases": {},
            "last_updated": "2026-04-21T10:00:00Z",
            "test_mode": True,
        }
        for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            if completed_before and ph in completed_before:
                status = "COMPLETED"
            elif ph == phase:
                status = "IN_PROGRESS"
            else:
                status = "NOT_STARTED"
            state_data["phases"][ph] = {
                "phase": ph, "name": f"Fase {ph}", "status": status,
                "started_at": None, "completed_at": None,
                "blocked_reason": None, "warnings": [], "generated_files": [],
            }
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        (ci / "orchestrator_state.json").write_text(
            json.dumps(state_data, ensure_ascii=False), encoding="utf-8"
        )

    def test_fase_2_in_progress_no_continuar(self):
        self._set_phase_in_progress("2", completed_before=["1"])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_fase_in_progress_action_revisar(self):
        self._set_phase_in_progress("3")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_REVISAR_FASE_EN_PROGRESO)

    def test_fase_in_progress_interrupted_phase(self):
        self._set_phase_in_progress("4")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.interrupted_phase, "4")

    def test_fase_in_progress_issue_code(self):
        self._set_phase_in_progress("2")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("PHASE_IN_PROGRESS", codes)

    def test_interrupted_phase_metodo(self):
        self._set_phase_in_progress("5")
        sr = SessionRecovery(self.exp)
        self.assertEqual(sr.interrupted_phase(), "5")


# ---------------------------------------------------------------------------
# TestFaseBlocked
# ---------------------------------------------------------------------------

class TestFaseBlocked(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def _set_phase_blocked(self, phase: str, reason: str = "Gap crítico abierto"):
        state_data = {
            "expediente_id": self.exp.name,
            "current_phase": phase,
            "phases": {},
            "last_updated": "2026-04-21T10:00:00Z",
            "test_mode": True,
        }
        for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            if ph == phase:
                status = "BLOCKED"
            else:
                status = "NOT_STARTED"
            state_data["phases"][ph] = {
                "phase": ph, "name": f"Fase {ph}", "status": status,
                "started_at": None, "completed_at": None,
                "blocked_reason": reason if ph == phase else None,
                "warnings": [], "generated_files": [],
            }
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        (ci / "orchestrator_state.json").write_text(
            json.dumps(state_data, ensure_ascii=False), encoding="utf-8"
        )

    def test_fase_blocked_no_continuar(self):
        self._set_phase_blocked("3", "Normativa no verificada")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_fase_blocked_action(self):
        self._set_phase_blocked("3")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_RESOLVER_BLOQUEO)

    def test_fase_blocked_issue_code(self):
        self._set_phase_blocked("2")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("PHASE_BLOCKED", codes)

    def test_fase_blocked_issue_message_contiene_razon(self):
        self._set_phase_blocked("4", "RC pendiente de validación")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        msgs = [i.message for i in report.issues if i.code == "PHASE_BLOCKED"]
        self.assertTrue(any("RC pendiente" in m for m in msgs))


# ---------------------------------------------------------------------------
# TestLogConErrores
# ---------------------------------------------------------------------------

class TestLogConErrores(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_log_con_evento_error_no_continuar(self):
        _make_clean_state(self.exp, [])
        _make_clean_log(self.exp, [
            (EventType.ERROR_RECORDED, "1", EventStatus.ERROR),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_log_con_evento_blocked_no_continuar(self):
        _make_clean_state(self.exp, [])
        _make_clean_log(self.exp, [
            (EventType.PHASE_BLOCKED, "2", EventStatus.BLOCKED),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_log_con_error_action_no_continuar(self):
        _make_clean_state(self.exp, [])
        _make_clean_log(self.exp, [
            (EventType.ERROR_RECORDED, "1", EventStatus.ERROR),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_NO_CONTINUAR)

    def test_log_con_error_issue_code(self):
        _make_clean_state(self.exp, [])
        _make_clean_log(self.exp, [
            (EventType.ERROR_RECORDED, "3", EventStatus.ERROR),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("LOG_BLOCKING_ERROR", codes)

    def test_log_con_warning_no_bloquea(self):
        _make_clean_state(self.exp, [])
        _make_clean_log(self.exp, [
            (EventType.WARNING_RECORDED, "1", EventStatus.WARNING),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        # WARNING en log no bloquea
        self.assertNotIn("LOG_BLOCKING_ERROR", [i.code for i in report.issues])


# ---------------------------------------------------------------------------
# TestLogCorrupto
# ---------------------------------------------------------------------------

class TestLogCorrupto(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_log_corrupto_no_continuar(self):
        _make_clean_state(self.exp, [])
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_log.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_log_corrupto_action(self):
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_log.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_REVISAR_LOG_CORRUPTO)

    def test_log_corrupto_issue_code(self):
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_log.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("LOG_CORRUPTED", codes)


# ---------------------------------------------------------------------------
# TestEstadoCorrupto
# ---------------------------------------------------------------------------

class TestEstadoCorrupto(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_estado_corrupto_no_continuar(self):
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_state.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertFalse(report.can_continue)

    def test_estado_corrupto_action(self):
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_state.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE)

    def test_estado_corrupto_issue_code(self):
        ci = self.exp / "control_interno"
        ci.mkdir(exist_ok=True)
        _corrupt_file(ci / "orchestrator_state.json")
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("STATE_CORRUPTED", codes)


# ---------------------------------------------------------------------------
# TestDiscrepancias
# ---------------------------------------------------------------------------

class TestDiscrepancias(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_estado_completed_sin_evento_log_warning(self):
        # Estado dice fase 1 COMPLETED pero log no tiene PHASE_COMPLETED
        _make_clean_state(self.exp, completed_phases=["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED, "1", EventStatus.OK),
            # Falta PHASE_COMPLETED
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("STATE_LOG_DISCREPANCY", codes)

    def test_estado_completed_sin_evento_log_es_warning_no_error(self):
        _make_clean_state(self.exp, completed_phases=["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED, "1", EventStatus.OK),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        discrepancy_issues = [i for i in report.issues if i.code == "STATE_LOG_DISCREPANCY"]
        self.assertTrue(all(i.severity == "WARNING" for i in discrepancy_issues))

    def test_log_started_sin_cierre_no_estado_warning(self):
        # Log tiene PHASE_STARTED para fase 2 sin PHASE_COMPLETED
        # pero estado dice NOT_STARTED (inconsistencia silenciosa)
        _make_clean_state(self.exp, completed_phases=["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
            (EventType.PHASE_STARTED,   "2", EventStatus.OK),
            # Falta PHASE_COMPLETED para fase 2
            # El estado tiene fase 2 NOT_STARTED, no IN_PROGRESS
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("LOG_STARTED_NOT_CLOSED", codes)

    def test_coherente_no_discrepancia(self):
        # Estado y log coherentes: no debe haber discrepancias
        _make_clean_state(self.exp, completed_phases=["1", "2"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
            (EventType.PHASE_STARTED,   "2", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "2", EventStatus.OK),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertNotIn("STATE_LOG_DISCREPANCY", codes)
        self.assertNotIn("LOG_STARTED_NOT_CLOSED", codes)


# ---------------------------------------------------------------------------
# TestSoloLogSinEstado
# ---------------------------------------------------------------------------

class TestSoloLogSinEstado(unittest.TestCase):
    """Log existe pero no hay orchestrator_state.json."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
        ])

    def test_state_missing_log_exists_issue(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("STATE_MISSING_LOG_EXISTS", codes)

    def test_action_recrear_estado(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.suggested_action, ACTION_RECREAR_ESTADO_DESDE_LOG_MANUALMENTE)


# ---------------------------------------------------------------------------
# TestSoloEstadoSinLog
# ---------------------------------------------------------------------------

class TestSoloEstadoSinLog(unittest.TestCase):
    """Estado existe pero no hay log."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        _make_clean_state(self.exp, completed_phases=["1"])

    def test_log_missing_issue(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("LOG_MISSING", codes)

    def test_log_missing_es_warning_no_error(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        log_missing = [i for i in report.issues if i.code == "LOG_MISSING"]
        self.assertTrue(all(i.severity == "WARNING" for i in log_missing))

    def test_can_continue_true_pese_a_log_missing(self):
        # Sin errores (solo warning) → puede continuar
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertTrue(report.can_continue)


# ---------------------------------------------------------------------------
# TestWriteRecoveryReport
# ---------------------------------------------------------------------------

class TestWriteRecoveryReport(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_crea_archivo_json(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        self.assertTrue(path.exists())

    def test_ruta_en_control_interno(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        self.assertEqual(path.parent.name, "control_interno")
        self.assertEqual(path.name, "recovery_report.json")

    def test_json_valido(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("can_continue", data)
        self.assertIn("suggested_action", data)
        self.assertIn("issues", data)

    def test_json_contiene_can_continue(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data["can_continue"], bool)

    def test_json_contiene_campos_requeridos(self):
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        data = json.loads(path.read_text(encoding="utf-8"))
        for campo in ("expediente_path", "can_continue", "suggested_action",
                      "last_phase", "interrupted_phase", "error_count",
                      "warning_count", "is_clean", "issues"):
            self.assertIn(campo, data, f"Campo faltante: {campo}")

    def test_json_issues_es_lista(self):
        _make_clean_log(self.exp, [(EventType.ERROR_RECORDED, "1", EventStatus.ERROR)])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data["issues"], list)

    def test_json_issue_tiene_campos(self):
        _make_clean_log(self.exp, [(EventType.ERROR_RECORDED, "1", EventStatus.ERROR)])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["issues"]:
            issue = data["issues"][0]
            for campo in ("severity", "code", "message"):
                self.assertIn(campo, issue)

    def test_no_modifica_state_ni_log(self):
        _make_clean_state(self.exp, ["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
        ])
        state_path = self.exp / "control_interno" / "orchestrator_state.json"
        log_path   = self.exp / "control_interno" / "orchestrator_log.json"
        mtime_state_before = state_path.stat().st_mtime
        mtime_log_before   = log_path.stat().st_mtime
        time.sleep(0.05)

        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        sr.write_recovery_report(report)

        self.assertAlmostEqual(state_path.stat().st_mtime, mtime_state_before, places=2)
        self.assertAlmostEqual(log_path.stat().st_mtime,   mtime_log_before,   places=2)


# ---------------------------------------------------------------------------
# TestSuggestNextAction
# ---------------------------------------------------------------------------

class TestSuggestNextAction(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)
        self.sr = SessionRecovery(self.exp)

    def test_suggest_desde_report_sin_estado(self):
        report = self.sr.analyze()
        accion = self.sr.suggest_next_action(report)
        self.assertEqual(accion, ACTION_INICIAR_FASE_1)

    def test_suggest_desde_report_con_fase_completada(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _make_clean_state(exp, ["1"])
            _make_clean_log(exp, [
                (EventType.PHASE_STARTED,   "1", EventStatus.OK),
                (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
            ])
            sr = SessionRecovery(exp)
            report = sr.analyze()
            accion = sr.suggest_next_action(report)
            self.assertEqual(accion, ACTION_CONTINUAR_SIGUIENTE_FASE)


# ---------------------------------------------------------------------------
# TestConOrquestadorReal
# ---------------------------------------------------------------------------

class TestConOrquestadorReal(unittest.TestCase):
    """Tests de integración usando EIAOrchestrator para crear el estado."""

    def test_fase_1_completada_via_orquestador(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            orch = EIAOrchestrator(exp, test_mode=True)
            orch.start_phase("1", agent="AG-01")
            orch.complete_phase("1", generated_files=["capas/hechos_confirmados.json"])

            sr = SessionRecovery(exp)
            report = sr.analyze()
            self.assertEqual(report.last_phase, "1")
            self.assertTrue(report.can_continue)

    def test_fase_bloqueada_via_orquestador(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            orch = EIAOrchestrator(exp, test_mode=True)
            orch.start_phase("1", agent="AG-01")
            orch.complete_phase("1")
            orch.start_phase("2")
            orch.block_phase("2", reason="RC pendiente confirmación")

            sr = SessionRecovery(exp)
            report = sr.analyze()
            self.assertFalse(report.can_continue)
            self.assertEqual(report.suggested_action, ACTION_RESOLVER_BLOQUEO)

    def test_in_progress_via_orquestador(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            orch = EIAOrchestrator(exp, test_mode=True)
            orch.start_phase("1", agent="AG-01")
            # No se completa → queda IN_PROGRESS

            sr = SessionRecovery(exp)
            report = sr.analyze()
            self.assertFalse(report.can_continue)
            self.assertEqual(report.interrupted_phase, "1")

    def test_state_log_discrepancy_via_orquestador(self):
        """Estado dice fase 1 COMPLETED pero no hay evento PHASE_COMPLETED en log."""
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            orch = EIAOrchestrator(exp, test_mode=True)
            orch.start_phase("1")
            orch.complete_phase("1")

            # Borrar eventos PHASE_COMPLETED del log para crear discrepancia
            log_path = exp / "control_interno" / "orchestrator_log.json"
            events = json.loads(log_path.read_text(encoding="utf-8"))
            events_sin_completed = [
                e for e in events
                if e.get("event_type") != EventType.PHASE_COMPLETED
            ]
            log_path.write_text(
                json.dumps(events_sin_completed, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            sr = SessionRecovery(exp)
            report = sr.analyze()
            codes = [i.code for i in report.issues]
            self.assertIn("STATE_LOG_DISCREPANCY", codes)


# ---------------------------------------------------------------------------
# TestInterruptedPhaseEnLog
# ---------------------------------------------------------------------------

class TestInterruptedPhaseEnLog(unittest.TestCase):
    """PHASE_STARTED en log sin cierre, detectado via _find_interrupted_in_log."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp = _make_exp(self.tmp)

    def test_log_started_sin_completed_detectado(self):
        # Estado coherente (fase 1 COMPLETED), pero log también tiene fase 2 STARTED
        # sin cierre → LOG_STARTED_NOT_CLOSED
        _make_clean_state(self.exp, ["1"])
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED,   "1", EventStatus.OK),
            (EventType.PHASE_COMPLETED, "1", EventStatus.OK),
            (EventType.PHASE_STARTED,   "2", EventStatus.OK),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        codes = [i.code for i in report.issues]
        self.assertIn("LOG_STARTED_NOT_CLOSED", codes)

    def test_sin_estado_interrupted_phase_via_log(self):
        # Sin estado pero log tiene PHASE_STARTED sin PHASE_COMPLETED
        _make_clean_log(self.exp, [
            (EventType.PHASE_STARTED, "3", EventStatus.OK),
        ])
        sr = SessionRecovery(self.exp)
        report = sr.analyze()
        self.assertEqual(report.interrupted_phase, "3")


# ---------------------------------------------------------------------------
# TestNoModificaPilotos
# ---------------------------------------------------------------------------

class TestNoModificaPilotos(unittest.TestCase):
    """Garantiza que analyze() y write_recovery_report() no modifican pilotos reales."""

    def _get_mtimes(self, exp: Path) -> dict:
        mtimes = {}
        ci = exp / "control_interno"
        if ci.exists():
            for f in ci.iterdir():
                if f.is_file():
                    mtimes[f.name] = f.stat().st_mtime
        return mtimes

    def _check_not_modified(self, exp: Path, mtimes_before: dict):
        ci = exp / "control_interno"
        if not ci.exists():
            return
        for fname, mtime_before in mtimes_before.items():
            if fname == "recovery_report.json":
                continue  # write_recovery_report crea este archivo, permitido
            current = ci / fname
            if current.exists():
                self.assertAlmostEqual(
                    current.stat().st_mtime, mtime_before, places=2,
                    msg=f"Archivo modificado inesperadamente: {fname}"
                )

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_nave222_no_modificado(self):
        report_path = NAVE_222 / "control_interno" / "recovery_report.json"
        self.addCleanup(lambda: report_path.unlink(missing_ok=True))
        mtimes_before = self._get_mtimes(NAVE_222)
        time.sleep(0.05)
        sr = SessionRecovery(NAVE_222)
        report = sr.analyze()
        sr.write_recovery_report(report)
        self._check_not_modified(NAVE_222, mtimes_before)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_parcela_no_modificado(self):
        report_path = PARCELA / "control_interno" / "recovery_report.json"
        self.addCleanup(lambda: report_path.unlink(missing_ok=True))
        mtimes_before = self._get_mtimes(PARCELA)
        time.sleep(0.05)
        sr = SessionRecovery(PARCELA)
        report = sr.analyze()
        sr.write_recovery_report(report)
        self._check_not_modified(PARCELA, mtimes_before)


# ---------------------------------------------------------------------------
# TestPilotoRealNave222
# ---------------------------------------------------------------------------

class TestPilotoRealNave222(unittest.TestCase):

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_analyze_devuelve_recovery_report(self):
        sr = SessionRecovery(NAVE_222)
        report = sr.analyze()
        self.assertIsInstance(report, RecoveryReport)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_expediente_path_correcto(self):
        sr = SessionRecovery(NAVE_222)
        report = sr.analyze()
        self.assertEqual(report.expediente_path.resolve(), NAVE_222.resolve())

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_summary_devuelve_string(self):
        sr = SessionRecovery(NAVE_222)
        report = sr.analyze()
        self.assertIsInstance(report.summary(), str)
        self.assertGreater(len(report.summary()), 10)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_write_report_crea_json(self):
        report_path = NAVE_222 / "control_interno" / "recovery_report.json"
        self.addCleanup(lambda: report_path.unlink(missing_ok=True))
        sr = SessionRecovery(NAVE_222)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("can_continue", data)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_no_tiene_orchestrator_state(self):
        # NAVE-222 es expediente piloto manual: no tiene orchestrator_state.json
        state_path = NAVE_222 / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            sr = SessionRecovery(NAVE_222)
            report = sr.analyze()
            # Debe detectar NO_STATE_NO_LOG o similar
            codes = [i.code for i in report.issues]
            # Al menos una de estas condiciones debe estar presente
            self.assertTrue(
                "NO_STATE_NO_LOG" in codes or "STATE_MISSING_LOG_EXISTS" in codes,
                f"Códigos detectados: {codes}"
            )


# ---------------------------------------------------------------------------
# TestPilotoRealParcela
# ---------------------------------------------------------------------------

class TestPilotoRealParcela(unittest.TestCase):

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_analyze_devuelve_recovery_report(self):
        sr = SessionRecovery(PARCELA)
        report = sr.analyze()
        self.assertIsInstance(report, RecoveryReport)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_expediente_path_correcto(self):
        sr = SessionRecovery(PARCELA)
        report = sr.analyze()
        self.assertEqual(report.expediente_path.resolve(), PARCELA.resolve())

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_no_tiene_orchestrator_state(self):
        state_path = PARCELA / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            sr = SessionRecovery(PARCELA)
            report = sr.analyze()
            codes = [i.code for i in report.issues]
            self.assertTrue(
                "NO_STATE_NO_LOG" in codes or "STATE_MISSING_LOG_EXISTS" in codes,
                f"Códigos detectados: {codes}"
            )

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_write_report_no_lanza_excepcion(self):
        report_path = PARCELA / "control_interno" / "recovery_report.json"
        self.addCleanup(lambda: report_path.unlink(missing_ok=True))
        sr = SessionRecovery(PARCELA)
        report = sr.analyze()
        path = sr.write_recovery_report(report)
        self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
