"""Tests para CL-03 — climate_indices.py

Sin llamadas a AEMET. Sin red. Fixtures en memoria.
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.climate_indices import (
    ClimateClassification,
    MonthlyClimateData,
    classify_climate,
    classify_koppen,
    classify_martonne,
    gaussen_dry_months,
    martonne_index,
    month_names_es,
    parse_monthly_climate_from_aemet_normals,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_data(temps, precips, **kwargs) -> MonthlyClimateData:
    return MonthlyClimateData(
        temperatures_c=list(temps),
        precipitations_mm=list(precips),
        **kwargs,
    )

def _uniform(t=15.0, p=50.0) -> MonthlyClimateData:
    return _make_data([t] * 12, [p] * 12)

def _lanzarote() -> MonthlyClimateData:
    """Lanzarote aproximado. T_anual≈21.4°C, P_anual≈131mm, lluvias invernales → BWh."""
    return _make_data(
        temps  =[17.8,18.1,18.8,19.4,20.7,22.7,24.9,25.7,25.1,23.5,21.0,18.6],
        precips=[22.0,19.0,15.0, 7.0, 2.0, 1.0, 0.0, 1.0, 5.0,14.0,21.0,24.0],
        station_id="C029O", station_name="Lanzarote Aeropuerto",
    )

def _bwh_hot_desert() -> MonthlyClimateData:
    """Desierto cálido tipo Sahara → BWh."""
    return _make_data(
        temps  =[22,23,26,30,34,37,38,37,33,29,25,22],
        precips=[ 5, 5, 3, 1, 0, 0, 0, 0, 1, 3, 5, 5],
    )

def _bsh_hot_steppe() -> MonthlyClimateData:
    """Estepa cálida → BSh. P=350mm, invierno dominante, T_anual≈27°C."""
    return _make_data(
        temps  =[20,21,23,26,29,33,35,35,32,28,23,20],
        precips=[60,50,30,15,10, 5, 5, 5,15,50,60,45],
    )

def _bsk_cold_steppe() -> MonthlyClimateData:
    """Estepa fría → BSk. P=300mm, T_anual≈13.7°C."""
    return _make_data(
        temps  =[ 0, 3, 8,14,19,25,28,27,21,13, 5, 1],
        precips=[30,25,25,30,35,20,15,15,20,25,30,30],
    )

def _csa_mediterranean() -> MonthlyClimateData:
    """Mediterráneo cálido → Csa. Verano seco, T_warm≥22°C."""
    return _make_data(
        temps  =[10,11,13,15,19,24,27,27,23,19,14,11],
        precips=[80,70,60,40,30,10, 5, 5,20,60,80,90],
    )

def _csb_mediterranean_cool() -> MonthlyClimateData:
    """Mediterráneo fresco → Csb. Verano seco, T_warm<22°C."""
    return _make_data(
        temps  =[ 8, 9,11,13,16,19,21,21,18,15,11, 9],
        precips=[80,60,50,40,25,10, 3, 3,15,60,80,90],
    )

def _cfb_oceanic() -> MonthlyClimateData:
    """Oceánico templado → Cfb. Sin estación seca, T_warm<22°C."""
    return _make_data(
        temps  =[ 5, 6, 8,10,13,16,18,18,15,12, 8, 6],
        precips=[80,70,65,55,60,60,55,60,65,80,85,90],
    )

def _cfa_humid_subtropical() -> MonthlyClimateData:
    """Subtropical húmedo cálido → Cfa. Sin estación seca, T_warm≥22°C."""
    return _make_data(
        temps  =[ 6, 8,12,17,21,26,29,28,23,17,12, 7],
        precips=[80,80,90,85,90,100,120,100,85,80,80,80],
    )

def _af_tropical_rainforest() -> MonthlyClimateData:
    """Tropical lluvioso → Af. Todos los meses ≥18°C, mes más seco ≥60mm."""
    return _make_data(
        temps  =[26,27,28,28,27,26,25,25,26,27,27,26],
        precips=[200,180,200,220,230,180,160,160,180,200,220,200],
    )

def _aw_tropical_savanna() -> MonthlyClimateData:
    """Tropical de sabana → Aw. Todos ≥18°C, estación seca marcada."""
    return _make_data(
        temps  =[28,29,30,30,28,26,25,25,26,27,27,27],
        precips=[100,80,150,180,200,150,30,10,20,80,150,120],
    )

def _et_tundra() -> MonthlyClimateData:
    """Tundra → ET. T_warm=10°C."""
    return _make_data(
        temps  =[-10,-8,-5, 0, 5, 8,10, 8, 4,-1,-6,-8],
        precips=[ 20,15,15,20,30,40,45,40,35,25,20,20],
    )

def _ef_ice_cap() -> MonthlyClimateData:
    """Casquete → EF. T_warm≤0°C."""
    return _make_data(
        temps  =[-20,-18,-15,-8,-4,-1, 0,-2,-6,-12,-16,-18],
        precips=[  5,  5,  5, 5, 5, 5, 5, 5,  5,  5,  5,  5],
    )

def _dfb_continental() -> MonthlyClimateData:
    """Continental húmedo fresco → Dfb. T_cold≤-3°C."""
    return _make_data(
        temps  =[-5,-3, 3,10,16,19,21,20,14, 8, 2,-3],
        precips=[40,35,40,45,55,65,70,65,55,50,45,40],
    )


# ===========================================================================
# A. MonthlyClimateData
# ===========================================================================

class TestMonthlyClimateData(unittest.TestCase):

    def test_validate_passes_with_12_months(self):
        _uniform().validate()  # no exception

    def test_validate_fails_11_temperatures(self):
        d = _make_data([15]*11, [50]*12)
        with self.assertRaises(ValueError):
            d.validate()

    def test_validate_fails_11_precipitations(self):
        d = _make_data([15]*12, [50]*11)
        with self.assertRaises(ValueError):
            d.validate()

    def test_validate_fails_negative_precipitation(self):
        p = [50]*12
        p[3] = -1
        d = _make_data([15]*12, p)
        with self.assertRaises(ValueError):
            d.validate()

    def test_annual_temperature_is_mean(self):
        temps = list(range(12))          # 0..11
        d = _make_data(temps, [0]*12)
        self.assertAlmostEqual(d.annual_temperature(), sum(temps)/12)

    def test_annual_precipitation_is_sum(self):
        precips = [10.0 * (i + 1) for i in range(12)]
        d = _make_data([15]*12, precips)
        self.assertAlmostEqual(d.annual_precipitation(), sum(precips))

    def test_coldest_month(self):
        d = _lanzarote()
        self.assertAlmostEqual(d.coldest_month_temp(), 17.8)

    def test_warmest_month(self):
        d = _lanzarote()
        self.assertAlmostEqual(d.warmest_month_temp(), 25.7)

    def test_driest_month(self):
        d = _lanzarote()
        self.assertAlmostEqual(d.driest_month_precipitation(), 0.0)

    def test_wettest_month(self):
        d = _lanzarote()
        self.assertAlmostEqual(d.wettest_month_precipitation(), 24.0)

    def test_to_dict_from_dict_roundtrip(self):
        d = _lanzarote()
        d2 = MonthlyClimateData.from_dict(d.to_dict())
        self.assertEqual(d.temperatures_c, d2.temperatures_c)
        self.assertEqual(d.precipitations_mm, d2.precipitations_mm)
        self.assertEqual(d.station_id, d2.station_id)
        self.assertEqual(d.station_name, d2.station_name)

    def test_to_dict_contains_expected_keys(self):
        keys = _uniform().to_dict().keys()
        for k in ("temperatures_c", "precipitations_mm", "station_id",
                  "station_name", "period", "source"):
            self.assertIn(k, keys)

    def test_from_dict_optional_fields_default_none(self):
        d = MonthlyClimateData.from_dict({
            "temperatures_c": [15.0]*12,
            "precipitations_mm": [50.0]*12,
        })
        self.assertIsNone(d.station_id)
        self.assertIsNone(d.station_name)
        self.assertIsNone(d.period)
        self.assertIsNone(d.source)


# ===========================================================================
# B. Martonne
# ===========================================================================

class TestMartonne(unittest.TestCase):

    def test_index_calculation(self):
        # Lanzarote: P≈131, T≈21.4 → I = 131/(21.4+10) = 131/31.4 ≈ 4.17
        idx = martonne_index(131.0, 21.4)
        self.assertAlmostEqual(idx, 131.0 / 31.4, places=4)

    def test_index_T_plus_10_zero_raises(self):
        with self.assertRaises(ValueError):
            martonne_index(100.0, -10.0)

    def test_index_T_plus_10_negative_raises(self):
        with self.assertRaises(ValueError):
            martonne_index(100.0, -15.0)

    def test_classify_arido_extremo(self):
        self.assertEqual(classify_martonne(3.0), "árido extremo")

    def test_classify_arido(self):
        self.assertEqual(classify_martonne(7.0), "árido")

    def test_classify_semiarido(self):
        self.assertEqual(classify_martonne(15.0), "semiárido")

    def test_classify_subhumedo(self):
        self.assertEqual(classify_martonne(25.0), "subhúmedo")

    def test_classify_humedo(self):
        self.assertEqual(classify_martonne(45.0), "húmedo")

    def test_classify_muy_humedo(self):
        self.assertEqual(classify_martonne(70.0), "muy húmedo")

    def test_boundary_arido_extremo_5(self):
        # I=5 → árido (no árido extremo)
        self.assertEqual(classify_martonne(5.0), "árido")

    def test_lanzarote_arido_extremo(self):
        d = _lanzarote()
        idx = martonne_index(d.annual_precipitation(), d.annual_temperature())
        self.assertLess(idx, 5.0)
        self.assertEqual(classify_martonne(idx), "árido extremo")


# ===========================================================================
# C. Gaussen
# ===========================================================================

class TestGaussen(unittest.TestCase):

    def test_detects_dry_months(self):
        # Jul: T=25, P=0 → 0<=50 → seco; Ago: T=26, P=0 → seco
        d = _lanzarote()
        dry = gaussen_dry_months(d.temperatures_c, d.precipitations_mm)
        self.assertIn(7, dry)   # julio = mes 7
        self.assertIn(8, dry)   # agosto = mes 8

    def test_returns_1_indexed(self):
        # Si enero es seco, debe aparecer como 1 (no 0)
        temps = [20.0] * 12
        precips = [5.0] * 12   # 5 <= 2*20=40 → todos secos
        dry = gaussen_dry_months(temps, precips)
        self.assertIn(1, dry)
        self.assertNotIn(0, dry)

    def test_all_months_wet(self):
        # P=200 > 2*T=30 → ningún mes seco
        temps = [15.0] * 12
        precips = [200.0] * 12
        self.assertEqual(gaussen_dry_months(temps, precips), [])

    def test_boundary_exactly_2T(self):
        # P = 2*T exactamente → seco (criterion: P <= 2T)
        temps = [10.0] * 12
        precips = [20.0] * 12   # 20 == 2*10
        dry = gaussen_dry_months(temps, precips)
        self.assertEqual(len(dry), 12)

    def test_negative_temperature_not_dry(self):
        # T<0 → 2T<0, P>=0 > 2T → no seco
        temps = [-5.0] * 12
        precips = [0.0] * 12
        # 0 <= 2*(-5) = -10 → False → no seco
        self.assertEqual(gaussen_dry_months(temps, precips), [])

    def test_month_names_es_correct(self):
        self.assertEqual(month_names_es([1, 7, 12]),
                         ["Enero", "Julio", "Diciembre"])

    def test_month_names_es_all_12(self):
        names = month_names_es(list(range(1, 13)))
        self.assertEqual(names[0], "Enero")
        self.assertEqual(names[5], "Junio")
        self.assertEqual(names[11], "Diciembre")


# ===========================================================================
# D. Köppen fixtures
# ===========================================================================

class TestKoppenFixtures(unittest.TestCase):

    def _code(self, data):
        code, _, _ = classify_koppen(data)
        return code

    def test_bwh_hot_desert(self):
        self.assertEqual(self._code(_bwh_hot_desert()), "BWh")

    def test_bwh_lanzarote(self):
        """Lanzarote: T_anual≈21.4°C, P≈131mm, lluvias invernales → BWh."""
        self.assertEqual(self._code(_lanzarote()), "BWh")

    def test_bsh_hot_steppe(self):
        self.assertEqual(self._code(_bsh_hot_steppe()), "BSh")

    def test_bsk_cold_steppe(self):
        self.assertEqual(self._code(_bsk_cold_steppe()), "BSk")

    def test_csa_mediterranean(self):
        self.assertEqual(self._code(_csa_mediterranean()), "Csa")

    def test_csb_mediterranean_cool(self):
        self.assertEqual(self._code(_csb_mediterranean_cool()), "Csb")

    def test_cfb_oceanic(self):
        self.assertEqual(self._code(_cfb_oceanic()), "Cfb")

    def test_cfa_humid_subtropical(self):
        self.assertEqual(self._code(_cfa_humid_subtropical()), "Cfa")

    def test_af_tropical_rainforest(self):
        self.assertEqual(self._code(_af_tropical_rainforest()), "Af")

    def test_aw_tropical_savanna(self):
        self.assertEqual(self._code(_aw_tropical_savanna()), "Aw")

    def test_et_tundra(self):
        self.assertEqual(self._code(_et_tundra()), "ET")

    def test_ef_ice_cap(self):
        self.assertEqual(self._code(_ef_ice_cap()), "EF")

    def test_dfb_continental(self):
        self.assertEqual(self._code(_dfb_continental()), "Dfb")

    def test_koppen_returns_note_about_simplification(self):
        _, _, notes = classify_koppen(_lanzarote())
        self.assertTrue(any("simplificada" in n for n in notes))

    def test_koppen_label_not_empty(self):
        _, label, _ = classify_koppen(_lanzarote())
        self.assertTrue(label)

    def test_bwh_label_mentions_arido(self):
        _, label, _ = classify_koppen(_lanzarote())
        self.assertIn("BWh", label)

    def test_b_group_requires_normals_check(self):
        # Todos los climas B deben tener P < Pth
        for data, expected_prefix in [
            (_bwh_hot_desert(), "BW"),
            (_lanzarote(), "BW"),
            (_bsh_hot_steppe(), "BS"),
        ]:
            code = self._code(data)
            self.assertTrue(code.startswith(expected_prefix),
                            f"Esperado {expected_prefix}, got {code}")


# ===========================================================================
# E. classify_climate
# ===========================================================================

class TestClassifyClimate(unittest.TestCase):

    def setUp(self):
        self.result = classify_climate(_lanzarote())

    def test_returns_ClimateClassification(self):
        self.assertIsInstance(self.result, ClimateClassification)

    def test_includes_koppen_code(self):
        self.assertEqual(self.result.koppen_code, "BWh")

    def test_includes_martonne_index(self):
        self.assertFalse(math.isnan(self.result.martonne_index))
        self.assertLess(self.result.martonne_index, 5.0)

    def test_includes_martonne_label(self):
        self.assertEqual(self.result.martonne_label, "árido extremo")

    def test_includes_dry_months(self):
        # Lanzarote: al menos julio y agosto secos
        self.assertIn(7, self.result.dry_months_gaussen)
        self.assertIn(8, self.result.dry_months_gaussen)

    def test_includes_dry_month_names(self):
        self.assertIn("Julio", self.result.dry_months_names)
        self.assertIn("Agosto", self.result.dry_months_names)

    def test_annual_temperature_close_to_expected(self):
        self.assertAlmostEqual(self.result.annual_temperature_c, 21.36, places=1)

    def test_annual_precipitation_close_to_expected(self):
        self.assertAlmostEqual(self.result.annual_precipitation_mm, 131.0, places=0)

    def test_summary_not_empty(self):
        s = self.result.summary()
        self.assertGreater(len(s), 20)
        self.assertIn("BWh", s)

    def test_to_dict_keys(self):
        d = self.result.to_dict()
        for k in ("koppen_code", "koppen_label", "martonne_index",
                  "martonne_label", "dry_months_gaussen", "dry_months_names",
                  "annual_temperature_c", "annual_precipitation_mm",
                  "notes", "warnings"):
            self.assertIn(k, d)

    def test_to_dict_roundtrip_codes(self):
        d = self.result.to_dict()
        self.assertEqual(d["koppen_code"], "BWh")
        self.assertIsInstance(d["dry_months_gaussen"], list)

    def test_oceanic_cfb_classifies_correctly(self):
        r = classify_climate(_cfb_oceanic())
        self.assertEqual(r.koppen_code, "Cfb")
        # P muy alta → Martonne húmedo
        self.assertGreater(r.martonne_index, 30.0)

    def test_classify_validates_data(self):
        bad = _make_data([15]*11, [50]*12)
        with self.assertRaises(ValueError):
            classify_climate(bad)


# ===========================================================================
# F. parse_monthly_climate_from_aemet_normals
# ===========================================================================

def _aemet_record(mes, tm, pr, **extra):
    return {"mes": str(mes), "tm_mes": str(tm), "pr_mes": str(pr), **extra}


class TestParseAEMETNormals(unittest.TestCase):

    def _make_list(self, include_annual=False):
        temps = [17.8,18.1,18.8,19.4,20.7,22.7,24.9,25.7,25.1,23.5,21.0,18.6]
        precips = [22,19,15,7,2,1,0,1,5,14,21,24]
        records = [
            _aemet_record(m, t, p,
                          indicativo="C029O",
                          nombre="LANZAROTE AEROPUERTO",
                          periodo="1991-2020")
            for m, t, p in zip(range(1, 13), temps, precips)
        ]
        if include_annual:
            records.append({"mes": "Año", "tm_mes": "21.4", "pr_mes": "131"})
        return records

    def test_parse_list_format_12_records(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertEqual(len(data.temperatures_c), 12)
        self.assertEqual(len(data.precipitations_mm), 12)

    def test_parse_list_format_station_id_from_record(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertEqual(data.station_id, "C029O")

    def test_parse_list_format_station_name_from_record(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertEqual(data.station_name, "LANZAROTE AEROPUERTO")

    def test_parse_list_ignores_annual_record(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list(include_annual=True))
        self.assertEqual(len(data.temperatures_c), 12)

    def test_parse_list_station_id_override(self):
        data = parse_monthly_climate_from_aemet_normals(
            self._make_list(), station_id="OVERRIDE"
        )
        self.assertEqual(data.station_id, "OVERRIDE")

    def test_parse_list_station_name_override(self):
        data = parse_monthly_climate_from_aemet_normals(
            self._make_list(), station_name="MI ESTACION"
        )
        self.assertEqual(data.station_name, "MI ESTACION")

    def test_parse_dict_internal_format(self):
        raw = {
            "temperatures_c": [15.0]*12,
            "precipitations_mm": [50.0]*12,
            "period": "1991-2020",
        }
        data = parse_monthly_climate_from_aemet_normals(raw)
        self.assertEqual(data.temperatures_c, [15.0]*12)
        self.assertEqual(data.period, "1991-2020")

    def test_parse_dict_unrecognized_raises(self):
        with self.assertRaises(ValueError):
            parse_monthly_climate_from_aemet_normals({"foo": "bar"})

    def test_parse_wrong_type_raises(self):
        with self.assertRaises(ValueError):
            parse_monthly_climate_from_aemet_normals("texto")

    def test_parse_11_records_raises(self):
        records = self._make_list()[:11]
        with self.assertRaises(ValueError):
            parse_monthly_climate_from_aemet_normals(records)

    def test_parse_missing_tm_mes_raises(self):
        records = self._make_list()
        del records[0]["tm_mes"]
        with self.assertRaises(ValueError):
            parse_monthly_climate_from_aemet_normals(records)

    def test_parse_missing_pr_mes_raises(self):
        records = self._make_list()
        del records[0]["pr_mes"]
        with self.assertRaises(ValueError):
            parse_monthly_climate_from_aemet_normals(records)

    def test_parse_source_set_to_aemet(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertIn("AEMET", data.source)

    def test_parse_period_extracted(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertEqual(data.period, "1991-2020")

    def test_parse_temperatures_correct(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertAlmostEqual(data.temperatures_c[0], 17.8)  # enero
        self.assertAlmostEqual(data.temperatures_c[6], 24.9)  # julio

    def test_parse_precipitations_correct(self):
        data = parse_monthly_climate_from_aemet_normals(self._make_list())
        self.assertAlmostEqual(data.precipitations_mm[0], 22.0)  # enero
        self.assertAlmostEqual(data.precipitations_mm[6], 0.0)   # julio


if __name__ == "__main__":
    unittest.main()
