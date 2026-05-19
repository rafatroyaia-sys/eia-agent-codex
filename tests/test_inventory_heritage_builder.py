"""
tests/test_inventory_heritage_builder.py -- IV-09
Tests for src/eia_agent/core/inventory_heritage_builder.py

Categorias:
  A. TestAuxiliaries                  -- extract_heritage_context, detect_heritage_mentions
  B. TestBuildFI012Basic              -- con ubicacion, sin menciones patrimoniales
  C. TestBuildFI012WithMention        -- con BIC/yacimiento/arqueologia
  D. TestBuildFI012PromoterDecl       -- promotor declara informacion patrimonial
  E. TestBuildFI012NoData             -- PENDIENTE sin datos
  F. TestHeritageInventoryBuildResult -- dataclass HeritageInventoryBuildResult
  G. TestBuildWrapper                 -- build_heritage_inventory_factor_from_phase4
  H. TestMerge                        -- merge_heritage_factor_into_summary
  I. TestIntegrationWithIV02          -- build_inventory_from_phase4_data con IV-09
  J. TestPrudenceLexical              -- ausencia de patrones prohibidos
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_heritage_builder import (
    HeritageInventoryBuildResult,
    build_heritage_factor_from_phase_data,
    build_heritage_inventory_factor_from_phase4,
    detect_heritage_mentions,
    extract_heritage_context,
    merge_heritage_factor_into_summary,
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

PHASE2_BASIC = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento de chatarra metalica"],
        "descripcion_actividad": "Gestion de residuos metalicos en nave industrial.",
    }
}

PHASE2_WITH_HERITAGE = {
    "object_scope": {
        "titular": "CONSTRUCTORA S.L.",
        "coordenadas_wgs84": ["28.0000 N, 15.4000 W"],
        "operaciones_incluidas": ["D15 - deposito definitivo"],
        "descripcion_actividad": (
            "Proyecto en zona con posible yacimiento arqueologico catalogado. "
            "Se advierte de la presencia de restos arqueologicos en el PGOU vigente."
        ),
    }
}

PHASE2_WITH_BIC = {
    "object_scope": {
        "titular": "PROMOTORA S.A.",
        "coordenadas_wgs84": ["27.9000 N, 15.3500 W"],
        "descripcion_actividad": (
            "La parcela se encuentra proxima a un BIC declarado por el Cabildo. "
            "El IGPC ha informado sobre la existencia de materiales historicos."
        ),
    }
}

PHASE2_NO_COORDS = {
    "object_scope": {
        "titular": "EMPRESA S.L.",
        "operaciones_incluidas": ["R13 - tratamiento de residuos"],
    }
}

CART_PLAN_BASIC = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [],
}

CART_PLAN_WITH_HERITAGE = {
    "expediente_id": "EIA-TEST",
    "center": {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
    "maps": [
        {
            "map_id": "MAP-007",
            "map_type": "patrimonio_cultural",
            "title": "Catalogo de patrimonio cultural y yacimientos",
            "notes": "Inventario arqueologico autonómico pendiente de consulta",
        }
    ],
}


# ---------------------------------------------------------------------------
# A. TestAuxiliaries
# ---------------------------------------------------------------------------

class TestAuxiliaries(unittest.TestCase):

    def test_extract_no_crash_none(self):
        text = extract_heritage_context(None, None, None)
        self.assertIsInstance(text, str)

    def test_extract_no_crash_empty_dicts(self):
        text = extract_heritage_context({}, {}, {})
        self.assertIsInstance(text, str)

    def test_extract_detects_patrimonio(self):
        phase2 = {"notes": "zona con patrimonio cultural relevante"}
        text = extract_heritage_context(phase2, None, None)
        self.assertIn("patrimonio", text)

    def test_extract_detects_yacimiento(self):
        phase4 = {"info": "presencia de yacimiento arqueologico"}
        text = extract_heritage_context(None, phase4, None)
        self.assertIn("yacimiento", text)

    def test_extract_detects_bic(self):
        cart = {"notes": "BIC declarado en el entorno"}
        text = extract_heritage_context(None, None, cart)
        self.assertIn("bic", text)

    def test_extract_detects_igpc(self):
        phase2 = {"notes": "consulta al IGPC pendiente"}
        text = extract_heritage_context(phase2, None, None)
        self.assertIn("igpc", text)

    def test_extract_detects_arqueolog(self):
        phase4 = {"notes": "restos arqueologicos identificados"}
        text = extract_heritage_context(None, phase4, None)
        self.assertIn("arqueolog", text)

    def test_extract_deep_nested(self):
        phase2 = {"a": {"b": {"c": "zona con yacimiento arqueologico"}}}
        text = extract_heritage_context(phase2, None, None)
        self.assertIn("yacimiento", text)

    def test_extract_no_false_positives(self):
        phase2 = {"notes": "almacenamiento de materiales reciclables"}
        text = extract_heritage_context(phase2, None, None)
        self.assertEqual(text, "")

    def test_detect_returns_list(self):
        result = detect_heritage_mentions("zona con patrimonio catalogado")
        self.assertIsInstance(result, list)

    def test_detect_finds_patrimonio(self):
        result = detect_heritage_mentions("hay patrimonio cultural en la zona")
        self.assertIn("patrimonio", result)

    def test_detect_finds_yacimiento(self):
        result = detect_heritage_mentions("existe un yacimiento arqueologico")
        self.assertIn("yacimiento", result)

    def test_detect_finds_bic(self):
        result = detect_heritage_mentions("bien bic declarado en el entorno")
        self.assertIn("bic", result)

    def test_detect_finds_igpc(self):
        result = detect_heritage_mentions("informe del igpc disponible")
        self.assertIn("igpc", result)

    def test_detect_finds_arqueolog(self):
        result = detect_heritage_mentions("estudio arqueologico requerido")
        self.assertIn("arqueolog", result)

    def test_detect_no_duplicates(self):
        result = detect_heritage_mentions("patrimonio patrimonio patrimonio")
        self.assertEqual(result.count("patrimonio"), 1)

    def test_detect_empty_text(self):
        result = detect_heritage_mentions("")
        self.assertEqual(result, [])

    def test_detect_no_match(self):
        result = detect_heritage_mentions("almacenamiento de residuos metalicos")
        self.assertEqual(result, [])

    def test_detect_finds_historic(self):
        result = detect_heritage_mentions("edificio historico catalogado")
        self.assertIn("historic", result)

    def test_detect_finds_etnografi(self):
        result = detect_heritage_mentions("bien etnografico protegido")
        self.assertIn("etnografi", result)


# ---------------------------------------------------------------------------
# B. TestBuildFI012Basic
# ---------------------------------------------------------------------------

class TestBuildFI012Basic(unittest.TestCase):

    def setUp(self):
        self.fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_factor_id(self):
        self.assertEqual(self.fi.factor_id, "FI-012")

    def test_factor_name_contains_patrimonio(self):
        self.assertIn("Patrimonio", self.fi.factor_name)

    def test_evidence_estimado_with_location(self):
        self.assertEqual(self.fi.evidence_status, "ESTIMADO")

    def test_semaphore_amarillo_with_location_no_mentions(self):
        self.assertEqual(self.fi.inventory_semaphore, "AMARILLO")

    def test_field_mode_campo_recomendado(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")

    def test_has_at_least_one_gap(self):
        self.assertGreaterEqual(len(self.fi.gaps), 1)

    def test_gap_001_present(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-012-001", gap_ids)

    def test_gap_001_alta_criticality(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-001")
        self.assertEqual(g.criticality, "ALTA")

    def test_gap_001_gabinete(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-001")
        self.assertEqual(g.resolution_mode, "GABINETE")

    def test_gap_001_pendiente(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-001")
        self.assertEqual(g.status, "PENDIENTE")

    def test_no_gap_002_without_heritage_mention(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-012-002", gap_ids)

    def test_data_sources_ob06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("OB-06", joined)

    def test_data_sources_f4(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("F4-01", joined)

    def test_description_mentions_gabinete(self):
        self.assertIn("gabinete", self.fi.description.lower())

    def test_description_mentions_no_descarta(self):
        self.assertIn("no es posible descartar", self.fi.description.lower())

    def test_description_mentions_consulta_oficial(self):
        self.assertIn("consulta", self.fi.description.lower())


# ---------------------------------------------------------------------------
# C. TestBuildFI012WithMention
# ---------------------------------------------------------------------------

class TestBuildFI012WithMention(unittest.TestCase):

    def setUp(self):
        self.fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_HERITAGE,
        )

    def test_evidence_declarado_when_promoter_declares(self):
        self.assertEqual(self.fi.evidence_status, "DECLARADO")

    def test_semaphore_rojo_amarillo_with_heritage_mention(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_recomendado_with_coords(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_gap_002_with_heritage_mention(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-012-002", gap_ids)

    def test_gap_002_alta_criticality(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-002")
        self.assertEqual(g.criticality, "ALTA")

    def test_gap_002_gabinete(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-002")
        self.assertEqual(g.resolution_mode, "GABINETE")

    def test_gap_002_pendiente(self):
        g = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-012-002")
        self.assertEqual(g.status, "PENDIENTE")

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")

    def test_description_mentions_detected_terms(self):
        self.assertIn("menciones", self.fi.description.lower())

    def test_description_prudence_no_descarta(self):
        self.assertIn("no es posible descartar", self.fi.description.lower())


# ---------------------------------------------------------------------------
# C2. TestBuildFI012WithBIC
# ---------------------------------------------------------------------------

class TestBuildFI012WithBIC(unittest.TestCase):

    def setUp(self):
        self.fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_BIC,
        )

    def test_evidence_declarado(self):
        self.assertEqual(self.fi.evidence_status, "DECLARADO")

    def test_semaphore_rojo_amarillo(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_gap_002_present(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-012-002", gap_ids)

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_description_mentions_bic_terms(self):
        desc = self.fi.description.lower()
        self.assertTrue(
            "bic" in desc or "bien" in desc or "menciones" in desc,
            "description should reference heritage mentions",
        )


# ---------------------------------------------------------------------------
# D. TestBuildFI012CartographyMention
# ---------------------------------------------------------------------------

class TestBuildFI012CartographyMention(unittest.TestCase):

    def test_cartography_with_heritage_map_gets_rojo_amarillo(self):
        fi = build_heritage_factor_from_phase_data(
            cartography_plan=CART_PLAN_WITH_HERITAGE,
        )
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_cartography_with_heritage_map_adds_gap_002(self):
        fi = build_heritage_factor_from_phase_data(
            cartography_plan=CART_PLAN_WITH_HERITAGE,
        )
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertIn("GAP-FI-012-002", gap_ids)

    def test_basic_cartography_no_heritage_map_amarillo(self):
        fi = build_heritage_factor_from_phase_data(
            cartography_plan=CART_PLAN_BASIC,
        )
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_basic_cartography_no_gap_002(self):
        fi = build_heritage_factor_from_phase_data(
            cartography_plan=CART_PLAN_BASIC,
        )
        gap_ids = [g.gap_id for g in fi.gaps]
        self.assertNotIn("GAP-FI-012-002", gap_ids)

    def test_embedded_plan_from_phase4(self):
        fi = build_heritage_factor_from_phase_data(
            phase4_result=PHASE4_WITH_CENTER,
        )
        self.assertNotEqual(fi.evidence_status, "PENDIENTE")


# ---------------------------------------------------------------------------
# E. TestBuildFI012NoData
# ---------------------------------------------------------------------------

class TestBuildFI012NoData(unittest.TestCase):

    def setUp(self):
        self.fi = build_heritage_factor_from_phase_data(
            phase2_data=None,
            phase4_result=None,
            cartography_plan=None,
        )

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
        self.assertIn("GAP-FI-012-001", gap_ids)

    def test_no_gap_002_without_mentions(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertNotIn("GAP-FI-012-002", gap_ids)

    def test_empty_data_sources(self):
        self.assertEqual(len(self.fi.data_sources), 0)

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")

    def test_description_has_no_location_text(self):
        self.assertIn("no se dispone de coordenadas", self.fi.description.lower())


# ---------------------------------------------------------------------------
# F. TestHeritageInventoryBuildResult
# ---------------------------------------------------------------------------

class TestHeritageInventoryBuildResult(unittest.TestCase):

    def setUp(self):
        self.result = build_heritage_inventory_factor_from_phase4(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_result_is_dataclass(self):
        self.assertIsInstance(self.result, HeritageInventoryBuildResult)

    def test_factor_attribute_is_factor_inventory(self):
        self.assertIsInstance(self.result.factor, FactorInventory)

    def test_factor_id_fi012(self):
        self.assertEqual(self.result.factor.factor_id, "FI-012")

    def test_warnings_is_list(self):
        self.assertIsInstance(self.result.warnings, list)

    def test_notes_is_list(self):
        self.assertIsInstance(self.result.notes, list)

    def test_to_dict_returns_dict(self):
        d = self.result.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_has_factor_key(self):
        d = self.result.to_dict()
        self.assertIn("factor", d)

    def test_to_dict_has_warnings_and_notes(self):
        d = self.result.to_dict()
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_to_dict_json_serializable(self):
        d = self.result.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)

    def test_summary_returns_string(self):
        s = self.result.summary()
        self.assertIsInstance(s, str)
        self.assertIn("FI-012", s)

    def test_notes_contains_iv09_marker(self):
        joined = " ".join(self.result.notes)
        self.assertIn("IV-09", joined)


# ---------------------------------------------------------------------------
# G. TestBuildWrapper
# ---------------------------------------------------------------------------

class TestBuildWrapper(unittest.TestCase):

    def test_no_data_produces_warning(self):
        result = build_heritage_inventory_factor_from_phase4()
        self.assertTrue(len(result.warnings) > 0)

    def test_heritage_mention_produces_warning(self):
        result = build_heritage_inventory_factor_from_phase4(
            phase2_data=PHASE2_WITH_HERITAGE,
        )
        joined = " ".join(result.warnings)
        self.assertIn("FI-012", joined)

    def test_basic_data_notes_contain_iv09(self):
        result = build_heritage_inventory_factor_from_phase4(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )
        joined = " ".join(result.notes)
        self.assertIn("IV-09", joined)

    def test_embedded_plan_from_phase4_enriches(self):
        result = build_heritage_inventory_factor_from_phase4(
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        self.assertNotEqual(result.factor.evidence_status, "PENDIENTE")

    def test_explicit_cartography_plan_used(self):
        result = build_heritage_inventory_factor_from_phase4(
            cartography_plan=CART_PLAN_BASIC,
        )
        self.assertEqual(result.factor.evidence_status, "ESTIMADO")


# ---------------------------------------------------------------------------
# H. TestMerge
# ---------------------------------------------------------------------------

class TestMerge(unittest.TestCase):

    def setUp(self):
        factors = build_all_empty_factors()
        self.summary = build_inventory_summary("EIA-TEST", factors)
        self.factor = build_heritage_factor_from_phase_data(
            phase4_result=PHASE4_WITH_CENTER,
        )

    def test_merge_returns_new_summary(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        self.assertIsNot(new, self.summary)

    def test_merge_does_not_mutate_original(self):
        original_fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        original_status = original_fi012.evidence_status
        merge_heritage_factor_into_summary(self.summary, self.factor)
        fi012_after = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        self.assertEqual(fi012_after.evidence_status, original_status)

    def test_merge_replaces_fi012(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        fi012 = next(f for f in new.factors if f.factor_id == "FI-012")
        self.assertNotEqual(fi012.evidence_status, "PENDIENTE")

    def test_merge_preserves_16_factors(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        self.assertEqual(len(new.factors), 16)

    def test_merge_preserves_canonical_order(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        ids = [f.factor_id for f in new.factors]
        expected = sorted(FACTOR_NAMES.keys())
        self.assertEqual(ids, expected)

    def test_merge_no_duplicate_fi012(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        count = sum(1 for f in new.factors if f.factor_id == "FI-012")
        self.assertEqual(count, 1)

    def test_merge_preserves_other_factors(self):
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        fi001 = next(f for f in new.factors if f.factor_id == "FI-001")
        orig_fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, orig_fi001.evidence_status)

    def test_merge_propagates_warnings(self):
        self.summary.warnings.append("test-warning")
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        self.assertIn("test-warning", new.warnings)

    def test_merge_propagates_notes(self):
        self.summary.notes.append("test-note")
        new = merge_heritage_factor_into_summary(self.summary, self.factor)
        self.assertIn("test-note", new.notes)


# ---------------------------------------------------------------------------
# I. TestIntegrationWithIV02
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

    def test_fi012_is_enriched(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        self.assertNotEqual(fi012.evidence_status, "PENDIENTE")

    def test_fi012_semaphore_not_verde(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        self.assertNotEqual(fi012.inventory_semaphore, "VERDE")

    def test_fi012_ready_false(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        self.assertFalse(fi012.ready_for_impact_assessment)

    def test_fi012_has_gap_001(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        gap_ids = [g.gap_id for g in fi012.gaps]
        self.assertIn("GAP-FI-012-001", gap_ids)

    def test_canonical_order_preserved(self):
        ids = [f.factor_id for f in self.summary.factors]
        expected = sorted(FACTOR_NAMES.keys())
        self.assertEqual(ids, expected)

    def test_iv09_in_notes(self):
        joined = " ".join(self.summary.notes)
        self.assertIn("IV-09", joined)

    def test_fi001_enriched(self):
        fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_fi002_enriched(self):
        fi002 = next(f for f in self.summary.factors if f.factor_id == "FI-002")
        self.assertNotEqual(fi002.evidence_status, "PENDIENTE")

    def test_fi009_enriched(self):
        fi009 = next(f for f in self.summary.factors if f.factor_id == "FI-009")
        self.assertNotEqual(fi009.evidence_status, "PENDIENTE")

    def test_fi015_enriched(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertNotEqual(fi015.evidence_status, "PENDIENTE")

    def test_no_duplicate_factor_ids(self):
        ids = [f.factor_id for f in self.summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_ready_false_feature_is_false(self):
        self.assertFalse(self.summary.all_ready_for_phase6)

    def test_fi012_with_heritage_mentions_gets_rojo_amarillo(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_WITH_HERITAGE,
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        fi012 = next(f for f in summary.factors if f.factor_id == "FI-012")
        self.assertEqual(fi012.inventory_semaphore, "ROJO_AMARILLO")

    def test_fi012_with_heritage_gets_two_gaps(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_WITH_HERITAGE,
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        fi012 = next(f for f in summary.factors if f.factor_id == "FI-012")
        gap_ids = [g.gap_id for g in fi012.gaps]
        self.assertIn("GAP-FI-012-002", gap_ids)

    def test_summary_json_serializable(self):
        d = self.summary.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)

    def test_fi012_gap_factor_id_is_fi012(self):
        fi012 = next(f for f in self.summary.factors if f.factor_id == "FI-012")
        for g in fi012.gaps:
            self.assertEqual(g.factor_id, "FI-012")


# ---------------------------------------------------------------------------
# J. TestPrudenceLexical
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "no hay patrimonio",
    "sin yacimientos",
    "sin afeccion patrimonial",
    "sin afección patrimonial",
    "descartado",
    "no existe patrimonio",
    "ausencia de patrimonio",
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

    def _collect_all_text(self, fi: FactorInventory) -> str:
        parts = [fi.description, fi.factor_name, " ".join(fi.data_sources)]
        for g in fi.gaps:
            parts.append(g.description)
        return " ".join(parts).lower()

    def _check_no_forbidden(self, fi: FactorInventory):
        text = self._collect_all_text(fi)
        for pattern in FORBIDDEN_PATTERNS:
            self.assertNotIn(pattern.lower(), text, f"Forbidden pattern found: '{pattern}'")

    def test_basic_no_forbidden(self):
        fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_BASIC,
            phase4_result=PHASE4_WITH_CENTER,
        )
        self._check_no_forbidden(fi)

    def test_with_heritage_mention_no_forbidden(self):
        fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_HERITAGE,
        )
        self._check_no_forbidden(fi)

    def test_no_data_no_forbidden(self):
        fi = build_heritage_factor_from_phase_data()
        self._check_no_forbidden(fi)

    def test_with_bic_no_forbidden(self):
        fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_BIC,
        )
        self._check_no_forbidden(fi)

    def test_ready_always_false_pendiente(self):
        fi = build_heritage_factor_from_phase_data()
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_ready_always_false_estimado(self):
        fi = build_heritage_factor_from_phase_data(
            phase4_result=PHASE4_WITH_CENTER,
        )
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_ready_always_false_declarado(self):
        fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_HERITAGE,
        )
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_semaphore_never_verde_any_case(self):
        cases = [
            (None, None, None),
            (PHASE2_BASIC, PHASE4_WITH_CENTER, None),
            (PHASE2_WITH_HERITAGE, None, None),
            (PHASE2_WITH_BIC, None, None),
            (None, PHASE4_WITH_CENTER, CART_PLAN_WITH_HERITAGE),
        ]
        for p2, p4, cart in cases:
            fi = build_heritage_factor_from_phase_data(
                phase2_data=p2, phase4_result=p4, cartography_plan=cart
            )
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE for {p2}, {p4}")

    def test_no_descarta_absent_from_all_cases(self):
        fi = build_heritage_factor_from_phase_data(
            phase2_data=PHASE2_WITH_HERITAGE,
        )
        desc = fi.description.lower()
        self.assertNotIn("sin afeccion", desc)
        self.assertNotIn("sin yacim", desc)
        self.assertNotIn("no hay patr", desc)


if __name__ == "__main__":
    unittest.main()
