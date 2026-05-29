"""
Tests para positive_impact_gap_validator -- RD-07.

Tests 100% offline: sin red, sin IA, sin APIs, sin modificacion de expedientes piloto.
Usan tempfile.TemporaryDirectory para expedientes sinteticos.
"""
import json
import tempfile
import unittest
from pathlib import Path

from eia_agent.core.positive_impact_gap_validator import (
    POSITIVE_GAP_STATUS,
    POSITIVE_GAP_SEVERITY,
    POSITIVE_SIGNIFICANCE_VALUES,
    HIGH_GAP_VALUES,
    UNCERTAINTY_KEYWORDS,
    PROHIBITED_POSITIVE_CLOSURE_PHRASES,
    PositiveGapIssue,
    PositiveGapValidationResult,
    normalize_positive_gap_text,
    impact_is_positive,
    extract_impact_gaps,
    impact_has_high_gap,
    impact_has_uncertainty_note,
    text_has_positive_uncertainty_note,
    text_has_prohibited_positive_closure,
    validate_positive_impact_gap,
    validate_positive_impacts_with_high_gaps,
    load_phase6_model_impacts_from_json,
    load_relevant_markdowns,
    validate_positive_gap_from_files,
    build_positive_gap_report_markdown,
    write_positive_gap_outputs,
)


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _make_impact(
    impact_id="IMP-001",
    nature="NEGATIVO",
    status="VALORADO",
    sig_wo="MODERADO",
    sig_w="MODERADO",
    description="",
    name="Impacto de prueba",
    data_gaps=None,
    notes=None,
    warnings=None,
) -> dict:
    return {
        "impact_id": impact_id,
        "nature": nature,
        "status": status,
        "significance_without_measures": sig_wo,
        "significance_with_measures": sig_w,
        "description": description,
        "name": name,
        "data_gaps": data_gaps or [],
        "notes": notes or [],
        "warnings": warnings or [],
    }


def _make_positive_impact_no_gap(**kwargs):
    kwargs.setdefault("nature", "POSITIVO")
    kwargs.setdefault("sig_wo", "POSITIVO_MODERADO")
    kwargs.setdefault("sig_w", "POSITIVO_MODERADO")
    kwargs.setdefault("status", "VALORADO")
    return _make_impact(**kwargs)


def _make_positive_impact_high_gap(**kwargs):
    kwargs.setdefault("nature", "POSITIVO")
    kwargs.setdefault("sig_wo", "POSITIVO_MODERADO")
    kwargs.setdefault("sig_w", "POSITIVO_MODERADO")
    kwargs.setdefault("status", "PENDIENTE_DATOS")
    return _make_impact(**kwargs)


def _write_model_json(dir_path: Path, impacts: list[dict], filename: str = "phase6_model_with_pva.json"):
    model = {"expediente_id": "TEST-001", "impacts": impacts, "measures": [], "pva_programs": []}
    path = dir_path / "impactos" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. normalize_positive_gap_text
# ---------------------------------------------------------------------------

class TestNormalizePositiveGapText(unittest.TestCase):

    def test_quita_tildes(self):
        result = normalize_positive_gap_text("Ácido ñoño")
        self.assertNotIn("Á", result)
        self.assertNotIn("ñ", result)

    def test_minusculas(self):
        result = normalize_positive_gap_text("IMPACTO POSITIVO")
        self.assertEqual(result, "impacto positivo")

    def test_compacta_espacios(self):
        result = normalize_positive_gap_text("  gap   alta  ")
        self.assertEqual(result, "gap alta")

    def test_tolera_none(self):
        result = normalize_positive_gap_text(None)
        self.assertEqual(result, "")

    def test_tolera_cadena_vacia(self):
        result = normalize_positive_gap_text("")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# 2. impact_is_positive
# ---------------------------------------------------------------------------

