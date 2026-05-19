"""
tests/test_prl_measure_validator.py
Tests para RD-09 -- Validador separacion EIA / PRL.

Cubre:
  1. is_prl_measure -- flag, tipo, status, keywords
  2. measure_is_presented_as_environmental_reduction -- detection y no-detection
  3. validate_prl_measure -- reglas E001, E002, W001
  4. validate_prl_measures_in_model -- SIN_DATOS, OK, NO_CONFORME, mutacion
  5. validate_prl_markdown -- tabla EIA con PRL, seccion PRL separada, formacion PRL
  6. JSON / files -- from_json, expediente temporal, markdowns temporales
  7. Markdown/report -- advertencia EIA/PRL, incidencias
  8. Escritura -- write_prl_measure_outputs
  9. CLI -- exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.prl_measure_validator import (
    ENVIRONMENTAL_REDUCTION_KEYWORDS,
    PRL_KEYWORDS,
    PRL_VALIDATION_STATUS,
    PRLMeasureIssue,
    PRLMeasureValidationResult,
    build_prl_measure_report_markdown,
    is_prl_measure,
    measure_is_presented_as_environmental_reduction,
    validate_prl_markdown,
    validate_prl_measures_from_files,
    validate_prl_measures_from_json,
    validate_prl_measures_in_model,
    validate_prl_measures_markdowns_from_files,
    validate_prl_measure,
    write_prl_measure_outputs,
)
from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    ReceptorFactor,
)


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _action(action_id="AC-001") -> ProjectAction:
    return ProjectAction(action_id=action_id, name="Operacion test", action_type="OPERACION")


def _receptor(receptor_id="FR-014") -> ReceptorFactor:
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id="FI-014",
        name="Ruido",
        ready_from_inventory=True,
    )


def _impact(
    impact_id="IMP-001",
    sig_without="SEVERO",
    sig_with="SEVERO",
    measure_ids=None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id="FR-014",
        name="Impacto acustico exterior",
        nature="NEGATIVO",
        status="VALORADO",
        significance_without_measures=sig_without,
        significance_with_measures=sig_with,
        measure_ids=measure_ids or [],
    )


def _measure(
    measure_id="MED-001",
    name="Medida test",
    description="",
    measure_type="CORRECTORA",
    status="PROPUESTA",
    is_prl_only=False,
    is_diagnostic=False,
    target_impact_ids=None,
    notes=None,
    warnings=None,
) -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id,
        name=name,
        description=description,
        measure_type=measure_type,
        status=status,
        is_prl_only=is_prl_only,
        is_diagnostic=is_diagnostic,
        target_impact_ids=target_impact_ids or [],
        notes=notes or [],
        warnings=warnings or [],
    )


def _minimal_model(measures=None, impacts=None) -> Phase6Model:
    return Phase6Model(
        expediente_id="EIA-TEST",
        actions=[_action()],
        receptor_factors=[_receptor()],
        impacts=impacts or [],
        measures=measures or [],
    )


# ---------------------------------------------------------------------------
# 1. is_prl_measure
# ---------------------------------------------------------------------------

class TestIsPrlMeasure(unittest.TestCase):

    def test_flag_is_prl_only_true(self):
        m = _measure(is_prl_only=True)
        self.assertTrue(is_prl_measure(m))

    def test_measure_type_prl_no_eia(self):
        m = _measure(measure_type="PRL_NO_EIA")
        self.assertTrue(is_prl_measure(m))

    def test_status_no_eia(self):
        m = _measure(status="NO_EIA")
        self.assertTrue(is_prl_measure(m))

    def test_epi_in_name(self):
        m = _measure(name="EPI auditivo")
        self.assertTrue(is_prl_measure(m))

    def test_epis_in_name(self):
        m = _measure(name="Uso de EPIs en zona de trabajo")
        self.assertTrue(is_prl_measure(m))

    def test_proteccion_auditiva_in_name(self):
        m = _measure(name="Proteccion auditiva del operario")
        self.assertTrue(is_prl_measure(m))

    def test_casco_in_name(self):
        m = _measure(name="Uso de casco protector")
        self.assertTrue(is_prl_measure(m))

    def test_formacion_prl_in_description(self):
        m = _measure(name="Medida", description="Formacion PRL para operarios")
        self.assertTrue(is_prl_measure(m))

    def test_prevencion_riesgos_laborales_in_notes(self):
        m = _measure(name="Medida", notes=["prevencion de riesgos laborales exigida"])
        self.assertTrue(is_prl_measure(m))

    def test_seguridad_laboral_in_description(self):
        m = _measure(name="Medida", description="Protocolo de seguridad laboral interno")
        self.assertTrue(is_prl_measure(m))

    def test_guantes_in_name(self):
        m = _measure(name="Uso de guantes de seguridad")
        self.assertTrue(is_prl_measure(m))

    def test_arnes_in_name(self):
        m = _measure(name="Uso de arnes de seguridad en altura")
        self.assertTrue(is_prl_measure(m))

    def test_no_marca_pantalla_acustica(self):
        m = _measure(
            name="Pantalla acustica perimetral",
            description="Instalacion de barrera de 3m para reducir ruido exterior",
            measure_type="CORRECTORA",
        )
        self.assertFalse(is_prl_measure(m))

    def test_no_marca_impermeabilizacion(self):
        m = _measure(
            name="Impermeabilizacion de solera",
            description="Membrana impermeabilizante bajo actividad",
        )
        self.assertFalse(is_prl_measure(m))

    def test_no_marca_riego_pistas(self):
        m = _measure(
            name="Riego de pistas de tierra",
            description="Control de polvo en viales internos",
        )
        self.assertFalse(is_prl_measure(m))

    def test_reconocimiento_medico_in_name(self):
        m = _measure(name="Reconocimiento medico anual de trabajadores")
        self.assertTrue(is_prl_measure(m))

    def test_vigilancia_salud_in_name(self):
        m = _measure(name="Vigilancia de la salud del personal")
        self.assertTrue(is_prl_measure(m))

    def test_accentuated_keyword_detected(self):
        # "protección auditiva" with accent
        m = _measure(name="Protección auditiva para el personal")
        self.assertTrue(is_prl_measure(m))

    def test_arnes_with_accent(self):
        m = _measure(name="Arnés de seguridad en trabajos en altura")
        self.assertTrue(is_prl_measure(m))


# ---------------------------------------------------------------------------
# 2. measure_is_presented_as_environmental_reduction
# ---------------------------------------------------------------------------

class TestMeasurePresentedAsEnvReduction(unittest.TestCase):

    def test_reduce_ruido_exterior(self):
        m = _measure(description="Reduce ruido exterior del recinto")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_reduce_impacto_ambiental(self):
        m = _measure(description="Con esta medida se reduce el impacto ambiental")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_medida_correctora_ambiental(self):
        m = _measure(description="Actua como medida correctora ambiental del ruido")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_medida_preventiva_ambiental(self):
        m = _measure(description="Funciona como medida preventiva ambiental")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_corrige_impacto(self):
        m = _measure(description="Corrige impacto acustico exterior")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_reduce_significancia_in_notes(self):
        m = _measure(notes=["Con EPI se reduce significancia del ruido exterior"])
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_reduce_afeccion(self):
        m = _measure(description="Reduce afeccion sobre la fauna")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_reduce_emisiones(self):
        m = _measure(description="Reduce emisiones del proceso al exterior")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))

    def test_no_reduce_impacto_ambiental_not_detected(self):
        m = _measure(
            name="EPI auditivo",
            description=(
                "No reduce impacto ambiental exterior. "
                "Solo protege al trabajador. PRL_NO_EIA."
            ),
        )
        self.assertFalse(measure_is_presented_as_environmental_reduction(m))

    def test_prl_no_eia_no_computable_not_detected(self):
        m = _measure(
            name="EPI",
            description=(
                "PRL_NO_EIA no computable como medida ambiental. "
                "No debe computarse como medida EIA reductora de significancia."
            ),
        )
        self.assertFalse(measure_is_presented_as_environmental_reduction(m))

    def test_neutral_text_not_detected(self):
        m = _measure(
            name="Formacion PRL",
            description="Formacion anual de los operarios en materia de seguridad.",
        )
        self.assertFalse(measure_is_presented_as_environmental_reduction(m))

    def test_evita_afeccion_ambiental_detected(self):
        m = _measure(description="Con EPIs se evita afeccion ambiental sobre el suelo")
        self.assertTrue(measure_is_presented_as_environmental_reduction(m))


# ---------------------------------------------------------------------------
# 3. validate_prl_measure
# ---------------------------------------------------------------------------

class TestValidatePrlMeasure(unittest.TestCase):

    def test_correct_prl_no_eia_no_error(self):
        m = _measure(
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
        )
        issues = validate_prl_measure(m)
        self.assertFalse(any(i.severity == "ERROR" for i in issues))

    def test_epi_as_correctora_error_e001(self):
        m = _measure(
            name="EPI auditivo para operarios",
            measure_type="CORRECTORA",
            is_prl_only=True,
        )
        issues = validate_prl_measure(m)
        self.assertTrue(any(i.code == "RD09-E001" for i in issues))

    def test_proteccion_auditiva_as_preventiva_error(self):
        m = _measure(
            name="Proteccion auditiva del personal",
            measure_type="PREVENTIVA",
        )
        issues = validate_prl_measure(m)
        self.assertTrue(any(i.code == "RD09-E001" for i in issues))

    def test_formacion_prl_claims_reduction_error_e002(self):
        m = _measure(
            name="Formacion PRL",
            description="Reduce ruido exterior del recinto operativo.",
            measure_type="PRL_NO_EIA",
        )
        issues = validate_prl_measure(m)
        self.assertTrue(any(i.code == "RD09-E002" for i in issues))

    def test_epi_claims_env_reduction_error_e002(self):
        m = _measure(
            name="EPI auditivo",
            description="Corrige impacto acustico exterior segun modelo.",
            measure_type="CORRECTORA",
        )
        issues = validate_prl_measure(m)
        self.assertTrue(any(i.code == "RD09-E002" for i in issues))

    def test_prl_linked_to_impact_without_no_eia_status_warning_w001(self):
        m = _measure(
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="PROPUESTA",   # should be NO_EIA
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001")
        issues = validate_prl_measure(m, related_impacts=[imp])
        self.assertTrue(any(i.code == "RD09-W001" for i in issues))

    def test_prl_correct_no_eia_linked_no_warning(self):
        m = _measure(
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001")
        issues = validate_prl_measure(m, related_impacts=[imp])
        # E001 and W001 should not fire; E002 also not
        self.assertFalse(any(i.code in ("RD09-E001", "RD09-W001") for i in issues))

    def test_issue_has_measure_id(self):
        m = _measure(
            measure_id="MED-777",
            name="EPI auditivo",
            measure_type="CORRECTORA",
        )
        issues = validate_prl_measure(m)
        for i in issues:
            if i.code == "RD09-E001":
                self.assertEqual(i.measure_id, "MED-777")

    def test_both_e001_and_e002_possible(self):
        m = _measure(
            name="EPI auditivo",
            description="Reduce ruido exterior.",
            measure_type="CORRECTORA",
            is_prl_only=True,
        )
        issues = validate_prl_measure(m)
        codes = {i.code for i in issues}
        self.assertIn("RD09-E001", codes)
        self.assertIn("RD09-E002", codes)

    def test_no_related_impacts_no_w001(self):
        m = _measure(
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="PROPUESTA",
        )
        issues = validate_prl_measure(m, related_impacts=None)
        self.assertFalse(any(i.code == "RD09-W001" for i in issues))

    def test_source_is_model(self):
        m = _measure(name="EPI", measure_type="CORRECTORA", is_prl_only=True)
        issues = validate_prl_measure(m)
        for i in issues:
            self.assertEqual(i.source, "model")


# ---------------------------------------------------------------------------
# 4. validate_prl_measures_in_model
# ---------------------------------------------------------------------------

class TestValidatePrlMeasuresInModel(unittest.TestCase):

    def test_model_without_measures_sin_datos(self):
        model = _minimal_model(measures=[])
        result = validate_prl_measures_in_model(model)
        self.assertEqual(result.status, "SIN_DATOS")

    def test_model_only_environmental_measures_ok(self):
        m = _measure(
            name="Pantalla acustica",
            measure_type="CORRECTORA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        model = _minimal_model(measures=[m], impacts=[imp])
        result = validate_prl_measures_in_model(model)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.prl_measures, [])

    def test_model_with_correct_prl_no_eia_ok(self):
        m = _measure(
            measure_id="MED-001",
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
        )
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        self.assertEqual(result.status, "OK")
        self.assertIn("MED-001", result.prl_measures)
        self.assertEqual(result.error_count(), 0)

    def test_epi_as_correctora_no_conforme(self):
        m = _measure(
            measure_id="MED-001",
            name="EPI auditivo",
            measure_type="CORRECTORA",
            is_prl_only=True,
        )
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertIn("MED-001", result.problematic_measures)
        self.assertTrue(any(i.code == "RD09-E001" for i in result.issues))

    def test_prl_sole_measure_severo_error_e003(self):
        prl = _measure(
            measure_id="MED-001",
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="SEVERO")
        model = _minimal_model(measures=[prl], impacts=[imp])
        result = validate_prl_measures_in_model(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertTrue(any(i.code == "RD09-E003" for i in result.issues))

    def test_prl_sole_measure_critico_error_e003(self):
        prl = _measure(
            measure_id="MED-001",
            name="EPI protector",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="CRITICO", sig_with="CRITICO")
        model = _minimal_model(measures=[prl], impacts=[imp])
        result = validate_prl_measures_in_model(model)
        self.assertTrue(any(i.code == "RD09-E003" for i in result.issues))

    def test_prl_not_sole_measure_no_e003(self):
        prl = _measure(
            measure_id="MED-001",
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
            target_impact_ids=["IMP-001"],
        )
        corrective = _measure(
            measure_id="MED-002",
            name="Pantalla acustica",
            measure_type="CORRECTORA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        model = _minimal_model(measures=[prl, corrective], impacts=[imp])
        result = validate_prl_measures_in_model(model)
        self.assertFalse(any(i.code == "RD09-E003" for i in result.issues))

    def test_does_not_mutate_model(self):
        prl = _measure(
            measure_id="MED-001",
            name="EPI",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
        )
        model = _minimal_model(measures=[prl])
        original_measures = list(model.measures)
        validate_prl_measures_in_model(model)
        self.assertEqual(model.measures, original_measures)
        self.assertEqual(model.measures[0].measure_id, "MED-001")

    def test_checked_measures_includes_all(self):
        m1 = _measure(measure_id="MED-001", name="Pantalla acustica", measure_type="CORRECTORA")
        m2 = _measure(measure_id="MED-002", name="EPI auditivo", measure_type="PRL_NO_EIA",
                      status="NO_EIA", is_prl_only=True)
        model = _minimal_model(measures=[m1, m2])
        result = validate_prl_measures_in_model(model)
        self.assertIn("MED-001", result.checked_measures)
        self.assertIn("MED-002", result.checked_measures)
        self.assertNotIn("MED-001", result.prl_measures)
        self.assertIn("MED-002", result.prl_measures)

    def test_status_values_are_valid(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        self.assertIn(result.status, PRL_VALIDATION_STATUS)

    def test_is_valid_no_errors(self):
        m = _measure(name="EPI", measure_type="PRL_NO_EIA", status="NO_EIA", is_prl_only=True)
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        self.assertTrue(result.is_valid())

    def test_not_valid_when_errors(self):
        m = _measure(name="EPI", measure_type="CORRECTORA", is_prl_only=True)
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        self.assertFalse(result.is_valid())

    def test_administrative_ready_always_false(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        self.assertFalse(result.administrative_ready)

    def test_to_dict_contains_required_keys(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        d = result.to_dict()
        for key in (
            "status", "administrative_ready", "checked_measures",
            "prl_measures", "problematic_measures", "issues",
            "error_count", "warning_count", "info_count",
        ):
            self.assertIn(key, d)

    def test_summary_contains_status(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        self.assertIn(result.status, result.summary())

    def test_moderado_prl_sole_no_e003(self):
        # E003 only fires for SEVERO/CRITICO, not MODERADO
        prl = _measure(
            name="EPI",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="MODERADO", sig_with="MODERADO")
        model = _minimal_model(measures=[prl], impacts=[imp])
        result = validate_prl_measures_in_model(model)
        self.assertFalse(any(i.code == "RD09-E003" for i in result.issues))


# ---------------------------------------------------------------------------
# 5. validate_prl_markdown
# ---------------------------------------------------------------------------

class TestValidatePrlMarkdown(unittest.TestCase):

    def test_epi_in_correctoras_table_error(self):
        md = """
