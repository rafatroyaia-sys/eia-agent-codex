"""
client_submission_validator -- validacion ligera de entrega cliente.

Revisa la documentacion y campos aportados contra el form schema cliente:
faltantes obligatorios, formatos no aceptados y coordenadas basicas.

No ejecuta fases, no interpreta juridicamente y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.client_form_schema import build_client_form_schema
from eia_agent.core.client_intake import IntakeRequirement, build_client_intake


CLIENT_SUBMISSION_VALIDATION_JSON = "cliente_submission_validation.json"
CLIENT_SUBMISSION_VALIDATION_MD = "cliente_submission_validation.md"

DISCLAIMER = (
    "Esta validacion no declara el expediente apto para presentacion administrativa. "
    "Solo revisa si la entrega cliente puede pasar a ingesta/procesamiento inicial."
)


@dataclass
class SubmissionIssue:
    """Incidencia de entrada cliente."""

    issue_id: str
    control_id: str
    severity: str  # ERROR | WARNING | INFO
    title: str
    message: str
    expected_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "control_id": self.control_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "expected_action": self.expected_action,
        }


@dataclass
class ClientSubmissionValidation:
    """Resultado de validacion de entrega cliente."""

    expediente_id: str
    status: str
    can_start_initial_processing: bool
    administrative_ready: bool = False
    issues: list[SubmissionIssue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "can_start_initial_processing": self.can_start_initial_processing,
            "administrative_ready": False,
            "counts": dict(self.counts),
            "issues": [issue.to_dict() for issue in self.issues],
            "warnings": list(self.warnings),
            "source_files": list(self.source_files),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        return "\n".join([
            f"--- Validacion entrega cliente [{self.expediente_id}] ---",
            f"Estado       : {self.status}",
            f"Errores      : {self.counts.get('errors', 0)}",
            f"Advertencias : {self.counts.get('warnings', 0)}",
            f"Inicio       : {self.can_start_initial_processing}",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _phase2_scope(exp: Path, source_files: list[str]) -> dict[str, Any]:
    for rel_path in (
        "control_interno/phase2_result.json",
        "fase2/phase2_result.json",
        "control_interno/object_scope.json",
        "fase2/object_scope.json",
    ):
        data = _safe_load_json(exp / rel_path)
        if data is None:
            continue
        source_files.append(rel_path)
        if isinstance(data.get("object_scope"), dict):
            return data["object_scope"]
        return data
    return {}


def _as_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _coordinate_values(scope: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("coordenadas_wgs84", "coordenadas", "coordenadas_utm"):
        for item in _as_values(scope.get(key)):
            if isinstance(item, dict):
                values.append(" ".join(str(v) for v in item.values()))
            else:
                values.append(str(item))
    return [v.strip() for v in values if v.strip()]


def _coordinates_look_valid(values: list[str]) -> bool:
    if not values:
        return False
    number_re = re.compile(r"-?\d+(?:[.,]\d+)?")
    for value in values:
        numbers = [float(n.replace(",", ".")) for n in number_re.findall(value)]
        if len(numbers) >= 2:
            lat, lon = numbers[0], numbers[1]
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return True
    return False


def _suffix_format(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix.upper()


def _accepted_formats(req: IntakeRequirement) -> set[str]:
    return {str(fmt).upper().strip() for fmt in req.accepted_formats if str(fmt).strip()}


def _files_in_target(exp: Path, target: str) -> list[str]:
    rel_target = str(target or "").strip().rstrip("/\\")
    if not rel_target or rel_target.startswith("form."):
        return []
    base = exp / rel_target
    if not base.exists() or not base.is_dir():
        return []
    files: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file():
            try:
                files.append(str(path.relative_to(exp)).replace("\\", "/"))
            except ValueError:
                files.append(str(path).replace("\\", "/"))
    return files


def _make_issue(
    index: int,
    control_id: str,
    severity: str,
    title: str,
    message: str,
    expected_action: str,
) -> SubmissionIssue:
    return SubmissionIssue(
        issue_id=f"CSV-{index:03d}",
        control_id=control_id,
        severity=severity,
        title=title,
        message=message,
        expected_action=expected_action,
    )


def _validate_requirement(
    exp: Path,
    req: IntakeRequirement,
    scope: dict[str, Any],
    start_index: int,
) -> list[SubmissionIssue]:
    issues: list[SubmissionIssue] = []
    idx = start_index
    if req.required and req.status == "PENDIENTE":
        issues.append(_make_issue(
            idx,
            req.requirement_id,
            "ERROR",
            f"Falta obligatorio: {req.title}",
            f"El control {req.requirement_id} esta pendiente y es obligatorio.",
            f"Aportar {req.title} en {req.target}.",
        ))
        idx += 1
    elif req.priority == "ALTA" and req.status == "PARCIAL":
        issues.append(_make_issue(
            idx,
            req.requirement_id,
            "WARNING",
            f"Requisito ALTA parcial: {req.title}",
            f"El control {req.requirement_id} tiene evidencia parcial.",
            "Completar el contenido antes de cierre documental.",
        ))
        idx += 1

    accepted = _accepted_formats(req)
    target_files = _files_in_target(exp, req.target)
    evidence_files = list(dict.fromkeys(list(req.evidence) + target_files))
    if accepted and evidence_files:
        for evidence in evidence_files:
            fmt = _suffix_format(evidence)
            if fmt and fmt not in accepted:
                issues.append(_make_issue(
                    idx,
                    req.requirement_id,
                    "ERROR",
                    f"Formato no aceptado: {req.title}",
                    f"El archivo {evidence} usa formato {fmt}, no incluido en {sorted(accepted)}.",
                    f"Subir un archivo en formato aceptado para {req.title}.",
                ))
                idx += 1

    if req.requirement_id == "DAT-002" and req.status == "COMPLETO":
        values = _coordinate_values(scope)
        if not _coordinates_look_valid(values):
            issues.append(_make_issue(
                idx,
                req.requirement_id,
                "ERROR",
                "Coordenadas con formato no verificable",
                "No se pudo detectar un par latitud/longitud WGS84 dentro de rangos validos.",
                "Aportar coordenadas WGS84 y, si es posible, REGCAN95/UTM huso 28N.",
            ))
    return issues


def build_client_submission_validation(expediente_path: str | Path) -> ClientSubmissionValidation:
    """Valida la entrega cliente contra el intake/form schema."""
    exp = Path(expediente_path)
    source_files: list[str] = []
    intake = build_client_intake(exp)
    form_schema = build_client_form_schema(exp)
    scope = _phase2_scope(exp, source_files)

    issues: list[SubmissionIssue] = []
    next_index = 1
    for req in intake.requirements:
        new_issues = _validate_requirement(exp, req, scope, next_index)
        issues.extend(new_issues)
        next_index += len(new_issues)

    errors = sum(1 for issue in issues if issue.severity == "ERROR")
    warnings = sum(1 for issue in issues if issue.severity == "WARNING")
    status = "BLOQUEADO_ENTRADA" if errors else "CON_OBSERVACIONES" if warnings else "LISTO_PARA_INGESTA"
    can_start = errors == 0
    counts = {
        "controls": form_schema.counts().get("total", 0),
        "errors": errors,
        "warnings": warnings,
        "issues": len(issues),
        "required_pending": intake.counts().get("required_pending", 0),
        "high_not_complete": intake.counts().get("high_pending", 0),
    }
    return ClientSubmissionValidation(
        expediente_id=exp.name,
        status=status,
        can_start_initial_processing=can_start,
        administrative_ready=False,
        issues=issues,
        counts=counts,
        warnings=list(dict.fromkeys(list(intake.warnings) + list(form_schema.warnings))),
        source_files=list(dict.fromkeys(list(intake.source_files) + list(form_schema.source_files) + source_files)),
    )


def build_client_submission_validation_markdown(result: ClientSubmissionValidation) -> str:
    """Renderiza la validacion de entrega cliente en Markdown."""
    lines = [
        f"# Validacion entrega cliente - {result.expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Resumen",
        "",
        f"- Estado: {result.status}",
        f"- Puede iniciar procesamiento: {str(result.can_start_initial_processing).lower()}",
        f"- Errores: {result.counts.get('errors', 0)}",
        f"- Advertencias: {result.counts.get('warnings', 0)}",
        "- administrative_ready: false",
        "",
        "## Incidencias",
        "",
    ]
    if not result.issues:
        lines.append("- Sin incidencias de entrada cliente.")
    for issue in result.issues:
        lines.append(
            f"- [{issue.severity}] {issue.issue_id} {issue.control_id}: "
            f"{issue.title}. {issue.expected_action}"
        )
    if result.warnings:
        lines.extend(["", "## Avisos", ""])
        for warning in result.warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "---", "", f"*{DISCLAIMER}*"])
    return "\n".join(lines)


def write_client_submission_validation_outputs(
    result: ClientSubmissionValidation,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown de validacion en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLIENT_SUBMISSION_VALIDATION_JSON
    md_path = out_dir / CLIENT_SUBMISSION_VALIDATION_MD
    json_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_submission_validation_markdown(result), encoding="utf-8")
    return json_path, md_path
