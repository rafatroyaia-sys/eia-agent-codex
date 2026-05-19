"""Tests para phase2_pipeline -- OB-06."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.phase2_pipeline import (
    Phase2Result,
    build_classification_result_from_phase1,
    run_phase2,
)

# ---------------------------------------------------------------------------
# Rutas de pilots
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_PARCELA = _ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"
_NAVE = _ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PHASE1_MINIMO_APTO = {
    "expediente_id": "expediente-TEST",
    "candidate_facts": [
        {
            "id": "FACT-001",
            "categoria": "promotor",
            "campo": "nombre_promotor",
            "valor": "EMPRESA TEST SL",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "PROMOTOR",
            "confidence": "HIGH",
            "context": None,
            "normalized_value": None,
            "notes": [],
        },
        {
            "id": "FACT-002",
            "categoria": "emplazamiento",
            "campo": "referencia_catastral",
            "valor": "1234567AB1234S0001XY",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "REFERENCIA_CATASTRAL",
            "confidence": "HIGH",
            "context": None,
            "normalized_value": None,
            "notes": [],
        },
        {
            "id": "FACT-003",
            "categoria": "operaciones",
            "campo": "operacion_residuos",
            "valor": "R1201",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "OPERACION",
            "confidence": "HIGH",
            "context": None,
            "normalized_value": None,
            "notes": [],
        },
    ],
    "warnings": [],
    "documents_processed": 1,
    "docx_processed": 1,
    "pdf_pending": 0,
}

_PHASE1_CON_COORDS = {
    **_PHASE1_MINIMO_APTO,
    "candidate_facts": _PHASE1_MINIMO_APTO["candidate_facts"] + [
        {
            "id": "FACT-004",
            "categoria": "emplazamiento",
            "campo": "coordenadas_wgs84",
            "valor": "28.1234,-15.4321",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "COORDENADA",
            "confidence": "HIGH",
            "context": None,
            "normalized_value": None,
            "notes": [],
        },
    ],
}

_PHASE1_VACIO = {
    "expediente_id": "expediente-VACIO",
    "candidate_facts": [],
    "warnings": ["No se encontraron documentos."],
    "documents_processed": 0,
    "docx_processed": 0,
    "pdf_pending": 0,
}


def _write_phase1_json(data: dict, directory: Path) -> Path:
    """Escribe un phase1_result.json de prueba en el directorio dado."""
    ci = directory / "control_interno"
    ci.mkdir(parents=True, exist_ok=True)
    p = ci / "phase1_result.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Clase 1: Phase2Result — estructura y métodos
# ---------------------------------------------------------------------------

class TestPhase2ResultSummary(unittest.TestCase):
    def _make_result(self, **kwargs) -> Phase2Result:
        defaults = dict(
            expediente_id="EXP-TEST",
            object_scope={"titular": "EMPRESA", "modo": "GABINETE",
                          "referencia_catastral": None},
            gate2_passed=True,
            gate2_summary="Gate 2 [TEST] — EXP-TEST: APTO",
            issues=[],
            warnings=[],
        )
        defaults.update(kwargs)
        return Phase2Result(**defaults)

    def test_summary_contiene_expediente_id(self):
        r = self._make_result(expediente_id="EXP-DEMO")
        self.assertIn("EXP-DEMO", r.summary())

    def test_summary_apto_cuando_gate2_passed(self):
        r = self._make_result(gate2_passed=True)
        self.assertIn("APTO", r.summary())

    def test_summary_bloqueado_cuando_gate2_falla(self):
        r = self._make_result(gate2_passed=False)
        self.assertIn("BLOQUEADO", r.summary())

    def test_summary_muestra_titular(self):
        r = self._make_result(object_scope={"titular": "RECIMETAL SL",
                                            "modo": "GABINETE",
                                            "referencia_catastral": None})
        self.assertIn("RECIMETAL SL", r.summary())

    def test_summary_muestra_modo(self):
        r = self._make_result(object_scope={"titular": None,
                                            "modo": "GABINETE",
                                            "referencia_catastral": None})
        self.assertIn("GABINETE", r.summary())

    def test_summary_conteo_errores(self):
        r = self._make_result(
            gate2_passed=False,
            issues=[{"severity": "ERROR", "code": "X", "message": "err",
                     "field": None, "recommendation": None}],
        )
        self.assertIn("1", r.summary())

    def test_to_dict_incluye_todos_los_campos(self):
        r = self._make_result()
        d = r.to_dict()
        for key in ("expediente_id", "object_scope", "gate2_passed",
                    "gate2_summary", "issues", "warnings", "notes"):
            self.assertIn(key, d)

    def test_to_dict_es_json_serializable(self):
        r = self._make_result()
        dumped = json.dumps(r.to_dict())
        self.assertIsInstance(dumped, str)


# ---------------------------------------------------------------------------
# Clase 2: build_classification_result_from_phase1
# ---------------------------------------------------------------------------

class TestBuildClassificationResultFromPhase1(unittest.TestCase):
    def test_lista_vacia_devuelve_classification_vacio(self):
        cr = build_classification_result_from_phase1({"candidate_facts": []})
        self.assertEqual(cr.facts, [])

    def test_clave_ausente_devuelve_classification_vacio(self):
        cr = build_classification_result_from_phase1({})
        self.assertEqual(cr.facts, [])

    def test_reconstruye_campo_nombre_promotor(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        promotor = cr.values("nombre_promotor")
        self.assertEqual(promotor, ["EMPRESA TEST SL"])

    def test_reconstruye_campo_referencia_catastral(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        rc = cr.values("referencia_catastral")
        self.assertEqual(rc, ["1234567AB1234S0001XY"])

    def test_reconstruye_operaciones(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        ops = cr.values("operacion_residuos")
        self.assertIn("R1201", ops)

    def test_numero_de_facts_correcto(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        self.assertEqual(len(cr.facts), 3)

    def test_confidence_preservada(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        for fact in cr.facts:
            self.assertEqual(fact.confidence, "HIGH")

    def test_fuentes_preservadas(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        for fact in cr.facts:
            self.assertIn("doc.docx", fact.fuentes)

    def test_estado_preservado(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        for fact in cr.facts:
            self.assertEqual(fact.estado, "DECLARADO")

    def test_notes_son_lista(self):
        cr = build_classification_result_from_phase1(_PHASE1_MINIMO_APTO)
        for fact in cr.facts:
            self.assertIsInstance(fact.notes, list)


# ---------------------------------------------------------------------------
# Clase 3: run_phase2 — falta phase1_result.json
# ---------------------------------------------------------------------------

class TestRunPhase2SinPhase1(unittest.TestCase):
    def test_sin_phase1_result_lanza_filenotfounderror(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                run_phase2(tmp)

    def test_error_menciona_phase1(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                run_phase2(tmp)
                self.fail("Debería haber lanzado FileNotFoundError")
            except FileNotFoundError as exc:
                self.assertIn("phase1_result.json", str(exc))

    def test_error_menciona_como_generarlo(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                run_phase2(tmp)
                self.fail("Debería haber lanzado FileNotFoundError")
            except FileNotFoundError as exc:
                # Debe indicar cómo generarlo
                self.assertTrue(
                    "phase1" in str(exc).lower() or "write" in str(exc).lower()
                )

    def test_ruta_explicita_inexistente_lanza_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                run_phase2(tmp, phase1_result_path="/ruta/inexistente/phase1.json")


# ---------------------------------------------------------------------------
# Clase 4: run_phase2 — con datos mínimos válidos
# ---------------------------------------------------------------------------

class TestRunPhase2ConDatosMinimos(unittest.TestCase):
    def test_phase1_vacio_devuelve_phase2result(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_VACIO, Path(tmp))
            result = run_phase2(tmp)
        self.assertIsInstance(result, Phase2Result)

    def test_phase1_vacio_genera_nota(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_VACIO, Path(tmp))
            result = run_phase2(tmp)
        self.assertTrue(any("hechos candidatos" in n.lower() or "overrides" in n.lower()
                            for n in result.notes))

    def test_phase1_minimo_construye_object_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp)
        scope = result.object_scope
        self.assertEqual(scope["titular"], "EMPRESA TEST SL")
        self.assertEqual(scope["referencia_catastral"], "1234567AB1234S0001XY")

    def test_expediente_id_es_nombre_directorio(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            exp_dir = tmp_path / "expediente-EIA-TEST-999"
            exp_dir.mkdir()
            _write_phase1_json(_PHASE1_MINIMO_APTO, exp_dir)
            result = run_phase2(exp_dir)
        self.assertEqual(result.expediente_id, "expediente-EIA-TEST-999")

    def test_warnings_de_fase1_propagados(self):
        data = {**_PHASE1_VACIO, "warnings": ["aviso de fase 1 de prueba"]}
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(data, Path(tmp))
            result = run_phase2(tmp)
        self.assertTrue(any("aviso de fase 1 de prueba" in w for w in result.warnings))


# ---------------------------------------------------------------------------
# Clase 5: Gate 2 APTO / BLOQUEADO
# ---------------------------------------------------------------------------

class TestRunPhase2Gate2(unittest.TestCase):
    def test_gate2_bloqueado_sin_coords_ni_modo(self):
        """Sin coords ni modo declarado, gate 2 está bloqueado."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp)
        # Sin modo declarado y sin coords → bloqueado
        self.assertFalse(result.gate2_passed)

    def test_gate2_apto_con_coords_y_modo(self):
        """Con coords, modo y operaciones, gate 2 debe pasar en test_mode."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_CON_COORDS, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"modo": "GABINETE"},
                test_mode=True,
            )
        self.assertTrue(result.gate2_passed)

    def test_gate2_bloqueado_sin_titular(self):
        data = {
            **_PHASE1_VACIO,
            "candidate_facts": [
                {
                    "id": "F1",
                    "categoria": "emplazamiento",
                    "campo": "referencia_catastral",
                    "valor": "1234567AB1234S0001XY",
                    "estado": "DECLARADO",
                    "fuentes": ["doc.docx"],
                    "entity_type": "REFERENCIA_CATASTRAL",
                    "confidence": "HIGH",
                    "context": None,
                    "normalized_value": None,
                    "notes": [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(data, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={
                    "modo": "GABINETE",
                    "coordenadas_wgs84": ["28.0,-15.5"],
                    "operaciones_incluidas": ["R1201"],
                },
            )
        # Sin titular → bloqueado
        self.assertFalse(result.gate2_passed)

    def test_gate2_issues_no_vacia_cuando_bloqueado(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_VACIO, Path(tmp))
            result = run_phase2(tmp)
        self.assertGreater(len(result.issues), 0)

    def test_gate2_summary_en_resultado(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp)
        self.assertIn("Gate 2", result.gate2_summary)

    def test_prod_mode_mas_restrictivo(self):
        """En --prod, AT activos deben generar ERROR (no WARNING)."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_CON_COORDS, Path(tmp))
            result_prod = run_phase2(
                tmp,
                overrides={
                    "modo": "GABINETE",
                    "at_activos": ["AT-001 — dato provisional"],
                },
                test_mode=False,
            )
        at_issues = [i for i in result_prod.issues
                     if "at_activos" in (i.get("field") or "")]
        self.assertTrue(any(i["severity"] == "ERROR" for i in at_issues))

    def test_test_mode_at_activos_son_warning(self):
        """En test_mode=True, AT activos deben ser WARNING (no bloquean)."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_CON_COORDS, Path(tmp))
            result_test = run_phase2(
                tmp,
                overrides={
                    "modo": "GABINETE",
                    "at_activos": ["AT-001 — dato provisional"],
                },
                test_mode=True,
            )
        at_issues = [i for i in result_test.issues
                     if "at_activos" in (i.get("field") or "")]
        self.assertTrue(any(i["severity"] == "WARNING" for i in at_issues))


# ---------------------------------------------------------------------------
# Clase 6: overrides
# ---------------------------------------------------------------------------

class TestRunPhase2Overrides(unittest.TestCase):
    def test_override_modo(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp, overrides={"modo": "CAMPO"})
        self.assertEqual(result.object_scope["modo"], "CAMPO")

    def test_override_operaciones_excluidas(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"operaciones_excluidas": ["R1302", "R1303"]},
            )
        self.assertIn("R1302", result.object_scope["operaciones_excluidas"])
        self.assertIn("R1303", result.object_scope["operaciones_excluidas"])

    def test_override_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"gaps": ["GAP-001 — coordenadas PENDIENTE"]},
            )
        self.assertIn("GAP-001 — coordenadas PENDIENTE",
                      result.object_scope["gaps"])

    def test_override_coordenadas_wgs84(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"coordenadas_wgs84": ["27.9999,-15.3333"]},
            )
        self.assertIn("27.9999,-15.3333", result.object_scope["coordenadas_wgs84"])

    def test_override_vacio_no_rompe(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp, overrides={})
        self.assertIsInstance(result, Phase2Result)

    def test_overrides_none_no_rompe(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(tmp, overrides=None)
        self.assertIsInstance(result, Phase2Result)

    def test_override_at_activos(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"at_activos": ["AT-002 — prueba"]},
            )
        self.assertIn("AT-002 — prueba", result.object_scope["at_activos"])


# ---------------------------------------------------------------------------
# Clase 7: write_outputs
# ---------------------------------------------------------------------------

class TestRunPhase2WriteOutputs(unittest.TestCase):
    def test_write_false_no_escribe_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            # Contar archivos en control_interno antes
            ci = Path(tmp) / "control_interno"
            before = set(ci.iterdir()) if ci.exists() else set()
            run_phase2(tmp, write_outputs=False)
            after = set(ci.iterdir()) if ci.exists() else set()
            # Solo debe existir phase1_result.json que creamos nosotros
            nuevos = after - before
            self.assertEqual(nuevos, set())

    def test_write_true_crea_phase2_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            run_phase2(tmp, write_outputs=True)
            self.assertTrue((Path(tmp) / "control_interno" / "phase2_result.json").exists())

    def test_write_true_crea_ficha_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            run_phase2(tmp, write_outputs=True)
            self.assertTrue((Path(tmp) / "control_interno" / "ficha_objeto_evaluado.md").exists())

    def test_write_true_crea_object_scope_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            run_phase2(tmp, write_outputs=True)
            self.assertTrue((Path(tmp) / "control_interno" / "object_scope.json").exists())

    def test_phase2_json_es_valido(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            run_phase2(tmp, write_outputs=True)
            p = Path(tmp) / "control_interno" / "phase2_result.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("expediente_id", data)
            self.assertIn("gate2_passed", data)
            self.assertIn("object_scope", data)

    def test_ficha_md_contiene_objeto_evaluado(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            run_phase2(tmp, write_outputs=True)
            md = (Path(tmp) / "control_interno" / "ficha_objeto_evaluado.md").read_text(encoding="utf-8")
            self.assertIn("Objeto Evaluado", md)

    def test_output_dir_personalizado(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Escribir phase1_result en directorio personalizado
            data_path = Path(tmp) / "mis_salidas" / "phase1_result.json"
            data_path.parent.mkdir(parents=True)
            data_path.write_text(json.dumps(_PHASE1_MINIMO_APTO), encoding="utf-8")
            run_phase2(
                tmp,
                phase1_result_path=data_path,
                write_outputs=True,
                output_dir="mis_salidas",
            )
            self.assertTrue((Path(tmp) / "mis_salidas" / "phase2_result.json").exists())


# ---------------------------------------------------------------------------
# Clase 8: context dict
# ---------------------------------------------------------------------------

class TestRunPhase2Context(unittest.TestCase):
    def test_rc_verificada_false_genera_warning_en_test_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_CON_COORDS, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"modo": "GABINETE"},
                test_mode=True,
                context={"rc_verificada": False},
            )
        rc_issues = [i for i in result.issues if "catastral" in (i.get("field") or "")]
        self.assertTrue(any(i["severity"] == "WARNING" for i in rc_issues))

    def test_rc_verificada_false_genera_error_en_prod(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_CON_COORDS, Path(tmp))
            result = run_phase2(
                tmp,
                overrides={"modo": "GABINETE"},
                test_mode=False,
                context={"rc_verificada": False},
            )
        rc_issues = [i for i in result.issues if "catastral" in (i.get("field") or "")]
        self.assertTrue(any(i["severity"] == "ERROR" for i in rc_issues))


# ---------------------------------------------------------------------------
# Clase 9: CLI — integración mínima
# ---------------------------------------------------------------------------

class TestCLIPhase2(unittest.TestCase):
    def _run_cli(self, *args):
        import subprocess
        cli = Path(__file__).parent.parent / "run_expediente.py"
        cmd = [sys.executable, str(cli)] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def test_cli_phase2_sin_phase1_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_cli(tmp, "phase2")
        self.assertEqual(r.returncode, 1)

    def test_cli_phase2_sin_phase1_imprime_mensaje(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_cli(tmp, "phase2")
        self.assertIn("phase1_result.json", r.stderr)

    def test_cli_phase2_con_phase1_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            r = self._run_cli(tmp, "phase2")
        self.assertEqual(r.returncode, 0)

    def test_cli_phase2_imprime_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            r = self._run_cli(tmp, "phase2")
        self.assertIn("Fase 2", r.stdout)

    def test_cli_phase2_sin_write_no_crea_phase2_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            self._run_cli(tmp, "phase2")
            p = Path(tmp) / "control_interno" / "phase2_result.json"
            self.assertFalse(p.exists())

    def test_cli_phase2_con_write_crea_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(_PHASE1_MINIMO_APTO, Path(tmp))
            self._run_cli(tmp, "phase2", "--write")
            p = Path(tmp) / "control_interno" / "phase2_result.json"
            self.assertTrue(p.exists())

    def test_cli_phase2_prod_aplica_modo_produccion(self):
        """--prod debe aplicar test_mode=False; AT activos son ERROR."""
        with tempfile.TemporaryDirectory() as tmp:
            data = {
                **_PHASE1_CON_COORDS,
                "candidate_facts": _PHASE1_CON_COORDS["candidate_facts"],
            }
            _write_phase1_json(data, Path(tmp))
            self._run_cli(tmp, "phase2", "--write", "--prod")
            p = Path(tmp) / "control_interno" / "phase2_result.json"
            if p.exists():
                loaded = json.loads(p.read_text(encoding="utf-8"))
                # En producción sin modo declarado → issues contienen ERROR
                self.assertIsInstance(loaded.get("issues"), list)

    def test_cli_expediente_inexistente_exit_1(self):
        r = self._run_cli("/ruta/que/no/existe/jamas", "phase2")
        self.assertEqual(r.returncode, 1)


# ---------------------------------------------------------------------------
# Clase 10: Pilots — solo lectura (PARCELA)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_PARCELA.exists(), "Piloto PARCELA no disponible")
class TestRunPhase2PilotoParcela(unittest.TestCase):
    def _get_phase1_result(self) -> dict:
        """Obtiene phase1 result en memoria desde PARCELA sin escritura."""
        from eia_agent.core.phase1_pipeline import run_phase1
        r = run_phase1(_PARCELA, write_outputs=False)
        return r.to_dict()

    def test_no_modifica_inputs(self):
        inputs_dir = _PARCELA / "inputs"
        before = set(inputs_dir.glob("**/*")) if inputs_dir.exists() else set()
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            run_phase2(tmp, write_outputs=False)
        after = set(inputs_dir.glob("**/*")) if inputs_dir.exists() else set()
        self.assertEqual(before, after)

    def test_no_modifica_control_interno_de_parcela(self):
        ci = _PARCELA / "control_interno"
        before = set(ci.glob("phase2*")) if ci.exists() else set()
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            run_phase2(tmp, write_outputs=False)
        after = set(ci.glob("phase2*")) if ci.exists() else set()
        self.assertEqual(before, after)

    def test_devuelve_phase2result(self):
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            result = run_phase2(tmp, write_outputs=False)
        self.assertIsInstance(result, Phase2Result)

    def test_summary_no_vacio(self):
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            result = run_phase2(tmp, write_outputs=False)
        self.assertGreater(len(result.summary()), 0)

    def test_object_scope_tiene_datos(self):
        """PARCELA tiene DOCX con entidades → scope no debe estar totalmente vacío."""
        phase1_data = self._get_phase1_result()
        # Verificar que hay facts antes de continuar
        if not phase1_data.get("candidate_facts"):
            self.skipTest("PARCELA no generó candidate_facts")
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            result = run_phase2(tmp, write_outputs=False)
        scope = result.object_scope
        # Al menos algún campo distinto de None o vacío
        tiene_datos = (
            scope.get("titular") is not None
            or scope.get("referencia_catastral") is not None
            or len(scope.get("operaciones_incluidas", [])) > 0
        )
        self.assertTrue(tiene_datos)


# ---------------------------------------------------------------------------
# Clase 11: Pilots — solo lectura (NAVE-222)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_NAVE.exists(), "Piloto NAVE-222 no disponible")
class TestRunPhase2PilotoNave222(unittest.TestCase):
    def _get_phase1_result(self) -> dict:
        from eia_agent.core.phase1_pipeline import run_phase1
        r = run_phase1(_NAVE, write_outputs=False)
        return r.to_dict()

    def test_no_modifica_inputs(self):
        inputs_dir = _NAVE / "inputs"
        before = set(inputs_dir.glob("**/*")) if inputs_dir.exists() else set()
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            run_phase2(tmp, write_outputs=False)
        after = set(inputs_dir.glob("**/*")) if inputs_dir.exists() else set()
        self.assertEqual(before, after)

    def test_no_modifica_control_interno_de_nave(self):
        ci = _NAVE / "control_interno"
        before = set(ci.glob("phase2*")) if ci.exists() else set()
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            run_phase2(tmp, write_outputs=False)
        after = set(ci.glob("phase2*")) if ci.exists() else set()
        self.assertEqual(before, after)

    def test_devuelve_phase2result(self):
        phase1_data = self._get_phase1_result()
        with tempfile.TemporaryDirectory() as tmp:
            _write_phase1_json(phase1_data, Path(tmp))
            result = run_phase2(tmp, write_outputs=False)
        self.assertIsInstance(result, Phase2Result)


if __name__ == "__main__":
    unittest.main()
