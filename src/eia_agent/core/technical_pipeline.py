"""
technical_pipeline -- PIPE-01 + PIPE-02 + PIPE-03 + PIPE-04 + PIPE-05
Pipeline técnico automático desde inventario (Fase 5) hasta auditoría final (AU-04).

Orquesta en un único flujo, en orden, todos los módulos ya construidos:
  1.  INVENTORY_BUILD              — build_inventory_from_phase4
  2.  INVENTORY_GATE               — evaluate_phase5_gate_from_inventory_json
  3.  PHASE6_ACTIONS               — build_phase6_model_with_actions
  4.  PHASE6_IDENTIFY_IMPACTS      — identify_impacts_from_model
  5.  PHASE6_ASSIGN_CONESA         — assign_conesa_attributes_to_model
  6.  PHASE6_GENERATE_MEASURES     — generate_measures_for_model
  7.  PHASE6_GENERATE_PVA          — generate_pva_for_model
  8.  PHASE6_VALIDATE_PVA          — validate_pva_coverage
  9.  AUDIT_CONDITIONAL_CHAINS     — validate_conditional_chains_from_files (IM-09)
  10. AUDIT_POSITIVE_GAPS          — validate_positive_gap_from_files (RD-07)
  11. PHASE6_CUMULATIVE            — build_cumulative_synergistic_section_from_json
  12. AUDIT_ART45                  — evaluate_art45_checklist_from_files
  13. AUDIT_PRUDENCE               — validate_prudence_from_files
  14. AUDIT_TRACEABILITY           — validate_traceability_from_files
  15. AUDIT_BLOCK_CONSISTENCY      — validate_block_consistency_from_files (RD-04)
  16. AUDIT_CONESA                 — validate_conesa_coverage_from_files (RD-06)
  17. AUDIT_DIAGNOSTIC_MEASURES   — validate_diagnostic_measures_from_files (RD-08)
  18. AUDIT_PRL_MEASURES          — validate_prl_measures_from_files (RD-09)
  19. AUDIT_FINAL                 — build_final_audit_from_files

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No duplica lógica de negocio de los módulos ya existentes.
  - No declara aptitud administrativa.
  - No importa de run_expediente.py (evita dependencia circular).
  - Cada paso captura excepciones y las convierte en StepResult.

Modo dry-run (write_outputs=False):
  - Ejecuta los módulos en memoria.
  - No escribe archivos de fases intermedias.
  - Si un paso necesita un archivo intermedio que no existe (porque el paso
    anterior no lo escribió), se marca BLOCKED.

Modo write (write_outputs=True):
  - Escribe todos los outputs en sus rutas normales.
  - Los pasos posteriores encuentran los archivos generados.
"""
from __future__ import annotations

import json
import traceback
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PIPELINE_STEP_STATUS: list[str] = [
    "SUCCESS",
    "FAILED",
    "SKIPPED",
    "BLOCKED",
    "WARNING",
]

PIPELINE_MODE: list[str] = ["TEST", "PROD"]

TECHNICAL_PIPELINE_STEPS: list[str] = [
    "INVENTORY_BUILD",
    "INVENTORY_GATE",
    "PHASE6_ACTIONS",
    "PHASE6_IDENTIFY_IMPACTS",
    "PHASE6_ASSIGN_CONESA",
    "PHASE6_GENERATE_MEASURES",
    "PHASE6_GENERATE_PVA",
    "PHASE6_VALIDATE_PVA",
    "AUDIT_CONDITIONAL_CHAINS",
    "AUDIT_POSITIVE_GAPS",
    "PHASE6_CUMULATIVE",
    "AUDIT_ART45",
    "AUDIT_PRUDENCE",
    "AUDIT_TRACEABILITY",
    "AUDIT_BLOCK_CONSISTENCY",
    "AUDIT_CONESA",
    "AUDIT_DIAGNOSTIC_MEASURES",
    "AUDIT_PRL_MEASURES",
    "AUDIT_FINAL",
]

