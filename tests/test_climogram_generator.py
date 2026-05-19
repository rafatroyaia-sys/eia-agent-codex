"""Tests para CL-04 — climogram_generator.py

Sin AEMET real. Sin red. PNG generado en directorio temporal.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.climate_indices import MonthlyClimateData

try:
    from eia_agent.core.climogram_generator import (
        ClimogramConfig,
        ClimogramResult,
        default_climogram_filename,
        generate_climogram,
        generate_climogram_from_dict,
        validate_png,
    )
    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False

# ---------------------------------------------------------------------------
# Fixtures climáticos
# ---------------------------------------------------------------------------

def _lanzarote() -> MonthlyClimateData:
    """Lanzarote aproximado — árido cálido. P anual ~131 mm."""
    return MonthlyClimateData(
        temperatures_c  =[17.8,18.1,18.8,19.4,20.7,22.7,24.9,25.7,25.1,23.5,21.0,18.6],
        precipitations_mm=[22.0,19.0,15.0, 7.0, 2.0, 1.0, 0.0, 1.0, 5.0,14.0,21.0,24.0],
        station_id="C029O",
        station_name="Lanzarote Aeropuerto",
        period="1991-2020",
    )

def _humid() -> MonthlyClimateData:
    """Clima húmedo oceánico — P anual ~825 mm."""
    return MonthlyClimateData(
        temperatures_c  =[ 5, 6, 8,10,13,16,18,18,15,12, 8, 6],
        precipitations_mm=[80,70,65,55,60,60,55,60,65,80,85,90],
        station_id="HUM01",
        station_name="Estación Húmeda",
        period="1991-2020",
    )

def _minimal() -> MonthlyClimateData:
    """Datos mínimos sin station_id ni periodo."""
    return MonthlyClimateData(
        temperatures_c  =[10.0]*12,
        precipitations_mm=[50.0]*12,
    )


# ===========================================================================
# A. ClimogramConfig
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestClimogramConfig(unittest.TestCase):

    def test_default_values(self):
        c = ClimogramConfig()
        self.assertIsNone(c.title)
        self.assertIsNone(c.subtitle)
        self.assertAlmostEqual(c.width_inches, 10.0)
        self.assertAlmostEqual(c.height_inches, 6.0)
        self.assertEqual(c.dpi, 150)
        self.assertTrue(c.show_gaussen)
        self.assertTrue(c.show_annual_summary)
        self.assertEqual(c.language, "es")

    def test_to_dict_keys(self):
        d = ClimogramConfig().to_dict()
        for k in ("title", "subtitle", "width_inches", "height_inches",
                  "dpi", "show_gaussen", "show_annual_summary", "language"):
            self.assertIn(k, d)

    def test_from_dict_roundtrip(self):
        c = ClimogramConfig(title="Mi título", dpi=200, show_gaussen=False)
        c2 = ClimogramConfig.from_dict(c.to_dict())
        self.assertEqual(c2.title, "Mi título")
        self.assertEqual(c2.dpi, 200)
        self.assertFalse(c2.show_gaussen)

    def test_from_dict_defaults_for_missing_keys(self):
        c = ClimogramConfig.from_dict({})
        self.assertEqual(c.dpi, 150)
        self.assertEqual(c.language, "es")

    def test_custom_dimensions(self):
        c = ClimogramConfig(width_inches=8.0, height_inches=5.0)
        self.assertAlmostEqual(c.width_inches, 8.0)
        self.assertAlmostEqual(c.height_inches, 5.0)


# ===========================================================================
# B. default_climogram_filename
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestDefaultFilename(unittest.TestCase):

    def test_no_args(self):
        self.assertEqual(default_climogram_filename(), "climograma.png")

    def test_with_station_id(self):
        name = default_climogram_filename(station_id="C029O")
        self.assertIn("C029O", name)
        self.assertTrue(name.endswith(".png"))

    def test_with_station_and_period(self):
        name = default_climogram_filename("C029O", "1981-2010")
        self.assertIn("C029O", name)
        self.assertIn("1981-2010", name)
        self.assertTrue(name.endswith(".png"))

    def test_no_problematic_characters(self):
        # Espacios, barras, puntos especiales deben quedar reemplazados
        name = default_climogram_filename("ID/con espacios", "1991-2020")
        self.assertNotIn("/", name)
        self.assertNotIn(" ", name)
        self.assertTrue(name.endswith(".png"))

    def test_none_period_excluded(self):
        name = default_climogram_filename(station_id="ABC", period=None)
        # No debe tener doble guión bajo ni sufijo None
        self.assertNotIn("None", name)
        self.assertTrue(name.endswith(".png"))


# ===========================================================================
# C. Generación básica
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestGenerateClimoBasic(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _out(self, name="climo.png"):
        return str(Path(self.tmp) / name)

    def test_generates_png_file(self):
        path = self._out()
        generate_climogram(_lanzarote(), path)
        self.assertTrue(Path(path).exists())

    def test_validate_png_true(self):
        path = self._out("v.png")
        generate_climogram(_lanzarote(), path)
        self.assertTrue(validate_png(path))

    def test_validate_png_false_for_missing(self):
        self.assertFalse(validate_png(self._out("nonexistent.png")))

    def test_result_output_path(self):
        path = self._out()
        result = generate_climogram(_lanzarote(), path)
        self.assertEqual(result.output_path, path)

    def test_result_width_px_positive(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertGreater(result.width_px, 0)

    def test_result_height_px_positive(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertGreater(result.height_px, 0)

    def test_result_annual_temperature(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertAlmostEqual(result.annual_temperature_c, 21.36, places=1)

    def test_result_annual_precipitation(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertAlmostEqual(result.annual_precipitation_mm, 131.0, places=0)

    def test_result_dry_months_lanzarote(self):
        result = generate_climogram(_lanzarote(), self._out())
        # Lanzarote tiene meses secos (P<=2T para varios meses)
        self.assertIsInstance(result.dry_months_gaussen, list)
        self.assertIn(7, result.dry_months_gaussen)  # julio

    def test_result_station_id(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertEqual(result.station_id, "C029O")

    def test_result_station_name(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertEqual(result.station_name, "Lanzarote Aeropuerto")

    def test_result_period(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertEqual(result.period, "1991-2020")

    def test_result_is_ClimogramResult(self):
        result = generate_climogram(_lanzarote(), self._out())
        self.assertIsInstance(result, ClimogramResult)

    def test_result_to_dict_keys(self):
        result = generate_climogram(_lanzarote(), self._out())
        d = result.to_dict()
        for k in ("output_path", "width_px", "height_px", "dpi",
                  "station_id", "station_name", "period",
                  "annual_temperature_c", "annual_precipitation_mm",
                  "dry_months_gaussen", "warnings", "notes"):
            self.assertIn(k, d)

    def test_summary_not_empty(self):
        result = generate_climogram(_lanzarote(), self._out())
        s = result.summary()
        self.assertGreater(len(s), 10)
        self.assertIn("Lanzarote", s)

    def test_humid_fixture_generates_png(self):
        path = self._out("humid.png")
        generate_climogram(_humid(), path)
        self.assertTrue(validate_png(path))

    def test_minimal_data_generates_png(self):
        path = self._out("minimal.png")
        generate_climogram(_minimal(), path)
        self.assertTrue(validate_png(path))


# ===========================================================================
# D. Creación de directorios
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestDirectoryCreation(unittest.TestCase):

    def test_creates_nested_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b" / "c" / "climo.png"
            generate_climogram(_minimal(), str(nested))
            self.assertTrue(nested.exists())


# ===========================================================================
# E. Configuración
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestConfiguration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _out(self, name="c.png"):
        return str(Path(self.tmp) / name)

    def test_respects_dpi(self):
        cfg = ClimogramConfig(dpi=100, width_inches=8.0, height_inches=5.0)
        result = generate_climogram(_lanzarote(), self._out("dpi.png"), config=cfg)
        self.assertEqual(result.dpi, 100)

    def test_show_gaussen_false_gives_empty_dry_months(self):
        cfg = ClimogramConfig(show_gaussen=False)
        result = generate_climogram(_lanzarote(), self._out("nog.png"), config=cfg)
        self.assertEqual(result.dry_months_gaussen, [])

    def test_custom_title_in_summary(self):
        cfg = ClimogramConfig(title="MI TÍTULO")
        result = generate_climogram(_lanzarote(), self._out("t.png"), config=cfg)
        # El título se pasa a matplotlib — no lo verifica el summary, pero debe
        # generar sin error
        self.assertTrue(validate_png(result.output_path))

    def test_custom_subtitle(self):
        cfg = ClimogramConfig(subtitle="Subtítulo personalizado")
        result = generate_climogram(_lanzarote(), self._out("st.png"), config=cfg)
        self.assertTrue(validate_png(result.output_path))

    def test_show_annual_summary_false(self):
        cfg = ClimogramConfig(show_annual_summary=False)
        result = generate_climogram(_lanzarote(), self._out("ns.png"), config=cfg)
        self.assertTrue(validate_png(result.output_path))

    def test_none_config_uses_defaults(self):
        result = generate_climogram(_lanzarote(), self._out("def.png"), config=None)
        self.assertEqual(result.dpi, 150)

    def test_width_px_matches_config(self):
        cfg = ClimogramConfig(width_inches=8.0, height_inches=4.0, dpi=100)
        result = generate_climogram(_lanzarote(), self._out("w.png"), config=cfg)
        self.assertEqual(result.width_px, 800)
        self.assertEqual(result.height_px, 400)


# ===========================================================================
# F. Errores
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestErrors(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _out(self, name):
        return str(Path(self.tmp) / name)

    def test_invalid_11_months_raises_value_error(self):
        bad = MonthlyClimateData(
            temperatures_c=[15.0]*11,
            precipitations_mm=[50.0]*12,
        )
        with self.assertRaises(ValueError):
            generate_climogram(bad, self._out("bad.png"))

    def test_non_png_extension_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_climogram(_minimal(), self._out("climo.jpg"))

    def test_non_png_extension_docx_raises(self):
        with self.assertRaises(ValueError):
            generate_climogram(_minimal(), self._out("climo.docx"))

    def test_no_extension_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_climogram(_minimal(), self._out("climo"))

    def test_validate_png_empty_file_false(self):
        empty = Path(self.tmp) / "empty.png"
        empty.write_bytes(b"")
        self.assertFalse(validate_png(empty))

    def test_validate_png_bad_header_false(self):
        bad = Path(self.tmp) / "bad.png"
        bad.write_bytes(b"notapng12345678")
        self.assertFalse(validate_png(bad))


# ===========================================================================
# G. generate_climogram_from_dict
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestFromDict(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _out(self, name="d.png"):
        return str(Path(self.tmp) / name)

    def test_from_dict_valid(self):
        d = _lanzarote().to_dict()
        result = generate_climogram_from_dict(d, self._out())
        self.assertTrue(validate_png(result.output_path))

    def test_from_dict_station_id_preserved(self):
        d = _lanzarote().to_dict()
        result = generate_climogram_from_dict(d, self._out())
        self.assertEqual(result.station_id, "C029O")

    def test_from_dict_missing_key_raises(self):
        with self.assertRaises(KeyError):
            generate_climogram_from_dict({"temperatures_c": [15.0]*12}, self._out("e.png"))

    def test_from_dict_invalid_data_raises(self):
        bad = {"temperatures_c": [15.0]*11, "precipitations_mm": [50.0]*12}
        with self.assertRaises(ValueError):
            generate_climogram_from_dict(bad, self._out("e2.png"))


# ===========================================================================
# H. Fixtures climáticos
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestClimaticFixtures(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _out(self, name):
        return str(Path(self.tmp) / name)

    def test_lanzarote_generates_without_error(self):
        result = generate_climogram(_lanzarote(), self._out("lz.png"))
        self.assertTrue(validate_png(result.output_path))

    def test_lanzarote_has_dry_months(self):
        result = generate_climogram(_lanzarote(), self._out("lz2.png"))
        self.assertGreater(len(result.dry_months_gaussen), 0)

    def test_humid_generates_without_error(self):
        result = generate_climogram(_humid(), self._out("hu.png"))
        self.assertTrue(validate_png(result.output_path))

    def test_humid_has_no_dry_months_or_few(self):
        result = generate_climogram(_humid(), self._out("hu2.png"))
        # En clima muy húmedo (P=65-90mm, T=5-18°C) P > 2T para la mayoría de meses
        # No todos son secos
        # P_min=55 (Abr), T_Apr=10 → 55 vs 20 → no seco
        self.assertEqual(result.dry_months_gaussen, [])

    def test_png_file_size_reasonable(self):
        path = self._out("sz.png")
        generate_climogram(_lanzarote(), path)
        size = Path(path).stat().st_size
        # PNG de 10"×6"@150dpi debe ser > 10 KB y < 2 MB
        self.assertGreater(size, 10_000)
        self.assertLess(size, 2_000_000)


# ===========================================================================
# I. No modificación de datos de entrada
# ===========================================================================

@unittest.skipUnless(_MATPLOTLIB_OK, "matplotlib no disponible")
class TestNoModification(unittest.TestCase):

    def test_does_not_modify_temperatures(self):
        data = _lanzarote()
        orig_temps = list(data.temperatures_c)
        with tempfile.TemporaryDirectory() as tmp:
            generate_climogram(data, str(Path(tmp) / "c.png"))
        self.assertEqual(data.temperatures_c, orig_temps)

    def test_does_not_modify_precipitations(self):
        data = _lanzarote()
        orig_precips = list(data.precipitations_mm)
        with tempfile.TemporaryDirectory() as tmp:
            generate_climogram(data, str(Path(tmp) / "c.png"))
        self.assertEqual(data.precipitations_mm, orig_precips)

    def test_does_not_modify_station_id(self):
        data = _lanzarote()
        with tempfile.TemporaryDirectory() as tmp:
            generate_climogram(data, str(Path(tmp) / "c.png"))
        self.assertEqual(data.station_id, "C029O")


if __name__ == "__main__":
    unittest.main()
