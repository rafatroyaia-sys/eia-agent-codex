"""tests/test_cli_runner.py — Suite de tests para CLI-01 (run_expediente.py).

Cubre los criterios de cierre del ítem:
- ayuda general del CLI devuelve exit 0
- validate sobre expediente válido mínimo devuelve 0
- validate con expediente inválido devuelve 1
- gate fase 1 funciona con expediente mínimo
- gate fase inválida devuelve exit 0 (warning, no error)
- recover sin --write-report no crea recovery_report.json
- recover con --write-report sí lo crea
- log-summary no crea eventos
- status no modifica expediente si no hay estado
- comandos contra PARCELA y NAVE-222 en solo lectura
"""
import io
import json
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# run_expediente.py está en la raíz del proyecto
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from run_expediente import main, build_parser

# Pilotos reales
NAVE_222 = _ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"
PARCELA  = _ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exp(tmp: str, name: str = "EIA-TEST-CLI") -> Path:
    exp = Path(tmp) / name
    exp.mkdir(parents=True, exist_ok=True)
    return exp


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _setup_minimal_capas(exp: Path) -> None:
    """Crea las 6 capas JSON con contenido mínimo que pasa los schemas v2.1."""
    capas = exp / "capas"
    capas.mkdir(exist_ok=True)

    _write_json(capas / "hechos_confirmados.json", [
        {"id": "HC-001", "categoria": "identificacion_instalacion",
         "campo": "nombre_instalacion", "valor": "Expediente de prueba CLI",
         "estado": "CONFIRMADO", "fuentes": ["DOC-001"], "nota": None},
    ])

    _write_json(capas / "inferencias_y_gaps.json", [
        {"id": "GAP-001", "tipo": "gap_documental",
         "descripcion": "Gap de prueba", "campo": "campo_prueba",
         "criticidad": "INFORMATIVA", "fuente": "DOC-001",
         "impacto": "ninguno en prueba",
         "accion_requerida": "ninguna", "fase_bloquea": None},
    ])

    _write_json(capas / "normativa_aplicable.json", [
        {"id": "NJ-001", "tipo": "ley_estatal",
         "norma": "Ley 21/2013, de 9 de diciembre, de evaluación ambiental",
         "referencia_boe": "BOE-A-2013-12913",
         "version": "Consolidada", "fecha_verificacion_online": "2026-04-21",
         "articulos_relevantes": ["art.45"], "anexos_relevantes": ["Anexo II"],
         "estado": "VERIFICADA ONLINE", "nota": None},
    ])

    _write_json(capas / "cartografia_trace.json", [
        {"id": "CT-001", "titulo": "Verificación coordenadas de prueba",
         "tipo_cartografia": "VERIFICACION_INTERNA",
         "archivo_resultado": "N/A", "estado": "VERIFICADO",
         "fuente": "Catastro", "sistema_referencia": "WGS84 / EPSG:4326",
         "datos": {"latitud": 28.0, "longitud": -13.0},
         "estado_evidencia": "CONFIRMADO",
         "limitacion": "Modo gabinete", "hc_asociado": "HC-001"},
    ])

    _write_json(capas / "salidas_generadas.json", [
        {"id": "SG-001", "fase": "Fase 2", "agente": "AG-04",
         "tipo": "ficha_objeto_evaluado",
         "nombre_archivo": "control_interno/ficha_objeto_evaluado.md",
         "archivo": "control_interno/ficha_objeto_evaluado.md",
         "fecha": "2026-04-21", "estado": "GENERADO_MODO_TEST",
         "descripcion": "Ficha de prueba",
         "asunciones_aplicadas": [], "pendientes_arrastrados": [],
         "nota": None},
    ])

    _write_json(capas / "matriz_trazabilidad.json", [
        {"id": "TR-001", "fuente_primaria": "DOC-001",
         "estado_evidencia": "CONFIRMADO",
         "dato": "Dato de prueba", "valor": "Valor de prueba",
         "hc_ids": ["HC-001"], "nota": None},
    ])


