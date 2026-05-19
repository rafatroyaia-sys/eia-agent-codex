"""
tests/test_cumulative_synergistic_section.py
Tests para IM-08 — Generador de sección C.5 (efectos acumulativos y sinérgicos).

Cubre:
  1. CumulativeSynergyIssue — to_dict, summary
  2. CumulativeSynergyResult — conteos, to_dict, summary
  3. group_impacts_by_receptor — agrupación, exclusión, conservación
  4. detect_cumulative_impact_groups — reglas de detección
  5. detect_synergistic_impact_groups — 5 pares de sinergia
  6. extract_unresolved_cumulative_gaps — fuentes y deduplicación
  7. build_cumulative_synergistic_markdown — estructura, prudencia, secciones
  8. build_cumulative_synergistic_section — result completo, no mutación
  9. write_cumulative_synergistic_outputs — escritura de archivos
  10. CLI phase6-cumulative — exit codes, --write
"""
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
    ReceptorFactor,
)
from eia_agent.core.cumulative_synergistic_section import (
    CumulativeSynergyIssue,
    CumulativeSynergyResult,
    build_cumulative_synergistic_markdown,
    build_cumulative_synergistic_section,
    build_cumulative_synergistic_section_from_json,
    detect_cumulative_impact_groups,
    detect_synergistic_impact_groups,
    extract_unresolved_cumulative_gaps,
    group_impacts_by_receptor,
    write_cumulative_synergistic_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_impact(
    impact_id: str = "IMP-001",
    receptor_id: str = "FR-014",
    action_id: str = "AC-001",
    nature: str = "NEGATIVO",
    status: str = "VALORADO",
    significance: str = "COMPATIBLE",
    data_gaps: list | None = None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id=action_id,
        receptor_id=receptor_id,
        name=f"Impacto {impact_id}",
        nature=nature,
        status=status,
        significance_without_measures=significance,
        significance_with_measures=significance,
        data_gaps=data_gaps or [],
    )


def _make_receptor(
    receptor_id: str = "FR-014",
    critical_gaps: list | None = None,
) -> ReceptorFactor:
    fi_id = receptor_id.replace("FR-", "FI-")
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=f"Factor {receptor_id}",
        critical_gaps=critical_gaps or [],
        notes=["test"],
    )


def _make_model(
    impacts: list | None = None,
    receptor_ids: list[str] | None = None,
    receptor_critical_gaps: dict | None = None,
) -> Phase6Model:
    if impacts is None:
        impacts = [_make_impact()]
    if receptor_ids is None:
        seen: set[str] = set()
        receptor_ids = []
        for imp in impacts:
            if imp.receptor_id not in seen:
                receptor_ids.append(imp.receptor_id)
                seen.add(imp.receptor_id)
    rcg = receptor_critical_gaps or {}
    receptors = [
        _make_receptor(r, rcg.get(r, []))
        for r in receptor_ids
    ]
    return Phase6Model(
        expediente_id="TEST-CS-001",
        actions=[ProjectAction("AC-001", "Operacion", action_type="OPERACION")],
        receptor_factors=receptors,
        impacts=impacts,
    )


# ---------------------------------------------------------------------------
# 1. CumulativeSynergyIssue
# ---------------------------------------------------------------------------

