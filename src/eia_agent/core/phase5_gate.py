"""
phase5_gate -- F5-01
Gate de cierre de Fase 5 / Inventario ambiental offline.

Evalúa si el inventario ambiental cumple los requisitos mínimos para avanzar
a Fase 6 (valoración de impactos). Produce un resultado estructurado con
decisión, issues y un informe markdown.

No usa IA. No consulta fuentes externas. No valora impactos. Offline-only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
)

# ---------------------------------------------------------------------------
# Constantes de decisión
# ---------------------------------------------------------------------------

GATE_DECISIONS: frozenset[str] = frozenset({
    "APTO_FASE6",             # todos los factores listos, sin gaps ALTA ni bloqueantes
    "APTO_FASE6_CON_CAUTELAS",  # sin errores estructurales, pero gaps o no-ready
    "NO_APTO_FASE6",          # errores estructurales o de coherencia
})

ISSUE_SEVERITIES: frozenset[str] = frozenset({"ERROR", "WARNING", "INFO"})

_BLOCKING_SEMAPHORES: frozenset[str] = frozenset({"ROJO", "NO_CONSTA"})

# ---------------------------------------------------------------------------
# Phase5GateIssue
# ---------------------------------------------------------------------------

@dataclass
class Phase5GateIssue:
    """Un issue detectado durante la evaluación del gate de Fase 5.

    severity: ERROR (bloquea gate), WARNING (cautela), INFO (informativo).
    code: código corto identificador (p.ej. MISSING_FACTOR, READY_ROJO).
    factor_id: factor afectado, o None si es issue a nivel de resumen.
    message: descripción legible del problema.
    recommendation: acción sugerida para resolver el issue.
    """

    severity: str
    code: str
    message: str
    recommendation: str = ""
    factor_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.severity not in ISSUE_SEVERITIES:
            raise ValueError(
                f"Phase5GateIssue.severity inválido: {self.severity!r}. "
                f"Valores válidos: {sorted(ISSUE_SEVERITIES)}"
            )

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "factor_id": self.factor_id,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        fid = f"[{self.factor_id}] " if self.factor_id else ""
        return f"{self.severity} {self.code}: {fid}{self.message}"


# ---------------------------------------------------------------------------
# Phase5GateResult
# ---------------------------------------------------------------------------

@dataclass
class Phase5GateResult:
    """Resultado de la evaluación del gate de Fase 5.

    decision:
        APTO_FASE6              — sin errores, todos listos, sin gaps ALTA
        APTO_FASE6_CON_CAUTELAS — sin errores estructurales pero cautelas
        NO_APTO_FASE6           — errores que impiden avanzar

    administrative_ready: siempre False. El gate ambiental no reemplaza la
    tramitación administrativa (presentación al órgano ambiental).
    """

    expediente_id: str
    decision: str
    total_factors: int
    ready_count: int
    not_ready_factors: list[str] = field(default_factory=list)
    critical_gaps: list[dict] = field(default_factory=list)
    red_or_no_consta_factors: list[str] = field(default_factory=list)
    issues: list[Phase5GateIssue] = field(default_factory=list)
    administrative_ready: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_blocked(self) -> bool:
        return self.decision == "NO_APTO_FASE6"

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "decision": self.decision,
            "total_factors": self.total_factors,
            "ready_count": self.ready_count,
            "not_ready_factors": list(self.not_ready_factors),
            "critical_gaps": list(self.critical_gaps),
            "red_or_no_consta_factors": list(self.red_or_no_consta_factors),
            "issues": [i.to_dict() for i in self.issues],
            "administrative_ready": self.administrative_ready,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_blocked": self.is_blocked(),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        decision_labels = {
            "APTO_FASE6": "APTO FASE 6",
            "APTO_FASE6_CON_CAUTELAS": "APTO FASE 6 CON CAUTELAS",
            "NO_APTO_FASE6": "NO APTO — BLOQUEADO",
        }
        label = decision_labels.get(self.decision, self.decision)
        lines = [
            f"Gate Fase 5 — {self.expediente_id}",
            f"  Decisión       : {label}",
            f"  Factores       : {self.total_factors}/16",
            f"  Listos F6      : {self.ready_count}/{self.total_factors}",
            f"  Errors         : {self.error_count()}",
            f"  Warnings       : {self.warning_count()}",
            f"  Gaps ALTA      : {len(self.critical_gaps)}",
            f"  ROJO/NO_CONSTA : {len(self.red_or_no_consta_factors)}",
            f"  Admin. listo   : NO (tramitación independiente)",
        ]
        if self.error_count() > 0:
            lines.append("")
            lines.append("  ERRORES:")
            for iss in self.issues:
                if iss.severity == "ERROR":
                    lines.append(f"    • {iss.summary()}")
        if self.warning_count() > 0:
            lines.append("")
            lines.append("  AVISOS:")
            for iss in self.issues:
                if iss.severity == "WARNING":
                    lines.append(f"    • {iss.summary()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# evaluate_phase5_gate
# ---------------------------------------------------------------------------

def evaluate_phase5_gate(
    summary: InventorySummary,
    test_mode: bool = True,
) -> Phase5GateResult:
    """Evalúa el gate de cierre de Fase 5 sobre un InventorySummary.

    Reglas aplicadas (en orden):

    1. Estructura del resumen:
       - Exactamente 16 factores → ERROR si no
       - Sin IDs duplicados → ERROR si hay
       - IDs en FI-001...FI-016 → ERROR si no

    2. Por factor:
       - evidence_status vacío o no válido → ERROR
       - field_mode vacío o no válido → ERROR
       - inventory_semaphore vacío o no válido → ERROR
       - description vacía → WARNING
       - data_sources vacío → WARNING
       - ready=True con semáforo ROJO o NO_CONSTA → ERROR
       - ready=True con gap ALTA PENDIENTE → ERROR

    3. Por gap:
       - criticality o resolution_mode ausente/inválido → ERROR
       - description vacía → WARNING
       - ALTA+PENDIENTE → registrar en critical_gaps

    4. Decisión:
       - error_count > 0 → NO_APTO_FASE6
       - sin errores pero hay critical_gaps o factores no-ready → APTO_FASE6_CON_CAUTELAS
       - sin errores, todos ready, sin gaps ALTA, ningún ROJO/NO_CONSTA → APTO_FASE6

    test_mode no altera la lógica de este gate (diferente al gate de fases 2-4
    donde test_mode relaja condiciones). El gate de Fase 5 es siempre riguroso
    porque valida coherencia interna del inventario ya construido.
    """
    issues: list[Phase5GateIssue] = []
    critical_gaps: list[dict] = []
    red_or_no_consta: list[str] = []
    not_ready: list[str] = []
    warnings: list[str] = []
    notes: list[str] = [f"F5-01 gate evaluado (test_mode={test_mode})"]

    # --- 1. Estructura del resumen ---
    factor_ids = [f.factor_id for f in summary.factors]
    n = len(factor_ids)

    if n != 16:
        issues.append(Phase5GateIssue(
            severity="ERROR",
            code="WRONG_FACTOR_COUNT",
            message=f"Se esperan 16 factores, hay {n}.",
            recommendation="Regenerar el inventario con inventory-build para obtener los 16 factores canónicos.",
        ))

    seen_ids: set[str] = set()
    for fid in factor_ids:
        if fid in seen_ids:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="DUPLICATE_FACTOR",
                factor_id=fid,
                message=f"Factor duplicado: {fid}.",
                recommendation=f"Eliminar la entrada duplicada de {fid} del inventario.",
            ))
        seen_ids.add(fid)
        if fid not in FACTOR_NAMES:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="INVALID_FACTOR_ID",
                factor_id=fid,
                message=f"factor_id desconocido: {fid!r}. No pertenece a FI-001...FI-016.",
                recommendation="Corregir el factor_id para que coincida con un ID canónico.",
            ))

    missing = [fid for fid in sorted(FACTOR_NAMES.keys()) if fid not in seen_ids]
    for fid in missing:
        issues.append(Phase5GateIssue(
            severity="ERROR",
            code="MISSING_FACTOR",
            factor_id=fid,
            message=f"Factor canónico ausente: {fid} ({FACTOR_NAMES[fid]}).",
            recommendation=f"Regenerar el inventario para incluir {fid}.",
        ))

    # --- 2. Por factor ---
    from eia_agent.core.inventory_model import (
        EVIDENCE_STATUS_VALUES,
        FIELD_MODES,
        INVENTORY_SEMAPHORES,
        GAP_CRITICALITIES,
        GAP_RESOLUTION_MODES,
        GAP_STATUSES,
    )

    for factor in summary.factors:
        fid = factor.factor_id

        if not factor.evidence_status or factor.evidence_status not in EVIDENCE_STATUS_VALUES:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="INVALID_EVIDENCE_STATUS",
                factor_id=fid,
                message=f"evidence_status inválido o vacío: {factor.evidence_status!r}.",
                recommendation="Asignar un evidence_status válido (PENDIENTE, ESTIMADO, DECLARADO, etc.).",
            ))

        if not factor.field_mode or factor.field_mode not in FIELD_MODES:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="INVALID_FIELD_MODE",
                factor_id=fid,
                message=f"field_mode inválido o vacío: {factor.field_mode!r}.",
                recommendation="Asignar un field_mode válido (GABINETE_SUFICIENTE, CAMPO_RECOMENDADO, etc.).",
            ))

        if not factor.inventory_semaphore or factor.inventory_semaphore not in INVENTORY_SEMAPHORES:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="INVALID_SEMAPHORE",
                factor_id=fid,
                message=f"inventory_semaphore inválido o vacío: {factor.inventory_semaphore!r}.",
                recommendation="Asignar un semáforo válido (VERDE, AMARILLO, ROJO_AMARILLO, etc.).",
            ))

        if not factor.description:
            issues.append(Phase5GateIssue(
                severity="WARNING",
                code="EMPTY_DESCRIPTION",
                factor_id=fid,
                message=f"description vacía para {fid}.",
                recommendation="Añadir una descripción del estado de conocimiento del factor.",
            ))

        if not factor.data_sources:
            issues.append(Phase5GateIssue(
                severity="WARNING",
                code="NO_DATA_SOURCES",
                factor_id=fid,
                message=f"data_sources vacío para {fid}.",
                recommendation="Indicar al menos una fuente de datos o documentación consultada.",
            ))

        if factor.ready_for_impact_assessment and factor.inventory_semaphore in _BLOCKING_SEMAPHORES:
            issues.append(Phase5GateIssue(
                severity="ERROR",
                code="READY_WITH_BLOCKING_SEMAPHORE",
                factor_id=fid,
                message=(
                    f"ready_for_impact_assessment=True con semáforo bloqueante "
                    f"{factor.inventory_semaphore!r}."
                ),
                recommendation="Un factor con semáforo ROJO o NO_CONSTA no puede estar listo para Fase 6.",
            ))

        # gaps ALTA pendientes con ready=True
        for gap in factor.gaps:
            if (
                factor.ready_for_impact_assessment
                and gap.criticality == "ALTA"
                and gap.status == "PENDIENTE"
            ):
                issues.append(Phase5GateIssue(
                    severity="ERROR",
                    code="READY_WITH_ALTA_GAP",
                    factor_id=fid,
                    message=(
                        f"ready_for_impact_assessment=True pero {gap.gap_id} "
                        f"tiene criticidad ALTA y estado PENDIENTE."
                    ),
                    recommendation=f"Resolver {gap.gap_id} antes de marcar {fid} como listo.",
                ))

        # 3. Por gap (validación de estructura)
        for gap in factor.gaps:
            if not gap.criticality or gap.criticality not in GAP_CRITICALITIES:
                issues.append(Phase5GateIssue(
                    severity="ERROR",
                    code="INVALID_GAP_CRITICALITY",
                    factor_id=fid,
                    message=f"Gap {gap.gap_id}: criticality inválida {gap.criticality!r}.",
                    recommendation="Asignar criticidad válida (ALTA, MEDIA, BAJA).",
                ))

            if not gap.resolution_mode or gap.resolution_mode not in GAP_RESOLUTION_MODES:
                issues.append(Phase5GateIssue(
                    severity="ERROR",
                    code="INVALID_GAP_RESOLUTION_MODE",
                    factor_id=fid,
                    message=f"Gap {gap.gap_id}: resolution_mode inválido {gap.resolution_mode!r}.",
                    recommendation="Asignar resolution_mode válido (GABINETE, CAMPO, IRRESOLUBLE_OFFLINE).",
                ))

            if not gap.description:
                issues.append(Phase5GateIssue(
                    severity="WARNING",
                    code="EMPTY_GAP_DESCRIPTION",
                    factor_id=fid,
                    message=f"Gap {gap.gap_id}: description vacía.",
                    recommendation="Añadir una descripción del gap.",
                ))

            if gap.criticality == "ALTA" and gap.status == "PENDIENTE":
                critical_gaps.append({
                    "gap_id": gap.gap_id,
                    "factor_id": fid,
                    "description": gap.description,
                    "resolution_mode": gap.resolution_mode,
                })

        # Acumular factores no listos y bloqueantes
        if not factor.ready_for_impact_assessment:
            not_ready.append(fid)
        if factor.inventory_semaphore in _BLOCKING_SEMAPHORES:
            red_or_no_consta.append(fid)

    # --- 4. Decisión ---
    error_count = sum(1 for i in issues if i.severity == "ERROR")

    if error_count > 0:
        decision = "NO_APTO_FASE6"
    elif critical_gaps or not_ready:
        decision = "APTO_FASE6_CON_CAUTELAS"
    else:
        decision = "APTO_FASE6"

    # Nota informativa sobre administrative_ready
    notes.append(
        "administrative_ready=False: el gate ambiental no reemplaza la presentación "
        "del Documento Ambiental al órgano ambiental competente."
    )

    if decision == "APTO_FASE6_CON_CAUTELAS":
        warnings.append(
            f"Inventario con {len(not_ready)} factor(es) no listos y "
            f"{len(critical_gaps)} gap(s) ALTA pendientes. "
            "Avanzar con cautela; resolver gaps antes de Fase 6 definitiva."
        )
    elif decision == "APTO_FASE6":
        notes.append("Todos los factores están listos para Fase 6. Sin gaps ALTA pendientes.")

    return Phase5GateResult(
        expediente_id=summary.expediente_id,
        decision=decision,
        total_factors=len(summary.factors),
        ready_count=sum(1 for f in summary.factors if f.ready_for_impact_assessment),
        not_ready_factors=not_ready,
        critical_gaps=critical_gaps,
        red_or_no_consta_factors=red_or_no_consta,
        issues=issues,
        administrative_ready=False,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Reconstrucción desde JSON
# ---------------------------------------------------------------------------

def _gap_from_dict(d: dict) -> InventoryGap:
    return InventoryGap(
        gap_id=d.get("gap_id", ""),
        factor_id=d.get("factor_id", ""),
        field=d.get("field", ""),
        description=d.get("description", ""),
        criticality=d.get("criticality", "MEDIA"),
        resolution_mode=d.get("resolution_mode", "GABINETE"),
        status=d.get("status", "PENDIENTE"),
    )


def _factor_from_dict(d: dict) -> FactorInventory:
    gaps = [_gap_from_dict(g) for g in d.get("gaps", [])]
    return FactorInventory(
        factor_id=d.get("factor_id", ""),
        factor_name=d.get("factor_name"),
        factor_type=d.get("factor_type"),
        description=d.get("description", ""),
        data_sources=list(d.get("data_sources", [])),
        evidence_status=d.get("evidence_status", "PENDIENTE"),
        field_mode=d.get("field_mode", "NO_CONSTA"),
        field_mode_justification=d.get("field_mode_justification", ""),
        inventory_semaphore=d.get("inventory_semaphore", "NO_CONSTA"),
        semaphore_justification=d.get("semaphore_justification", ""),
        gaps=gaps,
        ready_for_impact_assessment=bool(d.get("ready_for_impact_assessment", False)),
        warnings=list(d.get("warnings", [])),
        notes=list(d.get("notes", [])),
    )


def _summary_from_dict(d: dict) -> InventorySummary:
    factors = [_factor_from_dict(f) for f in d.get("factors", [])]
    return InventorySummary(
        expediente_id=d.get("expediente_id", "DESCONOCIDO"),
        factors=factors,
        warnings=list(d.get("warnings", [])),
        notes=list(d.get("notes", [])),
    )


def evaluate_phase5_gate_from_inventory_json(
    path: str | Path,
    test_mode: bool = True,
) -> Phase5GateResult:
    """Carga un inventory_summary.json y evalúa el gate de Fase 5.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON no es válido o no contiene 'factors'.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró el archivo de inventario: {p}")

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {p}: {exc}") from exc

    if "factors" not in data:
        raise ValueError(
            f"El archivo {p} no contiene la clave 'factors'. "
            "¿Es un inventory_summary.json válido?"
        )

    summary = _summary_from_dict(data)
    return evaluate_phase5_gate(summary, test_mode=test_mode)


