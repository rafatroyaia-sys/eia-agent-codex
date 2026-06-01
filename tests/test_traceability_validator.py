"""
tests/test_traceability_validator.py
Tests para AU-03 — Validador de trazabilidad HC ↔ DA.

Cubre:
  1. normalize_traceability_text — normalización conservando IDs
  2. TraceabilityReference / TraceabilityIssue / TraceabilityResult — to_dict, summary, conteos
  3. extract_traceability_references_from_dict — traversal de JSON
  4. extract_claims_from_markdown — extracción de afirmaciones
  5. claim_has_traceability — TRAZADO / PARCIAL / NO_TRAZADO / NO_APLICA
  6. validate_markdown_traceability — validación de markdown
  7. validate_traceability_from_files — expediente temporal
  8. build_traceability_report_markdown — estructura del informe
  9. write_traceability_validation_outputs — escritura de archivos
  10. CLI audit-traceability — exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.traceability_validator import (
    TRACEABILITY_STATUS,
    TRACEABILITY_SEVERITY,
    SOURCE_TYPES,
    TraceabilityIssue,
    TraceabilityReference,
    TraceabilityResult,
    build_traceability_report_markdown,
    claim_has_traceability,
    extract_claims_from_markdown,
    extract_traceability_references_from_dict,
    load_traceability_references,
    normalize_traceability_text,
    validate_markdown_traceability,
    validate_traceability_from_files,
    write_traceability_validation_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_ref(
    ref_id: str = "FI-007",
    source_type: str = "INVENTARIO",
    label: str = "Flora",
    text: str = "",
) -> TraceabilityReference:
    return TraceabilityReference(
        ref_id=ref_id,
        source_type=source_type,
        label=label,
        text=text,
    )


def _make_issue(severity: str = "ERROR", claim: str = "Afirmacion sin trazar") -> TraceabilityIssue:
    return TraceabilityIssue(
        severity=severity,
        code="AU03-E001",
        source="test/source.md",
        claim=claim,
        message="Afirmacion tecnica sin trazabilidad.",
        recommendation="Incluir ID del sistema.",
    )


def _refs_standard() -> list[TraceabilityReference]:
    """Conjunto mínimo de referencias para tests."""
    return [
        _make_ref("FI-007", "INVENTARIO", "Flora"),
        _make_ref("FI-014", "INVENTARIO", "Ruido"),
        _make_ref("FI-010", "INVENTARIO", "Red Natura 2000"),
        _make_ref("IMP-001", "IMPACTO", "Impacto sobre suelo"),
        _make_ref("MED-001", "MEDIDA", "Medida correctora suelo"),
        _make_ref("PVA-001", "PVA", "PVA suelo"),
        _make_ref("GAP-001", "GAP", "Gap de campo flora"),
        _make_ref("HC-001", "HECHO_CONFIRMADO", "Hecho confirmado 1"),
    ]


# ---------------------------------------------------------------------------
# 1. TestNormalizeTraceabilityText
# ---------------------------------------------------------------------------

class TestNormalizeTraceabilityText(unittest.TestCase):

    def test_removes_accents(self) -> None:
        result = normalize_traceability_text("afección")
        self.assertEqual(result, "afeccion")

    def test_lowercase(self) -> None:
        result = normalize_traceability_text("FLORA Y FAUNA")
        self.assertEqual(result, "flora y fauna")

    def test_preserves_fi_code(self) -> None:
        result = normalize_traceability_text("Factor FI-007 flora")
        self.assertIn("fi-007", result)

    def test_preserves_imp_code(self) -> None:
        result = normalize_traceability_text("IMP-001 sobre suelo")
        self.assertIn("imp-001", result)

    def test_preserves_med_code(self) -> None:
        result = normalize_traceability_text("MED-003 correctora")
        self.assertIn("med-003", result)

    def test_normalizes_spaces(self) -> None:
        result = normalize_traceability_text("flora  y   fauna")
        self.assertNotIn("  ", result)

    def test_normalizes_newlines(self) -> None:
        result = normalize_traceability_text("flora\ny\nfauna")
        self.assertNotIn("\n", result)

    def test_strips(self) -> None:
        result = normalize_traceability_text("  ruido  ")
        self.assertEqual(result, "ruido")

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_traceability_text(""), "")

    def test_preserves_pva_code(self) -> None:
        result = normalize_traceability_text("PVA-001 indicador")
        self.assertIn("pva-001", result)


# ---------------------------------------------------------------------------
# 2. TestTraceabilityDataclasses
# ---------------------------------------------------------------------------

class TestTraceabilityReference(unittest.TestCase):

    def test_to_dict_keys(self) -> None:
        ref = _make_ref()
        d = ref.to_dict()
        for k in ("ref_id", "source_type", "label", "text", "metadata"):
            self.assertIn(k, d)

    def test_to_dict_values(self) -> None:
        ref = _make_ref("FI-010", "INVENTARIO", "Red Natura")
        d = ref.to_dict()
        self.assertEqual(d["ref_id"], "FI-010")
        self.assertEqual(d["source_type"], "INVENTARIO")

    def test_summary_is_string(self) -> None:
        ref = _make_ref()
        self.assertIsInstance(ref.summary(), str)

    def test_summary_is_ascii_safe(self) -> None:
        ref = _make_ref(label="Descripción con tilde")
        ref.summary().encode("ascii")  # must not raise

    def test_summary_contains_ref_id(self) -> None:
        ref = _make_ref("IMP-001")
        self.assertIn("IMP-001", ref.summary())


class TestTraceabilityIssue(unittest.TestCase):

    def test_to_dict_keys(self) -> None:
        iss = _make_issue()
        d = iss.to_dict()
        for k in ("severity", "code", "source", "claim", "message", "recommendation", "candidate_refs"):
            self.assertIn(k, d)

    def test_to_dict_severity(self) -> None:
        iss = _make_issue("WARNING")
        self.assertEqual(iss.to_dict()["severity"], "WARNING")

    def test_summary_contains_severity(self) -> None:
        iss = _make_issue("ERROR")
        self.assertIn("ERROR", iss.summary())

    def test_summary_is_ascii_safe(self) -> None:
        iss = _make_issue(claim="Afirmación técnica específica")
        iss.summary().encode("ascii")  # must not raise

    def test_candidate_refs_empty_by_default(self) -> None:
        iss = _make_issue()
        self.assertEqual(iss.candidate_refs, [])

    def test_candidate_refs_stored(self) -> None:
        iss = TraceabilityIssue(
            severity="WARNING", code="AU03-W001", source="src",
            claim="test", message="msg", recommendation="rec",
            candidate_refs=["FI-007", "FI-008"],
        )
        self.assertEqual(iss.to_dict()["candidate_refs"], ["FI-007", "FI-008"])


class TestTraceabilityResult(unittest.TestCase):

    def _make(self, errors: int = 0, warnings: int = 0, infos: int = 0) -> TraceabilityResult:
        issues = []
        for _ in range(errors):
            issues.append(_make_issue("ERROR"))
        for _ in range(warnings):
            issues.append(_make_issue("WARNING"))
        for _ in range(infos):
            issues.append(_make_issue("INFO"))
        return TraceabilityResult(
            checked_sources=["src1"],
            issues=issues,
        )

    def test_error_count(self) -> None:
        r = self._make(errors=3)
        self.assertEqual(r.error_count(), 3)

    def test_warning_count(self) -> None:
        r = self._make(warnings=2)
        self.assertEqual(r.warning_count(), 2)

    def test_info_count(self) -> None:
        r = self._make(infos=4)
        self.assertEqual(r.info_count(), 4)

    def test_is_valid_no_errors(self) -> None:
        r = self._make(warnings=2)
        self.assertTrue(r.is_valid())

    def test_is_valid_with_errors(self) -> None:
        r = self._make(errors=1)
        self.assertFalse(r.is_valid())

    def test_is_valid_empty(self) -> None:
        r = TraceabilityResult()
        self.assertTrue(r.is_valid())

    def test_to_dict_keys(self) -> None:
        r = self._make(errors=1)
        d = r.to_dict()
        for k in ("checked_sources", "references_loaded", "traced_claims",
                   "partial_claims", "untraced_claims", "issues", "warnings",
                   "notes", "error_count", "warning_count", "info_count", "is_valid"):
            self.assertIn(k, d)

    def test_to_dict_counts(self) -> None:
        r = self._make(errors=2, warnings=1)
        d = r.to_dict()
        self.assertEqual(d["error_count"], 2)
        self.assertEqual(d["warning_count"], 1)
        self.assertFalse(d["is_valid"])

    def test_summary_is_ascii_safe(self) -> None:
        r = self._make(errors=2)
        r.summary().encode("ascii")

    def test_summary_contains_result_label(self) -> None:
        valid = self._make()
        self.assertIn("VALIDO", valid.summary())
        invalid = self._make(errors=1)
        self.assertIn("NO VALIDO", invalid.summary())


# ---------------------------------------------------------------------------
# 3. TestExtractTraceabilityReferencesFromDict
# ---------------------------------------------------------------------------

class TestExtractTraceabilityReferencesFromDict(unittest.TestCase):

    def test_extracts_factor_id(self) -> None:
        data = {"factor_id": "FI-006", "factor_name": "Calidad del aire", "description": "Desc."}
        refs = extract_traceability_references_from_dict(data, "INVENTARIO")
        ids = [r.ref_id for r in refs]
        self.assertIn("FI-006", ids)

    def test_extracts_impact_id(self) -> None:
        data = {"impact_id": "IMP-001", "name": "Impacto sobre suelo"}
        refs = extract_traceability_references_from_dict(data, "IMPACTO")
        ids = [r.ref_id for r in refs]
        self.assertIn("IMP-001", ids)

    def test_extracts_measure_id(self) -> None:
        data = {"measure_id": "MED-003", "name": "Medida correctora"}
        refs = extract_traceability_references_from_dict(data, "MEDIDA")
        ids = [r.ref_id for r in refs]
        self.assertIn("MED-003", ids)

    def test_extracts_pva_id(self) -> None:
        data = {"pva_id": "PVA-002", "name": "PVA ruido"}
        refs = extract_traceability_references_from_dict(data, "PVA")
        ids = [r.ref_id for r in refs]
        self.assertIn("PVA-002", ids)

    def test_traverses_nested_list(self) -> None:
        data = {
            "factors": [
                {"factor_id": "FI-007", "factor_name": "Flora"},
                {"factor_id": "FI-008", "factor_name": "Fauna"},
            ]
        }
        refs = extract_traceability_references_from_dict(data, "INVENTARIO")
        ids = [r.ref_id for r in refs]
        self.assertIn("FI-007", ids)
        self.assertIn("FI-008", ids)

    def test_traverses_nested_dict(self) -> None:
        data = {
            "summary": {
                "impacts": [
                    {"impact_id": "IMP-001", "name": "Impacto"}
                ]
            }
        }
        refs = extract_traceability_references_from_dict(data, "IMPACTO")
        ids = [r.ref_id for r in refs]
        self.assertIn("IMP-001", ids)

    def test_tolerates_empty_dict(self) -> None:
        refs = extract_traceability_references_from_dict({}, "INVENTARIO")
        self.assertEqual(refs, [])

    def test_tolerates_none_values(self) -> None:
        data = {"factor_id": None, "name": "Test"}
        refs = extract_traceability_references_from_dict(data, "INVENTARIO")
        # Should not raise; no ref extracted for None ID
        self.assertIsInstance(refs, list)

    def test_tolerates_empty_list(self) -> None:
        refs = extract_traceability_references_from_dict([], "INVENTARIO")
        self.assertEqual(refs, [])

    def test_extracts_gap_id(self) -> None:
        data = {"gap_id": "GAP-003", "description": "Gap de campo"}
        refs = extract_traceability_references_from_dict(data, "GAP")
        ids = [r.ref_id for r in refs]
        self.assertIn("GAP-003", ids)

    def test_source_type_preserved(self) -> None:
        data = {"factor_id": "FI-012", "factor_name": "Patrimonio"}
        refs = extract_traceability_references_from_dict(data, "INVENTARIO")
        matching = [r for r in refs if r.ref_id == "FI-012"]
        self.assertTrue(len(matching) > 0)
        self.assertEqual(matching[0].source_type, "INVENTARIO")

    def test_label_from_name(self) -> None:
        data = {"factor_id": "FI-001", "factor_name": "Clima"}
        refs = extract_traceability_references_from_dict(data, "INVENTARIO")
        matching = [r for r in refs if r.ref_id == "FI-001"]
        self.assertTrue(len(matching) > 0)
        self.assertIn("Clima", matching[0].label)

    def test_returns_list_of_references(self) -> None:
        data = {"impact_id": "IMP-005"}
        refs = extract_traceability_references_from_dict(data, "IMPACTO")
        for r in refs:
            self.assertIsInstance(r, TraceabilityReference)


# ---------------------------------------------------------------------------
# 4. TestExtractClaimsFromMarkdown
# ---------------------------------------------------------------------------

class TestExtractClaimsFromMarkdown(unittest.TestCase):

    def test_extracts_heading(self) -> None:
        md = "## Inventario ambiental del área de estudio"
        claims = extract_claims_from_markdown(md)
        self.assertTrue(any("Inventario ambiental" in c for c in claims))

    def test_extracts_bullet(self) -> None:
        md = "- El factor FI-007 (flora) presenta 12 especies protegidas."
        claims = extract_claims_from_markdown(md)
        self.assertTrue(any("FI-007" in c for c in claims))

    def test_extracts_paragraph(self) -> None:
        md = "La geología del entorno está dominada por materiales volcánicos recientes."
        claims = extract_claims_from_markdown(md)
        self.assertTrue(len(claims) > 0)

    def test_ignores_empty_lines(self) -> None:
        md = "\n\n\n"
        claims = extract_claims_from_markdown(md)
        self.assertEqual(claims, [])

    def test_ignores_separators(self) -> None:
        md = "---\n***\n___\n==="
        claims = extract_claims_from_markdown(md)
        self.assertEqual(claims, [])

    def test_ignores_table_separator_row(self) -> None:
        md = "|---|---|---|\n| contenido | celda | valor |"
        claims = extract_claims_from_markdown(md)
        # Should extract the content row but not the separator
        self.assertTrue(any("contenido" in c for c in claims))
        self.assertFalse(any("---" in c and "contenido" not in c for c in claims))

    def test_extracts_table_row(self) -> None:
        md = "| IMP-001 | Suelo | NEGATIVO | SEVERO |"
        claims = extract_claims_from_markdown(md)
        self.assertTrue(any("IMP-001" in c for c in claims))

    def test_short_claims_filtered(self) -> None:
        md = "# OK\n## A\nSi"
        claims = extract_claims_from_markdown(md)
        # Very short claims should be filtered
        self.assertFalse(any(len(c) < 5 for c in claims))

    def test_code_block_ignored(self) -> None:
        md = "```\nsin afeccion nula\n```"
        claims = extract_claims_from_markdown(md)
        self.assertFalse(any("sin afeccion nula" in c for c in claims))

    def test_ordered_list_extracted(self) -> None:
        md = "1. El impacto IMP-001 afecta al suelo con significancia SEVERO."
        claims = extract_claims_from_markdown(md)
        self.assertTrue(any("IMP-001" in c for c in claims))

    def test_deduplication(self) -> None:
        md = "El factor FI-007 presenta flora diversa.\nEl factor FI-007 presenta flora diversa."
        claims = extract_claims_from_markdown(md)
        # Duplicate should be deduplicated
        count = sum(1 for c in claims if "FI-007" in c)
        self.assertEqual(count, 1)

    def test_returns_list_of_strings(self) -> None:
        md = "## Sección\n\n- Bullet de prueba con contenido suficiente."
        claims = extract_claims_from_markdown(md)
        for c in claims:
            self.assertIsInstance(c, str)


# ---------------------------------------------------------------------------
# 5. TestClaimHasTraceability
# ---------------------------------------------------------------------------

class TestClaimHasTraceability(unittest.TestCase):

    def _refs(self) -> list[TraceabilityReference]:
        return _refs_standard()

    def test_claim_with_existing_imp_is_trazado(self) -> None:
        status, refs = claim_has_traceability(
            "El impacto IMP-001 afecta al suelo de la parcela.", self._refs()
        )
        self.assertEqual(status, "TRAZADO")
        self.assertIn("IMP-001", refs)

    def test_claim_with_existing_med_is_trazado(self) -> None:
        status, refs = claim_has_traceability(
            "La medida MED-001 reduce el impacto sobre el suelo.", self._refs()
        )
        self.assertEqual(status, "TRAZADO")
        self.assertIn("MED-001", refs)

    def test_claim_with_existing_fi_is_trazado(self) -> None:
        status, refs = claim_has_traceability(
            "El factor FI-007 presenta alta diversidad florística.", self._refs()
        )
        self.assertEqual(status, "TRAZADO")
        self.assertIn("FI-007", refs)

    def test_claim_with_existing_hc_is_trazado(self) -> None:
        status, refs = claim_has_traceability(
            "Según HC-001 el expediente está en modo gabinete.", self._refs()
        )
        self.assertEqual(status, "TRAZADO")

    def test_claim_ruido_without_id_is_parcial(self) -> None:
        status, refs = claim_has_traceability(
            "El nivel de ruido en el entorno es elevado.", self._refs()
        )
        self.assertEqual(status, "PARCIAL")
        self.assertTrue(any("FI-014" in r for r in refs))

    def test_claim_flora_without_id_is_parcial(self) -> None:
        status, refs = claim_has_traceability(
            "La flora del área incluye especies de matorral.", self._refs()
        )
        self.assertEqual(status, "PARCIAL")

    def test_claim_red_natura_without_id_is_parcial(self) -> None:
        status, refs = claim_has_traceability(
            "La red natura 2000 está presente en el entorno.", self._refs()
        )
        self.assertEqual(status, "PARCIAL")

    def test_claim_with_unknown_id_is_parcial(self) -> None:
        # ID format correct but not in references
        status, refs = claim_has_traceability(
            "El impacto IMP-999 fue descartado.", self._refs()
        )
        self.assertEqual(status, "PARCIAL")
        self.assertIn("IMP-999", refs)

    def test_technical_claim_without_topic_is_no_trazado(self) -> None:
        status, _ = claim_has_traceability(
            "La parcela tiene 12,5 ha de superficie total.", self._refs()
        )
        self.assertEqual(status, "NO_TRAZADO")

    def test_dba_measurement_without_topic_is_no_trazado(self) -> None:
        # Claim with measurement but NO keyword from any factor → NO_TRAZADO
        status, _ = claim_has_traceability(
            "El registro de campo indica valores de 85 dBa en el punto P-3.", self._refs()
        )
        self.assertEqual(status, "NO_TRAZADO")

    def test_generic_title_is_no_aplica(self) -> None:
        status, _ = claim_has_traceability(
            "El presente documento describe el proyecto.", self._refs()
        )
        self.assertEqual(status, "NO_APLICA")

    def test_very_short_claim_is_no_aplica(self) -> None:
        status, _ = claim_has_traceability("Flora", self._refs())
        self.assertEqual(status, "NO_APLICA")

    def test_empty_references_still_works(self) -> None:
        # With no references, IDs found → PARCIAL
        status, refs = claim_has_traceability(
            "El impacto IMP-001 es significativo.", []
        )
        # Should be PARCIAL (ID found but not in references)
        self.assertIn(status, ("PARCIAL", "TRAZADO"))

    def test_returns_tuple(self) -> None:
        result = claim_has_traceability("flora y fauna del área", self._refs())
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_candidate_refs_is_list(self) -> None:
        _, candidate_refs = claim_has_traceability(
            "El factor flora y vegetación del área.", self._refs()
        )
        self.assertIsInstance(candidate_refs, list)


# ---------------------------------------------------------------------------
# 6. TestValidateMarkdownTraceability
# ---------------------------------------------------------------------------

class TestValidateMarkdownTraceability(unittest.TestCase):

    def _refs(self) -> list[TraceabilityReference]:
        return _refs_standard()

    def test_markdown_with_existing_ids_no_errors(self) -> None:
        md = (
            "## Inventario de flora\n\n"
            "El factor FI-007 presenta vegetación de matorral. "
            "El impacto IMP-001 se valoró como MODERADO."
        )
        result = validate_markdown_traceability(md, self._refs(), source="test.md")
        self.assertTrue(result.is_valid())

    def test_markdown_technical_no_id_is_error(self) -> None:
        md = "La parcela tiene 15 ha de extensión total."
        result = validate_markdown_traceability(md, self._refs(), source="test.md")
        self.assertFalse(result.is_valid())
        self.assertGreater(result.error_count(), 0)

    def test_markdown_topic_match_is_warning(self) -> None:
        md = "La fauna del área incluye aves migratorias de paso."
        result = validate_markdown_traceability(md, self._refs(), source="test.md")
        # "fauna" → PARCIAL → WARNING
        self.assertGreater(result.warning_count(), 0)

    def test_source_recorded(self) -> None:
        md = "Texto limpio sin afirmaciones técnicas concretas."
        result = validate_markdown_traceability(md, self._refs(), source="mi/fuente.md")
        self.assertIn("mi/fuente.md", result.checked_sources)

    def test_does_not_mutate_markdown(self) -> None:
        md = "flora y fauna del área de estudio presente."
        original = md
        validate_markdown_traceability(md, self._refs())
        self.assertEqual(md, original)

    def test_empty_markdown_no_issues(self) -> None:
        result = validate_markdown_traceability("", self._refs(), source="test.md")
        self.assertTrue(result.is_valid())

    def test_methodological_text_no_error(self) -> None:
        md = "El presente documento describe el proyecto y sus alternativas."
        result = validate_markdown_traceability(md, self._refs(), source="test.md")
        # Should be NO_APLICA → no ERROR
        self.assertTrue(result.is_valid())

    def test_notes_populated(self) -> None:
        md = "texto de prueba con contenido suficiente para el test"
        result = validate_markdown_traceability(md, self._refs())
        self.assertGreater(len(result.notes), 0)

    def test_traced_claims_populated(self) -> None:
        md = "El factor FI-007 presenta flora diversa en la zona."
        result = validate_markdown_traceability(md, self._refs())
        self.assertGreater(len(result.traced_claims), 0)

    def test_partial_claims_populated(self) -> None:
        md = "La vegetación del área es densa y diversa."
        result = validate_markdown_traceability(md, self._refs())
        self.assertGreater(len(result.partial_claims), 0)

    def test_untraced_claims_populated(self) -> None:
        md = "La parcela tiene 25 ha de superficie."
        result = validate_markdown_traceability(md, self._refs())
        self.assertGreater(len(result.untraced_claims), 0)


# ---------------------------------------------------------------------------
# 7. TestValidateTraceabilityFromFiles
# ---------------------------------------------------------------------------

class TestValidateTraceabilityFromFiles(unittest.TestCase):

    def test_raises_if_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            validate_traceability_from_files("/ruta/inexistente")

    def test_empty_expediente_returns_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_traceability_from_files(tmp)
            self.assertTrue(len(result.warnings) > 0)

    def test_clean_markdown_with_ids_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Create a markdown with explicit IDs
            bloques_dir = Path(tmp) / "bloques"
            bloques_dir.mkdir()
            (bloques_dir / "B_inventario.md").write_text(
                "## Inventario\n\nEl factor FI-007 y el impacto IMP-001 están trazados.",
                encoding="utf-8",
            )
            # Create a JSON with those references
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            inv_data = {
                "factors": [
                    {"factor_id": "FI-007", "factor_name": "Flora"},
                ]
            }
            imp_dir = Path(tmp) / "impactos"
            imp_dir.mkdir()
            imp_data = {
                "impacts": [
                    {"impact_id": "IMP-001", "name": "Impacto sobre suelo"}
                ]
            }
            (inv_dir / "inventory_summary.json").write_text(
                json.dumps(inv_data), encoding="utf-8"
            )
            (imp_dir / "phase6_model_with_impacts.json").write_text(
                json.dumps(imp_data), encoding="utf-8"
            )
            result = validate_traceability_from_files(tmp)
            # The claims with IDs should be TRAZADO
            self.assertGreater(len(result.traced_claims), 0)

    def test_markdown_with_measurement_no_ref_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques_dir = Path(tmp) / "bloques"
            bloques_dir.mkdir()
            (bloques_dir / "B_datos.md").write_text(
                "La parcela tiene 50 ha de superficie.",
                encoding="utf-8",
            )
            result = validate_traceability_from_files(tmp)
            self.assertFalse(result.is_valid())

    def test_corrupt_json_adds_warning_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "inventory_summary.json").write_text(
                "{ invalid json {{", encoding="utf-8"
            )
            # Should not raise
            result = validate_traceability_from_files(tmp)
            self.assertIsInstance(result, TraceabilityResult)

    def test_references_loaded_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            inv_data = {
                "factors": [{"factor_id": "FI-007", "factor_name": "Flora"}]
            }
            (inv_dir / "inventory_summary.json").write_text(
                json.dumps(inv_data), encoding="utf-8"
            )
            result = validate_traceability_from_files(tmp)
            fi7_refs = [r for r in result.references_loaded if r.ref_id == "FI-007"]
            self.assertTrue(len(fi7_refs) > 0)

    def test_multiple_dirs_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for dirname in ("bloques", "inventario", "impactos"):
                d = Path(tmp) / dirname
                d.mkdir()
                (d / "file.md").write_text(
                    "El factor FI-007 está presente.", encoding="utf-8"
                )
            result = validate_traceability_from_files(tmp)
            self.assertGreaterEqual(len(result.checked_sources), 3)

    def test_generated_auditoria_dir_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud_dir = Path(tmp) / "auditoria"
            aud_dir.mkdir()
            (aud_dir / "traceability_validation_result.md").write_text(
                "La parcela tiene 50 ha de superficie.",
                encoding="utf-8",
            )

            result = validate_traceability_from_files(tmp)

            self.assertEqual(result.error_count(), 0)
            self.assertFalse(any(src.startswith("auditoria") for src in result.checked_sources))

    def test_notes_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_traceability_from_files(tmp)
            self.assertGreater(len(result.notes), 0)


# ---------------------------------------------------------------------------
# 8. TestBuildTraceabilityReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildTraceabilityReportMarkdown(unittest.TestCase):

    def _result_with_issues(self) -> TraceabilityResult:
        r = TraceabilityResult(
            checked_sources=["bloques/B.md"],
            references_loaded=[_make_ref("FI-007")],
            traced_claims=["El factor FI-007 tiene flora."],
            partial_claims=["La fauna del área."],
            untraced_claims=["La parcela tiene 50 ha."],
            issues=[_make_issue("ERROR"), _make_issue("WARNING")],
        )
        return r

    def test_has_section_1_resumen(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 1. Resumen", md)

    def test_has_section_2_fuentes(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 2. Fuentes revisadas", md)

    def test_has_section_3_referencias(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 3. Referencias cargadas", md)

    def test_has_section_4_trazadas(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 4. Afirmaciones trazadas", md)

    def test_has_section_5_parciales(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 5. Afirmaciones parcialmente trazadas", md)

    def test_has_section_6_no_trazadas(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 6. Afirmaciones no trazadas", md)

    def test_has_section_7_incidencias(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 7. Incidencias", md)

    def test_has_section_8_recomendaciones(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 8. Recomendaciones", md)

    def test_has_section_9_advertencia(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("## 9. Advertencia de alcance", md)

    def test_no_valido_when_errors(self) -> None:
        md = build_traceability_report_markdown(self._result_with_issues())
        self.assertIn("NO VALIDO", md)

    def test_valido_when_no_errors(self) -> None:
        result = TraceabilityResult(
            issues=[_make_issue("WARNING")],
        )
        md = build_traceability_report_markdown(result)
        self.assertIn("VALIDO", md)

    def test_advertencia_no_declara_aptitud(self) -> None:
        md = build_traceability_report_markdown(TraceabilityResult())
        # Normalize for comparison
        import unicodedata
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertIn("no declara aptitud", norm)

    def test_advertencia_no_corrige(self) -> None:
        md = build_traceability_report_markdown(TraceabilityResult())
        import unicodedata
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertIn("no corrige", norm)

    def test_returns_string(self) -> None:
        md = build_traceability_report_markdown(TraceabilityResult())
        self.assertIsInstance(md, str)


# ---------------------------------------------------------------------------
# 9. TestWriteTraceabilityValidationOutputs
# ---------------------------------------------------------------------------

class TestWriteTraceabilityValidationOutputs(unittest.TestCase):

    def _make_result(self) -> TraceabilityResult:
        return TraceabilityResult(
            checked_sources=["bloques/B.md"],
            issues=[_make_issue("ERROR")],
        )

    def test_writes_json_and_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_traceability_validation_outputs(
                self._make_result(), out
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, _ = write_traceability_validation_outputs(
                self._make_result(), out
            )
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("issues", data)
            self.assertIn("error_count", data)

    def test_md_has_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            _, md_path = write_traceability_validation_outputs(
                self._make_result(), out
            )
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Resumen", content)
            self.assertIn("## 9. Advertencia de alcance", content)

    def test_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nuevo" / "auditoria"
            self.assertFalse(out.exists())
            write_traceability_validation_outputs(self._make_result(), out)
            self.assertTrue(out.exists())

    def test_returns_tuple_of_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            result = write_traceability_validation_outputs(self._make_result(), out)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], Path)
            self.assertIsInstance(result[1], Path)

    def test_json_error_count_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            res = self._make_result()
            json_path, _ = write_traceability_validation_outputs(res, out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["error_count"], res.error_count())

    def test_filenames_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_traceability_validation_outputs(
                self._make_result(), out
            )
            self.assertEqual(json_path.name, "traceability_validation_result.json")
            self.assertEqual(md_path.name, "traceability_validation_result.md")


# ---------------------------------------------------------------------------
# 10. TestCLIAuditTraceability
# ---------------------------------------------------------------------------

class TestCLIAuditTraceability(unittest.TestCase):

    def _run_cli(self, argv: list[str]) -> int:
        from run_expediente import main
        return main(argv)

    def test_empty_expediente_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "audit-traceability"])
            self.assertEqual(code, 0)

    def test_clean_markdown_with_ids_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques = Path(tmp) / "bloques"
            bloques.mkdir()
            (bloques / "B.md").write_text(
                "## Intro\n\nEl presente documento describe el proyecto.",
                encoding="utf-8",
            )
            code = self._run_cli([tmp, "audit-traceability"])
            self.assertEqual(code, 0)

    def test_technical_claim_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques = Path(tmp) / "bloques"
            bloques.mkdir()
            (bloques / "B.md").write_text(
                "La parcela tiene 50 ha de superficie.",
                encoding="utf-8",
            )
            code = self._run_cli([tmp, "audit-traceability"])
            self.assertEqual(code, 1)

    def test_no_write_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques = Path(tmp) / "bloques"
            bloques.mkdir()
            (bloques / "B.md").write_text("Texto limpio.", encoding="utf-8")
            self._run_cli([tmp, "audit-traceability"])
            auditoria = Path(tmp) / "auditoria"
            self.assertFalse((auditoria / "traceability_validation_result.json").exists())

    def test_write_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques = Path(tmp) / "bloques"
            bloques.mkdir()
            (bloques / "B.md").write_text(
                "El factor FI-007 presenta flora en el área.",
                encoding="utf-8",
            )
            self._run_cli([tmp, "audit-traceability", "--write"])
            auditoria = Path(tmp) / "auditoria"
            self.assertTrue((auditoria / "traceability_validation_result.json").exists())
            self.assertTrue((auditoria / "traceability_validation_result.md").exists())

    def test_nonexistent_expediente_exit_1(self) -> None:
        code = self._run_cli(["/ruta/que/no/existe", "audit-traceability"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
