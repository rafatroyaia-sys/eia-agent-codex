"""Tests para block_a_gap_visibility -- OB-04."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.block_a_gap_visibility import (
    GapVisibilityIssue,
    GapVisibilityResult,
    check_block_a_gap_visibility,
    check_block_a_gap_visibility_from_files,
    extract_markdown_section,
    is_identity_related_gap,
    load_gaps_json,
    normalize_criticality,
)

# ---------------------------------------------------------------------------
# Rutas de fixtures
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent

_BLOQUE_A_PARCELA = (
    _ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"
    / "bloques" / "A_identificacion_y_descripcion.md"
)
_GAPS_PARCELA = (
    _ROOT / "expediente-EIA-2026-RECIMETAL-PARCELA"
    / "capas" / "inferencias_y_gaps.json"
)

_BLOQUE_A_NAVE = (
    _ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"
    / "bloques" / "A_identificacion_y_descripcion.md"
)
_GAPS_NAVE = (
    _ROOT / "expediente-EIA-2026-RECIMETAL-NAVE-222"
    / "capas" / "inferencias_y_gaps.json"
)

# ---------------------------------------------------------------------------
# Fixtures sintéticos
# ---------------------------------------------------------------------------

_BLOQUE_A_SAMPLE = """\
# Bloque A — Identificación y descripción del proyecto

## A.1 Promotor y titular

La empresa promotora es EMPRESA TEST, S.L. (NIF B12345678).

GAP-001 relativo a la identificación del titular pendiente de verificación.

CONT-001 queda abierto por discrepancia de uso catastral declarado.

### A.1.1 Identificación administrativa

NIF y datos fiscales del promotor.

## A.2 Emplazamiento y situación

La parcela se ubica en coordenadas verificadas por Catastro.

## A.3 Descripción del proyecto

Descripción general del proyecto de gestión de residuos.

### A.3.1 Objeto evaluado y delimitación

El objeto evaluado comprende las operaciones R12 y R13.

GAP-002 documenta la falta de coordenadas UTM verificadas en la delimitación.

### A.3.2 Operaciones incluidas

Operaciones R1201 y R1301 incluidas en el expediente.

## A.4 Alternativas estudiadas

No procede evaluación de alternativas.

## A.8 Observaciones y gaps pendientes

GAP-003 referente al inventario forestal de la zona de influencia.

