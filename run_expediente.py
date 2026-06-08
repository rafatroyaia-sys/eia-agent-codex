#!/usr/bin/env python3
"""
run_expediente.py — CLI-01
Runner básico para EIA-Agent v2.1.

No ejecuta agentes reales ni genera fases.
Proporciona acceso desde consola a los módulos de productización:
  init-expediente, config-check, secrets-scan,
  status, validate, gate, recover, log-summary,
  phase1, phase2, phase3, phase4-precheck, phase4-climate,
  cartography-plan, schematic-maps, phase4-offline,
  inventory-build, inventory-gate,
  phase6-actions, phase6-identify-impacts, phase6-assign-conesa,
  phase6-generate-measures, phase6-generate-pva,
  phase6-validate-pva, phase6-cumulative, audit-art45, audit-prudence,
  document-manifest, document-build-md, document-build-docx,
  document-insert-figures, document-qc, document-package, document-export,
  document-prepare-presentation, audit-positive-gaps,
  document-structure, document-numbering, document-toc, cliente-intake,
  cliente-form-schema, cliente-submission-check, cliente-plan,
  cliente-dashboard, cliente-climate-traceability, cliente-portal, cliente-portal-site, cliente-trial-package,
  cliente-app-package, cliente-backend.

Uso:
    python run_expediente.py <expediente> init-expediente [--force] [--no-guides]
    python run_expediente.py <expediente> config-check [--write]
    python run_expediente.py <expediente> secrets-scan [--write]
    python run_expediente.py <expediente> status
    python run_expediente.py <expediente> validate
    python run_expediente.py <expediente> gate <fase> [--prod]
    python run_expediente.py <expediente> recover [--write-report]
    python run_expediente.py <expediente> log-summary
    python run_expediente.py <expediente> phase1 [--write]
    python run_expediente.py <expediente> phase2 [--write] [--prod]
    python run_expediente.py <expediente> phase3 [--write]
    python run_expediente.py <expediente> phase4-precheck [--write]
    python run_expediente.py <expediente> phase4-climate --stations <f> --climate-data <f> [--write]
    python run_expediente.py <expediente> cartography-plan [--write]
    python run_expediente.py <expediente> schematic-maps [--plan <f>] [--write]
    python run_expediente.py <expediente> phase4-offline --stations <f> --climate-data <f> [--write]
    python run_expediente.py <expediente> inventory-build [--write]
    python run_expediente.py <expediente> inventory-gate [--write] [--prod]
    python run_expediente.py <expediente> phase6-actions [--write]
    python run_expediente.py <expediente> phase6-identify-impacts [--write]
    python run_expediente.py <expediente> phase6-assign-conesa [--write] [--no-score]
    python run_expediente.py <expediente> phase6-generate-measures [--write]
    python run_expediente.py <expediente> phase6-generate-pva [--write]
    python run_expediente.py <expediente> document-package [--write] [--overwrite]
    python run_expediente.py <expediente> document-export [--write] [--no-pdf] [--overwrite]
    python run_expediente.py <expediente> document-prepare-presentation [--write] [--no-final-docx]
    python run_expediente.py <expediente> audit-positive-gaps [--write]
    python run_expediente.py <expediente> document-toc [--write] [--apply] [--no-replace]
    python run_expediente.py <expediente> cliente-intake [--write]
    python run_expediente.py <expediente> cliente-form-schema [--write]
    python run_expediente.py <expediente> cliente-submission-check [--write]
    python run_expediente.py <expediente> cliente-plan [--write]
    python run_expediente.py <expediente> cliente-dashboard [--write]
    python run_expediente.py <expediente> cliente-climate-traceability [--write]
    python run_expediente.py <expediente> cliente-portal [--write]
    python run_expediente.py <expediente> cliente-portal-site [--write]
    python run_expediente.py <expediente> cliente-trial-package [--write]
    python run_expediente.py <expediente> cliente-app-package [--write]
    python run_expediente.py <expediente> cliente-backend [--host 127.0.0.1] [--port 8765]
"""
import argparse
import sys
from pathlib import Path

# Asegurar que src/ está en el path cuando se ejecuta desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eia_agent.core.gate_checker import GateChecker
from eia_agent.core.orchestrator_log import OrchestratorLog
from eia_agent.core.schema_validator import validate_expediente
from eia_agent.core.session_recovery import SessionRecovery

_STATE_FILE = Path("control_interno") / "orchestrator_state.json"


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_status(exp_path: Path) -> int:
    """Muestra el estado del orquestador. No crea archivos si no existe estado."""
    state_path = exp_path / _STATE_FILE
    if not state_path.exists():
        print(f"Expediente : {exp_path.name}")
        print("Estado     : sin estado de orquestador")
        print("Acción     : ejecute una fase primero para inicializar el orquestador.")
        return 0

    # El estado ya existe: cargar EIAOrchestrator de forma segura (no crea archivos nuevos)
    from eia_agent.core.orchestrator import EIAOrchestrator
    try:
        orch = EIAOrchestrator(exp_path)
        print(orch.summary())
        return 0
    except Exception as exc:
        print(f"Error al cargar estado: {exc}", file=sys.stderr)
        return 1


def cmd_validate(exp_path: Path) -> int:
    """Valida los schemas del expediente y muestra el resumen."""
    result = validate_expediente(exp_path)
    print(result.summary())
    return 0 if result.is_valid() else 1


def cmd_gate(exp_path: Path, phase: str, prod: bool) -> int:
    """Evalúa el gate de una fase. test_mode por defecto; --prod activa modo estricto."""
    test_mode = not prod
    gc = GateChecker(exp_path, test_mode=test_mode)
    result = gc.check_phase(phase)
    print(result.summary())
    return 0 if not result.is_blocked() else 1


def cmd_recover(exp_path: Path, write_report: bool) -> int:
    """Diagnostica sesiones interrumpidas. Solo escribe si se pasa --write-report."""
    sr = SessionRecovery(exp_path)
    report = sr.analyze()
    print(report.summary())
    if write_report:
        path = sr.write_recovery_report(report)
        print(f"Informe escrito: {path}")
    return 0 if report.can_continue else 1


def cmd_log_summary(exp_path: Path) -> int:
    """Muestra el resumen del log del orquestador. No crea eventos."""
    log = OrchestratorLog(exp_path)
    print(log.summary())
    return 0


def cmd_phase2(exp_path: Path, write: bool, prod: bool) -> int:
    """Ejecuta el pipeline de Fase 2 (OB-06). Por defecto solo lectura, test_mode=True."""
    from eia_agent.core.phase2_pipeline import run_phase2
    test_mode = not prod
    try:
        result = run_phase2(exp_path, write_outputs=write, test_mode=test_mode)
        print(result.summary())
        if write:
            out_dir = exp_path / "control_interno"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en Fase 2: {exc}", file=sys.stderr)
        return 1


def cmd_phase4_climate(
    exp_path: Path,
    stations: str,
    climate_data: str,
    write: bool,
) -> int:
    """Ejecuta el pipeline climático de Fase 4 (CL-06). Por defecto solo lectura."""
    from eia_agent.core.phase4_climate_pipeline import run_phase4_climate
    try:
        result = run_phase4_climate(
            exp_path,
            stations_path=stations,
            climate_data_path=climate_data,
            write_outputs=write,
        )
        print(result.summary())
        if write:
            print(f"\nOutputs escritos en: {exp_path / 'clima'}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en pipeline climático Fase 4: {exc}", file=sys.stderr)
        return 1


def cmd_phase4_precheck(exp_path: Path, write: bool) -> int:
    """Ejecuta el precheck de Fase 4 (CA-08). Por defecto solo lectura."""
    from eia_agent.core.phase4_precheck import run_phase4_precheck
    try:
        result = run_phase4_precheck(exp_path, write_outputs=write)
        print(result.summary())
        if write:
            out_dir = exp_path / "control_interno"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0 if result.error_count() == 0 else 1
    except Exception as exc:
        print(f"Error en precheck Fase 4: {exc}", file=sys.stderr)
        return 1


def cmd_phase3(exp_path: Path, write: bool) -> int:
    """Ejecuta el pipeline de Fase 3 (TN-05). Por defecto solo lectura."""
    from eia_agent.core.phase3_pipeline import run_phase3
    try:
        result = run_phase3(exp_path, write_outputs=write)
        print(result.summary())
        if write:
            out_dir = exp_path / "control_interno"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en Fase 3: {exc}", file=sys.stderr)
        return 1


