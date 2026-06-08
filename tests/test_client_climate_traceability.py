"""
Tests para client_climate_traceability.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_climate_traceability import (  # noqa: E402
    TRACE_JSON_FILE,
    TRACE_MD_FILE,
    build_client_climate_traceability,
)


class TestClientClimateTraceability(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "control_interno").mkdir(parents=True, exist_ok=True)
        (self.tmp / "control_interno" / "entrada_cliente.json").write_text(
            json.dumps({"project": {"coordinates_wgs84": "28.963, -13.551"}}),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marks_pending_when_coordinates_exist_but_no_climate_data(self):
        result = build_client_climate_traceability(self.tmp, write_outputs=True)

        self.assertEqual(result["status"], "PENDING_AEMET_OR_LOCAL_DATA")
        self.assertEqual(result["evidence_status"], "PENDIENTE")
        self.assertFalse(result["administrative_ready"])
        self.assertTrue((self.tmp / TRACE_JSON_FILE).exists())
        self.assertTrue((self.tmp / TRACE_MD_FILE).exists())

    def test_detects_climogram_without_station_trace(self):
        climate_dir = self.tmp / "clima"
        climate_dir.mkdir(parents=True, exist_ok=True)
        (climate_dir / "climograma.png").write_bytes(b"PNG")

        result = build_client_climate_traceability(self.tmp, write_outputs=True)

        self.assertEqual(result["status"], "CLIMOGRAM_WITHOUT_STATION_TRACE")
        self.assertEqual(result["climogram_paths"], ["clima/climograma.png"])
        self.assertTrue(result["warnings"])

    def test_accepts_climogram_with_selected_station(self):
        climate_dir = self.tmp / "clima"
        climate_dir.mkdir(parents=True, exist_ok=True)
        (climate_dir / "climograma_c029o_1991-2020.png").write_bytes(b"PNG")
        (climate_dir / "phase4_climate_result.json").write_text(
            json.dumps(
                {
                    "selected_station": {
                        "station_id": "C029O",
                        "name": "Lanzarote Aeropuerto",
                    },
                    "station_distance_km": 8.4,
                    "station_selection_status": "OPTIMA",
                    "climogram_path": "clima/climograma_c029o_1991-2020.png",
                }
            ),
            encoding="utf-8",
        )

        result = build_client_climate_traceability(self.tmp, write_outputs=True)

        self.assertEqual(result["status"], "CLIMOGRAM_WITH_STATION")
        self.assertEqual(result["evidence_status"], "INFERIDO")
        self.assertEqual(result["selected_station"]["station_id"], "C029O")
        self.assertFalse(result["administrative_ready"])


if __name__ == "__main__":
    unittest.main()