class TestCumulativeSynergyIssue(unittest.TestCase):

    def _make_issue(self, severity="INFO", code="CS-I001"):
        return CumulativeSynergyIssue(
            severity=severity,
            code=code,
            factor_id="FR-014",
            impact_ids=["IMP-001", "IMP-002"],
            message="Grupo acumulativo detectado.",
            recommendation="Revisar medidas.",
        )

    def test_to_dict_keys(self):
        issue = self._make_issue()
        d = issue.to_dict()
        self.assertEqual(
            set(d.keys()),
            {"severity", "code", "factor_id", "impact_ids", "message", "recommendation"},
        )

    def test_to_dict_impact_ids_is_list(self):
        issue = self._make_issue()
        d = issue.to_dict()
        self.assertIsInstance(d["impact_ids"], list)

    def test_to_dict_none_factor_id(self):
        issue = CumulativeSynergyIssue(
            severity="WARNING", code="CS-W002",
            factor_id=None, impact_ids=[],
            message="Gaps.", recommendation="Resolver."
        )
        d = issue.to_dict()
        self.assertIsNone(d["factor_id"])

    def test_summary_returns_string(self):
        issue = self._make_issue()
        s = issue.summary()
        self.assertIsInstance(s, str)
        self.assertIn("CS-I001", s)

    def test_summary_ascii_safe(self):
        issue = self._make_issue()
        issue.summary().encode("ascii")

    def test_severity_values(self):
        for sev in ("INFO", "WARNING"):
            issue = self._make_issue(severity=sev)
            self.assertEqual(issue.to_dict()["severity"], sev)


# ---------------------------------------------------------------------------
# 2. CumulativeSynergyResult
# ---------------------------------------------------------------------------

class TestCumulativeSynergyResult(unittest.TestCase):

    def _make_result(self, n_warnings=0, n_infos=0):
        issues = []
        for i in range(n_warnings):
            issues.append(CumulativeSynergyIssue(
                "WARNING", f"CS-W{i:03d}", None, [], f"W{i}", "Fix."
            ))
        for i in range(n_infos):
            issues.append(CumulativeSynergyIssue(
                "INFO", f"CS-I{i:03d}", None, [], f"I{i}", "OK."
            ))
        return CumulativeSynergyResult(
            markdown="## C.5 test",
            issues=issues,
        )

    def test_error_count_always_zero(self):
        """Este módulo nunca genera ERRORs."""
        result = self._make_result(n_warnings=2, n_infos=3)
        self.assertEqual(result.error_count(), 0)

    def test_warning_count(self):
        result = self._make_result(n_warnings=3)
        self.assertEqual(result.warning_count(), 3)

    def test_info_count(self):
        result = self._make_result(n_infos=4)
        self.assertEqual(result.info_count(), 4)

    def test_to_dict_keys(self):
        result = self._make_result()
        d = result.to_dict()
        expected = {
            "markdown", "cumulative_groups", "synergistic_groups",
            "unresolved_gaps", "issues", "warnings", "notes",
            "warning_count", "info_count",
        }
        self.assertEqual(set(d.keys()), expected)

    def test_to_dict_json_serializable(self):
        result = self._make_result(n_warnings=1, n_infos=2)
        try:
            json.dumps(result.to_dict())
        except (TypeError, ValueError) as e:
            self.fail(f"to_dict() no es JSON serializable: {e}")

    def test_summary_returns_string(self):
        result = self._make_result()
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("IM-08", s)

    def test_summary_ascii_safe(self):
        result = self._make_result()
        result.summary().encode("ascii")


# ---------------------------------------------------------------------------
# 3. group_impacts_by_receptor
# ---------------------------------------------------------------------------

