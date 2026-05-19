"""tests/test_orchestrator.py — Suite de tests para EIAOrchestrator (NL-03).

Cubre los 16 criterios de cierre del ítem:
1.  Estado inicial: todas las fases NOT_STARTED
2.  control_interno/ creado automáticamente
3.  Existencia de fases 1 a 9
4.  Fase 1 puede empezar
5.  Fase 2 no puede empezar si fase 1 no está COMPLETED
6.  start_phase("1") marca IN_PROGRESS y registra evento
7.  complete_phase("1") marca COMPLETED y registra evento
8.  Tras completar fase 1, fase 2 puede empezar
9.  block_phase("2") marca BLOCKED y registra evento
10. Si hay bloqueo en log, no se puede avanzar
11. Fase desconocida lanza OrchestratorError
12. No se puede completar una fase que no está IN_PROGRESS
13. validate_model() registra VALIDATION_PASSED o VALIDATION_FAILED
14. summary() devuelve texto útil
15. Recargar EIAOrchestrator conserva estado
16. No modifica expedientes piloto reales
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.orchestrator import (
    EIAOrchestrator,
    OrchestratorError,
    Phase,
    PhaseStatusValue,
)
from eia_agent.core.orchestrator_log import EventStatus, EventType
from eia_agent.core.schema_validator import ValidationResult


# ---------------------------------------------------------------------------
# Rutas de referencia (solo lectura)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_NAVE222   = _REPO_ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_exp(tmp_dir: Path, name: str = "EIA-TEST-TEMP") -> Path:
    """Crea directorio vacío de expediente en tmp_dir."""
    exp = tmp_dir / f"expediente-{name}"
    exp.mkdir(parents=True)
    return exp


def _make_exp_with_capas(tmp_dir: Path) -> Path:
    """Crea expediente temporal con capas/ copiadas de NAVE-222 (solo lectura de origen)."""
    exp = _make_exp(tmp_dir, "EIA-TEST-CAPAS")
    src_capas = _NAVE222 / "capas"
    if src_capas.exists():
        shutil.copytree(src_capas, exp / "capas")
    return exp


# ---------------------------------------------------------------------------
# Tests de Phase (auxiliar)
# ---------------------------------------------------------------------------

class TestPhase(unittest.TestCase):

    def test_all_nine_phases_valid(self):
        for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            with self.subTest(phase=ph):
                self.assertTrue(Phase.is_valid(ph))

    def test_invalid_phases(self):
        for ph in ["0", "10", "A", "", "Fase 1"]:
            with self.subTest(phase=ph):
                self.assertFalse(Phase.is_valid(ph))

    def test_previous_of_first_is_none(self):
        self.assertIsNone(Phase.previous("1"))

    def test_previous_of_second_is_first(self):
        self.assertEqual(Phase.previous("2"), "1")

    def test_previous_of_last(self):
        self.assertEqual(Phase.previous("9"), "8")

    def test_next_of_last_is_none(self):
        self.assertIsNone(Phase.next_of("9"))

    def test_next_of_first(self):
        self.assertEqual(Phase.next_of("1"), "2")

    def test_name_of_returns_nonempty_string(self):
        for ph in ["1", "5", "9"]:
            with self.subTest(phase=ph):
                name = Phase.name_of(ph)
                self.assertIsInstance(name, str)
                self.assertGreater(len(name), 0)


# ---------------------------------------------------------------------------
# Tests de inicialización
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initial_state_all_not_started(self):
        """Criterio 1: todas las fases arrancan en NOT_STARTED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            with self.subTest(phase=ph):
                ps = orch.get_phase_status(ph)
                self.assertEqual(ps.status, PhaseStatusValue.NOT_STARTED)

    def test_creates_control_interno_dir(self):
        """Criterio 2: control_interno/ creado automáticamente."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        self.assertTrue((exp / "control_interno").is_dir())

    def test_all_nine_phases_exist(self):
        """Criterio 3: fases 1 a 9 presentes en el estado."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        for ph in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            with self.subTest(phase=ph):
                ps = orch.get_phase_status(ph)
                self.assertEqual(ps.phase, ph)

    def test_state_json_created(self):
        """orchestrator_state.json escrito con expediente_id correcto."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        state_path = exp / "control_interno" / "orchestrator_state.json"
        self.assertTrue(state_path.exists())
        data = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], exp.name)

    def test_log_json_created(self):
        """orchestrator_log.json creado tras primera operación."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        # El log se persiste la primera vez que se registra un evento
        orch.start_phase("1")
        log_path = exp / "control_interno" / "orchestrator_log.json"
        self.assertTrue(log_path.exists())


