"""
Tests para conesa_engine (IM-01).
Motor determinístico de valoración Conesa para Fase 6 EIA.
"""
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
    ProjectAction,
    ReceptorFactor,
)
from eia_agent.core.conesa_engine import (
    CONESA_MIN_VALUE,
    CONESA_MAX_VALUE,
    ConesaScoreResult,
    apply_conesa_to_impact,
    calculate_conesa_score,
    classify_conesa_score,
    score_phase6_impacts,
    validate_conesa_attributes,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _full_attrs(**kwargs) -> ConesaAttributes:
    """Devuelve ConesaAttributes completos con valor 1 salvo lo que se especifique."""
    defaults = {
        "intensidad": 1,
        "extension": 1,
        "momento": 1,
        "persistencia": 1,
        "reversibilidad": 1,
        "sinergia": 1,
        "acumulacion": 1,
        "efecto": 1,
        "periodicidad": 1,
        "recuperabilidad": 1,
    }
    defaults.update(kwargs)
    return ConesaAttributes(**defaults)


def _impact(impact_id: str = "IMP-001", nature: str = "NEGATIVO", **kwargs) -> EnvironmentalImpact:
    defaults = {
        "impact_id": impact_id,
        "action_id": "AC-001",
        "receptor_id": "FR-001",
        "name": "Impacto test",
    }
    defaults.update(kwargs)
    return EnvironmentalImpact(nature=nature, **defaults)


def _score_13() -> ConesaAttributes:
    """I = 3*1 + 2*1 + 1*8 = 3+2+8 = 13 → COMPATIBLE (<25)."""
    return ConesaAttributes(
        intensidad=1, extension=1, momento=8,
        persistencia=1, reversibilidad=1, sinergia=1,
        acumulacion=1, efecto=1, periodicidad=1, recuperabilidad=1,
    )


def _score_25() -> ConesaAttributes:
    """I = 3*4 + 2*1 + 1*9 = 12+2+9 = 23 → ajustar para llegar a 25.
    I = 3*4 + 2*3 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 = 12+6+8 = 26 → MODERADO."""
    return ConesaAttributes(
        intensidad=4, extension=3, momento=1,
        persistencia=1, reversibilidad=1, sinergia=1,
        acumulacion=1, efecto=1, periodicidad=1, recuperabilidad=1,
    )


def _score_exact(target: int) -> ConesaAttributes:
    """Construye atributos cuyo score sea exactamente target.

    Usa la fórmula: I = 3*IN + 2*EX + MO + PE + RV + SI + AC + EF + PR + Mc
    Fija IN=1, EX=1 → contribución = 5. Reparte el resto en MO (único valor variable).
    Si MO > 12, distribuye en PE también.
    """
    base = 5  # 3*1 + 2*1
    rest = target - base
    # rest en 8 atributos de peso 1 cada uno (MO, PE, RV, SI, AC, EF, PR, Mc)
    # Distribuir equitativamente, max 12 por atributo
    attrs = [1, 1, 1, 1, 1, 1, 1, 1]  # 8 attrs de peso 1
    remaining = rest - 8  # ya tenemos 8 × 1
    idx = 0
    while remaining > 0 and idx < 8:
        add = min(11, remaining)  # max añadir 11 (de 1 a 12)
        attrs[idx] += add
        remaining -= add
        idx += 1
    mo, pe, rv, si, ac, ef, pr, mc = attrs
    return ConesaAttributes(
        intensidad=1, extension=1,
        momento=mo, persistencia=pe, reversibilidad=rv, sinergia=si,
        acumulacion=ac, efecto=ef, periodicidad=pr, recuperabilidad=mc,
    )


# ---------------------------------------------------------------------------
# TestClassifyConesaScore
# ---------------------------------------------------------------------------

class TestClassifyConesaScore(unittest.TestCase):

    def test_none_returns_indeterminado(self):
        self.assertEqual(classify_conesa_score(None), "INDETERMINADO")

    def test_zero_returns_compatible(self):
        # 0 < 25
        self.assertEqual(classify_conesa_score(0), "COMPATIBLE")

    def test_24_returns_compatible(self):
        self.assertEqual(classify_conesa_score(24), "COMPATIBLE")

    def test_25_returns_moderado(self):
        self.assertEqual(classify_conesa_score(25), "MODERADO")

    def test_49_returns_moderado(self):
        self.assertEqual(classify_conesa_score(49), "MODERADO")

    def test_50_returns_severo(self):
        self.assertEqual(classify_conesa_score(50), "SEVERO")

    def test_74_returns_severo(self):
        self.assertEqual(classify_conesa_score(74), "SEVERO")

    def test_75_returns_critico(self):
        self.assertEqual(classify_conesa_score(75), "CRITICO")

    def test_100_returns_critico(self):
        self.assertEqual(classify_conesa_score(100), "CRITICO")

    def test_threshold_boundaries_are_inclusive_lower(self):
        """25 es el primer MODERADO, 50 el primer SEVERO, 75 el primer CRITICO."""
        self.assertEqual(classify_conesa_score(25), "MODERADO")
        self.assertEqual(classify_conesa_score(50), "SEVERO")
        self.assertEqual(classify_conesa_score(75), "CRITICO")

    def test_threshold_boundaries_are_exclusive_upper(self):
        """24, 49, 74 pertenecen a la categoría anterior."""
        self.assertEqual(classify_conesa_score(24), "COMPATIBLE")
        self.assertEqual(classify_conesa_score(49), "MODERADO")
        self.assertEqual(classify_conesa_score(74), "SEVERO")


# ---------------------------------------------------------------------------
# TestValidateConesaAttributes
# ---------------------------------------------------------------------------

class TestValidateConesaAttributes(unittest.TestCase):

    def test_all_valid_returns_empty(self):
        attrs = _full_attrs()
        self.assertEqual(validate_conesa_attributes(attrs), [])

    def test_all_none_returns_empty(self):
        attrs = ConesaAttributes()
        self.assertEqual(validate_conesa_attributes(attrs), [])

    def test_value_at_min_is_valid(self):
        attrs = _full_attrs(intensidad=CONESA_MIN_VALUE)
        self.assertEqual(validate_conesa_attributes(attrs), [])

    def test_value_at_max_is_valid(self):
        attrs = _full_attrs(intensidad=CONESA_MAX_VALUE)
        self.assertEqual(validate_conesa_attributes(attrs), [])

    def test_value_below_min_returns_error(self):
        attrs = _full_attrs(intensidad=0)
        errors = validate_conesa_attributes(attrs)
        self.assertEqual(len(errors), 1)
        self.assertIn("intensidad", errors[0])

    def test_value_above_max_returns_error(self):
        attrs = _full_attrs(extension=13)
        errors = validate_conesa_attributes(attrs)
        self.assertEqual(len(errors), 1)
        self.assertIn("extension", errors[0])

    def test_negative_value_returns_error(self):
        attrs = _full_attrs(momento=-1)
        errors = validate_conesa_attributes(attrs)
        self.assertEqual(len(errors), 1)

    def test_multiple_invalid_returns_multiple_errors(self):
        attrs = _full_attrs(intensidad=0, extension=13)
        errors = validate_conesa_attributes(attrs)
        self.assertEqual(len(errors), 2)

    def test_none_fields_not_reported_as_error(self):
        attrs = ConesaAttributes(intensidad=None, extension=1)
        errors = validate_conesa_attributes(attrs)
        self.assertEqual(errors, [])

    def test_all_max_valid(self):
        attrs = _full_attrs(
            intensidad=12, extension=12, momento=12, persistencia=12,
            reversibilidad=12, sinergia=12, acumulacion=12, efecto=12,
            periodicidad=12, recuperabilidad=12,
        )
        self.assertEqual(validate_conesa_attributes(attrs), [])


# ---------------------------------------------------------------------------
# TestCalculateConesaScore
# ---------------------------------------------------------------------------

class TestCalculateConesaScore(unittest.TestCase):

    def test_all_ones_score_is_13(self):
        """I = 3*1 + 2*1 + 1+1+1+1+1+1+1+1 = 5 + 8 = 13."""
        attrs = _full_attrs()
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 13)

    def test_all_ones_significance_compatible(self):
        attrs = _full_attrs()
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.significance, "COMPATIBLE")

    def test_score_is_complete_when_all_present(self):
        result = calculate_conesa_score(_full_attrs())
        self.assertTrue(result.is_complete)
        self.assertEqual(result.missing_attributes, [])

    def test_missing_one_attribute_returns_indeterminado(self):
        attrs = ConesaAttributes(
            intensidad=None, extension=1, momento=1, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertIsNone(result.score)
        self.assertEqual(result.significance, "INDETERMINADO")
        self.assertFalse(result.is_complete)
        self.assertIn("intensidad", result.missing_attributes)

    def test_all_none_returns_indeterminado(self):
        result = calculate_conesa_score(ConesaAttributes())
        self.assertIsNone(result.score)
        self.assertEqual(result.significance, "INDETERMINADO")
        self.assertEqual(len(result.missing_attributes), 10)

    def test_formula_weights(self):
        """Verifica pesos: IN×3, EX×2, resto×1."""
        # IN=2, EX=2, resto=1
        # I = 3*2 + 2*2 + 1*8 = 6+4+8 = 18
        attrs = _full_attrs(intensidad=2, extension=2)
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 18)

    def test_score_25_is_moderado(self):
        attrs = _score_25()
        result = calculate_conesa_score(attrs)
        self.assertGreaterEqual(result.score, 25)
        self.assertEqual(result.significance, "MODERADO")

    def test_score_50_is_severo(self):
        attrs = _full_attrs(intensidad=12, extension=12)
        # I = 36 + 24 + 8 = 68 → SEVERO
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.significance, "SEVERO")

    def test_score_75_is_critico(self):
        # I = 3*12 + 2*12 + 12*8 = 36+24+96 = 156 — pero max es 3*12+2*12+8*12=156
        attrs = _full_attrs(
            intensidad=12, extension=12, momento=12, persistencia=12,
            reversibilidad=12, sinergia=12, acumulacion=12, efecto=12,
            periodicidad=12, recuperabilidad=12,
        )
        result = calculate_conesa_score(attrs)
        self.assertGreaterEqual(result.score, 75)
        self.assertEqual(result.significance, "CRITICO")

    def test_out_of_range_attribute_adds_warning(self):
        attrs = _full_attrs(intensidad=0)
        result = calculate_conesa_score(attrs)
        self.assertTrue(any("intensidad" in w for w in result.warnings))

    def test_result_is_instance_of_ConesaScoreResult(self):
        result = calculate_conesa_score(_full_attrs())
        self.assertIsInstance(result, ConesaScoreResult)

    def test_to_dict_keys(self):
        result = calculate_conesa_score(_full_attrs())
        d = result.to_dict()
        self.assertIn("score", d)
        self.assertIn("significance", d)
        self.assertIn("is_complete", d)
        self.assertIn("missing_attributes", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_to_dict_json_serializable(self):
        result = calculate_conesa_score(_full_attrs())
        json.dumps(result.to_dict())

    def test_summary_complete(self):
        attrs = _full_attrs()
        result = calculate_conesa_score(attrs)
        summary = result.summary()
        self.assertIn("I=", summary)
        self.assertIn("COMPATIBLE", summary)

    def test_summary_incomplete(self):
        result = calculate_conesa_score(ConesaAttributes())
        summary = result.summary()
        self.assertIn("INDETERMINADO", summary)
        self.assertIn("faltan", summary)

    def test_max_possible_score(self):
        """Score máximo = 3*12 + 2*12 + 8*12 = 156."""
        attrs = _full_attrs(
            intensidad=12, extension=12, momento=12, persistencia=12,
            reversibilidad=12, sinergia=12, acumulacion=12, efecto=12,
            periodicidad=12, recuperabilidad=12,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 156)

    def test_min_possible_score(self):
        """Score mínimo (todos=1) = 3 + 2 + 8 = 13."""
        result = calculate_conesa_score(_full_attrs())
        self.assertEqual(result.score, 13)

    def test_missing_attributes_list_accurate(self):
        attrs = ConesaAttributes(intensidad=1, extension=None, momento=None)
        result = calculate_conesa_score(attrs)
        self.assertIn("extension", result.missing_attributes)
        self.assertIn("momento", result.missing_attributes)
        self.assertNotIn("intensidad", result.missing_attributes)

    def test_boundary_score_24_compatible(self):
        # Buscar combinación que dé exactamente 24
        # IN=1, EX=1 → base=5. Resto=19 en 8 atributos de peso 1
        # 8*1=8, necesito 11 más → MO=12, PE=1, resto=1
        # I = 3+2+12+1+1+1+1+1+1+1 = 24
        attrs = ConesaAttributes(
            intensidad=1, extension=1, momento=12, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 24)
        self.assertEqual(result.significance, "COMPATIBLE")

    def test_boundary_score_25_moderado(self):
        # I = 3+2+12+2+1+1+1+1+1+1 = 25
        attrs = ConesaAttributes(
            intensidad=1, extension=1, momento=12, persistencia=2,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 25)
        self.assertEqual(result.significance, "MODERADO")

    def test_boundary_score_49_moderado(self):
        # I = 3*4 + 2*4 + 1+1+1+1+1+1+1+1 = 12+8+8 = 28 → necesito más
        # I = 3*8 + 2*8 + 1*8 = 24+16+8 = 48, falta 1
        # I = 3*8 + 2*8 + 2+1+1+1+1+1+1+1 = 24+16+9 = 49
        attrs = ConesaAttributes(
            intensidad=8, extension=8, momento=2, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 49)
        self.assertEqual(result.significance, "MODERADO")

    def test_boundary_score_50_severo(self):
        # I = 3*8 + 2*8 + 3+1+1+1+1+1+1+1 = 24+16+10 = 50
        attrs = ConesaAttributes(
            intensidad=8, extension=8, momento=3, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 50)
        self.assertEqual(result.significance, "SEVERO")

    def test_boundary_score_74_severo(self):
        # I = 3*12 + 2*8 + 2+2+1+1+1+1+1+1 = 36+16+10 = 62 → falta más
        # I = 3*12 + 2*12 + 2+1+1+1+1+1+1+1 = 36+24+9 = 69 → falta 5
        # I = 3*12 + 2*12 + 7+1+1+1+1+1+1+1 = 36+24+14 = 74
        attrs = ConesaAttributes(
            intensidad=12, extension=12, momento=7, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 74)
        self.assertEqual(result.significance, "SEVERO")

    def test_boundary_score_75_critico(self):
        # I = 3*12 + 2*12 + 8+1+1+1+1+1+1+1 = 36+24+15 = 75
        attrs = ConesaAttributes(
            intensidad=12, extension=12, momento=8, persistencia=1,
            reversibilidad=1, sinergia=1, acumulacion=1, efecto=1,
            periodicidad=1, recuperabilidad=1,
        )
        result = calculate_conesa_score(attrs)
        self.assertEqual(result.score, 75)
        self.assertEqual(result.significance, "CRITICO")


# ---------------------------------------------------------------------------
# TestApplyConesaToImpact
# ---------------------------------------------------------------------------

class TestApplyConesaToImpact(unittest.TestCase):

    def test_without_measures_updates_significance_without(self):
        impact = _impact(conesa_attributes=_full_attrs())
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertNotEqual(updated.significance_without_measures, "NO_VALORADO")

    def test_without_measures_does_not_touch_significance_with(self):
        impact = _impact(conesa_attributes=_full_attrs(), significance_with_measures="NO_VALORADO")
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(updated.significance_with_measures, "NO_VALORADO")

    def test_with_measures_updates_significance_with(self):
        impact = _impact(conesa_attributes=_full_attrs())
        updated = apply_conesa_to_impact(impact, with_measures=True)
        self.assertNotEqual(updated.significance_with_measures, "NO_VALORADO")

    def test_with_measures_does_not_touch_significance_without(self):
        original_sig = "SEVERO"
        impact = _impact(
            conesa_attributes=_full_attrs(),
            significance_without_measures=original_sig,
        )
        updated = apply_conesa_to_impact(impact, with_measures=True)
        self.assertEqual(updated.significance_without_measures, original_sig)

    def test_complete_attrs_sets_status_valorado(self):
        impact = _impact(conesa_attributes=_full_attrs())
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(updated.status, "VALORADO")

    def test_incomplete_attrs_does_not_change_status(self):
        impact = _impact(conesa_attributes=ConesaAttributes())
        original_status = impact.status
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(updated.status, original_status)

    def test_does_not_mutate_original(self):
        impact = _impact(conesa_attributes=_full_attrs())
        original_sig = impact.significance_without_measures
        _ = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(impact.significance_without_measures, original_sig)

    def test_incomplete_adds_warning(self):
        impact = _impact(conesa_attributes=ConesaAttributes())
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertTrue(len(updated.warnings) > 0)
        self.assertTrue(any("faltan" in w.lower() or "No valorado" in w for w in updated.warnings))

    def test_complete_computes_correct_significance(self):
        # Todos=1 → I=13 → COMPATIBLE
        impact = _impact(conesa_attributes=_full_attrs())
        updated = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(updated.significance_without_measures, "COMPATIBLE")

    def test_returns_new_instance(self):
        impact = _impact(conesa_attributes=_full_attrs())
        updated = apply_conesa_to_impact(impact)
        self.assertIsNot(updated, impact)

    def test_other_fields_preserved(self):
        impact = _impact(
            impact_id="IMP-007",
            action_id="AC-003",
            receptor_id="FR-005",
            name="Test impacto",
            conesa_attributes=_full_attrs(),
        )
        updated = apply_conesa_to_impact(impact)
        self.assertEqual(updated.impact_id, "IMP-007")
        self.assertEqual(updated.action_id, "AC-003")
        self.assertEqual(updated.receptor_id, "FR-005")
        self.assertEqual(updated.name, "Test impacto")

    def test_default_with_measures_is_false(self):
        impact = _impact(conesa_attributes=_full_attrs())
        updated_default = apply_conesa_to_impact(impact)
        updated_explicit = apply_conesa_to_impact(impact, with_measures=False)
        self.assertEqual(
            updated_default.significance_without_measures,
            updated_explicit.significance_without_measures,
        )

    def test_out_of_range_still_updates_significance(self):
        """Atributo fuera de rango genera aviso pero la función no bloquea el cálculo."""
        attrs = _full_attrs(intensidad=0)  # fuera de rango pero not None
        impact = _impact(conesa_attributes=attrs)
        updated = apply_conesa_to_impact(impact, with_measures=False)
        # El score se calcula de todas formas (0 es un entero)
        self.assertNotEqual(updated.significance_without_measures, "NO_VALORADO")
        self.assertTrue(any("intensidad" in w for w in updated.warnings))


# ---------------------------------------------------------------------------
# TestScorePhase6Impacts
# ---------------------------------------------------------------------------

class TestScorePhase6Impacts(unittest.TestCase):

    def _make_model(self, impacts: list) -> Phase6Model:
        return Phase6Model(expediente_id="EXP-TEST", impacts=impacts)

    def test_empty_model_returns_empty(self):
        model = self._make_model([])
        scored = score_phase6_impacts(model)
        self.assertEqual(scored.impacts, [])

    def test_does_not_mutate_original_model(self):
        impact = _impact(conesa_attributes=_full_attrs())
        model = self._make_model([impact])
        _ = score_phase6_impacts(model)
        self.assertEqual(model.impacts[0].significance_without_measures, "NO_VALORADO")

    def test_returns_new_model_instance(self):
        model = self._make_model([])
        scored = score_phase6_impacts(model)
        self.assertIsNot(scored, model)

    def test_all_impacts_scored_without_measures(self):
        impacts = [
            _impact("IMP-001", conesa_attributes=_full_attrs()),
            _impact("IMP-002", conesa_attributes=_full_attrs()),
        ]
        model = self._make_model(impacts)
        scored = score_phase6_impacts(model, with_measures=False)
        for imp in scored.impacts:
            self.assertNotEqual(imp.significance_without_measures, "NO_VALORADO")

    def test_all_impacts_scored_with_measures(self):
        impacts = [
            _impact("IMP-001", conesa_attributes=_full_attrs()),
        ]
        model = self._make_model(impacts)
        scored = score_phase6_impacts(model, with_measures=True)
        for imp in scored.impacts:
            self.assertNotEqual(imp.significance_with_measures, "NO_VALORADO")

    def test_other_model_fields_preserved(self):
        from eia_agent.core.impact_model import MitigationMeasure, PVAProgram
        action = ProjectAction(action_id="AC-001", name="Acción", action_type="OPERACION")
        receptor = ReceptorFactor(
            receptor_id="FR-001", inventory_factor_id="FI-001", name="Clima",
            inventory_semaphore="VERDE", ready_from_inventory=True,
        )
        measure = MitigationMeasure(measure_id="MED-001", name="Medida", measure_type="PREVENTIVA")
        pva = PVAProgram(
            pva_id="PVA-001", name="PVA", factor_id="FI-001",
            indicator="Ind", frequency="MENSUAL",
        )
        model = Phase6Model(
            expediente_id="EXP-001",
            actions=[action],
            receptor_factors=[receptor],
            impacts=[_impact(conesa_attributes=_full_attrs())],
            measures=[measure],
            pva_programs=[pva],
            notes=["nota de prueba"],
        )
        scored = score_phase6_impacts(model)
        self.assertEqual(scored.expediente_id, "EXP-001")
        self.assertEqual(len(scored.actions), 1)
        self.assertEqual(len(scored.receptor_factors), 1)
        self.assertEqual(len(scored.measures), 1)
        self.assertEqual(len(scored.pva_programs), 1)
        self.assertEqual(scored.notes, ["nota de prueba"])

    def test_count_of_impacts_unchanged(self):
        impacts = [_impact(f"IMP-{str(i).zfill(3)}", conesa_attributes=_full_attrs()) for i in range(1, 6)]
        model = self._make_model(impacts)
        scored = score_phase6_impacts(model)
        self.assertEqual(len(scored.impacts), 5)

    def test_incomplete_impacts_get_warning_not_error(self):
        impact = _impact("IMP-001", conesa_attributes=ConesaAttributes())
        model = self._make_model([impact])
        scored = score_phase6_impacts(model)
        self.assertEqual(len(scored.impacts), 1)
        self.assertTrue(len(scored.impacts[0].warnings) > 0)

    def test_default_with_measures_false(self):
        impact = _impact(conesa_attributes=_full_attrs())
        model = self._make_model([impact])
        scored_default = score_phase6_impacts(model)
        scored_explicit = score_phase6_impacts(model, with_measures=False)
        self.assertEqual(
            scored_default.impacts[0].significance_without_measures,
            scored_explicit.impacts[0].significance_without_measures,
        )

    def test_mixed_complete_incomplete(self):
        impacts = [
            _impact("IMP-001", conesa_attributes=_full_attrs()),
            _impact("IMP-002", conesa_attributes=ConesaAttributes()),
        ]
        model = self._make_model(impacts)
        scored = score_phase6_impacts(model)
        self.assertEqual(scored.impacts[0].status, "VALORADO")
        self.assertNotEqual(scored.impacts[1].status, "VALORADO")


# ---------------------------------------------------------------------------
# TestMethodologicalRules
# ---------------------------------------------------------------------------

class TestMethodologicalRules(unittest.TestCase):

    def test_conesa_min_max_constants(self):
        self.assertEqual(CONESA_MIN_VALUE, 1)
        self.assertEqual(CONESA_MAX_VALUE, 12)

    def test_classify_all_threshold_sequence(self):
        """Secuencia completa de categorías en los umbrales exactos."""
        categories = [
            (0, "COMPATIBLE"),
            (24, "COMPATIBLE"),
            (25, "MODERADO"),
            (49, "MODERADO"),
            (50, "SEVERO"),
            (74, "SEVERO"),
            (75, "CRITICO"),
            (156, "CRITICO"),
        ]
        for score, expected in categories:
            with self.subTest(score=score):
                self.assertEqual(classify_conesa_score(score), expected)

    def test_intensidad_weight_3(self):
        """Incrementar intensidad en 1 debe incrementar I en 3."""
        base = _full_attrs(intensidad=1)
        higher = _full_attrs(intensidad=2)
        r1 = calculate_conesa_score(base)
        r2 = calculate_conesa_score(higher)
        self.assertEqual(r2.score - r1.score, 3)

    def test_extension_weight_2(self):
        """Incrementar extension en 1 debe incrementar I en 2."""
        base = _full_attrs(extension=1)
        higher = _full_attrs(extension=2)
        r1 = calculate_conesa_score(base)
        r2 = calculate_conesa_score(higher)
        self.assertEqual(r2.score - r1.score, 2)

    def test_remaining_attributes_weight_1(self):
        """Incrementar cualquier atributo restante en 1 debe incrementar I en 1."""
        for attr_name in ["momento", "persistencia", "reversibilidad", "sinergia",
                          "acumulacion", "efecto", "periodicidad", "recuperabilidad"]:
            base = _full_attrs(**{attr_name: 1})
            higher = _full_attrs(**{attr_name: 2})
            r1 = calculate_conesa_score(base)
            r2 = calculate_conesa_score(higher)
            with self.subTest(attr=attr_name):
                self.assertEqual(r2.score - r1.score, 1)

    def test_indeterminado_threshold_is_none_only(self):
        """INDETERMINADO sólo aparece cuando score es None (atributos incompletos)."""
        # Cualquier entero → no INDETERMINADO
        for i in [0, 1, 24, 25, 49, 50, 74, 75, 100, 156]:
            self.assertNotEqual(classify_conesa_score(i), "INDETERMINADO")
        # None → INDETERMINADO
        self.assertEqual(classify_conesa_score(None), "INDETERMINADO")

    def test_score_result_to_dict_is_serializable(self):
        result = calculate_conesa_score(ConesaAttributes())
        d = result.to_dict()
        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)

    def test_no_side_effects_on_repeated_calls(self):
        """Llamadas repetidas a calculate_conesa_score con los mismos attrs dan mismo resultado."""
        attrs = _full_attrs(intensidad=5, extension=4)
        r1 = calculate_conesa_score(attrs)
        r2 = calculate_conesa_score(attrs)
        self.assertEqual(r1.score, r2.score)
        self.assertEqual(r1.significance, r2.significance)

    def test_apply_conesa_idempotent_on_same_attrs(self):
        """Aplicar dos veces con los mismos atributos no cambia el resultado."""
        impact = _impact(conesa_attributes=_full_attrs())
        updated1 = apply_conesa_to_impact(impact, with_measures=False)
        updated2 = apply_conesa_to_impact(updated1, with_measures=False)
        self.assertEqual(
            updated1.significance_without_measures,
            updated2.significance_without_measures,
        )


if __name__ == "__main__":
    unittest.main()
