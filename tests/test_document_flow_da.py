"""
tests/test_document_flow_da.py
Tests DA-01 — Flujo completo de Documento Ambiental para expediente cliente.

Cubre:
  1. DAFlowStep — to_dict, is_ok, is_warning, is_failed
  2. DAEstadoItem — to_dict, categorias
  3. DAFlowResult — is_complete, has_blocking, count_by_categoria, summary, to_dict
  4. _determine_resultado_flujo — FLUJO_COMPLETO, CERRADO_CON_PENDIENTES, BLOQUEADO
  5. build_da_flow_estado_markdown — secciones, disclaimer, tablas
  6. write_da_flow_outputs — escribe JSON + MD
  7. run_da_flow — expediente vacio (todos los pasos manejan gracefully)
  8. run_da_flow — expediente con minimos (pasos ejecutan y producen estado)
  9. CLI cliente-da — exit codes, --write, --prod
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.document_flow_da import (
    DAFlowStep,
    DAEstadoItem,
    DAFlowResult,
    DISCLAIMER_DA,
    _determine_resultado_flujo,
    _safe_load_json,
    build_da_flow_estado_markdown,
    write_da_flow_outputs,
    run_da_flow,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(step_id="S1", status="OK", message="ok", warnings=None, errors=None):
    return DAFlowStep(
        step_id=step_id,
        name=f"Paso {step_id}",
        status=status,
        message=message,
        warnings=warnings or [],
        errors=errors or [],
    )


def _make_item(categoria="CERRADO", item="Item A", fuente="test", valor="OK", accion=""):
    return DAEstadoItem(categoria=categoria, item=item, fuente=fuente, valor=valor, accion=accion)


def _make_result(resultado_flujo="FLUJO_COMPLETO", steps=None, cerrado=None,
                 pendiente=None, bloqueante=None):
    return DAFlowResult(
        expediente_id="TEST-EXP",
        administrative_ready=False,
        resultado_flujo=resultado_flujo,
        steps=steps or [_make_step()],
        estado_cerrado=cerrado or [_make_item("CERRADO")],
        estado_pendiente=pendiente or [],
        estado_bloqueante=bloqueante or [],
    )


# ---------------------------------------------------------------------------
# 1. DAFlowStep
# ---------------------------------------------------------------------------

class TestDAFlowStep(unittest.TestCase):

    def test_is_ok_when_ok(self):
        s = _make_step(status="OK")
        self.assertTrue(s.is_ok())

    def test_is_ok_when_warning(self):
        s = _make_step(status="WARNING")
        self.assertTrue(s.is_ok())

    def test_is_not_ok_when_failed(self):
        s = _make_step(status="FAILED")
        self.assertFalse(s.is_ok())

    def test_is_not_ok_when_skipped(self):
        s = _make_step(status="SKIPPED")
        self.assertFalse(s.is_ok())

    def test_is_warning(self):
        s = _make_step(status="WARNING")
        self.assertTrue(s.is_warning())
        self.assertFalse(_make_step(status="OK").is_warning())

    def test_is_failed_when_failed(self):
        self.assertTrue(_make_step(status="FAILED").is_failed())

    def test_is_failed_when_skipped(self):
        self.assertTrue(_make_step(status="SKIPPED").is_failed())

    def test_is_not_failed_when_ok(self):
        self.assertFalse(_make_step(status="OK").is_failed())

    def test_to_dict_keys(self):
        s = _make_step(step_id="PIPE", status="OK", message="msg",
                       warnings=["w1"], errors=[])
        d = s.to_dict()
        self.assertIn("step_id", d)
        self.assertIn("name", d)
        self.assertIn("status", d)
        self.assertIn("message", d)
        self.assertIn("output_files", d)
        self.assertIn("warnings", d)
        self.assertIn("errors", d)

    def test_to_dict_values(self):
        s = _make_step(step_id="PIPE", status="WARNING", message="m",
                       warnings=["w"], errors=["e"])
        d = s.to_dict()
        self.assertEqual(d["step_id"], "PIPE")
        self.assertEqual(d["status"], "WARNING")
        self.assertEqual(d["warnings"], ["w"])
        self.assertEqual(d["errors"], ["e"])

    def test_default_output_files_empty(self):
        s = _make_step()
        self.assertEqual(s.output_files, [])


# ---------------------------------------------------------------------------
# 2. DAEstadoItem
# ---------------------------------------------------------------------------

class TestDAEstadoItem(unittest.TestCase):

    def test_to_dict_cerrado(self):
        it = _make_item("CERRADO", "Bloque A", "manifest", "READY")
        d = it.to_dict()
        self.assertEqual(d["categoria"], "CERRADO")
        self.assertEqual(d["item"], "Bloque A")
        self.assertEqual(d["valor"], "READY")
        self.assertNotIn("accion", d)

    def test_to_dict_pendiente_con_accion(self):
        it = _make_item("PENDIENTE", "Bloque G", "manifest", "PARTIAL", "Revisar fuentes")
        d = it.to_dict()
        self.assertEqual(d["categoria"], "PENDIENTE")
        self.assertEqual(d["accion"], "Revisar fuentes")

    def test_to_dict_bloqueante(self):
        it = _make_item("BLOQUEANTE", "Bloque K", "manifest", "MISSING", "Falta input")
        d = it.to_dict()
        self.assertEqual(d["categoria"], "BLOQUEANTE")
        self.assertIn("accion", d)

    def test_accion_omitted_when_empty(self):
        it = _make_item("CERRADO", "Item", "test", "OK", "")
        d = it.to_dict()
        self.assertNotIn("accion", d)

    def test_accion_included_when_set(self):
        it = _make_item("PENDIENTE", "Item", "test", "W", "hacer algo")
        d = it.to_dict()
        self.assertIn("accion", d)
        self.assertEqual(d["accion"], "hacer algo")

    def test_fuente_preserved(self):
        it = _make_item(fuente="final_audit_result")
        self.assertEqual(it.to_dict()["fuente"], "final_audit_result")


# ---------------------------------------------------------------------------
# 3. DAFlowResult
# ---------------------------------------------------------------------------

class TestDAFlowResult(unittest.TestCase):

    def test_is_complete_flujo_completo(self):
        r = _make_result("FLUJO_COMPLETO")
        self.assertTrue(r.is_complete())

    def test_is_not_complete_con_pendientes(self):
        r = _make_result("CERRADO_CON_PENDIENTES")
        self.assertFalse(r.is_complete())

    def test_is_not_complete_bloqueado(self):
        r = _make_result("BLOQUEADO")
        self.assertFalse(r.is_complete())

    def test_has_blocking_true(self):
        r = _make_result(bloqueante=[_make_item("BLOQUEANTE")])
        self.assertTrue(r.has_blocking())

    def test_has_blocking_false(self):
        r = _make_result(bloqueante=[])
        self.assertFalse(r.has_blocking())

    def test_count_by_categoria(self):
        r = _make_result(
            cerrado=[_make_item("CERRADO"), _make_item("CERRADO")],
            pendiente=[_make_item("PENDIENTE")],
            bloqueante=[],
        )
        counts = r.count_by_categoria()
        self.assertEqual(counts["CERRADO"], 2)
        self.assertEqual(counts["PENDIENTE"], 1)
        self.assertEqual(counts["BLOQUEANTE"], 0)

    def test_steps_ok_count(self):
        steps = [
            _make_step(status="OK"),
            _make_step(status="WARNING"),
            _make_step(status="FAILED"),
        ]
        r = _make_result(steps=steps)
        self.assertEqual(r.steps_ok(), 2)

    def test_steps_failed_count(self):
        steps = [_make_step(status="FAILED"), _make_step(status="SKIPPED")]
        r = _make_result(steps=steps)
        self.assertEqual(r.steps_failed(), 2)

    def test_administrative_ready_always_false(self):
        r = _make_result()
        self.assertFalse(r.administrative_ready)

    def test_summary_contains_expediente_id(self):
        r = _make_result()
        s = r.summary()
        self.assertIn("TEST-EXP", s)

    def test_summary_contains_resultado(self):
        r = _make_result("CERRADO_CON_PENDIENTES")
        s = r.summary()
        self.assertIn("CERRADO", s)

    def test_summary_contains_disclaimer(self):
        r = _make_result()
        s = r.summary()
        self.assertIn("NOTA:", s)
        self.assertIn("administrative_ready", s.lower())

    def test_summary_contains_counts(self):
        r = _make_result(
            cerrado=[_make_item("CERRADO"), _make_item("CERRADO")],
            pendiente=[_make_item("PENDIENTE")],
        )
        s = r.summary()
        self.assertIn("2", s)  # cerrado count
        self.assertIn("1", s)  # pendiente count

    def test_to_dict_keys(self):
        r = _make_result()
        d = r.to_dict()
        for key in ["expediente_id", "administrative_ready", "resultado_flujo",
                    "steps", "estado_cerrado", "estado_pendiente", "estado_bloqueante",
                    "counts", "disclaimer"]:
            self.assertIn(key, d)

    def test_to_dict_steps_serialized(self):
        r = _make_result(steps=[_make_step("S1", "OK"), _make_step("S2", "FAILED")])
        d = r.to_dict()
        self.assertEqual(len(d["steps"]), 2)
        self.assertEqual(d["steps"][0]["step_id"], "S1")

    def test_to_dict_disclaimer_present(self):
        r = _make_result()
        d = r.to_dict()
        self.assertIn("administrative", d["disclaimer"].lower())

    def test_to_dict_resultado_flujo_label(self):
        r = _make_result("FLUJO_COMPLETO")
        d = r.to_dict()
        self.assertIn("resultado_flujo_label", d)
        self.assertNotEqual(d["resultado_flujo_label"], "")


# ---------------------------------------------------------------------------
# 4. _determine_resultado_flujo
# ---------------------------------------------------------------------------

class TestDetermineResultadoFlujo(unittest.TestCase):

    def _call(self, cerrado=None, pendiente=None, bloqueante=None, steps=None):
        return _determine_resultado_flujo(
            cerrado or [], pendiente or [], bloqueante or [], steps or []
        )

    def test_flujo_completo_sin_pendientes(self):
        self.assertEqual(self._call(cerrado=[_make_item("CERRADO")]), "FLUJO_COMPLETO")

    def test_cerrado_con_pendientes_sin_bloqueante(self):
        result = self._call(
            cerrado=[_make_item("CERRADO")],
            pendiente=[_make_item("PENDIENTE")],
        )
        self.assertEqual(result, "CERRADO_CON_PENDIENTES")

    def test_bloqueado_con_items_bloqueantes(self):
        result = self._call(bloqueante=[_make_item("BLOQUEANTE")])
        self.assertEqual(result, "BLOQUEADO")

    def test_bloqueado_con_steps_fallidos(self):
        steps = [_make_step(status="FAILED")]
        result = self._call(steps=steps)
        self.assertEqual(result, "BLOQUEADO")

    def test_bloqueado_prioridad_sobre_pendientes(self):
        result = self._call(
            pendiente=[_make_item("PENDIENTE")],
            bloqueante=[_make_item("BLOQUEANTE")],
        )
        self.assertEqual(result, "BLOQUEADO")

    def test_flujo_completo_todos_vacios(self):
        self.assertEqual(self._call(), "FLUJO_COMPLETO")

    def test_cerrado_con_pendientes_si_solo_warnings(self):
        steps = [_make_step(status="WARNING")]
        result = self._call(pendiente=[_make_item("PENDIENTE")], steps=steps)
        self.assertEqual(result, "CERRADO_CON_PENDIENTES")


# ---------------------------------------------------------------------------
# 5. build_da_flow_estado_markdown
# ---------------------------------------------------------------------------

class TestBuildDaFlowEstadoMarkdown(unittest.TestCase):

    def setUp(self):
        self.result = _make_result(
            "CERRADO_CON_PENDIENTES",
            steps=[_make_step("S1", "OK"), _make_step("S2", "WARNING", warnings=["aviso"])],
            cerrado=[_make_item("CERRADO", "Bloque A", "manifest", "READY")],
            pendiente=[_make_item("PENDIENTE", "Bloque G", "manifest", "PARTIAL", "revisar")],
        )

    def test_contains_expediente_id(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("TEST-EXP", md)

    def test_contains_disclaimer(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn(DISCLAIMER_DA, md)

    def test_contains_cerrado_section(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("## CERRADO", md)

    def test_contains_pendiente_section(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("## PENDIENTE", md)

    def test_contains_bloqueante_section(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("## BLOQUEANTE", md)

    def test_no_administrative_ready_claim(self):
        md = build_da_flow_estado_markdown(self.result)
        md_lower = md.lower()
        # El disclaimer dice "NO declara... apto" — verificar que administrative_ready aparece
        # y que hay un marcador de negacion junto a la aptitud
        self.assertIn("administrative_ready", md_lower)
        self.assertIn("false", md_lower)
        # No debe aparecer "apto para presentacion" como afirmacion aislada en una linea
        self.assertNotIn("\napto para presentacion administrativa\n", md_lower)

    def test_contains_pasos_table(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("## Pasos ejecutados", md)

    def test_cerrado_items_in_table(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("Bloque A", md)
        self.assertIn("READY", md)

    def test_pendiente_items_in_table(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("Bloque G", md)
        self.assertIn("revisar", md)

    def test_no_bloqueante_items_shows_empty_notice(self):
        r = _make_result(bloqueante=[])
        md = build_da_flow_estado_markdown(r)
        self.assertIn("No hay items bloqueantes", md)

    def test_counts_in_headers(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("CERRADO (1 items)", md)
        self.assertIn("PENDIENTE (1 items)", md)

    def test_resultado_flujo_in_output(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIn("CERRADO", md)

    def test_resultado_is_string(self):
        md = build_da_flow_estado_markdown(self.result)
        self.assertIsInstance(md, str)
        self.assertGreater(len(md), 100)


# ---------------------------------------------------------------------------
# 6. write_da_flow_outputs
# ---------------------------------------------------------------------------

class TestWriteDaFlowOutputs(unittest.TestCase):

    def test_writes_json_and_md(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, mp = write_da_flow_outputs(result, exp_path)
            self.assertTrue(jp.exists())
            self.assertTrue(mp.exists())

    def test_json_valid(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, _ = write_da_flow_outputs(result, exp_path)
            data = json.loads(jp.read_text(encoding="utf-8"))
            self.assertIn("expediente_id", data)
            self.assertIn("administrative_ready", data)
            self.assertFalse(data["administrative_ready"])

    def test_md_contains_sections(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            _, mp = write_da_flow_outputs(result, exp_path)
            md = mp.read_text(encoding="utf-8")
            self.assertIn("## CERRADO", md)
            self.assertIn("## PENDIENTE", md)
            self.assertIn("## BLOQUEANTE", md)

    def test_creates_documento_dir(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, mp = write_da_flow_outputs(result, exp_path)
            self.assertTrue((exp_path / "documento").exists())

    def test_files_in_documento_subdir(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, mp = write_da_flow_outputs(result, exp_path)
            self.assertEqual(jp.parent.name, "documento")
            self.assertEqual(mp.parent.name, "documento")

    def test_json_has_disclaimer(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, _ = write_da_flow_outputs(result, exp_path)
            data = json.loads(jp.read_text(encoding="utf-8"))
            self.assertIn("disclaimer", data)

    def test_filenames(self):
        result = _make_result()
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, mp = write_da_flow_outputs(result, exp_path)
            self.assertEqual(jp.name, "estado_expediente_da.json")
            self.assertEqual(mp.name, "estado_expediente_da.md")

    def test_json_steps_count(self):
        result = _make_result(steps=[_make_step("S1"), _make_step("S2")])
        with tempfile.TemporaryDirectory() as tmp:
            exp_path = Path(tmp) / "expediente-TEST"
            exp_path.mkdir()
            jp, _ = write_da_flow_outputs(result, exp_path)
            data = json.loads(jp.read_text(encoding="utf-8"))
            self.assertEqual(len(data["steps"]), 2)


# ---------------------------------------------------------------------------
# 7. run_da_flow — expediente vacio
# ---------------------------------------------------------------------------

class TestRunDaFlowEmpty(unittest.TestCase):
    """run_da_flow sobre un directorio vacio — todos los pasos deben manejar gracefully."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp_path = Path(self.tmp) / "EIA-TEST-EMPTY"
        self.exp_path.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_daflowresult(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertIsInstance(result, DAFlowResult)

    def test_administrative_ready_false(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertFalse(result.administrative_ready)

    def test_expediente_id_correct(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertEqual(result.expediente_id, "EIA-TEST-EMPTY")

    def test_has_steps(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertGreater(len(result.steps), 0)

    def test_resultado_flujo_set(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertIn(result.resultado_flujo,
                      ("FLUJO_COMPLETO", "CERRADO_CON_PENDIENTES", "BLOQUEADO"))

    def test_no_exception_raised(self):
        # run_da_flow debe manejar expediente vacio sin lanzar excepciones
        try:
            run_da_flow(self.exp_path, write=False)
        except Exception as e:
            self.fail(f"run_da_flow lanzo excepcion inesperada: {e}")

    def test_pipeline_step_present(self):
        result = run_da_flow(self.exp_path, write=False)
        ids = [s.step_id for s in result.steps]
        self.assertIn("TECHNICAL_PIPELINE", ids)

    def test_document_steps_present(self):
        result = run_da_flow(self.exp_path, write=False)
        ids = [s.step_id for s in result.steps]
        self.assertIn("DOCUMENT_MANIFEST", ids)
        self.assertIn("DOCUMENT_TOC", ids)

    def test_twelve_steps_minimum(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertGreaterEqual(len(result.steps), 12)

    def test_summary_callable(self):
        result = run_da_flow(self.exp_path, write=False)
        summary = result.summary()
        self.assertIsInstance(summary, str)
        self.assertIn("EIA-TEST-EMPTY", summary)

    def test_write_outputs_on_empty(self):
        result = run_da_flow(self.exp_path, write=True)
        doc_dir = self.exp_path / "documento"
        # El directorio se crea aunque sea vacio
        jp = doc_dir / "estado_expediente_da.json"
        mp = doc_dir / "estado_expediente_da.md"
        self.assertTrue(jp.exists())
        self.assertTrue(mp.exists())

    def test_json_written_valid(self):
        run_da_flow(self.exp_path, write=True)
        jp = self.exp_path / "documento" / "estado_expediente_da.json"
        data = json.loads(jp.read_text(encoding="utf-8"))
        self.assertFalse(data["administrative_ready"])


# ---------------------------------------------------------------------------
# 8. run_da_flow — expediente con fixtures minimos
# ---------------------------------------------------------------------------

class TestRunDaFlowWithFixtures(unittest.TestCase):
    """run_da_flow con inputs minimos: bloques A-K + capas + fase4."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.exp_path = Path(self.tmp) / "EIA-TEST-FIXTURES"
        self.exp_path.mkdir()
        self._setup_fixtures()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _setup_fixtures(self):
        """Crea estructura minima que permite ejecutar el flujo parcialmente."""
        # Capas minimas
        capas = self.exp_path / "capas"
        capas.mkdir()
        hechos = [{"id": "HC-001", "categoria": "identificacion_instalacion",
                   "campo": "nombre", "valor": "Test DA-01",
                   "estado": "CONFIRMADO", "fuentes": ["DOC-001"], "nota": None}]
        (capas / "hechos_confirmados.json").write_text(
            json.dumps(hechos, ensure_ascii=False), encoding="utf-8"
        )
        (capas / "inferencias_y_gaps.json").write_text("[]", encoding="utf-8")
        (capas / "normativa_aplicable.json").write_text("[]", encoding="utf-8")
        (capas / "cartografia_trace.json").write_text("[]", encoding="utf-8")
        (capas / "matriz_trazabilidad.json").write_text("[]", encoding="utf-8")

        # Bloques A-K minimos
        bloques = self.exp_path / "bloques"
        bloques.mkdir()
        for letra in "ABCDEFGHIJK":
            (bloques / f"{letra}_bloque.md").write_text(
                f"# {letra}. Bloque de prueba DA-01\n\nContenido de prueba.\n",
                encoding="utf-8"
            )
        # Renombrar al formato canónico que usa el pipeline
        import os
        bloques_map = {
            "A": "A_identificacion_y_descripcion.md",
            "B": "B_inventario_ambiental.md",
            "C": "C_impactos.md",
            "D": "D_medidas.md",
            "E": "E_PVA.md",
            "F": "F_alternativas.md",
            "G": "G_vulnerabilidad.md",
            "H": "H_red_natura_2000.md",
            "I": "I_conclusiones.md",
            "J": "J_resumen_no_tecnico.md",
            "K": "K_referencias.md",
        }
        for letra, fname in bloques_map.items():
            src = bloques / f"{letra}_bloque.md"
            dst = bloques / fname
            if src.exists():
                src.rename(dst)

        # fase4/phase4_result.json minimo
        fase4 = self.exp_path / "fase4"
        fase4.mkdir()
        phase4_data = {
            "expediente_id": "EIA-TEST-FIXTURES",
            "precheck": {"status": "OK"},
            "climate": {
                "station": {"station_id": "C029O", "name": "Test"},
                "koppen": {"classification": "BWh", "description": "Arido seco"},
                "monthly_data": [],
            },
            "cartography_plan": {"maps": []},
            "schematic_maps": [],
            "status": "OK",
        }
        (fase4 / "phase4_result.json").write_text(
            json.dumps(phase4_data, ensure_ascii=False), encoding="utf-8"
        )

    def test_no_exception(self):
        try:
            run_da_flow(self.exp_path, write=False)
        except Exception as e:
            self.fail(f"run_da_flow con fixtures lanzo excepcion: {e}")

    def test_returns_daflowresult(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertIsInstance(result, DAFlowResult)

    def test_twelve_steps(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertEqual(len(result.steps), 12)

    def test_administrative_ready_false(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertFalse(result.administrative_ready)

    def test_resultado_flujo_is_valid_string(self):
        result = run_da_flow(self.exp_path, write=False)
        self.assertIn(result.resultado_flujo,
                      ("FLUJO_COMPLETO", "CERRADO_CON_PENDIENTES", "BLOQUEADO"))

    def test_pipeline_step_not_skipped(self):
        result = run_da_flow(self.exp_path, write=False)
        pipe = next((s for s in result.steps if s.step_id == "TECHNICAL_PIPELINE"), None)
        self.assertIsNotNone(pipe)

    def test_write_creates_estado_files(self):
        run_da_flow(self.exp_path, write=True)
        jp = self.exp_path / "documento" / "estado_expediente_da.json"
        mp = self.exp_path / "documento" / "estado_expediente_da.md"
        self.assertTrue(jp.exists(), "estado_expediente_da.json no creado")
        self.assertTrue(mp.exists(), "estado_expediente_da.md no creado")

    def test_estado_json_has_required_keys(self):
        run_da_flow(self.exp_path, write=True)
        data = json.loads(
            (self.exp_path / "documento" / "estado_expediente_da.json").read_text(encoding="utf-8")
        )
        for key in ["expediente_id", "administrative_ready", "resultado_flujo",
                    "estado_cerrado", "estado_pendiente", "estado_bloqueante", "counts"]:
            self.assertIn(key, data)

    def test_estado_md_has_sections(self):
        run_da_flow(self.exp_path, write=True)
        md = (self.exp_path / "documento" / "estado_expediente_da.md").read_text(encoding="utf-8")
        for section in ["## CERRADO", "## PENDIENTE", "## BLOQUEANTE", "## Pasos ejecutados"]:
            self.assertIn(section, md, f"Seccion '{section}' no encontrada en MD")

    def test_estado_md_has_disclaimer(self):
        run_da_flow(self.exp_path, write=True)
        md = (self.exp_path / "documento" / "estado_expediente_da.md").read_text(encoding="utf-8")
        self.assertIn("administrative_ready", md.lower())


# ---------------------------------------------------------------------------
# 9. CLI cliente-da
# ---------------------------------------------------------------------------

class TestClienteDaCLI(unittest.TestCase):

    def _run(self, argv):
        from run_expediente import main
        import io
        from unittest.mock import patch
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with patch("sys.stdout", buf_out), patch("sys.stderr", buf_err):
            code = main(argv)
        return code, buf_out.getvalue(), buf_err.getvalue()

    def test_cliente_da_inexistente_exit_1(self):
        code, _, err = self._run(["expediente-que-no-existe-da01", "cliente-da", "--write"])
        self.assertEqual(code, 1)

    def test_cliente_da_no_write_no_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST-CLI"
            exp.mkdir()
            code, out, _ = self._run([str(exp), "cliente-da"])
            # Sin --write debe ejecutarse igualmente (modo dry)
            self.assertIsInstance(code, int)

    def test_cliente_da_with_write_creates_estado(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST-CLI-WRITE"
            exp.mkdir()
            code, out, _ = self._run([str(exp), "cliente-da", "--write"])
            jp = exp / "documento" / "estado_expediente_da.json"
            mp = exp / "documento" / "estado_expediente_da.md"
            self.assertTrue(jp.exists(), "JSON no creado con --write")
            self.assertTrue(mp.exists(), "MD no creado con --write")

    def test_cli_output_contains_expediente_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-CLI-CHECK"
            exp.mkdir()
            _, out, _ = self._run([str(exp), "cliente-da"])
            self.assertIn("EIA-CLI-CHECK", out)

    def test_cli_output_contains_admin_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-CLI-ADMIN"
            exp.mkdir()
            _, out, _ = self._run([str(exp), "cliente-da"])
            self.assertIn("admin", out.lower())

    def test_cli_prod_flag_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-CLI-PROD"
            exp.mkdir()
            # No debe lanzar excepcion con --prod
            code, _, _ = self._run([str(exp), "cliente-da", "--prod"])
            self.assertIsInstance(code, int)

    def test_json_administrative_ready_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST-ADMIN"
            exp.mkdir()
            self._run([str(exp), "cliente-da", "--write"])
            jp = exp / "documento" / "estado_expediente_da.json"
            if jp.exists():
                data = json.loads(jp.read_text(encoding="utf-8"))
                self.assertFalse(data["administrative_ready"])

    def test_exit_code_0_when_no_blocking(self):
        """Un expediente sin items bloqueantes debe dar exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST-EXIT0"
            exp.mkdir()
            # Mock run_da_flow para devolver un resultado sin bloqueantes
            from eia_agent.core import document_flow_da
            clean_result = _make_result("FLUJO_COMPLETO", bloqueante=[])
            with patch.object(document_flow_da, "run_da_flow", return_value=clean_result):
                code, _, _ = self._run([str(exp), "cliente-da", "--write"])
            self.assertEqual(code, 0)

    def test_exit_code_1_when_blocking(self):
        """Un expediente con items bloqueantes debe dar exit 1."""
        with tempfile.TemporaryDirectory() as tmp:
            exp = Path(tmp) / "EIA-TEST-EXIT1"
            exp.mkdir()
            from eia_agent.core import document_flow_da
            blocked_result = _make_result(
                "BLOQUEADO",
                bloqueante=[_make_item("BLOQUEANTE")]
            )
            with patch.object(document_flow_da, "run_da_flow", return_value=blocked_result):
                code, _, _ = self._run([str(exp), "cliente-da", "--write"])
            self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# 10. _safe_load_json
# ---------------------------------------------------------------------------

class TestSafeLoadJson(unittest.TestCase):

    def test_returns_none_for_missing_file(self):
        self.assertIsNone(_safe_load_json("/ruta/que/no/existe.json"))

    def test_returns_dict_for_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump({"key": "value"}, f)
            path = f.name
        result = _safe_load_json(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        Path(path).unlink(missing_ok=True)

    def test_returns_none_for_corrupt_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            f.write("{ invalid json }")
            path = f.name
        result = _safe_load_json(path)
        self.assertIsNone(result)
        Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
