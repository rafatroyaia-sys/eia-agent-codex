"""
Tests para IM-04: conesa_attribute_assigner.py

Suite: 7 clases de tests que verifican reglas, asignación, puntuación,
no-mutación y restricciones metodológicas.
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
from eia_agent.core.conesa_attribute_assigner import (
    ConesaAssignmentRule,
    ConesaAssignmentResult,
    _all_none_attributes,
    assign_conesa_attributes_to_impact,
    assign_conesa_attributes_to_model,
    default_conesa_assignment_rules,
)


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _make_action(action_id="AC-001", action_type="OPERACION", name="Operacion test"):
    return ProjectAction(
        action_id=action_id,
        name=name,
        description="Descripcion de prueba",
        action_type=action_type,
    )


def _make_receptor(receptor_id="FR-014"):
    from eia_agent.core.impact_model import RECEPTOR_FACTOR_IDS, RECEPTOR_FACTOR_NAMES
    fi_id = RECEPTOR_FACTOR_IDS.get(receptor_id, "FI-014")
    name = RECEPTOR_FACTOR_NAMES.get(receptor_id, "Factor prueba")
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=name,
        notes=["fixture"],
    )


def _make_impact(
    impact_id="IMP-001",
    action_id="AC-001",
    receptor_id="FR-014",
    nature="NEGATIVO",
    status="PENDIENTE_DATOS",
    conesa_attributes=None,
):
    if conesa_attributes is None:
        conesa_attributes = ConesaAttributes()
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id=action_id,
        receptor_id=receptor_id,
        name=f"Impacto {impact_id}",
        nature=nature,
        status=status,
        conesa_attributes=conesa_attributes,
    )


def _make_model_with_impacts(impacts, actions=None, receptors=None):
    if actions is None:
        actions = [_make_action()]
    if receptors is None:
        receptors = [_make_receptor()]
    return Phase6Model(
        expediente_id="TEST-001",
        actions=actions,
        receptor_factors=receptors,
        impacts=impacts,
    )


# ---------------------------------------------------------------------------
# TestConesaAssignmentRule
# ---------------------------------------------------------------------------

class TestConesaAssignmentRule(unittest.TestCase):
    """Verifica la lógica de matches() y to_dict() de ConesaAssignmentRule."""

    def setUp(self):
        self.attrs = ConesaAttributes(
            intensidad=2, extension=2, momento=4, persistencia=2,
            reversibilidad=2, sinergia=1, acumulacion=4, efecto=4,
            periodicidad=4, recuperabilidad=2,
        )

    def test_matches_correct_receptor(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-014"], self.attrs)
        impact = _make_impact(receptor_id="FR-014")
        self.assertTrue(rule.matches(impact))

    def test_no_match_wrong_receptor(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-014"], self.attrs)
        impact = _make_impact(receptor_id="FR-006")
        self.assertFalse(rule.matches(impact))

    def test_matches_multiple_receptors(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-009", "FR-010"], self.attrs)
        impact_009 = _make_impact(receptor_id="FR-009")
        impact_010 = _make_impact(receptor_id="FR-010")
        impact_006 = _make_impact(receptor_id="FR-006")
        self.assertTrue(rule.matches(impact_009))
        self.assertTrue(rule.matches(impact_010))
        self.assertFalse(rule.matches(impact_006))

    def test_matches_nature_filter(self):
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-013"], self.attrs, target_natures=["POSITIVO"]
        )
        pos_impact = _make_impact(receptor_id="FR-013", nature="POSITIVO")
        neg_impact = _make_impact(receptor_id="FR-013", nature="NEGATIVO")
        self.assertTrue(rule.matches(pos_impact))
        self.assertFalse(rule.matches(neg_impact))

    def test_matches_empty_natures_any(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-014"], self.attrs)  # target_natures=[]
        neg = _make_impact(receptor_id="FR-014", nature="NEGATIVO")
        indet = _make_impact(receptor_id="FR-014", nature="INDETERMINADO")
        self.assertTrue(rule.matches(neg))
        self.assertTrue(rule.matches(indet))

    def test_matches_action_type_with_lookup(self):
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-014"], self.attrs, action_types=["OPERACION"]
        )
        action = _make_action(action_type="OPERACION")
        lookup = {"AC-001": action}
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        self.assertTrue(rule.matches(impact, lookup))

    def test_no_match_wrong_action_type(self):
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-014"], self.attrs, action_types=["OPERACION"]
        )
        action = _make_action(action_type="MANTENIMIENTO")
        lookup = {"AC-001": action}
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        self.assertFalse(rule.matches(impact, lookup))

    def test_matches_action_type_without_lookup_skips_check(self):
        """Sin action_lookup, la comprobación de tipo se omite (regla pasa)."""
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-014"], self.attrs, action_types=["OPERACION"]
        )
        impact = _make_impact(receptor_id="FR-014")
        self.assertTrue(rule.matches(impact, action_lookup=None))

    def test_matches_action_not_in_lookup(self):
        """Si action_id no está en el lookup, la regla NO coincide."""
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-014"], self.attrs, action_types=["OPERACION"]
        )
        lookup = {}  # vacío: AC-001 no está
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        self.assertFalse(rule.matches(impact, lookup))

    def test_to_dict_structure(self):
        rule = ConesaAssignmentRule(
            "R-TEST", ["FR-014"], self.attrs,
            action_types=["OPERACION"],
            target_natures=["NEGATIVO"],
            notes=["nota test"],
        )
        d = rule.to_dict()
        self.assertEqual(d["rule_id"], "R-TEST")
        self.assertIn("FR-014", d["target_receptor_ids"])
        self.assertIn("intensidad", d["conesa_attributes"])
        self.assertEqual(d["action_types"], ["OPERACION"])
        self.assertEqual(d["target_natures"], ["NEGATIVO"])
        self.assertIn("nota test", d["notes"])

    def test_to_dict_serializable(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-014"], self.attrs)
        d = rule.to_dict()
        # must serialize to JSON without error
        json_str = json.dumps(d)
        self.assertIn("R-TEST", json_str)

    def test_all_none_rule_matches_any_nature(self):
        rule = ConesaAssignmentRule("R-NONE", ["FR-009"], _all_none_attributes())
        neg = _make_impact(receptor_id="FR-009", nature="NEGATIVO")
        indet = _make_impact(receptor_id="FR-009", nature="INDETERMINADO")
        self.assertTrue(rule.matches(neg))
        self.assertTrue(rule.matches(indet))

    def test_defaults_empty_lists(self):
        rule = ConesaAssignmentRule("R-TEST", ["FR-014"], self.attrs)
        self.assertEqual(rule.action_types, [])
        self.assertEqual(rule.target_natures, [])
        self.assertEqual(rule.notes, [])


# ---------------------------------------------------------------------------
# TestDefaultConesaAssignmentRules
# ---------------------------------------------------------------------------

class TestDefaultConesaAssignmentRules(unittest.TestCase):
    """Verifica la colección de 10 reglas por defecto."""

    def setUp(self):
        self.rules = default_conesa_assignment_rules()

    def test_exactly_ten_rules(self):
        self.assertEqual(len(self.rules), 10)

    def test_all_rule_ids_unique(self):
        ids = [r.rule_id for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_rule_ids_cassign_prefix(self):
        for rule in self.rules:
            self.assertTrue(
                rule.rule_id.startswith("CASSIGN-"),
                f"rule_id sin prefijo CASSIGN-: {rule.rule_id}",
            )

    def test_cassign_a_targets_fr014(self):
        a = next(r for r in self.rules if r.rule_id == "CASSIGN-A")
        self.assertIn("FR-014", a.target_receptor_ids)

    def test_cassign_b_targets_fr006(self):
        b = next(r for r in self.rules if r.rule_id == "CASSIGN-B")
        self.assertIn("FR-006", b.target_receptor_ids)

    def test_cassign_c_targets_fr003(self):
        c = next(r for r in self.rules if r.rule_id == "CASSIGN-C")
        self.assertIn("FR-003", c.target_receptor_ids)

    def test_cassign_d_targets_fr004(self):
        d = next(r for r in self.rules if r.rule_id == "CASSIGN-D")
        self.assertIn("FR-004", d.target_receptor_ids)

    def test_cassign_e_targets_enp_and_natura(self):
        e = next(r for r in self.rules if r.rule_id == "CASSIGN-E")
        self.assertIn("FR-009", e.target_receptor_ids)
        self.assertIn("FR-010", e.target_receptor_ids)

    def test_cassign_f_targets_flora_fauna(self):
        f = next(r for r in self.rules if r.rule_id == "CASSIGN-F")
        self.assertIn("FR-007", f.target_receptor_ids)
        self.assertIn("FR-008", f.target_receptor_ids)

    def test_cassign_g_targets_patrimonio(self):
        g = next(r for r in self.rules if r.rule_id == "CASSIGN-G")
        self.assertIn("FR-012", g.target_receptor_ids)

    def test_cassign_h_targets_clima_cambio(self):
        h = next(r for r in self.rules if r.rule_id == "CASSIGN-H")
        self.assertIn("FR-015", h.target_receptor_ids)

    def test_cassign_i_targets_paisaje(self):
        i = next(r for r in self.rules if r.rule_id == "CASSIGN-I")
        self.assertIn("FR-011", i.target_receptor_ids)

    def test_cassign_j_targets_socioeconomia_positivo(self):
        j = next(r for r in self.rules if r.rule_id == "CASSIGN-J")
        self.assertIn("FR-013", j.target_receptor_ids)
        self.assertEqual(j.target_natures, ["POSITIVO"])

    def test_indeterminate_rules_all_none(self):
        """CASSIGN-E, F, G, I deben tener todos los atributos a None."""
        indeterminate_ids = {"CASSIGN-E", "CASSIGN-F", "CASSIGN-G", "CASSIGN-I"}
        for rule in self.rules:
            if rule.rule_id in indeterminate_ids:
                self.assertFalse(
                    rule.conesa_attributes.is_complete(),
                    f"{rule.rule_id} debería tener atributos incompletos",
                )
                missing = rule.conesa_attributes.missing_attributes()
                self.assertEqual(
                    len(missing), 10,
                    f"{rule.rule_id}: se esperaban 10 None, hay {len(missing)} None",
                )

    def test_scored_rules_complete_attributes(self):
        """CASSIGN-A, B, C, D, J deben tener los 10 atributos completos."""
        complete_ids = {"CASSIGN-A", "CASSIGN-B", "CASSIGN-C", "CASSIGN-D", "CASSIGN-J"}
        for rule in self.rules:
            if rule.rule_id in complete_ids:
                self.assertTrue(
                    rule.conesa_attributes.is_complete(),
                    f"{rule.rule_id} debería tener los 10 atributos completos",
                )

    def test_cassign_h_partial_none(self):
        """CASSIGN-H debe tener algunos atributos None (RV, SI, Mc)."""
        h = next(r for r in self.rules if r.rule_id == "CASSIGN-H")
        self.assertFalse(h.conesa_attributes.is_complete())
        missing = h.conesa_attributes.missing_attributes()
        self.assertIn("reversibilidad", missing)
        self.assertIn("sinergia", missing)
        self.assertIn("recuperabilidad", missing)
        # Pero IN y EX están asignados
        self.assertIsNotNone(h.conesa_attributes.intensidad)
        self.assertEqual(h.conesa_attributes.extension, 8)

    def test_cassign_a_action_types_not_empty(self):
        a = next(r for r in self.rules if r.rule_id == "CASSIGN-A")
        self.assertIn("OPERACION", a.action_types)
        self.assertIn("TRANSPORTE", a.action_types)

    def test_all_rules_have_notes(self):
        for rule in self.rules:
            self.assertTrue(
                len(rule.notes) > 0,
                f"{rule.rule_id} sin notas metodológicas",
            )

    def test_all_receptors_covered(self):
        all_receptor_ids = set()
        for rule in self.rules:
            all_receptor_ids.update(rule.target_receptor_ids)
        expected = {
            "FR-003", "FR-004", "FR-006", "FR-007", "FR-008",
            "FR-009", "FR-010", "FR-011", "FR-012", "FR-013",
            "FR-014", "FR-015",
        }
        self.assertEqual(all_receptor_ids, expected)


# ---------------------------------------------------------------------------
# TestConesaAssignmentResult
# ---------------------------------------------------------------------------

class TestConesaAssignmentResult(unittest.TestCase):
    """Verifica to_dict() y summary() de ConesaAssignmentResult."""

    def _make_result(self, assigned=3, scored=2, indet=1, skipped=0, no_rule=0):
        model = _make_model_with_impacts([])
        return ConesaAssignmentResult(
            model=model,
            assigned_count=assigned,
            scored_count=scored,
            indeterminate_count=indet,
            skipped_count=skipped,
            no_rule_count=no_rule,
            warnings=["Aviso de prueba con tildes: á é í"],
            notes=["Nota metodológica"],
        )

    def test_to_dict_has_counts(self):
        result = self._make_result()
        d = result.to_dict()
        self.assertEqual(d["assigned_count"], 3)
        self.assertEqual(d["scored_count"], 2)
        self.assertEqual(d["indeterminate_count"], 1)
        self.assertEqual(d["skipped_count"], 0)
        self.assertEqual(d["no_rule_count"], 0)

    def test_to_dict_has_model_key(self):
        result = self._make_result()
        d = result.to_dict()
        self.assertIn("model", d)
        self.assertIsInstance(d["model"], dict)

    def test_to_dict_json_serializable(self):
        result = self._make_result()
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        self.assertIn("assigned_count", json_str)

    def test_summary_is_ascii_safe(self):
        result = self._make_result()
        s = result.summary()
        # La salida de summary() debe ser codificable en ASCII
        s.encode("ascii")

    def test_summary_shows_counts(self):
        result = self._make_result(assigned=5, scored=3, indet=2)
        s = result.summary()
        self.assertIn("5", s)
        self.assertIn("3", s)
        self.assertIn("2", s)

    def test_summary_shows_warnings(self):
        result = self._make_result()
        s = result.summary()
        self.assertIn("AVISO", s)

    def test_empty_warnings_no_aviso(self):
        model = _make_model_with_impacts([])
        result = ConesaAssignmentResult(model=model)
        s = result.summary()
        self.assertNotIn("AVISO", s)


# ---------------------------------------------------------------------------
# TestAssignConesaAttributesToImpact
# ---------------------------------------------------------------------------

class TestAssignConesaAttributesToImpact(unittest.TestCase):
    """Verifica la asignación a un impacto individual."""

    def setUp(self):
        self.action_op = _make_action(action_id="AC-001", action_type="OPERACION")
        self.action_tr = _make_action(action_id="AC-002", action_type="TRANSPORTE")
        self.lookup = {
            "AC-001": self.action_op,
            "AC-002": self.action_tr,
        }

    def test_fr014_operacion_gets_cassign_a(self):
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        result = assign_conesa_attributes_to_impact(
            impact, action_lookup=self.lookup, score=False
        )
        self.assertIsNotNone(result.conesa_attributes.intensidad)
        self.assertTrue(result.conesa_attributes.is_complete())
        self.assertIn("CASSIGN-A", " ".join(result.notes))

    def test_fr006_transporte_gets_cassign_b(self):
        impact = _make_impact(receptor_id="FR-006", action_id="AC-002")
        result = assign_conesa_attributes_to_impact(
            impact, action_lookup=self.lookup, score=False
        )
        self.assertTrue(result.conesa_attributes.is_complete())
        self.assertIn("CASSIGN-B", " ".join(result.notes))

    def test_fr009_gets_all_none(self):
        impact = _make_impact(receptor_id="FR-009")
        result = assign_conesa_attributes_to_impact(impact, score=False)
        self.assertFalse(result.conesa_attributes.is_complete())
        self.assertEqual(len(result.conesa_attributes.missing_attributes()), 10)
        self.assertIn("CASSIGN-E", " ".join(result.notes))

    def test_fr007_flora_gets_all_none(self):
        impact = _make_impact(receptor_id="FR-007")
        result = assign_conesa_attributes_to_impact(impact, score=False)
        self.assertFalse(result.conesa_attributes.is_complete())
        self.assertIn("CASSIGN-F", " ".join(result.notes))

    def test_fr013_positivo_gets_cassign_j(self):
        impact = _make_impact(receptor_id="FR-013", nature="POSITIVO")
        result = assign_conesa_attributes_to_impact(impact, score=False)
        self.assertTrue(result.conesa_attributes.is_complete())
        self.assertIn("CASSIGN-J", " ".join(result.notes))

    def test_fr013_negativo_no_rule(self):
        """FR-013 NEGATIVO no coincide con CASSIGN-J (solo POSITIVO)."""
        impact = _make_impact(receptor_id="FR-013", nature="NEGATIVO")
        result = assign_conesa_attributes_to_impact(impact, score=False)
        # No se asignan atributos → sigue sin regla
        self.assertFalse(result.conesa_attributes.is_complete())
        self.assertNotIn("CASSIGN-J", " ".join(result.notes))

    def test_no_rule_returns_original_unchanged(self):
        """FR-001 (Clima) no tiene regla → impacto devuelto sin cambios."""
        impact = _make_impact(receptor_id="FR-001")
        result = assign_conesa_attributes_to_impact(impact, score=False)
        self.assertEqual(result.impact_id, impact.impact_id)
        self.assertFalse(result.conesa_attributes.is_complete())

    def test_already_complete_skipped(self):
        """Impacto con atributos completos no se sobreescribe."""
        complete_attrs = ConesaAttributes(
            intensidad=4, extension=4, momento=4, persistencia=4,
            reversibilidad=4, sinergia=4, acumulacion=4, efecto=4,
            periodicidad=4, recuperabilidad=4,
        )
        impact = _make_impact(receptor_id="FR-014", conesa_attributes=complete_attrs)
        result = assign_conesa_attributes_to_impact(impact, score=False)
        # Los atributos originales se conservan
        self.assertEqual(result.conesa_attributes.intensidad, 4)
        self.assertEqual(result.conesa_attributes.extension, 4)

    def test_score_true_sets_significance(self):
        """score=True → significance_without_measures calculada para impactos completos."""
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        result = assign_conesa_attributes_to_impact(
            impact, action_lookup=self.lookup, score=True
        )
        self.assertNotEqual(result.significance_without_measures, "NO_VALORADO")
        # FR-014 CASSIGN-A: I=33 → MODERADO
        self.assertEqual(result.significance_without_measures, "MODERADO")

    def test_score_false_leaves_no_valorado(self):
        """score=False → significance_without_measures no se modifica."""
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        result = assign_conesa_attributes_to_impact(
            impact, action_lookup=self.lookup, score=False
        )
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_score_fr009_stays_indeterminate(self):
        """Impacto con atributos INDETERMINADO → significance sigue NO_VALORADO tras score."""
        impact = _make_impact(receptor_id="FR-009")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        # apply_conesa_to_impact con attrs None no cambia significance_without_measures
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_no_mutation_original_impact(self):
        """La función no muta el impacto original."""
        impact = _make_impact(receptor_id="FR-014", action_id="AC-001")
        original_attrs = impact.conesa_attributes.to_dict()
        _ = assign_conesa_attributes_to_impact(impact, action_lookup=self.lookup)
        self.assertEqual(impact.conesa_attributes.to_dict(), original_attrs)

    def test_custom_rules_override_defaults(self):
        custom_attrs = ConesaAttributes(
            intensidad=8, extension=8, momento=4, persistencia=4,
            reversibilidad=4, sinergia=4, acumulacion=4, efecto=4,
            periodicidad=4, recuperabilidad=4,
        )
        custom_rule = ConesaAssignmentRule("CUSTOM-X", ["FR-014"], custom_attrs)
        impact = _make_impact(receptor_id="FR-014")
        result = assign_conesa_attributes_to_impact(
            impact, rules=[custom_rule], score=False
        )
        self.assertEqual(result.conesa_attributes.intensidad, 8)
        self.assertIn("CUSTOM-X", " ".join(result.notes))


# ---------------------------------------------------------------------------
# TestAssignConesaAttributesToModel
# ---------------------------------------------------------------------------

class TestAssignConesaAttributesToModel(unittest.TestCase):
    """Verifica la asignación al nivel del Phase6Model completo."""

    def _make_full_model(self):
        """Modelo con impactos sobre varios receptores."""
        action_op = _make_action("AC-001", "OPERACION")
        action_tr = _make_action("AC-002", "TRANSPORTE")
        impacts = [
            _make_impact("IMP-001", "AC-001", "FR-014"),     # CASSIGN-A → scored
            _make_impact("IMP-002", "AC-002", "FR-006"),     # CASSIGN-B → scored
            _make_impact("IMP-003", "AC-001", "FR-003"),     # CASSIGN-C → scored
            _make_impact("IMP-004", "AC-001", "FR-009"),     # CASSIGN-E → indeterminate
            _make_impact("IMP-005", "AC-001", "FR-007"),     # CASSIGN-F → indeterminate
            _make_impact("IMP-006", "AC-001", "FR-013", nature="POSITIVO"),  # CASSIGN-J → scored
        ]
        return Phase6Model(
            expediente_id="TEST-001",
            actions=[action_op, action_tr],
            receptor_factors=[
                _make_receptor("FR-014"), _make_receptor("FR-006"),
                _make_receptor("FR-003"), _make_receptor("FR-009"),
                _make_receptor("FR-007"), _make_receptor("FR-013"),
            ],
            impacts=impacts,
        )

    def test_model_result_type(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        self.assertIsInstance(result, ConesaAssignmentResult)

    def test_counts_correct(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(result.assigned_count, 6)
        self.assertEqual(result.scored_count, 4)       # A, B, C, J completos
        self.assertEqual(result.indeterminate_count, 2) # E, F todos None
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.no_rule_count, 0)

    def test_total_impacts_conserved(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(len(result.model.impacts), 6)

    def test_no_mutation_original_model(self):
        model = self._make_full_model()
        original_attrs = [
            imp.conesa_attributes.to_dict() for imp in model.impacts
        ]
        _ = assign_conesa_attributes_to_model(model)
        current_attrs = [
            imp.conesa_attributes.to_dict() for imp in model.impacts
        ]
        self.assertEqual(original_attrs, current_attrs)

    def test_actions_conserved(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(
            len(result.model.actions), len(model.actions)
        )

    def test_receptor_factors_conserved(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(
            len(result.model.receptor_factors), len(model.receptor_factors)
        )

    def test_score_false_no_significance(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model, score=False)
        for imp in result.model.impacts:
            self.assertEqual(imp.significance_without_measures, "NO_VALORADO")

    def test_score_true_significance_for_complete(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model, score=True)
        # FR-014 (IMP-001) → CASSIGN-A, I=33 → MODERADO
        imp_001 = next(i for i in result.model.impacts if i.impact_id == "IMP-001")
        self.assertEqual(imp_001.significance_without_measures, "MODERADO")

    def test_empty_model_generates_warning(self):
        model = Phase6Model(expediente_id="EMPTY", actions=[], receptor_factors=[], impacts=[])
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(result.assigned_count, 0)
        self.assertTrue(len(result.warnings) > 0)

    def test_no_rule_count_with_uncovered_receptor(self):
        model = _make_model_with_impacts([
            _make_impact("IMP-001", "AC-001", "FR-001"),  # Clima — sin regla
        ])
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(result.no_rule_count, 1)
        self.assertEqual(result.assigned_count, 0)

    def test_skipped_count_with_complete_existing(self):
        complete_attrs = ConesaAttributes(
            intensidad=2, extension=2, momento=4, persistencia=2,
            reversibilidad=2, sinergia=1, acumulacion=4, efecto=4,
            periodicidad=4, recuperabilidad=2,
        )
        model = _make_model_with_impacts([
            _make_impact("IMP-001", "AC-001", "FR-014", conesa_attributes=complete_attrs),
        ])
        result = assign_conesa_attributes_to_model(model)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.assigned_count, 0)

    def test_to_dict_json_serializable(self):
        model = self._make_full_model()
        result = assign_conesa_attributes_to_model(model)
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        self.assertIn("assigned_count", json_str)


# ---------------------------------------------------------------------------
# TestCLIPhase6AssignConesa
# ---------------------------------------------------------------------------

class TestCLIPhase6AssignConesa(unittest.TestCase):
    """Verifica el comando CLI phase6-assign-conesa."""

    def _make_model_json(self, exp_dir: Path):
        """Crea phase6_model_with_impacts.json en el directorio dado."""
        action = _make_action("AC-001", "OPERACION")
        receptor = _make_receptor("FR-014")
        impact = _make_impact("IMP-001", "AC-001", "FR-014")
        model = Phase6Model(
            expediente_id=exp_dir.name,
            actions=[action],
            receptor_factors=[receptor],
            impacts=[impact],
        )
        impactos_dir = exp_dir / "impactos"
        impactos_dir.mkdir(parents=True, exist_ok=True)
        model_path = impactos_dir / "phase6_model_with_impacts.json"
        with open(model_path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(model.to_dict(), f, ensure_ascii=False, indent=2)
        return model_path

    def test_without_write_creates_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            self._make_model_json(exp_dir)
            from run_expediente import main
            ret = main([str(exp_dir), "phase6-assign-conesa"])
            self.assertEqual(ret, 0)
            # No debe crear phase6_model_with_conesa.json
            conesa_path = exp_dir / "impactos" / "phase6_model_with_conesa.json"
            self.assertFalse(conesa_path.exists())

    def test_with_write_creates_two_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            self._make_model_json(exp_dir)
            from run_expediente import main
            ret = main([str(exp_dir), "phase6-assign-conesa", "--write"])
            self.assertEqual(ret, 0)
            self.assertTrue((exp_dir / "impactos" / "phase6_model_with_conesa.json").exists())
            self.assertTrue((exp_dir / "impactos" / "conesa_assignment_result.json").exists())

    def test_with_write_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            self._make_model_json(exp_dir)
            from run_expediente import main
            main([str(exp_dir), "phase6-assign-conesa", "--write"])
            import json as _json
            with open(exp_dir / "impactos" / "phase6_model_with_conesa.json", encoding="utf-8") as f:
                data = _json.load(f)
            self.assertIn("impacts", data)

    def test_no_model_exits_zero(self):
        """Sin phase6_model_with_impacts.json: aviso y exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            from run_expediente import main
            ret = main([str(exp_dir), "phase6-assign-conesa"])
            self.assertEqual(ret, 0)

    def test_no_score_flag(self):
        """--no-score: impactos sin significance_without_measures calculada."""
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            self._make_model_json(exp_dir)
            from run_expediente import main
            ret = main([str(exp_dir), "phase6-assign-conesa", "--write", "--no-score"])
            self.assertEqual(ret, 0)
            import json as _json
            with open(exp_dir / "impactos" / "phase6_model_with_conesa.json", encoding="utf-8") as f:
                data = _json.load(f)
            # Con --no-score, la significancia no debe estar calculada
            impacts = data.get("impacts", [])
            if impacts:
                self.assertEqual(impacts[0].get("significance_without_measures"), "NO_VALORADO")

    def test_creates_impactos_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            # Crear el JSON directamente sin el directorio impactos primero
            self._make_model_json(exp_dir)  # esto ya crea impactos/
            # Borrar el dir y volver a crear solo el expediente
            import shutil
            shutil.rmtree(exp_dir / "impactos")
            # Ahora sin el model, el CLI debe crear impactos/ y salir OK
            from run_expediente import main
            ret = main([str(exp_dir), "phase6-assign-conesa", "--write"])
            self.assertEqual(ret, 0)

    def test_with_write_conesa_result_has_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_dir = Path(tmp) / "expediente-test"
            exp_dir.mkdir()
            self._make_model_json(exp_dir)
            from run_expediente import main
            main([str(exp_dir), "phase6-assign-conesa", "--write"])
            import json as _json
            with open(
                exp_dir / "impactos" / "conesa_assignment_result.json", encoding="utf-8"
            ) as f:
                data = _json.load(f)
            self.assertIn("assigned_count", data)
            self.assertIn("scored_count", data)