## 4.3 Medidas correctoras ambientales

| Medida | Tipo | Descripcion |
|--------|------|-------------|
| EPI auditivo | Correctora | Reduce ruido exterior del operario |
"""
        result = validate_prl_markdown(md, source="test.md")
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertTrue(any(i.code == "RD09-MD-E001" for i in result.issues))

    def test_prl_section_separated_ok(self):
        md = """
## D.5 Medidas PRL (PRL_NO_EIA — no computables como medidas EIA)

Las siguientes medidas son de PRL NO_EIA y no reducen significancia ambiental:
- Uso de EPIs auditivos
- Formacion PRL
- Casco y guantes de seguridad
"""
        result = validate_prl_markdown(md, source="test.md")
        errors = [i for i in result.issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_formacion_prl_reduces_impacto_error(self):
        md = """
## Medidas preventivas ambientales

- Formacion PRL: reduce impacto ambiental sobre la zona de trabajo exterior
"""
        result = validate_prl_markdown(md, source="test.md")
        self.assertEqual(result.status, "NO_CONFORME")

    def test_epi_no_eia_marker_safe(self):
        md = """
## Medidas de PRL (no EIA)

Estas medidas son no EIA y no reducen significancia. Solo protegen al trabajador.

- EPI: casco, guantes, arnes
"""
        result = validate_prl_markdown(md, source="test.md")
        errors = [i for i in result.issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0)

    def test_proteccion_auditiva_in_eia_context_warning_or_error(self):
        md = """
