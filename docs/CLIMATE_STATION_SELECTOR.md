# CLIMATE_STATION_SELECTOR — CL-02

Módulo Python puro para selección de estación climática de referencia.

No llama a AEMET ni a ningún servicio externo. No descarga normales. No calcula Köppen ni Martonne. No genera climogramas. No escribe archivos.

## Importación

```python
from eia_agent.core.climate_station_selector import (
    ClimateStation,
    StationSelection,
    haversine_km,
    parse_dms_aemet,
    parse_station_from_aemet_dict,
    find_nearest_station,
    load_stations_from_json,
    select_station_for_object_scope,
)
```

---

## Clases de datos

### `ClimateStation`

Estación climatológica de referencia.

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `station_id` | `str` | Sí | Indicativo AEMET u otro identificador único |
| `name` | `str` | Sí | Nombre legible de la estación |
| `latitude` | `float` | Sí | Latitud WGS84 en grados decimales |
| `longitude` | `float` | Sí | Longitud WGS84 en grados decimales |
| `altitude_m` | `float \| None` | No | Altitud en metros |
| `province` | `str \| None` | No | Provincia o región |
| `island` | `str \| None` | No | Isla (Canarias) |
| `has_normals` | `bool` | No | Si tiene normales 1981-2010 (defecto: `True`) |
| `source` | `str \| None` | No | Origen del dato |

**Métodos:**
- `to_dict() -> dict` — Serializa a dict con todas las claves.
- `from_dict(data: dict) -> ClimateStation` — Construye desde formato serializado propio (`station_id`).

---

### `StationSelection`

Resultado de la selección de estación.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `selected` | `ClimateStation \| None` | Estación seleccionada (None si NO_DISPONIBLE) |
| `distance_km` | `float \| None` | Distancia en km al punto de proyecto |
| `status` | `str` | `OPTIMA` / `ACEPTABLE` / `LEJANA` / `NO_DISPONIBLE` |
| `warnings` | `list[str]` | Avisos (distancia excesiva, estaciones descartadas) |
| `notes` | `list[str]` | Notas informativas |
| `candidates_considered` | `int` | Número de candidatas evaluadas |

**Métodos:**
- `to_dict() -> dict`
- `summary() -> str` — Texto legible para consola/log.

**Umbrales de estado:**

| Estado | Condición |
|--------|-----------|
| `OPTIMA` | distancia ≤ 15 km |
| `ACEPTABLE` | 15 km < distancia ≤ 25 km |
| `LEJANA` | distancia > 25 km (genera warning) |
| `NO_DISPONIBLE` | sin candidatas válidas |

---

## Funciones

### `haversine_km`

```python
haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float
```

Distancia aproximada en km entre dos coordenadas WGS84 (fórmula haversine). Radio terrestre: 6 371 km.

---

### `parse_dms_aemet`

```python
parse_dms_aemet(s: str) -> float | None
```

Parsea el formato DMS de AEMET OpenData a grados decimales.

**Formato AEMET:**
- Latitud: `DDMMSS[N|S]` — 6 dígitos + hemisferio
- Longitud: `DDDMMSS[E|W]` — 7 dígitos + hemisferio

**Ejemplos:**

