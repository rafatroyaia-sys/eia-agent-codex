"""
client_climate_traceability -- control prudente del climograma cliente.

No consulta servicios externos ni inventa estaciones climaticas. Solo deja
trazabilidad del estado real antes de generar el Documento Ambiental.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eia_agent.core.client_official_maps import parse_wgs84_coordinates


CLIENT_ENTRY_FILE = "control_interno/entrada_cliente.json"
CLIMATE_RESULT_FILE = "clima/phase4_climate_result.json"
TRACE_JSON_FILE = "clima/trazabilidad_climatica_cliente.json"
TRACE_MD_FILE = "clima/trazabilidad_climatica_cliente.md"


@dataclass
class ClientClimateTraceabilityResult:
    """Resultado de control climatico para el expediente cliente."""

    status: str
    evidence_status: str
    administrative_ready: bool
    coordinates_wgs84: tuple[float, float] | None
    selected_station: dict[str, Any] | None = None
    station_distance_km: float | None = None
    station_selection_status: str | None = None
    climogram_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_status": self.evidence_status,
            "administrative_ready": False,
            "coordinates_wgs84": list(self.coordinates_wgs84) if self.coordinates_wgs84 else None,
            "selected_station": self.selected_station,
            "station_distance_km": self.station_distance_km,
            "station_selection_status": self.station_selection_status,
            "climogram_paths": list(self.climogram_paths),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _relative_to_exp(path: Path, exp_path: Path) -> str:
    try:
        return path.relative_to(exp_path).as_posix()
    except ValueError:
        return path.as_posix()


def _discover_climograms(exp_path: Path) -> list[str]:
    climate_dir = exp_path / "clima"
    if not climate_dir.exists():
        return []
    paths: list[str] = []
    for candidate in sorted(climate_dir.rglob("*")):
        if candidate.is_file() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            if "climograma" in candidate.name.lower() or "climogram" in candidate.name.lower():
                paths.append(_relative_to_exp(candidate, exp_path))
    return paths


def _read_declared_coordinates(exp_path: Path) -> tuple[float, float] | None:
    entry = _read_json(exp_path / CLIENT_ENTRY_FILE)
    value = (entry.get("project") or {}).get("coordinates_wgs84")
    return parse_wgs84_coordinates(str(value or ""))


def _build_markdown(result: ClientClimateTraceabilityResult) -> str:
    lines = [
        "# Trazabilidad climatica del expediente cliente",
        "",
        f"- **Estado**: {result.status}",
        f"- **Estado de evidencia**: {result.evidence_status}",
        "- **Aptitud administrativa automatica**: NO. Requiere revision tecnica.",
    ]
    if result.coordinates_wgs84:
        lat, lon = result.coordinates_wgs84
        lines.append(f"- **Coordenadas WGS84 declaradas**: {lat:.6f}, {lon:.6f}")
    else:
        lines.append("- **Coordenadas WGS84 declaradas**: no validables")

    if result.selected_station:
        station_id = result.selected_station.get("station_id") or result.selected_station.get("indicativo") or "?"
        station_name = result.selected_station.get("name") or result.selected_station.get("nombre") or "?"
        lines.append(f"- **Estacion climatica**: {station_name} ({station_id})")
        if result.station_distance_km is not None:
            lines.append(f"- **Distancia a estacion**: {result.station_distance_km:.1f} km")
        if result.station_selection_status:
            lines.append(f"- **Criterio de seleccion**: {result.station_selection_status}")
    else:
        lines.append("- **Estacion climatica**: no consta seleccion trazable")

    if result.climogram_paths:
        lines.append("- **Climogramas detectados**:")
        lines.extend(f"  - `{path}`" for path in result.climogram_paths)
    else:
        lines.append("- **Climogramas detectados**: ninguno")

    if result.warnings:
        lines.append("")
        lines.append("## Avisos")
        lines.extend(f"- {warning}" for warning in result.warnings)

    if result.notes:
        lines.append("")
        lines.append("## Notas")
        lines.extend(f"- {note}" for note in result.notes)

    lines.append("")
    lines.append(
        "Este control no sustituye la verificacion tecnica de la estacion, "
        "periodo climatico y representatividad de los datos."
    )
    return "\n".join(lines) + "\n"


def build_client_climate_traceability(
    expediente_path: str | Path,
    *,
    write_outputs: bool = False,
) -> dict[str, Any]:
    """Comprueba si el climograma tiene soporte trazable para el flujo cliente."""

    exp_path = Path(expediente_path)
    coordinates = _read_declared_coordinates(exp_path)
    phase4_result = _read_json(exp_path / CLIMATE_RESULT_FILE)
    climograms = _discover_climograms(exp_path)
    warnings: list[str] = []
    notes: list[str] = [
        "Control generado sin consultar servicios externos ni elevar evidencia declarada.",
        f"Generado en UTC: {datetime.now(timezone.utc).isoformat()}",
    ]

    selected_station = phase4_result.get("selected_station") if phase4_result else None
    station_distance_km = phase4_result.get("station_distance_km") if phase4_result else None
    station_selection_status = phase4_result.get("station_selection_status") if phase4_result else None
    climogram_path = phase4_result.get("climogram_path") if phase4_result else None
    if climogram_path:
        path = Path(str(climogram_path))
        if path.is_absolute():
            climogram_ref = _relative_to_exp(path, exp_path)
        else:
            climogram_ref = path.as_posix()
        if climogram_ref not in climograms:
            climograms.append(climogram_ref)

    if selected_station and climograms:
        status = "CLIMOGRAM_WITH_STATION"
        evidence_status = "INFERIDO"
        notes.append("Existe climograma y consta estacion seleccionada en la Fase 4.")
    elif climograms:
        status = "CLIMOGRAM_WITHOUT_STATION_TRACE"
        evidence_status = "PENDIENTE"
        warnings.append(
            "Hay climograma grafico, pero no consta trazabilidad completa de estacion y periodo."
        )
    elif coordinates:
        status = "PENDING_AEMET_OR_LOCAL_DATA"
        evidence_status = "PENDIENTE"
        warnings.append(
            "Hay coordenadas validas, pero falta ejecutar o aportar datos climaticos trazables "
            "para seleccionar estacion y generar climograma."
        )
    else:
        status = "SKIPPED_NO_COORDINATES"
        evidence_status = "PENDIENTE"
        warnings.append("No hay coordenadas WGS84 validables para seleccionar estacion climatica.")

    result = ClientClimateTraceabilityResult(
        status=status,
        evidence_status=evidence_status,
        administrative_ready=False,
        coordinates_wgs84=coordinates,
        selected_station=selected_station,
        station_distance_km=station_distance_km,
        station_selection_status=station_selection_status,
        climogram_paths=sorted(climograms),
        warnings=warnings,
        notes=notes,
    )
    payload = result.to_dict()
    payload["markdown"] = _build_markdown(result)

    if write_outputs:
        (exp_path / "clima").mkdir(parents=True, exist_ok=True)
        (exp_path / TRACE_JSON_FILE).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (exp_path / TRACE_MD_FILE).write_text(payload["markdown"], encoding="utf-8")

    return payload
