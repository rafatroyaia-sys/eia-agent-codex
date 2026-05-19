# PHASE4_CLIMATE_PIPELINE — CL-06

Módulo `src/eia_agent/core/phase4_climate_pipeline.py`  
Pipeline climático de Fase 4 en modo seguro/offline. Orquesta CL-02, CL-03 y CL-04 a partir de archivos locales/fixtures, sin llamadas a AEMET.

---

## Qué hace

1. Lee coordenadas WGS84 de `control_interno/phase2_result.json`.
2. Carga un listado local de estaciones climáticas.
3. Selecciona la estación más próxima (CL-02 — `find_nearest_station`).
4. Carga datos climáticos mensuales de un archivo local.
5. Localiza los datos de la estación seleccionada.
6. Clasifica el clima: Köppen-Geiger, índice de Martonne, meses secos Gaussen (CL-03).
7. Si `write_outputs=True`, genera el climograma PNG (CL-04).
8. Genera un texto markdown de descripción climática.
9. Si `write_outputs=True`, escribe JSON de resultado, MD y PNG en `clima/`.
10. Devuelve `Phase4ClimateResult` con todos los metadatos.

## Qué NO hace

- **No llama a AEMET** ni a ningún servicio externo.
- **No genera cartografía** — eso es CA-02 a CA-05.
- **No inserta el climograma en DOCX** — eso es CL-05.
- **No redacta el Bloque B completo** — eso es AG-10.
- **No escribe nada** si `write_outputs=False`.
- **No modifica el expediente piloto** en tests (usa tempfiles).
- **No usa IA**.

---

## Relación con otros módulos

| Módulo | Rol | Relación |
|--------|-----|----------|
| CA-08 `phase4_precheck.py` | Precheck de Fase 4 (coords, API keys) | Prerequisito recomendado |
| CL-02 `climate_station_selector.py` | Selector de estación por distancia haversine | Usado internamente |
| CL-03 `climate_indices.py` | Köppen, Martonne, Gaussen | Usado internamente |
| CL-04 `climogram_generator.py` | Genera PNG del climograma | Usado si `write_outputs=True` |
| CL-05 `climogram_docx_inserter.py` | Inserta PNG en DOCX | Paso siguiente tras CL-06 |

Flujo completo de Fase 4:
```
CA-08 (precheck) → CL-06 (pipeline offline) → CL-05 (inserción DOCX)
                    ├── CL-02 (selector estación)
                    ├── CL-03 (clasificación climática)
                    └── CL-04 (climograma PNG)
```

---

## Formato de stations.json

Lista de objetos con la estructura de `ClimateStation`:

```json
[
  {
    "station_id": "C029O",
    "name": "Lanzarote Aeropuerto",
    "latitude": 28.9583,
    "longitude": -13.6052,
    "altitude_m": 14.0,
    "has_normals": true,
    "island": "Lanzarote"
  },
  {
    "station_id": "C449C",
    "name": "Las Palmas Aeropuerto",
    "latitude": 27.9333,
    "longitude": -15.3833,
    "altitude_m": 24.0,
    "has_normals": true,
    "island": "Gran Canaria"
  }
]
```

Campos obligatorios: `station_id`, `name`, `latitude`, `longitude`.  
Campo `has_normals` controla si la estación es candidata (por defecto `true`).

---

## Formato de climate_data.json

Lista de objetos con 12 valores de temperatura y precipitación:

```json
[
  {
    "station_id": "C029O",
    "station_name": "Lanzarote Aeropuerto",
    "period": "1991-2020",
    "temperatures_c": [17.8, 18.1, 18.8, 19.4, 20.7, 22.7, 24.9, 25.7, 25.1, 23.5, 21.0, 18.6],
    "precipitations_mm": [22.0, 19.0, 15.0, 7.0, 2.0, 1.0, 0.0, 1.0, 5.0, 14.0, 21.0, 24.0]
  }
]
```

Campos obligatorios: `station_id`, `temperatures_c` (12 valores), `precipitations_mm` (12 valores).  
Campos opcionales: `station_name`, `period`.

La función `load_monthly_climate_dataset(path)` devuelve un `dict[str, MonthlyClimateData]` indexado por `station_id`.

---

## API principal

### run_phase4_climate

```python
run_phase4_climate(
    expediente_path: str | Path,
    phase2_result_path: str | Path | None = None,
    stations_path: str | Path | None = None,
    climate_data_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "clima",
) -> Phase4ClimateResult
```

**Raises**:
- `FileNotFoundError` — si `phase2_result.json` no existe
- `ValueError` — si las coordenadas no se pueden extraer de `object_scope`

Si `stations_path` o `climate_data_path` son `None`, el pipeline avanza lo que puede y devuelve un resultado parcial con el `station_selection_status` apropiado.

Si la estación seleccionada no tiene datos en el dataset, se añade un aviso en `result.warnings` y `climate_classification` es `None`.

