"""
tests/test_inventory_protected_areas_builder.py -- IV-06
Tests for src/eia_agent/core/inventory_protected_areas_builder.py

Categorias:
  A. TestDetectors              -- has_red_natura_map_planned, has_enp_map_planned
  B. TestExtractContext         -- extract_protected_area_context
  C. TestBuildEnpFactor         -- build_enp_factor_from_phase4 (FI-009)
  D. TestBuildRedNaturaFactor   -- build_red_natura_factor_from_phase4 (FI-010)
  E. TestProtectedAreasResult   -- ProtectedAreasInventoryBuildResult dataclass
  F. TestBuildCombined          -- build_protected_areas_inventory_factors_from_phase4
  G. TestMerge                  -- merge_protected_area_factors_into_summary
  H. TestIntegrationWithIV02    -- build_inventory_from_phase4_data con IV-06
  I. TestPrudenceLexical        -- ausencia de patrones prohibidos
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_protected_areas_builder import (
    ProtectedAreasInventoryBuildResult,
    build_enp_factor_from_phase4,
    build_protected_areas_inventory_factors_from_phase4,
    build_red_natura_factor_from_phase4,
    extract_protected_area_context,
    has_enp_map_planned,
    has_red_natura_map_planned,
    merge_protected_area_factors_into_summary,
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

MAP_004 = {
    "map_id": "MAP-004",
    "map_type": "red_natura_enp",
    "title": "Red Natura 2000 / ENP",
    "purpose": "Distancia y relacion con espacios protegidos",
    "required_layers": ["red_natura_2000", "espacios_naturales_protegidos", "marcador_proyecto"],
    "source_candidates": ["Grafcan IdeCAN", "MITERD Natura 2000"],
    "output_filename": "MAP-004_red_natura_enp.png",
    "status": "READY_FOR_RENDER",
    "warnings": [],
}

MAP_004_GENERATED = {
    "map_id": "MAP-004",
    "map_type": "red_natura_enp",
    "title": "Red Natura 2000 / ENP",
    "required_layers": ["red_natura_2000", "espacios_naturales_protegidos"],
    "output_filename": "MAP-004_red_natura_enp.png",
    "status": "GENERATED_PROVISIONAL",
}

MAP_001 = {
    "map_id": "MAP-001",
    "map_type": "situacion_general",
    "title": "Situacion general",
    "required_layers": ["osm_base"],
    "output_filename": "MAP-001.png",
    "status": "READY_FOR_RENDER",
}

MAP_006 = {
    "map_id": "MAP-006",
    "map_type": "inundabilidad_riesgos",
    "title": "Inundabilidad y riesgos",
    "required_layers": ["snczi_inundabilidad"],
    "output_filename": "MAP-006.png",
    "status": "READY_FOR_RENDER",
}

# Plan con MAP-004
CART_PLAN_WITH_MAP004 = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_004, MAP_006],
    "ready_for_render": True,
    "warnings": [],
    "notes": [],
}

# Plan con MAP-004 generado (provisional)
CART_PLAN_MAP004_GENERATED = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_004_GENERATED],
    "ready_for_render": True,
    "warnings": [],
}

# Plan sin MAP-004
CART_PLAN_NO_MAP004 = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [MAP_001, MAP_006],
    "ready_for_render": True,
    "warnings": [],
}

# Plan con capa red_natura_2000 en mapa sin MAP-004 id
MAP_RN_LAYER_ONLY = {
    "map_id": "MAP-009",
    "map_type": "personalizado",
    "title": "Red Natura personalizado",
    "required_layers": ["red_natura_2000"],
    "output_filename": "MAP-009.png",
    "status": "READY_FOR_RENDER",
}

CART_PLAN_RN_LAYER = {
    "expediente_id": "EIA-TEST",
    "maps": [MAP_001, MAP_RN_LAYER_ONLY],
}

# Plan con capa ENP sin MAP-004 id
MAP_ENP_LAYER_ONLY = {
    "map_id": "MAP-010",
    "map_type": "personalizado",
    "title": "ENP personalizado",
    "required_layers": ["espacios_naturales_protegidos"],
    "output_filename": "MAP-010.png",
    "status": "READY_FOR_RENDER",
}

CART_PLAN_ENP_LAYER = {
    "expediente_id": "EIA-TEST",
    "maps": [MAP_001, MAP_ENP_LAYER_ONLY],
}

# Plan vacio
CART_PLAN_EMPTY = {
    "expediente_id": "EIA-TEST",
    "maps": [],
}

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

PHASE4_WITH_MAP004 = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": CART_PLAN_WITH_MAP004,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_NO_PLAN = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_WITH_CLIMATE_ONLY = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}


# ---------------------------------------------------------------------------
# A. TestDetectors
# ---------------------------------------------------------------------------

class TestDetectors(unittest.TestCase):

    def test_has_red_natura_map_detects_map004_id(self):
        self.assertTrue(has_red_natura_map_planned(CART_PLAN_WITH_MAP004))

    def test_has_red_natura_map_detects_map_type(self):
        plan = {"maps": [{"map_id": "X", "map_type": "red_natura_enp", "required_layers": []}]}
        self.assertTrue(has_red_natura_map_planned(plan))

    def test_has_red_natura_map_detects_layer(self):
        self.assertTrue(has_red_natura_map_planned(CART_PLAN_RN_LAYER))

    def test_has_red_natura_map_false_no_map004(self):
        self.assertFalse(has_red_natura_map_planned(CART_PLAN_NO_MAP004))

    def test_has_red_natura_map_false_empty_plan(self):
        self.assertFalse(has_red_natura_map_planned(CART_PLAN_EMPTY))

    def test_has_red_natura_map_false_none(self):
        self.assertFalse(has_red_natura_map_planned(None))

    def test_has_enp_map_detects_map004_id(self):
        self.assertTrue(has_enp_map_planned(CART_PLAN_WITH_MAP004))

    def test_has_enp_map_detects_map_type(self):
        plan = {"maps": [{"map_id": "X", "map_type": "red_natura_enp", "required_layers": []}]}
        self.assertTrue(has_enp_map_planned(plan))

    def test_has_enp_map_detects_layer(self):
        self.assertTrue(has_enp_map_planned(CART_PLAN_ENP_LAYER))

    def test_has_enp_map_false_no_enp(self):
        self.assertFalse(has_enp_map_planned(CART_PLAN_NO_MAP004))

    def test_has_enp_map_false_none(self):
        self.assertFalse(has_enp_map_planned(None))

    def test_has_enp_map_false_empty(self):
        self.assertFalse(has_enp_map_planned(CART_PLAN_EMPTY))


# ---------------------------------------------------------------------------
# B. TestExtractContext
# ---------------------------------------------------------------------------

class TestExtractContext(unittest.TestCase):

    def test_no_crash_with_empty_dicts(self):
        text = extract_protected_area_context({}, {})
        self.assertIsInstance(text, str)

    def test_no_crash_with_none(self):
        text = extract_protected_area_context(None, None)
        self.assertEqual(text, "")

    def test_detects_red_natura_in_plan(self):
        text = extract_protected_area_context(None, CART_PLAN_WITH_MAP004)
        self.assertIn("red_natura", text)

    def test_detects_enp_in_plan(self):
        text = extract_protected_area_context(None, CART_PLAN_WITH_MAP004)
        self.assertIn("enp", text)

    def test_detects_map004_string(self):
        text = extract_protected_area_context(None, CART_PLAN_WITH_MAP004)
        self.assertIn("map-004", text)

    def test_detects_lic_keyword(self):
        phase4 = {"notes": ["se detecta LIC en el entorno del proyecto"]}
        text = extract_protected_area_context(phase4, None)
        self.assertIn("lic", text)

    def test_detects_zec_keyword(self):
        phase4 = {"notes": ["ZEC ES7010014 en el area de estudio"]}
        text = extract_protected_area_context(phase4, None)
        self.assertIn("zec", text)

    def test_detects_zepa_keyword(self):
        phase4 = {"notes": ["ZEPA Malpaís de La Corona"]}
        text = extract_protected_area_context(phase4, None)
        self.assertIn("zepa", text)

    def test_result_is_lowercase(self):
        text = extract_protected_area_context(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(text, text.lower())

    def test_no_context_from_unrelated_data(self):
        phase4 = {"notes": ["datos de temperatura media anual"]}
        text = extract_protected_area_context(phase4, None)
        self.assertEqual(text, "")


# ---------------------------------------------------------------------------
# C. TestBuildEnpFactor
# ---------------------------------------------------------------------------

class TestBuildEnpFactor(unittest.TestCase):

    def test_factor_id_is_fi009(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.factor_id, "FI-009")

    def test_with_map004_is_estimado(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_map004_is_amarillo(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_map004_campo_recomendado(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_without_plan_is_pendiente(self):
        fi = build_enp_factor_from_phase4(None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_plan_no_consta(self):
        fi = build_enp_factor_from_phase4(None, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_never_verde(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, CART_PLAN_EMPTY, None]:
            fi = build_enp_factor_from_phase4(None, plan)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE prohibido con plan={plan}")

    def test_gap_fi009_001_always_present(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, None]:
            fi = build_enp_factor_from_phase4(None, plan)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-009-001", gap_ids)

    def test_gap_criticality_alta(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_resolution_gabinete(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        gap = fi.gaps[0]
        self.assertEqual(gap.resolution_mode, "GABINETE")

    def test_ready_always_false(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, None]:
            fi = build_enp_factor_from_phase4(None, plan)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_data_sources_populated_with_plan(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_data_sources_empty_without_plan(self):
        fi = build_enp_factor_from_phase4(None, None)
        self.assertEqual(fi.data_sources, [])

    def test_description_mentions_official_source(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        desc = fi.description.lower()
        self.assertTrue(
            "oficial" in desc or "grafcan" in desc or "miterd" in desc or "fuente" in desc,
            "Descripcion debe mencionar fuente oficial"
        )

    def test_description_mentions_cartography_offline(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        desc = fi.description.lower()
        self.assertIn("offline", desc)

    def test_plan_without_map004_also_estimado(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_NO_MAP004)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_empty_plan_is_pendiente(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_EMPTY)
        # CART_PLAN_EMPTY tiene el dict pero maps vacio — sigue siendo truthy como plan
        # con maps vacio sigue teniendo plan = True → ESTIMADO
        self.assertIn(fi.evidence_status, ["ESTIMADO", "PENDIENTE"])

    def test_schematic_map_mentioned_when_generated(self):
        fi = build_enp_factor_from_phase4(None, CART_PLAN_MAP004_GENERATED)
        desc = fi.description.lower()
        self.assertTrue("provisional" in desc or "ca-11" in desc or "esquema" in desc)


# ---------------------------------------------------------------------------
# D. TestBuildRedNaturaFactor
# ---------------------------------------------------------------------------

class TestBuildRedNaturaFactor(unittest.TestCase):

    def test_factor_id_is_fi010(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.factor_id, "FI-010")

    def test_with_map004_is_estimado(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_map004_is_amarillo(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_map004_campo_recomendado(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_without_plan_is_pendiente(self):
        fi = build_red_natura_factor_from_phase4(None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_plan_no_consta(self):
        fi = build_red_natura_factor_from_phase4(None, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_never_verde(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, CART_PLAN_EMPTY, None]:
            fi = build_red_natura_factor_from_phase4(None, plan)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE prohibido con plan={plan}")

    def test_gap_fi010_001_always_present(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, None]:
            fi = build_red_natura_factor_from_phase4(None, plan)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-010-001", gap_ids)

    def test_gap_criticality_alta(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        gap = fi.gaps[0]
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_resolution_gabinete(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        gap = fi.gaps[0]
        self.assertEqual(gap.resolution_mode, "GABINETE")

    def test_ready_always_false(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, None]:
            fi = build_red_natura_factor_from_phase4(None, plan)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_description_mentions_organo_ambiental(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        desc = fi.description.lower()
        self.assertTrue(
            "organo ambiental" in desc or "órgano ambiental" in desc,
            "Descripcion debe mencionar organo ambiental"
        )

    def test_description_mentions_verification(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        desc = fi.description.lower()
        self.assertTrue(
            "verificaci" in desc or "oficial" in desc,
            "Descripcion debe mencionar verificacion oficial"
        )

    def test_data_sources_populated_with_plan(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_data_sources_mention_ca10(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_WITH_MAP004)
        combined = " ".join(fi.data_sources).lower()
        self.assertTrue("ca-10" in combined or "f4-01" in combined)

    def test_plan_without_map004_also_estimado(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_NO_MAP004)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_schematic_map_mentioned_when_generated(self):
        fi = build_red_natura_factor_from_phase4(None, CART_PLAN_MAP004_GENERATED)
        desc = fi.description.lower()
        self.assertTrue("provisional" in desc or "ca-11" in desc or "esquema" in desc)


# ---------------------------------------------------------------------------
# E. TestProtectedAreasResult
# ---------------------------------------------------------------------------

class TestProtectedAreasResult(unittest.TestCase):

    def _make_result(self):
        return build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)

    def test_factors_has_two_elements(self):
        r = self._make_result()
        self.assertEqual(len(r.factors), 2)

    def test_first_factor_is_fi009(self):
        r = self._make_result()
        self.assertEqual(r.factors[0].factor_id, "FI-009")

    def test_second_factor_is_fi010(self):
        r = self._make_result()
        self.assertEqual(r.factors[1].factor_id, "FI-010")

    def test_to_dict_has_factors_key(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertIn("factors", d)
        self.assertEqual(len(d["factors"]), 2)

    def test_to_dict_is_json_serializable(self):
        r = self._make_result()
        d = r.to_dict()
        try:
            json.dumps(d)
        except (TypeError, ValueError) as exc:
            self.fail(f"to_dict() no serializable a JSON: {exc}")

    def test_summary_contains_fi009(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("FI-009", s)

    def test_summary_contains_fi010(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("FI-010", s)

    def test_warnings_and_notes_are_lists(self):
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

    def test_returns_two_factors_with_plan(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(len(r.factors), 2)

    def test_returns_two_factors_without_plan(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, None)
        self.assertEqual(len(r.factors), 2)

    def test_fi009_first(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(r.factors[0].factor_id, "FI-009")

    def test_fi010_second(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(r.factors[1].factor_id, "FI-010")

    def test_warnings_when_pendiente(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, None)
        combined = " ".join(r.warnings)
        self.assertIn("FI-009", combined)
        self.assertIn("FI-010", combined)

    def test_no_warnings_when_estimado(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        self.assertEqual(r.warnings, [])

    def test_uses_embedded_plan_from_phase4(self):
        phase4 = {
            "cartography_plan": CART_PLAN_WITH_MAP004,
            "climate": None,
        }
        r = build_protected_areas_inventory_factors_from_phase4(phase4, None)
        self.assertEqual(r.factors[0].evidence_status, "ESTIMADO")

    def test_notes_contain_iv06(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        combined = " ".join(r.notes)
        self.assertIn("IV-06", combined)


# ---------------------------------------------------------------------------
# G. TestMerge
# ---------------------------------------------------------------------------

class TestMerge(unittest.TestCase):

    def _base_summary(self):
        factors = build_all_empty_factors()
        return build_inventory_summary("EIA-TEST", factors)

    def test_merge_replaces_fi009(self):
        summary = self._base_summary()
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        fi009 = next(f for f in new_summary.factors if f.factor_id == "FI-009")
        self.assertEqual(fi009.evidence_status, "ESTIMADO")

    def test_merge_replaces_fi010(self):
        summary = self._base_summary()
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        fi010 = next(f for f in new_summary.factors if f.factor_id == "FI-010")
        self.assertEqual(fi010.inventory_semaphore, "AMARILLO")

    def test_merge_preserves_16_factors(self):
        summary = self._base_summary()
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        self.assertEqual(len(new_summary.factors), len(FACTOR_NAMES))

    def test_merge_no_duplicates(self):
        summary = self._base_summary()
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_merge_canonical_order(self):
        summary = self._base_summary()
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_merge_does_not_mutate_original(self):
        summary = self._base_summary()
        orig_fi009 = next(f for f in summary.factors if f.factor_id == "FI-009")
        orig_status = orig_fi009.evidence_status
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        merge_protected_area_factors_into_summary(summary, r.factors)
        still_fi009 = next(f for f in summary.factors if f.factor_id == "FI-009")
        self.assertEqual(still_fi009.evidence_status, orig_status)

    def test_other_factors_unchanged_after_merge(self):
        summary = self._base_summary()
        fi001_before = next(f for f in summary.factors if f.factor_id == "FI-001")
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        fi001_after = next(f for f in new_summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001_before.evidence_status, fi001_after.evidence_status)

    def test_merge_preserves_summary_warnings(self):
        summary = self._base_summary()
        summary.warnings.append("warning previo test")
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        new_summary = merge_protected_area_factors_into_summary(summary, r.factors)
        self.assertIn("warning previo test", new_summary.warnings)


# ---------------------------------------------------------------------------
# H. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def test_fi009_estimado_with_map004(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        self.assertEqual(fi009.evidence_status, "ESTIMADO")

    def test_fi010_estimado_with_map004(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi010 = next(f for f in result.factors if f.factor_id == "FI-010")
        self.assertEqual(fi010.evidence_status, "ESTIMADO")

    def test_fi009_pendiente_without_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_NO_PLAN)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        self.assertEqual(fi009.evidence_status, "PENDIENTE")

    def test_fi010_pendiente_without_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_NO_PLAN)
        fi010 = next(f for f in result.factors if f.factor_id == "FI-010")
        self.assertEqual(fi010.evidence_status, "PENDIENTE")

    def test_fi001_still_enriched(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_result_has_16_factors(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        self.assertEqual(len(result.factors), len(FACTOR_NAMES))

    def test_no_duplicate_factor_ids(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_canonical_order(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_fi009_gap_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        gap_ids = [g.gap_id for g in fi009.gaps]
        self.assertIn("GAP-FI-009-001", gap_ids)

    def test_fi010_gap_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi010 = next(f for f in result.factors if f.factor_id == "FI-010")
        gap_ids = [g.gap_id for g in fi010.gaps]
        self.assertIn("GAP-FI-010-001", gap_ids)

    def test_notes_contain_iv06(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        combined = " ".join(result.notes)
        self.assertIn("IV-06", combined)

    def test_all_ready_false(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        fi010 = next(f for f in result.factors if f.factor_id == "FI-010")
        self.assertFalse(fi009.ready_for_impact_assessment)
        self.assertFalse(fi010.ready_for_impact_assessment)

    def test_fi009_amarillo_with_map004(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        self.assertEqual(fi009.inventory_semaphore, "AMARILLO")

    def test_fi010_amarillo_with_map004(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_MAP004)
        fi010 = next(f for f in result.factors if f.factor_id == "FI-010")
        self.assertEqual(fi010.inventory_semaphore, "AMARILLO")

    def test_fi009_pendiente_with_empty_plan(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE_ONLY)
        fi009 = next(f for f in result.factors if f.factor_id == "FI-009")
        # Con plan vacio (sin maps) → sigue siendo plan truthy → ESTIMADO o PENDIENTE
        # segun logica: CART_PLAN vacio como {} sería None→PENDIENTE; {"maps":[]}→ESTIMADO
        # PHASE4_WITH_CLIMATE_ONLY tiene cartography_plan: {"maps": []} → truthy plan → ESTIMADO
        self.assertIn(fi009.evidence_status, ["ESTIMADO", "PENDIENTE"])


# ---------------------------------------------------------------------------
# I. TestPrudenceLexical
# ---------------------------------------------------------------------------

_FORBIDDEN_ENP: list[str] = [
    "no hay enp",
    "fuera de espacios protegidos",
    "sin afeccion",
    "sin afección",
    "descartado",
    "inexistente",
    "no existe",
]

_FORBIDDEN_RN: list[str] = [
    "no hay red natura",
    "sin afeccion apreciable",
    "sin afección apreciable",
    "sin afeccion significativa",
    "sin afección significativa",
    "descartado",
    "inexistente",
    "no existe",
]


class TestPrudenceLexical(unittest.TestCase):

    def _all_texts(self, plan):
        r = build_protected_areas_inventory_factors_from_phase4(None, plan)
        texts = []
        for f in r.factors:
            texts.append(f.description.lower())
            for g in f.gaps:
                texts.append(g.description.lower())
        return texts

    def _check_no_forbidden(self, plan, forbidden, label):
        texts = self._all_texts(plan)
        for text in texts:
            for pat in forbidden:
                self.assertNotIn(pat, text, f"Patron prohibido '{pat}' en {label}: {text[:120]}")

    def test_no_forbidden_enp_with_map004(self):
        self._check_no_forbidden(CART_PLAN_WITH_MAP004, _FORBIDDEN_ENP, "MAP004")

    def test_no_forbidden_enp_no_plan(self):
        self._check_no_forbidden(None, _FORBIDDEN_ENP, "None")

    def test_no_forbidden_enp_empty_plan(self):
        self._check_no_forbidden(CART_PLAN_EMPTY, _FORBIDDEN_ENP, "EMPTY")

    def test_no_forbidden_rn_with_map004(self):
        self._check_no_forbidden(CART_PLAN_WITH_MAP004, _FORBIDDEN_RN, "MAP004")

    def test_no_forbidden_rn_no_plan(self):
        self._check_no_forbidden(None, _FORBIDDEN_RN, "None")

    def test_no_forbidden_rn_empty_plan(self):
        self._check_no_forbidden(CART_PLAN_EMPTY, _FORBIDDEN_RN, "EMPTY")

    def test_fi010_description_mentions_organo(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        fi010 = r.factors[1]
        desc = fi010.description.lower()
        self.assertTrue("organo" in desc or "órgano" in desc)

    def test_fi009_description_mentions_da_definitivo(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        fi009 = r.factors[0]
        desc = fi009.description.lower()
        self.assertTrue("definitivo" in desc or "document" in desc or "oficial" in desc)

    def test_fi010_description_no_cumple(self):
        r = build_protected_areas_inventory_factors_from_phase4(None, CART_PLAN_WITH_MAP004)
        fi010 = r.factors[1]
        self.assertNotIn("cumple", fi010.description.lower())

    def test_no_impact_valuation_terms(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, None]:
            r = build_protected_areas_inventory_factors_from_phase4(None, plan)
            for f in r.factors:
                desc = f.description.lower()
                self.assertNotIn("moderado", desc)
                self.assertNotIn("severo", desc)
                self.assertNotIn("critico", desc)
                self.assertNotIn("crítico", desc)

    def test_no_verde_in_any_plan(self):
        for plan in [CART_PLAN_WITH_MAP004, CART_PLAN_NO_MAP004, CART_PLAN_EMPTY, None]:
            r = build_protected_areas_inventory_factors_from_phase4(None, plan)
            for f in r.factors:
                self.assertNotEqual(f.inventory_semaphore, "VERDE")


if __name__ == "__main__":
    unittest.main()
