"""
tests/test_document_package_builder.py
Tests unitarios para document_package_builder (DOC-06).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.document_package_builder import (
    PACKAGE_DIR_NAME,
    PACKAGE_RESULT_JSON,
    PACKAGE_RESULT_MD,
    DocumentPackageResult,
    PackageFile,
    build_document_package,
    build_package_report_markdown,
    build_readme_entrega,
    collect_package_files,
    safe_copy_file,
    write_package_build_outputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exp(tmp: Path) -> Path:
    """Crea estructura mínima de expediente."""
    exp = tmp / "expediente-EIA-TEST-001"
    (exp / "documento").mkdir(parents=True)
    (exp / "auditoria").mkdir(parents=True)
    return exp


def _write_file(path: Path, content: str = "contenido") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_docx(path: Path) -> None:
    """Crea un archivo .docx mínimo (solo comprueba existencia, no formato real)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04FAKE_DOCX_CONTENT")


# ---------------------------------------------------------------------------
# 1. PackageFile
# ---------------------------------------------------------------------------

class TestPackageFile(unittest.TestCase):

    def _make_pf(self, **kw) -> PackageFile:
        defaults = dict(
            source_path="/exp/documento/doc.md",
            package_path="/pkg/01_documento_ambiental/doc.md",
            exists=True,
            copied=True,
            file_size_bytes=1024,
            required=True,
            warnings=[],
            notes=[],
        )
        defaults.update(kw)
        return PackageFile(**defaults)

    def test_to_dict_keys(self):
        pf = self._make_pf()
        d = pf.to_dict()
        for key in ("source_path", "package_path", "exists", "copied",
                    "file_size_bytes", "required", "warnings", "notes"):
            self.assertIn(key, d)

    def test_to_dict_values(self):
        pf = self._make_pf(exists=False, copied=False, file_size_bytes=0)
        d = pf.to_dict()
        self.assertFalse(d["exists"])
        self.assertFalse(d["copied"])
        self.assertEqual(d["file_size_bytes"], 0)

    def test_summary_ok(self):
        pf = self._make_pf(copied=True, exists=True, required=True)
        s = pf.summary()
        self.assertIn("OK", s)
        self.assertIn("REQUERIDO", s)

    def test_summary_falta(self):
        pf = self._make_pf(copied=False, exists=False, required=True)
        s = pf.summary()
        self.assertIn("NO_EXISTE", s)

    def test_summary_optional(self):
        pf = self._make_pf(copied=True, exists=True, required=False)
        s = pf.summary()
        self.assertIn("OPCIONAL", s)


# ---------------------------------------------------------------------------
# 2. DocumentPackageResult
# ---------------------------------------------------------------------------

class TestDocumentPackageResult(unittest.TestCase):

    def _make_result(self, **kw) -> DocumentPackageResult:
        defaults = dict(
            expediente_id="EIA-TEST-001",
            package_dir=None,
            generated=False,
            files=[],
            required_missing=[],
            optional_missing=[],
            copied_files=[],
            warnings=[],
            notes=[],
        )
        defaults.update(kw)
        return DocumentPackageResult(**defaults)

    def test_copied_count(self):
        r = self._make_result(copied_files=["a", "b", "c"])
        self.assertEqual(r.copied_count(), 3)

    def test_missing_required_count(self):
        r = self._make_result(required_missing=["x", "y"])
        self.assertEqual(r.missing_required_count(), 2)

    def test_missing_optional_count(self):
        r = self._make_result(optional_missing=["z"])
        self.assertEqual(r.missing_optional_count(), 1)

    def test_is_success_true(self):
        r = self._make_result(generated=True, required_missing=[])
        self.assertTrue(r.is_success())

    def test_is_success_false_missing(self):
        r = self._make_result(generated=True, required_missing=["doc.docx"])
        self.assertFalse(r.is_success())

    def test_is_success_false_not_generated(self):
        r = self._make_result(generated=False, required_missing=[])
        self.assertFalse(r.is_success())

    def test_to_dict_keys(self):
        r = self._make_result()
        d = r.to_dict()
        for key in ("expediente_id", "package_dir", "generated", "files",
                    "required_missing", "optional_missing", "copied_files",
                    "warnings", "notes", "copied_count", "missing_required_count",
                    "missing_optional_count", "is_success"):
            self.assertIn(key, d)

    def test_to_dict_files(self):
        pf = PackageFile(
            source_path="/a", package_path="/b",
            exists=True, copied=True, file_size_bytes=0, required=True,
        )
        r = self._make_result(files=[pf])
        d = r.to_dict()
        self.assertEqual(len(d["files"]), 1)

    def test_summary_contains_expediente(self):
        r = self._make_result(expediente_id="EIA-CUSTOM-999")
        s = r.summary()
        self.assertIn("EIA-CUSTOM-999", s)

    def test_summary_contains_disclaimer(self):
        r = self._make_result()
        s = r.summary()
        self.assertIn("presentacion administrativa", s.lower().replace("ó", "o").replace("ó", "o"))

    def test_summary_lists_required_missing(self):
        r = self._make_result(generated=True, required_missing=["doc.docx"])
        s = r.summary()
        self.assertIn("doc.docx", s)


