# PHASE4_OFFLINE_PIPELINE — F4-01

Módulo `src/eia_agent/core/phase4_offline_pipeline.py`  
Pipeline integrador de Fase 4 offline (modo test). Coordina en secuencia CA-08 + CL-06 + CA-10 + CA-11. No llama a AEMET, Mapbox ni WMS/WMTS.

---

## Qué hace

1. Valida que `stations_path` y `climate_data_path` existen (levanta `FileNotFoundError` si no).
2. **CA-08** — `run_phase4_precheck`: comprueba que el expediente está preparado para Fase 4.
3. **CL-06** — `run_phase4_climate`: selecciona estación climática más cercana, calcula índices (Köppen, Martonne), genera climograma PNG.
4. **CA-10** — `build_cartography_plan`: genera 6 `MapSpec` a partir de las coordenadas del expediente.
5. **CA-11** — `generate_schematic_maps_from_plan`: si `write_outputs=True`, genera 6 PNGs esquemáticos provisionales.
6. Determina `ready_for_phase5` y `administrative_ready` (siempre `False`).
7. Si `write_outputs=True`, escribe `fase4/phase4_result.json` y `fase4/phase4_result.md`.

## Qué NO hace

- **No llama a AEMET** ni a ninguna API meteorológica real.
- **No llama a Mapbox** ni descarga teselas.
- **No usa WMS/WMTS** ni capas geoespaciales reales.
- **No genera cartografía oficial** — los PNGs llevan sello PROVISIONAL y no son aptos para presentación administrativa.
- **No modifica el expediente piloto**.
- **No ejecuta agentes IA**.
- `administrative_ready` es siempre `False` en este pipeline.

---

## API principal

### Phase4OfflineResult

```python
@dataclass
class Phase4OfflineResult:
    expediente_id: str
    precheck: dict
    climate: dict | None
    cartography_plan: dict | None
    schematic_maps: list[dict]
    ready_for_phase5: bool
    administrative_ready: bool   # Siempre False
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict: ...
    def summary(self) -> str: ...
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | `str` | Nombre del directorio del expediente |
| `precheck` | `dict` | Resultado de CA-08 serializado |
| `climate` | `dict \| None` | Resultado de CL-06 serializado; `None` si falló |
| `cartography_plan` | `dict \| None` | Resultado de CA-10 serializado; `None` si falló |
| `schematic_maps` | `list[dict]` | Lista de MapSpec/SchematicMapResult serializados (6 entradas) |
| `ready_for_phase5` | `bool` | `True` solo si precheck OK + clima + plan + ≥6 mapas |
| `administrative_ready` | `bool` | Siempre `False` |
| `warnings` | `list[str]` | Avisos acumulados (prefijados `[Clima]`, `[Cartografía]`) |
| `notes` | `list[str]` | Nota obligatoria de modo offline + ruta si `write_outputs=True` |

### run_phase4_offline

```python
run_phase4_offline(
    expediente_path: str | Path,
    stations_path: str | Path,
    climate_data_path: str | Path,
    phase2_result_path: str | Path | None = None,
    phase3_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "fase4",
) -> Phase4OfflineResult
```

**Raises**:
- `FileNotFoundError` — si `stations_path` o `climate_data_path` no existen, o si falta `phase2_result.json`.
- `ValueError` — si las coordenadas no se pueden extraer del `phase2_result.json`.

### build_phase4_offline_markdown

```python
build_phase4_offline_markdown(result: Phase4OfflineResult) -> str
```

Genera el markdown resumen con secciones: estado general, precheck (CA-08), clima (CL-06), cartografía (CA-10 + CA-11), avisos, notas. Incluye aviso obligatorio de modo offline.

---

## Lógica de ready_for_phase5

```python
ready_for_phase5 = (
    precheck_ok          # CA-08 sin errores
    and climate_dict is not None   # CL-06 completado
    and cartography_plan_dict is not None  # CA-10 completado
    and len(schematic_maps) >= 6   # 6 mapas (esquemáticos o planificados)
)
```

---

## Comportamiento de schematic_maps según write_outputs

| `write_outputs` | Comportamiento |
|-----------------|----------------|
| `False` | CA-11 no se ejecuta. `schematic_maps` = `[m.to_dict() for m in cart_result.maps]` (MapSpec dicts, sin PNGs) |
| `True` | CA-10 escribe `cartografia/cartografia_plan.json`. CA-11 lee ese JSON y genera 6 PNGs en `cartografia/mapas/`. `schematic_maps` = `[r.to_dict() for r in smap_results]` |

---

## Outputs generados con --write

```
expediente-EIA-X/
├── fase4/
│   ├── phase4_result.json     ← resumen completo serializado
│   └── phase4_result.md       ← informe markdown
├── clima/
│   ├── phase4_climate_result.json
│   ├── descripcion_clima.md
│   └── climograma_*.png
└── cartografia/
    ├── cartografia_plan.json
    ├── cartografia_plan.md
    └── mapas/
        ├── MAP-001_situacion_general.png
        ├── MAP-002_emplazamiento.png
        ├── MAP-003_parcela_catastro.png
        ├── MAP-004_red_natura_enp.png
        ├── MAP-005_usos_suelo_entorno.png
        └── MAP-006_inundabilidad_riesgos.png
