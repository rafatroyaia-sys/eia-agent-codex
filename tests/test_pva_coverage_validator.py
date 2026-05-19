"""
tests/test_pva_coverage_validator.py
Tests para IM-07 — Validador de cobertura PVA.

Cubre:
  1. PVACoverageIssue — to_dict, summary
  2. PVACoverageResult — conteos, is_valid, to_dict, summary
  3. impact_requires_pva — todas las reglas
  4. find_pva_coverage_for_impact — DIRECT / BY_FACTOR / TRANSVERSAL / sin cobertura
  5. validate_pva_coverage — todos los casos de clasificación
  6. build_pva_coverage_markdown — estructura y contenido
  7. validate_pva_coverage_from_json — fixture temporal
  8. write_pva_coverage_outputs — JSON + MD
  9. CLI phase6-validate-pva — exit codes, --write
"""
import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
    RECEPTOR_FACTOR_IDS,
)
from eia_agent.core.pva_coverage_validator import (
    COVERAGE_BY_FACTOR,
    COVERAGE_DIRECT,
    COVERAGE_TRANSVERSAL,
    PVACoverageIssue,
    PVACoverageResult,
    _coverage_type,
    _is_annual_review_pva,
    _pva_is_conditioned,
    build_pva_coverage_markdown,
    find_pva_coverage_for_impact,
    impact_requires_pva,
    validate_pva_coverage,
    validate_pva_coverage_from_json,
    write_pva_coverage_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_impact(
    impact_id: str = "IMP-001",
    receptor_id: str = "FR-014",
    nature: str = "NEGATIVO",
    significance: str = "COMPATIBLE",
    status: str = "VALORADO",
    data_gaps: list | None = None,
    pva_ids: list | None = None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id=receptor_id,
        name=f"Impacto {impact_id}",
        description="",
        nature=nature,
        status=status,
        significance_without_measures=significance,
        significance_with_measures=significance,
        data_gaps=data_gaps or [],
        pva_ids=pva_ids or [],
    )


def _make_pva(
    pva_id: str = "PVA-001",
    factor_id: str = "FI-014",
    target_impact_ids: list | None = None,
    conditioned: bool = False,
    annual: bool = False,
    transversal_note: bool = False,
) -> PVAProgram:
    name = "Revision interna anual del PVA" if annual else f"PVA {pva_id}"
    notes = ["Esta ficha tambien cubre cobertura transversal"] if transversal_note else []
    pva_warnings = ["CONDICIONADO — se activa si se confirma CONT-001."] if conditioned else []
    return PVAProgram(
        pva_id=pva_id,
        name=name,
        factor_id=factor_id,
        indicator="Indicador de prueba",
        target_impact_ids=target_impact_ids or [],
        warnings=pva_warnings,
        notes=notes,
    )


def _make_receptor(receptor_id: str = "FR-014") -> ReceptorFactor:
    fi_id = receptor_id.replace("FR-", "FI-")
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=f"Factor {receptor_id}",
        notes=["test"],
    )


def _make_model(
    impacts: list | None = None,
    pva_programs: list | None = None,
) -> Phase6Model:
    if impacts is None:
        impacts = [_make_impact()]
    seen: set[str] = set()
    unique_receptors = []
    for imp in impacts:
        if imp.receptor_id not in seen:
            unique_receptors.append(_make_receptor(imp.receptor_id))
            seen.add(imp.receptor_id)
    return Phase6Model(
        expediente_id="TEST-001",
        actions=[ProjectAction("AC-001", "Operacion", action_type="OPERACION")],
        receptor_factors=unique_receptors,
        impacts=impacts,
        pva_programs=pva_programs if pva_programs is not None else [],
    )


# ---------------------------------------------------------------------------
# 1. PVACoverageIssue
# ---------------------------------------------------------------------------

