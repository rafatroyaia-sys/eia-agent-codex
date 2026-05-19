"""
Tests para project_action_builder (IM-02).
Constructor de acciones del proyecto desde datos de Fase 2.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    ProjectAction,
    PVAProgram,
    ReceptorFactor,
    build_empty_phase6_model,
)
from eia_agent.core.project_action_builder import (
    ProjectActionBuildResult,
    build_actions_from_phase2_data,
    build_phase6_model_with_actions,
    detect_project_operations,
    extract_project_action_text,
    merge_actions_into_phase6_model,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _phase2_with_ops(operaciones: list[str]) -> dict:
    return {"object_scope": {"operaciones_incluidas": operaciones}}


def _phase2_with_actividad(actividad: str) -> dict:
    return {"object_scope": {"actividad": actividad}}


def _phase2_with_maquinaria(maquinaria: str) -> dict:
    return {"maquinaria": maquinaria}


def _phase2_with_residuos(residuos: str) -> dict:
    return {"residuos": residuos}


def _make_phase6_model_with_impacts() -> Phase6Model:
    """Crea un Phase6Model con un impacto, medida y PVA para tests de merge."""
    from eia_agent.core.impact_model import ConesaAttributes
    impact = EnvironmentalImpact(
        impact_id="IMP-001",
        action_id="AC-001",
        receptor_id="FR-001",
        name="Test",
    )
    measure = MitigationMeasure(
        measure_id="MED-001",
        name="Medida",
        measure_type="PREVENTIVA",
    )
    pva = PVAProgram(
        pva_id="PVA-001",
        name="PVA",
        factor_id="FI-001",
        indicator="Ind",
        frequency="MENSUAL",
    )
    receptor = ReceptorFactor(
        receptor_id="FR-001",
        inventory_factor_id="FI-001",
        name="Clima",
        inventory_semaphore="VERDE",
        ready_from_inventory=True,
    )
    return Phase6Model(
        expediente_id="EXP-001",
        actions=[ProjectAction(action_id="AC-000", name="Original", action_type="OTRO")],
        receptor_factors=[receptor],
        impacts=[impact],
        measures=[measure],
        pva_programs=[pva],
    )


# ---------------------------------------------------------------------------
# TestExtractProjectActionText
# ---------------------------------------------------------------------------

class TestExtractProjectActionText(unittest.TestCase):

    def test_none_returns_empty(self):
        self.assertEqual(extract_project_action_text(None), "")

    def test_empty_dict_returns_empty(self):
        self.assertEqual(extract_project_action_text({}), "")

    def test_extracts_from_operaciones_incluidas_list(self):
        data = _phase2_with_ops(["R1201", "R13"])
        text = extract_project_action_text(data)
        self.assertIn("r1201", text)
        self.assertIn("r13", text)

    def test_extracts_from_actividad_string(self):
        data = _phase2_with_actividad("Gestión de residuos metálicos")
        text = extract_project_action_text(data)
        self.assertIn("gestion", text)
        self.assertIn("residuos", text)

    def test_normalizes_accents(self):
        data = _phase2_with_actividad("clasificación y separación")
        text = extract_project_action_text(data)
        self.assertIn("clasificacion", text)
        self.assertIn("separacion", text)

    def test_normalizes_to_lowercase(self):
        data = _phase2_with_ops(["R1201", "R13"])
        text = extract_project_action_text(data)
        self.assertEqual(text, text.lower())

    def test_extracts_from_nested_dict(self):
        data = {
            "object_scope": {
                "operaciones_incluidas": ["R1201"],
                "actividad": "clasificación",
            }
        }
        text = extract_project_action_text(data)
        self.assertIn("r1201", text)
        self.assertIn("clasificaci", text)

    def test_extracts_from_maquinaria_key(self):
        data = _phase2_with_maquinaria("Compresor y báscula industrial")
        text = extract_project_action_text(data)
        self.assertIn("compresor", text)
        self.assertIn("bascula", text)

    def test_extracts_from_residuos_key(self):
        data = _phase2_with_residuos("residuos peligrosos: aceites usados")
        text = extract_project_action_text(data)
        self.assertIn("residuos peligrosos", text)
        self.assertIn("aceites", text)

    def test_does_not_fail_with_nested_list_of_dicts(self):
        data = {
            "datos": [
                {"actividad": "clasificación de residuos"},
                {"maquinaria": "triturador"},
            ]
        }
        text = extract_project_action_text(data)
        self.assertIn("clasificaci", text)
        self.assertIn("triturador", text)


# ---------------------------------------------------------------------------
# TestDetectProjectOperations
# ---------------------------------------------------------------------------

class TestDetectProjectOperations(unittest.TestCase):

    def test_empty_text_all_groups_empty(self):
        result = detect_project_operations("")
        for group_key in result:
            self.assertEqual(result[group_key], [])

    def test_returns_dict_with_all_groups(self):
        result = detect_project_operations("")
        expected_groups = {
            "recepcion_almacenamiento",
            "clasificacion_separacion",
            "tratamiento_mecanico",
            "carga_descarga_transporte",
            "maquinaria_auxiliar",
            "gestion_residuos_peligrosos",
            "cese_limpieza",
        }
        self.assertEqual(set(result.keys()), expected_groups)

    def test_r13_detects_recepcion(self):
        result = detect_project_operations("operacion r13 en la instalacion")
        self.assertIn("r13", result["recepcion_almacenamiento"])

    def test_r1301_detects_recepcion(self):
        result = detect_project_operations("operacion r1301")
        self.assertIn("r1301", result["recepcion_almacenamiento"])

    def test_r1302_detects_recepcion(self):
        result = detect_project_operations("operacion r1302")
        self.assertIn("r1302", result["recepcion_almacenamiento"])

    def test_r1201_detects_clasificacion(self):
        result = detect_project_operations("operacion r1201")
        self.assertIn("r1201", result["clasificacion_separacion"])

    def test_r1201_does_not_pollute_other_groups(self):
        result = detect_project_operations("r1201")
        self.assertEqual(result["recepcion_almacenamiento"], [])
        self.assertEqual(result["tratamiento_mecanico"], [])

    def test_r1203_detects_tratamiento(self):
        result = detect_project_operations("operacion r1203")
        self.assertIn("r1203", result["tratamiento_mecanico"])

    def test_trituracion_detects_tratamiento(self):
        result = detect_project_operations("trituracion de residuos metalicos")
        self.assertIn("trituraci", result["tratamiento_mecanico"])

    def test_cizalla_detects_tratamiento(self):
        result = detect_project_operations("uso de cizalla para corte")
        self.assertIn("cizalla", result["tratamiento_mecanico"])

    def test_molino_detects_tratamiento(self):
        result = detect_project_operations("molino de martillos")
        self.assertIn("molino", result["tratamiento_mecanico"])

    def test_carretilla_detects_transporte(self):
        result = detect_project_operations("movimiento con carretilla elevadora")
        self.assertIn("carretilla", result["carga_descarga_transporte"])

    def test_carga_detects_transporte(self):
        result = detect_project_operations("operaciones de carga y descarga")
        self.assertIn("carga", result["carga_descarga_transporte"])

    def test_camion_detects_transporte(self):
        result = detect_project_operations("acceso de camion a las instalaciones")
        self.assertIn("camion", result["carga_descarga_transporte"])

    def test_compresor_detects_auxiliar(self):
        result = detect_project_operations("compresor de aire comprimido")
        self.assertIn("compresor", result["maquinaria_auxiliar"])

    def test_bascula_detects_auxiliar(self):
        result = detect_project_operations("pesaje en bascula de precision")
        self.assertIn("bascula", result["maquinaria_auxiliar"])

    def test_diesel_detects_auxiliar(self):
        result = detect_project_operations("generador diesel de apoyo")
        self.assertIn("diesel", result["maquinaria_auxiliar"])

    def test_residuo_peligroso_detects_hazardous(self):
        result = detect_project_operations("gestion de residuo peligroso en nave")
        self.assertIn("residuo peligroso", result["gestion_residuos_peligrosos"])

    def test_aceite_detects_hazardous(self):
        result = detect_project_operations("aceite de motor usado")
        self.assertIn("aceite", result["gestion_residuos_peligrosos"])

    def test_bateria_detects_hazardous(self):
        result = detect_project_operations("baterias de vehiculos electricos")
        self.assertIn("bateria", result["gestion_residuos_peligrosos"])

    def test_raee_detects_hazardous(self):
        result = detect_project_operations("residuos raee de aparatos electronicos")
        self.assertIn("raee", result["gestion_residuos_peligrosos"])

    def test_ler_asterisco_literal_detects_hazardous(self):
        result = detect_project_operations("codigo ler* para residuos peligrosos")
        self.assertIn("ler*", result["gestion_residuos_peligrosos"])

    def test_ler_code_pattern_detects_hazardous(self):
        """Patrón XX XX XX* (código LER peligroso) detectado vía regex."""
        result = detect_project_operations("codigo ler 16 06 01* aceite mineral")
        self.assertIn("ler_codigo_peligroso", result["gestion_residuos_peligrosos"])

    def test_cese_detects_cese(self):
        result = detect_project_operations("cese de la actividad")
        self.assertIn("cese", result["cese_limpieza"])

    def test_desmantelamiento_detects_cese(self):
        result = detect_project_operations("desmantelamiento de instalaciones")
        self.assertIn("desmantelamiento", result["cese_limpieza"])

    def test_limpieza_final_detects_cese(self):
        result = detect_project_operations("limpieza final del emplazamiento")
        self.assertIn("limpieza final", result["cese_limpieza"])

    def test_retirada_detects_cese(self):
        result = detect_project_operations("retirada de equipos al final")
        self.assertIn("retirada", result["cese_limpieza"])

    def test_detection_is_list_of_strings(self):
        result = detect_project_operations("r13 cizalla compresor cese")
        for group_key, found in result.items():
            self.assertIsInstance(found, list)
            for term in found:
                self.assertIsInstance(term, str)


# ---------------------------------------------------------------------------
# TestBuildActionsFromPhase2Data
# ---------------------------------------------------------------------------

class TestBuildActionsFromPhase2Data(unittest.TestCase):

    def test_none_generates_minimal_action(self):
        result = build_actions_from_phase2_data(None)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action_id, "AC-001")
        self.assertEqual(result.actions[0].action_type, "OTRO")

    def test_none_generates_warning(self):
        result = build_actions_from_phase2_data(None)
        self.assertTrue(len(result.warnings) > 0)

    def test_empty_dict_generates_minimal_action(self):
        result = build_actions_from_phase2_data({})
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].action_type, "OTRO")

    def test_r13_generates_recepcion_almacenamiento(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        types = [a.action_type for a in result.actions]
        self.assertIn("ALMACENAMIENTO", types)

    def test_r13_sets_operation_code_r13(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        for a in result.actions:
            if a.action_type == "ALMACENAMIENTO":
                self.assertEqual(a.operation_code, "R13")

    def test_r1301_sets_operation_code_r1301(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1301"]))
        for a in result.actions:
            if a.action_type == "ALMACENAMIENTO":
                self.assertEqual(a.operation_code, "R1301")

    def test_r1302_sets_operation_code_r1302(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1302"]))
        for a in result.actions:
            if a.action_type == "ALMACENAMIENTO":
                self.assertEqual(a.operation_code, "R1302")

    def test_r1201_generates_clasificacion(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1201"]))
        types = [a.action_type for a in result.actions]
        self.assertIn("OPERACION", types)

    def test_r1201_sets_operation_code_r1201(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1201"]))
        for a in result.actions:
            if a.action_type == "OPERACION" and "clasificaci" in a.name.lower():
                self.assertEqual(a.operation_code, "R1201")

    def test_r1203_generates_tratamiento_mecanico(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1203"]))
        types = [a.action_type for a in result.actions]
        self.assertIn("OPERACION", types)

    def test_trituracion_generates_tratamiento(self):
        result = build_actions_from_phase2_data(_phase2_with_actividad("Trituración mecánica de residuos"))
        names = [a.name for a in result.actions]
        self.assertTrue(any("mecánico" in n or "mecanico" in n.lower() for n in names))

    def test_carga_descarga_generates_transporte(self):
        result = build_actions_from_phase2_data(_phase2_with_actividad("Carga y descarga de residuos"))
        types = [a.action_type for a in result.actions]
        self.assertIn("TRANSPORTE", types)

    def test_carretilla_generates_transporte(self):
        result = build_actions_from_phase2_data(_phase2_with_maquinaria("Carretilla elevadora para manejo de materiales"))
        types = [a.action_type for a in result.actions]
        self.assertIn("TRANSPORTE", types)

    def test_compresor_generates_auxiliar(self):
        result = build_actions_from_phase2_data(_phase2_with_maquinaria("Compresor de aire"))
        types = [a.action_type for a in result.actions]
        self.assertIn("AUXILIAR", types)

    def test_bascula_generates_auxiliar(self):
        result = build_actions_from_phase2_data(_phase2_with_maquinaria("Báscula industrial para pesaje"))
        types = [a.action_type for a in result.actions]
        self.assertIn("AUXILIAR", types)

    def test_residuos_peligrosos_generates_gestion(self):
        result = build_actions_from_phase2_data(
            _phase2_with_residuos("Residuos peligrosos: aceites usados")
        )
        types = [a.action_type for a in result.actions]
        self.assertIn("MANTENIMIENTO", types)

    def test_ler_asterisco_generates_gestion(self):
        data = {"residuos": "LER* para residuos peligrosos de la actividad"}
        result = build_actions_from_phase2_data(data)
        types = [a.action_type for a in result.actions]
        self.assertIn("MANTENIMIENTO", types)

    def test_ler_code_pattern_generates_gestion(self):
        data = {"residuos": "Generacion de aceite cod. LER 13 02 06* (aceites sinteticos)"}
        result = build_actions_from_phase2_data(data)
        types = [a.action_type for a in result.actions]
        self.assertIn("MANTENIMIENTO", types)

    def test_cese_generates_cese_action(self):
        result = build_actions_from_phase2_data(_phase2_with_actividad("Incluye cese y limpieza final"))
        types = [a.action_type for a in result.actions]
        self.assertIn("CESE", types)

    def test_desmantelamiento_generates_cese_action(self):
        result = build_actions_from_phase2_data(
            _phase2_with_actividad("Plan de desmantelamiento al cierre")
        )
        types = [a.action_type for a in result.actions]
        self.assertIn("CESE", types)

    def test_ids_are_correlative_ac_001_onwards(self):
        data = _phase2_with_ops(["R13", "R1201", "R1203"])
        result = build_actions_from_phase2_data(data)
        ids = [a.action_id for a in result.actions]
        for i, action_id in enumerate(ids, start=1):
            self.assertEqual(action_id, f"AC-{i:03d}")

    def test_no_duplicate_actions_for_same_group(self):
        # Múltiples términos del mismo grupo no deben generar acción duplicada
        data = _phase2_with_actividad("R13 y acopio y almacenamiento")
        result = build_actions_from_phase2_data(data)
        types = [a.action_type for a in result.actions]
        self.assertEqual(types.count("ALMACENAMIENTO"), 1)

    def test_multiple_groups_all_detected(self):
        data = _phase2_with_ops(["R13", "R1201", "R1203"])
        result = build_actions_from_phase2_data(data)
        self.assertGreaterEqual(len(result.actions), 3)

    def test_actions_have_source_refs(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1201"]))
        for a in result.actions:
            self.assertTrue(len(a.source_refs) > 0)

    def test_actions_have_notes_with_detected_terms(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1201"]))
        for a in result.actions:
            if a.action_type != "OTRO":
                self.assertTrue(len(a.notes) > 0)
                self.assertTrue(any("Términos" in n or "terminos" in n.lower() for n in a.notes))

    def test_minimal_action_type_is_otro(self):
        result = build_actions_from_phase2_data({})
        self.assertEqual(result.actions[0].action_type, "OTRO")

    def test_returns_project_action_build_result(self):
        result = build_actions_from_phase2_data(None)
        self.assertIsInstance(result, ProjectActionBuildResult)

    def test_result_is_list_of_project_actions(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        for a in result.actions:
            self.assertIsInstance(a, ProjectAction)


# ---------------------------------------------------------------------------
# TestProjectActionBuildResult
# ---------------------------------------------------------------------------

class TestProjectActionBuildResult(unittest.TestCase):

    def test_to_dict_is_json_serializable(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13", "R1201"]))
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        self.assertIsInstance(json_str, str)

    def test_to_dict_has_required_keys(self):
        result = build_actions_from_phase2_data(None)
        d = result.to_dict()
        self.assertIn("actions", d)
        self.assertIn("warnings", d)
        self.assertIn("notes", d)

    def test_to_dict_actions_are_dicts(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        d = result.to_dict()
        for a in d["actions"]:
            self.assertIsInstance(a, dict)
            self.assertIn("action_id", a)

    def test_summary_not_empty(self):
        result = build_actions_from_phase2_data(None)
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertTrue(len(s) > 0)

    def test_summary_contains_action_count(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13", "R1201"]))
        s = result.summary()
        self.assertIn("2", s)

    def test_summary_contains_action_id(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        s = result.summary()
        self.assertIn("AC-001", s)


# ---------------------------------------------------------------------------
# TestMergeActionsIntoPhase6Model
# ---------------------------------------------------------------------------

class TestMergeActionsIntoPhase6Model(unittest.TestCase):

    def _new_actions(self) -> list[ProjectAction]:
        return [
            ProjectAction(action_id="AC-001", name="Nueva acción", action_type="OPERACION"),
            ProjectAction(action_id="AC-002", name="Otra acción", action_type="TRANSPORTE"),
        ]

    def test_replaces_actions(self):
        model = _make_phase6_model_with_impacts()
        new_actions = self._new_actions()
        merged = merge_actions_into_phase6_model(model, new_actions)
        self.assertEqual(len(merged.actions), 2)
        self.assertEqual(merged.actions[0].action_id, "AC-001")
        self.assertEqual(merged.actions[1].action_id, "AC-002")

    def test_preserves_receptor_factors(self):
        model = _make_phase6_model_with_impacts()
        original_rf_count = len(model.receptor_factors)
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual(len(merged.receptor_factors), original_rf_count)

    def test_preserves_impacts(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual(len(merged.impacts), len(model.impacts))

    def test_preserves_measures(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual(len(merged.measures), len(model.measures))

    def test_preserves_pva_programs(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual(len(merged.pva_programs), len(model.pva_programs))

    def test_does_not_mutate_original(self):
        model = _make_phase6_model_with_impacts()
        original_action_ids = [a.action_id for a in model.actions]
        merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual([a.action_id for a in model.actions], original_action_ids)

    def test_returns_new_instance(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertIsNot(merged, model)

    def test_empty_actions_list_accepted(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, [])
        self.assertEqual(merged.actions, [])

    def test_preserves_expediente_id(self):
        model = _make_phase6_model_with_impacts()
        merged = merge_actions_into_phase6_model(model, self._new_actions())
        self.assertEqual(merged.expediente_id, model.expediente_id)


# ---------------------------------------------------------------------------
# TestBuildPhase6ModelWithActions
# ---------------------------------------------------------------------------

class TestBuildPhase6ModelWithActions(unittest.TestCase):

    def test_creates_model_with_actions(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R1201"]))
        self.assertTrue(len(model.actions) > 0)

    def test_expediente_id_set(self):
        model = build_phase6_model_with_actions("EXP-PRUEBA", None)
        self.assertEqual(model.expediente_id, "EXP-PRUEBA")

    def test_no_impacts_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13", "R1201"]))
        self.assertEqual(model.impacts, [])

    def test_no_measures_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13"]))
        self.assertEqual(model.measures, [])

    def test_no_pva_programs_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13"]))
        self.assertEqual(model.pva_programs, [])

    def test_without_inventory_summary_empty_receptor_factors(self):
        model = build_phase6_model_with_actions("EXP-TEST", None, None)
        self.assertEqual(model.receptor_factors, [])

    def test_with_inventory_summary_creates_receptor_factors(self):
        from eia_agent.core.inventory_model import (
            build_all_empty_factors,
            build_inventory_summary,
        )
        factors = build_all_empty_factors()
        summary = build_inventory_summary("EXP-TEST", factors)
        model = build_phase6_model_with_actions("EXP-TEST", None, summary)
        self.assertEqual(len(model.receptor_factors), 16)

    def test_returns_phase6_model(self):
        model = build_phase6_model_with_actions("EXP-TEST")
        self.assertIsInstance(model, Phase6Model)

    def test_none_phase2_creates_minimal_action(self):
        model = build_phase6_model_with_actions("EXP-TEST", None)
        self.assertEqual(len(model.actions), 1)
        self.assertEqual(model.actions[0].action_type, "OTRO")


# ---------------------------------------------------------------------------
# TestCLIPhase6Actions
# ---------------------------------------------------------------------------

class TestCLIPhase6Actions(unittest.TestCase):
    """Tests de integración para el comando phase6-actions de run_expediente.py."""

    def _make_expediente(self, with_phase2: bool = False, phase2_ops: list | None = None) -> Path:
        """Crea un directorio de expediente temporal con estructura mínima."""
        tmpdir = tempfile.mkdtemp()
        exp_path = Path(tmpdir)
        (exp_path / "control_interno").mkdir()
        if with_phase2:
            phase2_data = _phase2_with_ops(phase2_ops or ["R1201", "R13"])
            with open(exp_path / "control_interno" / "phase2_result.json", "w", encoding="utf-8") as f:
                json.dump(phase2_data, f)
        return exp_path

    def test_without_write_does_not_create_files(self):
        exp_path = self._make_expediente(with_phase2=True)
        import run_expediente
        run_expediente.cmd_phase6_actions(exp_path, write=False)
        self.assertFalse((exp_path / "impactos" / "phase6_actions.json").exists())

    def test_with_write_creates_phase6_actions_json(self):
        exp_path = self._make_expediente(with_phase2=True)
        import run_expediente
        run_expediente.cmd_phase6_actions(exp_path, write=True)
        self.assertTrue((exp_path / "impactos" / "phase6_actions.json").exists())

    def test_with_write_creates_phase6_model_base_json(self):
        exp_path = self._make_expediente(with_phase2=True)
        import run_expediente
        run_expediente.cmd_phase6_actions(exp_path, write=True)
        self.assertTrue((exp_path / "impactos" / "phase6_model_base.json").exists())

    def test_with_write_json_is_valid(self):
        exp_path = self._make_expediente(with_phase2=True, phase2_ops=["R13", "R1201"])
        import run_expediente
        run_expediente.cmd_phase6_actions(exp_path, write=True)
        with open(exp_path / "impactos" / "phase6_actions.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("actions", data)
        self.assertTrue(len(data["actions"]) >= 1)

    def test_missing_phase2_generates_minimal_action_and_succeeds(self):
        exp_path = self._make_expediente(with_phase2=False)
        import run_expediente
        exit_code = run_expediente.cmd_phase6_actions(exp_path, write=True)
        self.assertEqual(exit_code, 0)
        with open(exp_path / "impactos" / "phase6_actions.json", encoding="utf-8") as f:
            data = json.load(f)
        # Acción mínima generada
        self.assertEqual(len(data["actions"]), 1)
        self.assertEqual(data["actions"][0]["action_type"], "OTRO")

    def test_missing_phase2_with_warnings_in_output(self):
        exp_path = self._make_expediente(with_phase2=False)
        import run_expediente
        run_expediente.cmd_phase6_actions(exp_path, write=True)
        with open(exp_path / "impactos" / "phase6_actions.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(len(data["warnings"]) > 0)


# ---------------------------------------------------------------------------
# TestMethodologicalRules
# ---------------------------------------------------------------------------

class TestMethodologicalRules(unittest.TestCase):

    def _all_actions_for_full_data(self) -> list[ProjectAction]:
        data = {
            "object_scope": {
                "operaciones_incluidas": ["R13", "R1201", "R1203"],
            },
            "maquinaria": "compresor, báscula, carretilla",
            "residuos": "aceite usado, baterías, RAEE",
            "notes": ["cese y limpieza final de la actividad"],
        }
        return build_actions_from_phase2_data(data).actions

    def test_action_descriptions_no_impacto(self):
        for action in self._all_actions_for_full_data():
            self.assertNotIn("impacto", action.description.lower(),
                             msg=f"Action '{action.name}' description contains 'impacto'")

    def test_action_descriptions_no_significance_words(self):
        forbidden = ["compatible", "moderado", "severo", "critico", "crítico"]
        for action in self._all_actions_for_full_data():
            desc_lower = action.description.lower()
            for word in forbidden:
                self.assertNotIn(word, desc_lower,
                                 msg=f"Action '{action.name}' contains significance word '{word}'")

    def test_no_environmental_impacts_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13", "R1201"]))
        self.assertEqual(model.impacts, [])

    def test_no_mitigation_measures_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13", "R1201"]))
        self.assertEqual(model.measures, [])

    def test_no_pva_programs_created(self):
        model = build_phase6_model_with_actions("EXP-TEST", _phase2_with_ops(["R13", "R1201"]))
        self.assertEqual(model.pva_programs, [])

    def test_no_environmental_impacts_in_build_result(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13"]))
        # ProjectActionBuildResult solo contiene ProjectAction
        for action in result.actions:
            self.assertIsInstance(action, ProjectAction)
            self.assertNotIsInstance(action, EnvironmentalImpact)

    def test_detected_terms_appear_in_action_notes(self):
        result = build_actions_from_phase2_data(_phase2_with_ops(["R1201"]))
        for action in result.actions:
            if action.action_type == "OPERACION":
                notes_text = " ".join(action.notes)
                self.assertIn("r1201", notes_text.lower())

    def test_actions_have_valid_action_types(self):
        from eia_agent.core.impact_model import ACTION_TYPES
        data = {
            "object_scope": {"operaciones_incluidas": ["R13", "R1201", "R1203"]},
            "maquinaria": "compresor carretilla",
            "residuos": "aceite bateria raee",
            "notes": ["cese"],
        }
        result = build_actions_from_phase2_data(data)
        for action in result.actions:
            self.assertIn(action.action_type, ACTION_TYPES)

    def test_all_action_ids_unique(self):
        data = {
            "object_scope": {"operaciones_incluidas": ["R13", "R1201", "R1203"]},
            "maquinaria": "compresor carretilla",
            "residuos": "aceites bateria",
            "notes": ["cese"],
        }
        result = build_actions_from_phase2_data(data)
        ids = [a.action_id for a in result.actions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_action_ids_follow_ac_nnn_pattern(self):
        import re
        result = build_actions_from_phase2_data(_phase2_with_ops(["R13", "R1201"]))
        pattern = re.compile(r"^AC-\d{3,}$")
        for action in result.actions:
            self.assertRegex(action.action_id, pattern)


if __name__ == "__main__":
    unittest.main()
