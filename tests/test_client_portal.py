"""
Tests para client_portal.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_portal import (
    build_client_portal,
    build_client_portal_markdown,
    write_client_portal_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientPortal(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_phase2_complete(self):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor Test SL",
                "coordenadas_wgs84": ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })

    def _write_inputs_complete(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "fotos" / "foto1.jpg")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")
        _write_file(self.exp / "inputs" / "cartografia_aportada" / "parcela.geojson")

    def _write_dashboard_sources(self):
        _write_json(self.exp / "documento" / "plan_accion_cliente.json", {
            "expediente_id": self.exp.name,
            "administrative_ready": False,
            "executive_summary": {
                "status": "BLOQUEADO_POR_ITEMS_ALTA",
                "headline": "Expediente con 1 item(s) ALTA pendientes.",
                "next_action": "Solicitar primero al promotor la documentacion ALTA pendiente.",
                "administrative_ready": False,
            },
            "closing_route": [
                {
                    "order": 1,
                    "title": "Solicitar al promotor los 1 item(s) de criticidad ALTA.",
                    "audience": "PROMOTOR",
                    "priority": "ALTA",
                    "action_refs": ["ACP-001"],
                }
            ],
            "counts": {
                "promoter_requests": 1,
                "promoter_high": 1,
                "technical_actions": 0,
                "technical_high": 0,
            },
        })
        _write_json(self.exp / "documento" / "estado_expediente_da.json", {
            "counts": {"CERRADO": 10, "PENDIENTE": 2, "BLOQUEANTE": 1},
            "administrative_ready": False,
        })
        _write_file(self.exp / "documento" / "documento_ambiental_borrador.md")

    def test_missing_required_intake_blocks_client_portal(self):
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")

        portal = build_client_portal(self.exp)
        data = portal.to_dict()

        self.assertEqual(data["status"], "ESPERANDO_DOCUMENTACION_CLIENTE")
        self.assertFalse(data["administrative_ready"])
        self.assertFalse(data["intake"]["ready_for_initial_processing"])
        self.assertTrue(data["upload_sections"])
        self.assertEqual(data["next_steps"][0]["audience"], "PROMOTOR")

    def test_complete_intake_can_surface_dashboard_blocked_status(self):
        self._write_phase2_complete()
        self._write_inputs_complete()
        self._write_dashboard_sources()

        portal = build_client_portal(self.exp)
        data = portal.to_dict()

        self.assertEqual(data["status"], "BLOQUEADO_POR_ITEMS_ALTA")
        self.assertTrue(data["intake"]["ready_for_initial_processing"])
        self.assertEqual(data["dashboard"]["counts"]["promoter_high"], 1)
        self.assertTrue(any(a["available"] for a in data["artifacts"]))
        self.assertFalse(data["administrative_ready"])

    def test_markdown_contains_sections_for_ui_review(self):
        self._write_phase2_complete()
        self._write_inputs_complete()

        md = build_client_portal_markdown(build_client_portal(self.exp))

        self.assertIn("# Portal cliente", md)
        self.assertIn("## Entrada cliente", md)
        self.assertIn("## Siguientes pasos", md)
        self.assertIn("## Artefactos", md)
        self.assertIn("administrative_ready: false", md)

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_phase2_complete()
        self._write_inputs_complete()
        portal = build_client_portal(self.exp)

        json_path, md_path = write_client_portal_outputs(portal, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], self.exp.name)


if __name__ == "__main__":
    unittest.main()
