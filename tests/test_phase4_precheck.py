"""
tests/test_phase4_precheck.py — CA-08

Tests para phase4_precheck.py: precheck programático de Fase 4.
No llama a APIs. No genera mapas ni climogramas. Solo lectura.
Los pilotos PARCELA y NAVE-222 se usan en modo solo lectura.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.phase4_precheck import (
    Phase4PrecheckIssue,
    Phase4PrecheckResult,
    _check_api_keys,
    _check_api_keys_issues,
    _check_coordinates,
    _check_rc,
    _looks_like_rc,
    _parse_wgs84_coord,
    run_phase4_precheck,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SCOPE_CON_WGS84: dict = {
    "titular": "Empresa Test SL",
    "referencia_catastral": "1234567AB1234A0001LP",
    "coordenadas_wgs84": ["28.1, -15.4"],
    "coordenadas_utm": [],
    "operaciones_incluidas": ["R1201"],
    "operaciones_excluidas": [],
    "modo": "GABINETE",
    "at_activos": [],
    "gaps": [],
    "superficie_m2": "5000",
    "capacidad": "25000 t/ano",
}

_SCOPE_CON_UTM: dict = {
    "titular": "Empresa Test SL",
    "referencia_catastral": "1234567AB1234A0001LP",
    "coordenadas_wgs84": [],
    "coordenadas_utm": ["456789.1, 3109876.2"],
    "operaciones_incluidas": [],
    "operaciones_excluidas": [],
    "modo": "GABINETE",
    "at_activos": [],
    "gaps": [],
    "superficie_m2": None,
    "capacidad": None,
}

_SCOPE_SIN_COORDS: dict = {
    "titular": "Empresa Test SL",
    "referencia_catastral": "1234567AB1234A0001LP",
    "coordenadas_wgs84": [],
    "coordenadas_utm": [],
    "operaciones_incluidas": [],
    "operaciones_excluidas": [],
    "modo": "NO_DECLARADO",
    "at_activos": [],
    "gaps": [],
    "superficie_m2": None,
    "capacidad": None,
}

_SCOPE_SIN_RC: dict = {
    "titular": "Empresa Test SL",
    "referencia_catastral": "",
    "coordenadas_wgs84": ["28.1, -15.4"],
    "coordenadas_utm": [],
    "operaciones_incluidas": [],
    "operaciones_excluidas": [],
    "modo": "GABINETE",
    "at_activos": [],
    "gaps": [],
    "superficie_m2": None,
    "capacidad": None,
}

_SCOPE_RC_INVALIDA: dict = {
    "titular": "Empresa Test SL",
    "referencia_catastral": "INVALIDA",
    "coordenadas_wgs84": ["28.1, -15.4"],
    "coordenadas_utm": [],
    "operaciones_incluidas": [],
    "operaciones_excluidas": [],
    "modo": "GABINETE",
    "at_activos": [],
    "gaps": [],
    "superficie_m2": None,
    "capacidad": None,
}

_PHASE2_MINIMO: dict = {
    "expediente_id": "test-expediente",
    "object_scope": _SCOPE_CON_WGS84,
    "gate2_passed": True,
    "gate2_summary": "Gate 2 APTO",
    "issues": [],
    "warnings": [],
}

_PHASE2_SIN_COORDS: dict = {
    "expediente_id": "test-expediente",
    "object_scope": _SCOPE_SIN_COORDS,
    "gate2_passed": False,
    "gate2_summary": "Gate 2 BLOQUEADO",
    "issues": [{"severity": "ERROR", "code": "G2-E001", "message": "Sin coords"}],
    "warnings": [],
}

_PHASE2_CON_UTM: dict = {
    "expediente_id": "test-expediente",
    "object_scope": _SCOPE_CON_UTM,
    "gate2_passed": True,
    "gate2_summary": "Gate 2 APTO",
    "issues": [],
    "warnings": [],
}

_PHASE2_SIN_RC: dict = {
    "expediente_id": "test-expediente",
    "object_scope": _SCOPE_SIN_RC,
    "gate2_passed": True,
    "gate2_summary": "Gate 2 APTO (sin RC)",
    "issues": [],
    "warnings": [],
}

_PHASE2_RC_INVALIDA: dict = {
    "expediente_id": "test-expediente",
    "object_scope": _SCOPE_RC_INVALIDA,
    "gate2_passed": False,
    "gate2_summary": "Gate 2 BLOQUEADO",
    "issues": [],
    "warnings": [],
}


def _write_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestPhase4PrecheckIssueStructure
# ---------------------------------------------------------------------------

class TestPhase4PrecheckIssueStructure(unittest.TestCase):
    def _make(self) -> Phase4PrecheckIssue:
        return Phase4PrecheckIssue(
            severity="ERROR",
            code="P4-E001",
            message="Sin coordenadas",
            field="coordenadas_wgs84",
            recommendation="Declare coordenadas",
        )

    def test_fields(self):
        i = self._make()
        self.assertEqual(i.severity, "ERROR")
        self.assertEqual(i.code, "P4-E001")

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        for k in ("severity", "code", "message", "field", "recommendation"):
            self.assertIn(k, d)

    def test_optional_fields_none(self):
        i = Phase4PrecheckIssue(severity="INFO", code="P4-I001", message="msg")
        self.assertIsNone(i.field)
        self.assertIsNone(i.recommendation)
        self.assertIsNone(i.to_dict()["field"])


# ---------------------------------------------------------------------------
# TestPhase4PrecheckResultStructure
# ---------------------------------------------------------------------------

class TestPhase4PrecheckResultStructure(unittest.TestCase):
    def _make(self, errors=0, warnings=0, infos=0) -> Phase4PrecheckResult:
        issues = []
        for _ in range(errors):
            issues.append(Phase4PrecheckIssue("ERROR", "E", "error msg"))
        for _ in range(warnings):
            issues.append(Phase4PrecheckIssue("WARNING", "W", "warn msg"))
        for _ in range(infos):
            issues.append(Phase4PrecheckIssue("INFO", "I", "info msg"))
        return Phase4PrecheckResult(
            expediente_id="test-exp",
            ready_for_cartography=True,
            ready_for_climate=True,
            ready_for_phase4=(errors == 0),
            coordinates_status="OK",
            rc_status="OK",
            api_keys_status={"AEMET_API_KEY": True, "MAPBOX_TOKEN": False},
            required_maps=["MAP-001", "MAP-002"],
            required_climate_outputs=["climograma"],
            issues=issues,
            warnings=["aviso-test"],
            notes=["nota-test"],
        )

    def test_error_count(self):
        r = self._make(errors=2, warnings=1)
        self.assertEqual(r.error_count(), 2)

    def test_warning_count(self):
        r = self._make(errors=1, warnings=3)
        self.assertEqual(r.warning_count(), 3)

    def test_info_count(self):
        r = self._make(infos=4)
        self.assertEqual(r.info_count(), 4)

    def test_summary_contains_expediente(self):
        self.assertIn("test-exp", self._make().summary())

    def test_summary_contains_cartography_si(self):
        r = self._make()
        self.assertIn("SI", r.summary())

    def test_summary_contains_error_count(self):
        r = self._make(errors=3)
        self.assertIn("3", r.summary())

    def test_summary_contains_api_keys(self):
        r = self._make()
        self.assertIn("AEMET_API_KEY", r.summary())

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        for k in (
            "expediente_id", "ready_for_cartography", "ready_for_climate",
            "ready_for_phase4", "coordinates_status", "rc_status",
            "api_keys_status", "required_maps", "required_climate_outputs",
            "issues", "warnings", "notes",
        ):
            self.assertIn(k, d)

    def test_to_dict_issues_list(self):
        r = self._make(errors=1)
        d = r.to_dict()
        self.assertIsInstance(d["issues"], list)
        self.assertIsInstance(d["issues"][0], dict)

    def test_to_dict_json_serializable(self):
        r = self._make(errors=1, warnings=2, infos=1)
        json.dumps(r.to_dict())  # no excepción


# ---------------------------------------------------------------------------
# TestHelperFunctions
# ---------------------------------------------------------------------------

class TestHelperFunctions(unittest.TestCase):
    def test_parse_wgs84_valid(self):
        result = _parse_wgs84_coord("28.1, -15.4")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 28.1)
        self.assertAlmostEqual(result[1], -15.4)

    def test_parse_wgs84_no_spaces(self):
        result = _parse_wgs84_coord("28.1,-15.4")
        self.assertIsNotNone(result)

    def test_parse_wgs84_invalid(self):
        self.assertIsNone(_parse_wgs84_coord("PENDIENTE"))
        self.assertIsNone(_parse_wgs84_coord("no-es-coord"))
        self.assertIsNone(_parse_wgs84_coord(""))

    def test_looks_like_rc_valid(self):
        self.assertTrue(_looks_like_rc("1234567AB1234A0001LP"))

    def test_looks_like_rc_case_insensitive(self):
        self.assertTrue(_looks_like_rc("1234567ab1234a0001lp"))

    def test_looks_like_rc_invalid_short(self):
        self.assertFalse(_looks_like_rc("1234567AB"))

    def test_looks_like_rc_invalid_all_digits(self):
        self.assertFalse(_looks_like_rc("12345678901234567890"))

    def test_looks_like_rc_empty(self):
        self.assertFalse(_looks_like_rc(""))


# ---------------------------------------------------------------------------
# TestCheckCoordinates
# ---------------------------------------------------------------------------

class TestCheckCoordinates(unittest.TestCase):
    def _run(self, scope: dict) -> tuple:
        issues: list = []
        warnings: list = []
        has_loc, status = _check_coordinates(scope, issues, warnings)
        return has_loc, status, issues, warnings

    def test_no_coords_error(self):
        has_loc, status, issues, _ = self._run({"coordenadas_wgs84": [], "coordenadas_utm": []})
        self.assertFalse(has_loc)
        self.assertEqual(status, "ABSENT")
        self.assertEqual(len([i for i in issues if i.code == "P4-E001"]), 1)

    def test_wgs84_present_ok(self):
        has_loc, status, issues, _ = self._run({"coordenadas_wgs84": ["28.1, -15.4"], "coordenadas_utm": []})
        self.assertTrue(has_loc)
        self.assertEqual(status, "OK")
        self.assertEqual(len([i for i in issues if i.severity == "ERROR"]), 0)

    def test_utm_present_ok(self):
        has_loc, status, issues, _ = self._run({"coordenadas_wgs84": [], "coordenadas_utm": ["456789, 3109876"]})
        self.assertTrue(has_loc)
        self.assertEqual(status, "OK")

    def test_pendiente_marker_warning(self):
        has_loc, status, issues, warnings = self._run(
            {"coordenadas_wgs84": ["PENDIENTE"], "coordenadas_utm": []}
        )
        self.assertTrue(has_loc)
        self.assertEqual(status, "WARNING")
        codes = [i.code for i in issues]
        self.assertIn("P4-W001", codes)

    def test_estimado_marker_warning(self):
        has_loc, status, issues, _ = self._run(
            {"coordenadas_wgs84": ["ESTIMADO 28.1"], "coordenadas_utm": []}
        )
        self.assertEqual(status, "WARNING")
        self.assertIn("P4-W001", [i.code for i in issues])

    def test_invalid_format_warning(self):
        has_loc, status, issues, _ = self._run(
            {"coordenadas_wgs84": ["no-es-un-numero"], "coordenadas_utm": []}
        )
        self.assertTrue(has_loc)
        self.assertEqual(status, "WARNING")
        self.assertIn("P4-W002", [i.code for i in issues])

    def test_none_coords_treated_as_empty(self):
        has_loc, status, issues, _ = self._run(
            {"coordenadas_wgs84": None, "coordenadas_utm": None}
        )
        self.assertFalse(has_loc)
        self.assertEqual(status, "ABSENT")

    def test_missing_key_treated_as_empty(self):
        has_loc, status, _, _ = self._run({})
        self.assertFalse(has_loc)
        self.assertEqual(status, "ABSENT")


# ---------------------------------------------------------------------------
# TestCheckRC
# ---------------------------------------------------------------------------

class TestCheckRC(unittest.TestCase):
    def _run(self, scope: dict) -> tuple:
        issues: list = []
        warnings: list = []
        status = _check_rc(scope, issues, warnings)
        return status, issues, warnings

    def test_valid_rc_ok(self):
        status, issues, _ = self._run({"referencia_catastral": "1234567AB1234A0001LP"})
        self.assertEqual(status, "OK")
        self.assertEqual(len(issues), 0)

    def test_absent_rc_warning(self):
        status, issues, warnings = self._run({"referencia_catastral": ""})
        self.assertEqual(status, "ABSENT")
        self.assertIn("P4-W003", [i.code for i in issues])
        self.assertTrue(len(warnings) > 0)

    def test_missing_key_warning(self):
        status, issues, _ = self._run({})
        self.assertEqual(status, "ABSENT")
        self.assertIn("P4-W003", [i.code for i in issues])

    def test_invalid_rc_error(self):
        status, issues, _ = self._run({"referencia_catastral": "INVALIDA"})
        self.assertEqual(status, "INVALID")
        self.assertIn("P4-E002", [i.code for i in issues])
        self.assertEqual([i.severity for i in issues if i.code == "P4-E002"], ["ERROR"])

    def test_none_rc_warning(self):
        status, issues, _ = self._run({"referencia_catastral": None})
        self.assertEqual(status, "ABSENT")


# ---------------------------------------------------------------------------
# TestCheckAPIKeys
# ---------------------------------------------------------------------------

class TestCheckAPIKeys(unittest.TestCase):
    def test_both_present(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "key123", "MAPBOX_TOKEN": "tok456"}):
            keys = _check_api_keys()
        self.assertTrue(keys["AEMET_API_KEY"])
        self.assertTrue(keys["MAPBOX_TOKEN"])

    def test_both_absent(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            keys = _check_api_keys()
        self.assertFalse(keys["AEMET_API_KEY"])
        self.assertFalse(keys["MAPBOX_TOKEN"])

    def test_empty_string_treated_as_absent(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "   ", "MAPBOX_TOKEN": ""}):
            keys = _check_api_keys()
        self.assertFalse(keys["AEMET_API_KEY"])
        self.assertFalse(keys["MAPBOX_TOKEN"])

    def test_aemet_absent_generates_warning(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            keys = _check_api_keys()
            issues: list = []
            warnings: list = []
            _check_api_keys_issues(keys, issues, warnings)
        codes = [i.code for i in issues]
        self.assertIn("P4-W004", codes)
        self.assertIn("P4-W005", codes)
        # No ERRORs — only WARNINGs
        self.assertEqual([i.severity for i in issues], ["WARNING", "WARNING"])

    def test_aemet_present_no_warning(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "key", "MAPBOX_TOKEN": "tok"}):
            keys = _check_api_keys()
            issues: list = []
            warnings: list = []
            _check_api_keys_issues(keys, issues, warnings)
        self.assertEqual(len(issues), 0)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckSinPhase2
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckSinPhase2(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-test"
        self.exp.mkdir()
        (self.exp / "control_interno").mkdir()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_error_p4_e005_presente(self):
        result = run_phase4_precheck(self.exp)
        codes = [i.code for i in result.issues]
        self.assertIn("P4-E005", codes)

    def test_error_es_severity_error(self):
        result = run_phase4_precheck(self.exp)
        e005 = next(i for i in result.issues if i.code == "P4-E005")
        self.assertEqual(e005.severity, "ERROR")

    def test_ready_for_cartography_false(self):
        result = run_phase4_precheck(self.exp)
        self.assertFalse(result.ready_for_cartography)

    def test_ready_for_climate_false(self):
        result = run_phase4_precheck(self.exp)
        self.assertFalse(result.ready_for_climate)

    def test_ready_for_phase4_false(self):
        result = run_phase4_precheck(self.exp)
        self.assertFalse(result.ready_for_phase4)

    def test_coords_status_absent(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.coordinates_status, "ABSENT")

    def test_rc_status_absent(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.rc_status, "ABSENT")

    def test_explicit_path_missing(self):
        missing = self.exp / "no_existe.json"
        result = run_phase4_precheck(self.exp, phase2_result_path=missing)
        codes = [i.code for i in result.issues]
        self.assertIn("P4-E005", codes)

    def test_error_count_positive(self):
        result = run_phase4_precheck(self.exp)
        self.assertGreater(result.error_count(), 0)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckSinCoordenadas
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckSinCoordenadas(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-test"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_SIN_COORDS, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ready_for_cartography_false(self):
        result = run_phase4_precheck(self.exp)
        self.assertFalse(result.ready_for_cartography)

    def test_ready_for_climate_false(self):
        result = run_phase4_precheck(self.exp)
        self.assertFalse(result.ready_for_climate)

    def test_error_p4_e001(self):
        result = run_phase4_precheck(self.exp)
        self.assertIn("P4-E001", [i.code for i in result.issues])

    def test_coordinates_status_absent(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.coordinates_status, "ABSENT")


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckConCoordenadasWGS84
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckConCoordenadasWGS84(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-test"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")
        # Ensure no phase3 and no AEMET/MAPBOX in env for clean test
        self._env_patch = patch.dict(
            os.environ,
            {k: v for k, v in os.environ.items()
             if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")},
            clear=True,
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self.tmpdir.cleanup()

    def test_ready_for_cartography_true(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(result.ready_for_cartography)

    def test_ready_for_climate_true(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(result.ready_for_climate)

    def test_coordinates_status_ok(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.coordinates_status, "OK")

    def test_rc_status_ok(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.rc_status, "OK")

    def test_no_coord_errors(self):
        result = run_phase4_precheck(self.exp)
        coord_errors = [i for i in result.issues if i.code in ("P4-E001",)]
        self.assertEqual(len(coord_errors), 0)

    def test_no_p4e005(self):
        result = run_phase4_precheck(self.exp)
        self.assertNotIn("P4-E005", [i.code for i in result.issues])


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckConCoordenadasUTM
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckConCoordenadasUTM(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-test"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_CON_UTM, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ready_for_cartography_true(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(result.ready_for_cartography)

    def test_coordinates_status_ok(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(result.coordinates_status, "OK")


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckCoordendasUnreliable
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckCoordendasUnreliable(unittest.TestCase):
    def _make_scope_with_coords(self, coords: list) -> dict:
        return {
            "titular": "Test",
            "referencia_catastral": "1234567AB1234A0001LP",
            "coordenadas_wgs84": coords,
            "coordenadas_utm": [],
            "operaciones_incluidas": [],
            "operaciones_excluidas": [],
            "modo": "GABINETE",
            "at_activos": [],
            "gaps": [],
        }

    def _run(self, coords: list) -> "Phase4PrecheckResult":
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            phase2 = {
                "expediente_id": "exp",
                "object_scope": self._make_scope_with_coords(coords),
                "gate2_passed": True,
                "gate2_summary": "test",
                "issues": [],
                "warnings": [],
            }
            _write_json(phase2, ci / "phase2_result.json")
            return run_phase4_precheck(exp)

    def test_pendiente_warning(self):
        result = self._run(["PENDIENTE"])
        self.assertIn("P4-W001", [i.code for i in result.issues])

    def test_estimado_warning(self):
        result = self._run(["ESTIMADO"])
        self.assertIn("P4-W001", [i.code for i in result.issues])

    def test_no_declarado_warning(self):
        result = self._run(["NO_DECLARADO"])
        self.assertIn("P4-W001", [i.code for i in result.issues])

    def test_provisional_warning(self):
        result = self._run(["PROVISIONAL"])
        self.assertIn("P4-W001", [i.code for i in result.issues])

    def test_unreliable_still_has_location(self):
        result = self._run(["PENDIENTE"])
        self.assertTrue(result.ready_for_cartography)

    def test_unreliable_coords_status_warning(self):
        result = self._run(["PENDIENTE"])
        self.assertEqual(result.coordinates_status, "WARNING")

    def test_invalid_format_warning(self):
        result = self._run(["no-es-numero"])
        self.assertIn("P4-W002", [i.code for i in result.issues])


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckRCCheck
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckRCCheck(unittest.TestCase):
    def _run_with_phase2(self, phase2_data: dict) -> "Phase4PrecheckResult":
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(phase2_data, ci / "phase2_result.json")
            return run_phase4_precheck(exp)

    def test_sin_rc_warning_not_error(self):
        result = self._run_with_phase2(_PHASE2_SIN_RC)
        w003 = [i for i in result.issues if i.code == "P4-W003"]
        self.assertEqual(len(w003), 1)
        self.assertEqual(w003[0].severity, "WARNING")

    def test_sin_rc_ready_for_cartography_still_true(self):
        result = self._run_with_phase2(_PHASE2_SIN_RC)
        self.assertTrue(result.ready_for_cartography)

    def test_sin_rc_rc_status_absent(self):
        result = self._run_with_phase2(_PHASE2_SIN_RC)
        self.assertEqual(result.rc_status, "ABSENT")

    def test_rc_invalida_error(self):
        result = self._run_with_phase2(_PHASE2_RC_INVALIDA)
        self.assertIn("P4-E002", [i.code for i in result.issues])

    def test_rc_invalida_ready_for_phase4_false(self):
        result = self._run_with_phase2(_PHASE2_RC_INVALIDA)
        self.assertFalse(result.ready_for_phase4)

    def test_rc_invalida_status_invalid(self):
        result = self._run_with_phase2(_PHASE2_RC_INVALIDA)
        self.assertEqual(result.rc_status, "INVALID")

    def test_rc_valida_ok(self):
        result = self._run_with_phase2(_PHASE2_MINIMO)
        self.assertEqual(result.rc_status, "OK")


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckAPIKeys
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckAPIKeys(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "exp"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_aemet_absent_warning(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            result = run_phase4_precheck(self.exp)
        self.assertIn("P4-W004", [i.code for i in result.issues])

    def test_mapbox_absent_warning(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            result = run_phase4_precheck(self.exp)
        self.assertIn("P4-W005", [i.code for i in result.issues])

    def test_aemet_absent_not_error(self):
        env = {k: v for k, v in os.environ.items() if k != "AEMET_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = run_phase4_precheck(self.exp)
        w004 = [i for i in result.issues if i.code == "P4-W004"]
        self.assertEqual(w004[0].severity, "WARNING")

    def test_mapbox_absent_not_error(self):
        env = {k: v for k, v in os.environ.items() if k != "MAPBOX_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            result = run_phase4_precheck(self.exp)
        w005 = [i for i in result.issues if i.code == "P4-W005"]
        self.assertEqual(w005[0].severity, "WARNING")

    def test_api_keys_status_dict_has_both_keys(self):
        result = run_phase4_precheck(self.exp)
        self.assertIn("AEMET_API_KEY", result.api_keys_status)
        self.assertIn("MAPBOX_TOKEN", result.api_keys_status)

    def test_aemet_present_no_w004(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "real-key"}):
            result = run_phase4_precheck(self.exp)
        self.assertNotIn("P4-W004", [i.code for i in result.issues])

    def test_mapbox_present_no_w005(self):
        with patch.dict(os.environ, {"MAPBOX_TOKEN": "real-token"}):
            result = run_phase4_precheck(self.exp)
        self.assertNotIn("P4-W005", [i.code for i in result.issues])

    def test_api_absent_does_not_block_cartography(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AEMET_API_KEY", "MAPBOX_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            result = run_phase4_precheck(self.exp)
        self.assertTrue(result.ready_for_cartography)
        self.assertTrue(result.ready_for_climate)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckRequiredOutputs
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckRequiredOutputs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "exp"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_required_maps_6_items(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(len(result.required_maps), 6)

    def test_required_maps_contains_map001(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("MAP-001" in m for m in result.required_maps))

    def test_required_maps_contains_map003(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("MAP-003" in m or "catastro" in m for m in result.required_maps))

    def test_required_maps_contains_natura(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("Natura" in m or "ENP" in m for m in result.required_maps))

    def test_required_climate_outputs_5_items(self):
        result = run_phase4_precheck(self.exp)
        self.assertEqual(len(result.required_climate_outputs), 5)

    def test_required_climate_contains_climograma(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("climograma" in c for c in result.required_climate_outputs))

    def test_required_climate_contains_tabla(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("tabla" in c for c in result.required_climate_outputs))

    def test_required_climate_contains_koppen(self):
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("Koppen" in c or "koppen" in c.lower() for c in result.required_climate_outputs))


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckPhase3Info
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckPhase3Info(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "exp"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_phase3_absent_info_issue(self):
        result = run_phase4_precheck(self.exp)
        self.assertIn("P4-I001", [i.code for i in result.issues])

    def test_phase3_absent_severity_info(self):
        result = run_phase4_precheck(self.exp)
        i001 = next(i for i in result.issues if i.code == "P4-I001")
        self.assertEqual(i001.severity, "INFO")

    def test_phase3_present_no_info(self):
        ci = self.exp / "control_interno"
        _write_json({"expediente_id": "test"}, ci / "phase3_result.json")
        result = run_phase4_precheck(self.exp)
        self.assertNotIn("P4-I001", [i.code for i in result.issues])

    def test_phase3_explicit_path_present_no_info(self):
        with tempfile.TemporaryDirectory() as tmp2:
            p3 = Path(tmp2) / "phase3_result.json"
            _write_json({"expediente_id": "test"}, p3)
            result = run_phase4_precheck(self.exp, phase3_result_path=p3)
        self.assertNotIn("P4-I001", [i.code for i in result.issues])


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckReadyForPhase4
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckReadyForPhase4(unittest.TestCase):
    def _run_with_scope(self, scope: dict) -> "Phase4PrecheckResult":
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            phase2 = {
                "expediente_id": "exp",
                "object_scope": scope,
                "gate2_passed": True,
                "gate2_summary": "test",
                "issues": [],
                "warnings": [],
            }
            _write_json(phase2, ci / "phase2_result.json")
            # Ensure phase3 exists to avoid P4-I001, but allow API key warnings
            _write_json({"expediente_id": "test"}, ci / "phase3_result.json")
            with patch.dict(os.environ, {"AEMET_API_KEY": "key", "MAPBOX_TOKEN": "tok"}):
                return run_phase4_precheck(exp)

    def test_ready_for_phase4_true_when_no_errors(self):
        result = self._run_with_scope(_SCOPE_CON_WGS84)
        self.assertEqual(result.error_count(), 0)
        self.assertTrue(result.ready_for_phase4)

    def test_ready_for_phase4_false_when_errors(self):
        result = self._run_with_scope(_SCOPE_RC_INVALIDA)
        self.assertGreater(result.error_count(), 0)
        self.assertFalse(result.ready_for_phase4)

    def test_warnings_dont_block_phase4(self):
        # No RC (WARNING) + API keys present + phase3 present
        result = self._run_with_scope(_SCOPE_SIN_RC)
        self.assertEqual(result.error_count(), 0)
        self.assertTrue(result.ready_for_phase4)

    def test_missing_phase2_blocks_phase4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            result = run_phase4_precheck(exp)
        self.assertFalse(result.ready_for_phase4)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckWriteOutputs
# ---------------------------------------------------------------------------

class TestRunPhase4PrecheckWriteOutputs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "exp"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_write_by_default(self):
        run_phase4_precheck(self.exp)
        ci = self.exp / "control_interno"
        self.assertFalse((ci / "phase4_precheck.json").exists())
        self.assertFalse((ci / "phase4_precheck.md").exists())

    def test_write_creates_json(self):
        run_phase4_precheck(self.exp, write_outputs=True)
        self.assertTrue((self.exp / "control_interno" / "phase4_precheck.json").exists())

    def test_write_creates_md(self):
        run_phase4_precheck(self.exp, write_outputs=True)
        self.assertTrue((self.exp / "control_interno" / "phase4_precheck.md").exists())

    def test_json_valid(self):
        run_phase4_precheck(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "phase4_precheck.json").read_text(encoding="utf-8")
        data = json.loads(content)
        self.assertIn("expediente_id", data)
        self.assertIn("ready_for_cartography", data)

    def test_json_fields_complete(self):
        run_phase4_precheck(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "phase4_precheck.json").read_text(encoding="utf-8")
        data = json.loads(content)
        for k in (
            "expediente_id", "ready_for_cartography", "ready_for_climate",
            "ready_for_phase4", "coordinates_status", "rc_status",
            "api_keys_status", "required_maps", "required_climate_outputs",
            "issues", "warnings", "notes",
        ):
            self.assertIn(k, data)

    def test_md_contains_header(self):
        run_phase4_precheck(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "phase4_precheck.md").read_text(encoding="utf-8")
        self.assertIn("Precheck Fase 4", content)

    def test_custom_output_dir(self):
        p2_path = self.exp / "control_interno" / "phase2_result.json"
        run_phase4_precheck(
            self.exp,
            phase2_result_path=p2_path,
            write_outputs=True,
            output_dir="salidas",
        )
        self.assertTrue((self.exp / "salidas" / "phase4_precheck.json").exists())

    def test_phase2_warnings_propagated(self):
        phase2 = dict(_PHASE2_MINIMO)
        phase2["warnings"] = ["aviso-test-fase2"]
        ci = self.exp / "control_interno"
        _write_json(phase2, ci / "phase2_result.json")
        result = run_phase4_precheck(self.exp)
        self.assertTrue(any("aviso-test-fase2" in w for w in result.warnings))

    def test_phase2_invalid_json_error(self):
        (self.exp / "control_interno" / "phase2_result.json").write_text(
            "INVALID JSON", encoding="utf-8"
        )
        result = run_phase4_precheck(self.exp)
        self.assertIn("P4-E004", [i.code for i in result.issues])


# ---------------------------------------------------------------------------
# TestCLIPhase4Precheck
# ---------------------------------------------------------------------------

class TestCLIPhase4Precheck(unittest.TestCase):
    def _run(self, *args) -> tuple[int, str, str]:
        result = subprocess.run(
            [sys.executable, "run_expediente.py"] + list(args),
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        return result.returncode, result.stdout, result.stderr

    def test_sin_phase2_exit1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp-cli"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            code, out, err = self._run(str(exp), "phase4-precheck")
            self.assertEqual(code, 1)

    def test_sin_phase2_mensaje_en_salida(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp-cli"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            code, out, err = self._run(str(exp), "phase4-precheck")
            # Summary is printed to stdout even when there are errors
            self.assertIn("Fase 4 Precheck", out)

    def test_sin_write_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp-cli"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")
            code, out, err = self._run(str(exp), "phase4-precheck")
            self.assertFalse((ci / "phase4_precheck.json").exists())

    def test_con_write_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp-cli"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")
            code, out, err = self._run(str(exp), "phase4-precheck", "--write")
            self.assertTrue((ci / "phase4_precheck.json").exists())
            self.assertTrue((ci / "phase4_precheck.md").exists())

    def test_expediente_inexistente_exit1(self):
        code, out, err = self._run("/ruta/que/no/existe", "phase4-precheck")
        self.assertEqual(code, 1)

    def test_con_phase2_valido_exit0_if_no_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp-cli"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(_PHASE2_MINIMO, ci / "phase2_result.json")
            # Use env with keys to avoid warnings-only issues
            env = dict(os.environ)
            env["AEMET_API_KEY"] = "test"
            env["MAPBOX_TOKEN"] = "test"
            result = subprocess.run(
                [sys.executable, "run_expediente.py", str(exp), "phase4-precheck"],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent),
                env=env,
            )
            # Errors = 0 (only warnings for phase3 info) → exit 0
            # P4-I001 is INFO not ERROR, so error_count = 0
            self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckPilotoParcela
# ---------------------------------------------------------------------------

_PARCELA = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-PARCELA"


@unittest.skipUnless(_PARCELA.exists(), "Piloto PARCELA no disponible")
class TestRunPhase4PrecheckPilotoParcela(unittest.TestCase):
    def setUp(self):
        ci = _PARCELA / "control_interno"
        # Use a tempdir to avoid writing to the pilot
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_exp = Path(self.tmpdir.name) / "expediente-EIA-2026-RECIMETAL-PARCELA"
        self.tmp_exp.mkdir()
        tmp_ci = self.tmp_exp / "control_interno"
        tmp_ci.mkdir()

        # Copy phase2_result.json if it exists; otherwise skip
        p2_src = ci / "phase2_result.json"
        if p2_src.exists():
            import shutil
            shutil.copy2(p2_src, tmp_ci / "phase2_result.json")
            p3_src = ci / "phase3_result.json"
            if p3_src.exists():
                shutil.copy2(p3_src, tmp_ci / "phase3_result.json")
        else:
            self.skipTest("phase2_result.json no existe en PARCELA")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_solo_lectura_no_modifica_piloto(self):
        before = {
            p: p.stat().st_mtime
            for p in _PARCELA.rglob("*")
            if p.is_file()
        }
        run_phase4_precheck(self.tmp_exp)
        after = {
            p: p.stat().st_mtime
            for p in _PARCELA.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_returns_result(self):
        result = run_phase4_precheck(self.tmp_exp)
        self.assertIsInstance(result, Phase4PrecheckResult)

    def test_required_maps_6(self):
        result = run_phase4_precheck(self.tmp_exp)
        self.assertEqual(len(result.required_maps), 6)


# ---------------------------------------------------------------------------
# TestRunPhase4PrecheckPilotoNave222
# ---------------------------------------------------------------------------

_NAVE222 = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-NAVE-222"


@unittest.skipUnless(_NAVE222.exists(), "Piloto NAVE-222 no disponible")
class TestRunPhase4PrecheckPilotoNave222(unittest.TestCase):
    def setUp(self):
        ci = _NAVE222 / "control_interno"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_exp = Path(self.tmpdir.name) / "expediente-EIA-2026-RECIMETAL-NAVE-222"
        self.tmp_exp.mkdir()
        tmp_ci = self.tmp_exp / "control_interno"
        tmp_ci.mkdir()

        p2_src = ci / "phase2_result.json"
        if p2_src.exists():
            import shutil
            shutil.copy2(p2_src, tmp_ci / "phase2_result.json")
        else:
            self.skipTest("phase2_result.json no existe en NAVE-222")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_solo_lectura_no_modifica_piloto(self):
        before = {
            p: p.stat().st_mtime
            for p in _NAVE222.rglob("*")
            if p.is_file()
        }
        run_phase4_precheck(self.tmp_exp)
        after = {
            p: p.stat().st_mtime
            for p in _NAVE222.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_returns_result(self):
        result = run_phase4_precheck(self.tmp_exp)
        self.assertIsInstance(result, Phase4PrecheckResult)


if __name__ == "__main__":
    unittest.main()
