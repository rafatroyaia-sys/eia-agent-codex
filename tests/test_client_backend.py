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
    GENERATION_STEPS,
    build_project_readiness,
    build_project_backup,
    build_generate_plan,
    build_backend_handler,
    create_project_from_payload,
    get_backend_project,
    get_generation_status,
    list_backend_projects,
    parse_multipart_form,
    restore_project_backup,
    save_project_upload,
    storage_status,
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
        self.assertIn("phase4-offline --write", plan["commands"])
        self.assertIn("cliente-app-package --write", plan["commands"])
        generation_commands = [" ".join(step[2]) for step in GENERATION_STEPS]
        self.assertIn("cartography-plan --write", generation_commands)
        self.assertIn("schematic-maps --write", generation_commands)
        self.assertIn("__official_maps__", generation_commands)
        self.assertFalse(plan["administrative_ready"])
        self.assertIn("gates", plan["note"].lower())

    def test_readiness_requires_saved_high_priority_documents(self):
        result = create_project_from_payload(self.tmp, self._payload())

        readiness = build_project_readiness(self.tmp, result.project_id)

        self.assertFalse(readiness["ready_for_generation"])
        self.assertEqual(len(readiness["missing_documents"]), 3)
        self.assertTrue(readiness["coordinate_format_ok"])

    def test_readiness_accepts_complete_minimum_entry(self):
        result = create_project_from_payload(self.tmp, self._payload())
        for control_id in ("DOC-001", "DOC-002", "DOC-004"):
            save_project_upload(
                self.tmp,
                result.project_id,
                control_id,
                f"{control_id}.pdf",
                b"PDF",
                "application/pdf",
            )

        readiness = build_project_readiness(self.tmp, result.project_id)

        self.assertTrue(readiness["ready_for_generation"])
        self.assertFalse(readiness["administrative_ready"])
        self.assertEqual(readiness["blockers"], [])

    def test_generation_status_starts_as_not_started(self):
        result = create_project_from_payload(self.tmp, self._payload())

        status = get_generation_status(self.tmp, result.project_id)

        self.assertEqual(status["status"], "NOT_STARTED")
        self.assertEqual(status["outputs"], [])
        self.assertFalse(status["administrative_ready"])

    def test_generation_status_lists_visual_outputs(self):
        result = create_project_from_payload(self.tmp, self._payload())
        exp_path = Path(result.expediente_path)
        maps_dir = exp_path / "cartografia" / "mapas"
        climate_dir = exp_path / "clima"
        maps_dir.mkdir(parents=True, exist_ok=True)
        climate_dir.mkdir(parents=True, exist_ok=True)
        (maps_dir / "MAP-001_situacion.png").write_bytes(b"PNG-MAP")
        (climate_dir / "climograma.png").write_bytes(b"PNG-CLIMA")

        status = get_generation_status(self.tmp, result.project_id)
        labels = {item["name"]: item["label"] for item in status["outputs"]}

        self.assertEqual(labels["MAP-001_situacion.png"], "Mapa/plano")
        self.assertEqual(labels["climograma.png"], "Climograma")

    def test_generation_status_lists_official_map_outputs(self):
        result = create_project_from_payload(self.tmp, self._payload())
        exp_path = Path(result.expediente_path)
        maps_dir = exp_path / "cartografia" / "mapas"
        maps_dir.mkdir(parents=True, exist_ok=True)
        (maps_dir / "MAP-OFICIAL-001_catastro_parcela.png").write_bytes(b"PNG-MAP")

        status = get_generation_status(self.tmp, result.project_id)
        item = next(x for x in status["outputs"] if x["name"] == "MAP-OFICIAL-001_catastro_parcela.png")

        self.assertEqual(item["label"], "Mapa oficial Catastro")
        self.assertEqual(item["kind"], "OFFICIAL_CADASTRE_MAP")

    def test_generation_status_lists_red_natura_outputs(self):
        result = create_project_from_payload(self.tmp, self._payload())
        exp_path = Path(result.expediente_path)
        maps_dir = exp_path / "cartografia" / "mapas"
        maps_dir.mkdir(parents=True, exist_ok=True)
        (maps_dir / "MAP-OFICIAL-002_red_natura_2000.png").write_bytes(b"PNG-MAP")

        status = get_generation_status(self.tmp, result.project_id)
        item = next(x for x in status["outputs"] if x["name"] == "MAP-OFICIAL-002_red_natura_2000.png")

        self.assertEqual(item["label"], "Mapa oficial Red Natura")
        self.assertEqual(item["kind"], "OFFICIAL_RED_NATURA_MAP")

    def test_get_backend_project_supports_resuming_work(self):
        result = create_project_from_payload(self.tmp, self._payload())

        project = get_backend_project(self.tmp, result.project_id)

        self.assertEqual(project["project_id"], result.project_id)
        self.assertEqual(project["entry"]["project"]["project_name"], "Planta Cliente Norte")
        self.assertIn("readiness", project)
        self.assertIn("generation", project)

    def test_backup_and_restore_preserve_complete_project(self):
        result = create_project_from_payload(self.tmp, self._payload())
        save_project_upload(
            self.tmp,
            result.project_id,
            "DOC-001",
            "memoria.pdf",
            b"PDF-CONTENT",
            "application/pdf",
        )
        backup = build_project_backup(self.tmp, result.project_id)
        restored_workspace = self.tmp / "restored"

        restored = restore_project_backup(restored_workspace, backup.name, backup.read_bytes())

        self.assertEqual(restored.project_id, result.project_id)
        restored_exp = Path(restored.expediente_path)
        self.assertTrue((restored_exp / CLIENT_ENTRY_FILE).exists())
        self.assertEqual(
            (restored_exp / "inputs/memoria_tecnica/memoria.pdf").read_bytes(),
            b"PDF-CONTENT",
        )

    def test_storage_status_is_prudent_by_default(self):
        status = storage_status(self.tmp)

        self.assertFalse(status["persistent"])
        self.assertEqual(status["mode"], "TEMPORARY_WITH_BACKUPS")

    def test_parse_multipart_form_works_without_cgi(self):
        boundary = "----EIAAgentBoundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="control_id"\r\n\r\n'
            "DOC-001\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="memoria.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + b"PDF-CONTENT\r\n" + f"--{boundary}--\r\n".encode("utf-8")

        fields, files = parse_multipart_form(
            f"multipart/form-data; boundary={boundary}",
            body,
        )

        self.assertEqual(fields["control_id"], "DOC-001")
        self.assertEqual(files[0]["filename"], "memoria.pdf")
        self.assertEqual(files[0]["content"], b"PDF-CONTENT")

    def test_backend_handler_accepts_access_token_configuration(self):
        static_dir = self.tmp / "static"
        static_dir.mkdir()

        handler = build_backend_handler(self.tmp, static_dir, access_token="clave-segura")

        self.assertEqual(handler.access_token, "clave-segura")


if __name__ == "__main__":
    unittest.main()
