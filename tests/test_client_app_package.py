"""
Tests para client_app_package.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.client_app_package import build_client_app_package


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_file(path: Path, text: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestClientAppPackage(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.exp = self.tmp / "expediente-EIA-TEST"
        self.exp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_minimal_inputs(self):
        _write_json(self.exp / "control_interno" / "phase2_result.json", {
            "object_scope": {
                "titular": "Promotor Test SL",
                "coordenadas_wgs84": ["28.1, -16.1"],
                "referencia_catastral": "1234567FS1613S0001AB",
                "operaciones_incluidas": ["R12"],
                "capacidad": "1200 t/ano",
            }
        })
        _write_file(self.exp / "inputs" / "memoria_tecnica" / "memoria.pdf")
        _write_file(self.exp / "inputs" / "memoria_explotacion" / "explotacion.docx")
        _write_file(self.exp / "inputs" / "imagenes" / "plano.pdf")
        _write_file(self.exp / "documento" / "documento_ambiental_borrador.docx")
        _write_file(self.exp / "documento" / "documento_ambiental_borrador.md")
        _write_file(self.exp / "mapas" / "mapa_localizacion.png")
        _write_file(self.exp / "clima" / "climograma.png")

    def test_preview_does_not_write_app(self):
        self._write_minimal_inputs()

        result = build_client_app_package(self.exp, write_outputs=False)

        self.assertEqual(result.status, "PREVIEW_APP_CLIENTE")
        self.assertFalse((self.exp / "documento" / "cliente_app").exists())
        self.assertFalse(result.administrative_ready)

    def test_write_creates_professional_app_zip(self):
        self._write_minimal_inputs()

        result = build_client_app_package(self.exp, write_outputs=True)
        app_dir = self.exp / "documento" / "cliente_app"
        zip_path = self.exp / "documento" / "eia_agent_cliente_app.zip"

        self.assertEqual(result.status, "APP_CLIENTE_LISTA")
        self.assertTrue((app_dir / "index.html").exists())
        self.assertTrue((app_dir / "nuevo_expediente.html").exists())
        self.assertTrue((app_dir / "INICIAR_APP_WINDOWS.bat").exists())
        self.assertTrue((app_dir / "server" / "eia_client_server.py").exists())
        self.assertTrue((app_dir / "DEPLOY_PROVISIONAL.md").exists())
        self.assertTrue((app_dir / "README_CLIENTE.md").exists())
        self.assertTrue((app_dir / "data" / "app_manifest.json").exists())
        self.assertTrue((app_dir / "data" / "new_project_blueprint.json").exists())
        self.assertTrue((app_dir / "data" / "map_requirements.json").exists())
        self.assertTrue((app_dir / "markdown" / "map_requirements.md").exists())
        self.assertTrue((app_dir / "documentos" / "documento_ambiental.docx").exists())
        self.assertTrue((app_dir / "planos_mapas" / "mapas" / "mapa_localizacion.png").exists())
        self.assertTrue((app_dir / "planos_mapas" / "clima" / "climograma.png").exists())
        self.assertTrue(zip_path.exists())

    def test_manifest_describes_real_app_workflow(self):
        self._write_minimal_inputs()

        build_client_app_package(self.exp, write_outputs=True)
        manifest_path = self.exp / "documento" / "cliente_app" / "data" / "app_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["app_name"], "EIA-Agent Cliente")
        self.assertIn("redaccion_documento_ambiental", manifest["workflow"])
        self.assertIn("mapas_planos", manifest["expected_outputs"])
        self.assertEqual(manifest["new_project_entrypoint"], "nuevo_expediente.html")
        self.assertEqual(manifest["portable_runtime"]["windows_launcher"], "INICIAR_APP_WINDOWS.bat")
        self.assertEqual(manifest["portable_runtime"]["local_url"], "http://127.0.0.1:8765/")
        self.assertEqual(manifest["deploy_entrypoint"], "DEPLOY_PROVISIONAL.md")
        self.assertGreaterEqual(len(manifest["map_requirements"]), 12)
        self.assertTrue(any(item["title"] == "Ruido y receptores acusticos" for item in manifest["map_requirements"]))
        self.assertFalse(manifest["administrative_ready"])

    def test_zip_contains_app_and_document_entrypoints(self):
        self._write_minimal_inputs()

        build_client_app_package(self.exp, write_outputs=True)
        zip_path = self.exp / "documento" / "eia_agent_cliente_app.zip"

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())

        self.assertIn("index.html", names)
        self.assertIn("nuevo_expediente.html", names)
        self.assertIn("INICIAR_APP_WINDOWS.bat", names)
        self.assertIn("server/eia_client_server.py", names)
        self.assertIn("DEPLOY_PROVISIONAL.md", names)
        self.assertIn("README_CLIENTE.md", names)
        self.assertIn("data/app_manifest.json", names)
        self.assertIn("data/new_project_blueprint.json", names)
        self.assertIn("data/map_requirements.json", names)
        self.assertIn("documentos/documento_ambiental.docx", names)
        self.assertIn("planos_mapas/clima/climograma.png", names)

    def test_portable_runtime_files_are_client_ready(self):
        self._write_minimal_inputs()

        build_client_app_package(self.exp, write_outputs=True)
        app_dir = self.exp / "documento" / "cliente_app"
        launcher = (app_dir / "INICIAR_APP_WINDOWS.bat").read_text(encoding="utf-8")
        server = (app_dir / "server" / "eia_client_server.py").read_text(encoding="utf-8")
        deploy = (app_dir / "DEPLOY_PROVISIONAL.md").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8765/", launcher)
        self.assertIn("Mantenga esta ventana abierta", launcher)
        self.assertIn("codex-runtimes", launcher)
        self.assertIn("server\\eia_client_server.py", launcher)
        self.assertIn("/api/projects", server)
        self.assertIn("expedientes_cliente", server)
        self.assertIn("Uso en el ordenador del cliente", deploy)
        self.assertIn("administrative_ready: false", deploy)

    def test_new_project_app_supports_real_intake_workflow(self):
        self._write_minimal_inputs()

        build_client_app_package(self.exp, write_outputs=True)
        html = (self.exp / "documento" / "cliente_app" / "nuevo_expediente.html").read_text(encoding="utf-8")
        blueprint = json.loads(
            (self.exp / "documento" / "cliente_app" / "data" / "new_project_blueprint.json").read_text(encoding="utf-8")
        )

        self.assertIn("Nuevo expediente ambiental", html)
        self.assertIn("Guardar borrador local", html)
        self.assertIn("Guardar expediente y subir archivos", html)
        self.assertIn("Generar Documento Ambiental", html)
        self.assertIn("Clave de acceso", html)
        self.assertIn("X-EIA-Key", html)
        self.assertIn("/api/health", html)
        self.assertIn("/api/projects", html)
        self.assertIn("Validar documentacion", html)
        self.assertIn("Que falta ahora", html)
        self.assertIn("Escriba el nombre del proyecto", html)
        self.assertIn("Suba ${uploadLabel(id).toLowerCase()}", html)
        self.assertIn("localStorage", html)
        self.assertIn("ready_for_engine", html)
        self.assertIn("Generar Documento Ambiental", html)
        self.assertIn("alta_proyecto", blueprint["workflow"][0]["step"])
        self.assertIn("coordinates_wgs84", blueprint["minimum_project_fields"])
        self.assertGreaterEqual(len(blueprint["map_requirements"]), 12)

    def test_zip_excludes_internal_scripts(self):
        self._write_minimal_inputs()
        _write_file(self.exp / "mapas" / "generar_mapas.py", "print('interno')")

        build_client_app_package(self.exp, write_outputs=True)
        zip_path = self.exp / "documento" / "eia_agent_cliente_app.zip"

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())

        self.assertNotIn("planos_mapas/mapas/generar_mapas.py", names)

    def test_generates_climogram_from_description_when_png_missing(self):
        self._write_minimal_inputs()
        (self.exp / "clima" / "climograma.png").unlink()
        _write_file(self.exp / "clima" / "descripcion_clima.md", """\
