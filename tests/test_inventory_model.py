"""Tests para IV-00 — inventory_model.py

Sin IA. Sin red. Sin APIs. Fixtures sintéticos en memoria.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_model import (
    EVIDENCE_STATUS_VALUES,
    FACTOR_NAMES,
    FACTOR_TYPES,
    FIELD_MODES,
    GAP_CRITICALITIES,
    GAP_RESOLUTION_MODES,
    GAP_STATUSES,
    INVENTORY_SEMAPHORES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_all_empty_factors,
    build_empty_factor_inventory,
    build_inventory_summary,
    classify_semaphore_from_evidence,
    factor_type_for,
    validate_factor_id,
    validate_field_mode,
    validate_inventory_semaphore,
)


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------

def _gap(
    gap_id="GAP-IV-001",
    factor_id="FI-001",
    field="campo_test",
    description="Descripción de test del gap",
    criticality="MEDIA",
    resolution_mode="GABINETE",
    status="PENDIENTE",
) -> InventoryGap:
    return InventoryGap(
        gap_id=gap_id,
        factor_id=factor_id,
        field=field,
        description=description,
        criticality=criticality,
        resolution_mode=resolution_mode,
        status=status,
    )


def _factor(
    factor_id="FI-001",
    evidence_status="DECLARADO",
    field_mode="GABINETE_SUFICIENTE",
    inventory_semaphore="AMARILLO",
    ready=False,
    description="Descripción preoperacional del factor.",
    gaps=None,
) -> FactorInventory:
    return FactorInventory(
        factor_id=factor_id,
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=inventory_semaphore,
        ready_for_impact_assessment=ready,
        description=description,
        gaps=gaps or [],
    )


def _make_16_factors(ready: bool = False, semaphore: str = "VERDE") -> list[FactorInventory]:
    """Crea los 16 factores canónicos con semáforo y ready configurables."""
    factors = []
    for fid in sorted(FACTOR_NAMES.keys()):
        f = FactorInventory(
            factor_id=fid,
            evidence_status="CONFIRMADO_GABINETE",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore=semaphore,
            ready_for_impact_assessment=ready,
        )
        factors.append(f)
    return factors


# ===========================================================================
# 1. TestConstants
# ===========================================================================

class TestConstants(unittest.TestCase):

    def test_factor_names_has_16_entries(self):
        self.assertEqual(len(FACTOR_NAMES), 16)

    def test_fi001_is_clima(self):
        self.assertEqual(FACTOR_NAMES["FI-001"], "Clima")

    def test_fi016_is_riesgos_naturales(self):
        self.assertEqual(FACTOR_NAMES["FI-016"], "Riesgos naturales")

    def test_fi007_is_flora(self):
        self.assertEqual(FACTOR_NAMES["FI-007"], "Flora")

    def test_fi013_is_socioeconomia(self):
        self.assertEqual(FACTOR_NAMES["FI-013"], "Socioeconomía")

    def test_factor_types_keys(self):
        expected = {"fisico", "biologico", "perceptual", "socioeconomico", "integracion"}
        self.assertEqual(set(FACTOR_TYPES.keys()), expected)

    def test_fisico_contains_fi001(self):
        self.assertIn("FI-001", FACTOR_TYPES["fisico"])

    def test_biologico_contains_fi007(self):
        self.assertIn("FI-007", FACTOR_TYPES["biologico"])

    def test_socioeconomico_contains_fi013(self):
        self.assertIn("FI-013", FACTOR_TYPES["socioeconomico"])

    def test_factor_type_for_fisico(self):
        self.assertEqual(factor_type_for("FI-001"), "fisico")

    def test_factor_type_for_biologico(self):
        self.assertEqual(factor_type_for("FI-007"), "biologico")

    def test_factor_type_for_perceptual(self):
        self.assertEqual(factor_type_for("FI-011"), "perceptual")

    def test_factor_type_for_unknown(self):
        self.assertEqual(factor_type_for("FI-999"), "desconocido")

    def test_evidence_status_values_not_empty(self):
        self.assertGreater(len(EVIDENCE_STATUS_VALUES), 0)

    def test_evidence_status_contains_confirmado(self):
        self.assertIn("CONFIRMADO", EVIDENCE_STATUS_VALUES)

    def test_evidence_status_contains_asuncion_test(self):
        self.assertIn("ASUNCION_TEST", EVIDENCE_STATUS_VALUES)

    def test_all_factor_ids_sequential(self):
        ids = sorted(FACTOR_NAMES.keys())
        expected = [f"FI-{i:03d}" for i in range(1, 17)]
        self.assertEqual(ids, expected)


# ===========================================================================
# 2. TestInventoryGap
# ===========================================================================

class TestInventoryGap(unittest.TestCase):

    def test_creation_valid(self):
        g = _gap()
        self.assertEqual(g.gap_id, "GAP-IV-001")
        self.assertEqual(g.criticality, "MEDIA")
        self.assertEqual(g.status, "PENDIENTE")

    def test_to_dict_keys(self):
        d = _gap().to_dict()
        expected = {
            "gap_id", "factor_id", "field", "description",
            "criticality", "resolution_mode", "status",
        }
        self.assertEqual(set(d.keys()), expected)

    def test_to_dict_values(self):
        g = _gap(criticality="ALTA", status="CUBIERTO")
        d = g.to_dict()
        self.assertEqual(d["criticality"], "ALTA")
        self.assertEqual(d["status"], "CUBIERTO")

    def test_summary_not_empty(self):
        self.assertGreater(len(_gap().summary()), 0)

    def test_summary_contains_gap_id(self):
        self.assertIn("GAP-IV-001", _gap().summary())

    def test_summary_contains_criticality(self):
        self.assertIn("MEDIA", _gap(criticality="MEDIA").summary())

    def test_invalid_criticality_raises_value_error(self):
        with self.assertRaises(ValueError):
            _gap(criticality="EXTREMA")

    def test_none_criticality_raises_value_error(self):
        with self.assertRaises((ValueError, TypeError)):
            InventoryGap(
                gap_id="G1", factor_id="FI-001", field="f",
                description="d", criticality=None,
                resolution_mode="GABINETE",
            )

    def test_empty_criticality_raises_value_error(self):
        with self.assertRaises(ValueError):
            _gap(criticality="")

    def test_invalid_resolution_mode_raises_value_error(self):
        with self.assertRaises(ValueError):
            _gap(resolution_mode="ONLINE")

    def test_invalid_status_raises_value_error(self):
        with self.assertRaises(ValueError):
            _gap(status="CERRADO")

    def test_validate_invalid_factor_id(self):
        g = InventoryGap(
            gap_id="G1", factor_id="FI-999", field="f",
            description="d", criticality="ALTA",
            resolution_mode="CAMPO",
        )
        issues = g.validate()
        self.assertTrue(any("FI-999" in i for i in issues))

    def test_validate_valid_gap_no_issues(self):
        issues = _gap(factor_id="FI-006", criticality="ALTA").validate()
        self.assertEqual(issues, [])

    def test_default_status_is_pendiente(self):
        g = InventoryGap(
            gap_id="G1", factor_id="FI-001", field="f",
            description="d", criticality="BAJA",
            resolution_mode="GABINETE",
        )
        self.assertEqual(g.status, "PENDIENTE")


# ===========================================================================
# 3. TestFactorInventory
# ===========================================================================

class TestFactorInventory(unittest.TestCase):

    def test_factor_name_inferred_from_id(self):
        f = FactorInventory(factor_id="FI-001")
        self.assertEqual(f.factor_name, "Clima")

    def test_factor_type_inferred_from_id(self):
        f = FactorInventory(factor_id="FI-007")
        self.assertEqual(f.factor_type, "biologico")

    def test_explicit_factor_name_not_overwritten(self):
        f = FactorInventory(factor_id="FI-001", factor_name="Mi nombre")
        self.assertEqual(f.factor_name, "Mi nombre")

    def test_ready_for_impact_assessment_default_false(self):
        f = FactorInventory(factor_id="FI-001")
        self.assertFalse(f.ready_for_impact_assessment)

    def test_to_dict_returns_dict(self):
        d = _factor().to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_keys(self):
        d = _factor().to_dict()
        expected = {
            "factor_id", "factor_name", "factor_type", "description",
            "data_sources", "evidence_status", "field_mode",
            "field_mode_justification", "inventory_semaphore",
            "semaphore_justification", "gaps",
            "ready_for_impact_assessment", "warnings", "notes",
        }
        self.assertEqual(set(d.keys()), expected)

    def test_to_dict_gaps_serialized(self):
        g = _gap()
        f = _factor(gaps=[g])
        d = f.to_dict()
        self.assertEqual(len(d["gaps"]), 1)
        self.assertEqual(d["gaps"][0]["gap_id"], "GAP-IV-001")

    def test_summary_not_empty(self):
        self.assertGreater(len(_factor().summary()), 0)

    def test_summary_contains_factor_id(self):
        self.assertIn("FI-001", _factor("FI-001").summary())

    def test_gap_count_by_criticality_no_gaps(self):
        counts = _factor().gap_count_by_criticality()
        self.assertEqual(counts, {"ALTA": 0, "MEDIA": 0, "BAJA": 0})

    def test_gap_count_by_criticality_with_gaps(self):
        g1 = _gap(gap_id="G1", criticality="ALTA")
        g2 = _gap(gap_id="G2", criticality="ALTA")
        g3 = _gap(gap_id="G3", criticality="MEDIA")
        f = _factor(gaps=[g1, g2, g3])
        counts = f.gap_count_by_criticality()
        self.assertEqual(counts["ALTA"], 2)
        self.assertEqual(counts["MEDIA"], 1)

    def test_gap_count_excludes_covered(self):
        g = _gap(gap_id="G1", criticality="ALTA", status="CUBIERTO")
        f = _factor(gaps=[g])
        counts = f.gap_count_by_criticality()
        self.assertEqual(counts["ALTA"], 0)

    def test_has_critical_gaps_false_when_no_gaps(self):
        self.assertFalse(_factor().has_critical_gaps())

    def test_has_critical_gaps_true_with_alta_pendiente(self):
        g = _gap(criticality="ALTA", status="PENDIENTE")
        self.assertTrue(_factor(gaps=[g]).has_critical_gaps())

    def test_has_critical_gaps_false_when_covered(self):
        g = _gap(criticality="ALTA", status="CUBIERTO")
        self.assertFalse(_factor(gaps=[g]).has_critical_gaps())

    def test_needs_field_work_false_for_gabinete(self):
        self.assertFalse(_factor(field_mode="GABINETE_SUFICIENTE").needs_field_work())

    def test_needs_field_work_true_for_campo_recomendado(self):
        self.assertTrue(_factor(field_mode="CAMPO_RECOMENDADO").needs_field_work())

    def test_needs_field_work_true_for_campo_necesario(self):
        self.assertTrue(_factor(field_mode="CAMPO_NECESARIO").needs_field_work())

    def test_validate_ready_true_with_rojo_adds_warning(self):
        f = _factor(
            inventory_semaphore="ROJO",
            ready=True,
        )
        issues = f.validate()
        self.assertTrue(any("AVISO FUERTE" in i for i in issues))

    def test_validate_ready_true_with_no_consta_adds_warning(self):
        f = _factor(
            inventory_semaphore="NO_CONSTA",
            ready=True,
        )
        issues = f.validate()
        self.assertTrue(any("AVISO FUERTE" in i for i in issues))

    def test_validate_prudencia_no_existe_without_gabinete(self):
        f = _factor(
            field_mode="CAMPO_RECOMENDADO",
            description="En la zona no existe vegetación relevante.",
        )
        issues = f.validate()
        self.assertTrue(any("PRUDENCIA" in i for i in issues))

    def test_validate_prudencia_not_triggered_with_gabinete_suficiente(self):
        f = _factor(
            field_mode="GABINETE_SUFICIENTE",
            description="No existe vegetación relevante en las fuentes consultadas.",
        )
        issues = f.validate()
        prudencia_issues = [i for i in issues if "PRUDENCIA" in i]
        self.assertEqual(len(prudencia_issues), 0)

    def test_validate_prudencia_no_hay(self):
        f = _factor(
            field_mode="NO_CONSTA",
            description="No hay fauna catalogada en el ámbito.",
        )
        issues = f.validate()
        self.assertTrue(any("PRUDENCIA" in i for i in issues))

    def test_unknown_factor_id_adds_warning(self):
        f = FactorInventory(factor_id="FI-999")
        self.assertTrue(len(f.warnings) > 0)

    def test_valid_factor_id_no_warning(self):
        f = FactorInventory(factor_id="FI-001")
        warnings_about_id = [w for w in f.warnings if "factor_id" in w]
        self.assertEqual(len(warnings_about_id), 0)


# ===========================================================================
# 4. TestInventorySummary
# ===========================================================================

class TestInventorySummary(unittest.TestCase):

    def _summary_16_ready(self) -> InventorySummary:
        return build_inventory_summary(
            "EXP-TEST", _make_16_factors(ready=True, semaphore="VERDE")
        )

    def _summary_16_not_ready(self) -> InventorySummary:
        return build_inventory_summary(
            "EXP-TEST", _make_16_factors(ready=False, semaphore="VERDE")
        )

    def test_total_factors(self):
        s = build_inventory_summary("X", _make_16_factors())
        self.assertEqual(s.total_factors, 16)

    def test_ready_count_zero_when_none_ready(self):
        s = self._summary_16_not_ready()
        self.assertEqual(s.ready_count, 0)

    def test_ready_count_16_when_all_ready(self):
        s = self._summary_16_ready()
        self.assertEqual(s.ready_count, 16)

    def test_campo_necesario_count_zero(self):
        s = build_inventory_summary("X", _make_16_factors())
        self.assertEqual(s.campo_necesario_count, 0)

    def test_campo_necesario_count_positive(self):
        factors = _make_16_factors()
        factors[0].field_mode = "CAMPO_NECESARIO"
        s = build_inventory_summary("X", factors)
        self.assertEqual(s.campo_necesario_count, 1)

    def test_rojo_count_zero(self):
        s = self._summary_16_ready()
        self.assertEqual(s.rojo_count, 0)

    def test_rojo_count_positive(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        factors[0].inventory_semaphore = "ROJO"
        s = build_inventory_summary("X", factors)
        self.assertEqual(s.rojo_count, 1)

    def test_has_critical_gaps_false_when_none(self):
        s = self._summary_16_ready()
        self.assertFalse(s.has_critical_gaps)

    def test_has_critical_gaps_true(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        g = _gap(factor_id="FI-001", criticality="ALTA")
        factors[0].gaps = [g]
        s = build_inventory_summary("X", factors)
        self.assertTrue(s.has_critical_gaps)

    def test_all_ready_for_phase6_false_if_less_than_16(self):
        s = build_inventory_summary("X", _make_16_factors(ready=True)[:15])
        self.assertFalse(s.all_ready_for_phase6)

    def test_all_ready_for_phase6_false_if_not_all_ready(self):
        s = self._summary_16_not_ready()
        self.assertFalse(s.all_ready_for_phase6)

    def test_all_ready_for_phase6_false_if_rojo(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        factors[0].inventory_semaphore = "ROJO"
        s = build_inventory_summary("X", factors)
        self.assertFalse(s.all_ready_for_phase6)

    def test_all_ready_for_phase6_false_if_no_consta(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        factors[0].inventory_semaphore = "NO_CONSTA"
        s = build_inventory_summary("X", factors)
        self.assertFalse(s.all_ready_for_phase6)

    def test_all_ready_for_phase6_false_if_critical_gap(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        factors[0].gaps = [_gap(criticality="ALTA")]
        s = build_inventory_summary("X", factors)
        self.assertFalse(s.all_ready_for_phase6)

    def test_all_ready_for_phase6_true(self):
        s = self._summary_16_ready()
        self.assertTrue(s.all_ready_for_phase6)

    def test_factors_by_semaphore_returns_dict(self):
        s = self._summary_16_ready()
        d = s.factors_by_semaphore()
        self.assertIsInstance(d, dict)
        self.assertIn("VERDE", d)

    def test_factors_by_semaphore_verde_has_16(self):
        s = self._summary_16_ready()
        d = s.factors_by_semaphore()
        self.assertEqual(len(d["VERDE"]), 16)

    def test_factors_needing_field_work_empty(self):
        s = self._summary_16_ready()
        self.assertEqual(s.factors_needing_field_work(), [])

    def test_factors_needing_field_work_nonempty(self):
        factors = _make_16_factors(ready=True)
        factors[0].field_mode = "CAMPO_NECESARIO"
        s = build_inventory_summary("X", factors)
        self.assertIn("FI-001", s.factors_needing_field_work())

    def test_missing_factor_ids_empty_when_all_present(self):
        s = build_inventory_summary("X", _make_16_factors())
        self.assertEqual(s.missing_factor_ids(), [])

    def test_missing_factor_ids_lists_missing(self):
        factors = _make_16_factors()[:10]
        s = build_inventory_summary("X", factors)
        missing = s.missing_factor_ids()
        self.assertEqual(len(missing), 6)

    def test_to_dict_has_expected_keys(self):
        d = self._summary_16_ready().to_dict()
        for k in ("expediente_id", "factors", "total_factors",
                  "ready_count", "all_ready_for_phase6"):
            self.assertIn(k, d)

    def test_summary_not_empty(self):
        s = self._summary_16_ready()
        self.assertGreater(len(s.summary()), 30)

    def test_build_inventory_summary_warning_when_incomplete(self):
        factors = _make_16_factors()[:5]
        s = build_inventory_summary("X", factors)
        self.assertGreater(len(s.warnings), 0)

    def test_build_inventory_summary_no_warning_when_complete(self):
        s = build_inventory_summary("X", _make_16_factors())
        self.assertEqual(len(s.warnings), 0)


# ===========================================================================
# 5. TestValidators
# ===========================================================================

class TestValidators(unittest.TestCase):

    def test_validate_factor_id_fi001_ok(self):
        self.assertTrue(validate_factor_id("FI-001"))

    def test_validate_factor_id_fi016_ok(self):
        self.assertTrue(validate_factor_id("FI-016"))

    def test_validate_factor_id_fi01_ko(self):
        self.assertFalse(validate_factor_id("FI-01"))

    def test_validate_factor_id_fi017_ko(self):
        self.assertFalse(validate_factor_id("FI-017"))

    def test_validate_factor_id_fi000_ko(self):
        self.assertFalse(validate_factor_id("FI-000"))

    def test_validate_factor_id_empty_ko(self):
        self.assertFalse(validate_factor_id(""))

    def test_validate_inventory_semaphore_verde_ok(self):
        self.assertTrue(validate_inventory_semaphore("VERDE"))

    def test_validate_inventory_semaphore_verde_amarillo_ok(self):
        self.assertTrue(validate_inventory_semaphore("VERDE_AMARILLO"))

    def test_validate_inventory_semaphore_rojo_ok(self):
        self.assertTrue(validate_inventory_semaphore("ROJO"))

    def test_validate_inventory_semaphore_invalid_ko(self):
        self.assertFalse(validate_inventory_semaphore("MODERADO"))

    def test_validate_field_mode_gabinete_ok(self):
        self.assertTrue(validate_field_mode("GABINETE_SUFICIENTE"))

    def test_validate_field_mode_campo_necesario_ok(self):
        self.assertTrue(validate_field_mode("CAMPO_NECESARIO"))

    def test_validate_field_mode_invalid_ko(self):
        self.assertFalse(validate_field_mode("CAMPO_OBLIGATORIO"))

    def test_validate_field_mode_no_consta_ok(self):
        self.assertTrue(validate_field_mode("NO_CONSTA"))


# ===========================================================================
# 6. TestClassifySemaphore
# ===========================================================================

class TestClassifySemaphore(unittest.TestCase):

    def test_confirmado_no_gaps_verde(self):
        self.assertEqual(classify_semaphore_from_evidence("CONFIRMADO", []), "VERDE")

    def test_confirmado_gabinete_no_gaps_verde(self):
        self.assertEqual(classify_semaphore_from_evidence("CONFIRMADO_GABINETE", []), "VERDE")

    def test_confirmado_campo_no_gaps_verde(self):
        self.assertEqual(classify_semaphore_from_evidence("CONFIRMADO_CAMPO", []), "VERDE")

    def test_declarado_no_gaps_amarillo(self):
        self.assertEqual(classify_semaphore_from_evidence("DECLARADO", []), "AMARILLO")

    def test_inferido_no_gaps_verde_amarillo(self):
        self.assertEqual(classify_semaphore_from_evidence("INFERIDO", []), "VERDE_AMARILLO")

    def test_inferido_tecnico_no_gaps_verde_amarillo(self):
        self.assertEqual(classify_semaphore_from_evidence("INFERIDO_TECNICO", []), "VERDE_AMARILLO")

    def test_estimado_no_gaps_amarillo(self):
        self.assertEqual(classify_semaphore_from_evidence("ESTIMADO", []), "AMARILLO")

    def test_estimado_gap_media_rojo_amarillo(self):
        g = _gap(criticality="MEDIA")
        self.assertEqual(classify_semaphore_from_evidence("ESTIMADO", [g]), "ROJO_AMARILLO")

    def test_estimado_gap_alta_rojo(self):
        g = _gap(criticality="ALTA")
        self.assertEqual(classify_semaphore_from_evidence("ESTIMADO", [g]), "ROJO")

    def test_pendiente_gap_alta_rojo(self):
        g = _gap(criticality="ALTA")
        self.assertEqual(classify_semaphore_from_evidence("PENDIENTE", [g]), "ROJO")

    def test_pendiente_no_gaps_no_consta(self):
        self.assertEqual(classify_semaphore_from_evidence("PENDIENTE", []), "NO_CONSTA")

    def test_no_consta_no_consta(self):
        self.assertEqual(classify_semaphore_from_evidence("NO_CONSTA", []), "NO_CONSTA")

    def test_estado_desconocido_no_consta(self):
        self.assertEqual(classify_semaphore_from_evidence("INVENTADO", []), "NO_CONSTA")

    def test_declarado_gap_alta_rojo_amarillo(self):
        g = _gap(criticality="ALTA")
        self.assertEqual(classify_semaphore_from_evidence("DECLARADO", [g]), "ROJO_AMARILLO")

    def test_confirmado_with_gaps_verde_amarillo(self):
        g = _gap(criticality="ALTA")
        self.assertEqual(classify_semaphore_from_evidence("CONFIRMADO", [g]), "VERDE_AMARILLO")

    def test_covered_gaps_not_counted(self):
        g = _gap(criticality="ALTA", status="CUBIERTO")
        # Gap cubierto no cuenta → CONFIRMADO sin activos → VERDE
        self.assertEqual(classify_semaphore_from_evidence("CONFIRMADO", [g]), "VERDE")

    def test_asuncion_test_no_gaps_rojo_amarillo(self):
        result = classify_semaphore_from_evidence("ASUNCION_TEST", [])
        self.assertEqual(result, "ROJO_AMARILLO")

    def test_provisional_gap_alta_rojo(self):
        g = _gap(criticality="ALTA")
        self.assertEqual(classify_semaphore_from_evidence("PROVISIONAL", [g]), "ROJO")

    def test_error_state_no_consta(self):
        self.assertEqual(classify_semaphore_from_evidence("ERROR", []), "NO_CONSTA")


# ===========================================================================
# 7. TestBuildHelpers
# ===========================================================================

class TestBuildHelpers(unittest.TestCase):

    def test_build_empty_fi001(self):
        f = build_empty_factor_inventory("FI-001")
        self.assertIsInstance(f, FactorInventory)
        self.assertEqual(f.factor_id, "FI-001")
        self.assertEqual(f.inventory_semaphore, "NO_CONSTA")
        self.assertEqual(f.field_mode, "NO_CONSTA")
        self.assertEqual(f.evidence_status, "PENDIENTE")
        self.assertFalse(f.ready_for_impact_assessment)

    def test_build_empty_fi016(self):
        f = build_empty_factor_inventory("FI-016")
        self.assertEqual(f.factor_id, "FI-016")
        self.assertEqual(f.factor_name, "Riesgos naturales")

    def test_build_empty_fi001_name_inferred(self):
        f = build_empty_factor_inventory("FI-001")
        self.assertEqual(f.factor_name, "Clima")

    def test_build_empty_invalid_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_empty_factor_inventory("FI-017")

    def test_build_empty_fi000_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_empty_factor_inventory("FI-000")

    def test_build_all_empty_factors_returns_16(self):
        factors = build_all_empty_factors()
        self.assertEqual(len(factors), 16)

    def test_build_all_empty_factors_ids_sequential(self):
        factors = build_all_empty_factors()
        ids = [f.factor_id for f in factors]
        expected = [f"FI-{i:03d}" for i in range(1, 17)]
        self.assertEqual(ids, expected)

    def test_build_all_empty_factors_all_no_consta(self):
        factors = build_all_empty_factors()
        for f in factors:
            self.assertEqual(f.inventory_semaphore, "NO_CONSTA")

    def test_build_inventory_summary_returns_summary(self):
        s = build_inventory_summary("EXP-001", _make_16_factors())
        self.assertIsInstance(s, InventorySummary)

    def test_build_inventory_summary_expediente_id(self):
        s = build_inventory_summary("EXP-NAVE-222", _make_16_factors())
        self.assertEqual(s.expediente_id, "EXP-NAVE-222")

    def test_build_inventory_summary_incomplete_adds_warning(self):
        s = build_inventory_summary("X", _make_16_factors()[:3])
        self.assertGreater(len(s.warnings), 0)


# ===========================================================================
# 8. TestFixtureLanzarote
# ===========================================================================

class TestFixtureLanzarote(unittest.TestCase):
    """Fixture realista basado en el expediente piloto NAVE-222 / Lanzarote."""

    def _fi001_clima(self) -> FactorInventory:
        """FI-001 Clima — caracterizado con datos del pipeline CL-06."""
        return FactorInventory(
            factor_id="FI-001",
            evidence_status="CONFIRMADO_GABINETE",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="VERDE",
            semaphore_justification=(
                "Normales climatológicas 1991-2020 de Lanzarote Aeropuerto (C029O) "
                "procesadas por CL-06. Köppen BWh. Martonne < 5 (árido). "
                "Climograma generado. Dato suficiente para EIA simplificada."
            ),
            data_sources=[
                "CL-06 phase4 climate pipeline",
                "Lanzarote Aeropuerto C029O (1991-2020)",
            ],
            description=(
                "Clima árido subtropical (BWh según Köppen-Geiger). "
                "Temperatura media anual ~21 °C. Precipitación anual ~131 mm. "
                "Índice de Martonne < 5 (árido). Sin meses fríos. "
                "Vientos alisios dominantes. Fuente: normales AEMET 1991-2020."
            ),
            ready_for_impact_assessment=True,
        )

    def test_fi001_factor_id(self):
        f = self._fi001_clima()
        self.assertEqual(f.factor_id, "FI-001")

    def test_fi001_factor_name_inferred(self):
        f = self._fi001_clima()
        self.assertEqual(f.factor_name, "Clima")

    def test_fi001_evidence_status(self):
        f = self._fi001_clima()
        self.assertIn(f.evidence_status, EVIDENCE_STATUS_VALUES)

    def test_fi001_field_mode_gabinete(self):
        f = self._fi001_clima()
        self.assertEqual(f.field_mode, "GABINETE_SUFICIENTE")

    def test_fi001_semaphore_verde(self):
        f = self._fi001_clima()
        self.assertEqual(f.inventory_semaphore, "VERDE")

    def test_fi001_has_data_sources(self):
        f = self._fi001_clima()
        self.assertIn("CL-06 phase4 climate pipeline", f.data_sources)

    def test_fi001_ready_for_impact_assessment(self):
        f = self._fi001_clima()
        self.assertTrue(f.ready_for_impact_assessment)

    def test_fi001_no_critical_gaps(self):
        f = self._fi001_clima()
        self.assertFalse(f.has_critical_gaps())

    def test_fi001_validate_no_severe_issues(self):
        f = self._fi001_clima()
        issues = f.validate()
        severe = [i for i in issues if "AVISO FUERTE" in i or "PRUDENCIA" in i]
        self.assertEqual(len(severe), 0)

    def test_fi001_to_dict_json_serializable(self):
        import json
        d = self._fi001_clima().to_dict()
        s = json.dumps(d, ensure_ascii=False)
        self.assertGreater(len(s), 10)

    def test_summary_16_not_all_ready_not_ready_for_phase6(self):
        factors = _make_16_factors(ready=False)
        s = build_inventory_summary("expediente-EIA-NAVE-222", factors)
        self.assertFalse(s.all_ready_for_phase6)

    def test_summary_16_all_ready_for_phase6(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        s = build_inventory_summary("expediente-EIA-NAVE-222", factors)
        self.assertTrue(s.all_ready_for_phase6)

    def test_summary_contains_expediente_id(self):
        s = build_inventory_summary("expediente-EIA-NAVE-222", _make_16_factors())
        self.assertIn("expediente-EIA-NAVE-222", s.summary())

    def test_summary_to_dict_round_trip(self):
        import json
        s = build_inventory_summary("expediente-EIA-NAVE-222",
                                    _make_16_factors(ready=True, semaphore="VERDE"))
        d = s.to_dict()
        raw = json.dumps(d, ensure_ascii=False)
        restored = json.loads(raw)
        self.assertTrue(restored["all_ready_for_phase6"])
        self.assertEqual(restored["expediente_id"], "expediente-EIA-NAVE-222")


if __name__ == "__main__":
    unittest.main()
