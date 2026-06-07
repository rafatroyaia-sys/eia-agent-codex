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
RED_NATURA_WMS_URL = "https://wms.mapama.gob.es/sig/Biodiversidad/RedNatura/wms.aspx"
RED_NATURA_LAYER = "PS.ProtectedSite"
PNOA_WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
PNOA_LAYER = "OI.OrthoimageCoverage"
SNCZI_Q500_WMS_URL = "https://wms.mapama.gob.es/sig/agua/ZI_LaminasQ500/wms.aspx"
SNCZI_Q500_LAYER = "NZ.RiskZone"


@dataclass(frozen=True)
class OfficialWmsSpec:
    """Especificacion de mapa oficial WMS para el flujo cliente."""

    map_id: str
    title: str
    output_filename: str
    source: str
    wms_url: str
    layer: str
    transparent: bool = False
    warning: str = "Mapa oficial de apoyo generado por WMS. Requiere revision tecnica."


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


def build_wms_getmap_url(
    lat: float,
    lon: float,
    *,
    wms_url: str,
    layer: str,
    transparent: bool = False,
    width: int = 1200,
    height: int = 900,
) -> str:
    """URL GetMap para WMS con CRS EPSG:4326."""
    bbox = build_bbox(lat, lon)
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "STYLES": "",
        "SRS": "EPSG:4326",
        "BBOX": ",".join(f"{n:.8f}" for n in bbox),
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE" if transparent else "FALSE",
    }
    return f"{wms_url}?{urlencode(params)}"


def build_catastro_wms_url(lat: float, lon: float, width: int = 1200, height: int = 900) -> str:
    """URL GetMap para cartografia catastral WMS con CRS EPSG:4326."""
    return build_wms_getmap_url(
        lat,
        lon,
        wms_url=CATASTRO_WMS_URL,
        layer=CATASTRO_LAYER,
        width=width,
        height=height,
    )


def build_red_natura_wms_url(lat: float, lon: float, width: int = 1200, height: int = 900) -> str:
    """URL GetMap para Red Natura 2000 MITECO con CRS EPSG:4326."""
    return build_wms_getmap_url(
        lat,
        lon,
        wms_url=RED_NATURA_WMS_URL,
        layer=RED_NATURA_LAYER,
        transparent=False,
        width=width,
        height=height,
    )


def build_pnoa_ortofoto_wms_url(lat: float, lon: float, width: int = 1200, height: int = 900) -> str:
    """URL GetMap para ortofoto PNOA maxima actualidad con CRS EPSG:4326."""
    return build_wms_getmap_url(
        lat,
        lon,
        wms_url=PNOA_WMS_URL,
        layer=PNOA_LAYER,
        transparent=False,
        width=width,
        height=height,
    )


def build_snczi_q500_wms_url(lat: float, lon: float, width: int = 1200, height: int = 900) -> str:
    """URL GetMap para zonas inundables SNCZI T=500 con CRS EPSG:4326."""
    return build_wms_getmap_url(
        lat,
        lon,
        wms_url=SNCZI_Q500_WMS_URL,
        layer=SNCZI_Q500_LAYER,
        transparent=False,
        width=width,
        height=height,
    )


OFFICIAL_WMS_SPECS: tuple[OfficialWmsSpec, ...] = (
    OfficialWmsSpec(
        map_id="MAP-OFICIAL-001",
        title="Cartografia catastral oficial del entorno",
        output_filename="MAP-OFICIAL-001_catastro_parcela.png",
        source="Catastro WMS - Direccion General del Catastro",
        wms_url=CATASTRO_WMS_URL,
        layer=CATASTRO_LAYER,
        warning=(
            "Mapa oficial de apoyo generado por WMS. La delimitacion exacta de parcela "
            "debe verificarse con referencia catastral o geometria aportada."
        ),
    ),
    OfficialWmsSpec(
        map_id="MAP-OFICIAL-002",
        title="Red Natura 2000 y espacios protegidos de referencia",
        output_filename="MAP-OFICIAL-002_red_natura_2000.png",
        source="MITECO WMS - Red Natura 2000",
        wms_url=RED_NATURA_WMS_URL,
        layer=RED_NATURA_LAYER,
        warning=(
            "Mapa oficial de apoyo generado por WMS. Las distancias y afecciones deben "
            "verificarse con analisis GIS y cartografia vigente."
        ),
    ),
    OfficialWmsSpec(
        map_id="MAP-OFICIAL-003",
        title="Ortofoto PNOA maxima actualidad del emplazamiento",
        output_filename="MAP-OFICIAL-003_ortofoto_pnoa.png",
        source="IGN/CNIG WMS - PNOA maxima actualidad",
        wms_url=PNOA_WMS_URL,
        layer=PNOA_LAYER,
        warning=(
            "Ortofoto oficial de apoyo generada por WMS. Debe revisarse escala, fecha "
            "y adecuacion al ambito exacto del proyecto."
        ),
    ),
    OfficialWmsSpec(
        map_id="MAP-OFICIAL-004",
        title="Zonas inundables SNCZI T500 del entorno",
        output_filename="MAP-OFICIAL-004_inundabilidad_snczi_t500.png",
        source="MITECO WMS - SNCZI zonas inundables T=500",
        wms_url=SNCZI_Q500_WMS_URL,
        layer=SNCZI_Q500_LAYER,
        warning=(
            "Mapa oficial de apoyo generado por WMS. La existencia o ausencia de zona "
            "inundable debe verificarse con consulta GIS, demarcacion hidrografica y escala adecuada."
        ),
    ),
)


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


def _generate_one_wms_map(
    exp_path: Path,
    lat: float,
    lon: float,
    spec: OfficialWmsSpec,
    fetcher: Callable[[str], bytes],
    write_outputs: bool,
) -> tuple[OfficialMapResult, str | None]:
    url = build_wms_getmap_url(
        lat,
        lon,
        wms_url=spec.wms_url,
        layer=spec.layer,
        transparent=spec.transparent,
    )
    out_rel = f"cartografia/mapas/{spec.output_filename}"
    out_path = exp_path / out_rel
    try:
        data = fetcher(url)
        if not _looks_like_png(data):
            raise ValueError("La respuesta WMS no es una imagen PNG valida.")
        if write_outputs:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
        return (
            OfficialMapResult(
                map_id=spec.map_id,
                title=spec.title,
                status="GENERATED_REQUIRES_REVIEW",
                source=spec.source,
                output_path=out_rel if write_outputs else None,
                warnings=[spec.warning],
            ),
            None,
        )
    except Exception as exc:
        return (
            OfficialMapResult(
                map_id=spec.map_id,
                title=spec.title,
                status="NOT_AVAILABLE",
                source=spec.source,
                warnings=["Se mantiene la cartografia provisional y se requiere verificacion posterior."],
            ),
            f"No se pudo descargar {spec.title}: {exc}",
        )


def generate_client_official_maps(
    expediente_path: str | Path,
    *,
    fetcher: Callable[[str], bytes] | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Genera mapas oficiales cliente desde servicios WMS publicos.

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
        active_fetcher = fetcher or _default_fetcher
        for spec in OFFICIAL_WMS_SPECS:
            map_result, warning = _generate_one_wms_map(
                exp_path,
                lat,
                lon,
                spec,
                active_fetcher,
                write_outputs,
            )
            generated.append(map_result)
            if warning:
                warnings.append(warning)
        if any(item.status == "GENERATED_REQUIRES_REVIEW" for item in generated):
            status = "GENERATED_WITH_REVIEW"
        else:
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
