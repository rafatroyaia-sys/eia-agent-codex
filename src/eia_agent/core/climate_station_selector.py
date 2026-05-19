"""
climate_station_selector -- CL-02
Selector de estación climática de referencia.

Dados unos coordenadas WGS84 y una lista de estaciones candidatas, devuelve
la estación más próxima con sus metadatos de selección.

No llama a AEMET ni a ningún servicio externo.
No descarga normales climatológicas (CL-01).
No calcula Köppen ni Martonne (CL-03).
No genera climogramas (CL-04).
No escribe archivos.

Uso:
    from eia_agent.core.climate_station_selector import (
        ClimateStation, find_nearest_station, load_stations_from_json,
    )

    stations = load_stations_from_json("config/estaciones_canarias.json")
    result = find_nearest_station(28.95, -13.60, stations)
    print(result.summary())
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eia_agent.core.object_scope_builder import ObjectScope

# ---------------------------------------------------------------------------
# Umbrales de distancia
# ---------------------------------------------------------------------------

_DIST_OPTIMA_KM: float = 15.0
_DIST_ACEPTABLE_KM: float = 25.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClimateStation:
    """Estación climatológica de referencia."""
    station_id: str
    name: str
    latitude: float
    longitude: float
    altitude_m: float | None = None
    province: str | None = None
    island: str | None = None
    has_normals: bool = True
    source: str | None = None

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "province": self.province,
            "island": self.island,
            "has_normals": self.has_normals,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClimateStation":
        """Construye ClimateStation desde el formato serializado propio (clave 'station_id')."""
        return cls(
            station_id=data["station_id"],
            name=data["name"],
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            altitude_m=data.get("altitude_m"),
            province=data.get("province"),
            island=data.get("island"),
            has_normals=bool(data.get("has_normals", True)),
            source=data.get("source"),
        )


@dataclass
class StationSelection:
    """Resultado de la selección de estación climática."""
    selected: ClimateStation | None
    distance_km: float | None
    status: str          # OPTIMA / ACEPTABLE / LEJANA / NO_DISPONIBLE
    warnings: list[str]
    notes: list[str]
    candidates_considered: int

    def to_dict(self) -> dict:
        return {
            "selected": self.selected.to_dict() if self.selected else None,
            "distance_km": self.distance_km,
            "status": self.status,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "candidates_considered": self.candidates_considered,
        }

    def summary(self) -> str:
        if self.status == "NO_DISPONIBLE":
            parts = ["Seleccion de estacion: NO_DISPONIBLE — sin candidatas validas."]
            for w in self.warnings:
                parts.append(f"  AVISO: {w}")
            return "\n".join(parts)
        assert self.selected is not None
        lines = [
            f"Estacion seleccionada: {self.selected.name} ({self.selected.station_id})",
            f"  Distancia    : {self.distance_km:.1f} km",
            f"  Estado       : {self.status}",
            f"  Candidatas   : {self.candidates_considered}",
        ]
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia aproximada en km entre dos coordenadas WGS84 (fórmula haversine).

    Args:
        lat1, lon1: Coordenada de origen en grados decimales.
        lat2, lon2: Coordenada de destino en grados decimales.

    Returns:
        Distancia en kilómetros (>= 0).
    """
    R = 6371.0  # radio medio de la Tierra en km
    lat1r, lon1r, lat2r, lon2r = (math.radians(x) for x in (lat1, lon1, lat2, lon2))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))  # min evita error de dominio por coma flotante


# ---------------------------------------------------------------------------
# Helpers de parseo de coordenadas
# ---------------------------------------------------------------------------

def parse_dms_aemet(s: str) -> float | None:
    """Parsea el formato DMS de AEMET OpenData a grados decimales.

    AEMET codifica coordenadas como:
    - Latitud:  DDMMSS[N|S]  (6 dígitos + hemisferio)
    - Longitud: DDDMMSS[E|W] (7 dígitos + hemisferio)

    Ejemplos:
        "275545N"  → 27.9292° (27° 55' 45" N)
        "0152241W" → -15.3781° (15° 22' 41" W)

    Returns:
        Grados decimales o None si el formato no es reconocible.
    """
    s = s.strip().upper()
    if not s or s[-1] not in "NSEW":
        return None
    direction = s[-1]
    digits = s[:-1]
    if not digits.isdigit():
        return None
    n = len(digits)
    if n == 6:
        d, m, sec = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    elif n == 7:
        d, m, sec = int(digits[0:3]), int(digits[3:5]), int(digits[5:7])
    else:
        return None
    decimal = d + m / 60.0 + sec / 3600.0
    if direction in "SW":
        decimal = -decimal
    return decimal


