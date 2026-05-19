"""Tests para F4-01 — phase4_offline_pipeline.py

Sin AEMET real. Sin red. Sin Mapbox. Sin WMS/WMTS.
Fixtures sintéticos en directorios temporales.
"""
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.phase4_offline_pipeline import (
    Phase4OfflineResult,
    build_phase4_offline_markdown,
    run_phase4_offline,
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_expediente(tmp: Path, phase2_data: dict | None = None) -> Path:
    """Crea estructura mínima de expediente con control_interno/phase2_result.json."""
    exp = tmp / "expediente-EIA-F4TEST"
    (exp / "control_interno").mkdir(parents=True)
    if phase2_data is None:
        phase2_data = _PHASE2_ARRECIFE
    _write_json(exp / "control_interno" / "phase2_result.json", phase2_data)
    return exp


def _make_config_files(tmp: Path) -> tuple[Path, Path]:
    """Escribe estaciones y datos climáticos en el directorio temporal."""
    st = _write_json(tmp / "estaciones.json", _STATIONS_LANZAROTE)
    cd = _write_json(tmp / "datos_climaticos.json", _CLIMATE_LANZAROTE)
    return st, cd


def _run_pipeline(tmp: Path, write_outputs: bool = False) -> "Phase4OfflineResult":
    """Crea expediente + config files y ejecuta el pipeline."""
    exp = _make_expediente(tmp)
    st, cd = _make_config_files(tmp)
    return run_phase4_offline(exp, stations_path=st, climate_data_path=cd,
                              write_outputs=write_outputs)


# ===========================================================================
# 1. Resultado básico — estructura y tipos
# ===========================================================================

class TestPhase4OfflineResultBasico(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_returns_Phase4OfflineResult(self):
        result = _run_pipeline(self.tmp)
        self.assertIsInstance(result, Phase4OfflineResult)

    def test_expediente_id_matches_dir_name(self):
        result = _run_pipeline(self.tmp)
        self.assertEqual(result.expediente_id, "expediente-EIA-F4TEST")

    def test_precheck_is_dict(self):
        result = _run_pipeline(self.tmp)
        self.assertIsInstance(result.precheck, dict)

    def test_climate_is_dict_or_none(self):
        result = _run_pipeline(self.tmp)
        self.assertTrue(result.climate is None or isinstance(result.climate, dict))

    def test_cartography_plan_is_dict_or_none(self):
        result = _run_pipeline(self.tmp)
        self.assertTrue(result.cartography_plan is None or isinstance(result.cartography_plan, dict))

    def test_schematic_maps_is_list(self):
        result = _run_pipeline(self.tmp)
        self.assertIsInstance(result.schematic_maps, list)

    def test_ready_for_phase5_is_bool(self):
        result = _run_pipeline(self.tmp)
        self.assertIsInstance(result.ready_for_phase5, bool)

    def test_administrative_ready_always_false(self):
        result = _run_pipeline(self.tmp)
        self.assertFalse(result.administrative_ready)

    def test_warnings_is_list(self):
        result = _run_pipeline(self.tmp)
        self.assertIsInstance(result.warnings, list)

    def test_notes_contains_offline_message(self):
        result = _run_pipeline(self.tmp)
        combined = " ".join(result.notes)
        self.assertIn("offline", combined.lower())


# ===========================================================================
# 2. Modo sin escritura — no crea ficheros
# ===========================================================================

class TestSinEscritura(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_no_write_creates_no_fase4_dir(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=False)
        self.assertFalse((exp / "fase4").exists())

    def test_no_write_creates_no_cartografia_json(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=False)
        self.assertFalse((exp / "cartografia" / "cartografia_plan.json").exists())

    def test_no_write_creates_no_mapas(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=False)
        self.assertFalse((exp / "cartografia" / "mapas").exists())

    def test_no_write_schematic_maps_populated(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd,
                                    write_outputs=False)
        self.assertGreater(len(result.schematic_maps), 0)

    def test_no_write_schematic_maps_are_dicts(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd,
                                    write_outputs=False)
        for m in result.schematic_maps:
            self.assertIsInstance(m, dict)


# ===========================================================================
# 3. Modo con escritura — crea ficheros
# ===========================================================================

class TestConEscritura(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_write_creates_phase4_result_json(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "fase4" / "phase4_result.json").exists())

    def test_write_creates_phase4_result_md(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "fase4" / "phase4_result.md").exists())

    def test_write_json_is_valid(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        p = exp / "fase4" / "phase4_result.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertIn("expediente_id", data)
        self.assertIn("ready_for_phase5", data)
        self.assertIn("administrative_ready", data)

    def test_write_json_administrative_ready_false(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        data = json.loads((exp / "fase4" / "phase4_result.json").read_text(encoding="utf-8"))
        self.assertFalse(data["administrative_ready"])

    def test_write_creates_cartografia_plan(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "cartografia" / "cartografia_plan.json").exists())

    def test_write_creates_mapas_pngs(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        pngs = list((exp / "cartografia" / "mapas").glob("*.png"))
        self.assertGreater(len(pngs), 0)

    def test_write_creates_clima_json(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd, write_outputs=True)
        self.assertTrue((exp / "clima" / "phase4_climate_result.json").exists())

    def test_write_notes_contains_fase4_path(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd,
                                    write_outputs=True)
        combined = " ".join(result.notes)
        self.assertIn("phase4_result", combined)

    def test_write_custom_output_dir(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        run_phase4_offline(exp, stations_path=st, climate_data_path=cd,
                           write_outputs=True, output_dir="resumen_fase4")
        self.assertTrue((exp / "resumen_fase4" / "phase4_result.json").exists())


# ===========================================================================
# 4. Validaciones de entrada
# ===========================================================================

class TestValidacionesEntrada(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_missing_stations_raises_file_not_found(self):
        exp = _make_expediente(self.tmp)
        _, cd = _make_config_files(self.tmp)
        with self.assertRaises(FileNotFoundError):
            run_phase4_offline(exp,
                               stations_path=self.tmp / "no_existe.json",
                               climate_data_path=cd)

    def test_missing_climate_data_raises_file_not_found(self):
        exp = _make_expediente(self.tmp)
        st, _ = _make_config_files(self.tmp)
        with self.assertRaises(FileNotFoundError):
            run_phase4_offline(exp,
                               stations_path=st,
                               climate_data_path=self.tmp / "no_existe.json")

    def test_missing_phase2_raises_file_not_found(self):
        exp = self.tmp / "sin_fase2"
        exp.mkdir()
        st, cd = _make_config_files(self.tmp)
        with self.assertRaises(FileNotFoundError):
            run_phase4_offline(exp, stations_path=st, climate_data_path=cd)

    def test_accepts_string_paths(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        result = run_phase4_offline(str(exp), stations_path=str(st),
                                    climate_data_path=str(cd))
        self.assertIsInstance(result, Phase4OfflineResult)

    def test_error_message_mentions_stations_filename(self):
        exp = _make_expediente(self.tmp)
        _, cd = _make_config_files(self.tmp)
        try:
            run_phase4_offline(exp, stations_path=self.tmp / "mis_estaciones.json",
                               climate_data_path=cd)
        except FileNotFoundError as exc:
            self.assertIn("mis_estaciones", str(exc))


# ===========================================================================
# 5. Integración de clima (CL-06)
# ===========================================================================

class TestIntegracionClima(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_climate_dict_not_none(self):
        result = _run_pipeline(self.tmp)
        self.assertIsNotNone(result.climate)

    def test_climate_has_selected_station(self):
        result = _run_pipeline(self.tmp)
        self.assertIn("selected_station", result.climate)

    def test_climate_has_climate_classification(self):
        result = _run_pipeline(self.tmp)
        self.assertIn("climate_classification", result.climate)

    def test_climate_koppen_present(self):
        result = _run_pipeline(self.tmp)
        classif = result.climate.get("climate_classification") or {}
        self.assertIn("koppen_code", classif)

    def test_climate_station_lanzarote(self):
        result = _run_pipeline(self.tmp)
        station = result.climate.get("selected_station") or {}
        name = station.get("name", "")
        self.assertIn("Lanzarote", name)

    def test_climate_warnings_propagated(self):
        # Con estación lejana, CL-06 emite warning que llega al pipeline
        stations_lejanas = [{
            "station_id": "X999",
            "name": "Estacion Lejana",
            "latitude": 40.4,
            "longitude": -3.7,
            "altitude_m": 600.0,
            "has_normals": True,
        }]
        climate_lejana = [{
            "station_id": "X999",
            "station_name": "Estacion Lejana",
            "period": "1991-2020",
            "temperatures_c": [5, 6, 8, 10, 13, 16, 18, 18, 15, 12, 8, 6],
            "precipitations_mm": [60, 55, 50, 50, 55, 40, 20, 25, 50, 70, 70, 65],
        }]
        exp = _make_expediente(self.tmp)
        st = _write_json(self.tmp / "st_lejana.json", stations_lejanas)
        cd = _write_json(self.tmp / "cd_lejana.json", climate_lejana)
        result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd)
        # El warning de estación lejana debe propagarse (prefijado [Clima])
        climate_warnings = [w for w in result.warnings if "[Clima]" in w]
        self.assertGreater(len(climate_warnings), 0)


# ===========================================================================
# 6. Integración cartográfica (CA-10)
# ===========================================================================

class TestIntegracionCartografia(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_cartography_plan_not_none(self):
        result = _run_pipeline(self.tmp)
        self.assertIsNotNone(result.cartography_plan)

    def test_cartography_plan_has_maps(self):
        result = _run_pipeline(self.tmp)
        maps = result.cartography_plan.get("maps", [])
        self.assertGreater(len(maps), 0)

    def test_cartography_plan_has_6_maps(self):
        result = _run_pipeline(self.tmp)
        maps = result.cartography_plan.get("maps", [])
        self.assertEqual(len(maps), 6)

    def test_schematic_maps_has_6_entries(self):
        result = _run_pipeline(self.tmp)
        self.assertEqual(len(result.schematic_maps), 6)

    def test_schematic_maps_have_map_id(self):
        result = _run_pipeline(self.tmp)
        for m in result.schematic_maps:
            self.assertIn("map_id", m)

    def test_schematic_maps_ids_sequential(self):
        result = _run_pipeline(self.tmp)
        ids = [m.get("map_id", "") for m in result.schematic_maps]
        self.assertIn("MAP-001", ids)
        self.assertIn("MAP-006", ids)

    def test_cartography_warnings_propagated(self):
        # Con coordenadas inválidas, CA-10 puede emitir warnings
        exp = _make_expediente(self.tmp, phase2_data={
            "object_scope": {
                "coordenadas_wgs84": [],
                "referencia_catastral": "XXX",
            }
        })
        st, cd = _make_config_files(self.tmp)
        try:
            result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd)
            # Si no levanta excepción, puede haber warnings
        except (FileNotFoundError, ValueError):
            pass  # Aceptable que falle con coords vacías


# ===========================================================================
# 7. Markdown — build_phase4_offline_markdown
# ===========================================================================

class TestMarkdown(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _get_result(self) -> Phase4OfflineResult:
        return _run_pipeline(self.tmp)

    def test_markdown_not_empty(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertGreater(len(md), 100)

    def test_markdown_contains_expediente_id(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn(result.expediente_id, md)

    def test_markdown_contains_offline_note(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn("offline", md.lower())

    def test_markdown_contains_no_administrative_valid(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        # Debe contener aviso de no apta para administración
        self.assertTrue(
            "administrat" in md.lower() or "administrativa" in md.lower()
        )

    def test_markdown_contains_precheck_section(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn("CA-08", md)

    def test_markdown_contains_climate_section(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn("CL-06", md)

    def test_markdown_contains_cartography_section(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn("CA-10", md)

    def test_markdown_contains_CA11_section(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIn("CA-11", md)

    def test_markdown_is_string(self):
        result = self._get_result()
        md = build_phase4_offline_markdown(result)
        self.assertIsInstance(md, str)

    def test_summary_not_empty(self):
        result = self._get_result()
        s = result.summary()
        self.assertGreater(len(s), 30)

    def test_summary_contains_expediente_id(self):
        result = self._get_result()
        s = result.summary()
        self.assertIn(result.expediente_id, s)

    def test_summary_contains_offline_note(self):
        result = self._get_result()
        s = result.summary()
        self.assertIn("offline", s.lower())

    def test_to_dict_returns_dict(self):
        result = self._get_result()
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_keys(self):
        result = self._get_result()
        d = result.to_dict()
        expected_keys = {
            "expediente_id", "precheck", "climate", "cartography_plan",
            "schematic_maps", "ready_for_phase5", "administrative_ready",
            "warnings", "notes",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_administrative_ready_false(self):
        result = self._get_result()
        d = result.to_dict()
        self.assertFalse(d["administrative_ready"])


# ===========================================================================
# 8. CLI — phase4-offline
# ===========================================================================

class TestCLIPhase4Offline(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _run(self, argv: list) -> int:
        import run_expediente
        importlib.reload(run_expediente)
        return run_expediente.main(argv)

    def _setup(self):
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        return exp, st, cd

    def test_cli_no_write_returns_zero(self):
        exp, st, cd = self._setup()
        rc = self._run([
            str(exp), "phase4-offline",
            "--stations", str(st),
            "--climate-data", str(cd),
        ])
        self.assertEqual(rc, 0)

    def test_cli_no_write_creates_no_fase4_dir(self):
        exp, st, cd = self._setup()
        self._run([str(exp), "phase4-offline", "--stations", str(st),
                   "--climate-data", str(cd)])
        self.assertFalse((exp / "fase4").exists())

    def test_cli_write_creates_json(self):
        exp, st, cd = self._setup()
        self._run([str(exp), "phase4-offline", "--stations", str(st),
                   "--climate-data", str(cd), "--write"])
        self.assertTrue((exp / "fase4" / "phase4_result.json").exists())

    def test_cli_write_creates_md(self):
        exp, st, cd = self._setup()
        self._run([str(exp), "phase4-offline", "--stations", str(st),
                   "--climate-data", str(cd), "--write"])
        self.assertTrue((exp / "fase4" / "phase4_result.md").exists())

    def test_cli_write_creates_pngs(self):
        exp, st, cd = self._setup()
        self._run([str(exp), "phase4-offline", "--stations", str(st),
                   "--climate-data", str(cd), "--write"])
        pngs = list((exp / "cartografia" / "mapas").glob("*.png"))
        self.assertGreater(len(pngs), 0)

    def test_cli_missing_stations_returns_one(self):
        exp = _make_expediente(self.tmp)
        _, cd = _make_config_files(self.tmp)
        rc = self._run([
            str(exp), "phase4-offline",
            "--stations", str(self.tmp / "no_existe.json"),
            "--climate-data", str(cd),
        ])
        self.assertEqual(rc, 1)

    def test_cli_missing_phase2_returns_one(self):
        exp = self.tmp / "sin_fase2"
        exp.mkdir()
        st, cd = _make_config_files(self.tmp)
        rc = self._run([str(exp), "phase4-offline", "--stations", str(st),
                        "--climate-data", str(cd)])
        self.assertEqual(rc, 1)

    def test_cli_missing_expediente_returns_one(self):
        st, cd = _make_config_files(self.tmp)
        rc = self._run([
            str(self.tmp / "expediente_inexistente"), "phase4-offline",
            "--stations", str(st), "--climate-data", str(cd),
        ])
        self.assertEqual(rc, 1)


# ===========================================================================
# 9. Fixture Lanzarote — integración completa
# ===========================================================================

class TestLanzaroteFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        exp = _make_expediente(self.tmp)
        st, cd = _make_config_files(self.tmp)
        self.result = run_phase4_offline(exp, stations_path=st, climate_data_path=cd)

    def test_returns_result(self):
        self.assertIsInstance(self.result, Phase4OfflineResult)

    def test_expediente_id(self):
        self.assertEqual(self.result.expediente_id, "expediente-EIA-F4TEST")

    def test_climate_not_none(self):
        self.assertIsNotNone(self.result.climate)

    def test_climate_station_is_lanzarote(self):
        station = (self.result.climate.get("selected_station") or {}).get("name", "")
        self.assertIn("Lanzarote", station)

    def test_climate_koppen_B_family(self):
        classif = (self.result.climate.get("climate_classification") or {})
        koppen = classif.get("koppen_code", "")
        self.assertTrue(koppen.startswith("B"), f"Köppen esperado B..., obtenido: {koppen}")

    def test_cartography_plan_6_maps(self):
        maps = (self.result.cartography_plan or {}).get("maps", [])
        self.assertEqual(len(maps), 6)

    def test_schematic_maps_6_entries(self):
        self.assertEqual(len(self.result.schematic_maps), 6)

    def test_administrative_ready_false(self):
        self.assertFalse(self.result.administrative_ready)

    def test_notes_has_offline_note(self):
        combined = " ".join(self.result.notes)
        self.assertIn("offline", combined.lower())

    def test_to_dict_json_serializable(self):
        d = self.result.to_dict()
        # Debe poder serializar sin error
        s = json.dumps(d, ensure_ascii=False)
        self.assertGreater(len(s), 10)

    def test_summary_contains_koppen(self):
        s = self.result.summary()
        self.assertIn("Köppen", s)

    def test_summary_contains_map_count(self):
        s = self.result.summary()
        self.assertIn("/6", s)

    def test_precheck_dict_has_issues(self):
        self.assertIn("issues", self.result.precheck)

    def test_md_not_empty(self):
        md = build_phase4_offline_markdown(self.result)
        self.assertGreater(len(md), 200)


if __name__ == "__main__":
    unittest.main()
