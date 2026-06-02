"""
Tests para client_action_plan.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_action_plan import (
    build_client_action_plan,
    build_client_action_plan_markdown,
    write_client_action_plan_outputs,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class TestClientActionPlan(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_audit(self):
        _write_json(self.exp / "auditoria" / "final_audit_result.json", {
            "expediente_id": self.exp.name,
            "status": "NO_CONFORME",
            "administrative_ready": False,
            "issues": [
                {
                    "severity": "ALTA",
                    "source": "AU-01_ART45",
                    "code": "AU04-E102",
                    "message": "Requisito ART45-03 NO CUBIERTO en el expediente.",
                    "recommendation": "Incluir alternativas.",
                    "related_requirement": "ART45-03",
                },
                {
                    "severity": "ALTA",
                    "source": "AU-01_ART45",
                    "code": "AU04-AU01-E10",
                    "message": "ART45-10 NO CUBIERTO: Cartografia y ubicacion suficiente.",
                    "recommendation": "Completar mapas.",
                    "related_requirement": "ART45-10",
                },
                {
                    "severity": "BLOQUEANTE",
                    "source": "AU-02_PRUDENCE",
                    "code": "AU04-AU02-E001",
                    "message": "Frase prohibida detectada: 'sin afeccion'.",
                    "recommendation": "Sustituir por lenguaje prudente.",
                    "related_file": "impactos/valoracion.md",
                },
            ],
        })

    def test_art45_03_goes_to_promoter_requests(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)

        titles = [i.title for i in plan.promoter_requests]

        self.assertTrue(any("alternativas" in t.lower() for t in titles))
        self.assertEqual(plan.promoter_high_count(), 2)

    def test_prudence_issue_goes_to_technical_actions(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)

        titles = [i.title for i in plan.technical_actions]

        self.assertTrue(any("lenguaje prudente" in t.lower() for t in titles))
        self.assertEqual(plan.technical_high_count(), 1)

    def test_repeated_prudence_issues_are_grouped(self):
        _write_json(self.exp / "auditoria" / "final_audit_result.json", {
            "issues": [
                {
                    "severity": "ALTA",
                    "source": "AU-02_PRUDENCE",
                    "code": "AU04-AU02-E001",
                    "message": "Frase prohibida detectada: 'sin afeccion'.",
                    "related_file": "bloques/A.md",
                },
                {
                    "severity": "MEDIA",
                    "source": "AU-02_PRUDENCE",
                    "code": "AU04-AU02-W001",
                    "message": "Frase prohibida detectada: 'moderado'.",
                    "related_file": "bloques/B.md",
                },
            ],
        })

        plan = build_client_action_plan(self.exp)
        prudence = [i for i in plan.technical_actions if i.source == "AU-02_PRUDENCE"]

        self.assertEqual(len(prudence), 1)
        self.assertIn("2 incidencia", prudence[0].reason)

    def test_rd04_group_adds_specific_diagnostic_measure_guidance(self):
        _write_json(self.exp / "auditoria" / "final_audit_result.json", {
            "issues": [
                {
                    "severity": "ALTA",
                    "source": "RD-04_BLOCK_CONSISTENCY",
                    "code": "BC-MEA-001",
                    "message": (
                        "D_medidas presenta estudio acustico diagnostica como "
                        "reductora de impacto."
                    ),
                    "recommendation": "Separar diagnosticas de correctoras.",
                    "related_file": "bloques/D_medidas.md",
                },
                {
                    "severity": "ALTA",
                    "source": "RD-04_BLOCK_CONSISTENCY",
                    "code": "BC-MEA-002",
                    "message": "AG09_medidas presenta EPI/PRL como correctora ambiental.",
                    "recommendation": "Separar PRL de medidas ambientales.",
                    "related_file": "impactos/AG09_medidas.md",
                },
            ],
        })

        plan = build_client_action_plan(self.exp)
        rd04 = [i for i in plan.technical_actions if i.source == "RD-04_BLOCK_CONSISTENCY"]

        self.assertEqual(len(rd04), 1)
        self.assertIn("2 incidencia", rd04[0].reason)
        self.assertIn("estudio acustico no reduce", rd04[0].recommendation.lower())
        self.assertIn("epi no computan", rd04[0].recommendation.lower())
        self.assertIn("bloques/D_medidas.md", rd04[0].reason)

    def test_plan_never_sets_administrative_ready(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)

        self.assertFalse(plan.administrative_ready)
        self.assertFalse(plan.to_dict()["administrative_ready"])

    def test_to_dict_contains_structured_closing_route(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)
        data = plan.to_dict()

        route = data["closing_route"]

        self.assertEqual(route[0]["order"], 1)
        self.assertEqual(route[0]["audience"], "PROMOTOR")
        self.assertEqual(route[0]["priority"], "ALTA")
        self.assertEqual(route[0]["action_refs"], ["ACP-001", "ACP-002"])
        self.assertIn("Solicitar al promotor", route[0]["title"])
        self.assertIn("no sustituye firma", route[-1]["title"])

    def test_deduplicates_audit_and_da_state_same_requirement(self):
        self._write_audit()
        _write_json(self.exp / "documento" / "estado_expediente_da.json", {
            "expediente_id": self.exp.name,
            "estado_bloqueante": [
                {
                    "categoria": "BLOQUEANTE",
                    "item": "Auditoria: AU04-E102",
                    "fuente": "final_audit_result",
                    "valor": "ALTA",
                    "accion": "Requisito ART45-03 NO CUBIERTO.",
                }
            ],
            "estado_pendiente": [],
        })

        plan = build_client_action_plan(self.exp)
        art45_03 = [i for i in plan.promoter_requests if i.reference == "ART45-03"]

        self.assertEqual(len(art45_03), 1)

    def test_markdown_contains_email_draft_when_promoter_items_exist(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)
        md = build_client_action_plan_markdown(plan)

        self.assertIn("Borrador de correo", md)
        self.assertIn("Solicitud de informacion tecnica", md)

    def test_markdown_contains_ordered_closing_route(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)
        md = build_client_action_plan_markdown(plan)

        self.assertIn("## Ruta recomendada de cierre", md)
        self.assertIn("Solicitar al promotor los 2 item(s) de criticidad ALTA", md)
        self.assertIn("Resolver las 1 accion(es) tecnicas ALTA", md)
        self.assertIn("Regenerar Documento Ambiental", md)
        self.assertIn("no sustituye firma ni validacion juridica", md)

    def test_write_outputs_creates_json_and_markdown(self):
        self._write_audit()
        plan = build_client_action_plan(self.exp)

        json_path, md_path = write_client_action_plan_outputs(plan, self.exp)

        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["counts"]["promoter_requests"], 2)

    def test_missing_sources_returns_warning(self):
        plan = build_client_action_plan(self.exp)

        self.assertTrue(plan.warnings)
        self.assertEqual(plan.promoter_requests, [])
        self.assertEqual(plan.technical_actions, [])


if __name__ == "__main__":
    unittest.main()