class TestImpactIsPositive(unittest.TestCase):

    def test_detecta_nature_positivo(self):
        imp = _make_impact(nature="POSITIVO")
        self.assertTrue(impact_is_positive(imp))

    def test_detecta_significance_positivo_moderado(self):
        imp = _make_impact(nature="INDETERMINADO", sig_wo="POSITIVO_MODERADO")
        self.assertTrue(impact_is_positive(imp))

    def test_detecta_significance_positivo_notable(self):
        imp = _make_impact(nature="INDETERMINADO", sig_w="POSITIVO_NOTABLE")
        self.assertTrue(impact_is_positive(imp))

    def test_detecta_descripcion_impacto_positivo_empleo(self):
        imp = _make_impact(
            nature="INDETERMINADO",
            sig_wo="NO_VALORADO",
            description="impacto positivo sobre el empleo local"
        )
        self.assertTrue(impact_is_positive(imp))

    def test_no_detecta_no_positivo(self):
        imp = _make_impact(
            nature="INDETERMINADO",
            sig_wo="NO_VALORADO",
            description="no positivo sobre la economia"
        )
        self.assertFalse(impact_is_positive(imp))

    def test_no_detecta_impacto_negativo(self):
        imp = _make_impact(nature="NEGATIVO", sig_wo="MODERADO")
        self.assertFalse(impact_is_positive(imp))

    def test_detecta_beneficioso_en_descripcion(self):
        imp = _make_impact(nature="INDETERMINADO", sig_wo="NO_VALORADO",
                           description="efecto beneficioso sobre la economia")
        self.assertTrue(impact_is_positive(imp))

    def test_no_detecta_mixto(self):
        imp = _make_impact(nature="MIXTO", sig_wo="MODERADO")
        self.assertFalse(impact_is_positive(imp))


# ---------------------------------------------------------------------------
# 3. extract_impact_gaps
# ---------------------------------------------------------------------------

class TestExtractImpactGaps(unittest.TestCase):

    def test_extrae_data_gaps_strings(self):
        imp = _make_impact(data_gaps=["GAP-FI-013-001", "GAP-FI-007-001"])
        gaps = extract_impact_gaps(imp)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0]["gap_id"], "GAP-FI-013-001")
        self.assertEqual(gaps[0]["source"], "data_gaps")

    def test_extrae_data_gaps_dicts(self):
        imp = {"impact_id": "IMP-001", "data_gaps": [
            {"gap_id": "GAP-001", "criticality": "ALTA", "description": "dato no acreditado"}
        ]}
        gaps = extract_impact_gaps(imp)
        self.assertEqual(gaps[0]["criticality"], "ALTA")
        self.assertEqual(gaps[0]["gap_id"], "GAP-001")

    def test_tolera_ausencia_de_gaps(self):
        imp = _make_impact(data_gaps=[])
        gaps = extract_impact_gaps(imp)
        self.assertEqual(gaps, [])

    def test_extrae_criticidad_de_texto(self):
        imp = _make_impact(data_gaps=["Gap criticidad ALTA sobre flora"])
        gaps = extract_impact_gaps(imp)
        self.assertEqual(gaps[0]["criticality"], "ALTA")

    def test_extrae_bloqueante_de_texto(self):
        imp = _make_impact(data_gaps=["Gap BLOQUEANTE datos hidrogeologia"])
        gaps = extract_impact_gaps(imp)
        self.assertEqual(gaps[0]["criticality"], "BLOQUEANTE")

    def test_extrae_campo_gaps_adicional(self):
        imp = {"impact_id": "IMP-002", "data_gaps": [], "gaps": [
            {"gap_id": "GAP-B", "criticality": "MEDIA"}
        ]}
        gaps = extract_impact_gaps(imp)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["source"], "gaps")


# ---------------------------------------------------------------------------
# 4. impact_has_high_gap
# ---------------------------------------------------------------------------