_STEP_NAMES: dict[str, str] = {
    "INVENTORY_BUILD": "Construccion de inventario ambiental (Fase 5)",
    "INVENTORY_GATE": "Gate de cierre de Fase 5",
    "PHASE6_ACTIONS": "Acciones del proyecto (Fase 6)",
    "PHASE6_IDENTIFY_IMPACTS": "Identificacion de impactos candidatos",
    "PHASE6_ASSIGN_CONESA": "Asignacion Conesa prudente",
    "PHASE6_GENERATE_MEASURES": "Generacion de medidas ambientales",
    "PHASE6_GENERATE_PVA": "Generacion del PVA",
    "PHASE6_VALIDATE_PVA": "Validacion de cobertura PVA",
    "AUDIT_CONDITIONAL_CHAINS": "Cadenas condicionales impacto-medida-PVA (IM-09)",
    "AUDIT_POSITIVE_GAPS": "Impactos positivos con gaps ALTA (RD-07)",
    "PHASE6_CUMULATIVE": "Seccion C.5 acumulativos/sinergicos",
    "AUDIT_ART45": "Auditoria art.45 (AU-01)",
    "AUDIT_PRUDENCE": "Auditoria prudencia metodologica (AU-02)",
    "AUDIT_TRACEABILITY": "Auditoria trazabilidad HC<->DA (AU-03)",
    "AUDIT_BLOCK_CONSISTENCY": "Coherencia entre bloques (RD-04)",
    "AUDIT_CONESA": "Cobertura Conesa en impactos (RD-06)",
    "AUDIT_DIAGNOSTIC_MEASURES": "Medidas diagnosticas vs reductoras (RD-08)",
    "AUDIT_PRL_MEASURES": "Separacion EIA / PRL (RD-09)",
    "AUDIT_FINAL": "Informe final de auditoria (AU-04+RD-04+RD-06+RD-07+RD-08+RD-09+IM-09)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def now_iso() -> str:
    """Devuelve la hora actual en formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_load_json(path: "str | Path") -> "dict | None":
    """Carga un JSON si existe; devuelve None si no existe o está corrupto."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _phase6_model_from_dict(data: dict, exp_id: str) -> "Phase6Model":
    """Deserializa un Phase6Model desde un dict JSON.

    No implementa lógica de negocio: es solo mapeo de tipos.
    """
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        EnvironmentalImpact,
        MitigationMeasure,
        Phase6Model,
        ProjectAction,
        PVAProgram,
        ReceptorFactor,
    )

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

    pva_programs = [
        PVAProgram(
            pva_id=p["pva_id"],
            name=p.get("name", p["pva_id"]),
            factor_id=p.get("factor_id", "FI-001"),
            indicator=p.get("indicator", ""),
            threshold=p.get("threshold", ""),
            frequency=p.get("frequency", "CONDICIONAL"),
            target_impact_ids=p.get("target_impact_ids", []),
            target_measure_ids=p.get("target_measure_ids", []),
            responsible=p.get("responsible", ""),
            records=p.get("records", []),
            warnings=p.get("warnings", []),
            notes=p.get("notes", []),
        )
        for p in data.get("pva_programs", [])
    ]

    return Phase6Model(
        expediente_id=data.get("expediente_id", exp_id),
        actions=actions,
        receptor_factors=receptor_factors,
        impacts=impacts,
        measures=measures,
        pva_programs=pva_programs,
        warnings=data.get("warnings", []),
        notes=data.get("notes", []),
    )


