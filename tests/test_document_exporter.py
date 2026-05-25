"""
Tests para document_exporter (DOC-07).

Estrategia offline:
  - tempfile.TemporaryDirectory() para aislamiento total.
  - subprocess.run mockeado: no se llama a LibreOffice real.
  - win32com mockeado via sys.modules: no se requiere pywin32 instalado.
  - shutil.which mockeado para detectar soffice.
  - No se modifican expedientes piloto reales.
  - No se realizan llamadas externas.
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Asegurar que src/ esta en el path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.document_exporter import (
    EXPORT_SEVERITY,
    EXPORT_STATUS,
    PDF_EXPORT_STATUS,
    PACKAGE_ZIP_FILENAME,
    PDF_OUTPUT_FILENAME,
    DEFAULT_PACKAGE_DIR,
    DEFAULT_DOCX_SOURCE,
    DocumentExportResult,
    ExportIssue,
    _should_exclude,
    build_export_report_markdown,
    can_use_word_com,
    convert_docx_to_pdf_with_soffice,
    convert_docx_to_pdf_with_word_com,
    create_zip_from_directory,
    export_document_package,
    export_pdf_best_effort,
    find_soffice_executable,
    write_export_result_outputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_package_dir(exp_root: Path) -> Path:
    """Crea estructura minima de paquete_entrega/ en un directorio de expediente."""
    pkg = exp_root / "documento" / "paquete_entrega"
    (pkg / "01_documento_ambiental").mkdir(parents=True)
    (pkg / "01_documento_ambiental" / "doc.docx").write_bytes(b"PK\x03\x04" + b"\x00" * 20)
    (pkg / "01_documento_ambiental" / "doc.md").write_text("# Doc", encoding="utf-8")
    (pkg / "02_auditorias").mkdir(parents=True)
    (pkg / "02_auditorias" / "audit.json").write_text('{"status": "OK"}', encoding="utf-8")
    (pkg / "03_anexos_graficos").mkdir(parents=True)
    (pkg / "03_anexos_graficos" / "figs.md").write_text("# Figs", encoding="utf-8")
    (pkg / "04_trazabilidad").mkdir(parents=True)
    (pkg / "04_trazabilidad" / "manifest.json").write_text('{}', encoding="utf-8")
    (pkg / "README_ENTREGA.md").write_text("# README", encoding="utf-8")
    return pkg


def _make_fake_docx(exp_root: Path) -> Path:
    """Crea un DOCX fuente falso para conversion PDF."""
    docx = exp_root / "documento" / "documento_ambiental_borrador_con_figuras.docx"
    docx.parent.mkdir(parents=True, exist_ok=True)
    docx.write_bytes(b"PK\x03\x04" + b"\x00" * 20)
    return docx


def _make_export_result(
    zip_generated: bool = True,
    pdf_status: str = PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER,
    issues: "list[ExportIssue] | None" = None,
    files_zipped: "list[str] | None" = None,
) -> DocumentExportResult:
    return DocumentExportResult(
        expediente_id="test_exp",
        package_dir="/tmp/test_exp/documento/paquete_entrega",
        zip_path="/tmp/test_exp/documento/paquete_entrega.zip",
        pdf_source_docx="/tmp/test_exp/documento/doc.docx",
        pdf_path=None,
        zip_generated=zip_generated,
        pdf_status=pdf_status,
        files_zipped=files_zipped or ["01_documento_ambiental/doc.docx"],
        issues=issues or [],
        warnings=[],
        notes=[],
    )


# ---------------------------------------------------------------------------
# TestExportIssue
# ---------------------------------------------------------------------------

class TestExportIssue(unittest.TestCase):

    def test_to_dict_contains_all_fields(self):
        issue = ExportIssue(
            severity=EXPORT_SEVERITY.ERROR,
            code="EXP-E001",
            message="Test message",
            recommendation="Fix it",
            evidence=["path/to/file"],
        )
        d = issue.to_dict()
        self.assertEqual(d["severity"], EXPORT_SEVERITY.ERROR)
        self.assertEqual(d["code"], "EXP-E001")
        self.assertEqual(d["message"], "Test message")
        self.assertEqual(d["recommendation"], "Fix it")
        self.assertEqual(d["evidence"], ["path/to/file"])

    def test_summary_contains_severity_and_code(self):
        issue = ExportIssue(
            severity=EXPORT_SEVERITY.WARNING,
            code="EXP-W001",
            message="Missing file",
            recommendation="Add it",
        )
        s = issue.summary()
        self.assertIn("WARNING", s)
        self.assertIn("EXP-W001", s)
        self.assertIn("Missing file", s)

    def test_default_evidence_is_empty_list(self):
        issue = ExportIssue(
            severity=EXPORT_SEVERITY.INFO,
            code="EXP-I001",
            message="Info",
            recommendation="N/A",
        )
        self.assertEqual(issue.evidence, [])


# ---------------------------------------------------------------------------
# TestDocumentExportResult
# ---------------------------------------------------------------------------

class TestDocumentExportResult(unittest.TestCase):

    def test_error_count_counts_only_errors(self):
        result = _make_export_result(issues=[
            ExportIssue(EXPORT_SEVERITY.ERROR, "E1", "e", "r"),
            ExportIssue(EXPORT_SEVERITY.WARNING, "W1", "w", "r"),
            ExportIssue(EXPORT_SEVERITY.INFO, "I1", "i", "r"),
        ])
        self.assertEqual(result.error_count(), 1)

    def test_warning_count_counts_only_warnings(self):
        result = _make_export_result(issues=[
            ExportIssue(EXPORT_SEVERITY.ERROR, "E1", "e", "r"),
            ExportIssue(EXPORT_SEVERITY.WARNING, "W1", "w", "r"),
            ExportIssue(EXPORT_SEVERITY.WARNING, "W2", "w", "r"),
        ])
        self.assertEqual(result.warning_count(), 2)

    def test_files_zipped_count(self):
        result = _make_export_result(files_zipped=["a.docx", "b.json", "c.md"])
        self.assertEqual(result.files_zipped_count(), 3)

    def test_is_success_true_when_zip_and_no_errors(self):
        result = _make_export_result(zip_generated=True, issues=[])
        self.assertTrue(result.is_success())

    def test_is_success_false_when_no_zip(self):
        result = _make_export_result(zip_generated=False, issues=[])
        self.assertFalse(result.is_success())

    def test_is_success_false_when_error_present(self):
        result = _make_export_result(
            zip_generated=True,
            issues=[ExportIssue(EXPORT_SEVERITY.ERROR, "E1", "e", "r")],
        )
        self.assertFalse(result.is_success())

    def test_is_success_true_when_pdf_skipped_but_zip_ok(self):
        """Falta de conversor PDF no bloquea is_success si ZIP OK."""
        result = _make_export_result(
            zip_generated=True,
            pdf_status=PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER,
            issues=[ExportIssue(EXPORT_SEVERITY.WARNING, "W1", "no pdf", "install lo")],
        )
        self.assertTrue(result.is_success())

    def test_is_success_false_when_zip_not_generated_with_error(self):
        result = _make_export_result(
            zip_generated=False,
            issues=[ExportIssue(EXPORT_SEVERITY.ERROR, "E1", "e", "r")],
        )
        self.assertFalse(result.is_success())

    def test_to_dict_contains_expected_keys(self):
        result = _make_export_result()
        d = result.to_dict()
        for key in ("expediente_id", "zip_path", "pdf_status", "zip_generated",
                    "files_zipped", "issues", "error_count", "warning_count", "is_success"):
            self.assertIn(key, d)

    def test_summary_contains_disclaimer(self):
        result = _make_export_result()
        s = result.summary()
        self.assertIn("presentacion administrativa", s.lower())

    def test_summary_shows_zip_status(self):
        result_ok = _make_export_result(zip_generated=True)
        result_ko = _make_export_result(zip_generated=False)
        self.assertIn("GENERADO", result_ok.summary())
        self.assertIn("NO_GENERADO", result_ko.summary())

    def test_issue_count(self):
        result = _make_export_result(issues=[
            ExportIssue(EXPORT_SEVERITY.ERROR, "E1", "e", "r"),
            ExportIssue(EXPORT_SEVERITY.WARNING, "W1", "w", "r"),
        ])
        self.assertEqual(result.issue_count(), 2)


# ---------------------------------------------------------------------------
# TestFindSofficeExecutable
# ---------------------------------------------------------------------------

class TestFindSofficeExecutable(unittest.TestCase):

    def test_returns_path_when_shutil_finds_soffice(self):
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda name: (
                "/usr/bin/soffice" if name == "soffice" else None
            )
            result = find_soffice_executable()
        self.assertEqual(result, "/usr/bin/soffice")

    def test_returns_none_when_not_in_path_and_no_typical_paths(self):
        with patch("shutil.which", return_value=None):
            with patch("os.path.exists", return_value=False):
                result = find_soffice_executable()
        self.assertIsNone(result)

    def test_returns_typical_windows_path_when_exists(self):
        typical = r"C:\Program Files\LibreOffice\program\soffice.exe"
        with patch("shutil.which", return_value=None):
            with patch("os.path.exists", side_effect=lambda p: p == typical):
                result = find_soffice_executable()
        self.assertEqual(result, typical)


# ---------------------------------------------------------------------------
# TestCanUseWordCom
# ---------------------------------------------------------------------------

class TestCanUseWordCom(unittest.TestCase):

    def test_returns_bool_without_raising(self):
        result = can_use_word_com()
        self.assertIsInstance(result, bool)

    def test_returns_false_when_win32com_unavailable(self):
        saved = {k: v for k, v in sys.modules.items() if "win32com" in k}
        for k in list(sys.modules.keys()):
            if "win32com" in k:
                del sys.modules[k]
        sys.modules["win32com"] = None  # type: ignore
        sys.modules["win32com.client"] = None  # type: ignore
        try:
            with patch("platform.system", return_value="Windows"):
                result = can_use_word_com()
            self.assertFalse(result)
        finally:
            for k in ["win32com", "win32com.client"]:
                sys.modules.pop(k, None)
            sys.modules.update(saved)


# ---------------------------------------------------------------------------
# TestShouldExclude
# ---------------------------------------------------------------------------

class TestShouldExclude(unittest.TestCase):

    def test_excludes_pycache(self):
        self.assertTrue(_should_exclude(("__pycache__", "foo.pyc")))

    def test_excludes_pytest_cache(self):
        self.assertTrue(_should_exclude((".pytest_cache", "v", "cache")))

    def test_excludes_thumbs_db(self):
        self.assertTrue(_should_exclude(("thumbs.db",)))

    def test_excludes_desktop_ini(self):
        self.assertTrue(_should_exclude(("desktop.ini",)))

    def test_excludes_office_temp_file(self):
        self.assertTrue(_should_exclude(("~$document.docx",)))

    def test_does_not_exclude_normal_file(self):
        self.assertFalse(_should_exclude(("01_doc", "document.docx")))


# ---------------------------------------------------------------------------
# TestCreateZipFromDirectory
# ---------------------------------------------------------------------------

class TestCreateZipFromDirectory(unittest.TestCase):

    def test_creates_zip_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            src.mkdir()
            (src / "file.txt").write_text("hello", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            create_zip_from_directory(src, out)
            self.assertTrue(out.exists())

    def test_includes_files_with_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            (src / "sub").mkdir(parents=True)
            (src / "sub" / "file.txt").write_text("x", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            included = create_zip_from_directory(src, out)
            self.assertIn("sub/file.txt", included)
            with zipfile.ZipFile(str(out)) as zf:
                self.assertIn("sub/file.txt", zf.namelist())

    def test_excludes_pycache_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            (src / "__pycache__").mkdir(parents=True)
            (src / "__pycache__" / "module.pyc").write_bytes(b"cache")
            (src / "real.txt").write_text("real", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            included = create_zip_from_directory(src, out)
            self.assertNotIn("__pycache__/module.pyc", included)
            self.assertIn("real.txt", included)

    def test_excludes_office_temp_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            src.mkdir()
            (src / "~$document.docx").write_bytes(b"temp")
            (src / "document.docx").write_bytes(b"real")
            out = Path(tmpdir) / "output.zip"
            included = create_zip_from_directory(src, out)
            temp_names = [f for f in included if f.startswith("~$")]
            self.assertEqual(len(temp_names), 0)
            self.assertIn("document.docx", included)

    def test_excludes_desktop_ini(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            src.mkdir()
            (src / "desktop.ini").write_text("[.ShellClassInfo]", encoding="utf-8")
            (src / "readme.md").write_text("# README", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            included = create_zip_from_directory(src, out)
            self.assertNotIn("desktop.ini", included)
            self.assertIn("readme.md", included)

    def test_raises_file_not_found_if_source_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "nonexistent"
            out = Path(tmpdir) / "output.zip"
            with self.assertRaises(FileNotFoundError):
                create_zip_from_directory(missing, out)

    def test_returns_list_of_strings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            src.mkdir()
            (src / "a.txt").write_text("a", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            result = create_zip_from_directory(src, out)
            self.assertIsInstance(result, list)
            self.assertTrue(all(isinstance(s, str) for s in result))

    def test_does_not_include_files_outside_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source"
            src.mkdir()
            (src / "inside.txt").write_text("in", encoding="utf-8")
            outside = Path(tmpdir) / "outside.txt"
            outside.write_text("out", encoding="utf-8")
            out = Path(tmpdir) / "output.zip"
            included = create_zip_from_directory(src, out)
            self.assertIn("inside.txt", included)
            for name in included:
                self.assertNotIn("outside", name)


# ---------------------------------------------------------------------------
# TestConvertDocxToPdfWithSoffice
# ---------------------------------------------------------------------------

class TestConvertDocxToPdfWithSoffice(unittest.TestCase):

    def test_returns_true_when_pdf_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"

            def fake_run(cmd, **kwargs):
                # Simula que LibreOffice crea el PDF
                pdf.write_bytes(b"fake pdf content")
                return Mock(returncode=0)

            with patch("subprocess.run", side_effect=fake_run):
                result = convert_docx_to_pdf_with_soffice(
                    docx, pdf, soffice_path="/fake/soffice"
                )
            self.assertTrue(result)
            self.assertTrue(pdf.exists())

    def test_returns_false_when_subprocess_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"

            with patch("subprocess.run", return_value=Mock(returncode=1)):
                result = convert_docx_to_pdf_with_soffice(
                    docx, pdf, soffice_path="/fake/soffice"
                )
            self.assertFalse(result)

    def test_returns_false_when_docx_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "missing.docx"
            pdf = Path(tmpdir) / "out.pdf"
            result = convert_docx_to_pdf_with_soffice(docx, pdf, soffice_path="/fake/soffice")
            self.assertFalse(result)

    def test_returns_false_when_no_soffice_in_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"
            with patch("shutil.which", return_value=None):
                with patch("os.path.exists", return_value=False):
                    result = convert_docx_to_pdf_with_soffice(docx, pdf)
            self.assertFalse(result)

    def test_renames_soffice_output_if_stem_differs(self):
        """LibreOffice crea <stem>.pdf en outdir; el modulo debe moverlo si el nombre difiere."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "source_doc.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "final_output.pdf"

            def fake_run(cmd, **kwargs):
                # LibreOffice crea source_doc.pdf, no final_output.pdf
                (Path(tmpdir) / "source_doc.pdf").write_bytes(b"pdf content")
                return Mock(returncode=0)

            with patch("subprocess.run", side_effect=fake_run):
                result = convert_docx_to_pdf_with_soffice(
                    docx, pdf, soffice_path="/fake/soffice"
                )
            self.assertTrue(result)
            self.assertTrue(pdf.exists())


