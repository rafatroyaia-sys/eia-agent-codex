"""tests/test_gate_checker.py — Suite de tests para GateChecker (NL-04).

Cubre los criterios de cierre del ítem:
- GateChecker se inicializa en expediente temporal
- check_model_schema pasa con estructura válida mínima
- check_model_schema falla si falta capa
- fase 1 pasa con capas mínimas y HC no vacío
- fase 2 falla si falta ficha_objeto_evaluado.md
- fase 3 falla si normativa está vacía
- fase 4 emite WARNING con cartografía PROVISIONAL en test
- fase 4 emite ERROR con cartografía PROVISIONAL en producción
- fase 6 falla si falta impactos.json
- fase 7 falla si falta un bloque
- fase 8 detecta docx existente
- fase 9 detecta informe M-12 con conclusión
- ASUNCION_TEST genera WARNING en test
- ASUNCION_TEST genera ERROR en producción
- log con error bloqueante genera ERROR
- summary() devuelve texto útil
- pruebas de solo lectura contra expedientes reales PARCELA y NAVE-222
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.gate_checker import (
    FINAL_CONCLUSION_KEYWORDS,
    REQUIRED_BLOCKS,
    REQUIRED_IMPACT_FILES,
    REQUIRED_LAYERS,
    GateChecker,
    GateIssue,
    GateResult,
)
from eia_agent.core.orchestrator import EIAOrchestrator
from eia_agent.core.orchestrator_log import EventStatus, EventType


# ---------------------------------------------------------------------------
# Rutas de referencia (solo lectura)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_NAVE222   = _REPO_ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"
_PARCELA   = _REPO_ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _make_exp(tmp: Path, name: str = "EIA-TEST-GC") -> Path:
    """Crea directorio de expediente vacío."""
    exp = tmp / f"expediente-{name}"
    exp.mkdir(parents=True)
    return exp


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _setup_capas_from(exp: Path, src: Path) -> None:
    """Copia la carpeta capas/ del expediente src al exp (solo lectura del origen)."""
    src_capas = src / "capas"
    if src_capas.exists():
        shutil.copytree(src_capas, exp / "capas")


def _setup_minimal_capas(exp: Path) -> None:
    """Crea las 6 capas mínimas con contenido sintético válido."""
    capas = exp / "capas"
    capas.mkdir(parents=True, exist_ok=True)
    hc = [{"id": "HC-001", "campo": "nombre", "valor": "TEST", "estado": "CONFIRMADO", "fuentes": ["DOC-001"]}]
    _write_json(capas / "hechos_confirmados.json", hc)
    _write_json(capas / "inferencias_y_gaps.json", [])
    _write_json(capas / "normativa_aplicable.json", [
        {"id": "NJ-001", "norma": "Ley test", "estado": "VERIFICADA ONLINE"}
    ])
    _write_json(capas / "cartografia_trace.json", [
        {"id": "CT-001", "titulo": "Ubicación", "estado": "VERIFICADO"}
    ])
    _write_json(capas / "salidas_generadas.json", [
        {"id": "SG-001", "tipo": "descripcion_clima", "archivo": "clima/descripcion_clima.md"}
    ])
    _write_json(capas / "matriz_trazabilidad.json", [])


def _setup_all_blocks(exp: Path) -> None:
    """Crea los 12 bloques requeridos con contenido mínimo."""
    bloques = exp / "bloques"
    bloques.mkdir(parents=True, exist_ok=True)
    for bloque in REQUIRED_BLOCKS:
        (bloques / bloque).write_text(f"# {bloque}\nContenido de prueba.\n", encoding="utf-8")


def _setup_impactos(exp: Path) -> None:
    """Crea impactos/, medidas.json y pva.json con contenido mínimo."""
    imp = exp / "impactos"
    imp.mkdir(parents=True, exist_ok=True)
    _write_json(imp / "impactos.json", [
        {"id": "IMP-001", "descripcion": "Ruido test", "signo": "negativo"}
    ])
    _write_json(imp / "medidas.json", [
        {"id": "MED-001", "descripcion": "Insonorización test"}
    ])
    _write_json(imp / "pva.json", [
        {"id": "PVA-001", "impacto": "IMP-001", "indicador": "Leq dB(A)"}
    ])


def _setup_output_with_docx(exp: Path, nombre: str = "DA_TEST_BORRADOR.docx") -> None:
    """Crea output/ con un .docx vacío (solo para verificar existencia)."""
    out = exp / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / nombre).write_bytes(b"PK\x03\x04")  # magic number ZIP/DOCX mínimo


def _setup_audit_report(exp: Path, conclusion: str = "CON OBSERVACIONES EN MODO TEST") -> None:
    """Crea informe_auditoria_final.md con una conclusión reconocible."""
    ci = exp / "control_interno"
    ci.mkdir(parents=True, exist_ok=True)
    content = f"# INFORME M-12\n\n## Conclusión\n\nResultado: **{conclusion}**\n"
    (ci / "informe_auditoria_final.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests de GateIssue y GateResult
# ---------------------------------------------------------------------------

class TestGateIssue(unittest.TestCase):

    def test_str_includes_severity_and_code(self):
        issue = GateIssue(severity="ERROR", phase="1", code="TEST_CODE", message="Test msg")
        s = str(issue)
        self.assertIn("ERROR", s)
        self.assertIn("TEST_CODE", s)

    def test_str_includes_path_when_present(self):
        issue = GateIssue(severity="WARNING", phase="2", code="X", message="m", path="capas/foo.json")
        self.assertIn("capas/foo.json", str(issue))

    def test_str_no_path_when_absent(self):
        issue = GateIssue(severity="INFO", phase="1", code="X", message="m")
        self.assertNotIn("[None]", str(issue))


class TestGateResult(unittest.TestCase):

    def _result(self, issues: list) -> GateResult:
        return GateResult(
            expediente_path=Path("/tmp/test"),
            phase="1",
            passed=not any(i.severity == "ERROR" for i in issues),
            test_mode=True,
            issues=issues,
        )

    def test_error_count(self):
        r = self._result([
            GateIssue("ERROR", "1", "E", "m"),
            GateIssue("WARNING", "1", "W", "m"),
            GateIssue("INFO", "1", "I", "m"),
        ])
        self.assertEqual(r.error_count(), 1)
        self.assertEqual(r.warning_count(), 1)
        self.assertEqual(r.info_count(), 1)

    def test_is_blocked_true_when_error(self):
        r = self._result([GateIssue("ERROR", "1", "E", "m")])
        self.assertTrue(r.is_blocked())

    def test_is_blocked_false_when_only_warnings(self):
        r = self._result([GateIssue("WARNING", "1", "W", "m")])
        self.assertFalse(r.is_blocked())

    def test_summary_nonempty(self):
        r = self._result([])
        s = r.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 0)

    def test_summary_contains_gate_status(self):
        r = self._result([])
        r.passed = True
        self.assertIn("PASSED", r.summary())

    def test_summary_contains_expediente_name(self):
        r = GateResult(Path("/tmp/expediente-TEST"), "1", True, True, [])
        self.assertIn("expediente-TEST", r.summary())


# ---------------------------------------------------------------------------
# Tests de inicialización
# ---------------------------------------------------------------------------

class TestGateCheckerInit(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initializes_without_error(self):
        """GateChecker se inicializa en expediente temporal sin error."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp, test_mode=True)
        self.assertEqual(gc.expediente_id, exp.name)
        self.assertTrue(gc.test_mode)

    def test_does_not_create_files(self):
        """GateChecker no crea archivos al inicializarse."""
        exp = _make_exp(self.tmp_path)
        _ = GateChecker(exp)
        contents = list(exp.rglob("*"))
        self.assertEqual(len(contents), 0)

    def test_accepts_string_path(self):
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(str(exp))
        self.assertIsInstance(gc.expediente_path, Path)


