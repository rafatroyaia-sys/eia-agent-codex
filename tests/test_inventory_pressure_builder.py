"""
tests/test_inventory_pressure_builder.py -- IV-05
Tests for src/eia_agent/core/inventory_pressure_builder.py

Categorias:
  A. TestExtractActivityText            -- extract_activity_text
  B. TestDetectAirQualityOperations     -- detect_air_quality_relevant_operations
  C. TestDetectNoiseOperations          -- detect_noise_relevant_operations
  D. TestBuildAirQualityFactor          -- build_air_quality_factor_from_phase_data (FI-006)
  E. TestBuildNoiseFactor               -- build_noise_factor_from_phase_data (FI-014)
  F. TestPressureInventoryBuildResult   -- dataclass to_dict / summary
  G. TestBuildPressureInventory         -- build_pressure_inventory_factors_from_phase_data
  H. TestMergePressureFactors           -- merge_pressure_factors_into_summary
  I. TestIntegrationWithIV02            -- build_inventory_from_phase4_data con IV-05
  J. TestPrudenceLexical                -- ausencia de patrones prohibidos en descripciones
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_pressure_builder import (
    PressureInventoryBuildResult,
    build_air_quality_factor_from_phase_data,
    build_noise_factor_from_phase_data,
    build_pressure_inventory_factors_from_phase_data,
    detect_air_quality_relevant_operations,
    detect_noise_relevant_operations,
    extract_activity_text,
    merge_pressure_factors_into_summary,
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

PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-TEST",
    "climate": CLIMATE_STATION,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_EMPTY = {
    "expediente_id": "EIA-TEST",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

# phase2 con operaciones de trituración (alta presion, sin filtracion)
PHASE2_TRITURAR = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - trituración de chatarra metálica", "R13 - cribado y separación"],
    }
}

# phase2 con operaciones de trituración + filtro
PHASE2_TRITURAR_CON_FILTRO = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": [
            "R12 - trituración de chatarra",
            "R13 - cribado",
            "instalación de filtros de mangas para captación de polvo",
        ],
    }
}

# phase2 solo carga/descarga (presion media)
PHASE2_CARGA = {
    "object_scope": {
        "titular": "EMPRESA S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - almacenamiento con carga de material"],
    }
}

# phase2 vacío
PHASE2_EMPTY = {
    "object_scope": {
        "titular": None,
        "coordenadas_wgs84": [],
        "operaciones_incluidas": [],
    }
}

# phase2 con prensa y cizalla (ruido alto)
PHASE2_PRENSA = {
    "object_scope": {
        "titular": "RECIMETAL S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - corte con cizalla", "R13 - prensado de residuos"],
    }
}

# phase2 solo transporte (ruido moderado)
PHASE2_TRANSPORTE = {
    "object_scope": {
        "titular": "EMPRESA S.L.",
        "coordenadas_wgs84": [],
        "operaciones_incluidas": ["R12 - transporte y manipulacion de materiales"],
    }
}

# phase2 con motores diesel
PHASE2_DIESEL = {
    "object_scope": {
        "titular": "EMPRESA S.L.",
        "coordenadas_wgs84": ["28.9773 N, 13.5395 W"],
        "operaciones_incluidas": ["R12 - grupo electrogeno diesel", "R13 - generador"],
    }
}


# ---------------------------------------------------------------------------
# A. TestExtractActivityText
# ---------------------------------------------------------------------------

class TestExtractActivityText(unittest.TestCase):

    def test_extracts_from_phase2_operaciones(self):
        text = extract_activity_text(PHASE2_TRITURAR, None)
        self.assertIn("trituraci", text)

    def test_returns_lowercase(self):
        text = extract_activity_text(PHASE2_TRITURAR, None)
        self.assertEqual(text, text.lower())

    def test_returns_empty_string_when_both_none(self):
        text = extract_activity_text(None, None)
        self.assertEqual(text, "")

    def test_returns_empty_string_when_empty_ops(self):
        text = extract_activity_text(PHASE2_EMPTY, None)
        self.assertEqual(text, "")

    def test_fallback_phase4_object_scope(self):
        phase4 = {
            "object_scope": {
                "operaciones_incluidas": ["R12 - molino de viento"],
            }
        }
        text = extract_activity_text(None, phase4)
        self.assertIn("molino", text)

    def test_phase2_wins_over_phase4(self):
        phase4 = {
            "object_scope": {
                "operaciones_incluidas": ["R99 - operacion inexistente"],
            }
        }
        text = extract_activity_text(PHASE2_TRITURAR, phase4)
        self.assertIn("trituraci", text)

    def test_multiple_ops_joined(self):
        text = extract_activity_text(PHASE2_TRITURAR, None)
        self.assertIn("cribado", text)

    def test_none_phase2_empty_phase4(self):
        text = extract_activity_text(None, PHASE4_EMPTY)
        self.assertEqual(text, "")

    def test_descripcion_actividad_included(self):
        phase2 = {
            "object_scope": {
                "operaciones_incluidas": [],
                "descripcion_actividad": "Instalación de trituración industrial",
            }
        }
        text = extract_activity_text(phase2, None)
        self.assertIn("trituraci", text)

    def test_ops_as_string(self):
        phase2 = {
            "object_scope": {
                "operaciones_incluidas": "R12 - cribado y acopio",
            }
        }
        text = extract_activity_text(phase2, None)
        self.assertIn("cribado", text)


# ---------------------------------------------------------------------------
# B. TestDetectAirQualityOperations
# ---------------------------------------------------------------------------

class TestDetectAirQualityOperations(unittest.TestCase):

    def test_detects_tritura(self):
        found = detect_air_quality_relevant_operations("trituracion de chatarra")
        self.assertIn("tritura", found)

    def test_detects_cribado(self):
        found = detect_air_quality_relevant_operations("cribado y separacion")
        self.assertIn("cribado", found)

    def test_detects_corte(self):
        found = detect_air_quality_relevant_operations("operacion de corte con sierra")
        self.assertIn("corte", found)

    def test_detects_diesel(self):
        found = detect_air_quality_relevant_operations("motor diesel en instalacion")
        self.assertIn("diesel", found)

    def test_no_false_positives_neutral_text(self):
        found = detect_air_quality_relevant_operations("almacenamiento de residuos inertes")
        self.assertEqual(found, [])

    def test_empty_text_returns_empty(self):
        found = detect_air_quality_relevant_operations("")
        self.assertEqual(found, [])

    def test_no_duplicates(self):
        found = detect_air_quality_relevant_operations("tritura tritura tritura")
        self.assertEqual(found.count("tritura"), 1)

    def test_detects_soldadura(self):
        found = detect_air_quality_relevant_operations("proceso de soldadura")
        self.assertIn("soldadura", found)

    def test_detects_emision(self):
        found = detect_air_quality_relevant_operations("control de emision de gases")
        self.assertIn("emision", found)

    def test_detects_polvo(self):
        found = detect_air_quality_relevant_operations("generacion de polvo en acopio")
        self.assertIn("polvo", found)


# ---------------------------------------------------------------------------
# C. TestDetectNoiseOperations
# ---------------------------------------------------------------------------

class TestDetectNoiseOperations(unittest.TestCase):

    def test_detects_cizalla(self):
        found = detect_noise_relevant_operations("corte con cizalla industrial")
        self.assertIn("cizalla", found)

    def test_detects_prensa(self):
        found = detect_noise_relevant_operations("prensado de chatarra")
        self.assertIn("prensa", found)

    def test_detects_compresor(self):
        found = detect_noise_relevant_operations("uso de compresor de aire")
        self.assertIn("compresor", found)

    def test_detects_generador(self):
        found = detect_noise_relevant_operations("grupo generador de emergencia")
        self.assertIn("generador", found)

    def test_detects_camion(self):
        found = detect_noise_relevant_operations("transporte en camion")
        self.assertIn("camion", found)

    def test_no_false_positives(self):
        found = detect_noise_relevant_operations("almacenamiento de residuos")
        self.assertEqual(found, [])

    def test_empty_text_returns_empty(self):
        found = detect_noise_relevant_operations("")
        self.assertEqual(found, [])

    def test_no_duplicates(self):
        found = detect_noise_relevant_operations("prensa prensa prensa")
        self.assertEqual(found.count("prensa"), 1)

    def test_detects_diesel(self):
        found = detect_noise_relevant_operations("motor diesel")
        self.assertIn("diesel", found)

    def test_detects_tritura(self):
        found = detect_noise_relevant_operations("trituracion industrial")
        self.assertIn("tritura", found)


# ---------------------------------------------------------------------------
# D. TestBuildAirQualityFactor
# ---------------------------------------------------------------------------

class TestBuildAirQualityFactor(unittest.TestCase):

    def test_factor_id_is_fi006(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(fi.factor_id, "FI-006")

    def test_without_operations_is_pendiente(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_operations_semaphore_no_consta(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_without_operations_field_mode_no_consta(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.field_mode, "NO_CONSTA")

    def test_high_pressure_without_filtration_is_rojo_amarillo(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_high_pressure_without_filtration_is_estimado(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_high_pressure_with_filtration_is_amarillo(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR_CON_FILTRO, None)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_medium_pressure_is_amarillo(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_CARGA, None)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_never_verde(self):
        for phase2 in [PHASE2_TRITURAR, PHASE2_TRITURAR_CON_FILTRO, PHASE2_CARGA, PHASE2_EMPTY]:
            fi = build_air_quality_factor_from_phase_data(phase2, None)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE prohibido para {phase2}")

    def test_gap_fi006_001_always_present(self):
        for phase2 in [PHASE2_TRITURAR, PHASE2_CARGA, PHASE2_EMPTY]:
            fi = build_air_quality_factor_from_phase_data(phase2, None)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-006-001", gap_ids, f"GAP-FI-006-001 debe estar en {phase2}")

    def test_gap_fi006_002_only_high_pressure_without_filtration(self):
        fi_high = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        gap_ids_high = [g.gap_id for g in fi_high.gaps]
        self.assertIn("GAP-FI-006-002", gap_ids_high)

        fi_filtro = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR_CON_FILTRO, None)
        gap_ids_filtro = [g.gap_id for g in fi_filtro.gaps]
        self.assertNotIn("GAP-FI-006-002", gap_ids_filtro)

        fi_medium = build_air_quality_factor_from_phase_data(PHASE2_CARGA, None)
        gap_ids_medium = [g.gap_id for g in fi_medium.gaps]
        self.assertNotIn("GAP-FI-006-002", gap_ids_medium)

    def test_gap_fi006_002_alta_criticality(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-006-002")
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_fi006_001_is_campo_when_operations(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-006-001")
        self.assertEqual(gap.resolution_mode, "CAMPO")

    def test_ready_for_impact_assessment_always_false(self):
        for phase2 in [PHASE2_TRITURAR, PHASE2_TRITURAR_CON_FILTRO, PHASE2_CARGA, PHASE2_EMPTY]:
            fi = build_air_quality_factor_from_phase_data(phase2, None)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_data_sources_populated_when_operations(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_data_sources_empty_when_no_operations(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.data_sources, [])

    def test_both_none_returns_pendiente(self):
        fi = build_air_quality_factor_from_phase_data(None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_fi006_with_only_phase4(self):
        phase4 = {
            "object_scope": {
                "operaciones_incluidas": ["trituracion de madera"],
            }
        }
        fi = build_air_quality_factor_from_phase_data(None, phase4)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_field_mode_campo_recomendado_when_operations(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_CARGA, None)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_high_pressure_field_mode_campo_recomendado(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_fi006_with_diesel(self):
        fi = build_air_quality_factor_from_phase_data(PHASE2_DIESEL, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")


# ---------------------------------------------------------------------------
# E. TestBuildNoiseFactor
# ---------------------------------------------------------------------------

class TestBuildNoiseFactor(unittest.TestCase):

    def test_factor_id_is_fi014(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        self.assertEqual(fi.factor_id, "FI-014")

    def test_without_operations_is_pendiente(self):
        fi = build_noise_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_without_operations_semaphore_no_consta(self):
        fi = build_noise_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.inventory_semaphore, "NO_CONSTA")

    def test_without_operations_field_mode_no_consta(self):
        fi = build_noise_factor_from_phase_data(PHASE2_EMPTY, None)
        self.assertEqual(fi.field_mode, "NO_CONSTA")

    def test_high_noise_terms_rojo_amarillo(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_high_noise_campo_necesario(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        self.assertEqual(fi.field_mode, "CAMPO_NECESARIO")

    def test_medium_noise_amarillo(self):
        fi = build_noise_factor_from_phase_data(PHASE2_TRANSPORTE, None)
        self.assertEqual(fi.inventory_semaphore, "AMARILLO")

    def test_medium_noise_campo_recomendado(self):
        fi = build_noise_factor_from_phase_data(PHASE2_TRANSPORTE, None)
        self.assertEqual(fi.field_mode, "CAMPO_RECOMENDADO")

    def test_never_verde(self):
        for phase2 in [PHASE2_PRENSA, PHASE2_TRANSPORTE, PHASE2_DIESEL, PHASE2_EMPTY]:
            fi = build_noise_factor_from_phase_data(phase2, None)
            self.assertNotEqual(fi.inventory_semaphore, "VERDE", f"VERDE prohibido para {phase2}")

    def test_gap_fi014_001_always_present(self):
        for phase2 in [PHASE2_PRENSA, PHASE2_TRANSPORTE, PHASE2_EMPTY]:
            fi = build_noise_factor_from_phase_data(phase2, None)
            gap_ids = [g.gap_id for g in fi.gaps]
            self.assertIn("GAP-FI-014-001", gap_ids)

    def test_gap_fi014_002_only_high_noise(self):
        fi_high = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        gap_ids_high = [g.gap_id for g in fi_high.gaps]
        self.assertIn("GAP-FI-014-002", gap_ids_high)

        fi_medium = build_noise_factor_from_phase_data(PHASE2_TRANSPORTE, None)
        gap_ids_medium = [g.gap_id for g in fi_medium.gaps]
        self.assertNotIn("GAP-FI-014-002", gap_ids_medium)

    def test_gap_fi014_001_alta_when_high_noise(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-014-001")
        self.assertEqual(gap.criticality, "ALTA")

    def test_gap_fi014_001_media_when_medium_noise(self):
        fi = build_noise_factor_from_phase_data(PHASE2_TRANSPORTE, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-014-001")
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_fi014_002_media_criticality(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-014-002")
        self.assertEqual(gap.criticality, "MEDIA")

    def test_gap_fi014_001_campo_resolution(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        gap = next(g for g in fi.gaps if g.gap_id == "GAP-FI-014-001")
        self.assertEqual(gap.resolution_mode, "CAMPO")

    def test_ready_for_impact_assessment_always_false(self):
        for phase2 in [PHASE2_PRENSA, PHASE2_TRANSPORTE, PHASE2_EMPTY]:
            fi = build_noise_factor_from_phase_data(phase2, None)
            self.assertFalse(fi.ready_for_impact_assessment)

    def test_both_none_returns_pendiente(self):
        fi = build_noise_factor_from_phase_data(None, None)
        self.assertEqual(fi.evidence_status, "PENDIENTE")

    def test_high_noise_estimado(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        self.assertEqual(fi.evidence_status, "ESTIMADO")

    def test_data_sources_populated_when_operations(self):
        fi = build_noise_factor_from_phase_data(PHASE2_PRENSA, None)
        self.assertTrue(len(fi.data_sources) > 0)

    def test_diesel_is_high_noise(self):
        fi = build_noise_factor_from_phase_data(PHASE2_DIESEL, None)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")

    def test_tritura_is_high_noise(self):
        fi = build_noise_factor_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(fi.inventory_semaphore, "ROJO_AMARILLO")


# ---------------------------------------------------------------------------
# F. TestPressureInventoryBuildResult
# ---------------------------------------------------------------------------

class TestPressureInventoryBuildResult(unittest.TestCase):

    def _make_result(self):
        return build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)

    def test_factors_has_two_elements(self):
        r = self._make_result()
        self.assertEqual(len(r.factors), 2)

    def test_first_factor_is_fi006(self):
        r = self._make_result()
        self.assertEqual(r.factors[0].factor_id, "FI-006")

    def test_second_factor_is_fi014(self):
        r = self._make_result()
        self.assertEqual(r.factors[1].factor_id, "FI-014")

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

    def test_summary_contains_fi006(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("FI-006", s)

    def test_summary_contains_fi014(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("FI-014", s)

    def test_warnings_and_notes_are_lists(self):
        r = self._make_result()
        self.assertIsInstance(r.warnings, list)
        self.assertIsInstance(r.notes, list)


# ---------------------------------------------------------------------------
# G. TestBuildPressureInventory
# ---------------------------------------------------------------------------

class TestBuildPressureInventory(unittest.TestCase):

    def test_returns_two_factors(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(len(r.factors), 2)

    def test_fi006_first(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(r.factors[0].factor_id, "FI-006")

    def test_fi014_second(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        self.assertEqual(r.factors[1].factor_id, "FI-014")

    def test_both_none_returns_pendiente_both(self):
        r = build_pressure_inventory_factors_from_phase_data(None, None)
        self.assertEqual(r.factors[0].evidence_status, "PENDIENTE")
        self.assertEqual(r.factors[1].evidence_status, "PENDIENTE")

    def test_warnings_when_pendiente(self):
        r = build_pressure_inventory_factors_from_phase_data(None, None)
        combined = " ".join(r.warnings)
        self.assertIn("FI-006", combined)
        self.assertIn("FI-014", combined)

    def test_notes_always_present(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        self.assertTrue(len(r.notes) > 0)

    def test_high_pressure_with_phase4(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, PHASE4_WITH_CLIMATE)
        self.assertEqual(r.factors[0].inventory_semaphore, "ROJO_AMARILLO")


# ---------------------------------------------------------------------------
# H. TestMergePressureFactors
# ---------------------------------------------------------------------------

class TestMergePressureFactors(unittest.TestCase):

    def _base_summary(self):
        factors = build_all_empty_factors()
        return build_inventory_summary("EIA-TEST", factors)

    def test_merge_replaces_fi006(self):
        summary = self._base_summary()
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        fi006 = next(f for f in new_summary.factors if f.factor_id == "FI-006")
        self.assertEqual(fi006.evidence_status, "ESTIMADO")

    def test_merge_replaces_fi014(self):
        summary = self._base_summary()
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_PRENSA, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        fi014 = next(f for f in new_summary.factors if f.factor_id == "FI-014")
        self.assertEqual(fi014.inventory_semaphore, "ROJO_AMARILLO")

    def test_merge_preserves_16_factors(self):
        summary = self._base_summary()
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        self.assertEqual(len(new_summary.factors), len(FACTOR_NAMES))

    def test_merge_no_duplicates(self):
        summary = self._base_summary()
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_merge_canonical_order(self):
        summary = self._base_summary()
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        ids = [f.factor_id for f in new_summary.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_merge_does_not_mutate_original(self):
        summary = self._base_summary()
        orig_fi006 = next(f for f in summary.factors if f.factor_id == "FI-006")
        orig_status = orig_fi006.evidence_status
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        merge_pressure_factors_into_summary(summary, r.factors)
        # original unchanged
        still_fi006 = next(f for f in summary.factors if f.factor_id == "FI-006")
        self.assertEqual(still_fi006.evidence_status, orig_status)

    def test_other_factors_unchanged_after_merge(self):
        summary = self._base_summary()
        fi001_before = next(f for f in summary.factors if f.factor_id == "FI-001")
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        fi001_after = next(f for f in new_summary.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001_before.evidence_status, fi001_after.evidence_status)

    def test_merge_preserves_summary_warnings(self):
        summary = self._base_summary()
        summary.warnings.append("test warning previo")
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        new_summary = merge_pressure_factors_into_summary(summary, r.factors)
        self.assertIn("test warning previo", new_summary.warnings)


# ---------------------------------------------------------------------------
# I. TestIntegrationWithIV02
# ---------------------------------------------------------------------------

class TestIntegrationWithIV02(unittest.TestCase):

    def test_no_phase2_fi006_pendiente(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        fi006 = next(f for f in result.factors if f.factor_id == "FI-006")
        self.assertEqual(fi006.evidence_status, "PENDIENTE")

    def test_no_phase2_fi014_pendiente(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        fi014 = next(f for f in result.factors if f.factor_id == "FI-014")
        self.assertEqual(fi014.evidence_status, "PENDIENTE")

    def test_with_phase2_triturar_fi006_estimado(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        fi006 = next(f for f in result.factors if f.factor_id == "FI-006")
        self.assertEqual(fi006.evidence_status, "ESTIMADO")

    def test_with_phase2_triturar_fi006_rojo_amarillo(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        fi006 = next(f for f in result.factors if f.factor_id == "FI-006")
        self.assertEqual(fi006.inventory_semaphore, "ROJO_AMARILLO")

    def test_with_phase2_prensa_fi014_rojo_amarillo(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_PRENSA)
        fi014 = next(f for f in result.factors if f.factor_id == "FI-014")
        self.assertEqual(fi014.inventory_semaphore, "ROJO_AMARILLO")

    def test_with_phase2_prensa_fi014_campo_necesario(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_PRENSA)
        fi014 = next(f for f in result.factors if f.factor_id == "FI-014")
        self.assertEqual(fi014.field_mode, "CAMPO_NECESARIO")

    def test_result_has_16_factors(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        self.assertEqual(len(result.factors), len(FACTOR_NAMES))

    def test_no_duplicate_factor_ids(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(len(ids), len(set(ids)))

    def test_fi001_still_enriched(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertNotEqual(fi001.evidence_status, "PENDIENTE")

    def test_canonical_order(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_filtro_operation_reduces_risk(self):
        result_sin = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        result_con = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR_CON_FILTRO)
        fi006_sin = next(f for f in result_sin.factors if f.factor_id == "FI-006")
        fi006_con = next(f for f in result_con.factors if f.factor_id == "FI-006")
        self.assertEqual(fi006_sin.inventory_semaphore, "ROJO_AMARILLO")
        self.assertEqual(fi006_con.inventory_semaphore, "AMARILLO")

    def test_warnings_propagated(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        combined = " ".join(result.warnings)
        # Sin phase2 ambos factores PENDIENTE → warnings de IV-05 en resultado
        self.assertIn("FI-006", combined)

    def test_notes_contain_iv05_info(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE, phase2_data=PHASE2_TRITURAR)
        combined = " ".join(result.notes)
        self.assertIn("IV-05", combined)


# ---------------------------------------------------------------------------
# J. TestPrudenceLexical
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    "sin emisiones",
    "no hay polvo",
    "sin ruido",
    "cumple limites",
    "cumple límites",
    "sin afeccion acustica",
    "sin afección acústica",
    "impacto compatible",
    "moderado",
    "severo",
    "critico",
    "crítico",
    "sin afecci",
    "no existe afecci",
    "no hay afecci",
    "inexistente",
]


class TestPrudenceLexical(unittest.TestCase):

    def _all_descriptions(self, phase2):
        r = build_pressure_inventory_factors_from_phase_data(phase2, None)
        texts = []
        for f in r.factors:
            texts.append(f.description.lower())
            for g in f.gaps:
                texts.append(g.description.lower())
        return texts

    def _check_no_forbidden(self, phase2, label):
        texts = self._all_descriptions(phase2)
        for text in texts:
            for pat in _FORBIDDEN_PATTERNS:
                self.assertNotIn(pat, text, f"Patron prohibido '{pat}' en {label}: {text[:100]}")

    def test_no_forbidden_tritura(self):
        self._check_no_forbidden(PHASE2_TRITURAR, "PHASE2_TRITURAR")

    def test_no_forbidden_tritura_con_filtro(self):
        self._check_no_forbidden(PHASE2_TRITURAR_CON_FILTRO, "PHASE2_TRITURAR_CON_FILTRO")

    def test_no_forbidden_carga(self):
        self._check_no_forbidden(PHASE2_CARGA, "PHASE2_CARGA")

    def test_no_forbidden_empty(self):
        self._check_no_forbidden(PHASE2_EMPTY, "PHASE2_EMPTY")

    def test_no_forbidden_prensa(self):
        self._check_no_forbidden(PHASE2_PRENSA, "PHASE2_PRENSA")

    def test_no_forbidden_transporte(self):
        self._check_no_forbidden(PHASE2_TRANSPORTE, "PHASE2_TRANSPORTE")

    def test_no_forbidden_diesel(self):
        self._check_no_forbidden(PHASE2_DIESEL, "PHASE2_DIESEL")

    def test_no_forbidden_none_inputs(self):
        self._check_no_forbidden(None, "None")

    def test_description_mentions_detected_terms(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_TRITURAR, None)
        fi006 = r.factors[0]
        # La descripcion debe mencionar los terminos detectados
        self.assertIn("tritura", fi006.description.lower())

    def test_fi014_description_mentions_noise_terms(self):
        r = build_pressure_inventory_factors_from_phase_data(PHASE2_PRENSA, None)
        fi014 = r.factors[1]
        # alguno de los terminos detectados aparece en la descripcion
        found = detect_noise_relevant_operations(extract_activity_text(PHASE2_PRENSA, None))
        desc_lower = fi014.description.lower()
        self.assertTrue(any(t in desc_lower for t in found))

    def test_prudence_no_impact_valuation(self):
        # No se afirman impactos valorados (moderado/severo/critico)
        for phase2 in [PHASE2_TRITURAR, PHASE2_PRENSA]:
            r = build_pressure_inventory_factors_from_phase_data(phase2, None)
            for f in r.factors:
                self.assertNotIn("moderado", f.description.lower())
                self.assertNotIn("severo", f.description.lower())

    def test_prudence_no_compliance_claims(self):
        for phase2 in [PHASE2_TRITURAR_CON_FILTRO, PHASE2_CARGA]:
            r = build_pressure_inventory_factors_from_phase_data(phase2, None)
            for f in r.factors:
                self.assertNotIn("cumple", f.description.lower())


if __name__ == "__main__":
    unittest.main()
