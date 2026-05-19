"""
Tests CA-09 — geospatial_utils.py

Grupos:
  A. validate_lat_lon
  B. GeoPoint
  C. BoundingBox
  D. parse_wgs84_coordinate
  E. haversine_distance_km
  F. bounding_box_around_point
  G. build_map_extent / MapExtent
  H. extract_geopoint_from_phase2 / build_standard_map_extents
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.geospatial_utils import (
    BoundingBox,
    GeoPoint,
    MapExtent,
    bounding_box_around_point,
    build_map_extent,
    build_standard_map_extents,
    extract_geopoint_from_phase2,
    haversine_distance_km,
    parse_wgs84_coordinate,
    validate_lat_lon,
)


# ---------------------------------------------------------------------------
# A. validate_lat_lon
# ---------------------------------------------------------------------------

class TestValidateLatLon(unittest.TestCase):

    def test_valid_canary_point(self):
        validate_lat_lon(28.9773, -13.5395)  # debe no lanzar

    def test_valid_extremes(self):
        validate_lat_lon(-90.0, -180.0)
        validate_lat_lon(90.0, 180.0)

    def test_lat_too_high(self):
        with self.assertRaises(ValueError):
            validate_lat_lon(90.0001, 0.0)

    def test_lat_too_low(self):
        with self.assertRaises(ValueError):
            validate_lat_lon(-90.0001, 0.0)

    def test_lon_too_high(self):
        with self.assertRaises(ValueError):
            validate_lat_lon(0.0, 180.0001)

    def test_lon_too_low(self):
        with self.assertRaises(ValueError):
            validate_lat_lon(0.0, -180.0001)

    def test_error_message_contains_value(self):
        with self.assertRaises(ValueError) as ctx:
            validate_lat_lon(91.0, 0.0)
        self.assertIn("91.0", str(ctx.exception))


# ---------------------------------------------------------------------------
# B. GeoPoint
# ---------------------------------------------------------------------------

class TestGeoPoint(unittest.TestCase):

    def test_defaults(self):
        p = GeoPoint(lat=28.9, lon=-13.5)
        self.assertEqual(p.status, "DECLARADO")
        self.assertIsNone(p.source)
        self.assertEqual(p.notes, [])

    def test_validate_ok(self):
        GeoPoint(lat=28.9, lon=-13.5, status="VERIFICADO").validate()

    def test_validate_invalid_status(self):
        with self.assertRaises(ValueError):
            GeoPoint(lat=28.9, lon=-13.5, status="INVENTADO").validate()

    def test_validate_invalid_coords(self):
        with self.assertRaises(ValueError):
            GeoPoint(lat=200.0, lon=0.0).validate()

    def test_to_dict(self):
        p = GeoPoint(lat=28.9, lon=-13.5, source="test", status="ESTIMADO", notes=["n"])
        d = p.to_dict()
        self.assertEqual(d["lat"], 28.9)
        self.assertEqual(d["lon"], -13.5)
        self.assertEqual(d["source"], "test")
        self.assertEqual(d["status"], "ESTIMADO")
        self.assertEqual(d["notes"], ["n"])

    def test_from_dict_roundtrip(self):
        p = GeoPoint(lat=28.9, lon=-13.5, source="s", status="PROVISIONAL", notes=["x"])
        p2 = GeoPoint.from_dict(p.to_dict())
        self.assertEqual(p.lat, p2.lat)
        self.assertEqual(p.lon, p2.lon)
        self.assertEqual(p.source, p2.source)
        self.assertEqual(p.status, p2.status)
        self.assertEqual(p.notes, p2.notes)

    def test_from_dict_defaults(self):
        p = GeoPoint.from_dict({"lat": "28.9", "lon": "-13.5"})
        self.assertEqual(p.lat, 28.9)
        self.assertEqual(p.status, "DECLARADO")
        self.assertIsNone(p.source)

    def test_as_tuple(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        self.assertEqual(p.as_tuple(), (28.9773, -13.5395))

    def test_all_valid_statuses(self):
        statuses = ["DECLARADO", "ESTIMADO", "VERIFICADO", "PROVISIONAL", "NO_DECLARADO"]
        for s in statuses:
            GeoPoint(lat=28.0, lon=-13.0, status=s).validate()

    def test_notes_isolation(self):
        notes = ["original"]
        p = GeoPoint(lat=28.0, lon=-13.0, notes=notes)
        p.to_dict()["notes"].append("extra")
        self.assertEqual(p.notes, ["original"])


# ---------------------------------------------------------------------------
# C. BoundingBox
# ---------------------------------------------------------------------------

class TestBoundingBox(unittest.TestCase):

    def test_valid_bbox(self):
        bb = BoundingBox(min_lat=28.0, min_lon=-14.0, max_lat=29.0, max_lon=-13.0)
        bb.validate()

    def test_min_lat_equals_max_lat_raises(self):
        with self.assertRaises(ValueError):
            BoundingBox(28.0, -14.0, 28.0, -13.0).validate()

    def test_min_lat_greater_max_lat_raises(self):
        with self.assertRaises(ValueError):
            BoundingBox(29.0, -14.0, 28.0, -13.0).validate()

    def test_min_lon_equals_max_lon_raises(self):
        with self.assertRaises(ValueError):
            BoundingBox(28.0, -13.0, 29.0, -13.0).validate()

    def test_lat_out_of_range(self):
        with self.assertRaises(ValueError):
            BoundingBox(-91.0, -14.0, 29.0, -13.0).validate()

    def test_lon_out_of_range(self):
        with self.assertRaises(ValueError):
            BoundingBox(28.0, -181.0, 29.0, -13.0).validate()

    def test_to_dict(self):
        bb = BoundingBox(1.0, 2.0, 3.0, 4.0)
        d = bb.to_dict()
        self.assertEqual(d, {"min_lat": 1.0, "min_lon": 2.0, "max_lat": 3.0, "max_lon": 4.0})

    def test_width_degrees(self):
        bb = BoundingBox(28.0, -14.0, 29.0, -13.0)
        self.assertAlmostEqual(bb.width_degrees(), 1.0)

    def test_height_degrees(self):
        bb = BoundingBox(28.0, -14.0, 29.5, -13.0)
        self.assertAlmostEqual(bb.height_degrees(), 1.5)


# ---------------------------------------------------------------------------
# D. parse_wgs84_coordinate
# ---------------------------------------------------------------------------

class TestParseWgs84Coordinate(unittest.TestCase):

    def test_string_comma(self):
        p = parse_wgs84_coordinate("28.9773, -13.5395")
        self.assertAlmostEqual(p.lat, 28.9773)
        self.assertAlmostEqual(p.lon, -13.5395)

    def test_string_space(self):
        p = parse_wgs84_coordinate("28.9773 -13.5395")
        self.assertAlmostEqual(p.lat, 28.9773)
        self.assertAlmostEqual(p.lon, -13.5395)

    def test_string_extra_spaces(self):
        p = parse_wgs84_coordinate("  28.9773,  -13.5395  ")
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_list_strings(self):
        p = parse_wgs84_coordinate(["28.9773", "-13.5395"])
        self.assertAlmostEqual(p.lat, 28.9773)
        self.assertAlmostEqual(p.lon, -13.5395)

    def test_list_floats(self):
        p = parse_wgs84_coordinate([28.9773, -13.5395])
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_dict_lat_lon(self):
        p = parse_wgs84_coordinate({"lat": 28.9773, "lon": -13.5395})
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_dict_latitude_longitude(self):
        p = parse_wgs84_coordinate({"latitude": 28.9773, "longitude": -13.5395})
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_dict_latitud_longitud(self):
        p = parse_wgs84_coordinate({"latitud": 28.9773, "longitud": -13.5395})
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_dict_string_values(self):
        p = parse_wgs84_coordinate({"lat": "28.9773", "lon": "-13.5395"})
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_tuple_input(self):
        p = parse_wgs84_coordinate((28.9773, -13.5395))
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_invalid_string_raises(self):
        with self.assertRaises(ValueError):
            parse_wgs84_coordinate("not_a_coordinate")

    def test_dict_missing_keys_raises(self):
        with self.assertRaises(ValueError):
            parse_wgs84_coordinate({"x": 1.0, "y": 2.0})

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            parse_wgs84_coordinate("200.0, 0.0")

    def test_list_too_short_raises(self):
        with self.assertRaises(ValueError):
            parse_wgs84_coordinate(["28.9773"])

    def test_unsupported_type_raises(self):
        with self.assertRaises(ValueError):
            parse_wgs84_coordinate(12345)

    def test_returns_geopoint(self):
        p = parse_wgs84_coordinate("28.9773, -13.5395")
        self.assertIsInstance(p, GeoPoint)


# ---------------------------------------------------------------------------
# E. haversine_distance_km
# ---------------------------------------------------------------------------

class TestHaversineDistanceKm(unittest.TestCase):

    def test_same_point_is_zero(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        self.assertAlmostEqual(haversine_distance_km(p, p), 0.0, places=6)

    def test_lanzarote_to_gran_canaria_approx(self):
        lanzarote = GeoPoint(lat=28.9583, lon=-13.6052)
        gran_canaria = GeoPoint(lat=27.9333, lon=-15.3833)
        dist = haversine_distance_km(lanzarote, gran_canaria)
        # Distancia real aprox 200 km
        self.assertGreater(dist, 150.0)
        self.assertLess(dist, 250.0)

    def test_symmetry(self):
        a = GeoPoint(lat=28.0, lon=-14.0)
        b = GeoPoint(lat=29.0, lon=-13.0)
        self.assertAlmostEqual(haversine_distance_km(a, b), haversine_distance_km(b, a), places=6)

    def test_one_degree_lat_approx_111km(self):
        a = GeoPoint(lat=0.0, lon=0.0)
        b = GeoPoint(lat=1.0, lon=0.0)
        dist = haversine_distance_km(a, b)
        self.assertAlmostEqual(dist, 111.195, delta=0.5)

    def test_result_is_float(self):
        a = GeoPoint(lat=28.0, lon=-14.0)
        b = GeoPoint(lat=28.1, lon=-14.1)
        self.assertIsInstance(haversine_distance_km(a, b), float)


# ---------------------------------------------------------------------------
# F. bounding_box_around_point
# ---------------------------------------------------------------------------

class TestBoundingBoxAroundPoint(unittest.TestCase):

    def test_returns_bounding_box(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        bb = bounding_box_around_point(p, 1000.0)
        self.assertIsInstance(bb, BoundingBox)

    def test_center_inside_bbox(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        bb = bounding_box_around_point(p, 1000.0)
        self.assertGreater(p.lat, bb.min_lat)
        self.assertLess(p.lat, bb.max_lat)
        self.assertGreater(p.lon, bb.min_lon)
        self.assertLess(p.lon, bb.max_lon)

    def test_1000m_radius_approx(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        bb = bounding_box_around_point(p, 1000.0)
        lat_half = (bb.max_lat - bb.min_lat) / 2.0
        lat_m = lat_half * 111_320.0
        self.assertAlmostEqual(lat_m, 1000.0, delta=10.0)

    def test_larger_radius_bigger_bbox(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        bb500 = bounding_box_around_point(p, 500.0)
        bb2000 = bounding_box_around_point(p, 2000.0)
        self.assertGreater(bb2000.width_degrees(), bb500.width_degrees())
        self.assertGreater(bb2000.height_degrees(), bb500.height_degrees())

    def test_zero_radius_raises(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        with self.assertRaises(ValueError):
            bounding_box_around_point(p, 0.0)

    def test_negative_radius_raises(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        with self.assertRaises(ValueError):
            bounding_box_around_point(p, -500.0)

    def test_bbox_is_valid(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        bb = bounding_box_around_point(p, 25000.0)
        bb.validate()

    def test_near_equator(self):
        p = GeoPoint(lat=0.0, lon=0.0)
        bb = bounding_box_around_point(p, 1000.0)
        bb.validate()
        self.assertGreater(bb.max_lat, 0.0)


# ---------------------------------------------------------------------------
# G. build_map_extent / MapExtent
# ---------------------------------------------------------------------------

class TestBuildMapExtent(unittest.TestCase):

    def test_returns_map_extent(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertIsInstance(ext, MapExtent)

    def test_scale_hint_auto_detalle(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 250.0)
        self.assertEqual(ext.scale_hint, "detalle_parcela")

    def test_scale_hint_auto_emplazamiento(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertEqual(ext.scale_hint, "emplazamiento")

    def test_scale_hint_auto_entorno(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 5000.0)
        self.assertEqual(ext.scale_hint, "entorno")

    def test_scale_hint_auto_situacion_general(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 25000.0)
        self.assertEqual(ext.scale_hint, "situacion_general")

    def test_scale_hint_override(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 250.0, scale_hint="personalizado")
        self.assertEqual(ext.scale_hint, "personalizado")

    def test_warning_for_estimado(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="ESTIMADO")
        ext = build_map_extent(p, 1000.0)
        self.assertTrue(len(ext.warnings) > 0)
        self.assertIn("ESTIMADO", ext.warnings[0])

    def test_warning_for_provisional(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="PROVISIONAL")
        ext = build_map_extent(p, 1000.0)
        self.assertTrue(len(ext.warnings) > 0)

    def test_warning_for_no_declarado(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="NO_DECLARADO")
        ext = build_map_extent(p, 1000.0)
        self.assertTrue(len(ext.warnings) > 0)

    def test_no_warning_for_declarado(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="DECLARADO")
        ext = build_map_extent(p, 1000.0)
        self.assertEqual(ext.warnings, [])

    def test_no_warning_for_verificado(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="VERIFICADO")
        ext = build_map_extent(p, 1000.0)
        self.assertEqual(ext.warnings, [])

    def test_to_dict_keys(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        d = ext.to_dict()
        self.assertIn("center", d)
        self.assertIn("bbox", d)
        self.assertIn("radius_m", d)
        self.assertIn("scale_hint", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_summary_contains_coords(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        summary = ext.summary()
        self.assertIn("28.97730", summary)
        self.assertIn("-13.53950", summary)

    def test_summary_contains_radius(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertIn("1000", ext.summary())

    def test_summary_contains_scale_hint(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertIn("emplazamiento", ext.summary())

    def test_summary_contains_warning(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395, status="ESTIMADO")
        ext = build_map_extent(p, 1000.0)
        self.assertIn("AVISO", ext.summary())

    def test_radius_stored_in_extent(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 2000.0)
        self.assertEqual(ext.radius_m, 2000.0)

    def test_center_is_geopoint(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertIsInstance(ext.center, GeoPoint)

    def test_bbox_is_bounding_box(self):
        p = GeoPoint(lat=28.9773, lon=-13.5395)
        ext = build_map_extent(p, 1000.0)
        self.assertIsInstance(ext.bbox, BoundingBox)


# ---------------------------------------------------------------------------
# H. extract_geopoint_from_phase2 / build_standard_map_extents
# ---------------------------------------------------------------------------

class TestExtractGeopointFromPhase2(unittest.TestCase):

    def _make_phase2(self, coords):
        return {"object_scope": {"coordenadas_wgs84": coords}}

    def test_string_comma_format(self):
        data = self._make_phase2(["28.9773, -13.5395"])
        p = extract_geopoint_from_phase2(data)
        self.assertAlmostEqual(p.lat, 28.9773)
        self.assertAlmostEqual(p.lon, -13.5395)

    def test_two_strings_format(self):
        data = self._make_phase2(["28.9773", "-13.5395"])
        p = extract_geopoint_from_phase2(data)
        self.assertAlmostEqual(p.lat, 28.9773)
        self.assertAlmostEqual(p.lon, -13.5395)

    def test_dict_format(self):
        data = self._make_phase2([{"lat": 28.9773, "lon": -13.5395}])
        p = extract_geopoint_from_phase2(data)
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_list_floats_format(self):
        data = self._make_phase2([28.9773, -13.5395])
        p = extract_geopoint_from_phase2(data)
        self.assertAlmostEqual(p.lat, 28.9773)

    def test_source_is_phase2_result(self):
        data = self._make_phase2(["28.9773, -13.5395"])
        p = extract_geopoint_from_phase2(data)
        self.assertEqual(p.source, "phase2_result")

    def test_no_coords_raises(self):
        with self.assertRaises(ValueError):
            extract_geopoint_from_phase2({"object_scope": {"coordenadas_wgs84": []}})

    def test_missing_object_scope_raises(self):
        with self.assertRaises(ValueError):
            extract_geopoint_from_phase2({})

    def test_none_coords_raises(self):
        with self.assertRaises(ValueError):
            extract_geopoint_from_phase2({"object_scope": {"coordenadas_wgs84": None}})

    def test_unparseable_raises(self):
        with self.assertRaises(ValueError):
            extract_geopoint_from_phase2({"object_scope": {"coordenadas_wgs84": ["no_coord"]}})

    def test_uses_first_coord_of_multiple(self):
        data = self._make_phase2(["28.9773, -13.5395", "27.0, -15.0"])
        p = extract_geopoint_from_phase2(data)
        self.assertAlmostEqual(p.lat, 28.9773)


class TestBuildStandardMapExtents(unittest.TestCase):

    def setUp(self):
        self.point = GeoPoint(lat=28.9773, lon=-13.5395)
        self.extents = build_standard_map_extents(self.point)

    def test_returns_dict(self):
        self.assertIsInstance(self.extents, dict)

    def test_five_extents(self):
        self.assertEqual(len(self.extents), 5)

    def test_expected_keys(self):
        expected = {"detalle_parcela", "emplazamiento", "entorno_500m", "entorno_2000m", "situacion_general"}
        self.assertEqual(set(self.extents.keys()), expected)

    def test_detalle_parcela_radius(self):
        self.assertEqual(self.extents["detalle_parcela"].radius_m, 250.0)

    def test_emplazamiento_radius(self):
        self.assertEqual(self.extents["emplazamiento"].radius_m, 1000.0)

    def test_entorno_500m_radius(self):
        self.assertEqual(self.extents["entorno_500m"].radius_m, 500.0)

    def test_entorno_2000m_radius(self):
        self.assertEqual(self.extents["entorno_2000m"].radius_m, 2000.0)

    def test_situacion_general_radius(self):
        self.assertEqual(self.extents["situacion_general"].radius_m, 25000.0)

    def test_all_extents_are_map_extent(self):
        for name, ext in self.extents.items():
            self.assertIsInstance(ext, MapExtent, msg=f"{name} no es MapExtent")

    def test_all_bboxes_valid(self):
        for name, ext in self.extents.items():
            ext.bbox.validate()

    def test_situacion_general_bigger_than_detalle(self):
        gen = self.extents["situacion_general"]
        det = self.extents["detalle_parcela"]
        self.assertGreater(gen.bbox.width_degrees(), det.bbox.width_degrees())

    def test_all_centers_same_point(self):
        for ext in self.extents.values():
            self.assertAlmostEqual(ext.center.lat, self.point.lat)
            self.assertAlmostEqual(ext.center.lon, self.point.lon)


if __name__ == "__main__":
    unittest.main()