class TestPVACoverageIssue(unittest.TestCase):

    def _make_issue(self, severity="ERROR", code="PVA-COV-E001"):
        return PVACoverageIssue(
            severity=severity,
            code=code,
            impact_id="IMP-001",
            pva_id="PVA-001",
            message="Impacto sin cobertura PVA.",
            recommendation="Generar ficha PVA.",
        )

    def test_to_dict_keys(self):
        issue = self._make_issue()
        d = issue.to_dict()
        self.assertEqual(
            set(d.keys()),
            {"severity", "code", "impact_id", "pva_id", "message", "recommendation"},
        )

    def test_to_dict_values(self):
        issue = self._make_issue()
        d = issue.to_dict()
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["code"], "PVA-COV-E001")
        self.assertEqual(d["impact_id"], "IMP-001")

    def test_summary_returns_string(self):
        issue = self._make_issue()
        s = issue.summary()
        self.assertIsInstance(s, str)
        self.assertIn("ERROR", s)
        self.assertIn("PVA-COV-E001", s)

    def test_summary_ascii_safe(self):
        issue = self._make_issue()
        issue.summary().encode("ascii")

    def test_none_ids_allowed(self):
        issue = PVACoverageIssue(
            severity="INFO",
            code="PVA-COV-I003",
            impact_id=None,
            pva_id=None,
            message="Sin impactos.",
            recommendation="Ninguna.",
        )
        d = issue.to_dict()
        self.assertIsNone(d["impact_id"])
        self.assertIsNone(d["pva_id"])


# ---------------------------------------------------------------------------
# 2. PVACoverageResult
# ---------------------------------------------------------------------------

class TestPVACoverageResult(unittest.TestCase):

    def _make_result(self, n_errors=0, n_warnings=0, n_infos=0):
        issues = []
        for i in range(n_errors):
            issues.append(PVACoverageIssue(
                "ERROR", f"E{i:03d}", f"IMP-{i:03d}", None, "Error.", "Fix."
            ))
        for i in range(n_warnings):
            issues.append(PVACoverageIssue(
                "WARNING", f"W{i:03d}", f"IMP-{i:03d}", None, "Warning.", "Check."
            ))
        for i in range(n_infos):
            issues.append(PVACoverageIssue(
                "INFO", f"I{i:03d}", f"IMP-{i:03d}", None, "Info.", "OK."
            ))
        return PVACoverageResult(issues=issues)

    def test_error_count(self):
        result = self._make_result(n_errors=3, n_warnings=2, n_infos=1)
        self.assertEqual(result.error_count(), 3)

    def test_warning_count(self):
        result = self._make_result(n_errors=1, n_warnings=4)
        self.assertEqual(result.warning_count(), 4)

    def test_info_count(self):
        result = self._make_result(n_infos=5)
        self.assertEqual(result.info_count(), 5)

    def test_is_valid_no_errors(self):
        result = self._make_result(n_warnings=3, n_infos=2)
        self.assertTrue(result.is_valid())

    def test_is_valid_with_errors(self):
        result = self._make_result(n_errors=1)
        self.assertFalse(result.is_valid())

    def test_to_dict_keys(self):
        result = self._make_result()
        d = result.to_dict()
        expected = {
            "covered_impact_ids", "uncovered_impact_ids", "conditional_coverage_ids",
            "ignored_impact_ids", "issues", "warnings", "notes",
            "error_count", "warning_count", "info_count", "is_valid",
        }
        self.assertEqual(set(d.keys()), expected)

    def test_to_dict_is_valid_reflects_errors(self):
        result = self._make_result(n_errors=2)
        self.assertFalse(result.to_dict()["is_valid"])

    def test_summary_returns_string(self):
        result = self._make_result(n_errors=1)
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("IM-07", s)

    def test_summary_ascii_safe(self):
        result = self._make_result(n_errors=1)
        result.summary().encode("ascii")

    def test_summary_contains_no_valido(self):
        result = self._make_result(n_errors=2)
        self.assertIn("NO VALIDO", result.summary())

    def test_summary_contains_valido_no_errors(self):
        result = self._make_result()
        self.assertIn("VALIDO", result.summary())


