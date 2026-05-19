"""
tests/test_climate_station_selector.py -- CL-02
Tests para climate_station_selector.py.

No llama a AEMET ni a ningún servicio externo.
No genera climogramas. No calcula Köppen.
No modifica expedientes piloto.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.climate_station_selector import (
    ClimateStation,
    StationSelection,
    haversine_km,
    parse_dms_aemet,
    parse_station_from_aemet_dict,
    find_nearest_station,
    load_stations_from_json,
    select_station_for_object_scope,
    _parse_coord_value,
    _parse_wgs84_pair,
)


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------

def _station(station_id, name, lat, lon, has_normals=True, **kwargs) -> ClimateStation:
    return ClimateStation(
        station_id=station_id, name=name,
        latitude=lat, longitude=lon, has_normals=has_normals, **kwargs,
    )


def _scope_mock(wgs84_list):
    """Mock de ObjectScope con coordenadas_wgs84."""
    scope = MagicMock()
    scope.coordenadas_wgs84 = wgs84_list
    return scope


# ---------------------------------------------------------------------------
# TestHaversine
# ---------------------------------------------------------------------------

class TestHaversine(unittest.TestCase):
    def test_same_coordinates_returns_zero(self):
        self.assertAlmostEqual(haversine_km(28.0, -15.0, 28.0, -15.0), 0.0, places=6)

    def test_result_is_positive(self):
        dist = haversine_km(28.0, -15.0, 29.0, -16.0)
        self.assertGreater(dist, 0.0)

    def test_one_degree_latitude_approx_111km(self):
        dist = haversine_km(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(dist, 111.19, delta=0.5)

    def test_symmetry(self):
        d1 = haversine_km(28.0, -15.0, 29.0, -14.0)
        d2 = haversine_km(29.0, -14.0, 28.0, -15.0)
        self.assertAlmostEqual(d1, d2, places=8)

    def test_known_canary_distance(self):
        # Las Palmas/Gando (C447A) ≈ 27.927°N 15.386°W
        # Arrecife/Lanzarote (C029O) ≈ 28.944°N 13.603°W
        # Distancia aproximada ≈ 195 km
        dist = haversine_km(27.927, -15.386, 28.944, -13.603)
        self.assertGreater(dist, 180.0)
        self.assertLess(dist, 220.0)


# ---------------------------------------------------------------------------
# TestClimateStationDataclass
# ---------------------------------------------------------------------------

class TestClimateStationDataclass(unittest.TestCase):
    def test_required_fields_stored(self):
        s = ClimateStation(station_id="C447A", name="Las Palmas", latitude=27.93, longitude=-15.39)
        self.assertEqual(s.station_id, "C447A")
        self.assertEqual(s.name, "Las Palmas")
        self.assertAlmostEqual(s.latitude, 27.93)
        self.assertAlmostEqual(s.longitude, -15.39)

    def test_has_normals_default_true(self):
        s = ClimateStation(station_id="X", name="X", latitude=0.0, longitude=0.0)
        self.assertTrue(s.has_normals)

    def test_altitude_default_none(self):
        s = ClimateStation(station_id="X", name="X", latitude=0.0, longitude=0.0)
        self.assertIsNone(s.altitude_m)

    def test_island_default_none(self):
        s = ClimateStation(station_id="X", name="X", latitude=0.0, longitude=0.0)
        self.assertIsNone(s.island)

    def test_source_default_none(self):
        s = ClimateStation(station_id="X", name="X", latitude=0.0, longitude=0.0)
        self.assertIsNone(s.source)

    def test_to_dict_keys(self):
        s = ClimateStation(station_id="C447A", name="LP", latitude=27.93, longitude=-15.39)
        d = s.to_dict()
        for key in ("station_id", "name", "latitude", "longitude",
                    "altitude_m", "province", "island", "has_normals", "source"):
            self.assertIn(key, d)

    def test_from_dict_roundtrip(self):
        original = ClimateStation(
            station_id="C447A", name="Las Palmas", latitude=27.927, longitude=-15.386,
            altitude_m=24.0, province="Las Palmas", island="Gran Canaria",
            has_normals=True, source="AEMET",
        )
        restored = ClimateStation.from_dict(original.to_dict())
        self.assertEqual(restored.station_id, original.station_id)
        self.assertEqual(restored.name, original.name)
        self.assertAlmostEqual(restored.latitude, original.latitude)
        self.assertAlmostEqual(restored.longitude, original.longitude)
        self.assertEqual(restored.altitude_m, original.altitude_m)
        self.assertEqual(restored.province, original.province)
        self.assertEqual(restored.island, original.island)
        self.assertEqual(restored.has_normals, original.has_normals)

    def test_from_dict_optional_fields_default(self):
        d = {"station_id": "X", "name": "X", "latitude": 1.0, "longitude": 2.0}
        s = ClimateStation.from_dict(d)
        self.assertTrue(s.has_normals)
        self.assertIsNone(s.altitude_m)
        self.assertIsNone(s.source)


# ---------------------------------------------------------------------------
# TestParseDMSAEMET
# ---------------------------------------------------------------------------

class TestParseDMSAEMET(unittest.TestCase):
    def test_lat_north(self):
        # 275545N → 27° 55' 45" N = 27.9292°
        result = parse_dms_aemet("275545N")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 27.9292, places=3)

    def test_lat_south(self):
        # 102030S → 10° 20' 30" S = -10.3417°
        result = parse_dms_aemet("102030S")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -10.3417, places=3)

    def test_lon_west(self):
        # 0152241W → 15° 22' 41" W = -15.3781°
        result = parse_dms_aemet("0152241W")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -15.3781, places=3)

    def test_lon_east(self):
        # 0023000E → 2° 30' 00" E = 2.5°
        result = parse_dms_aemet("0023000E")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 2.5, places=3)

    def test_invalid_format_returns_none(self):
        self.assertIsNone(parse_dms_aemet(""))
        self.assertIsNone(parse_dms_aemet("INVALID"))
        self.assertIsNone(parse_dms_aemet("123"))
        self.assertIsNone(parse_dms_aemet("12345X"))  # dirección inválida

    def test_lowercase_accepted(self):
        result = parse_dms_aemet("275545n")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 27.9292, places=3)


# ---------------------------------------------------------------------------
# TestParseCoordValue
# ---------------------------------------------------------------------------

class TestParseCoordValue(unittest.TestCase):
    def test_float_passthrough(self):
        self.assertAlmostEqual(_parse_coord_value(28.5), 28.5)

    def test_int_converted_to_float(self):
        self.assertAlmostEqual(_parse_coord_value(28), 28.0)

    def test_decimal_string(self):
        self.assertAlmostEqual(_parse_coord_value("28.123"), 28.123)

    def test_dms_string(self):
        result = _parse_coord_value("275545N")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 27.9292, places=3)

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_coord_value("not_a_coord"))


# ---------------------------------------------------------------------------
# TestParseStationFromAEMETDict
# ---------------------------------------------------------------------------

class TestParseStationFromAEMETDict(unittest.TestCase):
    def test_standard_english_keys(self):
        d = {"station_id": "C447A", "name": "Las Palmas", "latitude": 27.93, "longitude": -15.39}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.station_id, "C447A")
        self.assertEqual(s.name, "Las Palmas")
        self.assertAlmostEqual(s.latitude, 27.93)
        self.assertAlmostEqual(s.longitude, -15.39)

    def test_standard_spanish_keys(self):
        d = {"indicativo": "C029O", "nombre": "Lanzarote Aeropuerto",
             "latitud": "284838N", "longitud": "0133524W"}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.station_id, "C029O")
        self.assertEqual(s.name, "Lanzarote Aeropuerto")
        self.assertAlmostEqual(s.latitude, 28.8105, places=2)
        self.assertAlmostEqual(s.longitude, -13.5900, places=2)

    def test_id_key(self):
        d = {"id": "X001", "name": "Test", "latitude": 1.0, "longitude": 2.0}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.station_id, "X001")

    def test_decimal_lat_lon_strings(self):
        d = {"indicativo": "X", "latitud": "28.5", "longitud": "-15.3"}
        s = parse_station_from_aemet_dict(d)
        self.assertAlmostEqual(s.latitude, 28.5)
        self.assertAlmostEqual(s.longitude, -15.3)

    def test_altitude_from_altitud_key(self):
        d = {"indicativo": "X", "latitud": 28.0, "longitud": -15.0, "altitud": "24"}
        s = parse_station_from_aemet_dict(d)
        self.assertAlmostEqual(s.altitude_m, 24.0)

    def test_altitude_from_altitude_key(self):
        d = {"station_id": "X", "name": "X", "latitude": 28.0, "longitude": -15.0, "altitude": 100.5}
        s = parse_station_from_aemet_dict(d)
        self.assertAlmostEqual(s.altitude_m, 100.5)

    def test_province_from_provincia_key(self):
        d = {"indicativo": "X", "latitud": 28.0, "longitud": -15.0, "provincia": "Las Palmas"}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.province, "Las Palmas")

    def test_province_from_province_key(self):
        d = {"station_id": "X", "name": "X", "latitude": 28.0, "longitude": -15.0, "province": "Tenerife"}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.province, "Tenerife")

    def test_missing_station_id_raises_value_error(self):
        d = {"name": "X", "latitude": 28.0, "longitude": -15.0}
        with self.assertRaises(ValueError) as ctx:
            parse_station_from_aemet_dict(d)
        self.assertIn("identificador", str(ctx.exception).lower())

    def test_missing_latitude_raises_value_error(self):
        d = {"indicativo": "X", "longitud": -15.0}
        with self.assertRaises(ValueError) as ctx:
            parse_station_from_aemet_dict(d)
        self.assertIn("latitud", str(ctx.exception).lower())

    def test_missing_longitude_raises_value_error(self):
        d = {"indicativo": "X", "latitud": 28.0}
        with self.assertRaises(ValueError) as ctx:
            parse_station_from_aemet_dict(d)
        self.assertIn("longitud", str(ctx.exception).lower())

    def test_name_defaults_to_station_id_if_absent(self):
        d = {"indicativo": "C447A", "latitud": 28.0, "longitud": -15.0}
        s = parse_station_from_aemet_dict(d)
        self.assertEqual(s.name, "C447A")

    def test_dms_latitude_and_longitude_parsed(self):
        d = {"indicativo": "C447A", "nombre": "Las Palmas/Gando",
             "latitud": "275545N", "longitud": "0152241W"}
        s = parse_station_from_aemet_dict(d)
        self.assertAlmostEqual(s.latitude, 27.9292, places=3)
        self.assertAlmostEqual(s.longitude, -15.3781, places=3)


# ---------------------------------------------------------------------------
# TestStationSelectionStructure
# ---------------------------------------------------------------------------

class TestStationSelectionStructure(unittest.TestCase):
    def setUp(self):
        self.station = _station("C447A", "Las Palmas", 27.93, -15.39)
        self.sel = StationSelection(
            selected=self.station,
            distance_km=5.0,
            status="OPTIMA",
            warnings=[],
            notes=["nota de prueba"],
            candidates_considered=3,
        )

    def test_to_dict_keys(self):
        d = self.sel.to_dict()
        for key in ("selected", "distance_km", "status", "warnings", "notes", "candidates_considered"):
            self.assertIn(key, d)

    def test_to_dict_selected_is_dict(self):
        d = self.sel.to_dict()
        self.assertIsInstance(d["selected"], dict)
        self.assertEqual(d["selected"]["station_id"], "C447A")

    def test_summary_contains_station_name(self):
        text = self.sel.summary()
        self.assertIn("Las Palmas", text)

    def test_summary_no_disponible(self):
        sel = StationSelection(
            selected=None, distance_km=None, status="NO_DISPONIBLE",
            warnings=["sin estaciones"], notes=[], candidates_considered=0,
        )
        text = sel.summary()
        self.assertIn("NO_DISPONIBLE", text)

    def test_to_dict_no_disponible(self):
        sel = StationSelection(
            selected=None, distance_km=None, status="NO_DISPONIBLE",
            warnings=[], notes=[], candidates_considered=0,
        )
        d = sel.to_dict()
        self.assertIsNone(d["selected"])
        self.assertEqual(d["status"], "NO_DISPONIBLE")


# ---------------------------------------------------------------------------
# TestFindNearestStation
# ---------------------------------------------------------------------------

class TestFindNearestStation(unittest.TestCase):
    # Proyecto de referencia: 28.0, -15.0
    LAT = 28.0
    LON = -15.0

    def _station_at_offset(self, station_id, dlat=0.0, dlon=0.0, has_normals=True):
        return _station(station_id, f"Estacion {station_id}",
                        self.LAT + dlat, self.LON + dlon, has_normals=has_normals)

    def test_selects_nearest_station(self):
        stations = [
            self._station_at_offset("NEAR", dlat=0.01),   # ~1.1 km
            self._station_at_offset("FAR", dlat=1.0),     # ~111 km
        ]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertEqual(result.selected.station_id, "NEAR")

    def test_ignores_stations_without_normals_when_required(self):
        stations = [
            self._station_at_offset("NO_NORM", dlat=0.01, has_normals=False),  # muy cerca pero sin normales
            self._station_at_offset("WITH_NORM", dlat=0.5, has_normals=True),  # más lejos pero con normales
        ]
        result = find_nearest_station(self.LAT, self.LON, stations, require_normals=True)
        self.assertEqual(result.selected.station_id, "WITH_NORM")

    def test_includes_stations_without_normals_when_not_required(self):
        stations = [
            self._station_at_offset("NO_NORM", dlat=0.01, has_normals=False),
            self._station_at_offset("WITH_NORM", dlat=0.5, has_normals=True),
        ]
        result = find_nearest_station(self.LAT, self.LON, stations, require_normals=False)
        self.assertEqual(result.selected.station_id, "NO_NORM")

    def test_status_OPTIMA_within_15km(self):
        # 0.05° lat ≈ 5.6 km → OPTIMA
        stations = [self._station_at_offset("S1", dlat=0.05)]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertEqual(result.status, "OPTIMA")

    def test_status_ACEPTABLE_between_15_and_25km(self):
        # 0.16° lat ≈ 17.8 km → ACEPTABLE
        stations = [self._station_at_offset("S1", dlat=0.16)]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertEqual(result.status, "ACEPTABLE")

    def test_status_LEJANA_above_25km(self):
        # 0.24° lat ≈ 26.7 km → LEJANA
        stations = [self._station_at_offset("S1", dlat=0.24)]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertEqual(result.status, "LEJANA")

    def test_status_NO_DISPONIBLE_empty_list(self):
        result = find_nearest_station(self.LAT, self.LON, [])
        self.assertEqual(result.status, "NO_DISPONIBLE")
        self.assertIsNone(result.selected)
        self.assertIsNone(result.distance_km)

    def test_warning_when_station_is_lejana(self):
        stations = [self._station_at_offset("S1", dlat=0.24)]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertTrue(any("25" in w or "lejana" in w.lower() or "km" in w for w in result.warnings))

    def test_no_warning_when_OPTIMA(self):
        stations = [self._station_at_offset("S1", dlat=0.05)]
        result = find_nearest_station(self.LAT, self.LON, stations)
        lejana_warnings = [w for w in result.warnings if "25" in w or "lejana" in w.lower()]
        self.assertEqual(lejana_warnings, [])

    def test_warning_when_stations_discarded_for_no_normals(self):
        stations = [self._station_at_offset("NO_NORM", dlat=0.01, has_normals=False)]
        result = find_nearest_station(self.LAT, self.LON, stations, require_normals=True)
        self.assertEqual(result.status, "NO_DISPONIBLE")
        self.assertTrue(any("descartada" in w or "normal" in w.lower() for w in result.warnings))

    def test_warning_when_some_stations_lack_normals(self):
        stations = [
            self._station_at_offset("NO_NORM", dlat=0.01, has_normals=False),
            self._station_at_offset("OK", dlat=0.1, has_normals=True),
        ]
        result = find_nearest_station(self.LAT, self.LON, stations, require_normals=True)
        self.assertTrue(any("descartada" in w for w in result.warnings))

    def test_candidates_considered_count(self):
        stations = [
            self._station_at_offset("A", dlat=0.1),
            self._station_at_offset("B", dlat=0.2),
            self._station_at_offset("C", dlat=0.3),
        ]
        result = find_nearest_station(self.LAT, self.LON, stations)
        self.assertEqual(result.candidates_considered, 3)

    def test_invalid_latitude_raises(self):
        stations = [self._station_at_offset("S1")]
        with self.assertRaises(ValueError):
            find_nearest_station(91.0, self.LON, stations)

    def test_invalid_longitude_raises(self):
        stations = [self._station_at_offset("S1")]
        with self.assertRaises(ValueError):
            find_nearest_station(self.LAT, 181.0, stations)

    def test_lat_minus_90_valid(self):
        stations = [_station("S", "S", 0.0, 0.0)]
        result = find_nearest_station(-90.0, 0.0, stations)
        self.assertNotEqual(result.status, "ERROR")

    def test_lat_plus_90_valid(self):
        stations = [_station("S", "S", 0.0, 0.0)]
        result = find_nearest_station(90.0, 0.0, stations)
        self.assertNotEqual(result.status, "ERROR")


# ---------------------------------------------------------------------------
# TestLoadStationsFromJson
# ---------------------------------------------------------------------------

class TestLoadStationsFromJson(unittest.TestCase):
    def test_loads_valid_json_list(self):
        data = [
            {"station_id": "C447A", "name": "LP", "latitude": 27.93, "longitude": -15.39,
             "has_normals": True},
            {"station_id": "C029O", "name": "Lanzarote", "latitude": 28.94, "longitude": -13.60},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         encoding="utf-8", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            stations = load_stations_from_json(path)
            self.assertEqual(len(stations), 2)
            self.assertEqual(stations[0].station_id, "C447A")
            self.assertEqual(stations[1].station_id, "C029O")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_loads_aemet_format(self):
        data = [{"indicativo": "X001", "nombre": "Test", "latitud": "280000N", "longitud": "0150000W"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         encoding="utf-8", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            stations = load_stations_from_json(path)
            self.assertEqual(stations[0].station_id, "X001")
            self.assertAlmostEqual(stations[0].latitude, 28.0, places=2)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_stations_from_json("/tmp/no_existe_123456.json")

    def test_invalid_json_raises_value_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         encoding="utf-8", delete=False) as f:
            f.write("{ invalid json }")
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_stations_from_json(path)
            self.assertIn("JSON", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_not_a_list_raises_value_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         encoding="utf-8", delete=False) as f:
            json.dump({"indicativo": "X"}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_stations_from_json(path)
            self.assertIn("lista", str(ctx.exception))
        finally:
            Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# TestSelectStationForObjectScope
# ---------------------------------------------------------------------------

class TestSelectStationForObjectScope(unittest.TestCase):
    def setUp(self):
        self.stations = [
            _station("C447A", "Las Palmas", 27.927, -15.386),
            _station("C029O", "Lanzarote Apto", 28.944, -13.603),
        ]

    def test_with_valid_wgs84_returns_selection(self):
        scope = _scope_mock(["27.93, -15.39"])
        result = select_station_for_object_scope(scope, self.stations)
        self.assertNotEqual(result.status, "NO_DISPONIBLE")
        self.assertIsNotNone(result.selected)

    def test_selects_nearest_station(self):
        # Coords near Las Palmas
        scope = _scope_mock(["27.93, -15.39"])
        result = select_station_for_object_scope(scope, self.stations)
        self.assertEqual(result.selected.station_id, "C447A")

    def test_empty_coords_list_returns_no_disponible(self):
        scope = _scope_mock([])
        result = select_station_for_object_scope(scope, self.stations)
        self.assertEqual(result.status, "NO_DISPONIBLE")

    def test_none_coords_returns_no_disponible(self):
        scope = _scope_mock(None)
        result = select_station_for_object_scope(scope, self.stations)
        self.assertEqual(result.status, "NO_DISPONIBLE")

    def test_invalid_wgs84_string_returns_no_disponible(self):
        scope = _scope_mock(["PENDIENTE"])
        result = select_station_for_object_scope(scope, self.stations)
        self.assertEqual(result.status, "NO_DISPONIBLE")

    def test_does_not_modify_object_scope(self):
        original_coords = ["27.93, -15.39"]
        scope = _scope_mock(original_coords[:])  # copia
        _ = select_station_for_object_scope(scope, self.stations)
        # El mock no debe haber sido mutado por el selector
        # (verificamos que no lanzó excepciones y que el estado es coherente)
        self.assertEqual(scope.coordenadas_wgs84, original_coords)

    def test_dict_scope_also_works(self):
        scope_dict = {"coordenadas_wgs84": ["27.93, -15.39"]}
        result = select_station_for_object_scope(scope_dict, self.stations)
        self.assertNotEqual(result.status, "NO_DISPONIBLE")

    def test_uses_first_valid_coordinate(self):
        # Primera coord inválida, segunda válida cerca de Las Palmas
        scope = _scope_mock(["INVALIDA", "27.93, -15.39"])
        result = select_station_for_object_scope(scope, self.stations)
        self.assertEqual(result.selected.station_id, "C447A")


# ---------------------------------------------------------------------------
# TestFixtureLanzarote — sin AEMET real
# ---------------------------------------------------------------------------

class TestFixtureLanzarote(unittest.TestCase):
    """Fixture de estaciones para la isla de Lanzarote.
    Verifica que para un proyecto en Arrecife, la estación del aeropuerto
    (la más cercana) sea seleccionada correctamente.
    """

    def setUp(self):
        # Estaciones ficticias de Lanzarote con coordenadas aproximadas
        self.aeropuerto_lanzarote = _station(
            "C029O", "Lanzarote Aeropuerto",
            lat=28.9447, lon=-13.6058,
            altitude_m=14.0, island="Lanzarote",
        )
        self.arrecife_ciudad = _station(
            "C029B", "Arrecife Ciudad",
            lat=28.9636, lon=-13.5480,  # ~8 km al NE del aeropuerto
            altitude_m=9.0, island="Lanzarote",
        )
        self.fuerteventura_apto = _station(
            "C249I", "Fuerteventura Aeropuerto",
            lat=28.4528, lon=-13.8637,  # isla vecina, >60 km
            island="Fuerteventura",
        )
        self.stations = [
            self.aeropuerto_lanzarote,
            self.arrecife_ciudad,
            self.fuerteventura_apto,
        ]

    def test_project_near_arrecife_selects_nearest(self):
        # Proyecto en Arrecife (cerca del aeropuerto de Lanzarote)
        project_lat, project_lon = 28.9500, -13.6100
        result = find_nearest_station(project_lat, project_lon, self.stations)
        self.assertIsNotNone(result.selected)
        # La más cercana debe ser el aeropuerto o Arrecife ciudad, no Fuerteventura
        self.assertNotEqual(result.selected.station_id, "C249I")

    def test_airport_not_selected_when_project_is_closer_to_arrecife(self):
        # Proyecto en el centro de Arrecife (mucho más cerca de C029B que C029O)
        project_lat, project_lon = 28.9636, -13.5480  # exactamente C029B
        result = find_nearest_station(project_lat, project_lon, self.stations)
        self.assertEqual(result.selected.station_id, "C029B")

    def test_selection_is_optima_or_aceptable_for_local_project(self):
        # Para un proyecto en Lanzarote, la distancia a la estación más cercana
        # debe ser menor de 25 km (OPTIMA o ACEPTABLE)
        project_lat, project_lon = 28.9500, -13.6100
        result = find_nearest_station(project_lat, project_lon, self.stations)
        self.assertIn(result.status, ("OPTIMA", "ACEPTABLE"))

    def test_fuerteventura_project_selects_fuerteventura_station(self):
        project_lat, project_lon = 28.4528, -13.8637  # cerca del aeropuerto de Fuerteventura
        result = find_nearest_station(project_lat, project_lon, self.stations)
        self.assertEqual(result.selected.station_id, "C249I")


# ---------------------------------------------------------------------------
# TestParseWGS84Pair
# ---------------------------------------------------------------------------

class TestParseWGS84Pair(unittest.TestCase):
    def test_valid_pair_parsed(self):
        result = _parse_wgs84_pair("28.5, -15.3")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 28.5)
        self.assertAlmostEqual(result[1], -15.3)

    def test_valid_pair_no_spaces(self):
        result = _parse_wgs84_pair("28.5,-15.3")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 28.5)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_wgs84_pair("PENDIENTE"))
        self.assertIsNone(_parse_wgs84_pair("NO VALIDO"))
        self.assertIsNone(_parse_wgs84_pair(""))


if __name__ == "__main__":
    unittest.main()