GAP-005 relativo a la referencia catastral no verificada.
"""

_GAPS_SAMPLE: list[dict] = [
    # identity-related, ALTA, visible en A.1 → INFO
    {"id": "GAP-001", "descripcion": "titular no verificado",
     "criticidad": "ALTA", "campo": "titular"},
    # identity-related, ALTA, visible en A.1 → INFO
    {"id": "CONT-001", "descripcion": "uso catastral vs declarado",
     "criticidad": "ALTA", "campo": "uso catastral"},
    # identity-related, ALTA, visible en A.3.1 → INFO
    {"id": "GAP-002", "descripcion": "coordenadas sin verificar",
     "criticidad": "ALTA", "campo": "coordenada"},
    # NOT identity-related (inventario forestal) → omitido
    {"id": "GAP-003", "descripcion": "inventario forestal de la zona",
     "criticidad": "ALTA", "campo": "flora"},
    # identity-related (parcela), MEDIA → omitido con only_high=True
    {"id": "GAP-004", "descripcion": "superficie parcela sin verificar",
     "criticidad": "MEDIA", "campo": "parcela"},
    # identity-related, ALTA, visible solo en A.8 → WARNING
    {"id": "GAP-005", "descripcion": "referencia catastral no verificada",
     "criticidad": "ALTA", "campo": "catastral"},
    # identity-related, ALTA, no visible en ningún lado → ERROR
    {"id": "GAP-006", "descripcion": "emplazamiento sin confirmar",
     "criticidad": "ALTA", "campo": "emplazamiento"},
]


# ---------------------------------------------------------------------------
# 1. extract_markdown_section
# ---------------------------------------------------------------------------

class TestExtractSection(unittest.TestCase):

    def test_extrae_a1(self):
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "## A.1")
        self.assertIn("GAP-001", text)
        self.assertIn("CONT-001", text)

    def test_a1_no_incluye_a2(self):
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "## A.1")
        self.assertNotIn("## A.2", text)

    def test_extrae_a31(self):
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "### A.3.1")
        self.assertIn("GAP-002", text)

    def test_a31_no_incluye_a32(self):
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "### A.3.1")
        self.assertNotIn("### A.3.2", text)

    def test_seccion_inexistente_devuelve_vacio(self):
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "## A.99")
        self.assertEqual(text, "")

    def test_a1_incluye_subsecciones(self):
        # A.1.1 es subsección de A.1; debe quedar dentro
        text = extract_markdown_section(_BLOQUE_A_SAMPLE, "## A.1")
        self.assertIn("A.1.1", text)

    def test_match_con_titulo_en_heading(self):
        bloque = "## A.1 Promotor y titular\ncontenido\n## A.2 Otro\n"
        text = extract_markdown_section(bloque, "## A.1")
        self.assertIn("contenido", text)
        self.assertNotIn("A.2", text)

    def test_seccion_al_final_del_documento(self):
        bloque = "## A.1\nfinal del documento sin más headings"
        text = extract_markdown_section(bloque, "## A.1")
        self.assertIn("final del documento", text)


# ---------------------------------------------------------------------------
# 2. normalize_criticality
# ---------------------------------------------------------------------------

class TestNormalizeCriticality(unittest.TestCase):

    def test_alta(self):
        self.assertEqual(normalize_criticality("ALTA"), "ALTA")

    def test_critica_con_tilde(self):
        self.assertEqual(normalize_criticality("CRÍTICA"), "ALTA")

    def test_critica_sin_tilde(self):
        self.assertEqual(normalize_criticality("CRITICA"), "ALTA")

    def test_bloqueante(self):
        self.assertEqual(normalize_criticality("BLOQUEANTE"), "ALTA")

    def test_critical_ingles(self):
        self.assertEqual(normalize_criticality("CRITICAL"), "ALTA")

    def test_media(self):
        self.assertEqual(normalize_criticality("MEDIA"), "MEDIA")

    def test_baja(self):
        self.assertEqual(normalize_criticality("BAJA"), "BAJA")

    def test_minusculas_aceptadas(self):
        self.assertEqual(normalize_criticality("alta"), "ALTA")
        self.assertEqual(normalize_criticality("media"), "MEDIA")


# ---------------------------------------------------------------------------
# 3. is_identity_related_gap
# ---------------------------------------------------------------------------

class TestIsIdentityRelated(unittest.TestCase):

    def test_titular_es_identidad(self):
        item = {"id": "GAP-001", "descripcion": "titular no verificado",
                "campo": "titular"}
        self.assertTrue(is_identity_related_gap(item))

    def test_referencia_catastral_es_identidad(self):
        item = {"id": "GAP-002", "descripcion": "referencia catastral no confirmada",
                "campo": "catastral"}
        self.assertTrue(is_identity_related_gap(item))

    def test_coordenada_es_identidad(self):
        item = {"id": "GAP-003", "descripcion": "coordenadas sin verificar",
                "campo": "coordenada"}
        self.assertTrue(is_identity_related_gap(item))

    def test_uso_catastral_es_identidad(self):
        item = {"id": "CONT-001", "descripcion": "uso catastral vs uso declarado",
                "campo": "uso catastral"}
        self.assertTrue(is_identity_related_gap(item))

    def test_objeto_evaluado_es_identidad(self):
        item = {"id": "GAP-004", "descripcion": "delimitación del objeto evaluado incompleta"}
        self.assertTrue(is_identity_related_gap(item))

    def test_emplazamiento_es_identidad(self):
        item = {"id": "GAP-005", "campo": "emplazamiento",
                "descripcion": "ubicación sin confirmar"}
        self.assertTrue(is_identity_related_gap(item))

    def test_impacto_fauna_no_es_identidad(self):
        item = {"id": "GAP-X", "descripcion": "impacto sobre fauna amenazada",
                "campo": "fauna"}
        self.assertFalse(is_identity_related_gap(item))

    def test_ruido_no_es_identidad(self):
        item = {"id": "GAP-Y", "descripcion": "nivel de ruido nocturno superado",
                "campo": "ruido"}
        self.assertFalse(is_identity_related_gap(item))

    def test_inventario_forestal_no_es_identidad(self):
        item = {"id": "GAP-Z", "descripcion": "inventario forestal incompleto",
                "campo": "flora"}
        self.assertFalse(is_identity_related_gap(item))


# ---------------------------------------------------------------------------
# 4. check_block_a_gap_visibility — validación de visibilidad
# ---------------------------------------------------------------------------

class TestCheckVisibility(unittest.TestCase):

    def test_gap_visible_en_a1(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertIn("GAP-001", result.visible_gaps)

    def test_gap_visible_en_a31(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertIn("GAP-002", result.visible_gaps)

    def test_gap_visible_solo_en_a8_genera_warning(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        gap5_issues = [i for i in result.issues
                       if i.gap_id == "GAP-005"]
        self.assertTrue(any(i.severity == "WARNING" for i in gap5_issues))

    def test_gap_visible_solo_en_a8_no_es_visible_pleno(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertNotIn("GAP-005", result.visible_gaps)
        self.assertIn("GAP-005", result.missing_gaps)

    def test_gap_no_visible_genera_error(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        gap6_issues = [i for i in result.issues
                       if i.gap_id == "GAP-006" and i.severity == "ERROR"]
        self.assertGreater(len(gap6_issues), 0)

    def test_gap_no_visible_en_missing_gaps(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertIn("GAP-006", result.missing_gaps)

    def test_gap_media_no_chequeado_con_only_high(self):
        result = check_block_a_gap_visibility(
            _BLOQUE_A_SAMPLE, _GAPS_SAMPLE, only_high=True
        )
        self.assertNotIn("GAP-004", result.checked_gaps)

    def test_gap_media_chequeado_con_only_high_false(self):
        result = check_block_a_gap_visibility(
            _BLOQUE_A_SAMPLE, _GAPS_SAMPLE, only_high=False
        )
        self.assertIn("GAP-004", result.checked_gaps)

    def test_gap_no_identidad_no_chequeado(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertNotIn("GAP-003", result.checked_gaps)

    def test_sin_gaps_relevantes_passed_true(self):
        gaps_sin_identidad = [
            {"id": "GAP-X", "descripcion": "impacto acústico",
             "criticidad": "ALTA", "campo": "ruido"},
        ]
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, gaps_sin_identidad)
        self.assertTrue(result.passed)

    def test_sin_gaps_relevantes_genera_info(self):
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, [])
        self.assertEqual(result.info_count(), 1)
        self.assertTrue(result.passed)

    def test_resultado_mixto(self):
        # GAP-001 visible (A.1), GAP-006 no visible → error count > 0, visible > 0
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)
        self.assertGreater(len(result.visible_gaps), 0)
        self.assertGreater(len(result.missing_gaps), 0)

    def test_bloque_vacio_gaps_relevantes_es_error(self):
        gaps = [{"id": "GAP-001", "descripcion": "titular no verificado",
                 "criticidad": "ALTA", "campo": "titular"}]
        result = check_block_a_gap_visibility("", gaps)
        self.assertGreater(result.error_count(), 0)
        self.assertFalse(result.passed)

    def test_warning_no_bloquea(self):
        # GAP-005 solo aparece en A.8 → WARNING pero no ERROR
        gaps_solo_warning = [
            {"id": "GAP-005",
             "descripcion": "referencia catastral no verificada",
             "criticidad": "ALTA", "campo": "catastral"},
        ]
        result = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, gaps_solo_warning)
        self.assertGreater(result.warning_count(), 0)
        self.assertEqual(result.error_count(), 0)
        self.assertTrue(result.passed)


# ---------------------------------------------------------------------------
# 5. GapVisibilityResult — métodos
# ---------------------------------------------------------------------------

class TestGapVisibilityResultMethods(unittest.TestCase):

    def _make_result(self, issues, **kwargs) -> GapVisibilityResult:
        return GapVisibilityResult(
            passed=all(i.severity != "ERROR" for i in issues),
            checked_gaps=kwargs.get("checked", []),
            visible_gaps=kwargs.get("visible", []),
            missing_gaps=kwargs.get("missing", []),
            issues=issues,
        )

    def test_error_count(self):
        r = self._make_result([
            GapVisibilityIssue("ERROR", "OB04-E001", "GAP-001", "msg"),
            GapVisibilityIssue("WARNING", "OB04-W001", "GAP-002", "msg"),
        ])
        self.assertEqual(r.error_count(), 1)

    def test_warning_count(self):
        r = self._make_result([
            GapVisibilityIssue("WARNING", "OB04-W001", "GAP-001", "msg"),
            GapVisibilityIssue("WARNING", "OB04-W001", "GAP-002", "msg"),
        ])
        self.assertEqual(r.warning_count(), 2)

    def test_info_count(self):
        r = self._make_result([GapVisibilityIssue("INFO", "OB04-I001", None, "msg")])
        self.assertEqual(r.info_count(), 1)

    def test_is_blocked_con_error(self):
        r = self._make_result([GapVisibilityIssue("ERROR", "OB04-E001", "GAP-001", "msg")])
        self.assertTrue(r.is_blocked())

    def test_is_blocked_sin_error(self):
        r = self._make_result([GapVisibilityIssue("WARNING", "OB04-W001", "GAP-001", "msg")])
        self.assertFalse(r.is_blocked())

    def test_summary_contiene_estado(self):
        r = self._make_result([])
        s = r.summary()
        self.assertIn("OK", s)
        self.assertGreater(len(s), 0)

    def test_summary_con_error_contiene_incompleto(self):
        r = self._make_result([GapVisibilityIssue("ERROR", "OB04-E001", "GAP-001", "msg")])
        self.assertIn("INCOMPLETO", r.summary())


# ---------------------------------------------------------------------------
# 6. load_gaps_json
# ---------------------------------------------------------------------------

class TestLoadGapsJson(unittest.TestCase):

    def test_carga_lista_valida(self):
        data = [
            {"id": "GAP-001", "criticidad": "ALTA"},
            {"id": "GAP-002", "criticidad": "MEDIA"},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f)
            path = f.name
        result = load_gaps_json(path)
        self.assertEqual(len(result), 2)

    def test_archivo_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            load_gaps_json("/ruta/que/no/existe/gaps.json")

    def test_json_invalido(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{no es json válido")
            path = f.name
        with self.assertRaises(ValueError):
            load_gaps_json(path)

    def test_no_es_lista(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"id": "GAP-001"}, f)
            path = f.name
        with self.assertRaises(ValueError):
            load_gaps_json(path)


# ---------------------------------------------------------------------------
# 7. check_block_a_gap_visibility_from_files
# ---------------------------------------------------------------------------

class TestFromFiles(unittest.TestCase):

    def test_funciona_con_tempfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bloque_a = tmp_path / "bloque_a.md"
            gaps_json = tmp_path / "gaps.json"

            bloque_a.write_text(_BLOQUE_A_SAMPLE, encoding="utf-8")
            gaps_json.write_text(json.dumps(_GAPS_SAMPLE), encoding="utf-8")

            result = check_block_a_gap_visibility_from_files(bloque_a, gaps_json)
        self.assertIsInstance(result, GapVisibilityResult)

    def test_no_escribe_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bloque_a = tmp_path / "bloque_a.md"
            gaps_json = tmp_path / "gaps.json"
            bloque_a.write_text(_BLOQUE_A_SAMPLE, encoding="utf-8")
            gaps_json.write_text(json.dumps(_GAPS_SAMPLE), encoding="utf-8")

            files_before = set(tmp_path.iterdir())
            check_block_a_gap_visibility_from_files(bloque_a, gaps_json)
            files_after = set(tmp_path.iterdir())
        self.assertEqual(files_before, files_after)

    def test_bloque_a_inexistente_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            gaps_json = Path(tmp) / "gaps.json"
            gaps_json.write_text("[]", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                check_block_a_gap_visibility_from_files(
                    Path(tmp) / "no_existe.md", gaps_json
                )

    def test_gaps_json_inexistente_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            bloque_a = Path(tmp) / "bloque_a.md"
            bloque_a.write_text(_BLOQUE_A_SAMPLE, encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                check_block_a_gap_visibility_from_files(
                    bloque_a, Path(tmp) / "no_existe.json"
                )

    def test_resultado_coherente_con_funcion_directa(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bloque_a = tmp_path / "bloque_a.md"
            gaps_json = tmp_path / "gaps.json"
            bloque_a.write_text(_BLOQUE_A_SAMPLE, encoding="utf-8")
            gaps_json.write_text(json.dumps(_GAPS_SAMPLE), encoding="utf-8")

            result_files = check_block_a_gap_visibility_from_files(bloque_a, gaps_json)
            result_direct = check_block_a_gap_visibility(_BLOQUE_A_SAMPLE, _GAPS_SAMPLE)

        self.assertEqual(result_files.checked_gaps, result_direct.checked_gaps)
        self.assertEqual(result_files.visible_gaps, result_direct.visible_gaps)
        self.assertEqual(result_files.missing_gaps, result_direct.missing_gaps)


# ---------------------------------------------------------------------------
# 8. Fixture PARCELA — solo lectura (skipUnless)
# ---------------------------------------------------------------------------

_PARCELA_DISPONIBLE = _BLOQUE_A_PARCELA.exists() and _GAPS_PARCELA.exists()
_NAVE_DISPONIBLE = _BLOQUE_A_NAVE.exists() and _GAPS_NAVE.exists()


@unittest.skipUnless(_PARCELA_DISPONIBLE, "Fixture PARCELA (bloque A + gaps) no disponible")
class TestFixtureParcela(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mtime_bloque = _BLOQUE_A_PARCELA.stat().st_mtime
        cls.mtime_gaps = _GAPS_PARCELA.stat().st_mtime
        cls.result = check_block_a_gap_visibility_from_files(
            _BLOQUE_A_PARCELA, _GAPS_PARCELA
        )

    def test_mtime_bloque_sin_cambios(self):
        self.assertEqual(_BLOQUE_A_PARCELA.stat().st_mtime, self.mtime_bloque)

    def test_mtime_gaps_sin_cambios(self):
        self.assertEqual(_GAPS_PARCELA.stat().st_mtime, self.mtime_gaps)

    def test_result_es_gap_visibility_result(self):
        self.assertIsInstance(self.result, GapVisibilityResult)

    def test_summary_no_vacio(self):
        self.assertGreater(len(self.result.summary()), 0)

    def test_no_escritura_en_piloto(self):
        piloto_dir = _BLOQUE_A_PARCELA.parent.parent
        for f in piloto_dir.rglob("gap_visibility_result*"):
            self.fail(f"check escribió en piloto: {f}")


@unittest.skipUnless(_NAVE_DISPONIBLE, "Fixture NAVE-222 (bloque A + gaps) no disponible")
class TestFixtureNave222(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mtime_bloque = _BLOQUE_A_NAVE.stat().st_mtime
        cls.mtime_gaps = _GAPS_NAVE.stat().st_mtime
        cls.result = check_block_a_gap_visibility_from_files(
            _BLOQUE_A_NAVE, _GAPS_NAVE
        )

    def test_mtime_bloque_sin_cambios(self):
        self.assertEqual(_BLOQUE_A_NAVE.stat().st_mtime, self.mtime_bloque)

    def test_mtime_gaps_sin_cambios(self):
        self.assertEqual(_GAPS_NAVE.stat().st_mtime, self.mtime_gaps)

    def test_result_es_gap_visibility_result(self):
        self.assertIsInstance(self.result, GapVisibilityResult)

    def test_summary_no_vacio(self):
        self.assertGreater(len(self.result.summary()), 0)

    def test_no_escritura_en_piloto(self):
        piloto_dir = _BLOQUE_A_NAVE.parent.parent
        for f in piloto_dir.rglob("gap_visibility_result*"):
            self.fail(f"check escribió en piloto: {f}")


if __name__ == "__main__":
    unittest.main()
