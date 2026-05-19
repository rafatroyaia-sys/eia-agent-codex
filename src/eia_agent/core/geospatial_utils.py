"""
geospatial_utils -- CA-09
Núcleo geoespacial offline para cartografía EIA.

Provee tipos y utilidades geoespaciales básicas reutilizables por los
módulos CA-xx que generarán mapas. No realiza ninguna llamada externa.

No genera mapas.
No llama a Mapbox ni a WMS/WMTS.
No consulta Catastro.
No verifica coordenadas contra ningún servicio externo.
No usa IA.

Uso:
    from eia_agent.core.geospatial_utils import (
        GeoPoint, build_map_extent, build_standard_map_extents,
        extract_geopoint_from_phase2,
    )

    point = GeoPoint(lat=28.9773, lon=-13.5395, source="phase2_result")
    extents = build_standard_map_extents(point)
    print(extents["emplazamiento"].summary())
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_LAT_DEG_TO_M: float = 111_320.0  # metros por grado de latitud (approx.)

_VALID_STATUSES = frozenset({
    "DECLARADO", "ESTIMADO", "VERIFICADO", "PROVISIONAL", "NO_DECLARADO",
})

_UNRELIABLE_STATUSES = frozenset({"ESTIMADO", "PROVISIONAL", "NO_DECLARADO"})

# Radios estándar de los 5 extents mínimos de Fase 4
_STANDARD_RADII: dict[str, float] = {
    "detalle_parcela": 250.0,
    "emplazamiento": 1_000.0,
    "entorno_500m": 500.0,
    "entorno_2000m": 2_000.0,
    "situacion_general": 25_000.0,
}


# ---------------------------------------------------------------------------
# GeoPoint
# ---------------------------------------------------------------------------

@dataclass
class GeoPoint:
    """Punto geográfico WGS84 con metadatos de procedencia y estado de evidencia."""

    lat: float
    lon: float
    source: str | None = None
    status: str = "DECLARADO"
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Lanza ValueError si las coordenadas o el estado no son válidos."""
        validate_lat_lon(self.lat, self.lon)
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"Estado '{self.status}' no válido. "
                f"Valores permitidos: {sorted(_VALID_STATUSES)}"
            )

    def to_dict(self) -> dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "source": self.source,
            "status": self.status,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeoPoint":
        return cls(
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            source=data.get("source"),
            status=data.get("status", "DECLARADO"),
            notes=list(data.get("notes") or []),
        )

    def as_tuple(self) -> tuple[float, float]:
        """Devuelve (lat, lon)."""
        return self.lat, self.lon


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    """Bounding box geográfico en WGS84 (grados decimales)."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def validate(self) -> None:
        """Lanza ValueError si los valores están fuera de rango o son inconsistentes."""
        for lat in (self.min_lat, self.max_lat):
            if not (-90.0 <= lat <= 90.0):
                raise ValueError(f"Latitud fuera de rango [-90, 90]: {lat}")
        for lon in (self.min_lon, self.max_lon):
            if not (-180.0 <= lon <= 180.0):
                raise ValueError(f"Longitud fuera de rango [-180, 180]: {lon}")
        if self.min_lat >= self.max_lat:
            raise ValueError(
                f"min_lat ({self.min_lat}) debe ser menor que max_lat ({self.max_lat})"
            )
        if self.min_lon >= self.max_lon:
            raise ValueError(
                f"min_lon ({self.min_lon}) debe ser menor que max_lon ({self.max_lon})"
            )

    def to_dict(self) -> dict:
        return {
            "min_lat": self.min_lat,
            "min_lon": self.min_lon,
            "max_lat": self.max_lat,
            "max_lon": self.max_lon,
        }

    def width_degrees(self) -> float:
        """Ancho del bbox en grados de longitud."""
        return self.max_lon - self.min_lon

    def height_degrees(self) -> float:
        """Alto del bbox en grados de latitud."""
        return self.max_lat - self.min_lat


# ---------------------------------------------------------------------------
# MapExtent
# ---------------------------------------------------------------------------

@dataclass
class MapExtent:
    """Extent cartográfico con centro, bbox, radio y escala sugerida."""

    center: GeoPoint
    bbox: BoundingBox
    radius_m: float
    scale_hint: str
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "center": self.center.to_dict(),
            "bbox": self.bbox.to_dict(),
            "radius_m": self.radius_m,
            "scale_hint": self.scale_hint,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Extent [{self.scale_hint}]",
            f"  Centro  : ({self.center.lat:.5f}, {self.center.lon:.5f})"
            f" [{self.center.status}]",
            f"  Radio   : {self.radius_m:.0f} m",
            f"  BBox    : [{self.bbox.min_lat:.5f}, {self.bbox.min_lon:.5f},"
            f" {self.bbox.max_lat:.5f}, {self.bbox.max_lon:.5f}]",
        ]
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# validate_lat_lon
# ---------------------------------------------------------------------------

def validate_lat_lon(lat: float, lon: float) -> None:
    """Lanza ValueError si lat o lon están fuera de rango WGS84."""
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(
            f"Latitud fuera del rango WGS84 [-90, 90]: {lat}"
        )
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(
            f"Longitud fuera del rango WGS84 [-180, 180]: {lon}"
        )


# ---------------------------------------------------------------------------
# parse_wgs84_coordinate
# ---------------------------------------------------------------------------

def _try_parse_two_floats(a: str, b: str) -> tuple[float, float] | None:
    try:
        return float(a.strip()), float(b.strip())
    except (ValueError, AttributeError):
        return None


def parse_wgs84_coordinate(value) -> GeoPoint:
    """Parsea un valor de coordenada WGS84 en múltiples formatos y devuelve GeoPoint.

    Formatos aceptados:
        "28.9773, -13.5395"           — string con coma
        "28.9773 -13.5395"            — string con espacio
        ["28.9773", "-13.5395"]       — lista de dos strings
        [28.9773, -13.5395]           — lista de dos floats
        {"lat": 28.9773, "lon": -13.5395}
        {"latitude": 28.9773, "longitude": -13.5395}

    Raises:
        ValueError: Si el formato no es reconocido o las coordenadas están fuera de rango.
    """
    lat: float | None = None
    lon: float | None = None

    # Formato dict
    if isinstance(value, dict):
        raw_lat = value.get("lat") or value.get("latitude") or value.get("latitud")
        raw_lon = value.get("lon") or value.get("longitude") or value.get("longitud")
        if raw_lat is None or raw_lon is None:
            raise ValueError(
                f"Dict de coordenadas sin claves lat/lon reconocidas: {value!r}"
            )
        try:
            lat, lon = float(raw_lat), float(raw_lon)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"No se pudo convertir a float: {value!r}") from exc

    # Formato lista o tupla
    elif isinstance(value, (list, tuple)):
        if len(value) < 2:
            raise ValueError(
                f"Lista de coordenadas debe tener al menos 2 elementos: {value!r}"
            )
        parsed = _try_parse_two_floats(str(value[0]), str(value[1]))
        if parsed is None:
            raise ValueError(f"No se pudo parsear lista de coordenadas: {value!r}")
        lat, lon = parsed

    # Formato string
    elif isinstance(value, str):
        s = value.strip()
        # Intentar con coma
        if "," in s:
            parts = s.split(",", 1)
            parsed = _try_parse_two_floats(parts[0], parts[1])
            if parsed is not None:
                lat, lon = parsed
        # Intentar con espacio (puede haber signo negativo)
        if lat is None:
            parts = s.split()
            if len(parts) >= 2:
                parsed = _try_parse_two_floats(parts[0], parts[1])
                if parsed is not None:
                    lat, lon = parsed
        if lat is None:
            raise ValueError(
                f"No se pudo parsear cadena de coordenadas: {value!r}. "
                "Formatos aceptados: 'lat, lon' o 'lat lon'."
            )

    else:
        raise ValueError(
            f"Tipo de valor de coordenada no reconocido: {type(value).__name__!r}. "
            "Tipos aceptados: str, list, dict."
        )

    validate_lat_lon(lat, lon)
    return GeoPoint(lat=lat, lon=lon)


# ---------------------------------------------------------------------------
# haversine_distance_km
# ---------------------------------------------------------------------------

def haversine_distance_km(point_a: GeoPoint, point_b: GeoPoint) -> float:
    """Distancia aproximada en km entre dos puntos WGS84 (fórmula haversine).

    Implementación independiente de CL-02. Misma fórmula, interfaz con GeoPoint.
    """
    R = 6_371.0
    lat1r, lon1r = math.radians(point_a.lat), math.radians(point_a.lon)
    lat2r, lon2r = math.radians(point_b.lat), math.radians(point_b.lon)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


# ---------------------------------------------------------------------------
# bounding_box_around_point
# ---------------------------------------------------------------------------

def bounding_box_around_point(point: GeoPoint, radius_m: float) -> BoundingBox:
    """Genera un bounding box aproximado alrededor de un punto WGS84.

    Aproximación:
        - 1° latitud ≈ 111 320 m (constante)
        - 1° longitud ≈ 111 320 · cos(lat) m (variable con latitud)

    Válida para distancias de trabajo EIA (1 m a 50 km) en España/Canarias.
    No es una transformación geodésica de precisión.

    Args:
        point:    Centro del bbox.
        radius_m: Radio en metros. Debe ser > 0.

    Raises:
        ValueError: Si radius_m <= 0.
    """
    if radius_m <= 0:
        raise ValueError(f"radius_m debe ser mayor que 0, recibido: {radius_m}")

    lat_delta = radius_m / _LAT_DEG_TO_M
    cos_lat = math.cos(math.radians(point.lat))
    lon_delta = radius_m / (_LAT_DEG_TO_M * max(cos_lat, 1e-9))

    min_lat = max(point.lat - lat_delta, -90.0)
    max_lat = min(point.lat + lat_delta, 90.0)
    min_lon = max(point.lon - lon_delta, -180.0)
    max_lon = min(point.lon + lon_delta, 180.0)

    bbox = BoundingBox(
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )
    bbox.validate()
    return bbox


# ---------------------------------------------------------------------------
# build_map_extent
# ---------------------------------------------------------------------------

def _scale_hint_for_radius(radius_m: float) -> str:
    if radius_m <= 500.0:
        return "detalle_parcela"
    if radius_m <= 2_000.0:
        return "emplazamiento"
    if radius_m <= 10_000.0:
        return "entorno"
    return "situacion_general"


def build_map_extent(
    point: GeoPoint,
    radius_m: float,
    scale_hint: str | None = None,
) -> MapExtent:
    """Construye un MapExtent a partir de un punto y un radio en metros.

    Args:
        point:      Centro del extent.
        radius_m:   Radio en metros (> 0).
        scale_hint: Etiqueta de escala. Si None, se asigna automáticamente.

    Raises:
        ValueError: Si radius_m <= 0.
    """
    bbox = bounding_box_around_point(point, radius_m)
    hint = scale_hint if scale_hint is not None else _scale_hint_for_radius(radius_m)
    warnings: list[str] = []
    notes: list[str] = []

    if point.status in _UNRELIABLE_STATUSES:
        warnings.append(
            f"El punto central tiene estado '{point.status}'. "
            "Las coordenadas no están confirmadas — el extent debe revisarse "
            "cuando las coordenadas sean VERIFICADO o DECLARADO."
        )

    return MapExtent(
        center=point,
        bbox=bbox,
        radius_m=radius_m,
        scale_hint=hint,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# extract_geopoint_from_phase2
# ---------------------------------------------------------------------------

def extract_geopoint_from_phase2(phase2_data: dict) -> GeoPoint:
    """Extrae el GeoPoint principal de un phase2_result cargado.

    Busca la primera coordenada parseable en ``object_scope.coordenadas_wgs84``.

    Formats accepted in coordenadas_wgs84:
        ["28.9773, -13.5395"]
        ["28.9773", "-13.5395"]
        [{"lat": 28.9773, "lon": -13.5395}]
        [28.9773, -13.5395]   (mixto con la función parse_wgs84_coordinate)

    Raises:
        ValueError: Si no hay coordenadas o no se pueden parsear.
    """
    object_scope: dict = phase2_data.get("object_scope") or {}
    coords: list = object_scope.get("coordenadas_wgs84") or []

    if not coords:
        raise ValueError(
            "No se encontraron coordenadas WGS84 en 'object_scope.coordenadas_wgs84'. "
            "Ejecute Fase 2 y declare las coordenadas del emplazamiento."
        )

    # Intentar parsear el primer elemento directamente
    first = coords[0]
    try:
        point = parse_wgs84_coordinate(first)
        point.source = "phase2_result"
        return point
    except (ValueError, TypeError):
        pass

    # Fallback: si el primer elemento es un string sin coma y hay un segundo elemento,
    # tratar los dos primeros como lat/lon separados
    if len(coords) >= 2:
        try:
            point = parse_wgs84_coordinate([str(coords[0]), str(coords[1])])
            point.source = "phase2_result"
            return point
        except (ValueError, TypeError):
            pass

    raise ValueError(
        f"No se pudo extraer coordenadas WGS84 de coordenadas_wgs84: {coords!r}. "
        "Formatos aceptados: ['lat, lon'], ['lat', 'lon'], [{'lat': ..., 'lon': ...}]."
    )


# ---------------------------------------------------------------------------
# build_standard_map_extents
# ---------------------------------------------------------------------------

def build_standard_map_extents(point: GeoPoint) -> "dict[str, MapExtent]":
    """Genera los 5 extents cartográficos estándar para un emplazamiento EIA.

    Extents generados:
        "detalle_parcela"    → 250 m
        "emplazamiento"      → 1 000 m
        "entorno_500m"       → 500 m
        "entorno_2000m"      → 2 000 m
        "situacion_general"  → 25 000 m

    No genera imágenes. No escribe archivos.
    """
    return {
        name: build_map_extent(point, radius_m)
        for name, radius_m in _STANDARD_RADII.items()
    }