def _parse_coord_value(val: "str | float | int") -> float | None:
    """Convierte un valor de coordenada (float, decimal string o DMS de AEMET) a float."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    try:
        return float(s)
    except ValueError:
        pass
    return parse_dms_aemet(s)


def _parse_wgs84_pair(coord_str: str) -> tuple[float, float] | None:
    """Parsea 'lat, lon' de una cadena WGS84. Devuelve None si falla."""
    parts = str(coord_str).replace(" ", "").split(",")
    if len(parts) >= 2:
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            pass
    return None


# ---------------------------------------------------------------------------
# parse_station_from_aemet_dict
# ---------------------------------------------------------------------------

def parse_station_from_aemet_dict(data: dict) -> ClimateStation:
    """Convierte un dict procedente de AEMET OpenData o fixture a ClimateStation.

    Acepta claves en español (indicativo/nombre/latitud/longitud) o en inglés
    (station_id/name/latitude/longitude).
    Las coordenadas pueden ser float decimal o DMS de AEMET ("275545N").

    Raises:
        ValueError: si faltan campos esenciales o no se puede parsear lat/lon.
    """
    # station_id — busca en orden de preferencia
    station_id: str | None = None
    for key in ("indicativo", "station_id", "id", "identificativo"):
        if key in data:
            station_id = str(data[key]).strip() if data[key] is not None else None
            break
    if not station_id:
        raise ValueError(
            "Campo de identificador de estación no encontrado en el dict. "
            "Esperado: 'indicativo', 'station_id' o 'id'."
        )

    # name
    name: str = str(
        data.get("nombre") or data.get("name") or station_id
    ).strip()

    # latitude
    lat_raw = None
    for key in ("latitud", "latitude"):
        if key in data:
            lat_raw = data[key]
            break
    if lat_raw is None:
        raise ValueError(
            f"Latitud no encontrada para estación '{station_id}'. "
            "Esperado: 'latitud' o 'latitude'."
        )
    lat = _parse_coord_value(lat_raw)
    if lat is None:
        raise ValueError(
            f"No se pudo parsear la latitud '{lat_raw}' para estación '{station_id}'."
        )

    # longitude
    lon_raw = None
    for key in ("longitud", "longitude"):
        if key in data:
            lon_raw = data[key]
            break
    if lon_raw is None:
        raise ValueError(
            f"Longitud no encontrada para estación '{station_id}'. "
            "Esperado: 'longitud' o 'longitude'."
        )
    lon = _parse_coord_value(lon_raw)
    if lon is None:
        raise ValueError(
            f"No se pudo parsear la longitud '{lon_raw}' para estación '{station_id}'."
        )

    # altitude (optional)
    altitude_m: float | None = None
    for key in ("altitud", "altitude", "altitude_m"):
        if key in data and data[key] is not None:
            try:
                altitude_m = float(str(data[key]))
            except (ValueError, TypeError):
                altitude_m = None
            break

    return ClimateStation(
        station_id=station_id,
        name=name,
        latitude=lat,
        longitude=lon,
        altitude_m=altitude_m,
        province=data.get("provincia") or data.get("province") or None,
        island=data.get("isla") or data.get("island") or None,
        has_normals=bool(data.get("has_normals", True)),
        source=data.get("source") or None,
    )


# ---------------------------------------------------------------------------
# find_nearest_station
# ---------------------------------------------------------------------------

def find_nearest_station(
    lat: float,
    lon: float,
    stations: list[ClimateStation],
    require_normals: bool = True,
) -> StationSelection:
    """Selecciona la estación climática más cercana a las coordenadas dadas.

    No hace llamadas externas.

    Criterios de estado:
    - OPTIMA      : distancia <= 15 km
    - ACEPTABLE   : distancia > 15 km y <= 25 km
    - LEJANA      : distancia > 25 km
    - NO_DISPONIBLE: sin candidatas válidas

    Args:
        lat:             Latitud WGS84 del proyecto (-90 a 90).
        lon:             Longitud WGS84 del proyecto (-180 a 180).
        stations:        Lista de estaciones candidatas.
        require_normals: Si True (por defecto), filtra estaciones sin normales 1981-2010.

    Returns:
        StationSelection con la estación más cercana y metadatos de selección.

    Raises:
        ValueError: si lat o lon están fuera de rango.
    """
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitud fuera de rango [-90, 90]: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitud fuera de rango [-180, 180]: {lon}")

    warnings: list[str] = []
    notes: list[str] = []

    # Filtrar por disponibilidad de normales
    without_normals = [s for s in stations if not s.has_normals]
    candidates = [s for s in stations if not require_normals or s.has_normals]

    if require_normals and without_normals:
        n = len(without_normals)
        warnings.append(
            f"{n} estacion(es) descartada(s) por no tener normales climatologicas 1981-2010."
        )

    if not candidates:
        if stations and require_normals and without_normals:
            warnings.append(
                "Todas las estaciones candidatas fueron descartadas por falta de normales. "
                "Considere require_normals=False o amplíe el área de búsqueda."
            )
        else:
            warnings.append("No hay estaciones candidatas en la lista proporcionada.")
        return StationSelection(
            selected=None,
            distance_km=None,
            status="NO_DISPONIBLE",
            warnings=warnings,
            notes=notes,
            candidates_considered=0,
        )

    # Calcular distancias y seleccionar la menor
    best = candidates[0]
    best_dist = haversine_km(lat, lon, best.latitude, best.longitude)

    for station in candidates[1:]:
        dist = haversine_km(lat, lon, station.latitude, station.longitude)
        if dist < best_dist:
            best = station
            best_dist = dist

    # Determinar estado
    if best_dist <= _DIST_OPTIMA_KM:
        status = "OPTIMA"
    elif best_dist <= _DIST_ACEPTABLE_KM:
        status = "ACEPTABLE"
    else:
        status = "LEJANA"
        warnings.append(
            f"Estacion mas cercana '{best.name}' ({best.station_id}) a {best_dist:.1f} km. "
            "Distancia >25 km — verificar representatividad climatica para el emplazamiento."
        )

    return StationSelection(
        selected=best,
        distance_km=round(best_dist, 3),
        status=status,
        warnings=warnings,
        notes=notes,
        candidates_considered=len(candidates),
    )


# ---------------------------------------------------------------------------
# load_stations_from_json
# ---------------------------------------------------------------------------

def load_stations_from_json(path: "str | Path") -> list[ClimateStation]:
    """Carga una lista de estaciones desde un archivo JSON.

    Acepta tanto el formato serializado de ClimateStation (clave 'station_id')
    como el formato de respuesta de AEMET OpenData (clave 'indicativo').

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON es inválido o no es una lista.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo de estaciones no encontrado: {p}")

    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido en {p}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(
            f"El archivo {p} no contiene una lista de estaciones "
            f"(tipo encontrado: {type(data).__name__})."
        )

    stations: list[ClimateStation] = []
    for item in data:
        if "station_id" in item:
            stations.append(ClimateStation.from_dict(item))
        else:
            stations.append(parse_station_from_aemet_dict(item))

    return stations


