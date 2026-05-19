"""
tests/test_inventory_builder.py — IV-02
Tests for src/eia_agent/core/inventory_builder.py

Categorias:
  A. TestLoadJsonFile                  — load_json_file
  B. TestInventoryBuildResult          — dataclass to_dict / summary
  C. TestBuildClimateFactorComplete    — build_climate_factor_from_phase4 con datos completos
  D. TestBuildClimateFactorPartial     — sin clasificacion climatica
  E. TestBuildClimateFactorEdge        — sin estacion / lejana / propagacion de warnings
  F. TestBuildBaseFactor               — build_base_factor (todos los factores)
  G. TestBuildInventoryFromPhase4Data  — build_inventory_from_phase4_data
  H. TestBuildInventoryFromPhase4      — build_inventory_from_phase4 con fixtures en disco
  I. TestFixtureLanzarote              — fixture realista Lanzarote (BWh, CL-06, VERDE)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_builder import (
    InventoryBuildResult,
    build_base_factor,
    build_climate_factor_from_phase4,
    build_inventory_from_phase4,
    build_inventory_from_phase4_data,
    load_json_file,
)
from eia_agent.core.inventory_model import FACTOR_NAMES, InventorySummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLIMATE_COMPLETE = {
    "selected_station": {
        "station_id": "C029O",
        "name": "Arrecife/Lanzarote Aeropuerto",
    },
    "station_distance_km": 3.2,
    "station_selection_status": "OPTIMA",
    "climate_classification": {
        "koppen_code": "BWh",
        "koppen_label": "Desierto calido",
        "martonne_index": 4.2,
        "martonne_label": "Arido",
        "dry_months_gaussen": 12,
        "dry_months_names": [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ],
        "annual_temperature_c": 20.4,
        "annual_precipitation_mm": 141.2,
        "notes": [],
    },
    "climogram_path": "clima/climograma_C029O.png",
    "description_md": "Clima de tipo BWh.",
    "warnings": [],
    "notes": ["Datos de periodo normal 1991-2020."],
}

CLIMATE_PARTIAL = {
    "selected_station": {
        "station_id": "C029O",
        "name": "Arrecife/Lanzarote Aeropuerto",
    },
    "station_distance_km": 8.5,
    "station_selection_status": "ACEPTABLE",
    "climate_classification": None,
    "warnings": ["Clasificacion no disponible por datos insuficientes."],
    "notes": [],
}

CLIMATE_NO_STATION = {
    "selected_station": None,
    "station_distance_km": None,
    "station_selection_status": "NO_DISPONIBLE",
    "climate_classification": None,
    "warnings": ["No hay estaciones disponibles en el area."],
    "notes": [],
}

CLIMATE_LEJANA = {
    "selected_station": {
        "station_id": "Z999X",
        "name": "Estacion Lejana Test",
    },
    "station_distance_km": 35.0,
    "station_selection_status": "LEJANA",
    "climate_classification": {
        "koppen_code": "BSh",
        "koppen_label": "Estepa calida",
        "martonne_index": 12.1,
        "martonne_label": "Semi-arido",
        "dry_months_gaussen": 6,
        "dry_months_names": [
            "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
        ],
        "annual_temperature_c": 18.5,
        "annual_precipitation_mm": 250.0,
        "notes": [],
    },
    "warnings": [],
    "notes": [],
}

PHASE4_WITH_CLIMATE = {
    "expediente_id": "EIA-2026-TEST",
    "climate": CLIMATE_COMPLETE,
    "cartography_plan": {"maps": []},
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}

PHASE4_MINIMAL = {
    "expediente_id": "EIA-2026-MINIMAL",
    "climate": None,
    "cartography_plan": None,
    "ready_for_phase5": False,
    "warnings": [],
    "notes": [],
}


# ---------------------------------------------------------------------------
# A. TestLoadJsonFile
# ---------------------------------------------------------------------------

class TestLoadJsonFile(unittest.TestCase):

    def test_load_valid_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.json"
            p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
            result = load_json_file(p)
            self.assertEqual(result, {"key": "value"})

    def test_load_nested_json(self):
        data = {"a": [1, 2, 3], "b": {"c": True}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "nested.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_json_file(p), data)

    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_json_file("/ruta/que/no/existe/test.json")

    def test_invalid_json_raises_value_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{not valid json}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_json_file(p)

    def test_accepts_path_object(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ok.json"
            p.write_text('{"x": 1}', encoding="utf-8")
            self.assertEqual(load_json_file(p), {"x": 1})

    def test_accepts_string_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ok.json"
            p.write_text('{"y": 2}', encoding="utf-8")
            self.assertEqual(load_json_file(str(p)), {"y": 2})

    def test_empty_json_object(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.json"
            p.write_text("{}", encoding="utf-8")
            self.assertEqual(load_json_file(p), {})

    def test_error_message_contains_path(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load_json_file("/no/existe/archivo.json")
        self.assertIn("archivo.json", str(ctx.exception))


# ---------------------------------------------------------------------------
# B. TestInventoryBuildResult
# ---------------------------------------------------------------------------

class TestInventoryBuildResult(unittest.TestCase):

    def _make_summary(self) -> InventorySummary:
        from eia_agent.core.inventory_model import build_all_empty_factors, build_inventory_summary
        factors = build_all_empty_factors()
        return build_inventory_summary("EIA-TEST", factors)

    def test_to_dict_has_required_keys(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-TEST",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        d = r.to_dict()
        for key in ("expediente_id", "factor_count", "ready_count",
                    "all_ready_for_phase6", "rendered_files", "warnings", "notes"):
            self.assertIn(key, d)

    def test_to_dict_json_serializable(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-SERIAL",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        json_str = json.dumps(r.to_dict())
        self.assertIn("EIA-SERIAL", json_str)

    def test_summary_contains_expediente_id(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-ID-PRUEBA",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        self.assertIn("EIA-ID-PRUEBA", r.summary())

    def test_summary_contains_factor_count(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        self.assertIn("16", r.summary())

    def test_summary_shows_rendered_files_count_when_present(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
            rendered_files=["/path/a.md", "/path/b.md"],
        )
        self.assertIn("2", r.summary())

    def test_summary_shows_no_file_count_when_empty(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        self.assertNotIn("Archivos", r.summary())

    def test_summary_shows_warnings(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
            warnings=["Aviso de test."],
        )
        self.assertIn("Aviso de test.", r.summary())

    def test_summary_shows_notes(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
            notes=["Nota de test."],
        )
        self.assertIn("Nota de test.", r.summary())

    def test_all_ready_for_phase6_is_false_for_empty_factors(self):
        s = self._make_summary()
        r = InventoryBuildResult(
            expediente_id="EIA-X",
            inventory_summary=s,
            factor_count=16,
            ready_count=0,
        )
        self.assertFalse(r.to_dict()["all_ready_for_phase6"])


# ---------------------------------------------------------------------------
# C. TestBuildClimateFactorComplete
# ---------------------------------------------------------------------------

class TestBuildClimateFactorComplete(unittest.TestCase):

    def setUp(self):
        self.factor = build_climate_factor_from_phase4(CLIMATE_COMPLETE)

    def test_factor_id_is_fi001(self):
        self.assertEqual(self.factor.factor_id, "FI-001")

    def test_evidence_status_confirmado_gabinete(self):
        self.assertEqual(self.factor.evidence_status, "CONFIRMADO_GABINETE")

    def test_field_mode_gabinete_suficiente(self):
        self.assertEqual(self.factor.field_mode, "GABINETE_SUFICIENTE")

    def test_ready_for_impact_assessment_true(self):
        self.assertTrue(self.factor.ready_for_impact_assessment)

    def test_semaphore_verde(self):
        self.assertEqual(self.factor.inventory_semaphore, "VERDE")

    def test_no_gaps(self):
        self.assertEqual(len(self.factor.gaps), 0)

    def test_description_contains_station_name(self):
        self.assertIn("Arrecife/Lanzarote", self.factor.description)

    def test_description_contains_koppen_code(self):
        self.assertIn("BWh", self.factor.description)

    def test_description_contains_temperature(self):
        self.assertIn("20.4", self.factor.description)

    def test_description_contains_precipitation(self):
        self.assertIn("141.2", self.factor.description)

    def test_description_contains_martonne(self):
        self.assertIn("Martonne", self.factor.description)

    def test_description_dry_months_todos_meses(self):
        self.assertIn("todos los meses", self.factor.description)

    def test_data_sources_includes_cl06(self):
        self.assertTrue(any("CL-06" in s for s in self.factor.data_sources))

    def test_data_sources_includes_station_name(self):
        self.assertTrue(any("Arrecife" in s for s in self.factor.data_sources))

    def test_data_sources_includes_normales(self):
        self.assertTrue(any("normales" in s.lower() for s in self.factor.data_sources))

    def test_note_procede_fase4(self):
        self.assertTrue(any("Fase 4 offline" in n for n in self.factor.notes))

    def test_no_classification_warning(self):
        # Con datos completos no debe haber aviso de clasificacion
        for w in self.factor.warnings:
            self.assertNotIn("clasificacion climatica completa", w.lower())

    def test_field_mode_justification_present(self):
        self.assertGreater(len(self.factor.field_mode_justification or ""), 0)

    def test_semaphore_justification_contains_koppen(self):
        self.assertIn("BWh", self.factor.semaphore_justification or "")


# ---------------------------------------------------------------------------
# D. TestBuildClimateFactorPartial
# ---------------------------------------------------------------------------

class TestBuildClimateFactorPartial(unittest.TestCase):

    def setUp(self):
        self.factor = build_climate_factor_from_phase4(CLIMATE_PARTIAL)

    def test_evidence_status_declarado(self):
        self.assertEqual(self.factor.evidence_status, "DECLARADO")

    def test_field_mode_gabinete_suficiente(self):
        self.assertEqual(self.factor.field_mode, "GABINETE_SUFICIENTE")

    def test_ready_for_impact_assessment_false(self):
        self.assertFalse(self.factor.ready_for_impact_assessment)

    def test_semaphore_not_verde(self):
        self.assertNotEqual(self.factor.inventory_semaphore, "VERDE")

    def test_has_one_gap(self):
        self.assertEqual(len(self.factor.gaps), 1)

    def test_gap_id_fi001(self):
        self.assertEqual(self.factor.gaps[0].gap_id, "GAP-FI-001-001")

    def test_gap_field_clasificacion(self):
        self.assertEqual(self.factor.gaps[0].field, "clasificacion_climatica")

    def test_gap_criticality_media(self):
        self.assertEqual(self.factor.gaps[0].criticality, "MEDIA")

    def test_warning_about_missing_classification(self):
        self.assertTrue(len(self.factor.warnings) > 0)
        has_classif_warning = any(
            "clasificacion" in w.lower() or "koppen" in w.lower()
            for w in self.factor.warnings
        )
        self.assertTrue(has_classif_warning)

    def test_description_mentions_no_classification(self):
        self.assertIn("clasificacion", self.factor.description.lower())

    def test_data_sources_includes_cl06(self):
        self.assertTrue(any("CL-06" in s for s in self.factor.data_sources))

    def test_upstream_warnings_propagated(self):
        has_upstream = any("Clasificacion no disponible" in w for w in self.factor.warnings)
        self.assertTrue(has_upstream)


# ---------------------------------------------------------------------------
# E. TestBuildClimateFactorEdge
# ---------------------------------------------------------------------------

class TestBuildClimateFactorEdge(unittest.TestCase):

    def test_no_station_evidence_pendiente(self):
        factor = build_climate_factor_from_phase4(CLIMATE_NO_STATION)
        self.assertEqual(factor.evidence_status, "PENDIENTE")

    def test_no_station_field_mode_no_consta(self):
        factor = build_climate_factor_from_phase4(CLIMATE_NO_STATION)
        self.assertEqual(factor.field_mode, "NO_CONSTA")

    def test_no_station_ready_false(self):
        factor = build_climate_factor_from_phase4(CLIMATE_NO_STATION)
        self.assertFalse(factor.ready_for_impact_assessment)

    def test_no_station_warning_present(self):
        factor = build_climate_factor_from_phase4(CLIMATE_NO_STATION)
        self.assertTrue(len(factor.warnings) > 0)

    def test_no_station_upstream_warning_propagated(self):
        factor = build_climate_factor_from_phase4(CLIMATE_NO_STATION)
        has_upstream = any("estaciones disponibles" in w for w in factor.warnings)
        self.assertTrue(has_upstream)

    def test_lejana_warning_present(self):
        factor = build_climate_factor_from_phase4(CLIMATE_LEJANA)
        has_lejana_warning = any("LEJANA" in w or "lejana" in w.lower() for w in factor.warnings)
        self.assertTrue(has_lejana_warning)

    def test_lejana_warning_contains_distance(self):
        factor = build_climate_factor_from_phase4(CLIMATE_LEJANA)
        lejana_warnings = [w for w in factor.warnings if "LEJANA" in w or "35" in w]
        self.assertTrue(len(lejana_warnings) > 0)

    def test_lejana_still_confirmed_gabinete(self):
        factor = build_climate_factor_from_phase4(CLIMATE_LEJANA)
        self.assertEqual(factor.evidence_status, "CONFIRMADO_GABINETE")

    def test_notes_from_pipeline_propagated(self):
        data = {**CLIMATE_COMPLETE, "notes": ["Nota adicional del pipeline."]}
        factor = build_climate_factor_from_phase4(data)
        has_note = any("Nota adicional" in n for n in factor.notes)
        self.assertTrue(has_note)

    def test_warnings_from_pipeline_propagated(self):
        data = {**CLIMATE_PARTIAL, "warnings": ["Advertencia del pipeline externo."]}
        factor = build_climate_factor_from_phase4(data)
        has_w = any("Advertencia del pipeline" in w for w in factor.warnings)
        self.assertTrue(has_w)

    def test_factor_id_always_fi001(self):
        for climate in [CLIMATE_COMPLETE, CLIMATE_PARTIAL, CLIMATE_NO_STATION, CLIMATE_LEJANA]:
            factor = build_climate_factor_from_phase4(climate)
            self.assertEqual(factor.factor_id, "FI-001")


# ---------------------------------------------------------------------------
# F. TestBuildBaseFactor
# ---------------------------------------------------------------------------

class TestBuildBaseFactor(unittest.TestCase):

    BASE_IDS = [f"FI-{i:03d}" for i in range(2, 17)]  # FI-002...FI-016

    def test_all_factor_ids_valid(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.factor_id, fid)

    def test_evidence_status_pendiente(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.evidence_status, "PENDIENTE", f"{fid}: evidence_status")

    def test_field_mode_no_consta(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.field_mode, "NO_CONSTA", f"{fid}: field_mode")

    def test_semaphore_no_consta(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.inventory_semaphore, "NO_CONSTA", f"{fid}: semaphore")

    def test_ready_false(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertFalse(factor.ready_for_impact_assessment, f"{fid}: ready")

    def test_has_one_gap(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(len(factor.gaps), 1, f"{fid}: gap count")

    def test_gap_id_pattern(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            expected_gap_id = f"GAP-{fid}-001"
            self.assertEqual(factor.gaps[0].gap_id, expected_gap_id, f"{fid}: gap_id")

    def test_gap_factor_id_matches(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.gaps[0].factor_id, fid)

    def test_gap_field_datos_generales(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.gaps[0].field, "datos_generales")

    def test_gap_criticality_media(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.gaps[0].criticality, "MEDIA")

    def test_gap_resolution_mode_gabinete(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.gaps[0].resolution_mode, "GABINETE")

    def test_gap_status_pendiente(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertEqual(factor.gaps[0].status, "PENDIENTE")

    def test_has_at_least_one_note(self):
        for fid in self.BASE_IDS:
            factor = build_base_factor(fid)
            self.assertGreater(len(factor.notes), 0)

    def test_custom_reason_used_in_gap(self):
        factor = build_base_factor("FI-005", reason="Razon personalizada para test.")
        self.assertIn("Razon personalizada", factor.gaps[0].description)

    def test_fi001_also_works_as_base(self):
        factor = build_base_factor("FI-001")
        self.assertEqual(factor.factor_id, "FI-001")
        self.assertEqual(factor.evidence_status, "PENDIENTE")


# ---------------------------------------------------------------------------
# G. TestBuildInventoryFromPhase4Data
# ---------------------------------------------------------------------------

class TestBuildInventoryFromPhase4Data(unittest.TestCase):

    def test_returns_inventory_summary(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        self.assertIsInstance(result, InventorySummary)

    def test_summary_has_16_factors(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        self.assertEqual(result.total_factors, 16)

    def test_expediente_id_preserved(self):
        result = build_inventory_from_phase4_data("EIA-MI-ID", PHASE4_WITH_CLIMATE)
        self.assertEqual(result.expediente_id, "EIA-MI-ID")

    def test_fi001_climate_factor_when_climate_provided(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_fi001_base_when_no_climate(self):
        result = build_inventory_from_phase4_data("EIA-NODATA", PHASE4_MINIMAL)
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, "PENDIENTE")

    def test_fi002_fi016_are_base_factors(self):
        # FI-001 enriquecido por CL-06; FI-005 y FI-016 enriquecidos por IV-03.
        # FI-011 enriquecido por IV-04 (has_coords=True via estacion climatica,
        # has_plan=True via plan embebido {"maps":[]}). FI-013 sigue PENDIENTE
        # (no phase2_data → sin promotor/actividad).
        # FI-006/FI-014 PENDIENTE (no phase2_data → sin operaciones).
        # FI-009/FI-010 enriquecidos por IV-06 (has_plan=True via plan embebido {"maps":[]}).
        # FI-002/FI-003/FI-004 enriquecidos por IV-07 (has_plan=True via plan embebido {"maps":[]}).
        # FI-015 enriquecido por IV-08 (has_climate=True via PHASE4_WITH_CLIMATE).
        # FI-012 enriquecido por IV-09 (has_location=True via station proxy en PHASE4_WITH_CLIMATE).
        # FI-007/FI-008 enriquecidos por IV-10 (has_location=True via station proxy).
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        enriched_ids = {
            "FI-001", "FI-002", "FI-003", "FI-004",
            "FI-005", "FI-007", "FI-008", "FI-009", "FI-010",
            "FI-011", "FI-012", "FI-015", "FI-016",
        }
        for factor in result.factors:
            if factor.factor_id not in enriched_ids:
                self.assertEqual(factor.evidence_status, "PENDIENTE", factor.factor_id)

    def test_all_factor_ids_present(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        ids = {f.factor_id for f in result.factors}
        expected = set(FACTOR_NAMES.keys())
        self.assertEqual(ids, expected)

    def test_all_ready_for_phase6_false(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        self.assertFalse(result.all_ready_for_phase6)

    def test_warning_when_no_climate(self):
        result = build_inventory_from_phase4_data("EIA-NODATA", PHASE4_MINIMAL)
        has_w = any("climaticos" in w.lower() or "FI-001" in w for w in result.warnings)
        self.assertTrue(has_w)

    def test_warning_when_no_cartography(self):
        result = build_inventory_from_phase4_data("EIA-NODATA", PHASE4_MINIMAL)
        has_w = any("cartograf" in w.lower() for w in result.warnings)
        self.assertTrue(has_w)

    def test_external_climate_overrides_embedded(self):
        # climate_result explícito tiene prioridad sobre phase4_result["climate"]
        result = build_inventory_from_phase4_data(
            "EIA-OVERRIDE",
            PHASE4_WITH_CLIMATE,
            climate_result=CLIMATE_PARTIAL,
        )
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        # CLIMATE_PARTIAL → DECLARADO (sin clasificacion completa)
        self.assertEqual(fi001.evidence_status, "DECLARADO")

    def test_factors_ordered_canonically(self):
        result = build_inventory_from_phase4_data("EIA-TEST", PHASE4_WITH_CLIMATE)
        ids = [f.factor_id for f in result.factors]
        self.assertEqual(ids, sorted(FACTOR_NAMES.keys()))

    def test_climate_from_embedded_when_no_external(self):
        # PHASE4_WITH_CLIMATE embeds CLIMATE_COMPLETE in "climate"
        result = build_inventory_from_phase4_data(
            "EIA-EMBEDDED",
            PHASE4_WITH_CLIMATE,
            climate_result=None,
        )
        fi001 = next(f for f in result.factors if f.factor_id == "FI-001")
        self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")


# ---------------------------------------------------------------------------
# H. TestBuildInventoryFromPhase4
# ---------------------------------------------------------------------------

class TestBuildInventoryFromPhase4(unittest.TestCase):

    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_raises_if_phase4_result_missing(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            with self.assertRaises(FileNotFoundError):
                build_inventory_from_phase4(exp)

    def test_loads_phase4_result(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            self.assertIsInstance(result, InventoryBuildResult)

    def test_expediente_id_from_json(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            self.assertEqual(result.expediente_id, "EIA-2026-TEST")

    def test_factor_count_is_16(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            self.assertEqual(result.factor_count, 16)

    def test_fi001_confirmado_gabinete_when_climate_embedded(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            fi001 = next(
                f for f in result.inventory_summary.factors if f.factor_id == "FI-001"
            )
            self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_reads_separate_climate_file(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-SEP"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_MINIMAL)
            self._write_json(exp / "clima" / "phase4_climate_result.json", CLIMATE_COMPLETE)
            result = build_inventory_from_phase4(exp)
            fi001 = next(
                f for f in result.inventory_summary.factors if f.factor_id == "FI-001"
            )
            self.assertEqual(fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_no_write_outputs_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            self.assertEqual(result.rendered_files, [])

    def test_write_outputs_creates_files(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-WRITE"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp, write_outputs=True)
            self.assertGreater(len(result.rendered_files), 0)

    def test_write_outputs_creates_16_factor_files(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-WRITE"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp, write_outputs=True)
            md_files = [f for f in result.rendered_files if f.endswith(".md")]
            # 16 factor files + resumen
            self.assertGreaterEqual(len(md_files), 17)

    def test_write_outputs_creates_summary_json(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-WRITE"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp, write_outputs=True)
            json_files = [f for f in result.rendered_files if f.endswith(".json")]
            self.assertGreater(len(json_files), 0)

    def test_write_outputs_in_custom_output_dir(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-WRITE"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(
                exp, write_outputs=True, output_dir="mi_inventario"
            )
            out_dir = exp / "mi_inventario"
            self.assertTrue(out_dir.exists())

    def test_custom_phase4_result_path(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-CUSTOM"
            exp.mkdir()
            custom = Path(d) / "custom_phase4.json"
            self._write_json(custom, PHASE4_MINIMAL)
            result = build_inventory_from_phase4(exp, phase4_result_path=custom)
            self.assertEqual(result.expediente_id, "EIA-2026-MINIMAL")

    def test_warning_if_separate_climate_missing(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-MISS"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_MINIMAL)
            non_existent = Path(d) / "no_existe.json"
            result = build_inventory_from_phase4(
                exp,
                phase4_climate_result_path=non_existent,
            )
            has_w = any("climate" in w.lower() or "no encontrado" in w for w in result.warnings)
            self.assertTrue(has_w)

    def test_all_ready_false(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-TEST"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp)
            self.assertFalse(result.inventory_summary.all_ready_for_phase6)

    def test_inventory_summary_json_file_loadable(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-JSON"
            exp.mkdir()
            self._write_json(exp / "fase4" / "phase4_result.json", PHASE4_WITH_CLIMATE)
            result = build_inventory_from_phase4(exp, write_outputs=True)
            summary_json = [f for f in result.rendered_files if "inventory_summary" in f]
            self.assertEqual(len(summary_json), 1)
            data = json.loads(Path(summary_json[0]).read_text(encoding="utf-8"))
            self.assertIn("expediente_id", data)


# ---------------------------------------------------------------------------
# I. TestFixtureLanzarote
# ---------------------------------------------------------------------------

class TestFixtureLanzarote(unittest.TestCase):
    """Fixture realista: expediente en Lanzarote, estacion OPTIMA, BWh, CL-06."""

    LANZAROTE_CLIMATE = {
        "selected_station": {
            "station_id": "C029O",
            "name": "Arrecife/Lanzarote Aeropuerto",
        },
        "station_distance_km": 3.2,
        "station_selection_status": "OPTIMA",
        "climate_classification": {
            "koppen_code": "BWh",
            "koppen_label": "Desierto calido",
            "martonne_index": 4.2,
            "martonne_label": "Arido",
            "dry_months_gaussen": 12,
            "dry_months_names": [
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
            ],
            "annual_temperature_c": 20.4,
            "annual_precipitation_mm": 141.2,
            "notes": [],
        },
        "climogram_path": "clima/climograma_C029O.png",
        "description_md": "Clima desertico calido (BWh) tipico de Lanzarote.",
        "warnings": [],
        "notes": ["Normales 1991-2020 AEMET estacion C029O."],
    }

    LANZAROTE_PHASE4 = {
        "expediente_id": "EIA-2026-LANZAROTE-001",
        "climate": LANZAROTE_CLIMATE,
        "cartography_plan": {"maps": []},
        "ready_for_phase5": True,
        "warnings": [],
        "notes": ["Fase 4 offline completada."],
    }

    def setUp(self):
        self.fi001 = build_climate_factor_from_phase4(self.LANZAROTE_CLIMATE)
        self.summary = build_inventory_from_phase4_data(
            "EIA-2026-LANZAROTE-001",
            self.LANZAROTE_PHASE4,
        )

    def test_fi001_factor_id(self):
        self.assertEqual(self.fi001.factor_id, "FI-001")

    def test_fi001_evidence_confirmado_gabinete(self):
        self.assertEqual(self.fi001.evidence_status, "CONFIRMADO_GABINETE")

    def test_fi001_semaphore_verde(self):
        self.assertEqual(self.fi001.inventory_semaphore, "VERDE")

    def test_fi001_ready_true(self):
        self.assertTrue(self.fi001.ready_for_impact_assessment)

    def test_fi001_koppen_bwh_in_description(self):
        self.assertIn("BWh", self.fi001.description)

    def test_fi001_station_id_cl06(self):
        self.assertTrue(any("C029O" in s or "CL-06" in s for s in self.fi001.data_sources))

    def test_fi001_no_gaps(self):
        self.assertEqual(len(self.fi001.gaps), 0)

    def test_fi001_no_warnings(self):
        self.assertEqual(len(self.fi001.warnings), 0)

    def test_summary_expediente_id(self):
        self.assertEqual(self.summary.expediente_id, "EIA-2026-LANZAROTE-001")

    def test_summary_16_factors(self):
        self.assertEqual(self.summary.total_factors, 16)

    def test_fi001_ready_in_summary(self):
        fi001 = next(f for f in self.summary.factors if f.factor_id == "FI-001")
        self.assertTrue(fi001.ready_for_impact_assessment)

    def test_all_ready_false_because_base_factors(self):
        self.assertFalse(self.summary.all_ready_for_phase6)

    def test_write_produces_fi001_file(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-LANZAROTE"
            exp.mkdir()
            p4_path = exp / "fase4" / "phase4_result.json"
            p4_path.parent.mkdir()
            p4_path.write_text(
                json.dumps(self.LANZAROTE_PHASE4, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = build_inventory_from_phase4(exp, write_outputs=True)
            fi001_files = [f for f in result.rendered_files if "FI-001" in f]
            self.assertGreater(len(fi001_files), 0)

    def test_write_produces_all_16_factor_files(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Path(d) / "expediente-LANZAROTE"
            exp.mkdir()
            p4_path = exp / "fase4" / "phase4_result.json"
            p4_path.parent.mkdir()
            p4_path.write_text(
                json.dumps(self.LANZAROTE_PHASE4, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = build_inventory_from_phase4(exp, write_outputs=True)
            factor_md = [f for f in result.rendered_files if f.endswith(".md")
                         and "FI-" in f]
            self.assertEqual(len(factor_md), 16)

    def test_summary_json_serializable(self):
        d = self.summary.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        self.assertIn("EIA-2026-LANZAROTE-001", json_str)


if __name__ == "__main__":
    unittest.main()
