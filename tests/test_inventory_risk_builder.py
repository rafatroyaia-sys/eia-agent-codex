"""
tests/test_inventory_risk_builder.py -- IV-03
Tests for src/eia_agent/core/inventory_risk_builder.py

Categorias:
  A. TestBuildFloodRiskFactor    — build_flood_risk_factor_from_phase4
  B. TestBuildNaturalRisksFactor — build_natural_risks_factor_from_phase4
  C. TestRiskInventoryBuildResult — RiskInventoryBuildResult to_dict/summary
  D. TestBuildRiskInventory      — build_risk_inventory_factors_from_phase4
  E. TestMergeRiskFactors        — merge_risk_factors_into_summary
  F. TestIntegrationWithIV02     — build_inventory_from_phase4_data usa IV-03
  G. TestPrudenceLexical         — ningun factor genera frases prohibidas
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_builder import build_inventory_from_phase4, build_inventory_from_phase4_data
from eia_agent.core.inventory_model import FACTOR_NAMES, build_all_empty_factors, build_inventory_summary
from eia_agent.core.inventory_risk_builder import (
    RiskInventoryBuildResult,
    build_flood_risk_factor_from_phase4,
    build_natural_risks_factor_from_phase4,
    build_risk_inventory_factors_from_phase4,
    merge_risk_factors_into_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Mapa de inundabilidad (MAP-006 de CA-10)
INUND_MAP = {
    "map_id": "MAP-006",
    "title": "Inundabilidad / riesgos fisicos",
    "purpose": "Zonas de inundabilidad y riesgos fisicos en radio 2 000 m",
    "map_type": "inundabilidad_riesgos",
    "extent_key": "entorno_2000m",
    "extent": {},
    "required_layers": ["inundabilidad", "drenaje", "marcador_proyecto"],
    "source_candidates": [
        "MITERD / SNCZI Sistema Nacional Cartografia Zonas Inundables",
        "IGME / Mapa de riesgos geologicos",
        "Grafcan / RIESGOMAP Canarias",
    ],
    "output_filename": "MAP-006_inundabilidad_riesgos.png",
    "status": "READY_FOR_RENDER",
    "warnings": [],
    "notes": [],
}

OTRO_MAP = {
    "map_id": "MAP-001",
    "title": "Situacion general",
    "purpose": "Localizacion regional",
    "map_type": "situacion_general",
    "extent_key": "situacion_general",
    "extent": {},
    "required_layers": ["base_territorial"],
    "source_candidates": ["IGN / BTN100"],
    "output_filename": "MAP-001_situacion_general.png",
    "status": "READY_FOR_RENDER",
    "warnings": [],
    "notes": [],
}

CART_PLAN_WITH_INUND = {
    "expediente_id": "EIA-TEST",
    "center": {
        "lat": 28.9773,
        "lon": -13.5395,
        "source": "DECLARADO",
        "status": "DECLARADO",
        "notes": [],
    },
    "maps": [OTRO_MAP, INUND_MAP],
    "ready_for_render": True,
    "warnings": [],
    "notes": [],
}

CART_PLAN_NO_INUND = {
    "expediente_id": "EIA-TEST",
    "center": {
        "lat": 28.9773,
        "lon": -13.5395,
        "source": "DECLARADO",
        "status": "DECLARADO",
        "notes": [],
    },
    "maps": [OTRO_MAP],  # solo MAP-001, sin inundabilidad
    "ready_for_render": False,
    "warnings": [],
    "notes": [],
}

CART_PLAN_EMPTY_MAPS = {
    "expediente_id": "EIA-TEST",
    "center": {
        "lat": 28.9773,
        "lon": -13.5395,
        "source": "DECLARADO",
        "status": "DECLARADO",
        "notes": [],
    },
    "maps": [],
    "ready_for_render": False,
    "warnings": [],
    "notes": [],
}

CLIMATE_STATION = {
    "selected_station": {"station_id": "C029O", "name": "Arrecife Lanzarote Aeropuerto"},
    "station_distance_km": 3.2,
    "station_selection_status": "OPTIMA",
    "climate_classification": {
        "koppen_code": "BWh",
        "koppen_label": "Desierto calido",
        "martonne_index": 4.2,
        "martonne_label": "Arido",
        "dry_months_gaussen": 12,
        "dry_months_names": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "annual_temperature_c": 20.4,
        "annual_precipitation_mm": 141.2,
        "notes": [],
    },
    "warnings": [],
    "notes": [],
}

PHASE4_FULL = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": CART_PLAN_WITH_INUND,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_NO_PLAN = {
    "expediente_id": "EIA-2026-NOPLAN",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_CLIMATE_ONLY = {
    "expediente_id": "EIA-2026-CLIMATE",
    "climate": CLIMATE_STATION,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}


# ---------------------------------------------------------------------------
# A. TestBuildFloodRiskFactor
# ---------------------------------------------------------------------------

class TestBuildFloodRiskFactor(unittest.TestCase):

    def test_factor_id_is_fi005(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.factor_id, "FI-005")

    def test_with_inund_map_evidence_estimado(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.evidence_status, "ESTIMADO")

    def test_with_inund_map_field_mode_campo_recomendado(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.field_mode, "CAMPO_RECOMENDADO")

    def test_with_inund_map_semaphore_amarillo(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.inventory_semaphore, "AMARILLO")

    def test_never_verde_with_inund_map(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertNotEqual(factor.inventory_semaphore, "VERDE")

    def test_ready_false_always(self):
        for phase4, plan in [
            (PHASE4_FULL, CART_PLAN_WITH_INUND),
            (PHASE4_FULL, CART_PLAN_NO_INUND),
            (PHASE4_NO_PLAN, None),
        ]:
            factor = build_flood_risk_factor_from_phase4(phase4, plan)
            self.assertFalse(factor.ready_for_impact_assessment, f"plan={plan}")

    def test_has_gap_fi005(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(len(factor.gaps), 1)
        self.assertEqual(factor.gaps[0].gap_id, "GAP-FI-005-001")

    def test_gap_criticality_alta(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].criticality, "ALTA")

    def test_gap_resolution_mode_gabinete(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].resolution_mode, "GABINETE")

    def test_gap_status_pendiente(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].status, "PENDIENTE")

    def test_description_mentions_snczi(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("SNCZI", factor.description)

    def test_description_mentions_official_verification(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        has_official = "fuentes oficiales" in factor.description.lower() or "oficial" in factor.description.lower()
        self.assertTrue(has_official)

    def test_description_mentions_map006(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("MAP-006", factor.description)

    def test_data_sources_contains_f401(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertTrue(any("F4-01" in s for s in factor.data_sources))

    def test_data_sources_contains_ca10_when_plan(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertTrue(any("CA-10" in s for s in factor.data_sources))

    def test_data_sources_contains_ca11_when_inund_map(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertTrue(any("CA-11" in s for s in factor.data_sources))

    def test_without_plan_evidence_pendiente(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_NO_PLAN, None)
        self.assertEqual(factor.evidence_status, "PENDIENTE")

    def test_without_plan_semaphore_no_consta(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_NO_PLAN, None)
        self.assertEqual(factor.inventory_semaphore, "NO_CONSTA")

    def test_without_plan_field_mode_no_consta(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_NO_PLAN, None)
        self.assertEqual(factor.field_mode, "NO_CONSTA")

    def test_plan_no_inund_map_evidence_pendiente(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_NO_INUND)
        self.assertEqual(factor.evidence_status, "PENDIENTE")

    def test_plan_no_inund_map_semaphore_no_consta(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_NO_INUND)
        self.assertEqual(factor.inventory_semaphore, "NO_CONSTA")

    def test_plan_no_inund_map_has_warning(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_NO_INUND)
        self.assertGreater(len(factor.warnings), 0)

    def test_embedded_plan_used_when_no_external(self):
        # PHASE4_FULL has embedded CART_PLAN_WITH_INUND
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL)
        self.assertEqual(factor.inventory_semaphore, "AMARILLO")

    def test_gap_factor_id_matches(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].factor_id, "FI-005")

    def test_planned_map_still_gives_amarillo(self):
        planned_map = {**INUND_MAP, "status": "PLANNED"}
        plan = {**CART_PLAN_WITH_INUND, "maps": [planned_map]}
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, plan)
        self.assertEqual(factor.inventory_semaphore, "AMARILLO")

    def test_note_about_no_official(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        has_note = any("SNCZI" in n or "oficial" in n.lower() for n in factor.notes)
        self.assertTrue(has_note)


# ---------------------------------------------------------------------------
# B. TestBuildNaturalRisksFactor
# ---------------------------------------------------------------------------

class TestBuildNaturalRisksFactor(unittest.TestCase):

    def test_factor_id_is_fi016(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.factor_id, "FI-016")

    def test_with_coords_and_plan_evidence_estimado(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.evidence_status, "ESTIMADO")

    def test_with_coords_and_plan_semaphore_amarillo(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.inventory_semaphore, "AMARILLO")

    def test_never_verde(self):
        for phase4, plan in [
            (PHASE4_FULL, CART_PLAN_WITH_INUND),
            (PHASE4_CLIMATE_ONLY, None),
            (PHASE4_NO_PLAN, None),
        ]:
            factor = build_natural_risks_factor_from_phase4(phase4, plan)
            self.assertNotEqual(factor.inventory_semaphore, "VERDE", f"plan={plan}")

    def test_ready_false_always(self):
        for phase4, plan in [
            (PHASE4_FULL, CART_PLAN_WITH_INUND),
            (PHASE4_CLIMATE_ONLY, None),
            (PHASE4_NO_PLAN, None),
        ]:
            factor = build_natural_risks_factor_from_phase4(phase4, plan)
            self.assertFalse(factor.ready_for_impact_assessment)

    def test_has_gap_fi016(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(len(factor.gaps), 1)
        self.assertEqual(factor.gaps[0].gap_id, "GAP-FI-016-001")

    def test_gap_criticality_alta(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].criticality, "ALTA")

    def test_gap_resolution_gabinete(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].resolution_mode, "GABINETE")

    def test_description_mentions_inundabilidad(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("inundabilidad", factor.description.lower())

    def test_description_mentions_incendio_forestal(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("incendio forestal", factor.description.lower())

    def test_description_mentions_sismicidad(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("sismicidad", factor.description.lower())

    def test_description_mentions_meteorologicos(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("meteorologico", factor.description.lower())

    def test_description_mentions_volcanic_risk(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIn("volcanico", factor.description.lower())

    def test_description_doesnt_close_risks(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        # Ninguna frase cierra riesgos como inexistentes
        forbidden = ["sin riesgo", "riesgo nulo", "no existe riesgo"]
        for phrase in forbidden:
            self.assertNotIn(phrase, factor.description.lower(), f"Frase prohibida: {phrase}")

    def test_description_says_pending_verification(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        has_pending = "verificaci" in factor.description.lower() or "consulta" in factor.description.lower()
        self.assertTrue(has_pending)

    def test_data_sources_contains_f401(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertTrue(any("F4-01" in s for s in factor.data_sources))

    def test_without_coords_evidence_pendiente(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_NO_PLAN, None)
        self.assertEqual(factor.evidence_status, "PENDIENTE")

    def test_without_coords_semaphore_no_consta(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_NO_PLAN, None)
        self.assertEqual(factor.inventory_semaphore, "NO_CONSTA")

    def test_coords_only_evidence_estimado(self):
        # Solo clima (coordenadas via estacion), sin plan
        factor = build_natural_risks_factor_from_phase4(PHASE4_CLIMATE_ONLY, None)
        self.assertEqual(factor.evidence_status, "ESTIMADO")

    def test_coords_only_semaphore_no_consta(self):
        # Coordenadas disponibles pero sin plan → NO_CONSTA
        factor = build_natural_risks_factor_from_phase4(PHASE4_CLIMATE_ONLY, None)
        self.assertEqual(factor.inventory_semaphore, "NO_CONSTA")

    def test_embedded_plan_detected(self):
        # PHASE4_FULL tiene embedded CART_PLAN_WITH_INUND
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL)
        self.assertEqual(factor.inventory_semaphore, "AMARILLO")

    def test_gap_factor_id_matches(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(factor.gaps[0].factor_id, "FI-016")

    def test_note_about_no_official(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        has_note = any("oficial" in n.lower() for n in factor.notes)
        self.assertTrue(has_note)


# ---------------------------------------------------------------------------
# C. TestRiskInventoryBuildResult
# ---------------------------------------------------------------------------

class TestRiskInventoryBuildResult(unittest.TestCase):

    def _make_result(self) -> RiskInventoryBuildResult:
        return build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)

    def test_to_dict_has_factors_key(self):
        r = self._make_result()
        self.assertIn("factors", r.to_dict())

    def test_to_dict_factors_count(self):
        r = self._make_result()
        self.assertEqual(len(r.to_dict()["factors"]), 2)

    def test_to_dict_json_serializable(self):
        r = self._make_result()
        json_str = json.dumps(r.to_dict(), ensure_ascii=False)
        self.assertIn("FI-005", json_str)
        self.assertIn("FI-016", json_str)

    def test_to_dict_has_warnings_and_notes(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_summary_mentions_factor_ids(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("FI-005", s)
        self.assertIn("FI-016", s)

    def test_summary_shows_semaphore(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("AMARILLO", s)

    def test_no_plan_result_has_warning(self):
        r = build_risk_inventory_factors_from_phase4(PHASE4_NO_PLAN, None)
        self.assertGreater(len(r.warnings), 0)

    def test_with_plan_result_notes_not_empty(self):
        r = self._make_result()
        self.assertGreater(len(r.notes), 0)


# ---------------------------------------------------------------------------
# D. TestBuildRiskInventory
# ---------------------------------------------------------------------------

class TestBuildRiskInventory(unittest.TestCase):

    def test_returns_two_factors(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(len(result.factors), 2)

    def test_returns_fi005_and_fi016(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        ids = {f.factor_id for f in result.factors}
        self.assertEqual(ids, {"FI-005", "FI-016"})

    def test_notes_not_empty(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertGreater(len(result.notes), 0)

    def test_no_plan_adds_warning(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_NO_PLAN, None)
        self.assertGreater(len(result.warnings), 0)

    def test_with_plan_no_extra_warning(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        # No debe haber aviso de "no hay plan" cuando sí hay plan
        no_plan_warnings = [w for w in result.warnings if "plan cartografico" in w.lower() and "no se dispone" in w.lower()]
        self.assertEqual(len(no_plan_warnings), 0)

    def test_fi005_is_first_factor(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(result.factors[0].factor_id, "FI-005")

    def test_fi016_is_second_factor(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertEqual(result.factors[1].factor_id, "FI-016")

    def test_result_is_risk_inventory_build_result(self):
        result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        self.assertIsInstance(result, RiskInventoryBuildResult)


# ---------------------------------------------------------------------------
# E. TestMergeRiskFactors
# ---------------------------------------------------------------------------

class TestMergeRiskFactors(unittest.TestCase):

    def _make_base_summary(self) -> object:
        factors = build_all_empty_factors()
        return build_inventory_summary("EIA-MERGE-TEST", factors)

    def test_replaces_fi005(self):
        summary = self._make_base_summary()
        fi005 = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, [fi005])
        result_fi005 = next(f for f in new_summary.factors if f.factor_id == "FI-005")
        self.assertEqual(result_fi005.evidence_status, "ESTIMADO")

    def test_replaces_fi016(self):
        summary = self._make_base_summary()
        fi016 = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, [fi016])
        result_fi016 = next(f for f in new_summary.factors if f.factor_id == "FI-016")
        self.assertEqual(result_fi016.evidence_status, "ESTIMADO")

    def test_replaces_both_fi005_fi016(self):
        summary = self._make_base_summary()
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        fi005 = next(f for f in new_summary.factors if f.factor_id == "FI-005")
        fi016 = next(f for f in new_summary.factors if f.factor_id == "FI-016")
        self.assertEqual(fi005.evidence_status, "ESTIMADO")
        self.assertEqual(fi016.evidence_status, "ESTIMADO")

    def test_no_duplicates(self):
        summary = self._make_base_summary()
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_conserves_16_factors(self):
        summary = self._make_base_summary()
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        self.assertEqual(new_summary.total_factors, 16)

    def test_preserves_canonical_order(self):
        summary = self._make_base_summary()
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_does_not_mutate_original_factors(self):
        summary = self._make_base_summary()
        original_fi005_evidence = next(
            f for f in summary.factors if f.factor_id == "FI-005"
        ).evidence_status
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        merge_risk_factors_into_summary(summary, risk_result.factors)
        # El summary original no cambia
        current_fi005_evidence = next(
            f for f in summary.factors if f.factor_id == "FI-005"
        ).evidence_status
        self.assertEqual(original_fi005_evidence, current_fi005_evidence)

    def test_does_not_mutate_original_warnings(self):
        summary = self._make_base_summary()
        summary.warnings.append("aviso-original")
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        # El aviso original aparece en el nuevo summary (propagado)
        self.assertIn("aviso-original", new_summary.warnings)
        # El summary original tiene 1 aviso (no fue modificado por merge)
        self.assertEqual(summary.warnings.count("aviso-original"), 1)

    def test_propagates_original_warnings(self):
        summary = self._make_base_summary()
        summary.warnings.append("aviso-previo")
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        self.assertIn("aviso-previo", new_summary.warnings)

    def test_other_factors_unchanged(self):
        summary = self._make_base_summary()
        risk_result = build_risk_inventory_factors_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        new_summary = merge_risk_factors_into_summary(summary, risk_result.factors)
        fi001_new = next(f for f in new_summary.factors if f.factor_id == "FI-001")
        fi001_old = next(f for f in summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001_new.evidence_status, fi001_old.evidence_status)


# ---------------------------------------------------------------------------
# F. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def test_fi005_enriched_by_iv03_with_plan(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi005 = next(f for f in result.factors if f.factor_id == "FI-005")
        # Con plan que incluye MAP-006: ESTIMADO/AMARILLO
        self.assertEqual(fi005.evidence_status, "ESTIMADO")
        self.assertEqual(fi005.inventory_semaphore, "AMARILLO")

    def test_fi016_enriched_by_iv03_with_plan(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi016 = next(f for f in result.factors if f.factor_id == "FI-016")
        # Con coordenadas y plan: ESTIMADO/AMARILLO
        self.assertEqual(fi016.evidence_status, "ESTIMADO")
        self.assertEqual(fi016.inventory_semaphore, "AMARILLO")

    def test_fi005_not_verde(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi005 = next(f for f in result.factors if f.factor_id == "FI-005")
        self.assertNotEqual(fi005.inventory_semaphore, "VERDE")

    def test_fi016_not_verde(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi016 = next(f for f in result.factors if f.factor_id == "FI-016")
        self.assertNotEqual(fi016.inventory_semaphore, "VERDE")

    def test_fi005_ready_false(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi005 = next(f for f in result.factors if f.factor_id == "FI-005")
        self.assertFalse(fi005.ready_for_impact_assessment)

    def test_fi016_ready_false(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi016 = next(f for f in result.factors if f.factor_id == "FI-016")
        self.assertFalse(fi016.ready_for_impact_assessment)

    def test_all_ready_for_phase6_still_false(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        self.assertFalse(result.all_ready_for_phase6)

    def test_still_16_factors(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        self.assertEqual(result.total_factors, 16)

    def test_fi005_has_gap_alta(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi005 = next(f for f in result.factors if f.factor_id == "FI-005")
        alta_gaps = [g for g in fi005.gaps if g.criticality == "ALTA"]
        self.assertGreater(len(alta_gaps), 0)

    def test_fi016_has_gap_alta(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi016 = next(f for f in result.factors if f.factor_id == "FI-016")
        alta_gaps = [g for g in fi016.gaps if g.criticality == "ALTA"]
        self.assertGreater(len(alta_gaps), 0)

    def test_fi001_still_enriched_by_climate(self):
        result = build_inventory_from_phase4_data("EIA-INT", PHASE4_FULL)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_write_generates_fi005_with_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-INT"
            exp.mkdir()
            p4_path = exp / "fase4" / "phase4_result.json"
            p4_path.parent.mkdir()
            p4_path.write_text(
                json.dumps(PHASE4_FULL, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = build_inventory_from_phase4(exp, write_outputs=True)
            fi005_files = [f for f in result.rendered_files if "FI-005" in f and f.endswith(".md")]
            self.assertGreater(len(fi005_files), 0)
            # El contenido del archivo debe incluir el gap
            fi005_content = Path(fi005_files[0]).read_text(encoding="utf-8")
            self.assertIn("GAP-FI-005-001", fi005_content)

    def test_write_generates_fi016_with_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-INT"
            exp.mkdir()
            p4_path = exp / "fase4" / "phase4_result.json"
            p4_path.parent.mkdir()
            p4_path.write_text(
                json.dumps(PHASE4_FULL, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = build_inventory_from_phase4(exp, write_outputs=True)
            fi016_files = [f for f in result.rendered_files if "FI-016" in f and f.endswith(".md")]
            self.assertGreater(len(fi016_files), 0)
            fi016_content = Path(fi016_files[0]).read_text(encoding="utf-8")
            self.assertIn("GAP-FI-016-001", fi016_content)


# ---------------------------------------------------------------------------
# G. TestPrudenceLexical
# ---------------------------------------------------------------------------

class TestPrudenceLexical(unittest.TestCase):
    """Verifica que ninguna descripcion generada contiene frases prohibidas."""

    _FORBIDDEN = [
        "sin riesgo",
        "riesgo nulo",
        "no existe riesgo",
    ]

    def _check_no_forbidden(self, text: str, label: str) -> None:
        text_lower = text.lower()
        for phrase in self._FORBIDDEN:
            self.assertNotIn(phrase, text_lower, f"{label}: frase prohibida '{phrase}'")

    def test_fi005_description_no_forbidden_phrases(self):
        for phase4, plan in [
            (PHASE4_FULL, CART_PLAN_WITH_INUND),
            (PHASE4_FULL, CART_PLAN_NO_INUND),
            (PHASE4_NO_PLAN, None),
        ]:
            factor = build_flood_risk_factor_from_phase4(phase4, plan)
            self._check_no_forbidden(factor.description, f"FI-005 description (plan={bool(plan)})")

    def test_fi016_description_no_forbidden_phrases(self):
        for phase4, plan in [
            (PHASE4_FULL, CART_PLAN_WITH_INUND),
            (PHASE4_CLIMATE_ONLY, None),
            (PHASE4_NO_PLAN, None),
        ]:
            factor = build_natural_risks_factor_from_phase4(phase4, plan)
            self._check_no_forbidden(factor.description, f"FI-016 description (plan={bool(plan)})")

    def test_fi005_warnings_no_forbidden_phrases(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_NO_PLAN, None)
        for w in factor.warnings:
            self._check_no_forbidden(w, "FI-005 warning")

    def test_fi016_warnings_no_forbidden_phrases(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_NO_PLAN, None)
        for w in factor.warnings:
            self._check_no_forbidden(w, "FI-016 warning")

    def test_fi005_notes_no_forbidden_phrases(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        for n in factor.notes:
            self._check_no_forbidden(n, "FI-005 note")

    def test_fi016_notes_no_forbidden_phrases(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        for n in factor.notes:
            self._check_no_forbidden(n, "FI-016 note")

    def test_fi005_gap_description_no_forbidden_phrases(self):
        factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        for g in factor.gaps:
            self._check_no_forbidden(g.description, f"FI-005 gap {g.gap_id}")

    def test_fi016_gap_description_no_forbidden_phrases(self):
        factor = build_natural_risks_factor_from_phase4(PHASE4_FULL, CART_PLAN_WITH_INUND)
        for g in factor.gaps:
            self._check_no_forbidden(g.description, f"FI-016 gap {g.gap_id}")

    def test_fi005_all_variants_of_plan(self):
        for plan in [CART_PLAN_WITH_INUND, CART_PLAN_NO_INUND, CART_PLAN_EMPTY_MAPS, None]:
            factor = build_flood_risk_factor_from_phase4(PHASE4_FULL, plan)
            self._check_no_forbidden(factor.description, f"FI-005 plan_type={plan}")

    def test_fi016_all_variants_of_coords(self):
        for phase4 in [PHASE4_FULL, PHASE4_CLIMATE_ONLY, PHASE4_NO_PLAN]:
            factor = build_natural_risks_factor_from_phase4(phase4, None)
            self._check_no_forbidden(factor.description, f"FI-016 phase4={phase4.get('expediente_id')}")

    def test_integration_fi005_fi016_no_forbidden_in_summary(self):
        result = build_inventory_from_phase4_data("EIA-PRUD", PHASE4_FULL)
        for factor in result.factors:
            if factor.factor_id in ("FI-005", "FI-016"):
                self._check_no_forbidden(factor.description, factor.factor_id)


if __name__ == "__main__":
    unittest.main()