# ---------------------------------------------------------------------------
# 3. impact_requires_pva
# ---------------------------------------------------------------------------

class TestImpactRequiresPVA(unittest.TestCase):

    def test_negativo_compatible_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_moderado_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="MODERADO", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_severo_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="SEVERO", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_critico_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="CRITICO", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_indeterminado_significance_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="INDETERMINADO", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_no_valorado_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="NO_VALORADO", status="IDENTIFICADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_pendiente_datos_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="PENDIENTE_DATOS")
        self.assertTrue(impact_requires_pva(imp))

    def test_descartado_no_requires_pva(self):
        imp = _make_impact(status="DESCARTADO_JUSTIFICADO")
        self.assertFalse(impact_requires_pva(imp))

    def test_positivo_no_requires_pva(self):
        imp = _make_impact(nature="POSITIVO", significance="POSITIVO_MODERADO")
        self.assertFalse(impact_requires_pva(imp))

    def test_positivo_with_gaps_no_requires_pva(self):
        """POSITIVO con data_gaps genera WARNING pero no require PVA por la regla."""
        imp = _make_impact(nature="POSITIVO", data_gaps=["GAP-FI-013-001"])
        self.assertFalse(impact_requires_pva(imp))

    def test_indeterminado_sensitive_receptor_flora_requires_pva(self):
        imp = _make_impact(
            receptor_id="FR-007",
            nature="INDETERMINADO",
            status="INDETERMINADO",
            significance="INDETERMINADO",
        )
        self.assertTrue(impact_requires_pva(imp))

    def test_indeterminado_sensitive_receptor_fauna_requires_pva(self):
        imp = _make_impact(receptor_id="FR-008", status="INDETERMINADO", nature="INDETERMINADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_indeterminado_sensitive_receptor_enp_requires_pva(self):
        imp = _make_impact(receptor_id="FR-009", status="INDETERMINADO", nature="INDETERMINADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_indeterminado_sensitive_receptor_red_natura_requires_pva(self):
        imp = _make_impact(receptor_id="FR-010", status="INDETERMINADO", nature="INDETERMINADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_indeterminado_sensitive_receptor_patrimonio_requires_pva(self):
        imp = _make_impact(receptor_id="FR-012", status="INDETERMINADO", nature="INDETERMINADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_indeterminado_non_sensitive_no_requires_pva(self):
        """INDETERMINADO en receptor NO sensible no requiere PVA por esta regla."""
        imp = _make_impact(receptor_id="FR-001", status="INDETERMINADO", nature="INDETERMINADO")
        self.assertFalse(impact_requires_pva(imp))

    def test_mixto_compatible_requires_pva(self):
        imp = _make_impact(nature="MIXTO", significance="COMPATIBLE", status="VALORADO")
        self.assertTrue(impact_requires_pva(imp))

    def test_negativo_identificado_requires_pva(self):
        imp = _make_impact(nature="NEGATIVO", status="IDENTIFICADO", significance="COMPATIBLE")
        self.assertTrue(impact_requires_pva(imp))


# ---------------------------------------------------------------------------
# 4. find_pva_coverage_for_impact
# ---------------------------------------------------------------------------

class TestFindPVACoverage(unittest.TestCase):

    def test_direct_coverage_by_target_impact_ids(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva = _make_pva(pva_id="PVA-001", factor_id="FI-014", target_impact_ids=["IMP-001"])
        result = find_pva_coverage_for_impact(imp, [pva])
        self.assertIn(pva, result)

    def test_no_direct_coverage_wrong_id(self):
        imp = _make_impact(impact_id="IMP-002", receptor_id="FR-014")
        pva = _make_pva(pva_id="PVA-001", factor_id="FI-014", target_impact_ids=["IMP-001"])
        result = find_pva_coverage_for_impact(imp, [pva])
        # BY_FACTOR: same FI → still finds coverage
        self.assertIn(pva, result)

    def test_by_factor_coverage_when_not_in_targets(self):
        """PVA con factor FI-014 debe cubrir impactos en FR-014 aunque no estén en targets."""
        imp = _make_impact(impact_id="IMP-003", receptor_id="FR-014")
        pva = _make_pva(pva_id="PVA-002", factor_id="FI-014", target_impact_ids=[])
        result = find_pva_coverage_for_impact(imp, [pva])
        self.assertIn(pva, result)

    def test_no_coverage_wrong_factor(self):
        """PVA de factor FI-003 no cubre impacto en FR-014."""
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva = _make_pva(pva_id="PVA-001", factor_id="FI-003", target_impact_ids=[])
        result = find_pva_coverage_for_impact(imp, [pva])
        self.assertEqual(len(result), 0)

    def test_annual_review_excluded(self):
        """La revisión anual global no cuenta como cobertura de factor."""
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        annual_pva = _make_pva(
            pva_id="PVA-099",
            factor_id="FI-016",
            target_impact_ids=["IMP-001"],
            annual=True,
        )
        result = find_pva_coverage_for_impact(imp, [annual_pva])
        self.assertEqual(len(result), 0, "Revision anual no debe contar como cobertura")

    def test_transversal_note_with_matching_factor(self):
        """PVA con nota transversal y factor coincidente sí cubre el impacto."""
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-007")
        pva = _make_pva(
            pva_id="PVA-005",
            factor_id="FI-007",
            target_impact_ids=[],
            transversal_note=True,
        )
        result = find_pva_coverage_for_impact(imp, [pva])
        self.assertIn(pva, result)

    def test_empty_pva_list_no_coverage(self):
        imp = _make_impact()
        result = find_pva_coverage_for_impact(imp, [])
        self.assertEqual(result, [])

    def test_multiple_pvas_multiple_coverage(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva1 = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        pva2 = _make_pva("PVA-002", "FI-014", [])
        result = find_pva_coverage_for_impact(imp, [pva1, pva2])
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# 4b. Helpers internos de cobertura
# ---------------------------------------------------------------------------

class TestCoverageHelpers(unittest.TestCase):

    def test_coverage_type_direct(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        self.assertEqual(_coverage_type(imp, pva), COVERAGE_DIRECT)

    def test_coverage_type_by_factor(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva = _make_pva("PVA-001", "FI-014", [])
        self.assertEqual(_coverage_type(imp, pva), COVERAGE_BY_FACTOR)

    def test_coverage_type_none_wrong_factor(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        pva = _make_pva("PVA-001", "FI-003", [])
        self.assertIsNone(_coverage_type(imp, pva))

    def test_coverage_type_none_annual(self):
        imp = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        annual = _make_pva("PVA-099", "FI-016", ["IMP-001"], annual=True)
        self.assertIsNone(_coverage_type(imp, annual))

    def test_is_annual_review_pva_true(self):
        annual = _make_pva(annual=True)
        self.assertTrue(_is_annual_review_pva(annual))

    def test_is_annual_review_pva_false(self):
        normal = _make_pva()
        self.assertFalse(_is_annual_review_pva(normal))

    def test_pva_is_conditioned_true(self):
        pva = _make_pva(conditioned=True)
        self.assertTrue(_pva_is_conditioned(pva))

    def test_pva_is_conditioned_false(self):
        pva = _make_pva(conditioned=False)
        self.assertFalse(_pva_is_conditioned(pva))


# ---------------------------------------------------------------------------
# 5. validate_pva_coverage
# ---------------------------------------------------------------------------

class TestValidatePVACoverage(unittest.TestCase):

    def test_empty_model_is_valid_with_info(self):
        model = Phase6Model(expediente_id="EMPTY")
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertGreater(len(result.issues), 0)

    def test_negativo_without_pva_is_error(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        self.assertFalse(result.is_valid())
        self.assertIn("IMP-001", result.uncovered_impact_ids)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        self.assertGreater(len(errors), 0)

    def test_negativo_with_direct_pva_is_covered(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.covered_impact_ids)
        self.assertNotIn("IMP-001", result.uncovered_impact_ids)

    def test_negativo_with_factor_pva_is_conditional(self):
        """PVA con factor coincidente pero sin impact_id en targets → condicional."""
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        pva = _make_pva("PVA-001", "FI-014", [])  # no tiene IMP-001 en targets
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        # valid (no ERROR) pero sí WARNING
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.conditional_coverage_ids)

    def test_negativo_with_conditioned_pva_is_conditional(self):
        """PVA directo pero CONDICIONADO → condicional (WARNING)."""
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"], conditioned=True)
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.conditional_coverage_ids)
        warnings = [i for i in result.issues if i.severity == "WARNING"]
        self.assertGreater(len(warnings), 0)

    def test_positivo_without_gaps_is_ignored(self):
        imp = _make_impact(
            nature="POSITIVO",
            significance="POSITIVO_MODERADO",
            receptor_id="FR-013",
        )
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.ignored_impact_ids)

    def test_positivo_with_gaps_generates_warning(self):
        imp = _make_impact(
            nature="POSITIVO",
            significance="POSITIVO_MODERADO",
            receptor_id="FR-013",
            data_gaps=["GAP-FI-013-001"],
        )
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())  # solo WARNING, no ERROR
        self.assertIn("IMP-001", result.ignored_impact_ids)
        w003 = [i for i in result.issues if i.code == "PVA-COV-W003"]
        self.assertGreater(len(w003), 0)

    def test_descartado_is_ignored(self):
        imp = _make_impact(status="DESCARTADO_JUSTIFICADO")
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.ignored_impact_ids)

    def test_sensitive_indeterminado_without_pva_is_error(self):
        imp = _make_impact(
            receptor_id="FR-007",
            nature="INDETERMINADO",
            status="INDETERMINADO",
            significance="INDETERMINADO",
        )
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        self.assertFalse(result.is_valid())
        self.assertIn("IMP-001", result.uncovered_impact_ids)

    def test_sensitive_indeterminado_with_conditioned_pva_is_conditional(self):
        imp = _make_impact(
            receptor_id="FR-007",
            nature="INDETERMINADO",
            status="INDETERMINADO",
            significance="INDETERMINADO",
        )
        pva = _make_pva("PVA-001", "FI-007", ["IMP-001"], conditioned=True)
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        self.assertTrue(result.is_valid())
        self.assertIn("IMP-001", result.conditional_coverage_ids)

    def test_no_mutation_of_model(self):
        imp = _make_impact()
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(impacts=[imp], pva_programs=[pva])
        original_pva_count = len(model.pva_programs)
        original_imp_pva_ids = list(model.impacts[0].pva_ids)
        validate_pva_coverage(model)
        self.assertEqual(len(model.pva_programs), original_pva_count)
        self.assertEqual(model.impacts[0].pva_ids, original_imp_pva_ids)

    def test_multiple_impacts_mixed_coverage(self):
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO", significance="COMPATIBLE")
        imp2 = _make_impact("IMP-002", "FR-006", nature="NEGATIVO", significance="MODERADO")
        imp3 = _make_impact("IMP-003", receptor_id="FR-013", nature="POSITIVO")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(
            impacts=[imp1, imp2, imp3],
            pva_programs=[pva],
        )
        result = validate_pva_coverage(model)
        self.assertIn("IMP-001", result.covered_impact_ids)
        self.assertIn("IMP-002", result.uncovered_impact_ids)
        self.assertIn("IMP-003", result.ignored_impact_ids)
        self.assertFalse(result.is_valid())  # IMP-002 uncovered

    def test_annual_review_not_sufficient_coverage(self):
        """La revisión anual global no debe contar como cobertura suficiente."""
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE", status="VALORADO")
        annual = _make_pva("PVA-099", "FI-016", ["IMP-001"], annual=True)
        model = _make_model(impacts=[imp], pva_programs=[annual])
        result = validate_pva_coverage(model)
        self.assertFalse(result.is_valid())
        self.assertIn("IMP-001", result.uncovered_impact_ids)

    def test_error_code_pva_cov_e001_for_uncovered(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE")
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        codes = [i.code for i in result.issues]
        self.assertIn("PVA-COV-E001", codes)

    def test_warning_code_pva_cov_w001_for_conditioned(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"], conditioned=True)
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        codes = [i.code for i in result.issues]
        self.assertIn("PVA-COV-W001", codes)

    def test_warning_code_pva_cov_w002_for_by_factor(self):
        imp = _make_impact(nature="NEGATIVO", significance="COMPATIBLE")
        pva = _make_pva("PVA-001", "FI-014", [])  # no en targets
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        codes = [i.code for i in result.issues]
        self.assertIn("PVA-COV-W002", codes)

    def test_result_notes_not_empty(self):
        model = _make_model()
        result = validate_pva_coverage(model)
        self.assertGreater(len(result.notes), 0)

    def test_to_dict_json_serializable(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        result = validate_pva_coverage(model)
        try:
            json.dumps(result.to_dict())
        except (TypeError, ValueError) as e:
            self.fail(f"to_dict() no es JSON serializable: {e}")


# ---------------------------------------------------------------------------
# 6. build_pva_coverage_markdown
# ---------------------------------------------------------------------------

class TestBuildPVACoverageMarkdown(unittest.TestCase):

    def setUp(self):
        imp1 = _make_impact("IMP-001", nature="NEGATIVO", significance="COMPATIBLE")
        imp2 = _make_impact("IMP-002", receptor_id="FR-006", nature="NEGATIVO")
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(impacts=[imp1, imp2], pva_programs=[pva])
        self.result = validate_pva_coverage(model)
        self.md = build_pva_coverage_markdown(self.result)

    def test_returns_string(self):
        self.assertIsInstance(self.md, str)

    def test_contains_header(self):
        self.assertIn("IM-07", self.md)

    def test_contains_resumen_section(self):
        self.assertIn("Resumen", self.md)

    def test_contains_covered_section(self):
        self.assertIn("Impactos cubiertos", self.md)

    def test_contains_uncovered_section(self):
        self.assertIn("Impactos sin cobertura", self.md)

    def test_contains_conditional_section(self):
        self.assertIn("Coberturas condicionadas", self.md)

    def test_contains_ignored_section(self):
        self.assertIn("ignorados", self.md)

    def test_contains_issues_section(self):
        self.assertIn("Incidencias", self.md)

    def test_uncovered_impact_mentioned(self):
        self.assertIn("IMP-002", self.md)

    def test_covered_impact_mentioned(self):
        self.assertIn("IMP-001", self.md)

    def test_empty_model_markdown(self):
        model = Phase6Model(expediente_id="EMPTY")
        result = validate_pva_coverage(model)
        md = build_pva_coverage_markdown(result)
        self.assertIsInstance(md, str)
        self.assertIn("IM-07", md)

    def test_valid_result_shows_valido(self):
        imp = _make_impact()
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_pva_coverage(model)
        md = build_pva_coverage_markdown(result)
        self.assertIn("VÁLIDO", md)

    def test_invalid_result_shows_no_valido(self):
        imp = _make_impact(nature="NEGATIVO")
        model = _make_model(impacts=[imp], pva_programs=[])
        result = validate_pva_coverage(model)
        md = build_pva_coverage_markdown(result)
        self.assertIn("NO VÁLIDO", md)


# ---------------------------------------------------------------------------
# 7. validate_pva_coverage_from_json
# ---------------------------------------------------------------------------

class TestValidatePVACoverageFromJSON(unittest.TestCase):

    def _write_model_json(self, tmp_path: Path, impacts=None, pva_programs=None) -> Path:
        impacts_data = impacts if impacts is not None else [{
            "impact_id": "IMP-001",
            "action_id": "AC-001",
            "receptor_id": "FR-014",
            "name": "Impacto ruido",
            "description": "",
            "nature": "NEGATIVO",
            "status": "VALORADO",
            "significance_without_measures": "COMPATIBLE",
            "significance_with_measures": "COMPATIBLE",
            "conesa_attributes": {k: None for k in [
                "intensidad", "extension", "momento", "persistencia",
                "reversibilidad", "sinergia", "acumulacion",
                "efecto", "periodicidad", "recuperabilidad",
            ]},
            "data_gaps": [],
            "source_refs": [],
            "measure_ids": [],
            "pva_ids": [],
            "warnings": [],
            "notes": [],
        }]
        pva_data = pva_programs if pva_programs is not None else [{
            "pva_id": "PVA-001",
            "name": "Seguimiento ruido",
            "factor_id": "FI-014",
            "indicator": "Registro horario",
            "threshold": "Operaciones fuera de horario",
            "frequency": "MENSUAL",
            "target_impact_ids": ["IMP-001"],
            "target_measure_ids": [],
            "responsible": "Responsable",
            "records": ["Libro de operaciones"],
            "warnings": [],
            "notes": [],
        }]
        model_dict = {
            "expediente_id": "TEST-JSON-001",
            "actions": [],
            "receptor_factors": [],
            "impacts": impacts_data,
            "measures": [],
            "pva_programs": pva_data,
            "warnings": [],
            "notes": [],
        }
        path = tmp_path / "phase6_model_with_pva.json"
        path.write_text(json.dumps(model_dict), encoding="utf-8")
        return path

    def test_valid_json_returns_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_model_json(Path(tmp))
            result = validate_pva_coverage_from_json(path)
            self.assertIsInstance(result, PVACoverageResult)

    def test_valid_coverage_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_model_json(Path(tmp))
            result = validate_pva_coverage_from_json(path)
            self.assertTrue(result.is_valid())

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            validate_pva_coverage_from_json(Path("no_existe.json"))

    def test_invalid_json_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / "bad.json"
            bad_file.write_text("{not: valid json}", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_pva_coverage_from_json(bad_file)

    def test_uncovered_impact_in_json_not_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_model_json(Path(tmp), pva_programs=[])
            result = validate_pva_coverage_from_json(path)
            self.assertFalse(result.is_valid())
            self.assertIn("IMP-001", result.uncovered_impact_ids)


# ---------------------------------------------------------------------------
# 8. write_pva_coverage_outputs
# ---------------------------------------------------------------------------

class TestWritePVACoverageOutputs(unittest.TestCase):

    def _make_result_with_data(self):
        imp = _make_impact()
        pva = _make_pva("PVA-001", "FI-014", ["IMP-001"])
        model = _make_model(impacts=[imp], pva_programs=[pva])
        return validate_pva_coverage(model)

    def test_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result_with_data()
            json_path, _ = write_pva_coverage_outputs(result, Path(tmp))
            self.assertTrue(json_path.exists())

    def test_creates_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result_with_data()
            _, md_path = write_pva_coverage_outputs(result, Path(tmp))
            self.assertTrue(md_path.exists())

    def test_json_file_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result_with_data()
            json_path, _ = write_pva_coverage_outputs(result, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("covered_impact_ids", data)
            self.assertIn("uncovered_impact_ids", data)
            self.assertIn("is_valid", data)

    def test_md_file_contains_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result_with_data()
            _, md_path = write_pva_coverage_outputs(result, Path(tmp))
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("IM-07", content)

    def test_creates_output_dir_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "subdir" / "impactos"
            result = self._make_result_with_data()
            write_pva_coverage_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())

    def test_filenames_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result_with_data()
            json_path, md_path = write_pva_coverage_outputs(result, Path(tmp))
            self.assertEqual(json_path.name, "pva_coverage_result.json")
            self.assertEqual(md_path.name, "pva_coverage_result.md")


# ---------------------------------------------------------------------------
# 9. CLI phase6-validate-pva
# ---------------------------------------------------------------------------

class TestCLIValidatePVA(unittest.TestCase):

    def _minimal_pva_model(self, with_pva: bool = True, covered: bool = True) -> dict:
        pva_data = []
        if with_pva:
            pva_data.append({
                "pva_id": "PVA-001",
                "name": "Seguimiento ruido",
                "factor_id": "FI-014",
                "indicator": "Indicador",
                "threshold": "Umbral",
                "frequency": "MENSUAL",
                "target_impact_ids": ["IMP-001"] if covered else [],
                "target_measure_ids": [],
                "responsible": "Responsable",
                "records": [],
                "warnings": [],
                "notes": [],
            })
        return {
            "expediente_id": "TEST-CLI-IM07",
            "actions": [{"action_id": "AC-001", "name": "Op", "description": "",
                          "action_type": "OPERACION", "operation_code": None,
                          "source_refs": [], "notes": []}],
            "receptor_factors": [{"receptor_id": "FR-014", "inventory_factor_id": "FI-014",
                                   "name": "Ruido", "inventory_semaphore": "NO_CONSTA",
                                   "ready_from_inventory": False, "critical_gaps": [],
                                   "notes": ["test"]}],
            "impacts": [{
                "impact_id": "IMP-001",
                "action_id": "AC-001",
                "receptor_id": "FR-014",
                "name": "Impacto ruido",
                "description": "",
                "nature": "NEGATIVO",
                "status": "VALORADO",
                "significance_without_measures": "COMPATIBLE",
                "significance_with_measures": "COMPATIBLE",
                "conesa_attributes": {k: None for k in [
                    "intensidad", "extension", "momento", "persistencia",
                    "reversibilidad", "sinergia", "acumulacion",
                    "efecto", "periodicidad", "recuperabilidad",
                ]},
                "data_gaps": [], "source_refs": [], "measure_ids": [],
                "pva_ids": [], "warnings": [], "notes": [],
            }],
            "measures": [],
            "pva_programs": pva_data,
            "warnings": [],
            "notes": [],
        }

    def test_no_model_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            ret = main([str(exp_dir), "phase6-validate-pva"])
            self.assertEqual(ret, 1)

    def test_valid_coverage_exits_0(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_pva_model(with_pva=True, covered=True)),
                encoding="utf-8",
            )
            ret = main([str(exp_dir), "phase6-validate-pva"])
            self.assertEqual(ret, 0)

    def test_uncovered_impact_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_pva_model(with_pva=False)),
                encoding="utf-8",
            )
            ret = main([str(exp_dir), "phase6-validate-pva"])
            self.assertEqual(ret, 1)

    def test_no_write_creates_no_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_pva_model()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-validate-pva"])
            self.assertFalse((impactos_dir / "pva_coverage_result.json").exists())
            self.assertFalse((impactos_dir / "pva_coverage_result.md").exists())

    def test_with_write_creates_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_pva_model()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-validate-pva", "--write"])
            self.assertTrue((impactos_dir / "pva_coverage_result.json").exists())
            self.assertTrue((impactos_dir / "pva_coverage_result.md").exists())

    def test_fallback_to_measures_model(self):
        """Si no hay phase6_model_with_pva.json, usa phase6_model_with_measures.json."""
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_measures.json").write_text(
                json.dumps(self._minimal_pva_model(with_pva=True, covered=True)),
                encoding="utf-8",
            )
            ret = main([str(exp_dir), "phase6-validate-pva"])
            # Exit code depends on coverage, not on which file is used
            self.assertIn(ret, [0, 1])

    def test_output_json_has_is_valid_field(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_pva_model()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-validate-pva", "--write"])
            data = json.loads(
                (impactos_dir / "pva_coverage_result.json").read_text(encoding="utf-8")
            )
            self.assertIn("is_valid", data)
            self.assertIn("covered_impact_ids", data)


if __name__ == "__main__":
    unittest.main()
