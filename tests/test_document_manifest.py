"""
tests/test_document_manifest.py
Tests para DOC-00 — Manifest del Documento Ambiental.

Cubre:
  1. DocumentManifestItem — to_dict, summary, status
  2. DocumentManifestResult — conteos, is_ready, to_dict, summary
  3. build_document_manifest — expediente vacio, con outputs, sin expediente
  4. build_document_manifest_markdown — bloques A-K, faltantes, no aptitud
  5. write_document_manifest_outputs — JSON y MD
  6. CLI — sin/con --write, exit codes
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.document_manifest import (
    DOCUMENT_BLOCKS,
    DOCUMENT_REQUIRED_INPUTS,
    MANIFEST_STATUS,
    DocumentManifestItem,
    DocumentManifestResult,
    build_document_manifest,
    build_document_manifest_markdown,
    write_document_manifest_outputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    block_id: str = "A",
    title: str = "Test",
    required_files: list[str] | None = None,
    existing_files: list[str] | None = None,
    missing_files: list[str] | None = None,
    status: str = "READY",
) -> DocumentManifestItem:
    return DocumentManifestItem(
        block_id=block_id,
        title=title,
        required_files=required_files or [],
        optional_files=[],
        existing_files=existing_files or [],
        missing_files=missing_files or [],
        status=status,
    )


def _make_result(
    ready: list[str] | None = None,
    partial: list[str] | None = None,
    missing: list[str] | None = None,
    items: list[DocumentManifestItem] | None = None,
) -> DocumentManifestResult:
    return DocumentManifestResult(
        expediente_id="EIA-TEST",
        manifest_items=items or [],
        ready_blocks=ready or [],
        partial_blocks=partial or [],
        missing_blocks=missing or [],
    )


def _build_expediente_with_files(tmpdir: str, files: list[str]) -> Path:
    """Crea expediente temporal con los archivos indicados."""
    exp = Path(tmpdir) / "EIA-TEST"
    exp.mkdir()
    for f in files:
        p = exp / f
        p.parent.mkdir(parents=True, exist_ok=True)
        if "." in p.name:
            p.write_text("{}", encoding="utf-8")
        else:
            p.mkdir(exist_ok=True)
    return exp


def _pipeline_outputs() -> list[str]:
    """Lista de archivos que genera el pipeline completo."""
    return [
        "fase4/phase4_result.json",
        "inventario/inventory_summary.json",
        "inventario/phase5_gate_result.json",
        "impactos/phase6_actions.json",
        "impactos/phase6_model_base.json",
        "impactos/phase6_model_with_impacts.json",
        "impactos/phase6_model_with_conesa.json",
        "impactos/phase6_model_with_measures.json",
        "impactos/phase6_model_with_pva.json",
        "impactos/pva_coverage_result.json",
        "impactos/cumulative_synergistic_result.json",
        "impactos/C5_acumulativos_sinergicos.md",
        "auditoria/art45_checklist_result.json",
        "auditoria/prudence_validation_result.json",
        "auditoria/traceability_validation_result.json",
        "auditoria/block_consistency_result.json",
        "auditoria/conesa_check_result.json",
        "auditoria/diagnostic_measure_validation_result.json",
        "auditoria/prl_measure_validation_result.json",
        "auditoria/final_audit_result.json",
        "auditoria/final_audit_result.md",
        "capas/hechos_confirmados.json",
        "capas/normativa_aplicable.json",
        "capas/inferencias_y_gaps.json",
        "inputs",  # directory
        "capas",   # already created
        "clima",   # directory
    ]


# ---------------------------------------------------------------------------
# 1. DocumentManifestItem
# ---------------------------------------------------------------------------

class TestDocumentManifestItem(unittest.TestCase):

    def test_to_dict_has_required_keys(self):
        item = _make_item()
        d = item.to_dict()
        for key in ("block_id", "title", "status", "required_files",
                    "optional_files", "existing_files", "missing_files"):
            self.assertIn(key, d)

    def test_to_dict_values_match(self):
        item = _make_item(block_id="B", status="PARTIAL",
                          required_files=["f1", "f2"], existing_files=["f1"])
        d = item.to_dict()
        self.assertEqual(d["block_id"], "B")
        self.assertEqual(d["status"], "PARTIAL")
        self.assertEqual(d["required_files"], ["f1", "f2"])

    def test_summary_contains_status(self):
        item = _make_item(status="READY")
        self.assertIn("READY", item.summary())

    def test_summary_contains_block_id(self):
        item = _make_item(block_id="C")
        self.assertIn("C", item.summary())

    def test_status_ready(self):
        item = _make_item(
            required_files=["a", "b"],
            existing_files=["a", "b"],
            missing_files=[],
            status="READY",
        )
        self.assertEqual(item.status, "READY")

    def test_status_partial(self):
        item = _make_item(
            required_files=["a", "b"],
            existing_files=["a"],
            missing_files=["b"],
            status="PARTIAL",
        )
        self.assertEqual(item.status, "PARTIAL")

    def test_status_missing(self):
        item = _make_item(
            required_files=["a", "b"],
            existing_files=[],
            missing_files=["a", "b"],
            status="MISSING",
        )
        self.assertEqual(item.status, "MISSING")


# ---------------------------------------------------------------------------
# 2. DocumentManifestResult
# ---------------------------------------------------------------------------

class TestDocumentManifestResult(unittest.TestCase):

    def test_ready_count(self):
        r = _make_result(ready=["A", "B"], partial=["C"], missing=["D"])
        self.assertEqual(r.ready_count(), 2)

    def test_partial_count(self):
        r = _make_result(partial=["C", "E"])
        self.assertEqual(r.partial_count(), 2)

    def test_missing_count(self):
        r = _make_result(missing=["G", "H", "J"])
        self.assertEqual(r.missing_count(), 3)

    def test_is_ready_no_missing(self):
        r = _make_result(ready=["A", "B"], partial=["C"])
        self.assertTrue(r.is_ready_for_markdown_generation())

    def test_is_not_ready_with_missing(self):
        r = _make_result(ready=["A"], missing=["B"])
        self.assertFalse(r.is_ready_for_markdown_generation())

    def test_all_missing_not_ready(self):
        r = _make_result(missing=["A", "B", "C"])
        self.assertFalse(r.is_ready_for_markdown_generation())

    def test_administrative_ready_always_false(self):
        r = _make_result(ready=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"])
        self.assertFalse(r.administrative_ready)

    def test_to_dict_has_required_keys(self):
        r = _make_result()
        d = r.to_dict()
        for key in ("expediente_id", "administrative_ready", "ready_blocks",
                    "partial_blocks", "missing_blocks", "ready_count",
                    "partial_count", "missing_count",
                    "is_ready_for_markdown_generation", "manifest_items"):
            self.assertIn(key, d)

    def test_to_dict_administrative_ready_false(self):
        r = _make_result()
        self.assertFalse(r.to_dict()["administrative_ready"])

    def test_summary_contains_expediente_id(self):
        r = _make_result()
        self.assertIn("EIA-TEST", r.summary())

    def test_summary_contains_counts(self):
        r = _make_result(ready=["A"], partial=["B"], missing=["C"])
        s = r.summary()
        self.assertIn("1 READY", s)
        self.assertIn("1 PARTIAL", s)
        self.assertIn("1 MISSING", s)


# ---------------------------------------------------------------------------
# 3. build_document_manifest
# ---------------------------------------------------------------------------

class TestBuildDocumentManifest(unittest.TestCase):

    def test_nonexistent_expediente_raises(self):
        with self.assertRaises(FileNotFoundError):
            build_document_manifest("/ruta/que/no/existe")

    def test_empty_expediente_has_11_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-EMPTY"
            exp.mkdir()
            result = build_document_manifest(exp)
            self.assertEqual(len(result.manifest_items), 11)

    def test_empty_expediente_all_missing_or_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-EMPTY"
            exp.mkdir()
            result = build_document_manifest(exp)
            # All blocks should be MISSING or PARTIAL (no files exist)
            for item in result.manifest_items:
                self.assertIn(item.status, ("MISSING", "PARTIAL"))

    def test_empty_expediente_no_ready_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-EMPTY"
            exp.mkdir()
            result = build_document_manifest(exp)
            self.assertEqual(result.ready_count(), 0)

    def test_with_pipeline_outputs_several_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            # At least some blocks should be READY
            self.assertGreater(result.ready_count(), 0)

    def test_with_pipeline_outputs_b_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            b_item = next(i for i in result.manifest_items if i.block_id == "B")
            self.assertEqual(b_item.status, "READY")

    def test_with_pipeline_outputs_c_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            c_item = next(i for i in result.manifest_items if i.block_id == "C")
            self.assertEqual(c_item.status, "READY")

    def test_with_pipeline_outputs_d_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            d_item = next(i for i in result.manifest_items if i.block_id == "D")
            self.assertEqual(d_item.status, "READY")

    def test_with_pipeline_outputs_e_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            e_item = next(i for i in result.manifest_items if i.block_id == "E")
            self.assertEqual(e_item.status, "READY")

    def test_existing_bloques_markdown_make_manifest_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, [
                "bloques/A_identificacion_y_descripcion.md",
                "bloques/B_inventario_ambiental.md",
                "bloques/C_impactos.md",
                "bloques/D_medidas.md",
                "bloques/E_PVA.md",
                "bloques/F_alternativas.md",
                "bloques/G_vulnerabilidad.md",
                "bloques/H_red_natura_2000.md",
                "bloques/I_conclusiones.md",
                "bloques/J_resumen_no_tecnico.md",
                "bloques/K_referencias.md",
            ])
            result = build_document_manifest(exp)
            self.assertEqual(result.ready_count(), 11)
            self.assertEqual(result.missing_count(), 0)

    def test_block_f_g_titles_follow_ag10_convention(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            result = build_document_manifest(exp)
            titles = {i.block_id: i.title for i in result.manifest_items}
            self.assertIn("Alternativas", titles["F"])
            self.assertIn("Vulnerabilidad", titles["G"])

    def test_partial_when_some_files_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Only inventory files, no impactos
            exp = _build_expediente_with_files(tmp, [
                "inventario/inventory_summary.json",
                "inventario/phase5_gate_result.json",
            ])
            result = build_document_manifest(exp)
            b_item = next(i for i in result.manifest_items if i.block_id == "B")
            self.assertEqual(b_item.status, "READY")
            # Block C needs impactos files which don't exist
            c_item = next(i for i in result.manifest_items if i.block_id == "C")
            self.assertEqual(c_item.status, "MISSING")

    def test_does_not_raise_for_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            # Should not raise even though no files exist
            try:
                result = build_document_manifest(exp)
            except Exception as exc:
                self.fail(f"build_document_manifest raised unexpectedly: {exc}")
            self.assertIsInstance(result, DocumentManifestResult)

    def test_does_not_modify_expediente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            files_before = list(exp.iterdir())
            build_document_manifest(exp)
            files_after = list(exp.iterdir())
            self.assertEqual(files_before, files_after)

    def test_result_has_11_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            result = build_document_manifest(exp)
            self.assertEqual(len(result.manifest_items), 11)

    def test_block_ids_a_to_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            result = build_document_manifest(exp)
            ids = [i.block_id for i in result.manifest_items]
            for block_id in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"):
                self.assertIn(block_id, ids)

    def test_expediente_id_is_dirname(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-2026-PRUEBA"
            exp.mkdir()
            result = build_document_manifest(exp)
            self.assertEqual(result.expediente_id, "EIA-2026-PRUEBA")

    def test_is_not_ready_for_empty_expediente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            result = build_document_manifest(exp)
            self.assertFalse(result.is_ready_for_markdown_generation())

    def test_with_all_outputs_is_ready_for_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            # With all pipeline outputs, no block should be MISSING
            self.assertTrue(result.is_ready_for_markdown_generation())


# ---------------------------------------------------------------------------
# 4. build_document_manifest_markdown
# ---------------------------------------------------------------------------

class TestBuildDocumentManifestMarkdown(unittest.TestCase):

    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            result = build_document_manifest(exp)
            self.md = build_document_manifest_markdown(result)
        with tempfile.TemporaryDirectory() as tmp:
            exp_empty = Path(tmp) / "EIA-EMPTY"
            exp_empty.mkdir()
            result_empty = build_document_manifest(exp_empty)
            self.md_empty = build_document_manifest_markdown(result_empty)

    def test_contains_title(self):
        self.assertIn("Manifest del Documento Ambiental", self.md)

    def test_contains_block_a(self):
        self.assertIn("Bloque A", self.md)

    def test_contains_block_k(self):
        self.assertIn("Bloque K", self.md)

    def test_contains_all_11_blocks(self):
        for block_id in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"):
            self.assertIn(f"| {block_id} |", self.md)

    def test_contains_resumen_section(self):
        self.assertIn("## 1. Resumen", self.md)

    def test_contains_estado_por_bloque_section(self):
        self.assertIn("## 2. Estado por bloque", self.md)

    def test_contains_archivos_faltantes_section(self):
        self.assertIn("## 4. Archivos faltantes", self.md)

    def test_contains_advertencia_no_aptitud(self):
        md_lower = self.md.lower()
        self.assertIn("no declara aptitud administrativa", md_lower)

    def test_contains_siguiente_paso(self):
        self.assertIn("## 6. Siguiente paso recomendado", self.md)

    def test_empty_expediente_shows_missing(self):
        self.assertIn("MISSING", self.md_empty)

    def test_full_expediente_shows_ready(self):
        self.assertIn("READY", self.md)

    def test_no_generate_docx_disclaimer(self):
        md_lower = self.md.lower()
        self.assertIn("no genera el documento final", md_lower)

    def test_is_string(self):
        self.assertIsInstance(self.md, str)
        self.assertGreater(len(self.md), 200)


# ---------------------------------------------------------------------------
# 5. write_document_manifest_outputs
# ---------------------------------------------------------------------------

class TestWriteDocumentManifestOutputs(unittest.TestCase):

    def _make_result(self) -> DocumentManifestResult:
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST"
            exp.mkdir()
            return build_document_manifest(exp)

    def test_creates_json_and_md(self):
        result = self._make_result()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "documento"
            json_p, md_p = write_document_manifest_outputs(result, out)
            self.assertTrue(json_p.exists())
            self.assertTrue(md_p.exists())
            self.assertEqual(json_p.name, "document_manifest.json")
            self.assertEqual(md_p.name, "document_manifest.md")

    def test_json_is_loadable(self):
        result = self._make_result()
        with tempfile.TemporaryDirectory() as tmp:
            json_p, _ = write_document_manifest_outputs(result, Path(tmp))
            data = json.loads(json_p.read_text(encoding="utf-8"))
            self.assertIn("expediente_id", data)
            self.assertIn("manifest_items", data)
            self.assertIn("administrative_ready", data)

    def test_json_administrative_ready_false(self):
        result = self._make_result()
        with tempfile.TemporaryDirectory() as tmp:
            json_p, _ = write_document_manifest_outputs(result, Path(tmp))
            data = json.loads(json_p.read_text(encoding="utf-8"))
            self.assertFalse(data["administrative_ready"])

    def test_output_dir_created_if_missing(self):
        result = self._make_result()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new" / "documento"
            self.assertFalse(out.exists())
            write_document_manifest_outputs(result, out)
            self.assertTrue(out.exists())

    def test_md_matches_build(self):
        result = self._make_result()
        expected = build_document_manifest_markdown(result)
        with tempfile.TemporaryDirectory() as tmp:
            _, md_p = write_document_manifest_outputs(result, Path(tmp))
            self.assertEqual(md_p.read_text(encoding="utf-8"), expected)


# ---------------------------------------------------------------------------
# 6. CLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def _run_cli(self, exp_path: Path, extra_args: list[str] | None = None) -> int:
        from run_expediente import main as cli_main
        backup = sys.argv[:]
        args = ["run_expediente.py", str(exp_path), "document-manifest"]
        if extra_args:
            args.extend(extra_args)
        sys.argv = args
        try:
            return cli_main()
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0
        finally:
            sys.argv = backup

    def test_exit_1_with_missing_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-EMPTY"
            exp.mkdir()
            code = self._run_cli(exp)
            self.assertEqual(code, 1)

    def test_exit_0_all_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            code = self._run_cli(exp)
            self.assertEqual(code, 0)

    def test_without_write_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-EMPTY"
            exp.mkdir()
            self._run_cli(exp)
            doc_dir = exp / "documento"
            self.assertFalse((doc_dir / "document_manifest.json").exists())

    def test_with_write_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _build_expediente_with_files(tmp, _pipeline_outputs())
            self._run_cli(exp, extra_args=["--write"])
            doc_dir = exp / "documento"
            self.assertTrue((doc_dir / "document_manifest.json").exists())
            self.assertTrue((doc_dir / "document_manifest.md").exists())

    def test_nonexistent_expediente_exit_1(self):
        code = self._run_cli(Path("/ruta/que/no/existe"))
        self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

class TestConstants(unittest.TestCase):

    def test_document_blocks_has_11_entries(self):
        self.assertEqual(len(DOCUMENT_BLOCKS), 11)

    def test_block_ids_are_a_to_k(self):
        ids = [b[0] for b in DOCUMENT_BLOCKS]
        for expected_id in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"):
            self.assertIn(expected_id, ids)

    def test_required_inputs_has_11_blocks(self):
        self.assertEqual(len(DOCUMENT_REQUIRED_INPUTS), 11)

    def test_required_uses_correct_conesa_filename(self):
        # Must use phase6_model_with_conesa.json, NOT phase6_model_scored.json
        for block_id, files in DOCUMENT_REQUIRED_INPUTS.items():
            for f in files:
                self.assertNotIn("scored", f, msg=f"Block {block_id} has wrong filename: {f}")

    def test_manifest_status_values(self):
        for s in ("READY", "PARTIAL", "MISSING"):
            self.assertIn(s, MANIFEST_STATUS)


if __name__ == "__main__":
    unittest.main()
