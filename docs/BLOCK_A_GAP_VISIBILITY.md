# BLOCK_A_GAP_VISIBILITY — OB-04

**Módulo**: `src/eia_agent/core/block_a_gap_visibility.py`  
**Tests**: `tests/test_block_a_gap_visibility.py` — 65 tests OK  
**Dependencias**: ninguna interna (solo stdlib)  
**Regla de oro**: Solo valida visibilidad. No redacta. No modifica bloques. No usa IA.

---

## Propósito

Verifica programáticamente que los gaps de criticidad ALTA relacionados con
identidad/objeto evaluado aparecen mencionados **por código explícito** en las
secciones A.1 o A.3.1 del Bloque A del Documento Ambiental.

El problema que resuelve: un Bloque A puede contener información completa sobre
el promotor y el objeto evaluado sin mencionar explícitamente los gaps abiertos
(GAP-001, CONT-001, etc.). Esto deja al revisor sin traza entre los gaps del
expediente y la narrativa del documento.

---

## Diferencia entre visibilidad narrativa y resolución del gap

- **Visibilidad**: el código del gap (GAP-001, CONT-001...) aparece en A.1 o
  A.3.1 para que el lector sepa que existe una incidencia abierta.
- **Resolución**: el gap está aclarado, verificado o descartado. Esto es
  responsabilidad del promotor y del técnico, no de este módulo.

OB-04 solo valida visibilidad, no resolución.

---

## Por qué exige código explícito

Un gap documentado solo con texto descriptivo ("el titular no ha sido
verificado") podría referirse a cualquier incidencia. El código explícito
(GAP-001) crea una referencia trazable al registro en `inferencias_y_gaps.json`.

La heurística blanda ("parece hablar de este gap") introduce ambigüedad que
compromete la trazabilidad del expediente. Por eso la primera versión es estricta:
código explícito en A.1 o A.3.1.

---

## Por qué solo A.1 y A.3.1

- **A.1 Promotor y titular**: identifica al promotor, RC, titularidad. Los
  gaps de identidad personal/jurídica pertenecen aquí.
- **A.3.1 Objeto evaluado**: delimita exactamente qué se evalúa, coordenadas,
  operaciones incluidas/excluidas. Los gaps de delimitación pertenecen aquí.

Si el gap aparece solo en A.8 (observaciones) o en otra sección, no está
situado en el contexto del objeto evaluado → WARNING (no ERROR, porque hay
algo mejor que nada, pero no cumple el requisito pleno).

---

## API pública

### `check_block_a_gap_visibility(block_a_md, gaps_data, only_high=True) → GapVisibilityResult`

```python
from eia_agent.core.block_a_gap_visibility import check_block_a_gap_visibility

result = check_block_a_gap_visibility(bloque_a_text, gaps_data, only_high=True)
print(result.summary())
```

### `check_block_a_gap_visibility_from_files(block_a_path, gaps_json_path, only_high=True) → GapVisibilityResult`

Carga archivos desde disco. No escribe nada. Lanza `FileNotFoundError` si faltan.

### `GapVisibilityResult` — dataclass

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `passed` | bool | True si no hay ningún ERROR |
| `checked_gaps` | list[str] | Códigos de gaps revisados |
| `visible_gaps` | list[str] | Códigos visibles en A.1 o A.3.1 |
| `missing_gaps` | list[str] | Códigos no visibles en A.1/A.3.1 |
| `issues` | list[GapVisibilityIssue] | Incidencias detalladas |

Métodos: `error_count()`, `warning_count()`, `info_count()`, `is_blocked()`, `summary()`

### `GapVisibilityIssue` — dataclass

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | str | ERROR / WARNING / INFO |
| `code` | str | OB04-E001, OB04-W001, OB04-I001, OB04-I002 |
| `gap_id` | str\|None | Código del gap afectado |
| `message` | str | Descripción de la incidencia |
| `section` | str\|None | Sección donde se encontró (si aplica) |
| `recommendation` | str\|None | Acción recomendada |

### Funciones auxiliares

```python
extract_markdown_section(markdown_text, heading) -> str
normalize_criticality(value) -> str
is_identity_related_gap(item) -> bool
load_gaps_json(path) -> list[dict]
```

---

## Reglas de visibilidad

| Situación | Severidad | Código | `passed` |
|-----------|-----------|--------|---------|
| Gap ALTA visible en A.1 o A.3.1 | INFO | OB04-I002 | ✅ |
| Gap ALTA visible solo en otra sección de A | WARNING | OB04-W001 | ✅ |
| Gap ALTA no visible en ningún lugar del Bloque A | ERROR | OB04-E001 | ❌ |
| Sin gaps relevantes que revisar | INFO | OB04-I001 | ✅ |

---

## Filtro de gaps revisados

Un gap es revisado si cumple **ambas** condiciones:

1. **Criticidad alta** (si `only_high=True`): `normalize_criticality(item["criticidad"]) == "ALTA"`.
   Equivalencias: ALTA = CRÍTICA = CRITICA = BLOQUEANTE = CRITICAL.

2. **Identidad/objeto evaluado** (`is_identity_related_gap`): algún campo de texto del
   item contiene una de las palabras clave: titular, promotor, referencia catastral,
   catastral, coordenada, ubicacion/ubicación, emplazamiento, uso catastral, uso
   declarado, operacion incluida/excluida, objeto evaluado, delimitacion/delimitación,
   nave, parcela.

Gaps de inventario forestal, fauna, flora, ruido, calidad del aire, etc. **no se revisan**
aquí porque no afectan al objeto evaluado.

---

## Qué NO hace OB-04

- **No redacta**: no añade texto al Bloque A.
- **No confirma datos**: los gaps siguen siendo DECLARADO/PENDIENTE tras la validación.
- **No resuelve contradicciones**: detecta ausencia de mención, no la causa del gap.
- **No usa IA**: la detección es puramente textual y determinista.
- **No escribe en expedientes**: ni en piloto ni en producción.
- **No interpreta semánticamente**: no intenta deducir si "el promotor no ha sido
  verificado" se refiere a GAP-001. Solo busca el código explícito.

---

## Integración futura

- **OB-02** evalúa el ObjectScope antes del Gate 2; OB-04 verifica que los gaps
  abiertos son visibles en el Bloque A redactado.
- **NL-04 (GateChecker)** puede incorporar OB-04 como check adicional del Gate 7
  (Redacción) o del Gate 9 (Auditoría).
- **M-12 (Auditoría)** utilizará OB-04 para verificar coherencia entre
  `inferencias_y_gaps.json` y el Bloque A antes de emitir CONFORME.

---

## Cómo ejecutar tests

```bash
# Solo OB-04
venv\Scripts\python -m unittest tests.test_block_a_gap_visibility

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
