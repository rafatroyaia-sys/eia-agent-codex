"""
tests/test_expediente_initializer.py — BE-03
Tests del inicializador de estructura estandar de expediente EIA-Agent v2.1.

Todos los tests son offline: sin IA, sin web, sin APIs externas.
Se usan directorios temporales; no se modifica ningun expediente piloto.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.expediente_initializer import (
    STANDARD_EXPEDIENTE_DIRS,
    STANDARD_GUIDE_FILES,
    STANDARD_METADATA_FILE,
    STATUS_VALUES,
    ExpedienteInitFile,
    ExpedienteInitResult,
    build_default_metadata,
    build_documento_readme,
    build_estado_expediente_template,
    build_inputs_instructions,
    build_pendientes_promotor_template,
    build_readme_expediente,
    create_standard_dirs,
    initialize_expediente,
    sanitize_expediente_id,
    write_init_result,
    write_standard_guides,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmp_dir():
    """Crea un directorio temporal y devuelve (TemporaryDirectory, Path)."""
    td = tempfile.TemporaryDirectory()
    return td, Path(td.name)


# ---------------------------------------------------------------------------
# 1. sanitize_expediente_id
# ---------------------------------------------------------------------------

class TestSanitizeExpedienteId(unittest.TestCase):

    def test_limpia_espacios(self):
        result = sanitize_expediente_id("Recimetal Nave 222")
        self.assertNotIn(" ", result)
        self.assertIn("RECIMETAL", result)
        self.assertIn("NAVE", result)
        self.assertIn("222", result)

    def test_limpia_barras(self):
        result = sanitize_expediente_id("EIA 2026/Prueba")
        self.assertNotIn("/", result)
        self.assertIn("EIA", result)
        self.assertIn("2026", result)
        self.assertIn("PRUEBA", result)

    def test_limpia_barras_inversas(self):
        result = sanitize_expediente_id("EIA\\Proyecto")
        self.assertNotIn("\\", result)

    def test_conserva_guiones(self):
        result = sanitize_expediente_id("EIA-2026-NAVE-222")
        self.assertEqual(result, "EIA-2026-NAVE-222")

    def test_conserva_guion_bajo(self):
        result = sanitize_expediente_id("EIA_NAVE_222")
        self.assertEqual(result, "EIA_NAVE_222")

    def test_convierte_mayusculas(self):
        result = sanitize_expediente_id("eia-2026-nave")
        self.assertEqual(result, "EIA-2026-NAVE")

    def test_elimina_caracteres_especiales(self):
        result = sanitize_expediente_id("EIA@2026#Nave!")
        self.assertNotIn("@", result)
        self.assertNotIn("#", result)
        self.assertNotIn("!", result)

    def test_no_devuelve_vacio_salvo_input_vacio(self):
        result = sanitize_expediente_id("x")
        self.assertNotEqual(result, "")

    def test_input_vacio_devuelve_vacio(self):
        result = sanitize_expediente_id("")
        self.assertEqual(result, "")

    def test_colapsa_guiones_consecutivos(self):
        result = sanitize_expediente_id("EIA  2026  Nave")
        self.assertNotIn("--", result)

    def test_recimetal_nave_222(self):
        result = sanitize_expediente_id("Recimetal Nave 222")
        self.assertEqual(result, "RECIMETAL-NAVE-222")

    def test_eia_2026_barra_prueba(self):
        result = sanitize_expediente_id("EIA 2026/Prueba")
        self.assertEqual(result, "EIA-2026-PRUEBA")

    def test_solo_numeros(self):
        result = sanitize_expediente_id("123456")
        self.assertEqual(result, "123456")

    def test_solo_letras(self):
        result = sanitize_expediente_id("nave")
        self.assertEqual(result, "NAVE")

    def test_puntos_son_separadores(self):
        result = sanitize_expediente_id("EIA.2026.NAVE")
        self.assertNotIn(".", result)


# ---------------------------------------------------------------------------
# 2. build_default_metadata
# ---------------------------------------------------------------------------

class TestBuildDefaultMetadata(unittest.TestCase):

    def test_contiene_administrative_ready_false(self):
        meta = build_default_metadata("TEST-001")
        self.assertFalse(meta["administrative_ready"])

    def test_contiene_expediente_id(self):
        meta = build_default_metadata("EIA-2026-PRUEBA")
        self.assertEqual(meta["expediente_id"], "EIA-2026-PRUEBA")

    def test_contiene_status_created(self):
        meta = build_default_metadata("TEST-001")
        self.assertEqual(meta["status"], "CREATED")

    def test_contiene_tool(self):
        meta = build_default_metadata("TEST-001")
        self.assertEqual(meta["tool"], "EIA-Agent v2.1")

    def test_contiene_created_at_iso(self):
        meta = build_default_metadata("TEST-001")
        self.assertIn("created_at", meta)
        self.assertRegex(meta["created_at"], r"\d{4}-\d{2}-\d{2}T")

    def test_contiene_notes_con_advertencia(self):
        meta = build_default_metadata("TEST-001")
        notes_text = " ".join(meta["notes"])
        self.assertIn("administrativa", notes_text.lower())

    def test_es_serializable_a_json(self):
        meta = build_default_metadata("TEST-001")
        serialized = json.dumps(meta)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["expediente_id"], "TEST-001")
        self.assertFalse(parsed["administrative_ready"])


# ---------------------------------------------------------------------------
# 3. Builders Markdown
# ---------------------------------------------------------------------------

class TestBuildersMarkdown(unittest.TestCase):

    def test_readme_expediente_contiene_estructura_carpetas(self):
        content = build_readme_expediente("EIA-2026-TEST")
        self.assertIn("inputs/", content)
        self.assertIn("auditoria/", content)
        self.assertIn("impactos/", content)

    def test_readme_expediente_contiene_advertencia_administrativa(self):
        content = build_readme_expediente("EIA-2026-TEST")
        self.assertIn("administrativa", content.lower())

    def test_readme_expediente_contiene_id(self):
        content = build_readme_expediente("EIA-2026-NAVE-222")
        self.assertIn("EIA-2026-NAVE-222", content)

    def test_readme_expediente_contiene_memoria_tecnica(self):
        content = build_readme_expediente("EIA-2026-TEST")
        self.assertIn("memoria_tecnica", content)

    def test_inputs_instructions_contiene_memoria_tecnica(self):
        content = build_inputs_instructions()
        self.assertIn("memoria_tecnica", content)

    def test_inputs_instructions_contiene_coordenadas(self):
        content = build_inputs_instructions()
        self.assertIn("Coordenadas", content)

    def test_inputs_instructions_contiene_promotor(self):
        content = build_inputs_instructions()
        self.assertIn("Promotor", content)

    def test_inputs_instructions_contiene_residuos(self):
        content = build_inputs_instructions()
        self.assertIn("Residuos", content)

    def test_estado_expediente_contiene_checklist(self):
        content = build_estado_expediente_template("EIA-TEST")
        self.assertIn("Pendiente", content)

    def test_estado_expediente_contiene_fase1(self):
        content = build_estado_expediente_template("EIA-TEST")
        self.assertIn("Fase 1", content)

    def test_estado_expediente_contiene_id(self):
        content = build_estado_expediente_template("EIA-2026-NAVE")
        self.assertIn("EIA-2026-NAVE", content)

    def test_pendientes_promotor_contiene_tabla(self):
        content = build_pendientes_promotor_template()
        self.assertIn("| Prioridad |", content)
        self.assertIn("Dato pendiente", content)

    def test_pendientes_promotor_contiene_alta(self):
        content = build_pendientes_promotor_template()
        self.assertIn("ALTA", content)

    def test_documento_readme_contiene_docx(self):
        content = build_documento_readme()
        self.assertIn(".docx", content)

    def test_documento_readme_contiene_paquete(self):
        content = build_documento_readme()
        self.assertIn("paquete_entrega", content)

    def test_documento_readme_contiene_administrative_ready(self):
        content = build_documento_readme()
        self.assertIn("administrative_ready", content)


# ---------------------------------------------------------------------------
# 4. create_standard_dirs
# ---------------------------------------------------------------------------

class TestCreateStandardDirs(unittest.TestCase):

    def test_crea_todas_las_carpetas(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-TEST"
            exp_path.mkdir()
            dirs_created, dirs_existing = create_standard_dirs(exp_path)
            for rel_dir in STANDARD_EXPEDIENTE_DIRS:
                self.assertTrue(
                    (exp_path / rel_dir).exists(),
                    f"Carpeta no creada: {rel_dir}"
                )

    def test_segunda_ejecucion_las_marca_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            dirs_created2, dirs_existing2 = create_standard_dirs(exp_path)
            self.assertEqual(len(dirs_created2), 0)
            self.assertEqual(len(dirs_existing2), len(STANDARD_EXPEDIENTE_DIRS))

    def test_no_falla_si_ya_existen(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-TEST"
            exp_path.mkdir()
            for _ in range(3):
                dirs_c, dirs_e = create_standard_dirs(exp_path)
            self.assertEqual(len(dirs_c), 0)

    def test_devuelve_listas_correctas_primera_vez(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-TEST"
            exp_path.mkdir()
            dirs_created, dirs_existing = create_standard_dirs(exp_path)
            self.assertEqual(len(dirs_created), len(STANDARD_EXPEDIENTE_DIRS))
            self.assertEqual(len(dirs_existing), 0)

    def test_crea_subcarpetas_anidadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            self.assertTrue((exp_path / "inputs" / "memoria_tecnica").exists())
            self.assertTrue((exp_path / "cartografia" / "mapas").exists())
            self.assertTrue((exp_path / "documento" / "figuras").exists())


# ---------------------------------------------------------------------------
# 5. write_standard_guides
# ---------------------------------------------------------------------------

class TestWriteStandardGuides(unittest.TestCase):

    def test_crea_archivos_guia(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            files = write_standard_guides(exp_path, "EIA-TEST")
            created = [f for f in files if f.created]
            self.assertGreater(len(created), 0)
            # README_EXPEDIENTE.md debe existir
            self.assertTrue((exp_path / "README_EXPEDIENTE.md").exists())

    def test_no_sobrescribe_si_force_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            # Primera vez: crea
            write_standard_guides(exp_path, "EIA-TEST", force=False)
            # Modificar el README manualmente
            readme = exp_path / "README_EXPEDIENTE.md"
            readme.write_text("CONTENIDO PERSONALIZADO", encoding="utf-8")
            # Segunda vez con force=False: no debe sobrescribir
            write_standard_guides(exp_path, "EIA-TEST", force=False)
            self.assertEqual(readme.read_text(encoding="utf-8"), "CONTENIDO PERSONALIZADO")

    def test_sobrescribe_si_force_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            write_standard_guides(exp_path, "EIA-TEST", force=False)
            readme = exp_path / "README_EXPEDIENTE.md"
            readme.write_text("CONTENIDO PERSONALIZADO", encoding="utf-8")
            write_standard_guides(exp_path, "EIA-TEST", force=True)
            content = readme.read_text(encoding="utf-8")
            self.assertNotEqual(content, "CONTENIDO PERSONALIZADO")

    def test_registra_skipped_correctamente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            write_standard_guides(exp_path, "EIA-TEST", force=False)
            files2 = write_standard_guides(exp_path, "EIA-TEST", force=False)
            skipped = [f for f in files2 if f.skipped]
            self.assertGreater(len(skipped), 0)

    def test_registra_overwritten_correctamente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            write_standard_guides(exp_path, "EIA-TEST", force=False)
            files2 = write_standard_guides(exp_path, "EIA-TEST", force=True)
            overwritten = [f for f in files2 if f.overwritten]
            self.assertGreater(len(overwritten), 0)

    def test_crea_metadata_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            write_standard_guides(exp_path, "EIA-TEST")
            meta_path = exp_path / STANDARD_METADATA_FILE
            self.assertTrue(meta_path.exists())
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertFalse(meta["administrative_ready"])

    def test_file_size_bytes_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            create_standard_dirs(exp_path)
            files = write_standard_guides(exp_path, "EIA-TEST")
            for f in files:
                if f.created:
                    self.assertGreater(f.file_size_bytes, 0)


# ---------------------------------------------------------------------------
# 6. initialize_expediente
# ---------------------------------------------------------------------------

class TestInitializeExpediente(unittest.TestCase):

    def test_crea_raiz_nueva(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "EIA-2026-NUEVO"
            result = initialize_expediente(new_path)
            self.assertTrue(new_path.exists())
            self.assertEqual(result.status, "CREATED")

    def test_crea_estructura_completa(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "EIA-TEST"
            initialize_expediente(new_path)
            for rel_dir in STANDARD_EXPEDIENTE_DIRS:
                self.assertTrue((new_path / rel_dir).exists(), f"Falta: {rel_dir}")

    def test_crea_guias_por_defecto(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(new_path)
            self.assertGreater(result.created_file_count(), 0)
            self.assertTrue((new_path / "README_EXPEDIENTE.md").exists())

    def test_crea_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "EIA-TEST"
            initialize_expediente(new_path)
            meta_path = new_path / STANDARD_METADATA_FILE
            self.assertTrue(meta_path.exists())

    def test_with_guides_false_no_crea_guias(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(new_path, with_guides=False)
            self.assertEqual(result.created_file_count(), 0)
            self.assertEqual(len(result.files), 0)
            # Pero las carpetas si se crean
            self.assertGreater(result.created_dir_count(), 0)

    def test_expediente_id_none_usa_nombre_carpeta(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "eia-2026-prueba"
            result = initialize_expediente(new_path, expediente_id=None)
            self.assertEqual(result.expediente_id, "EIA-2026-PRUEBA")

    def test_expediente_id_explicito_se_usa(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "expediente-qualquiera"
            result = initialize_expediente(new_path, expediente_id="EIA-2026-NAVE-222")
            self.assertEqual(result.expediente_id, "EIA-2026-NAVE-222")

    def test_no_borra_archivos_existentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            exp_path.mkdir()
            custom_file = exp_path / "mi_archivo_personalizado.txt"
            custom_file.write_text("no borrar", encoding="utf-8")
            initialize_expediente(exp_path)
            self.assertTrue(custom_file.exists())
            self.assertEqual(custom_file.read_text(encoding="utf-8"), "no borrar")

    def test_segunda_ejecucion_no_rompe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result1 = initialize_expediente(exp_path)
            result2 = initialize_expediente(exp_path)
            self.assertTrue(result2.is_success())
            self.assertEqual(result2.status, "ALREADY_EXISTS")

    def test_is_success_true_en_ejecucion_correcta(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            self.assertTrue(result.is_success())

    def test_administrative_ready_false_en_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            initialize_expediente(exp_path)
            meta = json.loads((exp_path / STANDARD_METADATA_FILE).read_text(encoding="utf-8"))
            self.assertFalse(meta["administrative_ready"])

    def test_expediente_path_en_resultado(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            self.assertEqual(result.expediente_path, str(exp_path.resolve()))

    def test_to_dict_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            d = result.to_dict()
            serialized = json.dumps(d)
            parsed = json.loads(serialized)
            self.assertEqual(parsed["expediente_id"], result.expediente_id)

    def test_force_sobrescribe_guias(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            initialize_expediente(exp_path)
            readme = exp_path / "README_EXPEDIENTE.md"
            readme.write_text("PERSONALIZADO", encoding="utf-8")
            initialize_expediente(exp_path, force=True)
            self.assertNotEqual(readme.read_text(encoding="utf-8"), "PERSONALIZADO")


# ---------------------------------------------------------------------------
# 7. write_init_result
# ---------------------------------------------------------------------------

class TestWriteInitResult(unittest.TestCase):

    def test_escribe_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            out_path = Path(tmp) / "init_result.json"
            written = write_init_result(result, out_path)
            self.assertTrue(written.exists())
            self.assertTrue(written.stat().st_size > 0)

    def test_json_cargable(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            out_path = Path(tmp) / "init_result.json"
            write_init_result(result, out_path)
            parsed = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("expediente_id", parsed)
            self.assertIn("status", parsed)

    def test_json_contiene_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            out_path = Path(tmp) / "init_result.json"
            write_init_result(result, out_path)
            parsed = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("stats", parsed)
            self.assertIn("dirs_created", parsed["stats"])

    def test_devuelve_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-TEST"
            result = initialize_expediente(exp_path)
            out_path = Path(tmp) / "subdir" / "init_result.json"
            returned = write_init_result(result, out_path)
            self.assertIsInstance(returned, Path)
            self.assertTrue(returned.exists())


# ---------------------------------------------------------------------------
# 8. ExpedienteInitFile y ExpedienteInitResult
# ---------------------------------------------------------------------------

class TestDataclasses(unittest.TestCase):

    def test_init_file_to_dict_campos(self):
        f = ExpedienteInitFile(path="README.md", created=True, file_size_bytes=500)
        d = f.to_dict()
        self.assertEqual(d["path"], "README.md")
        self.assertTrue(d["created"])
        self.assertEqual(d["file_size_bytes"], 500)
        self.assertFalse(d["skipped"])

    def test_init_file_summary_created(self):
        f = ExpedienteInitFile(path="README.md", created=True, file_size_bytes=100)
        self.assertIn("CREATED", f.summary())

    def test_init_file_summary_skipped(self):
        f = ExpedienteInitFile(path="README.md", skipped=True)
        self.assertIn("SKIPPED", f.summary())

    def test_init_file_summary_overwritten(self):
        f = ExpedienteInitFile(path="README.md", overwritten=True, file_size_bytes=200)
        self.assertIn("OVERWRITTEN", f.summary())

    def test_init_result_created_dir_count(self):
        r = ExpedienteInitResult(
            expediente_id="X", expediente_path="/tmp/x", status="CREATED",
            dirs_created=["a", "b", "c"],
        )
        self.assertEqual(r.created_dir_count(), 3)

    def test_init_result_existing_dir_count(self):
        r = ExpedienteInitResult(
            expediente_id="X", expediente_path="/tmp/x", status="ALREADY_EXISTS",
            dirs_existing=["a", "b"],
        )
        self.assertEqual(r.existing_dir_count(), 2)

    def test_init_result_created_file_count(self):
        files = [
            ExpedienteInitFile(path="a.md", created=True),
            ExpedienteInitFile(path="b.md", skipped=True),
            ExpedienteInitFile(path="c.md", overwritten=True),
        ]
        r = ExpedienteInitResult(
            expediente_id="X", expediente_path="/tmp/x", status="CREATED", files=files
        )
        self.assertEqual(r.created_file_count(), 2)

    def test_init_result_skipped_file_count(self):
        files = [
            ExpedienteInitFile(path="a.md", created=True),
            ExpedienteInitFile(path="b.md", skipped=True),
        ]
        r = ExpedienteInitResult(
            expediente_id="X", expediente_path="/tmp/x", status="CREATED", files=files
        )
        self.assertEqual(r.skipped_file_count(), 1)

    def test_init_result_is_success_true(self):
        r = ExpedienteInitResult(expediente_id="X", expediente_path="/tmp/x", status="CREATED")
        self.assertTrue(r.is_success())

    def test_init_result_is_success_false_on_error(self):
        r = ExpedienteInitResult(expediente_id="X", expediente_path="/tmp/x", status="ERROR")
        self.assertFalse(r.is_success())

    def test_init_result_summary_contiene_id(self):
        r = ExpedienteInitResult(
            expediente_id="EIA-TEST", expediente_path="/tmp/x", status="CREATED"
        )
        self.assertIn("EIA-TEST", r.summary())

    def test_init_result_to_dict_tiene_stats(self):
        r = ExpedienteInitResult(
            expediente_id="X", expediente_path="/tmp/x", status="CREATED",
            dirs_created=["a"], dirs_existing=["b"]
        )
        d = r.to_dict()
        self.assertIn("stats", d)
        self.assertEqual(d["stats"]["dirs_created"], 1)
        self.assertEqual(d["stats"]["dirs_existing"], 1)


# ---------------------------------------------------------------------------
# 9. CLI — init-expediente
# ---------------------------------------------------------------------------

class TestCLIInitExpediente(unittest.TestCase):
    """Pruebas de la integracion CLI del comando init-expediente."""

    def _run_cli(self, args: list) -> int:
        """Importa y ejecuta main() de run_expediente.py con los args dados."""
        # Insertar src en path si no esta
        src_path = str(Path(__file__).parent.parent / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        root = str(Path(__file__).parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        import importlib
        import run_expediente
        importlib.reload(run_expediente)
        return run_expediente.main(args)

    def test_init_expediente_crea_estructura(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-CLI-TEST"
            ret = self._run_cli([str(exp_path), "init-expediente"])
            self.assertEqual(ret, 0)
            self.assertTrue(exp_path.exists())
            self.assertTrue((exp_path / "inputs").exists())
            self.assertTrue((exp_path / "auditoria").exists())

    def test_init_expediente_no_guides(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-CLI-TEST"
            ret = self._run_cli([str(exp_path), "init-expediente", "--no-guides"])
            self.assertEqual(ret, 0)
            self.assertTrue((exp_path / "inventario").exists())
            self.assertFalse((exp_path / "README_EXPEDIENTE.md").exists())

    def test_init_expediente_force_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-CLI"
            self._run_cli([str(exp_path), "init-expediente"])
            readme = exp_path / "README_EXPEDIENTE.md"
            readme.write_text("PERSONALIZADO", encoding="utf-8")
            self._run_cli([str(exp_path), "init-expediente", "--force"])
            self.assertNotEqual(readme.read_text(encoding="utf-8"), "PERSONALIZADO")

    def test_init_expediente_exit_0_en_exito(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-2026-CLI"
            ret = self._run_cli([str(exp_path), "init-expediente"])
            self.assertEqual(ret, 0)

    def test_init_expediente_no_toca_rutas_no_indicadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            otro_path = Path(tmp) / "OTRO-EXPEDIENTE"
            otro_path.mkdir()
            marker = otro_path / "marker.txt"
            marker.write_text("intacto", encoding="utf-8")
            exp_path = Path(tmp) / "EIA-2026-CLI"
            self._run_cli([str(exp_path), "init-expediente"])
            self.assertEqual(marker.read_text(encoding="utf-8"), "intacto")

    def test_init_expediente_escribe_result_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "EIA-CLI"
            self._run_cli([str(exp_path), "init-expediente"])
            result_json = exp_path / "control_interno" / "init_expediente_result.json"
            self.assertTrue(result_json.exists())
            data = json.loads(result_json.read_text(encoding="utf-8"))
            self.assertIn("expediente_id", data)


# ---------------------------------------------------------------------------
# 10. Constantes
# ---------------------------------------------------------------------------

class TestConstantes(unittest.TestCase):

    def test_standard_dirs_tiene_inputs(self):
        self.assertIn("inputs", STANDARD_EXPEDIENTE_DIRS)

    def test_standard_dirs_tiene_auditoria(self):
        self.assertIn("auditoria", STANDARD_EXPEDIENTE_DIRS)

    def test_standard_dirs_tiene_20_carpetas(self):
        self.assertEqual(len(STANDARD_EXPEDIENTE_DIRS), 20)

    def test_standard_guide_files_tiene_readme(self):
        self.assertIn("README_EXPEDIENTE.md", STANDARD_GUIDE_FILES)

    def test_standard_guide_files_tiene_instrucciones_inputs(self):
        self.assertIn("inputs/INSTRUCCIONES_INPUTS.md", STANDARD_GUIDE_FILES)

    def test_standard_metadata_file_en_control_interno(self):
        self.assertTrue(STANDARD_METADATA_FILE.startswith("control_interno/"))

    def test_status_values_tiene_created(self):
        self.assertIn("CREATED", STATUS_VALUES)

    def test_status_values_tiene_error(self):
        self.assertIn("ERROR", STATUS_VALUES)


if __name__ == "__main__":
    unittest.main()