class TestImpactHasHighGap(unittest.TestCase):

    def test_criticality_alta_en_gap_dict(self):
        imp = {"impact_id": "IMP-001", "data_gaps": [
            {"gap_id": "GAP-001", "criticality": "ALTA"}
        ], "status": "VALORADO", "notes": [], "warnings": [], "description": "", "name": "x"}
        self.assertTrue(impact_has_high_gap(imp))

    def test_criticality_bloqueante_en_gap_dict(self):
        imp = {"impact_id": "IMP-001", "data_gaps": [
            {"gap_id": "GAP-001", "criticality": "BLOQUEANTE"}
        ], "status": "VALORADO", "notes": [], "warnings": [], "description": "", "name": "x"}
        self.assertTrue(impact_has_high_gap(imp))

    def test_criticality_media_no_es_alta(self):
        imp = {"impact_id": "IMP-001", "data_gaps": [
            {"gap_id": "GAP-001", "criticality": "MEDIA"}
        ], "status": "VALORADO", "notes": [], "warnings": [], "description": "", "name": "x"}
        # MEDIA no activa high_gap por criticality, pero si status es VALORADO y sin
        # otros marcadores, puede depender del status check
        # status VALORADO no es PENDIENTE_DATOS/INDETERMINADO
        self.assertFalse(impact_has_high_gap(imp))

    def test_status_pendiente_datos_con_gaps(self):
        imp = _make_impact(status="PENDIENTE_DATOS", data_gaps=["GAP-FI-013-001"])
        self.assertTrue(impact_has_high_gap(imp))

    def test_status_indeterminado(self):
        imp = _make_impact(status="INDETERMINADO")
        self.assertTrue(impact_has_high_gap(imp))

    def test_status_pendiente_datos_sin_gaps(self):
        imp = _make_impact(status="PENDIENTE_DATOS")
        # Solo status PENDIENTE_DATOS también activa high_gap
        self.assertTrue(impact_has_high_gap(imp))

    def test_nota_alta_en_notes(self):
        imp = _make_impact(
            status="VALORADO",
            notes=["dato no acreditado, incertidumbre alta sobre los valores"]
        )
        self.assertTrue(impact_has_high_gap(imp))

    def test_sin_gap_alta(self):
        imp = _make_impact(status="VALORADO")
        self.assertFalse(impact_has_high_gap(imp))


# ---------------------------------------------------------------------------
# 5. impact_has_uncertainty_note
# ---------------------------------------------------------------------------

class TestImpactHasUncertaintyNote(unittest.TestCase):

    def test_detecta_condicionado_en_notes(self):
        imp = _make_impact(notes=["condicionado a datos del promotor"])
        self.assertTrue(impact_has_uncertainty_note(imp))

    def test_detecta_no_compensa_en_notes(self):
        imp = _make_impact(notes=["no compensa los impactos negativos"])
        self.assertTrue(impact_has_uncertainty_note(imp))

    def test_detecta_pendiente_en_warnings(self):
        imp = _make_impact(warnings=["pendiente de confirmacion de datos"])
        self.assertTrue(impact_has_uncertainty_note(imp))

    def test_no_detecta_estimado_solo_en_description(self):
        # description con "estimado" no es nota editorial: la nota debe estar en notes/warnings
        # (lo que dispara W001, no E001)
        imp = _make_impact(description="impacto estimado sobre la economia local")
        self.assertFalse(impact_has_uncertainty_note(imp))

    def test_no_detecta_texto_cerrado(self):
        imp = _make_impact(
            notes=["impacto con beneficio verificado"],
            description="mejora economica acreditada"
        )
        self.assertFalse(impact_has_uncertainty_note(imp))

    def test_tolera_impacto_sin_texto(self):
        imp = _make_impact()
        self.assertFalse(impact_has_uncertainty_note(imp))


# ---------------------------------------------------------------------------
# 6. text_has_positive_uncertainty_note
# ---------------------------------------------------------------------------

class TestTextHasPositiveUncertaintyNote(unittest.TestCase):

    def test_texto_con_impact_id_y_incertidumbre(self):
        text = "El impacto IMP-001 es un impacto positivo condicionado a datos del promotor."
        self.assertTrue(text_has_positive_uncertainty_note(text, "IMP-001"))

    def test_texto_con_impact_id_sin_incertidumbre(self):
        text = "El impacto IMP-001 mejora el empleo local de forma acreditada."
        self.assertFalse(text_has_positive_uncertainty_note(text, "IMP-001"))

    def test_seccion_general_impactos_positivos_con_incertidumbre(self):
        text = "## Impactos positivos\n\nEstos impactos son estimados y pendientes de confirmacion."
        self.assertTrue(text_has_positive_uncertainty_note(text))

    def test_texto_normal_sin_incertidumbre(self):
        text = "La planta procesara residuos de manera eficiente."
        self.assertFalse(text_has_positive_uncertainty_note(text))

    def test_tolera_texto_vacio(self):
        self.assertFalse(text_has_positive_uncertainty_note(""))

    def test_sin_impact_id_busca_seccion_general(self):
        text = "El beneficio sobre la economia es estimado y sujeto a confirmacion."
        self.assertTrue(text_has_positive_uncertainty_note(text, None))


# ---------------------------------------------------------------------------
# 7. text_has_prohibited_positive_closure
# ---------------------------------------------------------------------------

