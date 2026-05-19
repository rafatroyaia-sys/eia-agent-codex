# INVENTORY_RENDERER — IV-01
## Templates de fichas de inventario ambiental

Módulo: `src/eia_agent/core/inventory_renderer.py`  
Ítem: IV-01 | Estado: **COMPLETADO**  
Tests: `tests/test_inventory_renderer.py` (143 tests)  
Prerequisito: IV-00 (`inventory_model.py`)

---

## Qué hace

Convierte objetos `FactorInventory` e `InventorySummary` (definidos en IV-00) en
ficheros Markdown de inventario ambiental estructurados, listos para incluir en el
expediente EIA.

Genera:
- Una ficha `.md` por factor ambiental (FI-001…FI-016)
- Un resumen consolidado `resumen_inventario.md`
- Un índice de metadatos `indice_inventario.json`

---

## Qué NO hace

- **No consulta fuentes externas** — solo trabaja con los objetos que recibe.
- **No inventa datos** — si un campo está vacío, lo indica explícitamente ("NO CONSTA").
- **No valora impactos** — las fichas son de inventario, no de valoración.
- **No genera Fase 6** — el módulo no toma decisiones sobre impactos ni medidas.
- **No usa IA** — transformación puramente determinista.
- **No llama a APIs** — sin AEMET, sin Mapbox, sin WMS.

---

## Relación con IV-00

IV-00 define el modelo de datos (`FactorInventory`, `InventorySummary`, `InventoryGap`).  
IV-01 (este módulo) toma esos objetos y los renderiza como documentación Markdown.

```
IV-00 inventory_model.py
  └── FactorInventory ──► IV-01 inventory_renderer.py ──► FI-001_clima.md
  └── InventorySummary ──►                              ──► resumen_inventario.md
  └── InventoryGap ──►                                  ──► indice_inventario.json
```

---

## API

### `InventoryRenderConfig`

Configuración del renderizado.

```python
@dataclass
class InventoryRenderConfig:
    include_header: bool = True                # incluir título # FI-XXX
    include_gap_table: bool = True             # incluir tabla de gaps
    include_readiness_section: bool = True     # incluir sección 7 (Fase 6)
    include_methodological_note: bool = True   # incluir nota al pie
    language: str = "es"

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> InventoryRenderConfig: ...
```

### `InventoryRenderResult`

Resultado del proceso de escritura a disco.

```python
@dataclass
class InventoryRenderResult:
    factor_files: list[str]      # rutas absolutas de las fichas generadas
    summary_file: str | None     # ruta de resumen_inventario.md
    index_file: str | None       # ruta de indice_inventario.json
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict: ...
    def summary(self) -> str: ...
```

### `safe_factor_filename(factor) -> str`

Genera nombre de archivo seguro: sin tildes, sin espacios, minúsculas, `.md`.

```python
safe_factor_filename(FactorInventory("FI-001"))  # → "FI-001_clima.md"
safe_factor_filename(FactorInventory("FI-015"))  # → "FI-015_cambio_climatico.md"
```

Todos los 16 nombres generados son únicos.

### `render_factor_inventory_markdown(factor, config=None) -> str`

Renderiza un `FactorInventory` como string Markdown.

### `render_inventory_summary_markdown(summary, config=None) -> str`

Renderiza un `InventorySummary` como string Markdown.

### `build_inventory_index(summary, factor_filenames=None) -> dict`

Construye el diccionario JSON serializable del índice de inventario.

### `write_inventory_markdown_files(summary, output_dir, config=None) -> InventoryRenderResult`

Escribe todos los ficheros en `output_dir` (se crea si no existe).

---

## Estructura de una ficha FI

Cada ficha tiene 8 secciones obligatorias:

