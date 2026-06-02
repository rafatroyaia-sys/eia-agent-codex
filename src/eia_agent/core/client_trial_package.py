"""
client_trial_package -- paquete de prueba para cliente.

Genera una carpeta y ZIP entregables con portal HTML, contratos JSON/Markdown y
guia de uso para que el cliente pueda revisar el estado y probar la app.

No ejecuta fases tecnicas y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.client_form_schema import (
    build_client_form_schema,
    build_client_form_schema_markdown,
)
from eia_agent.core.client_portal import (
    build_client_portal,
    build_client_portal_markdown,
)
from eia_agent.core.client_portal_site import build_client_portal_html
from eia_agent.core.client_submission_validator import (
    build_client_submission_validation,
    build_client_submission_validation_markdown,
)


CLIENT_TRIAL_PACKAGE_DIR = "cliente_trial_package"
CLIENT_TRIAL_PACKAGE_ZIP = "cliente_trial_package.zip"

DISCLAIMER = (
    "Este paquete de prueba no declara el expediente apto para presentacion "
    "administrativa. Permite al cliente revisar entradas, estado y pendientes."
)


@dataclass
class TrialPackageArtifact:
    """Archivo incluido en el paquete de prueba."""

    artifact_id: str
    label: str
    path: str
    kind: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "label": self.label,
            "path": self.path,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
        }


@dataclass
class ClientTrialPackage:
    """Resultado de construccion del paquete cliente."""

    expediente_id: str
    status: str
    package_dir: str
    zip_path: str
    administrative_ready: bool = False
    artifacts: list[TrialPackageArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "package_dir": self.package_dir,
            "zip_path": self.zip_path,
            "administrative_ready": False,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        return "\n".join([
            f"--- Paquete prueba cliente [{self.expediente_id}] ---",
            f"Estado       : {self.status}",
            f"Archivos     : {len(self.artifacts)}",
            f"Carpeta      : {self.package_dir}",
            f"ZIP          : {self.zip_path}",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _artifact(root: Path, path: Path, artifact_id: str, label: str, kind: str) -> TrialPackageArtifact:
    return TrialPackageArtifact(
        artifact_id=artifact_id,
        label=label,
        path=str(path.relative_to(root)).replace("\\", "/"),
        kind=kind,
        size_bytes=path.stat().st_size if path.exists() else 0,
    )


def _readme_text(expediente_id: str, portal_status: str, submission_status: str) -> str:
    return "\n".join([
        f"# Paquete de prueba cliente - {expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Como probar",
        "",
        "1. Abrir `index.html` en el navegador.",
        "2. Revisar el estado ejecutivo y la accion principal.",
        "3. Revisar `data/cliente_form_schema.json` para ver los campos y subidas esperados.",
        "4. Revisar `data/cliente_submission_validation.json` para ver errores y advertencias.",
        "5. Aportar la documentacion pendiente antes de solicitar procesamiento inicial.",
        "",
        "## Estado actual",
        "",
        f"- Portal: {portal_status}",
        f"- Validacion de entrega: {submission_status}",
        "- administrative_ready: false",
        "",
        "## Archivos incluidos",
        "",
        "- `index.html`: vista visual del portal cliente.",
        "- `data/cliente_portal.json`: contrato completo para UI/API.",
        "- `data/cliente_form_schema.json`: controles y validaciones de formulario.",
        "- `data/cliente_submission_validation.json`: validacion de entrega cliente.",
        "- `markdown/`: versiones legibles para revision.",
        "",
        "## Criterio",
        "",
        "Este paquete permite probar la experiencia cliente. No sustituye la revision",
        "tecnica, juridica, cartografica ni la auditoria final del Documento Ambiental.",
        "",
    ])


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))


def build_client_trial_package(
    expediente_path: str | Path,
    write_outputs: bool = False,
) -> ClientTrialPackage:
    """Construye el paquete de prueba cliente y opcionalmente lo escribe."""
    exp = Path(expediente_path)
    portal = build_client_portal(exp)
    form_schema = build_client_form_schema(exp)
    submission = build_client_submission_validation(exp)

    package_dir = exp / "documento" / CLIENT_TRIAL_PACKAGE_DIR
    zip_path = exp / "documento" / CLIENT_TRIAL_PACKAGE_ZIP
    artifacts: list[TrialPackageArtifact] = []
    warnings = list(dict.fromkeys(list(portal.warnings) + list(form_schema.warnings) + list(submission.warnings)))

    if write_outputs:
        if package_dir.exists():
            shutil.rmtree(package_dir)
        data_dir = package_dir / "data"
        md_dir = package_dir / "markdown"
        _write_text(package_dir / "index.html", build_client_portal_html(portal))
        _write_text(package_dir / "README_CLIENTE.md", _readme_text(exp.name, portal.status, submission.status))
        _write_json(data_dir / "cliente_portal.json", portal.to_dict())
        _write_json(data_dir / "cliente_form_schema.json", form_schema.to_dict())
        _write_json(data_dir / "cliente_submission_validation.json", submission.to_dict())
        _write_text(md_dir / "cliente_portal.md", build_client_portal_markdown(portal))
        _write_text(md_dir / "cliente_form_schema.md", build_client_form_schema_markdown(form_schema))
        _write_text(md_dir / "cliente_submission_validation.md", build_client_submission_validation_markdown(submission))
        _zip_dir(package_dir, zip_path)
        artifact_specs = [
            ("TRIAL-HTML", "Portal cliente HTML", package_dir / "index.html", "html"),
            ("TRIAL-README", "Guia de prueba cliente", package_dir / "README_CLIENTE.md", "markdown"),
            ("TRIAL-PORTAL", "Contrato portal JSON", data_dir / "cliente_portal.json", "json"),
            ("TRIAL-FORM", "Contrato formulario JSON", data_dir / "cliente_form_schema.json", "json"),
            ("TRIAL-VALIDATION", "Validacion entrega JSON", data_dir / "cliente_submission_validation.json", "json"),
            ("TRIAL-ZIP", "ZIP del paquete", zip_path, "zip"),
        ]
        artifacts = [_artifact(exp, path, artifact_id, label, kind) for artifact_id, label, path, kind in artifact_specs]

    status = "LISTO_PARA_PRUEBA_CLIENTE" if write_outputs else "PREVIEW_PAQUETE_CLIENTE"
    return ClientTrialPackage(
        expediente_id=exp.name,
        status=status,
        package_dir=str(package_dir),
        zip_path=str(zip_path),
        administrative_ready=False,
        artifacts=artifacts,
        warnings=warnings,
    )
