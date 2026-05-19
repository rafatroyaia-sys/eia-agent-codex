"""
tests/test_inventory_context_builder.py -- IV-04
Tests for src/eia_agent/core/inventory_context_builder.py

Categorias:
  A. TestBuildLandscapeFactor       -- build_landscape_factor_from_phase_data (FI-011)
  B. TestBuildSocioeconomicFactor   -- build_socioeconomic_factor_from_phase_data (FI-013)
  C. TestContextInventoryBuildResult -- dataclass to_dict / summary
  D. TestBuildContextInventory      -- build_context_inventory_factors_from_phase_data
  E. TestMergeContextFactors        -- merge_context_factors_into_summary
  F. TestIntegrationWithIV02        -- build_inventory_from_phase4_data con IV-04
  G. TestPrudenceLexical            -- ausencia de patrones prohibidos en descripciones
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_context_builder import (
    ContextInventoryBuildResult,
    build_context_inventory_factors_from_phase_data,
    build_landscape_factor_from_phase_data,
    build_socioeconomic_factor_from_phase_data,
    merge_context_factors_into_summary,
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
        "koppen_label": "Arido desertico calido",
        "martonne_index": 4.18,
        "martonne_label": "Arido extremo",
        "dry_months_gaussen": 12,
        "dry_months_names": [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ],
        "annual_temperature_c": 21.36,
        "annual_precipitation_mm": 131.0,
        "notes": [],
    },
    "warnings": [],
    "notes": [],
}

OTRO_MAP = {
    "map_id": "MAP-001",
    "map_type": "situacion_general",
    "title": "Situacion general",
    "purpose": "Mapa de situacion",
    "required_layers": ["osm_base"],
    "source_candidates": ["OpenStreetMap"],
    "output_filename": "MAP-001_situacion_general.png",
    "status": "READY_FOR_RENDER",
    "warnings": [],
}

MAP_WITH_SCHEMATIC = {
    "map_id": "MAP-005",
    "map_type": "usos_suelo",
    "title": "Usos del suelo entorno",
    "purpose": "Usos del suelo",
    "required_layers": ["corine_land_cover"],
    "source_candidates": ["Copernicus CLC"],
    "output_filename": "MAP-005_usos_suelo_entorno.png",
    "status": "READY_FOR_RENDER",
    "warnings": [],
}

CART_PLAN_WITH_MAPS = {
    "expediente_id": "EIA-2026-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [OTRO_MAP, MAP_WITH_SCHEMATIC],
    "ready_for_render": True,
    "warnings": [],
    "notes": [],
}

CART_PLAN_EMPTY_MAPS = {
    "expediente_id": "EIA-2026-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [],
    "ready_for_render": True,
    "warnings": [],
}

CART_PLAN_NO_CENTER = {
    "expediente_id": "EIA-2026-TEST",
    "maps": [OTRO_MAP],
}

PHASE4_FULL = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": CART_PLAN_WITH_MAPS,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_NO_PLAN = {
    "expediente_id": "EIA-2026-TEST",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_CLIMATE_ONLY = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_WITH_EMBEDDED_EMPTY_PLAN = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE2_FULL = {
    "expediente_id": "EIA-2026-TEST",
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "referencia_catastral": "35016A02100041",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "coordenadas_utm": ["UTM 28N 617234 3207456"],
        "operaciones_incluidas": ["R12 - almacenamiento", "R13 - tratamiento previo"],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "superficie_m2": "2500",
        "capacidad": None,
        "at_activos": [],
        "gaps": [],
    },
    "gate2_passed": True,
    "gate2_summary": "APTO",
    "issues": [],
    "warnings": [],
    "notes": [],
}

PHASE2_NO_PROMOTER = {
    "expediente_id": "EIA-2026-TEST",
    "object_scope": {
        "titular": None,
        "referencia_catastral": "35016A02100041",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "coordenadas_utm": [],
        "operaciones_incluidas": ["R12 - almacenamiento"],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "superficie_m2": None,
        "capacidad": None,
        "at_activos": [],
        "gaps": [],
    },
    "gate2_passed": False,
    "issues": [],
    "warnings": [],
    "notes": [],
}

PHASE2_NO_ACTIVITY = {
    "expediente_id": "EIA-2026-TEST",
    "object_scope": {
        "titular": "EMPRESA TEST S.A.",
        "referencia_catastral": None,
        "coordenadas_wgs84": [],
        "coordenadas_utm": [],
        "operaciones_incluidas": [],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "superficie_m2": None,
        "capacidad": None,
        "at_activos": [],
        "gaps": [],
    },
    "gate2_passed": False,
    "issues": [],
    "warnings": [],
    "notes": [],
}

PHASE2_MINIMAL_COORDS = {
    "expediente_id": "EIA-2026-TEST",
    "object_scope": {
        "titular": "PROMOTOR TEST S.L.",
        "referencia_catastral": None,
        "coordenadas_wgs84": [],
        "coordenadas_utm": [],
        "operaciones_incluidas": ["R12 - almacenamiento"],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "superficie_m2": None,
        "capacidad": None,
        "at_activos": [],
        "gaps": [],
    },
    "gate2_passed": False,
    "issues": [],
    "warnings": [],
    "notes": [],
}

# Fixture reutilizado del test de IV-02
PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}


# ---------------------------------------------------------------------------
# A. TestBuildLandscapeFactor (FI-011)
# ---------------------------------------------------------------------------

class TestBuildLandscapeFactor(unittest.TestCase):

    # --- Caso completo: coords + plan ---

    def test_with_coords_and_plan_returns_estimado(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_coords_and_plan_returns_campo_recomendado(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_with_coords_and_plan_returns_amarillo(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_with_coords_and_plan_ready_false(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertFalse(fi.ready_for_impact_assessment)

    # --- Caso parcial: solo coords ---

    def test_with_coords_no_plan_returns_estimado(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_CLIMATE_ONLY)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_with_coords_no_plan_returns_no_consta_semaphore(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_CLIMATE_ONLY)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_with_coords_no_plan_returns_campo_recomendado(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_CLIMATE_ONLY)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    # --- Caso sin datos ---

    def test_no_data_returns_pendiente(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_no_data_returns_no_consta_semaphore(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_no_data_ready_false(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertFalse(fi.ready_for_impact_assessment)

    # --- Gap obligatorio ---

    def test_always_has_gap_fi011_001(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-011-001", gap_ids)

    def test_gap_fi011_criticality_media(self):
        fi = build_landscape_factor_from_phase_data()
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-011-001")
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_fi011_resolution_campo(self):
        fi = build_landscape_factor_from_phase_data()
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-011-001")
        self.assertEqual(gap.resolution_mode, "CAMPO")

    def test_gap_fi011_status_pendiente(self):
        fi = build_landscape_factor_from_phase_data()
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-011-001")
        self.assertEqual(gap.status, "PENDIENTE")

    def test_gap_present_also_when_no_data(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertTrue(any(g.gap_id == "GAP-FI-011-001" for g in fi.gaps))

    # --- Semaforo nunca VERDE ---

    def test_never_verde_with_full_data(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    def test_never_verde_verde_amarillo(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertNotEqual(fi.inventory_semaphore, "VERDE_AMARILLO")

    def test_never_verde_with_no_data(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    # --- factor_id ---

    def test_factor_id_is_fi011(self):
        fi = build_landscape_factor_from_phase_data()
        self.assertEqual(fi.factor_id, "FI-011")

    # --- Description ---

    def test_description_mentions_gabinete(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertIn("gabinete", fi.description.lower())

    def test_description_not_empty_with_data(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        self.assertTrue(len(fi.description) > 50)

    # --- Data sources ---

    def test_data_sources_has_ca10_when_plan(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        combined = " ".join(fi.data_sources)
        self.assertIn("CA-10", combined)

    def test_data_sources_has_f401_when_phase4(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        combined = " ".join(fi.data_sources)
        self.assertIn("F4-01", combined)

    def test_data_sources_has_phase2_when_phase2(self):
        fi = build_landscape_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        combined = " ".join(fi.data_sources)
        self.assertIn("OB-06", combined)

    def test_data_sources_has_ca11_when_maps_in_plan(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        combined = " ".join(fi.data_sources)
        self.assertIn("CA-11", combined)

    def test_data_sources_no_ca11_when_empty_maps(self):
        fi = build_landscape_factor_from_phase_data(
            cartography_plan=CART_PLAN_EMPTY_MAPS
        )
        combined = " ".join(fi.data_sources)
        self.assertNotIn("CA-11", combined)

    # --- Fixture compatible con IV-02 ---

    def test_phase4_with_embedded_empty_plan_returns_estimado(self):
        # Plan embebido {"maps": []} es truthy; coords via estacion climatica
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_WITH_EMBEDDED_EMPTY_PLAN
        )
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_phase4_with_embedded_empty_plan_returns_amarillo(self):
        fi = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_WITH_EMBEDDED_EMPTY_PLAN
        )
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")


# ---------------------------------------------------------------------------
# B. TestBuildSocioeconomicFactor (FI-013)
# ---------------------------------------------------------------------------

class TestBuildSocioeconomicFactor(unittest.TestCase):

    # --- Caso completo: promotor + actividad + ubicacion ---

    def test_with_full_phase2_returns_declarado(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertEqual(fi.evidence_status, "DECLARADO")

    def test_with_full_phase2_returns_gabinete(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertEqual(fi.field_mode, "GABINETE_SUFICIENTE")

    def test_with_full_phase2_ready_true(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertTrue(fi.ready_for_impact_assessment)

    def test_with_full_phase2_returns_amarillo(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    # --- Caso sin ubicacion: promotor + actividad sin coords ---

    def test_with_promoter_activity_no_coords_not_ready(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_MINIMAL_COORDS
        )
        # sin coordenadas en phase2 ni en phase4 → no ready
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_with_promoter_activity_no_coords_field_no_consta(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_MINIMAL_COORDS
        )
        self.assertEqual(fi.field_mode, "NO_CONSTA")

    def test_with_promoter_activity_via_phase4_coords_ready(self):
        # Fase 4 con estacion climatica provee ubicacion → ready = True
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_MINIMAL_COORDS, phase4_result=PHASE4_CLIMATE_ONLY
        )
        self.assertTrue(fi.ready_for_impact_assessment)

    # --- Caso sin promotor ---

    def test_no_promoter_returns_pendiente(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_PROMOTER)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_no_promoter_returns_no_consta_semaphore(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_PROMOTER)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_no_promoter_not_ready(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_PROMOTER)
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_no_promoter_has_gap_fi013_002(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_PROMOTER)
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-013-002", gap_ids)

    # --- Caso sin actividad ---

    def test_no_activity_returns_pendiente(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_ACTIVITY)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_no_activity_has_gap_fi013_002(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_ACTIVITY)
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-013-002", gap_ids)

    # --- Gap obligatorio GAP-FI-013-001 (siempre presente) ---

    def test_always_has_gap_fi013_001(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-013-001", gap_ids)

    def test_gap_fi013_001_criticality_media(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-013-001")
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_fi013_001_always_present_even_when_no_data(self):
        fi = build_socioeconomic_factor_from_phase_data()
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-013-001", gap_ids)

    def test_no_gap_fi013_002_when_promoter_and_activity(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertNotIn("GAP-FI-013-002", gap_ids)

    def test_gap_fi013_002_criticality_alta(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_NO_PROMOTER)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-013-002")
        self.assertEqual(gap.criticality, "ALTA")

    # --- factor_id ---

    def test_factor_id_is_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data()
        self.assertEqual(fi.factor_id, "FI-013")

    # --- Description ---

    def test_description_includes_promoter_name(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertIn("RECIMETAL", fi.description)

    def test_description_includes_operations(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertIn("R12", fi.description)

    def test_description_mentions_socioeconomia(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertIn("socioeconom", fi.description.lower())

    # --- Data sources ---

    def test_data_sources_has_ob06_when_phase2(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        combined = " ".join(fi.data_sources)
        self.assertIn("OB-06", combined)

    def test_data_sources_has_f401_when_phase4(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        combined = " ".join(fi.data_sources)
        self.assertIn("F4-01", combined)

    # --- Semaforo nunca VERDE ---

    def test_never_verde_with_full_data(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    def test_never_verde_verde_amarillo(self):
        fi = build_socioeconomic_factor_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        self.assertNotEqual(fi.inventory_semaphore, "VERDE_AMARILLO")

    # --- Sin datos ---

    def test_no_data_returns_pendiente(self):
        fi = build_socioeconomic_factor_from_phase_data()
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_no_data_not_ready(self):
        fi = build_socioeconomic_factor_from_phase_data()
        self.assertFalse(fi.ready_for_impact_assessment)


# ---------------------------------------------------------------------------
# C. TestContextInventoryBuildResult
# ---------------------------------------------------------------------------

class TestContextInventoryBuildResult(unittest.TestCase):

    def _make_result(self) -> ContextInventoryBuildResult:
        return build_context_inventory_factors_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL,
            cartography_plan=CART_PLAN_WITH_MAPS
        )

    def test_to_dict_has_factors_key(self):
        r = self._make_result()
        self.assertIn("factors", r.to_dict())

    def test_to_dict_has_warnings_key(self):
        r = self._make_result()
        self.assertIn("warnings", r.to_dict())

    def test_to_dict_has_notes_key(self):
        r = self._make_result()
        self.assertIn("notes", r.to_dict())

    def test_to_dict_factor_count(self):
        r = self._make_result()
        self.assertEqual(len(r.to_dict()["factors"]), 2)

    def test_summary_returns_string(self):
        r = self._make_result()
        s = r.summary()
        self.assertIsInstance(s, str)
        self.assertTrue(len(s) > 20)

    def test_summary_includes_fi011(self):
        r = self._make_result()
        self.assertIn("FI-011", r.summary())

    def test_summary_includes_fi013(self):
        r = self._make_result()
        self.assertIn("FI-013", r.summary())

    def test_json_serializable(self):
        r = self._make_result()
        dumped = json.dumps(r.to_dict(), ensure_ascii=False)
        self.assertIsInstance(dumped, str)


# ---------------------------------------------------------------------------
# D. TestBuildContextInventory
# ---------------------------------------------------------------------------

class TestBuildContextInventory(unittest.TestCase):

    def test_returns_two_factors(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertEqual(len(r.factors), 2)

    def test_fi011_first(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertEqual(r.factors[0].factor_id, "FI-011")

    def test_fi013_second(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertEqual(r.factors[1].factor_id, "FI-013")

    def test_no_args_returns_pendiente_factors(self):
        r = build_context_inventory_factors_from_phase_data()
        for f in r.factors:
            self.assertEqual(f.evidence_status, "PENDIENTE")

    def test_with_full_data_enriches_both(self):
        r = build_context_inventory_factors_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL,
            cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi011 = r.factors[0]
        fi013 = r.factors[1]
        self.assertEqual(fi011.evidence_status, "ESTIMADO")
        self.assertEqual(fi013.evidence_status, "DECLARADO")

    def test_result_has_notes(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertTrue(len(r.notes) > 0)

    def test_warnings_when_no_phase2(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertTrue(any("Fase 2" in w for w in r.warnings))

    def test_result_is_context_inventory_build_result(self):
        r = build_context_inventory_factors_from_phase_data()
        self.assertIsInstance(r, ContextInventoryBuildResult)


# ---------------------------------------------------------------------------
# E. TestMergeContextFactors
# ---------------------------------------------------------------------------

class TestMergeContextFactors(unittest.TestCase):

    def _base_summary(self) -> object:
        from eia_agent.core.inventory_model import build_inventory_summary
        factors = build_all_empty_factors()
        return build_inventory_summary("EIA-TEST", factors)

    def test_replaces_fi011(self):
        summary = self._base_summary()
        fi011 = build_landscape_factor_from_phase_data(
            phase4_result=PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        new_sum = merge_context_factors_into_summary(summary, [fi011])
        result_fi011 = next(f for f in new_sum.factors if f.factor_id == "FI-011")
        self.assertEqual(result_fi011.evidence_status, "ESTIMADO")

    def test_replaces_fi013(self):
        summary = self._base_summary()
        fi013 = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        new_sum = merge_context_factors_into_summary(summary, [fi013])
        result_fi013 = next(f for f in new_sum.factors if f.factor_id == "FI-013")
        self.assertEqual(result_fi013.evidence_status, "DECLARADO")

    def test_no_duplicates(self):
        summary = self._base_summary()
        r = build_context_inventory_factors_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        fi011_count = sum(1 for f in new_sum.factors if f.factor_id == "FI-011")
        fi013_count = sum(1 for f in new_sum.factors if f.factor_id == "FI-013")
        self.assertEqual(fi011_count, 1)
        self.assertEqual(fi013_count, 1)

    def test_still_16_factors(self):
        summary = self._base_summary()
        r = build_context_inventory_factors_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        self.assertEqual(new_sum.total_factors, 16)

    def test_canonical_order_preserved(self):
        summary = self._base_summary()
        r = build_context_inventory_factors_from_phase_data(
            phase2_data=PHASE2_FULL, phase4_result=PHASE4_FULL
        )
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_sum.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_does_not_mutate_original(self):
        summary = self._base_summary()
        original_fi011 = next(f for f in summary.factors if f.factor_id == "FI-011")
        original_status = original_fi011.evidence_status
        fi011 = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        merge_context_factors_into_summary(summary, [fi011])
        # Original no mutado
        still_fi011 = next(f for f in summary.factors if f.factor_id == "FI-011")
        self.assertEqual(still_fi011.evidence_status, original_status)

    def test_original_warnings_propagated(self):
        summary = self._base_summary()
        summary.warnings.append("AVISO ORIGINAL TEST")
        r = build_context_inventory_factors_from_phase_data()
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        self.assertIn("AVISO ORIGINAL TEST", new_sum.warnings)

    def test_original_notes_propagated(self):
        summary = self._base_summary()
        summary.notes.append("NOTA ORIGINAL TEST")
        r = build_context_inventory_factors_from_phase_data()
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        self.assertIn("NOTA ORIGINAL TEST", new_sum.notes)

    def test_partial_replace_fi011_only(self):
        summary = self._base_summary()
        fi011 = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        new_sum = merge_context_factors_into_summary(summary, [fi011])
        # FI-013 sigue siendo el de base (PENDIENTE)
        fi013 = next(f for f in new_sum.factors if f.factor_id == "FI-013")
        self.assertEqual(fi013.evidence_status, "PENDIENTE")

    def test_expediente_id_preserved(self):
        summary = self._base_summary()
        r = build_context_inventory_factors_from_phase_data()
        new_sum = merge_context_factors_into_summary(summary, r.factors)
        self.assertEqual(new_sum.expediente_id, "EIA-TEST")


# ---------------------------------------------------------------------------
# F. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def test_fi001_enriched_by_climate(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_fi005_enriched_by_iv03(self):
        # IV-03 siempre reemplaza el factor base de FI-005 con GAP-FI-005-001,
        # aunque la evidencia sea PENDIENTE si no hay mapa de inundabilidad.
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi005 = next(f for f in result.factors if f.factor_id == "FI-005")
        gap_ids = [g.gap_id for g in fi005.gaps]
        self.assertIn("GAP-FI-005-001", gap_ids)

    def test_fi016_enriched_by_iv03(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi016 = next(f for f in result.factors if f.factor_id == "FI-016")
        self.assertEqual(fi016.evidence_status, "ESTIMADO")

    def test_fi011_enriched_by_iv04_with_phase4_and_plan(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi011 = next(f for f in result.factors if f.factor_id == "FI-011")
        self.assertEqual(fi011.evidence_status, "ESTIMADO")
        self.assertEqual(fi011.inventory_semaphore, "AMARILLO")

    def test_fi011_enriched_by_iv04_with_embedded_plan(self):
        # Fixture IV-02: plan embebido {"maps": []} + estacion climatica
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_WITH_CLIMATE
        )
        fi011 = next(f for f in result.factors if f.factor_id == "FI-011")
        self.assertEqual(fi011.evidence_status, "ESTIMADO")

    def test_fi013_base_when_no_phase2(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL, cartography_plan=CART_PLAN_WITH_MAPS
        )
        fi013 = next(f for f in result.factors if f.factor_id == "FI-013")
        self.assertEqual(fi013.evidence_status, "PENDIENTE")

    def test_fi013_enriched_when_phase2_provided(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL,
            cartography_plan=CART_PLAN_WITH_MAPS,
            phase2_data=PHASE2_FULL,
        )
        fi013 = next(f for f in result.factors if f.factor_id == "FI-013")
        self.assertEqual(fi013.evidence_status, "DECLARADO")
        self.assertTrue(fi013.ready_for_impact_assessment)

    def test_all_ready_phase6_still_false(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL,
            cartography_plan=CART_PLAN_WITH_MAPS,
            phase2_data=PHASE2_FULL,
        )
        self.assertFalse(result.all_ready_for_phase6)

    def test_fi011_never_ready(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_FULL,
            cartography_plan=CART_PLAN_WITH_MAPS,
            phase2_data=PHASE2_FULL,
        )
        fi011 = next(f for f in result.factors if f.factor_id == "FI-011")
        self.assertFalse(fi011.ready_for_impact_assessment)

    def test_write_creates_fi011_file(self):
        with tempfile.TemporaryDirectory() as d:
            exp_dir = Path(d) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            (exp_dir / "fase4").mkdir()
            p4_data = dict(PHASE4_FULL)
            p4_data["expediente_id"] = "EIA-TEST"
            (exp_dir / "fase4" / "phase4_result.json").write_text(
                json.dumps(p4_data), encoding="utf-8"
            )
            from eia_agent.core.inventory_builder import build_inventory_from_phase4
            result = build_inventory_from_phase4(exp_dir, write_outputs=True)
            inv_dir = exp_dir / "inventario"
            fi011_files = list(inv_dir.glob("*FI_011*")) + list(inv_dir.glob("*FI-011*"))
            fi011_files += list(inv_dir.glob("*paisaje*"))
            self.assertTrue(
                len(fi011_files) > 0,
                f"No se encontro archivo FI-011 en {list(inv_dir.iterdir())}"
            )

    def test_write_creates_fi013_file(self):
        with tempfile.TemporaryDirectory() as d:
            exp_dir = Path(d) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            (exp_dir / "fase4").mkdir()
            p4_data = dict(PHASE4_FULL)
            p4_data["expediente_id"] = "EIA-TEST"
            (exp_dir / "fase4" / "phase4_result.json").write_text(
                json.dumps(p4_data), encoding="utf-8"
            )
            from eia_agent.core.inventory_builder import build_inventory_from_phase4
            result = build_inventory_from_phase4(exp_dir, write_outputs=True)
            inv_dir = exp_dir / "inventario"
            fi013_files = (
                list(inv_dir.glob("*FI_013*"))
                + list(inv_dir.glob("*FI-013*"))
                + list(inv_dir.glob("*socioeconom*"))
            )
            self.assertTrue(
                len(fi013_files) > 0,
                f"No se encontro archivo FI-013 en {list(inv_dir.iterdir())}"
            )

    def test_write_fi011_contains_gap(self):
        with tempfile.TemporaryDirectory() as d:
            exp_dir = Path(d) / "expediente-EIA-TEST"
            exp_dir.mkdir()
            (exp_dir / "fase4").mkdir()
            p4_data = dict(PHASE4_FULL)
            p4_data["expediente_id"] = "EIA-TEST"
            (exp_dir / "fase4" / "phase4_result.json").write_text(
                json.dumps(p4_data), encoding="utf-8"
            )
            from eia_agent.core.inventory_builder import build_inventory_from_phase4
            build_inventory_from_phase4(exp_dir, write_outputs=True)
            summary_json = exp_dir / "inventario" / "inventory_summary.json"
            data = json.loads(summary_json.read_text(encoding="utf-8"))
            fi011 = next(f for f in data["factors"] if f["factor_id"] == "FI-011")
            self.assertTrue(len(fi011["gaps"]) > 0)
            self.assertEqual(fi011["gaps"][0]["gap_id"], "GAP-FI-011-001")

    def test_phase2_data_enriches_fi013_via_param(self):
        result = build_inventory_from_phase4_data(
            "EIA-TEST", PHASE4_NO_PLAN, phase2_data=PHASE2_FULL
        )
        fi013 = next(f for f in result.factors if f.factor_id == "FI-013")
        self.assertIn("RECIMETAL", fi013.description)


# ---------------------------------------------------------------------------
# G. TestPrudenceLexical
# ---------------------------------------------------------------------------

class TestPrudenceLexical(unittest.TestCase):
    """Verifica que ninguna descripcion contiene patrones lexicos prohibidos."""

    _FORBIDDEN = [
        "sin afección",
        "sin afecion",
        "sin impacto",
        "inexistente",
        "beneficio economico neto",
        "beneficio económico neto",
        "compensa",
    ]

    def _all_descriptions(self) -> list[str]:
        """Recoge todas las descripciones de FI-011 y FI-013 en variantes."""
        texts: list[str] = []
        variants_phase4 = [None, PHASE4_NO_PLAN, PHASE4_CLIMATE_ONLY, PHASE4_FULL]
        variants_phase2 = [None, PHASE2_FULL, PHASE2_NO_PROMOTER, PHASE2_NO_ACTIVITY]
        variants_plan = [None, CART_PLAN_WITH_MAPS, CART_PLAN_EMPTY_MAPS]

        for p4 in variants_phase4:
            for p2 in variants_phase2:
                for cp in variants_plan:
                    fi011 = build_landscape_factor_from_phase_data(
                        phase2_data=p2, phase4_result=p4, cartography_plan=cp
                    )
                    fi013 = build_socioeconomic_factor_from_phase_data(
                        phase2_data=p2, phase4_result=p4
                    )
                    texts.append(fi011.description)
                    texts.append(fi013.description)
        return texts

    def test_no_sin_afecion_fi011(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        self.assertNotIn("sin afección", fi.description.lower())
        self.assertNotIn("sin afecion", fi.description.lower())

    def test_no_sin_impacto_fi011(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        self.assertNotIn("sin impacto", fi.description.lower())

    def test_no_inexistente_fi011(self):
        fi = build_landscape_factor_from_phase_data(phase4_result=PHASE4_FULL)
        self.assertNotIn("inexistente", fi.description.lower())

    def test_no_sin_afecion_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertNotIn("sin afección", fi.description.lower())
        self.assertNotIn("sin afecion", fi.description.lower())

    def test_no_sin_impacto_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertNotIn("sin impacto", fi.description.lower())

    def test_no_inexistente_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertNotIn("inexistente", fi.description.lower())

    def test_no_beneficio_economico_neto_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertNotIn("beneficio económico neto", fi.description.lower())
        self.assertNotIn("beneficio economico neto", fi.description.lower())

    def test_no_compensa_fi013(self):
        fi = build_socioeconomic_factor_from_phase_data(phase2_data=PHASE2_FULL)
        self.assertNotIn("compensa", fi.description.lower())

    def test_no_compensa_all_variants(self):
        for desc in self._all_descriptions():
            self.assertNotIn("compensa", desc.lower(), msg=desc[:80])

    def test_no_forbidden_patterns_all_variants(self):
        for desc in self._all_descriptions():
            desc_lower = desc.lower()
            for pattern in self._FORBIDDEN:
                self.assertNotIn(pattern, desc_lower, msg=f"'{pattern}' en: {desc[:80]}")


if __name__ == "__main__":
    unittest.main()
