# SCHEMATIC_MAP_GENERATOR — CA-11

Módulo `src/eia_agent/core/schematic_map_generator.py`  
Generador de mapas esquemáticos offline para Fase 4 EIA. Produce PNGs provisionales a partir de un plan cartográfico CA-10, útiles para pruebas, borradores y ensamblaje en modo test.

---

## Qué hace

1. Lee un `CartographyPlanResult` (CA-10) o `cartografia_plan.json`.
2. Por cada `MapSpec`, genera un PNG esquemático con Pillow.
3. El PNG incluye:
   - Barra de título con `map_id`, nombre del mapa y sello `PROVISIONAL — MODO TEST`.
   - Área de mapa con fondo, cuadrícula geográfica y coordenadas en los ejes.
   - Marcador central del proyecto (cruz + círculo rojo).
   - Indicadores cardinales (N / S / E / O).
   - Flecha norte (esquina superior derecha del área de mapa).
   - Barra de escala aproximada con etiquetas de distancia.
   - Panel lateral de leyenda: capas requeridas, fuentes candidatas, coordenadas, extensión.
   - Barra inferior: fuente, disclaimer de provisionalidad, estado.
   - Marca de agua diagonal `PROVISIONAL — MODO TEST` (configurable).
4. Si `write_outputs=True`, genera los PNGs en `cartografia/mapas/`.
5. Devuelve `list[SchematicMapResult]` con estado `GENERATED_PROVISIONAL` o `ERROR`.

## Qué NO hace

- **No genera cartografía oficial** — los PNGs no son aptos para presentación administrativa.
- **No usa WMS/WMTS** — no descarga teselas ni capas reales.
- **No llama a Mapbox** ni a ningún servicio de tiles.
- **No consulta Catastro** ni parcelas reales.
- **No verifica Red Natura 2000** ni espacios protegidos.
- **No descarga datos geoespaciales**.
- **No modifica el expediente piloto**.
- **No usa IA**.

---

## Diferencia entre mapa esquemático (CA-11) y mapa oficial

| Característica | Mapa esquemático CA-11 | Mapa oficial (futuro CA-12+) |
|----------------|------------------------|------------------------------|
| Fuente de datos | Ninguna (solo coordenadas y metadatos) | WMS/WMTS real (IGN, Grafcan…) |
| Contenido cartográfico | Fondo sintético + marcador | Teselas, capas reales |
| Apto para administración | **No** | Sí |
| Sello visible | PROVISIONAL — MODO TEST | Sin sello |
| Propósito | Pruebas, borradores, ensamblaje test | Presentación EIA |
| Tiempo de generación | < 1 s por mapa | Depende de APIs |
| Dependencias externas | Solo Pillow | Mapbox / WMS + Pillow |

---

## Relación con otros módulos

| Módulo | Rol | Relación |
|--------|-----|----------|
| CA-10 `cartography_plan.py` | Planificador cartográfico | CA-11 consume su `CartographyPlanResult` / `cartografia_plan.json` |
| CA-09 `geospatial_utils.py` | Tipos geoespaciales | Los extents en cada `MapSpec` provienen de CA-09 |
| CA-12 (futuro) | Renderizado oficial WMS | Siguiente hito; usará el mismo `CartographyPlanResult` |

---

## API principal

### SchematicMapConfig

```python
@dataclass
class SchematicMapConfig:
    width_px: int = 1600
    height_px: int = 1100
    dpi: int = 150
    show_test_watermark: bool = True
    background: str = "light"
    language: str = "es"

    def to_dict(self) -> dict: ...
    @classmethod def from_dict(cls, data: dict) -> "SchematicMapConfig": ...
```

### SchematicMapResult

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `map_id` | `str` | Identificador del mapa (`MAP-001`…`MAP-006`) |
| `title` | `str` | Título del mapa |
| `output_path` | `str` | Ruta absoluta al PNG generado |
| `width_px` | `int` | Ancho en píxeles |
| `height_px` | `int` | Alto en píxeles |
| `status` | `str` | `GENERATED_PROVISIONAL` o `ERROR` |
| `warnings` | `list[str]` | Avisos (incluye siempre aviso de provisionalidad) |
| `notes` | `list[str]` | Notas (ruta del PNG) |

Métodos: `to_dict()`, `summary()`

### generate_schematic_map

```python
generate_schematic_map(
    map_spec: MapSpec | dict,
    output_path: str | Path,
    config: SchematicMapConfig | None = None,
) -> SchematicMapResult
```

- Acepta `MapSpec` (CA-10) o dict compatible.
- Valida que `output_path` termina en `.png`.
- Crea directorios si no existen.
- Devuelve `SchematicMapResult` con `status="ERROR"` si falla (no lanza excepción).

**Raises**: `ValueError` si `output_path` no termina en `.png`.

