"""
Tests para client_form_schema.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_form_schema import (
    build_client_form_schema,
    build_client_form_schema_markdown,
    write_client_form_schema_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientFormSchema(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_phase2(self):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor Test SL",
                "coordenadas_wgs84": ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })

    def _write_inputs(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")

    def test_build_schema_contains_controls_and_counts(self):
        self._write_phase2()
        self._write_inputs()

        schema = build_client_form_schema(self.exp)
        data = schema.to_dict()

        self.assertEqual(data["counts"]["total"], 11)
        self.assertEqual(data["counts"]["uploads"], 6)
        self.assertEqual(data["counts"]["fields"], 5)
        self.assertFalse(data["administrative_ready"])

    def test_coordinates_control_has_epsg_validations(self):
        self._write_phase2()

        schema = build_client_form_schema(self.exp)
        by_id = {control.control_id: control for control in schema.controls}

        self.assertEqual(by_id["DAT-002"].control_type, "coordinates")
        self.assertIn("EPSG:4326", by_id["DAT-002"].validations["coordinate_systems"])
        self.assertTrue(by_id["DAT-002"].validations["requires_wgs84"])

    def test_upload_controls_expose_formats_and_file_limits(self):
        self._write_phase2()
        self._write_inputs()

        schema = build_client_form_schema(self.exp)
        by_id = {control.control_id: control for control in schema.controls}

        self.assertEqual(by_id["DOC-001"].control_type, "file_upload")
        self.assertIn("PDF", by_id["DOC-001"].accepted_formats)
        self.assertEqual(by_id["DOC-001"].validations["max_files"], 10)
        self.assertEqual(by_id["DOC-003"].validations["max_files"], 25)

    def test_operations_control_has_legal_code_hints(self):
        self._write_phase2()

        schema = build_client_form_schema(self.exp)
        by_id = {control.control_id: control for control in schema.controls}

        self.assertEqual(by_id["DAT-004"].control_type, "operation_selector")
        self.assertIn("R12", by_id["DAT-004"].validations["legal_codes"])
        self.assertTrue(by_id["DAT-004"].validations["requires_included_excluded_operations"])

    def test_markdown_contains_controls_and_validations(self):
        self._write_phase2()
        md = build_client_form_schema_markdown(build_client_form_schema(self.exp))

        self.assertIn("# Form schema cliente", md)
        self.assertIn("## Controles", md)
        self.assertIn("## Validaciones", md)
        self.assertIn("administrative_ready: false", md)

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_phase2()
        schema = build_client_form_schema(self.exp)

        json_path, md_path = write_client_form_schema_outputs(schema, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], self.exp.name)


if __name__ == "__main__":
    unittest.main()
