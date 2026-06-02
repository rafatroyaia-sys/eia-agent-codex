"""
Tests para client_intake.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_intake import (
    build_client_intake,
    build_client_intake_markdown,
    write_client_intake_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, data: bytes = b"fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class TestClientIntake(unittest.TestCase):

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
                "coordenadas_wgs84": ["28.9773, -13.5395"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12", "R13"],
                "capacidad": "1200 t/ano",
            }
        })

    def _write_inputs(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "fotos" / "foto1.jpg")
        _write_file(self.exp / "inputs" / "imagenes" / "plano_implantacion.pdf")
        _write_file(self.exp / "inputs" / "cartografia_aportada" / "parcela.geojson")

    def test_build_intake_detects_complete_fields_and_documents(self):
        self._write_phase2()
        self._write_inputs()

        intake = build_client_intake(self.exp)
        data = intake.to_dict()

        self.assertTrue(data["ready_for_initial_processing"])
        self.assertEqual(data["counts"]["required_pending"], 0)
        self.assertEqual(data["counts"]["high_pending"], 1)  # alternativas quedan PARCIAL
        self.assertFalse(data["administrative_ready"])

    def test_requirements_have_expected_contract_keys(self):
        self._write_phase2()
        self._write_inputs()

        intake = build_client_intake(self.exp)
        req = intake.to_dict()["requirements"][0]

        for key in (
            "requirement_id", "title", "kind", "priority", "required",
            "target", "help_text", "accepted_formats", "status", "evidence",
        ):
            self.assertIn(key, req)

    def test_missing_phase2_warns_and_marks_fields_pending(self):
        self._write_inputs()

        intake = build_client_intake(self.exp)
        by_id = {r.requirement_id: r for r in intake.requirements}

        self.assertTrue(intake.warnings)
        self.assertEqual(by_id["DAT-001"].status, "PENDIENTE")
        self.assertEqual(by_id["DOC-001"].status, "COMPLETO")
        self.assertFalse(intake.is_ready_for_initial_processing())

    def test_legacy_memorias_folder_counts_as_memory_input(self):
        self._write_phase2()
        _write_file(self.exp / "inputs" / "memorias" / "memoria_tecnica.pdf")

        intake = build_client_intake(self.exp)
        by_id = {r.requirement_id: r for r in intake.requirements}

        self.assertEqual(by_id["DOC-001"].status, "COMPLETO")
        self.assertIn("inputs/memorias/memoria_tecnica.pdf", by_id["DOC-001"].evidence)

    def test_markdown_contains_summary_and_table(self):
        self._write_phase2()
        self._write_inputs()

        md = build_client_intake_markdown(build_client_intake(self.exp))

        self.assertIn("# Intake cliente", md)
        self.assertIn("## Resumen", md)
        self.assertIn("| ID | Prioridad | Tipo | Estado | Requisito | Destino |", md)
        self.assertIn("administrative_ready: false", md)

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_phase2()
        self._write_inputs()
        intake = build_client_intake(self.exp)

        json_path, md_path = write_client_intake_outputs(intake, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], self.exp.name)


if __name__ == "__main__":
    unittest.main()
