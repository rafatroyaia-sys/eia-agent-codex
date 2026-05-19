"""Tests para CL-06 — phase4_climate_pipeline.py

Sin AEMET real. Sin red. Fixtures sintéticos en directorios temporales.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import matplotlib  # noqa: F401
    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False

from eia_agent.core.phase4_climate_pipeline import (
    Phase4ClimateResult,
    build_climate_description_md,
    extract_wgs84_from_phase2,
    load_monthly_climate_dataset,
    run_phase4_climate,
)

# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------

_STATIONS_LANZAROTE = [
    {
        "station_id": "C029O",
        "name": "Lanzarote Aeropuerto",
        "latitude": 28.9583,
        "longitude": -13.6052,
        "altitude_m": 14.0,
        "has_normals": True,
        "island": "Lanzarote",
    },
    {
        "station_id": "C447A",
        "name": "Madrid Barajas Aeropuerto",
        "latitude": 40.4689,
        "longitude": -3.5705,
        "altitude_m": 609.0,
        "has_normals": True,
    },
]

_CLIMATE_LANZAROTE = [
    {
        "station_id": "C029O",
        "station_name": "Lanzarote Aeropuerto",
        "period": "1991-2020",
        "temperatures_c": [17.8, 18.1, 18.8, 19.4, 20.7, 22.7, 24.9, 25.7, 25.1, 23.5, 21.0, 18.6],
        "precipitations_mm": [22.0, 19.0, 15.0, 7.0, 2.0, 1.0, 0.0, 1.0, 5.0, 14.0, 21.0, 24.0],
    }
]

_PHASE2_ARRECIFE = {
    "object_scope": {
        "coordenadas_wgs84": ["28.9773, -13.5395"],
        "referencia_catastral": "0000001XX0000X0000XX",
    }
}


def _write_json(path: Path, data) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_expediente(tmp: Path, phase2_data: dict | None = None) -> Path:
    """Crea estructura mínima de expediente con control_interno/phase2_result.json."""
    exp = tmp / "expediente-EIA-TEST"
    (exp / "control_interno").mkdir(parents=True)
    if phase2_data is None:
        phase2_data = _PHASE2_ARRECIFE
    _write_json(exp / "control_interno" / "phase2_result.json", phase2_data)
    return exp


# ===========================================================================
# 1. Carga de dataset climático
# ===========================================================================

class TestLoadMonthlyClimateDataset(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_valid_dataset_returns_dict(self):
        p = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        ds = load_monthly_climate_dataset(p)
        self.assertIn("C029O", ds)

    def test_returned_object_is_MonthlyClimateData(self):
        from eia_agent.core.climate_indices import MonthlyClimateData
        p = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        ds = load_monthly_climate_dataset(p)
        self.assertIsInstance(ds["C029O"], MonthlyClimateData)

    def test_temperatures_preserved(self):
        p = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        ds = load_monthly_climate_dataset(p)
        self.assertAlmostEqual(ds["C029O"].temperatures_c[0], 17.8)

    def test_multiple_stations(self):
        data = _CLIMATE_LANZAROTE + [{
            "station_id": "HUM01",
            "station_name": "Estación Húmeda",
            "period": "1991-2020",
            "temperatures_c": [5, 6, 8, 10, 13, 16, 18, 18, 15, 12, 8, 6],
            "precipitations_mm": [80, 70, 65, 55, 60, 60, 55, 60, 65, 80, 85, 90],
        }]
        p = _write_json(self.tmp / "cd2.json", data)
        ds = load_monthly_climate_dataset(p)
        self.assertEqual(len(ds), 2)
        self.assertIn("HUM01", ds)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_monthly_climate_dataset(self.tmp / "nope.json")

    def test_invalid_json_raises_value_error(self):
        p = self.tmp / "bad.json"
        p.write_text("{not: valid json}", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_monthly_climate_dataset(p)

    def test_not_a_list_raises_value_error(self):
        p = _write_json(self.tmp / "obj.json", {"station_id": "X"})
        with self.assertRaises(ValueError):
            load_monthly_climate_dataset(p)

    def test_eleven_months_raises_value_error(self):
        bad = [{
            "station_id": "BAD",
            "temperatures_c": [10.0] * 11,
            "precipitations_mm": [50.0] * 12,
        }]
        p = _write_json(self.tmp / "bad11.json", bad)
        with self.assertRaises(ValueError):
            load_monthly_climate_dataset(p)

    def test_missing_station_id_raises_value_error(self):
        bad = [{"temperatures_c": [10.0] * 12, "precipitations_mm": [50.0] * 12}]
        p = _write_json(self.tmp / "noid.json", bad)
        with self.assertRaises(ValueError):
            load_monthly_climate_dataset(p)


# ===========================================================================
# 2. Extracción de coordenadas
# ===========================================================================

class TestExtractWgs84(unittest.TestCase):

    def test_single_string_lat_lon(self):
        phase2 = {"object_scope": {"coordenadas_wgs84": ["28.9773, -13.5395"]}}
        lat, lon = extract_wgs84_from_phase2(phase2)
        self.assertAlmostEqual(lat, 28.9773, places=3)
        self.assertAlmostEqual(lon, -13.5395, places=3)

    def test_two_separate_strings(self):
        phase2 = {"object_scope": {"coordenadas_wgs84": ["28.9773", "-13.5395"]}}
        lat, lon = extract_wgs84_from_phase2(phase2)
        self.assertAlmostEqual(lat, 28.9773, places=3)
        self.assertAlmostEqual(lon, -13.5395, places=3)

    def test_dict_format(self):
        phase2 = {"object_scope": {"coordenadas_wgs84": [{"lat": 28.9773, "lon": -13.5395}]}}
        lat, lon = extract_wgs84_from_phase2(phase2)
        self.assertAlmostEqual(lat, 28.9773, places=3)
        self.assertAlmostEqual(lon, -13.5395, places=3)

    def test_dict_with_latitude_key(self):
        phase2 = {"object_scope": {"coordenadas_wgs84": [{"latitude": 28.1, "longitude": -15.4}]}}
        lat, lon = extract_wgs84_from_phase2(phase2)
        self.assertAlmostEqual(lat, 28.1, places=2)
        self.assertAlmostEqual(lon, -15.4, places=2)

    def test_no_coordinates_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_wgs84_from_phase2({"object_scope": {}})

    def test_empty_list_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_wgs84_from_phase2({"object_scope": {"coordenadas_wgs84": []}})

    def test_missing_object_scope_raises_value_error(self):
        with self.assertRaises(ValueError):
            extract_wgs84_from_phase2({})

    def test_string_with_spaces(self):
        phase2 = {"object_scope": {"coordenadas_wgs84": ["28.9773 , -13.5395"]}}
        lat, lon = extract_wgs84_from_phase2(phase2)
        self.assertAlmostEqual(lat, 28.9773, places=3)
        self.assertAlmostEqual(lon, -13.5395, places=3)


# ===========================================================================
# 3. Pipeline completo
# ===========================================================================

class TestRunPhase4Climate(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _make_exp(self, phase2_data=None):
        return _make_expediente(self.tmp, phase2_data)

    def _write_stations(self, name="stations.json"):
        return _write_json(self.tmp / name, _STATIONS_LANZAROTE)

    def _write_climate(self, name="climate.json"):
        return _write_json(self.tmp / name, _CLIMATE_LANZAROTE)

    def test_returns_Phase4ClimateResult(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertIsInstance(result, Phase4ClimateResult)

    def test_selects_nearest_station(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        # Arrecife está ~8 km de Lanzarote Aeropuerto, muy lejos de Madrid
        self.assertIsNotNone(result.selected_station)
        self.assertEqual(result.selected_station["station_id"], "C029O")

    def test_distance_reasonable(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertIsNotNone(result.station_distance_km)
        self.assertLess(result.station_distance_km, 30.0)

    def test_generates_climate_classification(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertIsNotNone(result.climate_classification)

    def test_koppen_starts_with_B_for_lanzarote(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        koppen = result.climate_classification["koppen_code"]
        self.assertTrue(koppen.startswith("B"), f"Se esperaba B… para Lanzarote, obtenido: {koppen}")

    def test_description_md_not_empty(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertGreater(len(result.description_md), 20)

    def test_description_md_contains_station_name(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertIn("Lanzarote", result.description_md)

    def test_no_write_creates_no_files(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=False)
        self.assertFalse((exp / "clima").exists())

    def test_write_creates_json(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "clima" / "phase4_climate_result.json").exists())

    def test_write_creates_md(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "clima" / "descripcion_clima.md").exists())

    @unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
    def test_write_creates_png(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertIsNotNone(result.climogram_path)
        self.assertTrue(Path(result.climogram_path).exists())

    @unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
    def test_climogram_is_valid_png(self):
        from eia_agent.core.climogram_generator import validate_png
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue(validate_png(result.climogram_path))

    def test_no_write_climogram_path_is_none(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=False)
        self.assertIsNone(result.climogram_path)

    def test_missing_phase2_raises_file_not_found(self):
        exp = self.tmp / "vacio"
        exp.mkdir()
        st = self._write_stations()
        cd = self._write_climate()
        with self.assertRaises(FileNotFoundError):
            run_phase4_climate(exp, stations_path=st, climate_data_path=cd)

    def test_station_not_in_dataset_gives_warning(self):
        # Dataset solo tiene Madrid, pero la estación más cercana es Lanzarote
        climate_no_lz = [{
            "station_id": "C447A",
            "station_name": "Madrid Barajas",
            "period": "1981-2010",
            "temperatures_c": [4.8, 6.3, 9.8, 11.9, 16.0, 20.8, 24.5, 24.0, 19.5, 13.9, 8.2, 5.2],
            "precipitations_mm": [42, 33, 35, 42, 45, 20, 11, 9, 26, 52, 52, 46],
        }]
        exp = self._make_exp()
        st = self._write_stations()
        cd = _write_json(self.tmp / "cdmad.json", climate_no_lz)
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        # classification debe ser None porque C029O no está en dataset
        self.assertIsNone(result.climate_classification)
        self.assertTrue(any("C029O" in w or "datos climáticos" in w for w in result.warnings))

    def test_stations_path_none_gives_no_disponible(self):
        exp = self._make_exp()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=None, climate_data_path=cd)
        self.assertEqual(result.station_selection_status, "NO_DISPONIBLE")

    def test_climate_data_path_none_gives_no_classification(self):
        exp = self._make_exp()
        st = self._write_stations()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=None)
        self.assertIsNotNone(result.selected_station)
        self.assertIsNone(result.climate_classification)

    def test_to_dict_keys(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        d = result.to_dict()
        for k in ("expediente_id", "selected_station", "station_distance_km",
                  "station_selection_status", "climate_classification",
                  "climogram_path", "description_md", "warnings", "notes"):
            self.assertIn(k, d)

    def test_summary_not_empty(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertGreater(len(result.summary()), 20)

    def test_expediente_id_matches_directory_name(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertEqual(result.expediente_id, exp.name)

    def test_explicit_phase2_path(self):
        """Acepta phase2_result_path explícito en otra ubicación."""
        exp = self._make_exp()
        p2 = _write_json(self.tmp / "p2custom.json", _PHASE2_ARRECIFE)
        st = self._write_stations()
        cd = self._write_climate()
        result = run_phase4_climate(
            exp,
            phase2_result_path=p2,
            stations_path=st,
            climate_data_path=cd,
        )
        self.assertIsNotNone(result.selected_station)

    def test_lejana_station_adds_warning(self):
        """Una estación muy lejana al proyecto genera aviso LEJANA."""
        phase2_madrid = {
            "object_scope": {"coordenadas_wgs84": ["40.4689, -3.5705"]}
        }
        exp = _make_expediente(self.tmp / "expM", phase2_madrid)
        # Stations: solo Lanzarote (muy lejos de Madrid)
        st = _write_json(self.tmp / "st_lz.json", [_STATIONS_LANZAROTE[0]])
        cd = self._write_climate()
        result = run_phase4_climate(exp, stations_path=st, climate_data_path=cd)
        self.assertEqual(result.station_selection_status, "LEJANA")
        self.assertTrue(any("LEJANA" in w or "lejos" in w.lower() or "km" in w for w in result.warnings))

    def test_json_output_valid(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        run_phase4_climate(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        json_path = exp / "clima" / "phase4_climate_result.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("expediente_id", data)
        self.assertIn("climate_classification", data)

    def test_write_output_dir_custom(self):
        exp = self._make_exp()
        st = self._write_stations()
        cd = self._write_climate()
        run_phase4_climate(exp, stations_path=st, climate_data_path=cd,
                           write_outputs=True, output_dir="clima_test")
        self.assertTrue((exp / "clima_test" / "phase4_climate_result.json").exists())


# ===========================================================================
# 4. CLI phase4-climate
# ===========================================================================

class TestCLIPhase4Climate(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _setup(self):
        exp = _make_expediente(self.tmp)
        st = _write_json(self.tmp / "st.json", _STATIONS_LANZAROTE)
        cd = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        return exp, st, cd

    def _run(self, argv):
        """Importa main de run_expediente y lo ejecuta."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import importlib
        import run_expediente
        importlib.reload(run_expediente)
        return run_expediente.main(argv)

    def test_cli_no_write_returns_zero(self):
        exp, st, cd = self._setup()
        rc = self._run([
            str(exp),
            "phase4-climate",
            "--stations", str(st),
            "--climate-data", str(cd),
        ])
        self.assertEqual(rc, 0)

    def test_cli_no_write_creates_no_files(self):
        exp, st, cd = self._setup()
        self._run([str(exp), "phase4-climate", "--stations", str(st), "--climate-data", str(cd)])
        self.assertFalse((exp / "clima").exists())

    def test_cli_write_creates_json(self):
        exp, st, cd = self._setup()
        self._run([
            str(exp), "phase4-climate",
            "--stations", str(st),
            "--climate-data", str(cd),
            "--write",
        ])
        self.assertTrue((exp / "clima" / "phase4_climate_result.json").exists())

    @unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
    def test_cli_write_creates_png(self):
        exp, st, cd = self._setup()
        self._run([
            str(exp), "phase4-climate",
            "--stations", str(st),
            "--climate-data", str(cd),
            "--write",
        ])
        png_files = list((exp / "clima").glob("*.png"))
        self.assertGreater(len(png_files), 0)

    def test_cli_missing_phase2_returns_one(self):
        exp = self.tmp / "sin_fase2"
        exp.mkdir()
        st = _write_json(self.tmp / "st.json", _STATIONS_LANZAROTE)
        cd = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        rc = self._run([str(exp), "phase4-climate", "--stations", str(st), "--climate-data", str(cd)])
        self.assertEqual(rc, 1)


