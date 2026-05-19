# CARTOGRAPHY_PLAN — CA-10

Módulo `src/eia_agent/core/cartography_plan.py`  
Planificador cartográfico offline para Fase 4 EIA. Genera especificaciones estructuradas de los 6 mapas mínimos obligatorios a partir de coordenadas WGS84.

---

## Qué hace

1. Lee `control_interno/phase2_result.json`.
2. Extrae el `GeoPoint` principal usando CA-09 (`extract_geopoint_from_phase2`).
3. Construye los 5 extents estándar con CA-09 (`build_standard_map_extents`).
4. Genera 6 `MapSpec` con capas requeridas, fuentes candidatas y estado.
5. Produce un `CartographyPlanResult` con metadatos del plan.
6. Si `write_outputs=True`, escribe `cartografia/cartografia_plan.json` y `cartografia/cartografia_plan.md`.

## Qué NO hace

- **No genera mapas** — solo especificaciones para renderizado posterior.
- **No llama a Mapbox** ni a ningún servicio de tiles.
- **No usa WMS/WMTS** — eso es CA-02 o módulos de renderizado futuros.
- **No verifica Catastro** ni consulta parcelas reales.
- **No descarga capas** geoespaciales.
- **No genera imágenes PNG** — eso es CA-11 o módulos de renderizado.
- **No modifica el expediente piloto**.
- **No usa IA**.

---

## Relación con otros módulos

| Módulo | Rol | Relación |
|--------|-----|----------|
| CA-08 `phase4_precheck.py` | Precheck Fase 4 | Prerequisito recomendado; verifica coordenadas antes de planificar |
| CA-09 `geospatial_utils.py` | Núcleo geoespacial | Usado internamente para GeoPoint y extents |
| CA-11 (futuro) | Renderizado cartográfico | Consumirá `CartographyPlanResult` para generar mapas PNG |

Flujo completo de Fase 4 (cartografía):
```
CA-08 (precheck) → CA-10 (plan offline) → CA-11 (renderizado PNG)
                    └── CA-09 (GeoPoint + extents)
```

---

## Tipos principales

### MapSpec

Especificación de un mapa cartográfico individual.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `map_id` | `str` | Identificador único (`MAP-001` a `MAP-006`) |
| `title` | `str` | Título descriptivo del mapa |
| `purpose` | `str` | Propósito del mapa en el contexto EIA |
| `map_type` | `str` | Tipo cartográfico |
| `extent_key` | `str` | Clave del extent estándar CA-09 |
| `extent` | `dict` | Extent completo serializado (centro, bbox, radio) |
| `required_layers` | `list[str]` | Capas que debe contener el mapa |
| `source_candidates` | `list[str]` | Fuentes cartográficas recomendadas |
| `output_filename` | `str` | Nombre del PNG que generará CA-11 |
| `status` | `str` | `READY_FOR_RENDER` o `PLANNED` |
| `warnings` | `list[str]` | Avisos (coordenadas no fiables, etc.) |
| `notes` | `list[str]` | Notas informativas |

### CartographyPlanResult

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | `str` | Nombre del directorio del expediente |
| `center` | `dict` | GeoPoint serializado del centro del emplazamiento |
| `maps` | `list[MapSpec]` | Los 6 MapSpec generados |
| `ready_for_render` | `bool` | `True` si todos los mapas son READY_FOR_RENDER |
| `warnings` | `list[str]` | Avisos del plan completo |
| `notes` | `list[str]` | Notas del plan completo |

Métodos: `to_dict()`, `summary()`

---

## Mapas mínimos obligatorios

| ID | Título | Tipo | Extent | Salida |
|----|--------|------|--------|--------|
| MAP-001 | Situación general | `situacion_general` | `situacion_general` (25 km) | `MAP-001_situacion_general.png` |
| MAP-002 | Emplazamiento | `emplazamiento` | `emplazamiento` (1 km) | `MAP-002_emplazamiento.png` |
| MAP-003 | Parcela / catastro | `parcela_catastro` | `detalle_parcela` (250 m) | `MAP-003_parcela_catastro.png` |
| MAP-004 | Red Natura 2000 / ENP | `red_natura_enp` | `situacion_general` (25 km) | `MAP-004_red_natura_enp.png` |
| MAP-005 | Usos del suelo entorno | `usos_suelo` | `entorno_500m` (500 m) | `MAP-005_usos_suelo_entorno.png` |
| MAP-006 | Inundabilidad / riesgos físicos | `inundabilidad_riesgos` | `entorno_2000m` (2 km) | `MAP-006_inundabilidad_riesgos.png` |

---

