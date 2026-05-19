# OBJECT_SCOPE_BUILDER — OB-01

**Módulo**: `src/eia_agent/core/object_scope_builder.py`  
**Tests**: `tests/test_object_scope_builder.py` — 70 tests OK  
**Dependencias**: `evidence_classifier.py` (ClassificationResult)  
**Regla de oro**: No escribe nada automáticamente. No usa IA. No resuelve contradicciones.

---

## Propósito

Construye la ficha estructurada del objeto evaluado (`ObjectScope`) a partir de un
`ClassificationResult` (IN-03) y/o overrides explícitos del usuario. Es la pieza central
del GATE 2 (Cierre del objeto evaluado).

---

## API pública

### `build_object_scope(expediente_id, classification=None, overrides=None) → ObjectScope`

Función principal. Combina datos de la clasificación con overrides. Siempre recalcula
`estado_gate2` al final.

```python
from eia_agent.core.object_scope_builder import build_object_scope

scope = build_object_scope(
    "expediente-EIA-2026-RECIMETAL-PARCELA",
    classification=classification_result,
    overrides={"modo": "GABINETE", "operaciones_excluidas": ["R1302"]},
)
print(scope.to_markdown())
```

### `ObjectScope` — dataclass

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | ID del expediente |
| `titular` | str \| None | Nombre del promotor/titular |
| `referencia_catastral` | str \| None | RC de la parcela |
| `coordenadas_wgs84` | list[str] | Coordenadas decimales (sin prefijo "DEC") |
| `coordenadas_utm` | list[str] | Coordenadas UTM (sin prefijo "UTM") |
| `operaciones_incluidas` | list[str] | Códigos de operación incluidos |
| `operaciones_excluidas` | list[str] | Códigos excluidos del objeto evaluado |
| `modo` | str | GABINETE \| CAMPO \| NO_DECLARADO |
| `superficie_m2` | str \| None | Superficie (cualquier subtipo) |
| `capacidad` | str \| None | Capacidad de gestión |
| `at_activos` | list[str] | Asunciones de test activas |
| `gaps` | list[str] | Gaps identificados |
| `estado_gate2` | str | APTO \| PENDIENTE \| BLOQUEADO |
| `fuentes` | list[str] | IDs documentales (e.g. "DOC-001") |
| `notes` | list[str] | Notas internas (modo inválido, etc.) |

### Métodos de `ObjectScope`

- `from_classification(result, expediente_id)` — constructor alternativo desde ClassificationResult
- `to_markdown()` — genera ficha de 10 secciones en Markdown
- `to_dict()` — serialización completa (via `dataclasses.asdict`)
- `from_dict(data)` — reconstrucción desde dict (e.g. JSON cargado)

### Funciones de escritura y carga

```python
write_object_scope_markdown(scope, output_path)  # escribe .md
write_object_scope_json(scope, output_path)       # escribe .json UTF-8 indentado
load_object_scope_json(path)                      # carga ObjectScope desde JSON
```

Ninguna se llama automáticamente. El llamador decide cuándo y dónde escribir.

---

## Extracción desde ClassificationResult

`from_classification` extrae los campos en este orden de prioridad:

| Campo ObjectScope | Fuente en ClassificationResult |
|-------------------|-------------------------------|
| `titular` | `nombre_promotor` HIGH confidence → cualquier confianza → `titular` |
| `referencia_catastral` | `referencia_catastral` (primero) |
| `coordenadas_wgs84` | `coordenadas_wgs84` — valor con prefijo "DEC " eliminado |
| `coordenadas_utm` | `coordenadas_utm` — valor con prefijo "UTM " eliminado |
| `operaciones_incluidas` | `operacion_residuos` |
| `superficie_m2` | Primera de: parcela → catastral → construida → util → nave → no_clasificada |
| `capacidad` | `capacidad` (primero) |
| `fuentes` | Todos los `fuentes` de todos los facts (únicos, orden de aparición) |

Campos no extraíbles: `modo="NO_DECLARADO"`, `operaciones_excluidas=[]`, `at_activos=[]`, `gaps=[]`.

---

## Lógica de `estado_gate2`

```
BLOQUEADO  → si NO titular Y NO RC Y NO coordenadas
APTO       → si titular Y RC Y coordenadas Y operaciones_incluidas
PENDIENTE  → cualquier otro caso (datos parciales)
```

Siempre se recalcula tras aplicar los overrides.

---

## Overrides

`build_object_scope` acepta un dict `overrides` con estas claves:

**Escalares**: `titular`, `referencia_catastral`, `modo`, `superficie_m2`, `capacidad`

**Listas** (reemplazo completo): `coordenadas_wgs84`, `coordenadas_utm`,
`operaciones_incluidas`, `operaciones_excluidas`, `at_activos`, `gaps`, `fuentes`, `notes`

Si `modo` no está en `{GABINETE, CAMPO, NO_DECLARADO}`, se añade nota a `notes` y
se resetea a `NO_DECLARADO`.

---

## Ficha Markdown — 10 secciones obligatorias

```
## 1. Identificación del promotor/titular
## 2. Emplazamiento
## 3. Operaciones autorizadas/solicitadas
## 4. Operaciones excluidas del objeto evaluado
## 5. Superficies y capacidades
## 6. Modo de trabajo
## 7. Asunciones de test activas
## 8. Gaps identificados
## 9. Estado del gate 2
## 10. Fuentes documentales
```

Los campos ausentes se muestran como `NO DECLARADO`. Las 10 secciones están siempre presentes.

---

## Reglas de uso

1. No llamar a `write_*` dentro de tests que apunten a expedientes reales.
2. `build_object_scope` nunca escribe — solo construye el objeto en memoria.
3. El `estado_gate2` es siempre el resultado de la lógica determinista, no un campo libre.
4. Los prefijos "DEC "/"UTM " son artefactos del clasificador para disambiguación y
   no deben aparecer en el ObjectScope final.

---

## Tests

`tests/test_object_scope_builder.py` — 70 tests, 8 clases:

| Clase | Tests | Cobertura |
|-------|-------|-----------|
| `TestFromClassification` | 15 | Extracción de cada campo, titular HIGH confidence, coordenadas, surface priority |
| `TestOverrides` | 10 | Overrides escalares y listas, modo inválido, sin classification |
| `TestEstadoGate2` | 8 | APTO/PENDIENTE/BLOQUEADO con combinaciones de campos |
| `TestToMarkdown` | 11 | 10 secciones presentes, NO DECLARADO para vacíos, emojis AT/gaps |
| `TestToDict` | 3 | Round-trip dict, from_dict campos faltantes |
| `TestWriteMarkdown` | 4 | Escritura en temp, no escritura en piloto |
| `TestWriteLoadJson` | 8 | Round-trip JSON, FileNotFoundError, JSON inválido |
| `TestFixtureParcela` | 10 | Fixture real PARCELA: solo lectura, modo GABINETE, fuentes DOC-001 |
