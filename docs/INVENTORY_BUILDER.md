# INVENTORY_BUILDER — IV-02
## Constructor de inventario ambiental desde Fase 4 offline

Módulo: `src/eia_agent/core/inventory_builder.py`  
Ítem: IV-02 | Estado: **COMPLETADO**  
Tests: `tests/test_inventory_builder.py` (117 tests)  
Prerequisitos: IV-00 (`inventory_model.py`), IV-01 (`inventory_renderer.py`), F4-01 (`phase4_offline_pipeline.py`)

---

## Qué hace

Lee los outputs de Fase 4 offline (JSONs en disco) y construye el `InventorySummary`
inicial de Fase 5 con los 16 factores ambientales FI-001…FI-016.

- **FI-001 Clima** se construye con datos reales del pipeline CL-06 (`phase4_climate_result.json`).
- **FI-002…FI-016** se inicializan en estado base `PENDIENTE/NO_CONSTA` con un gap de inventario pendiente.
- Si se pasa `write_outputs=True`, escribe las fichas Markdown, el resumen y el índice JSON en `inventario/`.

---

## Qué NO hace

- **No consulta fuentes externas** — solo lee JSONs locales.
- **No inventa datos** — si no hay clasificación climática, el factor queda PENDIENTE.
- **No valora impactos** — las fichas son de inventario, no de valoración.
- **No genera Fase 6** — el módulo no toma decisiones sobre impactos ni medidas.
- **No usa IA** — lógica puramente determinista.
- **No modifica el piloto** — no toca expedientes existentes salvo con `--write`.
- **No implementa IV-02+ (semáforo de campo avanzado)** — `field_mode` se asigna directamente según evidencia disponible.

---

## Relación con otros módulos

```
F4-01 phase4_offline_pipeline.py
  └── fase4/phase4_result.json ──► IV-02 inventory_builder.py ──► InventorySummary
CL-06 phase4_climate_pipeline.py                               ──► FI-001 Clima (CONFIRMADO/DECLARADO/PENDIENTE)
  └── clima/phase4_climate_result.json                         ──► FI-002..FI-016 (PENDIENTE/NO_CONSTA)

IV-02 inventory_builder.py
  └── InventorySummary ──► IV-01 inventory_renderer.py ──► inventario/*.md
                        ──► inventario/inventory_summary.json
                        ──► inventario/indice_inventario.json
```

---

## Archivos de entrada

| Archivo | Ruta por defecto | Obligatoriedad |
|---------|-----------------|----------------|
| `phase4_result.json` | `fase4/phase4_result.json` | **Obligatorio** — `FileNotFoundError` si no existe |
| `phase4_climate_result.json` | `clima/phase4_climate_result.json` | Opcional — fallback al `"climate"` embebido en `phase4_result.json` |
| `cartografia_plan.json` | `cartografia/cartografia_plan.json` | Opcional — informativo, no altera semáforos |

---

## API

### `load_json_file(path) -> dict`

Carga un archivo JSON local.

```python
data = load_json_file("expediente/fase4/phase4_result.json")
```

Raises:
- `FileNotFoundError` si el archivo no existe.
- `ValueError` si el contenido no es JSON válido.

---

### `InventoryBuildResult`

Resultado del proceso de construcción.

```python
@dataclass
class InventoryBuildResult:
    expediente_id: str
    inventory_summary: InventorySummary
    factor_count: int
    ready_count: int
    rendered_files: list[str]    # vacío si write_outputs=False
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict: ...   # JSON serializable
    def summary(self) -> str: ...    # resumen de texto para consola
```

---

### `build_climate_factor_from_phase4(climate_data) -> FactorInventory`

Construye **FI-001 Clima** desde el dict de `Phase4ClimateResult`.

Lógica de evidencia:

| Condición | `evidence_status` | `field_mode` | `ready` | Semáforo |
|-----------|-------------------|--------------|---------|----------|
| Estación + clasificación | `CONFIRMADO_GABINETE` | `GABINETE_SUFICIENTE` | `True` | `VERDE` |
| Estación sin clasificación | `DECLARADO` | `GABINETE_SUFICIENTE` | `False` | `AMARILLO`+ |
| Sin estación | `PENDIENTE` | `NO_CONSTA` | `False` | `ROJO`+ |

Avisos adicionales:
- `LEJANA` (>25 km): warning con distancia.
- `NO_DISPONIBLE`: warning de ausencia de estaciones.
- Warnings/notes del pipeline CL-06 se propagan sin duplicar.

Gap creado si no hay clasificación: `GAP-FI-001-001`, campo `clasificacion_climatica`, criticidad `MEDIA`.

---

### `build_base_factor(factor_id, reason=None) -> FactorInventory`

Crea un `FactorInventory` base para factores sin integración automática en Fase 4.

```python
factor = build_base_factor("FI-007")
# factor.evidence_status  → "PENDIENTE"
# factor.field_mode       → "NO_CONSTA"
# factor.inventory_semaphore → "NO_CONSTA"
# factor.ready_for_impact_assessment → False
# factor.gaps[0].gap_id  → "GAP-FI-007-001"
```

