"""
client_dashboard -- vista estructurada para la futura app cliente.

Compone una fotografia de expediente a partir de outputs ya generados:
  - estado DA-01;
  - plan de accion cliente;
  - auditoria final;
  - artefactos descargables.

No ejecuta pipelines, no cierra gaps y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.client_action_plan import (
    build_client_action_plan,
    build_client_action_plan_markdown,
)


CLIENT_DASHBOARD_JSON = "cliente_dashboard.json"
CLIENT_DASHBOARD_MD = "cliente_dashboard.md"

DISCLAIMER = (
    "Este dashboard no declara el expediente apto para presentacion administrativa. "
    "Solo resume outputs existentes para revision del cliente y del equipo tecnico."
)


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


@dataclass
class DashboardArtifact:
    """Artefacto descargable o revisable desde la app cliente."""

    artifact_id: str
    label: str
    path: str
    kind: str
    available: bool
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "label": self.label,
            "path": self.path,
            "kind": self.kind,
            "available": self.available,
            "size_bytes": self.size_bytes,
        }


@dataclass
class ClientDashboard:
    """Resultado compuesto para panel cliente."""

    expediente_id: str
    status: str
    headline: str
    next_action: str
    administrative_ready: bool = False
    counts: dict[str, int] = field(default_factory=dict)
    da_state: dict[str, Any] = field(default_factory=dict)
    action_plan: dict[str, Any] = field(default_factory=dict)
    artifacts: list[DashboardArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def available_artifacts(self) -> list[DashboardArtifact]:
        return [a for a in self.artifacts if a.available]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "headline": self.headline,
            "next_action": self.next_action,
            "administrative_ready": False,
            "counts": dict(self.counts),
            "da_state": dict(self.da_state),
            "action_plan": dict(self.action_plan),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "warnings": list(self.warnings),
            "source_files": list(self.source_files),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        return "\n".join([
            f"--- Dashboard cliente [{self.expediente_id}] ---",
            f"Estado       : {self.status}",
            f"Lectura      : {self.headline}",
            f"Siguiente    : {self.next_action}",
            f"Artefactos   : {len(self.available_artifacts())}/{len(self.artifacts)} disponibles",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _artifact(root: Path, artifact_id: str, label: str, rel_path: str, kind: str) -> DashboardArtifact:
    path = root / rel_path
    available = path.exists() and path.is_file()
    return DashboardArtifact(
        artifact_id=artifact_id,
        label=label,
        path=rel_path.replace("\\", "/"),
        kind=kind,
        available=available,
        size_bytes=path.stat().st_size if available else 0,
    )


def _collect_artifacts(exp: Path) -> list[DashboardArtifact]:
    artifacts = [
        _artifact(exp, "ART-DA-MD", "Borrador Documento Ambiental (Markdown)", "documento/documento_ambiental_borrador.md", "markdown"),
        _artifact(exp, "ART-DA-DOCX", "Borrador Documento Ambiental (DOCX)", "documento/documento_ambiental_borrador.docx", "docx"),
        _artifact(exp, "ART-DA-FINAL-DOCX", "Documento preparado para revision/firma", "documento/documento_ambiental_presentacion.docx", "docx"),
        _artifact(exp, "ART-PAQUETE-ZIP", "Paquete de entrega ZIP", "documento/paquete_entrega.zip", "zip"),
        _artifact(exp, "ART-PLAN-MD", "Plan de accion cliente", "documento/plan_accion_cliente.md", "markdown"),
        _artifact(exp, "ART-ESTADO-MD", "Estado del expediente DA", "documento/estado_expediente_da.md", "markdown"),
        _artifact(exp, "ART-AUDITORIA-MD", "Auditoria final", "auditoria/final_audit_result.md", "markdown"),
    ]
    return artifacts


def _compact_da_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {
            "available": False,
            "resultado_flujo": "SIN_DATOS",
            "counts": {"CERRADO": 0, "PENDIENTE": 0, "BLOQUEANTE": 0},
            "administrative_ready": False,
        }
    return {
        "available": True,
        "resultado_flujo": str(state.get("resultado_flujo", "NO_DECLARADO")),
        "resultado_flujo_label": str(state.get("resultado_flujo_label", "")),
        "counts": state.get("counts", {}),
        "administrative_ready": False,
    }


def build_client_dashboard(expediente_path: str | Path) -> ClientDashboard:
    """Construye el dashboard cliente desde outputs existentes del expediente."""
    exp = Path(expediente_path)
    expediente_id = exp.name
    warnings: list[str] = []
    source_files: list[str] = []

    state_path = exp / "documento" / "estado_expediente_da.json"
    plan_path = exp / "documento" / "plan_accion_cliente.json"
    audit_path = exp / "auditoria" / "final_audit_result.json"

    state = _safe_load_json(state_path)
    plan_data = _safe_load_json(plan_path)
    audit = _safe_load_json(audit_path)

    for path, data in ((state_path, state), (plan_path, plan_data), (audit_path, audit)):
        if data is not None:
            source_files.append(_rel(path, exp))

    if plan_data is None:
        plan = build_client_action_plan(exp)
        plan_data = plan.to_dict()
        if plan.warnings:
            warnings.extend(plan.warnings)
        if not (plan_path.exists()):
            warnings.append("Plan de accion no escrito en disco; dashboard usa plan calculado en memoria.")

    executive = plan_data.get("executive_summary", {}) if isinstance(plan_data, dict) else {}
    status = str(executive.get("status") or "SIN_PLAN_ACCION")
    headline = str(executive.get("headline") or "No hay resumen ejecutivo disponible.")
    next_action = str(executive.get("next_action") or "Ejecutar cliente-da y cliente-plan.")

    da_state = _compact_da_state(state)
    counts = {
        "promoter_requests": int(plan_data.get("counts", {}).get("promoter_requests", 0)),
        "promoter_high": int(plan_data.get("counts", {}).get("promoter_high", 0)),
        "technical_actions": int(plan_data.get("counts", {}).get("technical_actions", 0)),
        "technical_high": int(plan_data.get("counts", {}).get("technical_high", 0)),
        "da_cerrado": int(da_state.get("counts", {}).get("CERRADO", 0)),
        "da_pendiente": int(da_state.get("counts", {}).get("PENDIENTE", 0)),
        "da_bloqueante": int(da_state.get("counts", {}).get("BLOQUEANTE", 0)),
        "audit_issues": len(audit.get("issues", [])) if isinstance(audit, dict) else 0,
    }

    artifacts = _collect_artifacts(exp)
    if not any(a.available for a in artifacts):
        warnings.append("No se detectaron artefactos documentales descargables.")

    return ClientDashboard(
        expediente_id=expediente_id,
        status=status,
        headline=headline,
        next_action=next_action,
        administrative_ready=False,
        counts=counts,
        da_state=da_state,
        action_plan={
            "available": plan_data is not None,
            "executive_summary": executive,
            "closing_route": plan_data.get("closing_route", []) if isinstance(plan_data, dict) else [],
        },
        artifacts=artifacts,
        warnings=warnings,
        source_files=source_files,
    )


def build_client_dashboard_markdown(dashboard: ClientDashboard) -> str:
    """Renderiza el dashboard en Markdown para revision rapida."""
    lines = [
        f"# Dashboard cliente — {dashboard.expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Estado ejecutivo",
        "",
        f"- Estado: {dashboard.status}",
        f"- Lectura: {dashboard.headline}",
        f"- Siguiente accion: {dashboard.next_action}",
        "- administrative_ready: false",
        "",
        "## Indicadores",
        "",
    ]
    for key, value in dashboard.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Artefactos", ""])
    for artifact in dashboard.artifacts:
        status = "disponible" if artifact.available else "pendiente"
        lines.append(
            f"- {artifact.artifact_id}: {artifact.label} — {status} — `{artifact.path}`"
        )
    if dashboard.action_plan.get("closing_route"):
        lines.extend(["", "## Ruta de cierre", ""])
        for step in dashboard.action_plan["closing_route"]:
            lines.append(f"{step.get('order')}. {step.get('title')}")
    if dashboard.warnings:
        lines.extend(["", "## Avisos", ""])
        for warning in dashboard.warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "---", "", f"*{DISCLAIMER}*"])
    return "\n".join(lines)


def write_client_dashboard_outputs(
    dashboard: ClientDashboard,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown del dashboard en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLIENT_DASHBOARD_JSON
    md_path = out_dir / CLIENT_DASHBOARD_MD
    json_path.write_text(json.dumps(dashboard.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_dashboard_markdown(dashboard), encoding="utf-8")
    return json_path, md_path