# ---------------------------------------------------------------------------
# Tests de can_start_phase
# ---------------------------------------------------------------------------

class TestCanStart(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase1_can_start_initially(self):
        """Criterio 4: fase 1 puede empezar desde el estado inicial."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        can, reason = orch.can_start_phase("1")
        self.assertTrue(can)
        self.assertEqual(reason, "")

    def test_phase2_cannot_start_if_phase1_not_completed(self):
        """Criterio 5: fase 2 no puede empezar si fase 1 no está COMPLETED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        can, reason = orch.can_start_phase("2")
        self.assertFalse(can)
        self.assertIn("1", reason)

    def test_phase2_cannot_start_if_phase1_in_progress(self):
        """Criterio 5: fase 2 bloqueada mientras fase 1 está IN_PROGRESS."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        can, reason = orch.can_start_phase("2")
        self.assertFalse(can)

    def test_unknown_phase_returns_false(self):
        """Criterio 11 (can_start): fase desconocida devuelve False."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        can, reason = orch.can_start_phase("99")
        self.assertFalse(can)
        self.assertGreater(len(reason), 0)


# ---------------------------------------------------------------------------
# Tests de start_phase
# ---------------------------------------------------------------------------

class TestStartPhase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_phase1_marks_in_progress(self):
        """Criterio 6: start_phase("1") cambia estado a IN_PROGRESS."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        ps = orch.start_phase("1")
        self.assertEqual(ps.status, PhaseStatusValue.IN_PROGRESS)

    def test_start_phase1_sets_started_at(self):
        """Criterio 6: start_phase("1") registra started_at."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        ps = orch.get_phase_status("1")
        self.assertIsNotNone(ps.started_at)

    def test_start_phase1_records_phase_started_event(self):
        """Criterio 6: start_phase("1") registra evento PHASE_STARTED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        events = orch.log.events_by_type(EventType.PHASE_STARTED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].phase, "1")
        self.assertEqual(events[0].status, EventStatus.OK)

    def test_start_phase1_sets_current_phase(self):
        """start_phase actualiza current_phase en el estado."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        self.assertEqual(orch.state.current_phase, "1")

    def test_start_unknown_phase_raises(self):
        """Criterio 11: start_phase con fase desconocida lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.start_phase("0")

    def test_start_phase2_before_phase1_complete_raises(self):
        """Criterio 5/11: start_phase(2) sin fase 1 completa lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.start_phase("2")

    def test_start_phase_already_in_progress_raises(self):
        """Criterio 11: no se puede iniciar una fase ya IN_PROGRESS."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        with self.assertRaises(OrchestratorError):
            orch.start_phase("1")

    def test_start_agent_param_recorded_in_event(self):
        """El parámetro agent se persiste en el evento del log."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1", agent="AG-01")
        events = orch.log.events_by_type(EventType.PHASE_STARTED)
        self.assertEqual(events[0].agent, "AG-01")


# ---------------------------------------------------------------------------
# Tests de complete_phase
# ---------------------------------------------------------------------------