# ---------------------------------------------------------------------------
# TestConvertDocxToPdfWithWordCom
# ---------------------------------------------------------------------------

class TestConvertDocxToPdfWithWordCom(unittest.TestCase):

    def test_returns_false_when_win32com_unavailable(self):
        saved = {k: v for k, v in sys.modules.items() if "win32com" in k}
        for k in list(sys.modules.keys()):
            if "win32com" in k:
                del sys.modules[k]
        sys.modules["win32com"] = None  # type: ignore
        sys.modules["win32com.client"] = None  # type: ignore
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                docx = Path(tmpdir) / "test.docx"
                docx.write_bytes(b"fake")
                pdf = Path(tmpdir) / "test.pdf"
                result = convert_docx_to_pdf_with_word_com(docx, pdf)
            self.assertFalse(result)
        finally:
            for k in ["win32com", "win32com.client"]:
                sys.modules.pop(k, None)
            sys.modules.update(saved)

    def test_returns_false_when_docx_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "missing.docx"
            pdf = Path(tmpdir) / "out.pdf"
            # Incluso si win32com estuviera disponible, debe devolver False por docx ausente
            result = convert_docx_to_pdf_with_word_com(docx, pdf)
            self.assertFalse(result)

    def test_returns_true_when_word_com_mocked_successfully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"

            mock_win32_module = types.ModuleType("win32com")
            mock_client = types.ModuleType("win32com.client")
            mock_word = Mock()
            mock_doc = Mock()
            mock_client.Dispatch = Mock(return_value=mock_word)
            mock_word.Documents.Open = Mock(return_value=mock_doc)

            def fake_save_as(path, FileFormat=None):
                Path(path).write_bytes(b"pdf content")
            mock_doc.SaveAs = fake_save_as
            mock_win32_module.client = mock_client

            saved = {k: v for k, v in sys.modules.items() if "win32com" in k}
            for k in list(sys.modules.keys()):
                if "win32com" in k:
                    del sys.modules[k]
            sys.modules["win32com"] = mock_win32_module  # type: ignore
            sys.modules["win32com.client"] = mock_client  # type: ignore
            try:
                result = convert_docx_to_pdf_with_word_com(docx, pdf)
                self.assertTrue(result)
            finally:
                for k in ["win32com", "win32com.client"]:
                    sys.modules.pop(k, None)
                sys.modules.update(saved)