# ---------------------------------------------------------------------------
# select_station_for_object_scope
# ---------------------------------------------------------------------------

def select_station_for_object_scope(
    scope: "ObjectScope",
    stations: list[ClimateStation],
) -> StationSelection:
    """Selecciona la estación más próxima a partir del ObjectScope del expediente.

    Toma la primera coordenada WGS84 válida del ObjectScope.
    No modifica el ObjectScope.

    Args:
        scope:    ObjectScope con campo coordenadas_wgs84 (lista de strings).
        stations: Lista de estaciones candidatas.

    Returns:
        StationSelection. Si no hay coordenadas válidas en el scope: NO_DISPONIBLE.
    """
    # Acceso tolerante: dataclass ObjectScope o dict (ambos usan coordenadas_wgs84)
    if hasattr(scope, "coordenadas_wgs84"):
        coords_list: list = scope.coordenadas_wgs84 or []
    elif isinstance(scope, dict):
        coords_list = scope.get("coordenadas_wgs84") or []
    else:
        coords_list = []

    for coord_str in coords_list:
        pair = _parse_wgs84_pair(str(coord_str))
        if pair is None:
            continue
        lat, lon = pair
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return find_nearest_station(lat, lon, stations)

    return StationSelection(
        selected=None,
        distance_km=None,
        status="NO_DISPONIBLE",
        warnings=[
            "No se encontraron coordenadas WGS84 validas en el ObjectScope. "
            "Ejecute Fase 2 y declare las coordenadas del emplazamiento."
        ],
        notes=["Seleccion de estacion no posible sin coordenadas validas."],
        candidates_considered=0,
    )