## Tabla de medidas correctoras

| ID | Medida | Tipo |
|----|--------|------|
| M-01 | Proteccion auditiva del personal | Preventiva |
"""
        result = validate_prl_markdown(md, source="test.md")
        # Should flag as WARNING or ERROR (EIA context, no safe markers)
        self.assertIn(result.status, ("CON_OBSERVACIONES", "NO_CONFORME"))

    def test_casco_corrective_measures_context_warning(self):
        md = """
## D.4 Medidas correctoras

- Casco de seguridad para trabajadores en zona de obra
"""
        result = validate_prl_markdown(md, source="test.md")
        # EIA context detected, PRL keyword without safe markers -> WARNING
        self.assertIn(result.status, ("CON_OBSERVACIONES", "NO_CONFORME"))

    def test_no_prl_keywords_ok(self):
        md = """
## D.4 Medidas correctoras

- Pantalla acustica perimetral (3m)
- Riego de pistas de tierra
- Baliza de exclusion en zona sensible
"""
        result = validate_prl_markdown(md)
        self.assertEqual(result.status, "OK")

    def test_source_field_in_issue(self):
        md = """
## Medidas correctoras ambientales
- EPI: reduce ruido exterior
"""
        result = validate_prl_markdown(md, source="bloques/bloque_D.md")
        for i in result.issues:
            self.assertEqual(i.source, "bloques/bloque_D.md")

    def test_empty_markdown_ok(self):
        result = validate_prl_markdown("", source="empty.md")
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.issues, [])

    def test_arnes_in_eia_corrective_error(self):
        md = """
