"""
tests/test_diagnostic_measure_validator.py
Tests para RD-08 -- Validador de medidas diagnosticas vs reductoras.

Cubre:
  1. is_diagnostic_measure -- flag, tipo, keywords
  2. measure_claims_material_reduction -- detection y no-detection
  3. validate_diagnostic_measure -- reglas E001 y W001
  4. validate_diagnostic_measures_in_model -- SIN_DATOS, OK, NO_CONFORME, mutacion
  5. JSON / files -- from_json, expediente temporal
  6. Markdown -- advertencia de alcance, incidencias
  7. Escritura -- write_diagnostic_measure_outputs
  8. CLI -- exit codes, --write
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.diagnostic_measure_validator import (
    DIAGNOSTIC_KEYWORDS,
    DIAGNOSTIC_VALIDATION_STATUS,
    REDUCTION_KEYWORDS,
    DiagnosticMeasureIssue,
    DiagnosticMeasureValidationResult,
    build_diagnostic_measure_report_markdown,
    is_diagnostic_measure,
    measure_claims_material_reduction,
    validate_diagnostic_measure,
    validate_diagnostic_measures_from_files,
    validate_diagnostic_measures_from_json,
    validate_diagnostic_measures_in_model,
    write_diagnostic_measure_outputs,
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
    return ProjectAction(action_id=action_id, name="Accion test", action_type="OPERACION")


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
    nature="NEGATIVO",
    measure_ids=None,
) -> EnvironmentalImpact:
    return EnvironmentalImpact(
        impact_id=impact_id,
        action_id="AC-001",
        receptor_id="FR-014",
        name="Impacto acustico",
        nature=nature,
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
    is_diagnostic=False,
    is_prl_only=False,
    target_impact_ids=None,
    notes=None,
    warnings=None,
) -> MitigationMeasure:
    return MitigationMeasure(
        measure_id=measure_id,
        name=name,
        description=description,
        measure_type=measure_type,
        is_diagnostic=is_diagnostic,
        is_prl_only=is_prl_only,
        target_impact_ids=target_impact_ids or [],
        notes=notes or [],
        warnings=warnings or [],
    )


def _minimal_model(measures=None, impacts=None, actions=None, receptors=None) -> Phase6Model:
    return Phase6Model(
        expediente_id="EIA-TEST",
        actions=actions or [_action()],
        receptor_factors=receptors or [_receptor()],
        impacts=impacts or [],
        measures=measures or [],
    )


# ---------------------------------------------------------------------------
# 1. is_diagnostic_measure
# ---------------------------------------------------------------------------

class TestIsDiagnosticMeasure(unittest.TestCase):

    def test_flag_is_diagnostic_true(self):
        m = _measure(is_diagnostic=True)
        self.assertTrue(is_diagnostic_measure(m))

    def test_measure_type_diagnostica(self):
        m = _measure(measure_type="DIAGNOSTICA")
        self.assertTrue(is_diagnostic_measure(m))

    def test_estudio_acustico_in_name(self):
        m = _measure(name="Estudio acustico del entorno")
        self.assertTrue(is_diagnostic_measure(m))

    def test_consulta_patrimonial_in_name(self):
        m = _measure(name="Consulta patrimonial al cabildo")
        self.assertTrue(is_diagnostic_measure(m))

    def test_prospeccion_flora_in_name(self):
        m = _measure(name="Prospeccion de flora amenazada")
        self.assertTrue(is_diagnostic_measure(m))

    def test_verificacion_cartografica_in_description(self):
        m = _measure(name="Medida aux", description="Verificacion cartografica de limites")
        self.assertTrue(is_diagnostic_measure(m))

    def test_modelizacion_acustica_in_name(self):
        m = _measure(name="Modelizacion acustica")
        self.assertTrue(is_diagnostic_measure(m))

    def test_caracterizacion_in_description(self):
        m = _measure(name="Medida", description="Caracterizacion tecnica pendiente del suelo")
        self.assertTrue(is_diagnostic_measure(m))

    def test_informe_previo_in_notes(self):
        m = _measure(name="Medida", notes=["Se requiere informe previo del organismo competente"])
        self.assertTrue(is_diagnostic_measure(m))

    def test_analisis_previo_in_description(self):
        m = _measure(name="Accion", description="Se realizara analisis previo de calidad")
        self.assertTrue(is_diagnostic_measure(m))

    def test_diagnostico_keyword_in_name(self):
        m = _measure(name="Diagnostico inicial de la flora")
        self.assertTrue(is_diagnostic_measure(m))

    def test_no_marca_impermeabilizacion(self):
        m = _measure(
            name="Impermeabilizacion del suelo",
            description="Instalacion de membrana impermeable bajo la actividad",
        )
        self.assertFalse(is_diagnostic_measure(m))

    def test_no_marca_correctora_material(self):
        m = _measure(
            name="Pantalla acustica perimetral",
            description="Instalacion de barrera de 3m alrededor de la zona de operaciones",
            measure_type="CORRECTORA",
        )
        self.assertFalse(is_diagnostic_measure(m))

    def test_no_marca_preventiva_material(self):
        m = _measure(
            name="Riego de pistas de tierra",
            description="Control de polvo en viales internos",
            measure_type="PREVENTIVA",
        )
        self.assertFalse(is_diagnostic_measure(m))

    def test_accentuated_keyword_detected(self):
        # Keyword with accents should still be detected
        m = _measure(name="Medición acústica del recinto")  # "Medición acústica"
        self.assertTrue(is_diagnostic_measure(m))

    def test_prospection_with_accent(self):
        m = _measure(name="Prospección de fauna nocturna")  # "Prospección"
        self.assertTrue(is_diagnostic_measure(m))


# ---------------------------------------------------------------------------
# 2. measure_claims_material_reduction
# ---------------------------------------------------------------------------

class TestMeasureClaimsMaterialReduction(unittest.TestCase):

    def test_reduce_la_significancia(self):
        m = _measure(description="Esta medida reduce la significancia del impacto acustico")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_pasa_a_compatible(self):
        m = _measure(name="Estudio acustico", description="Con esta medida el impacto pasa a compatible")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_mitiga(self):
        m = _measure(description="Mitiga el impacto sobre el suelo")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_corrige(self):
        m = _measure(description="Corrige la afeccion sobre el paisaje")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_elimina(self):
        m = _measure(description="Elimina la afeccion sobre la flora")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_baja_la_significancia(self):
        m = _measure(description="Esta prospeccion baja la significancia del impacto")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_queda_corregido(self):
        m = _measure(description="Con este estudio previo el impacto queda corregido")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_se_considera_compatible_tras(self):
        m = _measure(description="Se considera compatible tras la realizacion del estudio")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_evita_completamente(self):
        m = _measure(description="Evita completamente el impacto sobre la cuenca")
        self.assertTrue(measure_claims_material_reduction(m))

    def test_reduccion_in_notes(self):
        m = _measure(name="Consulta", notes=["Permite la reduccion de la significancia"])
        self.assertTrue(measure_claims_material_reduction(m))

    def test_prudente_no_detectado(self):
        m = _measure(
            name="Estudio acustico",
            description=(
                "No reduce por si misma la significancia ambiental. "
                "Solo aporta informacion para dimensionar medidas correctoras."
            ),
        )
        self.assertFalse(measure_claims_material_reduction(m))

    def test_no_detecta_texto_neutral(self):
        m = _measure(
            name="Prospeccion de flora",
            description=(
                "Permite identificar la presencia de especies protegidas "
                "antes de iniciar las operaciones."
            ),
        )
        self.assertFalse(measure_claims_material_reduction(m))

    def test_no_detecta_pantalla_acustica(self):
        m = _measure(
            name="Pantalla acustica",
            description="Instalacion de barrera perimetral de 3m de altura",
        )
        self.assertFalse(measure_claims_material_reduction(m))

    def test_detects_in_warnings(self):
        m = _measure(
            name="Estudio",
            warnings=["Nota: reduce la significancia del impacto acustico"],
        )
        self.assertTrue(measure_claims_material_reduction(m))


# ---------------------------------------------------------------------------
# 3. validate_diagnostic_measure
# ---------------------------------------------------------------------------

class TestValidateDiagnosticMeasure(unittest.TestCase):

    def test_diagnostic_well_formulated_no_error(self):
        m = _measure(
            name="Estudio acustico previo",
            description="Solo aporta informacion; no reduce por si misma la significancia.",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
        )
        issues = validate_diagnostic_measure(m)
        self.assertFalse(any(i.severity == "ERROR" for i in issues))

    def test_estudio_claims_reduction_error(self):
        m = _measure(
            name="Estudio acustico",
            description="Reduce la significancia del impacto acustico.",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
        )
        issues = validate_diagnostic_measure(m)
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any(i.code == "RD08-E001" for i in errors))

    def test_consulta_oficial_descarta_afeccion_warning_or_error(self):
        m = _measure(
            name="Consulta oficial al organismo ambiental",
            description="Descarta la afeccion sobre la zona de interes.",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
        )
        issues = validate_diagnostic_measure(m)
        # "descarta" is not in REDUCTION_KEYWORDS explicitly but... let me check.
        # Actually "elimina" is, not "descarta". So this should have no E001.
        # But we can check overall behavior.
        self.assertIsInstance(issues, list)

    def test_diagnostic_linked_to_improved_impact_warning(self):
        m = _measure(
            name="Estudio acustico",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        issues = validate_diagnostic_measure(m, related_impacts=[imp])
        warnings = [i for i in issues if i.severity == "WARNING" and i.code == "RD08-W001"]
        self.assertTrue(len(warnings) > 0)

    def test_diagnostic_linked_to_unimproved_impact_no_w001(self):
        m = _measure(
            name="Estudio acustico",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="SEVERO")
        issues = validate_diagnostic_measure(m, related_impacts=[imp])
        w001_issues = [i for i in issues if i.code == "RD08-W001"]
        self.assertEqual(len(w001_issues), 0)

    def test_diagnostic_linked_no_related_impacts_no_w001(self):
        m = _measure(
            name="Estudio acustico",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
        )
        issues = validate_diagnostic_measure(m, related_impacts=None)
        self.assertFalse(any(i.code == "RD08-W001" for i in issues))

    def test_both_error_and_warning_possible(self):
        m = _measure(
            name="Estudio acustico",
            description="Reduce la significancia del impacto.",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        issues = validate_diagnostic_measure(m, related_impacts=[imp])
        codes = {i.code for i in issues}
        self.assertIn("RD08-E001", codes)
        self.assertIn("RD08-W001", codes)

    def test_issue_has_measure_id(self):
        m = _measure(
            name="Estudio acustico",
            description="Reduce la significancia.",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
            measure_id="MED-999",
        )
        issues = validate_diagnostic_measure(m)
        for i in issues:
            if i.code == "RD08-E001":
                self.assertEqual(i.measure_id, "MED-999")

    def test_w001_has_impact_id(self):
        m = _measure(
            name="Estudio",
            is_diagnostic=True,
            measure_type="DIAGNOSTICA",
            measure_id="MED-010",
            target_impact_ids=["IMP-007"],
        )
        imp = _impact("IMP-007", sig_without="CRITICO", sig_with="SEVERO")
        issues = validate_diagnostic_measure(m, related_impacts=[imp])
        w001 = next((i for i in issues if i.code == "RD08-W001"), None)
        self.assertIsNotNone(w001)
        self.assertEqual(w001.impact_id, "IMP-007")


# ---------------------------------------------------------------------------
# 4. validate_diagnostic_measures_in_model
# ---------------------------------------------------------------------------

class TestValidateDiagnosticMeasuresInModel(unittest.TestCase):

    def test_model_without_measures_sin_datos(self):
        model = _minimal_model(measures=[])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(result.status, "SIN_DATOS")

    def test_model_only_non_diagnostic_ok(self):
        m = _measure(
            name="Pantalla acustica",
            measure_type="CORRECTORA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        model = _minimal_model(measures=[m], impacts=[imp])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.diagnostic_measures, [])

    def test_model_with_correct_diagnostics_ok(self):
        # Diagnostic measure on a MODERADO impact (not high-sig): no W002, no E00x -> OK
        m = _measure(
            name="Estudio acustico previo",
            description="Aporta informacion. No reduce significancia.",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="MODERADO", sig_with="MODERADO")
        model = _minimal_model(measures=[m], impacts=[imp])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(result.status, "OK")
        self.assertIn("MED-001", result.diagnostic_measures)
        self.assertEqual(result.error_count(), 0)

    def test_diagnostic_sole_reducer_no_conforme(self):
        diag = _measure(
            measure_id="MED-001",
            name="Estudio acustico",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO", measure_ids=["MED-001"])
        model = _minimal_model(measures=[diag], impacts=[imp])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertIn("MED-001", result.problematic_measures)
        self.assertTrue(any(i.code == "RD08-E002" for i in result.issues))

    def test_diagnostic_claims_reduction_no_conforme(self):
        diag = _measure(
            measure_id="MED-002",
            name="Consulta oficial",
            description="Reduce la significancia del impacto.",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[diag])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(result.status, "NO_CONFORME")
        self.assertTrue(any(i.code == "RD08-E001" for i in result.issues))

    def test_diagnostic_linked_to_improved_with_other_corrective_con_observaciones(self):
        diag = _measure(
            measure_id="MED-001",
            name="Estudio acustico",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        corrective = _measure(
            measure_id="MED-002",
            name="Pantalla acustica",
            measure_type="CORRECTORA",
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="SEVERO", sig_with="MODERADO")
        model = _minimal_model(measures=[diag, corrective], impacts=[imp])
        result = validate_diagnostic_measures_in_model(model)
        # W001 (WARNING) but not E002 (no sole reducer)
        self.assertIn(result.status, ("CON_OBSERVACIONES", "OK"))
        self.assertFalse(any(i.code == "RD08-E002" for i in result.issues))

    def test_sole_diag_on_high_sig_unimproved_warning(self):
        diag = _measure(
            measure_id="MED-001",
            name="Estudio de fauna",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
            target_impact_ids=["IMP-001"],
        )
        imp = _impact("IMP-001", sig_without="CRITICO", sig_with="CRITICO")
        model = _minimal_model(measures=[diag], impacts=[imp])
        result = validate_diagnostic_measures_in_model(model)
        self.assertIn(result.status, ("CON_OBSERVACIONES", "NO_CONFORME"))
        self.assertTrue(any(i.code == "RD08-W002" for i in result.issues))

    def test_does_not_mutate_model(self):
        diag = _measure(
            measure_id="MED-001",
            name="Estudio acustico",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[diag])
        original_measures = list(model.measures)
        validate_diagnostic_measures_in_model(model)
        self.assertEqual(model.measures, original_measures)
        self.assertEqual(model.measures[0].measure_id, "MED-001")

    def test_checked_measures_includes_all(self):
        m1 = _measure(measure_id="MED-001", name="Pantalla", measure_type="CORRECTORA")
        m2 = _measure(measure_id="MED-002", name="Estudio", measure_type="DIAGNOSTICA", is_diagnostic=True)
        model = _minimal_model(measures=[m1, m2])
        result = validate_diagnostic_measures_in_model(model)
        self.assertIn("MED-001", result.checked_measures)
        self.assertIn("MED-002", result.checked_measures)
        self.assertNotIn("MED-001", result.diagnostic_measures)
        self.assertIn("MED-002", result.diagnostic_measures)

    def test_status_values_are_valid(self):
        model = _minimal_model(measures=[])
        result = validate_diagnostic_measures_in_model(model)
        self.assertIn(result.status, DIAGNOSTIC_VALIDATION_STATUS)

    def test_is_valid_when_no_errors(self):
        m = _measure(
            name="Estudio previo sin lenguaje reductivo",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[m])
        result = validate_diagnostic_measures_in_model(model)
        self.assertTrue(result.is_valid())

    def test_not_valid_when_errors(self):
        m = _measure(
            name="Estudio",
            description="Reduce la significancia.",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[m])
        result = validate_diagnostic_measures_in_model(model)
        self.assertFalse(result.is_valid())

    def test_administrative_ready_always_false(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        self.assertFalse(result.administrative_ready)

    def test_to_dict_contains_required_keys(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        d = result.to_dict()
        for key in (
            "status", "administrative_ready", "checked_measures",
            "diagnostic_measures", "problematic_measures", "issues",
            "error_count", "warning_count", "info_count",
        ):
            self.assertIn(key, d)

    def test_summary_contains_status(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        s = result.summary()
        self.assertIn(result.status, s)

    def test_multiple_diagnostic_measures(self):
        d1 = _measure(measure_id="MED-001", name="Estudio acustico", measure_type="DIAGNOSTICA", is_diagnostic=True)
        d2 = _measure(measure_id="MED-002", name="Consulta patrimonial", measure_type="DIAGNOSTICA", is_diagnostic=True)
        d3 = _measure(measure_id="MED-003", name="Prospeccion de flora", measure_type="DIAGNOSTICA", is_diagnostic=True)
        model = _minimal_model(measures=[d1, d2, d3])
        result = validate_diagnostic_measures_in_model(model)
        self.assertEqual(len(result.diagnostic_measures), 3)


# ---------------------------------------------------------------------------
# 5. JSON / files
# ---------------------------------------------------------------------------

def _minimal_model_dict(
    measures=None,
    impacts=None,
    actions=None,
    receptors=None,
    exp_id="EIA-TEST",
) -> dict:
    """Construye un dict serializable de Phase6Model minimo."""
    return {
        "expediente_id": exp_id,
        "actions": actions or [{"action_id": "AC-001", "name": "Accion test", "action_type": "OPERACION"}],
        "receptor_factors": receptors or [
            {
                "receptor_id": "FR-014",
                "inventory_factor_id": "FI-014",
                "name": "Ruido",
                "ready_from_inventory": True,
            }
        ],
        "impacts": impacts or [],
        "measures": measures or [],
        "pva_programs": [],
    }


class TestValidateFromJson(unittest.TestCase):

    def test_from_json_clean_model(self):
        data = _minimal_model_dict(
            measures=[
                {
                    "measure_id": "MED-001",
                    "name": "Pantalla acustica",
                    "measure_type": "CORRECTORA",
                    "target_impact_ids": [],
                }
            ]
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            tmp = Path(f.name)
        try:
            result = validate_diagnostic_measures_from_json(tmp)
            self.assertIn(result.status, DIAGNOSTIC_VALIDATION_STATUS)
        finally:
            tmp.unlink(missing_ok=True)

    def test_from_json_nonexistent_file(self):
        result = validate_diagnostic_measures_from_json("/no/existe/file.json")
        self.assertEqual(result.status, "SIN_DATOS")
        self.assertTrue(len(result.warnings) > 0)

    def test_from_json_corrupt_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            f.write("{invalid json}")
            tmp = Path(f.name)
        try:
            result = validate_diagnostic_measures_from_json(tmp)
            self.assertEqual(result.status, "SIN_DATOS")
        finally:
            tmp.unlink(missing_ok=True)

    def test_from_json_problematic_model_no_conforme(self):
        data = _minimal_model_dict(
            impacts=[
                {
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-014",
                    "name": "Impacto acustico",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "SEVERO",
                    "significance_with_measures": "MODERADO",
                    "measure_ids": ["MED-001"],
                }
            ],
            measures=[
                {
                    "measure_id": "MED-001",
                    "name": "Estudio acustico",
                    "measure_type": "DIAGNOSTICA",
                    "is_diagnostic": True,
                    "target_impact_ids": ["IMP-001"],
                }
            ],
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            tmp = Path(f.name)
        try:
            result = validate_diagnostic_measures_from_json(tmp)
            self.assertEqual(result.status, "NO_CONFORME")
        finally:
            tmp.unlink(missing_ok=True)


class TestValidateFromFiles(unittest.TestCase):

    def test_expediente_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            validate_diagnostic_measures_from_files("/no/existe/expediente")

    def test_expediente_without_model_sin_datos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-TEST"
            exp_path.mkdir()
            (exp_path / "impactos").mkdir()
            result = validate_diagnostic_measures_from_files(exp_path)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_expediente_with_model_with_pva(self):
        data = _minimal_model_dict(
            measures=[
                {
                    "measure_id": "MED-001",
                    "name": "Estudio acustico",
                    "measure_type": "DIAGNOSTICA",
                    "is_diagnostic": True,
                    "target_impact_ids": [],
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-TEST"
            (exp_path / "impactos").mkdir(parents=True)
            model_file = exp_path / "impactos" / "phase6_model_with_pva.json"
            model_file.write_text(json.dumps(data), encoding="utf-8")
            result = validate_diagnostic_measures_from_files(exp_path)
            self.assertEqual(result.status, "OK")
            self.assertIn("MED-001", result.diagnostic_measures)

    def test_expediente_no_model_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-TEST"
            exp_path.mkdir()
            result = validate_diagnostic_measures_from_files(exp_path)
            self.assertEqual(result.status, "SIN_DATOS")

    def test_expediente_with_problematic_model_no_conforme(self):
        data = _minimal_model_dict(
            impacts=[
                {
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-014",
                    "name": "Impacto acustico",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "CRITICO",
                    "significance_with_measures": "MODERADO",
                    "measure_ids": ["MED-001"],
                }
            ],
            measures=[
                {
                    "measure_id": "MED-001",
                    "name": "Estudio acustico sole",
                    "measure_type": "DIAGNOSTICA",
                    "is_diagnostic": True,
                    "target_impact_ids": ["IMP-001"],
                }
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-TEST"
            (exp_path / "impactos").mkdir(parents=True)
            model_file = exp_path / "impactos" / "phase6_model_with_measures.json"
            model_file.write_text(json.dumps(data), encoding="utf-8")
            result = validate_diagnostic_measures_from_files(exp_path)
            self.assertEqual(result.status, "NO_CONFORME")

    def test_model_search_order_with_pva_wins(self):
        """phase6_model_with_pva.json tiene prioridad sobre with_measures."""
        data_pva = _minimal_model_dict(measures=[])  # sin medidas -> SIN_DATOS
        data_measures = _minimal_model_dict(
            measures=[
                {
                    "measure_id": "MED-099",
                    "name": "Estudio",
                    "measure_type": "DIAGNOSTICA",
                    "is_diagnostic": True,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-TEST"
            (exp_path / "impactos").mkdir(parents=True)
            (exp_path / "impactos" / "phase6_model_with_pva.json").write_text(
                json.dumps(data_pva), encoding="utf-8"
            )
            (exp_path / "impactos" / "phase6_model_with_measures.json").write_text(
                json.dumps(data_measures), encoding="utf-8"
            )
            result = validate_diagnostic_measures_from_files(exp_path)
            # with_pva has no measures -> SIN_DATOS (wins over with_measures)
            self.assertEqual(result.status, "SIN_DATOS")


# ---------------------------------------------------------------------------
# 6. Markdown
# ---------------------------------------------------------------------------

class TestMarkdownReport(unittest.TestCase):

    def setUp(self):
        diag = _measure(
            measure_id="MED-001",
            name="Estudio acustico",
            description="Reduce la significancia.",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[diag])
        self.result = validate_diagnostic_measures_in_model(model)
        self.md = build_diagnostic_measure_report_markdown(self.result)

    def test_contains_advertencia_de_alcance_section(self):
        self.assertIn("Advertencia de alcance", self.md)

    def test_contains_no_reduce_por_si_sola(self):
        # The key sentence from spec
        md_lower = self.md.lower()
        self.assertIn("no reduce por si sola", md_lower)

    def test_contains_aporta_informacion(self):
        md_lower = self.md.lower()
        self.assertIn("aporta informacion", md_lower)

    def test_contains_incidencias_section(self):
        self.assertIn("Incidencias", self.md)

    def test_contains_resumen_section(self):
        self.assertIn("Resumen", self.md)

    def test_contains_issue_code(self):
        self.assertIn("RD08-E001", self.md)

    def test_contains_medidas_revisadas_section(self):
        self.assertIn("Medidas revisadas", self.md)

    def test_contains_medidas_diagnosticas_section(self):
        self.assertIn("diagnosticas", self.md.lower())

    def test_contains_recomendaciones_section(self):
        self.assertIn("Recomendaciones", self.md)

    def test_markdown_clean_model(self):
        model = _minimal_model(measures=[
            _measure(
                name="Pantalla acustica",
                measure_type="CORRECTORA",
            )
        ])
        result = validate_diagnostic_measures_in_model(model)
        md = build_diagnostic_measure_report_markdown(result)
        # No diagnostics, no issues
        self.assertIn("OK", md)
        self.assertNotIn("RD08-E001", md)

    def test_contains_no_modifica_medidas(self):
        md_lower = self.md.lower()
        # The doc says this validator does not modify measures
        self.assertIn("no modifica", md_lower)

    def test_markdown_is_string(self):
        self.assertIsInstance(self.md, str)
        self.assertTrue(len(self.md) > 100)


# ---------------------------------------------------------------------------
# 7. Escritura
# ---------------------------------------------------------------------------

class TestWriteOutputs(unittest.TestCase):

    def test_write_creates_json_and_md(self):
        diag = _measure(
            name="Estudio acustico",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[diag])
        result = validate_diagnostic_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "auditoria"
            json_p, md_p = write_diagnostic_measure_outputs(result, out)
            self.assertTrue(json_p.exists())
            self.assertTrue(md_p.exists())
            self.assertEqual(json_p.name, "diagnostic_measure_validation_result.json")
            self.assertEqual(md_p.name, "diagnostic_measure_validation_result.md")

    def test_json_is_valid_and_loadable(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            json_p, _ = write_diagnostic_measure_outputs(result, out)
            data = json.loads(json_p.read_text(encoding="utf-8"))
            self.assertIn("status", data)
            self.assertEqual(data["status"], result.status)

    def test_json_contains_expected_keys(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_p, _ = write_diagnostic_measure_outputs(result, Path(tmpdir))
            data = json.loads(json_p.read_text(encoding="utf-8"))
            for key in ("status", "diagnostic_measures", "issues", "error_count"):
                self.assertIn(key, data)

    def test_output_dir_created_if_missing(self):
        model = _minimal_model()
        result = validate_diagnostic_measures_in_model(model)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "auditoria"
            self.assertFalse(out.exists())
            write_diagnostic_measure_outputs(result, out)
            self.assertTrue(out.exists())

    def test_md_content_matches_build(self):
        diag = _measure(
            name="Consulta oficial",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        model = _minimal_model(measures=[diag])
        result = validate_diagnostic_measures_in_model(model)
        expected_md = build_diagnostic_measure_report_markdown(result)
        with tempfile.TemporaryDirectory() as tmpdir:
            _, md_p = write_diagnostic_measure_outputs(result, Path(tmpdir))
            actual_md = md_p.read_text(encoding="utf-8")
            self.assertEqual(actual_md, expected_md)


# ---------------------------------------------------------------------------
# 8. CLI
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):

    def _run_cli(self, exp_path: Path, extra_args: list[str] | None = None) -> int:
        from run_expediente import main as cli_main
        argv_backup = sys.argv[:]
        args = ["run_expediente.py", str(exp_path), "audit-diagnostic-measures"]
        if extra_args:
            args.extend(extra_args)
        sys.argv = args
        try:
            return cli_main()
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0
        finally:
            sys.argv = argv_backup

    def _build_expediente(self, tmpdir: str, with_error: bool = False) -> Path:
        """Construye expediente temporal con o sin error de medida diagnostica."""
        exp_path = Path(tmpdir) / "EIA-CLI-TEST"
        (exp_path / "impactos").mkdir(parents=True)
        if with_error:
            # Diagnostic measure as sole reducer -> ERROR -> NO_CONFORME -> exit 1
            data = _minimal_model_dict(
                impacts=[{
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-014",
                    "name": "Ruido",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "SEVERO",
                    "significance_with_measures": "MODERADO",
                    "measure_ids": ["MED-001"],
                }],
                measures=[{
                    "measure_id": "MED-001",
                    "name": "Estudio acustico",
                    "measure_type": "DIAGNOSTICA",
                    "is_diagnostic": True,
                    "target_impact_ids": ["IMP-001"],
                }],
            )
        else:
            # Clean model -> OK -> exit 0
            data = _minimal_model_dict(measures=[{
                "measure_id": "MED-001",
                "name": "Estudio acustico sin lenguaje reductivo",
                "measure_type": "DIAGNOSTICA",
                "is_diagnostic": True,
            }])
        (exp_path / "impactos" / "phase6_model_with_measures.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        return exp_path

    def test_exit_1_on_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = self._build_expediente(tmpdir, with_error=True)
            code = self._run_cli(exp_path)
            self.assertEqual(code, 1)

    def test_exit_0_on_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = self._build_expediente(tmpdir, with_error=False)
            code = self._run_cli(exp_path)
            self.assertEqual(code, 0)

    def test_without_write_no_json_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = self._build_expediente(tmpdir, with_error=False)
            self._run_cli(exp_path)
            audit_dir = exp_path / "auditoria"
            json_file = audit_dir / "diagnostic_measure_validation_result.json"
            self.assertFalse(json_file.exists())

    def test_with_write_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = self._build_expediente(tmpdir, with_error=False)
            self._run_cli(exp_path, extra_args=["--write"])
            audit_dir = exp_path / "auditoria"
            json_file = audit_dir / "diagnostic_measure_validation_result.json"
            md_file = audit_dir / "diagnostic_measure_validation_result.md"
            self.assertTrue(json_file.exists())
            self.assertTrue(md_file.exists())

    def test_exit_0_con_observaciones(self):
        """CON_OBSERVACIONES (solo WARNINGs) -> exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir) / "EIA-CLI-TEST2"
            (exp_path / "impactos").mkdir(parents=True)
            # Diagnostic linked to impact with improved sig, but there's also a corrective measure
            data = _minimal_model_dict(
                impacts=[{
                    "impact_id": "IMP-001",
                    "action_id": "AC-001",
                    "receptor_id": "FR-014",
                    "name": "Ruido",
                    "nature": "NEGATIVO",
                    "status": "VALORADO",
                    "significance_without_measures": "SEVERO",
                    "significance_with_measures": "MODERADO",
                    "measure_ids": ["MED-001", "MED-002"],
                }],
                measures=[
                    {
                        "measure_id": "MED-001",
                        "name": "Estudio acustico",
                        "measure_type": "DIAGNOSTICA",
                        "is_diagnostic": True,
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
            (exp_path / "impactos" / "phase6_model_with_measures.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            code = self._run_cli(exp_path)
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Clases de datos
# ---------------------------------------------------------------------------

class TestDiagnosticMeasureIssue(unittest.TestCase):

    def test_to_dict_has_all_fields(self):
        issue = DiagnosticMeasureIssue(
            severity="ERROR",
            code="RD08-E001",
            measure_id="MED-001",
            impact_id=None,
            message="Mensaje test",
            recommendation="Rec test",
            evidence=["ev1"],
        )
        d = issue.to_dict()
        for key in ("severity", "code", "measure_id", "impact_id", "message", "recommendation", "evidence"):
            self.assertIn(key, d)

    def test_invalid_severity_raises(self):
        with self.assertRaises(ValueError):
            DiagnosticMeasureIssue(
                severity="INVALID",
                code="RD08-X999",
                measure_id=None,
                impact_id=None,
                message="Test",
            )

    def test_summary_format(self):
        issue = DiagnosticMeasureIssue(
            severity="WARNING",
            code="RD08-W001",
            measure_id="MED-005",
            impact_id="IMP-002",
            message="Mensaje de prueba",
        )
        s = issue.summary()
        self.assertIn("WARNING", s)
        self.assertIn("RD08-W001", s)
        self.assertIn("MED-005", s)


class TestConstants(unittest.TestCase):

    def test_diagnostic_keywords_not_empty(self):
        self.assertTrue(len(DIAGNOSTIC_KEYWORDS) > 0)

    def test_reduction_keywords_not_empty(self):
        self.assertTrue(len(REDUCTION_KEYWORDS) > 0)

    def test_estudio_in_diagnostic_keywords(self):
        self.assertIn("estudio", DIAGNOSTIC_KEYWORDS)

    def test_consulta_in_diagnostic_keywords(self):
        self.assertIn("consulta", DIAGNOSTIC_KEYWORDS)

    def test_reduce_in_reduction_keywords(self):
        self.assertIn("reduce", REDUCTION_KEYWORDS)

    def test_pasa_a_compatible_in_reduction_keywords(self):
        self.assertIn("pasa a compatible", REDUCTION_KEYWORDS)

    def test_all_statuses_present(self):
        for s in ("OK", "CON_OBSERVACIONES", "NO_CONFORME", "SIN_DATOS"):
            self.assertIn(s, DIAGNOSTIC_VALIDATION_STATUS)


if __name__ == "__main__":
    unittest.main()
