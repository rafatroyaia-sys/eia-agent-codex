"""
client_official_maps -- cartografia oficial ligera para expedientes cliente.

Genera recursos visuales desde servicios publicos WMS cuando hay coordenadas
WGS84 declaradas. Si el servicio externo no responde, no bloquea el expediente:
deja trazabilidad y permite continuar con cartografia provisional.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import urlopen


CLIENT_ENTRY_FILE = "control_interno/entrada_cliente.json"
CATASTRO_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"
CATASTRO_LAYER = "Catastro"


@dataclass
class OfficialMapResult:
    """Resultado de generacion de un mapa oficial ligero."""

    map_id: str
    title: str
    status: str
    source: str
    output_path: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "title": self.title,
            "status": self.status,
            "source": self.source,
            "output_path": self.output_path,
            "warnings": list(self.warnings),
        }


def parse_wgs84_coordinates(value: str | None) -> tuple[float, float] | None:
    """Extrae latitud/longitud declaradas en formato 'lat, lon'."""
    if not value:
        return None
    match = re.fullmatch(
        r"\s*(-?\d{1,2}(?:[\.,]\d+)?)\s*,\s*(-?\d{1,3}(?:[\.,]\d+)?)\s*",
        value,
    )
    if not match:
        return None
    lat = float(match.group(1).replace(",", "."))
    lon = float(match.group(2).replace(",", "."))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def build_bbox(lat: float, lon: float, buffer_m: int = 550) -> tuple[float, float, float, float]:
    """Construye bbox EPSG:4326 alrededor del punto con buffer aproximado en metros."""
    lat_delta = buffer_m / 111_320
    cos_lat = max(math.cos(math.radians(lat)), 0.1)
    lon_delta = buffer_m / (111_320 * cos_lat)
    return lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta


def build_catastro_wms_url(lat: float, lon: float, width: int = 1200, height: int = 900) -> str:
    """URL GetMap para cartografia catastral WMS con CRS EPSG:4326."""
    bbox = build_bbox(lat, lon)
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": CATASTRO_LAYER,
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": ",".join(f"{n:.8f}" for n in bbox),
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/png",
        "TRANSPARENT": "FALSE",
    }
    return f"{CATASTRO_WMS_URL}?{urlencode(params)}"


def _default_fetcher(url: str) -> bytes:
    with urlopen(url, timeout=25) as response:  # noqa: S310 - fuente oficial configurable y publica
        return response.read()


def _read_client_entry(exp_path: Path) -> dict[str, Any]:
    entry_path = exp_path / CLIENT_ENTRY_FILE
    if not entry_path.exists():
        return {}
    return json.loads(entry_path.read_text(encoding="utf-8"))


def _looks_like_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def generate_client_official_maps(
    expediente_path: str | Path,
    *,
    fetcher: Callable[[str], bytes] | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Genera primer mapa oficial cliente desde Catastro WMS.

    Devuelve siempre un estado prudente. Los errores de red o de servicio se
    registran como WARNING, no como excepcion bloqueante.
    """
    exp_path = Path(expediente_path)
    entry = _read_client_entry(exp_path)
    coordinates = (entry.get("project") or {}).get("coordinates_wgs84")
    parsed = parse_wgs84_coordinates(coordinates)
    generated: list[OfficialMapResult] = []
    warnings: list[str] = []

    if parsed is None:
        warnings.append("No se pudo generar cartografia oficial: coordenadas WGS84 no reconocidas.")
        status = "SKIPPED"
    else:
        lat, lon = parsed
        url = build_catastro_wms_url(lat, lon)
        out_rel = "cartografia/mapas/MAP-OFICIAL-001_catastro_parcela.png"
        out_path = exp_path / out_rel
        source = "Catastro WMS - Direccion General del Catastro"
        try:
            data = (fetcher or _default_fetcher)(url)
            if not _looks_like_png(data):
                raise ValueError("La respuesta WMS no es una imagen PNG valida.")
            if write_outputs:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
            generated.append(
                OfficialMapResult(
                    map_id="MAP-OFICIAL-001",
                    title="Cartografia catastral oficial del entorno",
                    status="GENERATED_REQUIRES_REVIEW",
                    source=source,
                    output_path=out_rel if write_outputs else None,
                    warnings=[
                        "Mapa oficial de apoyo generado por WMS. La delimitacion exacta de parcela debe verificarse con referencia catastral o geometria aportada.",
                    ],
                )
            )
            status = "GENERATED_WITH_REVIEW"
        except Exception as exc:  # pragma: no cover - cubierto indirectamente con fetcher en tests
            warnings.append(f"No se pudo descargar Catastro WMS: {exc}")
            generated.append(
                OfficialMapResult(
                    map_id="MAP-OFICIAL-001",
                    title="Cartografia catastral oficial del entorno",
                    status="NOT_AVAILABLE",
                    source=source,
                    warnings=["Se mantiene la cartografia provisional y se requiere verificacion posterior."],
                )
            )
            status = "WARNING"

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "administrative_ready": False,
        "maps": [item.to_dict() for item in generated],
        "warnings": warnings,
    }
    if write_outputs:
        status_dir = exp_path / "cartografia"
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "mapas_oficiales_cliente.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (status_dir / "mapas_oficiales_cliente.md").write_text(
            build_official_maps_markdown(result),
            encoding="utf-8",
        )
    return result


def build_official_maps_markdown(result: dict[str, Any]) -> str:
    """Resumen markdown para trazabilidad."""
    lines = [
        "# Cartografia oficial cliente",
        "",
        f"- Estado: {result.get('status')}",
        "- Aptitud administrativa automatica: NO",
        "",
        "## Mapas",
        "",
    ]
    maps = result.get("maps") or []
    if not maps:
        lines.append("- No se genero ningun mapa oficial.")
    for item in maps:
        lines.append(f"- {item.get('map_id')}: {item.get('title')} ({item.get('status')})")
        if item.get("output_path"):
            lines.append(f"  - Archivo: `{item.get('output_path')}`")
        lines.append(f"  - Fuente: {item.get('source')}")
    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "## Avisos", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"
