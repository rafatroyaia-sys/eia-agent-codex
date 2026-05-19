"""
Tests CA-10 — cartography_plan.py

Grupos:
  1. MapSpec
  2. CartographyPlanResult
  3. Plan básico
  4. Estados (READY_FOR_RENDER / PLANNED)
  5. Markdown
  6. Escritura opcional
  7. CLI
  8. Fixture Lanzarote
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.cartography_plan import (
    CartographyPlanResult,
    MapSpec,
    build_cartography_plan,
    build_cartography_plan_markdown,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PHASE2_LANZAROTE = {
    "object_scope": {
        "coordenadas_wgs84": ["28.9773, -13.5395"],
        "referencia_catastral": "1234567AB1234A0001XY",
    }
}

_PHASE2_ESTIMADO = {
    "object_scope": {
        "coordenadas_wgs84": [{"lat": 28.9773, "lon": -13.5395}],
        "coordenadas_status": "ESTIMADO",
    }
}

_EXPECTED_MAP_IDS = [
    "MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006"
]

_EXPECTED_FILENAMES = [
    "MAP-001_situacion_general.png",
    "MAP-002_emplazamiento.png",
    "MAP-003_parcela_catastro.png",
    "MAP-004_red_natura_enp.png",
    "MAP-005_usos_suelo_entorno.png",
    "MAP-006_inundabilidad_riesgos.png",
]


def _make_expediente(tmp: Path, phase2_data: dict) -> Path:
    exp = tmp / "expediente-EIA-TEST"
    ci = exp / "control_interno"
    ci.mkdir(parents=True)
    (ci / "phase2_result.json").write_text(
        json.dumps(phase2_data), encoding="utf-8"
    )
    return exp


# ---------------------------------------------------------------------------
# 1. MapSpec
# ---------------------------------------------------------------------------

class TestMapSpec(unittest.TestCase):

    def _make_spec(self, status="READY_FOR_RENDER") -> MapSpec:
        return MapSpec(
            map_id="MAP-001",
            title="Situación general",
            purpose="Localización",
            map_type="situacion_general",
            extent_key="situacion_general",
            extent={"radius_m": 25000.0},
            required_layers=["base_territorial", "marcador_proyecto"],
            source_candidates=["IGN"],
            output_filename="MAP-001_situacion_general.png",
            status=status,
            warnings=[],
            notes=[],
        )

    def test_to_dict_has_all_fields(self):
        spec = self._make_spec()
        d = spec.to_dict()
        expected_keys = {
            "map_id", "title", "purpose", "map_type", "extent_key",
            "extent", "required_layers", "source_candidates",
            "output_filename", "status", "warnings", "notes",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_map_id(self):
        spec = self._make_spec()
        self.assertEqual(spec.to_dict()["map_id"], "MAP-001")

    def test_to_dict_status(self):
        spec = self._make_spec(status="PLANNED")
        self.assertEqual(spec.to_dict()["status"], "PLANNED")

    def test_to_dict_layers_copied(self):
        spec = self._make_spec()
        d = spec.to_dict()
        d["required_layers"].append("extra")
        self.assertNotIn("extra", spec.required_layers)

    def test_summary_not_empty(self):
        spec = self._make_spec()
        s = spec.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)

    def test_summary_contains_map_id(self):
        spec = self._make_spec()
        self.assertIn("MAP-001", spec.summary())

    def test_summary_contains_status(self):
        spec = self._make_spec(status="PLANNED")
        self.assertIn("PLANNED", spec.summary())

    def test_summary_shows_warning(self):
        spec = self._make_spec()
        spec.warnings = ["Coordenadas no fiables"]
        self.assertIn("AVISO", spec.summary())


# ---------------------------------------------------------------------------
# 2. CartographyPlanResult
# ---------------------------------------------------------------------------

class TestCartographyPlanResult(unittest.TestCase):

    def _make_result(self, ready=True) -> CartographyPlanResult:
        return CartographyPlanResult(
            expediente_id="EIA-TEST",
            center={"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO"},
            maps=[],
            ready_for_render=ready,
            warnings=[],
            notes=["Nota de prueba"],
        )

    def test_to_dict_has_all_fields(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertIn("expediente_id", d)
        self.assertIn("center", d)
        self.assertIn("maps", d)
        self.assertIn("ready_for_render", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_to_dict_maps_is_list(self):
        r = self._make_result()
        self.assertIsInstance(r.to_dict()["maps"], list)

    def test_to_dict_ready_for_render(self):
        r = self._make_result(ready=False)
        self.assertFalse(r.to_dict()["ready_for_render"])

    def test_summary_not_empty(self):
        r = self._make_result()
        self.assertIsInstance(r.summary(), str)
        self.assertGreater(len(r.summary()), 0)

    def test_summary_contains_expediente_id(self):
        r = self._make_result()
        self.assertIn("EIA-TEST", r.summary())

    def test_summary_contains_ready_label(self):
        r = self._make_result(ready=True)
        self.assertIn("LISTO", r.summary())

    def test_summary_contains_planned_label_when_not_ready(self):
        r = self._make_result(ready=False)
        self.assertIn("PLANIFICADO", r.summary())


# ---------------------------------------------------------------------------
# 3. Plan básico
# ---------------------------------------------------------------------------

class TestBuildCartographyPlanBasic(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._exp = _make_expediente(tmp, _PHASE2_LANZAROTE)
        self._result = build_cartography_plan(self._exp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_cartography_plan_result(self):
        self.assertIsInstance(self._result, CartographyPlanResult)

    def test_generates_six_maps(self):
        self.assertEqual(len(self._result.maps), 6)

    def test_all_map_ids_present(self):
        ids = [m.map_id for m in self._result.maps]
        for expected_id in _EXPECTED_MAP_IDS:
            self.assertIn(expected_id, ids, msg=f"{expected_id} no encontrado")

    def test_map_ids_in_order(self):
        ids = [m.map_id for m in self._result.maps]
        self.assertEqual(ids, _EXPECTED_MAP_IDS)

    def test_output_filenames_correct(self):
        filenames = [m.output_filename for m in self._result.maps]
        self.assertEqual(filenames, _EXPECTED_FILENAMES)

    def test_all_required_layers_non_empty(self):
        for m in self._result.maps:
            self.assertGreater(len(m.required_layers), 0, msg=f"{m.map_id} sin capas")

    def test_all_source_candidates_non_empty(self):
        for m in self._result.maps:
            self.assertGreater(
                len(m.source_candidates), 0, msg=f"{m.map_id} sin fuentes"
            )

    def test_expediente_id_set(self):
        self.assertEqual(self._result.expediente_id, "expediente-EIA-TEST")

    def test_center_has_lat_lon(self):
        self.assertIn("lat", self._result.center)
        self.assertIn("lon", self._result.center)

    def test_center_lat_approx(self):
        self.assertAlmostEqual(self._result.center["lat"], 28.9773, places=3)

    def test_all_maps_have_extent_dict(self):
        for m in self._result.maps:
            self.assertIsInstance(m.extent, dict, msg=f"{m.map_id} extent no es dict")
            self.assertGreater(len(m.extent), 0, msg=f"{m.map_id} extent vacío")

    def test_all_maps_have_extent_key(self):
        valid_keys = {
            "detalle_parcela", "emplazamiento", "entorno_500m",
            "entorno_2000m", "situacion_general",
        }
        for m in self._result.maps:
            self.assertIn(m.extent_key, valid_keys, msg=f"{m.map_id} extent_key inválido")

    def test_no_output_without_write_flag(self):
        cart_dir = self._exp / "cartografia"
        self.assertFalse(cart_dir.exists())


# ---------------------------------------------------------------------------
# 4. Estados
# ---------------------------------------------------------------------------

class TestMapStatuses(unittest.TestCase):

    def _run(self, coords_status: str) -> CartographyPlanResult:
        phase2 = {
            "object_scope": {
                "coordenadas_wgs84": [
                    {"lat": 28.9773, "lon": -13.5395}
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), phase2)
            result = build_cartography_plan(exp)
            # Patch the GeoPoint status by reconstructing via explicit path
            # (the fixture uses default DECLARADO; for ESTIMADO we override)
            return result

    def _run_with_status(self, point_status: str) -> CartographyPlanResult:
        from eia_agent.core.geospatial_utils import GeoPoint, build_standard_map_extents
        from eia_agent.core.cartography_plan import _build_map_specs, CartographyPlanResult

        point = GeoPoint(lat=28.9773, lon=-13.5395, status=point_status)
        extents = build_standard_map_extents(point)
        maps = _build_map_specs(point, extents)
        warnings = []
        if point_status in {"ESTIMADO", "PROVISIONAL", "NO_DECLARADO"}:
            warnings.append(f"Coordenadas con estado '{point_status}'.")
        ready = all(m.status == "READY_FOR_RENDER" for m in maps) and len(warnings) == 0
        return CartographyPlanResult(
            expediente_id="TEST",
            center=point.to_dict(),
            maps=maps,
            ready_for_render=ready,
            warnings=warnings,
        )

    def test_declarado_maps_ready_for_render(self):
        r = self._run_with_status("DECLARADO")
        for m in r.maps:
            self.assertEqual(m.status, "READY_FOR_RENDER", msg=f"{m.map_id} no READY")

    def test_verificado_maps_ready_for_render(self):
        r = self._run_with_status("VERIFICADO")
        for m in r.maps:
            self.assertEqual(m.status, "READY_FOR_RENDER")

    def test_estimado_maps_planned(self):
        r = self._run_with_status("ESTIMADO")
        for m in r.maps:
            self.assertEqual(m.status, "PLANNED", msg=f"{m.map_id} no PLANNED")

    def test_provisional_maps_planned(self):
        r = self._run_with_status("PROVISIONAL")
        for m in r.maps:
            self.assertEqual(m.status, "PLANNED")

    def test_no_declarado_maps_planned(self):
        r = self._run_with_status("NO_DECLARADO")
        for m in r.maps:
            self.assertEqual(m.status, "PLANNED")

    def test_estimado_maps_have_warnings(self):
        r = self._run_with_status("ESTIMADO")
        for m in r.maps:
            self.assertGreater(len(m.warnings), 0, msg=f"{m.map_id} sin warning")

    def test_declarado_maps_no_warnings(self):
        r = self._run_with_status("DECLARADO")
        for m in r.maps:
            self.assertEqual(m.warnings, [], msg=f"{m.map_id} con warning inesperado")

    def test_ready_for_render_true_when_declarado(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            r = build_cartography_plan(exp)
        self.assertTrue(r.ready_for_render)

    def test_ready_for_render_false_when_estimado(self):
        r = self._run_with_status("ESTIMADO")
        self.assertFalse(r.ready_for_render)

    def test_no_coords_raises_value_error(self):
        phase2_no_coords = {"object_scope": {"coordenadas_wgs84": []}}
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), phase2_no_coords)
            with self.assertRaises(ValueError):
                build_cartography_plan(exp)

    def test_missing_phase2_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-VACIO"
            exp.mkdir()
            with self.assertRaises(FileNotFoundError):
                build_cartography_plan(exp)


# ---------------------------------------------------------------------------
# 5. Markdown
# ---------------------------------------------------------------------------

class TestBuildCartographyPlanMarkdown(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        exp = _make_expediente(tmp, _PHASE2_LANZAROTE)
        self._result = build_cartography_plan(exp)
        self._md = build_cartography_plan_markdown(self._result)

    def tearDown(self):
        self._tmp.cleanup()

    def test_markdown_is_string(self):
        self.assertIsInstance(self._md, str)

    def test_markdown_not_empty(self):
        self.assertGreater(len(self._md), 0)

    def test_contains_map_001(self):
        self.assertIn("MAP-001", self._md)

    def test_contains_all_map_ids(self):
        for mid in _EXPECTED_MAP_IDS:
            self.assertIn(mid, self._md, msg=f"{mid} no en markdown")

    def test_contains_no_render_note(self):
        self.assertIn("no contiene cartografía generada", self._md)

    def test_contains_table(self):
        self.assertIn("| MAP-", self._md)

    def test_contains_expediente_id(self):
        self.assertIn("expediente-EIA-TEST", self._md)

    def test_contains_required_layers(self):
        self.assertIn("base_territorial", self._md)
        self.assertIn("ortofoto", self._md)

    def test_contains_source_candidates(self):
        self.assertIn("IGN", self._md)

    def test_contains_coords(self):
        self.assertIn("28.9", self._md)

    def test_markdown_with_warnings_contains_warning_text(self):
        from eia_agent.core.cartography_plan import _build_map_specs, CartographyPlanResult
        from eia_agent.core.geospatial_utils import GeoPoint, build_standard_map_extents

        point = GeoPoint(lat=28.9773, lon=-13.5395, status="ESTIMADO")
        extents = build_standard_map_extents(point)
        maps = _build_map_specs(point, extents)
        result = CartographyPlanResult(
            expediente_id="TEST-ESTIMADO",
            center=point.to_dict(),
            maps=maps,
            ready_for_render=False,
            warnings=["Coordenadas ESTIMADO"],
        )
        md = build_cartography_plan_markdown(result)
        self.assertIn("ESTIMADO", md)


# ---------------------------------------------------------------------------
# 6. Escritura opcional
# ---------------------------------------------------------------------------

class TestWriteOutputs(unittest.TestCase):

    def test_no_write_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=False)
            self.assertFalse((exp / "cartografia").exists())

    def test_write_creates_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True)
            json_path = exp / "cartografia" / "cartografia_plan.json"
            self.assertTrue(json_path.exists())

    def test_write_creates_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True)
            md_path = exp / "cartografia" / "cartografia_plan.md"
            self.assertTrue(md_path.exists())

    def test_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True)
            json_path = exp / "cartografia" / "cartografia_plan.json"
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIn("maps", data)
            self.assertEqual(len(data["maps"]), 6)

    def test_json_contains_map_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True)
            json_path = exp / "cartografia" / "cartografia_plan.json"
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            ids = [m["map_id"] for m in data["maps"]]
            self.assertEqual(ids, _EXPECTED_MAP_IDS)

    def test_md_contains_map_001(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True)
            md_path = exp / "cartografia" / "cartografia_plan.md"
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("MAP-001", content)

    def test_custom_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            build_cartography_plan(exp, write_outputs=True, output_dir="mapas_custom")
            self.assertTrue((exp / "mapas_custom" / "cartografia_plan.json").exists())

    def test_note_added_when_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            result = build_cartography_plan(exp, write_outputs=True)
            notes_text = " ".join(result.notes)
            self.assertIn("cartografia_plan.json", notes_text)


# ---------------------------------------------------------------------------
# 7. CLI
# ---------------------------------------------------------------------------

class TestCLICartographyPlan(unittest.TestCase):

    def _run_cli(self, args: list[str]) -> int:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_expediente",
            Path(__file__).parent.parent / "run_expediente.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main(args)

    def test_cli_no_write_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            code = self._run_cli([str(exp), "cartography-plan"])
            self.assertEqual(code, 0)

    def test_cli_no_write_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            self._run_cli([str(exp), "cartography-plan"])
            self.assertFalse((exp / "cartografia").exists())

    def test_cli_write_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            self._run_cli([str(exp), "cartography-plan", "--write"])
            self.assertTrue((exp / "cartografia" / "cartografia_plan.json").exists())
            self.assertTrue((exp / "cartografia" / "cartografia_plan.md").exists())

    def test_cli_missing_phase2_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-VACIO"
            exp.mkdir()
            code = self._run_cli([str(exp), "cartography-plan"])
            self.assertEqual(code, 1)

    def test_cli_write_json_has_six_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_expediente(Path(tmp), _PHASE2_LANZAROTE)
            self._run_cli([str(exp), "cartography-plan", "--write"])
            with open(exp / "cartografia" / "cartografia_plan.json", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data["maps"]), 6)


# ---------------------------------------------------------------------------
# 8. Fixture Lanzarote
# ---------------------------------------------------------------------------

class TestLanzaroteFixture(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._exp = _make_expediente(tmp, _PHASE2_LANZAROTE)
        self._result = build_cartography_plan(self._exp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_six_maps_generated(self):
        self.assertEqual(len(self._result.maps), 6)

    def test_center_lat_lanzarote(self):
        self.assertAlmostEqual(self._result.center["lat"], 28.9773, places=3)

    def test_center_lon_lanzarote(self):
        self.assertAlmostEqual(self._result.center["lon"], -13.5395, places=3)

    def test_ready_for_render_is_true(self):
        self.assertTrue(self._result.ready_for_render)

    def test_no_warnings(self):
        self.assertEqual(self._result.warnings, [])

    def test_each_map_has_bbox(self):
        for m in self._result.maps:
            self.assertIn("bbox", m.extent, msg=f"{m.map_id} sin bbox en extent")

    def test_situacion_general_radius(self):
        m = next(x for x in self._result.maps if x.map_id == "MAP-001")
        self.assertAlmostEqual(m.extent.get("radius_m", 0), 25000.0)

    def test_detalle_parcela_radius(self):
        m = next(x for x in self._result.maps if x.map_id == "MAP-003")
        self.assertAlmostEqual(m.extent.get("radius_m", 0), 250.0)

    def test_entorno_500m_radius(self):
        m = next(x for x in self._result.maps if x.map_id == "MAP-005")
        self.assertAlmostEqual(m.extent.get("radius_m", 0), 500.0)

    def test_entorno_2000m_radius(self):
        m = next(x for x in self._result.maps if x.map_id == "MAP-006")
        self.assertAlmostEqual(m.extent.get("radius_m", 0), 2000.0)

    def test_map_004_uses_situacion_general_extent(self):
        m = next(x for x in self._result.maps if x.map_id == "MAP-004")
        self.assertEqual(m.extent_key, "situacion_general")

    def test_all_statuses_ready(self):
        for m in self._result.maps:
            self.assertEqual(m.status, "READY_FOR_RENDER")


if __name__ == "__main__":
    unittest.main()