```

---

## Cómo ejecutar desde CLI

```bash
# Solo previsualización (no genera ficheros):
python run_expediente.py expediente-EIA-NAVE-222 phase4-offline \
    --stations config/estaciones.json \
    --climate-data config/datos_climaticos.json

# Generación completa de outputs:
python run_expediente.py expediente-EIA-NAVE-222 phase4-offline \
    --stations config/estaciones.json \
    --climate-data config/datos_climaticos.json \
    --write
```

---

## Relación con otros módulos

| Módulo | Rol | Relación |
|--------|-----|----------|
| CA-08 `phase4_precheck.py` | Precheck de Fase 4 | F4-01 lo ejecuta primero |
| CL-06 `phase4_climate_pipeline.py` | Análisis climático offline | F4-01 lo ejecuta segundo |
| CA-10 `cartography_plan.py` | Plan cartográfico | F4-01 lo ejecuta tercero |
| CA-11 `schematic_map_generator.py` | Mapas esquemáticos PNG | F4-01 lo ejecuta cuarto (solo si `write_outputs=True`) |

---

## Tests

`tests/test_phase4_offline_pipeline.py` — tests en 9 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestPhase4OfflineResultBasico` | 10 | Tipos, estructura, `administrative_ready=False`, nota offline |
| `TestSinEscritura` | 5 | No crea `fase4/`, `cartografia/`, `mapas/`; `schematic_maps` poblado en memoria |
| `TestConEscritura` | 9 | Crea JSON, MD, plan JSON, PNGs, JSON de clima; directorio custom |
| `TestValidacionesEntrada` | 5 | `FileNotFoundError` para stations/climate/phase2 ausentes; acepta strings |
| `TestIntegracionClima` | 6 | `climate` no nulo, contiene estación y Köppen, warnings propagados |
| `TestIntegracionCartografia` | 7 | Plan con 6 mapas, `schematic_maps` con 6 entradas, IDs secuenciales |
| `TestMarkdown` | 15 | MD no vacío, contiene ID/secciones CA-08/CL-06/CA-10/CA-11, `to_dict`, `summary` |
| `TestCLIPhase4Offline` | 8 | No-write=0, no crea dirs; write crea JSON/MD/PNGs; errores devuelven 1 |
| `TestLanzaroteFixture` | 14 | 6 mapas, Köppen B, `administrative_ready=False`, JSON serializable, summary |

---

## Limitaciones conocidas

1. **No es cartografía oficial**: los PNGs son esquemáticos y no aptos para presentación administrativa.
2. **Sin datos reales de AEMET**: los datos climáticos deben proporcionarse en un JSON local.
3. **Sin WMS/WMTS**: los mapas no contienen teselas ni capas geoespaciales reales.
4. **`administrative_ready` siempre `False`**: no existe modo que lo cambie a `True` en este pipeline.
5. `phase3_result_path` está reservado para uso futuro y no se usa actualmente.