# ---------------------------------------------------------------------------
# 3. safe_copy_file
# ---------------------------------------------------------------------------

class TestSafeCopyFile(unittest.TestCase):

    def test_copies_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src" / "test.txt"
            dst = Path(tmp) / "dst" / "sub" / "test.txt"
            src.parent.mkdir(parents=True)
            src.write_text("hola", encoding="utf-8")

            ok = safe_copy_file(src, dst)
            self.assertTrue(ok)
            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_text(encoding="utf-8"), "hola")

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.txt"
            src.write_text("x", encoding="utf-8")
            dst = Path(tmp) / "deep" / "nested" / "path" / "a.txt"

            ok = safe_copy_file(src, dst)
            self.assertTrue(ok)
            self.assertTrue(dst.exists())

    def test_returns_false_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "no_existe.txt"
            dst = Path(tmp) / "dest.txt"
            ok = safe_copy_file(src, dst)
            self.assertFalse(ok)

    def test_accepts_string_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.txt"
            dst = Path(tmp) / "dst.txt"
            src.write_text("test", encoding="utf-8")
            ok = safe_copy_file(str(src), str(dst))
            self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 4. collect_package_files
# ---------------------------------------------------------------------------

class TestCollectPackageFiles(unittest.TestCase):

    def test_empty_expediente_all_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-EMPTY"
            exp.mkdir()

            files = collect_package_files(exp)
            self.assertIsInstance(files, list)
            self.assertGreater(len(files), 0)

            existing = [f for f in files if f.exists]
            self.assertEqual(len(existing), 0)

    def test_required_files_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "expediente-EIA-REQ"
            exp.mkdir()

            files = collect_package_files(exp)
            required = [f for f in files if f.required]
            self.assertGreater(len(required), 0)
            required_paths = [Path(f.source_path).name for f in required]
            self.assertIn("documento_ambiental_borrador.docx", required_paths)
            self.assertIn("documento_ambiental_borrador.md", required_paths)

    def test_existing_files_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            files = collect_package_files(exp)
            by_name = {Path(f.source_path).name: f for f in files}
            self.assertTrue(by_name["documento_ambiental_borrador.docx"].exists)
            self.assertTrue(by_name["documento_ambiental_borrador.md"].exists)

    def test_destinations_inside_package_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            files = collect_package_files(exp)
            for pf in files:
                self.assertIn(PACKAGE_DIR_NAME, pf.package_path)

    def test_docx_base_goes_to_section_01(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            files = collect_package_files(exp)
            by_name = {Path(f.source_path).name: f for f in files}
            pf = by_name.get("documento_ambiental_borrador.docx")
            self.assertIsNotNone(pf)
            self.assertIn("01_documento_ambiental", pf.package_path)

    def test_audit_file_goes_to_section_02(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            files = collect_package_files(exp)
            by_name = {Path(f.source_path).name: f for f in files}
            pf = by_name.get("final_audit_result.json")
            self.assertIsNotNone(pf)
            self.assertIn("02_auditorias", pf.package_path)

    def test_figures_result_md_goes_to_section_03(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            files = collect_package_files(exp)
            # document_figures_result.md debe ir a 03_anexos_graficos
            figures_md = [
                f for f in files
                if Path(f.source_path).name == "document_figures_result.md"
                and "03_anexos_graficos" in f.package_path
            ]
            self.assertGreater(len(figures_md), 0)

    def test_enriched_docx_warning_when_figures_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            figs_json = exp / "documento" / "document_figures_result.json"
            figs_json.write_text(
                json.dumps({"generated": True, "figures_inserted": ["FIG-001"]}),
                encoding="utf-8",
            )
            # NO crear el DOCX enriquecido

            files = collect_package_files(exp)
            enriched = [
                f for f in files
                if Path(f.source_path).name == "documento_ambiental_borrador_con_figuras.docx"
            ]
            self.assertEqual(len(enriched), 1)
            self.assertGreater(len(enriched[0].warnings), 0)

    def test_no_warning_when_figures_not_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            # No existe document_figures_result.json

            files = collect_package_files(exp)
            enriched = [
                f for f in files
                if Path(f.source_path).name == "documento_ambiental_borrador_con_figuras.docx"
            ]
            self.assertEqual(len(enriched), 1)
            self.assertEqual(len(enriched[0].warnings), 0)


# ---------------------------------------------------------------------------
# 5. build_readme_entrega
# ---------------------------------------------------------------------------

class TestBuildReadmeEntrega(unittest.TestCase):

    def _make_result(self, **kw) -> DocumentPackageResult:
        defaults = dict(
            expediente_id="EIA-TEST-001",
            package_dir="/pkg",
            generated=True,
            files=[],
            required_missing=[],
            optional_missing=[],
            copied_files=[],
            warnings=[],
            notes=[],
        )
        defaults.update(kw)
        return DocumentPackageResult(**defaults)

    def test_contains_title(self):
        r = self._make_result()
        readme = build_readme_entrega(r)
        self.assertIn("Paquete de entrega", readme)

    def test_contains_expediente_id(self):
        r = self._make_result(expediente_id="EIA-CUSTOM-777")
        readme = build_readme_entrega(r)
        self.assertIn("EIA-CUSTOM-777", readme)

    def test_contains_disclaimer_aptitud(self):
        r = self._make_result()
        readme = build_readme_entrega(r)
        readme_norm = readme.lower()
        self.assertIn("no declara", readme_norm)
        self.assertIn("presentacion administrativa", readme_norm)

    def test_lists_missing_required(self):
        r = self._make_result(required_missing=["doc.docx", "doc.md"])
        readme = build_readme_entrega(r)
        self.assertIn("doc.docx", readme)
        self.assertIn("doc.md", readme)
        self.assertIn("REQUERIDO", readme)

    def test_lists_optional_missing(self):
        r = self._make_result(optional_missing=["audit.json"])
        readme = build_readme_entrega(r)
        self.assertIn("audit.json", readme)

    def test_contains_sections(self):
        r = self._make_result()
        readme = build_readme_entrega(r)
        self.assertIn("## 1.", readme)
        self.assertIn("## 2.", readme)
        self.assertIn("## 3.", readme)
        self.assertIn("## 4.", readme)
        self.assertIn("## 5.", readme)
        self.assertIn("## 6.", readme)

    def test_with_copied_files_shows_document(self):
        pf = PackageFile(
            source_path="/exp/documento/doc.docx",
            package_path="/pkg/01_documento_ambiental/doc.docx",
            exists=True,
            copied=True,
            file_size_bytes=1000,
            required=True,
        )
        r = self._make_result(files=[pf], copied_files=[pf.package_path])
        readme = build_readme_entrega(r)
        self.assertIn("doc.docx", readme)
        self.assertIn("Incluido", readme)


# ---------------------------------------------------------------------------
# 6. build_package_report_markdown
# ---------------------------------------------------------------------------

class TestBuildPackageReportMarkdown(unittest.TestCase):

    def _make_result(self, **kw) -> DocumentPackageResult:
        defaults = dict(
            expediente_id="EIA-TEST-001",
            package_dir="/pkg",
            generated=True,
            files=[],
            required_missing=[],
            optional_missing=[],
            copied_files=[],
            warnings=[],
            notes=[],
        )
        defaults.update(kw)
        return DocumentPackageResult(**defaults)

    def test_contains_title(self):
        r = self._make_result()
        md = build_package_report_markdown(r)
        self.assertIn("Resultado de empaquetado documental", md)

    def test_contains_resumen_section(self):
        r = self._make_result()
        md = build_package_report_markdown(r)
        self.assertIn("## 1. Resumen", md)

    def test_contains_copiados_section(self):
        r = self._make_result(copied_files=["a.docx"])
        md = build_package_report_markdown(r)
        self.assertIn("## 2. Archivos copiados", md)
        self.assertIn("a.docx", md)

    def test_contains_faltantes_section(self):
        r = self._make_result(required_missing=["req.docx"])
        md = build_package_report_markdown(r)
        self.assertIn("## 3. Archivos requeridos faltantes", md)
        self.assertIn("req.docx", md)

    def test_contains_opcionales_section(self):
        r = self._make_result(optional_missing=["opt.json"])
        md = build_package_report_markdown(r)
        self.assertIn("## 4. Archivos opcionales faltantes", md)
        self.assertIn("opt.json", md)

    def test_contains_advertencias_section(self):
        r = self._make_result(warnings=["advertencia X"])
        md = build_package_report_markdown(r)
        self.assertIn("## 5. Advertencias", md)
        self.assertIn("advertencia X", md)

    def test_contains_alcance_section(self):
        r = self._make_result()
        md = build_package_report_markdown(r)
        self.assertIn("## 6. Advertencia de alcance", md)
        self.assertIn("no declara", md.lower())

    def test_dry_run_message(self):
        r = self._make_result(generated=False)
        md = build_package_report_markdown(r)
        self.assertIn("dry", md.lower())


# ---------------------------------------------------------------------------
# 7. build_document_package
# ---------------------------------------------------------------------------

class TestBuildDocumentPackage(unittest.TestCase):

    def test_dry_run_no_files_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            result = build_document_package(exp, write_outputs=False)

            self.assertFalse(result.generated)
            self.assertIsNone(result.package_dir)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertFalse(package_dir.exists())

    def test_dry_run_result_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            result = build_document_package(exp, write_outputs=False)

            self.assertIsInstance(result.files, list)
            self.assertGreater(len(result.files), 0)
            self.assertEqual(result.copied_count(), 0)

    def test_write_creates_package_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            result = build_document_package(exp, write_outputs=True)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertTrue(package_dir.exists())
            self.assertTrue(result.generated)

    def test_write_copies_enriched_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador_con_figuras.docx")
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            result = build_document_package(exp, write_outputs=True)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            enriched = package_dir / "01_documento_ambiental" / "documento_ambiental_borrador_con_figuras.docx"
            self.assertTrue(enriched.exists())
            self.assertGreater(result.copied_count(), 0)

    def test_write_copies_base_docx_and_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            result = build_document_package(exp, write_outputs=True)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertTrue((package_dir / "01_documento_ambiental" / "documento_ambiental_borrador.docx").exists())
            self.assertTrue((package_dir / "01_documento_ambiental" / "documento_ambiental_borrador.md").exists())

    def test_write_copies_auditorias(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_file(exp / "auditoria" / "final_audit_result.json", '{"status": "CONFORME"}')
            _write_file(exp / "auditoria" / "final_audit_result.md", "# Final audit")

            result = build_document_package(exp, write_outputs=True)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertTrue((package_dir / "02_auditorias" / "final_audit_result.json").exists())

    def test_write_generates_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            build_document_package(exp, write_outputs=True)
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            readme = package_dir / "README_ENTREGA.md"
            self.assertTrue(readme.exists())
            content = readme.read_text(encoding="utf-8")
            self.assertIn("Paquete de entrega", content)

    def test_missing_required_docx_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            # Solo MD, no DOCX
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            result = build_document_package(exp, write_outputs=True)
            self.assertFalse(result.is_success())
            self.assertGreater(result.missing_required_count(), 0)

    def test_success_when_required_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            result = build_document_package(exp, write_outputs=True)
            self.assertTrue(result.is_success())

    def test_sources_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            src_docx = exp / "documento" / "documento_ambiental_borrador.docx"
            src_md = exp / "documento" / "documento_ambiental_borrador.md"
            _write_docx(src_docx)
            _write_file(src_md, "original content")

            mtime_docx_before = src_docx.stat().st_mtime
            mtime_md_before = src_md.stat().st_mtime

            build_document_package(exp, write_outputs=True)

            self.assertEqual(src_docx.stat().st_mtime, mtime_docx_before)
            self.assertEqual(src_md.stat().st_mtime, mtime_md_before)
            self.assertEqual(src_md.read_text(encoding="utf-8"), "original content")

    def test_overwrite_replaces_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")

            build_document_package(exp, write_outputs=True, overwrite=True)
            build_document_package(exp, write_outputs=True, overwrite=True)

            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertTrue(package_dir.exists())

    def test_result_package_dir_set_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(Path(tmp))
            result = build_document_package(exp, write_outputs=True)
            self.assertIsNotNone(result.package_dir)
            self.assertIn(PACKAGE_DIR_NAME, result.package_dir)


# ---------------------------------------------------------------------------
# 8. write_package_build_outputs
# ---------------------------------------------------------------------------

class TestWritePackageBuildOutputs(unittest.TestCase):

    def _make_result(self) -> DocumentPackageResult:
        return DocumentPackageResult(
            expediente_id="EIA-TEST-001",
            package_dir="/pkg",
            generated=True,
            files=[],
            required_missing=[],
            optional_missing=[],
            copied_files=["a.docx"],
            warnings=[],
            notes=["nota de prueba"],
        )

    def test_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "documento"
            result = self._make_result()

            json_path, md_path = write_package_build_outputs(result, out_dir)

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertEqual(json_path.name, PACKAGE_RESULT_JSON)
            self.assertEqual(md_path.name, PACKAGE_RESULT_MD)

    def test_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "documento"
            result = self._make_result()
            json_path, _ = write_package_build_outputs(result, out_dir)

            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)

            self.assertIn("expediente_id", data)
            self.assertEqual(data["expediente_id"], "EIA-TEST-001")
            self.assertIn("is_success", data)

    def test_md_contains_report_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "documento"
            result = self._make_result()
            _, md_path = write_package_build_outputs(result, out_dir)

            content = md_path.read_text(encoding="utf-8")
            self.assertIn("Resultado de empaquetado documental", content)

    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "nuevo_dir" / "anidado"
            result = self._make_result()
            json_path, md_path = write_package_build_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())


# ---------------------------------------------------------------------------
# 9. Integracion: CLI a traves de main()
# ---------------------------------------------------------------------------

class TestCLIDocumentPackage(unittest.TestCase):
    """
    Prueba el comando document-package a traves de main() de run_expediente.py.
    """

    def _setup_exp(self, tmp: Path, with_required: bool = True) -> Path:
        exp = _make_exp(tmp)
        if with_required:
            _write_docx(exp / "documento" / "documento_ambiental_borrador.docx")
            _write_file(exp / "documento" / "documento_ambiental_borrador.md")
        return exp

    def _run_cli(self, argv: list) -> int:
        import run_expediente as runner
        return runner.main(argv)

    def test_dry_run_does_not_create_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp))
            rc = self._run_cli([str(exp), "document-package"])
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertFalse(package_dir.exists())

    def test_write_creates_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp))
            rc = self._run_cli([str(exp), "document-package", "--write"])
            package_dir = exp / "documento" / PACKAGE_DIR_NAME
            self.assertTrue(package_dir.exists())

    def test_exit_0_when_required_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp), with_required=True)
            rc = self._run_cli([str(exp), "document-package", "--write"])
            self.assertEqual(rc, 0)

    def test_exit_1_when_required_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp), with_required=False)
            rc = self._run_cli([str(exp), "document-package", "--write"])
            self.assertEqual(rc, 1)

    def test_dry_run_exit_reflects_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp), with_required=False)
            rc = self._run_cli([str(exp), "document-package"])
            self.assertEqual(rc, 1)

    def test_dry_run_exit_0_when_all_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp), with_required=True)
            rc = self._run_cli([str(exp), "document-package"])
            self.assertEqual(rc, 0)

    def test_write_generates_build_result_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp))
            self._run_cli([str(exp), "document-package", "--write"])
            json_path = exp / "documento" / PACKAGE_RESULT_JSON
            self.assertTrue(json_path.exists())

    def test_write_generates_build_result_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = self._setup_exp(Path(tmp))
            self._run_cli([str(exp), "document-package", "--write"])
            md_path = exp / "documento" / PACKAGE_RESULT_MD
            self.assertTrue(md_path.exists())


