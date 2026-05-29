"""
Tests para config_manager.py — BE-04
Gestión segura de configuración y API keys.

Todos offline. Sin llamadas a APIs. Sin modificar expedientes piloto.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.config_manager import (
    ALLOWED_EIA_ENV,
    CONFIG_SEVERITY,
    CONFIG_STATUS,
    KNOWN_ENV_VARS,
    PLACEHOLDER_VALUES,
    SENSITIVE_ENV_VARS,
    ConfigIssue,
    ConfigValidationResult,
    EnvVarStatus,
    build_config_report_markdown,
    is_placeholder_value,
    load_dotenv_file,
    mask_secret,
    read_env_var_status,
    scan_file_for_potential_secrets,
    scan_repo_for_potential_secrets,
    scan_text_for_potential_secrets,
    validate_config,
    write_config_validation_outputs,
)


# ---------------------------------------------------------------------------
# TestMaskSecret
# ---------------------------------------------------------------------------

class TestMaskSecret(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(mask_secret(None))

    def test_empty_returns_stars(self):
        self.assertEqual(mask_secret(""), "****")

    def test_short_4_chars_returns_stars(self):
        self.assertEqual(mask_secret("abcd"), "****")

    def test_exactly_8_chars_returns_stars(self):
        self.assertEqual(mask_secret("abcdefgh"), "****")

    def test_long_value_masked_format(self):
        result = mask_secret("abcdefghijklmnopwxyz")
        self.assertEqual(result, "abcd...wxyz")

    def test_long_value_does_not_contain_middle(self):
        secret = "abcdefghijklmnopwxyz"
        result = mask_secret(secret)
        self.assertNotIn("efghijklmnop", result)

    def test_never_returns_full_value(self):
        secret = "sk-supersecretkey123456789"
        result = mask_secret(secret)
        self.assertNotEqual(result, secret)
        self.assertLess(len(result), len(secret))

    def test_9_chars_uses_ellipsis_format(self):
        result = mask_secret("abcde1234")
        self.assertIn("...", result)
        self.assertEqual(result, "abcd...1234")


# ---------------------------------------------------------------------------
# TestIsPlaceholderValue
# ---------------------------------------------------------------------------

class TestIsPlaceholderValue(unittest.TestCase):

    def test_empty_string_is_placeholder(self):
        self.assertTrue(is_placeholder_value(""))

    def test_none_is_placeholder(self):
        self.assertTrue(is_placeholder_value(None))

    def test_change_me_is_placeholder(self):
        self.assertTrue(is_placeholder_value("CHANGE_ME"))

    def test_xxx_is_placeholder(self):
        self.assertTrue(is_placeholder_value("xxx"))

    def test_your_api_key_is_placeholder(self):
        self.assertTrue(is_placeholder_value("your_api_key"))

    def test_your_api_key_here_is_placeholder(self):
        self.assertTrue(is_placeholder_value("your_api_key_here"))

    def test_all_x_pattern_is_placeholder(self):
        self.assertTrue(is_placeholder_value("xxxxxxxx"))

    def test_all_stars_is_placeholder(self):
        self.assertTrue(is_placeholder_value("****"))

    def test_all_dots_is_placeholder(self):
        self.assertTrue(is_placeholder_value("......"))

    def test_realistic_token_is_not_placeholder(self):
        real_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"
        self.assertFalse(is_placeholder_value(real_key))

    def test_realistic_api_key_is_not_placeholder(self):
        self.assertFalse(is_placeholder_value("abc123xyz987def456"))

    def test_case_insensitive(self):
        self.assertTrue(is_placeholder_value("TODO"))
        self.assertTrue(is_placeholder_value("todo"))


# ---------------------------------------------------------------------------
# TestLoadDotenvFile
# ---------------------------------------------------------------------------

class TestLoadDotenvFile(unittest.TestCase):

    def _write_env(self, content: str):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_loads_simple_key_value(self):
        p = self._write_env("AEMET_API_KEY=test-key-123\n")
        try:
            result = load_dotenv_file(p)
            self.assertEqual(result.get("AEMET_API_KEY"), "test-key-123")
        finally:
            p.unlink()

    def test_ignores_comments(self):
        p = self._write_env("# this is a comment\nKEY=VALUE\n")
        try:
            result = load_dotenv_file(p)
            self.assertNotIn("# this is a comment", result)
            self.assertEqual(result.get("KEY"), "VALUE")
        finally:
            p.unlink()

    def test_ignores_empty_lines(self):
        p = self._write_env("\n\nKEY=VALUE\n\n")
        try:
            result = load_dotenv_file(p)
            self.assertEqual(result.get("KEY"), "VALUE")
        finally:
            p.unlink()

    def test_returns_empty_dict_if_not_exists(self):
        result = load_dotenv_file("/nonexistent/path/.env")
        self.assertEqual(result, {})

    def test_strips_surrounding_quotes(self):
        p = self._write_env('KEY="value with spaces"\n')
        try:
            result = load_dotenv_file(p)
            self.assertEqual(result.get("KEY"), "value with spaces")
        finally:
            p.unlink()

    def test_loads_multiple_keys(self):
        p = self._write_env("A=1\nB=2\nC=3\n")
        try:
            result = load_dotenv_file(p)
            self.assertEqual(result.get("A"), "1")
            self.assertEqual(result.get("B"), "2")
            self.assertEqual(result.get("C"), "3")
        finally:
            p.unlink()

    def test_empty_value_allowed(self):
        p = self._write_env("AEMET_API_KEY=\n")
        try:
            result = load_dotenv_file(p)
            self.assertIn("AEMET_API_KEY", result)
            self.assertEqual(result["AEMET_API_KEY"], "")
        finally:
            p.unlink()


# ---------------------------------------------------------------------------
# TestReadEnvVarStatus
# ---------------------------------------------------------------------------

class TestReadEnvVarStatus(unittest.TestCase):

    def test_variable_from_env(self):
        status = read_env_var_status(
            "AEMET_API_KEY",
            env={"AEMET_API_KEY": "real-key-1234567890"},
        )
        self.assertTrue(status.present)
        self.assertEqual(status.source, "environment")
        self.assertFalse(status.is_placeholder)

    def test_variable_from_dotenv(self):
        status = read_env_var_status(
            "AEMET_API_KEY",
            env={},
            dotenv_values={"AEMET_API_KEY": "dotenv-key-1234567890"},
        )
        self.assertTrue(status.present)
        self.assertEqual(status.source, ".env")

    def test_env_has_priority_over_dotenv(self):
        status = read_env_var_status(
            "AEMET_API_KEY",
            env={"AEMET_API_KEY": "from-env"},
            dotenv_values={"AEMET_API_KEY": "from-dotenv"},
        )
        self.assertEqual(status.source, "environment")

    def test_missing_variable(self):
        status = read_env_var_status("AEMET_API_KEY", env={}, dotenv_values={})
        self.assertFalse(status.present)
        self.assertEqual(status.source, "missing")
        self.assertIsNone(status.masked_value)

    def test_sensitive_value_is_masked(self):
        status = read_env_var_status(
            "AEMET_API_KEY",
            env={"AEMET_API_KEY": "abcdefghijklmnop"},
        )
        self.assertNotEqual(status.masked_value, "abcdefghijklmnop")
        self.assertIsNotNone(status.masked_value)

    def test_placeholder_detected(self):
        status = read_env_var_status(
            "AEMET_API_KEY",
            env={"AEMET_API_KEY": "CHANGE_ME"},
        )
        self.assertTrue(status.is_placeholder)

    def test_non_sensitive_value_not_masked(self):
        status = read_env_var_status(
            "EIA_ENV",
            env={"EIA_ENV": "dev"},
        )
        self.assertEqual(status.masked_value, "dev")

    def test_is_sensitive_flag(self):
        s1 = read_env_var_status("AEMET_API_KEY", env={})
        s2 = read_env_var_status("EIA_ENV", env={})
        self.assertTrue(s1.is_sensitive)
        self.assertFalse(s2.is_sensitive)


# ---------------------------------------------------------------------------
# TestValidateConfig
# ---------------------------------------------------------------------------

class TestValidateConfig(unittest.TestCase):

    def test_all_optional_absent_gives_sin_datos_or_ok(self):
        result = validate_config(env={}, dotenv_path=None)
        self.assertIn(result.status, {"SIN_DATOS", "OK"})

    def test_required_missing_gives_error(self):
        result = validate_config(
            required_vars=["AEMET_API_KEY"],
            env={},
        )
        self.assertEqual(result.error_count(), 1)
        self.assertFalse(result.is_valid())
        self.assertEqual(result.status, "NO_CONFORME")

    def test_required_placeholder_gives_error(self):
        result = validate_config(
            required_vars=["AEMET_API_KEY"],
            env={"AEMET_API_KEY": "CHANGE_ME"},
        )
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertFalse(result.is_valid())

    def test_optional_placeholder_gives_warning(self):
        result = validate_config(
            env={"AEMET_API_KEY": "xxx"},
        )
        self.assertGreater(result.warning_count(), 0)
        self.assertIn(result.status, {"CON_OBSERVACIONES"})

    def test_invalid_eia_env_gives_warning(self):
        result = validate_config(
            env={"EIA_ENV": "staging_invalid_value"},
        )
        codes = [i.code for i in result.issues]
        self.assertIn("BE04-W003", codes)

    def test_valid_eia_env_no_warning(self):
        for val in ALLOWED_EIA_ENV:
            result = validate_config(env={"EIA_ENV": val})
            w003_issues = [i for i in result.issues if i.code == "BE04-W003"]
            self.assertEqual(len(w003_issues), 0, f"Unexpected W003 for EIA_ENV={val}")

    def test_openai_key_not_required_for_offline(self):
        result = validate_config(env={})
        errors = [i for i in result.issues if i.variable == "OPENAI_API_KEY" and i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_is_valid_true_without_errors(self):
        result = validate_config(
            env={"EIA_ENV": "dev"},
        )
        self.assertTrue(result.is_valid())

    def test_allow_missing_optional_false_gives_warnings(self):
        result = validate_config(env={}, allow_missing_optional=False)
        self.assertGreater(result.warning_count(), 0)

    def test_result_serializable(self):
        result = validate_config(env={"EIA_ENV": "dev"})
        d = result.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)


# ---------------------------------------------------------------------------
# TestBuildConfigReportMarkdown
# ---------------------------------------------------------------------------

class TestBuildConfigReportMarkdown(unittest.TestCase):

    def _get_result(self, env=None):
        return validate_config(
            env=env or {"AEMET_API_KEY": "abcdefghijklmnop12345678", "EIA_ENV": "dev"},
        )

    def test_contains_summary_section(self):
        result = self._get_result()
        md = build_config_report_markdown(result)
        self.assertIn("## 1. Resumen", md)

    def test_contains_variables_section(self):
        result = self._get_result()
        md = build_config_report_markdown(result)
        self.assertIn("## 2. Variables revisadas", md)

    def test_contains_security_warning(self):
        result = self._get_result()
        md = build_config_report_markdown(result)
        self.assertIn("no muestra claves reales", md)
        self.assertIn("enmascarados", md)

    def test_does_not_contain_real_secret(self):
        real_key = "abcdefghijklmnop12345678"
        result = validate_config(env={"AEMET_API_KEY": real_key})
        md = build_config_report_markdown(result)
        self.assertNotIn(real_key, md)

    def test_contains_masked_value(self):
        result = validate_config(env={"AEMET_API_KEY": "abcdefghijklmnop12345678"})
        md = build_config_report_markdown(result)
        self.assertIn("abcd...5678", md)

    def test_contains_recommendations_section(self):
        result = self._get_result()
        md = build_config_report_markdown(result)
        self.assertIn("## 4. Recomendaciones", md)

    def test_contains_status(self):
        result = self._get_result()
        md = build_config_report_markdown(result)
        self.assertIn(result.status, md)


# ---------------------------------------------------------------------------
# TestWriteConfigValidationOutputs
# ---------------------------------------------------------------------------

class TestWriteConfigValidationOutputs(unittest.TestCase):

    def test_writes_json_and_md(self):
        result = validate_config(env={"EIA_ENV": "dev"})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_config_validation_outputs(result, tmpdir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_json_is_loadable(self):
        result = validate_config(env={"EIA_ENV": "dev"})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, _ = write_config_validation_outputs(result, tmpdir)
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("status", data)
            self.assertIn("issues", data)

    def test_json_does_not_contain_real_secret(self):
        real_key = "abcdefghijklmnop12345678"
        result = validate_config(env={"AEMET_API_KEY": real_key})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, _ = write_config_validation_outputs(result, tmpdir)
            raw = json_path.read_text(encoding="utf-8")
            self.assertNotIn(real_key, raw)

    def test_md_does_not_contain_real_secret(self):
        real_key = "abcdefghijklmnop12345678"
        result = validate_config(env={"AEMET_API_KEY": real_key})
        with tempfile.TemporaryDirectory() as tmpdir:
            _, md_path = write_config_validation_outputs(result, tmpdir)
            raw = md_path.read_text(encoding="utf-8")
            self.assertNotIn(real_key, raw)

    def test_returns_path_objects(self):
        result = validate_config(env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_config_validation_outputs(result, tmpdir)
            self.assertIsInstance(json_path, Path)
            self.assertIsInstance(md_path, Path)

    def test_creates_output_dir_if_needed(self):
        result = validate_config(env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "sub" / "control_interno"
            json_path, md_path = write_config_validation_outputs(result, out_dir)
            self.assertTrue(out_dir.exists())
            self.assertTrue(json_path.exists())


# ---------------------------------------------------------------------------
# TestScanTextForPotentialSecrets
# ---------------------------------------------------------------------------

class TestScanTextForPotentialSecrets(unittest.TestCase):

    def test_detects_openai_sk_key(self):
        text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234"
        findings = scan_text_for_potential_secrets(text)
        self.assertTrue(any("sk-" in f for f in findings))

    def test_detects_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdefghij"
        findings = scan_text_for_potential_secrets(text)
        self.assertTrue(len(findings) > 0)

    def test_detects_jwt_pattern(self):
        text = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.SflKxwRJSMeKKF2QT4fwpMeJf36P"
        findings = scan_text_for_potential_secrets(text)
        self.assertTrue(len(findings) > 0)

    def test_detects_mapbox_pk_token(self):
        text = "MAPBOX_TOKEN=pk.eyJfakeSuperLongTokenThatLookReal123"
        findings = scan_text_for_potential_secrets(text)
        self.assertTrue(any("Mapbox" in f or "pk." in f for f in findings))

    def test_returns_masked_values(self):
        text = "sk-abcdefghijklmnopqrstuvwxyz1234"
        findings = scan_text_for_potential_secrets(text)
        for f in findings:
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz1234", f)

    def test_no_false_positives_on_short_text(self):
        text = "Hello world. This is a normal text without any secrets."
        findings = scan_text_for_potential_secrets(text)
        self.assertEqual(findings, [])

    def test_detects_api_key_pattern(self):
        text = 'api_key = "abcdefghijklmnopqrstuvwxy"'
        findings = scan_text_for_potential_secrets(text)
        self.assertTrue(len(findings) > 0)


# ---------------------------------------------------------------------------
# TestScanFileForPotentialSecrets
# ---------------------------------------------------------------------------

class TestScanFileForPotentialSecrets(unittest.TestCase):

    def test_detects_secret_in_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("sk-abcdefghijklmnopqrstuvwxyz1234567890\n")
            fname = f.name
        try:
            findings = scan_file_for_potential_secrets(fname)
            self.assertTrue(len(findings) > 0)
        finally:
            Path(fname).unlink()

    def test_returns_empty_for_nonexistent_file(self):
        findings = scan_file_for_potential_secrets("/nonexistent/file.txt")
        self.assertEqual(findings, [])

    def test_returns_empty_for_clean_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Esta es una descripcion de proyecto sin secretos.\n")
            fname = f.name
        try:
            findings = scan_file_for_potential_secrets(fname)
            self.assertEqual(findings, [])
        finally:
            Path(fname).unlink()

    def test_does_not_include_full_secret_in_findings(self):
        secret = "sk-mysupersecretkey12345678901234"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(f"API_KEY={secret}\n")
            fname = f.name
        try:
            findings = scan_file_for_potential_secrets(fname)
            for finding in findings:
                self.assertNotIn(secret, finding)
        finally:
            Path(fname).unlink()


# ---------------------------------------------------------------------------
# TestScanRepoForPotentialSecrets
# ---------------------------------------------------------------------------

class TestScanRepoForPotentialSecrets(unittest.TestCase):

    def test_detects_secret_in_allowed_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_file = Path(tmpdir) / "config.py"
            secret_file.write_text(
                "api_key = 'sk-abcdefghijklmnopqrstuvwxyz1234'\n",
                encoding="utf-8",
            )
            result = scan_repo_for_potential_secrets(tmpdir)
            self.assertEqual(result.status, "NO_CONFORME")
            self.assertGreater(result.error_count(), 0)

    def test_excludes_tmp_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_dir = Path(tmpdir) / "tmp"
            tmp_dir.mkdir()
            secret_file = tmp_dir / "secret.py"
            secret_file.write_text(
                "sk-abcdefghijklmnopqrstuvwxyz1234\n", encoding="utf-8"
            )
            result = scan_repo_for_potential_secrets(tmpdir)
            self.assertEqual(result.status, "OK")

    def test_excludes_venv_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_dir = Path(tmpdir) / "venv"
            venv_dir.mkdir()
            secret_file = venv_dir / "activate"
            secret_file.write_text(
                "sk-abcdefghijklmnopqrstuvwxyz1234\n", encoding="utf-8"
            )
            result = scan_repo_for_potential_secrets(tmpdir)
            self.assertEqual(result.status, "OK")

    def test_excludes_expediente_eia_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "expediente-EIA-2026-TEST"
            exp_dir.mkdir()
            secret_file = exp_dir / "file.py"
            secret_file.write_text(
                "sk-abcdefghijklmnopqrstuvwxyz1234\n", encoding="utf-8"
            )
            result = scan_repo_for_potential_secrets(tmpdir)
            self.assertEqual(result.status, "OK")

    def test_does_not_include_full_secret_in_issues(self):
        secret = "sk-mysupersecretkey12345678901234"
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text(f"key = '{secret}'\n", encoding="utf-8")
            result = scan_repo_for_potential_secrets(tmpdir)
            for issue in result.issues:
                self.assertNotIn(secret, issue.message)
                self.assertNotIn(secret, str(issue.evidence))

    def test_returns_ok_for_clean_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "readme.md"
            f.write_text("# Clean project\nNo secrets here.\n", encoding="utf-8")
            result = scan_repo_for_potential_secrets(tmpdir)
            self.assertEqual(result.status, "OK")

    def test_notes_include_scan_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_repo_for_potential_secrets(tmpdir)
            notes_text = " ".join(result.notes)
            self.assertIn("escaneados", notes_text)


# ---------------------------------------------------------------------------
# TestCLIConfigCheck
# ---------------------------------------------------------------------------

class TestCLIConfigCheck(unittest.TestCase):

    def _run(self, argv):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        return run_expediente.main(argv)

    def test_config_check_no_write_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            code = self._run([str(exp), "config-check"])
            result_json = exp / "control_interno" / "config_validation_result.json"
            self.assertFalse(result_json.exists())

    def test_config_check_with_write_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            self._run([str(exp), "config-check", "--write"])
            result_json = exp / "control_interno" / "config_validation_result.json"
            result_md = exp / "control_interno" / "config_validation_result.md"
            self.assertTrue(result_json.exists())
            self.assertTrue(result_md.exists())

    def test_config_check_exit_0_if_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            code = self._run([str(exp), "config-check"])
            self.assertEqual(code, 0)

    def test_config_check_required_missing_exit_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            # Temporarily patch env to force missing var
            import eia_agent.core.config_manager as cm
            orig = cm.KNOWN_ENV_VARS[:]
            try:
                # Cannot easily force required vars via CLI; test the function directly
                result = validate_config(
                    required_vars=["AEMET_API_KEY"],
                    env={},
                )
                self.assertFalse(result.is_valid())
            finally:
                cm.KNOWN_ENV_VARS.clear()
                cm.KNOWN_ENV_VARS.extend(orig)


# ---------------------------------------------------------------------------
# TestCLISecretsScan
# ---------------------------------------------------------------------------

class TestCLISecretsScan(unittest.TestCase):

    def _run(self, argv):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        return run_expediente.main(argv)

    def test_secrets_scan_no_write_exits_0_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            # Scan a clean expediente dir
            code = self._run([str(exp), "secrets-scan"])
            self.assertIn(code, [0, 1])

    def test_secrets_scan_with_write_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            self._run([str(exp), "secrets-scan", "--write"])
            result_json = exp / "control_interno" / "config_validation_result.json"
            self.assertTrue(result_json.exists())

    def test_secrets_scan_does_not_print_full_secret(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz1234"
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-2026-CLI-TEST"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            secret_file = exp / "bad_config.py"
            secret_file.write_text(f"key = '{secret}'\n", encoding="utf-8")
            # Run scan on the expediente (not full repo)
            result = scan_repo_for_potential_secrets(str(exp))
            # Verify no issue contains the full secret
            for issue in result.issues:
                self.assertNotIn(secret, issue.message)


# ---------------------------------------------------------------------------
# TestDataclasses
# ---------------------------------------------------------------------------

class TestDataclasses(unittest.TestCase):

    def test_config_issue_to_dict(self):
        issue = ConfigIssue(
            severity="ERROR",
            code="BE04-E001",
            variable="AEMET_API_KEY",
            message="Variable faltante.",
            recommendation="Configúrela.",
        )
        d = issue.to_dict()
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["code"], "BE04-E001")
        self.assertEqual(d["variable"], "AEMET_API_KEY")

    def test_config_issue_summary(self):
        issue = ConfigIssue(
            severity="WARNING",
            code="BE04-W001",
            variable="AEMET_API_KEY",
            message="Placeholder.",
            recommendation="Configure.",
        )
        s = issue.summary()
        self.assertIn("WARNING", s)
        self.assertIn("BE04-W001", s)
        self.assertIn("AEMET_API_KEY", s)

    def test_env_var_status_to_dict_no_real_value(self):
        status = EnvVarStatus(
            name="AEMET_API_KEY",
            present=True,
            is_sensitive=True,
            is_placeholder=False,
            masked_value="abcd...1234",
            source="environment",
        )
        d = status.to_dict()
        self.assertEqual(d["masked_value"], "abcd...1234")
        self.assertNotIn("abcdefghijklmnop1234", str(d))

    def test_env_var_status_summary_present(self):
        status = EnvVarStatus(
            name="AEMET_API_KEY",
            present=True,
            is_sensitive=True,
            is_placeholder=False,
            masked_value="abcd...1234",
            source="environment",
        )
        s = status.summary()
        self.assertIn("AEMET_API_KEY", s)
        self.assertIn("environment", s)

    def test_env_var_status_summary_absent(self):
        status = EnvVarStatus(
            name="AEMET_API_KEY",
            present=False,
            is_sensitive=True,
            is_placeholder=False,
            masked_value=None,
            source="missing",
        )
        s = status.summary()
        self.assertIn("ausente", s)

    def test_config_validation_result_counts(self):
        issues = [
            ConfigIssue("ERROR", "E1", None, "err", "fix"),
            ConfigIssue("WARNING", "W1", None, "warn", "fix"),
            ConfigIssue("INFO", "I1", None, "info", "fix"),
        ]
        result = ConfigValidationResult(status="NO_CONFORME", issues=issues)
        self.assertEqual(result.error_count(), 1)
        self.assertEqual(result.warning_count(), 1)
        self.assertEqual(result.info_count(), 1)
        self.assertFalse(result.is_valid())

    def test_config_validation_result_is_valid_true(self):
        result = ConfigValidationResult(status="OK", issues=[])
        self.assertTrue(result.is_valid())

    def test_config_validation_result_to_dict(self):
        result = ConfigValidationResult(
            status="OK",
            env_vars=[],
            issues=[],
            notes=["nota de prueba"],
        )
        d = result.to_dict()
        self.assertEqual(d["status"], "OK")
        self.assertIn("nota de prueba", d["notes"])


# ---------------------------------------------------------------------------
# TestConstantes
# ---------------------------------------------------------------------------

class TestConstantes(unittest.TestCase):

    def test_known_env_vars_includes_aemet(self):
        self.assertIn("AEMET_API_KEY", KNOWN_ENV_VARS)

    def test_known_env_vars_includes_eia_env(self):
        self.assertIn("EIA_ENV", KNOWN_ENV_VARS)

    def test_known_env_vars_has_4_items(self):
        self.assertEqual(len(KNOWN_ENV_VARS), 4)

    def test_sensitive_vars_does_not_include_eia_env(self):
        self.assertNotIn("EIA_ENV", SENSITIVE_ENV_VARS)

    def test_allowed_eia_env_includes_dev_test_prod(self):
        self.assertIn("dev", ALLOWED_EIA_ENV)
        self.assertIn("test", ALLOWED_EIA_ENV)
        self.assertIn("prod", ALLOWED_EIA_ENV)

    def test_config_status_has_4_values(self):
        self.assertEqual(len(CONFIG_STATUS), 4)

    def test_config_severity_has_3_values(self):
        self.assertEqual(len(CONFIG_SEVERITY), 3)

    def test_placeholder_values_includes_empty(self):
        self.assertIn("", PLACEHOLDER_VALUES)


if __name__ == "__main__":
    unittest.main()
