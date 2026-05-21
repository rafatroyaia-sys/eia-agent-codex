"""
tests/test_document_markdown_builder.py
Tests para DOC-01 — Generador Markdown del Documento Ambiental.

Cubre:
  1. Dataclasses DocumentBlockBuildResult y DocumentMarkdownBuildResult
  2. Helpers: safe_read_text, safe_load_json, format_missing_notice
  3. assemble_document_markdown: portada, advertencia, indice, orden A-K
  4. Builders bloque A-K: sin expediente, con expediente vacio, fuentes minimas
  5. build_document_markdown: write/no-write, expediente vacio, con outputs
  6. Bloque J: frases prohibidas
  7. CLI document-build-md: sin/con --write, exit codes
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.document_markdown_builder import (
    BLOCK_ORDER,
    DOCUMENT_BUILD_RESULT_FILENAME,
    DOCUMENT_OUTPUT_FILENAME,
    DocumentBlockBuildResult,
    DocumentMarkdownBuildResult,
    assemble_document_markdown,
    build_block_a,
    build_block_b,
    build_block_c,
    build_block_d,
    build_block_e,
    build_block_f,
    build_block_g,
    build_block_h,
    build_block_i,
    build_block_j,
    build_block_k,
    build_document_markdown,
    format_missing_notice,
    safe_load_json,
    safe_read_text,
)


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------

def _make_block(
    block_id: str = "A",
    title: str = "Test Block",
    status: str = "GENERATED",
    source_files: list | None = None,
    missing_files: list | None = None,
    markdown: str = "## Bloque A\nContenido de prueba.\n",
    warnings: list | None = None,
    notes: list | None = None,
) -> DocumentBlockBuildResult:
    return DocumentBlockBuildResult(
        block_id=block_id,
        title=title,
        status=status,
        source_files=source_files or ["inventario/test.json"],
        missing_files=missing_files or [],
        markdown=markdown,
        warnings=warnings or [],
        notes=notes or [],
    )


def _make_result(
    generated: list | None = None,
    partial: list | None = None,
    missing: list | None = None,
    blocks: list | None = None,
) -> DocumentMarkdownBuildResult:
    return DocumentMarkdownBuildResult(
        expediente_id="TEST-EXP",
        generated_blocks=generated or [],
        partial_blocks=partial or [],
        missing_blocks=missing or [],
        blocks=blocks or [],
    )


def _empty_expediente(tmp: Path) -> Path:
    """Crea expediente vacio (solo el directorio)."""
    exp = tmp / "expediente-test"
    exp.mkdir()
    return exp


def _minimal_expediente(tmp: Path) -> Path:
    """Crea expediente con un conjunto minimo de outputs JSON."""
    exp = tmp / "expediente-minimal"
    exp.mkdir()

    # inventario/
    inv_dir = exp / "inventario"
    inv_dir.mkdir()
    inv_summary = {
        "expediente_id": "TEST",
        "factor_count": 2,
        "factors": [
            {
                "factor_id": "FI-001",
                "name": "Clima",
                "inventory_semaphore": "VERDE",
                "evidence_state": "CONFIRMADO_GABINETE",
                "gaps": [],
            },
            {
                "factor_id": "FI-009",
                "name": "ENP",
                "inventory_semaphore": "AMARILLO",
                "evidence_state": "ESTIMADO",
                "gaps": [
                    {
                        "gap_id": "GAP-FI-009-001",
                        "factor_id": "FI-009",
                        "criticality": "ALTA",
                        "resolution_mode": "GABINETE",
                    }
                ],
            },
        ],
    }
    (inv_dir / "inventory_summary.json").write_text(
        json.dumps(inv_summary, ensure_ascii=False), encoding="utf-8"
    )
    phase5_gate = {
        "decision": "APTO_FASE6_CON_CAUTELAS",
        "total_issues": 2,
        "issues": [
            {"severity": "WARNING", "message": "Gap ALTA en FI-009"},
        ],
    }
    (inv_dir / "phase5_gate_result.json").write_text(
        json.dumps(phase5_gate, ensure_ascii=False), encoding="utf-8"
    )

    # impactos/
    imp_dir = exp / "impactos"
    imp_dir.mkdir()
    phase6_actions = {
        "actions": [
            {
                "action_id": "AC-001",
                "name": "Recepcion de residuos",
                "description": "Recepcion y clasificacion inicial",
                "action_type": "RECEPCION_CLASIFICACION",
            }
        ]
    }
    (imp_dir / "phase6_actions.json").write_text(
        json.dumps(phase6_actions, ensure_ascii=False), encoding="utf-8"
    )

    conesa_model = {
        "expediente_id": "TEST",
        "actions": [],
        "receptor_factors": [],
        "impacts": [
            {
                "impact_id": "IMP-001",
                "action_id": "AC-001",
                "receptor_id": "FR-003",
                "name": "Contaminacion de suelos",
                "nature": "NEGATIVO",
                "status": "PENDIENTE_DATOS",
                "significance_without_measures": "MODERADO",
                "significance_with_measures": "NO_VALORADO",
                "conesa_attributes": {
                    "intensidad": 1,
                    "extension": 1,
                    "momento": 1,
                    "persistencia": 1,
                    "reversibilidad": 1,
                    "sinergia": 1,
                    "acumulacion": 1,
                    "efecto": 1,
                    "periodicidad": 1,
                    "recuperabilidad": 1,
                    "conesa_score": 25,
                    "conesa_classification": "MODERADO",
                },
                "data_gaps": [],
                "measure_ids": [],
                "pva_ids": [],
                "warnings": [],
                "notes": [],
            }
        ],
        "measures": [],
        "pva_programs": [],
        "warnings": [],
        "notes": [],
    }
    (imp_dir / "phase6_model_with_conesa.json").write_text(
        json.dumps(conesa_model, ensure_ascii=False), encoding="utf-8"
    )
    (imp_dir / "phase6_model_with_impacts.json").write_text(
        json.dumps(conesa_model, ensure_ascii=False), encoding="utf-8"
    )

    measures_model = dict(conesa_model)
    measures_model["measures"] = [
        {
            "measure_id": "MEA-001",
            "name": "Cubeto de retencion",
            "description": "Instalacion de cubeto de retencion",
            "measure_type": "PREVENTIVA",
            "status": "PROPUESTA",
            "target_impact_ids": ["IMP-001"],
            "is_diagnostic": False,
            "is_prl_only": False,
            "condition_before_submission": False,
            "warnings": [],
            "notes": [],
        }
    ]
    (imp_dir / "phase6_model_with_measures.json").write_text(
        json.dumps(measures_model, ensure_ascii=False), encoding="utf-8"
    )

    pva_model = dict(measures_model)
    pva_model["pva_programs"] = [
        {
            "pva_id": "PVA-001",
            "name": "Vigilancia suelos",
            "receptor_id": "FR-003",
            "frequency": "SEMESTRAL",
            "status": "PROPUESTO",
            "conditioned": False,
        }
    ]
    (imp_dir / "phase6_model_with_pva.json").write_text(
        json.dumps(pva_model, ensure_ascii=False), encoding="utf-8"
    )

    pva_coverage = {
        "covered_count": 1,
        "uncovered_count": 0,
        "is_valid": True,
        "issues": [],
    }
    (imp_dir / "pva_coverage_result.json").write_text(
        json.dumps(pva_coverage, ensure_ascii=False), encoding="utf-8"
    )

    cumul = {
        "cumulative_groups": [{"group_id": "CG-001", "impacts": ["IMP-001"]}],
        "synergistic_groups": [],
        "unresolved_gaps": [],
    }
    (imp_dir / "cumulative_synergistic_result.json").write_text(
        json.dumps(cumul, ensure_ascii=False), encoding="utf-8"
    )
    (imp_dir / "C5_acumulativos_sinergicos.md").write_text(
        "## C.5 Acumulativos\nTexto de prueba.", encoding="utf-8"
    )

    # auditoria/
    aud_dir = exp / "auditoria"
    aud_dir.mkdir()
    audit_result = {
        "status": "CONFORME_CON_OBSERVACIONES",
        "issues": [
            {"severity": "MEDIA", "code": "AU02-W001", "message": "Aviso de prueba"},
        ],
        "administrative_ready": False,
    }
    (aud_dir / "final_audit_result.json").write_text(
        json.dumps(audit_result, ensure_ascii=False), encoding="utf-8"
    )
    conesa_check = {"is_valid": True, "issues": []}
    (aud_dir / "conesa_check_result.json").write_text(
        json.dumps(conesa_check, ensure_ascii=False), encoding="utf-8"
    )
    diag_val = {"is_valid": True, "issues": []}
    (aud_dir / "diagnostic_measure_validation_result.json").write_text(
        json.dumps(diag_val, ensure_ascii=False), encoding="utf-8"
    )
    prl_val = {"is_valid": True, "issues": []}
    (aud_dir / "prl_measure_validation_result.json").write_text(
        json.dumps(prl_val, ensure_ascii=False), encoding="utf-8"
    )
    consistency = {"is_valid": True, "issues": []}
    (aud_dir / "block_consistency_result.json").write_text(
        json.dumps(consistency, ensure_ascii=False), encoding="utf-8"
    )

    # capas/
    capas_dir = exp / "capas"
    capas_dir.mkdir()
    hechos = {"expediente_id": "TEST", "hechos": []}
    (capas_dir / "hechos_confirmados.json").write_text(
        json.dumps(hechos, ensure_ascii=False), encoding="utf-8"
    )
    normativa = {"items": []}
    (capas_dir / "normativa_aplicable.json").write_text(
        json.dumps(normativa, ensure_ascii=False), encoding="utf-8"
    )

    # control_interno/
    ci_dir = exp / "control_interno"
    ci_dir.mkdir()
    phase2 = {
        "expediente_id": "TEST",
        "scope": {
            "promotor": "Empresa de Prueba S.L.",
            "actividad": "Gestion de residuos",
            "coordenadas": {"latitud": "28.1234", "longitud": "-15.5678"},
            "referencia_catastral": "12345A00100001",
            "modo": "GABINETE",
        },
    }
    (ci_dir / "phase2_result.json").write_text(
        json.dumps(phase2, ensure_ascii=False), encoding="utf-8"
    )

    # inputs/
    inp_dir = exp / "inputs"
    inp_dir.mkdir()
    (inp_dir / "memoria.docx").write_bytes(b"fake docx")

    # clima/
    clima_dir = exp / "clima"
    clima_dir.mkdir()
    (clima_dir / "climograma.png").write_bytes(b"fake png")

    return exp


class _FakeManifestItem:
    """Item de manifest falso para tests de builders."""

    def __init__(
        self,
        block_id: str = "A",
        title: str = "Test",
        status: str = "READY",
        missing_files: list | None = None,
    ) -> None:
        self.block_id = block_id
        self.title = title
        self.status = status
        self.missing_files = missing_files or []


# ---------------------------------------------------------------------------
# 1. Tests de DocumentBlockBuildResult
# ---------------------------------------------------------------------------

class TestDocumentBlockBuildResult(unittest.TestCase):

    def test_to_dict_keys(self):
        b = _make_block()
        d = b.to_dict()
        self.assertIn("block_id", d)
        self.assertIn("title", d)
        self.assertIn("status", d)
        self.assertIn("source_files", d)
        self.assertIn("missing_files", d)
        self.assertIn("markdown_length", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_to_dict_values(self):
        b = _make_block(block_id="C", status="PARTIAL")
        d = b.to_dict()
        self.assertEqual(d["block_id"], "C")
        self.assertEqual(d["status"], "PARTIAL")

    def test_to_dict_markdown_not_included(self):
        b = _make_block(markdown="## Bloque\nLargo texto.\n")
        d = b.to_dict()
        self.assertNotIn("markdown", d)
        self.assertGreater(d["markdown_length"], 0)

    def test_summary_format(self):
        b = _make_block(block_id="B", title="Inventario ambiental", status="GENERATED")
        s = b.summary()
        self.assertIn("B", s)
        self.assertIn("GENERATED", s)
        self.assertIn("Inventario ambiental", s)

    def test_summary_missing(self):
        b = _make_block(status="MISSING", source_files=[])
        s = b.summary()
        self.assertIn("MISSING", s)

    def test_all_statuses_valid(self):
        for status in ("GENERATED", "PARTIAL", "MISSING", "SKIPPED"):
            b = _make_block(status=status)
            self.assertEqual(b.status, status)


# ---------------------------------------------------------------------------
# 2. Tests de DocumentMarkdownBuildResult
# ---------------------------------------------------------------------------

class TestDocumentMarkdownBuildResult(unittest.TestCase):

    def test_generated_count(self):
        r = _make_result(generated=["A", "B", "C"])
        self.assertEqual(r.generated_count(), 3)

    def test_partial_count(self):
        r = _make_result(partial=["D", "E"])
        self.assertEqual(r.partial_count(), 2)

    def test_missing_count(self):
        r = _make_result(missing=["F", "G", "H"])
        self.assertEqual(r.missing_count(), 3)

    def test_is_complete_draft_no_missing(self):
        r = _make_result(generated=["A", "B"], partial=["C"])
        self.assertTrue(r.is_complete_draft())

    def test_is_complete_draft_with_missing(self):
        r = _make_result(generated=["A"], missing=["B"])
        self.assertFalse(r.is_complete_draft())

    def test_is_complete_draft_all_missing(self):
        r = _make_result(missing=["A", "B", "C"])
        self.assertFalse(r.is_complete_draft())

    def test_to_dict_keys(self):
        r = _make_result(generated=["A"], partial=["B"], missing=["C"])
        d = r.to_dict()
        for key in (
            "expediente_id", "output_markdown_path",
            "generated_count", "partial_count", "missing_count",
            "is_complete_draft", "generated_blocks", "partial_blocks",
            "missing_blocks", "blocks", "warnings", "notes",
        ):
            self.assertIn(key, d)

    def test_to_dict_counts_consistent(self):
        r = _make_result(
            generated=["A", "B"],
            partial=["C"],
            missing=["D"],
        )
        d = r.to_dict()
        self.assertEqual(d["generated_count"], 2)
        self.assertEqual(d["partial_count"], 1)
        self.assertEqual(d["missing_count"], 1)
        self.assertFalse(d["is_complete_draft"])

    def test_summary_completado(self):
        r = _make_result(generated=list("ABCDEFGHIJK"))
        s = r.summary()
        self.assertIn("BORRADOR COMPLETO", s)

    def test_summary_incompleto(self):
        r = _make_result(generated=["A"], missing=["B"])
        s = r.summary()
        self.assertIn("BORRADOR INCOMPLETO", s)

    def test_no_administrative_ready(self):
        r = _make_result()
        d = r.to_dict()
        # No debe haber campo administrative_ready = True
        self.assertNotIn("administrative_ready", d)


# ---------------------------------------------------------------------------
# 3. Tests de helpers
# ---------------------------------------------------------------------------

class TestSafeReadText(unittest.TestCase):

    def test_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("hola", encoding="utf-8")
            result = safe_read_text(p)
            self.assertEqual(result, "hola")

    def test_nonexistent_file(self):
        result = safe_read_text("/ruta/que/no/existe/archivo.txt")
        self.assertIsNone(result)

    def test_string_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("texto", encoding="utf-8")
            result = safe_read_text(str(p))
            self.assertEqual(result, "texto")


class TestSafeLoadJson(unittest.TestCase):

    def test_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            p.write_text('{"key": "value"}', encoding="utf-8")
            result = safe_load_json(p)
            self.assertEqual(result, {"key": "value"})

    def test_nonexistent_file(self):
        result = safe_load_json("/ruta/no/existe.json")
        self.assertIsNone(result)

    def test_corrupted_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text("{bad json content", encoding="utf-8")
            result = safe_load_json(p)
            self.assertIsNone(result)

    def test_list_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "list.json"
            p.write_text('[1, 2, 3]', encoding="utf-8")
            result = safe_load_json(p)
            self.assertEqual(result, [1, 2, 3])

    def test_string_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            p.write_text('{"x": 1}', encoding="utf-8")
            result = safe_load_json(str(p))
            self.assertEqual(result, {"x": 1})


class TestFormatMissingNotice(unittest.TestCase):

    def test_contains_aviso(self):
        notice = format_missing_notice("A", ["file1.json", "file2.json"])
        self.assertIn("AVISO", notice)
        self.assertIn("Bloque A", notice)

    def test_contains_missing_files(self):
        notice = format_missing_notice("B", ["inventario/test.json", "auditoria/audit.json"])
        self.assertIn("inventario/test.json", notice)
        self.assertIn("auditoria/audit.json", notice)

    def test_empty_list_returns_empty(self):
        notice = format_missing_notice("C", [])
        self.assertEqual(notice, "")

    def test_includes_block_id(self):
        notice = format_missing_notice("H", ["some_file.json"])
        self.assertIn("H", notice)


# ---------------------------------------------------------------------------
# 4. Tests de assemble_document_markdown
# ---------------------------------------------------------------------------

class TestAssembleDocumentMarkdown(unittest.TestCase):

    def _make_all_blocks(self, status: str = "GENERATED") -> list[DocumentBlockBuildResult]:
        blocks = []
        for bid in BLOCK_ORDER:
            blocks.append(_make_block(
                block_id=bid,
                title=f"Titulo bloque {bid}",
                status=status,
                markdown=f"## Bloque {bid} — Titulo\nContenido {bid}.\n",
            ))
        return blocks

    def test_contains_portada(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        self.assertIn("Documento Ambiental", md)
        self.assertIn("Borrador tecnico", md)

    def test_contains_admin_disclaimer(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        self.assertIn("aptitud administrativa", md)
        self.assertIn("revision tecnica", md)

    def test_contains_indice(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        self.assertIn("Indice", md)

    def test_indice_contains_all_blocks(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        for bid in BLOCK_ORDER:
            self.assertIn(f"Bloque {bid}", md)

    def test_order_a_to_k(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        positions = {}
        for bid in BLOCK_ORDER:
            pos = md.find(f"## Bloque {bid} —")
            self.assertGreater(pos, -1, f"Bloque {bid} no encontrado en markdown")
            positions[bid] = pos
        # Verificar orden
        for i in range(len(BLOCK_ORDER) - 1):
            a = BLOCK_ORDER[i]
            b = BLOCK_ORDER[i + 1]
            self.assertLess(
                positions[a], positions[b],
                f"Bloque {a} deberia aparecer antes que Bloque {b}"
            )

    def test_missing_block_marked(self):
        blocks = self._make_all_blocks()
        # Reemplazar un bloque con MISSING
        for i, b in enumerate(blocks):
            if b.block_id == "C":
                blocks[i] = _make_block(
                    block_id="C",
                    status="MISSING",
                    source_files=[],
                    missing_files=["impactos/test.json"],
                    markdown="",
                )
        md = assemble_document_markdown(blocks)
        self.assertIn("MISSING", md)

    def test_partial_blocks_warned(self):
        blocks = self._make_all_blocks()
        for i, b in enumerate(blocks):
            if b.block_id == "G":
                blocks[i] = _make_block(
                    block_id="G",
                    status="PARTIAL",
                    missing_files=["capas/alternativas.json"],
                )
        md = assemble_document_markdown(blocks)
        self.assertIn("PARTIAL", md)

    def test_no_administrative_declaration(self):
        blocks = self._make_all_blocks()
        md = assemble_document_markdown(blocks)
        # La advertencia dice "No declara aptitud administrativa"
        self.assertIn("No declara aptitud administrativa", md)

    def test_empty_blocks_list(self):
        md = assemble_document_markdown([])
        self.assertIn("Documento Ambiental", md)


# ---------------------------------------------------------------------------
# 5. Tests de builders A-K (expediente vacío)
# ---------------------------------------------------------------------------

class TestBuildBlocksEmptyExpediente(unittest.TestCase):
    """Cada builder no lanza excepción con expediente vacío."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp_path = Path(self.tmp) / "exp-vacio"
        self.exp_path.mkdir()
        self.manifest_item = _FakeManifestItem(missing_files=["some_file.json"])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _test_builder_no_exception(self, builder, block_id):
        item = _FakeManifestItem(block_id=block_id)
        result = builder(self.exp_path, item)
        self.assertIsNotNone(result)
        self.assertEqual(result.block_id, block_id)
        self.assertIn(result.status, ("GENERATED", "PARTIAL", "MISSING", "SKIPPED"))
        self.assertIsInstance(result.markdown, str)

    def test_block_a_empty(self):
        self._test_builder_no_exception(build_block_a, "A")

    def test_block_b_empty(self):
        self._test_builder_no_exception(build_block_b, "B")

    def test_block_c_empty(self):
        self._test_builder_no_exception(build_block_c, "C")

    def test_block_d_empty(self):
        self._test_builder_no_exception(build_block_d, "D")

    def test_block_e_empty(self):
        self._test_builder_no_exception(build_block_e, "E")

    def test_block_f_empty(self):
        self._test_builder_no_exception(build_block_f, "F")

    def test_block_g_empty(self):
        self._test_builder_no_exception(build_block_g, "G")

    def test_block_h_empty(self):
        self._test_builder_no_exception(build_block_h, "H")

    def test_block_i_empty(self):
        self._test_builder_no_exception(build_block_i, "I")

    def test_block_j_empty(self):
        self._test_builder_no_exception(build_block_j, "J")

    def test_block_k_empty(self):
        self._test_builder_no_exception(build_block_k, "K")