def _best_phase6_model_path(impactos_dir: Path) -> "Path | None":
    """Devuelve el path al modelo Fase 6 más completo disponible."""
    candidates = [
        impactos_dir / "phase6_model_with_pva.json",
        impactos_dir / "phase6_model_with_measures.json",
        impactos_dir / "phase6_model_with_conesa.json",
        impactos_dir / "phase6_model_with_impacts.json",
        impactos_dir / "phase6_model_base.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------------------
# TechnicalPipelineStepResult
# ---------------------------------------------------------------------------

@dataclass
class TechnicalPipelineStepResult:
    """Resultado de un paso individual del pipeline técnico."""

    step_id: str
    name: str
    status: str
    started_at: str
    finished_at: str
    message: str = ""
    output_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def is_success(self) -> bool:
        return self.status in ("SUCCESS", "WARNING")

    def is_blocking_failure(self) -> bool:
        return self.status in ("FAILED", "BLOCKED")

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "message": self.message[:500],
            "output_files": list(self.output_files),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        s = f"[{self.status:8s}] {self.step_id:28s} — {self.name[:50]}"
        if self.errors:
            s += f" | ERROR: {self.errors[0][:60]}"
        return _ascii_safe(s)


# ---------------------------------------------------------------------------
# TechnicalPipelineResult
# ---------------------------------------------------------------------------

@dataclass
class TechnicalPipelineResult:
    """Resultado completo del pipeline técnico."""

    expediente_id: str
    expediente_path: str
    mode: str
    write_outputs: bool
    started_at: str
    finished_at: str = ""
    steps: list[TechnicalPipelineStepResult] = field(default_factory=list)
    final_status: str = "UNKNOWN"
    final_audit_status: Optional[str] = None
    output_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def success_count(self) -> int:
        return sum(1 for s in self.steps if s.status in ("SUCCESS", "WARNING"))

    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "FAILED")

    def skipped_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "SKIPPED")

    def blocked_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "BLOCKED")

    def is_success(self) -> bool:
        """True si no hay pasos FAILED ni BLOCKED."""
        return self.failed_count() == 0 and self.blocked_count() == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "expediente_path": self.expediente_path,
            "mode": self.mode,
            "write_outputs": self.write_outputs,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "final_status": self.final_status,
            "final_audit_status": self.final_audit_status,
            "steps": [s.to_dict() for s in self.steps],
            "success_count": self.success_count(),
            "failed_count": self.failed_count(),
            "skipped_count": self.skipped_count(),
            "blocked_count": self.blocked_count(),
            "output_files": list(self.output_files),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "notes": list(self.notes),
            "is_success": self.is_success(),
        }

    def summary(self) -> str:
        lines = [
            "--- PIPE-01 Pipeline tecnico automatico ---",
            f"Expediente  : {self.expediente_id}",
            f"Modo        : {self.mode} | write={self.write_outputs}",
            f"Estado      : {self.final_status}",
        ]
        if self.final_audit_status:
            lines.append(f"Auditoria   : {self.final_audit_status}")
        lines += [
            f"Pasos OK    : {self.success_count()}/{len(self.steps)}",
            f"Fallidos    : {self.failed_count()}",
            f"Bloqueados  : {self.blocked_count()}",
            f"Omitidos    : {self.skipped_count()}",
        ]
        for step in self.steps:
            lines.append(f"  {step.summary()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step runners internos
# ---------------------------------------------------------------------------

def _step(
    step_id: str,
    started: str,
    status: str,
    message: str = "",
    output_files: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    notes: list[str] | None = None,
) -> TechnicalPipelineStepResult:
    return TechnicalPipelineStepResult(
        step_id=step_id,
        name=_STEP_NAMES.get(step_id, step_id),
        status=status,
        started_at=started,
        finished_at=now_iso(),
        message=message,
        output_files=output_files or [],
        warnings=warnings or [],
        errors=errors or [],
        notes=notes or [],
    )


def _skipped(step_id: str) -> TechnicalPipelineStepResult:
    t = now_iso()
    return _step(step_id, t, "SKIPPED",
                 message="Paso omitido por fallo en paso anterior.")


def _blocked(step_id: str, reason: str) -> TechnicalPipelineStepResult:
    t = now_iso()
    return _step(step_id, t, "BLOCKED", errors=[reason])


def _run_inventory_build(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "INVENTORY_BUILD"
    try:
        from eia_agent.core.inventory_builder import build_inventory_from_phase4
        result = build_inventory_from_phase4(exp_path, write_outputs=write)
        outputs = []
        if write:
            inv_dir = exp_path / "inventario"
            if (inv_dir / "inventory_summary.json").exists():
                outputs.append(str(inv_dir / "inventory_summary.json"))
        return _step(
            step_id, started,
            "SUCCESS" if not result.warnings else "WARNING",
            message=f"Inventario: {result.factor_count} factores.",
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except FileNotFoundError as exc:
        return _step(step_id, started, "WARNING",
                     message=f"Inventario parcial: {exc}",
                     warnings=[str(exc)])
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_inventory_gate(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "INVENTORY_GATE"
    inv_path = exp_path / "inventario" / "inventory_summary.json"
    if not inv_path.exists():
        return _blocked(step_id, f"inventory_summary.json no encontrado: {inv_path}")
    try:
        from eia_agent.core.phase5_gate import (
            evaluate_phase5_gate_from_inventory_json,
            write_phase5_gate_outputs,
        )
        test_mode = (mode != "PROD")
        result = evaluate_phase5_gate_from_inventory_json(inv_path, test_mode=test_mode)
        outputs = []
        if write:
            json_p, md_p = write_phase5_gate_outputs(result, exp_path / "inventario")
            outputs = [str(json_p), str(md_p)]
        status = "FAILED" if result.is_blocked() else "SUCCESS"
        return _step(
            step_id, started, status,
            message=f"Gate F5: {result.decision}",
            output_files=outputs,
            warnings=list(result.warnings),
            errors=[f"Gate bloqueado: {result.decision}"] if result.is_blocked() else [],
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_actions(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_ACTIONS"
    try:
        from eia_agent.core.project_action_builder import (
            build_actions_from_phase2_data,
            build_phase6_model_with_actions,
        )
        phase2_data = safe_load_json(
            exp_path / "control_interno" / "phase2_result.json"
        )
        build_result = build_actions_from_phase2_data(phase2_data)
        model = build_phase6_model_with_actions(exp_path.name, phase2_data)

        outputs = []
        if write:
            impactos_dir = exp_path / "impactos"
            impactos_dir.mkdir(parents=True, exist_ok=True)
            actions_path = impactos_dir / "phase6_actions.json"
            model_path = impactos_dir / "phase6_model_base.json"
            with open(actions_path, "w", encoding="utf-8") as f:
                json.dump(build_result.to_dict(), f, ensure_ascii=False, indent=2)
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(model.to_dict(), f, ensure_ascii=False, indent=2)
            outputs = [str(actions_path), str(model_path)]

        return _step(
            step_id, started, "SUCCESS",
            message=f"Acciones: {len(model.actions)} detectadas.",
            output_files=outputs,
            warnings=list(build_result.warnings),
            notes=list(build_result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_identify_impacts(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_IDENTIFY_IMPACTS"
    try:
        from eia_agent.core.impact_identifier import (
            build_minimal_receptor_factors,
            build_phase6_model_with_identified_impacts,
            identify_impacts_from_model,
        )
        from eia_agent.core.project_action_builder import build_phase6_model_with_actions

        impactos_dir = exp_path / "impactos"
        model_path = impactos_dir / "phase6_model_base.json"

        if model_path.exists():
            data = safe_load_json(model_path)
            if data:
                model = _phase6_model_from_dict(data, exp_path.name)
            else:
                model = build_phase6_model_with_actions(exp_path.name, None)
        else:
            model = build_phase6_model_with_actions(exp_path.name, None)

        if not model.receptor_factors:
            import dataclasses
            model = dataclasses.replace(
                model, receptor_factors=build_minimal_receptor_factors()
            )

        result = identify_impacts_from_model(model)
        model_with_impacts = build_phase6_model_with_identified_impacts(model)

        outputs = []
        if write:
            impactos_dir.mkdir(parents=True, exist_ok=True)
            res_path = impactos_dir / "impact_identification_result.json"
            imp_model_path = impactos_dir / "phase6_model_with_impacts.json"
            with open(res_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            with open(imp_model_path, "w", encoding="utf-8") as f:
                json.dump(model_with_impacts.to_dict(), f, ensure_ascii=False, indent=2)
            outputs = [str(res_path), str(imp_model_path)]

        return _step(
            step_id, started, "SUCCESS",
            message=f"Impactos: {len(model_with_impacts.impacts)} identificados.",
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_assign_conesa(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_ASSIGN_CONESA"
    impactos_dir = exp_path / "impactos"
    model_path = (
        impactos_dir / "phase6_model_with_impacts.json"
        if (impactos_dir / "phase6_model_with_impacts.json").exists()
        else _best_phase6_model_path(impactos_dir)
    )
    if not model_path:
        if write:
            return _blocked(step_id, "No se encontro modelo Fase 6 en impactos/")
        # dry-run: nada que hacer sin modelo
        return _step(step_id, started, "WARNING",
                     message="Dry-run: no hay modelo Fase 6. Ejecute con --write.",
                     warnings=["Sin modelo Fase 6 disponible en dry-run."])
    try:
        from eia_agent.core.conesa_attribute_assigner import (
            assign_conesa_attributes_to_model,
        )
        data = safe_load_json(model_path)
        if not data:
            return _step(step_id, started, "FAILED",
                         errors=[f"JSON invalido: {model_path}"])
        model = _phase6_model_from_dict(data, exp_path.name)
        result = assign_conesa_attributes_to_model(model, score=True)

        outputs = []
        if write:
            impactos_dir.mkdir(parents=True, exist_ok=True)
            conesa_path = impactos_dir / "phase6_model_with_conesa.json"
            res_path = impactos_dir / "conesa_assignment_result.json"
            with open(conesa_path, "w", encoding="utf-8") as f:
                json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)
            res_dict = {
                "assigned_count": result.assigned_count,
                "scored_count": result.scored_count,
                "indeterminate_count": result.indeterminate_count,
                "warnings": result.warnings,
                "notes": result.notes,
            }
            with open(res_path, "w", encoding="utf-8") as f:
                json.dump(res_dict, f, ensure_ascii=False, indent=2)
            outputs = [str(conesa_path), str(res_path)]

        return _step(
            step_id, started, "SUCCESS",
            message=f"Conesa: {result.assigned_count} asignaciones.",
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_generate_measures(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_GENERATE_MEASURES"
    impactos_dir = exp_path / "impactos"

    # Preferir modelo Conesa si existe
    model_path = None
    for candidate in [
        impactos_dir / "phase6_model_with_conesa.json",
        impactos_dir / "phase6_model_with_impacts.json",
    ]:
        if candidate.exists():
            model_path = candidate
            break

    if not model_path:
        if write:
            return _blocked(step_id, "No se encontro phase6_model_with_conesa.json ni phase6_model_with_impacts.json")
        return _step(step_id, started, "WARNING",
                     message="Dry-run: sin modelo Conesa disponible.",
                     warnings=["Ejecute con --write para generar modelo Conesa primero."])
    try:
        from eia_agent.core.mitigation_measure_generator import (
            default_measure_generation_rules,
            generate_measures_for_model,
        )
        data = safe_load_json(model_path)
        if not data:
            return _step(step_id, started, "FAILED",
                         errors=[f"JSON invalido: {model_path}"])
        model = _phase6_model_from_dict(data, exp_path.name)
        rules = default_measure_generation_rules()
        result = generate_measures_for_model(model, rules)

        outputs = []
        if write:
            impactos_dir.mkdir(parents=True, exist_ok=True)
            measures_path = impactos_dir / "phase6_model_with_measures.json"
            res_path = impactos_dir / "measure_generation_result.json"
            with open(measures_path, "w", encoding="utf-8") as f:
                json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)
            res_dict = {
                "generated_count": result.generated_count,
                "diagnostic_count": result.diagnostic_count,
                "prl_only_count": result.prl_only_count,
                "condition_before_submission_count": result.condition_before_submission_count,
                "warnings": result.warnings,
                "notes": result.notes,
            }
            with open(res_path, "w", encoding="utf-8") as f:
                json.dump(res_dict, f, ensure_ascii=False, indent=2)
            outputs = [str(measures_path), str(res_path)]

        return _step(
            step_id, started, "SUCCESS",
            message=f"Medidas: {result.generated_count} generadas.",
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_generate_pva(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_GENERATE_PVA"
    impactos_dir = exp_path / "impactos"
    model_path = _best_phase6_model_path(impactos_dir)

    if not model_path:
        if write:
            return _blocked(step_id, "No se encontro modelo Fase 6 en impactos/")
        return _step(step_id, started, "WARNING",
                     message="Dry-run: sin modelo disponible.",
                     warnings=["Ejecute con --write para generar modelo primero."])
    try:
        from eia_agent.core.pva_generator import (
            default_pva_generation_rules,
            generate_pva_for_model,
        )
        data = safe_load_json(model_path)
        if not data:
            return _step(step_id, started, "FAILED",
                         errors=[f"JSON invalido: {model_path}"])
        model = _phase6_model_from_dict(data, exp_path.name)
        rules = default_pva_generation_rules()
        result = generate_pva_for_model(model, rules)

        outputs = []
        if write:
            impactos_dir.mkdir(parents=True, exist_ok=True)
            pva_model_path = impactos_dir / "phase6_model_with_pva.json"
            res_path = impactos_dir / "pva_generation_result.json"
            with open(pva_model_path, "w", encoding="utf-8") as f:
                json.dump(result.model.to_dict(), f, ensure_ascii=False, indent=2)
            res_dict = {
                "generated_count": result.generated_count,
                "conditioned_count": result.conditioned_count,
                "uncovered_impact_ids": result.uncovered_impact_ids,
                "warnings": result.warnings,
                "notes": result.notes,
            }
            with open(res_path, "w", encoding="utf-8") as f:
                json.dump(res_dict, f, ensure_ascii=False, indent=2)
            outputs = [str(pva_model_path), str(res_path)]

        return _step(
            step_id, started, "SUCCESS",
            message=f"PVA: {result.generated_count} programas.",
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_validate_pva(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_VALIDATE_PVA"
    impactos_dir = exp_path / "impactos"

    # Preferir modelo con PVA; si no existe, validar lo que haya
    model_path = _best_phase6_model_path(impactos_dir)

    if not model_path:
        return _blocked(step_id, "No se encontro ningun modelo Fase 6 en impactos/")
    try:
        from eia_agent.core.pva_coverage_validator import (
            validate_pva_coverage,
            write_pva_coverage_outputs,
        )
        data = safe_load_json(model_path)
        if not data:
            return _step(step_id, started, "FAILED",
                         errors=[f"JSON invalido: {model_path}"])
        model = _phase6_model_from_dict(data, exp_path.name)
        result = validate_pva_coverage(model)

        outputs = []
        if write:
            impactos_dir.mkdir(parents=True, exist_ok=True)
            json_p, md_p = write_pva_coverage_outputs(result, impactos_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_phase6_cumulative(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "PHASE6_CUMULATIVE"
    impactos_dir = exp_path / "impactos"
    model_path = _best_phase6_model_path(impactos_dir)

    if not model_path:
        return _blocked(step_id, "No se encontro ningun modelo Fase 6 en impactos/")
    try:
        from eia_agent.core.cumulative_synergistic_section import (
            build_cumulative_synergistic_section_from_json,
            write_cumulative_synergistic_outputs,
        )
        result = build_cumulative_synergistic_section_from_json(model_path)

        outputs = []
        if write:
            json_p, md_p = write_cumulative_synergistic_outputs(result, impactos_dir)
            outputs = [str(json_p), str(md_p)]

        return _step(
            step_id, started, "SUCCESS",
            message=(
                f"C.5: {len(result.cumulative_groups)} grupos acumulativos, "
                f"{len(result.synergistic_groups)} sinergicos."
            ),
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_art45(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_ART45"
    try:
        from eia_agent.core.art45_checklist import (
            evaluate_art45_checklist_from_files,
            write_art45_checklist_outputs,
        )
        result = evaluate_art45_checklist_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_art45_checklist_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_structurally_complete() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_prudence(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_PRUDENCE"
    try:
        from eia_agent.core.prudence_validator import (
            validate_prudence_from_files,
            write_prudence_validation_outputs,
        )
        result = validate_prudence_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_prudence_validation_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_traceability(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_TRACEABILITY"
    try:
        from eia_agent.core.traceability_validator import (
            validate_traceability_from_files,
            write_traceability_validation_outputs,
        )
        result = validate_traceability_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_traceability_validation_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_block_consistency(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_BLOCK_CONSISTENCY"
    try:
        from eia_agent.core.block_consistency_validator import (
            validate_block_consistency_from_files,
            write_block_consistency_outputs,
        )
        result = validate_block_consistency_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_block_consistency_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_conesa(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_CONESA"
    try:
        from eia_agent.core.conesa_checker import (
            validate_conesa_coverage_from_files,
            write_conesa_check_outputs,
        )
        result = validate_conesa_coverage_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_conesa_check_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_diagnostic_measures(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_DIAGNOSTIC_MEASURES"
    try:
        from eia_agent.core.diagnostic_measure_validator import (
            validate_diagnostic_measures_from_files,
            write_diagnostic_measure_outputs,
        )
        result = validate_diagnostic_measures_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_diagnostic_measure_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_prl_measures(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_PRL_MEASURES"
    try:
        from eia_agent.core.prl_measure_validator import (
            validate_prl_measures_from_files,
            validate_prl_measures_markdowns_from_files,
            write_prl_measure_outputs,
            _combine_results,
        )
        model_result = validate_prl_measures_from_files(exp_path)
        try:
            md_result = validate_prl_measures_markdowns_from_files(exp_path)
            result = _combine_results(model_result, md_result)
        except Exception:
            result = model_result

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_prl_measure_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_conditional_chains(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_CONDITIONAL_CHAINS"
    try:
        from eia_agent.core.conditional_chain_validator import (
            validate_conditional_chains_from_files,
            write_conditional_chain_outputs,
        )
        result = validate_conditional_chains_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_conditional_chain_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_positive_gaps(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_POSITIVE_GAPS"
    try:
        from eia_agent.core.positive_impact_gap_validator import (
            validate_positive_gap_from_files,
            write_positive_gap_outputs,
        )
        result = validate_positive_gap_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_positive_gap_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_valid() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


def _run_audit_final(
    exp_path: Path, write: bool, mode: str
) -> TechnicalPipelineStepResult:
    started = now_iso()
    step_id = "AUDIT_FINAL"
    try:
        from eia_agent.core.final_audit_report import (
            build_final_audit_from_files,
            write_final_audit_outputs,
        )
        result = build_final_audit_from_files(exp_path)

        outputs = []
        if write:
            aud_dir = exp_path / "auditoria"
            json_p, md_p = write_final_audit_outputs(result, aud_dir)
            outputs = [str(json_p), str(md_p)]

        status = "SUCCESS" if result.is_conforme() else "WARNING"
        return _step(
            step_id, started, status,
            message=result.summary()[:300],
            output_files=outputs,
            warnings=list(result.warnings),
            notes=list(result.notes),
        )
    except Exception as exc:
        return _step(step_id, started, "FAILED",
                     errors=[_ascii_safe(str(exc))],
                     notes=[traceback.format_exc()[-500:]])


# Mapa step_id → función runner
_STEP_RUNNERS = {
    "INVENTORY_BUILD": _run_inventory_build,
    "INVENTORY_GATE": _run_inventory_gate,
    "PHASE6_ACTIONS": _run_phase6_actions,
    "PHASE6_IDENTIFY_IMPACTS": _run_phase6_identify_impacts,
    "PHASE6_ASSIGN_CONESA": _run_phase6_assign_conesa,
    "PHASE6_GENERATE_MEASURES": _run_phase6_generate_measures,
    "PHASE6_GENERATE_PVA": _run_phase6_generate_pva,
    "PHASE6_VALIDATE_PVA": _run_phase6_validate_pva,
    "AUDIT_CONDITIONAL_CHAINS": _run_audit_conditional_chains,
    "AUDIT_POSITIVE_GAPS": _run_audit_positive_gaps,
    "PHASE6_CUMULATIVE": _run_phase6_cumulative,
    "AUDIT_ART45": _run_audit_art45,
    "AUDIT_PRUDENCE": _run_audit_prudence,
    "AUDIT_TRACEABILITY": _run_audit_traceability,
    "AUDIT_BLOCK_CONSISTENCY": _run_audit_block_consistency,
    "AUDIT_CONESA": _run_audit_conesa,
    "AUDIT_DIAGNOSTIC_MEASURES": _run_audit_diagnostic_measures,
    "AUDIT_PRL_MEASURES": _run_audit_prl_measures,
    "AUDIT_FINAL": _run_audit_final,
}


# ---------------------------------------------------------------------------
# run_technical_pipeline
# ---------------------------------------------------------------------------

def run_technical_pipeline(
    expediente_path: "str | Path",
    write_outputs: bool = False,
    mode: str = "TEST",
    stop_on_error: bool = True,
) -> TechnicalPipelineResult:
    """Ejecuta el pipeline técnico completo desde inventario hasta auditoría final.

    Orquesta los 13 pasos en orden, llamando directamente a las funciones
    públicas de los módulos ya existentes.

    Args:
        expediente_path: Ruta al directorio del expediente EIA.
        write_outputs: Si True, escribe los outputs en sus rutas normales.
        mode: "TEST" o "PROD". No cambia administrative_ready.
        stop_on_error: Si True, para al primer FAILED/BLOCKED y marca los
            siguientes como SKIPPED. Si False, intenta continuar.

    Returns:
        TechnicalPipelineResult con el estado de todos los pasos.

    Raises:
        FileNotFoundError: si el directorio del expediente no existe.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(
            f"Directorio de expediente no encontrado: {exp_path}"
        )

    started_at = now_iso()
    steps: list[TechnicalPipelineStepResult] = []
    all_output_files: list[str] = []
    blocked = False

    for step_id in TECHNICAL_PIPELINE_STEPS:
        if blocked:
            steps.append(_skipped(step_id))
            continue

        runner = _STEP_RUNNERS[step_id]
        step_result = runner(exp_path, write_outputs, mode)
        steps.append(step_result)
        all_output_files.extend(step_result.output_files)

        if stop_on_error and step_result.is_blocking_failure():
            blocked = True

    # Determinar estado final
    failed = sum(1 for s in steps if s.status == "FAILED")
    blk = sum(1 for s in steps if s.status == "BLOCKED")
    skipped = sum(1 for s in steps if s.status == "SKIPPED")

    if failed + blk > 0:
        final_status = "FAILED"
    elif skipped > 0:
        final_status = "PARTIAL"
    else:
        final_status = "SUCCESS"

    # Extraer estado de auditoría final si está disponible
    final_audit_status: str | None = None
    for step in reversed(steps):
        if step.step_id == "AUDIT_FINAL" and step.is_success():
            # Buscar el JSON de auditoría para leer el status
            aud_json = safe_load_json(
                exp_path / "auditoria" / "final_audit_result.json"
            )
            if aud_json:
                final_audit_status = aud_json.get("status")
            break

    all_warnings = []
    all_errors = []
    for s in steps:
        all_warnings.extend(s.warnings)
        all_errors.extend(s.errors)

    notes = [
        "Pipeline PIPE-01+PIPE-02+PIPE-03+PIPE-04+PIPE-05: no declara aptitud administrativa.",
        f"Modo: {mode} | write_outputs={write_outputs} | stop_on_error={stop_on_error}",
        f"Pasos ejecutados: {len(steps)} | Exitosos: {sum(1 for s in steps if s.is_success())}",
    ]

    return TechnicalPipelineResult(
        expediente_id=exp_path.name,
        expediente_path=str(exp_path),
        mode=mode,
        write_outputs=write_outputs,
        started_at=started_at,
        finished_at=now_iso(),
        steps=steps,
        final_status=final_status,
        final_audit_status=final_audit_status,
        output_files=list(set(all_output_files)),
        warnings=all_warnings,
        errors=all_errors,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# build_technical_pipeline_markdown
# ---------------------------------------------------------------------------

def build_technical_pipeline_markdown(result: TechnicalPipelineResult) -> str:
    """Genera el informe del pipeline en markdown."""
    lines: list[str] = []

    lines.append("# Pipeline tecnico automatico — PIPE-01")
    lines.append("")

    # ── 1. Resumen ejecutivo ──
    lines.append("## 1. Resumen ejecutivo")
    lines.append("")
    lines.append(f"**Expediente:** {result.expediente_id}")
    lines.append(f"**Modo:** {result.mode} | write_outputs={result.write_outputs}")
    lines.append(f"**Estado final:** {result.final_status}")
    if result.final_audit_status:
        lines.append(f"**Auditoria final:** {result.final_audit_status}")
    lines.append("")
    lines.append("| Metrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Pasos totales | {len(result.steps)} |")
    lines.append(f"| Exitosos | {result.success_count()} |")
    lines.append(f"| Fallidos | {result.failed_count()} |")
    lines.append(f"| Bloqueados | {result.blocked_count()} |")
    lines.append(f"| Omitidos | {result.skipped_count()} |")
    lines.append("")

    # ── 2. Estado final ──
    lines.append("## 2. Estado final")
    lines.append("")
    status_desc = {
        "SUCCESS": "Todos los pasos completados sin errores bloqueantes.",
        "PARTIAL": "Algunos pasos se omitieron tras un error.",
        "FAILED": "Uno o mas pasos fallaron o quedaron bloqueados.",
    }
    lines.append(status_desc.get(result.final_status, result.final_status))
    lines.append("")

    # ── 3. Pasos ejecutados ──
    lines.append("## 3. Pasos ejecutados")
    lines.append("")
    lines.append("| # | Paso | Estado | Mensaje |")
    lines.append("|---|------|--------|---------|")
    for i, step in enumerate(result.steps, 1):
        msg = step.message[:60].replace("\n", " ") if step.message else ""
        lines.append(
            f"| {i} | {step.step_id} | {step.status} | {msg} |"
        )
    lines.append("")

    # ── 4. Outputs generados ──
    lines.append("## 4. Outputs generados")
    lines.append("")
    all_outputs = sorted(set(
        f for s in result.steps for f in s.output_files
    ))
    if all_outputs:
        for out in all_outputs[:30]:
            lines.append(f"- `{out}`")
        if len(all_outputs) > 30:
            lines.append(f"- ... y {len(all_outputs)-30} mas.")
    else:
        lines.append("_Sin outputs escritos (dry-run o sin --write)._")
    lines.append("")

    # ── 5. Errores ──
    lines.append("## 5. Errores")
    lines.append("")
    failed_steps = [s for s in result.steps if s.is_blocking_failure()]
    if failed_steps:
        for step in failed_steps:
            lines.append(f"**{step.step_id}** ({step.status}):")
            for err in step.errors[:3]:
                lines.append(f"  - {err[:150]}")
    else:
        lines.append("_Sin errores._")
    lines.append("")

    # ── 6. Advertencias ──
    lines.append("## 6. Advertencias")
    lines.append("")
    warn_steps = [s for s in result.steps if s.warnings]
    if warn_steps:
        for step in warn_steps[:5]:
            for w in step.warnings[:2]:
                lines.append(f"- [{step.step_id}] {w[:120]}")
    else:
        lines.append("_Sin advertencias._")
    lines.append("")

    # ── 7. Informe de auditoría ──
    lines.append("## 7. Informe final de auditoria")
    lines.append("")
    if result.final_audit_status:
        lines.append(f"**Calificacion:** {result.final_audit_status}")
        lines.append(
            "_Ver `auditoria/final_audit_result.md` para el informe completo._"
        )
    else:
        lines.append(
            "_Auditoria final no disponible. "
            "Ejecute el pipeline con --write para generarla._"
        )
    lines.append("")

    # ── 8. Advertencia de alcance ──
    lines.append("## 8. Advertencia de alcance")
    lines.append("")
    lines.append(
        "> **Este pipeline no declara el expediente apto para presentacion "
        "administrativa. Solo ejecuta y agrupa modulos tecnicos y auditorias "
        "internas. La aptitud administrativa la determina el organo competente.**"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_pipeline_outputs
# ---------------------------------------------------------------------------

def write_pipeline_outputs(
    result: TechnicalPipelineResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe el informe del pipeline en JSON y Markdown.

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "technical_pipeline_result.json"
    md_path = output_dir / "technical_pipeline_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_technical_pipeline_markdown(result))

    return json_path, md_path
