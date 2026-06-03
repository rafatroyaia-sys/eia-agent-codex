"""
Tests para client_backend.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_backend import (
    CLIENT_ENTRY_FILE,
    CLIENT_FILES_INDEX,
    build_generate_plan,
    create_project_from_payload,
    list_backend_projects,
    save_project_upload,
)


class TestClientBackend(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _payload(self):
        return {
            "project": {
                "project_name": "Planta Cliente Norte",
                "promoter": "Cliente Test SL",
                "location": "Arrecife, Lanzarote",
                "coordinates_wgs84": "28.963, -13.551",
                "activity_type": "Gestion de residuos",
                "object_description": "Actividad de prueba.",
            },
            "validation": {"ready_for_engine": True},
        }

    def test_create_project_initializes_expediente_and_entry(self):
        result = create_project_from_payload(self.tmp, self._payload())
        exp_path = Path(result.expediente_path)

        self.assertEqual(result.project_id, "EXP-PLANTA-CLIENTE-NORTE")
        self.assertTrue((exp_path / "inputs").exists())
        self.assertTrue((exp_path / CLIENT_ENTRY_FILE).exists())
        self.assertFalse(result.administrative_ready)
        entry = json.loads((exp_path / CLIENT_ENTRY_FILE).read_text(encoding="utf-8"))
        self.assertEqual(entry["backend"]["project_id"], "EXP-PLANTA-CLIENTE-NORTE")
        self.assertFalse(entry["backend"]["administrative_ready"])

    def test_save_project_upload_routes_file_to_inputs(self):
        result = create_project_from_payload(self.tmp, self._payload())

        saved = save_project_upload(
            self.tmp,
            result.project_id,
            "DOC-001",
            "memoria tecnica.pdf",
            b"PDF",
            "application/pdf",
        )
        exp_path = Path(result.expediente_path)

        self.assertEqual(saved.stored_path, "inputs/memoria_tecnica/memoria_tecnica.pdf")
        self.assertTrue((exp_path / saved.stored_path).exists())
        index = json.loads((exp_path / CLIENT_FILES_INDEX).read_text(encoding="utf-8"))
        self.assertEqual(index["files"][0]["control_id"], "DOC-001")
        self.assertFalse(index["administrative_ready"])

    def test_list_backend_projects_reads_created_entries(self):
        create_project_from_payload(self.tmp, self._payload())

        projects = list_backend_projects(self.tmp)

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["project_name"], "Planta Cliente Norte")
        self.assertFalse(projects[0]["administrative_ready"])

    def test_build_generate_plan_is_prudent(self):
        result = create_project_from_payload(self.tmp, self._payload())

        plan = build_generate_plan(self.tmp, result.project_id)

        self.assertIn("phase1 --write", plan["commands"])
        self.assertIn("cliente-app-package --write", plan["commands"])
        self.assertFalse(plan["administrative_ready"])
        self.assertIn("gates", plan["note"].lower())


if __name__ == "__main__":
    unittest.main()
