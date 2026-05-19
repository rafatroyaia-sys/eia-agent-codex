"""
tests/test_mitigation_measure_generator.py
Tests para IM-05 — Generador de medidas ambientales por tipo de impacto.

Cubre:
  1. MeasureGenerationRule (to_dict, matches por receptor/keyword/significance/nature, no-match)
  2. default_measure_generation_rules (presencia, unicidad, validez)
  3. generate_measures_for_impact (por receptor, IDs, no mutación, deduplicación)
  4. generate_measures_for_model (impactos múltiples, measure_ids, no PVA, no mutación)
  5. merge_measures_into_model (sustitución, actualización, conservación, no mutación)
  6. Reglas metodológicas (PRL, diagnóstica, no compensación, no cierre compatibilidad)
  7. CLI phase6-generate-measures (exit 1 sin modelo, no escribe sin --write, JSONs correctos)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    ReceptorFactor,
)
from eia_agent.core.mitigation_measure_generator import (
    MeasureGenerationResult,
    MeasureGenerationRule,
    default_measure_generation_rules,
    generate_measures_for_impact,
    generate_measures_for_model,
    merge_measures_into_model,
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
    name: str = "Impacto por ruido de operaciones",
    description: str = "Emision de ruido por maquinaria de tratamiento mecanico",
    action_id: str = "AC-001",
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id=action_id,
        receptor_id=receptor_id,
        name=name,
        description=description,
        nature=nature,
        status=status,
        significance_without_measures=significance,
    )


def _make_action(action_id: str = "AC-001", action_type: str = "OPERACION") -> ProjectAction:
    return ProjectAction(
        action_id=action_id,
        name="Operacion mecanica",
        action_type=action_type,
    )


def _make_receptor(receptor_id: str = "FR-014") -> ReceptorFactor:
    fi_id = receptor_id.replace("FR-", "FI-")
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=f"Factor {receptor_id}",
        ready_from_inventory=False,
        notes=["Sin inventario de campo."],
    )


def _make_model_with_impacts(impacts, actions=None, receptor_ids=None):
    if actions is None:
        actions = [_make_action()]
    if receptor_ids is None:
        receptor_ids = list({imp.receptor_id for imp in impacts})
    receptors = [_make_receptor(rid) for rid in receptor_ids]
    return Phase6Model(
        expediente_id="TEST-IM05",
        actions=actions,
        receptor_factors=receptors,
        impacts=impacts,
    )


# ---------------------------------------------------------------------------
# 1. TestMeasureGenerationRule
# ---------------------------------------------------------------------------

class TestMeasureGenerationRule(unittest.TestCase):

    def _make_rule(self, **kwargs):
        defaults = dict(
            rule_id="TEST-RULE",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Medida de prueba",
            measure_description="Descripcion de prueba",
            measure_type="PREVENTIVA",
        )
        defaults.update(kwargs)
        return MeasureGenerationRule(**defaults)

    def test_to_dict_has_all_keys(self):
        rule = self._make_rule()
        d = rule.to_dict()
        for key in [
            "rule_id", "target_receptor_ids", "impact_keywords",
            "significance_levels", "measure_name", "measure_description",
            "measure_type", "status", "is_diagnostic", "is_prl_only",
            "condition_before_submission", "target_natures", "notes",
        ]:
            self.assertIn(key, d)

    def test_to_dict_json_serializable(self):
        rule = self._make_rule(notes=["nota 1"])
        d = rule.to_dict()
        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)

    def test_matches_by_receptor(self):
        rule = self._make_rule(target_receptor_ids=["FR-014"])
        impact = _make_impact(receptor_id="FR-014")
        self.assertTrue(rule.matches(impact))

    def test_no_matches_wrong_receptor(self):
        rule = self._make_rule(target_receptor_ids=["FR-014"])
        impact = _make_impact(receptor_id="FR-006")
        self.assertFalse(rule.matches(impact))

    def test_matches_any_keyword_in_name(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-014"],
            impact_keywords=["ruido", "acustico"],
        )
        impact = _make_impact(receptor_id="FR-014", name="Impacto por ruido de maquinaria")
        self.assertTrue(rule.matches(impact))

    def test_no_match_keyword_not_in_name_or_description(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-014"],
            impact_keywords=["paisaje"],
        )
        impact = _make_impact(receptor_id="FR-014", name="Impacto por ruido", description="")
        self.assertFalse(rule.matches(impact))

    def test_matches_keyword_in_description(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-014"],
            impact_keywords=["vibracion"],
        )
        impact = _make_impact(
            receptor_id="FR-014",
            name="Impacto acustico",
            description="Presencia de vibracion en operaciones",
        )
        self.assertTrue(rule.matches(impact))

    def test_matches_by_significance(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-014"],
            significance_levels=["MODERADO", "SEVERO"],
        )
        impact_mod = _make_impact(receptor_id="FR-014", significance="MODERADO")
        impact_sev = _make_impact(receptor_id="FR-014", significance="SEVERO")
        impact_comp = _make_impact(receptor_id="FR-014", significance="COMPATIBLE")
        self.assertTrue(rule.matches(impact_mod))
        self.assertTrue(rule.matches(impact_sev))
        self.assertFalse(rule.matches(impact_comp))

    def test_no_match_wrong_significance(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-014"],
            significance_levels=["SEVERO", "CRITICO"],
        )
        impact = _make_impact(receptor_id="FR-014", significance="COMPATIBLE")
        self.assertFalse(rule.matches(impact))

    def test_no_match_descartado(self):
        rule = self._make_rule()
        impact = _make_impact(receptor_id="FR-014", status="DESCARTADO_JUSTIFICADO")
        self.assertFalse(rule.matches(impact))

    def test_matches_by_nature_filter(self):
        rule = self._make_rule(
            target_receptor_ids=["FR-013"],
            target_natures=["POSITIVO"],
        )
        pos_impact = _make_impact(receptor_id="FR-013", nature="POSITIVO")
        neg_impact = _make_impact(receptor_id="FR-013", nature="NEGATIVO")
        self.assertTrue(rule.matches(pos_impact))
        self.assertFalse(rule.matches(neg_impact))

    def test_no_nature_filter_matches_any(self):
        rule = self._make_rule(target_receptor_ids=["FR-014"], target_natures=[])
        for nature in ["NEGATIVO", "POSITIVO", "MIXTO", "INDETERMINADO"]:
            impact = _make_impact(receptor_id="FR-014", nature=nature)
            self.assertTrue(rule.matches(impact), f"Should match nature={nature}")

    def test_empty_keyword_and_significance_matches_any_impact(self):
        rule = self._make_rule(target_receptor_ids=["FR-014"])
        for sig in ["COMPATIBLE", "MODERADO", "SEVERO", "CRITICO", "INDETERMINADO", "NO_VALORADO"]:
            impact = _make_impact(receptor_id="FR-014", significance=sig)
            self.assertTrue(rule.matches(impact))

    def test_defaults(self):
        rule = MeasureGenerationRule(
            rule_id="R",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="X",
            measure_description="Y",
            measure_type="PREVENTIVA",
        )
        self.assertEqual(rule.status, "PROPUESTA")
        self.assertFalse(rule.is_diagnostic)
        self.assertFalse(rule.is_prl_only)
        self.assertFalse(rule.condition_before_submission)
        self.assertEqual(rule.target_natures, [])
        self.assertEqual(rule.notes, [])


# ---------------------------------------------------------------------------
# 2. TestDefaultMeasureGenerationRules
# ---------------------------------------------------------------------------

class TestDefaultMeasureGenerationRules(unittest.TestCase):

    def setUp(self):
        self.rules = default_measure_generation_rules()

    def test_returns_nonempty(self):
        self.assertGreater(len(self.rules), 0)

    def test_has_16_rules(self):
        self.assertEqual(len(self.rules), 16)

    def test_has_rule_for_acoustic_study(self):
        mgen_a = next((r for r in self.rules if r.rule_id == "MGEN-A"), None)
        self.assertIsNotNone(mgen_a)
        self.assertIn("FR-014", mgen_a.target_receptor_ids)
        self.assertEqual(mgen_a.measure_type, "DIAGNOSTICA")
        self.assertTrue(mgen_a.is_diagnostic)
        self.assertEqual(mgen_a.status, "CONDICION_PREVIA")

    def test_has_prl_no_eia_rule(self):
        prl_rules = [r for r in self.rules if r.is_prl_only]
        self.assertGreater(len(prl_rules), 0)
        for r in prl_rules:
            self.assertEqual(r.measure_type, "PRL_NO_EIA")
            self.assertEqual(r.status, "NO_EIA")

    def test_has_red_natura_documental_rule(self):
        rn_rules = [
            r for r in self.rules
            if any(rid in ["FR-009", "FR-010"] for rid in r.target_receptor_ids)
        ]
        self.assertGreater(len(rn_rules), 0)
        for r in rn_rules:
            self.assertEqual(r.measure_type, "DOCUMENTAL")

    def test_has_enp_rule(self):
        enp_rule = next(
            (r for r in self.rules if "FR-009" in r.target_receptor_ids), None
        )
        self.assertIsNotNone(enp_rule)

    def test_has_patrimonio_rule(self):
        pat_rule = next(
            (r for r in self.rules if "FR-012" in r.target_receptor_ids), None
        )
        self.assertIsNotNone(pat_rule)
        self.assertEqual(pat_rule.measure_type, "DOCUMENTAL")

    def test_unique_rule_ids(self):
        ids = [r.rule_id for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)), "IDs de reglas no son únicos")

    def test_all_measure_types_valid(self):
        from eia_agent.core.impact_model import MEASURE_TYPES
        for rule in self.rules:
            self.assertIn(
                rule.measure_type, MEASURE_TYPES,
                f"{rule.rule_id}: measure_type inválido: {rule.measure_type}"
            )

    def test_all_statuses_valid(self):
        from eia_agent.core.impact_model import MEASURE_STATUS
        for rule in self.rules:
            self.assertIn(
                rule.status, MEASURE_STATUS,
                f"{rule.rule_id}: status inválido: {rule.status}"
            )

    def test_mgen_a_through_p_ids_present(self):
        expected_ids = {f"MGEN-{c}" for c in "ABCDEFGHIJKLMNOP"}
        actual_ids = {r.rule_id for r in self.rules}
        for eid in expected_ids:
            self.assertIn(eid, actual_ids, f"Regla {eid} no encontrada")

    def test_has_socioeconomia_positive_rule(self):
        mgen_p = next((r for r in self.rules if r.rule_id == "MGEN-P"), None)
        self.assertIsNotNone(mgen_p)
        self.assertIn("FR-013", mgen_p.target_receptor_ids)
        self.assertIn("POSITIVO", mgen_p.target_natures)
        self.assertEqual(mgen_p.measure_type, "DOCUMENTAL")

    def test_condition_before_submission_rules_have_status_condicion_previa(self):
        for rule in self.rules:
            if rule.condition_before_submission:
                self.assertEqual(
                    rule.status, "CONDICION_PREVIA",
                    f"{rule.rule_id}: condition_before_submission=True "
                    f"pero status={rule.status}"
                )

    def test_diagnostic_rules_have_correct_type(self):
        for rule in self.rules:
            if rule.is_diagnostic:
                self.assertEqual(
                    rule.measure_type, "DIAGNOSTICA",
                    f"{rule.rule_id}: is_diagnostic=True pero measure_type={rule.measure_type}"
                )

    def test_prl_rules_have_no_eia_status(self):
        for rule in self.rules:
            if rule.is_prl_only:
                self.assertEqual(rule.status, "NO_EIA")
                self.assertEqual(rule.measure_type, "PRL_NO_EIA")

    def test_flora_fauna_generate_diagnostica_not_correctora(self):
        bio_rules = [
            r for r in self.rules
            if any(rid in ["FR-007", "FR-008"] for rid in r.target_receptor_ids)
        ]
        for r in bio_rules:
            self.assertNotEqual(r.measure_type, "CORRECTORA",
                                f"{r.rule_id}: Flora/Fauna no debe generar CORRECTORA")
            self.assertIn(r.measure_type, ["DIAGNOSTICA", "DOCUMENTAL"])


# ---------------------------------------------------------------------------
# 3. TestGenerateMeasuresForImpact
# ---------------------------------------------------------------------------

class TestGenerateMeasuresForImpact(unittest.TestCase):

    def test_fr014_generates_acoustic_study(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        types = [m.measure_type for m in measures]
        self.assertIn("DIAGNOSTICA", types)
        # MGEN-A specifically
        mgen_a = next((m for m in measures if "MGEN-A" in " ".join(m.notes)), None)
        self.assertIsNotNone(mgen_a)
        self.assertTrue(mgen_a.is_diagnostic)

    def test_fr014_generates_material_correctora(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        types = [m.measure_type for m in measures]
        self.assertIn("CORRECTORA", types)

    def test_fr014_generates_preventiva(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        types = [m.measure_type for m in measures]
        self.assertIn("PREVENTIVA", types)

    def test_fr014_generates_epi_as_prl_no_eia(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        prl_measures = [m for m in measures if m.is_prl_only]
        self.assertGreater(len(prl_measures), 0)
        for m in prl_measures:
            self.assertEqual(m.measure_type, "PRL_NO_EIA")
            self.assertEqual(m.status, "NO_EIA")

    def test_fr006_generates_filtration_control(self):
        impact = _make_impact(
            receptor_id="FR-006",
            name="Impacto sobre calidad del aire por polvo",
        )
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        types = [m.measure_type for m in measures]
        self.assertIn("CORRECTORA", types)
        self.assertIn("PREVENTIVA", types)

    def test_fr003_generates_impermeabilizacion_and_protocol(self):
        impact = _make_impact(receptor_id="FR-003", name="Riesgo de contaminacion de suelo")
        measures = generate_measures_for_impact(impact)
        types = [m.measure_type for m in measures]
        self.assertIn("PROTECTORA", types)
        self.assertIn("PREVENTIVA", types)

    def test_fr004_generates_drainage(self):
        impact = _make_impact(receptor_id="FR-004", name="Impacto sobre hidrologia")
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        types = [m.measure_type for m in measures]
        self.assertIn("PROTECTORA", types)

    def test_fr009_generates_documental_measure(self):
        impact = _make_impact(
            receptor_id="FR-009",
            name="Posible afeccion a Espacio Natural Protegido",
            significance="INDETERMINADO",
        )
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        types = [m.measure_type for m in measures]
        self.assertIn("DOCUMENTAL", types)

    def test_fr010_generates_documental_measure(self):
        impact = _make_impact(
            receptor_id="FR-010",
            name="Posible afeccion a Red Natura 2000",
            significance="INDETERMINADO",
        )
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        types = [m.measure_type for m in measures]
        self.assertIn("DOCUMENTAL", types)

    def test_fr012_generates_patrimonio_consultation(self):
        impact = _make_impact(
            receptor_id="FR-012",
            name="Posible afeccion a patrimonio cultural",
            significance="INDETERMINADO",
        )
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        types = [m.measure_type for m in measures]
        self.assertIn("DOCUMENTAL", types)

    def test_fr013_positivo_generates_documental_not_compensatoria(self):
        impact = _make_impact(
            receptor_id="FR-013",
            nature="POSITIVO",
            name="Beneficio socieconomico: empleo",
            significance="POSITIVO_MODERADO",
        )
        measures = generate_measures_for_impact(impact)
        types = [m.measure_type for m in measures]
        # MGEN-P generates DOCUMENTAL for POSITIVO
        self.assertIn("DOCUMENTAL", types)
        # Must NOT generate COMPENSATORIA
        self.assertNotIn("COMPENSATORIA", types)

    def test_fr013_negativo_no_mgen_p(self):
        """MGEN-P solo aplica a POSITIVO; impacto NEGATIVO FR-013 no genera nota de no compensación vía MGEN-P."""
        impact = _make_impact(
            receptor_id="FR-013",
            nature="NEGATIVO",
            name="Impacto negativo socioeconomia",
            significance="COMPATIBLE",
        )
        measures = generate_measures_for_impact(impact)
        # MGEN-P should not match NEGATIVO
        pnotes = [n for m in measures for n in m.notes if "MGEN-P" in n]
        self.assertEqual(len(pnotes), 0, "MGEN-P no debe generar medida para impacto NEGATIVO")

    def test_ids_are_correlative_from_start_index(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact, start_index=5)
        expected_ids = [f"MED-{5+i:03d}" for i in range(len(measures))]
        actual_ids = [m.measure_id for m in measures]
        self.assertEqual(actual_ids, expected_ids)

    def test_default_start_index_is_1(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        self.assertTrue(measures[0].measure_id.startswith("MED-"))
        self.assertEqual(measures[0].measure_id, "MED-001")

    def test_target_impact_ids_linked_to_impact(self):
        impact = _make_impact(impact_id="IMP-042", receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        for m in measures:
            self.assertIn("IMP-042", m.target_impact_ids)

    def test_no_mutation_of_impact(self):
        impact = _make_impact(receptor_id="FR-014")
        original_measure_ids = list(impact.measure_ids)
        _ = generate_measures_for_impact(impact)
        self.assertEqual(impact.measure_ids, original_measure_ids)

    def test_descartado_gets_no_measures(self):
        impact = _make_impact(receptor_id="FR-014", status="DESCARTADO_JUSTIFICADO")
        measures = generate_measures_for_impact(impact)
        self.assertEqual(len(measures), 0)

    def test_deduplication_by_name_type(self):
        """Si dos reglas generan la misma (measure_name, measure_type), solo una medida."""
        impact = _make_impact(receptor_id="FR-014")
        duplicate_rule = MeasureGenerationRule(
            rule_id="DUP-RULE",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Estudio acustico previo a la presentacion",  # mismo que MGEN-A
            measure_description="Copia",
            measure_type="DIAGNOSTICA",  # mismo tipo
        )
        rules = default_measure_generation_rules() + [duplicate_rule]
        measures_no_dup = generate_measures_for_impact(impact, rules=rules)
        names_types = [(m.name, m.measure_type) for m in measures_no_dup]
        self.assertEqual(len(names_types), len(set(names_types)),
                         "Se generaron medidas duplicadas")

    def test_empty_model_no_rules_returns_empty(self):
        impact = _make_impact(receptor_id="FR-001")  # no hay regla para FR-001
        measures = generate_measures_for_impact(impact)
        self.assertEqual(len(measures), 0)


# ---------------------------------------------------------------------------
# 4. TestGenerateMeasuresForModel
# ---------------------------------------------------------------------------

class TestGenerateMeasuresForModel(unittest.TestCase):

    def _model_with_ruido_and_aire(self):
        impacts = [
            _make_impact("IMP-001", "FR-014", name="Ruido maquinaria"),
            _make_impact("IMP-002", "FR-006", name="Polvo operaciones"),
        ]
        return _make_model_with_impacts(
            impacts,
            receptor_ids=["FR-014", "FR-006"],
        )

    def test_generates_measures_for_multiple_impacts(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        self.assertIsInstance(result, MeasureGenerationResult)
        self.assertGreater(result.generated_count, 0)
        self.assertGreater(len(result.model.measures), 0)

    def test_updates_measure_ids_in_impacts(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        for impact in result.model.impacts:
            # Each impact should have measure_ids populated
            self.assertGreater(len(impact.measure_ids), 0,
                                f"{impact.impact_id} debería tener measure_ids")

    def test_measure_ids_reference_existing_measures(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        measure_ids_in_model = {m.measure_id for m in result.model.measures}
        for impact in result.model.impacts:
            for mid in impact.measure_ids:
                self.assertIn(mid, measure_ids_in_model,
                               f"measure_id {mid} en impacto no existe en modelo")

    def test_no_pva_created(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        self.assertEqual(len(result.model.pva_programs), 0)

    def test_conserves_actions(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        self.assertEqual(
            len(result.model.actions), len(model.actions)
        )
        self.assertEqual(
            result.model.actions[0].action_id,
            model.actions[0].action_id,
        )

    def test_conserves_receptor_factors(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        self.assertEqual(
            len(result.model.receptor_factors), len(model.receptor_factors)
        )

    def test_does_not_modify_significance(self):
        model = self._model_with_ruido_and_aire()
        original_sigs = {
            imp.impact_id: imp.significance_without_measures
            for imp in model.impacts
        }
        result = generate_measures_for_model(model)
        for imp in result.model.impacts:
            self.assertEqual(
                imp.significance_without_measures,
                original_sigs[imp.impact_id],
                f"{imp.impact_id}: significancia modificada inesperadamente"
            )

    def test_does_not_modify_significance_with_measures(self):
        model = self._model_with_ruido_and_aire()
        original_sigs = {
            imp.impact_id: imp.significance_with_measures
            for imp in model.impacts
        }
        result = generate_measures_for_model(model)
        for imp in result.model.impacts:
            self.assertEqual(
                imp.significance_with_measures,
                original_sigs[imp.impact_id],
            )

    def test_diagnostic_count(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        expected = sum(1 for m in result.model.measures if m.is_diagnostic)
        self.assertEqual(result.diagnostic_count, expected)

    def test_prl_only_count(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        expected = sum(1 for m in result.model.measures if m.is_prl_only)
        self.assertEqual(result.prl_only_count, expected)

    def test_condition_before_submission_count(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        expected = sum(1 for m in result.model.measures if m.condition_before_submission)
        self.assertEqual(result.condition_before_submission_count, expected)

    def test_no_mutation_of_original_model(self):
        model = self._model_with_ruido_and_aire()
        original_measures = list(model.measures)
        original_imp_measure_ids = [list(imp.measure_ids) for imp in model.impacts]
        _ = generate_measures_for_model(model)
        # Verify original not mutated
        self.assertEqual(model.measures, original_measures)
        for i, imp in enumerate(model.impacts):
            self.assertEqual(imp.measure_ids, original_imp_measure_ids[i])

    def test_empty_model_returns_graceful_result(self):
        model = Phase6Model(expediente_id="TEST-EMPTY")
        result = generate_measures_for_model(model)
        self.assertIsInstance(result, MeasureGenerationResult)
        self.assertEqual(result.generated_count, 0)
        self.assertGreater(len(result.warnings), 0)

    def test_global_index_is_correlative(self):
        impacts = [
            _make_impact("IMP-001", "FR-014"),
            _make_impact("IMP-002", "FR-006"),
            _make_impact("IMP-003", "FR-003"),
        ]
        model = _make_model_with_impacts(
            impacts, receptor_ids=["FR-014", "FR-006", "FR-003"]
        )
        result = generate_measures_for_model(model)
        ids = [m.measure_id for m in result.model.measures]
        nums = [int(mid.replace("MED-", "")) for mid in ids]
        for i in range(len(nums) - 1):
            self.assertEqual(nums[i + 1], nums[i] + 1,
                             "IDs de medidas no son consecutivos globalmente")

    def test_to_dict_json_serializable(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        self.assertIsInstance(json_str, str)

    def test_summary_is_string(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        summary = result.summary()
        self.assertIsInstance(summary, str)
        self.assertIn("IM-05", summary)

    def test_summary_ascii_safe(self):
        model = self._model_with_ruido_and_aire()
        result = generate_measures_for_model(model)
        summary = result.summary()
        summary.encode("ascii", errors="strict")  # Should not raise


# ---------------------------------------------------------------------------
# 5. TestMergeMeasuresIntoModel
# ---------------------------------------------------------------------------

class TestMergeMeasuresIntoModel(unittest.TestCase):

    def _base_model(self):
        impact = _make_impact("IMP-001", "FR-014")
        return _make_model_with_impacts([impact])

    def _make_measure(self, measure_id="MED-001", target_impact_ids=None):
        return MitigationMeasure(
            measure_id=measure_id,
            name="Medida de prueba",
            description="Descripcion",
            measure_type="PREVENTIVA",
            status="PROPUESTA",
            target_impact_ids=target_impact_ids or ["IMP-001"],
        )

    def test_replaces_measures_in_model(self):
        model = self._base_model()
        new_measures = [self._make_measure("MED-001"), self._make_measure("MED-002")]
        new_model = merge_measures_into_model(model, new_measures)
        self.assertEqual(len(new_model.measures), 2)
        ids = {m.measure_id for m in new_model.measures}
        self.assertIn("MED-001", ids)
        self.assertIn("MED-002", ids)

    def test_updates_impact_measure_ids(self):
        model = self._base_model()
        measures = [
            self._make_measure("MED-001", target_impact_ids=["IMP-001"]),
            self._make_measure("MED-002", target_impact_ids=["IMP-001"]),
        ]
        new_model = merge_measures_into_model(model, measures)
        imp = new_model.impacts[0]
        self.assertIn("MED-001", imp.measure_ids)
        self.assertIn("MED-002", imp.measure_ids)

    def test_impact_with_no_measures_gets_empty_ids(self):
        impact1 = _make_impact("IMP-001", "FR-014")
        impact2 = _make_impact("IMP-002", "FR-006")
        model = _make_model_with_impacts([impact1, impact2], receptor_ids=["FR-014", "FR-006"])
        measures = [self._make_measure("MED-001", target_impact_ids=["IMP-001"])]
        new_model = merge_measures_into_model(model, measures)
        imp2 = next(i for i in new_model.impacts if i.impact_id == "IMP-002")
        self.assertEqual(imp2.measure_ids, [])

    def test_conserves_pva_programs(self):
        model = self._base_model()
        # pva_programs is empty by default; verify it stays empty after merge
        new_model = merge_measures_into_model(model, [])
        self.assertEqual(new_model.pva_programs, [])

    def test_conserves_actions(self):
        model = self._base_model()
        new_model = merge_measures_into_model(model, [])
        self.assertEqual(len(new_model.actions), len(model.actions))

    def test_conserves_receptor_factors(self):
        model = self._base_model()
        new_model = merge_measures_into_model(model, [])
        self.assertEqual(len(new_model.receptor_factors), len(model.receptor_factors))

    def test_no_mutation_of_original_model(self):
        model = self._base_model()
        original_measures = list(model.measures)
        original_measure_ids = list(model.impacts[0].measure_ids)
        _ = merge_measures_into_model(model, [self._make_measure()])
        # Original untouched
        self.assertEqual(model.measures, original_measures)
        self.assertEqual(model.impacts[0].measure_ids, original_measure_ids)

    def test_empty_measures_clears_impact_measure_ids(self):
        """Si se merge una lista vacía, los measure_ids de los impactos quedan en []."""
        impact = dataclasses.replace(
            _make_impact("IMP-001", "FR-014"),
            measure_ids=["MED-999"],
        )
        model = _make_model_with_impacts([impact])
        new_model = merge_measures_into_model(model, [])
        self.assertEqual(new_model.impacts[0].measure_ids, [])


# ---------------------------------------------------------------------------
# Importar dataclasses para el test anterior
# ---------------------------------------------------------------------------

import dataclasses


# ---------------------------------------------------------------------------
# 6. TestMethodologicalRules
# ---------------------------------------------------------------------------

class TestMethodologicalRules(unittest.TestCase):

    def test_prl_not_classified_as_correctora_ambiental(self):
        """Medidas PRL_NO_EIA no deben confundirse con medidas CORRECTORA ambientales."""
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        for m in measures:
            if m.is_prl_only:
                self.assertNotEqual(m.measure_type, "CORRECTORA",
                                    f"{m.measure_id}: PRL no puede ser CORRECTORA")

    def test_diagnostic_measures_have_is_diagnostic_true(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        for m in measures:
            if m.measure_type == "DIAGNOSTICA":
                self.assertTrue(m.is_diagnostic,
                                f"{m.measure_id}: DIAGNOSTICA debe tener is_diagnostic=True")

    def test_diagnostic_measures_do_not_change_significance(self):
        """La generación de medidas diagnósticas no modifica ninguna significancia."""
        impact = _make_impact(receptor_id="FR-014", significance="MODERADO")
        original_sig = impact.significance_without_measures
        original_sig_with = impact.significance_with_measures
        _ = generate_measures_for_impact(impact)
        self.assertEqual(impact.significance_without_measures, original_sig)
        self.assertEqual(impact.significance_with_measures, original_sig_with)

    def test_positive_socioeconomic_does_not_generate_compensatoria(self):
        """Un impacto POSITIVO de FR-013 no genera medida COMPENSATORIA."""
        impact = _make_impact(
            receptor_id="FR-013", nature="POSITIVO",
            name="Beneficio empleo local", significance="POSITIVO_MODERADO"
        )
        measures = generate_measures_for_impact(impact)
        for m in measures:
            self.assertNotEqual(m.measure_type, "COMPENSATORIA",
                                f"{m.measure_id}: positivo no debe ser COMPENSATORIA")

    def test_no_measure_targets_both_positive_and_negative(self):
        """Ninguna medida debe apuntar a impactos POSITIVO y NEGATIVO a la vez."""
        impacts = [
            _make_impact("IMP-001", "FR-013", nature="NEGATIVO", significance="COMPATIBLE"),
            _make_impact("IMP-002", "FR-013", nature="POSITIVO", significance="POSITIVO_MODERADO"),
        ]
        model = _make_model_with_impacts(impacts, receptor_ids=["FR-013"])
        result = generate_measures_for_model(model)
        nature_map = {imp.impact_id: imp.nature for imp in result.model.impacts}
        for m in result.model.measures:
            targeted_natures = {
                nature_map[tid]
                for tid in m.target_impact_ids
                if tid in nature_map
            }
            self.assertFalse(
                "POSITIVO" in targeted_natures and "NEGATIVO" in targeted_natures,
                f"{m.measure_id}: medida no debe apuntar a POSITIVO y NEGATIVO a la vez"
            )

    def test_enp_flora_fauna_measures_are_documental_or_diagnostica(self):
        """ENP, Flora y Fauna solo generan medidas DOCUMENTAL o DIAGNOSTICA, no CORRECTORA."""
        for receptor_id in ["FR-007", "FR-008", "FR-009", "FR-010"]:
            impact = _make_impact(
                receptor_id=receptor_id,
                significance="INDETERMINADO",
                status="INDETERMINADO",
            )
            measures = generate_measures_for_impact(impact)
            for m in measures:
                self.assertIn(
                    m.measure_type, ["DOCUMENTAL", "DIAGNOSTICA"],
                    f"{receptor_id}: {m.measure_id} tipo {m.measure_type} no esperado"
                )

    def test_patrimonio_measure_does_not_close_compatibility(self):
        """La medida de patrimonio es DOCUMENTAL; no afirma impacto COMPATIBLE."""
        impact = _make_impact(
            receptor_id="FR-012",
            significance="INDETERMINADO",
        )
        measures = generate_measures_for_impact(impact)
        self.assertGreater(len(measures), 0)
        for m in measures:
            self.assertNotIn(
                "compatible", m.description.lower(),
                f"{m.measure_id}: la medida patrimonial no debe afirmar compatibilidad"
            )

    def test_prl_measure_has_no_eia_status(self):
        impact = _make_impact(receptor_id="FR-014")
        measures = generate_measures_for_impact(impact)
        prl = [m for m in measures if m.is_prl_only]
        for m in prl:
            self.assertEqual(m.status, "NO_EIA")

    def test_positive_negative_independence(self):
        """Verificar que measure_ids de impactos POSITIVO y NEGATIVO no se mezclan."""
        impacts = [
            _make_impact("IMP-001", "FR-014", nature="NEGATIVO", significance="MODERADO"),
            _make_impact("IMP-002", "FR-013", nature="POSITIVO", significance="POSITIVO_MODERADO"),
        ]
        model = _make_model_with_impacts(impacts, receptor_ids=["FR-014", "FR-013"])
        result = generate_measures_for_model(model)
        imp_neg = next(i for i in result.model.impacts if i.impact_id == "IMP-001")
        imp_pos = next(i for i in result.model.impacts if i.impact_id == "IMP-002")
        # Verify that measures from neg impact don't reference pos impact
        neg_measures = {m.measure_id for m in result.model.measures
                        if "IMP-001" in m.target_impact_ids}
        pos_measures = {m.measure_id for m in result.model.measures
                        if "IMP-002" in m.target_impact_ids}
        self.assertEqual(neg_measures.intersection(pos_measures), set())

    def test_mgen_b_is_not_prl(self):
        """MGEN-B (insonorización) es CORRECTORA ambiental, no PRL."""
        rules = default_measure_generation_rules()
        mgen_b = next((r for r in rules if r.rule_id == "MGEN-B"), None)
        self.assertIsNotNone(mgen_b)
        self.assertFalse(mgen_b.is_prl_only)
        self.assertEqual(mgen_b.measure_type, "CORRECTORA")

    def test_mgen_a_not_reducing_significance(self):
        """MGEN-A (estudio acústico) es DIAGNOSTICA: no marca como reductora."""
        rules = default_measure_generation_rules()
        mgen_a = next((r for r in rules if r.rule_id == "MGEN-A"), None)
        self.assertTrue(mgen_a.is_diagnostic)
        # is_diagnostic measures per IM-00 are in _NON_REDUCING_MEASURE_TYPES
        from eia_agent.core.impact_model import _NON_REDUCING_MEASURE_TYPES
        self.assertIn("DIAGNOSTICA", _NON_REDUCING_MEASURE_TYPES)


# ---------------------------------------------------------------------------
# 7. TestCLIPhase6GenerateMeasures
# ---------------------------------------------------------------------------

class TestCLIPhase6GenerateMeasures(unittest.TestCase):

    def _minimal_model_dict(self, n_impacts=1):
        """JSON mínimo compatible con el parser de la CLI."""
        impacts = []
        for i in range(n_impacts):
            impacts.append({
                "impact_id": f"IMP-{i+1:03d}",
                "action_id": "AC-001",
                "receptor_id": "FR-014",
                "name": "Ruido de maquinaria",
                "description": "Emision de ruido",
                "nature": "NEGATIVO",
                "status": "VALORADO",
                "significance_without_measures": "MODERADO",
                "significance_with_measures": "NO_VALORADO",
                "conesa_attributes": {
                    "intensidad": 2, "extension": 2, "momento": 4,
                    "persistencia": 2, "reversibilidad": 2, "sinergia": 1,
                    "acumulacion": 4, "efecto": 4, "periodicidad": 4,
                    "recuperabilidad": 2,
                },
                "data_gaps": [], "source_refs": [], "measure_ids": [],
                "pva_ids": [], "warnings": [], "notes": [],
            })
        return {
            "expediente_id": "TEST-CLI-IM05",
            "actions": [{"action_id": "AC-001", "name": "Op", "description": "",
                          "action_type": "OPERACION", "operation_code": None,
                          "source_refs": [], "notes": []}],
            "receptor_factors": [{"receptor_id": "FR-014", "inventory_factor_id": "FI-014",
                                   "name": "Ruido", "inventory_semaphore": "NO_CONSTA",
                                   "ready_from_inventory": False, "critical_gaps": [],
                                   "notes": ["Sin campo."]}],
            "impacts": impacts,
            "measures": [],
            "pva_programs": [],
            "warnings": [],
            "notes": [],
        }

    def test_no_model_exits_1(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            ret = main([str(exp_dir), "phase6-generate-measures"])
            self.assertEqual(ret, 1)

    def test_no_write_no_files_created(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            ret = main([str(exp_dir), "phase6-generate-measures"])
            self.assertEqual(ret, 0)
            self.assertFalse((impactos_dir / "phase6_model_with_measures.json").exists())
            self.assertFalse((impactos_dir / "measure_generation_result.json").exists())

    def test_with_write_creates_jsons(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            ret = main([str(exp_dir), "phase6-generate-measures", "--write"])
            self.assertEqual(ret, 0)
            self.assertTrue((impactos_dir / "phase6_model_with_measures.json").exists())
            self.assertTrue((impactos_dir / "measure_generation_result.json").exists())

    def test_output_json_contains_measures(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            main([str(exp_dir), "phase6-generate-measures", "--write"])
            result_path = impactos_dir / "measure_generation_result.json"
            with open(result_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("generated_count", data)
            self.assertIn("measures", data)
            self.assertGreater(data["generated_count"], 0)

    def test_output_model_json_valid(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            main([str(exp_dir), "phase6-generate-measures", "--write"])
            model_out = impactos_dir / "phase6_model_with_measures.json"
            with open(model_out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("measures", data)
            self.assertIn("impacts", data)
            self.assertGreater(len(data["measures"]), 0)

    def test_no_pva_in_output(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            main([str(exp_dir), "phase6-generate-measures", "--write"])
            model_out = impactos_dir / "phase6_model_with_measures.json"
            with open(model_out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data.get("pva_programs", [])), 0)

    def test_fallback_to_impacts_model_if_no_conesa(self):
        """Si no hay phase6_model_with_conesa.json, usa phase6_model_with_impacts.json."""
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            # Only write impacts model (no conesa model)
            model_path = impactos_dir / "phase6_model_with_impacts.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(self._minimal_model_dict(), f)
            ret = main([str(exp_dir), "phase6-generate-measures"])
            self.assertEqual(ret, 0)

    def test_multiple_impacts_generates_valid_json(self):
        from run_expediente import main
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            impactos_dir = exp_dir / "impactos"
            impactos_dir.mkdir()
            # 3 impacts
            model_data = self._minimal_model_dict(n_impacts=3)
            # Vary receptors
            model_data["impacts"][0]["receptor_id"] = "FR-014"
            model_data["impacts"][1]["receptor_id"] = "FR-006"
            model_data["impacts"][1]["action_id"] = "AC-001"
            model_data["impacts"][2]["receptor_id"] = "FR-003"
            model_data["impacts"][2]["action_id"] = "AC-001"
            model_data["receptor_factors"] = [
                {"receptor_id": "FR-014", "inventory_factor_id": "FI-014",
                 "name": "Ruido", "inventory_semaphore": "NO_CONSTA",
                 "ready_from_inventory": False, "critical_gaps": [], "notes": ["Sin campo."]},
                {"receptor_id": "FR-006", "inventory_factor_id": "FI-006",
                 "name": "Calidad del aire", "inventory_semaphore": "NO_CONSTA",
                 "ready_from_inventory": False, "critical_gaps": [], "notes": ["Sin campo."]},
                {"receptor_id": "FR-003", "inventory_factor_id": "FI-003",
                 "name": "Suelos", "inventory_semaphore": "NO_CONSTA",
                 "ready_from_inventory": False, "critical_gaps": [], "notes": ["Sin campo."]},
            ]
            model_path = impactos_dir / "phase6_model_with_conesa.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(model_data, f)
            ret = main([str(exp_dir), "phase6-generate-measures", "--write"])
            self.assertEqual(ret, 0)
            result_path = impactos_dir / "measure_generation_result.json"
            with open(result_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertGreater(data["generated_count"], 0)
            self.assertTrue(json.dumps(data))  # fully serializable


if __name__ == "__main__":
    unittest.main()