class TestTextHasProhibitedPositiveClosure(unittest.TestCase):

    def test_detecta_compensa_impactos_negativos(self):
        text = "El proyecto compensa los impactos negativos generados."
        self.assertTrue(text_has_prohibited_positive_closure(text))

    def test_detecta_balance_ambiental_positivo(self):
        text = "El resultado es un balance ambiental positivo neto."
        self.assertTrue(text_has_prohibited_positive_closure(text))

    def test_permite_no_compensa_impactos_negativos(self):
        text = "Este impacto no compensa los impactos negativos del proyecto."
        self.assertFalse(text_has_prohibited_positive_closure(text))

    def test_permite_no_puede_compensar(self):
        text = "El impacto positivo no puede compensar los impactos negativos."
        self.assertFalse(text_has_prohibited_positive_closure(text))

    def test_detecta_plenamente_acreditado(self):
        text = "El beneficio economico queda plenamente acreditado."
        self.assertTrue(text_has_prohibited_positive_closure(text))

    def test_permite_no_se_considera_plenamente_acreditado(self):
        text = "Este beneficio no se considera plenamente acreditado."
        self.assertFalse(text_has_prohibited_positive_closure(text))

    def test_tolera_texto_vacio(self):
        self.assertFalse(text_has_prohibited_positive_closure(""))

    def test_detecta_mejora_garantizada(self):
        text = "La mejora garantizada del empleo local es un impacto positivo."
        self.assertTrue(text_has_prohibited_positive_closure(text))


# ---------------------------------------------------------------------------
# 8. validate_positive_impact_gap
# ---------------------------------------------------------------------------

class TestValidatePositiveImpactGap(unittest.TestCase):

    def test_impacto_no_positivo_sin_issues(self):
        imp = _make_impact(nature="NEGATIVO", sig_wo="MODERADO")
        issues = validate_positive_impact_gap(imp)
        self.assertEqual(issues, [])

    def test_positivo_con_gap_alta_sin_nota_genera_error(self):
        imp = _make_positive_impact_high_gap(impact_id="IMP-010")
        issues = validate_positive_impact_gap(imp)
        codes = [i.code for i in issues]
        self.assertIn("RD07-E001", codes)

    def test_positivo_con_gap_alta_y_nota_en_modelo_sin_error(self):
        imp = _make_positive_impact_high_gap(
            impact_id="IMP-010",
            notes=["condicionado a la confirmacion de datos del promotor"]
        )
        issues = validate_positive_impact_gap(imp)
        error_codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertNotIn("RD07-E001", error_codes)

    def test_positivo_con_gap_alta_y_clausula_compensacion_genera_error(self):
        imp = _make_positive_impact_high_gap(
            impact_id="IMP-010",
            notes=["condicionado a datos"],
            description="este impacto compensa los impactos negativos"
        )
        issues = validate_positive_impact_gap(imp)
        codes = [i.code for i in issues]
        self.assertIn("RD07-E002", codes)

    def test_positivo_con_gap_nota_modelo_sin_markdown_genera_warning_w002(self):
        imp = _make_positive_impact_high_gap(
            impact_id="IMP-010",
            notes=["condicionado a datos del promotor"]
        )
        # Proveer markdowns vacios (sin mencion del impacto)
        mds = {"documento/borrador.md": "Texto generico sin mencionar IMP-010."}
        issues = validate_positive_impact_gap(imp, mds)
        codes = [i.code for i in issues]
        self.assertIn("RD07-W002", codes)

    def test_positivo_con_gap_y_nota_en_markdown_sin_error_w002(self):
        imp = _make_positive_impact_high_gap(
            impact_id="IMP-010",
            notes=["condicionado a datos del promotor"]
        )
        mds = {"documento/borrador.md": "El impacto IMP-010 es positivo pero pendiente de confirmacion."}
        issues = validate_positive_impact_gap(imp, mds)
        warning_codes = [i.code for i in issues if i.severity == "WARNING"]
        self.assertNotIn("RD07-W002", warning_codes)

    def test_positivo_estimado_sin_gap_explicito_genera_warning_w001(self):
        imp = _make_impact(
            impact_id="IMP-020",
            nature="POSITIVO",
            status="PENDIENTE_DATOS",
            sig_wo="NO_VALORADO",
            sig_w="NO_VALORADO",
        )
        # Baja a SIN_DATOS pero sin nota -> debe tener W001
        # Pero impact_has_high_gap(imp) es True por PENDIENTE_DATOS
        # Entonces va al bloque de high_gap, no al bloque estimado
        # El bloque estimado (W001) solo aplica si NO hay high_gap
        # Este test verifica que sin nota da ERROR (no W001)
        issues = validate_positive_impact_gap(imp)
        error_codes = [i.code for i in issues if i.severity == "ERROR"]
        self.assertIn("RD07-E001", error_codes)

    def test_positivo_estimado_sin_high_gap_genera_warning_w001(self):
        # Status VALORADO, pero description dice "estimado" → W001
        imp = _make_impact(
            impact_id="IMP-021",
            nature="POSITIVO",
            status="VALORADO",  # No es PENDIENTE_DATOS
            sig_wo="POSITIVO_MODERADO",
            description="impacto positivo estimado sobre el empleo local",
        )
        issues = validate_positive_impact_gap(imp)
        codes = [i.code for i in issues]
        self.assertIn("RD07-W001", codes)