```markdown
# FI-XXX -- Nombre del factor

## 1. Estado de la informacion
- Estado de evidencia: ...
- Modo de trabajo: ...
- Semaforo de inventario: ...
- Preparado para valoracion de impactos: Si/No

## 2. Descripcion del factor
<texto o "NO CONSTA INFORMACION DESCRIPTIVA SUFICIENTE.">

## 3. Fuentes de datos
- fuente 1
- fuente 2
<o "NO CONSTA FUENTE DOCUMENTAL ESPECIFICA.">

## 4. Justificacion del modo de trabajo
<texto o "NO CONSTA JUSTIFICACION ESPECIFICA.">

## 5. Justificacion del semaforo
<texto o "NO CONSTA JUSTIFICACION ESPECIFICA.">

## 6. Gaps y limitaciones
| Gap ID | Campo | Descripcion | Criticidad | Resolucion | Estado |
<o "No se han registrado gaps especificos para este factor.">

## 7. Preparacion para Fase 6
<"LISTO" o "NO esta listo... no debe utilizarse sin revision previa">

## 8. Notas y advertencias
<warnings, notes, avisos de prudencia si proceden>

---
*Esta ficha forma parte del inventario ambiental de gabinete...*
```

---

## Estructura del resumen de inventario

`resumen_inventario.md` contiene 6 secciones:

1. **Expediente** — ID, total factores, listos para Fase 6
2. **Estado general** — métricas de `InventorySummary` (total, ready, campo, rojo, gaps críticos, all_ready_for_phase6)
3. **Tabla de factores** — una fila por factor con Factor, Nombre, Tipo, Evidencia, Modo, Semáforo, Ready, Gaps críticos
4. **Factores por semáforo** — conteo agrupado por VERDE/AMARILLO/ROJO/etc.
5. **Factores que requieren trabajo de campo** — los que tienen CAMPO_RECOMENDADO o CAMPO_NECESARIO
6. **Advertencias y notas** — del `InventorySummary`

Incluye aviso de bloqueo si `all_ready_for_phase6` es `False`.

---

## Qué es `indice_inventario.json`

Fichero JSON serializable con metadatos para trazabilidad e integración posterior:

```json
{
  "expediente_id": "EIA-2026-001",
  "total_factors": 16,
  "ready_count": 0,
  "all_ready_for_phase6": false,
  "factors": [
    {
      "factor_id": "FI-001",
      "factor_name": "Clima",
      "semaphore": "VERDE",
      "ready": true,
      "filename": "FI-001_clima.md"
    },
    ...
  ]
}
```

---

## Reglas de prudencia aplicadas

### 1. Lenguaje de valoración de impacto prohibido

Si en los campos `description`, `warnings` o `notes` de un factor aparecen los
términos **COMPATIBLE, MODERADO, SEVERO, CRÍTICO** (en cualquier forma: moderado/a,
severo/a, crítico/a, con o sin tilde), el renderizador añade un aviso en la
sección 8:

```
AVISO DE PRUDENCIA: Se han detectado terminos de valoracion de impacto
(MODERADO) en los campos de esta ficha. Las fichas de inventario NO deben
contener valoracion de impactos...
```

La detección usa raíces (stems) para capturar formas flexionadas:
- `compatible` → compatible (invariable)
- `moderad` → moderado, moderada, moderados, moderadas
- `sever` → severo, severa, severos, severas
- `critic` → crítico, crítica, críticos, críticas

### 2. Campo vacío → "NO CONSTA"

Los campos vacíos nunca se omiten ni se inventan. Se indica explícitamente:
- `description` vacía → "NO CONSTA INFORMACION DESCRIPTIVA SUFICIENTE."
- `data_sources` vacío → "NO CONSTA FUENTE DOCUMENTAL ESPECIFICA."
- `field_mode_justification` vacío → "NO CONSTA JUSTIFICACION ESPECIFICA."
- `semaphore_justification` vacío → "NO CONSTA JUSTIFICACION ESPECIFICA."

### 3. Factor no listo → texto de bloqueo

Si `ready_for_impact_assessment=False`, la sección 7 incluye:
> "Este factor no debe utilizarse para valoracion de impactos sin revision previa."

### 4. Inventario no listo → nota de bloqueo en resumen

Si `all_ready_for_phase6=False`, el resumen incluye:
> "El inventario no debe avanzar a Fase 6 si all_ready_for_phase6 es False."

