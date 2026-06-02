"""
Tests para client_portal_site.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_portal import build_client_portal
from eia_agent.core.client_portal_site import (
    build_client_portal_html,
    write_client_portal_site,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientPortalSite(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_minimal_portal_inputs(self):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor <Test> SL",
                "coordenadas_wgs84": ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")

    def test_build_html_contains_client_sections(self):
        self._write_minimal_portal_inputs()
        portal = build_client_portal(self.exp)

        html = build_client_portal_html(portal)

        self.assertIn("<!doctype html>", html)
        self.assertIn("Portal cliente", html)
        self.assertIn("Entrada cliente", html)
        self.assertIn("Siguientes pasos", html)
        self.assertIn("Artefactos", html)
        self.assertIn("administrative_ready: false", html)

    def test_build_html_escapes_text(self):
        self._write_minimal_portal_inputs()
        portal = build_client_portal(self.exp)
        portal.headline = "Texto <script>alert(1)</script>"

        html = build_client_portal_html(portal)

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_write_site_creates_index_html(self):
        self._write_minimal_portal_inputs()
        portal = build_client_portal(self.exp)

        html_path = write_client_portal_site(self.exp, portal)

        self.assertTrue(html_path.exists())
        self.assertEqual(html_path.name, "index.html")
        self.assertIn("Portal cliente", html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
