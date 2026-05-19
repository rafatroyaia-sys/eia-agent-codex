"""
Tests CA-11 — schematic_map_generator.py

Grupos:
  1. Config
  2. PNG generation
  3. Contenido mínimo del resultado
  4. Plan (load_cartography_plan + generate_schematic_maps_from_plan)
  5. Report
  6. CLI
  7. Fixture Lanzarote
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.schematic_map_generator import (
    SchematicMapConfig,
    SchematicMapResult,
    build_map_generation_report,
    generate_schematic_map,
    generate_schematic_maps_from_plan,
    load_cartography_plan,
    validate_png,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_LANZAROTE_CENTER = {"lat": 28.9773, "lon": -13.5395, "status": "DECLARADO",
                     "source": "phase2_result", "notes": []}

_LANZAROTE_BBOX = {
    "min_lat": 28.9548, "min_lon": -13.5862,
    "max_lat": 28.9998, "max_lon": -13.4928,
}

def _make_map_spec_dict(map_id="MAP-001", title="Situación general",
                        extent_key="situacion_general", radius_m=25000.0,
                        status="READY_FOR_RENDER") -> dict:
    return {
        "map_id": map_id,
        "title": title,
        "purpose": "Test purpose",
        "map_type": "situacion_general",
        "extent_key": extent_key,
        "extent": {
            "center": _LANZAROTE_CENTER,
            "bbox": _LANZAROTE_BBOX,
            "radius_m": radius_m,
            "scale_hint": extent_key,
            "warnings": [],
            "notes": [],
        },
        "required_layers": ["base_territorial", "marcador_proyecto"],
        "source_candidates": ["IGN / BTN100", "PNOA"],
        "output_filename": f"{map_id}_test.png",
        "status": status,
        "warnings": [],
        "notes": [],
    }


_SIX_MAPS = [
    _make_map_spec_dict("MAP-001", "Situación general", "situacion_general", 25000),
    _make_map_spec_dict("MAP-002", "Emplazamiento", "emplazamiento", 1000),
    _make_map_spec_dict("MAP-003", "Parcela / catastro", "detalle_parcela", 250),
    _make_map_spec_dict("MAP-004", "Red Natura 2000 / ENP", "situacion_general", 25000),
    _make_map_spec_dict("MAP-005", "Usos del suelo entorno", "entorno_500m", 500),
    _make_map_spec_dict("MAP-006", "Inundabilidad / riesgos", "entorno_2000m", 2000),
]

_PLAN_LANZAROTE = {
    "expediente_id": "expediente-EIA-TEST",
    "center": _LANZAROTE_CENTER,
    "maps": _SIX_MAPS,
    "ready_for_render": True,
    "warnings": [],
    "notes": [],
}


def _write_plan(tmp: Path, plan: dict) -> Path:
    cart_dir = tmp / "expediente-EIA-TEST" / "cartografia"
    cart_dir.mkdir(parents=True)
    plan_path = cart_dir / "cartografia_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return plan_path


# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------

class TestSchematicMapConfig(unittest.TestCase):

    def test_defaults(self):
        c = SchematicMapConfig()
        self.assertEqual(c.width_px, 1600)
        self.assertEqual(c.height_px, 1100)
        self.assertEqual(c.dpi, 150)
        self.assertTrue(c.show_test_watermark)
        self.assertEqual(c.background, "light")
        self.assertEqual(c.language, "es")

    def test_to_dict_has_all_fields(self):
        c = SchematicMapConfig()
        d = c.to_dict()
        self.assertIn("width_px", d)
        self.assertIn("height_px", d)
        self.assertIn("dpi", d)
        self.assertIn("show_test_watermark", d)
        self.assertIn("background", d)
        self.assertIn("language", d)

    def test_to_dict_values(self):
        c = SchematicMapConfig(width_px=800, height_px=600, dpi=96)
        d = c.to_dict()
        self.assertEqual(d["width_px"], 800)
        self.assertEqual(d["height_px"], 600)
        self.assertEqual(d["dpi"], 96)

    def test_from_dict_roundtrip(self):
        c = SchematicMapConfig(width_px=1200, height_px=900, show_test_watermark=False)
        c2 = SchematicMapConfig.from_dict(c.to_dict())
        self.assertEqual(c.width_px, c2.width_px)
        self.assertEqual(c.height_px, c2.height_px)
        self.assertEqual(c.show_test_watermark, c2.show_test_watermark)

    def test_from_dict_defaults_on_empty(self):
        c = SchematicMapConfig.from_dict({})
        self.assertEqual(c.width_px, 1600)
        self.assertEqual(c.dpi, 150)

    def test_from_dict_accepts_partial(self):
        c = SchematicMapConfig.from_dict({"dpi": 72})
        self.assertEqual(c.dpi, 72)
        self.assertEqual(c.width_px, 1600)


# ---------------------------------------------------------------------------
# 2. PNG generation
# ---------------------------------------------------------------------------

class TestGenerateSchematicMap(unittest.TestCase):

    def _spec(self, **kw):
        return _make_map_spec_dict(**kw)

    def test_generates_png_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            generate_schematic_map(self._spec(), out)
            self.assertTrue(out.exists())

    def test_png_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            generate_schematic_map(self._spec(), out)
            self.assertTrue(validate_png(out))

    def test_png_size_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            generate_schematic_map(self._spec(), out)
            self.assertGreater(out.stat().st_size, 0)

    def test_png_dimensions_match_config(self):
        from PIL import Image
        cfg = SchematicMapConfig(width_px=800, height_px=600)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            generate_schematic_map(self._spec(), out, cfg)
            with Image.open(out) as img:
                size = img.size
            self.assertEqual(size, (800, 600))

    def test_invalid_extension_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                generate_schematic_map(self._spec(), Path(tmp) / "MAP-001.jpg")

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "a" / "b" / "c" / "MAP-001.png"
            generate_schematic_map(self._spec(), out)
            self.assertTrue(out.exists())

    def test_accepts_dict_input(self):
        spec_dict = self._spec()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            result = generate_schematic_map(spec_dict, out)
            self.assertEqual(result.status, "GENERATED_PROVISIONAL")

    def test_accepts_string_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "MAP-001.png")
            result = generate_schematic_map(self._spec(), out)
            self.assertTrue(validate_png(out))

    def test_without_watermark(self):
        cfg = SchematicMapConfig(show_test_watermark=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MAP-001.png"
            result = generate_schematic_map(self._spec(), out, cfg)
            self.assertEqual(result.status, "GENERATED_PROVISIONAL")
            self.assertTrue(validate_png(out))

    def test_different_radii_produce_valid_png(self):
        for radius in [250, 500, 1000, 2000, 25000]:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "test.png"
                spec = self._spec(radius_m=radius)
                result = generate_schematic_map(spec, out)
                self.assertTrue(validate_png(out),
                                msg=f"radius={radius} no generó PNG válido")


# ---------------------------------------------------------------------------
# 3. Contenido mínimo del resultado
# ---------------------------------------------------------------------------

class TestSchematicMapResult(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        out = Path(self._tmp.name) / "MAP-001.png"
        self._result = generate_schematic_map(_make_map_spec_dict(), out)

    def tearDown(self):
        self._tmp.cleanup()

    def test_result_has_map_id(self):
        self.assertEqual(self._result.map_id, "MAP-001")

    def test_result_has_title(self):
        self.assertEqual(self._result.title, "Situación general")

    def test_status_generated_provisional(self):
        self.assertEqual(self._result.status, "GENERATED_PROVISIONAL")

    def test_output_path_set(self):
        self.assertTrue(self._result.output_path.endswith(".png"))

    def test_width_height_set(self):
        self.assertEqual(self._result.width_px, 1600)
        self.assertEqual(self._result.height_px, 1100)

    def test_warnings_contain_provisional_note(self):
        text = " ".join(self._result.warnings)
        self.assertIn("provisional", text.lower())

    def test_notes_non_empty(self):
        self.assertGreater(len(self._result.notes), 0)

    def test_to_dict_has_all_fields(self):
        d = self._result.to_dict()
        for key in ("map_id", "title", "output_path", "width_px", "height_px",
                    "status", "warnings", "notes"):
            self.assertIn(key, d)

    def test_summary_not_empty(self):
        s = self._result.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)

    def test_summary_contains_map_id(self):
        self.assertIn("MAP-001", self._result.summary())

    def test_summary_contains_status(self):
        self.assertIn("GENERATED_PROVISIONAL", self._result.summary())

    def test_does_not_modify_original_spec(self):
        spec = _make_map_spec_dict()
        original_layers = list(spec["required_layers"])
        with tempfile.TemporaryDirectory() as tmp:
            generate_schematic_map(spec, Path(tmp) / "x.png")
        self.assertEqual(spec["required_layers"], original_layers)

    def test_result_to_dict_warnings_copied(self):
        d = self._result.to_dict()
        d["warnings"].append("extra")
        self.assertNotIn("extra", self._result.warnings)


# ---------------------------------------------------------------------------
# 4. Plan
# ---------------------------------------------------------------------------

class TestLoadCartographyPlan(unittest.TestCase):

    def test_load_valid_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            plan = load_cartography_plan(plan_path)
            self.assertIn("maps", plan)
            self.assertEqual(len(plan["maps"]), 6)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_cartography_plan("/no/existe/cartografia_plan.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cartography_plan(bad)

    def test_json_without_maps_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "plan.json"
            p.write_text(json.dumps({"expediente_id": "TEST"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cartography_plan(p)

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            result = load_cartography_plan(plan_path)
            self.assertIsInstance(result, dict)


class TestGenerateSchematicMapsFromPlan(unittest.TestCase):

    def test_generates_six_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            out_dir = Path(tmp) / "mapas"
            results = generate_schematic_maps_from_plan(plan_path, out_dir)
            self.assertEqual(len(results), 6)

    def test_all_results_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            out_dir = Path(tmp) / "mapas"
            results = generate_schematic_maps_from_plan(plan_path, out_dir)
            for r in results:
                self.assertEqual(r.status, "GENERATED_PROVISIONAL",
                                 msg=f"{r.map_id}: {r.warnings}")

    def test_all_pngs_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            out_dir = Path(tmp) / "mapas"
            results = generate_schematic_maps_from_plan(plan_path, out_dir)
            for r in results:
                self.assertTrue(validate_png(r.output_path),
                                msg=f"{r.map_id} no es PNG válido")

    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            out_dir = Path(tmp) / "nuevo_dir" / "mapas"
            generate_schematic_maps_from_plan(plan_path, out_dir)
            self.assertTrue(out_dir.exists())

    def test_missing_plan_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                generate_schematic_maps_from_plan(
                    Path(tmp) / "no_existe.json", Path(tmp) / "mapas"
                )

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = _write_plan(Path(tmp), _PLAN_LANZAROTE)
            results = generate_schematic_maps_from_plan(plan_path, Path(tmp) / "mapas")
            self.assertIsInstance(results, list)


# ---------------------------------------------------------------------------
# 5. Report
# ---------------------------------------------------------------------------

class TestBuildMapGenerationReport(unittest.TestCase):

    def _make_result(self, map_id="MAP-001", status="GENERATED_PROVISIONAL"):
        return SchematicMapResult(
            map_id=map_id,
            title=f"Test {map_id}",
            output_path=f"/tmp/{map_id}.png",
            width_px=1600,
            height_px=1100,
            status=status,
            warnings=["w"] if status == "ERROR" else [],
            notes=[],
        )

    def setUp(self):
        self._results = [self._make_result(mid) for mid in
                         ["MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006"]]
        self._report = build_map_generation_report(self._results)

    def test_report_is_string(self):
        self.assertIsInstance(self._report, str)

    def test_report_not_empty(self):
        self.assertGreater(len(self._report), 0)

    def test_contains_map_001(self):
        self.assertIn("MAP-001", self._report)

    def test_contains_all_map_ids(self):
        for mid in ["MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006"]:
            self.assertIn(mid, self._report, msg=f"{mid} no en report")

    def test_contains_provisional_warning(self):
        self.assertIn("provisional", self._report.lower())

    def test_contains_totals(self):
        self.assertIn("6", self._report)

    def test_error_status_shown(self):
        results_with_error = [
            self._make_result("MAP-001", "GENERATED_PROVISIONAL"),
            self._make_result("MAP-002", "ERROR"),
        ]
        report = build_map_generation_report(results_with_error)
        self.assertIn("ERROR", report)

    def test_contains_table_separator(self):
        self.assertIn("|", self._report)


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------

class TestCLISchematicMaps(unittest.TestCase):

    def _run_cli(self, args: list[str]) -> int:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_expediente",
            Path(__file__).parent.parent / "run_expediente.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main(args)

    def _make_exp(self, tmp: Path) -> Path:
        exp = tmp / "expediente-EIA-TEST"
        exp.mkdir()
        plan_path = _write_plan(tmp, _PLAN_LANZAROTE)
        return exp, plan_path

    def test_cli_no_write_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-TEST"
            exp.mkdir()
            _write_plan(Path(tmp), _PLAN_LANZAROTE)
            plan_file = Path(tmp) / "expediente-EIA-TEST" / "cartografia" / "cartografia_plan.json"
            code = self._run_cli([str(exp), "schematic-maps", "--plan", str(plan_file)])
            self.assertEqual(code, 0)

    def test_cli_no_write_no_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-TEST"
            exp.mkdir()
            _write_plan(Path(tmp), _PLAN_LANZAROTE)
            plan_file = Path(tmp) / "expediente-EIA-TEST" / "cartografia" / "cartografia_plan.json"
            self._run_cli([str(exp), "schematic-maps", "--plan", str(plan_file)])
            mapas_dir = exp / "cartografia" / "mapas"
            self.assertFalse(mapas_dir.exists())

    def test_cli_write_generates_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-TEST"
            exp.mkdir()
            _write_plan(Path(tmp), _PLAN_LANZAROTE)
            plan_file = Path(tmp) / "expediente-EIA-TEST" / "cartografia" / "cartografia_plan.json"
            self._run_cli([str(exp), "schematic-maps", "--plan", str(plan_file), "--write"])
            mapas_dir = exp / "cartografia" / "mapas"
            pngs = list(mapas_dir.glob("*.png"))
            self.assertEqual(len(pngs), 6)

    def test_cli_missing_plan_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-TEST"
            exp.mkdir()
            code = self._run_cli([
                str(exp), "schematic-maps",
                "--plan", str(exp / "cartografia" / "no_existe.json")
            ])
            self.assertEqual(code, 1)

    def test_cli_default_plan_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-TEST"
            exp.mkdir()
            _write_plan(Path(tmp), _PLAN_LANZAROTE)
            # Without --plan, should use default cartografia/cartografia_plan.json
            code = self._run_cli([str(exp), "schematic-maps"])
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# 7. Fixture Lanzarote
# ---------------------------------------------------------------------------

class TestLanzaroteFixture(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        plan_path = _write_plan(tmp, _PLAN_LANZAROTE)
        self._out_dir = tmp / "mapas"
        self._results = generate_schematic_maps_from_plan(plan_path, self._out_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_generates_six_maps(self):
        self.assertEqual(len(self._results), 6)

    def test_all_status_generated(self):
        for r in self._results:
            self.assertEqual(r.status, "GENERATED_PROVISIONAL",
                             msg=f"{r.map_id} no GENERATED_PROVISIONAL")

    def test_all_pngs_valid(self):
        for r in self._results:
            self.assertTrue(validate_png(r.output_path),
                            msg=f"{r.map_id} PNG inválido")

    def test_all_pngs_nonzero_size(self):
        for r in self._results:
            self.assertGreater(Path(r.output_path).stat().st_size, 1000,
                               msg=f"{r.map_id} PNG demasiado pequeño")

    def test_map_ids_present(self):
        ids = {r.map_id for r in self._results}
        for mid in ["MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006"]:
            self.assertIn(mid, ids)

    def test_situacion_general_map_valid(self):
        m001 = next(r for r in self._results if r.map_id == "MAP-001")
        self.assertTrue(validate_png(m001.output_path))

    def test_detalle_parcela_map_valid(self):
        m003 = next(r for r in self._results if r.map_id == "MAP-003")
        self.assertTrue(validate_png(m003.output_path))

    def test_report_from_lanzarote_results(self):
        report = build_map_generation_report(self._results)
        self.assertIn("MAP-001", report)
        self.assertIn("GENERATED_PROVISIONAL", report)

    def test_all_output_paths_in_output_dir(self):
        for r in self._results:
            self.assertTrue(
                Path(r.output_path).parent == self._out_dir,
                msg=f"{r.map_id} no está en {self._out_dir}"
            )


if __name__ == "__main__":
    unittest.main()