# ===========================================================================
# 5. Fixture Lanzarote — validación climática
# ===========================================================================

class TestLanzaroteFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _run_pipeline(self):
        exp = _make_expediente(self.tmp)
        st = _write_json(self.tmp / "st.json", _STATIONS_LANZAROTE)
        cd = _write_json(self.tmp / "cd.json", _CLIMATE_LANZAROTE)
        return run_phase4_climate(exp, stations_path=st, climate_data_path=cd)

    def test_selects_C029O(self):
        r = self._run_pipeline()
        self.assertEqual(r.selected_station["station_id"], "C029O")

    def test_koppen_is_B_family(self):
        r = self._run_pipeline()
        self.assertTrue(r.climate_classification["koppen_code"].startswith("B"))

    def test_martonne_arido(self):
        r = self._run_pipeline()
        # Lanzarote: P_anual~131mm, T_anual~21.4°C → I=131/31.4≈4.2 (árido extremo/árido)
        martonne = r.climate_classification["martonne_index"]
        self.assertLess(martonne, 15.0)

    def test_has_dry_months(self):
        r = self._run_pipeline()
        self.assertGreater(len(r.climate_classification["dry_months_gaussen"]), 0)

    def test_status_optima_or_aceptable(self):
        r = self._run_pipeline()
        self.assertIn(r.station_selection_status, ("OPTIMA", "ACEPTABLE"))

    def test_description_contains_koppen(self):
        r = self._run_pipeline()
        self.assertIn("Köppen", r.description_md)

    def test_description_contains_temperature(self):
        r = self._run_pipeline()
        self.assertIn("°C", r.description_md)

    def test_description_contains_gabinete_note(self):
        r = self._run_pipeline()
        self.assertIn("gabinete", r.description_md.lower())

    def test_annual_precipitation_approx_131(self):
        r = self._run_pipeline()
        p_anual = r.climate_classification["annual_precipitation_mm"]
        self.assertAlmostEqual(p_anual, 131.0, delta=1.0)

    def test_annual_temperature_approx_21(self):
        r = self._run_pipeline()
        t_anual = r.climate_classification["annual_temperature_c"]
        self.assertAlmostEqual(t_anual, 21.4, delta=0.2)