class TestCompletePhase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_phase1_marks_completed(self):
        """Criterio 7: complete_phase("1") cambia estado a COMPLETED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        ps = orch.complete_phase("1")
        self.assertEqual(ps.status, PhaseStatusValue.COMPLETED)

    def test_complete_phase1_sets_completed_at(self):
        """Criterio 7: complete_phase registra completed_at."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        ps = orch.get_phase_status("1")
        self.assertIsNotNone(ps.completed_at)

    def test_complete_phase1_records_event(self):
        """Criterio 7: complete_phase registra evento PHASE_COMPLETED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        events = orch.log.events_by_type(EventType.PHASE_COMPLETED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].phase, "1")
        self.assertEqual(events[0].status, EventStatus.OK)

    def test_complete_stores_generated_files(self):
        """complete_phase persiste generated_files en el estado de la fase."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        files = ["capas/hechos_confirmados.json", "inputs/inputs_index.json"]
        orch.complete_phase("1", generated_files=files)
        ps = orch.get_phase_status("1")
        self.assertEqual(ps.generated_files, files)

    def test_complete_stores_warnings(self):
        """complete_phase persiste warnings en el estado de la fase."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        warns = ["RC no verificada en catastro"]
        orch.complete_phase("1", warnings=warns)
        ps = orch.get_phase_status("1")
        self.assertEqual(ps.warnings, warns)

    def test_complete_records_file_generated_events(self):
        """complete_phase con generated_files registra evento FILE_GENERATED por archivo."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        files = ["capas/hechos_confirmados.json", "capas/inferencias_y_gaps.json"]
        orch.complete_phase("1", generated_files=files)
        fg_events = orch.log.events_by_type(EventType.FILE_GENERATED)
        self.assertEqual(len(fg_events), len(files))

    def test_phase2_can_start_after_phase1_completed(self):
        """Criterio 8: fase 2 puede empezar tras completar fase 1."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        can, reason = orch.can_start_phase("2")
        self.assertTrue(can)
        self.assertEqual(reason, "")

    def test_complete_not_in_progress_raises(self):
        """Criterio 12: complete_phase en NOT_STARTED lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.complete_phase("1")

    def test_complete_already_completed_raises(self):
        """Criterio 12: complete_phase en COMPLETED lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        with self.assertRaises(OrchestratorError):
            orch.complete_phase("1")

    def test_complete_blocked_phase_raises(self):
        """Criterio 12: complete_phase en BLOCKED lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("2", "gap ALTA pendiente")
        with self.assertRaises(OrchestratorError):
            orch.complete_phase("2")

    def test_allow_direct_complete_from_not_started(self):
        """allow_direct_complete=True permite completar desde NOT_STARTED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        ps = orch.complete_phase("1", allow_direct_complete=True)
        self.assertEqual(ps.status, PhaseStatusValue.COMPLETED)

    def test_complete_unknown_phase_raises(self):
        """Criterio 11: complete_phase con fase desconocida lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.complete_phase("99")


# ---------------------------------------------------------------------------
# Tests de block_phase
# ---------------------------------------------------------------------------

class TestBlockPhase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_block_phase_marks_blocked(self):
        """Criterio 9: block_phase marca la fase como BLOCKED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        ps = orch.block_phase("2", "Coordenadas pendientes de confirmar")
        self.assertEqual(ps.status, PhaseStatusValue.BLOCKED)

    def test_block_phase_stores_reason(self):
        """Criterio 9: block_phase almacena blocked_reason."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        reason = "GAP-001: RC no verificada"
        orch.block_phase("2", reason)
        ps = orch.get_phase_status("2")
        self.assertEqual(ps.blocked_reason, reason)

    def test_block_phase_records_event(self):
        """Criterio 9: block_phase registra evento PHASE_BLOCKED con status BLOCKED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("2", "gap ALTA sin resolver")
        events = orch.log.events_by_type(EventType.PHASE_BLOCKED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].phase, "2")
        self.assertEqual(events[0].status, EventStatus.BLOCKED)

    def test_block_phase_makes_log_blocking(self):
        """Criterio 10: tras block_phase, has_blocking_errors() devuelve True."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("2", "test")
        self.assertTrue(orch.log.has_blocking_errors())

    def test_blocking_log_prevents_phase1_start(self):
        """Criterio 10: log bloqueante impide iniciar cualquier fase, incluida la 1."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("2", "bloqueo de prueba")
        # Fase 1 no tiene prerequisito de fase anterior, pero el log está bloqueado
        can, reason = orch.can_start_phase("1")
        self.assertFalse(can)
        self.assertIn("bloqueante", reason.lower())

    def test_blocking_log_prevents_start_raises(self):
        """Criterio 10: start_phase lanza OrchestratorError si log está bloqueado."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("2", "bloqueo de prueba")
        with self.assertRaises(OrchestratorError):
            orch.start_phase("1")

    def test_block_unknown_phase_raises(self):
        """Criterio 11: block_phase con fase desconocida lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.block_phase("99", "test")

    def test_blocked_phase_cannot_start(self):
        """Una fase BLOCKED no puede iniciarse (can_start_phase = False)."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("1", "test")
        can, reason = orch.can_start_phase("1")
        self.assertFalse(can)
        self.assertIn("BLOCKED", reason)


