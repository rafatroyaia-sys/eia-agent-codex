"""
client_portal -- paquete unico para la futura experiencia cliente.

Compone intake + dashboard en una vista guiada para UI/API:
  - que debe aportar el promotor;
  - si puede iniciarse el procesamiento;
  - que acciones siguen despues;
  - que artefactos estan disponibles.

No ejecuta fases, no interpreta juridicamente y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.client_dashboard import (
    ClientDashboard,
    build_client_dashboard,
)
from eia_agent.core.client_intake import (
    ClientIntake,
    IntakeRequirement,
    build_client_intake,
)


CLIENT_PORTAL_JSON = "cliente_portal.json"
CLIENT_PORTAL_MD = "cliente_portal.md"

DISCLAIMER = (
    "Este portal no declara el expediente apto para presentacion administrativa. "
    "Solo organiza el flujo cliente y los outputs existentes."
)


@dataclass
class PortalUploadSection:
    """Bloque de entrada que la app cliente puede representar como formulario o subida."""

    section_id: str
    title: str
    kind: str
    priority: str
    required: bool
    status: str
    target: str
    help_text: str
    accepted_formats: list[str] = field(default_factory=list)
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "kind": self.kind,
            "priority": self.priority,
            "required": self.required,
            "status": self.status,
            "target": self.target,
            "help_text": self.help_text,
            "accepted_formats": list(self.accepted_formats),
            "evidence_count": self.evidence_count,
        }


@dataclass
class ClientPortal:
    """Contrato consolidado para el portal cliente."""

    expediente_id: str
    status: str
    headline: str
    primary_action: str
    administrative_ready: bool = False
    intake: dict[str, Any] = field(default_factory=dict)
    dashboard: dict[str, Any] = field(default_factory=dict)
    upload_sections: list[PortalUploadSection] = field(default_factory=list)
    next_steps: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "headline": self.headline,
            "primary_action": self.primary_action,
            "administrative_ready": False,
            "intake": dict(self.intake),
            "dashboard": dict(self.dashboard),
            "upload_sections": [s.to_dict() for s in self.upload_sections],
            "next_steps": list(self.next_steps),
            "artifacts": list(self.artifacts),
            "warnings": list(self.warnings),
            "source_files": list(self.source_files),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        intake_counts = self.intake.get("counts", {})
        available = sum(1 for artifact in self.artifacts if artifact.get("available"))
        return "\n".join([
            f"--- Portal cliente [{self.expediente_id}] ---",
            f"Estado       : {self.status}",
            f"Lectura      : {self.headline}",
            f"Accion       : {self.primary_action}",
            f"Intake       : {intake_counts.get('complete', 0)}/{intake_counts.get('total', 0)} completos",
            f"Artefactos   : {available}/{len(self.artifacts)} disponibles",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _section_from_requirement(req: IntakeRequirement) -> PortalUploadSection:
    return PortalUploadSection(
        section_id=req.requirement_id,
        title=req.title,
        kind=req.kind,
        priority=req.priority,
        required=req.required,
        status=req.status,
        target=req.target,
        help_text=req.help_text,
        accepted_formats=list(req.accepted_formats),
        evidence_count=len(req.evidence),
    )


def _status_from_intake_and_dashboard(intake: ClientIntake, dashboard: ClientDashboard) -> tuple[str, str, str]:
    counts = intake.counts()
    if counts["required_pending"] > 0:
        missing = counts["required_pending"]
        return (
            "ESPERANDO_DOCUMENTACION_CLIENTE",
            f"Faltan {missing} requisito(s) obligatorio(s) para iniciar el procesamiento.",
            "Completar primero los datos y documentos obligatorios del intake.",
        )
    if not intake.is_ready_for_initial_processing():
        return (
            "INTAKE_INCOMPLETO",
            "El intake aun contiene pendientes que deben revisarse antes de avanzar.",
            "Revisar los requisitos pendientes o parciales del intake.",
        )
    if dashboard.status in {"SIN_PLAN_ACCION", "SIN_DATOS"}:
        return (
            "LISTO_PARA_PROCESAMIENTO_INICIAL",
            "El intake permite iniciar procesamiento, pero aun no hay estado tecnico consolidado.",
            "Ejecutar el flujo tecnico del Documento Ambiental.",
        )
    if "BLOQUEADO" in dashboard.status:
        return (
            dashboard.status,
            dashboard.headline,
            dashboard.next_action,
        )
    return (
        dashboard.status,
        dashboard.headline,
        dashboard.next_action,
    )


def _next_steps(intake: ClientIntake, dashboard: ClientDashboard) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    pending_required = [
        r for r in intake.requirements
        if r.required and r.status == "PENDIENTE"
    ]
    partial_high = [
        r for r in intake.requirements
        if r.priority == "ALTA" and r.status == "PARCIAL"
    ]
    if pending_required:
        steps.append({
            "order": 1,
            "audience": "PROMOTOR",
            "priority": "ALTA",
            "title": "Completar documentacion obligatoria de entrada",
            "detail": ", ".join(r.title for r in pending_required[:6]),
            "action_refs": [r.requirement_id for r in pending_required],
        })
    if partial_high:
        steps.append({
            "order": len(steps) + 1,
            "audience": "PROMOTOR",
            "priority": "ALTA",
            "title": "Cerrar requisitos ALTA que figuran como parciales",
            "detail": ", ".join(r.title for r in partial_high[:6]),
            "action_refs": [r.requirement_id for r in partial_high],
        })
    closing_route = dashboard.action_plan.get("closing_route", [])
    for route_step in closing_route[:4]:
        steps.append({
            "order": len(steps) + 1,
            "audience": route_step.get("audience", "EQUIPO_TECNICO"),
            "priority": route_step.get("priority", "MEDIA"),
            "title": route_step.get("title", "Revisar paso de cierre"),
            "detail": route_step.get("description", ""),
            "action_refs": route_step.get("action_refs", []),
        })
    if not steps:
        steps.append({
            "order": 1,
            "audience": "EQUIPO_TECNICO",
            "priority": "MEDIA",
            "title": "Revisar outputs y preparar siguiente fase",
            "detail": "No hay pasos prioritarios calculados en los outputs disponibles.",
            "action_refs": [],
        })
    return steps


def _source_files(intake: ClientIntake, dashboard: ClientDashboard) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for source in list(intake.source_files) + list(dashboard.source_files):
        if source not in seen:
            result.append(source)
            seen.add(source)
    return result


def build_client_portal(expediente_path: str | Path) -> ClientPortal:
    """Construye el paquete unico del portal cliente desde outputs existentes."""
    exp = Path(expediente_path)
    intake = build_client_intake(exp)
    dashboard = build_client_dashboard(exp)
    status, headline, primary_action = _status_from_intake_and_dashboard(intake, dashboard)

    upload_sections = [_section_from_requirement(req) for req in intake.requirements]
    artifacts = [artifact.to_dict() for artifact in dashboard.artifacts]
    warnings = list(dict.fromkeys(list(intake.warnings) + list(dashboard.warnings)))

    return ClientPortal(
        expediente_id=exp.name,
        status=status,
        headline=headline,
        primary_action=primary_action,
        administrative_ready=False,
        intake={
            "ready_for_initial_processing": intake.is_ready_for_initial_processing(),
            "counts": intake.counts(),
            "warnings": list(intake.warnings),
        },
        dashboard={
            "status": dashboard.status,
            "headline": dashboard.headline,
            "next_action": dashboard.next_action,
            "counts": dict(dashboard.counts),
            "warnings": list(dashboard.warnings),
        },
        upload_sections=upload_sections,
        next_steps=_next_steps(intake, dashboard),
        artifacts=artifacts,
        warnings=warnings,
        source_files=_source_files(intake, dashboard),
    )


def build_client_portal_markdown(portal: ClientPortal) -> str:
    """Renderiza el portal en Markdown para revision de producto/equipo."""
    lines = [
        f"# Portal cliente - {portal.expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Estado",
        "",
        f"- Estado: {portal.status}",
        f"- Lectura: {portal.headline}",
        f"- Accion principal: {portal.primary_action}",
        "- administrative_ready: false",
        "",
        "## Entrada cliente",
        "",
        "| ID | Prioridad | Tipo | Estado | Requisito | Destino |",
        "|----|-----------|------|--------|-----------|---------|",
    ]
    for section in portal.upload_sections:
        lines.append(
            f"| {section.section_id} | {section.priority} | {section.kind} | "
            f"{section.status} | {section.title} | `{section.target}` |"
        )
    lines.extend(["", "## Siguientes pasos", ""])
    for step in portal.next_steps:
        lines.append(
            f"{step.get('order')}. [{step.get('priority')}] "
            f"{step.get('title')} ({step.get('audience')})"
        )
        if step.get("detail"):
            lines.append(f"   - {step.get('detail')}")
    lines.extend(["", "## Artefactos", ""])
    for artifact in portal.artifacts:
        status = "disponible" if artifact.get("available") else "pendiente"
        lines.append(f"- {artifact.get('artifact_id')}: {status} - `{artifact.get('path')}`")
    if portal.warnings:
        lines.extend(["", "## Avisos", ""])
        for warning in portal.warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "---", "", f"*{DISCLAIMER}*"])
    return "\n".join(lines)


def write_client_portal_outputs(
    portal: ClientPortal,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown del portal en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLIENT_PORTAL_JSON
    md_path = out_dir / CLIENT_PORTAL_MD
    json_path.write_text(json.dumps(portal.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_portal_markdown(portal), encoding="utf-8")
    return json_path, md_path
