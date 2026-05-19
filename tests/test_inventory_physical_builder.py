"""
tests/test_inventory_physical_builder.py -- IV-07
Tests for src/eia_agent/core/inventory_physical_builder.py

Categorias:
  A. TestAuxiliaries            -- extract_physical_context, has_*_source_planned
  B. TestBuildGeologyFactor     -- build_geology_factor_from_phase4 (FI-002)
  C. TestBuildSoilFactor        -- build_soil_factor_from_phase4 (FI-003)
  D. TestBuildHydrologyFactor   -- build_hydrology_factor_from_phase4 (FI-004)
  E. TestPhysicalBuildResult    -- PhysicalInventoryBuildResult dataclass
  F. TestBuildCombined          -- build_physical_inventory_factors_from_phase4
  G. TestMerge                  -- merge_physical_factors_into_summary
  H. TestIntegrationWithIV02    -- build_inventory_from_phase4_data con IV-07
  I. TestPrudenceLexical        -- ausencia de patrones prohibidos
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_physical_builder import (
    PhysicalInventoryBuildResult,
    build_geology_factor_from_phase4,
    build_hydrology_factor_from_phase4,
    build_physical_inventory_factors_from_phase4,
    build_soil_factor_from_phase4,
    extract_physical_context,
    has_geology_source_planned,
    has_hydrology_source_planned,
    has_soil_source_planned,
    merge_physical_factors_into_summary,
)
from eia_agent.core.inventory_builder import build_inventory_from_phase4_data
from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    build_all_empty_factors,
    build_inventory_summary,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIMATE_STATION = {
    "selected_station": {
        "station_id": "C029O",
        "name": "Lanzarote Aeropuerto",
    },
    "station_distance_km": 6.7,
    "station_selection_status": "OPTIMA",
    "climate_classification": {
        "koppen_code": "BWh",
        "annual_temperature_c": 21.36,
        "annual_precipitation_mm": 131.0,
        "notes": [],
    },
    "warnings": [],
    "notes": [],
}

MAP_001 = {
    "map_id": "MAP-001",
    "map_type": "situacion_general",
    "title": "Situacion general",
    "required_layers": ["osm_base"],
    "output_filename": "MAP-001.png",
    "status": "READY_FOR_RENDER",
}

MAP_005 = {
    "map_id": "MAP-005",
    "map_type": "usos_suelo",
    "title": "Usos del suelo entorno",
    "purpose": "Usos del suelo y presencia de receptores sensibles",
    "required_layers": ["usos_suelo", "buffer_500m", "marcador_proyecto"],
    "source_candidates": ["Corine Land Cover / IGN", "SIOSE / IGN"],
    "output_filename": "MAP-005_usos_suelo_entorno.png",
    "status": "READY_FOR_RENDER",
}

MAP_006 = {
    "map_id": "MAP-006",
    "map_type": "inundabilidad_riesgos",
    "title": "Inundabilidad / riesgos fisicos",
    "purpose": "Zonas de inundabilidad y riesgos fisicos",
    "required_layers": ["inundabilidad", "drenaje", "marcador_proyecto"],
    "source_candidates": [
        "MITERD / SNCZI",
        "IGME / Mapa de riesgos geologicos",
        "Grafcan / RIESGOMAP Canarias",
    ],
    "output_filename": "MAP-006_inundabilidad_riesgos.png",
    "status": "READY_FOR_RENDER",
}

MAP_006_GENERATED = {
    "map_id": "MAP-006",
    "map_type": "inundabilidad_riesgos",
    "title": "Inundabilidad / riesgos fisicos",
    "required_layers": ["inundabilidad", "drenaje"],
    "output_filename": "MAP-006_inundabilidad_riesgos.png",
    "status": "GENERATED_PROVISIONAL",
}

MAP_IGME = {
    "map_id": "MAP-IGME",
    "map_type": "geologia",
    "title": "Mapa geologico",
    "required_layers": ["geologia_igme", "litologia"],
    "source_candidates": ["IGME / GEODE"],
    "output_filename": "MAP-IGME_geologia.png",
    "status": "READY_FOR_RENDER",
}

# Plan completo con MAP-005 y MAP-006
CART_PLAN_FULL = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_005, MAP_006],
    "ready_for_render": True,
    "warnings": [],
    "notes": [],
}

# Plan con solo MAP-006 (hidrologico/geologico)
CART_PLAN_MAP006_ONLY = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_006],
    "ready_for_render": True,
    "warnings": [],
}

# Plan con MAP-006 generado (provisional)
CART_PLAN_MAP006_GENERATED = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_006_GENERATED],
    "ready_for_render": True,
}

# Plan con MAP-IGME (geologia explicita)
CART_PLAN_IGME = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_IGME],
    "ready_for_render": True,
}

# Plan vacio
CART_PLAN_EMPTY = {
    "expediente_id": "EIA-TEST",
    "maps": [],
}

# Plan base sin capas fisicas
CART_PLAN_BASE_ONLY = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001],
    "ready_for_render": True,
}

# Phase4 completo con MAP-006 y MAP-005
PHASE4_FULL = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": CART_PLAN_FULL,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

# Phase4 sin plan
PHASE4_NO_PLAN = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

# Phase4 con clima (plan embebido vacio)
PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

# Phase4 con MAP-006 embebido
PHASE4_WITH_MAP006 = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": CART_PLAN_MAP006_ONLY,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE2_FULL = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento", "R13 - tratamiento"],
    }
}


# ---------------------------------------------------------------------------
# A. TestAuxiliaries
# ---------------------------------------------------------------------------

class TestAuxiliaries(unittest.TestCase):

    def test_extract_no_crash_empty_dicts(self):
        text = extract_physical_context({}, {}, {})
        self.assertIsInstance(text, str)

    def test_extract_no_crash_none(self):
        text = extract_physical_context(None, None, None)
        self.assertEqual(text, "")

    def test_extract_detects_geology(self):
        phase4 = {"notes": ["formacion geologica volcanica"]}
        text = extract_physical_context(None, phase4, None)
        self.assertIn("geolog", text)

    def test_extract_detects_suelo(self):
        text = extract_physical_context(None, None, CART_PLAN_FULL)
        self.assertIn("usos_suelo", text)

    def test_extract_detects_hidrology(self):
        text = extract_physical_context(None, None, CART_PLAN_MAP006_ONLY)
        self.assertIn("inundab", text)

    def test_extract_lowercase(self):
        text = extract_physical_context(None, None, CART_PLAN_FULL)
        self.assertEqual(text, text.lower())

    def test_extract_detects_barranco(self):
        phase4 = {"notes": ["barranco de Los Encantados adyacente"]}
        text = extract_physical_context(None, phase4, None)
        self.assertIn("barranco", text)

    def test_extract_detects_igme(self):
        text = extract_physical_context(None, None, CART_PLAN_MAP006_ONLY)
        self.assertIn("igme", text)

    def test_has_geology_source_igme_in_source_candidates(self):
        self.assertTrue(has_geology_source_planned(CART_PLAN_MAP006_ONLY))

    def test_has_geology_source_igme_map(self):
        self.assertTrue(has_geology_source_planned(CART_PLAN_IGME))

    def test_has_geology_source_false_no_geo(self):
        self.assertFalse(has_geology_source_planned(CART_PLAN_BASE_ONLY))

    def test_has_geology_source_false_none(self):
        self.assertFalse(has_geology_source_planned(None))

    def test_has_soil_source_map005(self):
        self.assertTrue(has_soil_source_planned(CART_PLAN_FULL))

    def test_has_soil_source_false_no_soil(self):
        self.assertFalse(has_soil_source_planned(CART_PLAN_BASE_ONLY))

    def test_has_soil_source_false_none(self):
        self.assertFalse(has_soil_source_planned(None))

    def test_has_hydrology_source_map006(self):
        self.assertTrue(has_hydrology_source_planned(CART_PLAN_MAP006_ONLY))

    def test_has_hydrology_source_inundabilidad_layer(self):
        plan = {"maps": [{"map_id": "X", "required_layers": ["inundabilidad"], "source_candidates": []}]}
        self.assertTrue(has_hydrology_source_planned(plan))

    def test_has_hydrology_source_false_no_hydro(self):
        self.assertFalse(has_hydrology_source_planned(CART_PLAN_BASE_ONLY))

    def test_has_hydrology_source_false_none(self):
        self.assertFalse(has_hydrology_source_planned(None))


# ---------------------------------------------------------------------------
# B. TestBuildGeologyFactor
# ---------------------------------------------------------------------------

class TestBuildGeologyFactor(unittest.TestCase):

    def test_factor_id_is_fi002(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.factor_id, "FI-002")

    def test_with_plan_is_estimado(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_plan_is_amarillo(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_plan_campo_recomendado(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_without_plan_or_location_is_pendiente(self):
        fi = build_geology_factor_from_phase4(None, None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_plan_no_consta(self):
        fi = build_geology_factor_from_phase4(None, None, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_with_location_only_is_estimado(self):
        fi = build_geology_factor_from_phase4(PHASE2_FULL, None, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_never_verde(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, CART_PLAN_EMPTY, None]:
            fi = build_geology_factor_from_phase4(None, None, plan)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE prohibido con plan={plan}")

    def test_gap_fi002_001_always_present(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, None]:
            fi = build_geology_factor_from_phase4(None, None, plan)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-002-001", gap_ids)

    def test_gap_criticality_media(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_resolution_gabinete(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.resolution_mode, "GABINETE")

    def test_ready_always_false(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, None]:
            fi = build_geology_factor_from_phase4(None, None, plan)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_data_sources_populated_with_plan(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_data_sources_empty_without_plan_or_loc(self):
        fi = build_geology_factor_from_phase4(None, None, None)
        self.assertEqual(fi.data_sources, [])

    def test_description_mentions_igme(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_MAP006_ONLY)
        desc = fi.description.lower()
        self.assertTrue("igme" in desc or "geode" in desc or "geol" in desc)

    def test_uses_embedded_plan_from_phase4(self):
        fi = build_geology_factor_from_phase4(None, PHASE4_FULL, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_schematic_mentioned_when_generated(self):
        fi = build_geology_factor_from_phase4(None, None, CART_PLAN_MAP006_GENERATED)
        desc = fi.description.lower()
        self.assertTrue("provisional" in desc or "ca-11" in desc or "orientativo" in desc)


# ---------------------------------------------------------------------------
# C. TestBuildSoilFactor
# ---------------------------------------------------------------------------

class TestBuildSoilFactor(unittest.TestCase):

    def test_factor_id_is_fi003(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.factor_id, "FI-003")

    def test_with_plan_is_estimado(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_plan_is_amarillo(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_plan_campo_recomendado(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_without_plan_or_location_is_pendiente(self):
        fi = build_soil_factor_from_phase4(None, None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_plan_no_consta(self):
        fi = build_soil_factor_from_phase4(None, None, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_with_location_only_is_estimado(self):
        fi = build_soil_factor_from_phase4(PHASE2_FULL, None, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_never_verde(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, CART_PLAN_EMPTY, None]:
            fi = build_soil_factor_from_phase4(None, None, plan)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    def test_gap_fi003_001_always_present(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, None]:
            fi = build_soil_factor_from_phase4(None, None, plan)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-003-001", gap_ids)

    def test_gap_criticality_media(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_resolution_campo(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.resolution_mode, "CAMPO")

    def test_ready_always_false(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, None]:
            fi = build_soil_factor_from_phase4(None, None, plan)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_data_sources_populated_with_plan(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_description_mentions_sigpac_or_corine(self):
        fi = build_soil_factor_from_phase4(None, None, CART_PLAN_FULL)
        desc = fi.description.lower()
        self.assertTrue("sigpac" in desc or "corine" in desc or "usos" in desc)

    def test_uses_embedded_plan_from_phase4(self):
        fi = build_soil_factor_from_phase4(None, PHASE4_FULL, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")


# ---------------------------------------------------------------------------
# D. TestBuildHydrologyFactor
# ---------------------------------------------------------------------------

class TestBuildHydrologyFactor(unittest.TestCase):

    def test_factor_id_is_fi004(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.factor_id, "FI-004")

    def test_with_plan_is_estimado(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_plan_is_amarillo(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_plan_campo_recomendado(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_without_plan_or_location_is_pendiente(self):
        fi = build_hydrology_factor_from_phase4(None, None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_plan_no_consta(self):
        fi = build_hydrology_factor_from_phase4(None, None, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_with_location_only_is_estimado(self):
        fi = build_hydrology_factor_from_phase4(PHASE2_FULL, None, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_never_verde(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_MAP006_ONLY, CART_PLAN_BASE_ONLY, None]:
            fi = build_hydrology_factor_from_phase4(None, None, plan)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    def test_gap_fi004_001_always_present(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_BASE_ONLY, None]:
            fi = build_hydrology_factor_from_phase4(None, None, plan)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-004-001", gap_ids)

    def test_gap_criticality_alta_with_map006(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_MAP006_ONLY)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_criticality_media_without_map006(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_BASE_ONLY)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_criticality_alta_with_full_plan(self):
        # CART_PLAN_FULL tiene MAP-006 → ALTA
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_resolution_gabinete(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        gap = fi.gaps[0]
        self.assertEqual(gap.resolution_mode, "GABINETE")

    def test_ready_always_false(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_MAP006_ONLY, None]:
            fi = build_hydrology_factor_from_phase4(None, None, plan)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_data_sources_populated_with_plan(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_FULL)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_description_mentions_snczi_or_drenaje(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_MAP006_ONLY)
        desc = fi.description.lower()
        self.assertTrue("snczi" in desc or "drenaje" in desc or "hidrol" in desc)

    def test_uses_embedded_plan_from_phase4(self):
        fi = build_hydrology_factor_from_phase4(None, PHASE4_FULL, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_schematic_mentioned_when_generated(self):
        fi = build_hydrology_factor_from_phase4(None, None, CART_PLAN_MAP006_GENERATED)
        desc = fi.description.lower()
        self.assertTrue("provisional" in desc or "ca-11" in desc or "orientativo" in desc)


# ---------------------------------------------------------------------------
# E. TestPhysicalBuildResult
# ---------------------------------------------------------------------------

class TestPhysicalBuildResult(unittest.TestCase):

    def _make_result(self):
        return build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)

    def test_factors_has_three_elements(self):
        r = self._make_result()
        self.assertEqual(len(r.factors), 3)

    def test_first_factor_is_fi002(self):
        r = self._make_result()
        self.assertEqual(r.factors[0].factor_id, "FI-002")

    def test_second_factor_is_fi003(self):
        r = self._make_result()
        self.assertEqual(r.factors[1].factor_id, "FI-003")

    def test_third_factor_is_fi004(self):
        r = self._make_result()
        self.assertEqual(r.factors[2].factor_id, "FI-004")

    def test_to_dict_has_factors_key(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertIn("factors", d)
        self.assertEqual(len(d["factors"]), 3)

    def test_to_dict_is_json_serializable(self):
        r = self._make_result()
        d = r.to_dict()
        try:
            json.dumps(d)
        except (TypeError, ValueError) as exc:
            self.fail(f"to_dict() no serializable a JSON: {exc}")

    def test_summary_contains_fi002(self):
        r = self._make_result()
        self.assertIn("FI-002", r.summary())

    def test_summary_contains_fi003(self):
        r = self._make_result()
        self.assertIn("FI-003", r.summary())

    def test_summary_contains_fi004(self):
        r = self._make_result()
        self.assertIn("FI-004", r.summary())

    def test_warnings_and_notes_lists(self):
        r = self._make_result()
        self.assertIsInstance(r.warnings, list)
        self.assertIsInstance(r.notes, list)

    def test_notes_always_present(self):
        r = self._make_result()
        self.assertTrue(len(r.notes) > 0)


# ---------------------------------------------------------------------------
# F. TestBuildCombined
# ---------------------------------------------------------------------------

class TestBuildCombined(unittest.TestCase):

    def test_returns_three_factors(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(len(r.factors), 3)

    def test_returns_three_factors_without_plan(self):
        r = build_physical_inventory_factors_from_phase4(None, None, None)
        self.assertEqual(len(r.factors), 3)

    def test_warnings_when_all_pendiente(self):
        r = build_physical_inventory_factors_from_phase4(None, None, None)
        combined = " ".join(r.warnings)
        self.assertIn("FI-002", combined)
        self.assertIn("FI-003", combined)
        self.assertIn("FI-004", combined)

    def test_no_warnings_when_all_estimado(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        self.assertEqual(r.warnings, [])

    def test_notes_contain_iv07(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        combined = " ".join(r.notes)
        self.assertIn("IV-07", combined)

    def test_uses_embedded_plan_from_phase4(self):
        r = build_physical_inventory_factors_from_phase4(None, PHASE4_FULL, None)
        self.assertEqual(r.factors[0].evidence_status, "ESTIMADO")

    def test_fi004_alta_criticality_with_map006(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_MAP006_ONLY)
        fi004 = r.factors[2]
        self.assertEqual(fi004.gaps[0].criticality, "ALTA")


# ---------------------------------------------------------------------------
# G. TestMerge
# ---------------------------------------------------------------------------

class TestMerge(unittest.TestCase):

    def _base_summary(self):
        return build_inventory_summary("EIA-TEST", build_all_empty_factors())

    def test_merge_replaces_fi002(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        fi002 = next(f for f in new_summary.factors if f.factor_id == "FI-002")
        self.assertEqual(fi002.evidence_status, "ESTIMADO")

    def test_merge_replaces_fi003(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        fi003 = next(f for f in new_summary.factors if f.factor_id == "FI-003")
        self.assertEqual(fi003.inventory_semaphore, "AMARILLO")

    def test_merge_replaces_fi004(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        fi004 = next(f for f in new_summary.factors if f.factor_id == "FI-004")
        self.assertEqual(fi004.evidence_status, "ESTIMADO")

    def test_merge_preserves_16_factors(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        self.assertEqual(len(new_summary.factors), len(FACTOR_NAMES))

    def test_merge_no_duplicates(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_merge_canonical_order(self):
        summary = self._base_summary()
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_merge_does_not_mutate_original(self):
        summary = self._base_summary()
        orig_fi002 = next(f for f in summary.factors if f.factor_id == "FI-002")
        orig_status = orig_fi002.evidence_status
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        merge_physical_factors_into_summary(summary, r.factors)
        still_fi002 = next(f for f in summary.factors if f.factor_id == "FI-002")
        self.assertEqual(still_fi002.evidence_status, orig_status)

    def test_merge_preserves_summary_warnings(self):
        summary = self._base_summary()
        summary.warnings.append("warning previo test")
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        self.assertIn("warning previo test", new_summary.warnings)

    def test_other_factors_unchanged(self):
        summary = self._base_summary()
        fi001_before = next(f for f in summary.factors if f.factor_id == "FI-001")
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        new_summary = merge_physical_factors_into_summary(summary, r.factors)
        fi001_after = next(f for f in new_summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001_before.evidence_status, fi001_after.evidence_status)


# ---------------------------------------------------------------------------
# H. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def test_fi002_estimado_with_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi002 = next(f for f in result.factors if f.factor_id == "FI-002")
        self.assertEqual(fi002.evidence_status, "ESTIMADO")

    def test_fi003_estimado_with_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi003 = next(f for f in result.factors if f.factor_id == "FI-003")
        self.assertEqual(fi003.evidence_status, "ESTIMADO")

    def test_fi004_estimado_with_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi004 = next(f for f in result.factors if f.factor_id == "FI-004")
        self.assertEqual(fi004.evidence_status, "ESTIMADO")

    def test_fi002_pendiente_without_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_NO_PLAN)
        fi002 = next(f for f in result.factors if f.factor_id == "FI-002")
        self.assertEqual(fi002.evidence_status, "PENDIENTE")

    def test_fi004_gap_alta_with_map006(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP006)
        fi004 = next(f for f in result.factors if f.factor_id == "FI-004")
        self.assertEqual(fi004.gaps[0].criticality, "ALTA")

    def test_fi001_still_enriched(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_result_has_16_factors(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        self.assertEqual(len(result.factors), len(FACTOR_NAMES))

    def test_no_duplicate_factor_ids(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_canonical_order(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_fi002_gap_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi002 = next(f for f in result.factors if f.factor_id == "FI-002")
        self.assertIn("GAP-FI-002-001", [g.gap_id for g in fi002.gaps])

    def test_fi003_gap_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi003 = next(f for f in result.factors if f.factor_id == "FI-003")
        self.assertIn("GAP-FI-003-001", [g.gap_id for g in fi003.gaps])

    def test_fi004_gap_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        fi004 = next(f for f in result.factors if f.factor_id == "FI-004")
        self.assertIn("GAP-FI-004-001", [g.gap_id for g in fi004.gaps])

    def test_notes_contain_iv07(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        combined = " ".join(result.notes)
        self.assertIn("IV-07", combined)

    def test_all_ready_false(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_FULL)
        for fid in ["FI-002", "FI-003", "FI-004"]:
            fi = next(f for f in result.factors if f.factor_id == fid)
            self.assertFalse(fi.ready_for_impact_assessment, fid)


# ---------------------------------------------------------------------------
# I. TestPrudenceLexical
# ---------------------------------------------------------------------------

_FORBIDDEN = [
    "geologia sin interes",
    "geología sin interés",
    "sin afeccion geologica",
    "sin afección geológica",
    "terreno estable",
    "suelo sin afeccion",
    "suelo sin afección",
    "sin contaminacion",
    "sin contaminación",
    "suelo impermeabilizado",
    "no hay cauces",
    "sin escorrentia",
    "sin escorrentía",
    "sin conectividad hidrica",
    "sin conectividad hídrica",
    "sin afeccion hidrologica",
    "sin afección hidrológica",
]


class TestPrudenceLexical(unittest.TestCase):

    def _all_texts(self, plan):
        r = build_physical_inventory_factors_from_phase4(None, None, plan)
        texts = []
        for f in r.factors:
            texts.append(f.description.lower())
            for g in f.gaps:
                texts.append(g.description.lower())
        return texts

    def _check_no_forbidden(self, plan, label):
        texts = self._all_texts(plan)
        for text in texts:
            for pat in _FORBIDDEN:
                self.assertNotIn(pat, text, f"Patron prohibido '{pat}' en {label}: {text[:120]}")

    def test_no_forbidden_full_plan(self):
        self._check_no_forbidden(CART_PLAN_FULL, "CART_PLAN_FULL")

    def test_no_forbidden_map006_only(self):
        self._check_no_forbidden(CART_PLAN_MAP006_ONLY, "CART_PLAN_MAP006_ONLY")

    def test_no_forbidden_base_only(self):
        self._check_no_forbidden(CART_PLAN_BASE_ONLY, "CART_PLAN_BASE_ONLY")

    def test_no_forbidden_none(self):
        self._check_no_forbidden(None, "None")

    def test_fi002_description_mentions_gabinete_or_oficial(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        fi002 = r.factors[0]
        desc = fi002.description.lower()
        self.assertTrue("gabinete" in desc or "oficial" in desc)

    def test_fi003_description_mentions_inspeccion_or_oficial(self):
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        fi003 = r.factors[1]
        desc = fi003.description.lower()
        self.assertTrue("inspecci" in desc or "oficial" in desc)

    def test_fi004_description_mentions_cauces_or_escorrentia(self):
        # La descripcion DEBE mencionar cauces/barrancos/escorrentia (como objeto de verificacion)
        r = build_physical_inventory_factors_from_phase4(None, None, CART_PLAN_FULL)
        fi004 = r.factors[2]
        desc = fi004.description.lower()
        self.assertTrue("cauce" in desc or "barranco" in desc or "drenaje" in desc)

    def test_no_impact_valuation_terms(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_MAP006_ONLY, None]:
            r = build_physical_inventory_factors_from_phase4(None, None, plan)
            for f in r.factors:
                desc = f.description.lower()
                self.assertNotIn("moderado", desc)
                self.assertNotIn("severo", desc)
                self.assertNotIn("critico", desc)

    def test_no_verde_in_any_plan(self):
        for plan in [CART_PLAN_FULL, CART_PLAN_MAP006_ONLY, CART_PLAN_BASE_ONLY, None]:
            r = build_physical_inventory_factors_from_phase4(None, None, plan)
            for f in r.factors:
                self.assertNotEqual(f.inventory_semaphore, "VERDE")


if __name__ == "__main__":
    unittest.main()
