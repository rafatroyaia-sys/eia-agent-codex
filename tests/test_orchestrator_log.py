"""
Tests NL-06 -- orchestrator_log.py
Ejecutar: venv/Scripts/python -m unittest tests.test_orchestrator_log
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.orchestrator_log import (
    EventStatus,
    EventType,
    OrchestratorEvent,
    OrchestratorLog,
    generate_event_id,
    now_iso,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmp_expediente(name: str = "expediente-TEST-001") -> tuple:
    """Crea un directorio temporal simulando un expediente. Devuelve (tmp_root, exp_path)."""
    tmp = Path(tempfile.mkdtemp())
    exp = tmp / name
    exp.mkdir()
    return tmp, exp


# ---------------------------------------------------------------------------
# now_iso
# ---------------------------------------------------------------------------

class TestNowIso(unittest.TestCase):

    def test_formato_iso(self):
        ts = now_iso()
        # Debe tener el patron YYYY-MM-DDTHH:MM:SSZ
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_es_string(self):
        self.assertIsInstance(now_iso(), str)

    def test_longitud_esperada(self):
        self.assertEqual(len(now_iso()), 20)


# ---------------------------------------------------------------------------
# generate_event_id
# ---------------------------------------------------------------------------

class TestGenerateEventId(unittest.TestCase):

    def test_primer_evento_es_ev0001(self):
        self.assertEqual(generate_event_id([]), "EV-0001")

    def test_segundo_evento_es_ev0002(self):
        ev = OrchestratorEvent(
            event_id="EV-0001", timestamp="", expediente_id="x",
            event_type=EventType.MANUAL_NOTE, status=EventStatus.INFO,
            message="",
        )
        self.assertEqual(generate_event_id([ev]), "EV-0002")

    def test_incremento_desde_maximo(self):
        events = [
            OrchestratorEvent(
                event_id=f"EV-{n:04d}", timestamp="", expediente_id="x",
                event_type=EventType.MANUAL_NOTE, status=EventStatus.INFO,
                message="",
            )
            for n in [1, 5, 3]
        ]
        self.assertEqual(generate_event_id(events), "EV-0006")

    def test_id_con_formato_invalido_no_rompe(self):
        ev = OrchestratorEvent(
            event_id="ID-RARO", timestamp="", expediente_id="x",
            event_type=EventType.MANUAL_NOTE, status=EventStatus.INFO,
            message="",
        )
        result = generate_event_id([ev])
        self.assertTrue(result.startswith("EV-"))


# ---------------------------------------------------------------------------
# OrchestratorEvent
# ---------------------------------------------------------------------------

class TestOrchestratorEvent(unittest.TestCase):

    def _make_event(self, status: str) -> OrchestratorEvent:
        return OrchestratorEvent(
            event_id="EV-0001",
            timestamp=now_iso(),
            expediente_id="EXP-001",
            event_type=EventType.PHASE_STARTED,
            status=status,
            message="mensaje de prueba",
        )

    def test_is_blocking_error(self):
        self.assertTrue(self._make_event(EventStatus.ERROR).is_blocking())

    def test_is_blocking_blocked(self):
        self.assertTrue(self._make_event(EventStatus.BLOCKED).is_blocking())

    def test_is_not_blocking_ok(self):
        self.assertFalse(self._make_event(EventStatus.OK).is_blocking())

    def test_is_not_blocking_warning(self):
        self.assertFalse(self._make_event(EventStatus.WARNING).is_blocking())

    def test_is_not_blocking_info(self):
        self.assertFalse(self._make_event(EventStatus.INFO).is_blocking())

    def test_to_dict_contiene_campos(self):
        ev = self._make_event(EventStatus.OK)
        d = ev.to_dict()
        for campo in ("event_id", "timestamp", "expediente_id", "event_type", "status", "message"):
            self.assertIn(campo, d)

    def test_from_dict_roundtrip(self):
        ev = OrchestratorEvent(
            event_id="EV-0007",
            timestamp="2026-04-20T10:00:00Z",
            expediente_id="EXP-NAVE-222",
            event_type=EventType.GATE_PASSED,
            status=EventStatus.OK,
            message="Gate 2 superado",
            phase="Fase 2",
            agent="AG-04",
            details={"gate": "2", "campo": "coordenadas"},
            files=["control_interno/ficha_objeto_evaluado.md"],
        )
        d = ev.to_dict()
        ev2 = OrchestratorEvent.from_dict(d)
        self.assertEqual(ev.event_id, ev2.event_id)
        self.assertEqual(ev.phase, ev2.phase)
        self.assertEqual(ev.agent, ev2.agent)
        self.assertEqual(ev.details, ev2.details)
        self.assertEqual(ev.files, ev2.files)

    def test_defaults_opcionales(self):
        ev = OrchestratorEvent(
            event_id="EV-0001", timestamp="2026-01-01T00:00:00Z",
            expediente_id="X", event_type=EventType.MANUAL_NOTE,
            status=EventStatus.INFO, message="ok",
        )
        self.assertIsNone(ev.phase)
        self.assertIsNone(ev.agent)
        self.assertEqual(ev.details, {})
        self.assertEqual(ev.files, [])


# ---------------------------------------------------------------------------
# OrchestratorLog — creacion y persistencia
# ---------------------------------------------------------------------------

class TestOrchestratorLogCreacion(unittest.TestCase):

    def setUp(self):
        self.tmp, self.exp = _make_tmp_expediente()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_log_nuevo_sin_eventos(self):
        log = OrchestratorLog(self.exp)
        self.assertEqual(log.all_events(), [])

    def test_directorio_control_interno_se_crea(self):
        """control_interno/ debe crearse automaticamente al guardar."""
        log = OrchestratorLog(self.exp)
        self.assertFalse((self.exp / "control_interno").exists())
        log.record_event(
            event_type=EventType.MANUAL_NOTE,
            status=EventStatus.INFO,
            message="primer evento",
        )
        self.assertTrue((self.exp / "control_interno").exists())

    def test_archivo_log_se_crea_al_guardar(self):
        log = OrchestratorLog(self.exp)
        log.record_event(
            event_type=EventType.PHASE_STARTED,
            status=EventStatus.OK,
            message="inicio",
        )
        self.assertTrue(log.log_path.exists())

    def test_archivo_es_json_valido(self):
        log = OrchestratorLog(self.exp)
        log.record_event(
            event_type=EventType.MANUAL_NOTE,
            status=EventStatus.INFO,
            message="nota con caracter especial: accion",
        )
        raw = log.log_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertIsInstance(data, list)

    def test_archivo_es_utf8(self):
        log = OrchestratorLog(self.exp)
        log.record_event(
            event_type=EventType.MANUAL_NOTE,
            status=EventStatus.INFO,
            message="accion con tilde: evaluacion ambiental",
        )
        raw = log.log_path.read_bytes()
        decoded = raw.decode("utf-8")
        self.assertIn("evaluacion", decoded)

    def test_log_path_correcto(self):
        log = OrchestratorLog(self.exp)
        expected = (self.exp / "control_interno" / "orchestrator_log.json").resolve()
        self.assertEqual(log.log_path.resolve(), expected)

    def test_expediente_id_es_nombre_directorio(self):
        log = OrchestratorLog(self.exp)
        self.assertEqual(log.expediente_id, self.exp.name)


# ---------------------------------------------------------------------------
# OrchestratorLog — añadir y recargar eventos
# ---------------------------------------------------------------------------

class TestOrchestratorLogEventos(unittest.TestCase):

    def setUp(self):
        self.tmp, self.exp = _make_tmp_expediente()
        self.log = OrchestratorLog(self.exp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_event_devuelve_event(self):
        ev = self.log.record_event(
            event_type=EventType.PHASE_STARTED,
            status=EventStatus.OK,
            message="fase 2 iniciada",
            phase="Fase 2",
        )
        self.assertIsInstance(ev, OrchestratorEvent)
        self.assertEqual(ev.event_type, EventType.PHASE_STARTED)
        self.assertEqual(ev.phase, "Fase 2")

    def test_eventos_se_acumulan(self):
        for i in range(3):
            self.log.record_event(
                event_type=EventType.MANUAL_NOTE,
                status=EventStatus.INFO,
                message=f"evento {i}",
            )
        self.assertEqual(len(self.log.all_events()), 3)

    def test_ids_son_incrementales(self):
        for _ in range(5):
            self.log.record_event(
                event_type=EventType.MANUAL_NOTE,
                status=EventStatus.INFO,
                message="ev",
            )
        ids = [e.event_id for e in self.log.all_events()]
        self.assertEqual(ids, ["EV-0001", "EV-0002", "EV-0003", "EV-0004", "EV-0005"])

    def test_recarga_desde_disco(self):
        self.log.record_event(
            event_type=EventType.PHASE_COMPLETED,
            status=EventStatus.OK,
            message="fase completada",
            phase="Fase 1",
            agent="AG-01",
        )
        # Crear nueva instancia que carga desde disco
        log2 = OrchestratorLog(self.exp)
        self.assertEqual(len(log2.all_events()), 1)
        ev = log2.all_events()[0]
        self.assertEqual(ev.event_type, EventType.PHASE_COMPLETED)
        self.assertEqual(ev.phase, "Fase 1")
        self.assertEqual(ev.agent, "AG-01")

    def test_recarga_acumula_correctamente(self):
        self.log.record_event(
            event_type=EventType.PHASE_STARTED, status=EventStatus.OK,
            message="inicio fase 1",
        )
        log2 = OrchestratorLog(self.exp)
        log2.record_event(
            event_type=EventType.PHASE_COMPLETED, status=EventStatus.OK,
            message="fin fase 1",
        )
        self.assertEqual(len(log2.all_events()), 2)
        # IDs deben ser correlativas
        ids = [e.event_id for e in log2.all_events()]
        self.assertEqual(ids, ["EV-0001", "EV-0002"])

    def test_last_event_devuelve_ultimo(self):
        self.log.record_event(
            event_type=EventType.MANUAL_NOTE, status=EventStatus.INFO,
            message="primero",
        )
        self.log.record_event(
            event_type=EventType.MANUAL_NOTE, status=EventStatus.INFO,
            message="ultimo",
        )
        self.assertEqual(self.log.last_event().message, "ultimo")

    def test_last_event_none_si_vacio(self):
        self.assertIsNone(self.log.last_event())

    def test_details_y_files_se_persisten(self):
        self.log.record_event(
            event_type=EventType.FILE_GENERATED,
            status=EventStatus.OK,
            message="archivo generado",
            details={"formato": "json", "tamano_kb": 12},
            files=["capas/hechos_confirmados.json"],
        )
        log2 = OrchestratorLog(self.exp)
        ev = log2.all_events()[0]
        self.assertEqual(ev.details["formato"], "json")
        self.assertIn("capas/hechos_confirmados.json", ev.files)


# ---------------------------------------------------------------------------
# OrchestratorLog — consultas
# ---------------------------------------------------------------------------

class TestOrchestratorLogConsultas(unittest.TestCase):

    def setUp(self):
        self.tmp, self.exp = _make_tmp_expediente()
        self.log = OrchestratorLog(self.exp)
        self.log.record_event(EventType.PHASE_STARTED, EventStatus.OK,
                              "inicio F1", phase="Fase 1", agent="AG-01")
        self.log.record_event(EventType.PHASE_COMPLETED, EventStatus.OK,
                              "fin F1", phase="Fase 1", agent="AG-03")
        self.log.record_event(EventType.PHASE_STARTED, EventStatus.OK,
                              "inicio F2", phase="Fase 2", agent="AG-04")
        self.log.record_event(EventType.GATE_FAILED, EventStatus.BLOCKED,
                              "gate 2 fallido", phase="Fase 2")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_events_by_phase(self):
        fase1 = self.log.events_by_phase("Fase 1")
        self.assertEqual(len(fase1), 2)
        self.assertTrue(all(e.phase == "Fase 1" for e in fase1))

    def test_events_by_phase_vacio_si_no_existe(self):
        self.assertEqual(self.log.events_by_phase("Fase 9"), [])

    def test_has_blocking_errors_true(self):
        self.assertTrue(self.log.has_blocking_errors())

    def test_has_blocking_errors_false_si_solo_ok(self):
        _, exp2 = _make_tmp_expediente("exp-limpio")
        try:
            log2 = OrchestratorLog(exp2)
            log2.record_event(EventType.PHASE_STARTED, EventStatus.OK, "ok")
            self.assertFalse(log2.has_blocking_errors())
        finally:
            shutil.rmtree(exp2.parent, ignore_errors=True)

    def test_has_blocking_errors_true_para_error(self):
        _, exp3 = _make_tmp_expediente("exp-error")
        try:
            log3 = OrchestratorLog(exp3)
            log3.record_event(EventType.ERROR_RECORDED, EventStatus.ERROR,
                              "error critico")
            self.assertTrue(log3.has_blocking_errors())
        finally:
            shutil.rmtree(exp3.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# OrchestratorLog — summary
# ---------------------------------------------------------------------------

class TestOrchestratorLogSummary(unittest.TestCase):

    def setUp(self):
        self.tmp, self.exp = _make_tmp_expediente()
        self.log = OrchestratorLog(self.exp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_summary_vacio(self):
        s = self.log.summary()
        self.assertIn("OK", s)
        self.assertIn("0 total", s)

    def test_summary_con_error_indica_con_errores(self):
        self.log.record_event(EventType.ERROR_RECORDED, EventStatus.ERROR,
                              "algo fallo")
        s = self.log.summary()
        self.assertIn("CON ERRORES", s)

    def test_summary_muestra_expediente_id(self):
        s = self.log.summary()
        self.assertIn(self.exp.name, s)

    def test_summary_contiene_conteo(self):
        self.log.record_event(EventType.PHASE_STARTED, EventStatus.OK, "ev1")
        self.log.record_event(EventType.WARNING_RECORDED, EventStatus.WARNING, "ev2")
        s = self.log.summary()
        self.assertIn("2 total", s)

    def test_summary_muestra_ultimos_eventos(self):
        self.log.record_event(EventType.PHASE_STARTED, EventStatus.OK,
                              "inicio de fase especial xyz")
        s = self.log.summary()
        self.assertIn("inicio de fase especial xyz", s)


# ---------------------------------------------------------------------------
# OrchestratorLog — archivo corrupto y backup
# ---------------------------------------------------------------------------

class TestOrchestratorLogCorrupto(unittest.TestCase):
    """Verifica el comportamiento cuando orchestrator_log.json existe pero
    no puede parsearse como JSON valido."""

    def setUp(self):
        self.tmp, self.exp = _make_tmp_expediente()
        ci_dir = self.exp / "control_interno"
        ci_dir.mkdir()
        self.ci_dir = ci_dir
        self.log_path = ci_dir / "orchestrator_log.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_corrupt(self, content: bytes = b"esto no es json {{{"):
        self.log_path.write_bytes(content)

    def test_archivo_inexistente_sin_load_error(self):
        """Si el archivo no existe: load_error es None y lista vacia."""
        log = OrchestratorLog(self.exp)
        self.assertIsNone(log.load_error)
        self.assertEqual(log.all_events(), [])

    def test_archivo_corrupto_load_error_no_none(self):
        """Si el archivo existe y es JSON invalido, load_error se rellena."""
        self._write_corrupt()
        log = OrchestratorLog(self.exp)
        self.assertIsNotNone(log.load_error)

    def test_archivo_corrupto_load_error_es_string(self):
        self._write_corrupt()
        log = OrchestratorLog(self.exp)
        self.assertIsInstance(log.load_error, str)
        self.assertGreater(len(log.load_error), 0)

    def test_archivo_corrupto_crea_backup(self):
        """Debe existir exactamente un archivo .corrupt.*.json tras la carga."""
        self._write_corrupt()
        OrchestratorLog(self.exp)
        backups = list(self.ci_dir.glob("orchestrator_log.corrupt.*.json"))
        self.assertEqual(len(backups), 1)

    def test_archivo_corrupto_backup_mismo_contenido(self):
        """El backup preserva el contenido exacto del archivo corrupto."""
        contenido = b"[[[ json roto"
        self._write_corrupt(contenido)
        OrchestratorLog(self.exp)
        backups = list(self.ci_dir.glob("orchestrator_log.corrupt.*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), contenido)

    def test_archivo_corrupto_original_sigue_existiendo(self):
        """El archivo original no se borra; el backup es una copia separada."""
        self._write_corrupt()
        OrchestratorLog(self.exp)
        self.assertTrue(self.log_path.exists())
        backups = list(self.ci_dir.glob("orchestrator_log.corrupt.*.json"))
        # el backup tiene un nombre distinto al original
        self.assertNotEqual(backups[0].name, self.log_path.name)

    def test_archivo_corrupto_has_blocking_errors(self):
        """Con load_error activo, has_blocking_errors() debe devolver True."""
        self._write_corrupt()
        log = OrchestratorLog(self.exp)
        self.assertTrue(log.has_blocking_errors())

    def test_archivo_corrupto_summary_menciona_advertencia(self):
        """summary() debe exponer el error de carga de forma visible."""
        self._write_corrupt()
        log = OrchestratorLog(self.exp)
        s = log.summary()
        self.assertTrue(
            any(kw in s.upper() for kw in ("ADVERTENCIA", "CORRUPTO", "ERROR")),
            msg=f"summary() no menciona el problema de carga:\n{s}",
        )

    def test_archivo_corrupto_lista_eventos_vacia(self):
        """Tras un log corrupto, la lista de eventos en memoria es vacia."""
        self._write_corrupt()
        log = OrchestratorLog(self.exp)
        self.assertEqual(log.all_events(), [])

    def test_archivo_valido_load_error_none(self):
        """Con JSON valido, load_error debe permanecer None."""
        # escribir un log valido con un evento
        payload = [{
            "event_id": "EV-0001", "timestamp": "2026-04-20T10:00:00Z",
            "expediente_id": "expediente-TEST-001",
            "event_type": "MANUAL_NOTE", "status": "INFO",
            "message": "ok", "phase": None, "agent": None,
            "details": {}, "files": [],
        }]
        self.log_path.write_text(
            __import__("json").dumps(payload), encoding="utf-8"
        )
        log = OrchestratorLog(self.exp)
        self.assertIsNone(log.load_error)
        self.assertEqual(len(log.all_events()), 1)


# ---------------------------------------------------------------------------
# EventType y EventStatus
# ---------------------------------------------------------------------------

class TestEventTypeYStatus(unittest.TestCase):

    def test_todos_los_tipos_son_validos(self):
        tipos = [
            EventType.PHASE_STARTED, EventType.PHASE_COMPLETED,
            EventType.PHASE_BLOCKED, EventType.GATE_PASSED,
            EventType.GATE_FAILED, EventType.VALIDATION_PASSED,
            EventType.VALIDATION_FAILED, EventType.FILE_GENERATED,
            EventType.WARNING_RECORDED, EventType.ERROR_RECORDED,
            EventType.MANUAL_NOTE,
        ]
        for t in tipos:
            with self.subTest(tipo=t):
                self.assertTrue(EventType.is_valid(t))

    def test_tipo_inventado_no_es_valido(self):
        self.assertFalse(EventType.is_valid("TIPO_INVENTADO"))

    def test_status_blocking(self):
        self.assertTrue(EventStatus.is_blocking(EventStatus.ERROR))
        self.assertTrue(EventStatus.is_blocking(EventStatus.BLOCKED))

    def test_status_no_blocking(self):
        for s in (EventStatus.OK, EventStatus.WARNING, EventStatus.INFO):
            with self.subTest(status=s):
                self.assertFalse(EventStatus.is_blocking(s))


if __name__ == "__main__":
    unittest.main()