### generate_schematic_maps_from_plan

```python
generate_schematic_maps_from_plan(
    plan_path: str | Path,
    output_dir: str | Path,
    config: SchematicMapConfig | None = None,
) -> list[SchematicMapResult]
```

Carga `cartografia_plan.json` y genera un PNG por cada mapa.

### validate_png

```python
validate_png(path: str | Path) -> bool
```

Devuelve `True` si el archivo existe, no está vacío y tiene la firma PNG correcta.

### load_cartography_plan

```python
load_cartography_plan(path: str | Path) -> dict
```

Carga y valida un `cartografia_plan.json`. Lanza `FileNotFoundError` si no existe o `ValueError` si el JSON es inválido o no contiene lista de mapas.

### build_map_generation_report

```python
build_map_generation_report(results: list[SchematicMapResult]) -> str
```

Genera un informe markdown con tabla de resultados y advertencia de provisionalidad.

---

## Elementos cartográficos incluidos en el PNG

| Elemento | Descripción |
|----------|-------------|
| Barra de título | `map_id`, nombre del mapa, sello PROVISIONAL |
| Área de mapa | Fondo azul-gris + cuadrícula de coordenadas |
| Etiquetas de ejes | Latitud/longitud en los ejes de la cuadrícula |
| Indicadores cardinales | N / S / E / O en los bordes del área |
| Marcador del proyecto | Cruz + círculo rojo en el centro exacto |
| Flecha norte | Triángulo + "N" en esquina superior derecha |
| Barra de escala | Barra bicolor con ticks y etiquetas de distancia |
| Panel de leyenda | Capas requeridas (con puntos), fuentes candidatas, coordenadas, radio |
| Barra inferior | Fuente, disclaimer, estado |
| Marca de agua | "PROVISIONAL — MODO TEST" diagonal (desactivable) |

---

## Cómo generar mapas desde CLI

```bash
# Vista previa (no genera PNGs):
python run_expediente.py expediente-EIA-NAVE-222 schematic-maps

# Con plan personalizado:
python run_expediente.py expediente-EIA-NAVE-222 schematic-maps \
    --plan cartografia/cartografia_plan.json

# Generar PNGs en cartografia/mapas/:
python run_expediente.py expediente-EIA-NAVE-222 schematic-maps --write
```

**Sin `--write`**: carga el plan, muestra la lista de mapas que se generarían, no crea ficheros.  
**Con `--write`**: genera los 6 PNGs en `cartografia/mapas/`.

---

## Outputs generados en modo --write

```
expediente-EIA-X/
└── cartografia/
    └── mapas/
        ├── MAP-001_situacion_general.png
        ├── MAP-002_emplazamiento.png
        ├── MAP-003_parcela_catastro.png
        ├── MAP-004_red_natura_enp.png
        ├── MAP-005_usos_suelo_entorno.png
        └── MAP-006_inundabilidad_riesgos.png
```

---

## Limitaciones conocidas

1. **Sin datos reales**: el área de mapa es un fondo sintético. No hay información geoespacial real.
2. **No apto para administración**: los PNGs generados llevan el sello PROVISIONAL y no deben incluirse en el Documento Ambiental definitivo.
3. **Fuentes del sistema**: las fuentes de texto dependen del sistema operativo. En Windows se usan Calibri/Arial. En Linux, DejaVu. Si ninguna está disponible, se usa la fuente por defecto de Pillow (muy pequeña).
4. **Sin topología**: el mapa no muestra ni ríos, ni carreteras, ni parcelas reales. Solo el punto central y la extensión geográfica.
5. **Barra de escala aproximada**: la escala está calculada a partir del radio del extent y el DPI configurado, no de una proyección geodésica real.

---

## Tests

`tests/test_schematic_map_generator.py` — 62 tests en 7 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestSchematicMapConfig` | 6 | Defaults, to_dict, from_dict roundtrip |
| `TestGenerateSchematicMap` | 10 | PNG válido, dimensiones, dirs, extensión no-.png, sin watermark, radios variados |
| `TestSchematicMapResult` | 13 | map_id, status, warnings, to_dict, summary, aislamiento |
| `TestLoadCartographyPlan` | 5 | JSON válido, FileNotFoundError, ValueError |
| `TestGenerateSchematicMapsFromPlan` | 6 | 6 PNGs, todos válidos, crea dir, FileNotFoundError |
| `TestBuildMapGenerationReport` | 8 | IDs, provisional, totales, tabla, errores |
| `TestCLISchematicMaps` | 5 | Sin/con --write, PNGs, exit 0/1, plan por defecto |
| `TestLanzaroteFixture` | 9 | 6 mapas Lanzarote, GENERATED_PROVISIONAL, PNGs válidos, report |

Tiempo típico: ~15 s (6 renders PNG por fixture × DPI 150 con watermark).