def cmd_schematic_maps(exp_path: Path, plan: str | None, write: bool) -> int:
    """Genera (o previsualiza) mapas esquemáticos offline de Fase 4 (CA-11)."""
    from eia_agent.core.schematic_map_generator import (
        load_cartography_plan,
        generate_schematic_maps_from_plan,
        build_map_generation_report,
        SchematicMapConfig,
    )
    plan_path = Path(plan) if plan else exp_path / "cartografia" / "cartografia_plan.json"
    try:
        data = load_cartography_plan(plan_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de plan: {exc}", file=sys.stderr)
        return 1

    if not write:
        maps = data.get("maps", [])
        print(f"Plan cartográfico cargado: {len(maps)} mapas")
        print(f"Directorio de salida (con --write): {exp_path / 'cartografia' / 'mapas'}")
        print()
        for m in maps:
            print(f"  {m.get('map_id', '?')} -> {m.get('output_filename', '?')}")
        print()
        print("Use --write para generar los PNGs.")
        return 0

    out_dir = exp_path / "cartografia" / "mapas"
    try:
        config = SchematicMapConfig()
        results = generate_schematic_maps_from_plan(plan_path, out_dir, config)
        report = build_map_generation_report(results)
        print(report)
        generated = sum(1 for r in results if r.status == "GENERATED_PROVISIONAL")
        print(f"\n{generated}/{len(results)} mapas generados en: {out_dir}")
        return 0
    except Exception as exc:
        print(f"Error generando mapas: {exc}", file=sys.stderr)
        return 1


def cmd_cartography_plan(exp_path: Path, write: bool) -> int:
    """Genera el plan cartográfico offline de Fase 4 (CA-10). Por defecto solo lectura."""
    from eia_agent.core.cartography_plan import build_cartography_plan
    try:
        result = build_cartography_plan(exp_path, write_outputs=write)
        print(result.summary())
        if write:
            out_dir = exp_path / "cartografia"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en plan cartográfico: {exc}", file=sys.stderr)
        return 1


def cmd_phase4_offline(
    exp_path: Path,
    stations: str,
    climate_data: str,
    write: bool,
) -> int:
    """Pipeline integrador Fase 4 offline: CA-08 + CL-06 + CA-10 + CA-11 (F4-01)."""
    from eia_agent.core.phase4_offline_pipeline import run_phase4_offline
    try:
        result = run_phase4_offline(
            exp_path,
            stations_path=stations,
            climate_data_path=climate_data,
            write_outputs=write,
        )
        print(result.summary())
        if write:
            print(f"\nOutputs escritos en: {exp_path / 'fase4'}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en pipeline Fase 4 offline: {exc}", file=sys.stderr)
        return 1


def cmd_inventory_build(exp_path: Path, write: bool) -> int:
    """Construye el inventario ambiental inicial (Fase 5) desde los outputs de Fase 4 (IV-02)."""
    from eia_agent.core.inventory_builder import build_inventory_from_phase4
    try:
        result = build_inventory_from_phase4(exp_path, write_outputs=write)
        print(result.summary())
        if write:
            out_dir = exp_path / "inventario"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en inventory-build: {exc}", file=sys.stderr)
        return 1


def cmd_phase6_actions(exp_path: Path, write: bool) -> int:
    """Construye acciones de Fase 6 desde phase2_result.json (IM-02). Por defecto solo lectura."""
    import json as _json
    from eia_agent.core.project_action_builder import (
        build_actions_from_phase2_data,
        build_phase6_model_with_actions,
    )

    phase2_path = exp_path / "control_interno" / "phase2_result.json"
    phase2_data = None
    if phase2_path.exists():
        try:
            with open(phase2_path, encoding="utf-8") as f:
                phase2_data = _json.load(f)
        except _json.JSONDecodeError as exc:
            print(f"Error: JSON inválido en {phase2_path}: {exc}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"Error leyendo {phase2_path}: {exc}", file=sys.stderr)
            return 1
    else:
        print(f"Aviso: no se encontró {phase2_path}. Se generará acción mínima.")

    build_result = build_actions_from_phase2_data(phase2_data)
    print(build_result.summary())

    if not write:
        return 0

    impactos_dir = exp_path / "impactos"
    impactos_dir.mkdir(parents=True, exist_ok=True)

    actions_path = impactos_dir / "phase6_actions.json"
    with open(actions_path, "w", encoding="utf-8") as f:
        _json.dump(build_result.to_dict(), f, ensure_ascii=False, indent=2)

    model = build_phase6_model_with_actions(exp_path.name, phase2_data)
    model_path = impactos_dir / "phase6_model_base.json"
    with open(model_path, "w", encoding="utf-8") as f:
        _json.dump(model.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"\nOutputs escritos:")
    print(f"  {actions_path}")
    print(f"  {model_path}")
    return 0


def cmd_phase6_identify_impacts(exp_path: Path, write: bool) -> int:
    """Identifica impactos preliminares accion x receptor para Fase 6 (IM-03)."""
    import dataclasses as _dc
    import json as _json
    from eia_agent.core.impact_identifier import (
        build_minimal_receptor_factors,
        build_phase6_model_with_identified_impacts,
        identify_impacts_from_model,
    )
    from eia_agent.core.impact_model import Phase6Model, ProjectAction, ReceptorFactor

    # --- Intentar cargar phase6_model_base.json (output de IM-02) ---
    model_base_path = exp_path / "impactos" / "phase6_model_base.json"
    model: Phase6Model | None = None

    if model_base_path.exists():
        try:
            with open(model_base_path, encoding="utf-8") as f:
                data = _json.load(f)
            expediente_id = data.get("expediente_id", exp_path.name)
            actions = [
                ProjectAction(
                    action_id=a["action_id"],
                    name=a["name"],
                    description=a.get("description", ""),
                    action_type=a.get("action_type", "OTRO"),
                    operation_code=a.get("operation_code"),
                    source_refs=a.get("source_refs", []),
                    notes=a.get("notes", []),
                )
                for a in data.get("actions", [])
            ]
            receptor_factors = [
                ReceptorFactor(
                    receptor_id=r["receptor_id"],
                    inventory_factor_id=r["inventory_factor_id"],
                    name=r["name"],
                    inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
                    ready_from_inventory=r.get("ready_from_inventory", False),
                    critical_gaps=r.get("critical_gaps", []),
                    notes=r.get("notes", []),
                )
                for r in data.get("receptor_factors", [])
            ]
            model = Phase6Model(
                expediente_id=expediente_id,
                actions=actions,
                receptor_factors=receptor_factors,
            )
        except (_json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"Error: JSON invalido en {model_base_path}: {exc}", file=sys.stderr)
            return 1
    else:
        # Sin modelo base: construir desde phase2_result.json si existe
        print(
            f"Aviso: no se encontro {model_base_path}. "
            "Ejecute phase6-actions --write primero para mejores resultados."
        )
        from eia_agent.core.project_action_builder import build_phase6_model_with_actions
        phase2_path = exp_path / "control_interno" / "phase2_result.json"
        phase2_data = None
        if phase2_path.exists():
            try:
                with open(phase2_path, encoding="utf-8") as f:
                    phase2_data = _json.load(f)
            except _json.JSONDecodeError:
                pass
        model = build_phase6_model_with_actions(exp_path.name, phase2_data)

    # Si no hay factores receptores, usar los 16 por defecto
    if not model.receptor_factors:
        print(
            "Aviso: sin factores receptores en el modelo. "
            "Se usan 16 factores por defecto (sin datos de inventario)."
        )
        model = _dc.replace(model, receptor_factors=build_minimal_receptor_factors())

    result = identify_impacts_from_model(model)
    print(result.summary())

    if not write:
        return 0

    impactos_dir = exp_path / "impactos"
    impactos_dir.mkdir(parents=True, exist_ok=True)

    result_path = impactos_dir / "impact_identification_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        _json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    model_with_impacts = build_phase6_model_with_identified_impacts(model)
    model_path = impactos_dir / "phase6_model_with_impacts.json"
    with open(model_path, "w", encoding="utf-8") as f:
        _json.dump(model_with_impacts.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"\nOutputs escritos:")
    print(f"  {result_path}")
    print(f"  {model_path}")
    return 0


def cmd_phase6_assign_conesa(exp_path: Path, write: bool, no_score: bool) -> int:
    """Asigna atributos Conesa a impactos identificados en Fase 6 (IM-04)."""
    import json as _json
    from eia_agent.core.conesa_attribute_assigner import assign_conesa_attributes_to_model
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        EnvironmentalImpact,
        Phase6Model,
        ProjectAction,
        ReceptorFactor,
    )

    # --- Intentar cargar phase6_model_with_impacts.json (output de IM-03) ---
    model_path = exp_path / "impactos" / "phase6_model_with_impacts.json"

    if not model_path.exists():
        print(
            f"Aviso: no se encontro {model_path}.\n"
            "Ejecute primero: phase6-identify-impacts --write"
        )
        return 0

    try:
        with open(model_path, encoding="utf-8") as f:
            data = _json.load(f)

        expediente_id = data.get("expediente_id", exp_path.name)

        actions = [
            ProjectAction(
                action_id=a["action_id"],
                name=a["name"],
                description=a.get("description", ""),
                action_type=a.get("action_type", "OTRO"),
                operation_code=a.get("operation_code"),
                source_refs=a.get("source_refs", []),
                notes=a.get("notes", []),
            )
            for a in data.get("actions", [])
        ]

        receptor_factors = [
            ReceptorFactor(
                receptor_id=r["receptor_id"],
                inventory_factor_id=r["inventory_factor_id"],
                name=r["name"],
                inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
                ready_from_inventory=r.get("ready_from_inventory", False),
                critical_gaps=r.get("critical_gaps", []),
                notes=r.get("notes", []),
            )
            for r in data.get("receptor_factors", [])
        ]

        impacts = [
            EnvironmentalImpact(
                impact_id=imp["impact_id"],
                action_id=imp["action_id"],
                receptor_id=imp["receptor_id"],
                name=imp["name"],
                description=imp.get("description", ""),
                nature=imp.get("nature", "INDETERMINADO"),
                status=imp.get("status", "PENDIENTE_DATOS"),
                significance_without_measures=imp.get(
                    "significance_without_measures", "NO_VALORADO"
                ),
                significance_with_measures=imp.get(
                    "significance_with_measures", "NO_VALORADO"
                ),
                conesa_attributes=ConesaAttributes(
                    **{k: v for k, v in imp.get("conesa_attributes", {}).items()}
                ),
                data_gaps=imp.get("data_gaps", []),
                source_refs=imp.get("source_refs", []),
                measure_ids=imp.get("measure_ids", []),
                pva_ids=imp.get("pva_ids", []),
                warnings=imp.get("warnings", []),
                notes=imp.get("notes", []),
            )
            for imp in data.get("impacts", [])
        ]

        model = Phase6Model(
            expediente_id=expediente_id,
            actions=actions,
            receptor_factors=receptor_factors,
            impacts=impacts,
            warnings=data.get("warnings", []),
            notes=data.get("notes", []),
        )

    except (_json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Error: JSON invalido en {model_path}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error leyendo {model_path}: {exc}", file=sys.stderr)
        return 1

    score = not no_score
    result = assign_conesa_attributes_to_model(model, score=score)
    print(result.summary())

    if not write:
        return 0

    impactos_dir = exp_path / "impactos"
    impactos_dir.mkdir(parents=True, exist_ok=True)

    # Escribir el modelo actualizado
    conesa_model_path = impactos_dir / "phase6_model_with_conesa.json"
    with open(conesa_model_path, "w", encoding="utf-8") as f:
        _json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)

    # Escribir el resultado de asignación (sin el modelo completo para ligereza)
    result_dict = {
        "assigned_count": result.assigned_count,
        "scored_count": result.scored_count,
        "indeterminate_count": result.indeterminate_count,
        "skipped_count": result.skipped_count,
        "no_rule_count": result.no_rule_count,
        "warnings": result.warnings,
        "notes": result.notes,
    }
    result_path = impactos_dir / "conesa_assignment_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        _json.dump(result_dict, f, ensure_ascii=False, indent=2)

    print(f"\nOutputs escritos:")
    print(f"  {conesa_model_path}")
    print(f"  {result_path}")
    return 0


def cmd_phase6_generate_measures(exp_path: Path, write: bool) -> int:
    """Genera medidas ambientales por tipo de impacto para Fase 6 (IM-05)."""
    import json as _json
    from eia_agent.core.mitigation_measure_generator import (
        default_measure_generation_rules,
        generate_measures_for_model,
    )
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        EnvironmentalImpact,
        MitigationMeasure,
        Phase6Model,
        ProjectAction,
        ReceptorFactor,
    )

    impactos_dir = exp_path / "impactos"
    conesa_path = impactos_dir / "phase6_model_with_conesa.json"
    impacts_path = impactos_dir / "phase6_model_with_impacts.json"

    if conesa_path.exists():
        model_path = conesa_path
    elif impacts_path.exists():
        model_path = impacts_path
        print(f"Aviso: usando {impacts_path.name} (no se encontro phase6_model_with_conesa.json)")
    else:
        print(
            f"Error: no se encontro ningun modelo de impactos en {impactos_dir}.\n"
            "Ejecute primero: phase6-assign-conesa --write  (o phase6-identify-impacts --write)",
            file=sys.stderr,
        )
        return 1

    try:
        with open(model_path, encoding="utf-8") as f:
            data = _json.load(f)

        expediente_id = data.get("expediente_id", exp_path.name)

        actions = [
            ProjectAction(
                action_id=a["action_id"],
                name=a["name"],
                description=a.get("description", ""),
                action_type=a.get("action_type", "OTRO"),
                operation_code=a.get("operation_code"),
                source_refs=a.get("source_refs", []),
                notes=a.get("notes", []),
            )
            for a in data.get("actions", [])
        ]

        receptor_factors = [
            ReceptorFactor(
                receptor_id=r["receptor_id"],
                inventory_factor_id=r["inventory_factor_id"],
                name=r["name"],
                inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
                ready_from_inventory=r.get("ready_from_inventory", False),
                critical_gaps=r.get("critical_gaps", []),
                notes=r.get("notes", []),
            )
            for r in data.get("receptor_factors", [])
        ]

        impacts = [
            EnvironmentalImpact(
                impact_id=imp["impact_id"],
                action_id=imp["action_id"],
                receptor_id=imp["receptor_id"],
                name=imp["name"],
                description=imp.get("description", ""),
                nature=imp.get("nature", "INDETERMINADO"),
                status=imp.get("status", "PENDIENTE_DATOS"),
                significance_without_measures=imp.get(
                    "significance_without_measures", "NO_VALORADO"
                ),
                significance_with_measures=imp.get(
                    "significance_with_measures", "NO_VALORADO"
                ),
                conesa_attributes=ConesaAttributes(
                    **{k: v for k, v in imp.get("conesa_attributes", {}).items()}
                ),
                data_gaps=imp.get("data_gaps", []),
                source_refs=imp.get("source_refs", []),
                measure_ids=imp.get("measure_ids", []),
                pva_ids=imp.get("pva_ids", []),
                warnings=imp.get("warnings", []),
                notes=imp.get("notes", []),
            )
            for imp in data.get("impacts", [])
        ]

        existing_measures = [
            MitigationMeasure(
                measure_id=m["measure_id"],
                name=m["name"],
                description=m.get("description", ""),
                measure_type=m.get("measure_type", "CORRECTORA"),
                status=m.get("status", "PROPUESTA"),
                target_impact_ids=m.get("target_impact_ids", []),
                is_diagnostic=m.get("is_diagnostic", False),
                is_prl_only=m.get("is_prl_only", False),
                condition_before_submission=m.get("condition_before_submission", False),
                warnings=m.get("warnings", []),
                notes=m.get("notes", []),
            )
            for m in data.get("measures", [])
        ]

        model = Phase6Model(
            expediente_id=expediente_id,
            actions=actions,
            receptor_factors=receptor_factors,
            impacts=impacts,
            measures=existing_measures,
            warnings=data.get("warnings", []),
            notes=data.get("notes", []),
        )

    except (_json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Error: JSON invalido en {model_path}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error leyendo {model_path}: {exc}", file=sys.stderr)
        return 1

    rules = default_measure_generation_rules()
    result = generate_measures_for_model(model, rules)
    print(result.summary())

    if not write:
        return 0

    impactos_dir.mkdir(parents=True, exist_ok=True)

    measures_model_path = impactos_dir / "phase6_model_with_measures.json"
    with open(measures_model_path, "w", encoding="utf-8") as f:
        _json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)

    result_dict = {
        "generated_count": result.generated_count,
        "diagnostic_count": result.diagnostic_count,
        "prl_only_count": result.prl_only_count,
        "condition_before_submission_count": result.condition_before_submission_count,
        "measures": [m.to_dict() for m in result.model.measures],
        "warnings": result.warnings,
        "notes": result.notes,
    }
    result_path = impactos_dir / "measure_generation_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        _json.dump(result_dict, f, ensure_ascii=False, indent=2)

    print(f"\nOutputs escritos:")
    print(f"  {measures_model_path}")
    print(f"  {result_path}")
    return 0