| Mes | T media (degC) | T max media (degC) | T min media (degC) | P (mm) |
|-----|---------------|-------------------|-------------------|--------|
| Enero | 17.4 | 20.7 | 14.0 | 16 |
| Febrero | 17.9 | 21.3 | 14.3 | 18 |
| Marzo | 19.0 | 22.9 | 15.0 | 12 |
| Abril | 19.6 | 23.5 | 15.7 | 5 |
| Mayo | 20.8 | 24.6 | 16.8 | 2 |
| Junio | 22.6 | 26.3 | 18.8 | 0 |
| Julio | 24.3 | 28.2 | 20.4 | 0 |
| Agosto | 25.2 | 29.1 | 21.2 | 0 |
| Septiembre | 24.7 | 28.6 | 20.8 | 2 |
| Octubre | 23.0 | 26.7 | 19.4 | 10 |
| Noviembre | 20.7 | 24.2 | 17.2 | 15 |
| Diciembre | 18.6 | 21.8 | 15.4 | 29 |
""")

        build_client_app_package(self.exp, write_outputs=True)

        self.assertTrue((self.exp / "clima" / "climograma.png").exists())
        self.assertGreater((self.exp / "clima" / "climograma.png").stat().st_size, 1000)

    def test_final_revisable_uses_newer_figures_docx(self):
        self._write_minimal_inputs()
        final = self.exp / "documento" / "documento_ambiental_final_revisable.docx"
        figures = self.exp / "documento" / "documento_ambiental_borrador_con_figuras.docx"
        _write_file(final, "version antigua")
        time.sleep(0.01)
        _write_file(figures, "version con figuras nueva")
        now = time.time()
        os.utime(figures, (now, now))

        build_client_app_package(self.exp, write_outputs=True)

        packaged = self.exp / "documento" / "cliente_app" / "documentos" / "documento_ambiental_final_revisable.docx"
        self.assertEqual(packaged.read_text(encoding="utf-8"), "version con figuras nueva")


if __name__ == "__main__":
    unittest.main()
