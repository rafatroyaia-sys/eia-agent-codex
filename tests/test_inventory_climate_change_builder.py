"""
tests/test_inventory_climate_change_builder.py -- IV-08
Tests for src/eia_agent/core/inventory_climate_change_builder.py

Categorias:
  A. TestAuxiliaries                     -- extract_climate_change_context,
                                            detect_ghg_relevant_sources,
                                            detect_climate_vulnerability_terms
  B. TestBuildFI015FullData              -- DECLARADO con clima + actividad + GHG
  C. TestBuildFI015ClimateOnly           -- ESTIMADO con solo clima CL-06
  D. TestBuildFI015ActivityOnly          -- ESTIMADO con solo actividad
  E. TestBuildFI015HighGHG              -- ROJO_AMARILLO con combustion/diesel
  F. TestBuildFI015NoData               -- PENDIENTE/NO_CONSTA sin datos
  G. TestBuildFI015Description          -- contenido de descripcion
  H. TestClimateChangeResult            -- ClimateChangeInventoryBuildResult dataclass
  I. TestBuildWrapper                    -- build_climate_change_inventory_factor_from_phase4
  J. TestMerge                          -- merge_climate_change_factor_into_summary
  K. TestIntegrationWithIV02            -- build_inventory_from_phase4_data con IV-08
  L. TestPrudenceLexical                -- ausencia de patrones prohibidos
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_climate_change_builder import (
    ClimateChangeInventoryBuildResult,
    build_climate_change_factor_from_phase_data,
    build_climate_change_inventory_factor_from_phase4,
    detect_climate_vulnerability_terms,
    detect_ghg_relevant_sources,
    extract_climate_change_context,
    merge_climate_change_factor_into_summary,
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
        "koppen_label": "Arido calido",
        "annual_temperature_c": 21.36,
        "annual_precipitation_mm": 131.0,
        "martonne_index": 4.8,
        "martonne_label": "Arido",
        "dry_months_gaussen": 12,
        "dry_months_names": [
            "ene", "feb", "mar", "abr", "may", "jun",
            "jul", "ago", "sep", "oct", "nov", "dic",
        ],
    },
    "warnings": [],
    "notes": [],
}

PHASE2_WITH_ACTIVITY = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento de chatarra metalica"],
        "descripcion_actividad": (
            "Planta de gestion de residuos metalicos con carretilla elevadora diesel "
            "y transporte de material."
        ),
    }
}

PHASE2_NO_GHG = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento"],
        "descripcion_actividad": "Deposito de residuos inertes sin equipos moviles.",
    }
}

PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_RESULT,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_NO_CLIMATE = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_WITH_VULN = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_RESULT,
    "cartography_plan": {
        "maps": [
            {
                "map_id": "MAP-006",
                "map_type": "inundabilidad_riesgos",
                "title": "Inundabilidad y riesgos",
                "notes": "zona con riesgo de inundacion y aridez extrema",
            }
        ]
    },
    "notes": ["presencia de dana historica en el area"],
    "warnings": [],
    "ready_for_phase5": False,
}


# ---------------------------------------------------------------------------
# A. TestAuxiliaries
# ---------------------------------------------------------------------------

class TestAuxiliaries(unittest.TestCase):

    def test_extract_no_crash_none(self):
        text = extract_climate_change_context(None, None, None)
        self.assertIsInstance(text, str)

    def test_extract_no_crash_empty_dicts(self):
        text = extract_climate_change_context({}, {}, {})
        self.assertIsInstance(text, str)

    def test_extract_detects_diesel(self):
        phase2 = {"notes": "utilizamos maquinaria diesel en la planta"}
        text = extract_climate_change_context(phase2, None, None)
        self.assertIn("diesel", text)

    def test_extract_detects_koppen(self):
        climate = {"notes": ["clasificacion koppen bwh"]}
        text = extract_climate_change_context(None, None, climate)
        self.assertIn("koppen", text)

    def test_extract_detects_temperatura(self):
        phase4 = {"notes": ["temperatura media anual elevada"]}
        text = extract_climate_change_context(None, phase4, None)
        self.assertIn("temperatura", text)

    def test_extract_from_phase4_embedded_climate(self):
        phase4 = {"notes": ["cambio climatico evaluado"]}
        text = extract_climate_change_context(None, phase4, None)
        self.assertIn("cambio climatico", text)

    def test_extract_deep_nested(self):
        phase2 = {"a": {"b": {"c": "generador electrico de combustion"}}}
        text = extract_climate_change_context(phase2, None, None)
        self.assertIn("combustion", text)

    def test_detect_ghg_returns_list(self):
        result = detect_ghg_relevant_sources("maquinaria diesel y carretilla")
        self.assertIsInstance(result, list)

    def test_detect_ghg_finds_diesel(self):
        result = detect_ghg_relevant_sources("equipo con motor diesel")
        self.assertIn("diesel", result)

    def test_detect_ghg_finds_multiple(self):
        result = detect_ghg_relevant_sources("generador a gasoil y carretilla elevadora")
        self.assertIn("generador", result)
        self.assertIn("gasoil", result)
        self.assertIn("carretilla", result)

    def test_detect_ghg_no_duplicates(self):
        result = detect_ghg_relevant_sources("diesel diesel diesel")
        self.assertEqual(result.count("diesel"), 1)

    def test_detect_ghg_empty_text(self):
        result = detect_ghg_relevant_sources("")
        self.assertEqual(result, [])

    def test_detect_ghg_no_match(self):
        result = detect_ghg_relevant_sources("almacenamiento de inertes sin equipos")
        self.assertEqual(result, [])

    def test_detect_vulnerability_returns_list(self):
        result = detect_climate_vulnerability_terms("riesgo de inundabilidad y sequia")
        self.assertIsInstance(result, list)

    def test_detect_vulnerability_finds_inundabilidad(self):
        result = detect_climate_vulnerability_terms("zona de inundabilidad alta")
        self.assertIn("inundabilidad", result)

    def test_detect_vulnerability_finds_dana(self):
        result = detect_climate_vulnerability_terms("evento dana registrado")
        self.assertIn("dana", result)

    def test_detect_vulnerability_finds_sequia(self):
        result = detect_climate_vulnerability_terms("riesgo de sequia prolongada")
        self.assertIn("sequia", result)

    def test_detect_vulnerability_no_duplicates(self):
        result = detect_climate_vulnerability_terms("dana dana dana")
        self.assertEqual(result.count("dana"), 1)

    def test_detect_vulnerability_empty(self):
        result = detect_climate_vulnerability_terms("")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# B. TestBuildFI015FullData
# ---------------------------------------------------------------------------

class TestBuildFI015FullData(unittest.TestCase):

    def setUp(self):
        self.fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=PHASE4_WITH_CLIMATE,
            climate_result=CLIMATE_RESULT,
        )

    def test_factor_id(self):
        self.assertEqual(self.fi.factor_id, "FI-015")

    def test_factor_name_contains_cambio_climatico(self):
        self.assertIn("Cambio", self.fi.factor_name)

    def test_evidence_declarado(self):
        self.assertEqual(self.fi.evidence_status, "DECLARADO")

    def test_semaphore_is_rojo_amarillo_with_high_ghg(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_recomendado(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_is_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_two_gaps(self):
        self.assertEqual(len(self.fi.gaps), 2)

    def test_gap_gei_id(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-015-001", gap_ids)

    def test_gap_adapt_id(self):
        gap_ids = [g.gap_id for g in self.fi.gaps]
        self.assertIn("GAP-FI-015-002", gap_ids)

    def test_gap_gei_alta_with_high_ghg(self):
        gei_gap = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-015-001")
        self.assertEqual(gei_gap.criticality, "ALTA")

    def test_gap_adapt_media(self):
        adapt_gap = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-015-002")
        self.assertEqual(adapt_gap.criticality, "MEDIA")

    def test_gap_gei_gabinete(self):
        gei_gap = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-015-001")
        self.assertEqual(gei_gap.resolution_mode, "GABINETE")

    def test_gap_adapt_gabinete(self):
        adapt_gap = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-015-002")
        self.assertEqual(adapt_gap.resolution_mode, "GABINETE")

    def test_gaps_status_pendiente(self):
        for g in self.fi.gaps:
            self.assertEqual(g.status, "PENDIENTE")

    def test_data_sources_cl06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("CL-06", joined)

    def test_data_sources_ob06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("OB-06", joined)

    def test_semaphore_never_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# C. TestBuildFI015ClimateOnly
# ---------------------------------------------------------------------------

class TestBuildFI015ClimateOnly(unittest.TestCase):

    def setUp(self):
        self.fi = build_climate_change_factor_from_phase_data(
            phase2_data=None,
            phase4_result=None,
            climate_result=CLIMATE_RESULT,
        )

    def test_evidence_estimado(self):
        self.assertEqual(self.fi.evidence_status, "ESTIMADO")

    def test_semaphore_amarillo(self):
        self.assertEqual(self.fi.inventory_semaphore, "AMARILLO")

    def test_field_mode_gabinete_suficiente(self):
        self.assertEqual(self.fi.field_mode, "GABINETE_SUFICIENTE")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_two_gaps(self):
        self.assertEqual(len(self.fi.gaps), 2)

    def test_gap_gei_media_without_high_ghg(self):
        gei_gap = next(g for g in self.fi.gaps if g.gap_id == "GAP-FI-015-001")
        self.assertEqual(gei_gap.criticality, "MEDIA")

    def test_description_mentions_koppen(self):
        self.assertIn("Koppen", self.fi.description)

    def test_description_mentions_temperatura(self):
        self.assertIn("21.4", self.fi.description)

    def test_description_mentions_precipitacion(self):
        self.assertIn("131.0", self.fi.description)

    def test_description_mentions_martonne(self):
        self.assertIn("Martonne", self.fi.description)

    def test_description_mentions_station(self):
        self.assertIn("Lanzarote", self.fi.description)

    def test_data_sources_has_cl06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("CL-06", joined)

    def test_semaphore_never_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# D. TestBuildFI015ActivityOnly
# ---------------------------------------------------------------------------

class TestBuildFI015ActivityOnly(unittest.TestCase):

    def setUp(self):
        self.fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=None,
            climate_result=None,
        )

    def test_evidence_estimado(self):
        self.assertEqual(self.fi.evidence_status, "ESTIMADO")

    def test_semaphore_rojo_amarillo_with_high_ghg(self):
        self.assertEqual(self.fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_recomendado(self):
        self.assertEqual(self.fi.field_mode, "CAMPO_RECOMENDADO")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_description_mentions_ghg_sources(self):
        self.assertIn("GEI", self.fi.description)

    def test_data_sources_ob06(self):
        joined = " ".join(self.fi.data_sources)
        self.assertIn("OB-06", joined)

    def test_semaphore_never_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# E. TestBuildFI015HighGHG
# ---------------------------------------------------------------------------

class TestBuildFI015HighGHG(unittest.TestCase):

    def test_generador_causes_rojo_amarillo(self):
        phase2 = {
            "object_scope": {
                "descripcion_actividad": "planta con generador diesel permanente",
            }
        }
        fi = build_climate_change_factor_from_phase_data(phase2_data=phase2)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_caldera_causes_alta_gap(self):
        phase2 = {
            "object_scope": {
                "descripcion_actividad": "proceso con caldera de combustion",
            }
        }
        fi = build_climate_change_factor_from_phase_data(phase2_data=phase2)
        gei_gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-015-001")
        self.assertEqual(gei_gap.criticality, "ALTA")

    def test_camion_causes_campo_recomendado(self):
        phase2 = {
            "object_scope": {
                "descripcion_actividad": "recogida con camion propio",
            }
        }
        fi = build_climate_change_factor_from_phase_data(phase2_data=phase2)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_electricidad_no_high_ghg(self):
        phase2 = {
            "object_scope": {
                "descripcion_actividad": "instalacion electrica de media tension, potencia 400 kW",
            }
        }
        fi = build_climate_change_factor_from_phase_data(phase2_data=phase2)
        gei_gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-015-001")
        self.assertEqual(gei_gap.criticality, "MEDIA")

    def test_high_ghg_with_climate_still_rojo_amarillo(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")


# ---------------------------------------------------------------------------
# F. TestBuildFI015NoData
# ---------------------------------------------------------------------------

class TestBuildFI015NoData(unittest.TestCase):

    def setUp(self):
        self.fi = build_climate_change_factor_from_phase_data(
            phase2_data=None,
            phase4_result=None,
            climate_result=None,
        )

    def test_evidence_pendiente(self):
        self.assertEqual(self.fi.evidence_status, "PENDIENTE")

    def test_semaphore_no_consta(self):
        self.assertEqual(self.fi.inventory_semaphore, "NO_CONSTA")

    def test_field_mode_no_consta(self):
        self.assertEqual(self.fi.field_mode, "NO_CONSTA")

    def test_ready_false(self):
        self.assertFalse(self.fi.ready_for_impact_assessment)

    def test_has_two_gaps(self):
        self.assertEqual(len(self.fi.gaps), 2)

    def test_empty_data_sources(self):
        self.assertEqual(len(self.fi.data_sources), 0)

    def test_semaphore_never_verde(self):
        self.assertNotEqual(self.fi.inventory_semaphore, "VERDE")


# ---------------------------------------------------------------------------
# G. TestBuildFI015Description
# ---------------------------------------------------------------------------

class TestBuildFI015Description(unittest.TestCase):

    def test_koppen_in_description_with_climate(self):
        fi = build_climate_change_factor_from_phase_data(climate_result=CLIMATE_RESULT)
        self.assertIn("BWh", fi.description)

    def test_koppen_label_in_description(self):
        fi = build_climate_change_factor_from_phase_data(climate_result=CLIMATE_RESULT)
        self.assertIn("Arido", fi.description)

    def test_martonne_value_in_description(self):
        fi = build_climate_change_factor_from_phase_data(climate_result=CLIMATE_RESULT)
        self.assertIn("4.8", fi.description)

    def test_dry_months_in_description(self):
        fi = build_climate_change_factor_from_phase_data(climate_result=CLIMATE_RESULT)
        self.assertIn("12", fi.description)

    def test_ghg_disclaimer_present(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
        )
        self.assertIn("cuantificacion", fi.description.lower())

    def test_vulnerability_mention_with_vuln_terms(self):
        fi = build_climate_change_factor_from_phase_data(
            phase4_result=PHASE4_WITH_VULN,
        )
        self.assertIn("vulnerabilidad", fi.description.lower())

    def test_preliminary_disclaimer_always_present(self):
        fi = build_climate_change_factor_from_phase_data()
        self.assertIn("preliminar", fi.description.lower())

    def test_description_without_activity_has_preliminary_disclaimer(self):
        fi = build_climate_change_factor_from_phase_data(
            climate_result=CLIMATE_RESULT,
        )
        self.assertIn("preliminar", fi.description.lower())

    def test_description_is_string(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        self.assertIsInstance(fi.description, str)
        self.assertGreater(len(fi.description), 50)


# ---------------------------------------------------------------------------
# H. TestClimateChangeResult
# ---------------------------------------------------------------------------

class TestClimateChangeResult(unittest.TestCase):

    def setUp(self):
        self.result = build_climate_change_inventory_factor_from_phase4(
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=PHASE4_WITH_CLIMATE,
            climate_result=CLIMATE_RESULT,
        )

    def test_result_is_dataclass(self):
        self.assertIsInstance(self.result, ClimateChangeInventoryBuildResult)

    def test_factor_attribute_is_factor_inventory(self):
        self.assertIsInstance(self.result.factor, FactorInventory)

    def test_factor_id_is_fi015(self):
        self.assertEqual(self.result.factor.factor_id, "FI-015")

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
        self.assertIn("FI-015", s)

    def test_notes_contains_iv08_marker(self):
        joined = " ".join(self.result.notes)
        self.assertIn("IV-08", joined)


# ---------------------------------------------------------------------------
# I. TestBuildWrapper
# ---------------------------------------------------------------------------

class TestBuildWrapper(unittest.TestCase):

    def test_no_data_produces_warning(self):
        result = build_climate_change_inventory_factor_from_phase4()
        self.assertTrue(len(result.warnings) > 0)

    def test_only_climate_produces_note_not_warning(self):
        result = build_climate_change_inventory_factor_from_phase4(
            climate_result=CLIMATE_RESULT,
        )
        joined_notes = " ".join(result.notes)
        self.assertIn("FI-015", joined_notes)

    def test_embedded_climate_from_phase4(self):
        result = build_climate_change_inventory_factor_from_phase4(
            phase4_result=PHASE4_WITH_CLIMATE,
        )
        self.assertEqual(result.factor.evidence_status, "ESTIMADO")

    def test_full_data_no_warning(self):
        result = build_climate_change_inventory_factor_from_phase4(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        self.assertEqual(len(result.warnings), 0)

    def test_activity_only_produces_warning(self):
        result = build_climate_change_inventory_factor_from_phase4(
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=PHASE4_NO_CLIMATE,
        )
        self.assertTrue(len(result.warnings) > 0)


# ---------------------------------------------------------------------------
# J. TestMerge
# ---------------------------------------------------------------------------

class TestMerge(unittest.TestCase):

    def setUp(self):
        factors = build_all_empty_factors()
        self.summary = build_inventory_summary("EIA-TEST", factors)
        self.factor = build_climate_change_factor_from_phase_data(
            climate_result=CLIMATE_RESULT,
        )

    def test_merge_returns_new_summary(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        self.assertIsNot(new, self.summary)

    def test_merge_does_not_mutate_original(self):
        original_fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        original_status = original_fi015.evidence_status
        merge_climate_change_factor_into_summary(self.summary, self.factor)
        fi015_after = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015_after.evidence_status, original_status)

    def test_merge_replaces_fi015(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        fi015 = next(f for f in new.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015.evidence_status, "ESTIMADO")

    def test_merge_preserves_16_factors(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        self.assertEqual(len(new.factors), 16)

    def test_merge_preserves_canonical_order(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        ids = [f.factor_id for f in new.factors]
        expected = sorted(FACTOR_NAMES.keys())
        self.assertEqual(ids, expected)

    def test_merge_preserves_other_factors(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        fi001 = next(f for f in new.factors if f.factor_id == "FI-001")
        orig_fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, orig_fi001.evidence_status)

    def test_merge_propagates_warnings(self):
        self.summary.warnings.append("test-warning")
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        self.assertIn("test-warning", new.warnings)

    def test_merge_propagates_notes(self):
        self.summary.notes.append("test-note")
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        self.assertIn("test-note", new.notes)

    def test_no_duplicate_fi015(self):
        new = merge_climate_change_factor_into_summary(self.summary, self.factor)
        count = sum(1 for f in new.factors if f.factor_id == "FI-015")
        self.assertEqual(count, 1)


# ---------------------------------------------------------------------------
# K. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def setUp(self):
        self.summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=PHASE4_WITH_CLIMATE,
            climate_result=CLIMATE_RESULT,
        )

    def test_summary_has_16_factors(self):
        self.assertEqual(len(self.summary.factors), 16)

    def test_fi015_is_declarado(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015.evidence_status, "DECLARADO")

    def test_fi015_rojo_amarillo_with_high_ghg(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015.inventory_semaphore, "ROJO_AMARILLO")

    def test_fi015_ready_false(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertFalse(fi015.ready_for_impact_assessment)

    def test_fi015_has_two_gaps(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertEqual(len(fi015.gaps), 2)

    def test_canonical_order_preserved(self):
        ids = [f.factor_id for f in self.summary.factors]
        expected = sorted(FACTOR_NAMES.keys())
        self.assertEqual(ids, expected)

    def test_iv08_in_notes(self):
        joined = " ".join(self.summary.notes)
        self.assertIn("IV-08", joined)

    def test_fi001_enriched(self):
        fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_no_duplicate_factor_ids(self):
        ids = [f.factor_id for f in self.summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_summary_phase4_no_climate_fi015_estimado(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase2_data=PHASE2_WITH_ACTIVITY,
            phase4_result=PHASE4_NO_CLIMATE,
        )
        fi015 = next(f for f in summary.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015.evidence_status, "ESTIMADO")

    def test_summary_no_data_fi015_pendiente(self):
        summary = build_inventory_from_phase4_data(
            expediente_id="EIA-TEST",
            phase4_result={
                "expediente_id": "EIA-TEST",
                "climate": None,
                "cartography_plan": None,
            },
        )
        fi015 = next(f for f in summary.factors if f.factor_id == "FI-015")
        self.assertEqual(fi015.evidence_status, "PENDIENTE")

    def test_fi015_ready_false_in_integration(self):
        # IV-08 invariant: FI-015 is never ready for impact assessment in offline mode
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        self.assertFalse(fi015.ready_for_impact_assessment)

    def test_fi015_factor_id_fi015(self):
        fi015 = next((f for f in self.summary.factors if f.factor_id == "FI-015"), None)
        self.assertIsNotNone(fi015)

    def test_gaps_of_fi015_reference_fi015(self):
        fi015 = next(f for f in self.summary.factors if f.factor_id == "FI-015")
        for g in fi015.gaps:
            self.assertEqual(g.factor_id, "FI-015")

    def test_summary_json_serializable(self):
        d = self.summary.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)


# ---------------------------------------------------------------------------
# L. TestPrudenceLexical
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "sin emisiones",
    "carbono neutro",
    "emisiones despreciables",
    "impacto climatico compatible",
    "riesgo climatico bajo",
    "sin afeccion climatica",
    "impacto compatible",
    "impacto moderado",
    "impacto severo",
    "impacto critico",
    "no existe riesgo",
    "ausencia de emisiones",
    "no hay emisiones",
    "impacto positivo al clima",
]


class TestPrudenceLexical(unittest.TestCase):

    def _collect_all_text(self, fi: FactorInventory) -> str:
        parts = [
            fi.description,
            fi.factor_name,
            " ".join(fi.data_sources),
        ]
        for g in fi.gaps:
            parts.append(g.description)
        return " ".join(parts).lower()

    def _check_no_forbidden(self, fi: FactorInventory):
        text = self._collect_all_text(fi)
        for pattern in FORBIDDEN_PATTERNS:
            self.assertNotIn(pattern.lower(), text, f"Forbidden pattern found: '{pattern}'")

    def test_full_data_no_forbidden(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        self._check_no_forbidden(fi)

    def test_climate_only_no_forbidden(self):
        fi = build_climate_change_factor_from_phase_data(climate_result=CLIMATE_RESULT)
        self._check_no_forbidden(fi)

    def test_activity_only_no_forbidden(self):
        fi = build_climate_change_factor_from_phase_data(phase2_data=PHASE2_WITH_ACTIVITY)
        self._check_no_forbidden(fi)

    def test_no_data_no_forbidden(self):
        fi = build_climate_change_factor_from_phase_data()
        self._check_no_forbidden(fi)

    def test_no_ghg_activity_no_forbidden(self):
        fi = build_climate_change_factor_from_phase_data(phase2_data=PHASE2_NO_GHG)
        self._check_no_forbidden(fi)

    def test_ready_always_false_pendiente(self):
        fi = build_climate_change_factor_from_phase_data()
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_ready_always_false_declarado(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        self.assertFalse(fi.ready_for_impact_assessment)

    def test_semaphore_never_verde_any_case(self):
        for phase2, clim in [
            (None, None),
            (PHASE2_WITH_ACTIVITY, None),
            (None, CLIMATE_RESULT),
            (PHASE2_WITH_ACTIVITY, CLIMATE_RESULT),
            (PHASE2_NO_GHG, CLIMATE_RESULT),
        ]:
            fi = build_climate_change_factor_from_phase_data(
                phase2_data=phase2, climate_result=clim
            )
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE for {phase2}, {clim}")

    def test_no_valoracion_terms_in_description(self):
        fi = build_climate_change_factor_from_phase_data(
            phase2_data=PHASE2_WITH_ACTIVITY,
            climate_result=CLIMATE_RESULT,
        )
        desc_lower = fi.description.lower()
        for bad in ("compatible", "moderado", "severo", "crítico", "critico", "irreversible"):
            self.assertNotIn(bad, desc_lower, f"Valoracion term '{bad}' found in description")


if __name__ == "__main__":
    unittest.main()
