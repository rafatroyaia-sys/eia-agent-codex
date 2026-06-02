"""
Tests para client_dashboard.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_dashboard import (
    build_client_dashboard,
    build_client_dashboard_markdown,
    write_client_dashboard_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientDashboard(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_dashboard_sources(self):
        _write_json(self.exp / "documento" / "estado_expediente_da.json", {
            "expediente_id": self.exp.name,
            "resultado_flujo": "BLOQUEADO",
            "administrative_ready": False,
            "counts": {"CERRADO": 3, "PENDIENTE": 2, "BLOQUEANTE": 1},
        })
        _write_json(self.exp / "documento" / "plan_accion_cliente.json", {
            "expediente_id": self.exp.name,
            "administrative_ready": False,
            "executive_summary": {
                "status": "BLOQUEADO_POR_ITEMS_ALTA",
                "headline": "Expediente con 2 item(s) ALTA pendientes.",
                "next_action": "Solicitar primero al promotor la documentacion ALTA pendiente.",
                "has_high_priority": True,
                "promoter_high": 1,
                "technical_high": 1,
                "total_items": 4,
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
                "technical_actions": 3,
                "technical_high": 1,
            },
        })
        _write_json(self.exp / "auditoria" / "final_audit_result.json", {
            "issues": [{"severity": "ALTA"}, {"severity": "MEDIA"}],
            "administrative_ready": False,
        })
        _write_text(self.exp / "documento" / "documento_ambiental_borrador.md")
        _write_text(self.exp / "documento" / "plan_accion_cliente.md")

    def test_build_dashboard_from_existing_outputs(self):
        self._write_dashboard_sources()

        dashboard = build_client_dashboard(self.exp)
        data = dashboard.to_dict()

        self.assertEqual(data["status"], "BLOQUEADO_POR_ITEMS_ALTA")
        self.assertIn("Expediente con 2 item", data["headline"])
        self.assertEqual(data["counts"]["promoter_high"], 1)
        self.assertEqual(data["counts"]["technical_actions"], 3)
        self.assertEqual(data["counts"]["da_bloqueante"], 1)
        self.assertEqual(data["counts"]["audit_issues"], 2)
        self.assertFalse(data["administrative_ready"])

    def test_artifacts_mark_available_files(self):
        self._write_dashboard_sources()

        dashboard = build_client_dashboard(self.exp)
        artifacts = {a.artifact_id: a for a in dashboard.artifacts}

        self.assertTrue(artifacts["ART-DA-MD"].available)
        self.assertTrue(artifacts["ART-PLAN-MD"].available)
        self.assertFalse(artifacts["ART-PAQUETE-ZIP"].available)
        self.assertGreater(artifacts["ART-DA-MD"].size_bytes, 0)

    def test_markdown_contains_dashboard_sections(self):
        self._write_dashboard_sources()

        dashboard = build_client_dashboard(self.exp)
        md = build_client_dashboard_markdown(dashboard)

        self.assertIn("# Dashboard cliente", md)
        self.assertIn("## Estado ejecutivo", md)
        self.assertIn("## Indicadores", md)
        self.assertIn("## Artefactos", md)
        self.assertIn("## Ruta de cierre", md)
        self.assertIn("administrative_ready: false", md)

    def test_missing_plan_builds_in_memory_with_warning(self):
        _write_json(self.exp / "auditoria" / "final_audit_result.json", {
            "issues": [
                {
                    "severity": "ALTA",
                    "source": "AU-01_ART45",
                    "message": "ART45-10 NO CUBIERTO: Cartografia insuficiente.",
                    "related_requirement": "ART45-10",
                }
            ]
        })

        dashboard = build_client_dashboard(self.exp)

        self.assertEqual(dashboard.status, "BLOQUEADO_POR_ITEMS_ALTA")
        self.assertTrue(any("plan calculado en memoria" in w for w in dashboard.warnings))

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_dashboard_sources()
        dashboard = build_client_dashboard(self.exp)

        json_path, md_path = write_client_dashboard_outputs(dashboard, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["expediente_id"], self.exp.name)


if __name__ == "__main__":
    unittest.main()