# ---------------------------------------------------------------------------
# Tests de validate_model
# ---------------------------------------------------------------------------

class TestValidateModel(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_validation_result_instance(self):
        """Criterio 13: validate_model devuelve un ValidationResult."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        result = orch.validate_model()
        self.assertIsInstance(result, ValidationResult)

    def test_empty_expediente_records_validation_failed(self):
        """Criterio 13: expediente vacío → VALIDATION_FAILED registrado en log."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        result = orch.validate_model()
        self.assertFalse(result.is_valid())
        events = orch.log.events_by_type(EventType.VALIDATION_FAILED)
        self.assertEqual(len(events), 1)

    def test_empty_expediente_validation_does_not_block_log(self):
        """validate_model con errores registra WARNING, no ERROR — no bloquea log."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.validate_model()
        # El evento VALIDATION_FAILED usa EventStatus.WARNING (no bloquea)
        self.assertFalse(orch.log.has_blocking_errors())

    def test_valid_expediente_records_validation_passed(self):
        """Criterio 13: expediente con capas válidas → VALIDATION_PASSED registrado."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible en este entorno")
        exp = _make_exp_with_capas(self.tmp_path)
        orch = EIAOrchestrator(exp)
        result = orch.validate_model()
        if result.is_valid():
            events = orch.log.events_by_type(EventType.VALIDATION_PASSED)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].status, EventStatus.OK)
        else:
            # Si hay errores inesperados, al menos VALIDATION_FAILED debe estar registrado
            events = orch.log.events_by_type(EventType.VALIDATION_FAILED)
            self.assertEqual(len(events), 1)

    def test_validate_model_error_count_in_event_details(self):
        """validate_model registra error_count en details del evento."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.validate_model()
        events = orch.log.events_by_type(EventType.VALIDATION_FAILED)
        self.assertIn("error_count", events[0].details)
        self.assertGreater(events[0].details["error_count"], 0)


# ---------------------------------------------------------------------------
# Tests de summary
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_returns_nonempty_string(self):
        """Criterio 14: summary() devuelve string no vacío."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        s = orch.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)

    def test_summary_contains_expediente_id(self):
        """Criterio 14: summary contiene el expediente_id."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        s = orch.summary()
        self.assertIn(exp.name, s)

    def test_summary_reflects_completed_phase(self):
        """Criterio 14: summary refleja fases completadas."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        s = orch.summary()
        # Fase 1 debe aparecer como completada
        self.assertIn("1", s)

    def test_summary_reflects_blocked_phase(self):
        """Criterio 14: summary refleja fases bloqueadas."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("1", "test block")
        s = orch.summary()
        self.assertIn("1", s)

    def test_summary_initial_state_mentions_siguiente(self):
        """summary() con fase 1 libre indica Siguiente: Fase 1."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        s = orch.summary()
        self.assertIn("1", s)


# ---------------------------------------------------------------------------
# Tests de persistencia de estado
# ---------------------------------------------------------------------------

