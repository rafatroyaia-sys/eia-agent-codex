"""Tests para mapas oficiales cliente."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from eia_agent.core.client_official_maps import (
    build_catastro_wms_url,
    build_ign_topographic_wms_url,
    build_pnoa_ortofoto_wms_url,
    build_red_natura_wms_url,
    build_snczi_q500_wms_url,
    generate_client_official_maps,
    parse_wgs84_coordinates,
)


class TestClientOfficialMaps(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "control_interno").mkdir()
        entry = {"project": {"coordinates_wgs84": "28.963, -13.551"}}
        (self.tmp / "control_interno" / "entrada_cliente.json").write_text(
            json.dumps(entry),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_wgs84_coordinates_accepts_declared_pair(self):
        self.assertEqual(parse_wgs84_coordinates("28.963, -13.551"), (28.963, -13.551))

    def test_parse_wgs84_coordinates_rejects_invalid_values(self):
        self.assertIsNone(parse_wgs84_coordinates("500, -13.551"))

    def test_build_catastro_wms_url_contains_required_parameters(self):
        url = build_catastro_wms_url(28.963, -13.551)

        self.assertIn("SERVICE=WMS", url)
        self.assertIn("REQUEST=GetMap", url)
        self.assertIn("SRS=EPSG%3A4326", url)
        self.assertIn("LAYERS=Catastro", url)

    def test_build_red_natura_wms_url_contains_required_parameters(self):
        url = build_red_natura_wms_url(28.963, -13.551)

        self.assertIn("SERVICE=WMS", url)
        self.assertIn("REQUEST=GetMap", url)
        self.assertIn("SRS=EPSG%3A4326", url)
        self.assertIn("LAYERS=PS.ProtectedSite", url)

    def test_build_pnoa_ortofoto_wms_url_contains_required_parameters(self):
        url = build_pnoa_ortofoto_wms_url(28.963, -13.551)

        self.assertIn("SERVICE=WMS", url)
        self.assertIn("REQUEST=GetMap", url)
        self.assertIn("SRS=EPSG%3A4326", url)
        self.assertIn("LAYERS=OI.OrthoimageCoverage", url)

    def test_build_snczi_q500_wms_url_contains_required_parameters(self):
        url = build_snczi_q500_wms_url(28.963, -13.551)

        self.assertIn("SERVICE=WMS", url)
        self.assertIn("REQUEST=GetMap", url)
        self.assertIn("SRS=EPSG%3A4326", url)
        self.assertIn("LAYERS=NZ.RiskZone", url)

    def test_build_ign_topographic_wms_url_contains_required_parameters(self):
        url = build_ign_topographic_wms_url(28.963, -13.551)

        self.assertIn("SERVICE=WMS", url)
        self.assertIn("REQUEST=GetMap", url)
        self.assertIn("SRS=EPSG%3A4326", url)
        self.assertIn("LAYERS=mtn_rasterizado", url)

    def test_generate_client_official_maps_writes_png_with_fetcher(self):
        png = b"\x89PNG\r\n\x1a\n" + b"OFFICIAL"

        result = generate_client_official_maps(
            self.tmp,
            fetcher=lambda _url: png,
            write_outputs=True,
        )

        self.assertEqual(result["status"], "GENERATED_WITH_REVIEW")
        out = self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-001_catastro_parcela.png"
        red = self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-002_red_natura_2000.png"
        ortho = self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-003_ortofoto_pnoa.png"
        flood = self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-004_inundabilidad_snczi_t500.png"
        topo = self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-005_topografico_ign.png"
        self.assertEqual(out.read_bytes(), png)
        self.assertEqual(red.read_bytes(), png)
        self.assertEqual(ortho.read_bytes(), png)
        self.assertEqual(flood.read_bytes(), png)
        self.assertEqual(topo.read_bytes(), png)
        self.assertEqual(len(result["maps"]), 5)
        self.assertTrue((self.tmp / "cartografia" / "mapas_oficiales_cliente.json").exists())
        self.assertFalse(result["administrative_ready"])

    def test_generate_client_official_maps_skips_without_coordinates(self):
        (self.tmp / "control_interno" / "entrada_cliente.json").write_text(
            json.dumps({"project": {"coordinates_wgs84": "sin dato"}}),
            encoding="utf-8",
        )

        result = generate_client_official_maps(
            self.tmp,
            fetcher=lambda _url: b"not-called",
            write_outputs=True,
        )

        self.assertEqual(result["status"], "SKIPPED")
        self.assertFalse((self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-001_catastro_parcela.png").exists())
        self.assertFalse((self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-002_red_natura_2000.png").exists())
        self.assertFalse((self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-003_ortofoto_pnoa.png").exists())
        self.assertFalse((self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-004_inundabilidad_snczi_t500.png").exists())
        self.assertFalse((self.tmp / "cartografia" / "mapas" / "MAP-OFICIAL-005_topografico_ign.png").exists())


if __name__ == "__main__":
    unittest.main()