## Estado PLANNED vs READY_FOR_RENDER

| Condición | Status MapSpec | ready_for_render |
|-----------|---------------|------------------|
| GeoPoint.status = `DECLARADO` o `VERIFICADO` | `READY_FOR_RENDER` | `True` |
| GeoPoint.status = `ESTIMADO`, `PROVISIONAL` o `NO_DECLARADO` | `PLANNED` | `False` |
| Sin coordenadas en `object_scope.coordenadas_wgs84` | — | `ValueError` |

Los mapas con estado `PLANNED` incluyen un aviso en `warnings` que indica que las coordenadas deben confirmarse antes de renderizar.

---

## API principal

### build_cartography_plan

```python
build_cartography_plan(
    expediente_path: str | Path,
    phase2_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "cartografia",
) -> CartographyPlanResult
```

**Raises**:
- `FileNotFoundError` — si `phase2_result.json` no existe.
- `ValueError` — si no hay coordenadas en `object_scope.coordenadas_wgs84`.

### build_cartography_plan_markdown

```python
build_cartography_plan_markdown(result: CartographyPlanResult) -> str
```

Genera el markdown con tabla resumen y detalle de cada mapa. Incluye nota explícita de que no contiene cartografía generada.

---

## Cómo usar desde CLI

```bash
# Solo lectura (sin escribir nada):
python run_expediente.py expediente-EIA-NAVE-222 cartography-plan

# Modo escritura (genera JSON y MD en cartografia/):
python run_expediente.py expediente-EIA-NAVE-222 cartography-plan --write
```

---

## Diferencia lectura vs --write

| Acción | Sin `--write` | Con `--write` |
|--------|--------------|---------------|
| Extraer coordenadas | Sí | Sí |
| Construir extents | Sí | Sí |
| Generar 6 MapSpec | Sí | Sí |
| Mostrar summary en consola | Sí | Sí |
| Escribir `cartografia/cartografia_plan.json` | No | Sí |
| Escribir `cartografia/cartografia_plan.md` | No | Sí |
| Generar imágenes PNG | No | No |
| Modificar el expediente | No | Solo en `cartografia/` |

---

## Outputs generados en modo --write

```
expediente-EIA-X/
└── cartografia/
    ├── cartografia_plan.json     # CartographyPlanResult serializado
    └── cartografia_plan.md       # Plan cartográfico en markdown
```

---

## Uso en CA-11 o módulo de renderizado

`CartographyPlanResult.maps` es la entrada esperada para el módulo de renderizado posterior (CA-11 o similar). Cada `MapSpec` contiene:

- El **extent** completo (bbox, radio, centro) listo para configurar la ventana del mapa.
- La lista de **capas requeridas** que el renderizador debe solicitar a WMS/WMTS/archivos locales.
- Las **fuentes candidatas** ordenadas por preferencia.
- El **nombre de fichero de salida** esperado.

CA-11 puede filtrar los mapas por `status == "READY_FOR_RENDER"` antes de iniciar el renderizado.

---

## Limitaciones conocidas

1. **Fuentes candidatas como texto libre**: `source_candidates` son sugerencias de texto, no URLs ni configuración de servicio. CA-11 deberá resolver las URLs reales de los WMS desde el catálogo de servicios.
2. **Un único emplazamiento**: usa la primera coordenada WGS84 de `object_scope`. Para proyectos con múltiples recintos, se tomará el primero declarado.
3. **Sin validación de capas disponibles**: no verifica si las capas de `required_layers` están realmente disponibles en las fuentes candidatas.

---

## Tests

`tests/test_cartography_plan.py` — 75 tests en 8 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestMapSpec` | 8 | to_dict, summary, warnings, aislamiento de listas |
| `TestCartographyPlanResult` | 7 | to_dict, summary, ready_for_render labels |
| `TestBuildCartographyPlanBasic` | 13 | 6 mapas, IDs, filenames, capas, fuentes, expediente_id |
| `TestMapStatuses` | 11 | DECLARADO→READY, ESTIMADO→PLANNED, warnings, ready_for_render |
| `TestBuildCartographyPlanMarkdown` | 11 | Contenido MD, tabla, nota sin renderizado, warnings |
| `TestWriteOutputs` | 8 | Sin write no escribe, JSON válido, MD correcto, custom dir |
| `TestCLICartographyPlan` | 5 | CLI sin/con --write, exit 0/1, JSON con 6 mapas |
| `TestLanzaroteFixture` | 12 | Lanzarote (28.9773,-13.5395), 6 mapas, READY, bbox, radios |

Tiempo típico: < 0.5 s (sin renders, sin red, sin ficheros externos).