# ---------------------------------------------------------------------------
# build_phase5_gate_markdown
# ---------------------------------------------------------------------------

def build_phase5_gate_markdown(result: Phase5GateResult) -> str:
    """Genera el informe markdown del gate de Fase 5."""
    decision_labels = {
        "APTO_FASE6": "APTO PARA FASE 6",
        "APTO_FASE6_CON_CAUTELAS": "APTO PARA FASE 6 CON CAUTELAS",
        "NO_APTO_FASE6": "NO APTO — BLOQUEADO",
    }
    label = decision_labels.get(result.decision, result.decision)

    lines: list[str] = [
        f"# Gate Fase 5 — {result.expediente_id}",
        "",
        f"**Decisión**: {label}  ",
        f"**Factores evaluados**: {result.total_factors}/16  ",
        f"**Listos para Fase 6**: {result.ready_count}/{result.total_factors}  ",
        f"**Errors**: {result.error_count()} | **Warnings**: {result.warning_count()} | **Info**: {result.info_count()}  ",
        f"**Gaps ALTA pendientes**: {len(result.critical_gaps)}  ",
        f"**Factores ROJO/NO_CONSTA**: {len(result.red_or_no_consta_factors)}  ",
        f"**Administrativamente listo**: NO (tramitación independiente)  ",
        "",
    ]

    # Errores
    errors = [i for i in result.issues if i.severity == "ERROR"]
    if errors:
        lines += ["## Errores (bloquean gate)", ""]
        for iss in errors:
            fid_str = f" `{iss.factor_id}`" if iss.factor_id else ""
            lines.append(f"- **{iss.code}**{fid_str}: {iss.message}")
            if iss.recommendation:
                lines.append(f"  *Recomendación*: {iss.recommendation}")
        lines.append("")

    # Warnings
    warnlist = [i for i in result.issues if i.severity == "WARNING"]
    if warnlist:
        lines += ["## Avisos", ""]
        for iss in warnlist:
            fid_str = f" `{iss.factor_id}`" if iss.factor_id else ""
            lines.append(f"- **{iss.code}**{fid_str}: {iss.message}")
            if iss.recommendation:
                lines.append(f"  *Recomendación*: {iss.recommendation}")
        lines.append("")

    # Gaps ALTA
    if result.critical_gaps:
        lines += ["## Gaps ALTA pendientes", ""]
        lines.append("| Gap ID | Factor | Resolución | Descripción |")
        lines.append("|--------|--------|------------|-------------|")
        for g in result.critical_gaps:
            desc = g.get("description", "")
            preview = desc[:70] + ("..." if len(desc) > 70 else "")
            lines.append(
                f"| {g.get('gap_id', '?')} | {g.get('factor_id', '?')} "
                f"| {g.get('resolution_mode', '?')} | {preview} |"
            )
        lines.append("")

    # Factores no listos
    if result.not_ready_factors:
        lines += ["## Factores no listos para Fase 6", ""]
        from eia_agent.core.inventory_model import FACTOR_NAMES as _FN
        for fid in result.not_ready_factors:
            name = _FN.get(fid, fid)
            lines.append(f"- `{fid}` {name}")
        lines.append("")

    # Factores ROJO / NO_CONSTA
    if result.red_or_no_consta_factors:
        lines += ["## Factores con semáforo ROJO o NO_CONSTA", ""]
        from eia_agent.core.inventory_model import FACTOR_NAMES as _FN
        for fid in result.red_or_no_consta_factors:
            name = _FN.get(fid, fid)
            lines.append(f"- `{fid}` {name}")
        lines.append("")

    # Notas
    if result.notes:
        lines += ["## Notas", ""]
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generado por EIA-Agent v2.1 — F5-01 — Gate de cierre de Fase 5*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_phase5_gate_outputs
# ---------------------------------------------------------------------------

def write_phase5_gate_outputs(
    result: Phase5GateResult,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Escribe phase5_gate_result.json y phase5_gate_result.md en output_dir.

    Returns:
        (json_path, md_path)

    Raises:
        OSError: si no se puede escribir en output_dir.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "phase5_gate_result.json"
    md_path = out / "phase5_gate_result.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_path.write_text(
        build_phase5_gate_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
