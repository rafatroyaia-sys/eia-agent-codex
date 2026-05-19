"""
tests/test_phase3_pipeline.py — TN-05

Tests para phase3_pipeline.py: triaje normativo básico.
No IA, no web, no BOE online. Solo reglas Python puras.
Los pilotos PARCELA y NAVE-222 se usan solo en modo lectura.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.phase3_pipeline import (
    NormativeItem,
    Phase3Result,
    _build_cautelas,
    _build_normativa,
    _build_text_corpus,
    _detect_alta_capacidad,
    _detect_canarias,
    _detect_natura,
    _detect_patrimonio,
    _detect_residuos,
    _detect_ruido,
    _detect_urbanismo,
    _determine_procedimiento,
    _has_any_keyword,
    _has_r12_r13_operations,
    run_phase3,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PHASE1_MINIMO: dict = {
    "expediente_id": "test-expediente",
    "candidate_facts": [],
    "warnings": [],
    "notes": [],
}

_PHASE1_CON_RESIDUOS: dict = {
    "expediente_id": "test-expediente",
    "candidate_facts": [
        {
            "id": "CF-001",
            "categoria": "operaciones",
            "campo": "operacion_residuos",
            "valor": "R1201",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "OPERACION_RESIDUOS",
            "confidence": "HIGH",
            "context": "Operación de clasificación de chatarra",
            "normalized_value": None,
            "notes": [],
        },
        {
            "id": "CF-002",
            "categoria": "operaciones",
            "campo": "codigo_ler",
            "valor": "17 04 05",
            "estado": "DECLARADO",
            "fuentes": ["doc.docx"],
            "entity_type": "LER",
            "confidence": "HIGH",
            "context": None,
            "normalized_value": None,
            "notes": [],
        },
    ],
    "warnings": [],
    "notes": [],
}

_PHASE2_CON_SCOPE: dict = {
    "expediente_id": "test-expediente",
    "object_scope": {
        "titular": "Empresa Test SL",
        "referencia_catastral": "1234567AB1234A0001LP",
        "coordenadas_wgs84": ["28.1, -15.4"],
        "coordenadas_utm": [],
        "operaciones_incluidas": ["R1201", "R1301"],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "at_activos": [],
        "gaps": [],
        "superficie_m2": "5000",
        "capacidad": "25000 t/año",
    },
    "gate2_passed": True,
    "gate2_summary": "Gate 2 APTO",
    "issues": [],
    "warnings": [],
}

_PHASE2_CANARIAS_SCOPE: dict = {
    "expediente_id": "test-expediente",
    "object_scope": {
        "titular": "Empresa Canaria SL",
        "referencia_catastral": "1234567AB1234A0001LP",
        "coordenadas_wgs84": ["28.1, -15.4"],
        "coordenadas_utm": [],
        "operaciones_incluidas": ["R1201"],
        "operaciones_excluidas": [],
        "modo": "GABINETE",
        "at_activos": [],
        "gaps": [],
        "superficie_m2": "3000",
        "capacidad": None,
    },
    "gate2_passed": True,
    "gate2_summary": "Gate 2 APTO",
    "issues": [],
    "warnings": [],
}


def _write_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestNormativeItemStructure
# ---------------------------------------------------------------------------

class TestNormativeItemStructure(unittest.TestCase):
    def _make(self) -> NormativeItem:
        return NormativeItem(
            id="TN-A001",
            titulo="Ley 21/2013",
            ambito="estatal",
            materia="evaluacion_ambiental",
            referencia="BOE-A-2013-12913",
            estado="REFERENCIADA",
            razon_aplicabilidad="Marco base EIA",
            fuente_deteccion="regla_base",
            notas=["Verificar vigencia"],
        )

    def test_fields(self):
        item = self._make()
        self.assertEqual(item.id, "TN-A001")
        self.assertEqual(item.ambito, "estatal")
        self.assertEqual(item.estado, "REFERENCIADA")
        self.assertEqual(len(item.notas), 1)

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        for key in ("id", "titulo", "ambito", "materia", "referencia",
                    "estado", "razon_aplicabilidad", "fuente_deteccion", "notas"):
            self.assertIn(key, d)

    def test_to_dict_notas_copy(self):
        item = self._make()
        d = item.to_dict()
        d["notas"].append("extra")
        self.assertEqual(len(item.notas), 1)

    def test_referencia_none(self):
        item = self._make()
        item.referencia = None
        self.assertIsNone(item.to_dict()["referencia"])


# ---------------------------------------------------------------------------
# TestPhase3ResultSummary
# ---------------------------------------------------------------------------

class TestPhase3ResultSummary(unittest.TestCase):
    def _make(self, procedimiento="SIMPLIFICADA", n_normas=2) -> Phase3Result:
        normativa = [
            NormativeItem(
                id=f"TN-X{i:03d}",
                titulo=f"Norma {i}",
                ambito="estatal",
                materia="evaluacion_ambiental",
                referencia=None,
                estado="REFERENCIADA",
                razon_aplicabilidad="Razón",
                fuente_deteccion="test",
            )
            for i in range(n_normas)
        ]
        return Phase3Result(
            expediente_id="test-exp",
            normativa=normativa,
            procedimiento_eia=procedimiento,
            razones_procedimiento=["Razón de prueba"],
            cautelas=["[CAUTELA-TN-01] Verificar"],
            warnings=["aviso de prueba"],
            notes=["nota de prueba"],
        )

    def test_summary_contains_expediente(self):
        r = self._make()
        self.assertIn("test-exp", r.summary())

    def test_summary_contains_procedimiento(self):
        r = self._make(procedimiento="NO_DETERMINADO")
        self.assertIn("NO_DETERMINADO", r.summary())

    def test_summary_contains_norma_count(self):
        r = self._make(n_normas=3)
        self.assertIn("3", r.summary())

    def test_summary_contains_warnings(self):
        r = self._make()
        self.assertIn("aviso de prueba", r.summary())

    def test_summary_notes(self):
        r = self._make()
        self.assertIn("nota de prueba", r.summary())

    def test_to_dict_keys(self):
        r = self._make()
        d = r.to_dict()
        for key in ("expediente_id", "normativa", "procedimiento_eia",
                    "razones_procedimiento", "cautelas", "warnings", "notes"):
            self.assertIn(key, d)

    def test_to_dict_normativa_list(self):
        r = self._make(n_normas=2)
        d = r.to_dict()
        self.assertIsInstance(d["normativa"], list)
        self.assertEqual(len(d["normativa"]), 2)
        self.assertIsInstance(d["normativa"][0], dict)

    def test_to_dict_json_serializable(self):
        r = self._make()
        json.dumps(r.to_dict())  # no excepción


# ---------------------------------------------------------------------------
# TestHasAnyKeyword
# ---------------------------------------------------------------------------

class TestHasAnyKeyword(unittest.TestCase):
    def test_found(self):
        found, kw = _has_any_keyword("Gestión de residuos peligrosos", frozenset({"residuo"}))
        self.assertTrue(found)
        self.assertEqual(kw, "residuo")

    def test_not_found(self):
        found, kw = _has_any_keyword("Proyecto de construcción", frozenset({"residuo"}))
        self.assertFalse(found)
        self.assertEqual(kw, "")

    def test_case_insensitive(self):
        found, _ = _has_any_keyword("TENERIFE", frozenset({"tenerife"}))
        self.assertTrue(found)

    def test_empty_text(self):
        found, _ = _has_any_keyword("", frozenset({"residuo"}))
        self.assertFalse(found)

    def test_empty_keywords(self):
        found, _ = _has_any_keyword("residuo", frozenset())
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestBuildTextCorpus
# ---------------------------------------------------------------------------

class TestBuildTextCorpus(unittest.TestCase):
    def test_includes_fact_valor(self):
        facts = [{"valor": "R1201", "context": None, "normalized_value": None, "notes": []}]
        corpus = _build_text_corpus(facts, {})
        self.assertIn("R1201", corpus)

    def test_includes_fact_context(self):
        facts = [{"valor": None, "context": "chatarra metálica", "normalized_value": None, "notes": []}]
        corpus = _build_text_corpus(facts, {})
        self.assertIn("chatarra metálica", corpus)

    def test_includes_object_scope_fields(self):
        scope = {"titular": "RECIMETAL", "modo": "GABINETE"}
        corpus = _build_text_corpus([], scope)
        self.assertIn("RECIMETAL", corpus)
        self.assertIn("GABINETE", corpus)

    def test_includes_operations(self):
        scope = {"operaciones_incluidas": ["R1201"], "operaciones_excluidas": ["D15"]}
        corpus = _build_text_corpus([], scope)
        self.assertIn("R1201", corpus)
        self.assertIn("D15", corpus)

    def test_empty(self):
        corpus = _build_text_corpus([], {})
        self.assertEqual(corpus, "")


# ---------------------------------------------------------------------------
# TestDetectResiduous
# ---------------------------------------------------------------------------

class TestDetectResiduous(unittest.TestCase):
    def test_detects_campo_codigo_ler(self):
        facts = [{"campo": "codigo_ler", "entity_type": "", "valor": "17 04 05", "context": None,
                  "normalized_value": None, "notes": []}]
        found, src = _detect_residuos(facts, "")
        self.assertTrue(found)
        self.assertIn("codigo_ler", src)

    def test_detects_entity_type_ler(self):
        facts = [{"campo": "otro", "entity_type": "LER", "valor": "17 04 05", "context": None,
                  "normalized_value": None, "notes": []}]
        found, src = _detect_residuos(facts, "")
        self.assertTrue(found)
        self.assertIn("LER", src)

    def test_detects_keyword_in_corpus(self):
        found, src = _detect_residuos([], "gestión de residuos metálicos")
        self.assertTrue(found)
        self.assertIn("texto:", src)

    def test_not_detected_empty(self):
        found, src = _detect_residuos([], "proyecto de construcción de viviendas")
        self.assertFalse(found)
        self.assertEqual(src, "")

    def test_detects_campo_operacion_residuos(self):
        facts = [{"campo": "operacion_residuos", "entity_type": "", "valor": "R12", "context": None,
                  "normalized_value": None, "notes": []}]
        found, src = _detect_residuos(facts, "")
        self.assertTrue(found)


# ---------------------------------------------------------------------------
# TestHasR12R13Operations
# ---------------------------------------------------------------------------

class TestHasR12R13Operations(unittest.TestCase):
    def test_r12_in_facts(self):
        facts = [{"campo": "operacion_residuos", "valor": "R1201"}]
        self.assertTrue(_has_r12_r13_operations(facts, {}))

    def test_r13_in_facts(self):
        facts = [{"campo": "operacion_residuos", "valor": "R13"}]
        self.assertTrue(_has_r12_r13_operations(facts, {}))

    def test_r12_in_scope_operations(self):
        self.assertTrue(_has_r12_r13_operations([], {"operaciones_incluidas": ["R1201"]}))

    def test_r13_in_scope_operations(self):
        self.assertTrue(_has_r12_r13_operations([], {"operaciones_incluidas": ["R1301"]}))

    def test_not_r12_r13(self):
        facts = [{"campo": "operacion_residuos", "valor": "D15"}]
        self.assertFalse(_has_r12_r13_operations(facts, {}))

    def test_empty(self):
        self.assertFalse(_has_r12_r13_operations([], {}))


# ---------------------------------------------------------------------------
# TestDetectRuido
# ---------------------------------------------------------------------------

class TestDetectRuido(unittest.TestCase):
    def test_detects_campo_equipo(self):
        facts = [{"campo": "equipo", "entity_type": "", "valor": "trituradora", "context": None,
                  "normalized_value": None, "notes": []}]
        found, src = _detect_ruido(facts, "")
        self.assertTrue(found)

    def test_detects_entity_type_potencia(self):
        facts = [{"campo": "otro", "entity_type": "POTENCIA", "valor": "100 kW", "context": None,
                  "normalized_value": None, "notes": []}]
        found, src = _detect_ruido(facts, "")
        self.assertTrue(found)

    def test_detects_keyword_trituradora(self):
        found, src = _detect_ruido([], "instalación de trituradora de vehículos")
        self.assertTrue(found)

    def test_not_detected(self):
        found, _ = _detect_ruido([], "edificio de oficinas")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestDetectNatura
# ---------------------------------------------------------------------------

class TestDetectNatura(unittest.TestCase):
    def test_detects_zec(self):
        found, src = _detect_natura("posible afección a ZEC colindante")
        self.assertTrue(found)

    def test_detects_red_natura(self):
        found, src = _detect_natura("zona incluida en Red Natura 2000")
        self.assertTrue(found)

    def test_not_detected(self):
        found, _ = _detect_natura("parcela de uso industrial")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestDetectPatrimonio
# ---------------------------------------------------------------------------

class TestDetectPatrimonio(unittest.TestCase):
    def test_detects_patrimonio(self):
        found, _ = _detect_patrimonio("se ha detectado un yacimiento arqueológico")
        self.assertTrue(found)

    def test_detects_bic(self):
        found, _ = _detect_patrimonio("edificio declarado BIC")
        self.assertTrue(found)

    def test_not_detected(self):
        found, _ = _detect_patrimonio("nave industrial de reciente construcción")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestDetectCanarias
# ---------------------------------------------------------------------------

class TestDetectCanarias(unittest.TestCase):
    def test_detects_by_coords_wgs84(self):
        scope = {"coordenadas_wgs84": ["28.1, -15.4"]}
        found, src = _detect_canarias(scope, "")
        self.assertTrue(found)
        self.assertIn("coordenadas_wgs84", src)

    def test_detects_by_keyword_tenerife(self):
        found, src = _detect_canarias({}, "proyecto en Tenerife")
        self.assertTrue(found)

    def test_detects_by_keyword_cabildo(self):
        found, _ = _detect_canarias({}, "comunicación al Cabildo Insular")
        self.assertTrue(found)

    def test_not_detected_peninsula(self):
        scope = {"coordenadas_wgs84": ["40.4, -3.7"]}
        found, _ = _detect_canarias(scope, "proyecto en Madrid")
        self.assertFalse(found)

    def test_invalid_coord_fallback_to_keyword(self):
        scope = {"coordenadas_wgs84": ["invalido"]}
        found, _ = _detect_canarias(scope, "proyecto en Lanzarote")
        self.assertTrue(found)

    def test_canarias_lat_boundary(self):
        scope = {"coordenadas_wgs84": ["27.0, -16.0"]}
        found, _ = _detect_canarias(scope, "")
        self.assertTrue(found)

    def test_outside_canarias_coords(self):
        scope = {"coordenadas_wgs84": ["26.0, -16.0"]}
        found, _ = _detect_canarias(scope, "")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestDetectUrbanismo
# ---------------------------------------------------------------------------

class TestDetectUrbanismo(unittest.TestCase):
    def test_detects_rc_in_scope(self):
        scope = {"referencia_catastral": "1234567AB1234A0001LP"}
        found, src = _detect_urbanismo([], scope, "")
        self.assertTrue(found)
        self.assertIn("referencia_catastral", src)

    def test_detects_campo_rc_in_facts(self):
        facts = [{"campo": "referencia_catastral", "entity_type": "", "valor": "1234567AB",
                  "context": None, "normalized_value": None, "notes": []}]
        found, src = _detect_urbanismo(facts, {}, "")
        self.assertTrue(found)

    def test_detects_keyword_pgou(self):
        found, _ = _detect_urbanismo([], {}, "verificar compatibilidad con PGOU vigente")
        self.assertTrue(found)

    def test_not_detected(self):
        found, _ = _detect_urbanismo([], {}, "proyecto sin afección urbanística")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestDetectAltaCapacidad
# ---------------------------------------------------------------------------

class TestDetectAltaCapacidad(unittest.TestCase):
    def test_detects_keyword_fraccionamiento(self):
        found, src = _detect_alta_capacidad({}, "posible fraccionamiento del proyecto")
        self.assertTrue(found)

    def test_detects_keyword_anexo_i(self):
        found, _ = _detect_alta_capacidad({}, "podría encuadrarse en el Anexo I de la ley")
        self.assertTrue(found)

    def test_detects_alta_capacidad_numerica(self):
        scope = {"capacidad": "60000 t/año"}
        found, src = _detect_alta_capacidad(scope, "")
        self.assertTrue(found)
        self.assertIn("capacidad_elevada", src)

    def test_not_detects_low_capacidad(self):
        scope = {"capacidad": "25000 t/año"}
        found, _ = _detect_alta_capacidad(scope, "")
        self.assertFalse(found)

    def test_not_detected_empty(self):
        found, _ = _detect_alta_capacidad({}, "")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# TestBuildNormativa
# ---------------------------------------------------------------------------

class TestBuildNormativa(unittest.TestCase):
    def _build(self, **kwargs) -> list:
        defaults = dict(
            has_residuos=False, residuos_source="",
            has_ruido=False, ruido_source="",
            has_natura=False, natura_source="",
            has_patrimonio=False, patrimonio_source="",
            has_canarias=False, canarias_source="",
            has_urbanismo=False, urbanismo_source="",
        )
        defaults.update(kwargs)
        return _build_normativa(**defaults)

    def test_always_includes_ley21(self):
        items = self._build()
        ids = [i.id for i in items]
        self.assertIn("TN-A001", ids)

    def test_always_includes_rd445(self):
        items = self._build()
        ids = [i.id for i in items]
        self.assertIn("TN-B001", ids)

    def test_minimum_2_items(self):
        items = self._build()
        self.assertGreaterEqual(len(items), 2)

    def test_residuos_adds_ley7(self):
        items = self._build(has_residuos=True, residuos_source="campo:codigo_ler")
        ids = [i.id for i in items]
        self.assertIn("TN-C001", ids)

    def test_no_residuos_no_ley7(self):
        items = self._build(has_residuos=False)
        ids = [i.id for i in items]
        self.assertNotIn("TN-C001", ids)

    def test_ruido_adds_ley37_and_rd1367(self):
        items = self._build(has_ruido=True, ruido_source="campo:equipo")
        ids = [i.id for i in items]
        self.assertIn("TN-D001", ids)
        self.assertIn("TN-D002", ids)

    def test_natura_adds_ley42(self):
        items = self._build(has_natura=True, natura_source="texto:zec")
        ids = [i.id for i in items]
        self.assertIn("TN-E001", ids)

    def test_patrimonio_adds_ley16(self):
        items = self._build(has_patrimonio=True, patrimonio_source="texto:bic")
        ids = [i.id for i in items]
        self.assertIn("TN-F001", ids)

    def test_canarias_adds_ley4_and_ley6(self):
        items = self._build(has_canarias=True, canarias_source="texto:tenerife")
        ids = [i.id for i in items]
        self.assertIn("TN-G001", ids)
        self.assertIn("TN-G002", ids)

    def test_urbanismo_adds_tn_h001(self):
        items = self._build(has_urbanismo=True, urbanismo_source="object_scope:referencia_catastral")
        ids = [i.id for i in items]
        self.assertIn("TN-H001", ids)

    def test_patrimonio_estado_pendiente_verificacion(self):
        items = self._build(has_patrimonio=True, patrimonio_source="texto:yacimiento")
        f001 = next(i for i in items if i.id == "TN-F001")
        self.assertEqual(f001.estado, "PENDIENTE_VERIFICACION")

    def test_urbanismo_estado_pendiente_verificacion(self):
        items = self._build(has_urbanismo=True, urbanismo_source="texto:pgou")
        h001 = next(i for i in items if i.id == "TN-H001")
        self.assertEqual(h001.estado, "PENDIENTE_VERIFICACION")

    def test_ley21_estado_referenciada(self):
        items = self._build()
        a001 = next(i for i in items if i.id == "TN-A001")
        self.assertEqual(a001.estado, "REFERENCIADA")

    def test_all_items_detected(self):
        items = self._build(
            has_residuos=True, residuos_source="r",
            has_ruido=True, ruido_source="r",
            has_natura=True, natura_source="r",
            has_patrimonio=True, patrimonio_source="r",
            has_canarias=True, canarias_source="r",
            has_urbanismo=True, urbanismo_source="r",
        )
        self.assertEqual(len(items), 10)

    def test_residuos_source_in_razon(self):
        items = self._build(has_residuos=True, residuos_source="campo:codigo_ler")
        c001 = next(i for i in items if i.id == "TN-C001")
        self.assertIn("campo:codigo_ler", c001.razon_aplicabilidad)


# ---------------------------------------------------------------------------
# TestDetermineProcedimiento
# ---------------------------------------------------------------------------

class TestDetermineProcedimiento(unittest.TestCase):
    def test_simplificada_r12(self):
        facts = [{"campo": "operacion_residuos", "valor": "R1201"}]
        scope = {"operaciones_incluidas": ["R1201"]}
        proc, razones = _determine_procedimiento(
            has_residuos=True,
            has_alta_capacidad=False,
            alta_capacidad_source="",
            candidate_facts=facts,
            object_scope=scope,
        )
        self.assertEqual(proc, "SIMPLIFICADA")
        self.assertTrue(len(razones) > 0)

    def test_simplificada_residuos_sin_r12(self):
        proc, razones = _determine_procedimiento(
            has_residuos=True,
            has_alta_capacidad=False,
            alta_capacidad_source="",
            candidate_facts=[],
            object_scope={},
        )
        self.assertEqual(proc, "SIMPLIFICADA")

    def test_ordinaria_posible_alta_capacidad(self):
        proc, razones = _determine_procedimiento(
            has_residuos=True,
            has_alta_capacidad=True,
            alta_capacidad_source="texto:fraccionamiento",
            candidate_facts=[],
            object_scope={},
        )
        self.assertEqual(proc, "ORDINARIA_POSIBLE")

    def test_no_determinado_sin_residuos(self):
        proc, razones = _determine_procedimiento(
            has_residuos=False,
            has_alta_capacidad=False,
            alta_capacidad_source="",
            candidate_facts=[],
            object_scope={},
        )
        self.assertEqual(proc, "NO_DETERMINADO")

    def test_razones_not_empty(self):
        _, razones = _determine_procedimiento(
            has_residuos=True,
            has_alta_capacidad=False,
            alta_capacidad_source="",
            candidate_facts=[{"campo": "operacion_residuos", "valor": "R1201"}],
            object_scope={"operaciones_incluidas": ["R1201"]},
        )
        self.assertTrue(len(razones) >= 1)


# ---------------------------------------------------------------------------
# TestBuildCautelas
# ---------------------------------------------------------------------------

class TestBuildCautelas(unittest.TestCase):
    def test_always_includes_tn01_tn02(self):
        cautelas = _build_cautelas({}, has_natura=False, has_canarias=False, procedimiento="SIMPLIFICADA")
        codes = [c.split("]")[0].replace("[", "") for c in cautelas]
        self.assertIn("CAUTELA-TN-01", codes)
        self.assertIn("CAUTELA-TN-02", codes)

    def test_gabinete_adds_tn03(self):
        scope = {"modo": "GABINETE"}
        cautelas = _build_cautelas(scope, has_natura=False, has_canarias=False, procedimiento="SIMPLIFICADA")
        text = " ".join(cautelas)
        self.assertIn("CAUTELA-TN-03", text)

    def test_at_activos_adds_tn04(self):
        scope = {"at_activos": ["AT-001"]}
        cautelas = _build_cautelas(scope, has_natura=False, has_canarias=False, procedimiento="SIMPLIFICADA")
        text = " ".join(cautelas)
        self.assertIn("CAUTELA-TN-04", text)

    def test_natura_adds_tn05(self):
        cautelas = _build_cautelas({}, has_natura=True, has_canarias=False, procedimiento="SIMPLIFICADA")
        text = " ".join(cautelas)
        self.assertIn("CAUTELA-TN-05", text)

    def test_canarias_adds_tn06(self):
        cautelas = _build_cautelas({}, has_natura=False, has_canarias=True, procedimiento="SIMPLIFICADA")
        text = " ".join(cautelas)
        self.assertIn("CAUTELA-TN-06", text)

    def test_ordinaria_posible_adds_tn07(self):
        cautelas = _build_cautelas({}, has_natura=False, has_canarias=False, procedimiento="ORDINARIA_POSIBLE")
        text = " ".join(cautelas)
        self.assertIn("CAUTELA-TN-07", text)

    def test_minimum_cautelas(self):
        cautelas = _build_cautelas({}, has_natura=False, has_canarias=False, procedimiento="SIMPLIFICADA")
        self.assertGreaterEqual(len(cautelas), 2)


# ---------------------------------------------------------------------------
# TestRunPhase3SinPhase1
# ---------------------------------------------------------------------------

class TestRunPhase3SinPhase1(unittest.TestCase):
    def test_raises_filenotfounderror(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-test"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            with self.assertRaises(FileNotFoundError):
                run_phase3(exp)

    def test_error_message_mentions_phase1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-test"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            try:
                run_phase3(exp)
            except FileNotFoundError as exc:
                self.assertIn("phase1", str(exc).lower())
            else:
                self.fail("Expected FileNotFoundError")

    def test_explicit_path_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-test"
            exp.mkdir()
            missing = Path(tmpdir) / "no_existe.json"
            with self.assertRaises(FileNotFoundError):
                run_phase3(exp, phase1_result_path=missing)


# ---------------------------------------------------------------------------
# TestRunPhase3ConDatosMinimos
# ---------------------------------------------------------------------------

class TestRunPhase3ConDatosMinimos(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-test"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE1_MINIMO, ci / "phase1_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_returns_phase3result(self):
        result = run_phase3(self.exp)
        self.assertIsInstance(result, Phase3Result)

    def test_expediente_id_matches(self):
        result = run_phase3(self.exp)
        self.assertEqual(result.expediente_id, "expediente-test")

    def test_always_two_base_normas(self):
        result = run_phase3(self.exp)
        ids = [n.id for n in result.normativa]
        self.assertIn("TN-A001", ids)
        self.assertIn("TN-B001", ids)

    def test_no_phase2_note(self):
        result = run_phase3(self.exp)
        notes_text = " ".join(result.notes)
        self.assertIn("phase2", notes_text.lower())

    def test_no_phase2_empty_scope(self):
        # Sin scope, no hay Canarias
        result = run_phase3(self.exp)
        ids = [n.id for n in result.normativa]
        self.assertNotIn("TN-G001", ids)


# ---------------------------------------------------------------------------
# TestRunPhase3ConResidues
# ---------------------------------------------------------------------------

class TestRunPhase3ConResidues(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-residuos"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE1_CON_RESIDUOS, ci / "phase1_result.json")
        _write_json(_PHASE2_CON_SCOPE, ci / "phase2_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_detects_ley7_residuos(self):
        result = run_phase3(self.exp)
        ids = [n.id for n in result.normativa]
        self.assertIn("TN-C001", ids)

    def test_procedimiento_simplificada(self):
        result = run_phase3(self.exp)
        self.assertEqual(result.procedimiento_eia, "SIMPLIFICADA")

    def test_canarias_detected_by_coords(self):
        result = run_phase3(self.exp)
        ids = [n.id for n in result.normativa]
        self.assertIn("TN-G001", ids)
        self.assertIn("TN-G002", ids)

    def test_urbanismo_detected_by_rc(self):
        result = run_phase3(self.exp)
        ids = [n.id for n in result.normativa]
        self.assertIn("TN-H001", ids)

    def test_cautelas_not_empty(self):
        result = run_phase3(self.exp)
        self.assertTrue(len(result.cautelas) >= 2)

    def test_warnings_propagated_from_phase1(self):
        p1 = dict(_PHASE1_CON_RESIDUOS)
        p1["warnings"] = ["advertencia-test-fase1"]
        ci = self.exp / "control_interno"
        _write_json(p1, ci / "phase1_result.json")
        result = run_phase3(self.exp)
        warnings_text = " ".join(result.warnings)
        self.assertIn("advertencia-test-fase1", warnings_text)

    def test_phase2_json_invalid_handled(self):
        ci = self.exp / "control_interno"
        (ci / "phase2_result.json").write_text("INVALID JSON", encoding="utf-8")
        result = run_phase3(self.exp)
        warnings_text = " ".join(result.warnings)
        self.assertIn("JSON inválido", warnings_text)


# ---------------------------------------------------------------------------
# TestRunPhase3WriteOutputs
# ---------------------------------------------------------------------------

class TestRunPhase3WriteOutputs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-write"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        _write_json(_PHASE1_MINIMO, ci / "phase1_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_write_by_default(self):
        run_phase3(self.exp)
        ci = self.exp / "control_interno"
        self.assertFalse((ci / "phase3_result.json").exists())
        self.assertFalse((ci / "nota_encuadre_legal.md").exists())

    def test_write_creates_json(self):
        run_phase3(self.exp, write_outputs=True)
        self.assertTrue((self.exp / "control_interno" / "phase3_result.json").exists())

    def test_write_creates_md(self):
        run_phase3(self.exp, write_outputs=True)
        self.assertTrue((self.exp / "control_interno" / "nota_encuadre_legal.md").exists())

    def test_json_valid(self):
        run_phase3(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "phase3_result.json").read_text(encoding="utf-8")
        data = json.loads(content)
        self.assertIn("expediente_id", data)
        self.assertIn("normativa", data)
        self.assertIn("procedimiento_eia", data)

    def test_md_contains_header(self):
        run_phase3(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "nota_encuadre_legal.md").read_text(encoding="utf-8")
        self.assertIn("Nota de Encuadre Legal", content)

    def test_custom_output_dir(self):
        p1_path = self.exp / "control_interno" / "phase1_result.json"
        run_phase3(self.exp, phase1_result_path=p1_path, write_outputs=True, output_dir="salidas")
        self.assertTrue((self.exp / "salidas" / "phase3_result.json").exists())
        self.assertTrue((self.exp / "salidas" / "nota_encuadre_legal.md").exists())

    def test_json_fields_complete(self):
        run_phase3(self.exp, write_outputs=True)
        content = (self.exp / "control_interno" / "phase3_result.json").read_text(encoding="utf-8")
        data = json.loads(content)
        for key in ("expediente_id", "normativa", "procedimiento_eia",
                    "razones_procedimiento", "cautelas", "warnings", "notes"):
            self.assertIn(key, data)


# ---------------------------------------------------------------------------
# TestRunPhase3OrdinariaPosible
# ---------------------------------------------------------------------------

class TestRunPhase3OrdinariaPosible(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.exp = Path(self.tmpdir.name) / "expediente-alta-cap"
        self.exp.mkdir()
        ci = self.exp / "control_interno"
        ci.mkdir()
        p1 = dict(_PHASE1_MINIMO)
        p1["candidate_facts"] = [
            {
                "id": "CF-001",
                "categoria": "operaciones",
                "campo": "operacion_residuos",
                "valor": "R1201",
                "estado": "DECLARADO",
                "fuentes": ["doc.docx"],
                "entity_type": "OPERACION_RESIDUOS",
                "confidence": "HIGH",
                "context": "posible fraccionamiento del proyecto en varias fases",
                "normalized_value": None,
                "notes": [],
            }
        ]
        _write_json(p1, ci / "phase1_result.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ordinaria_posible_when_fraccionamiento(self):
        result = run_phase3(self.exp)
        self.assertEqual(result.procedimiento_eia, "ORDINARIA_POSIBLE")

    def test_cautela_tn07_present(self):
        result = run_phase3(self.exp)
        text = " ".join(result.cautelas)
        self.assertIn("CAUTELA-TN-07", text)


# ---------------------------------------------------------------------------
# TestCLIPhase3
# ---------------------------------------------------------------------------

class TestCLIPhase3(unittest.TestCase):
    def _run(self, *args) -> tuple[int, str, str]:
        result = subprocess.run(
            [sys.executable, "run_expediente.py"] + list(args),
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        return result.returncode, result.stdout, result.stderr

    def test_phase3_sin_phase1_exit1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-cli-test"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            code, out, err = self._run(str(exp), "phase3")
            self.assertEqual(code, 1)

    def test_phase3_sin_phase1_mensaje_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-cli-test"
            exp.mkdir()
            (exp / "control_interno").mkdir()
            code, out, err = self._run(str(exp), "phase3")
            self.assertIn("phase1", err.lower())

    def test_phase3_sin_write_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-cli-test"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(_PHASE1_MINIMO, ci / "phase1_result.json")
            code, out, err = self._run(str(exp), "phase3")
            self.assertEqual(code, 0)
            self.assertFalse((ci / "phase3_result.json").exists())

    def test_phase3_con_write_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "expediente-cli-test"
            exp.mkdir()
            ci = exp / "control_interno"
            ci.mkdir()
            _write_json(_PHASE1_MINIMO, ci / "phase1_result.json")
            code, out, err = self._run(str(exp), "phase3", "--write")
            self.assertEqual(code, 0)
            self.assertTrue((ci / "phase3_result.json").exists())
            self.assertTrue((ci / "nota_encuadre_legal.md").exists())

    def test_expediente_inexistente_exit1(self):
        code, out, err = self._run("/ruta/que/no/existe/expediente", "phase3")
        self.assertEqual(code, 1)


# ---------------------------------------------------------------------------
# TestRunPhase3PilotoParcela
# ---------------------------------------------------------------------------

_PARCELA = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-PARCELA"


@unittest.skipUnless(_PARCELA.exists(), "Piloto PARCELA no disponible")
class TestRunPhase3PilotoParcela(unittest.TestCase):
    def setUp(self):
        ci = _PARCELA / "control_interno"
        self.p1_path = ci / "phase1_result.json"
        if not self.p1_path.exists():
            self.skipTest("phase1_result.json no existe en PARCELA — ejecute phase1 --write primero")

    def test_solo_lectura_no_modifica_expediente(self):
        before = {
            p: p.stat().st_mtime
            for p in _PARCELA.rglob("*")
            if p.is_file()
        }
        run_phase3(_PARCELA)
        after = {
            p: p.stat().st_mtime
            for p in _PARCELA.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_returns_phase3result(self):
        result = run_phase3(_PARCELA)
        self.assertIsInstance(result, Phase3Result)

    def test_expediente_id_parcela(self):
        result = run_phase3(_PARCELA)
        self.assertEqual(result.expediente_id, "expediente-EIA-2026-RECIMETAL-PARCELA")

    def test_normativa_not_empty(self):
        result = run_phase3(_PARCELA)
        self.assertGreaterEqual(len(result.normativa), 2)


# ---------------------------------------------------------------------------
# TestRunPhase3PilotoNave222
# ---------------------------------------------------------------------------

_NAVE222 = Path(__file__).parent.parent / "expediente-EIA-2026-RECIMETAL-NAVE-222"


@unittest.skipUnless(_NAVE222.exists(), "Piloto NAVE-222 no disponible")
class TestRunPhase3PilotoNave222(unittest.TestCase):
    def setUp(self):
        ci = _NAVE222 / "control_interno"
        self.p1_path = ci / "phase1_result.json"
        if not self.p1_path.exists():
            self.skipTest("phase1_result.json no existe en NAVE-222 — ejecute phase1 --write primero")

    def test_solo_lectura_no_modifica_expediente(self):
        before = {
            p: p.stat().st_mtime
            for p in _NAVE222.rglob("*")
            if p.is_file()
        }
        run_phase3(_NAVE222)
        after = {
            p: p.stat().st_mtime
            for p in _NAVE222.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_returns_phase3result(self):
        result = run_phase3(_NAVE222)
        self.assertIsInstance(result, Phase3Result)


if __name__ == "__main__":
    unittest.main()
