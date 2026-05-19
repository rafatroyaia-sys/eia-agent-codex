"""
Tests para inventory_renderer -- IV-01

No usa IA, no usa web, no modifica expedientes piloto.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.inventory_model import (
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_all_empty_factors,
    build_inventory_summary,
    FACTOR_NAMES,
)
from eia_agent.core.inventory_renderer import (
    InventoryRenderConfig,
    InventoryRenderResult,
    build_inventory_index,
    render_factor_inventory_markdown,
    render_inventory_summary_markdown,
    safe_factor_filename,
    write_inventory_markdown_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gap(
    gap_id: str = "GAP-FI-001-01",
    factor_id: str = "FI-001",
    field: str = "campo_test",
    description: str = "Gap de prueba para tests.",
    criticality: str = "MEDIA",
    resolution_mode: str = "GABINETE",
    status: str = "PENDIENTE",
) -> InventoryGap:
    return InventoryGap(
        gap_id=gap_id,
        factor_id=factor_id,
        field=field,
        description=description,
        criticality=criticality,
        resolution_mode=resolution_mode,
        status=status,
    )


def _factor(
    factor_id: str = "FI-001",
    evidence_status: str = "DECLARADO",
    field_mode: str = "GABINETE_SUFICIENTE",
    inventory_semaphore: str = "AMARILLO",
    description: str = "",
    data_sources: list = None,
    gaps: list = None,
    ready_for_impact_assessment: bool = False,
    notes: list = None,
    warnings: list = None,
    field_mode_justification: str = "",
    semaphore_justification: str = "",
) -> FactorInventory:
    return FactorInventory(
        factor_id=factor_id,
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=inventory_semaphore,
        description=description,
        data_sources=data_sources or [],
        gaps=gaps or [],
        ready_for_impact_assessment=ready_for_impact_assessment,
        notes=notes or [],
        warnings=warnings or [],
        field_mode_justification=field_mode_justification,
        semaphore_justification=semaphore_justification,
    )


def _make_16_factors(
    ready: bool = False,
    semaphore: str = "AMARILLO",
) -> list[FactorInventory]:
    factors = []
    for fid in sorted(FACTOR_NAMES.keys()):
        factors.append(
            FactorInventory(
                factor_id=fid,
                evidence_status="DECLARADO",
                field_mode="GABINETE_SUFICIENTE",
                inventory_semaphore=semaphore,
                ready_for_impact_assessment=ready,
            )
        )
    return factors


# ---------------------------------------------------------------------------
# 1. TestInventoryRenderConfig
# ---------------------------------------------------------------------------

class TestInventoryRenderConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = InventoryRenderConfig()
        self.assertTrue(cfg.include_header)
        self.assertTrue(cfg.include_gap_table)
        self.assertTrue(cfg.include_readiness_section)
        self.assertTrue(cfg.include_methodological_note)
        self.assertEqual(cfg.language, "es")

    def test_to_dict_keys(self):
        cfg = InventoryRenderConfig()
        d = cfg.to_dict()
        self.assertIn("include_header", d)
        self.assertIn("include_gap_table", d)
        self.assertIn("include_readiness_section", d)
        self.assertIn("include_methodological_note", d)
        self.assertIn("language", d)

    def test_to_dict_values_default(self):
        cfg = InventoryRenderConfig()
        d = cfg.to_dict()
        self.assertTrue(d["include_header"])
        self.assertTrue(d["include_gap_table"])
        self.assertEqual(d["language"], "es")

    def test_from_dict_roundtrip_defaults(self):
        cfg = InventoryRenderConfig()
        d = cfg.to_dict()
        cfg2 = InventoryRenderConfig.from_dict(d)
        self.assertEqual(cfg2.include_header, cfg.include_header)
        self.assertEqual(cfg2.include_gap_table, cfg.include_gap_table)
        self.assertEqual(cfg2.include_methodological_note, cfg.include_methodological_note)
        self.assertEqual(cfg2.language, cfg.language)

    def test_from_dict_custom_values(self):
        d = {
            "include_header": False,
            "include_gap_table": False,
            "include_readiness_section": True,
            "include_methodological_note": False,
            "language": "en",
        }
        cfg = InventoryRenderConfig.from_dict(d)
        self.assertFalse(cfg.include_header)
        self.assertFalse(cfg.include_gap_table)
        self.assertFalse(cfg.include_methodological_note)
        self.assertEqual(cfg.language, "en")

    def test_from_dict_missing_keys_use_defaults(self):
        cfg = InventoryRenderConfig.from_dict({})
        self.assertTrue(cfg.include_header)
        self.assertTrue(cfg.include_gap_table)
        self.assertTrue(cfg.include_methodological_note)
        self.assertEqual(cfg.language, "es")

    def test_to_dict_from_dict_roundtrip_non_default(self):
        cfg = InventoryRenderConfig(
            include_header=False,
            include_gap_table=True,
            include_readiness_section=False,
            include_methodological_note=False,
            language="fr",
        )
        cfg2 = InventoryRenderConfig.from_dict(cfg.to_dict())
        self.assertEqual(cfg2.include_header, False)
        self.assertEqual(cfg2.include_readiness_section, False)
        self.assertEqual(cfg2.language, "fr")

    def test_custom_include_header_false(self):
        cfg = InventoryRenderConfig(include_header=False)
        self.assertFalse(cfg.include_header)

    def test_from_dict_is_classmethod(self):
        result = InventoryRenderConfig.from_dict({"language": "pt"})
        self.assertIsInstance(result, InventoryRenderConfig)
        self.assertEqual(result.language, "pt")


# ---------------------------------------------------------------------------
# 2. TestSafeFactorFilename
# ---------------------------------------------------------------------------

class TestSafeFactorFilename(unittest.TestCase):

    def test_fi_001_clima(self):
        f = _factor("FI-001")
        self.assertEqual(safe_factor_filename(f), "FI-001_clima.md")

    def test_fi_002_geologia(self):
        # Geologia (removes tilde from Geologia)
        f = _factor("FI-002")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-002_geologia.md")

    def test_fi_003_suelos(self):
        f = _factor("FI-003")
        self.assertEqual(safe_factor_filename(f), "FI-003_suelos.md")

    def test_fi_004_hidrologia(self):
        # Hidrologia (removes tilde)
        f = _factor("FI-004")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-004_hidrologia.md")

    def test_fi_005_inundabilidad(self):
        f = _factor("FI-005")
        self.assertEqual(safe_factor_filename(f), "FI-005_inundabilidad.md")

    def test_fi_006_calidad_del_aire(self):
        f = _factor("FI-006")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-006_calidad_del_aire.md")

    def test_fi_007_flora(self):
        f = _factor("FI-007")
        self.assertEqual(safe_factor_filename(f), "FI-007_flora.md")

    def test_fi_008_fauna(self):
        f = _factor("FI-008")
        self.assertEqual(safe_factor_filename(f), "FI-008_fauna.md")

    def test_fi_009_espacios_naturales_protegidos(self):
        f = _factor("FI-009")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-009_espacios_naturales_protegidos.md")

    def test_fi_010_red_natura_2000(self):
        f = _factor("FI-010")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-010_red_natura_2000.md")

    def test_fi_011_paisaje(self):
        f = _factor("FI-011")
        self.assertEqual(safe_factor_filename(f), "FI-011_paisaje.md")

    def test_fi_012_patrimonio_cultural(self):
        f = _factor("FI-012")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-012_patrimonio_cultural.md")

    def test_fi_013_socioeconomia(self):
        # Socioeconomia (removes tilde from Socioeconomia)
        f = _factor("FI-013")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-013_socioeconomia.md")

    def test_fi_014_ruido(self):
        f = _factor("FI-014")
        self.assertEqual(safe_factor_filename(f), "FI-014_ruido.md")

    def test_fi_015_cambio_climatico(self):
        # Cambio climatico (removes tilde from climatico)
        f = _factor("FI-015")
        result = safe_factor_filename(f)
        self.assertEqual(result, "FI-015_cambio_climatico.md")

    def test_fi_016_riesgos_naturales(self):
        f = _factor("FI-016")
        self.assertEqual(safe_factor_filename(f), "FI-016_riesgos_naturales.md")

    def test_no_spaces_in_result(self):
        for fid in FACTOR_NAMES:
            f = _factor(fid)
            self.assertNotIn(" ", safe_factor_filename(f))

    def test_no_tildes_in_result(self):
        accented = "áéíóúüñÁÉÍÓÚÜÑ"
        for fid in FACTOR_NAMES:
            f = _factor(fid)
            result = safe_factor_filename(f)
            for ch in accented:
                self.assertNotIn(ch, result, f"{fid}: {result} contains {ch}")

    def test_all_end_with_md(self):
        for fid in FACTOR_NAMES:
            f = _factor(fid)
            self.assertTrue(safe_factor_filename(f).endswith(".md"))

    def test_all_start_with_factor_id(self):
        for fid in FACTOR_NAMES:
            f = _factor(fid)
            self.assertTrue(safe_factor_filename(f).startswith(fid))

    def test_all_16_unique(self):
        factors = _make_16_factors()
        filenames = [safe_factor_filename(f) for f in factors]
        self.assertEqual(len(filenames), len(set(filenames)))


# ---------------------------------------------------------------------------
# 3. TestRenderFactorMarkdown
# ---------------------------------------------------------------------------

class TestRenderFactorMarkdown(unittest.TestCase):

    def setUp(self):
        self.factor = _factor(
            "FI-001",
            evidence_status="CONFIRMADO_GABINETE",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="VERDE",
            description="Clima de tipo arido segun clasificacion de Koppen.",
            data_sources=["CL-06", "AEMET normales 1981-2010"],
            ready_for_impact_assessment=True,
        )
        self.md = render_factor_inventory_markdown(self.factor)

    def test_contains_factor_id_in_title(self):
        self.assertIn("FI-001", self.md)

    def test_contains_factor_name_in_title(self):
        self.assertIn("Clima", self.md)

    def test_contains_section_1(self):
        self.assertIn("## 1. Estado de la informacion", self.md)

    def test_contains_section_2(self):
        self.assertIn("## 2. Descripcion del factor", self.md)

    def test_contains_section_3(self):
        self.assertIn("## 3. Fuentes de datos", self.md)

    def test_contains_section_4(self):
        self.assertIn("## 4. Justificacion del modo de trabajo", self.md)

    def test_contains_section_5(self):
        self.assertIn("## 5. Justificacion del semaforo", self.md)

    def test_contains_section_6(self):
        self.assertIn("## 6. Gaps y limitaciones", self.md)

    def test_contains_section_7(self):
        self.assertIn("## 7. Preparacion para Fase 6", self.md)

    def test_contains_section_8(self):
        self.assertIn("## 8. Notas y advertencias", self.md)

    def test_contains_evidence_status(self):
        self.assertIn("CONFIRMADO_GABINETE", self.md)

    def test_contains_semaphore(self):
        self.assertIn("VERDE", self.md)

    def test_contains_field_mode(self):
        self.assertIn("GABINETE_SUFICIENTE", self.md)

    def test_contains_description(self):
        self.assertIn("arido segun clasificacion", self.md)

    def test_contains_data_sources(self):
        self.assertIn("CL-06", self.md)
        self.assertIn("AEMET normales 1981-2010", self.md)

    def test_no_gaps_message(self):
        self.assertIn("No se han registrado gaps especificos", self.md)

    def test_gaps_in_table_when_present(self):
        g = _gap("GAP-FI-001-01", "FI-001", "precipitacion", "Falta dato.", "ALTA", "CAMPO")
        f = _factor("FI-001", gaps=[g])
        md = render_factor_inventory_markdown(f)
        self.assertIn("GAP-FI-001-01", md)
        self.assertIn("precipitacion", md)
        self.assertIn("ALTA", md)
        self.assertIn("CAMPO", md)
        self.assertIn("PENDIENTE", md)

    def test_gap_table_header_present(self):
        g = _gap()
        f = _factor("FI-001", gaps=[g])
        md = render_factor_inventory_markdown(f)
        self.assertIn("| Gap ID |", md)
        self.assertIn("| Campo |", md)

    def test_empty_description_consta(self):
        f = _factor("FI-001", description="")
        md = render_factor_inventory_markdown(f)
        self.assertIn("NO CONSTA INFORMACION DESCRIPTIVA SUFICIENTE", md)

    def test_empty_sources_consta(self):
        f = _factor("FI-001", data_sources=[])
        md = render_factor_inventory_markdown(f)
        self.assertIn("NO CONSTA FUENTE DOCUMENTAL ESPECIFICA", md)

    def test_empty_field_mode_justification_consta(self):
        f = _factor("FI-001", field_mode_justification="")
        md = render_factor_inventory_markdown(f)
        self.assertIn("NO CONSTA JUSTIFICACION ESPECIFICA", md)

    def test_methodological_note_present_by_default(self):
        md = render_factor_inventory_markdown(self.factor)
        self.assertIn("inventario ambiental de gabinete", md)

    def test_methodological_note_absent_when_config_false(self):
        cfg = InventoryRenderConfig(include_methodological_note=False)
        md = render_factor_inventory_markdown(self.factor, config=cfg)
        self.assertNotIn("inventario ambiental de gabinete", md)

    def test_warnings_in_section_8(self):
        f = _factor("FI-001", warnings=["Aviso de prueba"])
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO: Aviso de prueba", md)

    def test_notes_in_section_8(self):
        f = _factor("FI-001", notes=["Nota de prueba"])
        md = render_factor_inventory_markdown(f)
        self.assertIn("NOTA: Nota de prueba", md)

    def test_no_gaps_section_when_config_false(self):
        cfg = InventoryRenderConfig(include_gap_table=False)
        f = _factor("FI-001")
        md = render_factor_inventory_markdown(f, config=cfg)
        self.assertNotIn("## 6. Gaps y limitaciones", md)

    def test_no_readiness_section_when_config_false(self):
        cfg = InventoryRenderConfig(include_readiness_section=False)
        f = _factor("FI-001")
        md = render_factor_inventory_markdown(f, config=cfg)
        self.assertNotIn("## 7. Preparacion para Fase 6", md)

    def test_ready_false_revision_message(self):
        f = _factor("FI-001", ready_for_impact_assessment=False)
        md = render_factor_inventory_markdown(f)
        self.assertIn("sin revision previa", md)

    def test_ready_true_listo_message(self):
        f = _factor("FI-001", ready_for_impact_assessment=True,
                    inventory_semaphore="VERDE",
                    evidence_status="CONFIRMADO_GABINETE")
        md = render_factor_inventory_markdown(f)
        self.assertIn("LISTO para su uso", md)

    def test_no_header_when_config_false(self):
        cfg = InventoryRenderConfig(include_header=False)
        f = _factor("FI-001")
        md = render_factor_inventory_markdown(f, config=cfg)
        self.assertNotIn("# FI-001", md)

    def test_multiple_gaps_all_in_table(self):
        gaps = [
            _gap("GAP-FI-001-01", "FI-001", "campo1", "Desc1", "ALTA", "CAMPO"),
            _gap("GAP-FI-001-02", "FI-001", "campo2", "Desc2", "BAJA", "GABINETE"),
        ]
        f = _factor("FI-001", gaps=gaps)
        md = render_factor_inventory_markdown(f)
        self.assertIn("GAP-FI-001-01", md)
        self.assertIn("GAP-FI-001-02", md)

    def test_semaphore_verde_amarillo_label(self):
        f = _factor("FI-001", inventory_semaphore="VERDE_AMARILLO")
        md = render_factor_inventory_markdown(f)
        self.assertIn("VERDE-AMARILLO", md)

    def test_fi_012_renders(self):
        f = _factor("FI-012")
        md = render_factor_inventory_markdown(f)
        self.assertIn("FI-012", md)
        self.assertIn("Patrimonio", md)

    def test_field_mode_justification_in_section_4(self):
        f = _factor("FI-001", field_mode_justification="Los datos AEMET son suficientes.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("Los datos AEMET son suficientes.", md)

    def test_semaphore_justification_in_section_5(self):
        f = _factor("FI-001", semaphore_justification="Clasificacion verificada con CL-06.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("Clasificacion verificada con CL-06.", md)

    def test_default_config_none_uses_defaults(self):
        md = render_factor_inventory_markdown(self.factor, config=None)
        self.assertIn("## 1. Estado de la informacion", md)


# ---------------------------------------------------------------------------
# 4. TestPrudenceRules
# ---------------------------------------------------------------------------

class TestPrudenceRules(unittest.TestCase):

    def test_no_impact_language_no_warning(self):
        f = _factor("FI-001", description="Factor bien caracterizado.")
        md = render_factor_inventory_markdown(f)
        self.assertNotIn("AVISO DE PRUDENCIA", md)

    def test_compatible_in_description_detected(self):
        f = _factor("FI-001", description="El impacto es COMPATIBLE.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)
        self.assertIn("COMPATIBLE", md)

    def test_moderado_in_description_detected(self):
        f = _factor("FI-001", description="El impacto es moderado.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_severo_in_description_detected(self):
        f = _factor("FI-001", description="Impacto severo sobre el factor.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_critico_in_description_detected(self):
        f = _factor("FI-001", description="Impacto critico detectado.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_critico_with_tilde_detected(self):
        f = _factor("FI-001", description="Impacto critico grave.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_impact_language_in_notes_detected(self):
        f = _factor("FI-001", notes=["El factor presenta impacto compatible."])
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_impact_language_in_warnings_detected(self):
        f = _factor("FI-001", warnings=["Severidad moderada detectada."])
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)

    def test_impact_warning_in_section_8(self):
        f = _factor("FI-001", description="Impacto severo.")
        md = render_factor_inventory_markdown(f)
        # El aviso debe estar en sección 8
        idx_s8 = md.find("## 8. Notas y advertencias")
        idx_warn = md.find("AVISO DE PRUDENCIA")
        self.assertGreater(idx_warn, idx_s8)

    def test_uppercase_compatible_detected(self):
        f = _factor("FI-001", description="Clasificado como COMPATIBLE por defecto.")
        md = render_factor_inventory_markdown(f)
        self.assertIn("AVISO DE PRUDENCIA", md)


# ---------------------------------------------------------------------------
# 5. TestRenderSummaryMarkdown
# ---------------------------------------------------------------------------

class TestRenderSummaryMarkdown(unittest.TestCase):

    def setUp(self):
        factors = _make_16_factors(ready=False, semaphore="AMARILLO")
        self.summary = build_inventory_summary("EIA-TEST-001", factors)
        self.md = render_inventory_summary_markdown(self.summary)

    def test_title_present(self):
        self.assertIn("# Resumen del inventario ambiental", self.md)

    def test_expediente_id_present(self):
        self.assertIn("EIA-TEST-001", self.md)

    def test_section_1_present(self):
        self.assertIn("## 1. Expediente", self.md)

    def test_section_2_present(self):
        self.assertIn("## 2. Estado general", self.md)

    def test_section_3_present(self):
        self.assertIn("## 3. Tabla de factores", self.md)

    def test_section_4_present(self):
        self.assertIn("## 4. Factores por semaforo", self.md)

    def test_section_5_present(self):
        self.assertIn("## 5. Factores que requieren trabajo de campo", self.md)

    def test_section_6_present(self):
        self.assertIn("## 6. Advertencias y notas", self.md)

    def test_total_factors_present(self):
        self.assertIn("16", self.md)

    def test_all_ready_for_phase6_false_label(self):
        self.assertIn("all_ready_for_phase6**: NO", self.md)

    def test_blocking_note_when_not_ready(self):
        self.assertIn("no debe avanzar a Fase 6", self.md)

    def test_table_header_present(self):
        self.assertIn("| Factor |", self.md)
        self.assertIn("| Nombre |", self.md)
        self.assertIn("| Semaforo |", self.md)

    def test_table_rows_all_factors(self):
        for fid in FACTOR_NAMES:
            self.assertIn(fid, self.md)

    def test_factores_por_semaforo_section(self):
        self.assertIn("AMARILLO", self.md)

    def test_no_campo_factors_message(self):
        self.assertIn("Ningun factor tiene asignado modo de campo", self.md)

    def test_campo_factors_listed_when_present(self):
        factors = _make_16_factors()
        factors[0] = _factor("FI-001", field_mode="CAMPO_NECESARIO")
        summary = build_inventory_summary("EIA-TEST-002", factors)
        md = render_inventory_summary_markdown(summary)
        self.assertIn("CAMPO_NECESARIO", md)
        self.assertIn("FI-001", md)

    def test_all_ready_for_phase6_true_when_ready(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        # Usar CONFIRMADO_GABINETE para que no haya warnings de coherencia
        for f in factors:
            f.evidence_status = "CONFIRMADO_GABINETE"
        summary = build_inventory_summary("EIA-TEST-003", factors)
        md = render_inventory_summary_markdown(summary)
        self.assertIn("all_ready_for_phase6**: SI", md)

    def test_no_blocking_note_when_ready(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        for f in factors:
            f.evidence_status = "CONFIRMADO_GABINETE"
        summary = build_inventory_summary("EIA-TEST-004", factors)
        md = render_inventory_summary_markdown(summary)
        # La nota de bloqueo final solo aparece cuando all_ready_for_phase6 is False
        self.assertNotIn(
            "*El inventario no debe avanzar a Fase 6 si all_ready_for_phase6 es False.*",
            md,
        )

    def test_warnings_in_output(self):
        factors = _make_16_factors()
        summary = InventorySummary(
            expediente_id="EIA-TEST-005",
            factors=factors,
            warnings=["Aviso de prueba del resumen"],
        )
        md = render_inventory_summary_markdown(summary)
        self.assertIn("Aviso de prueba del resumen", md)

    def test_notes_in_output(self):
        factors = _make_16_factors()
        summary = InventorySummary(
            expediente_id="EIA-TEST-006",
            factors=factors,
            notes=["Nota de prueba del resumen"],
        )
        md = render_inventory_summary_markdown(summary)
        self.assertIn("Nota de prueba del resumen", md)

    def test_ready_count_present(self):
        self.assertIn("Factores listos (ready)", self.md)

    def test_campo_necesario_count_present(self):
        self.assertIn("Factores con campo necesario", self.md)

    def test_rojo_semaphore_listed(self):
        self.assertIn("ROJO", self.md)

    def test_verde_semaphore_listed(self):
        self.assertIn("VERDE", self.md)


# ---------------------------------------------------------------------------
# 6. TestBuildInventoryIndex
# ---------------------------------------------------------------------------

class TestBuildInventoryIndex(unittest.TestCase):

    def setUp(self):
        self.factors = _make_16_factors()
        self.summary = build_inventory_summary("EIA-IDX-001", self.factors)
        self.index = build_inventory_index(self.summary)

    def test_returns_dict(self):
        self.assertIsInstance(self.index, dict)

    def test_json_serializable(self):
        try:
            json.dumps(self.index)
        except (TypeError, ValueError) as e:
            self.fail(f"Index no es JSON serializable: {e}")

    def test_expediente_id(self):
        self.assertEqual(self.index["expediente_id"], "EIA-IDX-001")

    def test_total_factors_count(self):
        self.assertEqual(self.index["total_factors"], 16)

    def test_ready_count_zero(self):
        self.assertEqual(self.index["ready_count"], 0)

    def test_all_ready_for_phase6_false(self):
        self.assertFalse(self.index["all_ready_for_phase6"])

    def test_all_ready_for_phase6_true_when_ready(self):
        factors = _make_16_factors(ready=True, semaphore="VERDE")
        for f in factors:
            f.evidence_status = "CONFIRMADO_GABINETE"
        summary = build_inventory_summary("EIA-IDX-002", factors)
        index = build_inventory_index(summary)
        self.assertTrue(index["all_ready_for_phase6"])

    def test_factors_list_length(self):
        self.assertEqual(len(self.index["factors"]), 16)

    def test_factor_has_expected_keys(self):
        entry = self.index["factors"][0]
        self.assertIn("factor_id", entry)
        self.assertIn("factor_name", entry)
        self.assertIn("semaphore", entry)
        self.assertIn("ready", entry)
        self.assertIn("filename", entry)

    def test_factor_filename_none_when_not_provided(self):
        entry = self.index["factors"][0]
        self.assertIsNone(entry["filename"])

    def test_factor_filename_from_dict(self):
        filenames = {"FI-001": "FI-001_clima.md", "FI-002": "FI-002_geologia.md"}
        index = build_inventory_index(self.summary, factor_filenames=filenames)
        fi001 = next(e for e in index["factors"] if e["factor_id"] == "FI-001")
        fi002 = next(e for e in index["factors"] if e["factor_id"] == "FI-002")
        fi003 = next(e for e in index["factors"] if e["factor_id"] == "FI-003")
        self.assertEqual(fi001["filename"], "FI-001_clima.md")
        self.assertEqual(fi002["filename"], "FI-002_geologia.md")
        self.assertIsNone(fi003["filename"])

    def test_factor_semaphore_correct(self):
        for entry in self.index["factors"]:
            self.assertEqual(entry["semaphore"], "AMARILLO")

    def test_factor_ready_correct(self):
        for entry in self.index["factors"]:
            self.assertFalse(entry["ready"])

    def test_empty_filenames_dict(self):
        index = build_inventory_index(self.summary, factor_filenames={})
        for entry in index["factors"]:
            self.assertIsNone(entry["filename"])


# ---------------------------------------------------------------------------
# 7. TestWriteInventoryFiles
# ---------------------------------------------------------------------------

class TestWriteInventoryFiles(unittest.TestCase):

    def setUp(self):
        self.factors = _make_16_factors()
        self.summary = build_inventory_summary("EIA-WRITE-001", self.factors)

    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fichas_inventario"
            self.assertFalse(out.exists())
            write_inventory_markdown_files(self.summary, out)
            self.assertTrue(out.exists())

    def test_writes_16_factor_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            self.assertEqual(len(result.factor_files), 16)

    def test_all_factor_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            for fp in result.factor_files:
                self.assertTrue(Path(fp).exists(), f"Falta: {fp}")

    def test_writes_summary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            self.assertIsNotNone(result.summary_file)
            self.assertTrue(Path(result.summary_file).exists())
            self.assertTrue(result.summary_file.endswith("resumen_inventario.md"))

    def test_writes_index_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            self.assertIsNotNone(result.index_file)
            self.assertTrue(Path(result.index_file).exists())
            self.assertTrue(result.index_file.endswith("indice_inventario.json"))

    def test_factor_filenames_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            for fp in result.factor_files:
                fname = Path(fp).name
                self.assertTrue(fname.startswith("FI-"))
                self.assertTrue(fname.endswith(".md"))

    def test_index_json_loadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            with open(result.index_file, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertIn("expediente_id", data)
            self.assertIn("factors", data)

    def test_index_json_has_16_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            with open(result.index_file, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data["factors"]), 16)

    def test_files_only_in_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "salida"
            result = write_inventory_markdown_files(self.summary, out)
            for fp in result.factor_files:
                self.assertTrue(Path(fp).is_relative_to(out.resolve()))
            self.assertTrue(Path(result.summary_file).is_relative_to(out.resolve()))
            self.assertTrue(Path(result.index_file).is_relative_to(out.resolve()))

    def test_result_summary_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            s = result.summary()
            self.assertIn("16", s)

    def test_result_to_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            d = result.to_dict()
            self.assertIn("factor_files", d)
            self.assertIn("summary_file", d)
            self.assertIn("index_file", d)
            self.assertIsInstance(d["factor_files"], list)

    def test_factor_file_contains_factor_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            fi001_path = next(fp for fp in result.factor_files if "FI-001" in fp)
            content = Path(fi001_path).read_text(encoding="utf-8")
            self.assertIn("FI-001", content)

    def test_index_filenames_in_index_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            with open(result.index_file, encoding="utf-8") as fh:
                data = json.load(fh)
            for entry in data["factors"]:
                self.assertIsNotNone(entry["filename"], f"{entry['factor_id']} sin filename")
                self.assertTrue(entry["filename"].endswith(".md"))

    def test_result_has_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(self.summary, tmp)
            self.assertTrue(len(result.notes) > 0)


# ---------------------------------------------------------------------------
# 8. TestFixtureLanzarote
# ---------------------------------------------------------------------------

class TestFixtureLanzarote(unittest.TestCase):
    """Fixture realista: FI-001 Clima con datos del piloto Lanzarote."""

    def _make_fi001_lanzarote(self) -> FactorInventory:
        return FactorInventory(
            factor_id="FI-001",
            evidence_status="CONFIRMADO_GABINETE",
            field_mode="GABINETE_SUFICIENTE",
            inventory_semaphore="VERDE",
            description=(
                "Clima de tipo arido calido (BWh segun clasificacion de Koppen-Geiger). "
                "Indice de Martonne inferior a 5 mm/C (zona hiperarida). "
                "Temperatura media anual superior a 20C. "
                "Precipitacion media anual inferior a 150 mm. "
                "Clasificacion obtenida a partir de normales climatologicas 1981-2010 "
                "de la estacion AEMET mas proxima."
            ),
            data_sources=[
                "CL-06 — Pipeline climatico Fase 4 offline",
                "AEMET — Normales climatologicas 1981-2010",
                "Estacion C029O — Aeropuerto de Lanzarote",
            ],
            ready_for_impact_assessment=True,
            field_mode_justification=(
                "Las normales climatologicas de AEMET son suficientes para "
                "la caracterizacion del clima en modo gabinete. "
                "No se requiere trabajo de campo para este factor."
            ),
            semaphore_justification=(
                "Datos confirmados mediante normales 1981-2010. "
                "Sin gaps activos. Clasificacion Köppen verificada con CL-06."
            ),
            notes=[
                "Clasificacion Koppen: BWh (desierto calido)",
                "Indice Martonne: < 5 mm/C (hiperarido)",
                "Meses de Gaussen secos: todos los meses del ano",
            ],
        )

    def _make_summary_lanzarote(self) -> InventorySummary:
        factors = _make_16_factors(ready=False, semaphore="AMARILLO")
        factors[0] = self._make_fi001_lanzarote()
        return build_inventory_summary("EIA-2026-LANZAROTE-001", factors)

    def test_fi001_lanzarote_renders(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("FI-001", md)

    def test_fi001_lanzarote_verde_semaphore(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("VERDE", md)

    def test_fi001_lanzarote_ready_true(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("LISTO para su uso", md)

    def test_fi001_lanzarote_koppen_in_description(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("BWh", md)

    def test_fi001_lanzarote_martonne_in_description(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("Martonne", md)

    def test_fi001_lanzarote_sources_listed(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("CL-06", md)
        self.assertIn("C029O", md)

    def test_fi001_lanzarote_notes_preserved(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("BWh (desierto calido)", md)
        self.assertIn("hiperarido", md)

    def test_fi001_lanzarote_no_impact_language_warning(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertNotIn("AVISO DE PRUDENCIA", md)

    def test_fi001_lanzarote_methodological_note(self):
        f = self._make_fi001_lanzarote()
        md = render_factor_inventory_markdown(f)
        self.assertIn("inventario ambiental de gabinete", md)

    def test_fi001_lanzarote_filename(self):
        f = self._make_fi001_lanzarote()
        self.assertEqual(safe_factor_filename(f), "FI-001_clima.md")

    def test_lanzarote_summary_markdown(self):
        summary = self._make_summary_lanzarote()
        md = render_inventory_summary_markdown(summary)
        self.assertIn("EIA-2026-LANZAROTE-001", md)

    def test_lanzarote_summary_has_fi001_verde(self):
        summary = self._make_summary_lanzarote()
        md = render_inventory_summary_markdown(summary)
        self.assertIn("VERDE", md)

    def test_lanzarote_write_all_files(self):
        summary = self._make_summary_lanzarote()
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(summary, tmp)
            self.assertEqual(len(result.factor_files), 16)
            self.assertIsNotNone(result.summary_file)
            self.assertIsNotNone(result.index_file)

    def test_lanzarote_index_json(self):
        summary = self._make_summary_lanzarote()
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(summary, tmp)
            with open(result.index_file, encoding="utf-8") as fh:
                data = json.load(fh)
            fi001 = next(e for e in data["factors"] if e["factor_id"] == "FI-001")
            self.assertEqual(fi001["semaphore"], "VERDE")
            self.assertTrue(fi001["ready"])

    def test_lanzarote_fi001_file_readable(self):
        summary = self._make_summary_lanzarote()
        with tempfile.TemporaryDirectory() as tmp:
            result = write_inventory_markdown_files(summary, tmp)
            fi001_path = next(fp for fp in result.factor_files if "FI-001" in fp)
            content = Path(fi001_path).read_text(encoding="utf-8")
            self.assertIn("BWh", content)
            self.assertIn("CL-06", content)


if __name__ == "__main__":
    unittest.main()
