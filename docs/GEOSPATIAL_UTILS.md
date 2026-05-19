# GEOSPATIAL_UTILS — CA-09

Módulo `src/eia_agent/core/geospatial_utils.py`  
Núcleo geoespacial offline para cartografía EIA. Provee tipos y utilidades geoespaciales básicas reutilizables por los módulos CA-xx que generarán mapas.

---

## Qué hace

- Define los tipos `GeoPoint`, `BoundingBox` y `MapExtent` usados en toda la capa cartográfica.
- Valida coordenadas WGS84 (latitud [-90,90], longitud [-180,180]).
- Parsea coordenadas en múltiples formatos (string, lista, dict).
- Calcula distancias haversine entre dos `GeoPoint`.
- Genera bounding boxes aproximados alrededor de un punto dado un radio en metros.
- Construye extents cartográficos (`MapExtent`) con escala sugerida y avisos de fiabilidad.
- Genera los 5 extents estándar para un emplazamiento EIA.
- Extrae el `GeoPoint` principal de un `phase2_result.json`.

## Qué NO hace

- **No genera imágenes ni mapas** — eso es CA-02 a CA-05.
- **No llama a Mapbox** ni a ningún servicio de tiles.
- **No consulta WMS/WMTS** ni servicios cartográficos remotos.
- **No consulta Catastro** ni ninguna API de parcelas.
- **No verifica coordenadas** contra servicios externos.
- **No modifica el expediente piloto**.
- **No usa IA**.

---

## Relación con otros módulos

| Módulo | Rol | Relación |
|--------|-----|----------|
| CA-02 a CA-05 | Generadores de cartografía | Consumirán `GeoPoint`, `MapExtent` de CA-09 |
| CL-06 `phase4_climate_pipeline.py` | Pipeline climático | Usa su propia función `extract_wgs84_from_phase2`; CA-09 provee alternativa tipada |
| CA-08 `phase4_precheck.py` | Precheck de Fase 4 | Prerequisito recomendado antes de generar extents |

---

## Tipos principales

### GeoPoint

```python
@dataclass
class GeoPoint:
    lat: float
    lon: float
    source: str | None = None          # Procedencia del dato
    status: str = "DECLARADO"          # DECLARADO / ESTIMADO / VERIFICADO / PROVISIONAL / NO_DECLARADO
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None: ...    # Lanza ValueError si coords o status inválidos
    def to_dict(self) -> dict: ...
    @classmethod def from_dict(cls, data: dict) -> "GeoPoint": ...
    def as_tuple(self) -> tuple[float, float]: ...  # (lat, lon)
```

**Estados válidos**: `DECLARADO`, `ESTIMADO`, `VERIFICADO`, `PROVISIONAL`, `NO_DECLARADO`.  
**Estados no fiables** (generan aviso en extents): `ESTIMADO`, `PROVISIONAL`, `NO_DECLARADO`.

### BoundingBox

```python
@dataclass
class BoundingBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def validate(self) -> None: ...
    def to_dict(self) -> dict: ...
    def width_degrees(self) -> float: ...
    def height_degrees(self) -> float: ...
```

### MapExtent

```python
@dataclass
class MapExtent:
    center: GeoPoint
    bbox: BoundingBox
    radius_m: float
    scale_hint: str
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict: ...
    def summary(self) -> str: ...
```

---

## API de funciones

### validate_lat_lon

```python
validate_lat_lon(lat: float, lon: float) -> None
```

Lanza `ValueError` si `lat` está fuera de [-90, 90] o `lon` fuera de [-180, 180].

---

### parse_wgs84_coordinate

```python
parse_wgs84_coordinate(value) -> GeoPoint
```

Parsea coordenadas en múltiples formatos:

| Formato | Ejemplo |
|---------|---------|
| String con coma | `"28.9773, -13.5395"` |
| String con espacio | `"28.9773 -13.5395"` |
| Lista de strings | `["28.9773", "-13.5395"]` |
| Lista de floats | `[28.9773, -13.5395]` |
| Dict lat/lon | `{"lat": 28.9773, "lon": -13.5395}` |
| Dict latitude/longitude | `{"latitude": 28.9773, "longitude": -13.5395}` |
| Dict latitud/longitud | `{"latitud": 28.9773, "longitud": -13.5395}` |

Lanza `ValueError` si el formato no es reconocido o las coordenadas están fuera de rango.

---

### haversine_distance_km

```python
haversine_distance_km(point_a: GeoPoint, point_b: GeoPoint) -> float
```

Distancia aproximada en km entre dos puntos WGS84 (fórmula haversine). Interfaz con `GeoPoint` — independiente de `haversine_km` de CL-02 que usa floats directos.

---