# ---------------------------------------------------------------------------
# Tests de check_model_schema
# ---------------------------------------------------------------------------

class TestCheckModelSchema(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_fails_on_empty_expediente(self):
        """check_model_schema falla si faltan capas."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_model_schema()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertGreater(len(errors), 0)

    def test_schema_passes_with_nave222_capas(self):
        """check_model_schema pasa con capas copiadas de NAVE-222 (validadas en NL-01)."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        exp = _make_exp(self.tmp_path)
        _setup_capas_from(exp, _NAVE222)
        gc = GateChecker(exp)
        issues = gc.check_model_schema()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0, f"Errores inesperados: {errors}")

    def test_schema_returns_list(self):
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        result = gc.check_model_schema()
        self.assertIsInstance(result, list)

    def test_schema_issues_have_correct_fields(self):
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_model_schema()
        for issue in issues:
            self.assertIn(issue.severity, ("ERROR", "WARNING", "INFO"))
            self.assertIsInstance(issue.code, str)
            self.assertIsInstance(issue.message, str)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 1
# ---------------------------------------------------------------------------

class TestPhase1(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase1_no_errors_with_minimal_valid_structure(self):
        """Fase 1 sin errores estructurales con capas mínimas y HC no vacío."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        gc = GateChecker(exp)
        issues = gc.check_required_files("1")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase1_error_missing_layer(self):
        """Fase 1 → ERROR si falta una capa requerida."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        (exp / "capas" / "normativa_aplicable.json").unlink()
        gc = GateChecker(exp)
        issues = gc.check_required_files("1")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("LAYER_MISSING", codes)

    def test_phase1_error_hc_empty(self):
        """Fase 1 → ERROR si hechos_confirmados.json está vacío."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        _write_json(exp / "capas" / "hechos_confirmados.json", [])
        gc = GateChecker(exp)
        issues = gc.check_required_files("1")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("HC_EMPTY", codes)

    def test_phase1_all_layers_checked(self):
        """Fase 1 emite un ERROR por cada capa ausente."""
        exp = _make_exp(self.tmp_path)
        # No capas en absoluto
        gc = GateChecker(exp)
        issues = gc.check_required_files("1")
        layer_errors = [i for i in issues if i.code == "LAYER_MISSING"]
        self.assertEqual(len(layer_errors), len(REQUIRED_LAYERS))


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 2
# ---------------------------------------------------------------------------

class TestPhase2(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase2_error_missing_ficha_objeto(self):
        """Fase 2 → ERROR si falta ficha_objeto_evaluado.md."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        gc = GateChecker(exp)
        issues = gc.check_required_files("2")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("FICHA_OBJETO_MISSING", codes)

    def test_phase2_no_error_when_ficha_present(self):
        """Fase 2 sin error de ficha si ficha_objeto_evaluado.md existe."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "ficha_objeto_evaluado.md").write_text("# Ficha\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("2")
        ficha_errors = [i for i in issues if i.code == "FICHA_OBJETO_MISSING"]
        self.assertEqual(len(ficha_errors), 0)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 3
# ---------------------------------------------------------------------------

class TestPhase3(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase3_error_normativa_empty(self):
        """Fase 3 → ERROR si normativa_aplicable.json está vacío."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        _write_json(exp / "capas" / "normativa_aplicable.json", [])
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "nota_encuadre_legal.md").write_text("# Nota\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("3")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("NORMATIVA_EMPTY", codes)

    def test_phase3_error_normativa_sin_verificar(self):
        """Fase 3 → ERROR si ninguna norma tiene estado válido."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        _write_json(exp / "capas" / "normativa_aplicable.json", [
            {"id": "NJ-001", "norma": "Ley test", "estado": "PENDIENTE"}
        ])
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "nota_encuadre_legal.md").write_text("# Nota\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("3")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("NORMATIVA_SIN_VERIFICAR", codes)

    def test_phase3_no_error_with_verificada_online(self):
        """Fase 3 sin error cuando hay norma con estado VERIFICADA ONLINE."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        _write_json(exp / "capas" / "normativa_aplicable.json", [
            {"id": "NJ-001", "norma": "Ley 21/2013", "estado": "VERIFICADA ONLINE"}
        ])
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "nota_encuadre_legal.md").write_text("# Nota\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("3")
        normativa_errors = [i for i in issues if i.code in ("NORMATIVA_EMPTY", "NORMATIVA_SIN_VERIFICAR")]
        self.assertEqual(len(normativa_errors), 0)

    def test_phase3_error_missing_nota_legal(self):
        """Fase 3 → ERROR si falta nota_encuadre_legal.md."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        gc = GateChecker(exp)
        issues = gc.check_required_files("3")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("NOTA_LEGAL_MISSING", codes)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 4
# ---------------------------------------------------------------------------

class TestPhase4(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_exp_with_carta_provisional(self, n: int = 3) -> Path:
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        ct = [{"id": f"CT-{i:03d}", "titulo": f"Mapa {i}", "estado": "PROVISIONAL"} for i in range(1, n + 1)]
        _write_json(exp / "capas" / "cartografia_trace.json", ct)
        (exp / "clima").mkdir(parents=True, exist_ok=True)
        (exp / "clima" / "descripcion_clima.md").write_text("# Clima\n", encoding="utf-8")
        return exp

    def test_phase4_provisional_warning_in_test_mode(self):
        """Fase 4 → WARNING con cartografía PROVISIONAL en test_mode=True."""
        exp = self._make_exp_with_carta_provisional()
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_required_files("4")
        provisional_issues = [i for i in issues if i.code == "CARTOGRAFIA_PROVISIONAL"]
        self.assertEqual(len(provisional_issues), 1)
        self.assertEqual(provisional_issues[0].severity, "WARNING")

    def test_phase4_provisional_error_in_prod_mode(self):
        """Fase 4 → ERROR con cartografía PROVISIONAL en test_mode=False."""
        exp = self._make_exp_with_carta_provisional()
        gc = GateChecker(exp, test_mode=False)
        issues = gc.check_required_files("4")
        provisional_issues = [i for i in issues if i.code == "CARTOGRAFIA_PROVISIONAL"]
        self.assertEqual(len(provisional_issues), 1)
        self.assertEqual(provisional_issues[0].severity, "ERROR")

    def test_phase4_no_provisional_issue_when_verificado(self):
        """Fase 4 sin issue PROVISIONAL cuando todos los mapas son VERIFICADO."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        # cartografia_trace ya está VERIFICADO por _setup_minimal_capas
        (exp / "clima").mkdir(parents=True, exist_ok=True)
        (exp / "clima" / "descripcion_clima.md").write_text("# Clima\n", encoding="utf-8")
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_required_files("4")
        provisional_issues = [i for i in issues if i.code == "CARTOGRAFIA_PROVISIONAL"]
        self.assertEqual(len(provisional_issues), 0)

    def test_phase4_error_clima_missing(self):
        """Fase 4 → ERROR si no hay descripcion_clima.md ni salida climática."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        _write_json(exp / "capas" / "salidas_generadas.json", [])  # sin clima
        gc = GateChecker(exp)
        issues = gc.check_required_files("4")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("CLIMA_MISSING", codes)

    def test_phase4_clima_ok_via_salidas_generadas(self):
        """Fase 4 OK si hay entrada de clima en salidas_generadas.json."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        # salidas_generadas ya incluye tipo=descripcion_clima en _setup_minimal_capas
        gc = GateChecker(exp)
        issues = gc.check_required_files("4")
        clima_errors = [i for i in issues if i.code == "CLIMA_MISSING"]
        self.assertEqual(len(clima_errors), 0)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 5
# ---------------------------------------------------------------------------

class TestPhase5(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase5_error_missing_inventario_dir(self):
        """Fase 5 → ERROR si fichas_inventario/ no existe."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_required_files("5")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("INVENTARIO_DIR_MISSING", codes)

    def test_phase5_warning_less_than_16_factors(self):
        """Fase 5 → WARNING si hay menos de 16 fichas FI-*.md."""
        exp = _make_exp(self.tmp_path)
        inv = exp / "fichas_inventario"
        inv.mkdir(parents=True, exist_ok=True)
        for i in range(1, 10):  # solo 9 fichas
            (inv / f"FI-{i:03d}_factor.md").write_text("# FI\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("5")
        warn_codes = [i.code for i in issues if i.severity == "WARNING"]
        self.assertIn("INVENTARIO_FACTORES_INCOMPLETO", warn_codes)

    def test_phase5_no_warning_with_16_factors(self):
        """Fase 5 sin WARNING de factores con exactamente 16 FI-*.md."""
        exp = _make_exp(self.tmp_path)
        inv = exp / "fichas_inventario"
        inv.mkdir(parents=True, exist_ok=True)
        for i in range(1, 17):
            (inv / f"FI-{i:03d}_factor.md").write_text("# FI\n", encoding="utf-8")
        gc = GateChecker(exp)
        issues = gc.check_required_files("5")
        factor_issues = [i for i in issues if i.code == "INVENTARIO_FACTORES_INCOMPLETO"]
        self.assertEqual(len(factor_issues), 0)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 6
# ---------------------------------------------------------------------------

class TestPhase6(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase6_error_missing_impactos_dir(self):
        """Fase 6 → ERROR si carpeta impactos/ no existe."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_required_files("6")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("IMPACTOS_DIR_MISSING", codes)

    def test_phase6_error_missing_impactos_json(self):
        """Fase 6 → ERROR si falta impactos.json y su alias."""
        exp = _make_exp(self.tmp_path)
        imp = exp / "impactos"
        imp.mkdir(parents=True, exist_ok=True)
        # Solo pva.json, sin impactos ni medidas
        _write_json(imp / "pva.json", [{"id": "PVA-001"}])
        gc = GateChecker(exp)
        issues = gc.check_required_files("6")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("IMPACT_FILE_MISSING_IMPACTOS", codes)
        self.assertIn("IMPACT_FILE_MISSING_MEDIDAS", codes)

    def test_phase6_passes_with_canonical_names(self):
        """Fase 6 sin errores con impactos.json, medidas.json, pva.json."""
        exp = _make_exp(self.tmp_path)
        _setup_impactos(exp)
        gc = GateChecker(exp)
        issues = gc.check_required_files("6")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase6_passes_with_alias_names(self):
        """Fase 6 sin errores con nombres alias del piloto PARCELA."""
        exp = _make_exp(self.tmp_path)
        imp = exp / "impactos"
        imp.mkdir(parents=True, exist_ok=True)
        _write_json(imp / "identificacion_valoracion_impactos.json", [{"id": "IMP-001"}])
        _write_json(imp / "medidas_correctoras.json", [{"id": "MED-001"}])
        _write_json(imp / "pva.json", [{"id": "PVA-001"}])
        gc = GateChecker(exp)
        issues = gc.check_required_files("6")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase6_error_empty_impactos(self):
        """Fase 6 → ERROR si impactos.json existe pero está vacío."""
        exp = _make_exp(self.tmp_path)
        imp = exp / "impactos"
        imp.mkdir(parents=True, exist_ok=True)
        _write_json(imp / "impactos.json", [])
        _write_json(imp / "medidas.json", [{"id": "MED-001"}])
        _write_json(imp / "pva.json", [{"id": "PVA-001"}])
        gc = GateChecker(exp)
        issues = gc.check_required_files("6")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("IMPACT_FILE_EMPTY_IMPACTOS", codes)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 7
# ---------------------------------------------------------------------------

class TestPhase7(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase7_no_errors_with_all_blocks(self):
        """Fase 7 sin errores con los 12 bloques presentes."""
        exp = _make_exp(self.tmp_path)
        _setup_all_blocks(exp)
        gc = GateChecker(exp)
        issues = gc.check_required_files("7")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase7_error_missing_one_block(self):
        """Fase 7 → ERROR si falta un bloque."""
        exp = _make_exp(self.tmp_path)
        _setup_all_blocks(exp)
        (exp / "bloques" / "C_impactos.md").unlink()
        gc = GateChecker(exp)
        issues = gc.check_required_files("7")
        bloque_errors = [i for i in issues if i.code == "BLOQUE_MISSING"]
        self.assertEqual(len(bloque_errors), 1)
        self.assertIn("C_impactos.md", bloque_errors[0].message)

    def test_phase7_error_missing_dir(self):
        """Fase 7 → ERROR si carpeta bloques/ no existe."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_required_files("7")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("BLOQUES_DIR_MISSING", codes)

    def test_phase7_all_blocks_checked(self):
        """Fase 7 emite un ERROR por bloque ausente cuando bloques/ existe vacío."""
        exp = _make_exp(self.tmp_path)
        (exp / "bloques").mkdir(parents=True, exist_ok=True)
        gc = GateChecker(exp)
        issues = gc.check_required_files("7")
        bloque_errors = [i for i in issues if i.code == "BLOQUE_MISSING"]
        self.assertEqual(len(bloque_errors), len(REQUIRED_BLOCKS))


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 8
# ---------------------------------------------------------------------------

class TestPhase8(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase8_detects_docx(self):
        """Fase 8 sin error cuando output/ contiene un .docx."""
        exp = _make_exp(self.tmp_path)
        _setup_output_with_docx(exp)
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_required_files("8")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase8_error_no_docx(self):
        """Fase 8 → ERROR si output/ existe pero no hay .docx."""
        exp = _make_exp(self.tmp_path)
        (exp / "output").mkdir(parents=True, exist_ok=True)
        gc = GateChecker(exp)
        issues = gc.check_required_files("8")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("DOCX_MISSING", codes)

    def test_phase8_error_no_output_dir(self):
        """Fase 8 → ERROR si output/ no existe."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_required_files("8")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("OUTPUT_DIR_MISSING", codes)

    def test_phase8_warning_docx_sin_marca_test(self):
        """Fase 8 → WARNING si DOCX no tiene 'BORRADOR'/'TEST' en nombre (test_mode=True)."""
        exp = _make_exp(self.tmp_path)
        _setup_output_with_docx(exp, nombre="DA_FINAL_v1.docx")
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_required_files("8")
        warn_codes = [i.code for i in issues if i.severity == "WARNING"]
        self.assertIn("DOCX_SIN_MARCA_TEST", warn_codes)

    def test_phase8_no_warning_when_name_has_borrador(self):
        """Fase 8 sin WARNING si el DOCX tiene 'BORRADOR' en el nombre."""
        exp = _make_exp(self.tmp_path)
        _setup_output_with_docx(exp, nombre="DA_BORRADOR_v1.docx")
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_required_files("8")
        warn_codes = [i.code for i in issues if i.code == "DOCX_SIN_MARCA_TEST"]
        self.assertEqual(len(warn_codes), 0)


# ---------------------------------------------------------------------------
# Tests de check_required_files — Fase 9
# ---------------------------------------------------------------------------

class TestPhase9(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase9_detects_audit_with_conclusion(self):
        """Fase 9 sin error cuando informe tiene conclusión reconocible."""
        exp = _make_exp(self.tmp_path)
        _setup_audit_report(exp, "CONFORME EN MODO TEST")
        gc = GateChecker(exp)
        issues = gc.check_required_files("9")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_phase9_error_missing_audit(self):
        """Fase 9 → ERROR si informe_auditoria_final.md no existe."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_required_files("9")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("AUDITORIA_MISSING", codes)

    def test_phase9_error_audit_without_conclusion(self):
        """Fase 9 → ERROR si el informe existe pero sin conclusión reconocible."""
        exp = _make_exp(self.tmp_path)
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "informe_auditoria_final.md").write_text(
            "# Informe\nContenido sin conclusión estándar.\n", encoding="utf-8"
        )
        gc = GateChecker(exp)
        issues = gc.check_required_files("9")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("AUDITORIA_SIN_CONCLUSION", codes)

    def test_phase9_accepts_all_conclusion_keywords(self):
        """Fase 9 acepta cualquiera de los FINAL_CONCLUSION_KEYWORDS."""
        for kw in FINAL_CONCLUSION_KEYWORDS:
            with self.subTest(keyword=kw):
                tmp = tempfile.TemporaryDirectory()
                try:
                    exp = _make_exp(Path(tmp.name))
                    _setup_audit_report(exp, kw)
                    gc = GateChecker(exp)
                    issues = gc.check_required_files("9")
                    errors = [i for i in issues if i.severity == "ERROR"]
                    self.assertEqual(len(errors), 0, f"Error inesperado para keyword '{kw}': {errors}")
                finally:
                    tmp.cleanup()


# ---------------------------------------------------------------------------
# Tests de check_test_mode_conditions — ASUNCION_TEST
# ---------------------------------------------------------------------------

class TestAsuncionTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _exp_with_at_in_hc(self) -> Path:
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        hc = [
            {"id": "HC-001", "campo": "nombre", "valor": "TEST", "estado": "CONFIRMADO",
             "fuentes": ["DOC-001"], "nota": "Asunción test: AT-001 activa"},
        ]
        _write_json(exp / "capas" / "hechos_confirmados.json", hc)
        return exp

    def test_at_en_hechos_warning_in_test_mode(self):
        """AT en hechos → WARNING en test_mode=True."""
        exp = self._exp_with_at_in_hc()
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_test_mode_conditions("1")
        at_issues = [i for i in issues if i.code == "AT_EN_HECHOS"]
        self.assertEqual(len(at_issues), 1)
        self.assertEqual(at_issues[0].severity, "WARNING")

    def test_at_en_hechos_error_in_prod_mode(self):
        """AT en hechos → ERROR en test_mode=False."""
        exp = self._exp_with_at_in_hc()
        gc = GateChecker(exp, test_mode=False)
        issues = gc.check_test_mode_conditions("1")
        at_issues = [i for i in issues if i.code == "AT_EN_HECHOS"]
        self.assertEqual(len(at_issues), 1)
        self.assertEqual(at_issues[0].severity, "ERROR")

    def test_no_at_issue_when_hc_has_no_at_references(self):
        """Sin AT en hechos → sin issue AT_EN_HECHOS."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_test_mode_conditions("1")
        at_issues = [i for i in issues if i.code == "AT_EN_HECHOS"]
        self.assertEqual(len(at_issues), 0)

    def test_at_file_present_warning_in_test_mode(self):
        """Archivo asunciones_test*.md detectado → WARNING en test_mode=True."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "asunciones_test_expediente.md").write_text("# AT\n", encoding="utf-8")
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_test_mode_conditions("1")
        at_file_issues = [i for i in issues if i.code == "AT_FILE_PRESENT"]
        self.assertEqual(len(at_file_issues), 1)
        self.assertEqual(at_file_issues[0].severity, "WARNING")

    def test_at_file_present_error_in_prod_mode(self):
        """Archivo asunciones_test*.md detectado → ERROR en test_mode=False."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        ci = exp / "control_interno"
        ci.mkdir(parents=True, exist_ok=True)
        (ci / "asunciones_test_expediente.md").write_text("# AT\n", encoding="utf-8")
        gc = GateChecker(exp, test_mode=False)
        issues = gc.check_test_mode_conditions("1")
        at_file_issues = [i for i in issues if i.code == "AT_FILE_PRESENT"]
        self.assertEqual(len(at_file_issues), 1)
        self.assertEqual(at_file_issues[0].severity, "ERROR")


# ---------------------------------------------------------------------------
# Tests de check_blocking_log_errors
# ---------------------------------------------------------------------------

class TestBlockingLogErrors(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_issue_when_no_log(self):
        """Sin log → sin issue de log bloqueante."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_blocking_log_errors()
        self.assertEqual(len(issues), 0)

    def test_no_issue_when_log_has_only_ok_events(self):
        """Log con solo eventos OK → sin issue bloqueante."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        gc = GateChecker(exp)
        issues = gc.check_blocking_log_errors()
        self.assertEqual(len(issues), 0)

    def test_error_when_log_has_blocking_event(self):
        """Log con evento BLOCKED → ERROR en check_blocking_log_errors."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.block_phase("1", "gap ALTA pendiente de resolución")
        gc = GateChecker(exp)
        issues = gc.check_blocking_log_errors()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ERROR")
        self.assertEqual(issues[0].code, "LOG_BLOCKING_ERRORS")


# ---------------------------------------------------------------------------
# Tests de check_previous_phase_completed
# ---------------------------------------------------------------------------

class TestPreviousPhaseCompleted(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase1_no_prerequisite(self):
        """Fase 1 no tiene fase previa — sin issues de precedencia."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        issues = gc.check_previous_phase_completed("1")
        self.assertEqual(len(issues), 0)

    def test_phase2_warning_when_no_orchestrator_state_in_test_mode(self):
        """Fase 2 sin orchestrator_state.json → WARNING en test_mode."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp, test_mode=True)
        issues = gc.check_previous_phase_completed("2")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "WARNING")
        self.assertEqual(issues[0].code, "ORCHESTRATOR_STATE_MISSING")

    def test_phase2_error_when_no_orchestrator_state_in_prod(self):
        """Fase 2 sin orchestrator_state.json → ERROR en prod."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp, test_mode=False)
        issues = gc.check_previous_phase_completed("2")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "ERROR")

    def test_phase2_no_issue_when_phase1_completed(self):
        """Fase 2 sin issue cuando orquestador tiene fase 1 COMPLETED."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        orch.complete_phase("1")
        gc = GateChecker(exp)
        issues = gc.check_previous_phase_completed("2")
        self.assertEqual(len(issues), 0)

    def test_phase2_error_when_phase1_not_completed(self):
        """Fase 2 → ERROR cuando fase 1 está IN_PROGRESS en el orquestador."""
        exp = _make_exp(self.tmp_path)
        orch = EIAOrchestrator(exp)
        orch.start_phase("1")
        gc = GateChecker(exp)
        issues = gc.check_previous_phase_completed("2")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "PREV_PHASE_NOT_COMPLETED")


# ---------------------------------------------------------------------------
# Tests de check_phase (integración)
# ---------------------------------------------------------------------------

class TestCheckPhase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_phase_returns_gate_result(self):
        """check_phase devuelve un GateResult."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        result = gc.check_phase("1")
        self.assertIsInstance(result, GateResult)

    def test_check_phase_blocked_on_empty_expediente(self):
        """check_phase en expediente vacío devuelve is_blocked=True."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        result = gc.check_phase("1")
        self.assertTrue(result.is_blocked())

    def test_check_phase_result_contains_expediente_path(self):
        """check_phase incluye expediente_path en el resultado."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp)
        result = gc.check_phase("1")
        self.assertEqual(result.expediente_path.resolve(), exp.resolve())

    def test_check_phase_result_reflects_test_mode(self):
        """check_phase refleja test_mode en GateResult."""
        exp = _make_exp(self.tmp_path)
        gc = GateChecker(exp, test_mode=False)
        result = gc.check_phase("1")
        self.assertFalse(result.test_mode)

    def test_summary_returns_useful_string(self):
        """summary() devuelve texto con datos del expediente y resultado."""
        exp = _make_exp(self.tmp_path)
        _setup_minimal_capas(exp)
        gc = GateChecker(exp)
        result = gc.check_phase("1")
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 20)
        self.assertIn(exp.name, s)


# ---------------------------------------------------------------------------
# Tests contra expedientes reales (solo lectura)
# ---------------------------------------------------------------------------

class TestRealExpedientes(unittest.TestCase):
    """Pruebas de solo lectura contra los expedientes piloto.

    No modifican ningún archivo. Verifican comportamiento esperado
    según el estado conocido de cada expediente.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # -- NAVE-222 --

    def test_nave222_phase1_no_schema_errors(self):
        """NAVE-222: check_model_schema no produce errores (NL-01 validado)."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_model_schema()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0, f"Errores inesperados: {errors}")

    def test_nave222_phase1_has_capas(self):
        """NAVE-222: check_required_files("1") sin errores de capas ausentes."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_required_files("1")
        layer_errors = [i for i in issues if i.code == "LAYER_MISSING"]
        self.assertEqual(len(layer_errors), 0)

    def test_nave222_phase4_has_provisional_warning(self):
        """NAVE-222: fase 4 emite WARNING por cartografía PROVISIONAL en test_mode."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_required_files("4")
        provisional = [i for i in issues if i.code == "CARTOGRAFIA_PROVISIONAL"]
        self.assertGreater(len(provisional), 0, "Se esperaba issue PROVISIONAL en NAVE-222")
        self.assertEqual(provisional[0].severity, "WARNING")

    def test_nave222_phase4_has_provisional_error_in_prod(self):
        """NAVE-222: fase 4 emite ERROR por cartografía PROVISIONAL en prod mode."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=False)
        issues = gc.check_required_files("4")
        provisional = [i for i in issues if i.code == "CARTOGRAFIA_PROVISIONAL"]
        self.assertGreater(len(provisional), 0)
        self.assertEqual(provisional[0].severity, "ERROR")

    def test_nave222_phase7_all_blocks_present(self):
        """NAVE-222: fase 7 sin errores de bloques ausentes."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_required_files("7")
        bloque_errors = [i for i in issues if i.code == "BLOQUE_MISSING"]
        self.assertEqual(len(bloque_errors), 0)

    def test_nave222_phase9_missing_audit(self):
        """NAVE-222: fase 9 → AUDITORIA_MISSING (NAVE-222 no tiene informe M-12)."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_required_files("9")
        codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("AUDITORIA_MISSING", codes)

    def test_nave222_has_at_conditions(self):
        """NAVE-222: check_test_mode_conditions detecta asunciones AT."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        gc = GateChecker(_NAVE222, test_mode=True)
        issues = gc.check_test_mode_conditions("1")
        at_issues = [i for i in issues if i.code in ("AT_EN_HECHOS", "AT_FILE_PRESENT")]
        self.assertGreater(len(at_issues), 0, "NAVE-222 debe tener AT detectados")

    def test_nave222_not_modified(self):
        """NAVE-222: el gate checker no modifica ningún archivo del expediente."""
        if not _NAVE222.exists():
            self.skipTest("Expediente NAVE-222 no disponible")
        before = {f: f.stat().st_mtime for f in _NAVE222.rglob("*") if f.is_file()}
        gc = GateChecker(_NAVE222, test_mode=True)
        gc.check_phase("1")
        gc.check_phase("4")
        gc.check_phase("7")
        for path, mtime in before.items():
            with self.subTest(file=str(path.relative_to(_NAVE222))):
                self.assertEqual(path.stat().st_mtime, mtime,
                                 f"Archivo modificado: {path}")

    # -- PARCELA --

    def test_parcela_phase9_has_audit_report(self):
        """PARCELA: fase 9 detecta informe_auditoria_final.md con conclusión."""
        if not _PARCELA.exists():
            self.skipTest("Expediente PARCELA no disponible")
        gc = GateChecker(_PARCELA, test_mode=True)
        issues = gc.check_required_files("9")
        audit_errors = [i for i in issues if i.code == "AUDITORIA_MISSING"]
        self.assertEqual(len(audit_errors), 0, "PARCELA tiene informe de auditoría")

    def test_parcela_phase6_accepts_alias_names(self):
        """PARCELA: fase 6 pasa con nombres de archivo alias (identificacion_valoracion_impactos.json)."""
        if not _PARCELA.exists():
            self.skipTest("Expediente PARCELA no disponible")
        gc = GateChecker(_PARCELA, test_mode=True)
        issues = gc.check_required_files("6")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0, f"Errores inesperados en PARCELA fase 6: {errors}")

    def test_parcela_phase7_all_blocks_present(self):
        """PARCELA: fase 7 sin errores de bloques ausentes."""
        if not _PARCELA.exists():
            self.skipTest("Expediente PARCELA no disponible")
        gc = GateChecker(_PARCELA, test_mode=True)
        issues = gc.check_required_files("7")
        bloque_errors = [i for i in issues if i.code == "BLOQUE_MISSING"]
        self.assertEqual(len(bloque_errors), 0)

    def test_parcela_not_modified(self):
        """PARCELA: el gate checker no modifica ningún archivo del expediente."""
        if not _PARCELA.exists():
            self.skipTest("Expediente PARCELA no disponible")
        before = {f: f.stat().st_mtime for f in _PARCELA.rglob("*") if f.is_file()}
        gc = GateChecker(_PARCELA, test_mode=True)
        gc.check_phase("1")
        gc.check_phase("6")
        gc.check_phase("9")
        for path, mtime in before.items():
            with self.subTest(file=str(path.relative_to(_PARCELA))):
                self.assertEqual(path.stat().st_mtime, mtime,
                                 f"Archivo modificado: {path}")


if __name__ == "__main__":
    unittest.main()