# ---------------------------------------------------------------------------
# DOC-09 — Tests IM-09 en paquete
# ---------------------------------------------------------------------------

class TestConditionalChainInPackageDOC09(unittest.TestCase):
    """Verifica que conditional_chain_result.json/.md se empaquetan en 02_auditorias."""

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def _minimal_exp(self) -> Path:
        exp = self.tmp / "exp-cc-pkg"
        exp.mkdir()
        (exp / "auditoria").mkdir()
        (exp / "documento").mkdir()
        docx = exp / "documento" / "documento_ambiental_borrador.docx"
        docx.write_bytes(b"PK fake")
        md = exp / "documento" / "documento_ambiental_borrador.md"
        md.write_text("# Borrador", encoding="utf-8")
        return exp

    def test_cc_json_in_audit_files_constant(self):
        from eia_agent.core.document_package_builder import AUDIT_FILES
        self.assertIn("auditoria/conditional_chain_result.json", AUDIT_FILES)

    def test_cc_md_in_audit_files_constant(self):
        from eia_agent.core.document_package_builder import AUDIT_FILES
        self.assertIn("auditoria/conditional_chain_result.md", AUDIT_FILES)

    def test_cc_json_copied_to_02_auditorias_when_exists(self):
        exp = self._minimal_exp()
        cc_json = exp / "auditoria" / "conditional_chain_result.json"
        cc_json.write_text('{"status":"OK"}', encoding="utf-8")

        result = build_document_package(exp, write_outputs=True, overwrite=True)
        # copied files have package_path containing the filename
        pkg_paths = [f.package_path for f in result.files if f.copied]
        self.assertTrue(any("conditional_chain_result.json" in p for p in pkg_paths))

    def test_cc_json_in_02_auditorias_section(self):
        exp = self._minimal_exp()
        (exp / "auditoria" / "conditional_chain_result.json").write_text(
            '{"status":"OK"}', encoding="utf-8"
        )
        result = build_document_package(exp, write_outputs=True, overwrite=True)
        cc_files = [f for f in result.files
                    if "conditional_chain_result.json" in f.package_path and f.copied]
        self.assertTrue(cc_files)
        self.assertIn("02_auditorias", cc_files[0].package_path)

    def test_cc_json_absent_goes_to_optional_missing(self):
        exp = self._minimal_exp()
        result = build_document_package(exp, write_outputs=False)
        # optional_missing may contain full source paths
        found = any(
            "conditional_chain_result.json" in p
            for p in result.optional_missing
        )
        self.assertTrue(found, f"conditional_chain_result.json not in optional_missing: {result.optional_missing}")


if __name__ == "__main__":
    unittest.main()
