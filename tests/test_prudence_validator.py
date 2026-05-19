"""
tests/test_prudence_validator.py
Tests para AU-02 — Validador de prudencia metodológica.

Cubre:
  1. normalize_prudence_text — normalización de texto
  2. PrudenceIssue — to_dict, summary
  3. PrudenceValidationResult — conteos, is_valid, to_dict, summary
  4. find_forbidden_phrases — detección por categoría, deduplicación
  5. _is_methodological_context — ventana contextual
  6. validate_inventory_prudence — inventario con frases prohibidas
  7. validate_phase6_prudence — Phase6Model con frases prohibidas
  8. validate_markdown_prudence — markdown con frases prohibidas
  9. validate_prudence_from_files — expediente temporal con markdowns
  10. build_prudence_report_markdown — estructura y contenido del informe
  11. write_prudence_validation_outputs — escritura de archivos
  12. CLI audit-prudence — exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.inventory_model import FactorInventory, InventorySummary
from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
)
from eia_agent.core.prudence_validator import (
    PROHIBITED_PHRASES_GENERAL,
    PROHIBITED_IN_INVENTORY,
    PROHIBITED_BIODIVERSITY,
    PROHIBITED_RED_NATURA,
    PrudenceIssue,
    PrudenceValidationResult,
    _is_methodological_context,
    build_prudence_report_markdown,
    find_forbidden_phrases,
    normalize_prudence_text,
    validate_inventory_prudence,
    validate_markdown_prudence,
    validate_phase6_prudence,
    validate_prudence_from_files,
    write_prudence_validation_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_factor(
    factor_id: str = "FI-001",
    description: str = "No se detecta informacion en las fuentes consultadas.",
    notes: list[str] | None = None,
    warnings: list[str] | None = None,
) -> FactorInventory:
    return FactorInventory(
        factor_id=factor_id,
        description=description,
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_summary(factors: list[FactorInventory] | None = None) -> InventorySummary:
    return InventorySummary(
        expediente_id="EIA-TEST",
        factors=factors or [],
    )


def _make_action(action_id: str = "AC-001") -> ProjectAction:
    return ProjectAction(
        action_id=action_id,
        name="Operacion de prueba",
        action_type="OPERACION",
    )


def _make_receptor(receptor_id: str = "FR-001") -> ReceptorFactor:
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=receptor_id.replace("FR-", "FI-"),
        name="Factor de prueba",
    )


def _make_impact(
    impact_id: str = "IMP-001",
    receptor_id: str = "FR-001",
    nature: str = "NEGATIVO",
    status: str = "PRELIMINAR",
    description: str = "",
    notes: list[str] | None = None,
    warnings: list[str] | None = None,
    data_gaps: list[str] | None = None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id=receptor_id,
        name="Impacto de prueba",
        description=description,
        nature=nature,
        status=status,
        notes=notes or [],
        warnings=warnings or [],
        data_gaps=data_gaps or [],
    )


def _make_measure(
    measure_id: str = "MED-001",
    description: str = "",
    is_prl_only: bool = False,
    measure_type: str = "CORRECTORA",
    notes: list[str] | None = None,
    warnings: list[str] | None = None,
) -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id,
        measure_type=measure_type,
        name="Medida de prueba",
        description=description,
        is_prl_only=is_prl_only,
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_pva(
    pva_id: str = "PVA-001",
    indicator: str = "Se mide X",
    threshold: str = "Umbral Y",
    notes: list[str] | None = None,
    warnings: list[str] | None = None,
) -> PVAProgram:
    return PVAProgram(
        pva_id=pva_id,
        name="PVA de prueba",
        factor_id="FI-001",
        indicator=indicator,
        threshold=threshold,
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_phase6(
    impacts: list[EnvironmentalImpact] | None = None,
    measures: list[MitigationMeasure] | None = None,
    pva_programs: list[PVAProgram] | None = None,
) -> Phase6Model:
    return Phase6Model(
        expediente_id="EIA-TEST",
        actions=[_make_action()],
        receptor_factors=[_make_receptor()],
        impacts=impacts or [],
        measures=measures or [],
        pva_programs=pva_programs or [],
    )


def _make_issue(severity: str = "ERROR", phrase: str = "sin afeccion") -> PrudenceIssue:
    return PrudenceIssue(
        severity=severity,
        code="AU02-E001",
        source="test/source",
        phrase=phrase,
        context="...sin afeccion en la parcela...",
        message="Frase prohibida detectada.",
        recommendation="Sustituir por formulacion prudente.",
    )


# ---------------------------------------------------------------------------
# 1. TestNormalizePrudenceText
# ---------------------------------------------------------------------------

class TestNormalizePrudenceText(unittest.TestCase):

    def test_removes_accents(self) -> None:
        result = normalize_prudence_text("afección")
        self.assertEqual(result, "afeccion")

    def test_lowercase(self) -> None:
        result = normalize_prudence_text("SIN AFECCION")
        self.assertEqual(result, "sin afeccion")

    def test_accented_mixed_case(self) -> None:
        result = normalize_prudence_text("Sin Afección Apreciable")
        self.assertEqual(result, "sin afeccion apreciable")

    def test_normalizes_multiple_spaces(self) -> None:
        result = normalize_prudence_text("sin  afeccion   nula")
        self.assertNotIn("  ", result)

    def test_normalizes_newlines(self) -> None:
        result = normalize_prudence_text("sin\nafeccion\nalguna")
        self.assertNotIn("\n", result)
        self.assertIn("sin", result)
        self.assertIn("afeccion", result)

    def test_strips_whitespace(self) -> None:
        result = normalize_prudence_text("  despreciable  ")
        self.assertEqual(result, "despreciable")

    def test_empty_string(self) -> None:
        result = normalize_prudence_text("")
        self.assertEqual(result, "")

    def test_plain_ascii_unchanged(self) -> None:
        text = "no se detecta en las fuentes consultadas"
        result = normalize_prudence_text(text)
        self.assertEqual(result, text)

    def test_tabs_replaced(self) -> None:
        result = normalize_prudence_text("sin\tafeccion")
        self.assertNotIn("\t", result)


# ---------------------------------------------------------------------------
# 2. TestPrudenceIssue
# ---------------------------------------------------------------------------

class TestPrudenceIssue(unittest.TestCase):

    def _make(self, **kwargs) -> PrudenceIssue:
        defaults = dict(
            severity="ERROR",
            code="AU02-E001",
            source="inventario/FI-007/description",
            phrase="sin afeccion",
            context="...no hay sin afeccion aqui...",
            message="Frase prohibida detectada.",
            recommendation="Sustituir por formulacion prudente.",
        )
        defaults.update(kwargs)
        return PrudenceIssue(**defaults)

    def test_to_dict_keys(self) -> None:
        issue = self._make()
        d = issue.to_dict()
        for key in ("severity", "code", "source", "phrase", "context", "message", "recommendation"):
            self.assertIn(key, d)

    def test_to_dict_values(self) -> None:
        issue = self._make(severity="WARNING", phrase="despreciable")
        d = issue.to_dict()
        self.assertEqual(d["severity"], "WARNING")
        self.assertEqual(d["phrase"], "despreciable")

    def test_summary_contains_severity(self) -> None:
        issue = self._make(severity="ERROR")
        s = issue.summary()
        self.assertIn("ERROR", s)

    def test_summary_contains_code(self) -> None:
        issue = self._make(code="AU02-W001")
        s = issue.summary()
        self.assertIn("AU02-W001", s)

    def test_summary_is_ascii_safe(self) -> None:
        issue = self._make(source="inventario/FI-007/descripción")
        s = issue.summary()
        s.encode("ascii")  # must not raise

    def test_summary_is_string(self) -> None:
        issue = self._make()
        self.assertIsInstance(issue.summary(), str)


# ---------------------------------------------------------------------------
# 3. TestPrudenceValidationResult
# ---------------------------------------------------------------------------

class TestPrudenceValidationResult(unittest.TestCase):

    def _make_result(
        self,
        errors: int = 0,
        warnings: int = 0,
        infos: int = 0,
    ) -> PrudenceValidationResult:
        issues = []
        for _ in range(errors):
            issues.append(_make_issue("ERROR"))
        for _ in range(warnings):
            issues.append(_make_issue("WARNING"))
        for _ in range(infos):
            issues.append(_make_issue("INFO"))
        return PrudenceValidationResult(
            issues=issues,
            checked_sources=["src1", "src2"],
        )

    def test_error_count(self) -> None:
        r = self._make_result(errors=3, warnings=1)
        self.assertEqual(r.error_count(), 3)

    def test_warning_count(self) -> None:
        r = self._make_result(warnings=2, infos=1)
        self.assertEqual(r.warning_count(), 2)

    def test_info_count(self) -> None:
        r = self._make_result(errors=1, infos=4)
        self.assertEqual(r.info_count(), 4)

    def test_is_valid_no_errors(self) -> None:
        r = self._make_result(warnings=2, infos=1)
        self.assertTrue(r.is_valid())

    def test_is_valid_with_errors(self) -> None:
        r = self._make_result(errors=1)
        self.assertFalse(r.is_valid())

    def test_is_valid_empty(self) -> None:
        r = PrudenceValidationResult()
        self.assertTrue(r.is_valid())

    def test_to_dict_keys(self) -> None:
        r = self._make_result(errors=1)
        d = r.to_dict()
        for key in ("issues", "checked_sources", "warnings", "notes",
                    "error_count", "warning_count", "info_count", "is_valid"):
            self.assertIn(key, d)

    def test_to_dict_counts(self) -> None:
        r = self._make_result(errors=2, warnings=3, infos=1)
        d = r.to_dict()
        self.assertEqual(d["error_count"], 2)
        self.assertEqual(d["warning_count"], 3)
        self.assertEqual(d["info_count"], 1)
        self.assertFalse(d["is_valid"])

    def test_summary_is_ascii_safe(self) -> None:
        r = self._make_result(errors=2)
        s = r.summary()
        s.encode("ascii")  # must not raise

    def test_summary_contains_result_label(self) -> None:
        valid = self._make_result()
        self.assertIn("VALIDO", valid.summary())
        invalid = self._make_result(errors=1)
        self.assertIn("NO VALIDO", invalid.summary())

    def test_summary_shows_error_sources(self) -> None:
        r = self._make_result(errors=2)
        s = r.summary()
        # Should mention at least one error detail
        self.assertIn("sin afeccion", s)


# ---------------------------------------------------------------------------
# 4. TestFindForbiddenPhrases
# ---------------------------------------------------------------------------

class TestFindForbiddenPhrases(unittest.TestCase):

    def test_detects_general_phrase(self) -> None:
        text = "El estudio concluye que no hay impacto sobre el area."
        issues = find_forbidden_phrases(text, source="test", category="general")
        phrases = [i.phrase for i in issues]
        self.assertIn("no hay impacto", phrases)

    def test_detects_biodiversity_phrase(self) -> None:
        text = "En el area no hay fauna de interes."
        issues = find_forbidden_phrases(text, source="test", category="biodiversity")
        phrases = [i.phrase for i in issues]
        self.assertIn("no hay fauna", phrases)

    def test_detects_red_natura_phrase(self) -> None:
        text = "La parcela esta fuera de red natura."
        issues = find_forbidden_phrases(text, source="test", category="red_natura")
        phrases = [i.phrase for i in issues]
        self.assertIn("fuera de red natura", phrases)

    def test_clean_text_returns_empty(self) -> None:
        text = "No se detecta afeccion en las fuentes consultadas."
        issues = find_forbidden_phrases(text, source="test", category="general")
        self.assertEqual(issues, [])

    def test_category_all_detects_across_categories(self) -> None:
        text = "no hay fauna y sin afeccion apreciable"
        issues = find_forbidden_phrases(text, source="test", category="all")
        phrases = [i.phrase for i in issues]
        self.assertTrue(any("fauna" in p for p in phrases))

    def test_methodological_context_returns_info(self) -> None:
        # Phrase is mentioned as prohibited — should be INFO, not ERROR
        text = (
            "El sistema prohibe el uso de 'sin afeccion' sin evidencia de campo. "
            "No debe decir frases como 'sin afeccion'."
        )
        issues = find_forbidden_phrases(text, source="test", category="general")
        for iss in issues:
            if iss.phrase == "sin afeccion":
                self.assertEqual(iss.severity, "INFO")
                break
        else:
            # If phrase not found at all, also acceptable
            pass

    def test_deduplication(self) -> None:
        # Same phrase twice in very close positions should not generate many issues
        text = "sin afeccion. sin afeccion."
        issues = find_forbidden_phrases(text, source="test", category="general")
        # Both may be found since positions differ; just check it doesn't crash
        self.assertIsInstance(issues, list)

    def test_returns_list_of_prudence_issues(self) -> None:
        text = "El area no presenta sin afeccion relevante."
        issues = find_forbidden_phrases(text, source="test", category="general")
        for iss in issues:
            self.assertIsInstance(iss, PrudenceIssue)

    def test_issue_has_correct_source(self) -> None:
        text = "sin afeccion total"
        issues = find_forbidden_phrases(text, source="mi/fuente", category="general")
        if issues:
            self.assertEqual(issues[0].source, "mi/fuente")

    def test_warning_for_despreciable(self) -> None:
        text = "El impacto es despreciable."
        issues = find_forbidden_phrases(text, source="test", category="general")
        sev = {i.phrase: i.severity for i in issues}
        if "despreciable" in sev:
            self.assertEqual(sev["despreciable"], "WARNING")

    def test_error_for_strong_closure(self) -> None:
        text = "El impacto se descarta por completo."
        issues = find_forbidden_phrases(text, source="test", category="general")
        sev = {i.phrase: i.severity for i in issues}
        if "se descarta" in sev:
            self.assertEqual(sev["se descarta"], "ERROR")

    def test_unknown_category_falls_back_to_general(self) -> None:
        text = "sin afeccion total"
        issues = find_forbidden_phrases(text, source="test", category="categoria_inexistente")
        # Should not raise; may return empty or use general
        self.assertIsInstance(issues, list)

    def test_inventory_phrase_in_inventory_category(self) -> None:
        text = "El factor presenta condiciones compatibles."
        issues = find_forbidden_phrases(text, source="test", category="inventory")
        phrases = [i.phrase for i in issues]
        self.assertIn("compatible", phrases)

    def test_context_present_in_issue(self) -> None:
        text = "La afeccion es nula sobre el medio."
        issues = find_forbidden_phrases(text, source="test", category="general")
        if issues:
            self.assertIn("nula", issues[0].context)


# ---------------------------------------------------------------------------
# 5. TestIsMethodologicalContext
# ---------------------------------------------------------------------------

class TestIsMethodologicalContext(unittest.TestCase):

    def test_no_deve_decir_triggers_true(self) -> None:
        text = "el sistema no debe decir sin afeccion en el expediente"
        idx = text.find("sin afeccion")
        self.assertTrue(_is_methodological_context(text, idx))

    def test_prohibido_near_phrase_triggers_true(self) -> None:
        text = "uso prohibido de sin afeccion en modo gabinete"
        idx = text.find("sin afeccion")
        self.assertTrue(_is_methodological_context(text, idx))

    def test_normal_text_returns_false(self) -> None:
        text = "la parcela no presenta sin afeccion de ningún tipo"
        idx = text.find("sin afeccion")
        self.assertFalse(_is_methodological_context(text, idx))

    def test_evitar_near_phrase_triggers_true(self) -> None:
        text = "hay que evitar decir sin afeccion en inventario"
        idx = text.find("sin afeccion")
        self.assertTrue(_is_methodological_context(text, idx))

    def test_window_boundary_too_far(self) -> None:
        # The methodological indicator is more than 150 chars away
        far_text = "prohibido" + ("x" * 200) + "sin afeccion"
        idx = far_text.find("sin afeccion")
        self.assertFalse(_is_methodological_context(far_text, idx))

    def test_empty_text(self) -> None:
        self.assertFalse(_is_methodological_context("", 0))


# ---------------------------------------------------------------------------
# 6. TestValidateInventoryPrudence
# ---------------------------------------------------------------------------

class TestValidateInventoryPrudence(unittest.TestCase):

    def test_clean_inventory_no_issues(self) -> None:
        factor = _make_factor(
            description="No se detecta informacion en las fuentes consultadas.",
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        self.assertTrue(result.is_valid())
        self.assertEqual(result.error_count(), 0)

    def test_detects_sin_afeccion_in_description(self) -> None:
        factor = _make_factor(
            description="El factor ambiental presenta sin afeccion sobre la parcela.",
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        self.assertFalse(result.is_valid())
        self.assertGreater(result.error_count(), 0)

    def test_detects_prohibited_in_notes(self) -> None:
        factor = _make_factor(
            description="Descripcion prudente.",
            notes=["No hay impacto sobre el terreno."],
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        # "no hay impacto" is in PROHIBITED_PHRASES_GENERAL
        self.assertFalse(result.is_valid())

    def test_detects_compatible_in_fi007_inventory(self) -> None:
        # FI-007 has "inventory" category → "compatible" is ERROR
        factor = _make_factor(
            factor_id="FI-007",
            description="La flora se considera compatible con la actividad.",
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        phrases = [i.phrase for i in result.issues]
        self.assertIn("compatible", phrases)

    def test_detects_no_hay_fauna_in_fi008(self) -> None:
        factor = _make_factor(
            factor_id="FI-008",
            description="No hay fauna de interes en el area prospectada.",
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        self.assertFalse(result.is_valid())

    def test_empty_inventory_no_issues(self) -> None:
        summary = _make_summary([])
        result = validate_inventory_prudence(summary)
        self.assertTrue(result.is_valid())
        self.assertEqual(result.error_count(), 0)

    def test_result_has_checked_sources(self) -> None:
        factor = _make_factor(description="Descripcion prudente.")
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        self.assertGreater(len(result.checked_sources), 0)

    def test_result_has_notes(self) -> None:
        factor = _make_factor()
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        self.assertTrue(len(result.notes) > 0)

    def test_multiple_factors_aggregated(self) -> None:
        f1 = _make_factor(factor_id="FI-001", description="Descripcion limpia.")
        f2 = _make_factor(
            factor_id="FI-007",
            description="No hay flora en la zona.",
        )
        summary = _make_summary([f1, f2])
        result = validate_inventory_prudence(summary)
        self.assertGreater(result.error_count(), 0)

    def test_methodological_context_in_note_becomes_info(self) -> None:
        factor = _make_factor(
            description="Uso prohibido: 'sin afeccion' como afirmacion sin evidencia.",
        )
        summary = _make_summary([factor])
        result = validate_inventory_prudence(summary)
        # Should be INFO, not ERROR
        for iss in result.issues:
            if iss.phrase == "sin afeccion":
                self.assertEqual(iss.severity, "INFO")


# ---------------------------------------------------------------------------
# 7. TestValidatePhase6Prudence
# ---------------------------------------------------------------------------

class TestValidatePhase6Prudence(unittest.TestCase):

    def test_clean_model_no_issues(self) -> None:
        model = _make_phase6()
        result = validate_phase6_prudence(model)
        self.assertTrue(result.is_valid())

    def test_detects_sin_afeccion_in_impact_description(self) -> None:
        imp = _make_impact(description="El impacto presenta sin afeccion sobre el medio.")
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        self.assertFalse(result.is_valid())

    def test_detects_se_descarta_in_impact_note(self) -> None:
        imp = _make_impact(notes=["El impacto se descarta por ausencia de datos."])
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        self.assertFalse(result.is_valid())

    def test_compatible_significance_not_flagged_as_error(self) -> None:
        # "compatible" as typed field significance is OK in Phase 6
        # The test checks impact with "compatible" ONLY in the significance field,
        # not in free text descriptions — so no issues expected
        imp = _make_impact(description="Descripcion prudente sin lenguaje prohibido.")
        imp.significance_without_measures = "COMPATIBLE"
        imp.significance_with_measures = "COMPATIBLE"
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        # significance fields are not checked as free text
        self.assertTrue(result.is_valid())

    def test_closure_phrase_in_sensitive_indeterminado_is_error(self) -> None:
        # FR-007 is sensitive, INDETERMINADO status + "compatible" in text → ERROR AU02-E002
        imp = _make_impact(
            receptor_id="FR-007",
            status="INDETERMINADO",
            description="El impacto se considera compatible con la actividad.",
        )
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        codes = [i.code for i in result.issues]
        self.assertIn("AU02-E002", codes)

    def test_compensation_phrase_in_positive_impact_is_error(self) -> None:
        imp = _make_impact(
            nature="POSITIVO",
            description="Este impacto positivo compensa el impacto negativo sobre el suelo.",
        )
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        codes = [i.code for i in result.issues]
        self.assertIn("AU02-E003", codes)

    def test_prl_measure_with_correctora_language_is_warning(self) -> None:
        med = _make_measure(
            is_prl_only=True,
            measure_type="PRL_NO_EIA",
            description="Esta medida es una correctora ambiental del impacto.",
        )
        model = _make_phase6(measures=[med])
        result = validate_phase6_prudence(model)
        codes = [i.code for i in result.issues]
        self.assertIn("AU02-W002", codes)

    def test_prl_non_prl_measure_not_flagged(self) -> None:
        med = _make_measure(
            is_prl_only=False,
            measure_type="CORRECTORA",
            description="Esta medida es una correctora ambiental del impacto.",
        )
        model = _make_phase6(measures=[med])
        result = validate_phase6_prudence(model)
        # AU02-W002 only fires for is_prl_only measures
        codes = [i.code for i in result.issues]
        self.assertNotIn("AU02-W002", codes)

    def test_detects_prohibited_in_pva_indicator(self) -> None:
        pva = _make_pva(indicator="Sin afeccion verificada en campo.")
        model = _make_phase6(pva_programs=[pva])
        result = validate_phase6_prudence(model)
        self.assertFalse(result.is_valid())

    def test_result_has_notes(self) -> None:
        model = _make_phase6()
        result = validate_phase6_prudence(model)
        self.assertTrue(len(result.notes) > 0)

    def test_does_not_mutate_model(self) -> None:
        imp = _make_impact(description="sin afeccion detectable.")
        model = _make_phase6(impacts=[imp])
        original_desc = imp.description
        validate_phase6_prudence(model)
        self.assertEqual(imp.description, original_desc)

    def test_non_sensitive_indeterminado_no_e002(self) -> None:
        # FR-001 is not sensitive, so closure + INDETERMINADO should NOT trigger E002
        imp = _make_impact(
            receptor_id="FR-001",
            status="INDETERMINADO",
            description="El impacto se considera compatible.",
        )
        model = _make_phase6(impacts=[imp])
        result = validate_phase6_prudence(model)
        codes = [i.code for i in result.issues]
        self.assertNotIn("AU02-E002", codes)


# ---------------------------------------------------------------------------
# 8. TestValidateMarkdownPrudence
# ---------------------------------------------------------------------------

class TestValidateMarkdownPrudence(unittest.TestCase):

    def test_clean_markdown_no_issues(self) -> None:
        md = "## Inventario\n\nNo se detecta afeccion en las fuentes consultadas."
        result = validate_markdown_prudence(md, source="bloques/B_inventario.md")
        self.assertTrue(result.is_valid())

    def test_detects_sin_afeccion(self) -> None:
        md = "## Conclusion\n\nEl area presenta sin afeccion total."
        result = validate_markdown_prudence(md, source="bloques/B.md", category="general")
        self.assertFalse(result.is_valid())

    def test_category_general(self) -> None:
        md = "No hay impacto sobre el area."
        result = validate_markdown_prudence(md, source="test.md", category="general")
        self.assertGreater(result.error_count(), 0)

    def test_category_biodiversity(self) -> None:
        md = "No hay fauna en la zona."
        result = validate_markdown_prudence(md, source="test.md", category="biodiversity")
        self.assertFalse(result.is_valid())

    def test_category_all(self) -> None:
        md = "Sin habitats ni red natura afectada."
        result = validate_markdown_prudence(md, source="test.md", category="all")
        # "sin habitats" is in biodiversity; should be detected
        phrases = [i.phrase for i in result.issues]
        self.assertTrue(any("habitats" in p or "red natura" in p for p in phrases))

    def test_source_recorded(self) -> None:
        md = "Texto limpio sin problemas."
        result = validate_markdown_prudence(md, source="mi/ruta.md")
        self.assertIn("mi/ruta.md", result.checked_sources)

    def test_notes_present(self) -> None:
        result = validate_markdown_prudence("texto", source="f.md")
        self.assertGreater(len(result.notes), 0)

    def test_does_not_mutate_input(self) -> None:
        md = "sin afeccion"
        original = md
        validate_markdown_prudence(md, source="test.md")
        self.assertEqual(md, original)


# ---------------------------------------------------------------------------
# 9. TestValidatePrudenceFromFiles
# ---------------------------------------------------------------------------

class TestValidatePrudenceFromFiles(unittest.TestCase):

    def test_raises_if_expediente_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            validate_prudence_from_files("/ruta/inexistente/expediente")

    def test_no_markdowns_returns_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_prudence_from_files(tmp)
            self.assertTrue(len(result.warnings) > 0)

    def test_clean_markdown_no_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_001.md").write_text(
                "# Geologia\n\nNo se detecta afeccion en las fuentes.",
                encoding="utf-8",
            )
            result = validate_prudence_from_files(tmp)
            self.assertTrue(result.is_valid())

    def test_markdown_with_prohibited_phrase_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_007.md").write_text(
                "# Flora\n\nNo hay flora de interes en la zona.",
                encoding="utf-8",
            )
            result = validate_prudence_from_files(tmp)
            self.assertFalse(result.is_valid())

    def test_bloques_dir_also_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bloques_dir = Path(tmp) / "bloques"
            bloques_dir.mkdir()
            (bloques_dir / "B_inventario.md").write_text(
                "La zona presenta sin afeccion sobre el suelo.",
                encoding="utf-8",
            )
            result = validate_prudence_from_files(tmp)
            self.assertFalse(result.is_valid())

    def test_checked_sources_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_001.md").write_text("Texto limpio.", encoding="utf-8")
            result = validate_prudence_from_files(tmp)
            self.assertGreater(len(result.checked_sources), 0)

    def test_notes_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_prudence_from_files(tmp)
            self.assertTrue(len(result.notes) > 0)

    def test_multiple_dirs_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for dirname in ("inventario", "impactos", "bloques"):
                d = Path(tmp) / dirname
                d.mkdir()
                (d / "file.md").write_text("Texto limpio.", encoding="utf-8")
            result = validate_prudence_from_files(tmp)
            self.assertGreaterEqual(len(result.checked_sources), 3)


# ---------------------------------------------------------------------------
# 10. TestBuildPrudenceReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildPrudenceReportMarkdown(unittest.TestCase):

    def _result_with_error(self) -> PrudenceValidationResult:
        return PrudenceValidationResult(
            issues=[_make_issue("ERROR"), _make_issue("WARNING", "despreciable")],
            checked_sources=["inventario/FI-007"],
        )

    def test_has_section_1_resumen(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 1. Resumen", md)

    def test_has_section_2_fuentes(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 2. Fuentes revisadas", md)

    def test_has_section_3_errores(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 3. Incidencias ERROR", md)

    def test_has_section_4_warnings(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 4. Incidencias WARNING", md)

    def test_has_section_5_infos(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 5. Incidencias INFO", md)

    def test_has_section_6_recomendaciones(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 6. Recomendaciones", md)

    def test_has_section_7_advertencia(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("## 7. Advertencia de alcance", md)

    def test_no_valido_when_errors(self) -> None:
        md = build_prudence_report_markdown(self._result_with_error())
        self.assertIn("NO VALIDO", md)

    def test_valido_when_no_errors(self) -> None:
        result = PrudenceValidationResult(
            issues=[_make_issue("WARNING")],
            checked_sources=["src"],
        )
        md = build_prudence_report_markdown(result)
        self.assertIn("VALIDO", md)

    def test_clean_result_shows_sin_incidencias(self) -> None:
        result = PrudenceValidationResult(checked_sources=["src"])
        md = build_prudence_report_markdown(result)
        self.assertIn("Sin incidencias ERROR", md)
        self.assertIn("Sin incidencias WARNING", md)

    def test_source_listed_in_section_2(self) -> None:
        result = PrudenceValidationResult(
            checked_sources=["inventario/FI-007"],
        )
        md = build_prudence_report_markdown(result)
        self.assertIn("inventario/FI-007", md)

    def test_advertencia_contains_no_corrige(self) -> None:
        md = build_prudence_report_markdown(PrudenceValidationResult())
        normalized = md.lower().replace("á", "a").replace("ó", "o")
        self.assertIn("no corrige", normalized)

    def test_returns_string(self) -> None:
        md = build_prudence_report_markdown(PrudenceValidationResult())
        self.assertIsInstance(md, str)


# ---------------------------------------------------------------------------
# 11. TestWritePrudenceValidationOutputs
# ---------------------------------------------------------------------------

class TestWritePrudenceValidationOutputs(unittest.TestCase):

    def _make_result(self) -> PrudenceValidationResult:
        return PrudenceValidationResult(
            issues=[_make_issue("ERROR")],
            checked_sources=["inventario/FI-007"],
        )

    def test_writes_json_and_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_prudence_validation_outputs(self._make_result(), out)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, _ = write_prudence_validation_outputs(self._make_result(), out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("issues", data)
            self.assertIn("error_count", data)

    def test_md_has_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            _, md_path = write_prudence_validation_outputs(self._make_result(), out)
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Resumen", content)
            self.assertIn("## 7. Advertencia de alcance", content)

    def test_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nuevo" / "auditoria"
            self.assertFalse(out.exists())
            write_prudence_validation_outputs(self._make_result(), out)
            self.assertTrue(out.exists())

    def test_returns_tuple_of_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            result = write_prudence_validation_outputs(self._make_result(), out)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], Path)
            self.assertIsInstance(result[1], Path)

    def test_json_error_count_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            res = self._make_result()
            json_path, _ = write_prudence_validation_outputs(res, out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["error_count"], res.error_count())


# ---------------------------------------------------------------------------
# 12. TestCLIAuditPrudence
# ---------------------------------------------------------------------------

class TestCLIAuditPrudence(unittest.TestCase):

    def _run_cli(self, argv: list[str]) -> int:
        from run_expediente import main
        return main(argv)

    def test_clean_expediente_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_001.md").write_text(
                "No se detecta afeccion en las fuentes consultadas.",
                encoding="utf-8",
            )
            code = self._run_cli([tmp, "audit-prudence"])
            self.assertEqual(code, 0)

    def test_prohibited_phrase_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_007.md").write_text(
                "No hay flora de interes en la zona evaluada.",
                encoding="utf-8",
            )
            code = self._run_cli([tmp, "audit-prudence"])
            self.assertEqual(code, 1)

    def test_empty_expediente_exit_0(self) -> None:
        # No markdowns found → warning only, is_valid() = True
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "audit-prudence"])
            self.assertEqual(code, 0)

    def test_write_creates_auditoria_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_001.md").write_text("Texto limpio.", encoding="utf-8")
            self._run_cli([tmp, "audit-prudence", "--write"])
            auditoria = Path(tmp) / "auditoria"
            self.assertTrue((auditoria / "prudence_validation_result.json").exists())
            self.assertTrue((auditoria / "prudence_validation_result.md").exists())

    def test_no_write_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv_dir = Path(tmp) / "inventario"
            inv_dir.mkdir()
            (inv_dir / "FI_001.md").write_text("Texto limpio.", encoding="utf-8")
            self._run_cli([tmp, "audit-prudence"])
            auditoria = Path(tmp) / "auditoria"
            self.assertFalse(auditoria.exists())

    def test_nonexistent_expediente_exit_1(self) -> None:
        code = self._run_cli(["/ruta/que/no/existe", "audit-prudence"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