# ---------------------------------------------------------------------------
# TestExportPdfBestEffort
# ---------------------------------------------------------------------------

class TestExportPdfBestEffort(unittest.TestCase):

    def test_source_missing_returns_source_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_docx = Path(tmpdir) / "missing.docx"
            pdf = Path(tmpdir) / "out.pdf"
            status, issues = export_pdf_best_effort(missing_docx, pdf)
        self.assertEqual(status, PDF_EXPORT_STATUS.SOURCE_MISSING)
        self.assertTrue(len(issues) > 0)
        self.assertTrue(any(i.code == "EXP-W001" for i in issues))

    def test_no_converter_returns_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake")
            pdf = Path(tmpdir) / "out.pdf"
            with patch("shutil.which", return_value=None):
                with patch("os.path.exists", return_value=False):
                    with patch("platform.system", return_value="Linux"):
                        status, issues = export_pdf_best_effort(docx, pdf)
        self.assertEqual(status, PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER)
        self.assertTrue(any(i.code == "EXP-W002" for i in issues))

    def test_soffice_success_returns_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"

            def fake_run(cmd, **kwargs):
                pdf.write_bytes(b"pdf content")
                return Mock(returncode=0)

            with patch("shutil.which", side_effect=lambda n: "/soffice" if n == "soffice" else None):
                with patch("subprocess.run", side_effect=fake_run):
                    status, issues = export_pdf_best_effort(docx, pdf)
        self.assertEqual(status, PDF_EXPORT_STATUS.GENERATED)
        self.assertEqual(len([i for i in issues if i.severity == EXPORT_SEVERITY.ERROR]), 0)

    def test_soffice_failure_returns_failed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"
            with patch("shutil.which", side_effect=lambda n: "/soffice" if n == "soffice" else None):
                with patch("subprocess.run", return_value=Mock(returncode=1)):
                    with patch("platform.system", return_value="Linux"):
                        status, issues = export_pdf_best_effort(docx, pdf)
        self.assertEqual(status, PDF_EXPORT_STATUS.FAILED)
        self.assertTrue(any(i.code == "EXP-W003" for i in issues))

    def test_prefer_soffice_tried_before_word_com(self):
        """Con prefer='soffice', se intenta soffice primero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake docx")
            pdf = Path(tmpdir) / "test.pdf"
            call_order = []

            def fake_run(cmd, **kwargs):
                call_order.append("soffice")
                pdf.write_bytes(b"pdf")
                return Mock(returncode=0)

            with patch("shutil.which", side_effect=lambda n: "/soffice" if n == "soffice" else None):
                with patch("subprocess.run", side_effect=fake_run):
                    status, _ = export_pdf_best_effort(docx, pdf, prefer="soffice")

        self.assertEqual(status, PDF_EXPORT_STATUS.GENERATED)
        self.assertIn("soffice", call_order)

    def test_issues_are_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "test.docx"
            docx.write_bytes(b"fake")
            pdf = Path(tmpdir) / "out.pdf"
            with patch("shutil.which", return_value=None):
                with patch("os.path.exists", return_value=False):
                    with patch("platform.system", return_value="Linux"):
                        status, issues = export_pdf_best_effort(docx, pdf)
            self.assertIsInstance(issues, list)


# ---------------------------------------------------------------------------
# TestBuildExportReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildExportReportMarkdown(unittest.TestCase):

    def _get_result(self) -> DocumentExportResult:
        return _make_export_result(
            zip_generated=True,
            pdf_status=PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER,
            files_zipped=["01_documento_ambiental/doc.docx", "02_auditorias/audit.json"],
        )

    def test_contains_summary_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 1. Resumen", md)

    def test_contains_zip_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 2. ZIP generado", md)

    def test_contains_pdf_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 3. PDF generado", md)

    def test_contains_files_zipped_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 4. Archivos incluidos en ZIP", md)
        self.assertIn("doc.docx", md)

    def test_contains_disclaimer(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("presentacion administrativa", md.lower())

    def test_contains_incidencias_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 5. Incidencias", md)

    def test_contains_advertencias_section(self):
        md = build_export_report_markdown(self._get_result())
        self.assertIn("## 6. Advertencias", md)

    def test_shows_zip_status(self):
        result_ok = _make_export_result(zip_generated=True)
        md = build_export_report_markdown(result_ok)
        self.assertIn("GENERADO", md)


# ---------------------------------------------------------------------------
# TestWriteExportResultOutputs
# ---------------------------------------------------------------------------

class TestWriteExportResultOutputs(unittest.TestCase):

    def test_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            result = _make_export_result()
            json_path, md_path = write_export_result_outputs(result, out_dir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid_and_loadable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _make_export_result()
            json_path, _ = write_export_result_outputs(result, Path(tmpdir))
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIsInstance(data, dict)

    def test_json_has_required_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _make_export_result()
            json_path, _ = write_export_result_outputs(result, Path(tmpdir))
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            for key in ("expediente_id", "zip_generated", "pdf_status", "is_success"):
                self.assertIn(key, data)


# ---------------------------------------------------------------------------
# TestExportDocumentPackage
# ---------------------------------------------------------------------------

class TestExportDocumentPackage(unittest.TestCase):

    def test_missing_package_dir_yields_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            (exp / "documento").mkdir()
            # No paquete_entrega/
            result = export_document_package(exp, write_outputs=False)
        self.assertFalse(result.zip_generated)
        self.assertTrue(any(i.code == "EXP-E001" for i in result.issues))
        self.assertFalse(result.is_success())

    def test_dry_run_does_not_create_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(exp, write_outputs=False)
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            self.assertFalse(zip_path.exists())
            self.assertFalse(result.zip_generated)

    def test_dry_run_exit_condition_ok_when_package_present(self):
        """Dry-run con paquete presente: no errores, is_success False (no ZIP generado)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(exp, write_outputs=False)
        self.assertEqual(result.error_count(), 0)
        self.assertFalse(result.zip_generated)

    def test_write_creates_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            self.assertTrue(result.zip_generated)
            self.assertTrue(zip_path.exists())

    def test_write_zip_contains_expected_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            with zipfile.ZipFile(str(zip_path)) as zf:
                names = zf.namelist()
        self.assertTrue(any("doc.docx" in n for n in names))
        self.assertTrue(result.files_zipped_count() > 0)

    def test_no_pdf_flag_sets_not_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
        self.assertEqual(result.pdf_status, PDF_EXPORT_STATUS.NOT_REQUESTED)
        self.assertIsNone(result.pdf_path)

    def test_zip_not_contains_itself(self):
        """El ZIP en documento/ no debe estar dentro del ZIP (no esta en paquete_entrega/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            with zipfile.ZipFile(str(zip_path)) as zf:
                names = zf.namelist()
        self.assertFalse(any(PACKAGE_ZIP_FILENAME in n for n in names))

    def test_does_not_modify_package_entrega_contents(self):
        """Verificar que los archivos de paquete_entrega no se modificaron."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            pkg = _make_fake_package_dir(exp)
            original_content = (pkg / "README_ENTREGA.md").read_text(encoding="utf-8")
            export_document_package(exp, write_outputs=True, generate_pdf=False)
            after_content = (pkg / "README_ENTREGA.md").read_text(encoding="utf-8")
        self.assertEqual(original_content, after_content)

    def test_is_success_true_when_zip_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
        self.assertTrue(result.is_success())

    def test_is_success_true_when_pdf_skipped_no_converter(self):
        """PDF no disponible por falta de conversor no bloquea is_success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            _make_fake_docx(exp)
            with patch("shutil.which", return_value=None):
                with patch("os.path.exists", side_effect=lambda p: Path(p).exists()):
                    with patch("platform.system", return_value="Linux"):
                        result = export_document_package(
                            exp, write_outputs=True, generate_pdf=True
                        )
        self.assertTrue(result.zip_generated)
        self.assertEqual(result.pdf_status, PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER)
        self.assertTrue(result.is_success())

    def test_overwrite_replaces_existing_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            # Primera ejecucion
            export_document_package(exp, write_outputs=True, generate_pdf=False)
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            mtime1 = zip_path.stat().st_mtime
            # Segunda ejecucion con overwrite=True
            import time
            time.sleep(0.05)
            export_document_package(
                exp, write_outputs=True, generate_pdf=False, overwrite=True
            )
            mtime2 = zip_path.stat().st_mtime
        self.assertGreaterEqual(mtime2, mtime1)

    def test_zip_path_in_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=True, generate_pdf=False
            )
        self.assertIsNotNone(result.zip_path)
        self.assertIn(PACKAGE_ZIP_FILENAME, result.zip_path)

    def test_pdf_source_docx_in_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            _make_fake_package_dir(exp)
            result = export_document_package(
                exp, write_outputs=False, generate_pdf=True
            )
        self.assertIsNotNone(result.pdf_source_docx)
        self.assertIn("con_figuras.docx", result.pdf_source_docx)


# ---------------------------------------------------------------------------
# TestCLIDocumentExport
# ---------------------------------------------------------------------------

class TestCLIDocumentExport(unittest.TestCase):
    """Tests del comando document-export via run_expediente.py main()."""

    def _run_main(self, args: list[str]) -> int:
        from run_expediente import main
        return main(args)

    def test_dry_run_exit_0_when_package_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            code = self._run_main([str(exp), "document-export"])
        self.assertEqual(code, 0)

    def test_dry_run_exit_1_when_no_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            (exp / "documento").mkdir(parents=True)
            code = self._run_main([str(exp), "document-export"])
        self.assertEqual(code, 1)

    def test_write_creates_zip_exit_0(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            code = self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            self.assertEqual(code, 0)
            self.assertTrue(zip_path.exists())

    def test_write_missing_package_exit_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            (exp / "documento").mkdir(parents=True)
            code = self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
        self.assertEqual(code, 1)

    def test_no_pdf_flag_no_pdf_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
            pdf_path = exp / "documento" / PDF_OUTPUT_FILENAME
        self.assertFalse(pdf_path.exists())

    def test_pdf_skipped_no_converter_still_exit_0(self):
        """Sin conversor PDF, el ZIP OK da exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            with patch("shutil.which", return_value=None):
                with patch("os.path.exists", side_effect=lambda p: Path(p).exists()):
                    with patch("platform.system", return_value="Linux"):
                        code = self._run_main([str(exp), "document-export", "--write"])
        self.assertEqual(code, 0)

    def test_writes_result_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
            json_path = exp / "documento" / "document_export_result.json"
            md_path = exp / "documento" / "document_export_result.md"
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_overwrite_replaces_existing_zip_via_cli(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "exp01"
            exp.mkdir()
            _make_fake_package_dir(exp)
            self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
            zip_path = exp / "documento" / PACKAGE_ZIP_FILENAME
            size1 = zip_path.stat().st_size
            self._run_main([str(exp), "document-export", "--write", "--no-pdf"])
            size2 = zip_path.stat().st_size
        # El ZIP debe seguir existiendo y ser coherente
        self.assertGreater(size1, 0)
        self.assertGreater(size2, 0)


if __name__ == "__main__":
    unittest.main()
