"""
tests/test_inventory_biodiversity_builder.py -- IV-10
Tests for src/eia_agent/core/inventory_biodiversity_builder.py

Categorias:
  A. TestAuxiliaries                     -- extract_biodiversity_context,
                                            detect_flora_mentions,
                                            detect_fauna_mentions,
                                            has_biodiversity_related_context
  B. TestBuildFI007Basic                 -- FI-007 con ubicacion, sin menciones
  C. TestBuildFI007WithMention           -- FI-007 con menciones flora/habitats
  D. TestBuildFI007PromoterDecl          -- FI-007 con declaracion del promotor
  E. TestBuildFI007NoData                -- FI-007 PENDIENTE sin datos
  F. TestBuildFI008Basic                 -- FI-008 con ubicacion, sin menciones
  G. TestBuildFI008WithMention           -- FI-008 con menciones fauna/nidificacion
  H. TestBuildFI008PromoterDecl          -- FI-008 con declaracion del promotor
  I. TestBuildFI008NoData                -- FI-008 PENDIENTE sin datos
  J. TestBiodiversityBuildResult         -- dataclass BiodiversityInventoryBuildResult
  K. TestBuildCombined                   -- build_biodiversity_inventory_factors_from_phase_data
  L. TestMerge                           -- merge_biodiversity_factors_into_summary
  M. TestIntegrationWithIV02             -- build_inventory_from_phase4_data con IV-10
  N. TestPrudenceLexical                 -- ausencia de patrones prohibidos
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_biodiversity_builder import (
    BiodiversityInventoryBuildResult,
    build_biodiversity_inventory_factors_from_phase_data,
    build_fauna_factor_from_phase_data,
    build_flora_factor_from_phase_data,
    detect_fauna_mentions,
    detect_flora_mentions,
    extract_biodiversity_context,
    has_biodiversity_related_context,
    merge_biodiversity_factors_into_summary,
)
from eia_agent.core.inventory_builder import build_inventory_from_phase4_data
from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    build_all_empty_factors,
    build_inventory_summary,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIMATE_RESULT = {
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
    },
}

PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_RESULT,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_WITH_CENTER = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": {
        "expediente_id": "EIA-TEST",
        "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
        "maps": [],
    },
    "ready_for_phase5": False,
}

PHASE4_NO_DATA = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
}

PHASE4_WITH_RED_NATURA = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_RESULT,
    "cartography_plan": {
        "expediente_id": "EIA-TEST",
        "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
        "maps": [
            {
                "map_id": "MAP-004",
                "map_type": "red_natura_enp",
                "title": "Red Natura 2000 y ENP",
                "required_layers": ["red_natura_2000", "espacios_naturales_protegidos"],
                "status": "READY_FOR_RENDER",
            }
        ],
    },
    "ready_for_phase5": False,
}

PHASE4_WITH_USOS_SUELO = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_RESULT,
    "cartography_plan": {
        "expediente_id": "EIA-TEST",
        "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
        "maps": [
            {
                "map_id": "MAP-005",
                "map_type": "usos_suelo",
                "title": "Usos del suelo",
                "required_layers": ["usos_suelo"],
                "status": "READY_FOR_RENDER",
            }
        ],
    },
    "ready_for_phase5": False,
}

PHASE2_BASIC = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento de chatarra metalica"],
        "descripcion_actividad": "Gestion de residuos metalicos en nave industrial.",
    }
}

PHASE2_WITH_FLORA = {
    "object_scope": {
        "titular": "PROMOTORA S.L.",
        "coordenadas_wgs84": ["28.0 N, 15.4 W"],
        "descripcion_actividad": (
            "El proyecto se encuentra en zona con matorral y vegetacion natural. "
            "Se ha observado arbolado en el lindero norte de la parcela."
        ),
    }
}

PHASE2_WITH_FAUNA = {
    "object_scope": {
        "titular": "CONSTRUCTORA S.A.",
        "coordenadas_wgs84": ["28.0 N, 15.4 W"],
        "descripcion_actividad": (
            "La zona presenta avifauna en los alrededores. "
            "Se han observado nidificaciones en edificaciones proximas. "
            "No se han realizado estudios de fauna."
        ),
    }
}

PHASE2_WITH_BOTH = {
    "object_scope": {
        "titular": "EMPRESA S.L.",
        "coordenadas_wgs84": ["28.0 N, 15.4 W"],
        "descripcion_actividad": (
            "Parcela en entorno con matorral canario y fauna autoctona. "
            "Se detectan aves en el area de influencia y posible habitat de "
            "especie protegida."
        ),
    }
}

CART_PLAN_RED_NATURA = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [
        {
            "map_id": "MAP-004",
            "map_type": "red_natura_enp",
            "required_layers": ["red_natura_2000", "espacios_naturales_protegidos"],
        }
    ],
}

CART_PLAN_USOS = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [
        {
            "map_id": "MAP-005",
            "map_type": "usos_suelo",
            "required_layers": ["usos_suelo"],
        }
    ],
}

CART_PLAN_BASIC = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [],
}


# ---------------------------------------------------------------------------
# A. TestAuxiliaries
# ---------------------------------------------------------------------------

class TestAuxiliaries(unittest.TestCase):

    def test_extract_no_crash_none(self):
        text = extract_biodiversity_context(None, None, None)
        self.assertIsInstance(text, str)

    def test_extract_no_crash_empty_dicts(self):
        text = extract_biodiversity_context({}, {}, {})
        self.assertIsInstance(text, str)

    def test_extract_detects_flora(self):
        phase2 = {"notes": "zona con flora endemica relevante"}
        text = extract_biodiversity_context(phase2, None, None)
        self.assertIn("flora", text)

    def test_extract_detects_fauna(self):
        phase4 = {"notes": "presencia de fauna autoctona"}
        text = extract_biodiversity_context(None, phase4, None)
        self.assertIn("fauna", text)

    def test_extract_detects_avifauna(self):
        phase2 = {"notes": "avifauna migradora en la zona"}
        text = extract_biodiversity_context(phase2, None, None)
        self.assertIn("avifauna", text)

    def test_extract_detects_habitat(self):
        cart = {"notes": "habitat de interes comunitario"}
        text = extract_biodiversity_context(None, None, cart)
        self.assertIn("habitat", text)

    def test_extract_detects_red_natura(self):
        phase4 = {"notes": "proximidad a red natura 2000"}
        text = extract_biodiversity_context(None, phase4, None)
        self.assertIn("red natura", text)

    def test_extract_no_match_generic_text(self):
        phase2 = {"notes": "almacenamiento de residuos inertes en contenedor"}
        text = extract_biodiversity_context(phase2, None, None)
        self.assertEqual(text, "")

    def test_extract_deep_nested(self):
        phase2 = {"a": {"b": {"c": "vegetacion natural en entorno de la parcela"}}}
        text = extract_biodiversity_context(phase2, None, None)
        self.assertIn("vegetaci", text)

    def test_detect_flora_finds_flora(self):
        result = detect_flora_mentions("presencia de flora endemica")
        self.assertIn("flora", result)

    def test_detect_flora_finds_vegetacion(self):
        result = detect_flora_mentions("vegetacion natural en el lindero")
        self.assertIn("vegetaci", result)

    def test_detect_flora_finds_habitat(self):
        result = detect_flora_mentions("habitat de interes comunitario")
        self.assertIn("habitat", result)

    def test_detect_flora_finds_matorral(self):
        result = detect_flora_mentions("matorral canario presente")
        self.assertIn("matorral", result)

    def test_detect_flora_finds_especie_protegida(self):
        result = detect_flora_mentions("especie protegida identificada")
        self.assertIn("especie protegida", result)

    def test_detect_flora_no_duplicates(self):
        result = detect_flora_mentions("flora flora flora")
        self.assertEqual(result.count("flora"), 1)

    def test_detect_flora_empty(self):
        result = detect_flora_mentions("")
        self.assertEqual(result, [])

    def test_detect_fauna_finds_fauna(self):
        result = detect_fauna_mentions("fauna autoctona presente")
        self.assertIn("fauna", result)

    def test_detect_fauna_finds_avifauna(self):
        result = detect_fauna_mentions("avifauna migratoria detectada")
        self.assertIn("avifauna", result)

    def test_detect_fauna_finds_aves(self):
        result = detect_fauna_mentions("aves nidificantes en la zona")
        self.assertIn("aves", result)

    def test_detect_fauna_finds_reptil(self):
        result = detect_fauna_mentions("presencia de reptiles")
        self.assertIn("reptil", result)

    def test_detect_fauna_finds_nidificacion(self):
        result = detect_fauna_mentions("nidificacion observada en el edificio")
        self.assertIn("nidificaci", result)

    def test_detect_fauna_finds_quiroptero(self):
        result = detect_fauna_mentions("colonia de quiropteros detectada")
        self.assertIn("quiropter", result)

    def test_detect_fauna_no_duplicates(self):
        result = detect_fauna_mentions("fauna fauna fauna")
        self.assertEqual(result.count("fauna"), 1)

    def test_detect_fauna_empty(self):
        result = detect_fauna_mentions("")
        self.assertEqual(result, [])

    def test_has_bio_context_red_natura_map_type(self):
        self.assertTrue(has_biodiversity_related_context(PHASE4_WITH_RED_NATURA))

    def test_has_bio_context_usos_suelo_map_type(self):
        self.assertTrue(has_biodiversity_related_context(PHASE4_WITH_USOS_SUELO))

    def test_has_bio_context_map004(self):
        self.assertTrue(has_biodiversity_related_context(cartography_plan=CART_PLAN_RED_NATURA))

    def test_has_bio_context_map005(self):
        self.assertTrue(has_biodiversity_related_context(cartography_plan=CART_PLAN_USOS))

    def test_has_bio_context_layer_red_natura_2000(self):
        plan = {"maps": [{"map_id": "X", "required_layers": ["red_natura_2000"]}]}
        self.assertTrue(has_biodiversity_related_context(cartography_plan=plan))

    def test_has_bio_context_empty_maps_false(self):
        plan = {"maps": []}
        self.assertFalse(has_biodiversity_related_context(cartography_plan=plan))

    def test_has_bio_context_none_false(self):
        self.assertFalse(has_biodiversity_related_context(None, None))


# ---------------------------------------------------------------------------
# B. TestBuildFI007Basic
# ---------------------------------------------------------------------------

class TestBuildFI007Basic(unittest.TestCase):

    def setUp(self):
        self.fi = build_flora_factor_from_phase_data(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_factor_id(self):
        self.assertEqual(self.fi.factor_id, "FI-007")

    def test_factor_name_flora(self):
        self.assertIn("Flora", self.fi.factor_name)

    def test_evidence_estimado_with_location(self):
        self.assertEqual(self.fi.evidence_status, "ESTIMADO")

    def test_semaphore_amarillo(self):
        self.assertEqual(self.fi.inventory_semaphore, "AMARILLO")

    def test_field_mode_campo_recomendado(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")

    def test_has_gap_001(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-007-001", gap_ids)

    def test_gap_001_pendiente(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.status, "PENDIENTE")

    def test_no_gap_002_without_mention(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-007-002", gap_ids)

    def test_data_sources_ob06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("OB-06", joined)

    def test_data_sources_f4(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("F4-01", joined)

    def test_description_mentions_gabinete(self):
        self.assertIn("gabinete", self.fi.description.lower())

    def test_description_mentions_no_puede_afirmar(self):
        self.assertIn("no es posible afirmar", self.fi.description.lower())


# ---------------------------------------------------------------------------
# C. TestBuildFI007WithMention
# ---------------------------------------------------------------------------

class TestBuildFI007WithMention(unittest.TestCase):

    def setUp(self):
        self.fi = build_flora_factor_from_phase_data(
            phase2_data=PHASE2_WITH_FLORA,
        )

    def test_evidence_declarado_when_promoter_declares_flora(self):
        self.assertEqual(self.fi.evidence_status, "DECLARADO")

    def test_semaphore_rojo_amarillo_with_flora_mention(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_necesario(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_NECESARIO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_gap_002_present(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-007-002", gap_ids)

    def test_gap_002_alta(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-007-002")
        self.assertEqual(g.criticality, "ALTA")

    def test_gap_002_campo(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-007-002")
        self.assertEqual(g.resolution_mode, "CAMPO")

    def test_description_mentions_detected_terms(self):
        self.assertIn("menciones", self.fi.description.lower())

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# D. TestBuildFI007RedNatura
# ---------------------------------------------------------------------------

class TestBuildFI007RedNatura(unittest.TestCase):

    def test_red_natura_context_gets_alta_gap(self):
        fi = build_flora_factor_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.criticality, "ALTA")

    def test_red_natura_context_gets_campo_resolution(self):
        fi = build_flora_factor_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.resolution_mode, "CAMPO")

    def test_usos_suelo_context_gets_alta_gap(self):
        fi = build_flora_factor_from_phase_data(
            cartography_plan=CART_PLAN_USOS,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.criticality, "ALTA")

    def test_basic_location_only_gets_media_gap(self):
        fi = build_flora_factor_from_phase_data(
            cartography_plan=CART_PLAN_BASIC,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.criticality, "MEDIA")

    def test_embedded_red_natura_enriches_fi007(self):
        fi = build_flora_factor_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        self.assertNotEqual(fi.evidence_status, "PENDIENTE")


# ---------------------------------------------------------------------------
# E. TestBuildFI007NoData
# ---------------------------------------------------------------------------

class TestBuildFI007NoData(unittest.TestCase):

    def setUp(self):
        self.fi = build_flora_factor_from_phase_data()

    def test_evidence_pendiente(self):
        self.assertEqual(self.fi.evidence_status, "PENDIENTE")

    def test_semaphore_no_consta(self):
        self.assertEqual(self.fi.inventory_semaphore, "NO_CONSTA")

    def test_field_mode_no_consta(self):
        self.assertEqual(self.fi.field_mode, "NO_CONSTA")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_gap_001(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-007-001", gap_ids)

    def test_no_gap_002(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-007-002", gap_ids)

    def test_empty_data_sources(self):
        self.assertEqual(len(self.fi.data_sources), 0)

    def test_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# F. TestBuildFI008Basic
# ---------------------------------------------------------------------------

class TestBuildFI008Basic(unittest.TestCase):

    def setUp(self):
        self.fi = build_fauna_factor_from_phase_data(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_factor_id(self):
        self.assertEqual(self.fi.factor_id, "FI-008")

    def test_factor_name_fauna(self):
        self.assertIn("Fauna", self.fi.factor_name)

    def test_evidence_estimado(self):
        self.assertEqual(self.fi.evidence_status, "ESTIMADO")

    def test_semaphore_amarillo(self):
        self.assertEqual(self.fi.inventory_semaphore, "AMARILLO")

    def test_field_mode_campo_recomendado(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")

    def test_has_gap_001(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-008-001", gap_ids)

    def test_no_gap_002_without_mention(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-008-002", gap_ids)

    def test_data_sources_f4(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("F4-01", joined)

    def test_description_has_no_puede_afirmar(self):
        self.assertIn("no es posible afirmar", self.fi.description.lower())


# ---------------------------------------------------------------------------
# G. TestBuildFI008WithMention
# ---------------------------------------------------------------------------

class TestBuildFI008WithMention(unittest.TestCase):

    def setUp(self):
        self.fi = build_fauna_factor_from_phase_data(
            phase2_data=PHASE2_WITH_FAUNA,
        )

    def test_evidence_declarado(self):
        self.assertEqual(self.fi.evidence_status, "DECLARADO")

    def test_semaphore_rojo_amarillo(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_necesario(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_NECESARIO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_gap_002_present(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-008-002", gap_ids)

    def test_gap_002_alta(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-008-002")
        self.assertEqual(g.criticality, "ALTA")

    def test_gap_002_campo(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-008-002")
        self.assertEqual(g.resolution_mode, "CAMPO")

    def test_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# H. TestBuildFI008RedNatura
# ---------------------------------------------------------------------------

class TestBuildFI008RedNatura(unittest.TestCase):

    def test_red_natura_context_gets_alta_gap(self):
        fi = build_fauna_factor_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-008-001")
        self.assertEqual(g.criticality, "ALTA")

    def test_red_natura_context_gets_campo_resolution(self):
        fi = build_fauna_factor_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-008-001")
        self.assertEqual(g.resolution_mode, "CAMPO")

    def test_basic_location_only_gets_media_gap(self):
        fi = build_fauna_factor_from_phase_data(
            cartography_plan=CART_PLAN_BASIC,
        )
        g = next(g for g in fi.gaps if g.gap_id == "GAP-FI-008-001")
        self.assertEqual(g.criticality, "MEDIA")

    def test_nidificacion_mention_gets_rojo_amarillo(self):
        phase2 = {
            "object_scope": {
                "descripcion_actividad": "se observan nidificaciones en el edificio contiguo"
            }
        }
        fi = build_fauna_factor_from_phase_data(phase2_data=phase2)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")


# ---------------------------------------------------------------------------
# I. TestBuildFI008NoData
# ---------------------------------------------------------------------------

class TestBuildFI008NoData(unittest.TestCase):

    def setUp(self):
        self.fi = build_fauna_factor_from_phase_data()

    def test_evidence_pendiente(self):
        self.assertEqual(self.fi.evidence_status, "PENDIENTE")

    def test_semaphore_no_consta(self):
        self.assertEqual(self.fi.inventory_semaphore, "NO_CONSTA")

    def test_field_mode_no_consta(self):
        self.assertEqual(self.fi.field_mode, "NO_CONSTA")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_gap_001(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-008-001", gap_ids)

    def test_no_gap_002(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-008-002", gap_ids)


# ---------------------------------------------------------------------------
# J. TestBiodiversityBuildResult
# ---------------------------------------------------------------------------

class TestBiodiversityBuildResult(unittest.TestCase):

    def setUp(self):
        self.result = build_biodiversity_inventory_factors_from_phase_data(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_result_is_dataclass(self):
        self.assertIsInstance(self.result, BiodiversityInventoryBuildResult)

    def test_has_two_factors(self):
        self.assertEqual(len(self.result.factors), 2)

    def test_factors_are_fi007_and_fi008(self):
        ids = [f.factor_id for f in self.result.factors]
        self.assertIn("FI-007", ids)
        self.assertIn("FI-008", ids)

    def test_warnings_is_list(self):
        self.assertIsInstance(self.result.warnings, list)

    def test_notes_is_list(self):
        self.assertIsInstance(self.result.notes, list)

    def test_notes_not_empty(self):
        self.assertGreater(len(self.result.notes), 0)

    def test_to_dict_returns_dict(self):
        d = self.result.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_has_factors(self):
        d = self.result.to_dict()
        self.assertIn("factors", d)
        self.assertEqual(len(d["factors"]), 2)

    def test_to_dict_json_serializable(self):
        d = self.result.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)

    def test_summary_returns_string(self):
        s = self.result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("FI-007", s)
        self.assertIn("FI-008", s)

    def test_notes_contain_iv10_marker(self):
        joined = " ".join(self.result.notes)
        self.assertIn("IV-10", joined)


# ---------------------------------------------------------------------------
# K. TestBuildCombined
# ---------------------------------------------------------------------------

class TestBuildCombined(unittest.TestCase):

    def test_no_data_produces_warnings(self):
        result = build_biodiversity_inventory_factors_from_phase_data()
        self.assertGreater(len(result.warnings), 0)

    def test_red_natura_context_generates_note(self):
        result = build_biodiversity_inventory_factors_from_phase_data(
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        joined = " ".join(result.notes)
        self.assertIn("Red Natura", joined)

    def test_with_both_mentions_produces_warnings(self):
        result = build_biodiversity_inventory_factors_from_phase_data(
            phase2_data=PHASE2_WITH_BOTH,
        )
        joined = " ".join(result.warnings)
        self.assertIn("FI-007", joined)
        self.assertIn("FI-008", joined)

    def test_embedded_plan_from_phase4_is_used(self):
        result = build_biodiversity_inventory_factors_from_phase_data(
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        fi007 = next(f for f in result.factors if f.factor_id == "FI-007")
        self.assertNotEqual(fi007.evidence_status, "PENDIENTE")

    def test_factors_order_fi007_before_fi008(self):
        result = build_biodiversity_inventory_factors_from_phase_data(
            phase4_result=PHASE4_WITH_CENTER,
        )
        self.assertEqual(result.factors[0].factor_id, "FI-007")
        self.assertEqual(result.factors[1].factor_id, "FI-008")


# ---------------------------------------------------------------------------
# L. TestMerge
# ---------------------------------------------------------------------------

class TestMerge(unittest.TestCase):

    def setUp(self):
        factors_base = build_all_empty_factors()
        self.summary = build_inventory_summary("EIA-TEST", factors_base)
        result = build_biodiversity_inventory_factors_from_phase_data(
            phase4_result=PHASE4_WITH_CENTER,
        )
        self.bio_factors = result.factors

    def test_merge_returns_new_summary(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        self.assertIsNot(new, self.summary)

    def test_merge_does_not_mutate_original_fi007(self):
        original_fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        original_status = original_fi007.evidence_status
        merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        fi007_after = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        self.assertEqual(fi007_after.evidence_status, original_status)

    def test_merge_replaces_fi007(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        fi007 = next(f for f in new.factors if f.factor_id == "FI-007")
        self.assertNotEqual(fi007.evidence_status, "PENDIENTE")

    def test_merge_replaces_fi008(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        fi008 = next(f for f in new.factors if f.factor_id == "FI-008")
        self.assertNotEqual(fi008.evidence_status, "PENDIENTE")

    def test_merge_preserves_16_factors(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        self.assertEqual(len(new.factors), 16)

    def test_merge_preserves_canonical_order(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        ids = [f.factor_id for f in new.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_no_duplicate_fi007(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        count = sum(1 for f in new.factors if f.factor_id == "FI-007")
        self.assertEqual(count, 1)

    def test_no_duplicate_fi008(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        count = sum(1 for f in new.factors if f.factor_id == "FI-008")
        self.assertEqual(count, 1)

    def test_merge_propagates_warnings(self):
        self.summary.warnings.append("existing-warning")
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        self.assertIn("existing-warning", new.warnings)

    def test_merge_preserves_other_factors(self):
        new = merge_biodiversity_factors_into_summary(self.summary, self.bio_factors)
        fi001 = next(f for f in new.factors if f.factor_id == "FI-001")
        orig = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, orig.evidence_status)


# ---------------------------------------------------------------------------
# M. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def setUp(self):
        self.summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CLIMATE,
        )

    def test_summary_has_16_factors(self):
        self.assertEqual(len(self.summary.factors), 16)

    def test_fi007_is_enriched(self):
        fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        self.assertNotEqual(fi007.evidence_status, "PENDIENTE")

    def test_fi008_is_enriched(self):
        fi008 = next(f for f in self.summary.factors if f.factor_id == "FI-008")
        self.assertNotEqual(fi008.evidence_status, "PENDIENTE")

    def test_fi007_not_verde(self):
        fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        self.assertNotEqual(fi007.inventory_semaphore, "VERDE")

    def test_fi008_not_verde(self):
        fi008 = next(f for f in self.summary.factors if f.factor_id == "FI-008")
        self.assertNotEqual(fi008.inventory_semaphore, "VERDE")

    def test_fi007_ready_false(self):
        fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        self.assertFalse(fi007.ready_for_impact_assessment)

    def test_fi008_ready_false(self):
        fi008 = next(f for f in self.summary.factors if f.factor_id == "FI-008")
        self.assertFalse(fi008.ready_for_impact_assessment)

    def test_fi007_has_gap_001(self):
        fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        self.assertIn("GAP-FI-007-001", [g.gap_id for g in fi007.gaps])

    def test_fi008_has_gap_001(self):
        fi008 = next(f for f in self.summary.factors if f.factor_id == "FI-008")
        self.assertIn("GAP-FI-008-001", [g.gap_id for g in fi008.gaps])

    def test_canonical_order_preserved(self):
        ids = [f.factor_id for f in self.summary.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_iv10_in_notes(self):
        joined = " ".join(self.summary.notes)
        self.assertIn("IV-10", joined)

    def test_fi001_enriched(self):
        fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_fi015_enriched(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertNotEqual(fi015.evidence_status, "PENDIENTE")

    def test_fi012_enriched(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        self.assertNotEqual(fi012.evidence_status, "PENDIENTE")

    def test_no_duplicate_factor_ids(self):
        ids = [f.factor_id for f in self.summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_ready_false_is_false(self):
        self.assertFalse(self.summary.all_ready_for_phase6)

    def test_fi007_fi008_rojo_amarillo_with_bio_mentions(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_WITH_BOTH,
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        fi007 = next(f for f in summary.factors if f.factor_id == "FI-007")
        fi008 = next(f for f in summary.factors if f.factor_id == "FI-008")
        self.assertEqual(fi007.inventory_semaphore, "ROJO_AMARILLO")
        self.assertEqual(fi008.inventory_semaphore, "ROJO_AMARILLO")

    def test_fi007_fi008_red_natura_alta_gap(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase4_result=PHASE4_WITH_RED_NATURA,
        )
        fi007 = next(f for f in summary.factors if f.factor_id == "FI-007")
        g = next(g for g in fi007.gaps if g.gap_id == "GAP-FI-007-001")
        self.assertEqual(g.criticality, "ALTA")

    def test_summary_json_serializable(self):
        d = self.summary.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)

    def test_gap_factor_ids_correct_fi007(self):
        fi007 = next(f for f in self.summary.factors if f.factor_id == "FI-007")
        for g in fi007.gaps:
            self.assertEqual(g.factor_id, "FI-007")

    def test_gap_factor_ids_correct_fi008(self):
        fi008 = next(f for f in self.summary.factors if f.factor_id == "FI-008")
        for g in fi008.gaps:
            self.assertEqual(g.factor_id, "FI-008")


# ---------------------------------------------------------------------------
# N. TestPrudenceLexical
# ---------------------------------------------------------------------------

FORBIDDEN_FLORA = [
    "no hay flora",
    "sin vegetacion",
    "sin vegetación",
    "sin especies protegidas",
    "sin habitats",
    "sin hábitats",
    "sin afeccion a flora",
    "sin afección a flora",
    "descartado",
]

FORBIDDEN_FAUNA = [
    "no hay fauna",
    "sin fauna",
    "sin aves",
    "sin nidificacion",
    "sin nidificación",
    "sin afeccion a fauna",
    "sin afección a fauna",
    "descartado",
]

FORBIDDEN_VALORACION = [
    "impacto compatible",
    "impacto moderado",
    "impacto severo",
    "impacto critico",
    "impacto crítico",
    "compatible",
    "moderado",
    "severo",
]


class TestPrudenceLexical(unittest.TestCase):

    def _text(self, fi: FactorInventory) -> str:
        parts = [fi.description, fi.factor_name, " ".join(fi.data_sources)]
        for g in fi.gaps:
            parts.append(g.description)
        return " ".join(parts).lower()

    def _check(self, fi: FactorInventory, forbidden: list[str]):
        text = self._text(fi)
        for pat in forbidden:
            self.assertNotIn(pat.lower(), text, f"Forbidden: '{pat}'")

    def test_fi007_basic_no_forbidden_flora(self):
        fi = build_flora_factor_from_phase_data(
            phase2_data=PHASE2_BASIC, phase4_result=PHASE4_WITH_CENTER
        )
        self._check(fi, FORBIDDEN_FLORA)

    def test_fi007_mention_no_forbidden_flora(self):
        fi = build_flora_factor_from_phase_data(phase2_data=PHASE2_WITH_FLORA)
        self._check(fi, FORBIDDEN_FLORA)

    def test_fi007_no_data_no_forbidden_flora(self):
        fi = build_flora_factor_from_phase_data()
        self._check(fi, FORBIDDEN_FLORA)

    def test_fi007_no_valoracion_terms(self):
        fi = build_flora_factor_from_phase_data(
            phase2_data=PHASE2_BASIC, phase4_result=PHASE4_WITH_CENTER
        )
        self._check(fi, FORBIDDEN_VALORACION)

    def test_fi008_basic_no_forbidden_fauna(self):
        fi = build_fauna_factor_from_phase_data(
            phase2_data=PHASE2_BASIC, phase4_result=PHASE4_WITH_CENTER
        )
        self._check(fi, FORBIDDEN_FAUNA)

    def test_fi008_mention_no_forbidden_fauna(self):
        fi = build_fauna_factor_from_phase_data(phase2_data=PHASE2_WITH_FAUNA)
        self._check(fi, FORBIDDEN_FAUNA)

    def test_fi008_no_data_no_forbidden_fauna(self):
        fi = build_fauna_factor_from_phase_data()
        self._check(fi, FORBIDDEN_FAUNA)

    def test_fi008_no_valoracion_terms(self):
        fi = build_fauna_factor_from_phase_data(
            phase2_data=PHASE2_BASIC, phase4_result=PHASE4_WITH_CENTER
        )
        self._check(fi, FORBIDDEN_VALORACION)

    def test_ready_always_false_flora(self):
        for p2, p4 in [(None, None), (PHASE2_BASIC, PHASE4_WITH_CENTER), (PHASE2_WITH_FLORA, None)]:
            fi = build_flora_factor_from_phase_data(phase2_data=p2, phase4_result=p4)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_ready_always_false_fauna(self):
        for p2, p4 in [(None, None), (PHASE2_BASIC, PHASE4_WITH_CENTER), (PHASE2_WITH_FAUNA, None)]:
            fi = build_fauna_factor_from_phase_data(phase2_data=p2, phase4_result=p4)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_semaphore_never_verde_flora(self):
        for p2, p4 in [
            (None, None), (PHASE2_BASIC, PHASE4_WITH_CENTER),
            (PHASE2_WITH_FLORA, None), (None, PHASE4_WITH_RED_NATURA),
        ]:
            fi = build_flora_factor_from_phase_data(phase2_data=p2, phase4_result=p4)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE")

    def test_semaphore_never_verde_fauna(self):
        for p2, p4 in [
            (None, None), (PHASE2_BASIC, PHASE4_WITH_CENTER),
            (PHASE2_WITH_FAUNA, None), (None, PHASE4_WITH_RED_NATURA),
        ]:
            fi = build_fauna_factor_from_phase_data(phase2_data=p2, phase4_result=p4)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE")


if __name__ == "__main__":
    unittest.main()
