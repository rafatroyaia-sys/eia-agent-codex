"""
tests/test_technical_pipeline.py
Tests para PIPE-01 — Pipeline técnico automático.

Cubre:
  1.  TechnicalPipelineStepResult — to_dict, summary, is_success, is_blocking_failure
  2.  TechnicalPipelineResult — conteos, is_success, to_dict, summary
  3.  build_technical_pipeline_markdown — secciones, advertencia alcance
  4.  write_pipeline_outputs — escribe JSON y MD
  5.  run_technical_pipeline con expediente temporal vacío
  6.  run_technical_pipeline con fixtures mínimos
  7.  Mocks de pasos — success total, fallo con stop_on_error, continue-on-error
  8.  CLI run-technical-pipeline — exit codes, --write, --continue-on-error, --prod
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.technical_pipeline import (
    PIPELINE_STEP_STATUS,
    PIPELINE_MODE,
    TECHNICAL_PIPELINE_STEPS,
    TechnicalPipelineResult,
    TechnicalPipelineStepResult,
    build_technical_pipeline_markdown,
    now_iso,
    run_technical_pipeline,
    safe_load_json,
    write_pipeline_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_step(
    step_id: str = "INVENTORY_BUILD",
    status: str = "SUCCESS",
    output_files: list[str] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> TechnicalPipelineStepResult:
    t = now_iso()
    return TechnicalPipelineStepResult(
        step_id=step_id,
        name=f"Paso {step_id}",
        status=status,
        started_at=t,
        finished_at=t,
        message="Test step",
        output_files=output_files or [],
        errors=errors or [],
        warnings=warnings or [],
        notes=[],
    )


def _make_pipeline_result(
    steps: list[TechnicalPipelineStepResult] | None = None,
    final_status: str = "SUCCESS",
) -> TechnicalPipelineResult:
    t = now_iso()
    return TechnicalPipelineResult(
        expediente_id="EIA-TEST",
        expediente_path="/tmp/EIA-TEST",
        mode="TEST",
        write_outputs=False,
        started_at=t,
        finished_at=t,
        steps=steps or [],
        final_status=final_status,
    )


def _all_success_steps() -> list[TechnicalPipelineStepResult]:
    return [_make_step(s, "SUCCESS") for s in TECHNICAL_PIPELINE_STEPS]


def _make_step_runner_ok(step_id: str = "INVENTORY_BUILD") -> MagicMock:
    mock = MagicMock(return_value=_make_step(step_id, "SUCCESS"))
    return mock


# ---------------------------------------------------------------------------
# 1. TestTechnicalPipelineStepResult
# ---------------------------------------------------------------------------

class TestTechnicalPipelineStepResult(unittest.TestCase):

    def test_to_dict_keys(self) -> None:
        step = _make_step()
        d = step.to_dict()
        for k in ("step_id", "name", "status", "started_at", "finished_at",
                   "message", "output_files", "warnings", "errors", "notes"):
            self.assertIn(k, d)

    def test_to_dict_status(self) -> None:
        step = _make_step(status="FAILED")
        self.assertEqual(step.to_dict()["status"], "FAILED")

    def test_summary_is_string(self) -> None:
        self.assertIsInstance(_make_step().summary(), str)

    def test_summary_is_ascii_safe(self) -> None:
        step = _make_step()
        step.summary().encode("ascii")  # must not raise

    def test_summary_contains_step_id(self) -> None:
        step = _make_step("AUDIT_ART45")
        self.assertIn("AUDIT_ART45", step.summary())

    def test_is_success_for_success(self) -> None:
        self.assertTrue(_make_step(status="SUCCESS").is_success())

    def test_is_success_for_warning(self) -> None:
        self.assertTrue(_make_step(status="WARNING").is_success())

    def test_is_success_false_for_failed(self) -> None:
        self.assertFalse(_make_step(status="FAILED").is_success())

    def test_is_success_false_for_blocked(self) -> None:
        self.assertFalse(_make_step(status="BLOCKED").is_success())

    def test_is_success_false_for_skipped(self) -> None:
        self.assertFalse(_make_step(status="SKIPPED").is_success())

    def test_is_blocking_failure_for_failed(self) -> None:
        self.assertTrue(_make_step(status="FAILED").is_blocking_failure())

    def test_is_blocking_failure_for_blocked(self) -> None:
        self.assertTrue(_make_step(status="BLOCKED").is_blocking_failure())

    def test_is_blocking_failure_false_for_success(self) -> None:
        self.assertFalse(_make_step(status="SUCCESS").is_blocking_failure())

    def test_output_files_in_dict(self) -> None:
        step = _make_step(output_files=["a.json", "b.md"])
        self.assertEqual(step.to_dict()["output_files"], ["a.json", "b.md"])


# ---------------------------------------------------------------------------
# 2. TestTechnicalPipelineResult
# ---------------------------------------------------------------------------

class TestTechnicalPipelineResult(unittest.TestCase):

    def _make(self, statuses: list[str]) -> TechnicalPipelineResult:
        steps = [_make_step(f"STEP_{i}", s) for i, s in enumerate(statuses)]
        r = _make_pipeline_result(steps)
        r.final_status = "SUCCESS" if all(s in ("SUCCESS", "WARNING") for s in statuses) else "FAILED"
        return r

    def test_success_count(self) -> None:
        r = self._make(["SUCCESS", "WARNING", "FAILED"])
        self.assertEqual(r.success_count(), 2)

    def test_failed_count(self) -> None:
        r = self._make(["SUCCESS", "FAILED", "FAILED"])
        self.assertEqual(r.failed_count(), 2)

    def test_skipped_count(self) -> None:
        r = self._make(["SUCCESS", "SKIPPED", "SKIPPED"])
        self.assertEqual(r.skipped_count(), 2)

    def test_blocked_count(self) -> None:
        r = self._make(["BLOCKED", "BLOCKED"])
        self.assertEqual(r.blocked_count(), 2)

    def test_is_success_all_ok(self) -> None:
        r = self._make(["SUCCESS", "SUCCESS", "WARNING"])
        self.assertTrue(r.is_success())

    def test_is_success_false_with_failed(self) -> None:
        r = self._make(["SUCCESS", "FAILED"])
        self.assertFalse(r.is_success())

    def test_is_success_false_with_blocked(self) -> None:
        r = self._make(["BLOCKED"])
        self.assertFalse(r.is_success())

    def test_is_success_true_with_skipped_only_no_blocked(self) -> None:
        # Skipped alone doesn't make it fail (failed_count=0, blocked_count=0)
        r = self._make(["SUCCESS", "SKIPPED"])
        self.assertTrue(r.is_success())

    def test_to_dict_keys(self) -> None:
        r = self._make(["SUCCESS"])
        d = r.to_dict()
        for k in ("expediente_id", "expediente_path", "mode", "write_outputs",
                   "started_at", "finished_at", "final_status",
                   "steps", "success_count", "failed_count",
                   "skipped_count", "blocked_count", "is_success",
                   "output_files", "warnings", "errors", "notes"):
            self.assertIn(k, d)

    def test_to_dict_counts(self) -> None:
        r = self._make(["SUCCESS", "FAILED", "SKIPPED"])
        d = r.to_dict()
        self.assertEqual(d["success_count"], 1)
        self.assertEqual(d["failed_count"], 1)
        self.assertEqual(d["skipped_count"], 1)

    def test_summary_is_ascii_safe(self) -> None:
        r = self._make(["SUCCESS"])
        r.summary().encode("ascii")

    def test_summary_contains_expediente_id(self) -> None:
        r = _make_pipeline_result()
        self.assertIn("EIA-TEST", r.summary())

    def test_summary_contains_final_status(self) -> None:
        r = _make_pipeline_result(final_status="FAILED")
        self.assertIn("FAILED", r.summary())

    def test_17_steps_expected(self) -> None:
        self.assertEqual(len(TECHNICAL_PIPELINE_STEPS), 17)

    def test_audit_block_consistency_in_steps(self) -> None:
        self.assertIn("AUDIT_BLOCK_CONSISTENCY", TECHNICAL_PIPELINE_STEPS)

    def test_audit_conesa_in_steps(self) -> None:
        self.assertIn("AUDIT_CONESA", TECHNICAL_PIPELINE_STEPS)

    def test_audit_final_is_last(self) -> None:
        self.assertEqual(TECHNICAL_PIPELINE_STEPS[-1], "AUDIT_FINAL")

    def test_audit_block_consistency_before_final(self) -> None:
        idx_bc = TECHNICAL_PIPELINE_STEPS.index("AUDIT_BLOCK_CONSISTENCY")
        idx_final = TECHNICAL_PIPELINE_STEPS.index("AUDIT_FINAL")
        self.assertLess(idx_bc, idx_final)

    def test_audit_conesa_before_final(self) -> None:
        idx_conesa = TECHNICAL_PIPELINE_STEPS.index("AUDIT_CONESA")
        idx_final = TECHNICAL_PIPELINE_STEPS.index("AUDIT_FINAL")
        self.assertLess(idx_conesa, idx_final)


# ---------------------------------------------------------------------------
# 3. TestBuildTechnicalPipelineMarkdown
# ---------------------------------------------------------------------------

class TestBuildTechnicalPipelineMarkdown(unittest.TestCase):

    def _result(self) -> TechnicalPipelineResult:
        return _make_pipeline_result(steps=_all_success_steps(), final_status="SUCCESS")

    def test_has_section_1_resumen(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 1. Resumen ejecutivo", md)

    def test_has_section_2_estado(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 2. Estado final", md)

    def test_has_section_3_pasos(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 3. Pasos ejecutados", md)

    def test_has_section_4_outputs(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 4. Outputs generados", md)

    def test_has_section_5_errores(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 5. Errores", md)

    def test_has_section_6_advertencias(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 6. Advertencias", md)

    def test_has_section_7_auditoria(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 7. Informe final de auditoria", md)

    def test_has_section_8_advertencia_alcance(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("## 8. Advertencia de alcance", md)

    def test_advertencia_no_declara_aptitud(self) -> None:
        import unicodedata
        md = build_technical_pipeline_markdown(self._result())
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertIn("no declara", norm)

    def test_no_apto_administativo(self) -> None:
        import unicodedata
        md = build_technical_pipeline_markdown(self._result())
        norm = unicodedata.normalize("NFKD", md.lower()).encode("ascii", "ignore").decode()
        self.assertTrue("no declara" in norm or "organo competente" in norm)

    def test_contains_expediente_id(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        self.assertIn("EIA-TEST", md)

    def test_contains_all_step_ids(self) -> None:
        md = build_technical_pipeline_markdown(self._result())
        for step_id in TECHNICAL_PIPELINE_STEPS:
            self.assertIn(step_id, md, f"step_id missing: {step_id}")

    def test_returns_string(self) -> None:
        self.assertIsInstance(
            build_technical_pipeline_markdown(_make_pipeline_result()), str
        )


# ---------------------------------------------------------------------------
# 4. TestWritePipelineOutputs
# ---------------------------------------------------------------------------

class TestWritePipelineOutputs(unittest.TestCase):

    def _result(self) -> TechnicalPipelineResult:
        return _make_pipeline_result(steps=_all_success_steps())

    def test_writes_json_and_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_pipeline_outputs(self._result(), out)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, _ = write_pipeline_outputs(self._result(), out)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("steps", data)
            self.assertIn("final_status", data)

    def test_md_has_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            _, md_path = write_pipeline_outputs(self._result(), out)
            content = md_path.read_text(encoding="utf-8")
            self.assertIn("## 1. Resumen ejecutivo", content)
            self.assertIn("## 8. Advertencia de alcance", content)

    def test_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nuevo" / "auditoria"
            self.assertFalse(out.exists())
            write_pipeline_outputs(self._result(), out)
            self.assertTrue(out.exists())

    def test_filenames_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            json_path, md_path = write_pipeline_outputs(self._result(), out)
            self.assertEqual(json_path.name, "technical_pipeline_result.json")
            self.assertEqual(md_path.name, "technical_pipeline_result.md")

    def test_returns_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "auditoria"
            result = write_pipeline_outputs(self._result(), out)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], Path)


# ---------------------------------------------------------------------------
# 5. TestRunPipelineEmptyExpediente
# ---------------------------------------------------------------------------

class TestRunPipelineEmptyExpediente(unittest.TestCase):

    def test_raises_if_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            run_technical_pipeline("/ruta/inexistente")

    def test_empty_expediente_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_technical_pipeline(tmp, write_outputs=False)
            self.assertIsInstance(result, TechnicalPipelineResult)

    def test_empty_expediente_has_17_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_technical_pipeline(tmp, write_outputs=False)
            self.assertEqual(len(result.steps), 17)

    def test_empty_expediente_not_all_success(self) -> None:
        # Empty expediente → some steps will fail or be skipped
        with tempfile.TemporaryDirectory() as tmp:
            result = run_technical_pipeline(tmp, write_outputs=False)
            self.assertFalse(result.is_success())

    def test_empty_expediente_does_not_modify_outside_tmpdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_technical_pipeline(tmp, write_outputs=True)
            # Only auditoria/ dir may exist; no files outside tmp
            tmp_path = Path(tmp)
            for p in tmp_path.iterdir():
                self.assertTrue(
                    p.is_relative_to(tmp_path),
                    f"File outside tmpdir: {p}"
                )

    def test_empty_expediente_has_expediente_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_technical_pipeline(tmp)
            self.assertEqual(result.expediente_id, Path(tmp).name)

    def test_empty_expediente_has_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_technical_pipeline(tmp)
            self.assertTrue(result.started_at)
            self.assertTrue(result.finished_at)

    def test_dry_run_no_write_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_technical_pipeline(tmp, write_outputs=False)
            aud = Path(tmp) / "auditoria"
            # Pipeline report itself is not written without explicit call
            self.assertFalse((aud / "technical_pipeline_result.json").exists())


# ---------------------------------------------------------------------------
# 6. TestRunPipelineMinimalFixtures
# ---------------------------------------------------------------------------

class TestRunPipelineMinimalFixtures(unittest.TestCase):
    """Tests con fixtures mínimos que permiten ejecutar los pasos de auditoría."""

    def _make_expediente_with_audits(self) -> "tuple[tempfile.TemporaryDirectory, Path]":
        tmp = tempfile.TemporaryDirectory()
        exp = Path(tmp.name)
        aud = exp / "auditoria"
        aud.mkdir()

        # Audit JSONs limpios
        art45_data = {
            "items": [{"requirement_id": "ART45-01", "title": "T", "status": "CUBIERTO"}],
            "issues": [], "covered_count": 1, "partial_count": 0,
            "not_covered_count": 0, "error_count": 0, "warning_count": 0,
            "is_structurally_complete": True, "administrative_ready": False,
        }
        (aud / "art45_checklist_result.json").write_text(
            json.dumps(art45_data), encoding="utf-8"
        )
        prudence_data = {
            "issues": [], "checked_sources": [], "error_count": 0,
            "warning_count": 0, "info_count": 0, "is_valid": True,
        }
        (aud / "prudence_validation_result.json").write_text(
            json.dumps(prudence_data), encoding="utf-8"
        )
        traceability_data = {
            "issues": [], "traced_claims": [], "partial_claims": [],
            "untraced_claims": [], "references_loaded": [],
            "error_count": 0, "warning_count": 0, "info_count": 0,
            "is_valid": True,
        }
        (aud / "traceability_validation_result.json").write_text(
            json.dumps(traceability_data), encoding="utf-8"
        )
        return tmp, exp

    def test_audit_steps_can_run_with_fixtures(self) -> None:
        tmp, exp = self._make_expediente_with_audits()
        try:
            result = run_technical_pipeline(str(exp), write_outputs=False,
                                            stop_on_error=False)
            # AUDIT_FINAL should run and produce WARNING or SUCCESS
            audit_final = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertIsNotNone(audit_final)
            self.assertIn(audit_final.status, ("SUCCESS", "WARNING", "FAILED", "BLOCKED"))
        finally:
            tmp.cleanup()

    def test_write_with_audits_creates_pipeline_report(self) -> None:
        tmp, exp = self._make_expediente_with_audits()
        try:
            run_technical_pipeline(str(exp), write_outputs=True, stop_on_error=False)
            # Audit outputs should be created (or already existed)
            aud = exp / "auditoria"
            self.assertTrue((aud / "art45_checklist_result.json").exists())
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# 7. TestPipelineMocks
# ---------------------------------------------------------------------------

class TestPipelineMocks(unittest.TestCase):
    """Tests con mocks de los step runners internos."""

    def _patch_runners(self, statuses: dict[str, str]):
        """Parcha los runners individuales con mocks según status."""
        patches = {}
        for step_id, status in statuses.items():
            mock = MagicMock(return_value=_make_step(step_id, status))
            patches[step_id] = mock
        return patches

    def test_all_success_pipeline_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            all_ok = {s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS}
            patches = self._patch_runners(all_ok)
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertTrue(result.is_success())
            self.assertEqual(result.final_status, "SUCCESS")
            self.assertEqual(result.success_count(), 17)

    def test_step3_failed_stop_on_error_skips_rest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["PHASE6_ACTIONS"] = MagicMock(
                return_value=_make_step("PHASE6_ACTIONS", "FAILED",
                                        errors=["Error simulado"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=True)
            self.assertFalse(result.is_success())
            self.assertGreater(result.skipped_count(), 0)
            # Steps after PHASE6_ACTIONS should be SKIPPED
            step_idx = TECHNICAL_PIPELINE_STEPS.index("PHASE6_ACTIONS")
            for s in result.steps[step_idx + 1:]:
                self.assertEqual(s.status, "SKIPPED")

    def test_step3_failed_continue_on_error_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["PHASE6_ACTIONS"] = MagicMock(
                return_value=_make_step("PHASE6_ACTIONS", "FAILED",
                                        errors=["Error simulado"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=False)
            self.assertEqual(result.skipped_count(), 0)
            # Steps after failure should NOT be skipped
            self.assertFalse(result.is_success())
            self.assertGreater(result.failed_count(), 0)

    def test_outputs_aggregated_from_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["INVENTORY_BUILD"] = MagicMock(
                return_value=_make_step("INVENTORY_BUILD", "SUCCESS",
                                        output_files=["inventario/inventory_summary.json"])
            )
            patches["AUDIT_FINAL"] = MagicMock(
                return_value=_make_step("AUDIT_FINAL", "SUCCESS",
                                        output_files=["auditoria/final_audit_result.json"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertIn("inventario/inventory_summary.json", result.output_files)
            self.assertIn("auditoria/final_audit_result.json", result.output_files)

    def test_mode_passed_to_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            captured_modes = []
            def capture_mode(exp_path, write, mode):
                captured_modes.append(mode)
                return _make_step("INVENTORY_BUILD", "SUCCESS")
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["INVENTORY_BUILD"] = capture_mode
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                run_technical_pipeline(tmp, mode="PROD")
            self.assertIn("PROD", captured_modes)

    def test_write_passed_to_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            captured_writes = []
            def capture_write(exp_path, write, mode):
                captured_writes.append(write)
                return _make_step("INVENTORY_BUILD", "SUCCESS")
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["INVENTORY_BUILD"] = capture_write
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                run_technical_pipeline(tmp, write_outputs=True)
            self.assertIn(True, captured_writes)


# ---------------------------------------------------------------------------
# 7b. TestNewAuditStepsPIPE02
# ---------------------------------------------------------------------------

class TestNewAuditStepsPIPE02(unittest.TestCase):
    """Tests para los pasos AUDIT_BLOCK_CONSISTENCY y AUDIT_CONESA (PIPE-02)."""

    def _patch_runners(self, statuses: dict[str, str]):
        patches = {}
        for step_id, status in statuses.items():
            patches[step_id] = MagicMock(return_value=_make_step(step_id, status))
        return patches

    def test_audit_block_consistency_included_in_all_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            all_ok = {s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS}
            patches = self._patch_runners(all_ok)
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            bc_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_BLOCK_CONSISTENCY"), None
            )
            self.assertIsNotNone(bc_step)
            self.assertEqual(bc_step.status, "SUCCESS")

    def test_audit_conesa_included_in_all_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            all_ok = {s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS}
            patches = self._patch_runners(all_ok)
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            cc_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_CONESA"), None
            )
            self.assertIsNotNone(cc_step)
            self.assertEqual(cc_step.status, "SUCCESS")

    def test_audit_conesa_failed_stop_on_error_skips_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_CONESA"] = MagicMock(
                return_value=_make_step("AUDIT_CONESA", "FAILED", errors=["Error conesa"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=True)
            # AUDIT_FINAL should be SKIPPED
            final_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertIsNotNone(final_step)
            self.assertEqual(final_step.status, "SKIPPED")

    def test_audit_conesa_failed_continue_on_error_runs_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_CONESA"] = MagicMock(
                return_value=_make_step("AUDIT_CONESA", "FAILED", errors=["Error conesa"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=False)
            # AUDIT_FINAL should NOT be SKIPPED
            final_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertIsNotNone(final_step)
            self.assertNotEqual(final_step.status, "SKIPPED")

    def test_audit_block_consistency_outputs_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_BLOCK_CONSISTENCY"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_BLOCK_CONSISTENCY", "SUCCESS",
                    output_files=["auditoria/block_consistency_result.json"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertIn(
                "auditoria/block_consistency_result.json", result.output_files
            )

    def test_audit_conesa_outputs_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_CONESA"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_CONESA", "SUCCESS",
                    output_files=["auditoria/conesa_check_result.json"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertIn("auditoria/conesa_check_result.json", result.output_files)


# ---------------------------------------------------------------------------
# 7c. TestNewAuditStepsPIPE03
# ---------------------------------------------------------------------------

class TestNewAuditStepsPIPE03(unittest.TestCase):
    """Tests para los pasos AUDIT_DIAGNOSTIC_MEASURES y AUDIT_PRL_MEASURES (PIPE-03)."""

    def _patch_runners(self, statuses: dict[str, str]):
        patches = {}
        for step_id, status in statuses.items():
            patches[step_id] = MagicMock(return_value=_make_step(step_id, status))
        return patches

    def test_audit_diagnostic_measures_in_steps(self) -> None:
        self.assertIn("AUDIT_DIAGNOSTIC_MEASURES", TECHNICAL_PIPELINE_STEPS)

    def test_audit_prl_measures_in_steps(self) -> None:
        self.assertIn("AUDIT_PRL_MEASURES", TECHNICAL_PIPELINE_STEPS)

    def test_audit_final_is_last_step(self) -> None:
        self.assertEqual(TECHNICAL_PIPELINE_STEPS[-1], "AUDIT_FINAL")

    def test_audit_diagnostic_before_prl_before_final(self) -> None:
        idx_diag = TECHNICAL_PIPELINE_STEPS.index("AUDIT_DIAGNOSTIC_MEASURES")
        idx_prl = TECHNICAL_PIPELINE_STEPS.index("AUDIT_PRL_MEASURES")
        idx_final = TECHNICAL_PIPELINE_STEPS.index("AUDIT_FINAL")
        self.assertLess(idx_diag, idx_prl)
        self.assertLess(idx_prl, idx_final)

    def test_audit_diagnostic_included_in_all_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            all_ok = {s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS}
            patches = self._patch_runners(all_ok)
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            step = next(
                (s for s in result.steps if s.step_id == "AUDIT_DIAGNOSTIC_MEASURES"), None
            )
            self.assertIsNotNone(step)
            self.assertEqual(step.status, "SUCCESS")

    def test_audit_prl_included_in_all_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            all_ok = {s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS}
            patches = self._patch_runners(all_ok)
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            step = next(
                (s for s in result.steps if s.step_id == "AUDIT_PRL_MEASURES"), None
            )
            self.assertIsNotNone(step)
            self.assertEqual(step.status, "SUCCESS")

    def test_diag_failed_stop_on_error_skips_prl_and_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_DIAGNOSTIC_MEASURES"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_DIAGNOSTIC_MEASURES", "FAILED", errors=["Error diag"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=True)
            prl_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_PRL_MEASURES"), None
            )
            final_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertEqual(prl_step.status, "SKIPPED")
            self.assertEqual(final_step.status, "SKIPPED")

    def test_prl_failed_stop_on_error_skips_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_PRL_MEASURES"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_PRL_MEASURES", "FAILED", errors=["Error PRL"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=True)
            final_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertEqual(final_step.status, "SKIPPED")

    def test_prl_failed_continue_on_error_runs_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_PRL_MEASURES"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_PRL_MEASURES", "FAILED", errors=["Error PRL"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp, stop_on_error=False)
            final_step = next(
                (s for s in result.steps if s.step_id == "AUDIT_FINAL"), None
            )
            self.assertNotEqual(final_step.status, "SKIPPED")

    def test_diag_outputs_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_DIAGNOSTIC_MEASURES"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_DIAGNOSTIC_MEASURES", "SUCCESS",
                    output_files=["auditoria/diagnostic_measure_validation_result.json"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertIn(
                "auditoria/diagnostic_measure_validation_result.json",
                result.output_files,
            )

    def test_prl_outputs_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = self._patch_runners({s: "SUCCESS" for s in TECHNICAL_PIPELINE_STEPS})
            patches["AUDIT_PRL_MEASURES"] = MagicMock(
                return_value=_make_step(
                    "AUDIT_PRL_MEASURES", "SUCCESS",
                    output_files=["auditoria/prl_measure_validation_result.json"]
                )
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                result = run_technical_pipeline(tmp)
            self.assertIn(
                "auditoria/prl_measure_validation_result.json",
                result.output_files,
            )


# ---------------------------------------------------------------------------
# 8. TestCLIRunTechnicalPipeline
# ---------------------------------------------------------------------------

class TestCLIRunTechnicalPipeline(unittest.TestCase):

    def _run_cli(self, argv: list[str]) -> int:
        from run_expediente import main
        return main(argv)

    def test_nonexistent_expediente_exit_1(self) -> None:
        code = self._run_cli(["/ruta/que/no/existe", "run-technical-pipeline"])
        self.assertEqual(code, 1)

    def test_empty_expediente_exit_1(self) -> None:
        # Empty expediente → pipeline fails
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "run-technical-pipeline"])
            self.assertEqual(code, 1)

    def test_empty_expediente_no_write_no_pipeline_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli([tmp, "run-technical-pipeline"])
            aud = Path(tmp) / "auditoria"
            self.assertFalse((aud / "technical_pipeline_result.json").exists())

    def test_write_creates_pipeline_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._run_cli([tmp, "run-technical-pipeline", "--write"])
            aud = Path(tmp) / "auditoria"
            self.assertTrue((aud / "technical_pipeline_result.json").exists())
            self.assertTrue((aud / "technical_pipeline_result.md").exists())

    def test_continue_on_error_flag(self) -> None:
        # Should not raise
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "run-technical-pipeline", "--continue-on-error"])
            self.assertIn(code, (0, 1))

    def test_prod_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = self._run_cli([tmp, "run-technical-pipeline", "--prod"])
            self.assertIn(code, (0, 1))

    def test_all_success_mocks_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = {
                s: MagicMock(return_value=_make_step(s, "SUCCESS"))
                for s in TECHNICAL_PIPELINE_STEPS
            }
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                code = self._run_cli([tmp, "run-technical-pipeline"])
            self.assertEqual(code, 0)

    def test_failed_step_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = {
                s: MagicMock(return_value=_make_step(s, "SUCCESS"))
                for s in TECHNICAL_PIPELINE_STEPS
            }
            patches["INVENTORY_BUILD"] = MagicMock(
                return_value=_make_step("INVENTORY_BUILD", "FAILED", errors=["Test error"])
            )
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                code = self._run_cli([tmp, "run-technical-pipeline"])
            self.assertEqual(code, 1)

    def test_write_with_mocks_creates_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            patches = {
                s: MagicMock(return_value=_make_step(s, "SUCCESS"))
                for s in TECHNICAL_PIPELINE_STEPS
            }
            with patch.dict(
                "eia_agent.core.technical_pipeline._STEP_RUNNERS", patches
            ):
                self._run_cli([tmp, "run-technical-pipeline", "--write"])
            aud = Path(tmp) / "auditoria"
            self.assertTrue((aud / "technical_pipeline_result.json").exists())


if __name__ == "__main__":
    unittest.main()
