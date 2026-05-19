# CLIMOGRAM_GENERATOR — CL-04

Módulo `src/eia_agent/core/climogram_generator.py`  
Genera climogramas PNG (curva de temperatura + barras de precipitación) a partir de datos climáticos mensuales. Sin llamadas a AEMET. Sin inserción en DOCX (eso es CL-05).

---

## Dependencias

```
matplotlib  (backend Agg — sin ventanas)
eia_agent.core.climate_indices (MonthlyClimateData, gaussen_dry_months)
```

El backend `Agg` se activa en el momento de importar el módulo (`matplotlib.use("Agg")`), antes de cualquier `import matplotlib.pyplot`. Esto garantiza el modo headless en entornos sin display (CI, servidor, Windows sin GUI).

---

## Clases principales

### ClimogramConfig

Parámetros de configuración del climograma. Todos tienen valor por defecto.

| Campo | Tipo | Por defecto | Descripción |
|-------|------|-------------|-------------|
| `title` | `str \| None` | `None` | Título personalizado. Si `None`, se genera desde `station_name` |
| `subtitle` | `str \| None` | `None` | Subtítulo personalizado. Si `None`, se genera desde `period` |
| `width_inches` | `float` | `10.0` | Ancho del PNG en pulgadas |
| `height_inches` | `float` | `6.0` | Alto del PNG en pulgadas |
| `dpi` | `int` | `150` | Resolución. 150 dpi → 1500×900 px para inserción en DOCX |
| `show_gaussen` | `bool` | `True` | Mostrar criterio de aridez de Gaussen (fondo amarillo meses secos) |
| `show_annual_summary` | `bool` | `True` | Mostrar recuadro con T media anual y P anual |
| `language` | `str` | `"es"` | Idioma de etiquetas (actualmente solo español) |

Métodos:
- `to_dict() -> dict`
- `ClimogramConfig.from_dict(data: dict) -> ClimogramConfig` — las claves ausentes usan el valor por defecto

### ClimogramResult

Metadatos del climograma generado. Devuelto por `generate_climogram()`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `output_path` | `str` | Ruta completa del PNG generado |
| `width_px` | `int` | Ancho en píxeles (`width_inches × dpi`) |
| `height_px` | `int` | Alto en píxeles (`height_inches × dpi`) |
| `dpi` | `int` | Resolución utilizada |
| `station_id` | `str \| None` | ID de la estación (de `MonthlyClimateData`) |
| `station_name` | `str \| None` | Nombre de la estación |
| `period` | `str \| None` | Periodo de referencia (p.ej. `"1991-2020"`) |
| `annual_temperature_c` | `float` | T media anual calculada (media de 12 meses) |
| `annual_precipitation_mm` | `float` | P total anual (suma de 12 meses) |
| `dry_months_gaussen` | `list[int]` | Lista de meses secos 1-indexados (P ≤ 2·T). Vacía si `show_gaussen=False` |
| `warnings` | `list[str]` | Avisos no bloqueantes (p.ej. precipitaciones todas a 0) |
| `notes` | `list[str]` | Notas informativas |

Métodos:
- `to_dict() -> dict`
- `summary() -> str` — texto multilínea con estación, periodo, T, P y meses secos

---

## Funciones públicas

### generate_climogram

```python
def generate_climogram(
    data: MonthlyClimateData,
    output_path: str | Path,
    config: ClimogramConfig | None = None,
) -> ClimogramResult
```

Genera un PNG del climograma y lo guarda en `output_path`.

**Comportamiento**:
- Crea los directorios intermedios si no existen (`mkdir parents=True`).
- Si `config` es `None`, usa `ClimogramConfig()` (valores por defecto).
- Cierra siempre la figura matplotlib en un bloque `finally` para evitar fugas de memoria.
- Llama a `data.validate()` — lanza `ValueError` si los datos no tienen exactamente 12 meses.

**Raises**:
- `ValueError` — si `output_path` no termina en `.png` (insensible a mayúsculas)
- `ValueError` — si `data` tiene ≠ 12 meses de temperatura o precipitación

**Ejemplo**:
```python
from eia_agent.core.climate_indices import MonthlyClimateData
from eia_agent.core.climogram_generator import generate_climogram

data = MonthlyClimateData(
    temperatures_c=[17.8,18.1,18.8,19.4,20.7,22.7,24.9,25.7,25.1,23.5,21.0,18.6],
    precipitations_mm=[22,19,15,7,2,1,0,1,5,14,21,24],
    station_id="C029O",
    station_name="Lanzarote Aeropuerto",
    period="1991-2020",
)
result = generate_climogram(data, "clima/climograma.png")
print(result.summary())
```

---

### generate_climogram_from_dict

```python
def generate_climogram_from_dict(
    data: dict,
    output_path: str | Path,
    config: ClimogramConfig | None = None,
) -> ClimogramResult
```