---

## Nombres de archivo generados

| Factor | Archivo |
|--------|---------|
| FI-001 Clima | `FI-001_clima.md` |
| FI-002 Geología | `FI-002_geologia.md` |
| FI-003 Suelos | `FI-003_suelos.md` |
| FI-004 Hidrología | `FI-004_hidrologia.md` |
| FI-005 Inundabilidad | `FI-005_inundabilidad.md` |
| FI-006 Calidad del aire | `FI-006_calidad_del_aire.md` |
| FI-007 Flora | `FI-007_flora.md` |
| FI-008 Fauna | `FI-008_fauna.md` |
| FI-009 Espacios Naturales Protegidos | `FI-009_espacios_naturales_protegidos.md` |
| FI-010 Red Natura 2000 | `FI-010_red_natura_2000.md` |
| FI-011 Paisaje | `FI-011_paisaje.md` |
| FI-012 Patrimonio cultural | `FI-012_patrimonio_cultural.md` |
| FI-013 Socioeconomía | `FI-013_socioeconomia.md` |
| FI-014 Ruido | `FI-014_ruido.md` |
| FI-015 Cambio climático | `FI-015_cambio_climatico.md` |
| FI-016 Riesgos naturales | `FI-016_riesgos_naturales.md` |

---

## Uso típico

```python
from eia_agent.core.inventory_model import build_all_empty_factors, build_inventory_summary
from eia_agent.core.inventory_renderer import write_inventory_markdown_files, InventoryRenderConfig

# Construir inventario
factors = build_all_empty_factors()
summary = build_inventory_summary("EIA-2026-001", factors)

# Escribir fichas
result = write_inventory_markdown_files(summary, "expediente/fichas_inventario/")
print(result.summary())
# → Renderizado: 16 fichas de factor generadas.
#   Resumen: .../resumen_inventario.md
#   Indice JSON: .../indice_inventario.json

# Renderizar una sola ficha sin escribir
from eia_agent.core.inventory_renderer import render_factor_inventory_markdown
md = render_factor_inventory_markdown(factors[0])
print(md[:200])
```

---

## Dependencias

| Módulo | Ítem | Estado |
|--------|------|--------|
| `inventory_model.py` | IV-00 | COMPLETADO |
| `unicodedata` (stdlib) | — | — |
| `json` (stdlib) | — | — |
| `pathlib` (stdlib) | — | — |
| `dataclasses` (stdlib) | — | — |

Sin dependencias externas. Sin IA. Sin web. Sin APIs.

---

## Tests

Fichero: `tests/test_inventory_renderer.py` — **143 tests en 8 clases**

| Clase | Tests | Cobertura |
|-------|-------|-----------|
| TestInventoryRenderConfig | 9 | to_dict, from_dict, roundtrip, defaults, classmethod |
| TestSafeFactorFilename | 21 | todos los 16 factores, sin tildes, sin espacios, únicos |
| TestRenderFactorMarkdown | 33 | 8 secciones, evidencia, semáforo, fuentes, gaps, NO CONSTA, nota metodológica |
| TestPrudenceRules | 10 | compatible/moderado/severo/crítico en desc/warnings/notes, formas femeninas |
| TestRenderSummaryMarkdown | 22 | título, tabla, semáforos, campo, bloqueo, warnings, notas |
| TestBuildInventoryIndex | 13 | dict, JSON, filenames, all_ready_for_phase6 |
| TestWriteInventoryFiles | 14 | 16 fichas, resumen, índice, solo en output_dir, JSON cargable |
| TestFixtureLanzarote | 15 | FI-001 Clima BWh, CL-06, VERDE, ready=True, write 16 files |

### Ejecutar tests

```bash
venv/Scripts/python -m unittest tests.test_inventory_renderer
venv/Scripts/python -m unittest discover -s tests
```

---

*Generado por IV-01 — Templates de fichas de inventario ambiental.*  
*Siguiente: IV-02 (semáforo de campo programático).*