def cmd_phase6_generate_pva(exp_path: Path, write: bool) -> int:
    """Genera fichas del Programa de Vigilancia Ambiental para Fase 6 (IM-06)."""
    import json as _json
    from eia_agent.core.pva_generator import (
        default_pva_generation_rules,
        generate_pva_for_model,
    )
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        EnvironmentalImpact,
        MitigationMeasure,
        Phase6Model,
        ProjectAction,
        ReceptorFactor,
    )

    impactos_dir = exp_path / "impactos"
    measures_path = impactos_dir / "phase6_model_with_measures.json"
    conesa_path = impactos_dir / "phase6_model_with_conesa.json"
    impacts_path = impactos_dir / "phase6_model_with_impacts.json"

    if measures_path.exists():
        model_path = measures_path
    elif conesa_path.exists():
        model_path = conesa_path
        print(f"Aviso: usando {conesa_path.name} (no se encontro phase6_model_with_measures.json)")
    elif impacts_path.exists():
        model_path = impacts_path
        print(f"Aviso: usando {impacts_path.name} (no se encontro phase6_model_with_measures.json)")
    else:
        print(
            f"Error: no se encontro ningun modelo de impactos en {impactos_dir}.\n"
            "Ejecute primero: phase6-generate-measures --write",
            file=sys.stderr,
        )
        return 1

    try:
        with open(model_path, encoding="utf-8") as f:
            data = _json.load(f)

        expediente_id = data.get("expediente_id", exp_path.name)

        actions = [
            ProjectAction(
                action_id=a["action_id"],
                name=a["name"],
                description=a.get("description", ""),
                action_type=a.get("action_type", "OTRO"),
                operation_code=a.get("operation_code"),
                source_refs=a.get("source_refs", []),
                notes=a.get("notes", []),
            )
            for a in data.get("actions", [])
        ]

        receptor_factors = [
            ReceptorFactor(
                receptor_id=r["receptor_id"],
                inventory_factor_id=r["inventory_factor_id"],
                name=r["name"],
                inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
                ready_from_inventory=r.get("ready_from_inventory", False),
                critical_gaps=r.get("critical_gaps", []),
                notes=r.get("notes", []),
            )
            for r in data.get("receptor_factors", [])
        ]

        impacts = [
            EnvironmentalImpact(
                impact_id=imp["impact_id"],
                action_id=imp["action_id"],
                receptor_id=imp["receptor_id"],
                name=imp["name"],
                description=imp.get("description", ""),
                nature=imp.get("nature", "INDETERMINADO"),
                status=imp.get("status", "PENDIENTE_DATOS"),
                significance_without_measures=imp.get(
                    "significance_without_measures", "NO_VALORADO"
                ),
                significance_with_measures=imp.get(
                    "significance_with_measures", "NO_VALORADO"
                ),
                conesa_attributes=ConesaAttributes(
                    **{k: v for k, v in imp.get("conesa_attributes", {}).items()}
                ),
                data_gaps=imp.get("data_gaps", []),
                source_refs=imp.get("source_refs", []),
                measure_ids=imp.get("measure_ids", []),
                pva_ids=imp.get("pva_ids", []),
                warnings=imp.get("warnings", []),
                notes=imp.get("notes", []),
            )
            for imp in data.get("impacts", [])
        ]

        measures = [
            MitigationMeasure(
                measure_id=m["measure_id"],
                name=m["name"],
                description=m.get("description", ""),
                measure_type=m.get("measure_type", "CORRECTORA"),
                status=m.get("status", "PROPUESTA"),
                target_impact_ids=m.get("target_impact_ids", []),
                is_diagnostic=m.get("is_diagnostic", False),
                is_prl_only=m.get("is_prl_only", False),
                condition_before_submission=m.get("condition_before_submission", False),
                warnings=m.get("warnings", []),
                notes=m.get("notes", []),
            )
            for m in data.get("measures", [])
        ]

        model = Phase6Model(
            expediente_id=expediente_id,
            actions=actions,
            receptor_factors=receptor_factors,
            impacts=impacts,
            measures=measures,
            warnings=data.get("warnings", []),
            notes=data.get("notes", []),
        )

    except (_json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Error: JSON invalido en {model_path}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error leyendo {model_path}: {exc}", file=sys.stderr)
        return 1

    rules = default_pva_generation_rules()
    result = generate_pva_for_model(model, rules)
    print(result.summary())

    if not write:
        return 0

    impactos_dir.mkdir(parents=True, exist_ok=True)

    pva_model_path = impactos_dir / "phase6_model_with_pva.json"
    with open(pva_model_path, "w", encoding="utf-8") as f:
        _json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)

    result_dict = {
        "generated_count": result.generated_count,
        "conditioned_count": result.conditioned_count,
        "uncovered_impact_ids": result.uncovered_impact_ids,
        "coverage_notes": result.coverage_notes,
        "pva_programs": [p.to_dict() for p in result.model.pva_programs],
        "warnings": result.warnings,
        "notes": result.notes,
    }
    result_path = impactos_dir / "pva_generation_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        _json.dump(result_dict, f, ensure_ascii=False, indent=2)

    print(f"\nOutputs escritos:")
    print(f"  {pva_model_path}")
    print(f"  {result_path}")
    return 0