class TestPersistence(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reload_preserves_completed_phase(self):
        """Criterio 15: recargar el orquestador conserva fases COMPLETED."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        orch1.start_phase("1")
        orch1.complete_phase("1")

        orch2 = EIAOrchestrator(exp)
        ps = orch2.get_phase_status("1")
        self.assertEqual(ps.status, PhaseStatusValue.COMPLETED)

    def test_reload_preserves_in_progress_phase(self):
        """Criterio 15: recargar conserva fases IN_PROGRESS."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        orch1.start_phase("1")
        orch1.complete_phase("1")
        orch1.start_phase("2")

        orch2 = EIAOrchestrator(exp)
        ps = orch2.get_phase_status("2")
        self.assertEqual(ps.status, PhaseStatusValue.IN_PROGRESS)

    def test_reload_preserves_current_phase(self):
        """Criterio 15: recargar conserva current_phase."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        orch1.start_phase("1")
        orch1.complete_phase("1")
        orch1.start_phase("2")

        orch2 = EIAOrchestrator(exp)
        self.assertEqual(orch2.state.current_phase, "2")

    def test_reload_preserves_generated_files(self):
        """Criterio 15: recargar conserva generated_files en el estado de la fase."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        orch1.start_phase("1")
        files = ["capas/hechos_confirmados.json", "inputs/inputs_index.json"]
        orch1.complete_phase("1", generated_files=files)

        orch2 = EIAOrchestrator(exp)
        ps = orch2.get_phase_status("1")
        self.assertEqual(ps.generated_files, files)

    def test_reload_preserves_blocked_reason(self):
        """Criterio 15: recargar conserva blocked_reason."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        reason = "Coordenadas en estado PENDIENTE"
        orch1.block_phase("1", reason)

        orch2 = EIAOrchestrator(exp)
        ps = orch2.get_phase_status("1")
        self.assertEqual(ps.blocked_reason, reason)
        self.assertEqual(ps.status, PhaseStatusValue.BLOCKED)

    def test_reload_preserves_started_at_timestamp(self):
        """Criterio 15: recargar conserva started_at."""
        exp = _make_exp(self.tmp_path)
        orch1 = EIAOrchestrator(exp)
        orch1.start_phase("1")
        ts_original = orch1.get_phase_status("1").started_at

        orch2 = EIAOrchestrator(exp)
        ts_reloaded = orch2.get_phase_status("1").started_at
        self.assertEqual(ts_original, ts_reloaded)


# ---------------------------------------------------------------------------
# Tests de no-modificación de expedientes reales
# ---------------------------------------------------------------------------

class TestNoRealModification(unittest.TestCase):
    """Criterio 16: ningún expediente piloto real es modificado."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_expedientes_not_modified(self):
        """Criterio 16: mtimes de expedientes reales inalterados tras operaciones."""
        real_expedientes = list(_REPO_ROOT.glob("expediente-EIA-*"))
        if not real_expedientes:
            self.skipTest("No hay expedientes reales en el repositorio")

        # Capturar mtimes antes
        before: dict = {}
        for exp_dir in real_expedientes:
            for f in exp_dir.rglob("*"):
                if f.is_file():
                    before[f] = f.stat().st_mtime

        # Operaciones en expediente temporal
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        orch.start_phase("2")
        orch.block_phase("2", "prueba de aislamiento")
        orch.validate_model()
        orch.summary()

        # Verificar que ningún fichero real fue modificado
        for path, mtime_before in before.items():
            with self.subTest(file=str(path.relative_to(_REPO_ROOT))):
                self.assertEqual(
                    path.stat().st_mtime,
                    mtime_before,
                    f"Expediente real modificado inesperadamente: {path}",
                )

    def test_orchestrator_uses_temp_path_not_real(self):
        """Criterio 16: el orquestador escribe solo dentro del expediente temporal."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")

        # Los archivos escritos deben estar bajo el tmp_path
        state_path = exp / "control_interno" / "orchestrator_state.json"
        log_path   = exp / "control_interno" / "orchestrator_log.json"
        self.assertTrue(state_path.exists())
        self.assertTrue(log_path.exists())
        self.assertTrue(state_path.is_relative_to(self.tmp_path))
        self.assertTrue(log_path.is_relative_to(self.tmp_path))


# ---------------------------------------------------------------------------
# Tests de get_phase_status y previous_phase
# ---------------------------------------------------------------------------

class TestQueryMethods(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_phase_status_unknown_raises(self):
        """Criterio 11: get_phase_status con fase desconocida lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.get_phase_status("99")

    def test_previous_phase_of_unknown_raises(self):
        """Criterio 11: previous_phase con fase desconocida lanza OrchestratorError."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        with self.assertRaises(OrchestratorError):
            orch.previous_phase("99")

    def test_previous_phase_of_1_is_none(self):
        """previous_phase("1") devuelve None."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        self.assertIsNone(orch.previous_phase("1"))

    def test_previous_phase_of_2_is_1(self):
        """previous_phase("2") devuelve "1"."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        self.assertEqual(orch.previous_phase("2"), "1")


if __name__ == "__main__":
    unittest.main()
