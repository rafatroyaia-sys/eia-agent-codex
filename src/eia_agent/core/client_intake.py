"""
client_intake -- contrato de entrada para la futura app cliente.

Define y evalua los datos/documentos que el promotor debe aportar para iniciar
un Documento Ambiental: memorias, coordenadas, fotos, planos, cartografia y
datos operativos.

No interpreta juridicamente el expediente, no ejecuta fases y no declara aptitud.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CLIENT_INTAKE_JSON = "cliente_intake.json"
CLIENT_INTAKE_MD = "cliente_intake.md"

DISCLAIMER = (
    "Este intake no declara el expediente apto para presentacion administrativa. "
    "Solo ordena los datos y documentos que debe aportar el promotor."
)

TEXT_EXTENSIONS = {".docx", ".pdf", ".txt", ".md", ".odt", ".xlsx", ".xls", ".csv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".pdf"}
CARTO_EXTENSIONS = {".shp", ".dbf", ".shx", ".prj", ".kml", ".kmz", ".geojson", ".gpkg", ".dxf", ".dwg", ".pdf", ".png", ".jpg", ".jpeg"}


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def _truthy_text(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() not in {"PENDIENTE", "NO_DECLARADO", "NO CONSTA"}
    if isinstance(value, list):
        return any(_truthy_text(v) for v in value)
    return bool(value)


def _scan_files(exp: Path, dirs: list[str], extensions: set[str]) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for rel_dir in dirs:
        base = exp / rel_dir
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in extensions:
                rel = _rel(path, exp)
                if rel not in seen:
                    files.append(rel)
                    seen.add(rel)
    return files


@dataclass
class IntakeRequirement:
    """Campo o documento requerido para iniciar/cerrar el expediente."""

    requirement_id: str
    title: str
    kind: str  # FIELD | DOCUMENT | MEDIA | CARTOGRAPHY
    priority: str  # ALTA | MEDIA | BAJA
    required: bool
    target: str
    help_text: str
    accepted_formats: list[str] = field(default_factory=list)
    status: str = "PENDIENTE"  # COMPLETO | PARCIAL | PENDIENTE
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "kind": self.kind,
            "priority": self.priority,
            "required": self.required,
            "target": self.target,
            "help_text": self.help_text,
            "accepted_formats": list(self.accepted_formats),
            "status": self.status,
            "evidence": list(self.evidence),
        }


@dataclass
class ClientIntake:
    """Resultado de intake para expediente cliente."""

    expediente_id: str
    requirements: list[IntakeRequirement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    administrative_ready: bool = False

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.requirements),
            "complete": sum(1 for r in self.requirements if r.status == "COMPLETO"),
            "partial": sum(1 for r in self.requirements if r.status == "PARCIAL"),
            "pending": sum(1 for r in self.requirements if r.status == "PENDIENTE"),
            "required_pending": sum(1 for r in self.requirements if r.required and r.status == "PENDIENTE"),
            "high_pending": sum(1 for r in self.requirements if r.priority == "ALTA" and r.status != "COMPLETO"),
        }

    def is_ready_for_initial_processing(self) -> bool:
        counts = self.counts()
        return counts["required_pending"] == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "expediente_id": self.expediente_id,
            "administrative_ready": False,
            "ready_for_initial_processing": self.is_ready_for_initial_processing(),
            "counts": self.counts(),
            "requirements": [r.to_dict() for r in self.requirements],
            "warnings": list(self.warnings),
            "source_files": list(self.source_files),
            "disclaimer": DISCLAIMER,
        }

    def summary(self) -> str:
        counts = self.counts()
        lines = [
            f"--- Intake cliente [{self.expediente_id}] ---",
            f"Completos    : {counts['complete']}/{counts['total']}",
            f"Pendientes   : {counts['pending']} (ALTA no completos: {counts['high_pending']})",
            f"Listo inicial: {self.is_ready_for_initial_processing()}",
            "Admin ready  : False",
            f"NOTA: {DISCLAIMER}",
        ]
        if self.warnings:
            lines.append("Avisos       :")
            lines.extend(f"  - {warning}" for warning in self.warnings)
        return "\n".join(lines)


def _phase2_scope(exp: Path, source_files: list[str]) -> dict[str, Any]:
    for rel_path in (
        "control_interno/phase2_result.json",
        "fase2/phase2_result.json",
        "control_interno/object_scope.json",
        "fase2/object_scope.json",
    ):
        path = exp / rel_path
        data = _safe_load_json(path)
        if data is None:
            continue
        source_files.append(rel_path)
        if "object_scope" in data and isinstance(data["object_scope"], dict):
            return data["object_scope"]
        return data
    return {}


def _make_requirements(exp: Path, scope: dict[str, Any]) -> list[IntakeRequirement]:
    memoria_files = _scan_files(exp, ["inputs/memoria_tecnica", "inputs/memorias", "inputs"], TEXT_EXTENSIONS)
    explotacion_files = _scan_files(exp, ["inputs/memoria_explotacion", "inputs/memorias", "inputs"], TEXT_EXTENSIONS)
    foto_files = _scan_files(exp, ["inputs/fotos", "inputs/imagenes"], IMAGE_EXTENSIONS)
    plano_files = _scan_files(exp, ["inputs/imagenes", "inputs/planos", "inputs/cartografia_aportada"], IMAGE_EXTENSIONS | {".dxf", ".dwg"})
    carto_files = _scan_files(exp, ["inputs/cartografia_aportada", "inputs/planos"], CARTO_EXTENSIONS)

    field_checks = {
        "titular": _truthy_text(scope.get("titular") or scope.get("promotor")),
        "coordenadas": _truthy_text(scope.get("coordenadas_wgs84") or scope.get("coordenadas") or scope.get("coordenadas_utm")),
        "referencia_catastral": _truthy_text(scope.get("referencia_catastral")),
        "operaciones": _truthy_text(scope.get("operaciones_incluidas") or scope.get("actividad") or scope.get("uso_declarado")),
        "capacidad": _truthy_text(scope.get("capacidad") or scope.get("superficie_m2")),
    }

    requirements = [
        IntakeRequirement(
            "DAT-001", "Promotor o titular", "FIELD", "ALTA", True,
            "form.promotor", "Razon social, NIF y persona de contacto del promotor.",
            status="COMPLETO" if field_checks["titular"] else "PENDIENTE",
            evidence=["object_scope.titular"] if field_checks["titular"] else [],
        ),
        IntakeRequirement(
            "DAT-002", "Coordenadas del emplazamiento", "FIELD", "ALTA", True,
            "form.coordenadas", "Coordenadas WGS84 y, si es posible, REGCAN95/UTM huso 28N.",
            status="COMPLETO" if field_checks["coordenadas"] else "PENDIENTE",
            evidence=["object_scope.coordenadas"] if field_checks["coordenadas"] else [],
        ),
        IntakeRequirement(
            "DAT-003", "Referencia catastral", "FIELD", "ALTA", True,
            "form.referencia_catastral", "Referencia catastral de parcela o inmueble afectado.",
            status="COMPLETO" if field_checks["referencia_catastral"] else "PENDIENTE",
            evidence=["object_scope.referencia_catastral"] if field_checks["referencia_catastral"] else [],
        ),
        IntakeRequirement(
            "DAT-004", "Operaciones y actividad", "FIELD", "ALTA", True,
            "form.operaciones", "Actividad, operaciones incluidas/excluidas, codigos R/D y residuos LER si aplica.",
            status="COMPLETO" if field_checks["operaciones"] else "PENDIENTE",
            evidence=["object_scope.operaciones_incluidas"] if field_checks["operaciones"] else [],
        ),
        IntakeRequirement(
            "DAT-005", "Capacidad, superficie u horarios", "FIELD", "MEDIA", False,
            "form.datos_operativos", "Capacidad anual, superficie, horarios, maquinaria y turnos.",
            status="COMPLETO" if field_checks["capacidad"] else "PENDIENTE",
            evidence=["object_scope.capacidad/superficie"] if field_checks["capacidad"] else [],
        ),
        IntakeRequirement(
            "DOC-001", "Memoria tecnica del proyecto", "DOCUMENT", "ALTA", True,
            "inputs/memoria_tecnica/", "Memoria tecnica o proyecto tecnico en DOCX/PDF.",
            accepted_formats=["DOCX", "PDF"],
            status="COMPLETO" if memoria_files else "PENDIENTE",
            evidence=memoria_files[:10],
        ),
        IntakeRequirement(
            "DOC-002", "Memoria de explotacion u operaciones", "DOCUMENT", "ALTA", True,
            "inputs/memoria_explotacion/", "Descripcion de procesos, maquinaria, horarios, residuos y medidas.",
            accepted_formats=["DOCX", "PDF", "XLSX", "CSV"],
            status="COMPLETO" if explotacion_files else "PENDIENTE",
            evidence=explotacion_files[:10],
        ),
        IntakeRequirement(
            "DOC-003", "Fotografias del emplazamiento", "MEDIA", "MEDIA", False,
            "inputs/fotos/", "Fotos exteriores/interiores, accesos, entorno, focos y medidas existentes.",
            accepted_formats=["JPG", "PNG", "PDF"],
            status="COMPLETO" if foto_files else "PENDIENTE",
            evidence=foto_files[:10],
        ),
        IntakeRequirement(
            "DOC-004", "Planos o esquemas", "DOCUMENT", "ALTA", True,
            "inputs/imagenes/", "Plano de situacion, implantacion, distribucion, proceso y almacenamiento.",
            accepted_formats=["PDF", "PNG", "JPG", "DXF", "DWG"],
            status="COMPLETO" if plano_files else "PENDIENTE",
            evidence=plano_files[:10],
        ),
        IntakeRequirement(
            "DOC-005", "Cartografia aportada", "CARTOGRAPHY", "MEDIA", False,
            "inputs/cartografia_aportada/", "SHP/KML/KMZ/GeoJSON/DXF/PDF si el promotor dispone de cartografia.",
            accepted_formats=["SHP", "KML", "KMZ", "GeoJSON", "GPKG", "DXF", "PDF"],
            status="COMPLETO" if carto_files else "PENDIENTE",
            evidence=carto_files[:10],
        ),
        IntakeRequirement(
            "DOC-006", "Alternativas estudiadas o confirmacion de propuesta", "DOCUMENT", "MEDIA", False,
            "inputs/memoria_tecnica/", "Opcional: la app propone alternativa cero y alternativas razonables para confirmacion del promotor.",
            accepted_formats=["DOCX", "PDF"],
            status="PARCIAL" if memoria_files else "PENDIENTE",
            evidence=memoria_files[:5],
        ),
    ]
    return requirements


def build_client_intake(expediente_path: str | Path) -> ClientIntake:
    """Construye el intake cliente desde inputs y outputs de Fase 2 existentes."""
    exp = Path(expediente_path)
    source_files: list[str] = []
    warnings: list[str] = []

    scope = _phase2_scope(exp, source_files)
    if not scope:
        warnings.append("No se encontro Fase 2/ObjectScope; los campos de formulario quedan pendientes.")

    inputs_dir = exp / "inputs"
    if not inputs_dir.exists():
        warnings.append("No existe carpeta inputs/. Inicialice el expediente o cree la estructura de entrada.")

    requirements = _make_requirements(exp, scope)
    return ClientIntake(
        expediente_id=exp.name,
        requirements=requirements,
        warnings=warnings,
        source_files=source_files,
        administrative_ready=False,
    )


def build_client_intake_markdown(intake: ClientIntake) -> str:
    """Renderiza el intake en Markdown."""
    counts = intake.counts()
    lines = [
        f"# Intake cliente - {intake.expediente_id}",
        "",
        f"> **AVISO**: {DISCLAIMER}",
        "",
        "## Resumen",
        "",
        f"- Requisitos totales: {counts['total']}",
        f"- Completos: {counts['complete']}",
        f"- Parciales: {counts['partial']}",
        f"- Pendientes: {counts['pending']}",
        f"- ALTA no completos: {counts['high_pending']}",
        f"- Listo para procesamiento inicial: {str(intake.is_ready_for_initial_processing()).lower()}",
        "- administrative_ready: false",
        "",
        "## Requisitos",
        "",
        "| ID | Prioridad | Tipo | Estado | Requisito | Destino |",
        "|----|-----------|------|--------|-----------|---------|",
    ]
    for req in intake.requirements:
        lines.append(
            f"| {req.requirement_id} | {req.priority} | {req.kind} | "
            f"{req.status} | {req.title} | `{req.target}` |"
        )
    lines.extend(["", "## Detalle", ""])
    for req in intake.requirements:
        lines.append(f"### {req.requirement_id} - {req.title}")
        lines.append("")
        lines.append(f"- Estado: {req.status}")
        lines.append(f"- Prioridad: {req.priority}")
        lines.append(f"- Obligatorio: {str(req.required).lower()}")
        lines.append(f"- Destino: `{req.target}`")
        lines.append(f"- Indicacion: {req.help_text}")
        if req.accepted_formats:
            lines.append(f"- Formatos: {', '.join(req.accepted_formats)}")
        if req.evidence:
            lines.append("- Evidencia detectada:")
            for item in req.evidence:
                lines.append(f"  - `{item}`")
        lines.append("")
    if intake.warnings:
        lines.extend(["## Avisos", ""])
        for warning in intake.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.extend(["---", "", f"*{DISCLAIMER}*"])
    return "\n".join(lines)


def write_client_intake_outputs(
    intake: ClientIntake,
    expediente_path: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y Markdown del intake en documento/."""
    exp = Path(expediente_path)
    out_dir = exp / "documento"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLIENT_INTAKE_JSON
    md_path = out_dir / CLIENT_INTAKE_MD
    json_path.write_text(json.dumps(intake.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_client_intake_markdown(intake), encoding="utf-8")
    return json_path, md_path