def cmd_phase6_cumulative(exp_path: Path, write: bool) -> int:
    """Genera la sección C.5 de efectos acumulativos y sinérgicos (IM-08)."""
    import json as _json
    from eia_agent.core.cumulative_synergistic_section import (
        build_cumulative_synergistic_section_from_json,
        write_cumulative_synergistic_outputs,
    )

    impactos_dir = exp_path / "impactos"
    candidates = [
        impactos_dir / "phase6_model_with_pva.json",
        impactos_dir / "phase6_model_with_measures.json",
        impactos_dir / "phase6_model_with_conesa.json",
        impactos_dir / "phase6_model_with_impacts.json",
    ]

    model_path = None
    for candidate in candidates:
        if candidate.exists():
            model_path = candidate
            break

    if model_path is None:
        print(
            f"Error: no se encontro ningun modelo de Fase 6 en {impactos_dir}.\n"
            "Ejecute primero uno de:\n"
            "  phase6-generate-pva --write\n"
            "  phase6-generate-measures --write\n"
            "  phase6-identify-impacts --write",
            file=sys.stderr,
        )
        return 1

    if model_path.name != "phase6_model_with_pva.json":
        print(f"Aviso: usando {model_path.name} (phase6_model_with_pva.json no encontrado)")

    try:
        result = build_cumulative_synergistic_section_from_json(model_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error generando C.5: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        impactos_dir.mkdir(parents=True, exist_ok=True)
        json_path, md_path = write_cumulative_synergistic_outputs(result, impactos_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0


def cmd_phase6_validate_pva(exp_path: Path, write: bool) -> int:
    """Valida la cobertura PVA de los impactos de Fase 6 (IM-07)."""
    import json as _json
    from eia_agent.core.pva_coverage_validator import (
        validate_pva_coverage_from_json,
        write_pva_coverage_outputs,
    )

    impactos_dir = exp_path / "impactos"
    pva_path = impactos_dir / "phase6_model_with_pva.json"
    measures_path = impactos_dir / "phase6_model_with_measures.json"

    if pva_path.exists():
        model_path = pva_path
    elif measures_path.exists():
        model_path = measures_path
        print(f"Aviso: usando {measures_path.name} (no se encontro phase6_model_with_pva.json)")
    else:
        print(
            f"Error: no se encontro ningun modelo de Fase 6 en {impactos_dir}.\n"
            "Ejecute primero: phase6-generate-pva --write  (o phase6-generate-measures --write)",
            file=sys.stderr,
        )
        return 1

    try:
        result = validate_pva_coverage_from_json(model_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validacion de cobertura PVA: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        impactos_dir.mkdir(parents=True, exist_ok=True)
        json_path, md_path = write_pva_coverage_outputs(result, impactos_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_run_technical_pipeline(
    exp_path: Path,
    write: bool,
    prod: bool,
    continue_on_error: bool,
) -> int:
    """Pipeline tecnico automatico Fase5->Auditoria final (PIPE-01)."""
    from eia_agent.core.technical_pipeline import (
        run_technical_pipeline,
        write_pipeline_outputs,
    )

    mode = "PROD" if prod else "TEST"
    try:
        result = run_technical_pipeline(
            exp_path,
            write_outputs=write,
            mode=mode,
            stop_on_error=not continue_on_error,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en pipeline tecnico: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_pipeline_outputs(result, auditoria_dir)
        print(f"\nInforme de pipeline:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_success() else 1


def cmd_audit_final(exp_path: Path, write: bool) -> int:
    """Informe final de auditoría AU-04 — combina AU-01 + AU-02 + AU-03."""
    from eia_agent.core.final_audit_report import (
        build_final_audit_from_files,
        write_final_audit_outputs,
    )

    try:
        result = build_final_audit_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en informe final: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_final_audit_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    # exit 0 si CONFORME o CONFORME_CON_OBSERVACIONES; exit 1 si NO_CONFORME o INCOMPLETO
    return 0 if result.status in ("CONFORME", "CONFORME_CON_OBSERVACIONES") else 1


def cmd_audit_traceability(exp_path: Path, write: bool) -> int:
    """Validador de trazabilidad HC <-> DA (AU-03)."""
    from eia_agent.core.traceability_validator import (
        validate_traceability_from_files,
        write_traceability_validation_outputs,
    )

    try:
        result = validate_traceability_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador de trazabilidad: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_traceability_validation_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_prudence(exp_path: Path, write: bool) -> int:
    """Validador de prudencia metodológica y lenguaje prohibido (AU-02)."""
    from eia_agent.core.prudence_validator import (
        validate_prudence_from_files,
        write_prudence_validation_outputs,
    )

    try:
        result = validate_prudence_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador de prudencia: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_prudence_validation_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_conesa(exp_path: Path, write: bool) -> int:
    """Checker de cobertura Conesa en impactos y markdowns (RD-06)."""
    from eia_agent.core.conesa_checker import (
        validate_conesa_coverage_from_files,
        write_conesa_check_outputs,
    )

    try:
        result = validate_conesa_coverage_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en checker Conesa: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_conesa_check_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_block_consistency(exp_path: Path, write: bool) -> int:
    """Validador de coherencia entre bloques del expediente (RD-04)."""
    from eia_agent.core.block_consistency_validator import (
        validate_block_consistency_from_files,
        write_block_consistency_outputs,
    )

    try:
        result = validate_block_consistency_from_files(exp_path)
    except Exception as exc:
        print(f"Error en validador de coherencia: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_block_consistency_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_diagnostic_measures(exp_path: Path, write: bool) -> int:
    """Validador de medidas diagnosticas vs reductoras de significancia (RD-08)."""
    from eia_agent.core.diagnostic_measure_validator import (
        validate_diagnostic_measures_from_files,
        write_diagnostic_measure_outputs,
    )

    try:
        result = validate_diagnostic_measures_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador de medidas diagnosticas: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_diagnostic_measure_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_document_export(
    exp_path: Path, write: bool, generate_pdf: bool, overwrite: bool
) -> int:
    """Exporta el paquete de entrega a ZIP y opcionalmente PDF (DOC-07)."""
    from eia_agent.core.document_exporter import (
        export_document_package,
        write_export_result_outputs,
    )

    try:
        result = export_document_package(
            exp_path,
            write_outputs=write,
            generate_pdf=generate_pdf,
            overwrite=overwrite,
        )
    except Exception as exc:
        print(f"Error en document-export: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        doc_dir = exp_path / "documento"
        try:
            json_path, md_path = write_export_result_outputs(result, doc_dir)
            print(f"\nOutputs escritos:")
            if result.zip_path:
                print(f"  {result.zip_path}")
            if result.pdf_path:
                print(f"  {result.pdf_path}")
            print(f"  {json_path}")
            print(f"  {md_path}")
        except Exception as exc:
            print(f"Error escribiendo outputs: {exc}", file=sys.stderr)
            return 1

    # exit 0 si no hay ERRORs (tanto en dry-run como en write)
    # falta de conversor PDF no da exit 1 si paquete_entrega/ existe
    return 0 if result.error_count() == 0 else 1


def cmd_document_prepare_presentation(
    exp_path: Path, write: bool, create_final_docx: bool
) -> int:
    """Prepara el documento para revision y presentacion administrativa (DOC-08)."""
    from eia_agent.core.document_presentation_preparer import (
        prepare_document_for_presentation,
        write_presentation_outputs,
    )

    try:
        result = prepare_document_for_presentation(
            exp_path,
            write_outputs=write,
            create_final_docx=create_final_docx,
        )
    except Exception as exc:
        print(f"Error en document-prepare-presentation: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        print(f"\nOutputs escritos:")
        for f in result.generated_files:
            print(f"  {f}")

    return 0 if result.is_success() else 1


def cmd_document_package(exp_path: Path, write: bool, overwrite: bool) -> int:
    """Empaqueta los outputs del Documento Ambiental en paquete_entrega/ (DOC-06)."""
    from eia_agent.core.document_package_builder import (
        build_document_package,
        write_package_build_outputs,
    )

    try:
        result = build_document_package(exp_path, write_outputs=write, overwrite=overwrite)
    except Exception as exc:
        print(f"Error en document-package: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        doc_dir = exp_path / "documento"
        try:
            json_path, md_path = write_package_build_outputs(result, doc_dir)
            print(f"\nOutputs escritos:")
            print(f"  {result.package_dir}")
            print(f"  {json_path}")
            print(f"  {md_path}")
        except Exception as exc:
            print(f"Error escribiendo outputs: {exc}", file=sys.stderr)
            return 1

    # exit 0 si no faltan requeridos (tanto en dry-run como en write)
    return 0 if result.missing_required_count() == 0 else 1


def cmd_document_qc(exp_path: Path, write: bool) -> int:
    """Control de calidad del paquete documental final (DOC-04)."""
    from eia_agent.core.document_quality_checker import (
        run_document_quality_check,
        write_document_quality_outputs,
    )

    try:
        result = run_document_quality_check(exp_path)
    except Exception as exc:
        print(f"Error en document-qc: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        out_dir = exp_path / "documento"
        try:
            json_path, md_path = write_document_quality_outputs(result, out_dir)
            print("Outputs escritos:")
            print(f"  {json_path}")
            print(f"  {md_path}")
        except Exception as exc:
            print(f"Error escribiendo outputs: {exc}", file=sys.stderr)
            return 1

    return 0 if result.is_valid() else 1


def cmd_document_insert_figures(exp_path: Path, write: bool) -> int:
    """Localiza figuras del expediente e inserta en DOCX DOC-02 (DOC-03)."""
    from eia_agent.core.document_figure_inserter import insert_figures_into_document

    try:
        result = insert_figures_into_document(exp_path, write_outputs=write)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en document-insert-figures: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if result.warnings:
        print()
        for w in result.warnings[:10]:
            print(f"  [AVISO] {w}")

    if write and result.is_success():
        doc_dir = exp_path / "documento"
        print(f"\nOutputs escritos:")
        print(f"  {doc_dir / 'documento_ambiental_borrador_con_figuras.docx'}")
        print(f"  {doc_dir / 'document_figures_result.json'}")
        print(f"  {doc_dir / 'document_figures_result.md'}")

    return 0


def cmd_document_build_docx(exp_path: Path, write: bool) -> int:
    """Genera el DOCX del Documento Ambiental desde el Markdown DOC-01 (DOC-02)."""
    from eia_agent.core.document_docx_builder import build_docx_from_expediente

    try:
        result = build_docx_from_expediente(exp_path, write_outputs=write)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en document-build-docx: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if result.warnings:
        print()
        for w in result.warnings[:10]:
            print(f"  [AVISO] {w.summary()}")

    if write and result.generated:
        doc_dir = exp_path / "documento"
        print(f"\nOutputs escritos:")
        print(f"  {doc_dir / 'documento_ambiental_borrador.docx'}")
        print(f"  {doc_dir / 'docx_build_result.json'}")

    return 0 if result.is_success() or not write else 1


def cmd_document_build_md(exp_path: Path, write: bool) -> int:
    """Genera el borrador Markdown del Documento Ambiental (DOC-01)."""
    from eia_agent.core.document_markdown_builder import build_document_markdown

    try:
        result = build_document_markdown(exp_path, write_outputs=write)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en document-build-md: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if result.warnings:
        print()
        for w in result.warnings[:10]:
            print(f"  [AVISO] {w}")

    if write:
        doc_dir = exp_path / "documento"
        print(f"\nOutputs escritos:")
        print(f"  {doc_dir / 'documento_ambiental_borrador.md'}")
        print(f"  {doc_dir / 'document_build_result.json'}")

    if result.partial_blocks:
        print(f"\nBloques PARTIAL: {', '.join(result.partial_blocks)}")
        print("  (contenido generado con advertencias — revisar fuentes faltantes)")

    return 0 if result.is_complete_draft() else 1


def cmd_document_manifest(exp_path: Path, write: bool) -> int:
    """Manifest del Documento Ambiental: estado por bloque A-K (DOC-00)."""
    from eia_agent.core.document_manifest import (
        build_document_manifest,
        write_document_manifest_outputs,
    )

    try:
        result = build_document_manifest(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en manifest del documento: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        doc_dir = exp_path / "documento"
        json_path, md_path = write_document_manifest_outputs(result, doc_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_ready_for_markdown_generation() else 1


def cmd_audit_prl_measures(exp_path: Path, write: bool) -> int:
    """Validador de separacion EIA / PRL (RD-09)."""
    from eia_agent.core.prl_measure_validator import (
        validate_prl_measures_from_files,
        validate_prl_measures_markdowns_from_files,
        write_prl_measure_outputs,
        _combine_results,
    )

    try:
        model_result = validate_prl_measures_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador PRL (modelo): {exc}", file=sys.stderr)
        return 1

    try:
        md_result = validate_prl_measures_markdowns_from_files(exp_path)
    except FileNotFoundError:
        md_result = None
    except Exception as exc:
        print(f"Aviso validador PRL (markdown): {exc}", file=sys.stderr)
        md_result = None

    result = _combine_results(model_result, md_result) if md_result is not None else model_result

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_prl_measure_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_conditional_chains(exp_path: Path, write: bool) -> int:
    """Validador de cadenas condicionales impacto-medida-PVA (IM-09)."""
    from eia_agent.core.conditional_chain_validator import (
        validate_conditional_chains_from_files,
        write_conditional_chain_outputs,
    )

    try:
        result = validate_conditional_chains_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador cadenas condicionales: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_conditional_chain_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_valid() else 1


def cmd_audit_positive_gaps(exp_path: Path, write: bool) -> int:
    """Validador de impactos positivos con gap ALTA y nota de incertidumbre (RD-07)."""
    from eia_agent.core.positive_impact_gap_validator import (
        validate_positive_gap_from_files,
        write_positive_gap_outputs,
    )

    try:
        result = validate_positive_gap_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en validador de impactos positivos: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_positive_gap_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.error_count() == 0 else 1


def cmd_assumptions_summary(exp_path: Path, write: bool) -> int:
    """Muestra el resumen de asunciones de test del expediente (OB-05)."""
    from eia_agent.core.assumption_test_system import (
        build_assumptions_markdown,
        load_assumptions_registry,
    )

    at_json = exp_path / "control_interno" / "asunciones_test.json"

    try:
        registry = load_assumptions_registry(at_json)
    except ValueError as exc:
        print(f"Error: JSON corrupto en {at_json}: {exc}", file=sys.stderr)
        return 1

    if not registry.assumptions:
        print("Sin asunciones registradas.")
        if not at_json.exists():
            print(f"(archivo {at_json.name} no existe en control_interno/)")
        return 0

    print(registry.summary())

    if write:
        out_dir = exp_path / "control_interno"
        out_dir.mkdir(parents=True, exist_ok=True)
        md_content = build_assumptions_markdown(registry)
        md_path = out_dir / "asunciones_test_resumen.md"
        md_path.write_text(md_content, encoding="utf-8")
        print(f"\nOutput escrito:")
        print(f"  {md_path}")

    return 0


def cmd_audit_art45(exp_path: Path, write: bool) -> int:
    """Checklist programático del art. 45.1 Ley 21/2013 (AU-01)."""
    from eia_agent.core.art45_checklist import (
        evaluate_art45_checklist_from_files,
        write_art45_checklist_outputs,
    )

    try:
        result = evaluate_art45_checklist_from_files(exp_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en checklist art.45: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        auditoria_dir = exp_path / "auditoria"
        json_path, md_path = write_art45_checklist_outputs(result, auditoria_dir)
        print(f"\nOutputs escritos:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.is_structurally_complete() else 1


def cmd_inventory_gate(exp_path: Path, write: bool, prod: bool) -> int:
    """Evalúa el gate de cierre de Fase 5 sobre el inventario construido (F5-01)."""
    from eia_agent.core.phase5_gate import (
        evaluate_phase5_gate_from_inventory_json,
        write_phase5_gate_outputs,
    )
    inventory_path = exp_path / "inventario" / "inventory_summary.json"
    if not inventory_path.exists():
        print(
            f"Error: no se encontró {inventory_path}.\n"
            "Ejecute primero: inventory-build --write",
            file=sys.stderr,
        )
        return 1

    test_mode = not prod
    try:
        result = evaluate_phase5_gate_from_inventory_json(inventory_path, test_mode=test_mode)
        print(result.summary())
        if write:
            out_dir = exp_path / "inventario"
            json_path, md_path = write_phase5_gate_outputs(result, out_dir)
            print(f"\nOutputs escritos:")
            print(f"  {json_path}")
            print(f"  {md_path}")
        return 0 if not result.is_blocked() else 1
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error de datos: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error en inventory-gate: {exc}", file=sys.stderr)
        return 1


def cmd_init_expediente(exp_path: Path, force: bool, with_guides: bool) -> int:
    """Inicializa la estructura estandar de un expediente EIA-Agent (BE-03)."""
    from eia_agent.core.expediente_initializer import (
        initialize_expediente,
        write_init_result,
    )

    result = initialize_expediente(exp_path, force=force, with_guides=with_guides)
    print(result.summary())

    if result.is_success():
        result_path = exp_path / "control_interno" / "init_expediente_result.json"
        try:
            write_init_result(result, result_path)
            print(f"\nResultado escrito en: {result_path}")
        except Exception as exc:
            print(f"Aviso: no se pudo escribir result JSON: {exc}", file=sys.stderr)
        return 0

    return 1


def cmd_config_check(exp_path: Path, write: bool) -> int:
    """Valida variables de entorno conocidas (BE-04). Sin llamadas externas."""
    from eia_agent.core.config_manager import (
        validate_config,
        write_config_validation_outputs,
    )

    # Buscar .env en raíz del proyecto o en el expediente
    project_root = Path(__file__).parent
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        dotenv_path = exp_path / ".env"
        if not dotenv_path.exists():
            dotenv_path = None

    result = validate_config(dotenv_path=dotenv_path)
    print(result.summary())

    if write:
        out_dir = exp_path / "control_interno"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            json_path, md_path = write_config_validation_outputs(result, out_dir)
            print(f"\nOutputs escritos:")
            print(f"  {json_path}")
            print(f"  {md_path}")
        except Exception as exc:
            print(f"Aviso: no se pudo escribir output: {exc}", file=sys.stderr)

    return 0 if result.is_valid() else 1


def cmd_secrets_scan(exp_path: Path, write: bool) -> int:
    """Escanea el repositorio en busca de secretos potenciales (BE-04). Sin llamadas externas."""
    from eia_agent.core.config_manager import (
        scan_repo_for_potential_secrets,
        write_config_validation_outputs,
    )

    # Escanear raíz del proyecto
    project_root = Path(__file__).parent
    result = scan_repo_for_potential_secrets(project_root)
    print(result.summary())

    if result.issues:
        print()
        for issue in result.issues[:15]:
            print(f"  [{issue.severity}] {issue.message}")
        if len(result.issues) > 15:
            print(f"  ... y {len(result.issues) - 15} hallazgos más.")
        print()
        print("  AVISO: Este informe no muestra secretos completos.")
        print("  Verifique manualmente los archivos indicados.")

    if write:
        out_dir = exp_path / "control_interno"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            json_path, md_path = write_config_validation_outputs(result, out_dir)
            print(f"\nOutputs escritos:")
            print(f"  {json_path}")
            print(f"  {md_path}")
        except Exception as exc:
            print(f"Aviso: no se pudo escribir output: {exc}", file=sys.stderr)

    return 0 if result.error_count() == 0 else 1


def cmd_document_structure(
    exp_path: Path, write: bool, normalize: bool
) -> int:
    """Valida y normaliza la estructura del DOCX final (EN-02)."""
    from eia_agent.core.document_structure_manager import (
        find_best_available_docx,
        normalize_document_structure,
        validate_document_structure,
        write_document_structure_outputs,
    )

    docx_path = find_best_available_docx(exp_path)
    if docx_path is None:
        print("Error: no se encontro ningun DOCX en documento/", file=sys.stderr)
        return 1

    if normalize:
        out_docx = exp_path / "documento" / "documento_ambiental_estructurado.docx"
        result = normalize_document_structure(docx_path, out_docx)
    else:
        result = validate_document_structure(docx_path)

    print(result.summary())

    if result.errors:
        print()
        for err in result.errors[:10]:
            print(f"  [ERROR] {err['code']}: {err['message']}")

    if write:
        out_dir = exp_path / "documento"
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = write_document_structure_outputs(result, out_dir)
        print(f"\nOutputs escritos:")
        for p in paths:
            print(f"  {p}")

    return 0 if result.is_valid() else 1


def cmd_document_toc(
    exp_path: Path, write: bool, apply_toc: bool, replace_placeholder: bool
) -> int:
    """Gestiona el indice automatico (TOC) en el DOCX final (EN-05)."""
    from eia_agent.core.document_toc_manager import process_document_toc

    result = process_document_toc(
        exp_path,
        write_outputs=write,
        apply_toc=apply_toc,
        replace_placeholder=replace_placeholder,
    )

    print(result.summary())

    if result.issues:
        print()
        for issue in result.issues[:10]:
            print(f"  [{issue.severity}] {issue.code}: {issue.message}")

    if write:
        print(f"\nOutputs escritos en: {exp_path / 'documento'}")

    return 0 if result.is_valid() else 1


def cmd_document_numbering(exp_path: Path, write: bool, apply_styles: bool) -> int:
    """Analiza y aplica estilos de numeracion al DOCX final (EN-04)."""
    from eia_agent.core.document_numbering_manager import process_document_numbering

    result = process_document_numbering(
        exp_path,
        write_outputs=write,
        apply_styles=apply_styles,
    )

    print(result.summary())

    if result.issues:
        print()
        for issue in result.issues[:10]:
            print(f"  [{issue.severity}] {issue.code}: {issue.message}")

    if write:
        print(f"\nOutputs escritos en: {exp_path / 'documento'}")

    return 0 if result.is_valid() else 1


def cmd_cliente_da(exp_path: Path, write: bool, prod: bool) -> int:
    """Flujo completo DA-01: pipeline tecnico + cadena documental + estado final (DA-01)."""
    from eia_agent.core.document_flow_da import (
        run_da_flow,
        write_da_flow_outputs,
    )

    mode = "PROD" if prod else "TEST"
    try:
        result = run_da_flow(exp_path, write=write, mode=mode)
    except Exception as exc:
        print(f"Error en flujo DA-01: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_da_flow_outputs(result, exp_path)
        print(f"\nInforme de estado:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if not result.has_blocking() else 1


def cmd_cliente_plan(exp_path: Path, write: bool) -> int:
    """Plan de accion cliente: peticiones al promotor + acciones internas."""
    from eia_agent.core.client_action_plan import (
        build_client_action_plan,
        write_client_action_plan_outputs,
    )

    try:
        result = build_client_action_plan(exp_path)
    except Exception as exc:
        print(f"Error generando plan de accion cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_action_plan_outputs(result, exp_path)
        print("\nPlan de accion:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if not result.warnings else 1


def cmd_cliente_intake(exp_path: Path, write: bool) -> int:
    """Intake cliente: contrato de datos/documentos para iniciar expediente."""
    from eia_agent.core.client_intake import (
        build_client_intake,
        write_client_intake_outputs,
    )

    try:
        result = build_client_intake(exp_path)
    except Exception as exc:
        print(f"Error generando intake cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_intake_outputs(result, exp_path)
        print("\nIntake cliente:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0


def cmd_cliente_dashboard(exp_path: Path, write: bool) -> int:
    """Dashboard cliente: resumen UI/API del expediente."""
    from eia_agent.core.client_dashboard import (
        build_client_dashboard,
        write_client_dashboard_outputs,
    )

    try:
        result = build_client_dashboard(exp_path)
    except Exception as exc:
        print(f"Error generando dashboard cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_dashboard_outputs(result, exp_path)
        print("\nDashboard cliente:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if not result.warnings else 1


def cmd_cliente_climate_traceability(exp_path: Path, write: bool) -> int:
    """Control cliente: trazabilidad de climograma, estacion y datos."""
    from eia_agent.core.client_climate_traceability import build_client_climate_traceability

    try:
        result = build_client_climate_traceability(exp_path, write_outputs=write)
    except Exception as exc:
        print(f"Error generando trazabilidad climatica cliente: {exc}", file=sys.stderr)
        return 1

    print(f"Estado climatico cliente: {result.get('status')}")
    for warning in result.get("warnings") or []:
        print(f"  AVISO: {warning}")
    if write:
        print("\nOutputs escritos:")
        print(f"  {exp_path / 'clima' / 'trazabilidad_climatica_cliente.json'}")
        print(f"  {exp_path / 'clima' / 'trazabilidad_climatica_cliente.md'}")

    return 0


def cmd_cliente_form_schema(exp_path: Path, write: bool) -> int:
    """Form schema cliente: controles y validaciones minimas para UI/API."""
    from eia_agent.core.client_form_schema import (
        build_client_form_schema,
        write_client_form_schema_outputs,
    )

    try:
        result = build_client_form_schema(exp_path)
    except Exception as exc:
        print(f"Error generando form schema cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_form_schema_outputs(result, exp_path)
        print("\nForm schema cliente:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0


def cmd_cliente_submission_check(exp_path: Path, write: bool) -> int:
    """Validacion entrega cliente: faltantes, formatos y coordenadas basicas."""
    from eia_agent.core.client_submission_validator import (
        build_client_submission_validation,
        write_client_submission_validation_outputs,
    )

    try:
        result = build_client_submission_validation(exp_path)
    except Exception as exc:
        print(f"Error validando entrega cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_submission_validation_outputs(result, exp_path)
        print("\nValidacion entrega cliente:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0 if result.can_start_initial_processing else 1


def cmd_cliente_portal(exp_path: Path, write: bool) -> int:
    """Portal cliente: paquete unico intake + dashboard + siguientes pasos."""
    from eia_agent.core.client_portal import (
        build_client_portal,
        write_client_portal_outputs,
    )

    try:
        result = build_client_portal(exp_path)
    except Exception as exc:
        print(f"Error generando portal cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())

    if write:
        json_path, md_path = write_client_portal_outputs(result, exp_path)
        print("\nPortal cliente:")
        print(f"  {json_path}")
        print(f"  {md_path}")

    return 0


def cmd_cliente_portal_site(exp_path: Path, write: bool) -> int:
    """Portal cliente HTML: exportacion estatica autocontenida."""
    from eia_agent.core.client_portal import build_client_portal
    from eia_agent.core.client_portal_site import (
        build_client_portal_html,
        write_client_portal_site,
    )

    try:
        portal = build_client_portal(exp_path)
        html = build_client_portal_html(portal)
    except Exception as exc:
        print(f"Error generando portal cliente HTML: {exc}", file=sys.stderr)
        return 1

    print(portal.summary())
    print(f"HTML bytes   : {len(html.encode('utf-8'))}")

    if write:
        html_path = write_client_portal_site(exp_path, portal)
        print("\nPortal cliente HTML:")
        print(f"  {html_path}")

    return 0


def cmd_cliente_trial_package(exp_path: Path, write: bool) -> int:
    """Paquete de prueba cliente: HTML, contratos JSON/MD y ZIP entregable."""
    from eia_agent.core.client_trial_package import build_client_trial_package

    try:
        result = build_client_trial_package(exp_path, write_outputs=write)
    except Exception as exc:
        print(f"Error generando paquete de prueba cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())
    if write:
        print("\nPaquete de prueba cliente:")
        print(f"  {result.package_dir}")
        print(f"  {result.zip_path}")

    return 0


def cmd_cliente_app_package(exp_path: Path, write: bool) -> int:
    """App profesional cliente: HTML, contratos, documentos, mapas y ZIP."""
    from eia_agent.core.client_app_package import build_client_app_package

    try:
        result = build_client_app_package(exp_path, write_outputs=write)
    except Exception as exc:
        print(f"Error generando app profesional cliente: {exc}", file=sys.stderr)
        return 1

    print(result.summary())
    if write:
        print("\nApp profesional cliente:")
        print(f"  {result.app_dir}")
        print(f"  {result.zip_path}")

    return 0


def cmd_cliente_backend(exp_path: Path, host: str, port: int) -> int:
    """Backend local cliente: sirve app y API para expedientes nuevos."""
    from eia_agent.core.client_app_package import build_client_app_package
    from eia_agent.core.client_backend import serve_client_backend

    try:
        app_dir = exp_path / "documento" / "cliente_app"
        if not app_dir.exists():
            build_client_app_package(exp_path, write_outputs=True)
        workspace = exp_path.parent
        serve_client_backend(workspace=workspace, static_dir=app_dir, host=host, port=port)
        return 0
    except KeyboardInterrupt:
        print("\nBackend cliente detenido.")
        return 0
    except Exception as exc:
        print(f"Error arrancando backend cliente: {exc}", file=sys.stderr)
        return 1


def cmd_phase1(exp_path: Path, write: bool) -> int:
    """Ejecuta el pipeline de Fase 1 (IN-06). Por defecto solo lectura."""
    from eia_agent.core.phase1_pipeline import run_phase1
    try:
        result = run_phase1(exp_path, write_outputs=write)
        print(result.summary())
        if write:
            out_dir = exp_path / "control_interno"
            print(f"\nOutputs escritos en: {out_dir}")
        return 0
    except Exception as exc:
        print(f"Error en Fase 1: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_expediente.py",
        description="EIA-Agent v2.1 — Runner básico (CLI-01). No ejecuta agentes reales.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_expediente.py expediente-EIA-NAVE-222 status
  python run_expediente.py expediente-EIA-NAVE-222 validate
  python run_expediente.py expediente-EIA-NAVE-222 gate 4
  python run_expediente.py expediente-EIA-NAVE-222 gate 4 --prod
  python run_expediente.py expediente-EIA-NAVE-222 recover
  python run_expediente.py expediente-EIA-NAVE-222 recover --write-report
  python run_expediente.py expediente-EIA-NAVE-222 log-summary
  python run_expediente.py expediente-EIA-NAVE-222 phase1
  python run_expediente.py expediente-EIA-NAVE-222 phase1 --write
  python run_expediente.py expediente-EIA-NAVE-222 phase2
  python run_expediente.py expediente-EIA-NAVE-222 phase2 --write
  python run_expediente.py expediente-EIA-NAVE-222 phase2 --prod
  python run_expediente.py expediente-EIA-NAVE-222 phase3
  python run_expediente.py expediente-EIA-NAVE-222 phase3 --write
  python run_expediente.py expediente-EIA-NAVE-222 phase4-precheck
  python run_expediente.py expediente-EIA-NAVE-222 phase4-precheck --write
  python run_expediente.py expediente-EIA-NAVE-222 phase4-climate --stations config/estaciones.json --climate-data config/datos_climaticos.json
  python run_expediente.py expediente-EIA-NAVE-222 phase4-climate --stations config/estaciones.json --climate-data config/datos_climaticos.json --write
  python run_expediente.py expediente-EIA-NAVE-222 phase4-offline --stations config/estaciones.json --climate-data config/datos_climaticos.json
  python run_expediente.py expediente-EIA-NAVE-222 phase4-offline --stations config/estaciones.json --climate-data config/datos_climaticos.json --write
  python run_expediente.py expediente-EIA-NAVE-222 inventory-build
  python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
  python run_expediente.py expediente-EIA-NAVE-222 inventory-gate
  python run_expediente.py expediente-EIA-NAVE-222 inventory-gate --write
  python run_expediente.py expediente-EIA-NAVE-222 inventory-gate --prod
  python run_expediente.py expediente-EIA-NAVE-222 phase6-actions
  python run_expediente.py expediente-EIA-NAVE-222 phase6-actions --write
  python run_expediente.py expediente-EIA-NAVE-222 phase6-identify-impacts
  python run_expediente.py expediente-EIA-NAVE-222 phase6-identify-impacts --write
  python run_expediente.py expediente-EIA-NAVE-222 phase6-assign-conesa
  python run_expediente.py expediente-EIA-NAVE-222 phase6-assign-conesa --write
  python run_expediente.py expediente-EIA-NAVE-222 phase6-assign-conesa --write --no-score
        """,
    )
    parser.add_argument("expediente", help="Ruta al directorio del expediente EIA")

    sub = parser.add_subparsers(dest="command", required=True, metavar="COMANDO")

    cfg_p = sub.add_parser(
        "config-check",
        help=(
            "Validar variables de entorno conocidas (BE-04). "
            "Lee .env si existe. Sin llamadas externas ni validación contra APIs."
        ),
    )
    cfg_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir control_interno/config_validation_result.json y .md. "
            "Los valores sensibles aparecen siempre enmascarados."
        ),
    )

    scan_p = sub.add_parser(
        "secrets-scan",
        help=(
            "Escanear el repositorio en busca de secretos potenciales (BE-04). "
            "No imprime secretos reales. Sin llamadas externas."
        ),
    )
    scan_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir informe de escaneo en control_interno/config_validation_result.json y .md."
        ),
    )

    init_p = sub.add_parser(
        "init-expediente",
        help=(
            "Inicializar estructura estandar de carpetas, guias y metadatos (BE-03). "
            "Crea el directorio si no existe. No modifica expedientes existentes salvo --force."
        ),
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribir archivos guia estandar existentes (README, instrucciones, estado).",
    )
    init_p.add_argument(
        "--no-guides",
        action="store_true",
        dest="no_guides",
        help="Solo crear carpetas; no generar archivos guia ni metadata.",
    )

    sub.add_parser(
        "status",
        help="Estado actual del orquestador (sin modificar el expediente)",
    )
    sub.add_parser(
        "validate",
        help="Validar los schemas JSON de las capas del expediente",
    )

    gate_p = sub.add_parser(
        "gate",
        help="Evaluar el gate mínimo de una fase",
    )
    gate_p.add_argument("phase", metavar="FASE", help="Número de fase (1-9)")
    gate_p.add_argument(
        "--prod",
        action="store_true",
        help="Modo producción: AT/PROVISIONAL/INDETERMINADO son ERROR en lugar de WARNING",
    )

    recover_p = sub.add_parser(
        "recover",
        help="Diagnosticar sesiones interrumpidas o inconsistentes",
    )
    recover_p.add_argument(
        "--write-report",
        action="store_true",
        dest="write_report",
        help="Escribir control_interno/recovery_report.json (por defecto no escribe nada)",
    )

    sub.add_parser(
        "log-summary",
        help="Resumen del log del orquestador (solo lectura)",
    )

    phase1_p = sub.add_parser(
        "phase1",
        help="Pipeline de Fase 1: indexar documentos y extraer hechos candidatos (IN-06)",
    )
    phase1_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase1_result.json y phase1_result.md en control_interno/",
    )

    phase2_p = sub.add_parser(
        "phase2",
        help="Pipeline de Fase 2: construir ObjectScope y evaluar Gate 2 (OB-06)",
    )
    phase2_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase2_result.json, ficha_objeto_evaluado.md y object_scope.json",
    )
    phase2_p.add_argument(
        "--prod",
        action="store_true",
        help="Modo producción: AT activos y gaps ALTA son ERROR en lugar de WARNING",
    )

    phase3_p = sub.add_parser(
        "phase3",
        help="Pipeline de Fase 3: triaje normativo básico (TN-05)",
    )
    phase3_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase3_result.json y nota_encuadre_legal.md en control_interno/",
    )

    phase4pre_p = sub.add_parser(
        "phase4-precheck",
        help="Precheck de Fase 4: evaluar preparacion para cartografia y clima (CA-08)",
    )
    phase4pre_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase4_precheck.json y phase4_precheck.md en control_interno/",
    )

    phase4cl_p = sub.add_parser(
        "phase4-climate",
        help="Pipeline climático Fase 4 offline: selección estación, Köppen, climograma (CL-06)",
    )
    phase4cl_p.add_argument(
        "--stations",
        required=True,
        metavar="STATIONS_JSON",
        help="Ruta al JSON local de estaciones climáticas",
    )
    phase4cl_p.add_argument(
        "--climate-data",
        required=True,
        dest="climate_data",
        metavar="CLIMATE_DATA_JSON",
        help="Ruta al JSON local de datos climáticos mensuales",
    )
    phase4cl_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase4_climate_result.json, descripcion_clima.md y climograma PNG en clima/",
    )

    phase4off_p = sub.add_parser(
        "phase4-offline",
        help="Pipeline Fase 4 offline completo: CA-08 + CL-06 + CA-10 + CA-11 (F4-01)",
    )
    phase4off_p.add_argument(
        "--stations",
        required=True,
        metavar="STATIONS_JSON",
        help="Ruta al JSON local de estaciones climáticas",
    )
    phase4off_p.add_argument(
        "--climate-data",
        required=True,
        dest="climate_data",
        metavar="CLIMATE_DATA_JSON",
        help="Ruta al JSON local de datos climáticos mensuales",
    )
    phase4off_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir todos los outputs (fase4/, clima/, cartografia/)",
    )

    cart_p = sub.add_parser(
        "cartography-plan",
        help="Plan cartográfico offline Fase 4: 6 MapSpec sin renderizado (CA-10)",
    )
    cart_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir cartografia_plan.json y cartografia_plan.md en cartografia/",
    )

    smap_p = sub.add_parser(
        "schematic-maps",
        help="Generar mapas esquemáticos PNG provisionales desde un plan CA-10 (CA-11)",
    )
    smap_p.add_argument(
        "--plan",
        default=None,
        metavar="PLAN_JSON",
        help="Ruta al cartografia_plan.json (por defecto: cartografia/cartografia_plan.json)",
    )
    smap_p.add_argument(
        "--write",
        action="store_true",
        help="Generar los PNGs en cartografia/mapas/ (sin --write solo muestra la lista)",
    )

    p6act_p = sub.add_parser(
        "phase6-actions",
        help="Construir acciones del proyecto desde phase2_result.json para Fase 6 (IM-02)",
    )
    p6act_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase6_actions.json y phase6_model_base.json en impactos/",
    )

    p6imp_p = sub.add_parser(
        "phase6-identify-impacts",
        help="Identificar impactos preliminares accion x receptor para Fase 6 (IM-03)",
    )
    p6imp_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir impact_identification_result.json y "
            "phase6_model_with_impacts.json en impactos/"
        ),
    )

    p6conesa_p = sub.add_parser(
        "phase6-assign-conesa",
        help="Asignar atributos Conesa tipologicos a impactos identificados (IM-04)",
    )
    p6conesa_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir phase6_model_with_conesa.json y "
            "conesa_assignment_result.json en impactos/"
        ),
    )
    p6conesa_p.add_argument(
        "--no-score",
        action="store_true",
        dest="no_score",
        help="No aplicar valoración Conesa (IM-01) tras la asignación de atributos",
    )

    p6meas_p = sub.add_parser(
        "phase6-generate-measures",
        help="Generar medidas ambientales por tipo de impacto (IM-05)",
    )
    p6meas_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir phase6_model_with_measures.json y "
            "measure_generation_result.json en impactos/"
        ),
    )

    p6pva_p = sub.add_parser(
        "phase6-generate-pva",
        help="Generar fichas del Programa de Vigilancia Ambiental (IM-06)",
    )
    p6pva_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir phase6_model_with_pva.json y "
            "pva_generation_result.json en impactos/"
        ),
    )

    p6cum_p = sub.add_parser(
        "phase6-cumulative",
        help="Generar seccion C.5 efectos acumulativos y sinergicos (IM-08)",
    )
    p6cum_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir cumulative_synergistic_result.json y "
            "C5_acumulativos_sinergicos.md en impactos/"
        ),
    )

    p6vpva_p = sub.add_parser(
        "phase6-validate-pva",
        help="Validar cobertura PVA de impactos relevantes (IM-07)",
    )
    p6vpva_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir pva_coverage_result.json y "
            "pva_coverage_result.md en impactos/"
        ),
    )

    inv_p = sub.add_parser(
        "inventory-build",
        help="Construir inventario ambiental inicial Fase 5 desde outputs Fase 4 (IV-02)",
    )
    inv_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir fichas markdown, resumen e índice JSON en inventario/",
    )

    invgate_p = sub.add_parser(
        "inventory-gate",
        help="Evaluar gate de cierre de Fase 5 sobre inventario construido (F5-01)",
    )
    invgate_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir phase5_gate_result.json y .md en inventario/",
    )
    invgate_p.add_argument(
        "--prod",
        action="store_true",
        help="Modo producción (test_mode=False); por defecto test_mode=True",
    )

    au01_p = sub.add_parser(
        "audit-art45",
        help="Checklist art. 45.1 Ley 21/2013 — EIA simplificada (AU-01)",
    )
    au01_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir art45_checklist_result.json y "
            "art45_checklist_result.md en auditoria/"
        ),
    )

    au02_p = sub.add_parser(
        "audit-prudence",
        help="Validador de prudencia metodológica y lenguaje prohibido (AU-02)",
    )
    au02_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir prudence_validation_result.json y "
            "prudence_validation_result.md en auditoria/"
        ),
    )

    pipe01_p = sub.add_parser(
        "run-technical-pipeline",
        help="Pipeline tecnico automatico F5->AU-04 en un solo comando (PIPE-01)",
    )
    pipe01_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir todos los outputs de cada paso en sus rutas normales",
    )
    pipe01_p.add_argument(
        "--prod",
        action="store_true",
        help="Modo produccion (mode=PROD). No cambia administrative_ready.",
    )
    pipe01_p.add_argument(
        "--continue-on-error",
        dest="continue_on_error",
        action="store_true",
        help="Continuar con pasos siguientes aunque un paso falle",
    )

    au04_p = sub.add_parser(
        "audit-final",
        help="Informe final de auditoría: combina AU-01 + AU-02 + AU-03 (AU-04)",
    )
    au04_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir final_audit_result.json y "
            "final_audit_result.md en auditoria/"
        ),
    )

    au03_p = sub.add_parser(
        "audit-traceability",
        help="Validador de trazabilidad HC <-> DA — referencias en textos del expediente (AU-03)",
    )
    au03_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir traceability_validation_result.json y "
            "traceability_validation_result.md en auditoria/"
        ),
    )

    at_p = sub.add_parser(
        "assumptions-summary",
        help="Resumen de asunciones de test activas del expediente (OB-05)",
    )
    at_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir asunciones_test_resumen.md en control_interno/",
    )

    rd06_p = sub.add_parser(
        "audit-conesa",
        help="Checker de cobertura Conesa en impactos y markdowns (RD-06)",
    )
    rd06_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir conesa_check_result.json y .md en auditoria/",
    )

    rd04_p = sub.add_parser(
        "audit-block-consistency",
        help="Validador de coherencia entre bloques del expediente (RD-04)",
    )
    rd04_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir block_consistency_result.json y .md en auditoria/",
    )

    rd08_p = sub.add_parser(
        "audit-diagnostic-measures",
        help="Validador de medidas diagnosticas vs reductoras de significancia (RD-08)",
    )
    rd08_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir diagnostic_measure_validation_result.json y .md en auditoria/",
    )

    rd09_p = sub.add_parser(
        "audit-prl-measures",
        help="Validador de separacion medidas EIA / PRL (RD-09)",
    )
    rd09_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir prl_measure_validation_result.json y .md en auditoria/",
    )

    im09_p = sub.add_parser(
        "audit-conditional-chains",
        help="Validador de cadenas condicionales impacto-medida-PVA (IM-09)",
    )
    im09_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir conditional_chain_result.json y .md en auditoria/",
    )

    rd07_p = sub.add_parser(
        "audit-positive-gaps",
        help="Validador de impactos positivos con gap ALTA y nota de incertidumbre (RD-07)",
    )
    rd07_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir positive_gap_result.json y .md en auditoria/",
    )

    doc00_p = sub.add_parser(
        "document-manifest",
        help="Manifest del Documento Ambiental: estado por bloque A-K (DOC-00)",
    )
    doc00_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir document_manifest.json y .md en documento/",
    )

    doc01_p = sub.add_parser(
        "document-build-md",
        help=(
            "Generar borrador Markdown del Documento Ambiental a partir de "
            "outputs tecnicos (DOC-01)"
        ),
    )
    doc01_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir documento/documento_ambiental_borrador.md y "
            "documento/document_build_result.json"
        ),
    )

    doc02_p = sub.add_parser(
        "document-build-docx",
        help=(
            "Convertir borrador Markdown a DOCX profesional (DOC-02). "
            "Requiere documento/documento_ambiental_borrador.md generado por DOC-01."
        ),
    )
    doc02_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir documento/documento_ambiental_borrador.docx y "
            "documento/docx_build_result.json"
        ),
    )

    doc04_p = sub.add_parser(
        "document-qc",
        help=(
            "Control de calidad del paquete documental final (DOC-04). "
            "Verifica completitud, bloques A-K, disclaimer y coherencia."
        ),
    )
    doc04_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir documento/document_quality_result.json y "
            "documento/document_quality_result.md"
        ),
    )

    doc03_p = sub.add_parser(
        "document-insert-figures",
        help=(
            "Insertar figuras, mapas y climogramas en DOCX (DOC-03). "
            "Requiere documento/documento_ambiental_borrador.docx generado por DOC-02."
        ),
    )
    doc03_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir documento/documento_ambiental_borrador_con_figuras.docx, "
            "document_figures_result.json y document_figures_result.md"
        ),
    )

    doc06_p = sub.add_parser(
        "document-package",
        help=(
            "Empaquetar outputs documentales en documento/paquete_entrega/ (DOC-06). "
            "Sin --write solo muestra que se empaquetaria."
        ),
    )
    doc06_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Crear documento/paquete_entrega/, copiar archivos, "
            "generar README_ENTREGA.md, package_build_result.json y .md"
        ),
    )
    doc06_p.add_argument(
        "--overwrite",
        action="store_true",
        default=True,
        help=(
            "Sobreescribir paquete_entrega/ si ya existe (comportamiento por defecto). "
            "Pase --no-overwrite para omitir si ya existe."
        ),
    )

    doc07_p = sub.add_parser(
        "document-export",
        help=(
            "Exportar paquete_entrega/ a ZIP y opcionalmente a PDF (DOC-07). "
            "Sin --write solo muestra que se exportaria."
        ),
    )
    doc07_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Crear documento/paquete_entrega.zip "
            "e intentar PDF. Escribe document_export_result.json y .md."
        ),
    )
    doc07_p.add_argument(
        "--no-pdf",
        action="store_true",
        dest="no_pdf",
        help="Solo ZIP; no intentar exportacion PDF.",
    )
    doc07_p.add_argument(
        "--overwrite",
        action="store_true",
        default=True,
        help="Sobreescribir ZIP existente (comportamiento por defecto).",
    )

    doc08_p = sub.add_parser(
        "document-prepare-presentation",
        help=(
            "Preparar documento para revision y presentacion administrativa (DOC-08). "
            "Sin --write solo muestra que se generaria."
        ),
    )
    doc08_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir metadatos, hoja de firmas, checklist y (si procede) "
            "DOCX final revisable."
        ),
    )
    doc08_p.add_argument(
        "--no-final-docx",
        action="store_true",
        dest="no_final_docx",
        help="No crear documento_ambiental_final_revisable.docx.",
    )

    en02_p = sub.add_parser(
        "document-structure",
        help=(
            "Validar y normalizar la estructura del DOCX final (EN-02). "
            "Sin flags: solo valida. --write: escribe JSON/MD. "
            "--normalize: genera copia estructurada."
        ),
    )
    en02_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir documento/document_structure_result.json y .md."
        ),
    )
    en02_p.add_argument(
        "--normalize",
        action="store_true",
        help=(
            "Generar copia normalizada: documento/documento_ambiental_estructurado.docx. "
            "No modifica el DOCX original."
        ),
    )

    en04_p = sub.add_parser(
        "document-numbering",
        help=(
            "Analizar y aplicar estilos de numeracion en el DOCX final (EN-04). "
            "Sin flags: solo analiza. --write: escribe JSON/MD. "
            "--apply: crea copia con estilos de lista aplicados."
        ),
    )
    en04_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/document_numbering_result.json y .md.",
    )
    en04_p.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Crear documento/documento_ambiental_numerado.docx con estilos de "
            "lista aplicados a parrafos candidatos. No modifica el DOCX original."
        ),
    )

    en05_p = sub.add_parser(
        "document-toc",
        help=(
            "Gestionar el indice automatico (TOC) en el DOCX final (EN-05). "
            "Sin flags: solo analiza. --write: escribe JSON/MD. "
            "--apply: crea copia con campo TOC insertado."
        ),
    )
    en05_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/document_toc_result.json y .md.",
    )
    en05_p.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Crear documento/documento_ambiental_con_toc.docx con campo TOC insertado. "
            "No modifica el DOCX original."
        ),
    )
    en05_p.add_argument(
        "--no-replace",
        action="store_true",
        dest="no_replace",
        help=(
            "No reemplazar placeholder de TOC aunque exista; "
            "insertar el TOC al inicio del documento."
        ),
    )

    da01_p = sub.add_parser(
        "cliente-da",
        help=(
            "Flujo completo DA-01: pipeline tecnico + cadena documental + informe de estado "
            "(DA-01). Genera todos los outputs del Documento Ambiental y clasifica cada item "
            "como CERRADO, PENDIENTE o BLOQUEANTE. --write requerido para outputs completos."
        ),
    )
    da01_p.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribir todos los outputs del flujo: pipeline, documento MD/DOCX, "
            "figuras, QC, paquete, ZIP, presentacion, estructura, numeracion, TOC "
            "y estado_expediente_da.json/.md."
        ),
    )
    da01_p.add_argument(
        "--prod",
        action="store_true",
        help=(
            "Modo produccion (mode=PROD) para el pipeline tecnico. "
            "No cambia administrative_ready=False."
        ),
    )

    plan_p = sub.add_parser(
        "cliente-plan",
        help=(
            "Generar plan de accion cliente: peticiones al promotor y acciones "
            "internas pendientes a partir de DA-01/AU-04. No declara aptitud."
        ),
    )
    plan_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/plan_accion_cliente.json y .md.",
    )

    intake_p = sub.add_parser(
        "cliente-intake",
        help=(
            "Generar contrato de entrada cliente: datos, memorias, coordenadas, "
            "fotos, planos y cartografia requeridos. No declara aptitud."
        ),
    )
    intake_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_intake.json y .md.",
    )

    form_schema_p = sub.add_parser(
        "cliente-form-schema",
        help=(
            "Generar esquema de formulario para UI/API cliente: controles, "
            "validaciones minimas y formatos aceptados. No declara aptitud."
        ),
    )
    form_schema_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_form_schema.json y .md.",
    )

    submission_p = sub.add_parser(
        "cliente-submission-check",
        help=(
            "Validar entrega cliente contra el formulario: obligatorios, formatos "
            "y coordenadas basicas. No declara aptitud."
        ),
    )
    submission_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_submission_validation.json y .md.",
    )

    dash_p = sub.add_parser(
        "cliente-dashboard",
        help=(
            "Generar dashboard cliente para UI/API: estado ejecutivo, indicadores, "
            "ruta de cierre y artefactos disponibles. No declara aptitud."
        ),
    )
    dash_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_dashboard.json y .md.",
    )

    climate_trace_p = sub.add_parser(
        "cliente-climate-traceability",
        help=(
            "Comprobar trazabilidad cliente del climograma: coordenadas, estacion, "
            "datos y figura disponible. No declara aptitud."
        ),
    )
    climate_trace_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir clima/trazabilidad_climatica_cliente.json y .md.",
    )

    portal_p = sub.add_parser(
        "cliente-portal",
        help=(
            "Generar paquete unico para UI/API cliente: intake, dashboard, "
            "siguientes pasos y artefactos. No declara aptitud."
        ),
    )
    portal_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_portal.json y .md.",
    )

    portal_site_p = sub.add_parser(
        "cliente-portal-site",
        help=(
            "Generar HTML estatico del portal cliente en documento/portal_cliente/. "
            "No declara aptitud."
        ),
    )
    portal_site_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/portal_cliente/index.html.",
    )

    trial_package_p = sub.add_parser(
        "cliente-trial-package",
        help=(
            "Generar paquete de prueba cliente con portal HTML, JSON/Markdown "
            "y ZIP entregable. No declara aptitud."
        ),
    )
    trial_package_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_trial_package/ y .zip.",
    )

    app_package_p = sub.add_parser(
        "cliente-app-package",
        help=(
            "Generar app profesional cliente con HTML, contratos, documentos, "
            "mapas/clima disponibles y ZIP entregable. No declara aptitud."
        ),
    )
    app_package_p.add_argument(
        "--write",
        action="store_true",
        help="Escribir documento/cliente_app/ y eia_agent_cliente_app.zip.",
    )

    backend_p = sub.add_parser(
        "cliente-backend",
        help=(
            "Arrancar backend local cliente con app web y API para crear expedientes "
            "nuevos. No declara aptitud."
        ),
    )
    backend_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host de escucha. Por defecto 127.0.0.1.",
    )
    backend_p.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Puerto de escucha. Por defecto 8765.",
    )

    return parser


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    """Punto de entrada. Devuelve el código de salida (0=OK, 1=error/bloqueado)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # init-expediente: el directorio puede no existir todavia (BE-03)
    if args.command == "init-expediente":
        exp_path = Path(args.expediente).resolve()
        with_guides = not getattr(args, "no_guides", False)
        force = getattr(args, "force", False)
        return cmd_init_expediente(exp_path, force=force, with_guides=with_guides)

    # config-check / secrets-scan: no requieren que el expediente exista (BE-04)
    if args.command == "config-check":
        exp_path = Path(args.expediente).resolve()
        return cmd_config_check(exp_path, write=getattr(args, "write", False))
    if args.command == "secrets-scan":
        exp_path = Path(args.expediente).resolve()
        return cmd_secrets_scan(exp_path, write=getattr(args, "write", False))

    exp_path = Path(args.expediente).resolve()
    if not exp_path.exists():
        print(f"Error: el expediente '{args.expediente}' no existe.", file=sys.stderr)
        return 1
    if not exp_path.is_dir():
        print(f"Error: '{args.expediente}' no es un directorio.", file=sys.stderr)
        return 1

    if args.command == "status":
        return cmd_status(exp_path)
    if args.command == "validate":
        return cmd_validate(exp_path)
    if args.command == "gate":
        return cmd_gate(exp_path, args.phase, args.prod)
    if args.command == "recover":
        return cmd_recover(exp_path, args.write_report)
    if args.command == "log-summary":
        return cmd_log_summary(exp_path)
    if args.command == "phase1":
        return cmd_phase1(exp_path, args.write)
    if args.command == "phase2":
        return cmd_phase2(exp_path, args.write, args.prod)
    if args.command == "phase3":
        return cmd_phase3(exp_path, args.write)
    if args.command == "phase4-precheck":
        return cmd_phase4_precheck(exp_path, args.write)
    if args.command == "phase4-climate":
        return cmd_phase4_climate(exp_path, args.stations, args.climate_data, args.write)
    if args.command == "phase4-offline":
        return cmd_phase4_offline(exp_path, args.stations, args.climate_data, args.write)
    if args.command == "cartography-plan":
        return cmd_cartography_plan(exp_path, args.write)
    if args.command == "schematic-maps":
        return cmd_schematic_maps(exp_path, args.plan, args.write)
    if args.command == "phase6-actions":
        return cmd_phase6_actions(exp_path, args.write)
    if args.command == "phase6-identify-impacts":
        return cmd_phase6_identify_impacts(exp_path, args.write)
    if args.command == "phase6-assign-conesa":
        return cmd_phase6_assign_conesa(exp_path, args.write, args.no_score)
    if args.command == "phase6-generate-measures":
        return cmd_phase6_generate_measures(exp_path, args.write)
    if args.command == "phase6-generate-pva":
        return cmd_phase6_generate_pva(exp_path, args.write)
    if args.command == "phase6-cumulative":
        return cmd_phase6_cumulative(exp_path, args.write)
    if args.command == "phase6-validate-pva":
        return cmd_phase6_validate_pva(exp_path, args.write)
    if args.command == "inventory-build":
        return cmd_inventory_build(exp_path, args.write)
    if args.command == "inventory-gate":
        return cmd_inventory_gate(exp_path, args.write, args.prod)
    if args.command == "audit-art45":
        return cmd_audit_art45(exp_path, args.write)
    if args.command == "audit-prudence":
        return cmd_audit_prudence(exp_path, args.write)
    if args.command == "audit-traceability":
        return cmd_audit_traceability(exp_path, args.write)
    if args.command == "audit-final":
        return cmd_audit_final(exp_path, args.write)
    if args.command == "run-technical-pipeline":
        return cmd_run_technical_pipeline(
            exp_path, args.write, args.prod, args.continue_on_error
        )
    if args.command == "assumptions-summary":
        return cmd_assumptions_summary(exp_path, args.write)
    if args.command == "audit-conesa":
        return cmd_audit_conesa(exp_path, args.write)
    if args.command == "audit-block-consistency":
        return cmd_audit_block_consistency(exp_path, args.write)
    if args.command == "audit-diagnostic-measures":
        return cmd_audit_diagnostic_measures(exp_path, args.write)
    if args.command == "audit-prl-measures":
        return cmd_audit_prl_measures(exp_path, args.write)
    if args.command == "audit-conditional-chains":
        return cmd_audit_conditional_chains(exp_path, args.write)
    if args.command == "audit-positive-gaps":
        return cmd_audit_positive_gaps(exp_path, args.write)
    if args.command == "document-manifest":
        return cmd_document_manifest(exp_path, args.write)
    if args.command == "document-build-md":
        return cmd_document_build_md(exp_path, args.write)
    if args.command == "document-build-docx":
        return cmd_document_build_docx(exp_path, args.write)
    if args.command == "document-insert-figures":
        return cmd_document_insert_figures(exp_path, args.write)
    if args.command == "document-qc":
        return cmd_document_qc(exp_path, args.write)
    if args.command == "document-package":
        overwrite = getattr(args, "overwrite", True)
        return cmd_document_package(exp_path, args.write, overwrite)
    if args.command == "document-export":
        overwrite = getattr(args, "overwrite", True)
        generate_pdf = not getattr(args, "no_pdf", False)
        return cmd_document_export(exp_path, args.write, generate_pdf, overwrite)
    if args.command == "document-prepare-presentation":
        create_final_docx = not getattr(args, "no_final_docx", False)
        return cmd_document_prepare_presentation(exp_path, args.write, create_final_docx)
    if args.command == "document-structure":
        normalize = getattr(args, "normalize", False)
        return cmd_document_structure(exp_path, args.write, normalize)
    if args.command == "document-numbering":
        apply_styles = getattr(args, "apply", False)
        return cmd_document_numbering(exp_path, args.write, apply_styles)
    if args.command == "document-toc":
        apply_toc = getattr(args, "apply", False)
        replace_placeholder = not getattr(args, "no_replace", False)
        return cmd_document_toc(exp_path, args.write, apply_toc, replace_placeholder)

    if args.command == "cliente-da":
        return cmd_cliente_da(exp_path, args.write, getattr(args, "prod", False))
    if args.command == "cliente-plan":
        return cmd_cliente_plan(exp_path, args.write)
    if args.command == "cliente-intake":
        return cmd_cliente_intake(exp_path, args.write)
    if args.command == "cliente-form-schema":
        return cmd_cliente_form_schema(exp_path, args.write)
    if args.command == "cliente-submission-check":
        return cmd_cliente_submission_check(exp_path, args.write)
    if args.command == "cliente-dashboard":
        return cmd_cliente_dashboard(exp_path, args.write)
    if args.command == "cliente-climate-traceability":
        return cmd_cliente_climate_traceability(exp_path, args.write)
    if args.command == "cliente-portal":
        return cmd_cliente_portal(exp_path, args.write)
    if args.command == "cliente-portal-site":
        return cmd_cliente_portal_site(exp_path, args.write)
    if args.command == "cliente-trial-package":
        return cmd_cliente_trial_package(exp_path, args.write)
    if args.command == "cliente-app-package":
        return cmd_cliente_app_package(exp_path, args.write)
    if args.command == "cliente-backend":
        return cmd_cliente_backend(exp_path, args.host, args.port)

    # No debería llegar aquí (argparse lo impide con required=True)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
