"""
client_app_package -- app profesional cliente.

Genera una carpeta y ZIP entregables con una app HTML autocontenida, contratos
JSON/Markdown y artefactos documentales disponibles del expediente.

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


CLIENT_APP_PACKAGE_DIR = "cliente_app"
CLIENT_APP_PACKAGE_ZIP = "eia_agent_cliente_app.zip"

DISCLAIMER = (
    "Esta app organiza la carga documental, el control de faltantes y la "
    "generacion del Documento Ambiental. No declara por si sola la aptitud "
    "administrativa del expediente."
)

DOCUMENT_ARTIFACTS: list[tuple[str, str]] = [
    ("documento/documento_ambiental_final_revisable.docx", "documentos/documento_ambiental_final_revisable.docx"),
    ("documento/documento_ambiental_borrador_con_figuras.docx", "documentos/documento_ambiental_con_figuras.docx"),
    ("documento/documento_ambiental_borrador.docx", "documentos/documento_ambiental.docx"),
    ("documento/documento_ambiental_borrador.md", "documentos/documento_ambiental.md"),
    ("documento/checklist_presentacion.md", "control/checklist_presentacion.md"),
    ("documento/document_quality_result.md", "control/document_quality_result.md"),
    ("auditoria/final_audit_result.md", "control/final_audit_result.md"),
]

GRAPHIC_DIRS: list[tuple[str, str]] = [
    ("mapas", "planos_mapas/mapas"),
    ("clima", "planos_mapas/clima"),
    ("anejos", "anejos"),
    ("fichas_inventario", "evidencia/fichas_inventario"),
]

_INTERNAL_FILE_SUFFIXES: tuple[str, ...] = (".py", ".pyc", ".pyo")


@dataclass
class ClientAppArtifact:
    """Archivo incluido en la app cliente."""

    artifact_id: str
    label: str
    path: str
    kind: str
    size_bytes: int
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "label": self.label,
            "path": self.path,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "required": self.required,
        }


@dataclass
class ClientAppPackage:
    """Resultado de construccion de la app cliente."""

    expediente_id: str
    status: str
    app_dir: str
    zip_path: str
    administrative_ready: bool = False
    artifacts: list[ClientAppArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_document_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "app_dir": self.app_dir,
            "zip_path": self.zip_path,
            "administrative_ready": False,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": list(self.warnings),
            "missing_document_artifacts": list(self.missing_document_artifacts),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        return "\n".join([
            f"--- App profesional cliente [{self.expediente_id}] ---",
            f"Estado       : {self.status}",
            f"Archivos     : {len(self.artifacts)}",
            f"Faltantes doc: {len(self.missing_document_artifacts)}",
            f"Carpeta      : {self.app_dir}",
            f"ZIP          : {self.zip_path}",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ])


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _artifact(root: Path, path: Path, artifact_id: str, label: str, kind: str, required: bool = False) -> ClientAppArtifact:
    return ClientAppArtifact(
        artifact_id=artifact_id,
        label=label,
        path=str(path.relative_to(root)).replace("\\", "/"),
        kind=kind,
        size_bytes=path.stat().st_size if path.exists() else 0,
        required=required,
    )


def _copy_file(exp: Path, app_dir: Path, source_rel: str, target_rel: str) -> Path | None:
    source = exp / source_rel
    target = app_dir / target_rel
    if not source.exists() or not source.is_file():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _copy_dir(exp: Path, app_dir: Path, source_rel: str, target_rel: str) -> list[Path]:
    source = exp / source_rel
    target = app_dir / target_rel
    copied: list[Path] = []
    if not source.exists() or not source.is_dir():
        return copied
    for item in sorted(source.rglob("*")):
        if item.is_file():
            if item.suffix.lower() in _INTERNAL_FILE_SUFFIXES:
                continue
            if "__pycache__" in item.parts:
                continue
            destination = target / item.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
            copied.append(destination)
    return copied


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))


def _readme_text(expediente_id: str, portal_status: str, submission_status: str) -> str:
    return "\n".join([
        f"# EIA-Agent - App cliente - {expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Uso",
        "",
        "1. Abrir `index.html` en el navegador.",
        "2. Revisar el estado ejecutivo del expediente.",
        "3. Cargar o completar las memorias, coordenadas, fotos, planos y anexos indicados por la app.",
        "4. Regenerar el expediente con los documentos completos.",
        "5. Revisar el Documento Ambiental generado en `documentos/`.",
        "",
        "## Generacion esperada del expediente",
        "",
        "- Entrada: memoria tecnica, memoria de explotacion, coordenadas, fotos, planos, cartografia y datos del promotor.",
        "- Proceso: cierre del objeto, triaje normativo, geodatos, inventario, impactos, medidas, PVA, redaccion y auditoria.",
        "- Salida: Documento Ambiental DOCX estructurado, cartografia, climograma, anexos, trazabilidad y checklist.",
        "",
        "## Estado actual",
        "",
        f"- App: {portal_status}",
        f"- Validacion de entrega: {submission_status}",
        "- administrative_ready: false",
        "",
        "## Carpetas principales",
        "",
        "- `index.html`: app cliente autocontenida.",
        "- `documentos/`: Documento Ambiental y borradores disponibles.",
        "- `planos_mapas/`: mapas, planos y clima si existen en el expediente.",
        "- `data/`: contratos JSON para UI/API.",
        "- `control/`: checks y resultados de calidad.",
        "",
    ])


def _app_manifest(expediente_id: str, portal_status: str, submission_status: str, artifacts: list[ClientAppArtifact]) -> dict[str, Any]:
    return {
        "app_name": "EIA-Agent Cliente",
        "expediente_id": expediente_id,
        "status": "APP_CLIENTE_PROFESIONAL",
        "portal_status": portal_status,
        "submission_status": submission_status,
        "administrative_ready": False,
        "disclaimer": DISCLAIMER,
        "workflow": [
            "carga_inputs_cliente",
            "validacion_entrega",
            "cierre_objeto",
            "triaje_normativo",
            "cartografia_clima",
            "inventario",
            "impactos_medidas_pva",
            "redaccion_documento_ambiental",
            "ensamblaje_docx",
            "auditoria_final",
        ],
        "expected_inputs": [
            "memoria_tecnica",
            "memoria_explotacion",
            "coordenadas",
            "referencia_catastral",
            "fotografias",
            "planos",
            "cartografia",
            "datos_operativos",
        ],
        "expected_outputs": [
            "documento_ambiental_docx",
            "mapas_planos",
            "climograma",
            "anejos",
            "matrices_impacto",
            "medidas",
            "pva",
            "trazabilidad",
        ],
        "artifacts": [artifact.to_dict() for artifact in artifacts],
    }


def build_client_app_package(
    expediente_path: str | Path,
    write_outputs: bool = False,
) -> ClientAppPackage:
    """Construye la app cliente y opcionalmente la escribe."""
    exp = Path(expediente_path)
    portal = build_client_portal(exp)
    form_schema = build_client_form_schema(exp)
    submission = build_client_submission_validation(exp)

    app_dir = exp / "documento" / CLIENT_APP_PACKAGE_DIR
    zip_path = exp / "documento" / CLIENT_APP_PACKAGE_ZIP
    artifacts: list[ClientAppArtifact] = []
    missing_document_artifacts: list[str] = []
    warnings = list(dict.fromkeys(list(portal.warnings) + list(form_schema.warnings) + list(submission.warnings)))

    if write_outputs:
        if app_dir.exists():
            shutil.rmtree(app_dir)
        data_dir = app_dir / "data"
        md_dir = app_dir / "markdown"

        _write_text(app_dir / "index.html", build_client_portal_html(portal))
        _write_text(app_dir / "README_CLIENTE.md", _readme_text(exp.name, portal.status, submission.status))
        _write_json(data_dir / "cliente_portal.json", portal.to_dict())
        _write_json(data_dir / "cliente_form_schema.json", form_schema.to_dict())
        _write_json(data_dir / "cliente_submission_validation.json", submission.to_dict())
        _write_text(md_dir / "cliente_portal.md", build_client_portal_markdown(portal))
        _write_text(md_dir / "cliente_form_schema.md", build_client_form_schema_markdown(form_schema))
        _write_text(md_dir / "cliente_submission_validation.md", build_client_submission_validation_markdown(submission))

        base_specs = [
            ("APP-HTML", "App cliente HTML", app_dir / "index.html", "html", True),
            ("APP-README", "Guia profesional cliente", app_dir / "README_CLIENTE.md", "markdown", True),
            ("APP-PORTAL", "Contrato portal JSON", data_dir / "cliente_portal.json", "json", True),
            ("APP-FORM", "Contrato formulario JSON", data_dir / "cliente_form_schema.json", "json", True),
            ("APP-VALIDATION", "Validacion entrega JSON", data_dir / "cliente_submission_validation.json", "json", True),
        ]
        artifacts.extend(
            _artifact(exp, path, artifact_id, label, kind, required)
            for artifact_id, label, path, kind, required in base_specs
        )

        for source_rel, target_rel in DOCUMENT_ARTIFACTS:
            copied = _copy_file(exp, app_dir, source_rel, target_rel)
            if copied is None:
                missing_document_artifacts.append(source_rel)
                continue
            artifacts.append(_artifact(exp, copied, "APP-DOC", f"Documento: {Path(source_rel).name}", "document", False))

        for source_rel, target_rel in GRAPHIC_DIRS:
            copied_files = _copy_dir(exp, app_dir, source_rel, target_rel)
            for copied in copied_files:
                artifacts.append(_artifact(exp, copied, "APP-GRAPHIC", f"Recurso grafico: {copied.name}", "asset", False))

        _write_json(data_dir / "app_manifest.json", _app_manifest(exp.name, portal.status, submission.status, artifacts))
        artifacts.append(_artifact(exp, data_dir / "app_manifest.json", "APP-MANIFEST", "Manifest app cliente", "json", True))
        _zip_dir(app_dir, zip_path)
        artifacts.append(_artifact(exp, zip_path, "APP-ZIP", "ZIP app cliente", "zip", True))

    status = "APP_CLIENTE_LISTA" if write_outputs else "PREVIEW_APP_CLIENTE"
    return ClientAppPackage(
        expediente_id=exp.name,
        status=status,
        app_dir=str(app_dir),
        zip_path=str(zip_path),
        administrative_ready=False,
        artifacts=artifacts,
        warnings=warnings,
        missing_document_artifacts=missing_document_artifacts,
    )
