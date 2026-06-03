"""
client_app_package -- app profesional cliente.

Genera una carpeta y ZIP entregables con una app HTML autocontenida, contratos
JSON/Markdown y artefactos documentales disponibles del expediente.

No ejecuta fases tecnicas y no declara aptitud administrativa.
"""
from __future__ import annotations

import json
import re
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

PROFESSIONAL_MAP_REQUIREMENTS: list[dict[str, Any]] = [
    {
        "map_id": "MAP-001",
        "title": "Situacion general",
        "purpose": "Localizar el proyecto en la isla/municipio y contexto territorial.",
        "required_layers": ["base territorial", "municipios", "marcador de proyecto"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-002",
        "title": "Emplazamiento y accesos",
        "purpose": "Mostrar acceso viario, entorno inmediato y relacion con usos colindantes.",
        "required_layers": ["ortofoto", "viario", "marcador de proyecto"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-003",
        "title": "Delimitacion de parcela en rojo",
        "purpose": "Delimitar claramente la parcela/ambito de actuacion con perimetro rojo.",
        "required_layers": ["catastro", "parcela", "perimetro rojo", "escala"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-004",
        "title": "Topografico y pendientes",
        "purpose": "Caracterizar relieve, cotas, pendientes y drenaje superficial.",
        "required_layers": ["MDT", "curvas de nivel", "pendientes", "drenaje"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-005",
        "title": "Ortofoto detalle",
        "purpose": "Acreditar el estado fisico actual y ocupaciones del entorno cercano.",
        "required_layers": ["PNOA/GRAFCAN", "parcela", "buffer 100-250 m"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-006",
        "title": "Usos del suelo y receptores sensibles",
        "purpose": "Identificar viviendas, equipamientos, actividad industrial y receptores sensibles.",
        "required_layers": ["usos del suelo", "receptores", "buffer 500 m"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-007",
        "title": "Ruido y receptores acusticos",
        "purpose": "Ubicar focos, receptores, distancias y zonas potencialmente sensibles al ruido.",
        "required_layers": ["focos de ruido", "receptores", "distancias", "pantallas/obstaculos"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-008",
        "title": "Red Natura 2000 y ENP",
        "purpose": "Determinar relacion/distancias con espacios protegidos y zonas de sensibilidad.",
        "required_layers": ["Red Natura 2000", "ENP", "parcela", "distancias"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-009",
        "title": "Hidrologia, drenaje e inundabilidad",
        "purpose": "Evaluar cauces, escorrentia, zonas inundables y vector aguas pluviales.",
        "required_layers": ["cauces", "drenaje", "inundabilidad", "parcela"],
        "priority": "ALTA",
    },
    {
        "map_id": "MAP-010",
        "title": "Geologia, suelos y vulnerabilidad",
        "purpose": "Aportar contexto de suelo, litologia y vulnerabilidad del medio fisico.",
        "required_layers": ["geologia", "suelos", "vulnerabilidad", "parcela"],
        "priority": "MEDIA",
    },
    {
        "map_id": "MAP-011",
        "title": "Paisaje y cuencas visuales",
        "purpose": "Analizar exposicion visual y relacion con paisaje del entorno.",
        "required_layers": ["puntos de observacion", "cuencas visuales", "ortofoto"],
        "priority": "MEDIA",
    },
    {
        "map_id": "MAP-012",
        "title": "Sintesis ambiental",
        "purpose": "Integrar condicionantes principales para conclusiones, medidas y PVA.",
        "required_layers": ["condicionantes", "impactos", "medidas", "parcela"],
        "priority": "MEDIA",
    },
]


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


def _best_final_docx_source(exp: Path) -> str:
    """Elige el DOCX mas completo para entregar como final revisable en la app."""
    final_rel = "documento/documento_ambiental_final_revisable.docx"
    figures_rel = "documento/documento_ambiental_borrador_con_figuras.docx"
    base_rel = "documento/documento_ambiental_borrador.docx"
    final_path = exp / final_rel
    figures_path = exp / figures_rel
    if figures_path.exists():
        if not final_path.exists() or figures_path.stat().st_mtime >= final_path.stat().st_mtime:
            return figures_rel
    if final_path.exists():
        return final_rel
    return base_rel


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


def _ensure_climogram_from_description(exp: Path) -> Path | None:
    """Genera clima/climograma.png si hay tabla mensual en descripcion_clima.md."""
    output = exp / "clima" / "climograma.png"
    if output.exists() and output.stat().st_size > 0:
        return output
    description = exp / "clima" / "descripcion_clima.md"
    if not description.exists():
        return None
    text = description.read_text(encoding="utf-8", errors="ignore")
    rows = re.findall(
        r"\|\s*(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s*"
        r"\|\s*([\d.,]+)\s*\|\s*[\d.,]+\s*\|\s*[\d.,]+\s*\|\s*([\d.,]+)\s*\|",
        text,
        flags=re.IGNORECASE,
    )
    if len(rows) != 12:
        return None
    temperatures = [float(t.replace(",", ".")) for _, t, _ in rows]
    precipitations = [float(p.replace(",", ".")) for _, _, p in rows]
    try:
        from eia_agent.core.climate_indices import MonthlyClimateData
        from eia_agent.core.climogram_generator import ClimogramConfig, generate_climogram

        data = MonthlyClimateData(
            temperatures_c=temperatures,
            precipitations_mm=precipitations,
            station_id="C029O",
            station_name="Lanzarote Aeropuerto",
            period="1981-2010",
        )
        config = ClimogramConfig(
            title="Climograma - Lanzarote Aeropuerto",
            subtitle="Temperatura media y precipitacion mensual. Periodo normal 1981-2010",
            width_inches=10.5,
            height_inches=6.2,
            dpi=170,
        )
        result = generate_climogram(data, output, config=config)
        return Path(result.output_path)
    except Exception:
        try:
            _generate_climogram_with_pillow(temperatures, precipitations, output)
            return output if output.exists() else None
        except Exception:
            return None


def _generate_climogram_with_pillow(temperatures: list[float], precipitations: list[float], output: Path) -> None:
    """Fallback visual sin matplotlib: barras P, curva T y meses secos."""
    from PIL import Image, ImageDraw, ImageFont

    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1500, 900
    margin_l, margin_r, margin_t, margin_b = 120, 110, 115, 115
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
        font_small = ImageFont.truetype("arial.ttf", 22)
        font_title = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_title = ImageFont.load_default()

    months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    max_p = max(max(precipitations) * 1.25, 30.0)
    min_t = min(temperatures)
    max_t = max(temperatures)
    pad_t = max((max_t - min_t) * 0.35, 3.0)
    t_min = min_t - pad_t
    t_max = max_t + pad_t

    def x_at(i: int) -> float:
        return margin_l + (i + 0.5) * plot_w / 12

    def y_p(value: float) -> float:
        return margin_t + plot_h - (value / max_p) * plot_h

    def y_t(value: float) -> float:
        return margin_t + plot_h - ((value - t_min) / (t_max - t_min)) * plot_h

    draw.text((margin_l, 28), "Climograma - Lanzarote Aeropuerto", fill="#16202a", font=font_title)
    draw.text((margin_l, 72), "Temperatura media y precipitacion mensual. Periodo normal 1981-2010", fill="#667085", font=font_small)
    draw.rectangle([margin_l, margin_t, width - margin_r, height - margin_b], outline="#b8c2cc", width=2)

    for step in range(0, 6):
        p_val = max_p * step / 5
        y = y_p(p_val)
        draw.line([margin_l, y, width - margin_r, y], fill="#edf1f5", width=1)
        draw.text((35, y - 12), f"{p_val:.0f}", fill="#1f77b4", font=font_small)

    bar_w = plot_w / 18
    temp_points: list[tuple[float, float]] = []
    for i, (temp, prec) in enumerate(zip(temperatures, precipitations)):
        x = x_at(i)
        if prec < 2 * temp:
            draw.rectangle([x - plot_w / 24, margin_t, x + plot_w / 24, height - margin_b], fill="#fff6df")
        draw.rectangle([x - bar_w / 2, y_p(prec), x + bar_w / 2, height - margin_b], fill="#2f80ed")
        temp_points.append((x, y_t(temp)))
        draw.text((x - 18, height - margin_b + 28), months[i], fill="#344054", font=font_small)

    if len(temp_points) > 1:
        draw.line(temp_points, fill="#d62728", width=5, joint="curve")
    for x, y in temp_points:
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill="#d62728", outline="white", width=2)

    draw.text((margin_l, height - 58), f"T media anual: {sum(temperatures)/12:.1f} C", fill="#d62728", font=font)
    draw.text((margin_l + 360, height - 58), f"P anual: {sum(precipitations):.0f} mm", fill="#1f77b4", font=font)
    draw.text((width - 430, height - 58), "Sombreado: meses secos Gaussen", fill="#9a5b00", font=font_small)
    draw.text((35, margin_t + 8), "P (mm)", fill="#1f77b4", font=font_small)
    draw.text((width - 100, margin_t + 8), "T (C)", fill="#d62728", font=font_small)
    img.save(output, format="PNG")


def _map_requirements_status(exp: Path) -> list[dict[str, Any]]:
    files = [p.name.lower() for folder in [exp / "mapas", exp / "cartografia" / "mapas"] if folder.exists() for p in folder.glob("*.png")]
    enriched: list[dict[str, Any]] = []
    for req in PROFESSIONAL_MAP_REQUIREMENTS:
        map_id = req["map_id"].lower()
        available = any(name.startswith(map_id.lower()) for name in files)
        item = dict(req)
        item["status"] = "DISPONIBLE" if available else "PENDIENTE"
        item["available"] = available
        enriched.append(item)
    return enriched


def _map_requirements_markdown(items: list[dict[str, Any]]) -> str:
    lines = [
        "# Cartografia profesional requerida",
        "",
        "Catalogo de mapas y planos que debe revisar o completar el expediente antes de considerarse preparado.",
        "",
        "| ID | Prioridad | Estado | Mapa/plano | Finalidad | Capas minimas |",
        "|----|-----------|--------|------------|-----------|---------------|",
    ]
    for item in items:
        layers = ", ".join(item.get("required_layers", []))
        lines.append(
            f"| {item['map_id']} | {item['priority']} | {item['status']} | "
            f"{item['title']} | {item['purpose']} | {layers} |"
        )
    lines.extend([
        "",
        "Nota: la delimitacion de parcela debe representarse con perimetro rojo claramente visible.",
        "Los mapas oficiales deben mantener fuente, fecha, escala, norte, sistema de referencia y trazabilidad.",
    ])
    return "\n".join(lines)


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


def _app_manifest(
    expediente_id: str,
    portal_status: str,
    submission_status: str,
    artifacts: list[ClientAppArtifact],
    map_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
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
        "map_requirements": map_requirements,
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
        _ensure_climogram_from_description(exp)
        map_requirements = _map_requirements_status(exp)

        _write_text(app_dir / "index.html", build_client_portal_html(portal))
        _write_text(app_dir / "README_CLIENTE.md", _readme_text(exp.name, portal.status, submission.status))
        _write_json(data_dir / "cliente_portal.json", portal.to_dict())
        _write_json(data_dir / "cliente_form_schema.json", form_schema.to_dict())
        _write_json(data_dir / "cliente_submission_validation.json", submission.to_dict())
        _write_json(data_dir / "map_requirements.json", {"maps": map_requirements})
        _write_text(md_dir / "cliente_portal.md", build_client_portal_markdown(portal))
        _write_text(md_dir / "cliente_form_schema.md", build_client_form_schema_markdown(form_schema))
        _write_text(md_dir / "cliente_submission_validation.md", build_client_submission_validation_markdown(submission))
        _write_text(md_dir / "map_requirements.md", _map_requirements_markdown(map_requirements))

        base_specs = [
            ("APP-HTML", "App cliente HTML", app_dir / "index.html", "html", True),
            ("APP-README", "Guia profesional cliente", app_dir / "README_CLIENTE.md", "markdown", True),
            ("APP-PORTAL", "Contrato portal JSON", data_dir / "cliente_portal.json", "json", True),
            ("APP-FORM", "Contrato formulario JSON", data_dir / "cliente_form_schema.json", "json", True),
            ("APP-VALIDATION", "Validacion entrega JSON", data_dir / "cliente_submission_validation.json", "json", True),
            ("APP-MAPS", "Catalogo cartografico profesional", data_dir / "map_requirements.json", "json", True),
        ]
        artifacts.extend(
            _artifact(exp, path, artifact_id, label, kind, required)
            for artifact_id, label, path, kind, required in base_specs
        )

        for source_rel, target_rel in DOCUMENT_ARTIFACTS:
            if target_rel == "documentos/documento_ambiental_final_revisable.docx":
                source_rel = _best_final_docx_source(exp)
            copied = _copy_file(exp, app_dir, source_rel, target_rel)
            if copied is None:
                missing_document_artifacts.append(source_rel)
                continue
            artifacts.append(_artifact(exp, copied, "APP-DOC", f"Documento: {Path(source_rel).name}", "document", False))

        for source_rel, target_rel in GRAPHIC_DIRS:
            copied_files = _copy_dir(exp, app_dir, source_rel, target_rel)
            for copied in copied_files:
                artifacts.append(_artifact(exp, copied, "APP-GRAPHIC", f"Recurso grafico: {copied.name}", "asset", False))

        _write_json(data_dir / "app_manifest.json", _app_manifest(exp.name, portal.status, submission.status, artifacts, map_requirements))
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