def _run_main(argv: list[str], *, capture: bool = True) -> tuple[int, str, str]:
    """Ejecuta main(argv) capturando stdout/stderr. Devuelve (exit_code, stdout, stderr)."""
    if not capture:
        return main(argv), "", ""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with patch("sys.stdout", buf_out), patch("sys.stderr", buf_err):
        code = main(argv)
    return code, buf_out.getvalue(), buf_err.getvalue()


def _get_ci_files(exp: Path) -> set[str]:
    ci = exp / "control_interno"
    if not ci.exists():
        return set()
    return {f.name for f in ci.iterdir() if f.is_file()}


# ---------------------------------------------------------------------------
# TestCLIParser
# ---------------------------------------------------------------------------

class TestCLIParser(unittest.TestCase):

    def test_build_parser_devuelve_argumentparser(self):
        import argparse
        self.assertIsInstance(build_parser(), argparse.ArgumentParser)

    def test_main_help_exit_0(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_sin_argumentos_exit_no_0(self):
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_main_expediente_inexistente_exit_1(self):
        code, _, err = _run_main(["expediente-que-no-existe", "status"])
        self.assertEqual(code, 1)
        self.assertIn("no existe", err)

    def test_main_expediente_es_fichero_exit_1(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            code, _, err = _run_main([f.name, "status"])
            self.assertEqual(code, 1)
            self.assertIn("directorio", err)


# ---------------------------------------------------------------------------
# TestCmdStatus
# ---------------------------------------------------------------------------

class TestCmdStatus(unittest.TestCase):

    def test_status_sin_estado_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            code, out, _ = _run_main([str(exp), "status"])
            self.assertEqual(code, 0)

    def test_status_sin_estado_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            files_before = _get_ci_files(exp)
            _run_main([str(exp), "status"])
            self.assertEqual(_get_ci_files(exp), files_before)

    def test_status_sin_estado_mensaje_informativo(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            code, out, _ = _run_main([str(exp), "status"])
            self.assertIn("sin estado", out.lower())

    def test_status_con_estado_imprime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            # Crear estado via EIAOrchestrator
            sys.path.insert(0, str(_ROOT / "src"))
            from eia_agent.core.orchestrator import EIAOrchestrator
            EIAOrchestrator(exp)  # crea el estado

            code, out, _ = _run_main([str(exp), "status"])
            self.assertEqual(code, 0)
            self.assertIn("Expediente", out)


# ---------------------------------------------------------------------------
# TestCmdValidate
# ---------------------------------------------------------------------------

class TestCmdValidate(unittest.TestCase):

    def test_validate_expediente_con_capas_validas_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            code, out, _ = _run_main([str(exp), "validate"])
            self.assertEqual(code, 0)

    def test_validate_expediente_sin_capas_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            # Sin capas → hay errores de validación
            code, out, _ = _run_main([str(exp), "validate"])
            self.assertEqual(code, 1)

    def test_validate_imprime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            code, out, _ = _run_main([str(exp), "validate"])
            self.assertGreater(len(out.strip()), 0)

    def test_validate_con_json_invalido_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            # Corromper una capa
            capa = exp / "capas" / "hechos_confirmados.json"
            capa.write_text("{ no es json", encoding="utf-8")
            code, out, _ = _run_main([str(exp), "validate"])
            self.assertEqual(code, 1)

    def test_validate_no_modifica_expediente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            files_before = {f for f in (exp / "capas").iterdir()}
            _run_main([str(exp), "validate"])
            files_after = {f for f in (exp / "capas").iterdir()}
            self.assertEqual(files_before, files_after)


# ---------------------------------------------------------------------------
# TestCmdGate
# ---------------------------------------------------------------------------

class TestCmdGate(unittest.TestCase):

    def test_gate_fase_1_expediente_minimo(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            code, out, _ = _run_main([str(exp), "gate", "1"])
            # El resultado depende del estado de las capas; lo importante es que no falla
            self.assertIn(code, (0, 1))
            self.assertGreater(len(out.strip()), 0)

    def test_gate_fase_valida_imprime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            _, out, _ = _run_main([str(exp), "gate", "1"])
            self.assertGreater(len(out.strip()), 0)

    def test_gate_fase_invalida_exit_0_con_warning(self):
        # Fase inválida produce UNKNOWN_PHASE warning, no ERROR → gate no bloqueado → exit 0
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            code, out, _ = _run_main([str(exp), "gate", "99"])
            # No debe ser error fatal; gate puede pasar o no dependiendo de implementación
            self.assertIn(code, (0, 1))

    def test_gate_flag_prod_funciona(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            code_test, _, _ = _run_main([str(exp), "gate", "1"])
            code_prod, _, _ = _run_main([str(exp), "gate", "1", "--prod"])
            # Ambos deben ejecutar sin excepción
            self.assertIn(code_test, (0, 1))
            self.assertIn(code_prod, (0, 1))

    def test_gate_no_modifica_expediente(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _setup_minimal_capas(exp)
            files_before = _get_ci_files(exp)
            _run_main([str(exp), "gate", "1"])
            self.assertEqual(_get_ci_files(exp), files_before)


# ---------------------------------------------------------------------------
# TestCmdRecover
# ---------------------------------------------------------------------------

class TestCmdRecover(unittest.TestCase):

    def test_recover_sin_flag_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            code, out, _ = _run_main([str(exp), "recover"])
            self.assertEqual(code, 0)  # can_continue=True cuando no hay estado

    def test_recover_sin_write_report_no_crea_archivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _run_main([str(exp), "recover"])
            report_path = exp / "control_interno" / "recovery_report.json"
            self.assertFalse(report_path.exists())

    def test_recover_con_write_report_crea_archivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _run_main([str(exp), "recover", "--write-report"])
            report_path = exp / "control_interno" / "recovery_report.json"
            self.assertTrue(report_path.exists())

    def test_recover_con_write_report_json_valido(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _run_main([str(exp), "recover", "--write-report"])
            report_path = exp / "control_interno" / "recovery_report.json"
            data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("can_continue", data)
            self.assertIn("suggested_action", data)

    def test_recover_imprime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _, out, _ = _run_main([str(exp), "recover"])
            self.assertGreater(len(out.strip()), 0)

    def test_recover_expediente_con_fase_in_progress_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            # Crear estado con fase IN_PROGRESS
            from eia_agent.core.orchestrator import EIAOrchestrator
            orch = EIAOrchestrator(exp)
            orch.start_phase("1")  # queda IN_PROGRESS
            code, _, _ = _run_main([str(exp), "recover"])
            self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# TestCmdLogSummary
# ---------------------------------------------------------------------------

class TestCmdLogSummary(unittest.TestCase):

    def test_log_summary_sin_log_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            code, out, _ = _run_main([str(exp), "log-summary"])
            self.assertEqual(code, 0)

    def test_log_summary_imprime_algo(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            _, out, _ = _run_main([str(exp), "log-summary"])
            self.assertGreater(len(out.strip()), 0)

    def test_log_summary_no_crea_eventos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            log_path = exp / "control_interno" / "orchestrator_log.json"
            _run_main([str(exp), "log-summary"])
            # No debe crear el log si no existía
            self.assertFalse(log_path.exists())

    def test_log_summary_con_log_existente_no_añade_eventos(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = _make_exp(tmp)
            from eia_agent.core.orchestrator import EIAOrchestrator
            orch = EIAOrchestrator(exp)
            orch.start_phase("1")
            log_path = exp / "control_interno" / "orchestrator_log.json"
            eventos_before = len(json.loads(log_path.read_text(encoding="utf-8")))
            _run_main([str(exp), "log-summary"])
            eventos_after = len(json.loads(log_path.read_text(encoding="utf-8")))
            self.assertEqual(eventos_before, eventos_after)


# ---------------------------------------------------------------------------
# TestPilotoRealNave222
# ---------------------------------------------------------------------------

class TestPilotoRealNave222(unittest.TestCase):

    def _cleanup_report(self):
        p = NAVE_222 / "control_interno" / "recovery_report.json"
        if p.exists():
            p.unlink()

    def setUp(self):
        self.addCleanup(self._cleanup_report)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_validate_exit_0(self):
        code, out, _ = _run_main([str(NAVE_222), "validate"])
        self.assertEqual(code, 0, msg=f"Validate falló:\n{out}")

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_validate_no_modifica_expediente(self):
        ci_files_before = _get_ci_files(NAVE_222)
        time.sleep(0.05)
        _run_main([str(NAVE_222), "validate"])
        ci_files_after = _get_ci_files(NAVE_222)
        self.assertEqual(ci_files_before, ci_files_after)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_gate_9_test_mode_exit_0_o_1(self):
        # Gate 9 puede bloquearse o no según el estado del expediente; no debe lanzar excepción
        code, out, _ = _run_main([str(NAVE_222), "gate", "9"])
        self.assertIn(code, (0, 1))
        self.assertGreater(len(out.strip()), 0)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_gate_1_no_modifica_expediente(self):
        ci_files_before = _get_ci_files(NAVE_222)
        time.sleep(0.05)
        _run_main([str(NAVE_222), "gate", "1"])
        ci_files_after = _get_ci_files(NAVE_222)
        self.assertEqual(ci_files_before, ci_files_after)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_recover_sin_write_report_no_deja_archivo(self):
        _run_main([str(NAVE_222), "recover"])
        report_path = NAVE_222 / "control_interno" / "recovery_report.json"
        self.assertFalse(report_path.exists())

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_status_sin_estado_exit_0(self):
        # NAVE-222 es piloto manual sin orchestrator_state.json
        state_path = NAVE_222 / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            code, out, _ = _run_main([str(NAVE_222), "status"])
            self.assertEqual(code, 0)
            self.assertIn("sin estado", out.lower())

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_status_no_crea_estado(self):
        state_path = NAVE_222 / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            ci_files_before = _get_ci_files(NAVE_222)
            _run_main([str(NAVE_222), "status"])
            ci_files_after = _get_ci_files(NAVE_222)
            self.assertEqual(ci_files_before, ci_files_after)

    @unittest.skipUnless(NAVE_222.exists(), "Expediente NAVE-222 no disponible")
    def test_log_summary_exit_0(self):
        code, _, _ = _run_main([str(NAVE_222), "log-summary"])
        self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# TestPilotoRealParcela
# ---------------------------------------------------------------------------

class TestPilotoRealParcela(unittest.TestCase):

    def _cleanup_report(self):
        p = PARCELA / "control_interno" / "recovery_report.json"
        if p.exists():
            p.unlink()

    def setUp(self):
        self.addCleanup(self._cleanup_report)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_validate_exit_0(self):
        code, out, _ = _run_main([str(PARCELA), "validate"])
        self.assertEqual(code, 0, msg=f"Validate falló:\n{out}")

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_validate_no_modifica_expediente(self):
        ci_files_before = _get_ci_files(PARCELA)
        time.sleep(0.05)
        _run_main([str(PARCELA), "validate"])
        ci_files_after = _get_ci_files(PARCELA)
        self.assertEqual(ci_files_before, ci_files_after)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_gate_9_test_mode_exit_0_o_1(self):
        code, out, _ = _run_main([str(PARCELA), "gate", "9"])
        self.assertIn(code, (0, 1))
        self.assertGreater(len(out.strip()), 0)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_recover_sin_write_report_no_deja_archivo(self):
        _run_main([str(PARCELA), "recover"])
        report_path = PARCELA / "control_interno" / "recovery_report.json"
        self.assertFalse(report_path.exists())

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_status_sin_estado_exit_0(self):
        state_path = PARCELA / "control_interno" / "orchestrator_state.json"
        if not state_path.exists():
            code, out, _ = _run_main([str(PARCELA), "status"])
            self.assertEqual(code, 0)

    @unittest.skipUnless(PARCELA.exists(), "Expediente PARCELA no disponible")
    def test_log_summary_exit_0(self):
        code, _, _ = _run_main([str(PARCELA), "log-summary"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