# ---------------------------------------------------------------------------
# 9. validate_positive_impacts_with_high_gaps
# ---------------------------------------------------------------------------

class TestValidatePositiveImpactsWithHighGaps(unittest.TestCase):

    def test_modelo_vacio_sin_datos(self):
        result = validate_positive_impacts_with_high_gaps([])
        self.assertEqual(result.status, "SIN_DATOS")

    def test_solo_negativos_ok(self):
        impacts = [
            _make_impact(nature="NEGATIVO"),
            _make_impact(impact_id="IMP-002", nature="NEGATIVO"),
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.positive_impacts, [])

    def test_positivo_sin_gaps_ok(self):
        impacts = [
            _make_positive_impact_no_gap(impact_id="IMP-001", status="VALORADO")
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        # Sin gaps de alta ni status de incertidumbre -> OK
        # Pero sig_wo = POSITIVO_MODERADO y status = VALORADO → no hay warning
        self.assertIn(result.status, ("OK", "CON_OBSERVACIONES"))

    def test_positivo_con_gap_alta_sin_nota_no_conforme(self):
        impacts = [
            _make_positive_impact_high_gap(impact_id="IMP-001")
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertIn("IMP-001", result.positive_impacts_with_high_gaps)

    def test_positivo_con_gap_alta_y_nota_ok(self):
        impacts = [
            _make_positive_impact_high_gap(
                impact_id="IMP-001",
                notes=["condicionado a datos del promotor, no compensa negativos"]
            )
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        self.assertEqual(result.status, "OK")
        self.assertIn("IMP-001", result.positive_impacts_with_high_gaps)
        error_codes = [i.code for i in result.issues if i.severity == "ERROR"]
        self.assertEqual(error_codes, [])

    def test_multiples_con_algunos_problematicos(self):
        impacts = [
            _make_impact(nature="NEGATIVO"),
            _make_positive_impact_high_gap(impact_id="IMP-002"),  # Sin nota → ERROR
            _make_positive_impact_no_gap(impact_id="IMP-003", status="VALORADO"),  # OK
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertIn("IMP-002", result.positive_impacts)

    def test_checked_impacts_contiene_todos(self):
        impacts = [
            _make_impact(nature="NEGATIVO"),
            _make_positive_impact_no_gap(impact_id="IMP-002", status="VALORADO"),
        ]
        result = validate_positive_impacts_with_high_gaps(impacts)
        self.assertIn("IMP-001", result.checked_impacts)
        self.assertIn("IMP-002", result.checked_impacts)

    def test_markdown_sources_registrados(self):
        impacts = [_make_positive_impact_high_gap(impact_id="IMP-001")]
        mds = {"bloque_c.md": "contenido c", "bloque_i.md": "contenido i"}
        result = validate_positive_impacts_with_high_gaps(impacts, mds)
        self.assertEqual(set(result.markdown_sources_checked), set(mds.keys()))


# ---------------------------------------------------------------------------
# 10. validate_positive_gap_from_files
# ---------------------------------------------------------------------------

class TestValidatePositiveGapFromFiles(unittest.TestCase):

    def test_expediente_sin_modelo_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_positive_gap_from_files(tmpdir)
        self.assertEqual(result.status, "SIN_DATOS")
        self.assertTrue(any("modelo" in w.lower() for w in result.warnings))

    def test_expediente_con_modelo_problematico(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [_make_positive_impact_high_gap(impact_id="IMP-001")]
            _write_model_json(exp, impacts)
            result = validate_positive_gap_from_files(exp)
        self.assertEqual(result.status, "NO_CONFORME")

    def test_expediente_con_modelo_correcto(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [
                _make_positive_impact_high_gap(
                    impact_id="IMP-001",
                    notes=["condicionado a confirmacion de datos del promotor"]
                )
            ]
            _write_model_json(exp, impacts)
            result = validate_positive_gap_from_files(exp)
        self.assertEqual(result.status, "OK")

    def test_expediente_con_modelo_y_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [
                _make_positive_impact_high_gap(
                    impact_id="IMP-001",
                    notes=["condicionado a datos del promotor"]
                )
            ]
            _write_model_json(exp, impacts)
            # Crear markdown con referencia al impacto y nota de incertidumbre
            doc_dir = exp / "documento"
            doc_dir.mkdir()
            (doc_dir / "documento_ambiental_borrador.md").write_text(
                "El impacto IMP-001 es un beneficio pendiente de confirmacion.",
                encoding="utf-8",
            )
            result = validate_positive_gap_from_files(exp)
        self.assertEqual(result.status, "OK")
        self.assertIn("documento/documento_ambiental_borrador.md", result.markdown_sources_checked)

    def test_expediente_busca_en_orden_de_candidatos(self):
        """Verifica que usa phase6_model_with_pva.json primero si existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            (exp / "impactos").mkdir()
            # Solo crear el ultimo candidato
            impacts_conesa = [_make_impact(nature="NEGATIVO")]
            (exp / "impactos" / "phase6_model_with_conesa.json").write_text(
                json.dumps({"expediente_id": "T", "impacts": impacts_conesa}),
                encoding="utf-8",
            )
            result = validate_positive_gap_from_files(exp)
        # Debe encontrar el modelo y devolver OK (sin positivos)
        self.assertNotEqual(result.status, "SIN_DATOS")


# ---------------------------------------------------------------------------
# 11. build_positive_gap_report_markdown
# ---------------------------------------------------------------------------

class TestBuildPositiveGapReportMarkdown(unittest.TestCase):

    def _make_result(self, status="OK", positives=None, high_gaps=None, issues=None):
        return PositiveGapValidationResult(
            status=status,
            checked_impacts=["IMP-001", "IMP-002"],
            positive_impacts=positives or ["IMP-002"],
            positive_impacts_with_high_gaps=high_gaps or [],
            markdown_sources_checked=["documento/borrador.md"],
            issues=issues or [],
        )

    def test_contiene_impactos_positivos(self):
        result = self._make_result(positives=["IMP-002", "IMP-003"])
        md = build_positive_gap_report_markdown(result)
        self.assertIn("IMP-002", md)
        self.assertIn("IMP-003", md)

    def test_contiene_advertencia_de_alcance(self):
        result = self._make_result()
        md = build_positive_gap_report_markdown(result)
        self.assertIn("no elimina incertidumbres", md)
        self.assertIn("administrative_ready", md)

    def test_contiene_secciones_requeridas(self):
        result = self._make_result()
        md = build_positive_gap_report_markdown(result)
        for section in ("1. Resumen", "2. Impactos positivos", "3. Impactos positivos con gap",
                        "4. Incidencias", "5. Recomendaciones", "6. Advertencia de alcance"):
            self.assertIn(section, md)

    def test_muestra_estado(self):
        result = self._make_result(status="NO_CONFORME")
        md = build_positive_gap_report_markdown(result)
        self.assertIn("NO_CONFORME", md)

    def test_muestra_incidencias(self):
        issues = [PositiveGapIssue(
            severity="ERROR", code="RD07-E001", impact_id="IMP-001",
            message="Falta nota de incertidumbre", recommendation="Añadir nota."
        )]
        result = self._make_result(status="NO_CONFORME", issues=issues)
        md = build_positive_gap_report_markdown(result)
        self.assertIn("RD07-E001", md)


# ---------------------------------------------------------------------------
# 12. write_positive_gap_outputs
# ---------------------------------------------------------------------------

class TestWritePositiveGapOutputs(unittest.TestCase):

    def test_escribe_json_y_md(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = PositiveGapValidationResult(
                status="OK",
                checked_impacts=["IMP-001"],
                positive_impacts=[],
            )
            json_path, md_path = write_positive_gap_outputs(result, tmpdir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertEqual(json_path.name, "positive_gap_result.json")
            self.assertEqual(md_path.name, "positive_gap_result.md")

    def test_json_cargable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = PositiveGapValidationResult(
                status="CON_OBSERVACIONES",
                checked_impacts=["IMP-001"],
                positive_impacts=["IMP-001"],
            )
            json_path, _ = write_positive_gap_outputs(result, tmpdir)
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["status"], "CON_OBSERVACIONES")
            self.assertFalse(loaded["administrative_ready"])
            self.assertIn("error_count", loaded)

    def test_crea_directorio_si_no_existe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "auditoria" / "nuevo"
            result = PositiveGapValidationResult(status="OK")
            write_positive_gap_outputs(result, output_dir)
            self.assertTrue(output_dir.exists())


# ---------------------------------------------------------------------------
# 13. CLI integration (sin --write)
# ---------------------------------------------------------------------------

class TestCLIPositiveGapValidator(unittest.TestCase):

    def _run_cli(self, args: list):
        import sys
        from io import StringIO
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            code = run_expediente.main(args)
        except SystemExit as exc:
            code = exc.code
        finally:
            sys.stdout = old_stdout
        return code

    def test_sin_write_no_escribe_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Sin modelo: SIN_DATOS, exit 0 (is_valid True con SIN_DATOS)
            code = self._run_cli([tmpdir, "audit-positive-gaps"])
            # No debe haber creado archivos de auditoria
            audit_dir = Path(tmpdir) / "auditoria"
            if audit_dir.exists():
                self.assertFalse((audit_dir / "positive_gap_result.json").exists())

    def test_exit_1_con_errores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [_make_positive_impact_high_gap(impact_id="IMP-001")]
            _write_model_json(exp, impacts)
            code = self._run_cli([tmpdir, "audit-positive-gaps"])
        self.assertEqual(code, 1)

    def test_exit_0_con_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [
                _make_positive_impact_high_gap(
                    impact_id="IMP-001",
                    notes=["condicionado a datos del promotor"]
                )
            ]
            _write_model_json(exp, impacts)
            code = self._run_cli([tmpdir, "audit-positive-gaps"])
        self.assertEqual(code, 0)

    def test_con_write_escribe_archivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            impacts = [_make_positive_impact_no_gap(impact_id="IMP-001", status="VALORADO")]
            _write_model_json(exp, impacts)
            code = self._run_cli([tmpdir, "audit-positive-gaps", "--write"])
            audit_dir = exp / "auditoria"
            self.assertTrue((audit_dir / "positive_gap_result.json").exists())
            self.assertTrue((audit_dir / "positive_gap_result.md").exists())


# ---------------------------------------------------------------------------
# 14. Constantes publicas
# ---------------------------------------------------------------------------

class TestConstantesPublicas(unittest.TestCase):

    def test_positive_gap_status_contiene_esperados(self):
        for key in ("OK", "CON_OBSERVACIONES", "NO_CONFORME", "SIN_DATOS"):
            self.assertIn(key, POSITIVE_GAP_STATUS)

    def test_positive_gap_severity_contiene_esperados(self):
        for key in ("ERROR", "WARNING", "INFO"):
            self.assertIn(key, POSITIVE_GAP_SEVERITY)

    def test_positive_significance_values_no_vacio(self):
        self.assertGreater(len(POSITIVE_SIGNIFICANCE_VALUES), 0)

    def test_high_gap_values_contiene_alta_y_bloqueante(self):
        self.assertIn("ALTA", HIGH_GAP_VALUES)
        self.assertIn("BLOQUEANTE", HIGH_GAP_VALUES)


# ---------------------------------------------------------------------------
# 15. load_relevant_markdowns
# ---------------------------------------------------------------------------

class TestLoadRelevantMarkdowns(unittest.TestCase):

    def test_directorio_vacio_devuelve_dict_vacio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            texts = load_relevant_markdowns(tmpdir)
        self.assertIsInstance(texts, dict)

    def test_lee_documento_borrador(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            (exp / "documento").mkdir()
            (exp / "documento" / "documento_ambiental_borrador.md").write_text(
                "Contenido del borrador", encoding="utf-8"
            )
            texts = load_relevant_markdowns(exp)
        self.assertIn("documento/documento_ambiental_borrador.md", texts)
        self.assertIn("Contenido del borrador", texts["documento/documento_ambiental_borrador.md"])

    def test_lee_markdowns_de_impactos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            (exp / "impactos").mkdir()
            (exp / "impactos" / "resumen.md").write_text("Resumen impactos", encoding="utf-8")
            texts = load_relevant_markdowns(exp)
        self.assertIn("impactos/resumen.md", texts)

    def test_lee_markdowns_de_bloques(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir)
            (exp / "bloques").mkdir()
            (exp / "bloques" / "bloque_c.md").write_text("Bloque C", encoding="utf-8")
            texts = load_relevant_markdowns(exp)
        self.assertIn("bloques/bloque_c.md", texts)


# ---------------------------------------------------------------------------
# 16. load_phase6_model_impacts_from_json
# ---------------------------------------------------------------------------

class TestLoadPhase6ModelImpactsFromJson(unittest.TestCase):

    def test_carga_impactos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            impacts = [_make_impact(), _make_impact(impact_id="IMP-002")]
            path.write_text(json.dumps({"impacts": impacts}), encoding="utf-8")
            loaded = load_phase6_model_impacts_from_json(path)
        self.assertEqual(len(loaded), 2)

    def test_archivo_inexistente_devuelve_lista_vacia(self):
        loaded = load_phase6_model_impacts_from_json("/ruta/que/no/existe.json")
        self.assertEqual(loaded, [])

    def test_json_invalido_devuelve_lista_vacia(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("{ no valid json }", encoding="utf-8")
            loaded = load_phase6_model_impacts_from_json(path)
        self.assertEqual(loaded, [])

    def test_sin_clave_impacts_devuelve_lista_vacia(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            path.write_text(json.dumps({"measures": []}), encoding="utf-8")
            loaded = load_phase6_model_impacts_from_json(path)
        self.assertEqual(loaded, [])


# ---------------------------------------------------------------------------
# 17. PositiveGapIssue y PositiveGapValidationResult
# ---------------------------------------------------------------------------

class TestDataclasses(unittest.TestCase):

    def test_positive_gap_issue_to_dict(self):
        issue = PositiveGapIssue(
            severity="ERROR", code="RD07-E001", impact_id="IMP-001",
            source="modelo", message="Test", recommendation="Rec.",
            evidence=["ev1"]
        )
        d = issue.to_dict()
        self.assertEqual(d["severity"], "ERROR")
        self.assertEqual(d["code"], "RD07-E001")
        self.assertEqual(d["evidence"], ["ev1"])

    def test_positive_gap_issue_summary(self):
        issue = PositiveGapIssue(severity="WARNING", code="RD07-W001", impact_id="IMP-002",
                                  message="Falta nota")
        s = issue.summary()
        self.assertIn("RD07-W001", s)
        self.assertIn("IMP-002", s)

    def test_result_error_count(self):
        result = PositiveGapValidationResult(
            status="NO_CONFORME",
            issues=[
                PositiveGapIssue(severity="ERROR", code="RD07-E001"),
                PositiveGapIssue(severity="WARNING", code="RD07-W001"),
            ]
        )
        self.assertEqual(result.error_count(), 1)
        self.assertEqual(result.warning_count(), 1)

    def test_result_is_valid_true_sin_errores(self):
        result = PositiveGapValidationResult(status="CON_OBSERVACIONES", issues=[
            PositiveGapIssue(severity="WARNING", code="RD07-W001")
        ])
        self.assertTrue(result.is_valid())

    def test_result_is_valid_false_con_errores(self):
        result = PositiveGapValidationResult(status="NO_CONFORME", issues=[
            PositiveGapIssue(severity="ERROR", code="RD07-E001")
        ])
        self.assertFalse(result.is_valid())

    def test_result_to_dict_administrative_ready_false(self):
        result = PositiveGapValidationResult(status="OK")
        d = result.to_dict()
        self.assertFalse(d["administrative_ready"])

    def test_result_summary_contiene_estado(self):
        result = PositiveGapValidationResult(status="NO_CONFORME")
        s = result.summary()
        self.assertIn("NO_CONFORME", s)


if __name__ == "__main__":
    unittest.main()
