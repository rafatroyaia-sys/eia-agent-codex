"""
Tests para conditional_chain_validator -- IM-09.

Suite offline: sin IA, sin web, sin APIs externas.
No modifica expedientes piloto.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.conditional_chain_validator import (
    CONDITIONAL_CHAIN_STATUS,
    CONDITIONAL_MARKERS,
    ConditionalChainIssue,
    ConditionalChainResult,
    build_conditional_chain_report_markdown,
    impact_is_conditioned,
    measure_is_conditioned,
    pva_is_conditioned,
    text_contains_condition_marker,
    validate_conditioned_impact_chain,
    validate_conditioned_measure_chain,
    validate_conditioned_pva_chain,
    validate_conditional_chains,
    validate_conditional_chains_from_files,
    validate_conditional_chains_from_json,
    write_conditional_chain_outputs,
)
from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_action(action_id="AC-001"):
    return ProjectAction(action_id=action_id, name="Accion test")


def _make_receptor(receptor_id="FR-003"):
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id="FI-003",
        name="Suelos",
        inventory_semaphore="AMARILLO",
        notes=["Test"],
    )


def _make_impact(
    impact_id="IMP-001",
    status="PENDIENTE_DATOS",
    significance="NO_VALORADO",
    data_gaps=None,
    notes=None,
    warnings=None,
    measure_ids=None,
    pva_ids=None,
):
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id="FR-003",
        name=f"Impacto {impact_id}",
        status=status,
        significance_without_measures=significance,
        significance_with_measures=significance,
        data_gaps=data_gaps or [],
        notes=notes or [],
        warnings=warnings or [],
        measure_ids=measure_ids or [],
        pva_ids=pva_ids or [],
    )


def _make_measure(
    measure_id="MED-001",
    measure_type="CORRECTORA",
    status="PROPUESTA",
    is_diagnostic=False,
    notes=None,
    warnings=None,
    name=None,
    description="",
    target_impact_ids=None,
):
    return MitigationMeasure(
        measure_id=measure_id,
        name=name or f"Medida {measure_id}",
        description=description,
        measure_type=measure_type,
        status=status,
        is_diagnostic=is_diagnostic,
        target_impact_ids=target_impact_ids or [],
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_pva(
    pva_id="PVA-001",
    name=None,
    frequency="ANUAL",
    notes=None,
    warnings=None,
    indicator=None,
    target_impact_ids=None,
    target_measure_ids=None,
):
    return PVAProgram(
        pva_id=pva_id,
        name=name or f"PVA {pva_id}",
        factor_id="FI-003",
        indicator=indicator or "Indicador test",
        threshold="umbral test",
        frequency=frequency,
        target_impact_ids=target_impact_ids or [],
        target_measure_ids=target_measure_ids or [],
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_model(impacts=None, measures=None, pva_programs=None):
    return Phase6Model(
        expediente_id="TEST",
        actions=[_make_action()],
        receptor_factors=[_make_receptor()],
        impacts=impacts or [],
        measures=measures or [],
        pva_programs=pva_programs or [],
    )


# ---------------------------------------------------------------------------
# 1. TestTextContainsConditionMarker
# ---------------------------------------------------------------------------

class TestTextContainsConditionMarker(unittest.TestCase):

    def test_detects_gap(self):
        self.assertTrue(text_contains_condition_marker("Hay un GAP en datos"))

    def test_detects_cont(self):
        self.assertTrue(text_contains_condition_marker("CONT-001 activo"))

    def test_detects_at(self):
        self.assertTrue(text_contains_condition_marker("AT-001 activada"))

    def test_detects_condicionado(self):
        self.assertTrue(text_contains_condition_marker("estado condicionado"))

    def test_detects_indeterminado(self):
        self.assertTrue(text_contains_condition_marker("significancia indeterminado"))

    def test_detects_consulta_pendiente(self):
        self.assertTrue(text_contains_condition_marker("consulta pendiente al promotor"))

    def test_no_detects_normal_text(self):
        self.assertFalse(text_contains_condition_marker("impacto moderado sobre suelos"))

    def test_no_detects_empty_string(self):
        self.assertFalse(text_contains_condition_marker(""))

    def test_case_insensitive(self):
        self.assertTrue(text_contains_condition_marker("CONDICIONADO"))
        self.assertTrue(text_contains_condition_marker("Indeterminado"))

    def test_detects_incertidumbre(self):
        self.assertTrue(text_contains_condition_marker("existe incertidumbre"))

    def test_no_detects_preventiva_correctora(self):
        self.assertFalse(text_contains_condition_marker("medida preventiva correctora"))

    def test_detects_asuncion_test(self):
        self.assertTrue(text_contains_condition_marker("asuncion test AT"))


# ---------------------------------------------------------------------------
# 2. TestImpactIsConditioned
# ---------------------------------------------------------------------------

class TestImpactIsConditioned(unittest.TestCase):

    def test_status_indeterminado(self):
        imp = _make_impact(status="INDETERMINADO")
        self.assertTrue(impact_is_conditioned(imp))

    def test_status_pendiente_datos(self):
        imp = _make_impact(status="PENDIENTE_DATOS")
        self.assertTrue(impact_is_conditioned(imp))

    def test_indeterminado_significance_with_gaps(self):
        imp = _make_impact(
            status="VALORADO",
            significance="INDETERMINADO",
            data_gaps=["GAP-001"],
        )
        self.assertTrue(impact_is_conditioned(imp))

    def test_no_valorado_with_gaps(self):
        imp = _make_impact(
            status="IDENTIFICADO",
            significance="NO_VALORADO",
            data_gaps=["GAP-FI-003-001"],
        )
        self.assertTrue(impact_is_conditioned(imp))

    def test_any_data_gap_triggers(self):
        imp = _make_impact(
            status="IDENTIFICADO",
            significance="MODERADO",
            data_gaps=["GAP-001"],
        )
        self.assertTrue(impact_is_conditioned(imp))

    def test_notes_with_cont(self):
        imp = _make_impact(
            status="IDENTIFICADO",
            significance="MODERADO",
            notes=["Vinculado a CONT-001"],
        )
        self.assertTrue(impact_is_conditioned(imp))

    def test_warnings_with_at(self):
        imp = _make_impact(
            status="IDENTIFICADO",
            significance="MODERADO",
            warnings=["Pendiente resolución AT-001"],
        )
        self.assertTrue(impact_is_conditioned(imp))

    def test_valorado_sin_gaps_false(self):
        imp = _make_impact(
            status="VALORADO",
            significance="MODERADO",
        )
        self.assertFalse(impact_is_conditioned(imp))

    def test_compatible_sin_gaps_false(self):
        imp = _make_impact(
            status="IDENTIFICADO",
            significance="COMPATIBLE",
        )
        self.assertFalse(impact_is_conditioned(imp))


# ---------------------------------------------------------------------------
# 3. TestMeasureIsConditioned
# ---------------------------------------------------------------------------

class TestMeasureIsConditioned(unittest.TestCase):

    def test_diagnostica_type(self):
        m = _make_measure(measure_type="DIAGNOSTICA")
        self.assertTrue(measure_is_conditioned(m))

    def test_is_diagnostic_flag(self):
        m = _make_measure(is_diagnostic=True, measure_type="DIAGNOSTICA")
        self.assertTrue(measure_is_conditioned(m))

    def test_status_condicionada(self):
        m = _make_measure(status="CONDICIONADA")
        self.assertTrue(measure_is_conditioned(m))

    def test_status_condicion_previa(self):
        m = _make_measure(status="CONDICION_PREVIA")
        self.assertTrue(measure_is_conditioned(m))

    def test_notes_consulta_pendiente(self):
        m = _make_measure(notes=["Requiere consulta pendiente al CABILDO"])
        self.assertTrue(measure_is_conditioned(m))

    def test_notes_gap(self):
        m = _make_measure(notes=["Vinculada a GAP-001"])
        self.assertTrue(measure_is_conditioned(m))

    def test_description_indeterminado(self):
        m = _make_measure(description="Medida condicionada a datos indeterminados")
        self.assertTrue(measure_is_conditioned(m))

    def test_normal_correctora_false(self):
        m = _make_measure(measure_type="CORRECTORA", status="PROPUESTA")
        self.assertFalse(measure_is_conditioned(m))

    def test_preventiva_propuesta_false(self):
        m = _make_measure(measure_type="PREVENTIVA", status="PROPUESTA")
        self.assertFalse(measure_is_conditioned(m))


# ---------------------------------------------------------------------------
# 4. TestPvaIsConditioned
# ---------------------------------------------------------------------------

class TestPvaIsConditioned(unittest.TestCase):

    def test_frequency_condicional(self):
        p = _make_pva(frequency="CONDICIONAL")
        self.assertTrue(pva_is_conditioned(p))

    def test_notes_gap(self):
        p = _make_pva(notes=["Asociado a GAP-FI-003-001"])
        self.assertTrue(pva_is_conditioned(p))

    def test_notes_cont(self):
        p = _make_pva(notes=["Activo mientras CONT-001 no esté resuelto"])
        self.assertTrue(pva_is_conditioned(p))

    def test_notes_at(self):
        p = _make_pva(notes=["Depende de AT-001"])
        self.assertTrue(pva_is_conditioned(p))

    def test_name_condicionado(self):
        p = _make_pva(name="PVA condicionado a confirmacion")
        self.assertTrue(pva_is_conditioned(p))

    def test_indicator_indeterminado(self):
        p = _make_pva(indicator="Seguimiento hasta dato confirmado (indeterminado)")
        self.assertTrue(pva_is_conditioned(p))

    def test_warnings_consulta_pendiente(self):
        p = _make_pva(warnings=["consulta pendiente al organismo gestor"])
        self.assertTrue(pva_is_conditioned(p))

    def test_pva_normal_false(self):
        p = _make_pva(frequency="ANUAL")
        self.assertFalse(pva_is_conditioned(p))

    def test_pva_semestral_sin_markers_false(self):
        p = _make_pva(frequency="SEMESTRAL")
        self.assertFalse(pva_is_conditioned(p))


# ---------------------------------------------------------------------------
# 5. TestValidateConditionedImpactChain
# ---------------------------------------------------------------------------

class TestValidateConditionedImpactChain(unittest.TestCase):

    def test_conditioned_impact_no_measures_no_pva_error(self):
        imp = _make_impact(status="INDETERMINADO")
        issues = validate_conditioned_impact_chain(imp, [], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-IMP-E001", codes)

    def test_conditioned_impact_with_diagnostic_measure(self):
        imp = _make_impact(
            status="INDETERMINADO",
            measure_ids=["MED-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_impact_chain(imp, [med], [])
        # CC-IMP-E001 no debería aparecer; puede haber W002 por sin PVA
        codes = [i.code for i in issues]
        self.assertNotIn("CC-IMP-E001", codes)

    def test_conditioned_impact_with_diagnostic_and_conditioned_pva_ok(self):
        imp = _make_impact(
            status="INDETERMINADO",
            measure_ids=["MED-001"],
            pva_ids=["PVA-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_impact_chain(imp, [med], [pva])
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_conditioned_impact_unconditioned_correctora_severo_error(self):
        imp = _make_impact(
            status="INDETERMINADO",
            significance="INDETERMINADO",
            measure_ids=["MED-001"],
        )
        # Medida correctora sin condición sobre impacto INDETERMINADO
        med = _make_measure(
            measure_id="MED-001",
            measure_type="CORRECTORA",
            status="PROPUESTA",
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_impact_chain(imp, [med], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-IMP-E002", codes)

    def test_conditioned_impact_pva_not_conditioned_warning(self):
        imp = _make_impact(
            status="INDETERMINADO",
            measure_ids=["MED-001"],
            pva_ids=["PVA-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="ANUAL",  # no condicionado
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_impact_chain(imp, [med], [pva])
        codes = [i.code for i in issues]
        self.assertIn("CC-IMP-W002", codes)

    def test_no_issues_normal_impact(self):
        imp = _make_impact(status="VALORADO", significance="MODERADO")
        # No debería validar cadena (impacto no condicionado)
        # validate_conditioned_impact_chain se llama SOLO para condicionados
        # En el modelo, solo se llama si impact_is_conditioned(imp) es True
        self.assertFalse(impact_is_conditioned(imp))


# ---------------------------------------------------------------------------
# 6. TestValidateConditionedMeasureChain
# ---------------------------------------------------------------------------

class TestValidateConditionedMeasureChain(unittest.TestCase):

    def test_diagnostic_only_measure_severo_error(self):
        imp = _make_impact(
            impact_id="IMP-001",
            status="VALORADO",
            significance="SEVERO",
            measure_ids=["MED-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_measure_chain(med, [imp], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-MEA-E001", codes)

    def test_conditioned_measure_no_pva_warning(self):
        imp = _make_impact(
            impact_id="IMP-001",
            status="INDETERMINADO",
            measure_ids=["MED-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            status="CONDICIONADA",
            target_impact_ids=["IMP-001"],
        )
        issues = validate_conditioned_measure_chain(med, [imp], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-MEA-W001", codes)

    def test_conditioned_measure_with_pva_no_warning(self):
        imp = _make_impact(
            impact_id="IMP-001",
            status="INDETERMINADO",
            measure_ids=["MED-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            status="CONDICIONADA",
            target_impact_ids=["IMP-001"],
        )
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            target_impact_ids=["IMP-001"],
            target_measure_ids=["MED-001"],
        )
        issues = validate_conditioned_measure_chain(med, [imp], [pva])
        w001_issues = [i for i in issues if i.code == "CC-MEA-W001"]
        self.assertEqual(len(w001_issues), 0)


# ---------------------------------------------------------------------------
# 7. TestValidateConditionedPvaChain
# ---------------------------------------------------------------------------

class TestValidateConditionedPvaChain(unittest.TestCase):

    def test_conditioned_pva_no_reference_warning(self):
        pva = _make_pva(pva_id="PVA-001", frequency="CONDICIONAL")
        issues = validate_conditioned_pva_chain(pva, [], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-PVA-W001", codes)

    def test_conditioned_pva_with_impact_reference_no_w001(self):
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            target_impact_ids=["IMP-001"],
        )
        imp = _make_impact(impact_id="IMP-001", status="INDETERMINADO")
        issues = validate_conditioned_pva_chain(pva, [imp], [])
        w001_issues = [i for i in issues if i.code == "CC-PVA-W001"]
        self.assertEqual(len(w001_issues), 0)

    def test_conditioned_pva_closing_language_warning(self):
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            notes=["Este PVA queda resuelto tras confirmación"],
        )
        issues = validate_conditioned_pva_chain(pva, [], [])
        codes = [i.code for i in issues]
        self.assertIn("CC-PVA-W002", codes)

    def test_conditioned_pva_with_marker_text_no_w001(self):
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            notes=["Asociado a CONT-001 activo"],
        )
        issues = validate_conditioned_pva_chain(pva, [], [])
        w001_issues = [i for i in issues if i.code == "CC-PVA-W001"]
        self.assertEqual(len(w001_issues), 0)


# ---------------------------------------------------------------------------
# 8. TestValidateConditionalChains
# ---------------------------------------------------------------------------

class TestValidateConditionalChains(unittest.TestCase):

    def test_empty_model_sin_datos(self):
        model = _make_model()
        result = validate_conditional_chains(model)
        self.assertEqual(result.status, "SIN_DATOS")

    def test_model_without_conditioned_ok(self):
        imp = _make_impact(status="VALORADO", significance="MODERADO")
        med = _make_measure(measure_type="CORRECTORA")
        pva = _make_pva(frequency="ANUAL")
        model = _make_model(impacts=[imp], measures=[med], pva_programs=[pva])
        result = validate_conditional_chains(model)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.error_count(), 0)

    def test_model_with_broken_chain_no_conforme(self):
        imp = _make_impact(status="INDETERMINADO")
        model = _make_model(impacts=[imp])
        result = validate_conditional_chains(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertGreater(result.error_count(), 0)

    def test_model_not_mutated(self):
        imp = _make_impact(status="INDETERMINADO")
        model = _make_model(impacts=[imp])
        original_status = imp.status
        original_notes = list(imp.notes)
        validate_conditional_chains(model)
        self.assertEqual(imp.status, original_status)
        self.assertEqual(imp.notes, original_notes)

    def test_conditioned_impact_detected(self):
        imp = _make_impact(status="PENDIENTE_DATOS")
        model = _make_model(impacts=[imp])
        result = validate_conditional_chains(model)
        self.assertIn(imp.impact_id, result.conditioned_impacts)

    def test_conditioned_measure_detected(self):
        imp = _make_impact(status="VALORADO", significance="MODERADO", measure_ids=["MED-001"])
        med = _make_measure(measure_type="DIAGNOSTICA", is_diagnostic=True, target_impact_ids=["IMP-001"])
        model = _make_model(impacts=[imp], measures=[med])
        result = validate_conditional_chains(model)
        self.assertIn(med.measure_id, result.conditioned_measures)

    def test_conditioned_pva_detected(self):
        pva = _make_pva(frequency="CONDICIONAL")
        imp = _make_impact(status="VALORADO", significance="MODERADO")
        model = _make_model(impacts=[imp], pva_programs=[pva])
        result = validate_conditional_chains(model)
        self.assertIn(pva.pva_id, result.conditioned_pva_programs)

    def test_administrative_ready_always_false(self):
        model = _make_model()
        result = validate_conditional_chains(model)
        self.assertFalse(result.to_dict()["administrative_ready"])

    def test_valid_chain_ok_status(self):
        imp = _make_impact(
            status="INDETERMINADO",
            measure_ids=["MED-001"],
            pva_ids=["PVA-001"],
        )
        med = _make_measure(
            measure_id="MED-001",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        pva = _make_pva(
            pva_id="PVA-001",
            frequency="CONDICIONAL",
            target_impact_ids=["IMP-001"],
            notes=["Vinculado a CONT-001"],
        )
        model = _make_model(impacts=[imp], measures=[med], pva_programs=[pva])
        result = validate_conditional_chains(model)
        # No debe haber errores (puede haber warnings)
        self.assertEqual(result.error_count(), 0)

    def test_is_valid_true_when_no_errors(self):
        imp = _make_impact(status="VALORADO", significance="MODERADO")
        model = _make_model(impacts=[imp])
        result = validate_conditional_chains(model)
        self.assertTrue(result.is_valid())

    def test_is_valid_false_when_errors(self):
        imp = _make_impact(status="INDETERMINADO")
        model = _make_model(impacts=[imp])
        result = validate_conditional_chains(model)
        self.assertFalse(result.is_valid())


# ---------------------------------------------------------------------------
# 9. TestValidateConditionalChainsFromFiles
# ---------------------------------------------------------------------------

class TestValidateConditionalChainsFromFiles(unittest.TestCase):

    def test_expediente_without_model_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-TEST"
            exp.mkdir()
            (exp / "impactos").mkdir()
            result = validate_conditional_chains_from_files(exp)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_expediente_without_impactos_dir_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-TEST"
            exp.mkdir()
            result = validate_conditional_chains_from_files(exp)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_expediente_with_valid_model_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-TEST"
            exp.mkdir()
            impactos = exp / "impactos"
            impactos.mkdir()
            model_data = {
                "expediente_id": "TEST",
                "actions": [{"action_id": "AC-001", "name": "Accion", "action_type": "OTRO"}],
                "receptor_factors": [
                    {
                        "receptor_id": "FR-003",
                        "inventory_factor_id": "FI-003",
                        "name": "Suelos",
                        "notes": ["test"],
                    }
                ],
                "impacts": [
                    {
                        "impact_id": "IMP-001",
                        "action_id": "AC-001",
                        "receptor_id": "FR-003",
                        "name": "Impacto suelos",
                        "status": "VALORADO",
                        "significance_without_measures": "MODERADO",
                        "significance_with_measures": "COMPATIBLE",
                        "conesa_attributes": {},
                    }
                ],
                "measures": [],
                "pva_programs": [],
            }
            json_path = impactos / "phase6_model_with_pva.json"
            json_path.write_text(json.dumps(model_data), encoding="utf-8")
            result = validate_conditional_chains_from_files(exp)
            self.assertNotEqual(result.status, "SIN_DATOS")

    def test_expediente_with_broken_chain_no_conforme(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-TEST"
            exp.mkdir()
            impactos = exp / "impactos"
            impactos.mkdir()
            model_data = {
                "expediente_id": "TEST",
                "actions": [{"action_id": "AC-001", "name": "Accion", "action_type": "OTRO"}],
                "receptor_factors": [
                    {
                        "receptor_id": "FR-003",
                        "inventory_factor_id": "FI-003",
                        "name": "Suelos",
                        "notes": ["test"],
                    }
                ],
                "impacts": [
                    {
                        "impact_id": "IMP-001",
                        "action_id": "AC-001",
                        "receptor_id": "FR-003",
                        "name": "Impacto suelos",
                        "status": "INDETERMINADO",
                        "significance_without_measures": "INDETERMINADO",
                        "significance_with_measures": "INDETERMINADO",
                        "conesa_attributes": {},
                        "data_gaps": ["GAP-001"],
                    }
                ],
                "measures": [],
                "pva_programs": [],
            }
            json_path = impactos / "phase6_model_with_pva.json"
            json_path.write_text(json.dumps(model_data), encoding="utf-8")
            result = validate_conditional_chains_from_files(exp)
            self.assertEqual(result.status, "NO_CONFORME")


# ---------------------------------------------------------------------------
# 10. TestBuildConditionalChainReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildConditionalChainReportMarkdown(unittest.TestCase):

    def _result_with_conditioned_impact(self):
        result = ConditionalChainResult(
            status="NO_CONFORME",
            checked_impacts=["IMP-001"],
            conditioned_impacts=["IMP-001"],
            issues=[
                ConditionalChainIssue(
                    severity="ERROR",
                    code="CC-IMP-E001",
                    impact_id="IMP-001",
                    message="Cadena rota",
                    recommendation="Anadir medida diagnostica",
                )
            ],
        )
        return result

    def test_report_contains_title(self):
        result = self._result_with_conditioned_impact()
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("# Auditoría de cadenas condicionales", md)

    def test_report_contains_conditioned_impact(self):
        result = self._result_with_conditioned_impact()
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("IMP-001", md)

    def test_report_contains_scope_warning(self):
        result = ConditionalChainResult(status="OK")
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("no resuelve gaps", md.lower())

    def test_report_contains_administrative_ready_false(self):
        result = ConditionalChainResult(status="OK")
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("administrative_ready = False", md)

    def test_report_contains_resumen_section(self):
        result = ConditionalChainResult(status="OK")
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("## 1. Resumen", md)

    def test_report_contains_all_sections(self):
        result = ConditionalChainResult(status="OK")
        md = build_conditional_chain_report_markdown(result)
        for i in range(1, 8):
            self.assertIn(f"## {i}.", md)

    def test_report_no_conditioned_message_when_empty(self):
        result = ConditionalChainResult(status="OK")
        md = build_conditional_chain_report_markdown(result)
        self.assertIn("No se detectan impactos condicionados", md)


# ---------------------------------------------------------------------------
# 11. TestWriteConditionalChainOutputs
# ---------------------------------------------------------------------------

class TestWriteConditionalChainOutputs(unittest.TestCase):

    def test_writes_json_and_md(self):
        result = ConditionalChainResult(status="OK")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "auditoria"
            json_path, md_path = write_conditional_chain_outputs(result, out_dir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid_with_administrative_ready_false(self):
        result = ConditionalChainResult(status="OK")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "auditoria"
            json_path, _ = write_conditional_chain_outputs(result, out_dir)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("administrative_ready", data)
            self.assertFalse(data["administrative_ready"])

    def test_returns_two_paths(self):
        result = ConditionalChainResult(status="OK")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            paths = write_conditional_chain_outputs(result, out_dir)
            self.assertEqual(len(paths), 2)

    def test_creates_output_dir_if_not_exists(self):
        result = ConditionalChainResult(status="OK")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "nested" / "auditoria"
            write_conditional_chain_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())

    def test_json_contains_status(self):
        result = ConditionalChainResult(status="CON_OBSERVACIONES")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            json_path, _ = write_conditional_chain_outputs(result, out_dir)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["status"], "CON_OBSERVACIONES")


# ---------------------------------------------------------------------------
# 12. TestConditionalChainIssue
# ---------------------------------------------------------------------------

class TestConditionalChainIssue(unittest.TestCase):

    def test_to_dict_contains_all_fields(self):
        issue = ConditionalChainIssue(
            severity="ERROR",
            code="CC-IMP-E001",
            impact_id="IMP-001",
            message="Cadena rota",
            recommendation="Actuar",
            evidence=["dato1"],
        )
        d = issue.to_dict()
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["code"], "CC-IMP-E001")
        self.assertEqual(d["impact_id"], "IMP-001")
        self.assertIn("message", d)
        self.assertIn("recommendation", d)
        self.assertIn("evidence", d)

    def test_summary_mentions_code(self):
        issue = ConditionalChainIssue(severity="ERROR", code="CC-IMP-E001", message="test")
        s = issue.summary()
        self.assertIn("CC-IMP-E001", s)

    def test_summary_mentions_impact_id(self):
        issue = ConditionalChainIssue(
            severity="WARNING", code="CC-IMP-W001", impact_id="IMP-999", message="test"
        )
        s = issue.summary()
        self.assertIn("IMP-999", s)


# ---------------------------------------------------------------------------
# 13. TestConditionalChainResult
# ---------------------------------------------------------------------------

class TestConditionalChainResult(unittest.TestCase):

    def test_error_count(self):
        result = ConditionalChainResult(
            status="NO_CONFORME",
            issues=[
                ConditionalChainIssue(severity="ERROR", code="A", message="e1"),
                ConditionalChainIssue(severity="WARNING", code="B", message="w1"),
            ],
        )
        self.assertEqual(result.error_count(), 1)
        self.assertEqual(result.warning_count(), 1)

    def test_is_valid_true_no_errors(self):
        result = ConditionalChainResult(status="OK")
        self.assertTrue(result.is_valid())

    def test_is_valid_false_with_errors(self):
        result = ConditionalChainResult(
            status="NO_CONFORME",
            issues=[ConditionalChainIssue(severity="ERROR", code="X", message="err")],
        )
        self.assertFalse(result.is_valid())

    def test_administrative_ready_always_false(self):
        result = ConditionalChainResult(status="OK")
        d = result.to_dict()
        self.assertFalse(d["administrative_ready"])

    def test_summary_contains_status(self):
        result = ConditionalChainResult(status="NO_CONFORME")
        s = result.summary()
        self.assertIn("NO_CONFORME", s)

    def test_to_dict_contains_counts(self):
        result = ConditionalChainResult(
            status="NO_CONFORME",
            issues=[
                ConditionalChainIssue(severity="ERROR", code="A", message="e"),
                ConditionalChainIssue(severity="WARNING", code="B", message="w"),
                ConditionalChainIssue(severity="INFO", code="C", message="i"),
            ],
        )
        d = result.to_dict()
        self.assertEqual(d["error_count"], 1)
        self.assertEqual(d["warning_count"], 1)
        self.assertEqual(d["info_count"], 1)


# ---------------------------------------------------------------------------
# 14. TestCLIAuditConditionalChains
# ---------------------------------------------------------------------------

class TestCLIAuditConditionalChains(unittest.TestCase):
    """Tests de integración del comando audit-conditional-chains en run_expediente."""

    def _run_cli(self, args):
        from run_expediente import main
        return main(args)

    def test_cli_without_write_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "exp-TEST"
            exp.mkdir()
            (exp / "impactos").mkdir()
            rc = self._run_cli([str(exp), "audit-conditional-chains"])
            # exit 0 siempre (SIN_DATOS también es OK para la CLI)
            self.assertEqual(rc, 0)
            auditoria = exp / "auditoria"
            self.assertFalse((auditoria / "conditional_chain_result.json").exists())

    def test_cli_with_write_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "exp-TEST"
            exp.mkdir()
            impactos = exp / "impactos"
            impactos.mkdir()
            model_data = {
                "expediente_id": "TEST",
                "actions": [{"action_id": "AC-001", "name": "A", "action_type": "OTRO"}],
                "receptor_factors": [
                    {
                        "receptor_id": "FR-003",
                        "inventory_factor_id": "FI-003",
                        "name": "Suelos",
                        "notes": ["test"],
                    }
                ],
                "impacts": [
                    {
                        "impact_id": "IMP-001",
                        "action_id": "AC-001",
                        "receptor_id": "FR-003",
                        "name": "Impacto",
                        "status": "VALORADO",
                        "significance_without_measures": "MODERADO",
                        "significance_with_measures": "COMPATIBLE",
                        "conesa_attributes": {},
                    }
                ],
                "measures": [],
                "pva_programs": [],
            }
            (impactos / "phase6_model_with_pva.json").write_text(
                json.dumps(model_data), encoding="utf-8"
            )
            rc = self._run_cli([str(exp), "audit-conditional-chains", "--write"])
            self.assertEqual(rc, 0)
            auditoria = exp / "auditoria"
            self.assertTrue((auditoria / "conditional_chain_result.json").exists())
            self.assertTrue((auditoria / "conditional_chain_result.md").exists())

    def test_cli_exit_1_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "exp-TEST"
            exp.mkdir()
            impactos = exp / "impactos"
            impactos.mkdir()
            model_data = {
                "expediente_id": "TEST",
                "actions": [{"action_id": "AC-001", "name": "A", "action_type": "OTRO"}],
                "receptor_factors": [
                    {
                        "receptor_id": "FR-003",
                        "inventory_factor_id": "FI-003",
                        "name": "Suelos",
                        "notes": ["test"],
                    }
                ],
                "impacts": [
                    {
                        "impact_id": "IMP-001",
                        "action_id": "AC-001",
                        "receptor_id": "FR-003",
                        "name": "Impacto",
                        "status": "INDETERMINADO",
                        "significance_without_measures": "INDETERMINADO",
                        "significance_with_measures": "INDETERMINADO",
                        "conesa_attributes": {},
                        "data_gaps": ["GAP-001"],
                    }
                ],
                "measures": [],
                "pva_programs": [],
            }
            (impactos / "phase6_model_with_pva.json").write_text(
                json.dumps(model_data), encoding="utf-8"
            )
            rc = self._run_cli([str(exp), "audit-conditional-chains"])
            self.assertEqual(rc, 1)

    def test_cli_exit_0_on_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "exp-TEST"
            exp.mkdir()
            (exp / "impactos").mkdir()
            rc = self._run_cli([str(exp), "audit-conditional-chains"])
            self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# 15. TestValidateConditionalChainsFromJson
# ---------------------------------------------------------------------------

class TestValidateConditionalChainsFromJson(unittest.TestCase):

    def test_file_not_found_sin_datos(self):
        result = validate_conditional_chains_from_json("/nonexistent/path/model.json")
        self.assertEqual(result.status, "SIN_DATOS")
        self.assertTrue(len(result.warnings) > 0)

    def test_invalid_json_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text("not json", encoding="utf-8")
            result = validate_conditional_chains_from_json(p)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_valid_json_without_impacts_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model.json"
            p.write_text(json.dumps({"expediente_id": "X"}), encoding="utf-8")
            result = validate_conditional_chains_from_json(p)
            self.assertEqual(result.status, "SIN_DATOS")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