Wrapper que construye un `MonthlyClimateData` desde el dict serializado y llama a `generate_climogram`.

**Raises**:
- `KeyError` — si faltan las claves `temperatures_c` o `precipitations_mm`
- `ValueError` — igual que `generate_climogram`

---

### validate_png

```python
def validate_png(path: str | Path) -> bool
```

Comprueba que el archivo existe, tiene tamaño > 0 y empieza con la firma PNG de 8 bytes (`\x89PNG\r\n\x1a\n`). No lanza excepciones — devuelve `False` en cualquier error.

---

### default_climogram_filename

```python
def default_climogram_filename(
    station_id: str | None = None,
    period: str | None = None,
) -> str
```

Devuelve un nombre de archivo seguro para el climograma. Reemplaza caracteres problemáticos (espacios, barras, etc.) con `_`.

| Llamada | Resultado |
|---------|-----------|
| `default_climogram_filename()` | `"climograma.png"` |
| `default_climogram_filename("C029O")` | `"climograma_C029O.png"` |
| `default_climogram_filename("C029O", "1991-2020")` | `"climograma_C029O_1991-2020.png"` |
| `default_climogram_filename("ID/con espacios", "1991-2020")` | `"climograma_ID_con_espacios_1991-2020.png"` |

---

## Diseño visual del climograma

El climograma sigue la convención estándar Walter-Lieth:

| Elemento | Color | Eje | Detalle |
|----------|-------|-----|---------|
| Barras de precipitación | Azul (`#1f77b4`) | Izquierdo | α = 0.75 |
| Curva de temperatura | Rojo (`#d62728`) | Derecho | linewidth=2.5, marker "o" |
| Meses secos Gaussen | Amarillo (`#f7b731`) | — | axvspan, α = 0.18 |

**Escala de precipitación**: máximo = `max(P) × 1.25`, mínimo razonable 30 mm.  
**Escala de temperatura**: centrada en [min(T), max(T)] con margen del 30% o al menos 3 °C.  
**Leyenda unificada**: combina los handles de ambos ejes + parche de mes seco si procede.  
**Resumen anual**: recuadro en esquina superior izquierda con T media y P anual (ocultable con `show_annual_summary=False`).

---

## Criterio de aridez de Gaussen

Un mes es **seco** cuando `P ≤ 2·T` (precipitación en mm, temperatura en °C).  
Los meses con temperatura negativa nunca son secos (P ≥ 0 > 2·T cuando T < 0).  
Los índices devueltos son **1-indexados** (enero = 1, diciembre = 12).

Cuando `show_gaussen=False`, `dry_months_gaussen` en el resultado es siempre `[]`.

---

## Integración en el flujo EIA

En la **Fase 4** (AG-7), el climograma se genera a partir de las normales AEMET obtenidas por CL-01/CL-02:

```python
from eia_agent.core.aemet_client import AEMETClient
from eia_agent.core.climate_station_selector import find_nearest_station
from eia_agent.core.climate_indices import parse_monthly_climate_from_aemet_normals
from eia_agent.core.climogram_generator import generate_climogram

client = AEMETClient.from_env()
normales = client.get_normales_climatologicas(station_id)
data = parse_monthly_climate_from_aemet_normals(normales, station_id, station_name)
result = generate_climogram(data, f"clima/climograma_{station_id}.png")
```

La inserción del PNG en el DOCX es responsabilidad de **CL-05** (pendiente).

---

## Tests

`tests/test_climogram_generator.py` — 53 tests en 9 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestClimogramConfig` | 5 | Valores por defecto, `to_dict`, `from_dict` roundtrip, claves ausentes |
| `TestDefaultFilename` | 5 | Sin args, con station_id, con periodo, caracteres problemáticos, `None` period |
| `TestGenerateClimoBasic` | 16 | PNG generado, `validate_png`, metadatos del resultado, meses secos Lanzarote, `to_dict`, `summary` |
| `TestDirectoryCreation` | 1 | Creación de directorios anidados |
| `TestConfiguration` | 7 | DPI personalizado, `show_gaussen=False`, título/subtítulo, `show_annual_summary=False`, `config=None`, píxeles calculados |
| `TestErrors` | 6 | 11 meses, extensiones no-PNG (.jpg, .docx, sin extensión), PNG vacío, cabecera inválida |
| `TestFromDict` | 4 | Dict válido, `station_id` preservado, clave faltante, datos inválidos |
| `TestClimaticFixtures` | 5 | Lanzarote (árido, meses secos), clima húmedo (sin meses secos), tamaño de archivo razonable |
| `TestNoModification` | 3 | El objeto `MonthlyClimateData` de entrada no se modifica |

Ejecución: `venv\Scripts\python -m unittest tests/test_climogram_generator.py`  
Tiempo típico: ~15 s (renderizado matplotlib × 20+ figuras en tempdir).
