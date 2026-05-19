"""
tests/test_art45_checklist.py
Tests para AU-01 — Checklist art. 45.1 Ley 21/2013.

Cubre:
  1. Art45ChecklistItem — to_dict, summary
  2. Art45ChecklistIssue — to_dict, summary
  3. Art45ChecklistResult — conteos, is_structurally_complete, to_dict, summary
  4. evaluate_art45_checklist_from_model — reglas por requisito
  5. evaluate_art45_checklist_from_files — expediente temporal
  6. build_art45_checklist_markdown — estructura y contenido
  7. write_art45_checklist_outputs — escritura de archivos
  8. CLI audit-art45 — exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
)
from eia_agent.core.art45_checklist import (
    ART45_REQUIREMENTS,
    Art45ChecklistItem,
    Art45ChecklistIssue,
    Art45ChecklistResult,
    COVERAGE_STATUS,
    ISSUE_SEVERITY,
    build_art45_checklist_markdown,
    evaluate_art45_checklist_from_files,
    evaluate_art45_checklist_from_model,
    write_art45_checklist_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_action(action_id: str = "AC-001") -> ProjectAction:
    return ProjectAction(
        action_id=action_id, name="Operacion de prueba",
        action_type="OPERACION",
    )


def _make_receptor(receptor_id: str = "FR-014") -> ReceptorFactor:
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=receptor_id.replace("FR-", "FI-"),
        name=f"Factor {receptor_id}",
        notes=["test"],
    )


def _make_16_receptors() -> list[ReceptorFactor]:
    return [_make_receptor(f"FR-{i:03d}") for i in range(1, 17)]


def _make_impact(
    impact_id: str = "IMP-001",
    receptor_id: str = "FR-014",
    nature: str = "NEGATIVO",
    status: str = "VALORADO",
    data_gaps: list | None = None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id, action_id="AC-001",
        receptor_id=receptor_id, name=f"Impacto {impact_id}",
        nature=nature, status=status,
        significance_without_measures="COMPATIBLE",
        significance_with_measures="COMPATIBLE",
        data_gaps=data_gaps or [],
    )


def _make_measure(measure_id: str = "MED-001") -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id, name="Medida preventiva",
        measure_type="PREVENTIVA",
        target_impact_ids=["IMP-001"],
    )


def _make_pva(pva_id: str = "PVA-001") -> PVAProgram:
    return PVAProgram(
        pva_id=pva_id, name="Seguimiento ruido",
        factor_id="FI-014", indicator="Indicador",
    )


def _full_model() -> Phase6Model:
    """Modelo con todas las piezas: actions, 16 receptors, impacts, measures, PVA."""
    return Phase6Model(
        expediente_id="TEST-FULL-001",
        actions=[_make_action()],
        receptor_factors=_make_16_receptors(),
        impacts=[_make_impact(data_gaps=["GAP-001"])],
        measures=[_make_measure()],
        pva_programs=[_make_pva()],
    )


def _minimal_pva_coverage_result(is_valid: bool = True, warnings: int = 0) -> dict:
    return {
        "is_valid": is_valid,
        "warning_count": warnings,
        "covered_impact_ids": ["IMP-001"] if is_valid else [],
        "uncovered_impact_ids": [] if is_valid else ["IMP-001"],
    }


def _minimal_cumulative_result() -> dict:
    return {
        "markdown": "## C.5 test",
        "cumulative_groups": {"FR-014": ["IMP-001"]},
        "synergistic_groups": {},
        "unresolved_gaps": [],
    }


# ---------------------------------------------------------------------------
# 1. Art45ChecklistItem
# ---------------------------------------------------------------------------

class TestArt45ChecklistItem(unittest.TestCase):

    def _make_item(self, status: str = "CUBIERTO") -> Art45ChecklistItem:
        return Art45ChecklistItem(
            requirement_id="ART45-04",
            title="Evaluacion de efectos",
            status=status,
            evidence_refs=["Phase6Model.impacts presente"],
            missing_elements=[],
            notes=["Verificar Bloque C."],
        )

    def test_to_dict_keys(self):
        item = self._make_item()
        d = item.to_dict()
        self.assertEqual(
            set(d.keys()),
            {"requirement_id", "title", "status", "evidence_refs",
             "missing_elements", "notes"},
        )

    def test_to_dict_values(self):
        item = self._make_item("PARCIAL")
        d = item.to_dict()
        self.assertEqual(d["status"], "PARCIAL")
        self.assertEqual(d["requirement_id"], "ART45-04")

    def test_summary_returns_string(self):
        item = self._make_item()
        s = item.summary()
        self.assertIsInstance(s, str)
        self.assertIn("ART45-04", s)

    def test_summary_ascii_safe(self):
        item = self._make_item()
        item.summary().encode("ascii")

    def test_all_statuses_valid(self):
        for status in COVERAGE_STATUS:
            item = self._make_item(status)
            self.assertEqual(item.to_dict()["status"], status)


# ---------------------------------------------------------------------------
# 2. Art45ChecklistIssue
# ---------------------------------------------------------------------------

class TestArt45ChecklistIssue(unittest.TestCase):

    def _make_issue(self, severity: str = "ERROR") -> Art45ChecklistIssue:
        return Art45ChecklistIssue(
            severity=severity,
            code="AU01-E04",
            requirement_id="ART45-04",
            message="Impactos no cubiertos.",
            recommendation="Identificar impactos.",
        )

    def test_to_dict_keys(self):
        issue = self._make_issue()
        d = issue.to_dict()
        self.assertEqual(
            set(d.keys()),
            {"severity", "code", "requirement_id", "message", "recommendation"},
        )

    def test_to_dict_none_requirement_id(self):
        issue = Art45ChecklistIssue(
            severity="INFO", code="AU01-I00",
            requirement_id=None,
            message="Global.", recommendation="OK.",
        )
        self.assertIsNone(issue.to_dict()["requirement_id"])

    def test_summary_returns_string(self):
        issue = self._make_issue()
        s = issue.summary()
        self.assertIsInstance(s, str)
        self.assertIn("ERROR", s)
        self.assertIn("AU01-E04", s)

    def test_summary_ascii_safe(self):
        self._make_issue().summary().encode("ascii")


# ---------------------------------------------------------------------------
# 3. Art45ChecklistResult
# ---------------------------------------------------------------------------

class TestArt45ChecklistResult(unittest.TestCase):

    def _make_result(self, n_cubierto=6, n_parcial=3, n_no_cubierto=3) -> Art45ChecklistResult:
        items = []
        for i in range(n_cubierto):
            items.append(Art45ChecklistItem(f"ART45-{i+1:02d}", f"Req {i+1}", "CUBIERTO"))
        for i in range(n_parcial):
            items.append(Art45ChecklistItem(f"ART45-P{i+1}", f"Req P{i+1}", "PARCIAL"))
        for i in range(n_no_cubierto):
            items.append(Art45ChecklistItem(f"ART45-N{i+1}", f"Req N{i+1}", "NO_CUBIERTO"))
        issues = (
            [Art45ChecklistIssue("ERROR", "E001", None, "E", "Fix.")] * n_no_cubierto +
            [Art45ChecklistIssue("WARNING", "W001", None, "W", "Check.")] * n_parcial
        )
        return Art45ChecklistResult(
            expediente_id="TEST",
            items=items,
            issues=issues,
            administrative_ready=False,
        )

    def test_covered_count(self):
        result = self._make_result(n_cubierto=5)
        self.assertEqual(result.covered_count(), 5)

    def test_partial_count(self):
        result = self._make_result(n_parcial=4)
        self.assertEqual(result.partial_count(), 4)

    def test_not_covered_count(self):
        result = self._make_result(n_no_cubierto=3)
        self.assertEqual(result.not_covered_count(), 3)

    def test_error_count(self):
        result = self._make_result(n_no_cubierto=2)
        self.assertEqual(result.error_count(), 2)

    def test_warning_count(self):
        result = self._make_result(n_parcial=3)
        self.assertEqual(result.warning_count(), 3)

    def test_is_structurally_complete_true(self):
        result = self._make_result(n_no_cubierto=0)
        result.issues = []  # no errors
        self.assertTrue(result.is_structurally_complete())

    def test_is_structurally_complete_false_no_cubierto(self):
        result = self._make_result(n_no_cubierto=1)
        self.assertFalse(result.is_structurally_complete())

    def test_administrative_ready_always_false(self):
        result = self._make_result()
        self.assertFalse(result.administrative_ready)

    def test_to_dict_keys(self):
        result = self._make_result()
        d = result.to_dict()
        expected = {
            "expediente_id", "items", "issues", "administrative_ready",
            "warnings", "notes", "covered_count", "partial_count",
            "not_covered_count", "error_count", "warning_count",
            "is_structurally_complete",
        }
        self.assertEqual(set(d.keys()), expected)

    def test_to_dict_json_serializable(self):
        result = self._make_result()
        try:
            json.dumps(result.to_dict())
        except (TypeError, ValueError) as e:
            self.fail(f"to_dict() no es JSON serializable: {e}")

    def test_summary_returns_string(self):
        result = self._make_result()
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("AU-01", s)

    def test_summary_ascii_safe(self):
        result = self._make_result()
        result.summary().encode("ascii")

    def test_to_dict_administrative_ready_false(self):
        result = self._make_result()
        self.assertFalse(result.to_dict()["administrative_ready"])


# ---------------------------------------------------------------------------
# 4. evaluate_art45_checklist_from_model
# ---------------------------------------------------------------------------

class TestEvaluateArt45FromModel(unittest.TestCase):

    def _get_item(self, result, req_id: str) -> Art45ChecklistItem:
        for item in result.items:
            if item.requirement_id == req_id:
                return item
        self.fail(f"Requisito {req_id} no encontrado en el resultado")

    # ── Modelo completo ──
    def test_full_model_returns_12_items(self):
        model = _full_model()
        result = evaluate_art45_checklist_from_model(
            "TEST", phase6_model=model,
            cumulative_result=_minimal_cumulative_result(),
            pva_coverage_result=_minimal_pva_coverage_result(),
            metadata={"alternatives_analysis": "Alternativa cero y elegida"},
        )
        self.assertEqual(len(result.items), 12)

    def test_administrative_ready_always_false(self):
        result = evaluate_art45_checklist_from_model("TEST")
        self.assertFalse(result.administrative_ready)

    def test_art45_02_no_actions_is_not_covered(self):
        model = Phase6Model(expediente_id="TEST-EMPTY")
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-02")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_02_with_actions_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            actions=[_make_action()],
            receptor_factors=[_make_receptor()],
        )
        result = evaluate_art45_checklist_from_model(
            "TEST",
            phase6_model=model,
            metadata={"object_scope": {"coordinates": "28.0N -15.4W"}},
        )
        item = self._get_item(result, "ART45-02")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_03_no_alternatives_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", metadata={})
        item = self._get_item(result, "ART45-03")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_03_with_alternatives_cubierto(self):
        result = evaluate_art45_checklist_from_model(
            "TEST",
            metadata={"alternatives_analysis": "Alternativa cero + elegida"},
        )
        item = self._get_item(result, "ART45-03")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_03_alternativa_cero_parcial(self):
        result = evaluate_art45_checklist_from_model(
            "TEST",
            metadata={"alternativa_cero": True},
        )
        item = self._get_item(result, "ART45-03")
        self.assertEqual(item.status, "PARCIAL")

    def test_art45_04_with_impacts_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            actions=[_make_action()],
            receptor_factors=[_make_receptor()],
            impacts=[_make_impact()],
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-04")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_04_no_model_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        item = self._get_item(result, "ART45-04")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_04_receptors_no_impacts_parcial(self):
        model = Phase6Model(
            expediente_id="TEST",
            actions=[_make_action()],
            receptor_factors=[_make_receptor()],
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-04")
        self.assertEqual(item.status, "PARCIAL")

    def test_art45_05_with_cumulative_result_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            impacts=[_make_impact()],
        )
        result = evaluate_art45_checklist_from_model(
            "TEST",
            phase6_model=model,
            cumulative_result=_minimal_cumulative_result(),
        )
        item = self._get_item(result, "ART45-05")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_05_impacts_no_cumulative_parcial(self):
        model = Phase6Model(
            expediente_id="TEST",
            impacts=[_make_impact()],
        )
        result = evaluate_art45_checklist_from_model(
            "TEST", phase6_model=model, cumulative_result=None
        )
        item = self._get_item(result, "ART45-05")
        self.assertEqual(item.status, "PARCIAL")

    def test_art45_06_16_receptors_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            receptor_factors=_make_16_receptors(),
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-06")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_06_no_receptors_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        item = self._get_item(result, "ART45-06")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_07_with_measures_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            impacts=[_make_impact()],
            measures=[_make_measure()],
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-07")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_07_no_measures_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        item = self._get_item(result, "ART45-07")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_08_pva_valid_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            pva_programs=[_make_pva()],
        )
        result = evaluate_art45_checklist_from_model(
            "TEST",
            phase6_model=model,
            pva_coverage_result=_minimal_pva_coverage_result(is_valid=True),
        )
        item = self._get_item(result, "ART45-08")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_08_pva_with_warnings_parcial(self):
        model = Phase6Model(
            expediente_id="TEST",
            pva_programs=[_make_pva()],
        )
        result = evaluate_art45_checklist_from_model(
            "TEST",
            phase6_model=model,
            pva_coverage_result=_minimal_pva_coverage_result(is_valid=False, warnings=3),
        )
        item = self._get_item(result, "ART45-08")
        self.assertEqual(item.status, "PARCIAL")

    def test_art45_08_no_pva_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        item = self._get_item(result, "ART45-08")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_11_with_data_gaps_cubierto(self):
        model = Phase6Model(
            expediente_id="TEST",
            impacts=[_make_impact(data_gaps=["GAP-001", "GAP-002"])],
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-11")
        self.assertEqual(item.status, "CUBIERTO")

    def test_art45_12_no_material_not_covered(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        item = self._get_item(result, "ART45-12")
        self.assertEqual(item.status, "NO_CUBIERTO")

    def test_art45_12_full_material_parcial(self):
        """Con impactos+medidas+PVA pero sin non_technical_summary → PARCIAL."""
        model = _full_model()
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        item = self._get_item(result, "ART45-12")
        self.assertEqual(item.status, "PARCIAL")

    def test_art45_12_with_rnt_cubierto(self):
        result = evaluate_art45_checklist_from_model(
            "TEST",
            phase6_model=_full_model(),
            metadata={"non_technical_summary": "Resumen completo"},
        )
        item = self._get_item(result, "ART45-12")
        self.assertEqual(item.status, "CUBIERTO")

    def test_result_has_warnings(self):
        """El resultado siempre tiene la advertencia de alcance."""
        result = evaluate_art45_checklist_from_model("TEST")
        self.assertGreater(len(result.warnings), 0)
        has_warning = any("aptitud administrativa" in w.lower() for w in result.warnings)
        self.assertTrue(has_warning)

    def test_no_cubierto_generates_error_issue(self):
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=None)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        self.assertGreater(len(errors), 0)

    def test_parcial_generates_warning_issue(self):
        model = Phase6Model(
            expediente_id="TEST",
            actions=[_make_action()],
        )
        result = evaluate_art45_checklist_from_model("TEST", phase6_model=model)
        warnings = [i for i in result.issues if i.severity == "WARNING"]
        self.assertGreater(len(warnings), 0)


# ---------------------------------------------------------------------------
# 5. evaluate_art45_checklist_from_files
# ---------------------------------------------------------------------------

class TestEvaluateArt45FromFiles(unittest.TestCase):

    def _write_minimal_model(self, impactos_dir: Path) -> None:
        model_data = {
            "expediente_id": "TEST-FILES-001",
            "actions": [{"action_id": "AC-001", "name": "Op",
                          "description": "", "action_type": "OPERACION",
                          "operation_code": None, "source_refs": [], "notes": []}],
            "receptor_factors": [
                {"receptor_id": f"FR-{i:03d}",
                 "inventory_factor_id": f"FI-{i:03d}",
                 "name": f"Factor {i:03d}",
                 "inventory_semaphore": "NO_CONSTA",
                 "ready_from_inventory": False,
                 "critical_gaps": [],
                 "notes": []}
                for i in range(1, 17)
            ],
            "impacts": [{
                "impact_id": "IMP-001", "action_id": "AC-001",
                "receptor_id": "FR-014", "name": "Ruido",
                "nature": "NEGATIVO", "status": "VALORADO",
                "significance_without_measures": "COMPATIBLE",
                "significance_with_measures": "COMPATIBLE",
                "conesa_attributes": {},
                "data_gaps": ["GAP-001"],
                "source_refs": [], "measure_ids": [],
                "pva_ids": [], "warnings": [], "notes": [],
            }],
            "measures": [{"measure_id": "MED-001", "name": "Medida",
                           "description": "", "measure_type": "PREVENTIVA",
                           "status": "PROPUESTA", "target_impact_ids": [],
                           "is_diagnostic": False, "is_prl_only": False,
                           "condition_before_submission": False,
                           "warnings": [], "notes": []}],
            "pva_programs": [{"pva_id": "PVA-001", "name": "Seguimiento",
                               "factor_id": "FI-014", "indicator": "Ind",
                               "threshold": "Umbral", "frequency": "MENSUAL",
                               "target_impact_ids": ["IMP-001"],
                               "target_measure_ids": [], "responsible": "RA",
                               "records": [], "warnings": [], "notes": []}],
            "warnings": [], "notes": [],
        }
        (impactos_dir / "phase6_model_with_pva.json").write_text(
            json.dumps(model_data), encoding="utf-8"
        )

    def test_empty_expediente_returns_result_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-EMPTY"
            exp_dir.mkdir()
            result = evaluate_art45_checklist_from_files(exp_dir)
            self.assertIsInstance(result, Art45ChecklistResult)
            self.assertEqual(len(result.items), 12)

    def test_empty_expediente_has_no_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-EMPTY"
            exp_dir.mkdir()
            result = evaluate_art45_checklist_from_files(exp_dir)
            # Most items should be NO_CUBIERTO with empty expediente
            self.assertGreater(result.not_covered_count(), 5)

    def test_nonexistent_path_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            evaluate_art45_checklist_from_files(Path("no_existe_directorio"))

    def test_with_model_file_reduces_no_cubierto(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            self._write_minimal_model(impactos_dir)
            result_with = evaluate_art45_checklist_from_files(exp_dir)

            exp_empty = Path(tmp) / "expediente-EIA-EMPTY"
            exp_empty.mkdir()
            result_without = evaluate_art45_checklist_from_files(exp_empty)

            # With model should have fewer NO_CUBIERTO
            self.assertLess(
                result_with.not_covered_count(),
                result_without.not_covered_count(),
            )

    def test_expediente_id_from_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            self._write_minimal_model(impactos_dir)
            result = evaluate_art45_checklist_from_files(exp_dir)
            self.assertEqual(result.expediente_id, "TEST-FILES-001")

    def test_administrative_ready_always_false_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "test"
            exp_dir.mkdir()
            result = evaluate_art45_checklist_from_files(exp_dir)
            self.assertFalse(result.administrative_ready)


# ---------------------------------------------------------------------------
# 6. build_art45_checklist_markdown
# ---------------------------------------------------------------------------

class TestBuildArt45ChecklistMarkdown(unittest.TestCase):

    def _make_result(self) -> Art45ChecklistResult:
        model = _full_model()
        return evaluate_art45_checklist_from_model(
            "TEST-MD",
            phase6_model=model,
            cumulative_result=_minimal_cumulative_result(),
            pva_coverage_result=_minimal_pva_coverage_result(),
        )

    def test_returns_string(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIsInstance(md, str)

    def test_contains_all_requirements(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        for i in range(1, 13):
            self.assertIn(f"ART45-{i:02d}", md, f"ART45-{i:02d} no encontrado en markdown")

    def test_contains_resumen_section(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("Resumen", md)

    def test_contains_resultado_por_requisito_section(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("Resultado por requisito", md)

    def test_contains_advertencia_de_alcance(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("Advertencia de alcance", md)

    def test_advertencia_mentions_no_aptitud_administrativa(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("aptitud administrativa", md.lower())

    def test_advertencia_mentions_organo_ambiental(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        # El markdown usa "órgano ambiental" con tilde; verificamos sin tilde
        # normalizando a ASCII para la comparación
        import unicodedata
        md_ascii = unicodedata.normalize("NFKD", md).encode("ascii", "ignore").decode("ascii").lower()
        self.assertIn("organo ambiental", md_ascii)

    def test_contains_incidencias_section(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("Incidencias", md)

    def test_administrative_ready_false_in_markdown(self):
        result = self._make_result()
        md = build_art45_checklist_markdown(result)
        self.assertIn("administrative_ready", md)
        self.assertIn("False", md)

    def test_empty_expediente_markdown_valid(self):
        result = evaluate_art45_checklist_from_model("EMPTY")
        md = build_art45_checklist_markdown(result)
        self.assertIsInstance(md, str)
        self.assertGreater(len(md), 100)


# ---------------------------------------------------------------------------
# 7. write_art45_checklist_outputs
# ---------------------------------------------------------------------------

class TestWriteArt45ChecklistOutputs(unittest.TestCase):

    def _make_result(self) -> Art45ChecklistResult:
        return evaluate_art45_checklist_from_model("TEST-WRITE")

    def test_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_art45_checklist_outputs(result, Path(tmp))
            self.assertTrue(json_path.exists())

    def test_creates_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            _, md_path = write_art45_checklist_outputs(result, Path(tmp))
            self.assertTrue(md_path.exists())

    def test_json_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_art45_checklist_outputs(result, Path(tmp))
            self.assertEqual(json_path.name, "art45_checklist_result.json")

    def test_md_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            _, md_path = write_art45_checklist_outputs(result, Path(tmp))
            self.assertEqual(md_path.name, "art45_checklist_result.md")

    def test_json_loadable_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_art45_checklist_outputs(result, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("items", data)
            self.assertIn("is_structurally_complete", data)
            self.assertIn("administrative_ready", data)
            self.assertFalse(data["administrative_ready"])

    def test_creates_dir_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "auditoria" / "nuevo"
            result = self._make_result()
            write_art45_checklist_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())


# ---------------------------------------------------------------------------
# 8. CLI audit-art45
# ---------------------------------------------------------------------------

class TestCLIAuditArt45(unittest.TestCase):

    def _write_full_model(self, exp_dir: Path) -> None:
        impactos_dir = exp_dir / "impactos"
        impactos_dir.mkdir(parents=True, exist_ok=True)
        model_data = {
            "expediente_id": "CLI-TEST",
            "actions": [{"action_id": "AC-001", "name": "Op", "description": "",
                          "action_type": "OPERACION", "operation_code": None,
                          "source_refs": [], "notes": []}],
            "receptor_factors": [
                {"receptor_id": f"FR-{i:03d}", "inventory_factor_id": f"FI-{i:03d}",
                 "name": f"F{i}", "inventory_semaphore": "NO_CONSTA",
                 "ready_from_inventory": False, "critical_gaps": [], "notes": []}
                for i in range(1, 17)
            ],
            "impacts": [{
                "impact_id": "IMP-001", "action_id": "AC-001",
                "receptor_id": "FR-014", "name": "Ruido",
                "nature": "NEGATIVO", "status": "VALORADO",
                "significance_without_measures": "COMPATIBLE",
                "significance_with_measures": "COMPATIBLE",
                "conesa_attributes": {}, "data_gaps": ["GAP-001"],
                "source_refs": [], "measure_ids": [], "pva_ids": [],
                "warnings": [], "notes": [],
            }],
            "measures": [{"measure_id": "MED-001", "name": "M",
                           "description": "", "measure_type": "PREVENTIVA",
                           "status": "PROPUESTA", "target_impact_ids": [],
                           "is_diagnostic": False, "is_prl_only": False,
                           "condition_before_submission": False,
                           "warnings": [], "notes": []}],
            "pva_programs": [{"pva_id": "PVA-001", "name": "PVA",
                               "factor_id": "FI-014", "indicator": "I",
                               "threshold": "U", "frequency": "MENSUAL",
                               "target_impact_ids": ["IMP-001"],
                               "target_measure_ids": [], "responsible": "RA",
                               "records": [], "warnings": [], "notes": []}],
            "warnings": [], "notes": [],
        }
        (impactos_dir / "phase6_model_with_pva.json").write_text(
            json.dumps(model_data), encoding="utf-8"
        )
        # Tambien cumulative result para ART45-05
        cumul_data = {
            "markdown": "## C.5", "cumulative_groups": {}, "synergistic_groups": {},
            "unresolved_gaps": [], "issues": [], "warnings": [], "notes": [],
        }
        (impactos_dir / "cumulative_synergistic_result.json").write_text(
            json.dumps(cumul_data), encoding="utf-8"
        )
        # PVA coverage result
        pva_cov = {
            "is_valid": True, "warning_count": 0,
            "covered_impact_ids": ["IMP-001"], "uncovered_impact_ids": [],
        }
        (impactos_dir / "pva_coverage_result.json").write_text(
            json.dumps(pva_cov), encoding="utf-8"
        )

    def test_no_expediente_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "no_existe"
            ret = main([str(exp_dir), "audit-art45"])
            self.assertEqual(ret, 1)

    def test_empty_expediente_exits_1_incomplete(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-EMPTY"
            exp_dir.mkdir()
            ret = main([str(exp_dir), "audit-art45"])
            self.assertEqual(ret, 1)  # incompleto → exit 1

    def test_no_write_creates_no_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            self._write_full_model(exp_dir)
            main([str(exp_dir), "audit-art45"])
            self.assertFalse((exp_dir / "auditoria" / "art45_checklist_result.json").exists())

    def test_with_write_creates_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            self._write_full_model(exp_dir)
            main([str(exp_dir), "audit-art45", "--write"])
            self.assertTrue(
                (exp_dir / "auditoria" / "art45_checklist_result.json").exists()
            )
            self.assertTrue(
                (exp_dir / "auditoria" / "art45_checklist_result.md").exists()
            )

    def test_output_json_has_required_fields(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            self._write_full_model(exp_dir)
            main([str(exp_dir), "audit-art45", "--write"])
            data = json.loads(
                (exp_dir / "auditoria" / "art45_checklist_result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("items", data)
            self.assertIn("is_structurally_complete", data)
            self.assertFalse(data["administrative_ready"])
            self.assertEqual(len(data["items"]), 12)

    def test_output_does_not_modify_model_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            self._write_full_model(exp_dir)
            model_path = exp_dir / "impactos" / "phase6_model_with_pva.json"
            original_content = model_path.read_text(encoding="utf-8")
            main([str(exp_dir), "audit-art45", "--write"])
            self.assertEqual(model_path.read_text(encoding="utf-8"), original_content)


# ---------------------------------------------------------------------------
# 9. Constantes y metadatos
# ---------------------------------------------------------------------------

class TestArt45Constants(unittest.TestCase):

    def test_12_requirements_defined(self):
        self.assertEqual(len(ART45_REQUIREMENTS), 12)

    def test_requirement_ids_sequential(self):
        for i, req in enumerate(ART45_REQUIREMENTS, 1):
            self.assertEqual(req["requirement_id"], f"ART45-{i:02d}")

    def test_coverage_status_values(self):
        self.assertEqual(set(COVERAGE_STATUS), {"CUBIERTO", "PARCIAL", "NO_CUBIERTO", "NO_APLICA"})

    def test_issue_severity_values(self):
        self.assertEqual(set(ISSUE_SEVERITY), {"ERROR", "WARNING", "INFO"})

    def test_all_requirements_have_title_and_description(self):
        for req in ART45_REQUIREMENTS:
            self.assertIn("title", req)
            self.assertIn("description", req)
            self.assertTrue(req["title"].strip())
            self.assertTrue(req["description"].strip())


if __name__ == "__main__":
    unittest.main()
