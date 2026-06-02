"""
client_form_schema -- esquema de formulario para la futura app cliente.

Convierte el intake cliente en una definicion UI/API: campos, uploads,
validaciones minimas, textos de ayuda y destinos esperados.

No ejecuta fases, no interpreta juridicamente y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.client_intake import (
    IntakeRequirement,
    build_client_intake,
)


CLIENT_FORM_SCHEMA_JSON = "cliente_form_schema.json"
CLIENT_FORM_SCHEMA_MD = "cliente_form_schema.md"

DISCLAIMER = (
    "Este esquema de formulario no declara el expediente apto para presentacion "
    "administrativa. Solo define entradas y validaciones minimas para la app cliente."
)


@dataclass
class ClientFormControl:
    """Control de UI/API para entrada del cliente."""

    control_id: str
    label: str
    control_type: str
    priority: str
    required: bool
    status: str
    target: str
    help_text: str
    validations: dict[str, Any] = field(default_factory=dict)
    accepted_formats: list[str] = field(default_factory=list)
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "label": self.label,
            "control_type": self.control_type,
            "priority": self.priority,
            "required": self.required,
            "status": self.status,
            "target": self.target,
            "help_text": self.help_text,
            "validations": dict(self.validations),
            "accepted_formats": list(self.accepted_formats),
            "evidence_count": self.evidence_count,
        }


@dataclass
class ClientFormSchema:
    """Esquema completo de formulario para UI/API cliente."""

    expediente_id: str
    controls: list[ClientFormControl] = field(default_factory=list)
    administrative_ready: bool = False
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.controls),
            "required": sum(1 for c in self.controls if c.required),
            "uploads": sum(1 for c in self.controls if c.control_type == "file_upload"),
            "fields": sum(1 for c in self.controls if c.control_type != "file_upload"),
            "pending_required": sum(1 for c in self.controls if c.required and c.status == "PENDIENTE"),
            "high_priority": sum(1 for c in self.controls if c.priority == "ALTA"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "administrative_ready": False,
            "counts": self.counts(),
            "controls": [control.to_dict() for control in self.controls],
            "warnings": list(self.warnings),
            "source_files": list(self.source_files),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        counts = self.counts()
        return "\n".join([
            f"--- Form schema cliente [{self.expediente_id}] ---",
            f"Controles    : {counts['total']} ({counts['fields']} campos, {counts['uploads']} uploads)",
            f"Obligatorios : {counts['required']} (pendientes: {counts['pending_required']})",
            f"Prioridad ALTA: {counts['high_priority']}",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _format_extensions(formats: list[str]) -> list[str]:
    normalized = []
    for fmt in formats:
        value = str(fmt).strip().upper()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _control_type(req: IntakeRequirement) -> str:
    if req.kind in {"DOCUMENT", "MEDIA", "CARTOGRAPHY"}:
        return "file_upload"
    if req.requirement_id == "DAT-002":
        return "coordinates"
    if req.requirement_id == "DAT-004":
        return "operation_selector"
    return "text"


def _validations(req: IntakeRequirement) -> dict[str, Any]:
    base: dict[str, Any] = {
        "required": req.required,
        "evidence_state": "DECLARADO",
        "blocks_final_submission": req.required and req.priority == "ALTA",
    }
    if req.kind in {"DOCUMENT", "MEDIA", "CARTOGRAPHY"}:
        base.update({
            "max_files": 25 if req.kind == "MEDIA" else 10,
            "max_file_mb": 25 if req.kind == "MEDIA" else 50,
            "accepted_formats": _format_extensions(req.accepted_formats),
        })
    if req.requirement_id == "DAT-002":
        base.update({
            "coordinate_systems": ["EPSG:4326", "EPSG:32628"],
            "requires_wgs84": True,
            "requires_regcan95_utm28": False,
        })
    if req.requirement_id == "DAT-003":
        base.update({
            "min_length": 14,
            "max_length": 20,
            "pattern_hint": "Referencia catastral oficial si consta.",
        })
    if req.requirement_id == "DAT-004":
        base.update({
            "legal_codes": ["R12", "R13", "D15"],
            "requires_included_excluded_operations": True,
        })
    return base


def _control_from_requirement(req: IntakeRequirement) -> ClientFormControl:
    return ClientFormControl(
        control_id=req.requirement_id,
        label=req.title,
        control_type=_control_type(req),
        priority=req.priority,
        required=req.required,
        status=req.status,
        target=req.target,
        help_text=req.help_text,
        validations=_validations(req),
        accepted_formats=_format_extensions(req.accepted_formats),
        evidence_count=len(req.evidence),
    )


def build_client_form_schema(expediente_path: str | Path) -> ClientFormSchema:
    """Construye el esquema de formulario desde el intake cliente."""
    intake = build_client_intake(expediente_path)
    controls = [_control_from_requirement(req) for req in intake.requirements]
    return ClientFormSchema(
        expediente_id=intake.expediente_id,
        controls=controls,
        administrative_ready=False,
        warnings=list(intake.warnings),
        source_files=list(intake.source_files),
    )


def build_client_form_schema_markdown(schema: ClientFormSchema) -> str:
    """Renderiza el esquema de formulario en Markdown."""
    counts = schema.counts()
    lines = [
        f"# Form schema cliente - {schema.expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Resumen",
        "",
        f"- Controles: {counts['total']}",
        f"- Campos: {counts['fields']}",
        f"- Uploads: {counts['uploads']}",
        f"- Obligatorios pendientes: {counts['pending_required']}",
        "- administrative_ready: false",
        "",
        "## Controles",
        "",
        "| ID | Tipo | Prioridad | Obligatorio | Estado | Destino |",
        "|----|------|-----------|-------------|--------|---------|",
    ]
    for control in schema.controls:
        lines.append(
            f"| {control.control_id} | {control.control_type} | {control.priority} | "
            f"{str(control.required).lower()} | {control.status} | `{control.target}` |"
        )
    lines.extend(["", "## Validaciones", ""])
    for control in schema.controls:
        lines.append(f"### {control.control_id} - {control.label}")
        lines.append("")
        for key, value in control.validations.items():
            lines.append(f"- {key}: {value}")
        if control.accepted_formats:
            lines.append(f"- formatos: {', '.join(control.accepted_formats)}")
        lines.append("")
    if schema.warnings:
        lines.extend(["## Avisos", ""])
        for warning in schema.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.extend(["---", "", f"*{DISCLAIMER}*"])
    return "\n".join(lines)


def write_client_form_schema_outputs(
    schema: ClientFormSchema,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown del esquema en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLIENT_FORM_SCHEMA_JSON
    md_path = out_dir / CLIENT_FORM_SCHEMA_MD
    json_path.write_text(json.dumps(schema.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_form_schema_markdown(schema), encoding="utf-8")
    return json_path, md_path