## Medidas correctoras

- Arnes de seguridad: medida correctora ambiental para altura
"""
        result = validate_prl_markdown(md, source="test.md")
        self.assertIn(result.status, ("CON_OBSERVACIONES", "NO_CONFORME"))


# ---------------------------------------------------------------------------
# 6. JSON / files
# ---------------------------------------------------------------------------

def _minimal_model_dict(measures=None, impacts=None) -> dict:
    return {
        "expediente_id": "EIA-TEST",
        "actions": [{"action_id": "AC-001", "name": "Accion", "action_type": "OPERACION"}],
        "receptor_factors": [{
            "receptor_id": "FR-014",
            "inventory_factor_id": "FI-014",
            "name": "Ruido",
            "ready_from_inventory": True,
        }],
        "impacts": impacts or [],
        "measures": measures or [],
        "pva_programs": [],
    }


class TestValidateFromJson(unittest.TestCase):

    def test_from_json_clean_model(self):
        data = _minimal_model_dict(measures=[{
            "measure_id": "MED-001",
            "name": "EPI auditivo",
            "measure_type": "PRL_NO_EIA",
            "status": "NO_EIA",
            "is_prl_only": True,
        }])
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump(data, f)
            tmp = Path(f.name)
        try:
            result = validate_prl_measures_from_json(tmp)
            self.assertIn(result.status, PRL_VALIDATION_STATUS)
            self.assertEqual(result.status, "OK")
        finally:
            tmp.unlink(missing_ok=True)

    def test_from_json_nonexistent_file(self):
        result = validate_prl_measures_from_json("/no/existe/file.json")
        self.assertEqual(result.status, "SIN_DATOS")

    def test_from_json_corrupt_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            f.write("{invalid}")
            tmp = Path(f.name)
        try:
            result = validate_prl_measures_from_json(tmp)
            self.assertEqual(result.status, "SIN_DATOS")
        finally:
            tmp.unlink(missing_ok=True)

    def test_from_json_problematic_model_no_conforme(self):
        data = _minimal_model_dict(
            impacts=[{
                "impact_id": "IMP-001",
                "action_id": "AC-001",
                "receptor_id": "FR-014",
                "name": "Ruido",
                "nature": "NEGATIVO",
                "status": "VALORADO",
                "significance_without_measures": "SEVERO",
                "significance_with_measures": "SEVERO",
                "measure_ids": ["MED-001"],
            }],
            measures=[{
                "measure_id": "MED-001",
                "name": "EPI auditivo",
                "measure_type": "PRL_NO_EIA",
                "status": "NO_EIA",
                "is_prl_only": True,
                "target_impact_ids": ["IMP-001"],
            }],
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump(data, f)
            tmp = Path(f.name)
        try:
            result = validate_prl_measures_from_json(tmp)
            # E003: sole PRL for SEVERO impact
            self.assertEqual(result.status, "NO_CONFORME")
        finally:
            tmp.unlink(missing_ok=True)


class TestValidateFromFiles(unittest.TestCase):

    def test_expediente_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            validate_prl_measures_from_files("/no/existe")

    def test_expediente_without_model_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            exp.mkdir()
            (exp / "impactos").mkdir()
            result = validate_prl_measures_from_files(exp)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_expediente_with_clean_model_ok(self):
        data = _minimal_model_dict(measures=[{
            "measure_id": "MED-001",
            "name": "EPI auditivo",
            "measure_type": "PRL_NO_EIA",
            "status": "NO_EIA",
            "is_prl_only": True,
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            (exp / "impactos").mkdir(parents=True)
            (exp / "impactos" / "phase6_model_with_pva.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            result = validate_prl_measures_from_files(exp)
            self.assertEqual(result.status, "OK")

    def test_expediente_with_error_model_no_conforme(self):
        data = _minimal_model_dict(
            measures=[{
                "measure_id": "MED-001",
                "name": "EPI auditivo",
                "measure_type": "CORRECTORA",
                "is_prl_only": True,
            }]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            (exp / "impactos").mkdir(parents=True)
            (exp / "impactos" / "phase6_model_with_measures.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            result = validate_prl_measures_from_files(exp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_markdowns_problematic_no_conforme(self):
        md_content = """
