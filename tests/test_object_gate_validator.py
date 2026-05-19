"""Tests para object_gate_validator -- OB-02."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.object_scope_builder import ObjectScope, write_object_scope_json
from eia_agent.core.object_gate_validator import (
    ObjectGateIssue,
    ObjectGateResult,
    contains_high_or_critical_gap,
    evaluate_gate_2,
    evaluate_gate_2_from_json,
    looks_like_referencia_catastral,
)

# ---------------------------------------------------------------------------
# Rutas de fixtures
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_DOCX_PARCELA = (
    _ROOT
    / "expediente-EIA-2026-RECIMETAL-PARCELA"
    / "inputs"
    / "memorias"
    / "Documento_Ambiental_RECIMETAL_Parcela_v6.docx"
)


# ---------------------------------------------------------------------------
# Helper: ObjectScope válido por defecto
# ---------------------------------------------------------------------------

def _make_scope(**kwargs) -> ObjectScope:
    """ObjectScope mínimo válido. Sobreescribir campos con kwargs."""
    defaults = dict(
        expediente_id="EXP-TEST-001",
        titular="EMPRESA TEST, S.L.",
        referencia_catastral="2462302DS4026S0001GQ",
        coordenadas_wgs84=["28.4567 -16.2345"],
        coordenadas_utm=[],
        operaciones_incluidas=["R1201"],
        operaciones_excluidas=[],
        modo="GABINETE",
        superficie_m2="1000 m²",
        capacidad=None,
        at_activos=[],
        gaps=[],
        estado_gate2="APTO",
        fuentes=["DOC-001"],
        notes=[],
    )
    defaults.update(kwargs)
    return ObjectScope(**defaults)


# ---------------------------------------------------------------------------
# 1. looks_like_referencia_catastral
# ---------------------------------------------------------------------------

class TestLooksLikeRC(unittest.TestCase):

    def test_rc_valida_20_chars(self):
        self.assertTrue(looks_like_referencia_catastral("2462302DS4026S0001GQ"))

    def test_rc_corta_invalida(self):
        self.assertFalse(looks_like_referencia_catastral("2462302DS4026S00"))

    def test_rc_larga_invalida(self):
        self.assertFalse(looks_like_referencia_catastral("2462302DS4026S0001GQ123"))

    def test_rc_con_caracteres_especiales_invalida(self):
        self.assertFalse(looks_like_referencia_catastral("2462302DS4026S0001G!"))

    def test_rc_minusculas_valida(self):
        self.assertTrue(looks_like_referencia_catastral("2462302ds4026s0001gq"))

    def test_cadena_vacia_invalida(self):
        self.assertFalse(looks_like_referencia_catastral(""))


# ---------------------------------------------------------------------------
# 2. contains_high_or_critical_gap
# ---------------------------------------------------------------------------

class TestContainsHighCritical(unittest.TestCase):

    def test_detecta_alta(self):
        self.assertTrue(contains_high_or_critical_gap("Gap de criticidad ALTA sin resolver"))

    def test_detecta_critica(self):
        self.assertTrue(contains_high_or_critical_gap("Incidencia CRÍTICA detectada"))

    def test_detecta_critica_sin_tilde(self):
        self.assertTrue(contains_high_or_critical_gap("Incidencia CRITICA detectada"))

    def test_detecta_bloqueante(self):
        self.assertTrue(contains_high_or_critical_gap("Dato BLOQUEANTE no disponible"))

    def test_detecta_critical_en_ingles(self):
        self.assertTrue(contains_high_or_critical_gap("CRITICAL missing field"))

    def test_no_detecta_texto_neutro(self):
        self.assertFalse(contains_high_or_critical_gap("Gap menor: superficie no contrastada"))

    def test_no_detecta_vacio(self):
        self.assertFalse(contains_high_or_critical_gap(""))

    def test_detecta_alta_minusculas(self):
        self.assertTrue(contains_high_or_critical_gap("criticidad alta"))


# ---------------------------------------------------------------------------
# 3. ObjectGateResult — métodos
# ---------------------------------------------------------------------------

class TestObjectGateResultMethods(unittest.TestCase):

    def _make_result(self, issues):
        return ObjectGateResult(
            expediente_id="EXP-TEST",
            passed=all(i.severity != "ERROR" for i in issues),
            test_mode=True,
            issues=issues,
        )

    def test_error_count(self):
        r = self._make_result([
            ObjectGateIssue("ERROR", "OB02-E001", "msg"),
            ObjectGateIssue("WARNING", "OB02-W001", "msg"),
        ])
        self.assertEqual(r.error_count(), 1)

    def test_warning_count(self):
        r = self._make_result([
            ObjectGateIssue("WARNING", "OB02-W001", "msg"),
            ObjectGateIssue("WARNING", "OB02-W002", "msg"),
        ])
        self.assertEqual(r.warning_count(), 2)

    def test_info_count(self):
        r = self._make_result([ObjectGateIssue("INFO", "OB02-I001", "msg")])
        self.assertEqual(r.info_count(), 1)

    def test_is_blocked_con_error(self):
        r = self._make_result([ObjectGateIssue("ERROR", "OB02-E001", "msg")])
        self.assertTrue(r.is_blocked())

    def test_is_blocked_sin_error(self):
        r = self._make_result([ObjectGateIssue("WARNING", "OB02-W001", "msg")])
        self.assertFalse(r.is_blocked())

    def test_sin_issues_no_bloqueado(self):
        r = ObjectGateResult("EXP", True, True, [])
        self.assertFalse(r.is_blocked())


# ---------------------------------------------------------------------------
# 4. Validación: titular
# ---------------------------------------------------------------------------

class TestValidarTitular(unittest.TestCase):

    def test_sin_titular_es_error(self):
        scope = _make_scope(titular=None)
        result = evaluate_gate_2(scope)
        titular_errors = [i for i in result.issues
                          if i.field == "titular" and i.severity == "ERROR"]
        self.assertGreater(len(titular_errors), 0)
        self.assertFalse(result.passed)

    def test_titular_presente_no_genera_error(self):
        scope = _make_scope(titular="EMPRESA TEST, S.L.")
        result = evaluate_gate_2(scope)
        titular_errors = [i for i in result.issues
                          if i.field == "titular" and i.severity == "ERROR"]
        self.assertEqual(len(titular_errors), 0)

    def test_gap_titularidad_test_es_warning(self):
        scope = _make_scope(gaps=["Gap de titularidad pendiente de resolver"])
        result = evaluate_gate_2(scope, test_mode=True)
        titular_warnings = [i for i in result.issues
                            if i.field == "titular" and i.severity == "WARNING"]
        self.assertGreater(len(titular_warnings), 0)
        self.assertTrue(result.passed)

    def test_gap_titularidad_produccion_es_error(self):
        scope = _make_scope(gaps=["Gap de titularidad pendiente de resolver"])
        result = evaluate_gate_2(scope, test_mode=False)
        titular_errors = [i for i in result.issues
                          if i.field == "titular" and i.severity == "ERROR"]
        self.assertGreater(len(titular_errors), 0)
        self.assertFalse(result.passed)


# ---------------------------------------------------------------------------
# 5. Validación: referencia catastral
# ---------------------------------------------------------------------------

class TestValidarRC(unittest.TestCase):

    def test_sin_rc_es_error(self):
        scope = _make_scope(referencia_catastral=None)
        result = evaluate_gate_2(scope)
        rc_errors = [i for i in result.issues
                     if i.field == "referencia_catastral" and i.severity == "ERROR"]
        self.assertGreater(len(rc_errors), 0)

    def test_rc_formato_invalido_es_error(self):
        scope = _make_scope(referencia_catastral="RC_INVALIDA")
        result = evaluate_gate_2(scope)
        rc_errors = [i for i in result.issues
                     if i.field == "referencia_catastral" and i.severity == "ERROR"
                     and "OB02-E003" in i.code]
        self.assertGreater(len(rc_errors), 0)
        self.assertFalse(result.passed)

    def test_rc_valida_no_genera_error(self):
        scope = _make_scope(referencia_catastral="2462302DS4026S0001GQ")
        result = evaluate_gate_2(scope)
        rc_errors = [i for i in result.issues
                     if i.field == "referencia_catastral" and i.severity == "ERROR"]
        self.assertEqual(len(rc_errors), 0)

    def test_rc_no_verificada_test_es_warning(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope, test_mode=True, context={"rc_verificada": False})
        rc_warnings = [i for i in result.issues
                       if i.field == "referencia_catastral" and i.severity == "WARNING"
                       and "OB02-W002" in i.code]
        self.assertGreater(len(rc_warnings), 0)
        self.assertTrue(result.passed)

    def test_rc_no_verificada_produccion_es_error(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope, test_mode=False, context={"rc_verificada": False})
        rc_errors = [i for i in result.issues
                     if i.field == "referencia_catastral" and i.severity == "ERROR"
                     and "OB02-W002" not in i.code]
        # En producción, OB02-W002 se eleva a ERROR
        rc_code_issues = [i for i in result.issues
                          if "OB02" in i.code and i.field == "referencia_catastral"
                          and i.severity == "ERROR"]
        self.assertGreater(len(rc_code_issues), 0)
        self.assertFalse(result.passed)


# ---------------------------------------------------------------------------
# 6. Validación: coordenadas
# ---------------------------------------------------------------------------

class TestValidarCoordenadas(unittest.TestCase):

    def test_sin_coordenadas_es_error(self):
        scope = _make_scope(coordenadas_wgs84=[], coordenadas_utm=[])
        result = evaluate_gate_2(scope)
        coord_errors = [i for i in result.issues
                        if i.field == "coordenadas_wgs84" and i.severity == "ERROR"
                        and "OB02-E004" in i.code]
        self.assertGreater(len(coord_errors), 0)
        self.assertFalse(result.passed)

    def test_solo_utm_valido(self):
        scope = _make_scope(coordenadas_wgs84=[], coordenadas_utm=["E: 642000 N: 3189000"])
        result = evaluate_gate_2(scope)
        coord_errors = [i for i in result.issues
                        if i.code == "OB02-E004"]
        self.assertEqual(len(coord_errors), 0)

    def test_coordenada_pendiente_test_es_warning(self):
        scope = _make_scope(coordenadas_wgs84=["PENDIENTE"])
        result = evaluate_gate_2(scope, test_mode=True)
        coord_warnings = [i for i in result.issues
                          if i.field == "coordenadas_wgs84" and i.severity == "WARNING"
                          and "OB02-W003" in i.code]
        self.assertGreater(len(coord_warnings), 0)
        self.assertTrue(result.passed)

    def test_coordenada_pendiente_produccion_es_error(self):
        scope = _make_scope(coordenadas_wgs84=["PENDIENTE"])
        result = evaluate_gate_2(scope, test_mode=False)
        coord_errors = [i for i in result.issues
                        if i.field == "coordenadas_wgs84" and i.severity == "ERROR"
                        and "OB02-W003" in i.code]
        self.assertGreater(len(coord_errors), 0)
        self.assertFalse(result.passed)

    def test_coordenada_real_no_genera_warning(self):
        scope = _make_scope(coordenadas_wgs84=["28.4567 -16.2345"])
        result = evaluate_gate_2(scope)
        coord_prov = [i for i in result.issues if "OB02-W003" in i.code]
        self.assertEqual(len(coord_prov), 0)


# ---------------------------------------------------------------------------
# 7. Validación: operaciones
# ---------------------------------------------------------------------------

class TestValidarOperaciones(unittest.TestCase):

    def test_sin_operaciones_incluidas_es_error(self):
        scope = _make_scope(operaciones_incluidas=[])
        result = evaluate_gate_2(scope)
        op_errors = [i for i in result.issues
                     if i.field == "operaciones_incluidas" and i.severity == "ERROR"]
        self.assertGreater(len(op_errors), 0)
        self.assertFalse(result.passed)

    def test_operaciones_excluidas_generan_info(self):
        scope = _make_scope(operaciones_excluidas=["R1302"])
        result = evaluate_gate_2(scope)
        excl_info = [i for i in result.issues
                     if i.field == "operaciones_excluidas" and i.severity == "INFO"]
        self.assertGreater(len(excl_info), 0)

    def test_cont_abiertos_sin_excluidas_ni_at_es_error(self):
        scope = _make_scope(operaciones_excluidas=[], at_activos=[])
        result = evaluate_gate_2(scope, context={"cont_abiertos": True})
        cont_errors = [i for i in result.issues
                       if i.code == "OB02-E006"]
        self.assertGreater(len(cont_errors), 0)
        self.assertFalse(result.passed)

    def test_cont_abiertos_con_excluidas_no_es_error_e006(self):
        scope = _make_scope(operaciones_excluidas=["R1302"])
        result = evaluate_gate_2(scope, context={"cont_abiertos": True})
        cont_errors = [i for i in result.issues if i.code == "OB02-E006"]
        self.assertEqual(len(cont_errors), 0)

    def test_cont_abiertos_con_at_no_es_error_e006(self):
        scope = _make_scope(operaciones_excluidas=[], at_activos=["AT-001 uso catastral"])
        result = evaluate_gate_2(scope, test_mode=True, context={"cont_abiertos": True})
        cont_errors = [i for i in result.issues if i.code == "OB02-E006"]
        self.assertEqual(len(cont_errors), 0)


# ---------------------------------------------------------------------------
# 8. Validación: modo
# ---------------------------------------------------------------------------

class TestValidarModo(unittest.TestCase):

    def test_no_declarado_es_error(self):
        scope = _make_scope(modo="NO_DECLARADO")
        result = evaluate_gate_2(scope)
        modo_errors = [i for i in result.issues
                       if i.field == "modo" and i.severity == "ERROR"]
        self.assertGreater(len(modo_errors), 0)
        self.assertFalse(result.passed)

    def test_gabinete_genera_info(self):
        scope = _make_scope(modo="GABINETE")
        result = evaluate_gate_2(scope)
        modo_info = [i for i in result.issues
                     if i.field == "modo" and i.severity == "INFO"]
        self.assertGreater(len(modo_info), 0)

    def test_gabinete_no_bloquea(self):
        scope = _make_scope(modo="GABINETE")
        result = evaluate_gate_2(scope)
        self.assertTrue(result.passed)

    def test_campo_no_genera_issue_modo(self):
        scope = _make_scope(modo="CAMPO")
        result = evaluate_gate_2(scope)
        modo_issues = [i for i in result.issues if i.field == "modo"]
        self.assertEqual(len(modo_issues), 0)


# ---------------------------------------------------------------------------
# 9. Validación: asunciones de test activas
# ---------------------------------------------------------------------------

class TestValidarAT(unittest.TestCase):

    def test_at_en_test_es_warning(self):
        scope = _make_scope(at_activos=["AT-001 superficie estimada"])
        result = evaluate_gate_2(scope, test_mode=True)
        at_warnings = [i for i in result.issues
                       if i.field == "at_activos" and i.severity == "WARNING"]
        self.assertGreater(len(at_warnings), 0)

    def test_at_en_test_no_bloquea(self):
        scope = _make_scope(at_activos=["AT-001 superficie estimada"])
        result = evaluate_gate_2(scope, test_mode=True)
        self.assertTrue(result.passed)

    def test_at_en_produccion_es_error(self):
        scope = _make_scope(at_activos=["AT-001 superficie estimada"])
        result = evaluate_gate_2(scope, test_mode=False)
        at_errors = [i for i in result.issues
                     if i.field == "at_activos" and i.severity == "ERROR"]
        self.assertGreater(len(at_errors), 0)

    def test_at_en_produccion_bloquea(self):
        scope = _make_scope(at_activos=["AT-001"])
        result = evaluate_gate_2(scope, test_mode=False)
        self.assertFalse(result.passed)


# ---------------------------------------------------------------------------
# 10. Validación: gaps
# ---------------------------------------------------------------------------

class TestValidarGaps(unittest.TestCase):

    def test_gap_alta_test_es_warning(self):
        scope = _make_scope(gaps=["Coordenadas ALTA sin verificar"])
        result = evaluate_gate_2(scope, test_mode=True)
        gap_warnings = [i for i in result.issues
                        if i.field == "gaps" and i.severity == "WARNING"]
        self.assertGreater(len(gap_warnings), 0)

    def test_gap_alta_test_no_bloquea(self):
        scope = _make_scope(gaps=["Coordenadas ALTA sin verificar"])
        result = evaluate_gate_2(scope, test_mode=True)
        self.assertTrue(result.passed)

    def test_gap_alta_produccion_es_error(self):
        scope = _make_scope(gaps=["Coordenadas ALTA sin verificar"])
        result = evaluate_gate_2(scope, test_mode=False)
        gap_errors = [i for i in result.issues
                      if i.field == "gaps" and i.severity == "ERROR"]
        self.assertGreater(len(gap_errors), 0)

    def test_gap_alta_produccion_bloquea(self):
        scope = _make_scope(gaps=["Coordenadas ALTA sin verificar"])
        result = evaluate_gate_2(scope, test_mode=False)
        self.assertFalse(result.passed)

    def test_gap_menor_es_info(self):
        scope = _make_scope(gaps=["Superficie no contrastada con catastro"])
        result = evaluate_gate_2(scope, test_mode=True)
        gap_info = [i for i in result.issues
                    if i.field == "gaps" and i.severity == "INFO"]
        self.assertGreater(len(gap_info), 0)
        # No gap WARNING ni ERROR para este gap
        gap_high = [i for i in result.issues
                    if i.field == "gaps" and i.severity in ("WARNING", "ERROR")]
        self.assertEqual(len(gap_high), 0)


# ---------------------------------------------------------------------------
# 11. Validación: uso catastral vs uso declarado
# ---------------------------------------------------------------------------

class TestValidarUsoCatastral(unittest.TestCase):

    def test_discrepancia_sin_at_test_es_warning(self):
        scope = _make_scope()
        ctx = {"uso_catastral": "almacén agrario", "uso_declarado": "industrial"}
        result = evaluate_gate_2(scope, test_mode=True, context=ctx)
        uso_warnings = [i for i in result.issues
                        if "OB02-W007" in i.code]
        self.assertGreater(len(uso_warnings), 0)
        self.assertTrue(result.passed)

    def test_discrepancia_sin_at_produccion_es_error(self):
        scope = _make_scope()
        ctx = {"uso_catastral": "almacén agrario", "uso_declarado": "industrial"}
        result = evaluate_gate_2(scope, test_mode=False, context=ctx)
        uso_errors = [i for i in result.issues
                      if "OB02-E010" in i.code]
        self.assertGreater(len(uso_errors), 0)
        self.assertFalse(result.passed)

    def test_discrepancia_con_at_es_warning_no_error(self):
        scope = _make_scope(at_activos=["AT-001 uso catastral almacén agrario vs industrial"])
        ctx = {"uso_catastral": "almacén agrario", "uso_declarado": "industrial"}
        result = evaluate_gate_2(scope, test_mode=True, context=ctx)
        uso_w006 = [i for i in result.issues if "OB02-W006" in i.code]
        uso_error = [i for i in result.issues if "OB02-E010" in i.code]
        self.assertGreater(len(uso_w006), 0)
        self.assertEqual(len(uso_error), 0)

    def test_discrepancia_con_at_produccion_warning_no_error_uso(self):
        scope = _make_scope(at_activos=["AT-001"])
        ctx = {"uso_catastral": "almacén agrario", "uso_declarado": "industrial"}
        result = evaluate_gate_2(scope, test_mode=False, context=ctx)
        uso_e010 = [i for i in result.issues if "OB02-E010" in i.code]
        self.assertEqual(len(uso_e010), 0)
        uso_w006 = [i for i in result.issues if "OB02-W006" in i.code]
        self.assertGreater(len(uso_w006), 0)

    def test_sin_discrepancia_no_genera_issue_uso(self):
        scope = _make_scope()
        ctx = {"uso_catastral": "industrial", "uso_declarado": "industrial"}
        result = evaluate_gate_2(scope, context=ctx)
        uso_issues = [i for i in result.issues
                      if i.code in ("OB02-W006", "OB02-W007", "OB02-E010")]
        self.assertEqual(len(uso_issues), 0)


# ---------------------------------------------------------------------------
# 12. Lógica de passed
# ---------------------------------------------------------------------------

class TestPassedLogic(unittest.TestCase):

    def test_scope_completo_passed_true(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope, test_mode=True)
        self.assertTrue(result.passed)

    def test_con_error_passed_false(self):
        scope = _make_scope(titular=None)
        result = evaluate_gate_2(scope)
        self.assertFalse(result.passed)

    def test_solo_warnings_passed_true(self):
        scope = _make_scope(at_activos=["AT-001"])
        result = evaluate_gate_2(scope, test_mode=True)
        self.assertTrue(result.passed)
        self.assertGreater(result.warning_count(), 0)

    def test_solo_infos_passed_true(self):
        scope = _make_scope(operaciones_excluidas=["R1302"])
        result = evaluate_gate_2(scope, test_mode=True)
        self.assertTrue(result.passed)
        self.assertGreater(result.info_count(), 0)


# ---------------------------------------------------------------------------
# 13. evaluate_gate_2_from_json
# ---------------------------------------------------------------------------

class TestEvaluateGate2FromJson(unittest.TestCase):

    def test_carga_json_y_evalua(self):
        scope = _make_scope()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "scope.json"
            write_object_scope_json(scope, json_path)
            result = evaluate_gate_2_from_json(json_path, test_mode=True)
        self.assertIsInstance(result, ObjectGateResult)
        self.assertEqual(result.expediente_id, "EXP-TEST-001")

    def test_passed_para_scope_valido(self):
        scope = _make_scope()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "scope.json"
            write_object_scope_json(scope, json_path)
            result = evaluate_gate_2_from_json(json_path)
        self.assertTrue(result.passed)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            evaluate_gate_2_from_json("/ruta/inexistente/scope.json")

    def test_no_escribe_nada(self):
        scope = _make_scope()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "scope.json"
            write_object_scope_json(scope, json_path)
            files_before = set(Path(tmp).iterdir())
            evaluate_gate_2_from_json(json_path)
            files_after = set(Path(tmp).iterdir())
        self.assertEqual(files_before, files_after)


# ---------------------------------------------------------------------------
# 14. summary()
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):

    def test_summary_contiene_estado_apto(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope)
        self.assertIn("APTO", result.summary())

    def test_summary_contiene_estado_bloqueado(self):
        scope = _make_scope(titular=None)
        result = evaluate_gate_2(scope)
        self.assertIn("BLOQUEADO", result.summary())

    def test_summary_contiene_expediente_id(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope)
        self.assertIn("EXP-TEST-001", result.summary())

    def test_summary_contiene_contadores(self):
        scope = _make_scope(at_activos=["AT-001"])
        result = evaluate_gate_2(scope, test_mode=True)
        s = result.summary()
        self.assertIn("Errores:", s)
        self.assertIn("Avisos:", s)

    def test_summary_no_vacio(self):
        scope = _make_scope()
        result = evaluate_gate_2(scope)
        self.assertGreater(len(result.summary()), 0)


# ---------------------------------------------------------------------------
# 15. Fixture PARCELA — solo lectura
# ---------------------------------------------------------------------------

@unittest.skipUnless(_DOCX_PARCELA.exists(), "Fixture PARCELA no disponible")
class TestFixtureParcela(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from eia_agent.core.evidence_classifier import classify_entities_from_docx
        from eia_agent.core.object_scope_builder import build_object_scope

        cls.mtime_before = _DOCX_PARCELA.stat().st_mtime

        classification = classify_entities_from_docx(
            str(_DOCX_PARCELA), source_doc_id="DOC-001"
        )
        cls.scope = build_object_scope(
            "expediente-EIA-2026-RECIMETAL-PARCELA",
            classification=classification,
            overrides={"modo": "GABINETE"},
        )
        cls.result_test = evaluate_gate_2(cls.scope, test_mode=True)
        cls.result_prod = evaluate_gate_2(cls.scope, test_mode=False)

    def test_mtime_docx_sin_cambios(self):
        self.assertEqual(_DOCX_PARCELA.stat().st_mtime, self.mtime_before)

    def test_expediente_id_correcto(self):
        self.assertEqual(
            self.result_test.expediente_id,
            "expediente-EIA-2026-RECIMETAL-PARCELA",
        )

    def test_result_es_object_gate_result(self):
        self.assertIsInstance(self.result_test, ObjectGateResult)

    def test_test_mode_true_en_result(self):
        self.assertTrue(self.result_test.test_mode)

    def test_prod_mode_false_en_result(self):
        self.assertFalse(self.result_prod.test_mode)

    def test_modo_gabinete_genera_info(self):
        modo_infos = [i for i in self.result_test.issues
                      if i.field == "modo" and i.severity == "INFO"]
        self.assertGreater(len(modo_infos), 0)

    def test_gate2_coherente_con_estado_scope(self):
        if self.scope.estado_gate2 == "APTO":
            self.assertTrue(self.result_test.passed)
        else:
            self.assertGreater(len(self.result_test.issues), 0)

    def test_no_escritura_en_piloto(self):
        piloto_dir = _DOCX_PARCELA.parent.parent.parent
        for f in piloto_dir.rglob("gate2_result*"):
            self.fail(f"evaluate_gate_2 escribió en piloto: {f}")

    def test_summary_no_vacio(self):
        self.assertGreater(len(self.result_test.summary()), 0)


if __name__ == "__main__":
    unittest.main()
