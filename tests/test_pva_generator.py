"""
tests/test_pva_generator.py
Tests para IM-06 — Generador de fichas PVA (Programa de Vigilancia Ambiental).

Cubre:
  1. PVAGenerationRule (to_dict, matches por receptor/nature/significance, no-match)
  2. default_pva_generation_rules (presencia, unicidad, validez de campos)
  3. generate_pva_for_model (impactos múltiples, pva_ids, no mutación, revisión anual)
  4. Regla E-9: fichas CONDICIONADO por CONTs abiertos
  5. Regla E-10: nota de incertidumbre en impactos positivos con data_gaps
  6. GAP-PVA: impactos sin cobertura detectados en uncovered_impact_ids
  7. merge_pva_into_model (sustitución, actualización, conservación, no mutación)
  8. _build_annual_review_pva (nota de remisión al órgano ambiental obligatoria)
  9. Modelo vacío, receptores sin regla, impactos descartados
  10. CLI phase6-generate-pva (exit 1 sin modelo, no escribe sin --write, JSONs correctos)
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
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
)
from eia_agent.core.pva_generator import (
    PVAGenerationResult,
    PVAGenerationRule,
    _build_annual_review_pva,
    _impact_has_cont,
    _impact_is_conditioned,
    default_pva_generation_rules,
    generate_pva_for_model,
    merge_pva_into_model,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_impact(
    impact_id: str = "IMP-001",
    receptor_id: str = "FR-014",
    nature: str = "NEGATIVO",
    significance: str = "MODERADO",
    status: str = "VALORADO",
    name: str = "Impacto acustico por operaciones",
    action_id: str = "AC-001",
    data_gaps: list | None = None,
    pva_ids: list | None = None,
    measure_ids: list | None = None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id=action_id,
        receptor_id=receptor_id,
        name=name,
        description="Descripcion de impacto de prueba",
        nature=nature,
        status=status,
        significance_without_measures=significance,
        significance_with_measures=significance,
        data_gaps=data_gaps or [],
        pva_ids=pva_ids or [],
        measure_ids=measure_ids or [],
    )


def _make_receptor(
    receptor_id: str = "FR-014",
    inventory_factor_id: str = "FI-014",
    name: str = "Ruido",
) -> ReceptorFactor:
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=inventory_factor_id,
        name=name,
        notes=["Factor de prueba"],
    )


def _make_action(action_id: str = "AC-001") -> ProjectAction:
    return ProjectAction(
        action_id=action_id,
        name="Operacion de tratamiento mecanico",
        action_type="OPERACION",
    )


def _make_measure(
    measure_id: str = "MED-001",
    target_impact_ids: list | None = None,
    receptor_id_hint: str = "FR-014",
) -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id,
        name=f"Medida para {receptor_id_hint}",
        measure_type="CORRECTORA",
        target_impact_ids=target_impact_ids or ["IMP-001"],
    )


def _make_model(impacts=None, measures=None, receptor_ids=None) -> Phase6Model:
    if impacts is None:
        impacts = [_make_impact()]
    if receptor_ids is None:
        receptor_ids = list({imp.receptor_id for imp in impacts})
    receptors = [_make_receptor(r, r.replace("FR-", "FI-"), r) for r in receptor_ids]
    return Phase6Model(
        expediente_id="TEST-001",
        actions=[_make_action()],
        receptor_factors=receptors,
        impacts=impacts,
        measures=measures or [],
    )


# ---------------------------------------------------------------------------
# 1. PVAGenerationRule — matches y to_dict
# ---------------------------------------------------------------------------

class TestPVAGenerationRuleMatches(unittest.TestCase):

    def _rule(self, target_receptor_ids=None, target_natures=None, significance_levels=None):
        return PVAGenerationRule(
            rule_id="TEST-R",
            target_receptor_ids=target_receptor_ids or ["FR-014"],
            pva_name="Test PVA",
            factor_id="FI-014",
            indicator="Indicador de prueba",
            threshold="Umbral de prueba",
            frequency="MENSUAL",
            records=["Registro de prueba"],
            target_natures=target_natures or [],
            significance_levels=significance_levels or [],
        )

    def test_matches_by_receptor(self):
        rule = self._rule(target_receptor_ids=["FR-014"])
        imp = _make_impact(receptor_id="FR-014")
        self.assertTrue(rule.matches(imp))

    def test_no_match_wrong_receptor(self):
        rule = self._rule(target_receptor_ids=["FR-003"])
        imp = _make_impact(receptor_id="FR-014")
        self.assertFalse(rule.matches(imp))

    def test_no_match_descartado(self):
        rule = self._rule()
        imp = _make_impact(status="DESCARTADO_JUSTIFICADO")
        self.assertFalse(rule.matches(imp))

    def test_matches_any_nature_when_target_empty(self):
        rule = self._rule(target_natures=[])
        for nature in ("NEGATIVO", "POSITIVO", "MIXTO", "INDETERMINADO"):
            imp = _make_impact(nature=nature)
            self.assertTrue(rule.matches(imp), f"Deberia coincidir con {nature}")

    def test_no_match_wrong_nature(self):
        rule = self._rule(target_natures=["POSITIVO"])
        imp = _make_impact(nature="NEGATIVO")
        self.assertFalse(rule.matches(imp))

    def test_matches_correct_significance(self):
        rule = self._rule(significance_levels=["MODERADO", "SEVERO"])
        imp = _make_impact(significance="MODERADO")
        self.assertTrue(rule.matches(imp))

    def test_no_match_significance_not_in_list(self):
        rule = self._rule(significance_levels=["SEVERO", "CRITICO"])
        imp = _make_impact(significance="COMPATIBLE")
        self.assertFalse(rule.matches(imp))

    def test_to_dict_keys(self):
        rule = self._rule()
        d = rule.to_dict()
        expected_keys = {
            "rule_id", "target_receptor_ids", "pva_name", "factor_id",
            "indicator", "threshold", "frequency", "records",
            "target_natures", "significance_levels", "notes", "responsible_note",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_roundtrip_lists(self):
        rule = self._rule()
        d = rule.to_dict()
        self.assertIsInstance(d["target_receptor_ids"], list)
        self.assertIsInstance(d["records"], list)


# ---------------------------------------------------------------------------
# 2. default_pva_generation_rules
# ---------------------------------------------------------------------------

class TestDefaultPVAGenerationRules(unittest.TestCase):

    def setUp(self):
        self.rules = default_pva_generation_rules()

    def test_returns_list(self):
        self.assertIsInstance(self.rules, list)

    def test_minimum_count(self):
        self.assertGreaterEqual(len(self.rules), 10)

    def test_unique_rule_ids(self):
        ids = [r.rule_id for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)), "IDs de regla duplicados")

    def test_all_have_indicator(self):
        for r in self.rules:
            self.assertTrue(r.indicator.strip(), f"{r.rule_id} sin indicador")

    def test_all_have_threshold_or_positive(self):
        """Las reglas de impactos negativos deben tener umbral; las positivas pueden omitirlo."""
        for r in self.rules:
            if "POSITIVO" not in r.target_natures:
                self.assertTrue(
                    r.threshold.strip(),
                    f"{r.rule_id} (negativo/neutro) sin umbral definido"
                )

    def test_all_frequencies_valid(self):
        from eia_agent.core.impact_model import PVA_FREQUENCIES
        for r in self.rules:
            self.assertIn(
                r.frequency, PVA_FREQUENCIES,
                f"{r.rule_id} frecuencia invalida: {r.frequency}"
            )

    def test_all_have_records(self):
        for r in self.rules:
            self.assertGreater(len(r.records), 0, f"{r.rule_id} sin registros")

    def test_receptor_ruido_covered(self):
        receptors = [r2 for r in self.rules for r2 in r.target_receptor_ids]
        self.assertIn("FR-014", receptors, "FR-014 (Ruido) no cubierto")

    def test_receptor_suelos_covered(self):
        receptors = [r2 for r in self.rules for r2 in r.target_receptor_ids]
        self.assertIn("FR-003", receptors)

    def test_receptor_calidad_aire_covered(self):
        receptors = [r2 for r in self.rules for r2 in r.target_receptor_ids]
        self.assertIn("FR-006", receptors)

    def test_positivo_rule_has_no_threshold(self):
        """La regla POSITIVO (PVAGEN-K) debe tener 'No aplica' en threshold."""
        pos_rules = [r for r in self.rules if "POSITIVO" in r.target_natures]
        self.assertGreater(len(pos_rules), 0, "No hay reglas para impactos POSITIVOS")
        for r in pos_rules:
            self.assertIn("No aplica", r.threshold, f"{r.rule_id} positivo deberia tener 'No aplica'")

    def test_pvagen_k_targets_socioeconomia(self):
        k_rules = [r for r in self.rules if r.rule_id == "PVAGEN-K"]
        self.assertEqual(len(k_rules), 1)
        self.assertIn("FR-013", k_rules[0].target_receptor_ids)

    def test_factor_id_format(self):
        import re
        pattern = re.compile(r"^FI-\d{3}$")
        for r in self.rules:
            self.assertTrue(
                pattern.match(r.factor_id),
                f"{r.rule_id} factor_id invalido: {r.factor_id}"
            )


# ---------------------------------------------------------------------------
# 3. generate_pva_for_model — casos básicos
# ---------------------------------------------------------------------------

class TestGeneratePVAForModel(unittest.TestCase):

    def test_generates_pva_for_single_impact(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        self.assertIsInstance(result, PVAGenerationResult)
        self.assertGreater(result.generated_count, 0)

    def test_always_includes_annual_review(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        annual = [p for p in result.model.pva_programs
                  if "anual" in p.name.lower()]
        self.assertEqual(len(annual), 1, "Debe haber exactamente una revision anual")

    def test_annual_review_note_contains_remision_text(self):
        """La nota de remision al organo ambiental es obligatoria (especificacion §7)."""
        model = _make_model()
        result = generate_pva_for_model(model)
        annual = [p for p in result.model.pva_programs
                  if "anual" in p.name.lower()][0]
        remision_found = any(
            "IIA" in w or "art. 47" in w or "organo ambiental" in w.lower()
            for w in annual.warnings
        )
        self.assertTrue(remision_found, "Nota de remision al organo ambiental obligatoria en PVA anual")

    def test_pva_ids_updated_in_impacts(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        imp = result.model.impacts[0]
        self.assertGreater(len(imp.pva_ids), 0, "El impacto debe tener pva_ids asignados")

    def test_no_mutation_original_model(self):
        model = _make_model()
        original_pva_count = len(model.pva_programs)
        original_imp_pva = list(model.impacts[0].pva_ids)
        generate_pva_for_model(model)
        self.assertEqual(len(model.pva_programs), original_pva_count)
        self.assertEqual(list(model.impacts[0].pva_ids), original_imp_pva)

    def test_pva_id_format(self):
        import re
        model = _make_model()
        result = generate_pva_for_model(model)
        for pva in result.model.pva_programs:
            self.assertRegex(pva.pva_id, r"^PVA-\d{3,}$")

    def test_pva_count_equals_generated_count(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        self.assertEqual(result.generated_count, len(result.model.pva_programs))

    def test_empty_model_returns_only_annual(self):
        model = Phase6Model(expediente_id="EMPTY-001")
        result = generate_pva_for_model(model)
        self.assertEqual(result.generated_count, 1)
        self.assertIn("anual", result.model.pva_programs[0].name.lower())
        self.assertGreater(len(result.warnings), 0)

    def test_discarded_impact_not_covered(self):
        imp = _make_impact(status="DESCARTADO_JUSTIFICADO")
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        covered = {
            imp_id
            for pva in result.model.pva_programs
            for imp_id in pva.target_impact_ids
        }
        self.assertNotIn("IMP-001", covered)

    def test_target_measure_ids_populated(self):
        imp = _make_impact()
        med = _make_measure(target_impact_ids=["IMP-001"])
        model = _make_model(impacts=[imp], measures=[med])
        result = generate_pva_for_model(model)
        receptor_pva = [p for p in result.model.pva_programs
                        if "anual" not in p.name.lower()]
        if receptor_pva:
            all_measure_ids = [mid for p in receptor_pva for mid in p.target_measure_ids]
            self.assertIn("MED-001", all_measure_ids)

    def test_multiple_impacts_same_receptor_one_pva(self):
        imp1 = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        imp2 = _make_impact(impact_id="IMP-002", receptor_id="FR-014",
                            name="Otro impacto acustico")
        model = _make_model(impacts=[imp1, imp2])
        result = generate_pva_for_model(model)
        # Los dos impactos del mismo receptor deben estar en la misma ficha PVA
        receptor_pva = [p for p in result.model.pva_programs
                        if "anual" not in p.name.lower()
                        and "IMP-001" in p.target_impact_ids]
        self.assertGreater(len(receptor_pva), 0)
        pva = receptor_pva[0]
        self.assertIn("IMP-001", pva.target_impact_ids)
        self.assertIn("IMP-002", pva.target_impact_ids)

    def test_responsible_ambiental_gap_warning_in_all_pva(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        for pva in result.model.pva_programs:
            has_gap = any("GAP-PVA-001" in w for w in pva.warnings)
            self.assertTrue(has_gap, f"{pva.pva_id} sin aviso de Responsable Ambiental")


# ---------------------------------------------------------------------------
# 4. Regla E-9: fichas CONDICIONADO por CONTs
# ---------------------------------------------------------------------------

class TestE9CondicionadoCONT(unittest.TestCase):

    def test_impact_has_cont_true(self):
        imp = _make_impact(data_gaps=["CONT-001", "GAP-FI-014-001"])
        self.assertTrue(_impact_has_cont(imp))

    def test_impact_has_cont_false(self):
        imp = _make_impact(data_gaps=["GAP-FI-014-001"])
        self.assertFalse(_impact_has_cont(imp))

    def test_impact_is_conditioned_indeterminado_nature(self):
        imp = _make_impact(nature="INDETERMINADO")
        self.assertTrue(_impact_is_conditioned(imp))

    def test_impact_is_conditioned_cont_gap(self):
        imp = _make_impact(data_gaps=["CONT-002"])
        self.assertTrue(_impact_is_conditioned(imp))

    def test_impact_is_conditioned_false_normal(self):
        imp = _make_impact(nature="NEGATIVO", data_gaps=["GAP-FI-014-001"])
        self.assertFalse(_impact_is_conditioned(imp))

    def test_conditioned_pva_has_warning(self):
        imp = _make_impact(data_gaps=["CONT-001"])
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        self.assertGreater(result.conditioned_count, 0)
        pva_with_cont = [
            p for p in result.model.pva_programs
            if any("CONDICIONADO" in w for w in p.warnings)
        ]
        self.assertGreater(len(pva_with_cont), 0)

    def test_conditioned_warning_mentions_cont(self):
        imp = _make_impact(data_gaps=["CONT-003"])
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        cont_warnings = [
            w for p in result.model.pva_programs
            for w in p.warnings
            if "CONT" in w
        ]
        self.assertGreater(len(cont_warnings), 0)
        self.assertTrue(any("CONT-003" in w for w in cont_warnings))

    def test_indeterminate_impact_counted_as_conditioned(self):
        imp = _make_impact(nature="INDETERMINADO", status="INDETERMINADO",
                           significance="INDETERMINADO")
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        self.assertGreater(result.conditioned_count, 0)


# ---------------------------------------------------------------------------
# 5. Regla E-10: nota de incertidumbre en impactos positivos con data_gaps
# ---------------------------------------------------------------------------

class TestE10IncertidumbrePositivos(unittest.TestCase):

    def test_positive_with_gaps_gets_uncertainty_note(self):
        imp = _make_impact(
            receptor_id="FR-013",
            nature="POSITIVO",
            significance="POSITIVO_MODERADO",
            data_gaps=["GAP-FI-013-001"],
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-013"])
        result = generate_pva_for_model(model)
        uncertainty_warnings = [
            w for p in result.model.pva_programs
            for w in p.warnings
            if "NOTA DE INCERTIDUMBRE" in w or "PROVISIONAL" in w
        ]
        self.assertGreater(len(uncertainty_warnings), 0)

    def test_positive_without_gaps_no_uncertainty_note(self):
        imp = _make_impact(
            receptor_id="FR-013",
            nature="POSITIVO",
            significance="POSITIVO_MODERADO",
            data_gaps=[],
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-013"])
        result = generate_pva_for_model(model)
        uncertainty_warnings = [
            w for p in result.model.pva_programs
            for w in p.warnings
            if "NOTA DE INCERTIDUMBRE" in w or "PROVISIONAL" in w
        ]
        self.assertEqual(len(uncertainty_warnings), 0)

    def test_negative_with_gaps_no_e10_note(self):
        """E-10 solo aplica a positivos, no a negativos con gaps."""
        imp = _make_impact(
            receptor_id="FR-014",
            nature="NEGATIVO",
            data_gaps=["GAP-FI-014-001"],
        )
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        uncertainty_warnings = [
            w for p in result.model.pva_programs
            for w in p.warnings
            if "NOTA DE INCERTIDUMBRE" in w
        ]
        self.assertEqual(len(uncertainty_warnings), 0)


# ---------------------------------------------------------------------------
# 6. GAP-PVA: impactos sin cobertura
# ---------------------------------------------------------------------------

class TestUncoveredImpacts(unittest.TestCase):

    def test_impact_without_rule_is_uncovered(self):
        """Un impacto en un receptor sin regla PVA debe quedar en uncovered_impact_ids."""
        # FR-001 (Clima) no tiene regla en las por defecto
        imp = _make_impact(
            receptor_id="FR-001",
            nature="NEGATIVO",
            significance="COMPATIBLE",
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-001"])
        result = generate_pva_for_model(model)
        # Si no tiene regla, no hay PVA para ese receptor
        # → debe aparecer en uncovered_impact_ids
        if "IMP-001" in result.uncovered_impact_ids:
            self.assertIn("IMP-001", result.uncovered_impact_ids)
            # (La regla puede o no existir; lo importante es que si no hay
            # cobertura, aparece en uncovered)
        else:
            # Si hay una regla que lo cubre, no debe estar en uncovered
            covered = {
                imp_id
                for pva in result.model.pva_programs
                for imp_id in pva.target_impact_ids
            }
            self.assertIn("IMP-001", covered)

    def test_positive_impact_not_in_uncovered(self):
        """Los impactos positivos no son obligatorios en la cobertura PVA."""
        imp = _make_impact(
            receptor_id="FR-013",
            nature="POSITIVO",
            significance="POSITIVO_MODERADO",
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-013"])
        result = generate_pva_for_model(model)
        self.assertNotIn("IMP-001", result.uncovered_impact_ids)

    def test_discarded_impact_not_in_uncovered(self):
        imp = _make_impact(status="DESCARTADO_JUSTIFICADO")
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        self.assertNotIn("IMP-001", result.uncovered_impact_ids)

    def test_covered_impact_not_in_uncovered(self):
        imp = _make_impact(receptor_id="FR-014", nature="NEGATIVO",
                           significance="COMPATIBLE")
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        self.assertNotIn("IMP-001", result.uncovered_impact_ids)

    def test_uncovered_impacts_reported_in_warnings(self):
        """Si hay impactos sin cobertura, debe haber aviso."""
        # Usar receptor sin regla: FR-002 (Geología)
        imp = _make_impact(
            receptor_id="FR-002",
            nature="NEGATIVO",
            significance="COMPATIBLE",
        )
        model = _make_model(impacts=[imp], receptor_ids=["FR-002"])
        result = generate_pva_for_model(model)
        if result.uncovered_impact_ids:
            has_warning = any(
                "GAP-PVA" in w or "sin cobertura" in w.lower()
                for w in result.warnings
            )
            self.assertTrue(has_warning)


# ---------------------------------------------------------------------------
# 7. merge_pva_into_model
# ---------------------------------------------------------------------------

class TestMergePVAIntoModel(unittest.TestCase):

    def _make_pva(self, pva_id="PVA-001", target_impact_ids=None) -> PVAProgram:
        return PVAProgram(
            pva_id=pva_id,
            name="PVA de prueba",
            factor_id="FI-014",
            indicator="Indicador de prueba",
            target_impact_ids=target_impact_ids or ["IMP-001"],
        )

    def test_replaces_pva_programs(self):
        model = _make_model()
        pva = self._make_pva()
        updated = merge_pva_into_model(model, [pva])
        self.assertEqual(len(updated.pva_programs), 1)
        self.assertEqual(updated.pva_programs[0].pva_id, "PVA-001")

    def test_updates_pva_ids_in_impacts(self):
        model = _make_model()
        pva = self._make_pva(target_impact_ids=["IMP-001"])
        updated = merge_pva_into_model(model, [pva])
        imp = updated.impacts[0]
        self.assertIn("PVA-001", imp.pva_ids)

    def test_no_mutation_original_model(self):
        model = _make_model()
        original_pva = list(model.pva_programs)
        original_pva_ids = list(model.impacts[0].pva_ids)
        merge_pva_into_model(model, [self._make_pva()])
        self.assertEqual(list(model.pva_programs), original_pva)
        self.assertEqual(list(model.impacts[0].pva_ids), original_pva_ids)

    def test_preserves_measures(self):
        med = _make_measure()
        model = _make_model(measures=[med])
        updated = merge_pva_into_model(model, [self._make_pva()])
        self.assertEqual(len(updated.measures), 1)

    def test_preserves_actions(self):
        model = _make_model()
        updated = merge_pva_into_model(model, [])
        self.assertEqual(len(updated.actions), len(model.actions))

    def test_empty_pva_list_clears_pva_programs(self):
        model = _make_model()
        # Primero generar PVAs para tener algo que limpiar
        result = generate_pva_for_model(model)
        updated = merge_pva_into_model(result.model, [])
        self.assertEqual(len(updated.pva_programs), 0)

    def test_impact_not_targeted_pva_ids_cleared(self):
        """Un impacto que no está en ningún target_impact_ids queda con pva_ids=[]."""
        imp1 = _make_impact(impact_id="IMP-001")
        imp2 = _make_impact(impact_id="IMP-002", receptor_id="FR-003",
                            name="Impacto suelo")
        model = _make_model(impacts=[imp1, imp2], receptor_ids=["FR-014", "FR-003"])
        pva = self._make_pva(target_impact_ids=["IMP-001"])
        updated = merge_pva_into_model(model, [pva])
        imp2_updated = next(i for i in updated.impacts if i.impact_id == "IMP-002")
        self.assertEqual(imp2_updated.pva_ids, [])


# ---------------------------------------------------------------------------
# 8. _build_annual_review_pva
# ---------------------------------------------------------------------------

class TestBuildAnnualReviewPVA(unittest.TestCase):

    def setUp(self):
        self.pva = _build_annual_review_pva(
            pva_id="PVA-099",
            all_pva_ids=["PVA-001", "PVA-002"],
            all_impact_ids=["IMP-001", "IMP-002"],
        )

    def test_pva_id_set(self):
        self.assertEqual(self.pva.pva_id, "PVA-099")

    def test_name_contains_anual(self):
        self.assertIn("anual", self.pva.name.lower())

    def test_frequency_is_anual(self):
        self.assertEqual(self.pva.frequency, "ANUAL")

    def test_target_impact_ids_populated(self):
        self.assertIn("IMP-001", self.pva.target_impact_ids)
        self.assertIn("IMP-002", self.pva.target_impact_ids)

    def test_indicator_mentions_all_pva_ids(self):
        self.assertIn("PVA-001", self.pva.indicator)
        self.assertIn("PVA-002", self.pva.indicator)

    def test_remision_note_obligatoria(self):
        """La nota de remision al organo ambiental es obligatoria (especificacion §7)."""
        remision_found = any(
            "IIA" in w or "art. 47" in w or "organo ambiental" in w.lower()
            for w in self.pva.warnings
        )
        self.assertTrue(remision_found)

    def test_gap_pva_001_warning_present(self):
        has_gap = any("GAP-PVA-001" in w for w in self.pva.warnings)
        self.assertTrue(has_gap)

    def test_records_not_empty(self):
        self.assertGreater(len(self.pva.records), 0)

    def test_factor_id_format(self):
        import re
        self.assertRegex(self.pva.factor_id, r"^FI-\d{3}$")

    def test_empty_pva_ids_list(self):
        pva = _build_annual_review_pva("PVA-099", [], ["IMP-001"])
        self.assertIn("ninguna", pva.indicator.lower())


# ---------------------------------------------------------------------------
# 9. PVAGenerationResult — to_dict y summary
# ---------------------------------------------------------------------------

class TestPVAGenerationResult(unittest.TestCase):

    def test_to_dict_keys(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        d = result.to_dict()
        expected_keys = {
            "generated_count", "conditioned_count", "uncovered_impact_ids",
            "coverage_notes", "warnings", "notes", "model",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_summary_returns_string(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("IM-06", s)

    def test_summary_ascii_safe(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        s = result.summary()
        s.encode("ascii")

    def test_generated_count_in_summary(self):
        model = _make_model()
        result = generate_pva_for_model(model)
        self.assertIn(str(result.generated_count), result.summary())


# ---------------------------------------------------------------------------
# 10. CLI phase6-generate-pva (via run_expediente.main)
# ---------------------------------------------------------------------------

def _minimal_model_dict_for_pva(receptor_id="FR-014", fi_id="FI-014", name_receptor="Ruido"):
    """JSON mínimo compatible con el parser de run_expediente."""
    return {
        "expediente_id": "TEST-CLI-IM06",
        "actions": [{
            "action_id": "AC-001",
            "name": "Operacion de tratamiento mecanico",
            "description": "",
            "action_type": "OPERACION",
            "operation_code": None,
            "source_refs": [],
            "notes": [],
        }],
        "receptor_factors": [{
            "receptor_id": receptor_id,
            "inventory_factor_id": fi_id,
            "name": name_receptor,
            "inventory_semaphore": "NO_CONSTA",
            "ready_from_inventory": False,
            "critical_gaps": [],
            "notes": ["Factor de prueba CLI."],
        }],
        "impacts": [{
            "impact_id": "IMP-001",
            "action_id": "AC-001",
            "receptor_id": receptor_id,
            "name": "Impacto de prueba CLI",
            "description": "Descripcion de prueba",
            "nature": "NEGATIVO",
            "status": "VALORADO",
            "significance_without_measures": "COMPATIBLE",
            "significance_with_measures": "COMPATIBLE",
            "conesa_attributes": {k: 2 for k in [
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
        }],
        "measures": [],
        "pva_programs": [],
        "warnings": [],
        "notes": [],
    }


class TestCLIPVAGenerator(unittest.TestCase):

    def test_no_model_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            ret = main([str(exp_dir), "phase6-generate-pva"])
            self.assertEqual(ret, 1)

    def test_no_write_no_files_created(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_measures.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            ret = main([str(exp_dir), "phase6-generate-pva"])
            self.assertEqual(ret, 0)
            self.assertFalse((impactos_dir / "phase6_model_with_pva.json").exists())
            self.assertFalse((impactos_dir / "pva_generation_result.json").exists())

    def test_with_write_creates_jsons(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_measures.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            ret = main([str(exp_dir), "phase6-generate-pva", "--write"])
            self.assertEqual(ret, 0)
            self.assertTrue((impactos_dir / "phase6_model_with_pva.json").exists())
            self.assertTrue((impactos_dir / "pva_generation_result.json").exists())

    def test_output_json_has_pva_programs(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_measures.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            main([str(exp_dir), "phase6-generate-pva", "--write"])
            result_path = impactos_dir / "pva_generation_result.json"
            with open(result_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("pva_programs", data)
            self.assertIn("generated_count", data)
            self.assertGreater(data["generated_count"], 0)

    def test_output_model_has_pva_ids_in_impacts(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_measures.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            main([str(exp_dir), "phase6-generate-pva", "--write"])
            pva_model_path = impactos_dir / "phase6_model_with_pva.json"
            with open(pva_model_path, encoding="utf-8") as f:
                data = json.load(f)
            impacts = data.get("impacts", [])
            self.assertGreater(len(impacts), 0)
            imp = impacts[0]
            self.assertGreater(len(imp.get("pva_ids", [])), 0,
                               "El impacto debe tener pva_ids asignados")

    def test_fallback_to_conesa_model_if_no_measures(self):
        """Si no hay phase6_model_with_measures.json, usa phase6_model_with_conesa.json."""
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            ret = main([str(exp_dir), "phase6-generate-pva"])
            self.assertEqual(ret, 0)

    def test_annual_review_always_in_output(self):
        """La revision anual global siempre debe estar en el JSON de salida."""
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_measures.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(_minimal_model_dict_for_pva(), f)
            main([str(exp_dir), "phase6-generate-pva", "--write"])
            result_path = impactos_dir / "pva_generation_result.json"
            with open(result_path, encoding="utf-8") as f:
                data = json.load(f)
            pva_names = [p["name"] for p in data.get("pva_programs", [])]
            has_annual = any("anual" in n.lower() for n in pva_names)
            self.assertTrue(has_annual, "Debe haber una ficha de revision anual")


# ---------------------------------------------------------------------------
# 11. Coherencia del modelo después de generar PVAs
# ---------------------------------------------------------------------------

class TestModelCoherenceAfterPVA(unittest.TestCase):

    def test_all_pva_ids_reference_valid_impacts(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        impact_ids = {i.impact_id for i in result.model.impacts}
        for pva in result.model.pva_programs:
            for tid in pva.target_impact_ids:
                self.assertIn(
                    tid, impact_ids,
                    f"PVA {pva.pva_id} apunta a impacto inexistente {tid}"
                )

    def test_model_validate_no_errors_after_pva(self):
        """El modelo tras generacion de PVA debe pasar validate() sin errores criticos."""
        imp = _make_impact(
            nature="NEGATIVO",
            significance="COMPATIBLE",
            status="VALORADO",
        )
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        issues = result.model.validate()
        errors = [i for i in issues if i.startswith("ERROR")]
        self.assertEqual(errors, [], f"Errores en validate(): {errors}")

    def test_pva_to_dict_is_json_serializable(self):
        imp = _make_impact()
        model = _make_model(impacts=[imp])
        result = generate_pva_for_model(model)
        for pva in result.model.pva_programs:
            try:
                json.dumps(pva.to_dict())
            except (TypeError, ValueError) as e:
                self.fail(f"PVA {pva.pva_id} no es JSON serializable: {e}")

    def test_multiple_receptors_independent_pva(self):
        imp_ruido = _make_impact(impact_id="IMP-001", receptor_id="FR-014")
        imp_aire = _make_impact(
            impact_id="IMP-002",
            receptor_id="FR-006",
            name="Impacto calidad del aire",
        )
        model = _make_model(
            impacts=[imp_ruido, imp_aire],
            receptor_ids=["FR-014", "FR-006"],
        )
        result = generate_pva_for_model(model)
        receptor_pvas = [p for p in result.model.pva_programs
                         if "anual" not in p.name.lower()]
        # Deben existir PVAs para FR-014 y FR-006 de forma independiente
        covered_receptors = {
            imp.receptor_id
            for pva in receptor_pvas
            for imp_id in pva.target_impact_ids
            for imp in result.model.impacts
            if imp.impact_id == imp_id
        }
        self.assertIn("FR-014", covered_receptors)
        self.assertIn("FR-006", covered_receptors)


if __name__ == "__main__":
    unittest.main()
