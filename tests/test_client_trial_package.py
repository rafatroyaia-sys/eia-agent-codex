"""
Tests para client_trial_package.
"""
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_trial_package import build_client_trial_package


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientTrialPackage(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_minimal_inputs(self):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor Test SL",
                "coordenadas_wgs84": ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")

    def test_preview_does_not_write_package(self):
        self._write_minimal_inputs()

        result = build_client_trial_package(self.exp, write_outputs=False)

        self.assertEqual(result.status, "PREVIEW_PAQUETE_CLIENTE")
        self.assertFalse((self.exp / "documento" / "cliente_trial_package").exists())
        self.assertFalse(result.administrative_ready)

    def test_write_package_creates_html_json_markdown_and_zip(self):
        self._write_minimal_inputs()

        result = build_client_trial_package(self.exp, write_outputs=True)
        package_dir = self.exp / "documento" / "cliente_trial_package"
        zip_path = self.exp / "documento" / "cliente_trial_package.zip"

        self.assertEqual(result.status, "LISTO_PARA_PRUEBA_CLIENTE")
        self.assertTrue((package_dir / "index.html").exists())
        self.assertTrue((package_dir / "README_CLIENTE.md").exists())
        self.assertTrue((package_dir / "data" / "cliente_portal.json").exists())
        self.assertTrue((package_dir / "data" / "cliente_form_schema.json").exists())
        self.assertTrue((package_dir / "data" / "cliente_submission_validation.json").exists())
        self.assertTrue((package_dir / "markdown" / "cliente_portal.md").exists())
        self.assertTrue(zip_path.exists())
        self.assertGreater(len(result.artifacts), 0)

    def test_zip_contains_expected_entrypoints(self):
        self._write_minimal_inputs()

        build_client_trial_package(self.exp, write_outputs=True)
        zip_path = self.exp / "documento" / "cliente_trial_package.zip"

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())

        self.assertIn("index.html", names)
        self.assertIn("README_CLIENTE.md", names)
        self.assertIn("data/cliente_portal.json", names)
        self.assertIn("data/cliente_submission_validation.json", names)

    def test_manifest_never_sets_administrative_ready(self):
        self._write_minimal_inputs()

        result = build_client_trial_package(self.exp, write_outputs=True)
        data = result.to_dict()

        self.assertFalse(data["administrative_ready"])
        self.assertIn("no declara", data["disclaimer"])


if __name__ == "__main__":
    unittest.main()