El argumento `reason` permite personalizar la descripción del gap.

---

### `build_inventory_from_phase4_data(expediente_id, phase4_result, climate_result=None, cartography_plan=None) -> InventorySummary`

Construye `InventorySummary` con 16 factores en orden canónico.

- Si `climate_result` no es None, se usa para FI-001.
- Si `climate_result` es None, se usa `phase4_result["climate"]` si existe.
- Si ninguno, FI-001 queda en base PENDIENTE.
- FI-002…FI-016: siempre `build_base_factor`.

---

### `build_inventory_from_phase4(expediente_path, ..., write_outputs=False, output_dir="inventario") -> InventoryBuildResult`

Función principal. Carga los JSONs de Fase 4, construye el inventario y opcionalmente escribe los ficheros.

```python
result = build_inventory_from_phase4("expediente-EIA-2026-001")
print(result.summary())
# Inventario Fase 5 -- EIA-2026-001
#   Factores        : 16/16
#   Listos Fase 6   : 1/16
#   Listo Fase 6    : NO

result = build_inventory_from_phase4("expediente-EIA-2026-001", write_outputs=True)
# Escribe en expediente-EIA-2026-001/inventario/
```

---

## CLI

```bash
# Solo lectura — muestra resumen en consola
python run_expediente.py expediente-EIA-NAVE-222 inventory-build

# Escribe fichas en inventario/
python run_expediente.py expediente-EIA-NAVE-222 inventory-build --write
```

Sin `--write`: no crea ningún archivo.  
Con `--write`: crea `inventario/` con 16 fichas `.md`, `resumen_inventario.md`, `indice_inventario.json` e `inventory_summary.json`.

---

## Outputs generados (con `--write`)

```
expediente/
└── inventario/
    ├── FI-001_clima.md
    ├── FI-002_geologia.md
    ├── ...
    ├── FI-016_riesgos_naturales.md
    ├── resumen_inventario.md
    ├── indice_inventario.json
    └── inventory_summary.json
```

---

## Lógica de semáforo

El semáforo de FI-001 se calcula automáticamente con `classify_semaphore_from_evidence` (IV-00):

- `CONFIRMADO_GABINETE` + sin gaps → `VERDE`
- `DECLARADO` o gaps activos → `AMARILLO` o superior según gaps
- `PENDIENTE` + gaps → `ROJO_AMARILLO` o similar

Los factores base (FI-002…FI-016) reciben `NO_CONSTA` directamente, sin pasar por `classify_semaphore_from_evidence`.

---

## Uso típico

```python
from eia_agent.core.inventory_builder import build_inventory_from_phase4

# Modo lectura
result = build_inventory_from_phase4("expediente-EIA-2026-001")
print(result.summary())

# Modo escritura
result = build_inventory_from_phase4(
    "expediente-EIA-2026-001",
    write_outputs=True,
    output_dir="inventario",
)
for f in result.rendered_files:
    print(f)
```

---

## Dependencias

| Módulo | Ítem | Estado |
|--------|------|--------|
| `inventory_model.py` | IV-00 | COMPLETADO |
| `inventory_renderer.py` | IV-01 | COMPLETADO |
| `json` (stdlib) | — | — |
| `pathlib` (stdlib) | — | — |
| `dataclasses` (stdlib) | — | — |

Sin dependencias externas. Sin IA. Sin web. Sin APIs.

---

## Tests

Fichero: `tests/test_inventory_builder.py` — **117 tests en 9 clases**

| Clase | Tests | Cobertura |
|-------|-------|-----------|
| TestLoadJsonFile | 8 | válido, not found, JSON inválido, str/Path, vacío, error msg |
| TestInventoryBuildResult | 9 | to_dict, JSON serializable, summary, warnings, notes |
| TestBuildClimateFactorComplete | 18 | evidencia, semáforo, desc, fuentes, notas, justif |
| TestBuildClimateFactorPartial | 12 | DECLARADO, gap, warning propagation |
| TestBuildClimateFactorEdge | 11 | sin estación, LEJANA, propagación upstream, factor_id |
| TestBuildBaseFactor | 15 | todos los FI-002…FI-016, gap pattern, custom reason, FI-001 base |
| TestBuildInventoryFromPhase4Data | 13 | 16 factores, clima/no-clima, orden, warnings |
| TestBuildInventoryFromPhase4 | 15 | FileNotFoundError, lectura, write, custom dirs, JSON |
| TestFixtureLanzarote | 16 | BWh, C029O, VERDE, ready, write 16 fichas, JSON serializable |

### Ejecutar tests

```bash
venv/Scripts/python -m unittest tests.test_inventory_builder
venv/Scripts/python -m unittest discover -s tests
```

---

*Generado por IV-02 — Constructor de inventario ambiental desde Fase 4 offline.*  
*Siguiente: IV-03 (fichas de inventario por factor desde fuentes WMS/AEMET).*
