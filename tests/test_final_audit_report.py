"""
tests/test_final_audit_report.py
Tests para AU-04 — Informe final de auditoría JSON + Markdown.

Cubre:
  1.  FinalAuditIssue — to_dict, summary
  2.  FinalAuditResult — conteos, has_blocking, is_conforme, to_dict, summary
  3.  load_audit_json — válido, inexistente, corrupto
  4.  extract_final_issues_from_art45 — None, NO_CUBIERTO, PARCIAL, CUBIERTO
  5.  extract_final_issues_from_prudence — BLOQUEANTE, ALTA, MEDIA, None
  6.  extract_final_issues_from_traceability — ALTA, BLOQUEANTE umbral, MEDIA, None
  7.  determine_final_audit_status — CONFORME, CON_OBS, NO_CONFORME, INCOMPLETO
  8.  build_final_audit_result — combinación, administrative_ready, status, summaries
  9.  build_final_audit_report_markdown — secciones 1-9, aptitud admin
  10. build_final_audit_from_files — sin auditorías → INCOMPLETO, limpio → CONFORME
  11. write_final_audit_outputs — escribe JSON y MD
  12. CLI audit-final — exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.final_audit_report import (
    FINAL_AUDIT_STATUS,
    FINAL_AUDIT_SEVERITY,
    AUDIT_SOURCE,
    FinalAuditIssue,
    FinalAuditResult,
    build_final_audit_from_files,
    build_final_audit_report_markdown,
    build_final_audit_result,
    determine_final_audit_status,
    extract_final_issues_from_art45,
    extract_final_issues_from_block_consistency,
    extract_final_issues_from_conesa_check,
    extract_final_issues_from_conditional_chains,
    extract_final_issues_from_diagnostic_measures,
    extract_final_issues_from_prl_measures,
    extract_final_issues_from_prudence,
    extract_final_issues_from_traceability,
    load_audit_json,
    write_final_audit_outputs,
    _UNTRACED_BLOQUEANTE_THRESHOLD,
    _MISSING_CODE_PREFIX,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_issue(
    severity: str = "ALTA",
    source: str = "AU-01_ART45",
    code: str = "AU04-E001",
    message: str = "Test issue",
    recommendation: str = "Test rec",
) -> FinalAuditIssue:
    return FinalAuditIssue(
        severity=severity,
        source=source,
        code=code,
        message=message,
        recommendation=recommendation,
    )


def _make_result(
    status: str = "NO_CONFORME",
    blocking: int = 0,
    high: int = 1,
    medium: int = 0,
    low: int = 0,
) -> FinalAuditResult:
    issues = []
    for _ in range(blocking):
        issues.append(_make_issue("BLOQUEANTE"))
    for _ in range(high):
        issues.append(_make_issue("ALTA"))
    for _ in range(medium):
        issues.append(_make_issue("MEDIA"))
    for _ in range(low):
        issues.append(_make_issue("BAJA"))
    return FinalAuditResult(
        expediente_id="EIA-TEST",
        status=status,
        issues=issues,
        blocking_count=blocking,
        high_count=high,
        medium_count=medium,
        low_count=low,
    )


def _art45_data_ok() -> dict:
    """JSON limpio de AU-01 (todos cubiertos)."""
    return {
        "items": [
            {"requirement_id": "ART45-01", "title": "Req 1", "status": "CUBIERTO"},
            {"requirement_id": "ART45-02", "title": "Req 2", "status": "CUBIERTO"},
        ],
        "issues": [],
        "covered_count": 2,
        "partial_count": 0,
        "not_covered_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "is_structurally_complete": True,
        "administrative_ready": False,
    }


def _prudence_data_ok() -> dict:
    """JSON limpio de AU-02 (sin incidencias)."""
    return {
        "issues": [],
        "checked_sources": ["inventario/FI-001.md"],
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "is_valid": True,
    }


def _traceability_data_ok() -> dict:
    """JSON limpio de AU-03 (sin incidencias)."""
    return {
        "issues": [],
        "traced_claims": ["El factor FI-007 cumple"],
        "partial_claims": [],
        "untraced_claims": [],
        "references_loaded": [{"ref_id": "FI-007"}],
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "is_valid": True,
    }


# ---------------------------------------------------------------------------
# 1. TestFinalAuditIssue
# ---------------------------------------------------------------------------

class TestFinalAuditIssue(unittest.TestCase):

    def test_to_dict_keys(self) -> None:
        iss = _make_issue()
        d = iss.to_dict()
        for k in ("severity", "source", "code", "message", "recommendation",
                   "related_requirement", "related_file"):
            self.assertIn(k, d)

    def test_to_dict_values(self) -> None:
        iss = _make_issue(severity="BLOQUEANTE", code="AU04-TEST")
        d = iss.to_dict()
        self.assertEqual(d["severity"], "BLOQUEANTE")
        self.assertEqual(d["code"], "AU04-TEST")

    def test_to_dict_related_requirement_none_by_default(self) -> None:
        iss = _make_issue()
        self.assertIsNone(iss.to_dict()["related_requirement"])

    def test_summary_is_string(self) -> None:
        self.assertIsInstance(_make_issue().summary(), str)

    def test_summary_is_ascii_safe(self) -> None:
        iss = _make_issue(message="Afectación con tilde")
        iss.summary().encode("ascii")  # must not raise

    def test_summary_contains_severity(self) -> None:
        iss = _make_issue(severity="BLOQUEANTE")
        self.assertIn("BLOQUEANTE", iss.summary())

    def test_summary_contains_code(self) -> None:
        iss = _make_issue(code="AU04-M001")
        self.assertIn("AU04-M001", iss.summary())

    def test_related_requirement_in_to_dict(self) -> None:
        iss = FinalAuditIssue(
            severity="ALTA", source="AU-01_ART45", code="AU04-E102",
            message="msg", recommendation="rec", related_requirement="ART45-05"
        )
        self.assertEqual(iss.to_dict()["related_requirement"], "ART45-05")


# ---------------------------------------------------------------------------
# 2. TestFinalAuditResult
# ---------------------------------------------------------------------------

class TestFinalAuditResult(unittest.TestCase):

    def test_error_count_blocking_plus_high(self) -> None:
        r = _make_result(blocking=2, high=3)
        self.assertEqual(r.error_count(), 5)

    def test_has_blocking_issues_true(self) -> None:
        r = _make_result(blocking=1)
        self.assertTrue(r.has_blocking_issues())

    def test_has_blocking_issues_false(self) -> None:
        r = _make_result(blocking=0, high=2)
        self.assertFalse(r.has_blocking_issues())

    def test_is_conforme_true(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="CONFORME")
        self.assertTrue(r.is_conforme())

    def test_is_conforme_false_for_con_obs(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="CONFORME_CON_OBSERVACIONES")
        self.assertFalse(r.is_conforme())

    def test_is_conforme_false_for_no_conforme(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="NO_CONFORME")
        self.assertFalse(r.is_conforme())

    def test_administrative_ready_always_false(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="CONFORME", administrative_ready=True)
        self.assertFalse(r.administrative_ready)

    def test_to_dict_keys(self) -> None:
        r = _make_result()
        d = r.to_dict()
        for k in ("expediente_id", "status", "administrative_ready",
                   "art45_summary", "prudence_summary", "traceability_summary",
                   "issues", "blocking_count", "high_count", "medium_count",
                   "low_count", "error_count", "has_blocking_issues",
                   "is_conforme", "warnings", "notes"):
            self.assertIn(k, d)

    def test_to_dict_administrative_ready_always_false(self) -> None:
        r = _make_result()
        self.assertFalse(r.to_dict()["administrative_ready"])

    def test_to_dict_counts(self) -> None:
        r = _make_result(blocking=1, high=2, medium=3, low=1)
        d = r.to_dict()
        self.assertEqual(d["blocking_count"], 1)
        self.assertEqual(d["high_count"], 2)
        self.assertEqual(d["medium_count"], 3)
        self.assertEqual(d["low_count"], 1)

    def test_summary_is_ascii_safe(self) -> None:
        r = _make_result()
        r.summary().encode("ascii")

    def test_summary_contains_status(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="NO_CONFORME")
        self.assertIn("NO_CONFORME", r.summary())

    def test_summary_contains_no_declarada(self) -> None:
        r = _make_result()
        self.assertIn("NO DECLARADA", r.summary())


# ---------------------------------------------------------------------------
# 3. TestLoadAuditJson
# ---------------------------------------------------------------------------

class TestLoadAuditJson(unittest.TestCase):

    def test_existing_valid_json(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                         encoding="utf-8", delete=False) as f:
            json.dump({"test": True}, f)
            p = f.name
        result = load_audit_json(p)
        self.assertIsNotNone(result)
        self.assertEqual(result["test"], True)

    def test_nonexistent_returns_none(self) -> None:
        result = load_audit_json("/ruta/inexistente/file.json")
        self.assertIsNone(result)

    def test_corrupt_json_returns_error_dict(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("{ invalid json {{")
            p = f.name
        result = load_audit_json(p)
        self.assertIsNotNone(result)
        self.assertTrue(result.get("corrupt"))

    def test_corrupt_json_has_error_key(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write("not json at all!!!")
            p = f.name
        result = load_audit_json(p)
        self.assertIn("error", result)

    def test_path_as_string(self) -> None:
        result = load_audit_json("/ruta/que/no/existe.json")
        self.assertIsNone(result)

    def test_path_as_path_object(self) -> None:
        result = load_audit_json(Path("/ruta/que/no/existe.json"))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 4. TestExtractFinalIssuesFromArt45
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromArt45(unittest.TestCase):

    def test_none_generates_missing_issue(self) -> None:
        issues = extract_final_issues_from_art45(None)
        self.assertTrue(len(issues) > 0)
        self.assertTrue(any(iss.code.startswith(_MISSING_CODE_PREFIX) for iss in issues))

    def test_no_cubierto_generates_alta(self) -> None:
        data = {
            "items": [
                {"requirement_id": "ART45-03", "title": "Alternativas", "status": "NO_CUBIERTO"}
            ],
            "issues": [],
        }
        issues = extract_final_issues_from_art45(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))
        alta = [i for i in issues if i.severity == "ALTA"]
        self.assertTrue(any("ART45-03" in i.message for i in alta))

    def test_parcial_generates_media(self) -> None:
        data = {
            "items": [
                {"requirement_id": "ART45-05", "title": "Efectos", "status": "PARCIAL"}
            ],
            "issues": [],
        }
        issues = extract_final_issues_from_art45(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_cubierto_generates_no_issue(self) -> None:
        data = {
            "items": [
                {"requirement_id": "ART45-01", "title": "Motivacion", "status": "CUBIERTO"}
            ],
            "issues": [],
        }
        issues = extract_final_issues_from_art45(data)
        self.assertEqual(len(issues), 0)

    def test_error_issue_generates_alta(self) -> None:
        data = {
            "items": [],
            "issues": [
                {"severity": "ERROR", "code": "AU01-E001",
                 "message": "Error estructural", "recommendation": "Corregir",
                 "requirement_id": "ART45-02"}
            ],
        }
        issues = extract_final_issues_from_art45(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_warning_issue_generates_baja(self) -> None:
        data = {
            "items": [],
            "issues": [
                {"severity": "WARNING", "code": "AU01-W001",
                 "message": "Aviso", "recommendation": "Revisar",
                 "requirement_id": None}
            ],
        }
        issues = extract_final_issues_from_art45(data)
        self.assertTrue(any(i.severity == "BAJA" for i in issues))

    def test_corrupt_data_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "JSON decode error"}
        issues = extract_final_issues_from_art45(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_related_requirement_set(self) -> None:
        data = {
            "items": [
                {"requirement_id": "ART45-08", "title": "Medidas", "status": "NO_CUBIERTO"}
            ],
            "issues": [],
        }
        issues = extract_final_issues_from_art45(data)
        alta = [i for i in issues if i.severity == "ALTA"]
        self.assertTrue(any(i.related_requirement == "ART45-08" for i in alta))


# ---------------------------------------------------------------------------
# 5. TestExtractFinalIssuesFromPrudence
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromPrudence(unittest.TestCase):

    def test_none_generates_missing_issue(self) -> None:
        issues = extract_final_issues_from_prudence(None)
        self.assertTrue(any(iss.code.startswith(_MISSING_CODE_PREFIX) for iss in issues))

    def test_error_sin_afeccion_generates_bloqueante(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU02-E001",
                    "phrase": "sin afeccion",
                    "source": "inventario/FI-007",
                    "message": "Frase prohibida detectada: 'sin afeccion'",
                    "recommendation": "Sustituir",
                }
            ]
        }
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "BLOQUEANTE" for i in issues))

    def test_error_cumple_limites_generates_bloqueante(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU02-E001",
                    "phrase": "cumple limites",
                    "source": "bloques/B.md",
                    "message": "Frase: cumple limites",
                    "recommendation": "Sustituir",
                }
            ]
        }
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "BLOQUEANTE" for i in issues))

    def test_error_other_phrase_generates_alta(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU02-E001",
                    "phrase": "se descarta",
                    "source": "inventario/FI-001",
                    "message": "Frase prohibida: se descarta",
                    "recommendation": "Sustituir",
                }
            ]
        }
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))
        self.assertFalse(any(i.severity == "BLOQUEANTE" for i in issues))

    def test_warning_generates_media(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "WARNING",
                    "code": "AU02-W001",
                    "phrase": "despreciable",
                    "source": "inventario/FI-003",
                    "message": "Lenguaje debil",
                    "recommendation": "Revisar",
                }
            ]
        }
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_info_generates_info(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "INFO",
                    "code": "AU02-I001",
                    "phrase": "sin afeccion",
                    "source": "src/prudence_validator.py",
                    "message": "Frase en contexto metodologico",
                    "recommendation": "",
                }
            ]
        }
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "INFO" for i in issues))

    def test_empty_issues_no_problems(self) -> None:
        data = {"issues": [], "error_count": 0}
        issues = extract_final_issues_from_prudence(data)
        self.assertEqual(issues, [])

    def test_corrupt_data_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "decode error"}
        issues = extract_final_issues_from_prudence(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))


# ---------------------------------------------------------------------------
# 6. TestExtractFinalIssuesFromTraceability
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromTraceability(unittest.TestCase):

    def test_none_generates_missing_issue(self) -> None:
        issues = extract_final_issues_from_traceability(None)
        self.assertTrue(any(iss.code.startswith(_MISSING_CODE_PREFIX) for iss in issues))

    def test_error_generates_alta(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU03-E001",
                    "source": "bloques/B.md",
                    "claim": "La parcela tiene 50 ha.",
                    "message": "Afirmacion no trazada",
                    "recommendation": "Incluir ID",
                    "candidate_refs": [],
                }
            ],
            "untraced_claims": ["La parcela tiene 50 ha."],
        }
        issues = extract_final_issues_from_traceability(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_many_untraced_generates_bloqueante(self) -> None:
        untraced = [f"Claim tecnico {i} con 10 ha de extension." for i in range(_UNTRACED_BLOQUEANTE_THRESHOLD + 1)]
        data = {
            "issues": [],
            "untraced_claims": untraced,
        }
        issues = extract_final_issues_from_traceability(data)
        self.assertTrue(any(i.severity == "BLOQUEANTE" for i in issues))

    def test_few_untraced_no_bloqueante(self) -> None:
        # Exactly at threshold (not over)
        untraced = [f"Claim {i}" for i in range(_UNTRACED_BLOQUEANTE_THRESHOLD)]
        data = {
            "issues": [],
            "untraced_claims": untraced,
        }
        issues = extract_final_issues_from_traceability(data)
        self.assertFalse(any(i.severity == "BLOQUEANTE" for i in issues))

    def test_warning_generates_media(self) -> None:
        data = {
            "issues": [
                {
                    "severity": "WARNING",
                    "code": "AU03-W001",
                    "source": "inventario/FI-007.md",
                    "claim": "La fauna del area",
                    "message": "Afirmacion parcial",
                    "recommendation": "Incluir ID",
                    "candidate_refs": ["FI-008"],
                }
            ],
            "untraced_claims": [],
        }
        issues = extract_final_issues_from_traceability(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_empty_no_issues(self) -> None:
        data = {"issues": [], "untraced_claims": []}
        issues = extract_final_issues_from_traceability(data)
        self.assertEqual(issues, [])

    def test_corrupt_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "JSON decode error"}
        issues = extract_final_issues_from_traceability(data)
        self.assertTrue(any(i.severity == "ALTA" for i in issues))


# ---------------------------------------------------------------------------
# 7. TestDetermineFinalAuditStatus
# ---------------------------------------------------------------------------

class TestDetermineFinalAuditStatus(unittest.TestCase):

    def test_no_issues_conforme(self) -> None:
        self.assertEqual(determine_final_audit_status([]), "CONFORME")

    def test_only_info_conforme(self) -> None:
        issues = [_make_issue("INFO")]
        self.assertEqual(determine_final_audit_status(issues), "CONFORME")

    def test_media_conforme_con_observaciones(self) -> None:
        issues = [_make_issue("MEDIA")]
        self.assertEqual(
            determine_final_audit_status(issues), "CONFORME_CON_OBSERVACIONES"
        )

    def test_baja_conforme_con_observaciones(self) -> None:
        issues = [_make_issue("BAJA")]
        self.assertEqual(
            determine_final_audit_status(issues), "CONFORME_CON_OBSERVACIONES"
        )

    def test_alta_no_conforme(self) -> None:
        issues = [_make_issue("ALTA")]
        self.assertEqual(determine_final_audit_status(issues), "NO_CONFORME")

    def test_bloqueante_no_conforme(self) -> None:
        issues = [_make_issue("BLOQUEANTE")]
        self.assertEqual(determine_final_audit_status(issues), "NO_CONFORME")

    def test_missing_audit_incompleto(self) -> None:
        # Missing code prefix → INCOMPLETO
        issues = [_make_issue("ALTA", code=f"{_MISSING_CODE_PREFIX}001")]
        self.assertEqual(determine_final_audit_status(issues), "INCOMPLETO")

    def test_missing_has_priority_over_bloqueante(self) -> None:
        issues = [
            _make_issue("BLOQUEANTE"),
            _make_issue("ALTA", code=f"{_MISSING_CODE_PREFIX}002"),
        ]
        self.assertEqual(determine_final_audit_status(issues), "INCOMPLETO")

    def test_mixed_alta_and_media_no_conforme(self) -> None:
        issues = [_make_issue("ALTA"), _make_issue("MEDIA")]
        self.assertEqual(determine_final_audit_status(issues), "NO_CONFORME")


# ---------------------------------------------------------------------------
# 8. TestBuildFinalAuditResult
# ---------------------------------------------------------------------------

class TestBuildFinalAuditResult(unittest.TestCase):

    def test_all_clean_is_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_all_none_is_incompleto(self) -> None:
        result = build_final_audit_result("EIA-TEST", None, None, None)
        self.assertEqual(result.status, "INCOMPLETO")

    def test_one_missing_is_incompleto(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=None,
            traceability_data=_traceability_data_ok(),
        )
        self.assertEqual(result.status, "INCOMPLETO")

    def test_administrative_ready_always_false(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertFalse(result.administrative_ready)

    def test_art45_no_cubierto_is_no_conforme(self) -> None:
        bad_art45 = {
            "items": [
                {"requirement_id": "ART45-05", "title": "Efectos", "status": "NO_CUBIERTO"}
            ],
            "issues": [],
        }
        result = build_final_audit_result(
            "EIA-TEST", bad_art45, _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_prudence_error_no_conforme(self) -> None:
        bad_prudence = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU02-E001",
                    "phrase": "se descarta",
                    "source": "test.md",
                    "message": "Error prudencia",
                    "recommendation": "Corregir",
                }
            ]
        }
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), bad_prudence, _traceability_data_ok()
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_art45_summary_present(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertIn("available", result.art45_summary)
        self.assertTrue(result.art45_summary["available"])

    def test_prudence_summary_present(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertIn("available", result.prudence_summary)

    def test_traceability_summary_present(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertIn("available", result.traceability_summary)

    def test_notes_contain_calificacion_interna(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok()
        )
        self.assertTrue(any("calificacion" in n.lower() for n in result.notes))

    def test_blocking_count_correct(self) -> None:
        bad_prudence = {
            "issues": [
                {
                    "severity": "ERROR",
                    "code": "AU02-E001",
                    "phrase": "sin afeccion",
                    "source": "test.md",
                    "message": "Cierre indebido",
                    "recommendation": "Corregir",
                }
            ]
        }
        result = build_final_audit_result(
            "EIA-TEST", _art45_data_ok(), bad_prudence, _traceability_data_ok()
        )
        self.assertGreater(result.blocking_count, 0)


# ---------------------------------------------------------------------------
# 9. TestBuildFinalAuditReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildFinalAuditReportMarkdown(unittest.TestCase):

    def _result_no_conforme(self) -> FinalAuditResult:
        return _make_result("NO_CONFORME", high=2, medium=1)

    def test_has_section_1_resumen(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 1. Resumen ejecutivo", md)

    def test_has_section_2_au01(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 2. Resultado AU-01", md)

    def test_has_section_3_au02(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 3. Resultado AU-02", md)

    def test_has_section_4_au03(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 4. Resultado AU-03", md)

    def test_has_section_5_rd04(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 5. Resultado RD-04", md)

    def test_has_section_6_rd06(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 6. Resultado RD-06", md)

    def test_has_section_9_im09(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 9. Resultado IM-09", md)

    def test_has_section_10_bloqueantes(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 10. Incidencias bloqueantes", md)

    def test_has_section_11_altas(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 11. Incidencias altas", md)

    def test_has_section_12_medias_bajas(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 12. Incidencias medias y bajas", md)

    def test_has_section_13_recomendaciones(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 13. Recomendaciones prioritarias", md)

    def test_has_section_14_conclusion(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("## 14. Conclusion final", md)

    def test_no_declara_aptitud_administrativa(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        import unicodedata
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertIn("no declara", norm)

    def test_no_apto_para_presentacion(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        import unicodedata
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertIn("no declara", norm)

    def test_status_in_resumen(self) -> None:
        md = build_final_audit_report_markdown(self._result_no_conforme())
        self.assertIn("NO_CONFORME", md)

    def test_conforme_result_shows_conforme(self) -> None:
        r = FinalAuditResult(expediente_id="EIA", status="CONFORME")
        md = build_final_audit_report_markdown(r)
        self.assertIn("CONFORME", md)

    def test_returns_string(self) -> None:
        md = build_final_audit_report_markdown(FinalAuditResult(expediente_id="EIA", status="CONFORME"))
        self.assertIsInstance(md, str)


# ---------------------------------------------------------------------------
# 10. TestBuildFinalAuditFromFiles
# ---------------------------------------------------------------------------

class TestBuildFinalAuditFromFiles(unittest.TestCase):

    def test_raises_if_expediente_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            build_final_audit_from_files("/ruta/inexistente")

    def test_without_audits_is_incompleto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "INCOMPLETO")

    def test_with_three_clean_audits_is_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")

    def test_with_prudence_error_is_no_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            bad_prudence = {
                "issues": [
                    {
                        "severity": "ERROR",
                        "code": "AU02-E001",
                        "phrase": "se descarta",
                        "source": "test.md",
                        "message": "Error",
                        "recommendation": "Corregir",
                    }
                ]
            }
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(bad_prudence), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_expediente_id_from_dirname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.expediente_id, Path(tmp).name)

    def test_administrative_ready_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = build_final_audit_from_files(tmp)
            self.assertFalse(result.administrative_ready)


# ---------------------------------------------------------------------------
# 11. TestWriteFinalAuditOutputs
# ---------------------------------------------------------------------------

class TestWriteFinalAuditOutputs(unittest.TestCase):

    def _make_result(self) -> FinalAuditResult:
        return _make_result("NO_CONFORME", high=1)

    def test_writes_json_and_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_final_audit_outputs(self._make_result(), out)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, _ = write_final_audit_outputs(self._make_result(), out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("status", data)
            self.assertIn("issues", data)
            self.assertIn("administrative_ready", data)

    def test_json_administrative_ready_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, _ = write_final_audit_outputs(self._make_result(), out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertFalse(data["administrative_ready"])

    def test_md_has_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            _, md_path = write_final_audit_outputs(self._make_result(), out)
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Resumen ejecutivo", content)
            self.assertIn("## 14. Conclusion final", content)

    def test_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nuevo" / "auditoria"
            self.assertFalse(out.exists())
            write_final_audit_outputs(self._make_result(), out)
            self.assertTrue(out.exists())

    def test_filenames_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_final_audit_outputs(self._make_result(), out)
            self.assertEqual(json_path.name, "final_audit_result.json")
            self.assertEqual(md_path.name, "final_audit_result.md")

    def test_returns_tuple_of_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            result = write_final_audit_outputs(self._make_result(), out)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# 12. TestExtractFinalIssuesFromBlockConsistency (RD-04)
# ---------------------------------------------------------------------------


def _block_consistency_data_ok() -> dict:
    return {
        "status": "COHERENTE",
        "checked_blocks": ["bloques/bloque_H.md"],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "is_valid": True,
    }


def _block_consistency_data_errors() -> dict:
    return {
        "status": "INCOHERENTE",
        "checked_blocks": ["bloques/bloque_H.md", "bloques/bloque_J.md"],
        "issues": [
            {
                "severity": "ERROR",
                "code": "BC-RN-001",
                "source_block": "bloques/bloque_H.md",
                "target_block": "bloques/bloque_J.md",
                "message": "Red Natura cautela vs cierre",
                "recommendation": "Revisar",
                "evidence": ["sin afeccion apreciable"],
            }
        ],
        "error_count": 1,
        "warning_count": 0,
        "is_valid": False,
    }


def _conesa_check_data_ok() -> dict:
    return {
        "status": "OK",
        "checked_impacts": ["IMP-001"],
        "valued_impacts": ["IMP-001"],
        "indeterminate_impacts": [],
        "impacts_missing_conesa": [],
        "impacts_missing_markdown": [],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "is_valid": True,
    }


def _conesa_check_data_errors() -> dict:
    return {
        "status": "NO_CONFORME",
        "checked_impacts": ["IMP-001"],
        "valued_impacts": [],
        "indeterminate_impacts": [],
        "impacts_missing_conesa": ["IMP-001"],
        "impacts_missing_markdown": [],
        "issues": [
            {
                "severity": "ERROR",
                "code": "CC-B001",
                "impact_id": "IMP-001",
                "message": "IMP-001 sin atributos Conesa",
                "recommendation": "Completar",
                "evidence": ["intensidad", "extension"],
            }
        ],
        "error_count": 1,
        "warning_count": 0,
        "is_valid": False,
    }


class TestExtractFinalIssuesFromBlockConsistency(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        # None → backward compatible: no issue generated, no status change
        issues = extract_final_issues_from_block_consistency(None)
        self.assertEqual(issues, [])

    def test_none_no_incompleto(self) -> None:
        # Missing RD-04 must NOT trigger INCOMPLETO
        issues = extract_final_issues_from_block_consistency(None)
        self.assertFalse(any(i.code.startswith(_MISSING_CODE_PREFIX) for i in issues))

    def test_clean_data_no_issues(self) -> None:
        issues = extract_final_issues_from_block_consistency(_block_consistency_data_ok())
        self.assertEqual(issues, [])

    def test_error_generates_alta(self) -> None:
        issues = extract_final_issues_from_block_consistency(_block_consistency_data_errors())
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_corrupt_generates_alta(self) -> None:
        issues = extract_final_issues_from_block_consistency(
            {"corrupt": True, "error": "JSON error"}
        )
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_sin_datos_generates_media(self) -> None:
        issues = extract_final_issues_from_block_consistency({"status": "SIN_DATOS"})
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_source_is_rd04(self) -> None:
        issues = extract_final_issues_from_block_consistency(_block_consistency_data_errors())
        self.assertTrue(
            any("RD-04" in i.source or "SISTEMA" in i.source for i in issues)
        )


class TestExtractFinalIssuesFromConesaCheck(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        # None → backward compatible: no issue generated, no status change
        issues = extract_final_issues_from_conesa_check(None)
        self.assertEqual(issues, [])

    def test_none_no_incompleto(self) -> None:
        issues = extract_final_issues_from_conesa_check(None)
        self.assertFalse(any(i.code.startswith(_MISSING_CODE_PREFIX) for i in issues))

    def test_clean_data_no_issues(self) -> None:
        issues = extract_final_issues_from_conesa_check(_conesa_check_data_ok())
        self.assertEqual(issues, [])

    def test_error_generates_alta(self) -> None:
        issues = extract_final_issues_from_conesa_check(_conesa_check_data_errors())
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_missing_conesa_generates_alta(self) -> None:
        issues = extract_final_issues_from_conesa_check(_conesa_check_data_errors())
        # Should include AU04-E502 for missing_conesa
        self.assertTrue(any("E502" in i.code for i in issues))

    def test_corrupt_generates_alta(self) -> None:
        issues = extract_final_issues_from_conesa_check(
            {"corrupt": True, "error": "JSON error"}
        )
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_source_is_rd06(self) -> None:
        issues = extract_final_issues_from_conesa_check(_conesa_check_data_errors())
        self.assertTrue(
            any("RD-06" in i.source or "SISTEMA" in i.source for i in issues)
        )


class TestBuildFinalAuditResultWithRD04RD06(unittest.TestCase):

    def test_all_five_clean_is_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
            conesa_check_data=_conesa_check_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_rd04_error_is_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            block_consistency_data=_block_consistency_data_errors(),
            conesa_check_data=_conesa_check_data_ok(),
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_rd06_error_is_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
            conesa_check_data=_conesa_check_data_errors(),
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_rd06_missing_conesa_is_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
            conesa_check_data=_conesa_check_data_errors(),
        )
        # impacts_missing_conesa → ALTA → NO_CONFORME
        self.assertEqual(result.status, "NO_CONFORME")

    def test_falta_rd04_rd06_sigue_conforme(self) -> None:
        # Missing RD-04 and RD-06 (None) → no extra issues → CONFORME
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            # block_consistency_data not provided (None by default)
            # conesa_check_data not provided (None by default)
        )
        # None inputs generate no issues → same result as 3-audit clean
        self.assertEqual(result.status, "CONFORME")

    def test_block_consistency_summary_in_result(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
        )
        self.assertIn("available", result.block_consistency_summary)
        self.assertTrue(result.block_consistency_summary["available"])

    def test_conesa_check_summary_in_result(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            conesa_check_data=_conesa_check_data_ok(),
        )
        self.assertIn("available", result.conesa_check_summary)
        self.assertTrue(result.conesa_check_summary["available"])

    def test_to_dict_includes_new_summaries(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
            conesa_check_data=_conesa_check_data_ok(),
        )
        d = result.to_dict()
        self.assertIn("block_consistency_summary", d)
        self.assertIn("conesa_check_summary", d)

    def test_notes_mention_rd04_rd06(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
        )
        notes_text = " ".join(result.notes)
        self.assertIn("RD-04", notes_text)
        self.assertIn("RD-06", notes_text)


class TestBuildFinalAuditFromFilesWithRD04RD06(unittest.TestCase):

    def test_with_five_clean_audits_is_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "block_consistency_result.json").write_text(
                json.dumps(_block_consistency_data_ok()), encoding="utf-8"
            )
            (aud / "conesa_check_result.json").write_text(
                json.dumps(_conesa_check_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")

    def test_with_rd04_errors_is_no_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "block_consistency_result.json").write_text(
                json.dumps(_block_consistency_data_errors()), encoding="utf-8"
            )
            (aud / "conesa_check_result.json").write_text(
                json.dumps(_conesa_check_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_markdown_mentions_rd04_rd06(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            md = build_final_audit_report_markdown(result)
            self.assertIn("RD-04", md)
            self.assertIn("RD-06", md)

    def test_json_includes_new_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            d = result.to_dict()
            self.assertIn("block_consistency_summary", d)
            self.assertIn("conesa_check_summary", d)


# ---------------------------------------------------------------------------
# 13. TestCLIAuditFinal (formerly 12)
# ---------------------------------------------------------------------------

class TestCLIAuditFinal(unittest.TestCase):

    def _run_cli(self, argv: list[str]) -> int:
        from run_expediente import main
        return main(argv)

    def test_incompleto_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "audit-final"])
            self.assertEqual(code, 1)

    def test_conforme_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            code = self._run_cli([tmp, "audit-final"])
            self.assertEqual(code, 0)

    def test_no_conforme_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            bad_art45 = {
                "items": [
                    {"requirement_id": "ART45-05", "title": "Efectos", "status": "NO_CUBIERTO"}
                ],
                "issues": [],
            }
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(bad_art45), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            code = self._run_cli([tmp, "audit-final"])
            self.assertEqual(code, 1)

    def test_no_write_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli([tmp, "audit-final"])
            aud = Path(tmp) / "auditoria"
            self.assertFalse((aud / "final_audit_result.json").exists())

    def test_write_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            self._run_cli([tmp, "audit-final", "--write"])
            self.assertTrue((aud / "final_audit_result.json").exists())
            self.assertTrue((aud / "final_audit_result.md").exists())

    def test_nonexistent_expediente_exit_1(self) -> None:
        code = self._run_cli(["/ruta/que/no/existe", "audit-final"])
        self.assertEqual(code, 1)

    def test_conforme_con_obs_exit_0(self) -> None:
        # CONFORME_CON_OBSERVACIONES → exit 0
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            parcial_art45 = {
                "items": [
                    {"requirement_id": "ART45-03", "title": "Alternativas", "status": "PARCIAL"}
                ],
                "issues": [],
            }
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(parcial_art45), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            code = self._run_cli([tmp, "audit-final"])
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Fixtures RD-08 / RD-09
# ---------------------------------------------------------------------------

def _diagnostic_measure_data_ok() -> dict:
    return {
        "status": "OK",
        "checked_measures": ["MED-001"],
        "diagnostic_measures": ["MED-001"],
        "problematic_measures": [],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "is_valid": True,
    }


def _diagnostic_measure_data_errors() -> dict:
    return {
        "status": "NO_CONFORME",
        "checked_measures": ["MED-001"],
        "diagnostic_measures": ["MED-001"],
        "problematic_measures": ["MED-001"],
        "issues": [
            {
                "severity": "ERROR",
                "code": "RD08-E002",
                "measure_id": "MED-001",
                "impact_id": "IMP-001",
                "message": "Medida diagnostica usada como reductora",
                "recommendation": "Anadir medida correctora real",
                "evidence": [],
            }
        ],
        "error_count": 1,
        "warning_count": 0,
        "is_valid": False,
    }


def _prl_measure_data_ok() -> dict:
    return {
        "status": "OK",
        "checked_measures": ["MED-010"],
        "prl_measures": ["MED-010"],
        "problematic_measures": [],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "is_valid": True,
    }


def _prl_measure_data_errors() -> dict:
    return {
        "status": "NO_CONFORME",
        "checked_measures": ["MED-010"],
        "prl_measures": ["MED-010"],
        "problematic_measures": ["MED-010"],
        "issues": [
            {
                "severity": "ERROR",
                "code": "RD09-E001",
                "measure_id": "MED-010",
                "impact_id": None,
                "source": "model",
                "message": "EPI declarado como CORRECTORA",
                "recommendation": "Cambiar measure_type a PRL_NO_EIA",
                "evidence": [],
            }
        ],
        "error_count": 1,
        "warning_count": 0,
        "is_valid": False,
    }


# ---------------------------------------------------------------------------
# 16. TestExtractFinalIssuesFromDiagnosticMeasures (RD-08)
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromDiagnosticMeasures(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(None)
        self.assertEqual(issues, [])

    def test_none_no_incompleto(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(None)
        self.assertFalse(any(i.code.startswith(_MISSING_CODE_PREFIX) for i in issues))

    def test_clean_data_no_issues(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(_diagnostic_measure_data_ok())
        self.assertEqual(issues, [])

    def test_error_generates_alta(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(_diagnostic_measure_data_errors())
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_problematic_measures_generates_alta(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(_diagnostic_measure_data_errors())
        alta = [i for i in issues if i.severity == "ALTA"]
        self.assertTrue(len(alta) > 0)
        self.assertTrue(any(i.code == "AU04-E603" for i in alta))

    def test_sin_datos_generates_media(self) -> None:
        data = {"status": "SIN_DATOS", "problematic_measures": [], "issues": []}
        issues = extract_final_issues_from_diagnostic_measures(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_corrupt_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "json error"}
        issues = extract_final_issues_from_diagnostic_measures(data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ALTA")
        self.assertEqual(issues[0].code, "AU04-E601")

    def test_source_is_rd08(self) -> None:
        issues = extract_final_issues_from_diagnostic_measures(_diagnostic_measure_data_errors())
        self.assertTrue(all("RD-08" in i.source for i in issues))


# ---------------------------------------------------------------------------
# 17. TestExtractFinalIssuesFromPrlMeasures (RD-09)
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromPrlMeasures(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        issues = extract_final_issues_from_prl_measures(None)
        self.assertEqual(issues, [])

    def test_none_no_incompleto(self) -> None:
        issues = extract_final_issues_from_prl_measures(None)
        self.assertFalse(any(i.code.startswith(_MISSING_CODE_PREFIX) for i in issues))

    def test_clean_data_no_issues(self) -> None:
        issues = extract_final_issues_from_prl_measures(_prl_measure_data_ok())
        self.assertEqual(issues, [])

    def test_error_generates_alta(self) -> None:
        issues = extract_final_issues_from_prl_measures(_prl_measure_data_errors())
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_problematic_measures_generates_alta(self) -> None:
        issues = extract_final_issues_from_prl_measures(_prl_measure_data_errors())
        self.assertTrue(any(i.code == "AU04-E703" for i in issues))

    def test_sin_datos_generates_media(self) -> None:
        data = {"status": "SIN_DATOS", "problematic_measures": [], "issues": []}
        issues = extract_final_issues_from_prl_measures(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_corrupt_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "json error"}
        issues = extract_final_issues_from_prl_measures(data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ALTA")
        self.assertEqual(issues[0].code, "AU04-E701")

    def test_source_is_rd09(self) -> None:
        issues = extract_final_issues_from_prl_measures(_prl_measure_data_errors())
        self.assertTrue(all("RD-09" in i.source for i in issues))


# ---------------------------------------------------------------------------
# 18. TestBuildFinalAuditResultWithRD08RD09
# ---------------------------------------------------------------------------

class TestBuildFinalAuditResultWithRD08RD09(unittest.TestCase):

    def test_all_seven_clean_is_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            block_consistency_data=_block_consistency_data_ok(),
            conesa_check_data=_conesa_check_data_ok(),
            diagnostic_measure_data=_diagnostic_measure_data_ok(),
            prl_measure_data=_prl_measure_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_rd08_errors_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            diagnostic_measure_data=_diagnostic_measure_data_errors(),
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_rd09_errors_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            prl_measure_data=_prl_measure_data_errors(),
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_rd08_warnings_con_observaciones(self) -> None:
        data = {
            "status": "CON_OBSERVACIONES",
            "problematic_measures": [],
            "issues": [
                {
                    "severity": "WARNING",
                    "code": "RD08-W001",
                    "measure_id": "MED-001",
                    "impact_id": "IMP-001",
                    "message": "Medida diagnostica vinculada a impacto mejorado",
                    "recommendation": "Verificar",
                    "evidence": [],
                }
            ],
            "error_count": 0,
            "warning_count": 1,
        }
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            diagnostic_measure_data=data,
        )
        self.assertEqual(result.status, "CONFORME_CON_OBSERVACIONES")

    def test_rd09_warnings_con_observaciones(self) -> None:
        data = {
            "status": "CON_OBSERVACIONES",
            "problematic_measures": [],
            "issues": [
                {
                    "severity": "WARNING",
                    "code": "RD09-W001",
                    "measure_id": "MED-010",
                    "impact_id": None,
                    "source": "model",
                    "message": "PRL vinculada a impacto sin NO_EIA status",
                    "recommendation": "Cambiar status",
                    "evidence": [],
                }
            ],
            "error_count": 0,
            "warning_count": 1,
        }
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            prl_measure_data=data,
        )
        self.assertEqual(result.status, "CONFORME_CON_OBSERVACIONES")

    def test_none_rd08_rd09_stays_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_rd08_rd09_summaries_in_result(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            diagnostic_measure_data=_diagnostic_measure_data_ok(),
            prl_measure_data=_prl_measure_data_ok(),
        )
        self.assertIn("available", result.diagnostic_measure_summary)
        self.assertIn("available", result.prl_measure_summary)
        self.assertTrue(result.diagnostic_measure_summary["available"])
        self.assertTrue(result.prl_measure_summary["available"])

    def test_markdown_has_rd08_section(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            diagnostic_measure_data=_diagnostic_measure_data_ok(),
        )
        md = build_final_audit_report_markdown(result)
        self.assertIn("## 7. Resultado RD-08", md)

    def test_markdown_has_rd09_section(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            prl_measure_data=_prl_measure_data_ok(),
        )
        md = build_final_audit_report_markdown(result)
        self.assertIn("## 8. Resultado RD-09", md)

    def test_to_dict_contains_new_summaries(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
        )
        d = result.to_dict()
        self.assertIn("diagnostic_measure_summary", d)
        self.assertIn("prl_measure_summary", d)


# ---------------------------------------------------------------------------
# 19. TestBuildFinalAuditFromFilesWithRD08RD09
# ---------------------------------------------------------------------------

class TestBuildFinalAuditFromFilesWithRD08RD09(unittest.TestCase):

    def test_with_rd08_rd09_files_loads_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "diagnostic_measure_validation_result.json").write_text(
                json.dumps(_diagnostic_measure_data_ok()), encoding="utf-8"
            )
            (aud / "prl_measure_validation_result.json").write_text(
                json.dumps(_prl_measure_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")
            self.assertTrue(result.diagnostic_measure_summary.get("available"))
            self.assertTrue(result.prl_measure_summary.get("available"))

    def test_with_rd08_errors_no_conforme_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "diagnostic_measure_validation_result.json").write_text(
                json.dumps(_diagnostic_measure_data_errors()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_without_rd08_rd09_stays_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")


# ---------------------------------------------------------------------------
# Fixtures IM-09
# ---------------------------------------------------------------------------

def _conditional_chain_data_ok() -> dict:
    return {
        "status": "OK",
        "checked_impacts": ["IMP-001"],
        "conditioned_impacts": [],
        "conditioned_measures": [],
        "conditioned_pva_programs": [],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "is_valid": True,
    }


def _conditional_chain_data_errors() -> dict:
    return {
        "status": "NO_CONFORME",
        "checked_impacts": ["IMP-001"],
        "conditioned_impacts": ["IMP-001"],
        "conditioned_measures": [],
        "conditioned_pva_programs": [],
        "issues": [
            {
                "severity": "ERROR",
                "code": "CC-IMP-E001",
                "impact_id": "IMP-001",
                "measure_id": None,
                "pva_id": None,
                "message": "Impacto condicionado IMP-001 sin medidas ni PVA asociados",
                "recommendation": "Asociar medidas condicionadas al impacto",
                "evidence": [],
            }
        ],
        "error_count": 1,
        "warning_count": 0,
        "is_valid": False,
    }


def _conditional_chain_data_warnings() -> dict:
    return {
        "status": "CON_OBSERVACIONES",
        "checked_impacts": ["IMP-001"],
        "conditioned_impacts": ["IMP-001"],
        "conditioned_measures": ["MED-001"],
        "conditioned_pva_programs": [],
        "issues": [
            {
                "severity": "WARNING",
                "code": "CC-MEA-W001",
                "impact_id": None,
                "measure_id": "MED-001",
                "pva_id": None,
                "message": "Medida condicionada MED-001 sin PVA vinculado",
                "recommendation": "Crear PVA condicionado para MED-001",
                "evidence": [],
            }
        ],
        "error_count": 0,
        "warning_count": 1,
        "is_valid": True,
    }


# ---------------------------------------------------------------------------
# 20. TestExtractFinalIssuesFromConditionalChains (IM-09)
# ---------------------------------------------------------------------------

class TestExtractFinalIssuesFromConditionalChains(unittest.TestCase):

    def test_none_returns_empty(self) -> None:
        issues = extract_final_issues_from_conditional_chains(None)
        self.assertEqual(issues, [])

    def test_none_no_incompleto(self) -> None:
        issues = extract_final_issues_from_conditional_chains(None)
        self.assertFalse(any(i.code.startswith(_MISSING_CODE_PREFIX) for i in issues))

    def test_clean_data_no_issues(self) -> None:
        issues = extract_final_issues_from_conditional_chains(_conditional_chain_data_ok())
        self.assertEqual(issues, [])

    def test_error_generates_alta(self) -> None:
        issues = extract_final_issues_from_conditional_chains(_conditional_chain_data_errors())
        self.assertTrue(any(i.severity == "ALTA" for i in issues))

    def test_warning_generates_media(self) -> None:
        issues = extract_final_issues_from_conditional_chains(_conditional_chain_data_warnings())
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_sin_datos_generates_media(self) -> None:
        data = {"status": "SIN_DATOS", "issues": []}
        issues = extract_final_issues_from_conditional_chains(data)
        self.assertTrue(any(i.severity == "MEDIA" for i in issues))

    def test_corrupt_generates_alta(self) -> None:
        data = {"corrupt": True, "error": "json error"}
        issues = extract_final_issues_from_conditional_chains(data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ALTA")
        self.assertEqual(issues[0].code, "AU04-E801")

    def test_source_is_im09(self) -> None:
        issues = extract_final_issues_from_conditional_chains(_conditional_chain_data_errors())
        self.assertTrue(all("IM-09" in i.source for i in issues))


# ---------------------------------------------------------------------------
# 21. TestBuildFinalAuditResultWithIM09
# ---------------------------------------------------------------------------

class TestBuildFinalAuditResultWithIM09(unittest.TestCase):

    def test_all_clean_including_im09_is_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_im09_errors_no_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_errors(),
        )
        self.assertEqual(result.status, "NO_CONFORME")

    def test_im09_warnings_con_observaciones(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_warnings(),
        )
        self.assertEqual(result.status, "CONFORME_CON_OBSERVACIONES")

    def test_none_im09_stays_conforme(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            art45_data=_art45_data_ok(),
            prudence_data=_prudence_data_ok(),
            traceability_data=_traceability_data_ok(),
        )
        self.assertEqual(result.status, "CONFORME")

    def test_im09_summary_in_result(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_ok(),
        )
        self.assertIn("available", result.conditional_chain_summary)
        self.assertTrue(result.conditional_chain_summary["available"])

    def test_to_dict_contains_im09_summary(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
        )
        d = result.to_dict()
        self.assertIn("conditional_chain_summary", d)

    def test_markdown_has_im09_section(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_ok(),
        )
        md = build_final_audit_report_markdown(result)
        self.assertIn("IM-09", md)

    def test_markdown_has_cadenas_condicionales(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
        )
        md = build_final_audit_report_markdown(result)
        self.assertIn("condicionales", md.lower())

    def test_notes_include_im09_state(self) -> None:
        result = build_final_audit_result(
            "EIA-TEST",
            _art45_data_ok(), _prudence_data_ok(), _traceability_data_ok(),
            conditional_chain_data=_conditional_chain_data_ok(),
        )
        notes_text = " ".join(result.notes)
        self.assertIn("IM-09", notes_text)


# ---------------------------------------------------------------------------
# 22. TestBuildFinalAuditFromFilesWithIM09
# ---------------------------------------------------------------------------

class TestBuildFinalAuditFromFilesWithIM09(unittest.TestCase):

    def test_with_im09_file_loads_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "conditional_chain_result.json").write_text(
                json.dumps(_conditional_chain_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")
            self.assertTrue(result.conditional_chain_summary.get("available"))

    def test_with_im09_errors_no_conforme_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            (aud / "conditional_chain_result.json").write_text(
                json.dumps(_conditional_chain_data_errors()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_without_im09_stays_conforme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aud = Path(tmp) / "auditoria"
            aud.mkdir()
            (aud / "art45_checklist_result.json").write_text(
                json.dumps(_art45_data_ok()), encoding="utf-8"
            )
            (aud / "prudence_validation_result.json").write_text(
                json.dumps(_prudence_data_ok()), encoding="utf-8"
            )
            (aud / "traceability_validation_result.json").write_text(
                json.dumps(_traceability_data_ok()), encoding="utf-8"
            )
            result = build_final_audit_from_files(tmp)
            self.assertEqual(result.status, "CONFORME")
            self.assertFalse(result.conditional_chain_summary.get("available"))


if __name__ == "__main__":
    unittest.main()