### Phase4ClimateResult

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | `str` | Nombre del directorio del expediente |
| `selected_station` | `dict \| None` | Datos de la estación seleccionada (`ClimateStation.to_dict()`) |
| `station_distance_km` | `float \| None` | Distancia en km al emplazamiento |
| `station_selection_status` | `str` | `OPTIMA` / `ACEPTABLE` / `LEJANA` / `NO_DISPONIBLE` |
| `climate_classification` | `dict \| None` | Resultado de `ClimateClassification.to_dict()` |
| `climogram_path` | `str \| None` | Ruta del PNG generado (solo si `write_outputs=True`) |
| `description_md` | `str` | Texto markdown de descripción climática |
| `warnings` | `list[str]` | Avisos (estación LEJANA, datos ausentes, etc.) |
| `notes` | `list[str]` | Notas informativas |

Métodos: `to_dict()`, `summary()`

### Otras funciones

```python
load_monthly_climate_dataset(path: str | Path) -> dict[str, MonthlyClimateData]
extract_wgs84_from_phase2(phase2_data: dict) -> tuple[float, float]
build_climate_description_md(result: Phase4ClimateResult) -> str
```

`extract_wgs84_from_phase2` acepta tres formatos en `object_scope.coordenadas_wgs84`:
- `["28.9773, -13.5395"]` — un string "lat, lon"
- `["28.9773", "-13.5395"]` — dos strings separados
- `[{"lat": 28.9773, "lon": -13.5395}]` — un dict

---

## Cómo ejecutar desde CLI

```bash
# Solo lectura (sin escribir nada):
python run_expediente.py expediente-EIA-NAVE-222 phase4-climate \
    --stations config/estaciones_canarias.json \
    --climate-data config/datos_climaticos.json

# Modo escritura (genera JSON, MD y PNG en clima/):
python run_expediente.py expediente-EIA-NAVE-222 phase4-climate \
    --stations config/estaciones_canarias.json \
    --climate-data config/datos_climaticos.json \
    --write
```

Ambos argumentos `--stations` y `--climate-data` son **obligatorios** en CLI. Si falta alguno, el runner devuelve exit code 1 con mensaje claro.

---

## Diferencia lectura vs --write

| Acción | Sin `--write` | Con `--write` |
|--------|--------------|---------------|
| Seleccionar estación | Sí | Sí |
| Clasificar clima | Sí | Sí |
| Mostrar summary en consola | Sí | Sí |
| Generar climograma PNG | No | Sí |
| Escribir `clima/phase4_climate_result.json` | No | Sí |
| Escribir `clima/descripcion_clima.md` | No | Sí |
| Modificar el expediente | No | Sólo en `clima/` |

---

## Outputs generados en modo --write

```
expediente-EIA-X/
└── clima/
    ├── phase4_climate_result.json     # Phase4ClimateResult serializado
    ├── descripcion_clima.md           # Descripción climática en markdown
    └── climograma_<station_id>_<period>.png   # Climograma PNG (CL-04)
```

---

## Limitaciones conocidas

1. **Sin fallback de estación alternativa**: si la estación seleccionada no tiene datos en el dataset, no se busca automáticamente la siguiente candidata. Se añade un aviso y la clasificación queda como `None`.
2. **Un único punto de coordenadas**: se usa la primera coordenada WGS84 del ObjectScope. Para proyectos con múltiples recintos, se usará el centroide del primero declarado.
3. **Dataset local requerido**: el pipeline no descarga datos de AEMET. Hay que proporcionar un archivo `climate_data.json` con los datos de las estaciones candidatas.
4. **Descripción markdown**: la descripción generada es técnica y estructurada. La redacción narrativa del Bloque B del DA corresponde a AG-10.
5. **Un climograma por ejecución**: se genera siempre para la estación seleccionada, no para todas las candidatas.

---

## Tests

`tests/test_phase4_climate_pipeline.py` — 63 tests en 7 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestLoadMonthlyClimateDataset` | 9 | Carga válida, FileNotFoundError, JSON inválido, 11 meses |
| `TestExtractWgs84` | 8 | Formatos string/dict, espacios, sin coordenadas, object_scope ausente |
| `TestRunPhase4Climate` | 25 | Pipeline completo, selección, clasificación, write/no-write, PNG, warnings, CLI |
| `TestCLIPhase4Climate` | 5 | CLI sin/con --write, crea PNG, missing phase2 → exit 1 |
| `TestLanzaroteFixture` | 10 | Lanzarote → C029O, Köppen B, Martonne árido, meses secos, description |
| `TestBuildClimateDescriptionMd` | 7 | Contenido MD, aviso LEJANA, sin estación/clasificación |

Tiempo típico: ~3 s (sin renders matplotlib en modo no-write, 2-3 climogramas reales en write tests).