### bounding_box_around_point

```python
bounding_box_around_point(point: GeoPoint, radius_m: float) -> BoundingBox
```

Genera un bounding box aproximado alrededor de un punto.

**Aproximación**:
- `1° latitud ≈ 111 320 m` (constante)
- `1° longitud ≈ 111 320 · cos(lat) m` (varía con latitud)
- Protección contra división por cero cerca de los polos: `max(cos_lat, 1e-9)`

Válida para distancias de trabajo EIA (1 m a 50 km) en España/Canarias. No es una transformación geodésica de precisión.

Lanza `ValueError` si `radius_m <= 0`.

---

### build_map_extent

```python
build_map_extent(
    point: GeoPoint,
    radius_m: float,
    scale_hint: str | None = None,
) -> MapExtent
```

Construye un `MapExtent` con bbox, escala sugerida y avisos de fiabilidad.

**Escala automática** (si `scale_hint=None`):

| Radio | scale_hint |
|-------|------------|
| ≤ 500 m | `detalle_parcela` |
| ≤ 2 000 m | `emplazamiento` |
| ≤ 10 000 m | `entorno` |
| > 10 000 m | `situacion_general` |

**Aviso automático** si `point.status` es `ESTIMADO`, `PROVISIONAL` o `NO_DECLARADO`: el extent debe revisarse cuando las coordenadas sean `VERIFICADO` o `DECLARADO`.

---

### extract_geopoint_from_phase2

```python
extract_geopoint_from_phase2(phase2_data: dict) -> GeoPoint
```

Extrae el `GeoPoint` principal de un `phase2_result` cargado. Busca en `object_scope.coordenadas_wgs84` y parsea el primer elemento.

Establece `point.source = "phase2_result"`.

Lanza `ValueError` si no hay coordenadas o no se pueden parsear.

---

### build_standard_map_extents

```python
build_standard_map_extents(point: GeoPoint) -> dict[str, MapExtent]
```

Genera los 5 extents cartográficos estándar para un emplazamiento EIA:

| Clave | Radio |
|-------|-------|
| `detalle_parcela` | 250 m |
| `emplazamiento` | 1 000 m |
| `entorno_500m` | 500 m |
| `entorno_2000m` | 2 000 m |
| `situacion_general` | 25 000 m |

No genera imágenes. No escribe archivos.

---

## Uso típico

```python
from eia_agent.core.geospatial_utils import (
    GeoPoint, build_map_extent, build_standard_map_extents,
    extract_geopoint_from_phase2,
)

# Desde phase2_result.json cargado
with open("control_interno/phase2_result.json") as f:
    phase2 = json.load(f)

point = extract_geopoint_from_phase2(phase2)
extents = build_standard_map_extents(point)
print(extents["emplazamiento"].summary())

# O directamente
point = GeoPoint(lat=28.9773, lon=-13.5395, source="manual", status="DECLARADO")
ext = build_map_extent(point, 1000.0)
print(ext.summary())
```

---

## Limitaciones conocidas

1. **Aproximación plana**: `bounding_box_around_point` usa una aproximación esférica, no una transformación geodésica de precisión. Suficiente para EIA (1 m a 50 km en Canarias), pero no apta para trabajo topográfico de precisión.
2. **Un único CRS**: trabaja siempre en WGS84/EPSG:4326. La conversión a REGCAN95/UTM28N para medición y control interno corresponde a módulos CA-xx de nivel superior.
3. **Sin validación topológica avanzada**: no verifica si el punto cae en tierra, mar, o dentro de los límites de una isla específica.

---

## Tests

`tests/test_geospatial_utils.py` — 96 tests en 8 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestValidateLatLon` | 7 | Extremos válidos, latitud/longitud fuera de rango, mensaje de error |
| `TestGeoPoint` | 10 | Defaults, validación, to_dict, from_dict, as_tuple, notas aisladas |
| `TestBoundingBox` | 9 | Validación, to_dict, width/height |
| `TestParseWgs84Coordinate` | 16 | Todos los formatos, errores, tipo de retorno |
| `TestHaversineDistanceKm` | 5 | Punto idéntico=0, Lanzarote-Gran Canaria, simetría, 1°≈111km |
| `TestBoundingBoxAroundPoint` | 8 | Radio≈exacto, radio cero/negativo, valid bbox, Ecuador |
| `TestBuildMapExtent` | 19 | Scale hints automáticos, override, avisos por status, to_dict, summary |
| `TestExtractGeopointFromPhase2` + `TestBuildStandardMapExtents` | 22 | Formatos phase2, errores, 5 extents, radios, centros coincidentes |

Tiempo típico: < 0.1 s (sin renders, sin red, sin ficheros externos).