class TestGroupImpactsByReceptor(unittest.TestCase):

    def test_groups_by_receptor(self):
        imp1 = _make_impact("IMP-001", "FR-014")
        imp2 = _make_impact("IMP-002", "FR-014")
        imp3 = _make_impact("IMP-003", "FR-006")
        model = _make_model(impacts=[imp1, imp2, imp3])
        groups = group_impacts_by_receptor(model)
        self.assertIn("FR-014", groups)
        self.assertIn("FR-006", groups)
        self.assertEqual(len(groups["FR-014"]), 2)
        self.assertEqual(len(groups["FR-006"]), 1)

    def test_excludes_descartado(self):
        imp1 = _make_impact("IMP-001", "FR-014")
        imp2 = _make_impact("IMP-002", "FR-014", status="DESCARTADO_JUSTIFICADO")
        model = _make_model(impacts=[imp1, imp2])
        groups = group_impacts_by_receptor(model)
        # Only IMP-001 should be in the group
        ids = [i.impact_id for i in groups["FR-014"]]
        self.assertIn("IMP-001", ids)
        self.assertNotIn("IMP-002", ids)

    def test_keeps_indeterminado(self):
        imp = _make_impact("IMP-001", "FR-007", nature="INDETERMINADO",
                           status="INDETERMINADO")
        model = _make_model(impacts=[imp])
        groups = group_impacts_by_receptor(model)
        self.assertIn("FR-007", groups)
        self.assertEqual(len(groups["FR-007"]), 1)

    def test_keeps_pendiente_datos(self):
        imp = _make_impact("IMP-001", "FR-014", status="PENDIENTE_DATOS")
        model = _make_model(impacts=[imp])
        groups = group_impacts_by_receptor(model)
        self.assertIn("FR-014", groups)

    def test_empty_model(self):
        model = Phase6Model(expediente_id="EMPTY")
        groups = group_impacts_by_receptor(model)
        self.assertEqual(groups, {})

    def test_no_mutation(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        original_len = len(model.impacts)
        group_impacts_by_receptor(model)
        self.assertEqual(len(model.impacts), original_len)


# ---------------------------------------------------------------------------
# 4. detect_cumulative_impact_groups
# ---------------------------------------------------------------------------

class TestDetectCumulativeImpactGroups(unittest.TestCase):

    def test_two_fr014_impacts_form_group(self):
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO",
                            action_id="AC-002")
        model = _make_model(impacts=[imp1, imp2])
        groups = detect_cumulative_impact_groups(model)
        self.assertIn("FR-014", groups)
        self.assertIn("IMP-001", groups["FR-014"])
        self.assertIn("IMP-002", groups["FR-014"])

    def test_two_fr006_impacts_form_group(self):
        imp1 = _make_impact("IMP-001", "FR-006", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-006", nature="NEGATIVO")
        model = _make_model(impacts=[imp1, imp2])
        groups = detect_cumulative_impact_groups(model)
        self.assertIn("FR-006", groups)

    def test_two_fr003_impacts_form_group(self):
        imp1 = _make_impact("IMP-001", "FR-003", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-003", nature="MIXTO")
        model = _make_model(impacts=[imp1, imp2])
        groups = detect_cumulative_impact_groups(model)
        self.assertIn("FR-003", groups)

    def test_single_impact_no_group(self):
        imp = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        model = _make_model(impacts=[imp])
        groups = detect_cumulative_impact_groups(model)
        # Solo 1 impacto no sensible → no debe formar grupo
        self.assertNotIn("FR-014", groups)

    def test_descartado_not_counted(self):
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO",
                            status="DESCARTADO_JUSTIFICADO")
        model = _make_model(impacts=[imp1, imp2])
        groups = detect_cumulative_impact_groups(model)
        # imp2 descartado no cuenta: solo 1 impacto relevante
        self.assertNotIn("FR-014", groups)

    def test_positivo_not_cumulative(self):
        """Impactos POSITIVO no se acumulan con reglas de presión negativa."""
        imp1 = _make_impact("IMP-001", "FR-013", nature="POSITIVO")
        imp2 = _make_impact("IMP-002", "FR-013", nature="POSITIVO")
        model = _make_model(impacts=[imp1, imp2])
        groups = detect_cumulative_impact_groups(model)
        # POSITIVO no está en _CUMULATIVE_NATURES
        self.assertNotIn("FR-013", groups)

    def test_indeterminado_sensitive_single_forms_group(self):
        """Un solo impacto INDETERMINADO en receptor sensible → cautela acumulativa."""
        imp = _make_impact(
            "IMP-001", "FR-007",
            nature="INDETERMINADO", status="INDETERMINADO",
            significance="INDETERMINADO"
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-007"])
        groups = detect_cumulative_impact_groups(model)
        self.assertIn("FR-007", groups)

    def test_no_mutation(self):
        imp1 = _make_impact("IMP-001", "FR-014")
        imp2 = _make_impact("IMP-002", "FR-014")
        model = _make_model(impacts=[imp1, imp2])
        original_len = len(model.impacts)
        detect_cumulative_impact_groups(model)
        self.assertEqual(len(model.impacts), original_len)

    def test_empty_model_no_groups(self):
        model = Phase6Model(expediente_id="EMPTY")
        groups = detect_cumulative_impact_groups(model)
        self.assertEqual(groups, {})


# ---------------------------------------------------------------------------
# 5. detect_synergistic_impact_groups
# ---------------------------------------------------------------------------

class TestDetectSynergisticImpactGroups(unittest.TestCase):

    def _model_with_receptors(self, *receptor_ids: str) -> Phase6Model:
        impacts = [
            _make_impact(f"IMP-{i+1:03d}", r, nature="NEGATIVO")
            for i, r in enumerate(receptor_ids)
        ]
        return _make_model(impacts=impacts, receptor_ids=list(receptor_ids))

    def test_aire_ruido_detected(self):
        model = self._model_with_receptors("FR-006", "FR-014")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("aire_ruido", groups)

    def test_suelo_hidrologia_detected(self):
        model = self._model_with_receptors("FR-003", "FR-004")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("suelo_hidrologia", groups)

    def test_hidrologia_red_natura_via_fr009(self):
        model = self._model_with_receptors("FR-004", "FR-009")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("hidrologia_red_natura", groups)

    def test_hidrologia_red_natura_via_fr010(self):
        model = self._model_with_receptors("FR-004", "FR-010")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("hidrologia_red_natura", groups)

    def test_biodiversidad_red_natura_flora_fr009(self):
        model = self._model_with_receptors("FR-007", "FR-009")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("biodiversidad_red_natura", groups)

    def test_biodiversidad_red_natura_fauna_fr010(self):
        model = self._model_with_receptors("FR-008", "FR-010")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("biodiversidad_red_natura", groups)

    def test_clima_riesgos_detected(self):
        model = self._model_with_receptors("FR-015", "FR-016")
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("clima_riesgos", groups)

    def test_only_one_side_no_synergy(self):
        """Solo FR-006 sin FR-014 no activa aire_ruido."""
        model = self._model_with_receptors("FR-006")
        groups = detect_synergistic_impact_groups(model)
        self.assertNotIn("aire_ruido", groups)

    def test_descartado_not_counted(self):
        imp_aire = _make_impact("IMP-001", "FR-006", nature="NEGATIVO")
        imp_ruido = _make_impact("IMP-002", "FR-014", nature="NEGATIVO",
                                  status="DESCARTADO_JUSTIFICADO")
        model = _make_model(
            impacts=[imp_aire, imp_ruido],
            receptor_ids=["FR-006", "FR-014"],
        )
        groups = detect_synergistic_impact_groups(model)
        # imp_ruido descartado → lado B vacío → no sinergia
        self.assertNotIn("aire_ruido", groups)

    def test_impact_ids_in_group(self):
        imp_006 = _make_impact("IMP-001", "FR-006", nature="NEGATIVO")
        imp_014 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO")
        model = _make_model(
            impacts=[imp_006, imp_014],
            receptor_ids=["FR-006", "FR-014"],
        )
        groups = detect_synergistic_impact_groups(model)
        self.assertIn("IMP-001", groups["aire_ruido"])
        self.assertIn("IMP-002", groups["aire_ruido"])

    def test_no_mutation(self):
        model = self._model_with_receptors("FR-006", "FR-014")
        original_len = len(model.impacts)
        detect_synergistic_impact_groups(model)
        self.assertEqual(len(model.impacts), original_len)


# ---------------------------------------------------------------------------
# 6. extract_unresolved_cumulative_gaps
# ---------------------------------------------------------------------------

class TestExtractUnresolvedCumulativeGaps(unittest.TestCase):

    def test_collects_data_gaps_from_indeterminado_impacts(self):
        imp = _make_impact(
            "IMP-001", "FR-007",
            nature="INDETERMINADO", status="INDETERMINADO",
            data_gaps=["GAP-FI-007-001", "CONT-001"],
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-007"])
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertIn("GAP-FI-007-001", gaps)
        self.assertIn("CONT-001", gaps)

    def test_collects_data_gaps_from_significance_indeterminado(self):
        imp = _make_impact(
            "IMP-001", "FR-014",
            significance="INDETERMINADO",
            data_gaps=["GAP-FI-014-001"],
        )
        model = _make_model(impacts=[imp])
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertIn("GAP-FI-014-001", gaps)

    def test_collects_critical_gaps_from_receptors(self):
        imp = _make_impact("IMP-001", "FR-010", nature="INDETERMINADO")
        model = _make_model(
            impacts=[imp],
            receptor_ids=["FR-010"],
            receptor_critical_gaps={"FR-010": ["CRIT-GAP-001"]},
        )
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertIn("CRIT-GAP-001", gaps)

    def test_deduplicates_gaps(self):
        imp1 = _make_impact("IMP-001", "FR-007",
                             nature="INDETERMINADO", status="INDETERMINADO",
                             data_gaps=["GAP-001", "GAP-002"])
        imp2 = _make_impact("IMP-002", "FR-007",
                             nature="INDETERMINADO", status="INDETERMINADO",
                             data_gaps=["GAP-001", "GAP-003"])
        model = _make_model(
            impacts=[imp1, imp2],
            receptor_ids=["FR-007"],
        )
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertEqual(gaps.count("GAP-001"), 1)

    def test_descartado_gaps_not_collected(self):
        imp = _make_impact(
            "IMP-001", "FR-014",
            status="DESCARTADO_JUSTIFICADO",
            data_gaps=["GAP-DESCARTADO"],
        )
        model = _make_model(impacts=[imp])
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertNotIn("GAP-DESCARTADO", gaps)

    def test_empty_model_no_gaps(self):
        model = Phase6Model(expediente_id="EMPTY")
        gaps = extract_unresolved_cumulative_gaps(model)
        self.assertEqual(gaps, [])

    def test_no_mutation(self):
        imp = _make_impact("IMP-001", "FR-007", nature="INDETERMINADO",
                           data_gaps=["GAP-001"])
        model = _make_model(impacts=[imp], receptor_ids=["FR-007"])
        original_gaps = list(imp.data_gaps)
        extract_unresolved_cumulative_gaps(model)
        self.assertEqual(imp.data_gaps, original_gaps)


# ---------------------------------------------------------------------------
# 7. build_cumulative_synergistic_markdown
# ---------------------------------------------------------------------------

class TestBuildCumulativeSynergisticMarkdown(unittest.TestCase):

    def _model_with_cumulative_and_synergistic(self) -> Phase6Model:
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO", action_id="AC-002")
        imp3 = _make_impact("IMP-003", "FR-006", nature="NEGATIVO")
        return _make_model(
            impacts=[imp1, imp2, imp3],
            receptor_ids=["FR-014", "FR-006"],
        )

    def test_returns_string(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIsInstance(md, str)

    def test_contains_c51_section(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("C.5.1", md)

    def test_contains_c52_section(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("C.5.2", md)

    def test_contains_c53_section(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("C.5.3", md)

    def test_contains_c54_section(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("C.5.4", md)

    def test_contains_c55_section(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("C.5.5", md)

    def test_no_forbidden_phrase_no_existen_acumulativos(self):
        model = Phase6Model(expediente_id="EMPTY")
        md = build_cumulative_synergistic_markdown(model)
        self.assertNotIn("no existen efectos acumulativos", md.lower())

    def test_no_forbidden_phrase_se_descartan_acumulativos(self):
        model = Phase6Model(expediente_id="EMPTY")
        md = build_cumulative_synergistic_markdown(model)
        self.assertNotIn("se descartan efectos acumulativos", md.lower())

    def test_no_forbidden_phrase_no_existen_sinergias(self):
        model = Phase6Model(expediente_id="EMPTY")
        md = build_cumulative_synergistic_markdown(model)
        self.assertNotIn("no existen sinergias", md.lower())

    def test_no_forbidden_phrase_se_descartan_sinergias(self):
        model = Phase6Model(expediente_id="EMPTY")
        md = build_cumulative_synergistic_markdown(model)
        self.assertNotIn("se descartan sinergias", md.lower())

    def test_contains_cautela_when_no_data(self):
        model = Phase6Model(expediente_id="EMPTY")
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("cautela metodol", md.lower())

    def test_contains_no_modifica_valoracion(self):
        model = _make_model()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("no modifica", md.lower())

    def test_cumulative_group_mentioned(self):
        model = self._model_with_cumulative_and_synergistic()
        md = build_cumulative_synergistic_markdown(model)
        self.assertIn("FR-014", md)

    def test_synergy_mentioned_when_both_sides(self):
        model = self._model_with_cumulative_and_synergistic()
        md = build_cumulative_synergistic_markdown(model)
        # FR-006 + FR-014 → aire_ruido synergy (rendered as "Aire ruido")
        self.assertIn("Aire ruido", md)

    def test_not_closes_indeterminate_impacts(self):
        """El markdown debe declarar la incertidumbre, no cerrar los impactos INDETERMINADO."""
        imp = _make_impact("IMP-001", "FR-007", nature="INDETERMINADO",
                           status="INDETERMINADO")
        model = _make_model(impacts=[imp], receptor_ids=["FR-007"])
        md = build_cumulative_synergistic_markdown(model)
        # No debe afirmar que el impacto es compatible
        self.assertNotIn("impacto compatible", md.lower())
        # No debe resolver / cerrar el INDETERMINADO de forma afirmativa
        self.assertNotIn("impacto resuelto", md.lower())
        # Debe mencionar explícitamente que no cierra los INDETERMINADO
        self.assertTrue(
            "indeterminado" in md.upper()
            or "incertidumbre" in md.lower()
            or "no quedan" in md.lower(),
            "Debe mencionar INDETERMINADO o incertidumbre de forma explícita",
        )

    def test_no_mutation(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        original_len = len(model.impacts)
        build_cumulative_synergistic_markdown(model)
        self.assertEqual(len(model.impacts), original_len)


# ---------------------------------------------------------------------------
# 8. build_cumulative_synergistic_section
# ---------------------------------------------------------------------------

class TestBuildCumulativeSynergisticSection(unittest.TestCase):

    def test_returns_result(self):
        model = _make_model()
        result = build_cumulative_synergistic_section(model)
        self.assertIsInstance(result, CumulativeSynergyResult)

    def test_markdown_not_empty(self):
        model = _make_model()
        result = build_cumulative_synergistic_section(model)
        self.assertGreater(len(result.markdown), 100)

    def test_cumulative_groups_populated(self):
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO")
        model = _make_model(impacts=[imp1, imp2])
        result = build_cumulative_synergistic_section(model)
        self.assertIn("FR-014", result.cumulative_groups)

    def test_synergistic_groups_populated(self):
        imp1 = _make_impact("IMP-001", "FR-006", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO")
        model = _make_model(
            impacts=[imp1, imp2],
            receptor_ids=["FR-006", "FR-014"],
        )
        result = build_cumulative_synergistic_section(model)
        self.assertIn("aire_ruido", result.synergistic_groups)

    def test_unresolved_gaps_populated(self):
        imp = _make_impact(
            "IMP-001", "FR-007",
            nature="INDETERMINADO", status="INDETERMINADO",
            data_gaps=["GAP-FI-007-001"],
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-007"])
        result = build_cumulative_synergistic_section(model)
        self.assertIn("GAP-FI-007-001", result.unresolved_gaps)

    def test_no_mutation_of_model(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        original_len = len(model.impacts)
        original_pva_count = len(model.pva_programs)
        build_cumulative_synergistic_section(model)
        self.assertEqual(len(model.impacts), original_len)
        self.assertEqual(len(model.pva_programs), original_pva_count)

    def test_no_new_impacts_created(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        result = build_cumulative_synergistic_section(model)
        # Result has no impacts field — check model unchanged
        self.assertEqual(len(model.impacts), 1)

    def test_no_valoracion_changes(self):
        imp = _make_impact("IMP-001", "FR-014", significance="COMPATIBLE")
        model = _make_model(impacts=[imp])
        build_cumulative_synergistic_section(model)
        # significance_without_measures should remain unchanged
        self.assertEqual(model.impacts[0].significance_without_measures, "COMPATIBLE")

    def test_issues_generated_for_cumulative_group(self):
        imp1 = _make_impact("IMP-001", "FR-014", nature="NEGATIVO")
        imp2 = _make_impact("IMP-002", "FR-014", nature="NEGATIVO")
        model = _make_model(impacts=[imp1, imp2])
        result = build_cumulative_synergistic_section(model)
        codes = [i.code for i in result.issues]
        self.assertTrue(any("CS-I001" in c or "CS-W001" in c for c in codes))

    def test_empty_model_returns_valid_result(self):
        model = Phase6Model(expediente_id="EMPTY")
        result = build_cumulative_synergistic_section(model)
        self.assertIsInstance(result, CumulativeSynergyResult)
        self.assertGreater(len(result.markdown), 0)
        self.assertGreater(len(result.warnings), 0)

    def test_notes_not_empty(self):
        model = _make_model()
        result = build_cumulative_synergistic_section(model)
        self.assertGreater(len(result.notes), 0)


# ---------------------------------------------------------------------------
# 9. write_cumulative_synergistic_outputs
# ---------------------------------------------------------------------------

class TestWriteCumulativeSynergisticOutputs(unittest.TestCase):

    def _make_result(self) -> CumulativeSynergyResult:
        model = _make_model()
        return build_cumulative_synergistic_section(model)

    def test_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_cumulative_synergistic_outputs(result, Path(tmp))
            self.assertTrue(json_path.exists())

    def test_creates_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            _, md_path = write_cumulative_synergistic_outputs(result, Path(tmp))
            self.assertTrue(md_path.exists())

    def test_json_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_cumulative_synergistic_outputs(result, Path(tmp))
            self.assertEqual(json_path.name, "cumulative_synergistic_result.json")

    def test_md_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            _, md_path = write_cumulative_synergistic_outputs(result, Path(tmp))
            self.assertEqual(md_path.name, "C5_acumulativos_sinergicos.md")

    def test_json_loadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            json_path, _ = write_cumulative_synergistic_outputs(result, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("cumulative_groups", data)
            self.assertIn("synergistic_groups", data)
            self.assertIn("unresolved_gaps", data)

    def test_md_contains_c5_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._make_result()
            _, md_path = write_cumulative_synergistic_outputs(result, Path(tmp))
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("C.5", content)

    def test_creates_dir_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "impactos" / "new"
            result = self._make_result()
            write_cumulative_synergistic_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())


# ---------------------------------------------------------------------------
# 10. CLI phase6-cumulative
# ---------------------------------------------------------------------------

class TestCLICumulative(unittest.TestCase):

    def _minimal_model_dict(self, impacts=None) -> dict:
        if impacts is None:
            impacts = [{
                "impact_id": "IMP-001",
                "action_id": "AC-001",
                "receptor_id": "FR-014",
                "name": "Ruido",
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
            }]
        return {
            "expediente_id": "TEST-CLI-IM08",
            "actions": [{"action_id": "AC-001", "name": "Op", "description": "",
                          "action_type": "OPERACION", "operation_code": None,
                          "source_refs": [], "notes": []}],
            "receptor_factors": [{"receptor_id": "FR-014", "inventory_factor_id": "FI-014",
                                   "name": "Ruido", "inventory_semaphore": "NO_CONSTA",
                                   "ready_from_inventory": False, "critical_gaps": [],
                                   "notes": ["test"]}],
            "impacts": impacts,
            "measures": [],
            "pva_programs": [],
            "warnings": [],
            "notes": [],
        }

    def test_no_model_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            ret = main([str(exp_dir), "phase6-cumulative"])
            self.assertEqual(ret, 1)

    def test_valid_model_exits_0(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            ret = main([str(exp_dir), "phase6-cumulative"])
            self.assertEqual(ret, 0)

    def test_no_write_creates_no_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-cumulative"])
            self.assertFalse((impactos_dir / "cumulative_synergistic_result.json").exists())
            self.assertFalse((impactos_dir / "C5_acumulativos_sinergicos.md").exists())

    def test_with_write_creates_files(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-cumulative", "--write"])
            self.assertTrue((impactos_dir / "cumulative_synergistic_result.json").exists())
            self.assertTrue((impactos_dir / "C5_acumulativos_sinergicos.md").exists())

    def test_fallback_to_measures_model(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_measures.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            ret = main([str(exp_dir), "phase6-cumulative"])
            self.assertEqual(ret, 0)

    def test_fallback_to_impacts_model(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_impacts.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            ret = main([str(exp_dir), "phase6-cumulative"])
            self.assertEqual(ret, 0)

    def test_output_json_has_sections(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-cumulative", "--write"])
            data = json.loads(
                (impactos_dir / "cumulative_synergistic_result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("cumulative_groups", data)
            self.assertIn("synergistic_groups", data)
            self.assertIn("unresolved_gaps", data)
            self.assertIn("markdown", data)

    def test_md_file_contains_c5(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            (impactos_dir / "phase6_model_with_pva.json").write_text(
                json.dumps(self._minimal_model_dict()), encoding="utf-8"
            )
            main([str(exp_dir), "phase6-cumulative", "--write"])
            content = (impactos_dir / "C5_acumulativos_sinergicos.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("C.5", content)


# ---------------------------------------------------------------------------
# 11. build_cumulative_synergistic_section_from_json
# ---------------------------------------------------------------------------

class TestBuildFromJSON(unittest.TestCase):

    def _write_minimal_json(self, tmp_path: Path) -> Path:
        data = {
            "expediente_id": "TEST-JSON-IM08",
            "actions": [],
            "receptor_factors": [],
            "impacts": [{
                "impact_id": "IMP-001",
                "action_id": "AC-001",
                "receptor_id": "FR-014",
                "name": "Ruido",
                "nature": "NEGATIVO",
                "status": "VALORADO",
                "significance_without_measures": "COMPATIBLE",
                "significance_with_measures": "COMPATIBLE",
                "conesa_attributes": {},
                "data_gaps": [],
                "source_refs": [],
                "measure_ids": [],
                "pva_ids": [],
                "warnings": [],
                "notes": [],
            }],
            "measures": [],
            "pva_programs": [],
            "warnings": [],
            "notes": [],
        }
        path = tmp_path / "model.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_returns_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_minimal_json(Path(tmp))
            result = build_cumulative_synergistic_section_from_json(path)
            self.assertIsInstance(result, CumulativeSynergyResult)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            build_cumulative_synergistic_section_from_json(Path("no_existe.json"))

    def test_invalid_json_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not: valid}", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_cumulative_synergistic_section_from_json(bad)


if __name__ == "__main__":
    unittest.main()
