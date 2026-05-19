# PROJECT_ACTION_BUILDER — IM-02

Constructor de acciones del proyecto desde Fase 2.

**Módulo**: `src/eia_agent/core/project_action_builder.py`  
**ID de productización**: IM-02  
**Completado**: 2026-05-04  
**Dependencias**: IM-00 (`impact_model`), IV-00 (`inventory_model`, opcional)

---

## Qué hace IM-02

Extrae texto de los datos de Fase 2 (`phase2_result.json`), detecta términos de operaciones
por grupos predefinidos y construye una lista ordenada de `ProjectAction` para poblar el
campo `actions` de un `Phase6Model`.

1. **`extract_project_action_text(phase2_data)`** — Extrae y normaliza texto de dicts/listas anidados.
2. **`detect_project_operations(text)`** — Detecta términos por grupo (7 grupos).
3. **`build_actions_from_phase2_data(phase2_data)`** — Constructor principal. Devuelve `ProjectActionBuildResult`.
4. **`merge_actions_into_phase6_model(model, actions)`** — Sustituye las acciones de un `Phase6Model` sin mutarlo.
5. **`build_phase6_model_with_actions(expediente_id, phase2_data, inventory_summary)`** — Crea `Phase6Model` completo con acciones y (opcionalmente) factores receptores.

## Qué NO hace IM-02

| Capacidad | Estado |
|-----------|--------|
| Identificar impactos (acción × factor) | No — tarea del analista / futura IM |
| Valorar impactos con Conesa | No — IM-01 |
| Generar medidas correctoras | No — IM-03 |
| Generar fichas PVA | No — IM-04 |
| Redactar bloques del Documento Ambiental | No — Fase 7 |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Escribir archivos desde el módulo | No — responsabilidad de la CLI o el llamador |

---

## Grupos de acciones detectadas

| Grupo | Tipo de acción | Operation code | Términos clave |
|-------|---------------|----------------|----------------|
| `recepcion_almacenamiento` | `ALMACENAMIENTO` | R13 / R1301 / R1302 | recepci, almacenamiento, acopio, r13, r1301, r1302 |
| `clasificacion_separacion` | `OPERACION` | R1201 | clasificaci, separaci, selecci, triaje, r1201 |
| `tratamiento_mecanico` | `OPERACION` | R1203 | trituraci, triturado, molino, cizalla, corte, prensa, compactaci, cribado, r1203 |
| `carga_descarga_transporte` | `TRANSPORTE` | — | carga, descarga, expedici, transporte, camion, carretilla |
| `maquinaria_auxiliar` | `AUXILIAR` | — | compresor, bascula, maquinaria, equipo, motor, diesel, electricidad |
| `gestion_residuos_peligrosos` | `MANTENIMIENTO` | — | residuo peligroso, aceite, absorbente, filtro, bateria, raee, ler*, patrón XX XX XX* |
| `cese_limpieza` | `CESE` | — | cese, desmantelamiento, limpieza final, retirada, clausura |

Si no se detecta ningún grupo, se genera una acción mínima `AC-001` de tipo `OTRO` con aviso.

---

## Normalización de texto

`extract_project_action_text` normaliza el texto antes de la detección:
- Elimina acentos via `unicodedata.normalize("NFKD")` + codificación ASCII.
- Convierte a minúsculas.

Esto permite detectar "trituración" → "trituraci", "báscula" → "bascula", "camión" → "camion"
sin necesidad de incluir variantes acentuadas en los términos de detección.

---

## Asignación de IDs AC-NNN

Los IDs son correlativos, comenzando en `AC-001`, en el orden declarado de grupos:
1. recepcion_almacenamiento → AC-001 (si detectado)
2. clasificacion_separacion → AC-002 (si detectado)
3. tratamiento_mecanico → ...
4. carga_descarga_transporte → ...
5. maquinaria_auxiliar → ...
6. gestion_residuos_peligrosos → ...
7. cese_limpieza → AC-N (último)

Un grupo que no se detecta no recibe ID. Los IDs resultantes siempre son correlativos
sin huecos.

---

## API pública

### `ProjectActionBuildResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `actions` | `list[ProjectAction]` | Acciones detectadas |
| `warnings` | `list[str]` | Avisos (datos ausentes, acción mínima generada) |
| `notes` | `list[str]` | Notas de trazabilidad |

Métodos: `to_dict()`, `summary()`.

### `extract_project_action_text(phase2_data)`

```python
extract_project_action_text(phase2_data: dict | None = None) -> str
```

Devuelve texto normalizado. No falla con None o estructura inesperada.

Claves que extrae (en cualquier nivel de anidamiento): `object_scope`, `ficha_objeto_evaluado`,
`operaciones_incluidas`, `operaciones_excluidas`, `operaciones`, `actividad`, `actividades`,
`maquinaria`, `equipos`, `capacidad`, `residuos`, `ler`, `notes`, `warnings`, `scope`, `datos`,
`description`, `descripcion`, `denominacion`, `materiales`, `nombre_proyecto`.

### `detect_project_operations(text)`

```python
detect_project_operations(text: str) -> dict[str, list[str]]
```

Devuelve dict con los 7 grupos. Cada valor es la lista de términos encontrados (vacía si ninguno).
Incluye detección especial de códigos LER peligrosos via regex `\d{2}\s*\d{2}\s*\d{2}\s*\*`.

### `build_actions_from_phase2_data(phase2_data)`

```python
build_actions_from_phase2_data(phase2_data: dict | None = None) -> ProjectActionBuildResult
```