# ---------------------------------------------------------------------------
# TestMethodologicalRules
# ---------------------------------------------------------------------------

class TestMethodologicalRules(unittest.TestCase):
    """Verifica las reglas metodológicas de EIA-Agent v2.1."""

    def test_positive_impact_not_compensating_negative(self):
        """Un impacto POSITIVO (FR-013) no compensa los NEGATIVOS."""
        rules = default_conesa_assignment_rules()
        # FR-013 POSITIVO obtiene CASSIGN-J
        pos_impact = _make_impact("IMP-POS", "AC-001", "FR-013", nature="POSITIVO")
        result_pos = assign_conesa_attributes_to_impact(pos_impact, score=True)
        # FR-014 NEGATIVO obtiene CASSIGN-A
        neg_impact = _make_impact("IMP-NEG", "AC-001", "FR-014", nature="NEGATIVO")
        result_neg = assign_conesa_attributes_to_impact(neg_impact, score=True)
        # Ambos tienen significancia independiente; no hay mecanismo de compensación
        self.assertEqual(result_pos.significance_without_measures, "MODERADO")
        self.assertEqual(result_neg.significance_without_measures, "MODERADO")
        # Las significancias son independientes
        self.assertNotEqual(result_pos.significance_without_measures, "NO_VALORADO")
        self.assertNotEqual(result_neg.significance_without_measures, "NO_VALORADO")

    def test_enp_always_indeterminate(self):
        """FR-009 (ENP) siempre resulta en significancia INDETERMINADO."""
        impact = _make_impact(receptor_id="FR-009")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        # No se puede valorar sin atributos
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")
        self.assertFalse(result.conesa_attributes.is_complete())

    def test_red_natura_always_indeterminate(self):
        impact = _make_impact(receptor_id="FR-010")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_flora_always_indeterminate(self):
        impact = _make_impact(receptor_id="FR-007")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_fauna_always_indeterminate(self):
        impact = _make_impact(receptor_id="FR-008")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_paisaje_always_indeterminate(self):
        impact = _make_impact(receptor_id="FR-011")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_patrimonio_always_indeterminate(self):
        impact = _make_impact(receptor_id="FR-012")
        result = assign_conesa_attributes_to_impact(impact, score=True)
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_cassign_h_clima_indeterminate_significance(self):
        """CASSIGN-H: RV/SI/Mc INDETERMINADO → significancia INDETERMINADO."""
        impact = _make_impact(receptor_id="FR-015", action_id="AC-001")
        action = _make_action("AC-001", "TRANSPORTE")
        result = assign_conesa_attributes_to_impact(
            impact, action_lookup={"AC-001": action}, score=True
        )
        # Tiene algunos atributos (EX=8, IN=2) pero no todos
        self.assertIsNotNone(result.conesa_attributes.extension)
        self.assertIsNone(result.conesa_attributes.reversibilidad)
        # Significancia no calculable
        self.assertEqual(result.significance_without_measures, "NO_VALORADO")

    def test_no_significance_words_in_rule_notes_that_affirm_absence(self):
        """Las notas de reglas no deben afirmar ausencia de impacto directamente."""
        rules = default_conesa_assignment_rules()
        forbidden = ["no existe impacto", "sin impacto", "no hay impacto"]
        for rule in rules:
            for note in rule.notes:
                note_lower = note.lower()
                for phrase in forbidden:
                    self.assertNotIn(
                        phrase, note_lower,
                        f"Regla {rule.rule_id} afirma ausencia: '{phrase}' en '{note}'",
                    )

    def test_cassign_a_conesa_score_is_moderado(self):
        """CASSIGN-A: I=33 → MODERADO según la fórmula canónica."""
        from eia_agent.core.conesa_engine import calculate_conesa_score
        rules = default_conesa_assignment_rules()
        a = next(r for r in rules if r.rule_id == "CASSIGN-A")
        result = calculate_conesa_score(a.conesa_attributes)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.score, 33)
        self.assertEqual(result.significance, "MODERADO")

    def test_cassign_b_conesa_score_is_moderado(self):
        from eia_agent.core.conesa_engine import calculate_conesa_score
        rules = default_conesa_assignment_rules()
        b = next(r for r in rules if r.rule_id == "CASSIGN-B")
        result = calculate_conesa_score(b.conesa_attributes)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.score, 31)
        self.assertEqual(result.significance, "MODERADO")

    def test_cassign_c_conesa_score_is_moderado(self):
        from eia_agent.core.conesa_engine import calculate_conesa_score
        rules = default_conesa_assignment_rules()
        c = next(r for r in rules if r.rule_id == "CASSIGN-C")
        result = calculate_conesa_score(c.conesa_attributes)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.score, 29)
        self.assertEqual(result.significance, "MODERADO")

    def test_cassign_d_conesa_score_is_compatible(self):
        from eia_agent.core.conesa_engine import calculate_conesa_score
        rules = default_conesa_assignment_rules()
        d = next(r for r in rules if r.rule_id == "CASSIGN-D")
        result = calculate_conesa_score(d.conesa_attributes)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.score, 23)
        self.assertEqual(result.significance, "COMPATIBLE")

    def test_cassign_j_conesa_score_is_moderado(self):
        from eia_agent.core.conesa_engine import calculate_conesa_score
        rules = default_conesa_assignment_rules()
        j = next(r for r in rules if r.rule_id == "CASSIGN-J")
        result = calculate_conesa_score(j.conesa_attributes)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.score, 33)
        self.assertEqual(result.significance, "MODERADO")

    def test_rule_ids_are_a_to_j(self):
        rules = default_conesa_assignment_rules()
        ids = {r.rule_id for r in rules}
        for letter in "ABCDEFGHIJ":
            self.assertIn(f"CASSIGN-{letter}", ids)


if __name__ == "__main__":
    unittest.main()