class TestBuildBlocksStatusWithEmpty(unittest.TestCase):
    """Cada builder devuelve MISSING o PARTIAL cuando faltan fuentes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp_path = Path(self.tmp) / "exp-vacio"
        self.exp_path.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _assert_missing_or_partial(self, builder, block_id):
        item = _FakeManifestItem(block_id=block_id, missing_files=["some_file.json"])
        result = builder(self.exp_path, item)
        self.assertIn(result.status, ("MISSING", "PARTIAL"),
                     f"Bloque {block_id} deberia ser MISSING o PARTIAL con expediente vacio")

    def test_a_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_a, "A")

    def test_b_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_b, "B")

    def test_c_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_c, "C")

    def test_d_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_d, "D")

    def test_e_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_e, "E")

    def test_f_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_f, "F")

    def test_g_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_g, "G")

    def test_h_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_h, "H")

    def test_i_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_i, "I")

    def test_j_missing_or_partial(self):
        self._assert_missing_or_partial(build_block_j, "J")

    def test_k_missing_or_partial(self):
        # K con expediente vacio: no hay directorios, MISSING
        item = _FakeManifestItem(block_id="K", missing_files=["inputs"])
        result = build_block_k(self.exp_path, item)
        self.assertIn(result.status, ("MISSING", "PARTIAL"))


class TestBuildBlocksWithMinimalSources(unittest.TestCase):
    """Builders con fuentes mínimas devuelven GENERATED o PARTIAL."""

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)
        self.exp_path = _minimal_expediente(self.tmp)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def test_block_a_generated_or_partial(self):
        item = _FakeManifestItem("A")
        result = build_block_a(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))
        self.assertGreater(len(result.source_files), 0)

    def test_block_b_generated_or_partial(self):
        item = _FakeManifestItem("B")
        result = build_block_b(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))
        self.assertGreater(len(result.source_files), 0)

    def test_block_c_generated_or_partial(self):
        item = _FakeManifestItem("C")
        result = build_block_c(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_d_generated_or_partial(self):
        item = _FakeManifestItem("D")
        result = build_block_d(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_e_generated_or_partial(self):
        item = _FakeManifestItem("E")
        result = build_block_e(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_f_generated_or_partial(self):
        item = _FakeManifestItem("F")
        result = build_block_f(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_g_partial_no_alternatives(self):
        # G tipicamente PARTIAL en modo gabinete sin datos de alternativas
        item = _FakeManifestItem("G")
        result = build_block_g(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_h_generated_or_partial(self):
        item = _FakeManifestItem("H")
        result = build_block_h(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_i_generated_or_partial(self):
        item = _FakeManifestItem("I")
        result = build_block_i(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_j_generated_or_partial(self):
        item = _FakeManifestItem("J")
        result = build_block_j(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))

    def test_block_k_generated_or_partial(self):
        item = _FakeManifestItem("K")
        result = build_block_k(self.exp_path, item)
        self.assertIn(result.status, ("GENERATED", "PARTIAL"))
        self.assertGreater(len(result.source_files), 0)

    def test_no_invented_data_block_a(self):
        item = _FakeManifestItem("A")
        result = build_block_a(self.exp_path, item)
        # El promotor debe aparecer
        self.assertIn("Empresa de Prueba", result.markdown)

    def test_no_invented_data_block_b(self):
        item = _FakeManifestItem("B")
        result = build_block_b(self.exp_path, item)
        # FI-001 y FI-009 deben aparecer
        self.assertIn("FI-001", result.markdown)

    def test_blocks_have_markdown_content(self):
        builders_items = [
            (build_block_a, "A"), (build_block_b, "B"), (build_block_c, "C"),
            (build_block_d, "D"), (build_block_e, "E"), (build_block_f, "F"),
            (build_block_g, "G"), (build_block_h, "H"), (build_block_i, "I"),
            (build_block_j, "J"), (build_block_k, "K"),
        ]
        for builder, bid in builders_items:
            item = _FakeManifestItem(bid)
            result = builder(self.exp_path, item)
            self.assertGreater(
                len(result.markdown), 10,
                f"Bloque {bid} deberia tener contenido markdown"
            )


# ---------------------------------------------------------------------------
# 6. Tests de build_document_markdown
# ---------------------------------------------------------------------------

class TestBuildDocumentMarkdown(unittest.TestCase):

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def test_empty_expediente_returns_result(self):
        exp = _empty_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        self.assertIsNotNone(result)
        self.assertEqual(result.expediente_id, exp.name)

    def test_empty_expediente_has_missing_blocks(self):
        exp = _empty_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        self.assertGreater(result.missing_count(), 0)
        self.assertFalse(result.is_complete_draft())

    def test_write_false_no_files_created(self):
        exp = _empty_expediente(self.tmp)
        build_document_markdown(exp, write_outputs=False)
        doc_dir = exp / "documento"
        self.assertFalse(doc_dir.exists())

    def test_write_true_creates_md(self):
        exp = _minimal_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=True)
        md_path = exp / "documento" / DOCUMENT_OUTPUT_FILENAME
        self.assertTrue(md_path.exists())
        self.assertIsNotNone(result.output_markdown_path)

    def test_write_true_creates_json(self):
        exp = _minimal_expediente(self.tmp)
        build_document_markdown(exp, write_outputs=True)
        json_path = exp / "documento" / DOCUMENT_BUILD_RESULT_FILENAME
        self.assertTrue(json_path.exists())

    def test_write_true_json_loadable(self):
        exp = _minimal_expediente(self.tmp)
        build_document_markdown(exp, write_outputs=True)
        json_path = exp / "documento" / DOCUMENT_BUILD_RESULT_FILENAME
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("expediente_id", data)
        self.assertIn("blocks", data)
        self.assertIn("is_complete_draft", data)

    def test_no_other_dirs_modified(self):
        exp = _minimal_expediente(self.tmp)
        # Registrar estado previo de directorios no-documento
        inv_files_before = set(
            p.name for p in (exp / "inventario").iterdir()
        )
        imp_files_before = set(
            p.name for p in (exp / "impactos").iterdir()
        )
        build_document_markdown(exp, write_outputs=True)
        inv_files_after = set(
            p.name for p in (exp / "inventario").iterdir()
        )
        imp_files_after = set(
            p.name for p in (exp / "impactos").iterdir()
        )
        self.assertEqual(inv_files_before, inv_files_after)
        self.assertEqual(imp_files_before, imp_files_after)

    def test_minimal_expediente_has_blocks(self):
        exp = _minimal_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        self.assertEqual(len(result.blocks), 11)

    def test_minimal_expediente_no_output_path_without_write(self):
        exp = _minimal_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        self.assertIsNone(result.output_markdown_path)

    def test_blocks_list_has_all_ids(self):
        exp = _minimal_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        ids = {b.block_id for b in result.blocks}
        for bid in BLOCK_ORDER:
            self.assertIn(bid, ids)

    def test_write_creates_documento_dir_only(self):
        exp = _minimal_expediente(self.tmp)
        build_document_markdown(exp, write_outputs=True)
        doc_dir = exp / "documento"
        self.assertTrue(doc_dir.is_dir())
        # Solo documento/ debe haberse creado (no otros dirs nuevos)
        new_dirs = [
            d.name for d in exp.iterdir()
            if d.is_dir() and d.name not in (
                "inventario", "impactos", "auditoria", "capas",
                "control_interno", "inputs", "clima", "documento",
            )
        ]
        self.assertEqual(new_dirs, [])


# ---------------------------------------------------------------------------
# 7. Tests de Bloque J — Frases prohibidas
# ---------------------------------------------------------------------------

class TestBlockJFrasesProhibidas(unittest.TestCase):

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)
        self.exp_path = _minimal_expediente(self.tmp)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def _get_block_j_markdown(self) -> str:
        item = _FakeManifestItem("J")
        result = build_block_j(self.exp_path, item)
        return result.markdown.lower()

    def test_no_sin_afeccion(self):
        md = self._get_block_j_markdown()
        self.assertNotIn("sin afeccion", md)

    def test_no_apto_administrativamente(self):
        md = self._get_block_j_markdown()
        self.assertNotIn("apto administrativamente", md)

    def test_no_se_descarta(self):
        md = self._get_block_j_markdown()
        self.assertNotIn("se descarta", md)

    def test_no_todos_compatibles(self):
        md = self._get_block_j_markdown()
        self.assertNotIn("todos compatibles", md)

    def test_block_j_no_closes_indeterminate(self):
        # Usar tmpdir separado para evitar conflicto con setUp
        import tempfile as _tempfile
        import shutil as _shutil
        _tmp2 = _tempfile.mkdtemp()
        try:
            exp = _minimal_expediente(Path(_tmp2))
            conesa_path = exp / "impactos" / "phase6_model_with_conesa.json"
            data = json.loads(conesa_path.read_text(encoding="utf-8"))
            data["impacts"][0]["nature"] = "INDETERMINADO"
            data["impacts"][0]["significance_without_measures"] = "INDETERMINADO"
            conesa_path.write_text(json.dumps(data), encoding="utf-8")
            item = _FakeManifestItem("J")
            result = build_block_j(exp, item)
            # No debe cerrar el impacto INDETERMINADO
            self.assertNotIn("sin afeccion", result.markdown.lower())
            self.assertNotIn("descarta", result.markdown.lower())
        finally:
            _shutil.rmtree(_tmp2, ignore_errors=True)

    def test_block_j_contains_prudent_language(self):
        md = self._get_block_j_markdown()
        # Debe contener lenguaje prudente
        self.assertIn("no declara aptitud administrativa", md)


# ---------------------------------------------------------------------------
# 8. Tests CLI
# ---------------------------------------------------------------------------

class TestCLIDocumentBuildMd(unittest.TestCase):

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def _run_cli(self, args: list[str]) -> int:
        from run_expediente import main
        return main(args)

    def test_document_build_md_without_write_no_files(self):
        exp = _empty_expediente(self.tmp)
        rc = self._run_cli([str(exp), "document-build-md"])
        doc_dir = exp / "documento"
        # No debe crear documento/documento_ambiental_borrador.md
        self.assertFalse((doc_dir / DOCUMENT_OUTPUT_FILENAME).exists())

    def test_document_build_md_with_write_creates_md(self):
        exp = _minimal_expediente(self.tmp)
        self._run_cli([str(exp), "document-build-md", "--write"])
        md_path = exp / "documento" / DOCUMENT_OUTPUT_FILENAME
        self.assertTrue(md_path.exists())

    def test_document_build_md_with_write_creates_json(self):
        exp = _minimal_expediente(self.tmp)
        self._run_cli([str(exp), "document-build-md", "--write"])
        json_path = exp / "documento" / DOCUMENT_BUILD_RESULT_FILENAME
        self.assertTrue(json_path.exists())

    def test_exit_1_with_missing_blocks(self):
        exp = _empty_expediente(self.tmp)
        rc = self._run_cli([str(exp), "document-build-md"])
        self.assertEqual(rc, 1)

    def test_exit_0_if_no_missing(self):
        # Crear expediente con todos los archivos requeridos
        exp = _minimal_expediente(self.tmp)
        # Agregar archivos que aun puedan faltar para bloques MISSING
        # En minimal ya deben estar todos. Verificar.
        result = build_document_markdown(exp, write_outputs=False)
        if result.is_complete_draft():
            rc = self._run_cli([str(exp), "document-build-md"])
            self.assertEqual(rc, 0)
        else:
            # Si no es completo (bloques MISSING), exit debe ser 1
            rc = self._run_cli([str(exp), "document-build-md"])
            self.assertEqual(rc, 1)

    def test_partial_not_blocks_exit_0(self):
        # Crear expediente con algunos PARTIAL pero sin MISSING
        exp = _minimal_expediente(self.tmp)
        result = build_document_markdown(exp, write_outputs=False)
        if result.missing_count() == 0:
            rc = self._run_cli([str(exp), "document-build-md"])
            self.assertEqual(rc, 0)
        # Si hay MISSING no podemos testear exit 0 de forma determinista aqui

    def test_invalid_expediente_exit_1(self):
        rc = self._run_cli(["/ruta/no/existe", "document-build-md"])
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# 9. Tests adicionales: no inventar datos
# ---------------------------------------------------------------------------

class TestNoInventedData(unittest.TestCase):

    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)

    def tearDown(self):
        self.tmp_obj.cleanup()

    def test_block_a_shows_real_promotor(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("A")
        result = build_block_a(exp, item)
        self.assertIn("Empresa de Prueba", result.markdown)

    def test_block_a_shows_real_action(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("A")
        result = build_block_a(exp, item)
        self.assertIn("Recepcion de residuos", result.markdown)

    def test_block_b_shows_real_factor(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("B")
        result = build_block_b(exp, item)
        self.assertIn("Clima", result.markdown)

    def test_block_c_shows_real_impact(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("C")
        result = build_block_c(exp, item)
        self.assertIn("IMP-001", result.markdown)

    def test_block_d_shows_real_measure(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("D")
        result = build_block_d(exp, item)
        self.assertIn("MEA-001", result.markdown)

    def test_block_e_shows_pva(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("E")
        result = build_block_e(exp, item)
        self.assertIn("PVA-001", result.markdown)

    def test_block_i_shows_audit_status(self):
        exp = _minimal_expediente(self.tmp)
        item = _FakeManifestItem("I")
        result = build_block_i(exp, item)
        self.assertIn("CONFORME_CON_OBSERVACIONES", result.markdown)


# ---------------------------------------------------------------------------
# 10. Tests de constantes y estructura
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 11. Tests DOC-05 — visibilidad de auditoria final (bloques I y J)
# ---------------------------------------------------------------------------

class TestAuditVisibilityDOC05(unittest.TestCase):
    """Verifica que build_block_i y build_block_j reflejan el estado de auditoria."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _exp_with_audit(self, status: str) -> Path:
        """Expediente minimo con final_audit_result.json del status indicado."""
        exp = self.tmp / f"exp-{status.lower()}"
        exp.mkdir(parents=True, exist_ok=True)
        aud = exp / "auditoria"
        aud.mkdir(exist_ok=True)
        audit_data = {
            "status": status,
            "issues": [{"severity": "ALTA", "code": "X-001", "message": "Incidencia test"}],
            "administrative_ready": False,
        }
        (aud / "final_audit_result.json").write_text(
            json.dumps(audit_data, ensure_ascii=False), encoding="utf-8"
        )
        return exp

    # --- block I: NO_CONFORME ---

    def test_block_i_no_conforme_contains_phrase_with_space(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        # "NO CONFORME" con espacio → detectable por QC-E006
        self.assertIn("NO CONFORME", result.markdown)

    def test_block_i_no_conforme_contains_aviso_de_auditoria(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("AVISO DE AUDITORIA FINAL", result.markdown)

    def test_block_i_no_conforme_no_apto_phrase(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        md_lower = result.markdown.lower()
        # No debe haber declaracion afirmativa de aptitud
        self.assertNotIn("apto administrativamente", md_lower)
        self.assertNotIn("listo para presentar", md_lower)

    def test_block_i_no_conforme_mentions_tramite(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        # Debe mencionar la imposibilidad de tramitar o resolver incidencias
        md_lower = result.markdown.lower()
        self.assertTrue(
            "tramite" in md_lower or "incidencias" in md_lower,
            "El AVISO debe mencionar tramite o incidencias"
        )

    def test_block_i_no_conforme_no_prohibited_phrases(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        md_lower = result.markdown.lower()
        self.assertNotIn("apto para presentacion administrativa", md_lower)
        self.assertNotIn("listo para presentar", md_lower)

    def test_block_i_no_conforme_has_warning(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertTrue(len(result.warnings) > 0)

    # --- block I: CONFORME_CON_OBSERVACIONES ---

    def test_block_i_conforme_con_observaciones_has_aviso(self):
        exp = self._exp_with_audit("CONFORME_CON_OBSERVACIONES")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("observaciones", result.markdown.lower())

    def test_block_i_conforme_con_observaciones_status_visible(self):
        exp = self._exp_with_audit("CONFORME_CON_OBSERVACIONES")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("CONFORME_CON_OBSERVACIONES", result.markdown)

    # --- block I: INCOMPLETO ---

    def test_block_i_incompleto_has_aviso(self):
        exp = self._exp_with_audit("INCOMPLETO")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("INCOMPLETA", result.markdown)

    # --- block I: CONFORME ---

    def test_block_i_conforme_mentions_not_admin_equiv(self):
        exp = self._exp_with_audit("CONFORME")
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("no equivale a aptitud administrativa", result.markdown.lower())

    # --- block I: sin audit-final ---

    def test_block_i_no_audit_no_crash(self):
        exp = self.tmp / "exp-no-audit"
        exp.mkdir(parents=True, exist_ok=True)
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIsNotNone(result)
        self.assertIn("I", result.block_id)

    def test_block_i_no_audit_mentions_not_available(self):
        exp = self.tmp / "exp-no-audit2"
        exp.mkdir(parents=True, exist_ok=True)
        result = build_block_i(exp, _FakeManifestItem("I"))
        self.assertIn("No disponible", result.markdown)

    # --- block J: NO_CONFORME ---

    def test_block_j_no_conforme_contains_incidencias_pendientes(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_j(exp, _FakeManifestItem("J"))
        self.assertIn("incidencias pendientes", result.markdown.lower())

    def test_block_j_no_conforme_no_debe_considerarse(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_j(exp, _FakeManifestItem("J"))
        self.assertIn("no debe considerarse", result.markdown.lower())

    def test_block_j_no_conforme_has_warning(self):
        exp = self._exp_with_audit("NO_CONFORME")
        result = build_block_j(exp, _FakeManifestItem("J"))
        self.assertTrue(len(result.warnings) > 0)

    # --- block J: sin audit-final ---

    def test_block_j_no_audit_shows_fallback(self):
        exp = self.tmp / "exp-j-no-audit"
        exp.mkdir(parents=True, exist_ok=True)
        result = build_block_j(exp, _FakeManifestItem("J"))
        self.assertIsNotNone(result)

    # --- full document ---

    def test_full_doc_no_conforme_contains_detectable_phrase(self):
        """El Markdown completo con audit NO_CONFORME contiene 'NO CONFORME' (espacio)."""
        import unicodedata
        exp = self._exp_with_audit("NO_CONFORME")
        from eia_agent.core.document_markdown_builder import build_document_markdown
        result = build_document_markdown(exp, write_outputs=False)
        full_md = assemble_document_markdown(result.blocks)
        norm = unicodedata.normalize("NFKD", full_md.lower()).encode("ascii", "ignore").decode("ascii")
        self.assertIn("no conforme", norm)

class TestConstants(unittest.TestCase):

    def test_block_order_has_11_blocks(self):
        self.assertEqual(len(BLOCK_ORDER), 11)

    def test_block_order_sequence(self):
        self.assertEqual(BLOCK_ORDER, ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"])

    def test_output_filenames_defined(self):
        self.assertEqual(DOCUMENT_OUTPUT_FILENAME, "documento_ambiental_borrador.md")
        self.assertEqual(DOCUMENT_BUILD_RESULT_FILENAME, "document_build_result.json")


if __name__ == "__main__":
    unittest.main()
