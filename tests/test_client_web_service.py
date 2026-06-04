"""
Tests para el servicio web desplegable.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_web_service import build_deploy_static_site


class TestClientWebService(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_deploy_static_site_creates_public_frontend(self):
        static_dir = build_deploy_static_site(self.tmp / "web")

        html = (static_dir / "index.html").read_text(encoding="utf-8")
        self.assertTrue((static_dir / "nuevo_expediente.html").exists())
        self.assertTrue((static_dir / "data" / "new_project_blueprint.json").exists())
        self.assertIn("Nuevo expediente ambiental", html)
        self.assertIn("Crear expediente en backend", html)
        self.assertIn("Clave de acceso", html)
        self.assertIn("/api/projects", html)

    def test_repository_has_reproducible_cloud_deploy_files(self):
        root = Path(__file__).parent.parent

        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        render_yaml = (root / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("eia_agent.core.client_web_service", dockerfile)
        self.assertIn("EXPOSE 10000", dockerfile)
        self.assertIn("healthCheckPath: /api/health", render_yaml)
        self.assertIn("plan: free", render_yaml)
        self.assertNotIn("mountPath:", render_yaml)
        self.assertIn("EIA_ACCESS_TOKEN", render_yaml)


if __name__ == "__main__":
    unittest.main()