# ===========================================================================
# 6. build_climate_description_md
# ===========================================================================

class TestBuildClimateDescriptionMd(unittest.TestCase):

    def _make_result(self, station=True, classification=True):
        st = {
            "station_id": "C029O",
            "name": "Lanzarote Aeropuerto",
            "latitude": 28.9583,
            "longitude": -13.6052,
        } if station else None
        cc = {
            "koppen_code": "BWh",
            "koppen_label": "Árido cálido",
            "martonne_index": 4.2,
            "martonne_label": "Árido extremo",
            "annual_temperature_c": 21.4,
            "annual_precipitation_mm": 131.0,
            "dry_months_gaussen": [5, 6, 7, 8, 9],
            "dry_months_names": ["Mayo", "Junio", "Julio", "Agosto", "Septiembre"],
            "notes": [],
            "warnings": [],
        } if classification else None
        return Phase4ClimateResult(
            expediente_id="TEST",
            selected_station=st,
            station_distance_km=8.5 if station else None,
            station_selection_status="OPTIMA" if station else "NO_DISPONIBLE",
            climate_classification=cc,
            climogram_path=None,
            description_md="",
            warnings=[],
            notes=[],
        )

    def test_contains_station_name(self):
        r = self._make_result()
        md = build_climate_description_md(r)
        self.assertIn("Lanzarote", md)

    def test_contains_koppen(self):
        r = self._make_result()
        md = build_climate_description_md(r)
        self.assertIn("BWh", md)

    def test_contains_martonne(self):
        r = self._make_result()
        md = build_climate_description_md(r)
        self.assertIn("Martonne", md)

    def test_contains_gabinete_note(self):
        r = self._make_result()
        md = build_climate_description_md(r)
        self.assertIn("gabinete", md.lower())

    def test_lejana_adds_aviso(self):
        r = self._make_result()
        r.station_selection_status = "LEJANA"
        r.station_distance_km = 45.0
        md = build_climate_description_md(r)
        self.assertIn("AVISO", md)

    def test_no_station_no_crash(self):
        r = self._make_result(station=False, classification=False)
        md = build_climate_description_md(r)
        self.assertGreater(len(md), 10)

    def test_no_classification_no_crash(self):
        r = self._make_result(station=True, classification=False)
        md = build_climate_description_md(r)
        self.assertGreater(len(md), 10)


if __name__ == "__main__":
    unittest.main()
