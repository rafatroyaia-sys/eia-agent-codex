"""tests/test_object_scope_builder.py — Suite de tests para ObjectScopeBuilder (OB-01).

Cubre los criterios de cierre:
- from_classification extrae titular, RC, coordenadas, operaciones, superficie, capacidad
- overrides sobreescriben modo, operaciones_excluidas, at_activos, gaps
- to_markdown() contiene las 10 secciones obligatorias
- to_markdown() muestra NO DECLARADO cuando faltan datos
- estado_gate2 BLOQUEADO / PENDIENTE / APTO según datos
- write_object_scope_markdown y write_object_scope_json escriben en temp
- load_object_scope_json reconstruye ObjectScope; FileNotFoundError / ValueError
- solo lectura contra PARCELA (no modifica mtime)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import docx as python_docx

from eia_agent.core.evidence_state import EvidenceState
from eia_agent.core.entity_extractor import ExtractedEntity, ExtractionResult
from eia_agent.core.evidence_classifier import (
    ClassificationResult,
    CandidateFact,
    classify_entities,
)
from eia_agent.core.object_scope_builder import (
    ObjectScope,
    build_object_scope,
    load_object_scope_json,
    write_object_scope_json,
    write_object_scope_markdown,
)

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_DOCX_PARCELA = (
    _ROOT
    / "expediente-EIA-2026-RECIMETAL-PARCELA"
    / "inputs"
    / "memorias"
    / "Documento_Ambiental_RECIMETAL_Parcela_v6.docx"
)

_SECCIONES_OBLIGATORIAS = [
    "## 1. Identificación del promotor/titular",
    "## 2. Emplazamiento",
    "## 3. Operaciones autorizadas/solicitadas",
    "## 4. Operaciones excluidas del objeto evaluado",
    "## 5. Superficies y capacidades",
    "## 6. Modo de trabajo",
    "## 7. Asunciones de test activas",
    "## 8. Gaps identificados",
    "## 9. Estado del gate 2",
    "## 10. Fuentes documentales",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity(entity_type, value, confidence="HIGH", normalized_value=None):
    return ExtractedEntity(
        entity_type=entity_type,
        value=value,
        source="texto",
        confidence=confidence,
        normalized_value=normalized_value or value,
    )


def _classify(*entities):
    result = ExtractionResult(entities=list(entities))
    return classify_entities(result, "DOC-001", "test.docx")


def _full_classification() -> ClassificationResult:
    """ClassificationResult con todos los campos mínimos para APTO."""
    return _classify(
        _entity("PROMOTOR",             "EMPRESA TEST, S.L."),
        _entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"),
        _entity("COORDENADA",           "28.9234", normalized_value="DEC 28.9234"),
        _entity("OPERACION",            "R1201"),
    )


def _partial_classification() -> ClassificationResult:
    """Solo RC, sin titular ni operaciones."""
    return _classify(
        _entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"),
    )


def _empty_classification() -> ClassificationResult:
    return ClassificationResult()


# ---------------------------------------------------------------------------
# from_classification — extracción de campos
# ---------------------------------------------------------------------------

class TestFromClassification(unittest.TestCase):

    def test_extrae_titular(self):
        cl = _classify(_entity("PROMOTOR", "EMPRESA TEST, S.L."))
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertEqual(scope.titular, "EMPRESA TEST, S.L.")

    def test_extrae_rc(self):
        cl = _classify(_entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"))
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertEqual(scope.referencia_catastral, "2462302DS4026S0001GQ")

    def test_extrae_coordenadas_wgs84(self):
        cl = _classify(
            _entity("COORDENADA", "28.9234", normalized_value="DEC 28.9234")
        )
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIn("28.9234", scope.coordenadas_wgs84)

    def test_extrae_coordenadas_utm(self):
        cl = _classify(
            _entity("COORDENADA", "E: 642000", normalized_value="UTM E=642000")
        )
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertGreater(len(scope.coordenadas_utm), 0)

    def test_extrae_operaciones_incluidas(self):
        cl = _classify(
            _entity("OPERACION", "R1201", normalized_value="R1201"),
            _entity("OPERACION", "R13",   normalized_value="R13"),
        )
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIn("R1201", scope.operaciones_incluidas)
        self.assertIn("R13",   scope.operaciones_incluidas)

    def test_extrae_superficie(self):
        cl = _classify(
            _entity("SUPERFICIE_PARCELA", "2000 m²", normalized_value="2000 m²")
        )
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIsNotNone(scope.superficie_m2)
        self.assertIn("2000", scope.superficie_m2)

    def test_extrae_capacidad(self):
        cl = _classify(_entity("CAPACIDAD", "500 tm/día"))
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIsNotNone(scope.capacidad)

    def test_titular_none_si_no_hay_promotor(self):
        cl = _classify(_entity("LER", "17 04 05"))
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIsNone(scope.titular)

    def test_operaciones_excluidas_vacio_por_defecto(self):
        scope = ObjectScope.from_classification(_full_classification(), "EXP-001")
        self.assertEqual(scope.operaciones_excluidas, [])

    def test_modo_no_declarado_por_defecto(self):
        scope = ObjectScope.from_classification(_full_classification(), "EXP-001")
        self.assertEqual(scope.modo, "NO_DECLARADO")

    def test_at_activos_vacio_por_defecto(self):
        scope = ObjectScope.from_classification(_full_classification(), "EXP-001")
        self.assertEqual(scope.at_activos, [])

    def test_gaps_vacio_por_defecto(self):
        scope = ObjectScope.from_classification(_full_classification(), "EXP-001")
        self.assertEqual(scope.gaps, [])

    def test_fuentes_propagadas(self):
        scope = ObjectScope.from_classification(_full_classification(), "EXP-001")
        self.assertIn("DOC-001", scope.fuentes)

    def test_expediente_id_preservado(self):
        scope = ObjectScope.from_classification(_full_classification(), "MI-EXPEDIENTE")
        self.assertEqual(scope.expediente_id, "MI-EXPEDIENTE")

    def test_titular_high_confidence_preferido(self):
        cl = _classify(
            _entity("PROMOTOR", "EMPRESA HIGH, S.L.", confidence="HIGH"),
            _entity("PROMOTOR", "EMPRESA LOW, S.L.",  confidence="LOW"),
        )
        scope = ObjectScope.from_classification(cl, "EXP-001")
        self.assertIn("HIGH", scope.titular)


# ---------------------------------------------------------------------------
# build_object_scope — overrides
# ---------------------------------------------------------------------------

class TestOverrides(unittest.TestCase):

    def test_override_modo_gabinete(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"modo": "GABINETE"})
        self.assertEqual(scope.modo, "GABINETE")

    def test_override_modo_campo(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"modo": "CAMPO"})
        self.assertEqual(scope.modo, "CAMPO")

    def test_override_operaciones_excluidas(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"operaciones_excluidas": ["R1302", "R1303"]})
        self.assertEqual(scope.operaciones_excluidas, ["R1302", "R1303"])

    def test_override_at_activos(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"at_activos": ["AT-001: uso industrial asumido"]})
        self.assertIn("AT-001: uso industrial asumido", scope.at_activos)

    def test_override_gaps(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"gaps": ["RC sin verificar en Catastro"]})
        self.assertIn("RC sin verificar en Catastro", scope.gaps)

    def test_override_titular(self):
        scope = build_object_scope("EXP-001", _empty_classification(),
                                   overrides={"titular": "EMPRESA OVERRIDE, S.L."})
        self.assertEqual(scope.titular, "EMPRESA OVERRIDE, S.L.")

    def test_override_rc(self):
        scope = build_object_scope("EXP-001", _empty_classification(),
                                   overrides={"referencia_catastral": "9999999XX9999X9999XX"})
        self.assertEqual(scope.referencia_catastral, "9999999XX9999X9999XX")

    def test_modo_invalido_queda_como_no_declarado(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"modo": "INVENTADO"})
        self.assertEqual(scope.modo, "NO_DECLARADO")
        self.assertTrue(any("no reconocido" in n.lower() for n in scope.notes))

    def test_sin_classification_sin_overrides(self):
        scope = build_object_scope("EXP-001")
        self.assertIsNone(scope.titular)
        self.assertEqual(scope.estado_gate2, "BLOQUEADO")

    def test_overrides_solos_sin_classification(self):
        scope = build_object_scope(
            "EXP-001",
            overrides={
                "titular": "EMPRESA, S.L.",
                "referencia_catastral": "2462302DS4026S0001GQ",
                "coordenadas_wgs84": ["28.9234"],
                "operaciones_incluidas": ["R1201"],
            }
        )
        self.assertEqual(scope.estado_gate2, "APTO")


# ---------------------------------------------------------------------------
# Estado gate 2
# ---------------------------------------------------------------------------

class TestEstadoGate2(unittest.TestCase):

    def test_bloqueado_sin_datos(self):
        scope = build_object_scope("EXP-001", _empty_classification())
        self.assertEqual(scope.estado_gate2, "BLOQUEADO")

    def test_bloqueado_solo_operaciones(self):
        cl = _classify(_entity("OPERACION", "R1201", normalized_value="R1201"))
        scope = build_object_scope("EXP-001", cl)
        self.assertEqual(scope.estado_gate2, "BLOQUEADO")

    def test_pendiente_solo_rc(self):
        scope = build_object_scope("EXP-001", _partial_classification())
        self.assertEqual(scope.estado_gate2, "PENDIENTE")

    def test_pendiente_titular_y_rc_sin_coordenadas(self):
        cl = _classify(
            _entity("PROMOTOR",             "EMPRESA, S.L."),
            _entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"),
        )
        scope = build_object_scope("EXP-001", cl)
        self.assertEqual(scope.estado_gate2, "PENDIENTE")

    def test_pendiente_sin_operaciones(self):
        cl = _classify(
            _entity("PROMOTOR",             "EMPRESA, S.L."),
            _entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"),
            _entity("COORDENADA",           "28.9234", normalized_value="DEC 28.9234"),
        )
        scope = build_object_scope("EXP-001", cl)
        self.assertEqual(scope.estado_gate2, "PENDIENTE")

    def test_apto_todos_los_campos(self):
        scope = build_object_scope("EXP-001", _full_classification())
        self.assertEqual(scope.estado_gate2, "APTO")

    def test_apto_con_coordenadas_utm(self):
        cl = _classify(
            _entity("PROMOTOR",             "EMPRESA, S.L."),
            _entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"),
            _entity("COORDENADA",           "E: 642000", normalized_value="UTM E=642000"),
            _entity("OPERACION",            "R1201", normalized_value="R1201"),
        )
        scope = build_object_scope("EXP-001", cl)
        self.assertEqual(scope.estado_gate2, "APTO")

    def test_recalculo_tras_overrides(self):
        # Empieza BLOQUEADO, overrides lo llevan a APTO
        scope = build_object_scope(
            "EXP-001",
            _empty_classification(),
            overrides={
                "titular": "EMPRESA, S.L.",
                "referencia_catastral": "2462302DS4026S0001GQ",
                "coordenadas_wgs84": ["28.9234"],
                "operaciones_incluidas": ["R1201"],
            }
        )
        self.assertEqual(scope.estado_gate2, "APTO")


# ---------------------------------------------------------------------------
# to_markdown
# ---------------------------------------------------------------------------

class TestToMarkdown(unittest.TestCase):

    def test_contiene_10_secciones(self):
        scope = build_object_scope("EXP-001", _full_classification())
        md = scope.to_markdown()
        for seccion in _SECCIONES_OBLIGATORIAS:
            self.assertIn(seccion, md, f"Sección faltante: {seccion}")

    def test_no_declarado_cuando_faltan_datos(self):
        scope = build_object_scope("EXP-001", _empty_classification())
        md = scope.to_markdown()
        self.assertIn("NO DECLARADO", md)

    def test_titular_en_markdown(self):
        cl = _classify(_entity("PROMOTOR", "RECIMETAL LANZAROTE, S.L."))
        scope = build_object_scope("EXP-001", cl)
        md = scope.to_markdown()
        self.assertIn("RECIMETAL LANZAROTE, S.L.", md)

    def test_rc_en_markdown(self):
        cl = _classify(_entity("REFERENCIA_CATASTRAL", "2462302DS4026S0001GQ"))
        scope = build_object_scope("EXP-001", cl)
        md = scope.to_markdown()
        self.assertIn("2462302DS4026S0001GQ", md)

    def test_operaciones_en_markdown(self):
        cl = _classify(_entity("OPERACION", "R1201", normalized_value="R1201"))
        scope = build_object_scope("EXP-001", cl)
        md = scope.to_markdown()
        self.assertIn("R1201", md)

    def test_at_activos_visibles(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"at_activos": ["AT-001"]})
        md = scope.to_markdown()
        self.assertIn("AT-001", md)

    def test_gaps_visibles(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"gaps": ["RC pendiente"]})
        md = scope.to_markdown()
        self.assertIn("RC pendiente", md)

    def test_estado_gate2_en_markdown(self):
        scope = build_object_scope("EXP-001", _full_classification())
        md = scope.to_markdown()
        self.assertIn("APTO", md)

    def test_encabezado_con_expediente_id(self):
        scope = build_object_scope("MI-EXPEDIENTE-001", _empty_classification())
        md = scope.to_markdown()
        self.assertIn("MI-EXPEDIENTE-001", md)

    def test_modo_en_markdown(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"modo": "GABINETE"})
        md = scope.to_markdown()
        self.assertIn("GABINETE", md)

    def test_no_vacio(self):
        scope = build_object_scope("EXP-001", _empty_classification())
        self.assertTrue(len(scope.to_markdown()) > 0)


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------

class TestToDict(unittest.TestCase):

    def test_to_dict_tiene_campos_requeridos(self):
        scope = build_object_scope("EXP-001", _full_classification())
        d = scope.to_dict()
        for campo in ("expediente_id", "titular", "referencia_catastral",
                      "coordenadas_wgs84", "coordenadas_utm",
                      "operaciones_incluidas", "operaciones_excluidas",
                      "modo", "superficie_m2", "capacidad",
                      "at_activos", "gaps", "estado_gate2", "fuentes"):
            self.assertIn(campo, d)

    def test_from_dict_roundtrip(self):
        scope = build_object_scope("EXP-001", _full_classification(),
                                   overrides={"modo": "GABINETE",
                                              "gaps": ["Gap-1"]})
        d = scope.to_dict()
        scope2 = ObjectScope.from_dict(d)
        self.assertEqual(scope.expediente_id, scope2.expediente_id)
        self.assertEqual(scope.titular,       scope2.titular)
        self.assertEqual(scope.modo,          scope2.modo)
        self.assertEqual(scope.gaps,          scope2.gaps)
        self.assertEqual(scope.estado_gate2,  scope2.estado_gate2)

    def test_from_dict_error_si_faltan_campos(self):
        with self.assertRaises(ValueError):
            ObjectScope.from_dict({"expediente_id": "X"})


# ---------------------------------------------------------------------------
# write_object_scope_markdown
# ---------------------------------------------------------------------------

class TestWriteMarkdown(unittest.TestCase):

    def test_crea_archivo(self):
        scope = build_object_scope("EXP-001", _full_classification())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ficha.md"
            write_object_scope_markdown(scope, out)
            self.assertTrue(out.exists())

    def test_contenido_es_markdown(self):
        scope = build_object_scope("EXP-001", _full_classification())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ficha.md"
            write_object_scope_markdown(scope, out)
            contenido = out.read_text(encoding="utf-8")
        for seccion in _SECCIONES_OBLIGATORIAS:
            self.assertIn(seccion, contenido)

    def test_crea_directorio(self):
        scope = build_object_scope("EXP-001", _full_classification())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "subdir" / "profundo" / "ficha.md"
            write_object_scope_markdown(scope, out)
            self.assertTrue(out.exists())

    def test_retorna_path(self):
        scope = build_object_scope("EXP-001", _full_classification())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ficha.md"
            result = write_object_scope_markdown(scope, out)
        self.assertEqual(result, out)


# ---------------------------------------------------------------------------
# write_object_scope_json y load_object_scope_json
# ---------------------------------------------------------------------------

class TestWriteLoadJson(unittest.TestCase):

    def _build(self) -> ObjectScope:
        return build_object_scope("EXP-001", _full_classification(),
                                  overrides={"modo": "GABINETE",
                                             "at_activos": ["AT-001"],
                                             "gaps": ["RC sin verificar"]})

    def test_escribe_json(self):
        scope = self._build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scope.json"
            write_object_scope_json(scope, out)
            self.assertTrue(out.exists())

    def test_json_valido(self):
        scope = self._build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scope.json"
            write_object_scope_json(scope, out)
            data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("expediente_id", data)
        self.assertIn("estado_gate2", data)

    def test_crea_directorio(self):
        scope = self._build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "scope.json"
            write_object_scope_json(scope, out)
            self.assertTrue(out.exists())

    def test_retorna_path(self):
        scope = self._build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scope.json"
            result = write_object_scope_json(scope, out)
        self.assertEqual(result, out)

    def test_load_reconstruye_scope(self):
        scope = self._build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scope.json"
            write_object_scope_json(scope, out)
            loaded = load_object_scope_json(out)
        self.assertIsInstance(loaded, ObjectScope)
        self.assertEqual(loaded.expediente_id, scope.expediente_id)
        self.assertEqual(loaded.modo,          scope.modo)
        self.assertEqual(loaded.at_activos,    scope.at_activos)
        self.assertEqual(loaded.gaps,          scope.gaps)
        self.assertEqual(loaded.estado_gate2,  scope.estado_gate2)

    def test_load_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_object_scope_json("/ruta/que/no/existe/scope.json")

    def test_load_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.json"
            f.write_text("esto no es json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_object_scope_json(f)

    def test_load_json_sin_campos(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bad.json"
            f.write_text('{"expediente_id": "X"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_object_scope_json(f)


# ---------------------------------------------------------------------------
# Fixture real PARCELA — solo lectura
# ---------------------------------------------------------------------------

@unittest.skipUnless(
    _DOCX_PARCELA.exists(),
    f"Fixture PARCELA no disponible: {_DOCX_PARCELA}"
)
class TestFixtureParcela(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from eia_agent.core.evidence_classifier import classify_entities_from_docx
        cls.classification = classify_entities_from_docx(_DOCX_PARCELA, "DOC-001")
        cls.scope = build_object_scope(
            "expediente-EIA-2026-RECIMETAL-PARCELA",
            cls.classification,
            overrides={"modo": "GABINETE"},
        )

    def test_no_lanza_excepcion(self):
        self.assertIsInstance(self.scope, ObjectScope)

    def test_no_modifica_mtime(self):
        mtime_antes = os.path.getmtime(_DOCX_PARCELA)
        from eia_agent.core.evidence_classifier import classify_entities_from_docx
        cl = classify_entities_from_docx(_DOCX_PARCELA, "DOC-001")
        build_object_scope("EXP", cl)
        mtime_despues = os.path.getmtime(_DOCX_PARCELA)
        self.assertEqual(mtime_antes, mtime_despues)

    def test_detecta_rc(self):
        self.assertIsNotNone(self.scope.referencia_catastral)
        self.assertIn("2462302DS4026S0001GQ", self.scope.referencia_catastral)

    def test_detecta_promotor(self):
        self.assertIsNotNone(self.scope.titular)
        self.assertIn("RECIMETAL", self.scope.titular)

    def test_detecta_operaciones_o_pendiente(self):
        # PARCELA tiene operaciones en el documento → deben aparecer o
        # el estado debe ser al menos PENDIENTE
        self.assertIn(self.scope.estado_gate2, ("APTO", "PENDIENTE"))

    def test_modo_override_aplicado(self):
        self.assertEqual(self.scope.modo, "GABINETE")

    def test_to_markdown_no_vacio(self):
        md = self.scope.to_markdown()
        self.assertGreater(len(md), 0)

    def test_to_markdown_tiene_10_secciones(self):
        md = self.scope.to_markdown()
        for seccion in _SECCIONES_OBLIGATORIAS:
            self.assertIn(seccion, md, f"Sección faltante: {seccion}")

    def test_fuentes_contiene_doc001(self):
        self.assertIn("DOC-001", self.scope.fuentes)

    def test_no_escribe_en_directorio_piloto(self):
        piloto_dir = _DOCX_PARCELA.parent.parent.parent
        for f in piloto_dir.rglob("ficha_objeto_evaluado*"):
            self.fail(f"build_object_scope escribió en piloto: {f}")

    def test_write_solo_en_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_md = Path(tmp) / "ficha.md"
            out_json = Path(tmp) / "ficha.json"
            write_object_scope_markdown(self.scope, out_md)
            write_object_scope_json(self.scope, out_json)
            self.assertTrue(out_md.exists())
            self.assertTrue(out_json.exists())
        # Verificar que en el piloto no existe nada
        piloto_dir = _DOCX_PARCELA.parent.parent.parent
        self.assertFalse(any(piloto_dir.rglob("ficha_objeto_evaluado*")))


if __name__ == "__main__":
    unittest.main()
