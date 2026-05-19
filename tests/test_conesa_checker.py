"""
Tests para conesa_checker -- RD-06
Checker determinista de cobertura Conesa para impactos ambientales.

Usa unittest puro. Sin pytest, sin web, sin IA, sin llamadas externas.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.impact_model import (
    CONESA_ATTRIBUTE_NAMES,
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
    ProjectAction,
    ReceptorFactor,
)
from eia_agent.core.conesa_checker import (
    CONESA_CHECK_SEVERITY,
    CONESA_CHECK_STATUS,
    CONESA_REQUIRED_ATTRIBUTES,
    ConesaCheckIssue,
    ConesaCheckResult,
    build_conesa_check_report_markdown,
    detect_conesa_table_like_sections,
    extract_impact_ids_from_markdown,
    has_complete_conesa_attributes,
    impact_has_valid_conesa_explanation,
    missing_conesa_attributes,
    validate_conesa_coverage_from_files,
    validate_impact_conesa_coverage,
    validate_markdown_conesa_coverage,
    validate_phase6_conesa_coverage,
    write_conesa_check_outputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attrs_complete() -> ConesaAttributes:
    return ConesaAttributes(
        intensidad=4, extension=2, momento=4, persistencia=4,
        reversibilidad=2, sinergia=1, acumulacion=1, efecto=4,
        periodicidad=1, recuperabilidad=2,
    )


def _make_attrs_empty() -> ConesaAttributes:
    return ConesaAttributes()


def _make_impact(
    impact_id: str = "IMP-001",
    nature: str = "NEGATIVO",
    status: str = "PENDIENTE_DATOS",
    significance: str = "NO_VALORADO",
    attrs: ConesaAttributes | None = None,
    data_gaps: list | None = None,
    notes: list | None = None,
    warnings: list | None = None,
    description: str = "",
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id="FR-003",
        name="Impacto prueba",
        description=description,
        nature=nature,
        status=status,
        significance_without_measures=significance,
        conesa_attributes=attrs or _make_attrs_empty(),
        data_gaps=data_gaps or [],
        notes=notes or [],
        warnings=warnings or [],
    )


def _make_model(impacts: list[EnvironmentalImpact]) -> Phase6Model:
    return Phase6Model(
        expediente_id="EIA-TEST",
        actions=[ProjectAction(action_id="AC-001", name="Accion prueba")],
        receptor_factors=[
            ReceptorFactor(
                receptor_id="FR-003",
                inventory_factor_id="FI-003",
                name="Suelos",
                notes=["test"],
            )
        ],
        impacts=impacts,
    )


def _make_result_with(issues: list[ConesaCheckIssue], status: str = "NO_CONFORME") -> ConesaCheckResult:
    return ConesaCheckResult(
        status=status,
        checked_impacts=["IMP-001"],
        issues=issues,
    )


def _make_issue(
    severity: str = "ERROR",
    code: str = "CC-A001",
    impact_id: str = "IMP-001",
    message: str = "Mensaje de prueba",
) -> ConesaCheckIssue:
    return ConesaCheckIssue(
        severity=severity,
        code=code,
        impact_id=impact_id,
        message=message,
    )


# ---------------------------------------------------------------------------
# 1. has_complete_conesa_attributes
# ---------------------------------------------------------------------------


class TestHasCompleteConesaAttributes(unittest.TestCase):
    def test_con_10_atributos_positivos_true(self):
        impact = _make_impact(attrs=_make_attrs_complete())
        self.assertTrue(has_complete_conesa_attributes(impact))

    def test_con_atributo_none_false(self):
        attrs = _make_attrs_complete()
        attrs.intensidad = None
        impact = _make_impact(attrs=attrs)
        self.assertFalse(has_complete_conesa_attributes(impact))

    def test_con_valor_cero_false(self):
        attrs = _make_attrs_complete()
        attrs.extension = 0
        impact = _make_impact(attrs=attrs)
        self.assertFalse(has_complete_conesa_attributes(impact))

    def test_con_valor_negativo_false(self):
        attrs = _make_attrs_complete()
        attrs.momento = -1
        impact = _make_impact(attrs=attrs)
        self.assertFalse(has_complete_conesa_attributes(impact))

    def test_sin_atributos_false(self):
        impact = _make_impact(attrs=_make_attrs_empty())
        self.assertFalse(has_complete_conesa_attributes(impact))

    def test_10_atributos_son_requeridos(self):
        self.assertEqual(len(CONESA_REQUIRED_ATTRIBUTES), 10)


# ---------------------------------------------------------------------------
# 2. missing_conesa_attributes
# ---------------------------------------------------------------------------


class TestMissingConesaAttributes(unittest.TestCase):
    def test_lista_vacia_si_completo(self):
        impact = _make_impact(attrs=_make_attrs_complete())
        self.assertEqual(missing_conesa_attributes(impact), [])

    def test_devuelve_faltantes(self):
        attrs = ConesaAttributes(intensidad=4, extension=2)
        impact = _make_impact(attrs=attrs)
        missing = missing_conesa_attributes(impact)
        # Deben faltar los 8 restantes
        self.assertIn("momento", missing)
        self.assertIn("persistencia", missing)
        self.assertEqual(len(missing), 8)

    def test_valor_cero_es_invalido(self):
        attrs = _make_attrs_complete()
        attrs.sinergia = 0
        impact = _make_impact(attrs=attrs)
        missing = missing_conesa_attributes(impact)
        self.assertIn("sinergia", missing)

    def test_todos_none_devuelve_10(self):
        impact = _make_impact(attrs=_make_attrs_empty())
        missing = missing_conesa_attributes(impact)
        self.assertEqual(len(missing), 10)

    def test_nombres_correctos(self):
        attrs = ConesaAttributes(intensidad=4)
        impact = _make_impact(attrs=attrs)
        missing = missing_conesa_attributes(impact)
        for name in missing:
            self.assertIn(name, CONESA_ATTRIBUTE_NAMES)


# ---------------------------------------------------------------------------
# 3. impact_has_valid_conesa_explanation
# ---------------------------------------------------------------------------


class TestImpactHasValidConesaExplanation(unittest.TestCase):
    def test_indeterminado_con_data_gaps_true(self):
        impact = _make_impact(
            status="INDETERMINADO",
            data_gaps=["GAP-FI-010-001"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_pendiente_datos_con_data_gaps_true(self):
        impact = _make_impact(
            status="PENDIENTE_DATOS",
            data_gaps=["GAP-001"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_indeterminado_sin_explicacion_false(self):
        impact = _make_impact(
            status="INDETERMINADO",
            data_gaps=[],
            notes=[],
            warnings=[],
        )
        self.assertFalse(impact_has_valid_conesa_explanation(impact))

    def test_notes_con_keyword_gap_true(self):
        impact = _make_impact(
            status="PENDIENTE_DATOS",
            data_gaps=[],
            notes=["Hay un gap activo de campo necesario para esta valoracion"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_notes_con_at_activa_true(self):
        impact = _make_impact(
            notes=["AT activa: se asume dado provisional"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_notes_con_consulta_pendiente_true(self):
        impact = _make_impact(
            notes=["consulta pendiente al organismo competente"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_significance_indeterminado_con_gaps_true(self):
        impact = _make_impact(
            significance="INDETERMINADO",
            data_gaps=["GAP-001"],
        )
        self.assertTrue(impact_has_valid_conesa_explanation(impact))

    def test_sin_datos_false(self):
        impact = _make_impact(
            status="PENDIENTE_DATOS",
            data_gaps=[],
            notes=[],
        )
        self.assertFalse(impact_has_valid_conesa_explanation(impact))


# ---------------------------------------------------------------------------
# 4. validate_impact_conesa_coverage
# ---------------------------------------------------------------------------


class TestValidateImpactConesaCoverage(unittest.TestCase):
    def test_valorado_completo_sin_error(self):
        impact = _make_impact(
            status="VALORADO",
            significance="COMPATIBLE",
            attrs=_make_attrs_complete(),
        )
        issues = validate_impact_conesa_coverage(impact)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_valorado_incompleto_error(self):
        impact = _make_impact(
            status="VALORADO",
            significance="COMPATIBLE",
            attrs=_make_attrs_empty(),
        )
        issues = validate_impact_conesa_coverage(impact)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)
        codes = [i.code for i in errors]
        self.assertIn("CC-A001", codes)

    def test_valorado_no_valorado_significance_error(self):
        impact = _make_impact(
            status="VALORADO",
            significance="NO_VALORADO",
            attrs=_make_attrs_complete(),
        )
        issues = validate_impact_conesa_coverage(impact)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(any(i.code == "CC-A002" for i in errors))

    def test_compatible_sin_atributos_error(self):
        impact = _make_impact(
            status="IDENTIFICADO",
            significance="COMPATIBLE",
            attrs=_make_attrs_empty(),
        )
        issues = validate_impact_conesa_coverage(impact)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(any(i.code == "CC-B001" for i in errors))

    def test_severo_sin_atributos_error(self):
        impact = _make_impact(
            status="IDENTIFICADO",
            significance="SEVERO",
            attrs=_make_attrs_empty(),
        )
        issues = validate_impact_conesa_coverage(impact)
        errors = [i for i in issues if i.code == "CC-B001"]
        self.assertTrue(len(errors) > 0)

    def test_atributos_completos_no_valorado_warning(self):
        impact = _make_impact(
            status="IDENTIFICADO",
            significance="NO_VALORADO",
            attrs=_make_attrs_complete(),
        )
        issues = validate_impact_conesa_coverage(impact)
        warnings = [i for i in issues if i.severity == "WARNING" and i.code == "CC-C001"]
        self.assertTrue(len(warnings) > 0)

    def test_indeterminado_sin_gaps_error_o_warning(self):
        impact = _make_impact(
            status="INDETERMINADO",
            significance="INDETERMINADO",
            attrs=_make_attrs_empty(),
            data_gaps=[],
            notes=[],
        )
        issues = validate_impact_conesa_coverage(impact)
        d_issues = [i for i in issues if i.code == "CC-D001"]
        self.assertTrue(len(d_issues) > 0)

    def test_pendiente_datos_con_gaps_sin_error_d(self):
        impact = _make_impact(
            status="PENDIENTE_DATOS",
            data_gaps=["GAP-001"],
        )
        issues = validate_impact_conesa_coverage(impact)
        d_errors = [i for i in issues if i.code == "CC-D001" and i.severity == "ERROR"]
        self.assertEqual(len(d_errors), 0)

    def test_positivo_sin_nota_warning(self):
        impact = _make_impact(
            nature="POSITIVO",
            status="IDENTIFICADO",
            significance="POSITIVO_MODERADO",
            notes=[],
        )
        issues = validate_impact_conesa_coverage(impact)
        e_warnings = [i for i in issues if i.code == "CC-E001"]
        self.assertTrue(len(e_warnings) > 0)

    def test_positivo_con_nota_no_compensa_sin_warning_e(self):
        impact = _make_impact(
            nature="POSITIVO",
            notes=["No compensa impactos negativos segun regla de no compensacion"],
        )
        issues = validate_impact_conesa_coverage(impact)
        e_warnings = [i for i in issues if i.code == "CC-E001"]
        self.assertEqual(len(e_warnings), 0)

    def test_descartado_justificado_sin_justificacion_warning(self):
        impact = _make_impact(
            status="DESCARTADO_JUSTIFICADO",
            description="",
            notes=[],
            data_gaps=[],
        )
        issues = validate_impact_conesa_coverage(impact)
        f_warnings = [i for i in issues if i.code == "CC-F001"]
        self.assertTrue(len(f_warnings) > 0)

    def test_descartado_justificado_con_description_sin_warning_f(self):
        impact = _make_impact(
            status="DESCARTADO_JUSTIFICADO",
            description="Descartado porque el receptor no esta en el area de influencia",
        )
        issues = validate_impact_conesa_coverage(impact)
        f_warnings = [i for i in issues if i.code == "CC-F001"]
        self.assertEqual(len(f_warnings), 0)


# ---------------------------------------------------------------------------
# 5. validate_phase6_conesa_coverage
# ---------------------------------------------------------------------------


class TestValidatePhase6ConesaCoverage(unittest.TestCase):
    def test_modelo_sin_impactos_sin_datos(self):
        model = _make_model([])
        result = validate_phase6_conesa_coverage(model)
        self.assertEqual(result.status, "SIN_DATOS")

    def test_todos_validos_ok(self):
        impact = _make_impact(
            impact_id="IMP-001",
            status="VALORADO",
            significance="COMPATIBLE",
            attrs=_make_attrs_complete(),
        )
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertEqual(result.status, "OK")

    def test_con_error_no_conforme(self):
        impact = _make_impact(
            impact_id="IMP-001",
            status="VALORADO",
            significance="COMPATIBLE",
            attrs=_make_attrs_empty(),
        )
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertFalse(result.is_valid())

    def test_con_warning_con_observaciones(self):
        impact = _make_impact(
            impact_id="IMP-001",
            status="IDENTIFICADO",
            significance="NO_VALORADO",
            attrs=_make_attrs_complete(),
        )
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertEqual(result.status, "CON_OBSERVACIONES")
        self.assertTrue(result.is_valid())

    def test_no_muta_model(self):
        impact = _make_impact(
            impact_id="IMP-001",
            attrs=_make_attrs_complete(),
            significance="COMPATIBLE",
            status="VALORADO",
        )
        model = _make_model([impact])
        original_significancia = impact.significance_without_measures
        _ = validate_phase6_conesa_coverage(model)
        self.assertEqual(impact.significance_without_measures, original_significancia)

    def test_checked_impacts_lista(self):
        impact = _make_impact("IMP-001")
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertIn("IMP-001", result.checked_impacts)

    def test_valued_impacts_correctos(self):
        impact = _make_impact(
            impact_id="IMP-001",
            significance="MODERADO",
            attrs=_make_attrs_complete(),
            status="VALORADO",
        )
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertIn("IMP-001", result.valued_impacts)

    def test_indeterminate_impacts_correctos(self):
        impact = _make_impact(
            impact_id="IMP-001",
            status="INDETERMINADO",
            data_gaps=["GAP-001"],
        )
        model = _make_model([impact])
        result = validate_phase6_conesa_coverage(model)
        self.assertIn("IMP-001", result.indeterminate_impacts)

    def test_administrative_ready_false(self):
        model = _make_model([_make_impact()])
        result = validate_phase6_conesa_coverage(model)
        self.assertFalse(result.administrative_ready)


# ---------------------------------------------------------------------------
# 6. extract_impact_ids_from_markdown
# ---------------------------------------------------------------------------


class TestExtractImpactIdsFromMarkdown(unittest.TestCase):
    def test_detecta_imp_001(self):
        md = "El impacto IMP-001 ha sido valorado como compatible."
        result = extract_impact_ids_from_markdown(md)
        self.assertIn("IMP-001", result)

    def test_detecta_multiples(self):
        md = "IMP-001 es compatible. IMP-002 es moderado. IMP-003 es indeterminado."
        result = extract_impact_ids_from_markdown(md)
        self.assertEqual(len(result), 3)
        self.assertIn("IMP-001", result)
        self.assertIn("IMP-002", result)
        self.assertIn("IMP-003", result)

    def test_no_duplica(self):
        md = "IMP-001 aparece. Ver también IMP-001 en la tabla."
        result = extract_impact_ids_from_markdown(md)
        self.assertEqual(result.count("IMP-001"), 1)

    def test_case_insensitive(self):
        md = "imp-001 en minusculas."
        result = extract_impact_ids_from_markdown(md)
        self.assertIn("IMP-001", result)

    def test_sin_imp_lista_vacia(self):
        md = "Texto sin ningun impacto identificado."
        result = extract_impact_ids_from_markdown(md)
        self.assertEqual(result, [])

    def test_preserva_orden_aparicion(self):
        md = "IMP-003 luego IMP-001 luego IMP-002"
        result = extract_impact_ids_from_markdown(md)
        self.assertEqual(result[0], "IMP-003")
        self.assertEqual(result[1], "IMP-001")


# ---------------------------------------------------------------------------
# 7. detect_conesa_table_like_sections
# ---------------------------------------------------------------------------


class TestDetectConesaTableLikeSections(unittest.TestCase):
    def _md_with_conesa(self, imp_id: str) -> str:
        return (
            f"### {imp_id}\n"
            f"| Atributo | Valor |\n"
            f"| intensidad | 4 |\n"
            f"| extension | 2 |\n"
            f"| momento | 4 |\n"
            f"| persistencia | 4 |\n"
            f"| reversibilidad | 2 |\n"
            f"| importancia | 32 |\n"
            f"Significancia: COMPATIBLE\n"
        )

    def test_detecta_tabla_con_atributos(self):
        md = self._md_with_conesa("IMP-001")
        result = detect_conesa_table_like_sections(md)
        self.assertIn("IMP-001", result)
        # Debe encontrar palabras clave de Conesa
        self.assertTrue(len(result["IMP-001"]) > 0)

    def test_detecta_intensidad(self):
        md = "IMP-001: intensidad 4, extension 2, significancia MODERADO"
        result = detect_conesa_table_like_sections(md)
        self.assertIn("IMP-001", result)
        self.assertIn("intensidad", result["IMP-001"])

    def test_sin_vocabulario_conesa_lista_vacia(self):
        md = "IMP-001 es un impacto sin mas descripcion."
        result = detect_conesa_table_like_sections(md)
        self.assertIn("IMP-001", result)
        self.assertEqual(len(result["IMP-001"]), 0)

    def test_sin_imp_resultado_vacio(self):
        md = "Texto sin IMPs. Solo contenido general."
        result = detect_conesa_table_like_sections(md)
        self.assertEqual(result, {})

    def test_multiples_imp(self):
        md = (
            "IMP-001: intensidad 4 extension 2 conesa\n"
            "IMP-002: solo menciones sin vocabulario\n"
        )
        result = detect_conesa_table_like_sections(md)
        self.assertIn("IMP-001", result)
        self.assertIn("IMP-002", result)
        self.assertTrue(len(result["IMP-001"]) > 0)


# ---------------------------------------------------------------------------
# 8. validate_markdown_conesa_coverage
# ---------------------------------------------------------------------------


class TestValidateMarkdownConesaCoverage(unittest.TestCase):
    def _md_with_conesa(self, imp_id: str) -> str:
        return (
            f"{imp_id}: intensidad 4, extension 2, momento 4, "
            f"persistencia 4, reversibilidad 2, significancia COMPATIBLE conesa"
        )

    def test_imp_esperado_ausente_error(self):
        md = "Sin impactos mencionados."
        issues = validate_markdown_conesa_coverage(md, ["IMP-001"], "test.md")
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any(i.code == "CC-MD-001" for i in errors))

    def test_imp_presente_sin_conesa_warning(self):
        md = "IMP-001 esta presente pero no hay tabla Conesa."
        issues = validate_markdown_conesa_coverage(md, ["IMP-001"], "test.md")
        warnings = [i for i in issues if i.severity == "WARNING"]
        self.assertTrue(len(warnings) > 0)

    def test_imp_presente_con_tabla_info(self):
        md = self._md_with_conesa("IMP-001")
        issues = validate_markdown_conesa_coverage(md, ["IMP-001"], "test.md")
        infos = [i for i in issues if i.severity == "INFO"]
        self.assertTrue(len(infos) > 0)

    def test_imp_con_indeterminado_info(self):
        md = "IMP-001 esta indeterminado, pendiente de datos."
        issues = validate_markdown_conesa_coverage(md, ["IMP-001"], "test.md")
        # No debe dar ERROR (puede dar INFO)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_lista_vacia_sin_issues(self):
        md = "IMP-001 detallado."
        issues = validate_markdown_conesa_coverage(md, [], "test.md")
        self.assertEqual(len(issues), 0)

    def test_multiples_imp_algunos_ausentes(self):
        md = "IMP-001 presente. IMP-002 presente."
        issues = validate_markdown_conesa_coverage(
            md, ["IMP-001", "IMP-002", "IMP-003"], "test.md"
        )
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(any(i.impact_id == "IMP-003" for i in errors))


# ---------------------------------------------------------------------------
# 9. validate_conesa_coverage_from_files
# ---------------------------------------------------------------------------


class TestValidateConesaCoverageFromFiles(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self) -> Path:
        exp = self.tmp / "expediente-EIA-TEST"
        exp.mkdir()
        return exp

    def _write_model(self, exp: Path, impacts: list[dict]) -> None:
        impactos_dir = exp / "impactos"
        impactos_dir.mkdir(exist_ok=True)
        model_data = {
            "expediente_id": exp.name,
            "actions": [{"action_id": "AC-001", "name": "Accion", "action_type": "OPERACION"}],
            "receptor_factors": [
                {
                    "receptor_id": "FR-003",
                    "inventory_factor_id": "FI-003",
                    "name": "Suelos",
                    "notes": ["test"],
                }
            ],
            "impacts": impacts,
            "measures": [],
            "pva_programs": [],
        }
        (impactos_dir / "phase6_model_with_pva.json").write_text(
            json.dumps(model_data), encoding="utf-8"
        )

    def _impact_dict(
        self,
        impact_id: str = "IMP-001",
        status: str = "PENDIENTE_DATOS",
        significance: str = "NO_VALORADO",
        attrs: dict | None = None,
    ) -> dict:
        default_attrs = {k: None for k in CONESA_ATTRIBUTE_NAMES}
        if attrs:
            default_attrs.update(attrs)
        return {
            "impact_id": impact_id,
            "action_id": "AC-001",
            "receptor_id": "FR-003",
            "name": "Impacto prueba",
            "description": "",
            "nature": "NEGATIVO",
            "status": status,
            "significance_without_measures": significance,
            "significance_with_measures": "NO_VALORADO",
            "conesa_attributes": default_attrs,
            "data_gaps": [],
            "source_refs": [],
            "measure_ids": [],
            "pva_ids": [],
            "warnings": [],
            "notes": [],
        }

    def test_expediente_vacio_sin_datos(self):
        exp = self._make_exp()
        result = validate_conesa_coverage_from_files(exp)
        self.assertEqual(result.status, "SIN_DATOS")

    def test_con_modelo_valido_ok(self):
        exp = self._make_exp()
        attrs = {k: 4 for k in CONESA_ATTRIBUTE_NAMES}
        self._write_model(exp, [self._impact_dict(
            "IMP-001", "VALORADO", "COMPATIBLE", attrs
        )])
        result = validate_conesa_coverage_from_files(exp)
        self.assertEqual(result.status, "OK")

    def test_con_modelo_invalido_no_conforme(self):
        exp = self._make_exp()
        self._write_model(exp, [self._impact_dict(
            "IMP-001", "VALORADO", "COMPATIBLE"  # sin atributos → ERROR
        )])
        result = validate_conesa_coverage_from_files(exp)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertFalse(result.is_valid())

    def test_expediente_no_existe_lanza_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            validate_conesa_coverage_from_files(self.tmp / "no_existe")

    def test_con_markdown_sin_modelo(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_C.md").write_text(
            "IMP-001 impacto compatible. intensidad 4 conesa", encoding="utf-8"
        )
        result = validate_conesa_coverage_from_files(exp)
        self.assertNotEqual(result.status, "SIN_DATOS")

    def test_modelo_con_impacto_ausente_en_md_warning(self):
        exp = self._make_exp()
        attrs = {k: 4 for k in CONESA_ATTRIBUTE_NAMES}
        self._write_model(exp, [self._impact_dict("IMP-001", "VALORADO", "COMPATIBLE", attrs)])
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_C.md").write_text(
            "Sin mencionar el impacto.", encoding="utf-8"
        )
        result = validate_conesa_coverage_from_files(exp)
        self.assertIn("IMP-001", result.impacts_missing_markdown)


# ---------------------------------------------------------------------------
# 10. Report markdown
# ---------------------------------------------------------------------------


class TestBuildConesaCheckReportMarkdown(unittest.TestCase):
    def setUp(self):
        issues = [
            _make_issue("ERROR", "CC-A001", "IMP-001", "Atributos incompletos"),
            _make_issue("WARNING", "CC-C001", "IMP-002", "Atributos completos sin valorar"),
        ]
        self.result = _make_result_with(issues, "NO_CONFORME")
        self.result.checked_impacts = ["IMP-001", "IMP-002"]
        self.result.valued_impacts = ["IMP-002"]
        self.result.indeterminate_impacts = []
        self.md = build_conesa_check_report_markdown(self.result)

    def test_contiene_header(self):
        self.assertIn("# Auditoria de cobertura Conesa", self.md)

    def test_contiene_resumen(self):
        self.assertIn("## 1. Resumen", self.md)

    def test_contiene_impactos_revisados(self):
        self.assertIn("## 2. Impactos revisados", self.md)

    def test_contiene_advertencia_no_aptitud(self):
        md_lower = self.md.lower()
        self.assertIn("no declara", md_lower)
        self.assertIn("aptitud administrativa", md_lower)

    def test_contiene_estado(self):
        self.assertIn("NO_CONFORME", self.md)

    def test_contiene_impact_id(self):
        self.assertIn("IMP-001", self.md)

    def test_seccion_advertencia_alcance(self):
        self.assertIn("## 9. Advertencia de alcance", self.md)


# ---------------------------------------------------------------------------
# 11. Escritura
# ---------------------------------------------------------------------------


class TestWriteConesaCheckOutputs(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_escribe_json_y_md(self):
        result = ConesaCheckResult(status="OK")
        json_path, md_path = write_conesa_check_outputs(result, self.tmp)
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())

    def test_json_cargable(self):
        result = ConesaCheckResult(
            status="NO_CONFORME",
            issues=[_make_issue("ERROR")],
        )
        json_path, _ = write_conesa_check_outputs(result, self.tmp)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("status", data)
        self.assertIn("issues", data)

    def test_nombres_correctos(self):
        result = ConesaCheckResult(status="OK")
        json_path, md_path = write_conesa_check_outputs(result, self.tmp)
        self.assertEqual(json_path.name, "conesa_check_result.json")
        self.assertEqual(md_path.name, "conesa_check_result.md")

    def test_crea_directorio(self):
        result = ConesaCheckResult(status="OK")
        out = self.tmp / "sub" / "auditoria"
        write_conesa_check_outputs(result, out)
        self.assertTrue(out.exists())


# ---------------------------------------------------------------------------
# 12. CLI
# ---------------------------------------------------------------------------


class TestCLIAuditConesa(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self) -> Path:
        exp = self.tmp / "expediente-EIA-CLI"
        exp.mkdir()
        return exp

    def _run(self, args: list[str]) -> int:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import run_expediente
        return run_expediente.main(args)

    def test_sin_modelo_exit_0(self):
        exp = self._make_exp()
        rc = self._run([str(exp), "audit-conesa"])
        self.assertEqual(rc, 0)

    def test_con_modelo_ok_exit_0(self):
        exp = self._make_exp()
        impactos_dir = exp / "impactos"
        impactos_dir.mkdir()
        attrs = {k: 4 for k in CONESA_ATTRIBUTE_NAMES}
        model_data = {
            "expediente_id": "CLI-TEST",
            "actions": [{"action_id": "AC-001", "name": "A", "action_type": "OPERACION"}],
            "receptor_factors": [
                {
                    "receptor_id": "FR-003",
                    "inventory_factor_id": "FI-003",
                    "name": "Suelos",
                    "notes": ["test"],
                }
            ],
            "impacts": [
                {
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-003",
                    "name": "Impacto suelos",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "COMPATIBLE",
                    "significance_with_measures": "COMPATIBLE",
                    "conesa_attributes": attrs,
                    "data_gaps": [],
                    "source_refs": [],
                    "measure_ids": [],
                    "pva_ids": [],
                    "warnings": [],
                    "notes": [],
                    "description": "",
                }
            ],
            "measures": [],
            "pva_programs": [],
        }
        (impactos_dir / "phase6_model_with_pva.json").write_text(
            json.dumps(model_data), encoding="utf-8"
        )
        rc = self._run([str(exp), "audit-conesa"])
        self.assertEqual(rc, 0)

    def test_con_error_exit_1(self):
        exp = self._make_exp()
        impactos_dir = exp / "impactos"
        impactos_dir.mkdir()
        model_data = {
            "expediente_id": "CLI-TEST",
            "actions": [{"action_id": "AC-001", "name": "A", "action_type": "OPERACION"}],
            "receptor_factors": [
                {
                    "receptor_id": "FR-003",
                    "inventory_factor_id": "FI-003",
                    "name": "Suelos",
                    "notes": ["test"],
                }
            ],
            "impacts": [
                {
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-003",
                    "name": "Impacto sin Conesa",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "COMPATIBLE",
                    "significance_with_measures": "COMPATIBLE",
                    "conesa_attributes": {k: None for k in CONESA_ATTRIBUTE_NAMES},
                    "data_gaps": [],
                    "source_refs": [],
                    "measure_ids": [],
                    "pva_ids": [],
                    "warnings": [],
                    "notes": [],
                    "description": "",
                }
            ],
            "measures": [],
            "pva_programs": [],
        }
        (impactos_dir / "phase6_model_with_pva.json").write_text(
            json.dumps(model_data), encoding="utf-8"
        )
        rc = self._run([str(exp), "audit-conesa"])
        self.assertEqual(rc, 1)

    def test_sin_write_no_escribe(self):
        exp = self._make_exp()
        rc = self._run([str(exp), "audit-conesa"])
        json_path = exp / "auditoria" / "conesa_check_result.json"
        self.assertFalse(json_path.exists())

    def test_con_write_escribe_outputs(self):
        exp = self._make_exp()
        rc = self._run([str(exp), "audit-conesa", "--write"])
        json_path = exp / "auditoria" / "conesa_check_result.json"
        self.assertTrue(json_path.exists())


# ---------------------------------------------------------------------------
# Constantes y Dataclasses
# ---------------------------------------------------------------------------


class TestConstantesYDataclasses(unittest.TestCase):
    def test_severity_valores(self):
        self.assertIn("ERROR", CONESA_CHECK_SEVERITY)
        self.assertIn("WARNING", CONESA_CHECK_SEVERITY)
        self.assertIn("INFO", CONESA_CHECK_SEVERITY)

    def test_status_valores(self):
        self.assertIn("OK", CONESA_CHECK_STATUS)
        self.assertIn("NO_CONFORME", CONESA_CHECK_STATUS)
        self.assertIn("CON_OBSERVACIONES", CONESA_CHECK_STATUS)
        self.assertIn("SIN_DATOS", CONESA_CHECK_STATUS)

    def test_issue_severity_invalido(self):
        with self.assertRaises(ValueError):
            ConesaCheckIssue(
                severity="INVALIDO",
                code="X",
                impact_id="IMP-001",
                message="msg",
            )

    def test_result_error_count(self):
        issues = [_make_issue("ERROR"), _make_issue("WARNING")]
        result = _make_result_with(issues)
        self.assertEqual(result.error_count(), 1)
        self.assertEqual(result.warning_count(), 1)

    def test_result_is_valid_sin_errores(self):
        result = _make_result_with([_make_issue("WARNING")], "CON_OBSERVACIONES")
        self.assertTrue(result.is_valid())

    def test_result_is_valid_con_errores(self):
        result = _make_result_with([_make_issue("ERROR")], "NO_CONFORME")
        self.assertFalse(result.is_valid())

    def test_result_to_dict(self):
        result = _make_result_with([])
        d = result.to_dict()
        for campo in ("status", "issues", "error_count", "is_valid", "administrative_ready"):
            self.assertIn(campo, d)

    def test_result_administrative_ready_false(self):
        result = ConesaCheckResult(status="OK")
        self.assertFalse(result.administrative_ready)

    def test_issue_to_dict(self):
        issue = _make_issue()
        d = issue.to_dict()
        for campo in ("severity", "code", "impact_id", "message"):
            self.assertIn(campo, d)

    def test_issue_summary(self):
        issue = _make_issue("ERROR", "CC-A001", "IMP-001")
        s = issue.summary()
        self.assertIn("ERROR", s)
        self.assertIn("CC-A001", s)


if __name__ == "__main__":
    unittest.main()
