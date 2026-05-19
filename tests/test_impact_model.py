"""
Tests para impact_model (IM-00).
Modelo base de impactos, acciones, factores receptores, medidas y PVA para Fase 6 EIA.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.impact_model import (
    ACTION_TYPES,
    CONESA_ATTRIBUTE_NAMES,
    IMPACT_NATURES,
    IMPACT_SIGNIFICANCE,
    IMPACT_STATUS,
    MEASURE_STATUS,
    MEASURE_TYPES,
    PVA_FREQUENCIES,
    RECEPTOR_FACTOR_IDS,
    RECEPTOR_FACTOR_NAMES,
    ConesaAttributes,
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    PVAProgram,
    ProjectAction,
    ReceptorFactor,
    build_empty_phase6_model,
    build_receptor_factors_from_inventory,
)
from eia_agent.core.inventory_model import (
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_all_empty_factors,
    build_inventory_summary,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_action(action_id: str = "AC-001", name: str = "Recepción de materiales") -> ProjectAction:
    return ProjectAction(
        action_id=action_id,
        name=name,
        action_type="OPERACION",
    )


def _make_receptor(
    receptor_id: str = "FR-001",
    fi_id: str = "FI-001",
    name: str = "Clima",
) -> ReceptorFactor:
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=name,
        notes=["Factor pendiente de valoración."],
    )


def _make_conesa_complete() -> ConesaAttributes:
    return ConesaAttributes(
        intensidad=4,
        extension=2,
        momento=2,
        persistencia=1,
        reversibilidad=2,
        sinergia=1,
        acumulacion=1,
        efecto=1,
        periodicidad=1,
        recuperabilidad=2,
    )


def _make_impact(
    impact_id: str = "IMP-001",
    action_id: str = "AC-001",
    receptor_id: str = "FR-001",
    nature: str = "NEGATIVO",
    significance_without: str = "MODERADO",
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id=action_id,
        receptor_id=receptor_id,
        name="Impacto sobre calidad del aire",
        nature=nature,
        significance_without_measures=significance_without,
    )


def _make_measure(
    measure_id: str = "MED-001",
    name: str = "Riego de viales",
    measure_type: str = "PREVENTIVA",
    target_ids: list[str] | None = None,
) -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id,
        name=name,
        measure_type=measure_type,
        target_impact_ids=target_ids or ["IMP-001"],
    )


def _make_pva(
    pva_id: str = "PVA-001",
    factor_id: str = "FI-006",
    indicator: str = "Concentración PM10",
    threshold: str = "50 μg/m³",
    responsible: str = "Dirección Técnica",
) -> PVAProgram:
    return PVAProgram(
        pva_id=pva_id,
        name="Vigilancia calidad del aire",
        factor_id=factor_id,
        indicator=indicator,
        threshold=threshold,
        frequency="SEMESTRAL",
        responsible=responsible,
    )


def _make_full_model() -> Phase6Model:
    action = _make_action()
    receptor = _make_receptor()
    impact = _make_impact()
    measure = _make_measure(target_ids=["IMP-001"])
    pva = _make_pva(factor_id="FI-001")
    pva.target_impact_ids = ["IMP-001"]
    pva.target_measure_ids = ["MED-001"]
    return Phase6Model(
        expediente_id="TEST-001",
        actions=[action],
        receptor_factors=[receptor],
        impacts=[impact],
        measures=[measure],
        pva_programs=[pva],
    )


def _make_summary_with_gaps() -> InventorySummary:
    """InventorySummary con el primer factor teniendo un gap ALTA pendiente."""
    factors = build_all_empty_factors()
    gap = InventoryGap(
        gap_id="GAP-FI-001-001",
        factor_id="FI-001",
        field="prospección",
        description="Falta datos de campo",
        criticality="ALTA",
        resolution_mode="CAMPO",
        status="PENDIENTE",
    )
    factors[0].gaps = [gap]
    factors[0].ready_for_impact_assessment = False
    return build_inventory_summary("TEST-GAPS", factors)


# ===========================================================================
# TestProjectAction
# ===========================================================================

class TestProjectAction(unittest.TestCase):

    def test_valid_creation(self):
        a = _make_action()
        self.assertEqual(a.action_id, "AC-001")
        self.assertEqual(a.name, "Recepción de materiales")
        self.assertEqual(a.action_type, "OPERACION")

    def test_validate_passes_for_valid_action(self):
        a = _make_action()
        issues = a.validate()
        self.assertEqual(issues, [])

    def test_invalid_action_id_wrong_prefix(self):
        a = ProjectAction(action_id="IM-001", name="Acción", action_type="OTRO")
        issues = a.validate()
        self.assertTrue(any("action_id inválido" in i for i in issues))

    def test_invalid_action_id_no_digits(self):
        a = ProjectAction(action_id="AC-", name="Acción", action_type="OTRO")
        issues = a.validate()
        self.assertTrue(any("action_id inválido" in i for i in issues))

    def test_invalid_action_id_too_short_digits(self):
        a = ProjectAction(action_id="AC-01", name="Acción", action_type="OTRO")
        issues = a.validate()
        self.assertTrue(any("action_id inválido" in i for i in issues))

    def test_invalid_action_type(self):
        a = ProjectAction(action_id="AC-001", name="Acción", action_type="DESCONOCIDO")
        issues = a.validate()
        self.assertTrue(any("action_type inválido" in i for i in issues))

    def test_empty_name(self):
        a = ProjectAction(action_id="AC-001", name="", action_type="OTRO")
        issues = a.validate()
        self.assertTrue(any("name no puede estar vacío" in i for i in issues))

    def test_whitespace_name(self):
        a = ProjectAction(action_id="AC-001", name="   ", action_type="OTRO")
        issues = a.validate()
        self.assertTrue(any("name no puede estar vacío" in i for i in issues))

    def test_to_dict(self):
        a = _make_action(action_id="AC-002")
        d = a.to_dict()
        self.assertEqual(d["action_id"], "AC-002")
        self.assertIn("name", d)
        self.assertIn("action_type", d)
        self.assertIn("source_refs", d)
        self.assertIsInstance(d["source_refs"], list)

    def test_summary_returns_string(self):
        a = _make_action()
        s = a.summary()
        self.assertIsInstance(s, str)
        self.assertIn("AC-001", s)
        self.assertIn("OPERACION", s)

    def test_all_action_types_valid(self):
        for at in ACTION_TYPES:
            a = ProjectAction(action_id="AC-001", name="Test", action_type=at)
            issues = a.validate()
            self.assertFalse(
                any("action_type inválido" in i for i in issues),
                f"action_type={at!r} should be valid",
            )

    def test_operation_code_optional(self):
        a = ProjectAction(action_id="AC-001", name="Test", action_type="OTRO")
        self.assertIsNone(a.operation_code)
        d = a.to_dict()
        self.assertIsNone(d["operation_code"])

    def test_operation_code_set(self):
        a = ProjectAction(action_id="AC-001", name="Test", action_type="OPERACION",
                          operation_code="R1201")
        d = a.to_dict()
        self.assertEqual(d["operation_code"], "R1201")

    def test_to_dict_json_serializable(self):
        a = _make_action()
        a.source_refs = ["SRC-001"]
        a.notes = ["nota"]
        json.dumps(a.to_dict())  # must not raise


# ===========================================================================
# TestReceptorFactor
# ===========================================================================

class TestReceptorFactor(unittest.TestCase):

    def test_valid_creation(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=True,
        )
        issues = r.validate()
        self.assertEqual(issues, [])

    def test_invalid_receptor_id(self):
        r = ReceptorFactor(
            receptor_id="FI-001",
            inventory_factor_id="FI-001",
            name="Clima",
            notes=["nota"],
        )
        issues = r.validate()
        self.assertTrue(any("receptor_id inválido" in i for i in issues))

    def test_invalid_inventory_factor_id(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FR-001",
            name="Clima",
            notes=["nota"],
        )
        issues = r.validate()
        self.assertTrue(any("inventory_factor_id inválido" in i for i in issues))

    def test_not_ready_with_notes_no_warning(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=False,
            notes=["Factor pendiente de campo."],
        )
        issues = r.validate()
        self.assertFalse(any("ni notes ni critical_gaps" in i for i in issues))

    def test_not_ready_no_notes_no_gaps_warning(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=False,
        )
        issues = r.validate()
        self.assertTrue(any("ni notes ni critical_gaps" in i for i in issues))

    def test_not_ready_with_critical_gaps_no_warning(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=False,
            critical_gaps=["GAP-001"],
        )
        issues = r.validate()
        self.assertFalse(any("ni notes ni critical_gaps" in i for i in issues))

    def test_to_dict(self):
        r = _make_receptor()
        d = r.to_dict()
        self.assertEqual(d["receptor_id"], "FR-001")
        self.assertIn("inventory_factor_id", d)
        self.assertIn("inventory_semaphore", d)
        self.assertIn("ready_from_inventory", d)
        self.assertIsInstance(d["critical_gaps"], list)

    def test_summary_ready(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=True,
        )
        s = r.summary()
        self.assertIn("Listo", s)

    def test_summary_not_ready(self):
        r = _make_receptor()
        s = r.summary()
        self.assertIn("Pendiente", s)

    def test_critical_gaps_preserved(self):
        r = ReceptorFactor(
            receptor_id="FR-001",
            inventory_factor_id="FI-001",
            name="Clima",
            ready_from_inventory=False,
            critical_gaps=["GAP-001", "GAP-002"],
        )
        self.assertEqual(len(r.critical_gaps), 2)
        d = r.to_dict()
        self.assertEqual(d["critical_gaps"], ["GAP-001", "GAP-002"])

    def test_receptor_factor_ids_mapping_complete(self):
        self.assertEqual(len(RECEPTOR_FACTOR_IDS), 16)
        for fr_id, fi_id in RECEPTOR_FACTOR_IDS.items():
            self.assertTrue(fr_id.startswith("FR-"))
            self.assertTrue(fi_id.startswith("FI-"))


# ===========================================================================
# TestConesaAttributes
# ===========================================================================

class TestConesaAttributes(unittest.TestCase):

    def test_default_not_complete(self):
        c = ConesaAttributes()
        self.assertFalse(c.is_complete())

    def test_all_set_is_complete(self):
        c = _make_conesa_complete()
        self.assertTrue(c.is_complete())

    def test_missing_attributes_all_when_default(self):
        c = ConesaAttributes()
        missing = c.missing_attributes()
        self.assertEqual(len(missing), 10)
        for attr in CONESA_ATTRIBUTE_NAMES:
            self.assertIn(attr, missing)

    def test_missing_attributes_partial(self):
        c = ConesaAttributes(intensidad=4, extension=2)
        missing = c.missing_attributes()
        self.assertEqual(len(missing), 8)
        self.assertNotIn("intensidad", missing)
        self.assertNotIn("extension", missing)

    def test_missing_attributes_empty_when_complete(self):
        c = _make_conesa_complete()
        self.assertEqual(c.missing_attributes(), [])

    def test_validate_all_positive_passes(self):
        c = _make_conesa_complete()
        issues = c.validate()
        self.assertEqual(issues, [])

    def test_validate_negative_value_error(self):
        c = ConesaAttributes(intensidad=-1)
        issues = c.validate()
        self.assertTrue(any("intensidad" in i for i in issues))

    def test_validate_zero_value_error(self):
        c = ConesaAttributes(extension=0)
        issues = c.validate()
        self.assertTrue(any("extension" in i for i in issues))

    def test_validate_none_not_error(self):
        c = ConesaAttributes(intensidad=None)
        issues = c.validate()
        # None means pending, not invalid
        self.assertFalse(any("intensidad" in i for i in issues))

    def test_to_dict_all_none(self):
        c = ConesaAttributes()
        d = c.to_dict()
        self.assertEqual(len(d), 10)
        for attr in CONESA_ATTRIBUTE_NAMES:
            self.assertIsNone(d[attr])

    def test_to_dict_mixed(self):
        c = ConesaAttributes(intensidad=4, extension=2)
        d = c.to_dict()
        self.assertEqual(d["intensidad"], 4)
        self.assertEqual(d["extension"], 2)
        self.assertIsNone(d["momento"])

    def test_conesa_attribute_names_count(self):
        self.assertEqual(len(CONESA_ATTRIBUTE_NAMES), 10)


# ===========================================================================
# TestEnvironmentalImpact
# ===========================================================================

class TestEnvironmentalImpact(unittest.TestCase):

    def test_valid_creation(self):
        imp = _make_impact()
        issues = imp.validate()
        # May have AVISO for MODERADO without measures, check no errors
        self.assertFalse(any("impact_id inválido" in i for i in issues))

    def test_invalid_impact_id(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-01",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
        )
        issues = imp.validate()
        self.assertTrue(any("impact_id inválido" in i for i in issues))

    def test_invalid_action_id(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="XX-001",
            receptor_id="FR-001",
            name="Test",
        )
        issues = imp.validate()
        self.assertTrue(any("action_id inválido" in i for i in issues))

    def test_invalid_receptor_id(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FI-001",
            name="Test",
        )
        issues = imp.validate()
        self.assertTrue(any("receptor_id inválido" in i for i in issues))

    def test_invalid_nature(self):
        imp = _make_impact(nature="ALTO")
        issues = imp.validate()
        self.assertTrue(any("nature inválida" in i for i in issues))

    def test_invalid_status(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            status="APROBADO",
        )
        issues = imp.validate()
        self.assertTrue(any("status inválido" in i for i in issues))

    def test_invalid_significance_without(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            significance_without_measures="DESCONOCIDO",
        )
        issues = imp.validate()
        self.assertTrue(any("significance_without_measures inválida" in i for i in issues))

    def test_invalid_significance_with(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            significance_with_measures="DESCONOCIDO",
        )
        issues = imp.validate()
        self.assertTrue(any("significance_with_measures inválida" in i for i in issues))

    def test_is_indeterminate_nature(self):
        imp = _make_impact(nature="INDETERMINADO")
        self.assertTrue(imp.is_indeterminate())

    def test_is_indeterminate_significance_without(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            significance_without_measures="INDETERMINADO",
        )
        self.assertTrue(imp.is_indeterminate())

    def test_is_indeterminate_significance_with(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            significance_with_measures="INDETERMINADO",
        )
        self.assertTrue(imp.is_indeterminate())

    def test_is_indeterminate_false_when_all_determined(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            nature="NEGATIVO",
            significance_without_measures="MODERADO",
            significance_with_measures="COMPATIBLE",
        )
        self.assertFalse(imp.is_indeterminate())

    def test_requires_measures_severo(self):
        imp = _make_impact(significance_without="SEVERO")
        self.assertTrue(imp.requires_measures())

    def test_requires_measures_critico(self):
        imp = _make_impact(significance_without="CRITICO")
        self.assertTrue(imp.requires_measures())

    def test_requires_measures_false_moderado(self):
        imp = _make_impact(significance_without="MODERADO")
        self.assertFalse(imp.requires_measures())

    def test_requires_measures_false_compatible(self):
        imp = _make_impact(significance_without="COMPATIBLE")
        self.assertFalse(imp.requires_measures())

    def test_valorado_incomplete_conesa_error(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            status="VALORADO",
            conesa_attributes=ConesaAttributes(intensidad=4),  # incomplete
        )
        issues = imp.validate()
        self.assertTrue(any("VALORADO" in i and "incompletos" in i for i in issues))

    def test_valorado_complete_conesa_no_error(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            status="VALORADO",
            conesa_attributes=_make_conesa_complete(),
        )
        issues = imp.validate()
        self.assertFalse(any("VALORADO" in i and "incompletos" in i for i in issues))

    def test_severo_without_measures_warning(self):
        imp = _make_impact(significance_without="SEVERO")
        issues = imp.validate()
        self.assertTrue(any("SEVERO" in i for i in issues))

    def test_critico_without_measures_warning(self):
        imp = _make_impact(significance_without="CRITICO")
        issues = imp.validate()
        self.assertTrue(any("CRITICO" in i for i in issues))

    def test_severo_with_measures_no_warning(self):
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Test",
            significance_without_measures="SEVERO",
            measure_ids=["MED-001"],
        )
        issues = imp.validate()
        self.assertFalse(any("SEVERO" in i and "sin medidas" in i for i in issues))

    def test_to_dict(self):
        imp = _make_impact()
        d = imp.to_dict()
        self.assertIn("impact_id", d)
        self.assertIn("conesa_attributes", d)
        self.assertIsInstance(d["conesa_attributes"], dict)
        self.assertIn("measure_ids", d)
        self.assertIn("pva_ids", d)

    def test_to_dict_json_serializable(self):
        imp = _make_impact()
        json.dumps(imp.to_dict())

    def test_summary_returns_string(self):
        imp = _make_impact()
        s = imp.summary()
        self.assertIsInstance(s, str)
        self.assertIn("IMP-001", s)


# ===========================================================================
# TestMitigationMeasure
# ===========================================================================

class TestMitigationMeasure(unittest.TestCase):

    def test_valid_creation(self):
        m = _make_measure()
        issues = m.validate()
        self.assertEqual(issues, [])

    def test_invalid_measure_id(self):
        m = MitigationMeasure(measure_id="M-001", name="Test", measure_type="PREVENTIVA",
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("measure_id inválido" in i for i in issues))

    def test_empty_name(self):
        m = MitigationMeasure(measure_id="MED-001", name="",
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("name no puede estar vacío" in i for i in issues))

    def test_invalid_measure_type(self):
        m = MitigationMeasure(measure_id="MED-001", name="Test",
                              measure_type="INEXISTENTE",
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("measure_type inválido" in i for i in issues))

    def test_invalid_status(self):
        m = MitigationMeasure(measure_id="MED-001", name="Test",
                              status="APROBADA",
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("status inválido" in i for i in issues))

    def test_prl_only_with_wrong_type_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="EPIs",
                              measure_type="PREVENTIVA",
                              is_prl_only=True,
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("is_prl_only=True" in i for i in issues))

    def test_prl_only_with_correct_type_no_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="EPIs",
                              measure_type="PRL_NO_EIA",
                              is_prl_only=True)
        issues = m.validate()
        self.assertFalse(any("is_prl_only=True" in i for i in issues))

    def test_diagnostic_with_wrong_type_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="Test",
                              measure_type="PREVENTIVA",
                              is_diagnostic=True,
                              target_impact_ids=["IMP-001"])
        issues = m.validate()
        self.assertTrue(any("is_diagnostic=True" in i for i in issues))

    def test_diagnostic_with_correct_type_no_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="Monitoreo",
                              measure_type="DIAGNOSTICA",
                              is_diagnostic=True)
        issues = m.validate()
        self.assertFalse(any("is_diagnostic=True" in i for i in issues))

    def test_empty_target_preventiva_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="Test",
                              measure_type="PREVENTIVA",
                              target_impact_ids=[])
        issues = m.validate()
        self.assertTrue(any("target_impact_ids vacío" in i for i in issues))

    def test_empty_target_documental_no_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="Plan gestión",
                              measure_type="DOCUMENTAL",
                              target_impact_ids=[])
        issues = m.validate()
        self.assertFalse(any("target_impact_ids vacío" in i for i in issues))

    def test_empty_target_prl_no_warning(self):
        m = MitigationMeasure(measure_id="MED-001", name="EPIs",
                              measure_type="PRL_NO_EIA",
                              target_impact_ids=[])
        issues = m.validate()
        self.assertFalse(any("target_impact_ids vacío" in i for i in issues))

    def test_to_dict(self):
        m = _make_measure()
        d = m.to_dict()
        self.assertIn("measure_id", d)
        self.assertIn("measure_type", d)
        self.assertIn("target_impact_ids", d)
        self.assertIn("is_diagnostic", d)
        self.assertIn("is_prl_only", d)

    def test_to_dict_json_serializable(self):
        m = _make_measure()
        json.dumps(m.to_dict())

    def test_summary_returns_string(self):
        m = _make_measure()
        s = m.summary()
        self.assertIsInstance(s, str)
        self.assertIn("MED-001", s)

    def test_summary_diagnostic_flag(self):
        m = MitigationMeasure(
            measure_id="MED-001",
            name="Control polvo",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        s = m.summary()
        self.assertIn("DIAGNÓSTICA", s)

    def test_summary_prl_flag(self):
        m = MitigationMeasure(
            measure_id="MED-001",
            name="EPIs",
            measure_type="PRL_NO_EIA",
            is_prl_only=True,
        )
        s = m.summary()
        self.assertIn("PRL", s)


# ===========================================================================
# TestPVAProgram
# ===========================================================================

class TestPVAProgram(unittest.TestCase):

    def test_valid_creation(self):
        p = _make_pva()
        issues = p.validate()
        self.assertEqual(issues, [])

    def test_invalid_pva_id(self):
        p = PVAProgram(pva_id="PV-001", name="Test", factor_id="FI-001",
                       indicator="PM10", threshold="50", responsible="TE")
        issues = p.validate()
        self.assertTrue(any("pva_id inválido" in i for i in issues))

    def test_invalid_factor_id(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FR-001",
                       indicator="PM10", threshold="50", responsible="TE")
        issues = p.validate()
        self.assertTrue(any("factor_id inválido" in i for i in issues))

    def test_empty_indicator(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                       indicator="", threshold="50", responsible="TE")
        issues = p.validate()
        self.assertTrue(any("indicator no puede estar vacío" in i for i in issues))

    def test_whitespace_indicator(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                       indicator="   ", threshold="50", responsible="TE")
        issues = p.validate()
        self.assertTrue(any("indicator no puede estar vacío" in i for i in issues))

    def test_invalid_frequency(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                       indicator="PM10", threshold="50", frequency="RARA_VEZ",
                       responsible="TE")
        issues = p.validate()
        self.assertTrue(any("frequency inválida" in i for i in issues))

    def test_all_valid_frequencies(self):
        for freq in PVA_FREQUENCIES:
            p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                           indicator="PM10", threshold="50", frequency=freq,
                           responsible="TE")
            issues = p.validate()
            self.assertFalse(any("frequency inválida" in i for i in issues))

    def test_empty_threshold_warning(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                       indicator="PM10", threshold="", responsible="TE")
        issues = p.validate()
        self.assertTrue(any("threshold vacío" in i for i in issues))

    def test_empty_responsible_warning(self):
        p = PVAProgram(pva_id="PVA-001", name="Test", factor_id="FI-001",
                       indicator="PM10", threshold="50", responsible="")
        issues = p.validate()
        self.assertTrue(any("responsible vacío" in i for i in issues))

    def test_to_dict(self):
        p = _make_pva()
        d = p.to_dict()
        self.assertIn("pva_id", d)
        self.assertIn("factor_id", d)
        self.assertIn("indicator", d)
        self.assertIn("threshold", d)
        self.assertIn("frequency", d)
        self.assertIn("target_impact_ids", d)
        self.assertIn("target_measure_ids", d)

    def test_to_dict_json_serializable(self):
        p = _make_pva()
        json.dumps(p.to_dict())

    def test_summary_returns_string(self):
        p = _make_pva()
        s = p.summary()
        self.assertIsInstance(s, str)
        self.assertIn("PVA-001", s)
        self.assertIn("FI-006", s)

    def test_target_impact_ids_preserved(self):
        p = _make_pva()
        p.target_impact_ids = ["IMP-001", "IMP-002"]
        d = p.to_dict()
        self.assertEqual(d["target_impact_ids"], ["IMP-001", "IMP-002"])


# ===========================================================================
# TestPhase6Model
# ===========================================================================

class TestPhase6Model(unittest.TestCase):

    def test_empty_model(self):
        m = Phase6Model(expediente_id="TEST-001")
        issues = m.validate()
        self.assertEqual(issues, [])
        self.assertEqual(m.expediente_id, "TEST-001")
        self.assertEqual(len(m.actions), 0)
        self.assertEqual(len(m.impacts), 0)

    def test_model_with_data_valid(self):
        m = _make_full_model()
        issues = m.validate()
        self.assertEqual(issues, [])

    def test_duplicate_action_id(self):
        a1 = _make_action("AC-001")
        a2 = _make_action("AC-001")
        m = Phase6Model(expediente_id="TEST", actions=[a1, a2])
        issues = m.validate()
        self.assertTrue(any("action_id duplicado" in i for i in issues))

    def test_duplicate_impact_id(self):
        m = _make_full_model()
        imp2 = _make_impact()
        m.impacts.append(imp2)
        issues = m.validate()
        self.assertTrue(any("impact_id duplicado" in i for i in issues))

    def test_duplicate_receptor_id(self):
        r1 = _make_receptor()
        r2 = _make_receptor()
        m = Phase6Model(expediente_id="TEST", receptor_factors=[r1, r2])
        issues = m.validate()
        self.assertTrue(any("receptor_id duplicado" in i for i in issues))

    def test_impact_nonexistent_action_id(self):
        m = _make_full_model()
        bad_impact = EnvironmentalImpact(
            impact_id="IMP-099",
            action_id="AC-999",
            receptor_id="FR-001",
            name="Impacto sin acción",
        )
        m.impacts.append(bad_impact)
        issues = m.validate()
        self.assertTrue(any("AC-999" in i for i in issues))

    def test_impact_nonexistent_receptor_id(self):
        m = _make_full_model()
        bad_impact = EnvironmentalImpact(
            impact_id="IMP-099",
            action_id="AC-001",
            receptor_id="FR-099",
            name="Impacto sin receptor",
        )
        m.impacts.append(bad_impact)
        issues = m.validate()
        self.assertTrue(any("FR-099" in i for i in issues))

    def test_measure_nonexistent_target_impact(self):
        m = _make_full_model()
        bad_measure = MitigationMeasure(
            measure_id="MED-099",
            name="Medida sin impacto",
            measure_type="PREVENTIVA",
            target_impact_ids=["IMP-999"],
        )
        m.measures.append(bad_measure)
        issues = m.validate()
        self.assertTrue(any("IMP-999" in i for i in issues))

    def test_pva_nonexistent_target_impact(self):
        m = _make_full_model()
        bad_pva = PVAProgram(
            pva_id="PVA-099",
            name="PVA sin impacto",
            factor_id="FI-001",
            indicator="Test",
            threshold="X",
            responsible="TE",
            target_impact_ids=["IMP-999"],
        )
        m.pva_programs.append(bad_pva)
        issues = m.validate()
        self.assertTrue(any("IMP-999" in i for i in issues))

    def test_pva_nonexistent_target_measure(self):
        m = _make_full_model()
        bad_pva = PVAProgram(
            pva_id="PVA-099",
            name="PVA sin medida",
            factor_id="FI-001",
            indicator="Test",
            threshold="X",
            responsible="TE",
            target_measure_ids=["MED-999"],
        )
        m.pva_programs.append(bad_pva)
        issues = m.validate()
        self.assertTrue(any("MED-999" in i for i in issues))

    def test_impact_count_by_status_empty(self):
        m = Phase6Model(expediente_id="TEST")
        counts = m.impact_count_by_status()
        for status in IMPACT_STATUS:
            self.assertIn(status, counts)
        self.assertTrue(all(v == 0 for v in counts.values()))

    def test_impact_count_by_status_with_data(self):
        m = _make_full_model()
        # Add another impact with different status
        imp2 = EnvironmentalImpact(
            impact_id="IMP-002",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Impacto 2",
            status="VALORADO",
        )
        m.impacts.append(imp2)
        counts = m.impact_count_by_status()
        self.assertEqual(counts.get("PENDIENTE_DATOS", 0), 1)
        self.assertEqual(counts.get("VALORADO", 0), 1)

    def test_impacts_by_receptor(self):
        m = _make_full_model()
        by_rec = m.impacts_by_receptor()
        self.assertIn("FR-001", by_rec)
        self.assertIn("IMP-001", by_rec["FR-001"])

    def test_measures_by_impact(self):
        m = _make_full_model()
        by_imp = m.measures_by_impact()
        self.assertIn("IMP-001", by_imp)
        self.assertIn("MED-001", by_imp["IMP-001"])

    def test_pva_by_factor(self):
        m = _make_full_model()
        by_fac = m.pva_by_factor()
        self.assertIn("FI-001", by_fac)
        self.assertIn("PVA-001", by_fac["FI-001"])

    def test_to_dict_structure(self):
        m = _make_full_model()
        d = m.to_dict()
        self.assertIn("expediente_id", d)
        self.assertIn("actions", d)
        self.assertIn("receptor_factors", d)
        self.assertIn("impacts", d)
        self.assertIn("measures", d)
        self.assertIn("pva_programs", d)

    def test_to_dict_json_serializable(self):
        m = _make_full_model()
        json.dumps(m.to_dict())

    def test_summary_returns_string(self):
        m = _make_full_model()
        s = m.summary()
        self.assertIsInstance(s, str)
        self.assertIn("TEST-001", s)

    def test_severo_without_measures_warning_in_validate(self):
        action = _make_action()
        receptor = _make_receptor()
        imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Impacto severo sin medidas",
            significance_without_measures="SEVERO",
        )
        m = Phase6Model(
            expediente_id="TEST",
            actions=[action],
            receptor_factors=[receptor],
            impacts=[imp],
        )
        issues = m.validate()
        self.assertTrue(any("SEVERO" in i for i in issues))

    def test_no_compensation_rule_warning(self):
        """Medida que apunta a impacto POSITIVO y NEGATIVO genera aviso."""
        action = _make_action()
        receptor = _make_receptor()
        neg_imp = EnvironmentalImpact(
            impact_id="IMP-001",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Impacto negativo",
            nature="NEGATIVO",
        )
        pos_imp = EnvironmentalImpact(
            impact_id="IMP-002",
            action_id="AC-001",
            receptor_id="FR-001",
            name="Impacto positivo",
            nature="POSITIVO",
        )
        med = MitigationMeasure(
            measure_id="MED-001",
            name="Medida mixta",
            measure_type="PREVENTIVA",
            target_impact_ids=["IMP-001", "IMP-002"],
        )
        m = Phase6Model(
            expediente_id="TEST",
            actions=[action],
            receptor_factors=[receptor],
            impacts=[neg_imp, pos_imp],
            measures=[med],
        )
        issues = m.validate()
        self.assertTrue(any("compensación" in i.lower() for i in issues))


# ===========================================================================
# TestBuildReceptorFactorsFromInventory
# ===========================================================================

class TestBuildReceptorFactorsFromInventory(unittest.TestCase):

    def setUp(self):
        self.summary = build_inventory_summary("TEST", build_all_empty_factors())

    def test_creates_16_receptors(self):
        receptors = build_receptor_factors_from_inventory(self.summary)
        self.assertEqual(len(receptors), 16)

    def test_fr001_corresponds_to_fi001(self):
        receptors = build_receptor_factors_from_inventory(self.summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertEqual(fr001.inventory_factor_id, "FI-001")

    def test_fr016_corresponds_to_fi016(self):
        receptors = build_receptor_factors_from_inventory(self.summary)
        fr016 = next(r for r in receptors if r.receptor_id == "FR-016")
        self.assertEqual(fr016.inventory_factor_id, "FI-016")

    def test_copies_semaphore(self):
        factors = build_all_empty_factors()
        factors[0].inventory_semaphore = "AMARILLO"
        summary = build_inventory_summary("TEST", factors)
        receptors = build_receptor_factors_from_inventory(summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertEqual(fr001.inventory_semaphore, "AMARILLO")

    def test_copies_ready_from_inventory_false(self):
        receptors = build_receptor_factors_from_inventory(self.summary)
        for r in receptors:
            self.assertFalse(r.ready_from_inventory)

    def test_copies_ready_from_inventory_true(self):
        factors = build_all_empty_factors()
        factors[0].ready_for_impact_assessment = True
        factors[0].inventory_semaphore = "VERDE"
        summary = build_inventory_summary("TEST", factors)
        receptors = build_receptor_factors_from_inventory(summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertTrue(fr001.ready_from_inventory)

    def test_includes_critical_gaps_alta_pendiente(self):
        summary = _make_summary_with_gaps()
        receptors = build_receptor_factors_from_inventory(summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertIn("GAP-FI-001-001", fr001.critical_gaps)

    def test_cubierto_gap_not_included(self):
        factors = build_all_empty_factors()
        cubierto_gap = InventoryGap(
            gap_id="GAP-CUBIERTO",
            factor_id="FI-001",
            field="test",
            description="Gap resuelto",
            criticality="ALTA",
            resolution_mode="GABINETE",
            status="CUBIERTO",
        )
        factors[0].gaps = [cubierto_gap]
        summary = build_inventory_summary("TEST", factors)
        receptors = build_receptor_factors_from_inventory(summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertNotIn("GAP-CUBIERTO", fr001.critical_gaps)

    def test_media_gap_not_in_critical(self):
        factors = build_all_empty_factors()
        media_gap = InventoryGap(
            gap_id="GAP-MEDIA",
            factor_id="FI-001",
            field="test",
            description="Gap media",
            criticality="MEDIA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        )
        factors[0].gaps = [media_gap]
        summary = build_inventory_summary("TEST", factors)
        receptors = build_receptor_factors_from_inventory(summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertNotIn("GAP-MEDIA", fr001.critical_gaps)

    def test_not_ready_adds_note(self):
        receptors = build_receptor_factors_from_inventory(self.summary)
        fr001 = next(r for r in receptors if r.receptor_id == "FR-001")
        self.assertTrue(len(fr001.notes) > 0)
        self.assertTrue(any("no listo" in n for n in fr001.notes))

    def test_does_not_mutate_summary(self):
        original_factors_count = len(self.summary.factors)
        build_receptor_factors_from_inventory(self.summary)
        self.assertEqual(len(self.summary.factors), original_factors_count)

    def test_all_receptor_ids_valid_pattern(self):
        import re
        pattern = re.compile(r"^FR-\d{3,}$")
        receptors = build_receptor_factors_from_inventory(self.summary)
        for r in receptors:
            self.assertTrue(
                pattern.match(r.receptor_id),
                f"receptor_id inválido: {r.receptor_id!r}",
            )


# ===========================================================================
# TestBuildEmptyPhase6Model
# ===========================================================================

class TestBuildEmptyPhase6Model(unittest.TestCase):

    def test_without_inventory_no_receptors(self):
        model = build_empty_phase6_model("EIA-001")
        self.assertEqual(len(model.receptor_factors), 0)

    def test_with_inventory_16_receptors(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        self.assertEqual(len(model.receptor_factors), 16)

    def test_no_impacts_created(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        self.assertEqual(len(model.impacts), 0)

    def test_no_measures_created(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        self.assertEqual(len(model.measures), 0)

    def test_no_pva_created(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        self.assertEqual(len(model.pva_programs), 0)

    def test_expediente_id_set(self):
        model = build_empty_phase6_model("EIA-XYZ-001")
        self.assertEqual(model.expediente_id, "EIA-XYZ-001")

    def test_notes_added_with_inventory(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        self.assertTrue(len(model.notes) > 0)
        self.assertTrue(any("16" in n for n in model.notes))

    def test_notes_added_without_inventory(self):
        model = build_empty_phase6_model("EIA-001")
        self.assertTrue(len(model.notes) > 0)
        self.assertTrue(any("sin inventario" in n.lower() for n in model.notes))

    def test_no_actions_created(self):
        model = build_empty_phase6_model("EIA-001")
        self.assertEqual(len(model.actions), 0)

    def test_to_dict_json_serializable_empty(self):
        model = build_empty_phase6_model("EIA-001")
        json.dumps(model.to_dict())

    def test_to_dict_json_serializable_with_inventory(self):
        summary = build_inventory_summary("TEST", build_all_empty_factors())
        model = build_empty_phase6_model("EIA-001", inventory_summary=summary)
        json.dumps(model.to_dict())


# ===========================================================================
# TestConstantsIntegrity
# ===========================================================================

class TestConstantsIntegrity(unittest.TestCase):

    def test_action_types_non_empty(self):
        self.assertGreater(len(ACTION_TYPES), 0)

    def test_impact_natures_contains_expected(self):
        self.assertIn("NEGATIVO", IMPACT_NATURES)
        self.assertIn("POSITIVO", IMPACT_NATURES)
        self.assertIn("INDETERMINADO", IMPACT_NATURES)

    def test_impact_status_contains_expected(self):
        self.assertIn("VALORADO", IMPACT_STATUS)
        self.assertIn("PENDIENTE_DATOS", IMPACT_STATUS)

    def test_impact_significance_contains_expected(self):
        self.assertIn("COMPATIBLE", IMPACT_SIGNIFICANCE)
        self.assertIn("SEVERO", IMPACT_SIGNIFICANCE)
        self.assertIn("CRITICO", IMPACT_SIGNIFICANCE)
        self.assertIn("INDETERMINADO", IMPACT_SIGNIFICANCE)
        self.assertIn("NO_VALORADO", IMPACT_SIGNIFICANCE)

    def test_measure_types_contains_diagnostica(self):
        self.assertIn("DIAGNOSTICA", MEASURE_TYPES)

    def test_measure_types_contains_prl(self):
        self.assertIn("PRL_NO_EIA", MEASURE_TYPES)

    def test_pva_frequencies_non_empty(self):
        self.assertGreater(len(PVA_FREQUENCIES), 0)
        self.assertIn("SEMESTRAL", PVA_FREQUENCIES)

    def test_receptor_factor_names_count(self):
        self.assertEqual(len(RECEPTOR_FACTOR_NAMES), 16)

    def test_receptor_factor_ids_bidirectional(self):
        # Verificar que la correspondencia FR↔FI es biyectiva
        fi_values = list(RECEPTOR_FACTOR_IDS.values())
        self.assertEqual(len(set(fi_values)), 16, "Hay FI IDs duplicados en RECEPTOR_FACTOR_IDS")

    def test_conesa_attribute_names_complete(self):
        expected = {
            "intensidad", "extension", "momento", "persistencia",
            "reversibilidad", "sinergia", "acumulacion", "efecto",
            "periodicidad", "recuperabilidad",
        }
        self.assertEqual(set(CONESA_ATTRIBUTE_NAMES), expected)


if __name__ == "__main__":
    unittest.main()
