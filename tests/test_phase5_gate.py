"""
Tests para phase5_gate (F5-01).
Gate de cierre de Fase 5 / Inventario ambiental offline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_all_empty_factors,
)
from eia_agent.core.phase5_gate import (
    Phase5GateIssue,
    Phase5GateResult,
    build_phase5_gate_markdown,
    evaluate_phase5_gate,
    evaluate_phase5_gate_from_inventory_json,
    write_phase5_gate_outputs,
)


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------

def _make_ready_factor(factor_id: str) -> FactorInventory:
    """Factor completamente listo para Fase 6."""
    return FactorInventory(
        factor_id=factor_id,
        description="Factor caracterizado con suficiente información de gabinete.",
        data_sources=["Documentación del promotor", "Cartografía oficial"],
        evidence_status="ESTIMADO",
        field_mode="GABINETE_SUFICIENTE",
        inventory_semaphore="AMARILLO",
        ready_for_impact_assessment=True,
    )


def _make_pending_factor(factor_id: str) -> FactorInventory:
    """Factor no listo, sin caracterizar."""
    gap = InventoryGap(
        gap_id=f"GAP-{factor_id}-001",
        factor_id=factor_id,
        field="prospección",
        description="Prospección pendiente.",
        criticality="MEDIA",
        resolution_mode="CAMPO",
        status="PENDIENTE",
    )
    return FactorInventory(
        factor_id=factor_id,
        description="Factor pendiente de caracterización.",
        data_sources=["Documentación del promotor"],
        evidence_status="PENDIENTE",
        field_mode="NO_CONSTA",
        inventory_semaphore="NO_CONSTA",
        ready_for_impact_assessment=False,
        gaps=[gap],
    )


def _make_16_ready_factors() -> list[FactorInventory]:
    return [_make_ready_factor(fid) for fid in sorted(FACTOR_NAMES.keys())]


def _make_offline_summary() -> InventorySummary:
    """Resumen realista de inventario offline (ningún factor listo, gaps ALTA)."""
    factors = []
    for fid in sorted(FACTOR_NAMES.keys()):
        gap = InventoryGap(
            gap_id=f"GAP-{fid}-001",
            factor_id=fid,
            field="caracterización",
            description=f"Datos insuficientes para {fid} en modo gabinete.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="PENDIENTE",
        )
        f = FactorInventory(
            factor_id=fid,
            description=f"Factor {fid} pendiente de prospección de campo.",
            data_sources=["Documentación promotor"],
            evidence_status="PENDIENTE",
            field_mode="CAMPO_RECOMENDADO",
            inventory_semaphore="NO_CONSTA",
            ready_for_impact_assessment=False,
            gaps=[gap],
        )
        factors.append(f)
    return InventorySummary(
        expediente_id="EIA-TEST-F5",
        factors=factors,
    )


# ---------------------------------------------------------------------------
# TestPhase5GateIssue
# ---------------------------------------------------------------------------

class TestPhase5GateIssue(unittest.TestCase):
    def test_to_dict_keys(self):
        iss = Phase5GateIssue(
            severity="ERROR",
            code="TEST_CODE",
            message="mensaje",
            recommendation="acción",
            factor_id="FI-001",
        )
        d = iss.to_dict()
        assert d["severity"] == "ERROR"
        assert d["code"] == "TEST_CODE"
        assert d["factor_id"] == "FI-001"
        assert d["message"] == "mensaje"
        assert d["recommendation"] == "acción"

    def test_to_dict_without_factor(self):
        iss = Phase5GateIssue(severity="WARNING", code="W1", message="aviso")
        d = iss.to_dict()
        assert d["factor_id"] is None

    def test_summary_with_factor(self):
        iss = Phase5GateIssue(
            severity="ERROR", code="ERR", message="problema", factor_id="FI-005"
        )
        s = iss.summary()
        assert "ERROR" in s
        assert "ERR" in s
        assert "FI-005" in s
        assert "problema" in s

    def test_summary_without_factor(self):
        iss = Phase5GateIssue(severity="INFO", code="INFO1", message="nota")
        s = iss.summary()
        assert "INFO" in s
        assert "INFO1" in s

    def test_invalid_severity_raises(self):
        with self.assertRaisesRegex(ValueError, "severity"):
            Phase5GateIssue(severity="CRITICAL", code="X", message="x")

    def test_valid_severities(self):
        for sev in ("ERROR", "WARNING", "INFO"):
            iss = Phase5GateIssue(severity=sev, code="C", message="m")
            assert iss.severity == sev


# ---------------------------------------------------------------------------
# TestPhase5GateResult
# ---------------------------------------------------------------------------

class TestPhase5GateResult(unittest.TestCase):
    def _make_result(self, issues=None, decision="APTO_FASE6_CON_CAUTELAS"):
        return Phase5GateResult(
            expediente_id="EIA-TEST",
            decision=decision,
            total_factors=16,
            ready_count=0,
            issues=issues or [],
        )

    def test_error_count(self):
        r = self._make_result(issues=[
            Phase5GateIssue(severity="ERROR", code="E1", message="e"),
            Phase5GateIssue(severity="WARNING", code="W1", message="w"),
        ])
        assert r.error_count() == 1

    def test_warning_count(self):
        r = self._make_result(issues=[
            Phase5GateIssue(severity="WARNING", code="W1", message="w"),
            Phase5GateIssue(severity="WARNING", code="W2", message="w2"),
        ])
        assert r.warning_count() == 2

    def test_info_count(self):
        r = self._make_result(issues=[
            Phase5GateIssue(severity="INFO", code="I1", message="i"),
        ])
        assert r.info_count() == 1

    def test_is_blocked_no_apto(self):
        r = self._make_result(decision="NO_APTO_FASE6")
        assert r.is_blocked() is True

    def test_is_blocked_apto(self):
        r = self._make_result(decision="APTO_FASE6")
        assert r.is_blocked() is False

    def test_is_blocked_con_cautelas(self):
        r = self._make_result(decision="APTO_FASE6_CON_CAUTELAS")
        assert r.is_blocked() is False

    def test_administrative_ready_always_false(self):
        r = Phase5GateResult(
            expediente_id="EIA-X",
            decision="APTO_FASE6",
            total_factors=16,
            ready_count=16,
            administrative_ready=False,
        )
        assert r.administrative_ready is False

    def test_to_dict_keys(self):
        r = self._make_result()
        d = r.to_dict()
        for key in ("expediente_id", "decision", "total_factors", "ready_count",
                    "not_ready_factors", "critical_gaps", "red_or_no_consta_factors",
                    "issues", "administrative_ready", "error_count", "warning_count",
                    "info_count", "is_blocked", "warnings", "notes"):
            assert key in d

    def test_to_dict_json_serializable(self):
        r = self._make_result(issues=[
            Phase5GateIssue(severity="ERROR", code="E", message="e", factor_id="FI-001")
        ])
        raw = json.dumps(r.to_dict(), ensure_ascii=False)
        d = json.loads(raw)
        assert d["decision"] == "APTO_FASE6_CON_CAUTELAS"

    def test_summary_contains_key_fields(self):
        r = self._make_result(decision="NO_APTO_FASE6", issues=[
            Phase5GateIssue(severity="ERROR", code="MISSING_FACTOR", message="FI-005 ausente")
        ])
        s = r.summary()
        assert "EIA-TEST" in s
        assert "NO APTO" in s
        assert "MISSING_FACTOR" in s

    def test_summary_contains_admin_note(self):
        r = self._make_result()
        s = r.summary()
        assert "Admin" in s or "tramit" in s.lower() or "independiente" in s.lower()


# ---------------------------------------------------------------------------
# TestEvaluatePhase5Gate — structure checks
# ---------------------------------------------------------------------------

class TestEvaluatePhase5GateStructure(unittest.TestCase):
    def test_all_16_ready_apto(self):
        summary = InventorySummary(
            expediente_id="EIA-OK",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6"
        assert result.error_count() == 0
        assert result.is_blocked() is False
        assert result.administrative_ready is False

    def test_all_16_ready_no_errors(self):
        summary = InventorySummary(
            expediente_id="EIA-OK",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        assert result.error_count() == 0

    def test_missing_factor_no_apto(self):
        factors = _make_16_ready_factors()
        factors = [f for f in factors if f.factor_id != "FI-005"]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "MISSING_FACTOR" in codes or "WRONG_FACTOR_COUNT" in codes

    def test_duplicate_factor_no_apto(self):
        factors = _make_16_ready_factors()
        factors.append(_make_ready_factor("FI-001"))  # duplicado
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "DUPLICATE_FACTOR" in codes or "WRONG_FACTOR_COUNT" in codes

    def test_wrong_count_no_apto(self):
        factors = _make_16_ready_factors()[:10]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "WRONG_FACTOR_COUNT" in codes

    def test_invalid_factor_id_no_apto(self):
        factors = _make_16_ready_factors()
        # Reemplazar FI-001 con un ID inválido
        bad = FactorInventory(
            factor_id="FI-999",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
        )
        factors[0] = bad
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "INVALID_FACTOR_ID" in codes or "MISSING_FACTOR" in codes


# ---------------------------------------------------------------------------
# TestEvaluatePhase5Gate — factor-level checks
# ---------------------------------------------------------------------------

class TestEvaluatePhase5GateFactorLevel(unittest.TestCase):
    def test_ready_with_rojo_semaphore_error(self):
        factors = _make_16_ready_factors()
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="ROJO",
            ready_for_impact_assessment=True,
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "READY_WITH_BLOCKING_SEMAPHORE" in codes

    def test_ready_with_no_consta_semaphore_error(self):
        factors = _make_16_ready_factors()
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="NO_CONSTA",
            ready_for_impact_assessment=True,
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "READY_WITH_BLOCKING_SEMAPHORE" in codes

    def test_ready_with_alta_gap_pending_error(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-001-001",
            factor_id="FI-001",
            field="prospección",
            description="Gap ALTA pendiente.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="PENDIENTE",
        )
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"
        codes = {i.code for i in result.issues}
        assert "READY_WITH_ALTA_GAP" in codes

    def test_ready_with_alta_gap_cubierto_no_error(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-001-001",
            factor_id="FI-001",
            field="prospección",
            description="Gap ALTA cubierto.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="CUBIERTO",  # cubierto, no bloquea
        )
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        # Gap cubierto no debe generar READY_WITH_ALTA_GAP
        codes = {i.code for i in result.issues}
        assert "READY_WITH_ALTA_GAP" not in codes

    def test_empty_description_warning(self):
        factors = _make_16_ready_factors()
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="",  # vacío
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "EMPTY_DESCRIPTION" in codes
        # Es WARNING, no ERROR → no bloquea
        assert result.decision in ("APTO_FASE6", "APTO_FASE6_CON_CAUTELAS")

    def test_empty_data_sources_warning(self):
        factors = _make_16_ready_factors()
        factors[0] = FactorInventory(
            factor_id="FI-001",
            description="desc",
            data_sources=[],  # vacío
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "NO_DATA_SOURCES" in codes

    def test_invalid_evidence_status_error(self):
        factors = _make_16_ready_factors()
        factors[0] = FactorInventory.__new__(FactorInventory)
        factors[0].__dict__.update({
            "factor_id": "FI-001",
            "factor_name": "Clima",
            "factor_type": "fisico",
            "description": "desc",
            "data_sources": ["src"],
            "evidence_status": "INVALID_STATUS",
            "field_mode": "GABINETE_SUFICIENTE",
            "field_mode_justification": "",
            "inventory_semaphore": "AMARILLO",
            "semaphore_justification": "",
            "gaps": [],
            "ready_for_impact_assessment": True,
            "warnings": [],
            "notes": [],
        })
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "INVALID_EVIDENCE_STATUS" in codes

    def test_invalid_field_mode_error(self):
        factors = _make_16_ready_factors()
        f = factors[0]
        object.__setattr__(f, "field_mode", "CAMPO_OBLIGATORIO")  # inválido
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "INVALID_FIELD_MODE" in codes

    def test_invalid_semaphore_error(self):
        factors = _make_16_ready_factors()
        f = factors[0]
        object.__setattr__(f, "inventory_semaphore", "NARANJA")  # inválido
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "INVALID_SEMAPHORE" in codes


# ---------------------------------------------------------------------------
# TestEvaluatePhase5Gate — gap-level checks
# ---------------------------------------------------------------------------

class TestEvaluatePhase5GateGapLevel(unittest.TestCase):
    def test_alta_pending_gap_in_critical_gaps(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-002-001",
            factor_id="FI-002",
            field="geología",
            description="Estudio geológico pendiente.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="PENDIENTE",
        )
        factors[1] = FactorInventory(
            factor_id="FI-002",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="CAMPO_RECOMENDADO",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=False,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert len(result.critical_gaps) >= 1
        gap_ids = [g["gap_id"] for g in result.critical_gaps]
        assert "GAP-FI-002-001" in gap_ids

    def test_alta_pending_gap_cautelas_not_blocked(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-003-001",
            factor_id="FI-003",
            field="suelos",
            description="Análisis de suelos pendiente.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="PENDIENTE",
        )
        factors[2] = FactorInventory(
            factor_id="FI-003",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="CAMPO_RECOMENDADO",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=False,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6_CON_CAUTELAS"
        assert result.is_blocked() is False

    def test_media_gap_no_critical(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-004-001",
            factor_id="FI-004",
            field="hidrología",
            description="Gap de media criticidad.",
            criticality="MEDIA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        )
        factors[3] = FactorInventory(
            factor_id="FI-004",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert all(g["gap_id"] != "GAP-FI-004-001" for g in result.critical_gaps)

    def test_empty_gap_description_warning(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-005-001",
            factor_id="FI-005",
            field="inundabilidad",
            description="",  # vacío
            criticality="MEDIA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        )
        factors[4] = FactorInventory(
            factor_id="FI-005",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="AMARILLO",
            ready_for_impact_assessment=True,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        codes = {i.code for i in result.issues}
        assert "EMPTY_GAP_DESCRIPTION" in codes


# ---------------------------------------------------------------------------
# TestEvaluatePhase5Gate — decision logic
# ---------------------------------------------------------------------------

class TestPhase5GateDecision(unittest.TestCase):
    def test_apto_fase6_all_conditions(self):
        summary = InventorySummary(
            expediente_id="EIA-FULL",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6"
        assert result.ready_count == 16
        assert result.not_ready_factors == []
        assert result.critical_gaps == []

    def test_apto_con_cautelas_not_ready(self):
        factors = _make_16_ready_factors()
        factors[0] = _make_pending_factor("FI-001")
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6_CON_CAUTELAS"
        assert "FI-001" in result.not_ready_factors

    def test_apto_con_cautelas_critical_gap_not_ready(self):
        factors = _make_16_ready_factors()
        gap = InventoryGap(
            gap_id="GAP-FI-006-001",
            factor_id="FI-006",
            field="calidad del aire",
            description="Medición calidad del aire pendiente.",
            criticality="ALTA",
            resolution_mode="CAMPO",
            status="PENDIENTE",
        )
        factors[5] = FactorInventory(
            factor_id="FI-006",
            description="desc",
            data_sources=["src"],
            evidence_status="ESTIMADO",
            field_mode="CAMPO_RECOMENDADO",
            inventory_semaphore="ROJO_AMARILLO",
            ready_for_impact_assessment=False,
            gaps=[gap],
        )
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6_CON_CAUTELAS"

    def test_no_apto_on_structural_errors(self):
        factors = _make_16_ready_factors()[:-1]  # solo 15
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert result.decision == "NO_APTO_FASE6"

    def test_administrative_ready_always_false_all_decisions(self):
        for factors, expected_blocked in [
            (_make_16_ready_factors(), False),
            ([_make_pending_factor(fid) for fid in sorted(FACTOR_NAMES.keys())], False),
        ]:
            summary = InventorySummary(expediente_id="EIA-X", factors=factors)
            result = evaluate_phase5_gate(summary)
            assert result.administrative_ready is False

    def test_not_ready_factors_listed(self):
        factors = [_make_pending_factor(fid) for fid in sorted(FACTOR_NAMES.keys())]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        assert set(result.not_ready_factors) == set(FACTOR_NAMES.keys())

    def test_red_or_no_consta_factors_listed(self):
        factors = [_make_pending_factor(fid) for fid in sorted(FACTOR_NAMES.keys())]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        # Todos los factores pendientes tienen NO_CONSTA → todos en red_or_no_consta
        assert set(result.red_or_no_consta_factors) == set(FACTOR_NAMES.keys())

    def test_test_mode_flag_in_notes(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary, test_mode=True)
        assert any("test_mode=True" in n for n in result.notes)

    def test_prod_mode_flag_in_notes(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary, test_mode=False)
        assert any("test_mode=False" in n for n in result.notes)


# ---------------------------------------------------------------------------
# TestRealisticOfflineInventory
# ---------------------------------------------------------------------------

class TestRealisticOfflineInventory(unittest.TestCase):
    def test_offline_summary_cautelas(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        assert result.decision == "APTO_FASE6_CON_CAUTELAS"
        assert result.is_blocked() is False

    def test_offline_summary_16_critical_gaps(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        assert len(result.critical_gaps) == 16

    def test_offline_summary_16_not_ready(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        assert len(result.not_ready_factors) == 16

    def test_offline_summary_no_errors(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        assert result.error_count() == 0

    def test_offline_summary_admin_ready_false(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        assert result.administrative_ready is False

    def test_offline_summary_json_serializable(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        raw = json.dumps(result.to_dict(), ensure_ascii=False)
        d = json.loads(raw)
        assert d["decision"] == "APTO_FASE6_CON_CAUTELAS"


# ---------------------------------------------------------------------------
# TestBuildPhase5GateMarkdown
# ---------------------------------------------------------------------------

class TestBuildPhase5GateMarkdown(unittest.TestCase):
    def test_contains_expediente_id(self):
        summary = InventorySummary(
            expediente_id="EIA-MARKDOWN",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "EIA-MARKDOWN" in md

    def test_contains_decision_label(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "APTO PARA FASE 6" in md

    def test_contains_no_apto_label(self):
        factors = _make_16_ready_factors()[:10]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "NO APTO" in md

    def test_contains_cautelas_label(self):
        factors = _make_16_ready_factors()
        factors[0] = _make_pending_factor("FI-001")
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "CAUTELAS" in md

    def test_errors_section_present_when_errors(self):
        factors = _make_16_ready_factors()[:10]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "Errores" in md

    def test_critical_gaps_table_present(self):
        summary = _make_offline_summary()
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "Gaps ALTA" in md

    def test_not_ready_section_present(self):
        factors = [_make_pending_factor(fid) for fid in sorted(FACTOR_NAMES.keys())]
        summary = InventorySummary(expediente_id="EIA-X", factors=factors)
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "no listos" in md.lower()

    def test_admin_ready_note_in_markdown(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "tramit" in md.lower() or "independiente" in md.lower()

    def test_footer_present(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert "F5-01" in md

    def test_markdown_is_string(self):
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        md = build_phase5_gate_markdown(result)
        assert isinstance(md, str)
        assert len(md) > 100


# ---------------------------------------------------------------------------
# TestWritePhase5GateOutputs
# ---------------------------------------------------------------------------

class TestWritePhase5GateOutputs(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_writes_json_and_md(self):
        summary = InventorySummary(
            expediente_id="EIA-WRITE",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        json_path, md_path = write_phase5_gate_outputs(result, self.tmp_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_filenames(self):
        summary = InventorySummary(
            expediente_id="EIA-WRITE",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        json_path, md_path = write_phase5_gate_outputs(result, self.tmp_path)
        assert json_path.name == "phase5_gate_result.json"
        assert md_path.name == "phase5_gate_result.md"

    def test_json_is_valid(self):
        summary = InventorySummary(
            expediente_id="EIA-WRITE",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        json_path, _ = write_phase5_gate_outputs(result, self.tmp_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["decision"] == "APTO_FASE6"
        assert data["expediente_id"] == "EIA-WRITE"

    def test_md_contains_expediente_id(self):
        summary = InventorySummary(
            expediente_id="EIA-WRITE",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        _, md_path = write_phase5_gate_outputs(result, self.tmp_path)
        content = md_path.read_text(encoding="utf-8")
        assert "EIA-WRITE" in content

    def test_creates_output_dir(self):
        out_dir = self.tmp_path / "new_subdir"
        assert not out_dir.exists()
        summary = InventorySummary(
            expediente_id="EIA-X",
            factors=_make_16_ready_factors(),
        )
        result = evaluate_phase5_gate(summary)
        write_phase5_gate_outputs(result, out_dir)
        assert out_dir.exists()


# ---------------------------------------------------------------------------
# TestEvaluatePhase5GateFromInventoryJson
# ---------------------------------------------------------------------------

class TestEvaluateFromJson(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_reads_valid_json(self):
        summary = InventorySummary(
            expediente_id="EIA-JSON",
            factors=_make_16_ready_factors(),
        )
        inv_path = self.tmp_path / "inventory_summary.json"
        inv_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        result = evaluate_phase5_gate_from_inventory_json(inv_path)
        assert result.expediente_id == "EIA-JSON"
        assert result.decision == "APTO_FASE6"

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            evaluate_phase5_gate_from_inventory_json(self.tmp_path / "nope.json")

    def test_invalid_json_raises(self):
        bad = self.tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "JSON"):
            evaluate_phase5_gate_from_inventory_json(bad)

    def test_missing_factors_key_raises(self):
        no_factors = self.tmp_path / "no_factors.json"
        no_factors.write_text(
            json.dumps({"expediente_id": "X", "notes": []}), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "factors"):
            evaluate_phase5_gate_from_inventory_json(no_factors)

    def test_offline_inventory_json_cautelas(self):
        summary = _make_offline_summary()
        inv_path = self.tmp_path / "inventory_summary.json"
        inv_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        result = evaluate_phase5_gate_from_inventory_json(inv_path)
        assert result.decision == "APTO_FASE6_CON_CAUTELAS"


# ---------------------------------------------------------------------------
# TestCLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_cli_inventory_gate_missing_inventory(self):
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        code = run_expediente.main([str(self.tmp_path), "inventory-gate"])
        assert code == 1

    def test_cli_inventory_gate_ok(self):
        # Crear inventario válido
        inv_dir = self.tmp_path / "inventario"
        inv_dir.mkdir()
        summary = InventorySummary(
            expediente_id="EIA-CLI",
            factors=_make_16_ready_factors(),
        )
        inv_path = inv_dir / "inventory_summary.json"
        inv_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        code = run_expediente.main([str(self.tmp_path), "inventory-gate"])
        assert code == 0

    def test_cli_inventory_gate_blocked_returns_1(self):
        inv_dir = self.tmp_path / "inventario"
        inv_dir.mkdir()
        # Inventario con solo 10 factores → error estructural → NO_APTO
        summary = InventorySummary(
            expediente_id="EIA-CLI-ERR",
            factors=_make_16_ready_factors()[:10],
        )
        inv_path = inv_dir / "inventory_summary.json"
        inv_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        code = run_expediente.main([str(self.tmp_path), "inventory-gate"])
        assert code == 1

    def test_cli_inventory_gate_write(self):
        inv_dir = self.tmp_path / "inventario"
        inv_dir.mkdir()
        summary = InventorySummary(
            expediente_id="EIA-CLI-W",
            factors=_make_16_ready_factors(),
        )
        inv_path = inv_dir / "inventory_summary.json"
        inv_path.write_text(
            json.dumps(summary.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        code = run_expediente.main([str(self.tmp_path), "inventory-gate", "--write"])
        assert code == 0
        assert (inv_dir / "phase5_gate_result.json").exists()
        assert (inv_dir / "phase5_gate_result.md").exists()