| Entrada | Resultado |
|---------|-----------|
| `"275545N"` | `27.9292°` (27° 55' 45" N) |
| `"0152241W"` | `-15.3781°` (15° 22' 41" W) |
| `"000000N"` | `0.0°` |
| `"275545S"` | `-27.9292°` |

Devuelve `None` si el formato no es reconocible.

---

### `parse_station_from_aemet_dict`

```python
parse_station_from_aemet_dict(data: dict) -> ClimateStation
```

Convierte un dict procedente de AEMET OpenData o fixture a `ClimateStation`.

**Claves aceptadas:**

| Campo | Claves buscadas (en orden) |
|-------|---------------------------|
| `station_id` | `indicativo`, `station_id`, `id`, `identificativo` |
| `name` | `nombre`, `name` (defecto: station_id) |
| `latitude` | `latitud`, `latitude` |
| `longitude` | `longitud`, `longitude` |
| `altitude_m` | `altitud`, `altitude`, `altitude_m` |
| `province` | `provincia`, `province` |
| `island` | `isla`, `island` |

Las coordenadas pueden ser float decimal o string DMS de AEMET. Se usa iteración explícita por clave para evitar el bug de falsy-zero cuando lat/lon = 0.0.

**Raises:** `ValueError` si falta `station_id`, `latitude` o `longitude`, o si no se puede parsear lat/lon.

---

### `find_nearest_station`

```python
find_nearest_station(
    lat: float,
    lon: float,
    stations: list[ClimateStation],
    require_normals: bool = True,
) -> StationSelection
```

Selecciona la estación más cercana al punto dado.

- Si `require_normals=True` (defecto), descarta estaciones con `has_normals=False` y añade warning con el número descartado.
- Si todas las candidatas son descartadas, devuelve `NO_DISPONIBLE` con warning específico.
- Si la lista está vacía, devuelve `NO_DISPONIBLE`.

**Raises:** `ValueError` si `lat` o `lon` están fuera de rango (`[-90, 90]` / `[-180, 180]`).

---

### `load_stations_from_json`

```python
load_stations_from_json(path: str | Path) -> list[ClimateStation]
```

Carga una lista de estaciones desde un archivo JSON.

Acepta dos formatos:
- Formato serializado de `ClimateStation` (clave `station_id`) → usa `ClimateStation.from_dict()`
- Formato de respuesta AEMET OpenData (clave `indicativo`) → usa `parse_station_from_aemet_dict()`

**Raises:**
- `FileNotFoundError` — si el archivo no existe.
- `ValueError` — si el JSON es inválido o no es una lista.

---

### `select_station_for_object_scope`

```python
select_station_for_object_scope(
    scope: ObjectScope | dict,
    stations: list[ClimateStation],
) -> StationSelection
```

Selecciona la estación más próxima a partir del `ObjectScope` del expediente.

Toma la primera coordenada WGS84 válida del campo `coordenadas_wgs84` (lista de strings `"lat, lon"`). No modifica el scope.

Soporta duck typing:
- `ObjectScope` (dataclass) → accede via `scope.coordenadas_wgs84`
- `dict` → accede via `scope.get("coordenadas_wgs84")`

Si no hay coordenadas válidas, devuelve `NO_DISPONIBLE` con instrucción de ejecutar Fase 2.

---

## Formato de archivo JSON de estaciones

### Formato serializado (ClimateStation)

```json
[
  {
    "station_id": "C449C",
    "name": "Lanzarote/Arrecife",
    "latitude": 28.9603,
    "longitude": -13.6033,
    "altitude_m": 14.0,
    "province": "Las Palmas",
    "island": "Lanzarote",
    "has_normals": true,
    "source": "AEMET"
  }
]
```

### Formato AEMET OpenData

```json
[
  {
    "indicativo": "C449C",
    "nombre": "LANZAROTE AEROPUERTO",
    "latitud": "285740N",
    "longitud": "0134549W",
    "altitud": "14",
    "provincia": "LAS PALMAS"
  }
]
```

---

## Uso básico

```python
from eia_agent.core.climate_station_selector import (
    load_stations_from_json, find_nearest_station,
)

# Cargar candidatas
stations = load_stations_from_json("config/estaciones_canarias.json")

# Seleccionar para un proyecto en Lanzarote
result = find_nearest_station(28.95, -13.60, stations)
print(result.summary())
# Estacion seleccionada: Lanzarote/Arrecife (C449C)
#   Distancia    : 3.2 km
#   Estado       : OPTIMA
#   Candidatas   : 12
```

```python
# Desde un ObjectScope de expediente
from eia_agent.core.climate_station_selector import select_station_for_object_scope

result = select_station_for_object_scope(scope, stations)
if result.status == "NO_DISPONIBLE":
    print("Sin coordenadas — ejecutar Fase 2")
else:
    print(f"Estación: {result.selected.name}, {result.distance_km:.1f} km ({result.status})")
```

---

## Tests

```bash
# Suite completa CL-02
venv\Scripts\python -m pytest tests/test_climate_station_selector.py -v

# Suite completa del proyecto
venv\Scripts\python -m pytest tests/
```

78 tests OK. 0 fallos. Sin dependencias externas. Sin llamadas a AEMET.

---

## Dependencias

- Python ≥ 3.11 (usa `float | None` syntax)
- `math` (stdlib) — haversine
- `json`, `pathlib` (stdlib) — carga de archivos
- `dataclasses` (stdlib) — ClimateStation, StationSelection

Sin dependencias de terceros.

---

## Lo que NO hace este módulo

- No llama a AEMET ni a ningún servicio HTTP (eso es CL-01).
- No descarga normales climatológicas (eso es CL-01).
- No calcula Köppen ni Martonne (eso es CL-03).
- No genera climogramas (eso es CL-04).
- No escribe ningún archivo en disco.
- No modifica el ObjectScope ni ningún expediente.