## Medidas correctoras ambientales

| Medida | Descripcion |
|--------|-------------|
| EPI auditivo | Reduce ruido exterior de la instalacion |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            (exp / "bloques").mkdir(parents=True)
            (exp / "bloques" / "bloque_D_medidas.md").write_text(
                md_content, encoding="utf-8"
            )
            result = validate_prl_measures_markdowns_from_files(exp)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_markdowns_separated_prl_ok(self):
        md_content = """
## D.5 Medidas PRL NO_EIA — no computan como medidas ambientales EIA

- EPI auditivo
- Casco de seguridad
- Formacion PRL
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            (exp / "bloques").mkdir(parents=True)
            (exp / "bloques" / "bloque_D_medidas.md").write_text(
                md_content, encoding="utf-8"
            )
            result = validate_prl_measures_markdowns_from_files(exp)
            errors = [i for i in result.issues if i.severity == "ERROR"]
            self.assertEqual(len(errors), 0)

    def test_no_markdowns_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-TEST"
            exp.mkdir()
            result = validate_prl_measures_markdowns_from_files(exp)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_markdowns_raises_if_no_expediente(self):
        with self.assertRaises(FileNotFoundError):
            validate_prl_measures_markdowns_from_files("/no/existe/exp")


# ---------------------------------------------------------------------------
# 7. Markdown/report
# ---------------------------------------------------------------------------

class TestMarkdownReport(unittest.TestCase):

    def setUp(self):
        m = _measure(
            measure_id="MED-001",
            name="EPI auditivo",
            measure_type="CORRECTORA",
            is_prl_only=True,
            description="Reduce ruido exterior del operario.",
        )
        model = _minimal_model(measures=[m])
        self.result = validate_prl_measures_in_model(model)
        self.md = build_prl_measure_report_markdown(self.result)

    def test_contains_advertencia_de_alcance(self):
        self.assertIn("Advertencia de alcance", self.md)

    def test_contains_prl_eia_text(self):
        md_lower = self.md.lower()
        self.assertIn("prl", md_lower)
        self.assertIn("eia", md_lower)

    def test_contains_no_computarse(self):
        md_lower = self.md.lower()
        self.assertIn("no deben computarse", md_lower)

    def test_contains_incidencias_section(self):
        self.assertIn("Incidencias", self.md)

    def test_contains_resumen_section(self):
        self.assertIn("Resumen", self.md)

    def test_contains_issue_code(self):
        self.assertIn("RD09-E001", self.md)

    def test_contains_recomendaciones_section(self):
        self.assertIn("Recomendaciones", self.md)

    def test_contains_medidas_prl_section(self):
        self.assertIn("Medidas PRL", self.md)

    def test_contains_no_modifica(self):
        md_lower = self.md.lower()
        self.assertIn("no modifica", md_lower)

    def test_clean_model_no_issues_in_report(self):
        m = _measure(name="Pantalla acustica", measure_type="CORRECTORA")
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        md = build_prl_measure_report_markdown(result)
        self.assertNotIn("RD09-E001", md)

    def test_epi_no_eia_correct_no_errors_in_report(self):
        m = _measure(
            name="EPI auditivo",
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_prl_only=True,
        )
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        md = build_prl_measure_report_markdown(result)
        self.assertNotIn("RD09-E001", md)

    def test_markdown_is_string(self):
        self.assertIsInstance(self.md, str)
        self.assertTrue(len(self.md) > 100)


# ---------------------------------------------------------------------------
# 8. Escritura
# ---------------------------------------------------------------------------

class TestWriteOutputs(unittest.TestCase):

    def test_write_creates_json_and_md(self):
        m = _measure(name="EPI", measure_type="PRL_NO_EIA", status="NO_EIA", is_prl_only=True)
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "auditoria"
            json_p, md_p = write_prl_measure_outputs(result, out)
            self.assertTrue(json_p.exists())
            self.assertTrue(md_p.exists())
            self.assertEqual(json_p.name, "prl_measure_validation_result.json")
            self.assertEqual(md_p.name, "prl_measure_validation_result.md")

    def test_json_is_loadable(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_p, _ = write_prl_measure_outputs(result, Path(tmpdir))
            data = json.loads(json_p.read_text(encoding="utf-8"))
            self.assertIn("status", data)
            self.assertEqual(data["status"], result.status)

    def test_json_has_expected_keys(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_p, _ = write_prl_measure_outputs(result, Path(tmpdir))
            data = json.loads(json_p.read_text(encoding="utf-8"))
            for key in ("status", "prl_measures", "issues", "error_count"):
                self.assertIn(key, data)

    def test_output_dir_created_if_missing(self):
        model = _minimal_model()
        result = validate_prl_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "auditoria"
            self.assertFalse(out.exists())
            write_prl_measure_outputs(result, out)
            self.assertTrue(out.exists())

    def test_md_content_matches_build(self):
        m = _measure(name="EPI", measure_type="PRL_NO_EIA", status="NO_EIA", is_prl_only=True)
        model = _minimal_model(measures=[m])
        result = validate_prl_measures_in_model(model)
        expected = build_prl_measure_report_markdown(result)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, md_p = write_prl_measure_outputs(result, Path(tmpdir))
            self.assertEqual(md_p.read_text(encoding="utf-8"), expected)


# ---------------------------------------------------------------------------
# 9. CLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def _run_cli(self, exp_path: Path, extra_args=None) -> int:
        from run_expediente import main as cli_main
        backup = sys.argv[:]
        args = ["run_expediente.py", str(exp_path), "audit-prl-measures"]
        if extra_args:
            args.extend(extra_args)
        sys.argv = args
        try:
            return cli_main()
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0
        finally:
            sys.argv = backup

    def _build_expediente(self, tmpdir: str, with_error: bool = False) -> Path:
        exp = Path(tmpdir) / "EIA-CLI-RD09"
        (exp / "impactos").mkdir(parents=True)
        if with_error:
            data = _minimal_model_dict(measures=[{
                "measure_id": "MED-001",
                "name": "EPI auditivo",
                "measure_type": "CORRECTORA",
                "is_prl_only": True,
            }])
        else:
            data = _minimal_model_dict(measures=[{
                "measure_id": "MED-001",
                "name": "EPI auditivo",
                "measure_type": "PRL_NO_EIA",
                "status": "NO_EIA",
                "is_prl_only": True,
            }])
        (exp / "impactos" / "phase6_model_with_measures.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        return exp

    def test_exit_1_on_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = self._build_expediente(tmpdir, with_error=True)
            code = self._run_cli(exp)
            self.assertEqual(code, 1)

    def test_exit_0_on_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = self._build_expediente(tmpdir, with_error=False)
            code = self._run_cli(exp)
            self.assertEqual(code, 0)

    def test_without_write_no_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = self._build_expediente(tmpdir, with_error=False)
            self._run_cli(exp)
            self.assertFalse((exp / "auditoria" / "prl_measure_validation_result.json").exists())

    def test_with_write_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = self._build_expediente(tmpdir, with_error=False)
            self._run_cli(exp, extra_args=["--write"])
            self.assertTrue((exp / "auditoria" / "prl_measure_validation_result.json").exists())
            self.assertTrue((exp / "auditoria" / "prl_measure_validation_result.md").exists())

    def test_exit_0_con_observaciones(self):
        """CON_OBSERVACIONES (solo WARNINGs) -> exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp = Path(tmpdir) / "EIA-CLI-RD09-2"
            (exp / "impactos").mkdir(parents=True)
            # PRL_NO_EIA but status=PROPUESTA, linked to impact -> W001
            data = _minimal_model_dict(
                impacts=[{
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-014",
                    "name": "Ruido",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "MODERADO",
                    "significance_with_measures": "MODERADO",
                    "measure_ids": ["MED-001", "MED-002"],
                }],
                measures=[
                    {
                        "measure_id": "MED-001",
                        "name": "EPI auditivo",
                        "measure_type": "PRL_NO_EIA",
                        "status": "PROPUESTA",  # should be NO_EIA -> W001
                        "is_prl_only": True,
                        "target_impact_ids": ["IMP-001"],
                    },
                    {
                        "measure_id": "MED-002",
                        "name": "Pantalla acustica",
                        "measure_type": "CORRECTORA",
                        "target_impact_ids": ["IMP-001"],
                    },
                ],
            )
            (exp / "impactos" / "phase6_model_with_measures.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            code = self._run_cli(exp)
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Clases de datos
# ---------------------------------------------------------------------------

class TestPRLMeasureIssue(unittest.TestCase):

    def test_to_dict_has_all_fields(self):
        issue = PRLMeasureIssue(
            severity="ERROR",
            code="RD09-E001",
            measure_id="MED-001",
            impact_id=None,
            source="model",
            message="Msg test",
            recommendation="Rec test",
            evidence=["ev1"],
        )
        d = issue.to_dict()
        for key in ("severity", "code", "measure_id", "impact_id", "source", "message", "recommendation", "evidence"):
            self.assertIn(key, d)

    def test_invalid_severity_raises(self):
        with self.assertRaises(ValueError):
            PRLMeasureIssue(
                severity="INVALID",
                code="RD09-X999",
                measure_id=None,
                impact_id=None,
                source="model",
                message="Test",
            )

    def test_summary_format(self):
        issue = PRLMeasureIssue(
            severity="WARNING",
            code="RD09-W001",
            measure_id="MED-005",
            impact_id="IMP-002",
            source="model",
            message="Mensaje de prueba",
        )
        s = issue.summary()
        self.assertIn("WARNING", s)
        self.assertIn("RD09-W001", s)
        self.assertIn("MED-005", s)


class TestConstants(unittest.TestCase):

    def test_prl_keywords_not_empty(self):
        self.assertTrue(len(PRL_KEYWORDS) > 0)

    def test_epi_in_keywords(self):
        self.assertIn("epi", PRL_KEYWORDS)

    def test_reduce_impacto_in_env_keywords(self):
        self.assertIn("reduce impacto ambiental", ENVIRONMENTAL_REDUCTION_KEYWORDS)

    def test_all_statuses_present(self):
        for s in ("OK", "CON_OBSERVACIONES", "NO_CONFORME", "SIN_DATOS"):
            self.assertIn(s, PRL_VALIDATION_STATUS)

    def test_reduce_ruido_exterior_in_env_keywords(self):
        self.assertIn("reduce ruido exterior", ENVIRONMENTAL_REDUCTION_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
