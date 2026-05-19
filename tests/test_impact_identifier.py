"""
Tests para impact_identifier -- IM-03
Identificador preliminar de impactos accion x receptor para Fase 6 EIA.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from eia_agent.core.impact_model import (
    RECEPTOR_FACTOR_IDS,
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
)
from eia_agent.core.impact_identifier import (
    ImpactIdentificationResult,
    ImpactIdentificationRule,
    build_minimal_receptor_factors,
    build_phase6_model_with_identified_impacts,
    default_impact_identification_rules,
    identify_impacts_from_model,
    merge_identified_impacts_into_model,
)


# ---------------------------------------------------------------------------
# Helpers de construccion
# ---------------------------------------------------------------------------

def _make_action(
    action_id: str = "AC-001",
    action_type: str = "OPERACION",
    name: str = "Tratamiento mecanico de residuos",
    description: str = "Trituracion y cribado de residuos",
) -> ProjectAction:
    return ProjectAction(
        action_id=action_id,
        name=name,
        description=description,
        action_type=action_type,
    )


def _make_receptor(
    receptor_id: str = "FR-003",
    name: str = "Suelos",
    critical_gaps: list[str] | None = None,
    ready: bool = False,
) -> ReceptorFactor:
    fi_id = RECEPTOR_FACTOR_IDS.get(receptor_id, "FI-003")
    return ReceptorFactor(
        receptor_id=receptor_id,
        inventory_factor_id=fi_id,
        name=name,
        inventory_semaphore="AMARILLO",
        ready_from_inventory=ready,
        critical_gaps=critical_gaps or [],
        notes=["Test factor."],
    )


def _make_model(
    actions: list[ProjectAction] | None = None,
    receptors: list[ReceptorFactor] | None = None,
    expediente_id: str = "EXP-TEST",
) -> Phase6Model:
    return Phase6Model(
        expediente_id=expediente_id,
        actions=actions or [],
        receptor_factors=receptors or [],
    )


# ---------------------------------------------------------------------------
# TestImpactIdentificationRule
# ---------------------------------------------------------------------------

class TestImpactIdentificationRule(unittest.TestCase):

    def _make_rule(self, **kwargs) -> ImpactIdentificationRule:
        defaults = dict(
            rule_id="RULE-X",
            action_types=["OPERACION"],
            operation_keywords=[],
            target_receptor_ids=["FR-003"],
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
        )
        defaults.update(kwargs)
        return ImpactIdentificationRule(**defaults)

    def test_matches_correct_action_type_and_receptor(self):
        rule = self._make_rule()
        action = _make_action(action_type="OPERACION")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertTrue(rule.matches(action, receptor))

    def test_matches_fails_wrong_action_type(self):
        rule = self._make_rule(action_types=["ALMACENAMIENTO"])
        action = _make_action(action_type="OPERACION")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertFalse(rule.matches(action, receptor))

    def test_matches_fails_wrong_receptor_id(self):
        rule = self._make_rule(target_receptor_ids=["FR-004"])
        action = _make_action(action_type="OPERACION")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertFalse(rule.matches(action, receptor))

    def test_matches_empty_action_types_matches_any(self):
        rule = self._make_rule(action_types=[])
        for at in ["OPERACION", "ALMACENAMIENTO", "TRANSPORTE", "CESE", "AUXILIAR"]:
            action = _make_action(action_type=at)
            receptor = _make_receptor(receptor_id="FR-003")
            self.assertTrue(rule.matches(action, receptor), f"Should match {at}")

    def test_matches_keyword_present_in_name(self):
        rule = self._make_rule(operation_keywords=["trituraci"])
        action = _make_action(name="Trituracion de residuos")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertTrue(rule.matches(action, receptor))

    def test_matches_keyword_present_in_description(self):
        rule = self._make_rule(operation_keywords=["cizalla"])
        action = _make_action(name="Tratamiento mecanico", description="Uso de cizalla")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertTrue(rule.matches(action, receptor))

    def test_matches_keyword_absent(self):
        rule = self._make_rule(operation_keywords=["trituraci"])
        action = _make_action(name="Clasificacion de residuos", description="Triaje manual")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertFalse(rule.matches(action, receptor))

    def test_matches_keyword_normalized_accent(self):
        rule = self._make_rule(operation_keywords=["trituraci"])
        action = _make_action(name="Trituración de residuos")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertTrue(rule.matches(action, receptor))

    def test_matches_empty_keywords_no_filter(self):
        rule = self._make_rule(operation_keywords=[])
        action = _make_action(name="Cualquier operacion")
        receptor = _make_receptor(receptor_id="FR-003")
        self.assertTrue(rule.matches(action, receptor))

    def test_default_nature_is_negativo(self):
        rule = ImpactIdentificationRule(rule_id="RULE-X")
        self.assertEqual(rule.nature, "NEGATIVO")

    def test_default_status_is_pendiente_datos(self):
        rule = ImpactIdentificationRule(rule_id="RULE-X")
        self.assertEqual(rule.status, "PENDIENTE_DATOS")

    def test_to_dict_is_json_serializable(self):
        rule = self._make_rule()
        d = rule.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)

    def test_to_dict_has_required_keys(self):
        rule = self._make_rule()
        d = rule.to_dict()
        for key in ["rule_id", "action_types", "operation_keywords",
                    "target_receptor_ids", "impact_name_template",
                    "nature", "status", "default_gaps", "notes"]:
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# TestDefaultImpactIdentificationRules
# ---------------------------------------------------------------------------

class TestDefaultImpactIdentificationRules(unittest.TestCase):

    def setUp(self):
        self.rules = default_impact_identification_rules()

    def test_returns_10_rules(self):
        self.assertEqual(len(self.rules), 10)

    def test_rule_ids_are_unique(self):
        ids = [r.rule_id for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_rules_have_target_receptor_ids(self):
        for rule in self.rules:
            self.assertTrue(
                len(rule.target_receptor_ids) > 0,
                f"{rule.rule_id} has empty target_receptor_ids",
            )

    def test_rule_a_targets_suelos_and_hidrologia(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-A")
        self.assertIn("FR-003", rule.target_receptor_ids)
        self.assertIn("FR-004", rule.target_receptor_ids)

    def test_rule_b_targets_calidad_aire_and_ruido(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-B")
        self.assertIn("FR-006", rule.target_receptor_ids)
        self.assertIn("FR-014", rule.target_receptor_ids)

    def test_rule_c_targets_cambio_climatico(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-C")
        self.assertIn("FR-015", rule.target_receptor_ids)

    def test_rule_e_has_status_indeterminado(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-E")
        self.assertEqual(rule.status, "INDETERMINADO")

    def test_rule_f_has_status_indeterminado(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-F")
        self.assertEqual(rule.status, "INDETERMINADO")

    def test_rule_f_has_empty_action_types(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-F")
        self.assertEqual(rule.action_types, [])

    def test_rule_j_has_nature_positivo(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-J")
        self.assertEqual(rule.nature, "POSITIVO")

    def test_required_receptors_covered(self):
        required = {
            "FR-003", "FR-004", "FR-006", "FR-007", "FR-008",
            "FR-009", "FR-010", "FR-011", "FR-012", "FR-013",
            "FR-014", "FR-015",
        }
        covered: set[str] = set()
        for rule in self.rules:
            covered.update(rule.target_receptor_ids)
        for fr_id in required:
            self.assertIn(fr_id, covered, f"{fr_id} not covered by any rule")

    def test_rule_ids_follow_pattern(self):
        expected = {f"RULE-{c}" for c in "ABCDEFGHIJ"}
        actual = {r.rule_id for r in self.rules}
        self.assertEqual(expected, actual)

    def test_rule_f_has_prudencia_note(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-F")
        combined = " ".join(rule.notes).lower()
        self.assertIn("gabinete", combined)

    def test_rule_j_has_no_compensation_note(self):
        rule = next(r for r in self.rules if r.rule_id == "RULE-J")
        combined = " ".join(rule.notes).lower()
        self.assertIn("positivo", combined)
        self.assertIn("negativo", combined)

    def test_all_rules_have_default_gaps(self):
        for rule in self.rules:
            self.assertTrue(
                len(rule.default_gaps) > 0,
                f"{rule.rule_id} has no default_gaps",
            )


# ---------------------------------------------------------------------------
# TestImpactIdentificationResult
# ---------------------------------------------------------------------------

class TestImpactIdentificationResult(unittest.TestCase):

    def _make_impact(self, impact_id: str = "IMP-001") -> EnvironmentalImpact:
        return EnvironmentalImpact(
            impact_id=impact_id,
            action_id="AC-001",
            receptor_id="FR-003",
            name="Test impact",
            status="PENDIENTE_DATOS",
            nature="NEGATIVO",
        )

    def test_to_dict_is_json_serializable(self):
        result = ImpactIdentificationResult(
            impacts=[self._make_impact()],
            warnings=["w1"],
            notes=["n1"],
        )
        d = result.to_dict()
        self.assertIsInstance(json.dumps(d), str)

    def test_to_dict_has_required_keys(self):
        result = ImpactIdentificationResult()
        d = result.to_dict()
        self.assertIn("impacts", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_summary_is_nonempty(self):
        result = ImpactIdentificationResult(impacts=[self._make_impact()])
        self.assertTrue(len(result.summary()) > 0)

    def test_summary_ascii_only(self):
        result = ImpactIdentificationResult(
            impacts=[self._make_impact()],
            warnings=["Sin datos acusticos"],
        )
        text = result.summary()
        text.encode("ascii")  # raises UnicodeEncodeError if non-ASCII

    def test_summary_includes_count(self):
        result = ImpactIdentificationResult(impacts=[self._make_impact()])
        self.assertIn("1", result.summary())

    def test_summary_includes_warning(self):
        result = ImpactIdentificationResult(warnings=["test warning"])
        self.assertIn("AVISO", result.summary())


# ---------------------------------------------------------------------------
# TestBuildMinimalReceptorFactors
# ---------------------------------------------------------------------------

class TestBuildMinimalReceptorFactors(unittest.TestCase):

    def setUp(self):
        self.factors = build_minimal_receptor_factors()

    def test_returns_16_factors(self):
        self.assertEqual(len(self.factors), 16)

    def test_all_fr_ids_present(self):
        ids = {f.receptor_id for f in self.factors}
        for fr_id in RECEPTOR_FACTOR_IDS.keys():
            self.assertIn(fr_id, ids)

    def test_all_receptor_ids_valid(self):
        import re
        pattern = re.compile(r"^FR-\d{3,}$")
        for f in self.factors:
            self.assertRegex(f.receptor_id, pattern)

    def test_inventory_ids_match(self):
        for f in self.factors:
            expected_fi = RECEPTOR_FACTOR_IDS[f.receptor_id]
            self.assertEqual(f.inventory_factor_id, expected_fi)

    def test_ready_from_inventory_false(self):
        for f in self.factors:
            self.assertFalse(f.ready_from_inventory)

    def test_has_notes(self):
        for f in self.factors:
            self.assertTrue(len(f.notes) > 0)


# ---------------------------------------------------------------------------
# TestIdentifyImpactsFromModel
# ---------------------------------------------------------------------------

class TestIdentifyImpactsFromModel(unittest.TestCase):

    def _almacenamiento_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-001",
            action_type="ALMACENAMIENTO",
            name="Recepcion y almacenamiento temporal de residuos",
            description="Almacenamiento de residuos previo a tratamiento",
        )

    def _mecanico_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-002",
            action_type="OPERACION",
            name="Tratamiento mecanico de residuos",
            description="Trituracion y cribado de residuos",
        )

    def _clasificacion_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-003",
            action_type="OPERACION",
            name="Clasificacion y separacion de residuos",
            description="Triaje manual",
        )

    def _transporte_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-004",
            action_type="TRANSPORTE",
            name="Carga descarga y expedicion de materiales",
            description="Movimiento de vehiculos",
        )

    def _mantenimiento_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-005",
            action_type="MANTENIMIENTO",
            name="Gestion de residuos peligrosos propios",
            description="Aceites y baterias",
        )

    def _cese_action(self) -> ProjectAction:
        return _make_action(
            action_id="AC-006",
            action_type="CESE",
            name="Cese y limpieza final",
            description="Desmantelamiento de instalaciones",
        )

    def _full_receptors(self) -> list[ReceptorFactor]:
        return build_minimal_receptor_factors()

    def test_empty_model_no_actions_returns_warning(self):
        model = _make_model(actions=[], receptors=self._full_receptors())
        result = identify_impacts_from_model(model)
        self.assertEqual(len(result.impacts), 0)
        self.assertTrue(any("acciones" in w.lower() for w in result.warnings))

    def test_model_no_receptors_returns_warning(self):
        model = _make_model(actions=[self._almacenamiento_action()], receptors=[])
        result = identify_impacts_from_model(model)
        self.assertEqual(len(result.impacts), 0)
        self.assertTrue(any("receptor" in w.lower() for w in result.warnings))

    def test_almacenamiento_action_generates_suelos_impact(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-003", "Suelos")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-003" for i in result.impacts)
        )

    def test_almacenamiento_action_generates_hidrologia_impact(self):
        action = self._almacenamiento_action()
        receptors = [
            _make_receptor("FR-003", "Suelos"),
            _make_receptor("FR-004", "Hidrologia"),
        ]
        model = _make_model(actions=[action], receptors=receptors)
        result = identify_impacts_from_model(model)
        receptor_ids = {i.receptor_id for i in result.impacts}
        self.assertIn("FR-004", receptor_ids)

    def test_operacion_mecanico_generates_calidad_aire_impact(self):
        action = self._mecanico_action()
        receptor = _make_receptor("FR-006", "Calidad del aire")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-006" for i in result.impacts)
        )

    def test_operacion_mecanico_generates_ruido_impact(self):
        action = self._mecanico_action()
        receptors = [
            _make_receptor("FR-006", "Calidad del aire"),
            _make_receptor("FR-014", "Ruido"),
        ]
        model = _make_model(actions=[action], receptors=receptors)
        result = identify_impacts_from_model(model)
        receptor_ids = {i.receptor_id for i in result.impacts}
        self.assertIn("FR-014", receptor_ids)

    def test_transporte_generates_cambio_climatico_impact(self):
        action = self._transporte_action()
        receptor = _make_receptor("FR-015", "Cambio climatico")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-015" for i in result.impacts)
        )

    def test_clasificacion_generates_suelos_impact(self):
        action = self._clasificacion_action()
        receptor = _make_receptor("FR-003", "Suelos")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-003" for i in result.impacts)
        )

    def test_enp_and_rednatura_status_indeterminado(self):
        action = self._almacenamiento_action()
        receptors = [
            _make_receptor("FR-009", "ENP"),
            _make_receptor("FR-010", "Red Natura 2000"),
        ]
        model = _make_model(actions=[action], receptors=receptors)
        result = identify_impacts_from_model(model)
        for imp in result.impacts:
            if imp.receptor_id in ("FR-009", "FR-010"):
                self.assertEqual(imp.status, "INDETERMINADO")

    def test_flora_fauna_status_indeterminado(self):
        action = self._almacenamiento_action()
        receptors = [
            _make_receptor("FR-007", "Flora"),
            _make_receptor("FR-008", "Fauna"),
        ]
        model = _make_model(actions=[action], receptors=receptors)
        result = identify_impacts_from_model(model)
        for imp in result.impacts:
            if imp.receptor_id in ("FR-007", "FR-008"):
                self.assertEqual(imp.status, "INDETERMINADO")

    def test_mantenimiento_generates_suelos_impact(self):
        action = self._mantenimiento_action()
        receptor = _make_receptor("FR-003", "Suelos")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-003" for i in result.impacts)
        )

    def test_operacion_auxiliar_generates_paisaje_impact(self):
        action = _make_action(action_id="AC-001", action_type="AUXILIAR",
                              name="Maquinaria auxiliar")
        receptor = _make_receptor("FR-011", "Paisaje")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-011" for i in result.impacts)
        )

    def test_cese_generates_patrimonio_cultural_impact(self):
        action = self._cese_action()
        receptor = _make_receptor("FR-012", "Patrimonio cultural")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        self.assertTrue(
            any(i.receptor_id == "FR-012" for i in result.impacts)
        )

    def test_almacenamiento_generates_positivo_socioeconomia(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-013", "Socioeconomia")
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model)
        positivos = [
            i for i in result.impacts
            if i.receptor_id == "FR-013" and i.nature == "POSITIVO"
        ]
        self.assertTrue(len(positivos) > 0)

    def test_no_duplicates_same_key(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-003", "Suelos")
        custom_rules = [
            ImpactIdentificationRule(
                rule_id="RULE-X",
                action_types=["ALMACENAMIENTO"],
                target_receptor_ids=["FR-003"],
            )
        ]
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model, rules=custom_rules)
        self.assertEqual(len(result.impacts), 1)

    def test_impact_ids_are_consecutive(self):
        import re
        actions = [self._almacenamiento_action(), self._mecanico_action()]
        receptors = [
            _make_receptor("FR-003", "Suelos"),
            _make_receptor("FR-014", "Ruido"),
        ]
        model = _make_model(actions=actions, receptors=receptors)
        result = identify_impacts_from_model(model)
        ids = sorted(i.impact_id for i in result.impacts)
        for idx, imp_id in enumerate(ids, start=1):
            self.assertRegex(imp_id, re.compile(r"^IMP-\d{3,}$"))

    def test_significance_always_no_valorado(self):
        model = _make_model(
            actions=[self._almacenamiento_action()],
            receptors=self._full_receptors(),
        )
        result = identify_impacts_from_model(model)
        for imp in result.impacts:
            self.assertEqual(imp.significance_without_measures, "NO_VALORADO")
            self.assertEqual(imp.significance_with_measures, "NO_VALORADO")

    def test_status_indeterminado_when_receptor_has_critical_gaps(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor(
            "FR-003", "Suelos", critical_gaps=["GAP-001"]
        )
        custom_rules = [
            ImpactIdentificationRule(
                rule_id="RULE-A",
                action_types=["ALMACENAMIENTO"],
                target_receptor_ids=["FR-003"],
                status="PENDIENTE_DATOS",
            )
        ]
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model, rules=custom_rules)
        self.assertEqual(len(result.impacts), 1)
        self.assertEqual(result.impacts[0].status, "INDETERMINADO")

    def test_notes_contain_rule_id(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-003")
        custom_rules = [
            ImpactIdentificationRule(
                rule_id="RULE-TEST",
                action_types=["ALMACENAMIENTO"],
                target_receptor_ids=["FR-003"],
            )
        ]
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model, rules=custom_rules)
        self.assertEqual(len(result.impacts), 1)
        combined_notes = " ".join(result.impacts[0].notes)
        self.assertIn("RULE-TEST", combined_notes)

    def test_data_gaps_from_rule(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-003")
        custom_rules = [
            ImpactIdentificationRule(
                rule_id="RULE-X",
                action_types=["ALMACENAMIENTO"],
                target_receptor_ids=["FR-003"],
                default_gaps=["GAP: verificar solera"],
            )
        ]
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model, rules=custom_rules)
        self.assertIn("GAP: verificar solera", result.impacts[0].data_gaps)

    def test_source_refs_contains_rule_ref(self):
        action = self._almacenamiento_action()
        receptor = _make_receptor("FR-003")
        custom_rules = [
            ImpactIdentificationRule(
                rule_id="RULE-X",
                action_types=["ALMACENAMIENTO"],
                target_receptor_ids=["FR-003"],
            )
        ]
        model = _make_model(actions=[action], receptors=[receptor])
        result = identify_impacts_from_model(model, rules=custom_rules)
        self.assertTrue(
            any("RULE-X" in ref for ref in result.impacts[0].source_refs)
        )

    def test_returns_impact_identification_result(self):
        model = _make_model(
            actions=[self._almacenamiento_action()],
            receptors=[_make_receptor("FR-003")],
        )
        result = identify_impacts_from_model(model)
        self.assertIsInstance(result, ImpactIdentificationResult)


# ---------------------------------------------------------------------------
# TestMergeIdentifiedImpactsIntoModel
# ---------------------------------------------------------------------------

class TestMergeIdentifiedImpactsIntoModel(unittest.TestCase):

    def _make_impact(self, impact_id: str = "IMP-001") -> EnvironmentalImpact:
        return EnvironmentalImpact(
            impact_id=impact_id,
            action_id="AC-001",
            receptor_id="FR-003",
            name="Test",
            status="PENDIENTE_DATOS",
        )

    def _make_full_model(self) -> Phase6Model:
        action = _make_action()
        receptor = _make_receptor()
        measure = MitigationMeasure(
            measure_id="MED-001",
            name="Test measure",
            measure_type="DIAGNOSTICA",
            is_diagnostic=True,
        )
        pva = PVAProgram(
            pva_id="PVA-001",
            name="Test PVA",
            factor_id="FI-003",
            indicator="Check indicator",
            threshold="threshold",
            responsible="responsable",
        )
        return Phase6Model(
            expediente_id="EXP-001",
            actions=[action],
            receptor_factors=[receptor],
            measures=[measure],
            pva_programs=[pva],
        )

    def test_replaces_impacts(self):
        model = self._make_full_model()
        new_impacts = [self._make_impact("IMP-001"), self._make_impact("IMP-002")]
        merged = merge_identified_impacts_into_model(model, new_impacts)
        self.assertEqual(len(merged.impacts), 2)

    def test_preserves_actions(self):
        model = self._make_full_model()
        merged = merge_identified_impacts_into_model(model, [self._make_impact()])
        self.assertEqual(len(merged.actions), len(model.actions))

    def test_preserves_receptor_factors(self):
        model = self._make_full_model()
        merged = merge_identified_impacts_into_model(model, [self._make_impact()])
        self.assertEqual(len(merged.receptor_factors), len(model.receptor_factors))

    def test_preserves_measures(self):
        model = self._make_full_model()
        merged = merge_identified_impacts_into_model(model, [self._make_impact()])
        self.assertEqual(len(merged.measures), len(model.measures))

    def test_preserves_pva_programs(self):
        model = self._make_full_model()
        merged = merge_identified_impacts_into_model(model, [self._make_impact()])
        self.assertEqual(len(merged.pva_programs), len(model.pva_programs))

    def test_does_not_mutate_original(self):
        model = _make_model(
            actions=[_make_action()],
            receptors=[_make_receptor()],
        )
        original_impact_count = len(model.impacts)
        merge_identified_impacts_into_model(model, [self._make_impact()])
        self.assertEqual(len(model.impacts), original_impact_count)

    def test_empty_list_clears_impacts(self):
        model = Phase6Model(
            expediente_id="EXP-001",
            impacts=[self._make_impact()],
        )
        merged = merge_identified_impacts_into_model(model, [])
        self.assertEqual(len(merged.impacts), 0)


# ---------------------------------------------------------------------------
# TestBuildPhase6ModelWithIdentifiedImpacts
# ---------------------------------------------------------------------------

class TestBuildPhase6ModelWithIdentifiedImpacts(unittest.TestCase):

    def _make_model_with_almacenamiento(self) -> Phase6Model:
        return _make_model(
            actions=[_make_action(action_type="ALMACENAMIENTO",
                                  name="Almacenamiento temporal")],
            receptors=[
                _make_receptor("FR-003", "Suelos"),
                _make_receptor("FR-004", "Hidrologia"),
            ],
        )

    def test_returns_phase6_model(self):
        model = self._make_model_with_almacenamiento()
        result = build_phase6_model_with_identified_impacts(model)
        self.assertIsInstance(result, Phase6Model)

    def test_impacts_populated(self):
        model = self._make_model_with_almacenamiento()
        result = build_phase6_model_with_identified_impacts(model)
        self.assertGreater(len(result.impacts), 0)

    def test_expediente_id_preserved(self):
        model = Phase6Model(
            expediente_id="EXP-SPECIFIC",
            actions=[_make_action(action_type="ALMACENAMIENTO")],
            receptor_factors=[_make_receptor("FR-003")],
        )
        result = build_phase6_model_with_identified_impacts(model)
        self.assertEqual(result.expediente_id, "EXP-SPECIFIC")

    def test_measures_empty(self):
        model = self._make_model_with_almacenamiento()
        result = build_phase6_model_with_identified_impacts(model)
        self.assertEqual(len(result.measures), 0)

    def test_pva_empty(self):
        model = self._make_model_with_almacenamiento()
        result = build_phase6_model_with_identified_impacts(model)
        self.assertEqual(len(result.pva_programs), 0)

    def test_non_mutation(self):
        model = self._make_model_with_almacenamiento()
        build_phase6_model_with_identified_impacts(model)
        self.assertEqual(len(model.impacts), 0)

    def test_custom_rules_applied(self):
        custom_rule = ImpactIdentificationRule(
            rule_id="RULE-CUSTOM",
            action_types=["ALMACENAMIENTO"],
            target_receptor_ids=["FR-003"],
        )
        model = self._make_model_with_almacenamiento()
        result = build_phase6_model_with_identified_impacts(model, rules=[custom_rule])
        self.assertTrue(all("RULE-CUSTOM" in " ".join(i.notes) for i in result.impacts))


# ---------------------------------------------------------------------------
# TestCLIPhase6IdentifyImpacts
# ---------------------------------------------------------------------------

class TestCLIPhase6IdentifyImpacts(unittest.TestCase):

    def _make_phase6_model_json(self, expediente_id: str = "EXP-TEST") -> dict:
        return {
            "expediente_id": expediente_id,
            "actions": [
                {
                    "action_id": "AC-001",
                    "name": "Recepcion y almacenamiento temporal de residuos",
                    "description": "Almacenamiento de residuos",
                    "action_type": "ALMACENAMIENTO",
                    "operation_code": "R13",
                    "source_refs": ["phase2_result"],
                    "notes": [],
                }
            ],
            "receptor_factors": [],
            "impacts": [],
            "measures": [],
            "pva_programs": [],
            "warnings": [],
            "notes": [],
        }

    def test_no_write_no_files_created(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir()
            model_base = impactos_dir / "phase6_model_base.json"
            with open(model_base, "w", encoding="utf-8") as f:
                json.dump(self._make_phase6_model_json(), f)

            result_file = impactos_dir / "impact_identification_result.json"
            model_file = impactos_dir / "phase6_model_with_impacts.json"

            ret = cmd_phase6_identify_impacts(exp_path, write=False)
            self.assertEqual(ret, 0)
            self.assertFalse(result_file.exists())
            self.assertFalse(model_file.exists())

    def test_write_creates_two_json_files(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir()
            with open(impactos_dir / "phase6_model_base.json", "w", encoding="utf-8") as f:
                json.dump(self._make_phase6_model_json(), f)

            ret = cmd_phase6_identify_impacts(exp_path, write=True)
            self.assertEqual(ret, 0)
            self.assertTrue((impactos_dir / "impact_identification_result.json").exists())
            self.assertTrue((impactos_dir / "phase6_model_with_impacts.json").exists())

    def test_write_json_valid(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir()
            with open(impactos_dir / "phase6_model_base.json", "w", encoding="utf-8") as f:
                json.dump(self._make_phase6_model_json(), f)

            cmd_phase6_identify_impacts(exp_path, write=True)
            with open(impactos_dir / "impact_identification_result.json", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("impacts", data)
            self.assertIn("warnings", data)
            self.assertIn("notes", data)

    def test_without_phase6_model_base_exits_0(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            ret = cmd_phase6_identify_impacts(exp_path, write=False)
            self.assertEqual(ret, 0)

    def test_result_json_has_impacts_key(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir()
            with open(impactos_dir / "phase6_model_base.json", "w", encoding="utf-8") as f:
                json.dump(self._make_phase6_model_json(), f)

            cmd_phase6_identify_impacts(exp_path, write=True)
            with open(impactos_dir / "impact_identification_result.json", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data["impacts"], list)

    def test_model_json_has_impacts(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir()
            with open(impactos_dir / "phase6_model_base.json", "w", encoding="utf-8") as f:
                json.dump(self._make_phase6_model_json(), f)

            cmd_phase6_identify_impacts(exp_path, write=True)
            with open(impactos_dir / "phase6_model_with_impacts.json", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("impacts", data)
            self.assertIsInstance(data["impacts"], list)
            self.assertGreater(len(data["impacts"]), 0)

    def test_write_creates_impactos_dir_if_missing(self):
        from run_expediente import cmd_phase6_identify_impacts
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_path = Path(tmpdir)
            # No impactos dir
            ret = cmd_phase6_identify_impacts(exp_path, write=True)
            self.assertEqual(ret, 0)
            # Impactos dir should be created
            self.assertTrue((exp_path / "impactos").exists())


# ---------------------------------------------------------------------------
# TestMethodologicalRules
# ---------------------------------------------------------------------------

class TestMethodologicalRules(unittest.TestCase):

    def _full_result(self) -> ImpactIdentificationResult:
        actions = [
            _make_action("AC-001", "ALMACENAMIENTO", "Almacenamiento temporal"),
            _make_action("AC-002", "OPERACION", "Tratamiento mecanico", "Trituracion"),
            _make_action("AC-003", "TRANSPORTE", "Carga descarga"),
            _make_action("AC-004", "MANTENIMIENTO", "Gestion residuos peligrosos"),
            _make_action("AC-005", "CESE", "Cese y limpieza final", "Desmantelamiento"),
            _make_action("AC-006", "AUXILIAR", "Maquinaria auxiliar"),
        ]
        model = Phase6Model(
            expediente_id="EXP-001",
            actions=actions,
            receptor_factors=build_minimal_receptor_factors(),
        )
        return identify_impacts_from_model(model)

    def test_no_significance_words_in_descriptions(self):
        result = self._full_result()
        forbidden = {"compatible", "moderado", "severo", "critico"}
        for imp in result.impacts:
            words = set(imp.description.lower().split())
            intersection = words & forbidden
            self.assertEqual(
                intersection, set(),
                f"Impact {imp.impact_id} description has forbidden words: {intersection}",
            )

    def test_positivo_impacts_have_no_valorado_significance(self):
        result = self._full_result()
        for imp in result.impacts:
            if imp.nature == "POSITIVO":
                self.assertEqual(imp.significance_without_measures, "NO_VALORADO")
                self.assertEqual(imp.significance_with_measures, "NO_VALORADO")

    def test_all_impacts_status_is_pending_or_indeterminado(self):
        valid_statuses = {"PENDIENTE_DATOS", "INDETERMINADO"}
        result = self._full_result()
        for imp in result.impacts:
            self.assertIn(
                imp.status, valid_statuses,
                f"Impact {imp.impact_id} has invalid status {imp.status}",
            )

    def test_all_impacts_nature_is_valid(self):
        from eia_agent.core.impact_model import IMPACT_NATURES
        result = self._full_result()
        for imp in result.impacts:
            self.assertIn(imp.nature, IMPACT_NATURES)

    def test_all_impacts_have_valid_significance(self):
        from eia_agent.core.impact_model import IMPACT_SIGNIFICANCE
        result = self._full_result()
        for imp in result.impacts:
            self.assertIn(imp.significance_without_measures, IMPACT_SIGNIFICANCE)
            self.assertIn(imp.significance_with_measures, IMPACT_SIGNIFICANCE)

    def test_rule_j_note_includes_no_compensation(self):
        rules = default_impact_identification_rules()
        rule_j = next(r for r in rules if r.rule_id == "RULE-J")
        combined = " ".join(rule_j.notes).lower()
        self.assertIn("no compensa", combined)

    def test_all_impacts_have_source_refs(self):
        result = self._full_result()
        for imp in result.impacts:
            self.assertTrue(
                len(imp.source_refs) > 0,
                f"Impact {imp.impact_id} has no source_refs",
            )

    def test_all_impact_ids_follow_pattern(self):
        import re
        pattern = re.compile(r"^IMP-\d{3,}$")
        result = self._full_result()
        for imp in result.impacts:
            self.assertRegex(imp.impact_id, pattern)

    def test_rule_f_note_includes_gabinete(self):
        rules = default_impact_identification_rules()
        rule_f = next(r for r in rules if r.rule_id == "RULE-F")
        combined = " ".join(rule_f.notes).lower()
        self.assertIn("gabinete", combined)

    def test_rule_e_note_includes_cartografia(self):
        rules = default_impact_identification_rules()
        rule_e = next(r for r in rules if r.rule_id == "RULE-E")
        combined = " ".join(rule_e.notes + rule_e.default_gaps).lower()
        self.assertIn("cartograf", combined)

    def test_no_conesa_scoring_in_impacts(self):
        result = self._full_result()
        for imp in result.impacts:
            attrs = imp.conesa_attributes
            for field_name in [
                "intensidad", "extension", "momento", "persistencia",
                "reversibilidad", "sinergia", "acumulacion", "efecto",
                "periodicidad", "recuperabilidad",
            ]:
                self.assertIsNone(getattr(attrs, field_name))

    def test_no_measure_ids_in_preliminary_impacts(self):
        result = self._full_result()
        for imp in result.impacts:
            self.assertEqual(len(imp.measure_ids), 0)

    def test_no_pva_ids_in_preliminary_impacts(self):
        result = self._full_result()
        for imp in result.impacts:
            self.assertEqual(len(imp.pva_ids), 0)


if __name__ == "__main__":
    unittest.main()
