"""
Tests para block_consistency_validator -- RD-04
Validador de coherencia entre bloques del Documento Ambiental EIA.

Usa unittest puro. Sin pytest, sin web, sin IA, sin llamadas externas.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.block_consistency_validator import (
    BLOCK_FAMILIES,
    CONSISTENCY_SEVERITY,
    CONSISTENCY_STATUS,
    BlockConsistencyIssue,
    BlockConsistencyResult,
    build_block_consistency_report_markdown,
    detect_block_family,
    load_markdown_blocks,
    normalize_block_text,
    validate_assumption_consistency,
    validate_biodiversity_consistency,
    validate_block_consistency,
    validate_block_consistency_from_files,
    validate_conclusion_consistency,
    validate_heritage_consistency,
    validate_measure_consistency,
    validate_pva_consistency,
    validate_red_natura_consistency,
    write_block_consistency_outputs,
)
from eia_agent.core.assumption_test_system import (
    AsuncionTestRegistry,
    create_assumption_from_gap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    severity: str = "ERROR",
    code: str = "BC-TEST-001",
    source: str = "bloques/bloque_H.md",
    target: str = "bloques/bloque_J.md",
    message: str = "Mensaje de prueba",
    evidence: list | None = None,
) -> BlockConsistencyIssue:
    return BlockConsistencyIssue(
        severity=severity,
        code=code,
        source_block=source,
        target_block=target,
        message=message,
        evidence=evidence or ["frase detectada"],
        recommendation="Revisar",
    )


def _make_result_with(
    issues: list[BlockConsistencyIssue],
    status: str = "INCOHERENTE",
) -> BlockConsistencyResult:
    return BlockConsistencyResult(
        status=status,
        checked_blocks=["bloques/bloque_H.md", "bloques/bloque_J.md"],
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 1. normalize_block_text
# ---------------------------------------------------------------------------


class TestNormalizeBlockText(unittest.TestCase):
    def test_minusculas(self):
        result = normalize_block_text("Red Natura 2000")
        self.assertEqual(result, "red natura 2000")

    def test_quita_tildes(self):
        result = normalize_block_text("afección significativa")
        self.assertIn("afeccion significativa", result)

    def test_normaliza_espacios(self):
        result = normalize_block_text("texto   con   espacios")
        self.assertEqual(result, "texto con espacios")

    def test_conserva_codigo_fi(self):
        result = normalize_block_text("Factor FI-010 Red Natura")
        self.assertIn("fi-010", result)

    def test_conserva_codigo_imp(self):
        result = normalize_block_text("Impacto IMP-001 Indeterminado")
        self.assertIn("imp-001", result)

    def test_conserva_codigo_at(self):
        result = normalize_block_text("AT-001 activa en el expediente")
        self.assertIn("at-001", result)

    def test_conserva_codigo_gap(self):
        result = normalize_block_text("GAP-FI-007-001 campo necesario")
        self.assertIn("gap-fi-007-001", result)

    def test_conserva_codigo_med(self):
        result = normalize_block_text("MED-001 medida correctora")
        self.assertIn("med-001", result)

    def test_conserva_codigo_pva(self):
        result = normalize_block_text("PVA-001 programa de vigilancia")
        self.assertIn("pva-001", result)

    def test_vacio(self):
        self.assertEqual(normalize_block_text(""), "")


# ---------------------------------------------------------------------------
# 2. detect_block_family
# ---------------------------------------------------------------------------


class TestDetectBlockFamily(unittest.TestCase):
    def test_bloque_a(self):
        self.assertEqual(detect_block_family("bloques/bloque_A.md"), "A_IDENTIFICACION")

    def test_a_identificacion(self):
        self.assertEqual(detect_block_family("A_identificacion.md"), "A_IDENTIFICACION")

    def test_inventario_directorio(self):
        self.assertEqual(detect_block_family("inventario/FI-007_flora.md"), "B_INVENTARIO")

    def test_bloque_b(self):
        self.assertEqual(detect_block_family("bloque_B_inventario.md"), "B_INVENTARIO")

    def test_inventario_nombre(self):
        self.assertEqual(detect_block_family("inventario_ambiental.md"), "B_INVENTARIO")

    def test_impactos_directorio(self):
        self.assertEqual(detect_block_family("impactos/AG09_valoracion.md"), "C_IMPACTOS")

    def test_bloque_c(self):
        self.assertEqual(detect_block_family("bloque_C_impactos.md"), "C_IMPACTOS")

    def test_medidas(self):
        self.assertEqual(detect_block_family("bloque_D_medidas.md"), "D_MEDIDAS")

    def test_pva(self):
        self.assertEqual(detect_block_family("bloque_E_pva.md"), "E_PVA")

    def test_pva_directorio(self):
        self.assertEqual(detect_block_family("impactos/AG09_PVA.md"), "E_PVA")

    def test_red_natura(self):
        self.assertEqual(detect_block_family("bloque_H_red_natura.md"), "H_RED_NATURA")

    def test_bloque_h(self):
        self.assertEqual(detect_block_family("bloque_H.md"), "H_RED_NATURA")

    def test_conclusiones(self):
        self.assertEqual(detect_block_family("bloque_I_conclusiones.md"), "I_CONCLUSIONES")

    def test_rnt(self):
        self.assertEqual(detect_block_family("bloque_J_rnt.md"), "J_RNT")

    def test_resumen_no_tecnico(self):
        self.assertEqual(detect_block_family("bloque_J_resumen_no_tecnico.md"), "J_RNT")

    def test_anejo(self):
        self.assertEqual(detect_block_family("anejo_1.md"), "K_ANEXOS")

    def test_anexo(self):
        self.assertEqual(detect_block_family("anexo_cartografia.md"), "K_ANEXOS")

    def test_fallback_generico(self):
        self.assertEqual(detect_block_family("documento_cualquiera.md"), "GENERICO")

    def test_auditoria_directorio_generico(self):
        self.assertEqual(detect_block_family("auditoria/informe.md"), "GENERICO")


# ---------------------------------------------------------------------------
# 3. load_markdown_blocks
# ---------------------------------------------------------------------------


class TestLoadMarkdownBlocks(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self) -> Path:
        exp = self.tmp / "expediente-EIA-TEST"
        exp.mkdir()
        return exp

    def test_sin_markdowns_dict_vacio(self):
        exp = self._make_exp()
        blocks = load_markdown_blocks(exp)
        self.assertEqual(blocks, {})

    def test_carga_bloques_dir(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_H.md").write_text("Red Natura cautela", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertIn("bloques/bloque_H.md", blocks)
        self.assertIn("Red Natura cautela", blocks["bloques/bloque_H.md"])

    def test_carga_inventario_dir(self):
        exp = self._make_exp()
        (exp / "inventario").mkdir()
        (exp / "inventario" / "FI-007_flora.md").write_text("Flora gap pendiente", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertIn("inventario/FI-007_flora.md", blocks)

    def test_carga_impactos_dir(self):
        exp = self._make_exp()
        (exp / "impactos").mkdir()
        (exp / "impactos" / "valoracion.md").write_text("Impacto indeterminado", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertIn("impactos/valoracion.md", blocks)

    def test_carga_auditoria_dir(self):
        exp = self._make_exp()
        (exp / "auditoria").mkdir()
        (exp / "auditoria" / "art45.md").write_text("Checklist art45", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertIn("auditoria/art45.md", blocks)

    def test_no_carga_json(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "datos.json").write_text("{}", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertNotIn("bloques/datos.json", blocks)

    def test_no_carga_docs_proyecto(self):
        exp = self._make_exp()
        # No debe cargar docs/ del expediente si no es de las 4 carpetas
        (exp / "docs").mkdir()
        (exp / "docs" / "manual.md").write_text("Manual del sistema", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertNotIn("docs/manual.md", blocks)

    def test_multiples_bloques(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        for name in ("bloque_H.md", "bloque_I.md", "bloque_J.md"):
            (exp / "bloques" / name).write_text(f"Contenido {name}", encoding="utf-8")
        blocks = load_markdown_blocks(exp)
        self.assertEqual(len(blocks), 3)


# ---------------------------------------------------------------------------
# 4. Dataclasses
# ---------------------------------------------------------------------------


class TestBlockConsistencyIssue(unittest.TestCase):
    def test_to_dict_tiene_campos(self):
        issue = _make_issue()
        d = issue.to_dict()
        for campo in ("severity", "code", "source_block", "target_block", "message", "evidence"):
            self.assertIn(campo, d)

    def test_to_dict_serializable_json(self):
        issue = _make_issue()
        s = json.dumps(issue.to_dict())
        self.assertIsInstance(s, str)

    def test_summary_contiene_severity(self):
        issue = _make_issue(severity="ERROR")
        self.assertIn("ERROR", issue.summary())

    def test_summary_contiene_code(self):
        issue = _make_issue(code="BC-RN-001")
        self.assertIn("BC-RN-001", issue.summary())

    def test_severity_invalido_lanza_error(self):
        with self.assertRaises(ValueError):
            BlockConsistencyIssue(
                severity="INVALIDO",
                code="X",
                source_block="A",
                target_block="B",
                message="msg",
            )


class TestBlockConsistencyResult(unittest.TestCase):
    def test_error_count(self):
        issues = [_make_issue("ERROR"), _make_issue("WARNING")]
        result = _make_result_with(issues)
        self.assertEqual(result.error_count(), 1)

    def test_warning_count(self):
        issues = [_make_issue("ERROR"), _make_issue("WARNING"), _make_issue("WARNING")]
        result = _make_result_with(issues)
        self.assertEqual(result.warning_count(), 2)

    def test_info_count(self):
        issues = [_make_issue("INFO")]
        result = _make_result_with(issues, status="CON_OBSERVACIONES")
        self.assertEqual(result.info_count(), 1)

    def test_is_valid_sin_errores(self):
        issues = [_make_issue("WARNING")]
        result = _make_result_with(issues, status="CON_OBSERVACIONES")
        self.assertTrue(result.is_valid())

    def test_is_valid_con_errores(self):
        issues = [_make_issue("ERROR")]
        result = _make_result_with(issues, status="INCOHERENTE")
        self.assertFalse(result.is_valid())

    def test_to_dict_tiene_campos(self):
        result = _make_result_with([_make_issue()])
        d = result.to_dict()
        for campo in ("status", "checked_blocks", "issues", "error_count", "is_valid"):
            self.assertIn(campo, d)

    def test_administrative_ready_false(self):
        result = BlockConsistencyResult(status="COHERENTE")
        self.assertFalse(result.administrative_ready)

    def test_summary_contiene_estado(self):
        result = _make_result_with([])
        self.assertIn("INCOHERENTE", result.summary())

    def test_summary_contiene_contador(self):
        issues = [_make_issue("ERROR"), _make_issue("WARNING")]
        result = _make_result_with(issues)
        s = result.summary()
        self.assertIn("1", s)  # 1 ERROR


# ---------------------------------------------------------------------------
# 5. validate_red_natura_consistency
# ---------------------------------------------------------------------------


class TestValidateRedNaturaConsistency(unittest.TestCase):
    def _blocks_with_rn_cautela_and_close(self, close_phrase: str) -> dict:
        return {
            "bloques/bloque_H.md": (
                "Red Natura 2000 FI-010: consulta pendiente al organo ambiental. "
                "El area esta indeterminada hasta recibir respuesta."
            ),
            "bloques/bloque_J_rnt.md": (
                f"El proyecto no presenta impactos significativos. {close_phrase}."
            ),
        }

    def test_rn_cautela_mas_sin_afeccion_apreciable_error(self):
        blocks = self._blocks_with_rn_cautela_and_close("sin afeccion apreciable")
        issues = validate_red_natura_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0, f"Esperaba ERROR, issues={issues}")

    def test_rn_cautela_mas_no_afecta_red_natura_error(self):
        blocks = self._blocks_with_rn_cautela_and_close("no afecta a red natura")
        issues = validate_red_natura_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_rn_cautela_con_conclusion_prudente_sin_error(self):
        blocks = {
            "bloques/bloque_H.md": (
                "Red Natura 2000: consulta pendiente. No se puede determinar la afeccion."
            ),
            "bloques/bloque_J.md": (
                "No se detecta afeccion a Red Natura segun las fuentes consultadas. "
                "Se requiere confirmacion del organo ambiental."
            ),
        }
        issues = validate_red_natura_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_sin_bloque_rn_no_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Bloque de identificacion del proyecto.",
        }
        issues = validate_red_natura_consistency(blocks)
        self.assertEqual(len(issues), 0)

    def test_sin_conclusion_no_issues(self):
        blocks = {
            "bloques/bloque_H.md": "Red Natura pendiente de consulta.",
        }
        issues = validate_red_natura_consistency(blocks)
        self.assertEqual(len(issues), 0)

    def test_code_bc_rn_001(self):
        blocks = self._blocks_with_rn_cautela_and_close("sin afeccion apreciable")
        issues = validate_red_natura_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-RN-001", codes)


# ---------------------------------------------------------------------------
# 6. validate_biodiversity_consistency
# ---------------------------------------------------------------------------


class TestValidateBiodiversityConsistency(unittest.TestCase):
    def test_flora_gap_mas_sin_flora_error(self):
        blocks = {
            "inventario/FI-007_flora.md": (
                "Flora FI-007: campo necesario. Gap alta. "
                "Prospeccion pendiente. No se ha verificado presencia de flora protegida."
            ),
            "bloques/bloque_I_conclusiones.md": (
                "El proyecto no afecta a la biodiversidad. sin flora en el area de estudio."
            ),
        }
        issues = validate_biodiversity_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_fauna_gap_mas_sin_especies_error(self):
        blocks = {
            "inventario/FI-008_fauna.md": (
                "Fauna FI-008: gap. indeterminado. prospeccion pendiente."
            ),
            "bloques/bloque_J.md": "sin especies protegidas en el ambito del proyecto.",
        }
        issues = validate_biodiversity_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_bio_gap_conclusion_prudente_sin_error(self):
        blocks = {
            "inventario/FI-007_flora.md": "Flora FI-007: pendiente de prospeccion.",
            "bloques/bloque_I.md": (
                "No se detecta flora protegida en las fuentes consultadas. "
                "No consta prospeccion de campo. Se recomienda verificacion."
            ),
        }
        issues = validate_biodiversity_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_sin_bio_keywords_no_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Identificacion del proyecto industrial.",
            "bloques/bloque_I.md": "Conclusions generales.",
        }
        issues = validate_biodiversity_consistency(blocks)
        self.assertEqual(len(issues), 0)

    def test_code_bc_bio_001(self):
        blocks = {
            "inventario/FI-007_flora.md": "Flora FI-007: gap. pendiente campo.",
            "bloques/bloque_J.md": "no hay flora en el ambito.",
        }
        issues = validate_biodiversity_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-BIO-001", codes)


# ---------------------------------------------------------------------------
# 7. validate_heritage_consistency
# ---------------------------------------------------------------------------


class TestValidateHeritageConsistency(unittest.TestCase):
    def test_fi012_consulta_pendiente_mas_no_hay_patrimonio_error(self):
        blocks = {
            "inventario/FI-012_patrimonio.md": (
                "Patrimonio FI-012: consulta pendiente al Servicio de Cultura. "
                "gap alta. No se ha verificado."
            ),
            "bloques/bloque_J.md": "no hay patrimonio en la zona. El proyecto no afecta.",
        }
        issues = validate_heritage_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_patrimonio_sin_gap_conclusion_no_hay_sin_error(self):
        # Si no hay cautela en la fuente, no debe saltar error
        blocks = {
            "inventario/FI-012_patrimonio.md": (
                "Patrimonio FI-012: confirmado en gabinete. Sin yacimientos en catastro."
            ),
            "bloques/bloque_J.md": "no hay patrimonio arqueologico en el area revisada.",
        }
        issues = validate_heritage_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_heritage_sin_conclusion_no_issues(self):
        blocks = {
            "inventario/FI-012_patrimonio.md": "Patrimonio: consulta pendiente.",
        }
        issues = validate_heritage_consistency(blocks)
        self.assertEqual(len(issues), 0)

    def test_code_bc_her_001(self):
        blocks = {
            "inventario/FI-012_patrimonio.md": "Patrimonio gap pendiente consulta.",
            "bloques/bloque_I.md": "sin afeccion patrimonial en el proyecto.",
        }
        issues = validate_heritage_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-HER-001", codes)


# ---------------------------------------------------------------------------
# 8. validate_measure_consistency
# ---------------------------------------------------------------------------


class TestValidateMeasureConsistency(unittest.TestCase):
    def test_estudio_acustico_como_reductora_error(self):
        blocks = {
            "impactos/AG09_medidas.md": (
                "MED-001: estudio acustico. Esta medida correctora reduce la significancia "
                "del impacto acustico y reduce el impacto."
            ),
        }
        issues = validate_measure_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_prl_como_correctora_ambiental_error(self):
        blocks = {
            "impactos/AG09_medidas.md": (
                "MED-002: prl_no_eia dotacion de EPIs. Esta medida es correctora ambiental "
                "y reduce el impacto acustico exterior."
            ),
        }
        issues = validate_measure_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_medida_diagnostica_bien_separada_sin_error(self):
        blocks = {
            "impactos/AG09_medidas.md": (
                "MED-003: estudio acustico (diagnostica). "
                "Esta medida NO reduce la significancia. Su objetivo es caracterizar el impacto."
            ),
        }
        issues = validate_measure_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_sin_medidas_no_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Identificacion del proyecto.",
        }
        issues = validate_measure_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_diagnostica_como_reductora_code(self):
        blocks = {
            "impactos/valoracion.md": (
                "La medida diagnostica de monitorizacion acustica reduce el impacto."
            ),
        }
        issues = validate_measure_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-MEA-001", codes)

    def test_prl_code(self):
        blocks = {
            "impactos/medidas.md": (
                "medida prl: auditivos correctora ambiental reduce el ruido exterior."
            ),
        }
        issues = validate_measure_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-MEA-002", codes)


# ---------------------------------------------------------------------------
# 9. validate_assumption_consistency
# ---------------------------------------------------------------------------


class TestValidateAssumptionConsistency(unittest.TestCase):
    def _make_active_registry(self) -> AsuncionTestRegistry:
        at = create_assumption_from_gap(
            at_id="AT-001",
            gap_id="GAP-001",
            description="Datos no disponibles",
            scope="INVENTARIO",
            justification="Se asume valor provisional",
        )
        return AsuncionTestRegistry(expediente_id="TEST", assumptions=[at])

    def test_at_activa_mas_apto_para_presentacion_error(self):
        registry = self._make_active_registry()
        blocks = {
            "bloques/bloque_J.md": "El proyecto esta apto para presentacion ante el organo ambiental.",
        }
        issues = validate_assumption_consistency(blocks, registry)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_at_activa_mas_sin_condicionantes_error(self):
        registry = self._make_active_registry()
        blocks = {
            "bloques/bloque_I.md": "El expediente no presenta sin condicionantes y esta completo.",
        }
        issues = validate_assumption_consistency(blocks, registry)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_at_activa_mas_conclusion_prudente_sin_error(self):
        registry = self._make_active_registry()
        blocks = {
            "bloques/bloque_J.md": (
                "El expediente contiene asunciones de test activas que impiden "
                "la aptitud administrativa. Se remite al organo ambiental."
            ),
        }
        issues = validate_assumption_consistency(blocks, registry)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_sin_at_activa_sin_issues(self):
        registry = AsuncionTestRegistry(expediente_id="TEST", assumptions=[])
        blocks = {
            "bloques/bloque_J.md": "El expediente se presenta al organo ambiental.",
        }
        issues = validate_assumption_consistency(blocks, registry)
        self.assertEqual(len(issues), 0)

    def test_sin_registry_texto_at_activa_detecta(self):
        blocks = {
            "bloques/bloque_H.md": "AT activa en el expediente.",
            "bloques/bloque_J.md": "El expediente esta apto para presentacion.",
        }
        issues = validate_assumption_consistency(blocks, None)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_code_bc_at_001(self):
        registry = self._make_active_registry()
        blocks = {
            "bloques/bloque_I.md": "expediente apto administrativamente.",
        }
        issues = validate_assumption_consistency(blocks, registry)
        codes = [i.code for i in issues]
        self.assertIn("BC-AT-001", codes)

    def test_sin_registry_ni_texto_at_no_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Identificacion del proyecto industrial.",
            "bloques/bloque_J.md": "No se presentan impactos significativos.",
        }
        issues = validate_assumption_consistency(blocks, None)
        self.assertEqual(len(issues), 0)


# ---------------------------------------------------------------------------
# 10. validate_pva_consistency
# ---------------------------------------------------------------------------


class TestValidatePVAConsistency(unittest.TestCase):
    def test_pva_condicionado_mas_cerrado_error(self):
        blocks = {
            "impactos/AG09_PVA.md": (
                "PVA-001 condicionado por CONT-001: sujeto a cont. "
                "Ficha condicionada hasta obtener datos del promotor."
            ),
            "bloques/bloque_I.md": "El programa de vigilancia esta completado. PVA cerrado.",
        }
        issues = validate_pva_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_pva_condicionado_conclusion_prudente_sin_error(self):
        blocks = {
            "impactos/AG09_PVA.md": "PVA-001 condicionado por CONT-001.",
            "bloques/bloque_I.md": (
                "El programa de vigilancia contiene fichas condicionadas "
                "a la resolucion de contradicciones activas."
            ),
        }
        issues = validate_pva_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_sin_pva_no_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Identificacion del proyecto.",
            "bloques/bloque_I.md": "Conclusiones del expediente.",
        }
        issues = validate_pva_consistency(blocks)
        self.assertEqual(len(issues), 0)

    def test_code_bc_pva_001(self):
        blocks = {
            "impactos/AG09_PVA.md": "pva condicionado por at activa.",
            "bloques/bloque_J.md": "pva cerrado y definitivo.",
        }
        issues = validate_pva_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-PVA-001", codes)


# ---------------------------------------------------------------------------
# 11. validate_conclusion_consistency
# ---------------------------------------------------------------------------


class TestValidateConclusionConsistency(unittest.TestCase):
    def test_apto_para_presentacion_error(self):
        blocks = {
            "bloques/bloque_J.md": "El expediente esta apto para presentacion ante la administracion.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_apto_administrativamente_error(self):
        blocks = {
            "bloques/bloque_I.md": "El expediente es apto administrativamente.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_todos_compatibles_con_indeterminado_error(self):
        blocks = {
            "bloques/bloque_C.md": "IMP-001 naturaleza indeterminado. No se puede valorar.",
            "bloques/bloque_J.md": "todos los impactos son compatibles con el entorno.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_todos_compatibles_sin_indeterminado_en_otros_sin_error(self):
        blocks = {
            "bloques/bloque_C.md": "IMP-001 COMPATIBLE. IMP-002 MODERADO.",
            "bloques/bloque_J.md": "todos los impactos son compatibles.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR" and "BC-CON-001" in i.code]
        self.assertEqual(len(errors), 0)

    def test_sin_condicionantes_con_gap_alta_error(self):
        blocks = {
            "inventario/FI-007_flora.md": "GAP ALTA: prospeccion pendiente.",
            "bloques/bloque_I.md": "El expediente no presenta sin condicionantes.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_sin_bloques_conclusion_no_issues(self):
        blocks = {
            "bloques/bloque_H.md": "Red Natura cautela.",
            "bloques/bloque_C.md": "Impactos indeterminados.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.code == "BC-CON-001"]
        self.assertEqual(len(errors), 0)

    def test_code_bc_con_003(self):
        blocks = {
            "bloques/bloque_J.md": "conforme para presentar ante el organo ambiental.",
        }
        issues = validate_conclusion_consistency(blocks)
        codes = [i.code for i in issues]
        self.assertIn("BC-CON-003", codes)

    def test_no_existen_impactos_relevantes_con_impactos_error(self):
        blocks = {
            "inventario/FI-001.md": "Inventario. impacto IMP-001 detectado.",
            "bloques/bloque_J.md": "no existen impactos relevantes en el proyecto.",
        }
        issues = validate_conclusion_consistency(blocks)
        errors = [i for i in issues if i.code == "BC-CON-002"]
        self.assertTrue(len(errors) > 0)


# ---------------------------------------------------------------------------
# 12. validate_block_consistency
# ---------------------------------------------------------------------------


class TestValidateBlockConsistency(unittest.TestCase):
    def test_sin_blocks_sin_datos(self):
        result = validate_block_consistency({})
        self.assertEqual(result.status, "SIN_DATOS")

    def test_solo_warnings_con_observaciones(self):
        blocks = {
            "impactos/AG09_PVA.md": "revision anual ficha especifica del programa.",
            "bloques/bloque_J.md": "Prudente conclusion sin cierres indebidos.",
        }
        result = validate_block_consistency(blocks)
        self.assertIn(result.status, ("COHERENTE", "CON_OBSERVACIONES"))

    def test_con_error_incoherente(self):
        blocks = {
            "bloques/bloque_H.md": "Red Natura pendiente consulta indeterminado.",
            "bloques/bloque_J.md": "sin afeccion apreciable a red natura.",
        }
        result = validate_block_consistency(blocks)
        self.assertEqual(result.status, "INCOHERENTE")
        self.assertFalse(result.is_valid())

    def test_coherente_sin_issues(self):
        blocks = {
            "bloques/bloque_A.md": "Identificacion del proyecto.",
            "bloques/bloque_B.md": "Inventario ambiental detallado.",
        }
        result = validate_block_consistency(blocks)
        self.assertEqual(result.status, "COHERENTE")
        self.assertTrue(result.is_valid())

    def test_checked_blocks_lista(self):
        blocks = {
            "bloques/bloque_A.md": "Contenido A.",
            "bloques/bloque_B.md": "Contenido B.",
        }
        result = validate_block_consistency(blocks)
        self.assertEqual(len(result.checked_blocks), 2)

    def test_administrative_ready_false(self):
        blocks = {"bloques/bloque_A.md": "Contenido."}
        result = validate_block_consistency(blocks)
        self.assertFalse(result.administrative_ready)

    def test_ejecuta_todos_los_validadores(self):
        # Con contenido diverso, el validador debe ejecutar todos
        blocks = {
            "bloques/bloque_H.md": "Red Natura FI-010 pendiente consulta.",
            "inventario/FI-007.md": "Flora gap campo necesario.",
            "inventario/FI-012.md": "Patrimonio consulta pendiente.",
            "impactos/medidas.md": "estudio acustico correctora reductora.",
            "impactos/pva.md": "pva condicionado por cont.",
            "bloques/bloque_J.md": "sin afeccion apreciable.",
        }
        result = validate_block_consistency(blocks)
        self.assertIn(result.status, ("INCOHERENTE", "CON_OBSERVACIONES"))


# ---------------------------------------------------------------------------
# 13. validate_block_consistency_from_files
# ---------------------------------------------------------------------------


class TestValidateBlockConsistencyFromFiles(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_exp(self) -> Path:
        exp = self.tmp / "expediente-EIA-TEST"
        exp.mkdir()
        (exp / "bloques").mkdir()
        (exp / "control_interno").mkdir()
        return exp

    def test_carga_markdowns(self):
        exp = self._make_exp()
        (exp / "bloques" / "bloque_A.md").write_text("Identificacion.", encoding="utf-8")
        result = validate_block_consistency_from_files(exp)
        self.assertIn("bloques/bloque_A.md", result.checked_blocks)

    def test_carga_asunciones_test_json(self):
        exp = self._make_exp()
        # Crear AT activa
        from eia_agent.core.assumption_test_system import (
            AsuncionTestRegistry,
            write_assumptions_registry,
            create_assumption_from_gap,
        )
        at = create_assumption_from_gap(
            at_id="AT-001",
            gap_id="GAP-001",
            description="Datos pendientes",
            scope="INVENTARIO",
            justification="Provisional",
        )
        registry = AsuncionTestRegistry(expediente_id="TEST", assumptions=[at])
        write_assumptions_registry(registry, exp / "control_interno" / "asunciones_test.json")
        # Bloque con cierre
        (exp / "bloques" / "bloque_J.md").write_text(
            "apto para presentacion.", encoding="utf-8"
        )
        result = validate_block_consistency_from_files(exp)
        errors = [i for i in result.issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)

    def test_json_at_corrupto_no_rompe_todo(self):
        exp = self._make_exp()
        (exp / "control_interno" / "asunciones_test.json").write_text(
            "{ invalido }", encoding="utf-8"
        )
        (exp / "bloques" / "bloque_A.md").write_text("Contenido.", encoding="utf-8")
        result = validate_block_consistency_from_files(exp)
        # No debe lanzar excepcion; puede tener warnings
        self.assertIsInstance(result, BlockConsistencyResult)

    def test_sin_markdowns_sin_datos(self):
        exp = self._make_exp()
        result = validate_block_consistency_from_files(exp)
        self.assertEqual(result.status, "SIN_DATOS")


# ---------------------------------------------------------------------------
# 14. Markdown/report
# ---------------------------------------------------------------------------


class TestBuildBlockConsistencyReportMarkdown(unittest.TestCase):
    def setUp(self):
        issues = [_make_issue("ERROR", "BC-RN-001"), _make_issue("WARNING", "BC-MEA-003")]
        self.result = _make_result_with(issues, status="INCOHERENTE")
        self.md = build_block_consistency_report_markdown(self.result)

    def test_contiene_header(self):
        self.assertIn("# Auditoria de coherencia entre bloques", self.md)

    def test_contiene_resumen(self):
        self.assertIn("## 1. Resumen", self.md)

    def test_contiene_incidencias(self):
        self.assertIn("## 3. Incidencias ERROR", self.md)

    def test_contiene_codigo_issue(self):
        self.assertIn("BC-RN-001", self.md)

    def test_advertencia_no_aptitud(self):
        self.assertIn("no declara", self.md)
        self.assertIn("aptitud administrativa", self.md)

    def test_seccion_advertencia_alcance(self):
        self.assertIn("## 7. Advertencia de alcance", self.md)

    def test_sin_issues_coherente(self):
        result = BlockConsistencyResult(status="COHERENTE", checked_blocks=["a.md"])
        md = build_block_consistency_report_markdown(result)
        self.assertIn("COHERENTE", md)


# ---------------------------------------------------------------------------
# 15. Escritura
# ---------------------------------------------------------------------------


class TestWriteBlockConsistencyOutputs(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_escribe_json_y_md(self):
        issues = [_make_issue("ERROR")]
        result = _make_result_with(issues, status="INCOHERENTE")
        json_path, md_path = write_block_consistency_outputs(result, self.tmp)
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())

    def test_json_cargable(self):
        issues = [_make_issue("WARNING")]
        result = _make_result_with(issues, status="CON_OBSERVACIONES")
        json_path, _ = write_block_consistency_outputs(result, self.tmp)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("status", data)
        self.assertIn("issues", data)

    def test_nombres_correctos(self):
        result = BlockConsistencyResult(status="COHERENTE")
        json_path, md_path = write_block_consistency_outputs(result, self.tmp)
        self.assertEqual(json_path.name, "block_consistency_result.json")
        self.assertEqual(md_path.name, "block_consistency_result.md")

    def test_crea_directorio_si_no_existe(self):
        result = BlockConsistencyResult(status="COHERENTE")
        out = self.tmp / "sub" / "auditoria"
        write_block_consistency_outputs(result, out)
        self.assertTrue(out.exists())


# ---------------------------------------------------------------------------
# 16. CLI
# ---------------------------------------------------------------------------


class TestCLIAuditBlockConsistency(unittest.TestCase):
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

    def test_sin_markdowns_exit_0(self):
        exp = self._make_exp()
        rc = self._run([str(exp), "audit-block-consistency"])
        self.assertEqual(rc, 0)

    def test_coherente_exit_0(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_A.md").write_text("Identificacion.", encoding="utf-8")
        rc = self._run([str(exp), "audit-block-consistency"])
        self.assertEqual(rc, 0)

    def test_con_error_exit_1(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_H.md").write_text(
            "Red Natura FI-010 pendiente consulta indeterminado.", encoding="utf-8"
        )
        (exp / "bloques" / "bloque_J.md").write_text(
            "sin afeccion apreciable.", encoding="utf-8"
        )
        rc = self._run([str(exp), "audit-block-consistency"])
        self.assertEqual(rc, 1)

    def test_sin_write_no_escribe_archivo(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_A.md").write_text("Contenido.", encoding="utf-8")
        rc = self._run([str(exp), "audit-block-consistency"])
        json_path = exp / "auditoria" / "block_consistency_result.json"
        self.assertFalse(json_path.exists())

    def test_con_write_escribe_outputs(self):
        exp = self._make_exp()
        (exp / "bloques").mkdir()
        (exp / "bloques" / "bloque_A.md").write_text("Contenido.", encoding="utf-8")
        rc = self._run([str(exp), "audit-block-consistency", "--write"])
        json_path = exp / "auditoria" / "block_consistency_result.json"
        self.assertTrue(json_path.exists())


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------


class TestConstantes(unittest.TestCase):
    def test_severity_valores(self):
        self.assertIn("ERROR", CONSISTENCY_SEVERITY)
        self.assertIn("WARNING", CONSISTENCY_SEVERITY)
        self.assertIn("INFO", CONSISTENCY_SEVERITY)

    def test_status_valores(self):
        self.assertIn("COHERENTE", CONSISTENCY_STATUS)
        self.assertIn("INCOHERENTE", CONSISTENCY_STATUS)
        self.assertIn("CON_OBSERVACIONES", CONSISTENCY_STATUS)
        self.assertIn("SIN_DATOS", CONSISTENCY_STATUS)

    def test_block_families(self):
        self.assertIn("H_RED_NATURA", BLOCK_FAMILIES)
        self.assertIn("I_CONCLUSIONES", BLOCK_FAMILIES)
        self.assertIn("J_RNT", BLOCK_FAMILIES)
        self.assertEqual(len(BLOCK_FAMILIES), 10)


if __name__ == "__main__":
    unittest.main()