Constructor principal. Función pura sin efectos secundarios.

### `merge_actions_into_phase6_model(model, actions)`

```python
merge_actions_into_phase6_model(
    model: Phase6Model,
    actions: list[ProjectAction],
) -> Phase6Model
```

Devuelve nueva instancia de `Phase6Model` (no muta el original).
Conserva `receptor_factors`, `impacts`, `measures`, `pva_programs`.

### `build_phase6_model_with_actions(expediente_id, phase2_data, inventory_summary)`

```python
build_phase6_model_with_actions(
    expediente_id: str,
    phase2_data: dict | None = None,
    inventory_summary: InventorySummary | None = None,
) -> Phase6Model
```

Combina `build_empty_phase6_model` + `build_actions_from_phase2_data` + `merge_actions_into_phase6_model`.
Si se proporciona `inventory_summary`, puebla `receptor_factors` con los 16 factores de Fase 5.
`impacts`, `measures` y `pva_programs` siempre vacíos.

---

## CLI

```bash
# Solo lectura (no escribe nada)
python run_expediente.py <expediente> phase6-actions

# Escribe impactos/phase6_actions.json e impactos/phase6_model_base.json
python run_expediente.py <expediente> phase6-actions --write
```

**Comportamiento**:
- Lee `control_interno/phase2_result.json` (opcional; si no existe, genera acción mínima).
- Sin `--write`: imprime resumen de acciones, exit 0.
- Con `--write`: escribe los dos JSONs en `impactos/`, crea el directorio si no existe.
- Si el JSON de Fase 2 está malformado, imprime error y sale con código 1.

---

## Relación con IM-00, IM-01, Fase 2 y Fase 5

```
Fase 2 (phase2_result.json)
    │
    ▼
extract_project_action_text() → detect_project_operations()
    │
    ▼
build_actions_from_phase2_data() → ProjectActionBuildResult
    │
    ▼
merge_actions_into_phase6_model() → Phase6Model.actions
    │
    ├── IM-01 (conesa_engine) → score_phase6_impacts()  [futuro]
    ├── IM-03 (medidas) [futuro]
    └── IM-04 (PVA) [futuro]

Fase 5 (InventorySummary)
    │
    ▼
build_phase6_model_with_actions(inventory_summary=...) → Phase6Model.receptor_factors
```

---

## Cómo ejecutar los tests

```bash
# Solo IM-02
venv\Scripts\python -m unittest tests.test_project_action_builder

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_project_action_builder.py`  
**Tests**: 106 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestExtractProjectActionText` | 10 | None→vacío, dict/list recursivo, acentos normalizados, lowercase, claves maquinaria/residuos, lista anidada de dicts |
| `TestDetectProjectOperations` | 27 | Todos los grupos vacíos con texto vacío, R13/R1301/R1302, R1201 (no polución a otros), R1203, trituración, cizalla, molino, carretilla, carga, camion, compresor, báscula, diesel, residuo peligroso, aceite, batería, RAEE, ler*, patrón LER XX XX XX*, cese, desmantelamiento, limpieza final, retirada, tipos de retorno |
| `TestBuildActionsFromPhase2Data` | 26 | None→mínima+warning, dict vacío→mínima, R13→ALMACENAMIENTO, R1301→R1301, R1302→R1302, R1201→OPERACION+code, R1203→OPERACION, trituración, carga/descarga/carretilla→TRANSPORTE, compresor/báscula→AUXILIAR, residuos peligrosos/LER*→MANTENIMIENTO, cese/desmantelamiento→CESE, IDs correlativos, sin duplicados por grupo, múltiples grupos, source_refs, notas con términos, OTRO mínimo, tipo de retorno |
| `TestProjectActionBuildResult` | 6 | to_dict JSON serializable, claves requeridas, actions como dicts, summary no vacío, count en summary, action_id en summary |
| `TestMergeActionsIntoPhase6Model` | 9 | Sustituye actions, preserva receptor_factors/impacts/measures/pva, no muta original, nueva instancia, lista vacía, expediente_id |
| `TestBuildPhase6ModelWithActions` | 9 | Actions creadas, expediente_id, sin impacts/measures/pva, con/sin inventory_summary, tipo Phase6Model, acción mínima sin Fase 2 |
| `TestCLIPhase6Actions` | 6 | Sin --write no crea archivos, con --write crea los 2 JSONs, JSON válido, sin phase2_result→exit 0 + mínima, warnings en JSON |
| `TestMethodologicalRules` | 13 | No "impacto" en descripción, no palabras de significancia, no EnvironmentalImpact/MitigationMeasure/PVAProgram, términos en notas, tipos en ACTION_TYPES, IDs únicos, patrón AC-NNN |

---

## Decisión de ID canónico

En el momento de implementar IM-02, el backlog canónico ya tenía:
- IM-01: Motor Conesa ✅
- IM-02: Constructor medidas correctoras (sin código)
- IM-03: Constructor fichas PVA (sin código)
- IM-04: PVA genérico Compatible (sin código)
- IM-05: Validador cobertura PVA (sin código)

El "Constructor de acciones del proyecto desde Fase 2" es un paso necesario antes de
identificar impactos (acción × factor), que a su vez es prerequisito para medidas y PVA.
Se insertó como IM-02 y se reasignaron los IDs existentes: IM-02→IM-03, IM-03→IM-04,
IM-04→IM-05, IM-05→IM-06. Ninguno de los ítems desplazados tenía código implementado.

---

*Generado por EIA-Agent v2.1 — IM-02 — 2026-05-04*
