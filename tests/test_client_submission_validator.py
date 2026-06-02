"""
Tests para client_submission_validator.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_submission_validator import (
    build_client_submission_validation,
    build_client_submission_validation_markdown,
    write_client_submission_validation_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientSubmissionValidator(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_phase2_complete(self, coords=None):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor Test SL",
                "coordenadas_wgs84": coords or ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })

    def _write_required_inputs(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")

    def test_missing_required_fields_blocks_submission(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")

        result = build_client_submission_validation(self.exp)
        data = result.to_dict()

        self.assertEqual(data["status"], "BLOQUEADO_ENTRADA")
        self.assertFalse(data["can_start_initial_processing"])
        self.assertGreater(data["counts"]["errors"], 0)
        self.assertTrue(any(i["control_id"] == "DAT-001" for i in data["issues"]))

    def test_invalid_upload_format_is_error(self):
        self._write_phase2_complete()
        self._write_required_inputs()
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.exe")

        result = build_client_submission_validation(self.exp)
        errors = [issue for issue in result.issues if issue.severity == "ERROR"]

        self.assertTrue(any("Formato no aceptado" in issue.title for issue in errors))
        self.assertEqual(result.status, "BLOQUEADO_ENTRADA")

    def test_complete_required_inputs_allow_initial_processing_with_warnings(self):
        self._write_phase2_complete()
        self._write_required_inputs()

        result = build_client_submission_validation(self.exp)

        self.assertEqual(result.status, "CON_OBSERVACIONES")
        self.assertTrue(result.can_start_initial_processing)
        self.assertEqual(result.counts["errors"], 0)
        self.assertGreaterEqual(result.counts["warnings"], 1)

    def test_invalid_coordinates_generate_error(self):
        self._write_phase2_complete(coords=["999, 999"])
        self._write_required_inputs()

        result = build_client_submission_validation(self.exp)

        self.assertEqual(result.status, "BLOQUEADO_ENTRADA")
        self.assertTrue(any(issue.control_id == "DAT-002" for issue in result.issues))

    def test_markdown_contains_summary_and_issues(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")

        md = build_client_submission_validation_markdown(
            build_client_submission_validation(self.exp)
        )

        self.assertIn("# Validacion entrega cliente", md)
        self.assertIn("## Resumen", md)
        self.assertIn("## Incidencias", md)
        self.assertIn("administrative_ready: false", md)

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_phase2_complete()
        self._write_required_inputs()
        result = build_client_submission_validation(self.exp)

        json_path, md_path = write_client_submission_validation_outputs(result, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], self.exp.name)


if __name__ == "__main__":
    unittest.main()
