# PRUDENCE_VALIDATOR — AU-02

Módulo: `src/eia_agent/core/prudence_validator.py`  
CLI: `python run_expediente.py <expediente> audit-prudence [--write]`  
Tests: `tests/test_prudence_validator.py` (109 tests)

---

## Propósito

Detecta **lenguaje metodológicamente imprudente** en textos del expediente EIA: frases que afirman ausencias, descartan impactos, o califican significancias sin evidencia de campo. Implementa la Regla 4 de `CLAUDE.md`, §6 de `SYSTEM_BASE` (anti-despreciable) y la observación OBS-M12-003.

**No corrige textos. No modifica el expediente. No declara aptitud administrativa.**

---

## Frases prohibidas por categoría

| Categoría | Ejemplos representativos |
|-----------|--------------------------|
| `general` | `sin afeccion`, `no hay impacto`, `se descarta`, `despreciable`, `nulo` |
| `inventory` | `compatible`, `moderado`, `severo`, `critico`, `significativo` |
| `red_natura` | `sin afeccion apreciable`, `fuera de red natura`, `no afecta a red natura` |
| `biodiversity` | `no hay flora`, `no hay fauna`, `sin especies protegidas`, `sin habitats` |
| `heritage` | `no hay patrimonio`, `sin yacimientos`, `sin afeccion patrimonial` |
| `noise_air` | `sin ruido`, `sin emisiones`, `cumple limites acusticos` |
| `hydrology` | `no hay cauces`, `sin escorrentia`, `sin afeccion hidrologica` |
| `climate` | `emisiones despreciables`, `carbono neutro`, `riesgo climatico bajo` |

### Severidades

- **ERROR**: cierres indebidos fuertes (`sin afeccion`, `no hay impacto`, `se descarta`, `no hay flora/fauna`...).
- **WARNING**: lenguaje débil sin medición (`despreciable`, `irrelevante`, `nulo`, `compatible`, `moderado`...).
- **INFO**: frase detectada en contexto metodológico (texto de prohibición — el validador la menciona para documentarla, no como uso real).

---

## Regla de contexto metodológico

Si una frase prohibida aparece dentro de una ventana de ±150 caracteres que contiene un indicador metodológico (`prohibido`, `no debe decir`, `no usar`, `evitar`, `lenguaje prohibido`...), se genera `INFO` en lugar de `ERROR`/`WARNING`.

Esto permite que documentos de auditoría y prompts que citan las frases prohibidas no se autoincriminen.

---

## API pública

### `normalize_prudence_text(text) -> str`

Normaliza texto para detección: quita tildes (NFKD → ASCII), minúsculas, normaliza espacios y saltos de línea. No elimina puntuación.

### `find_forbidden_phrases(text, source, category) -> list[PrudenceIssue]`

Busca frases prohibidas de la categoría indicada. `category="all"` aplica todas.

### `validate_inventory_prudence(summary: InventorySummary) -> PrudenceValidationResult`

Valida un inventario completo. Revisa `description`, `notes`, `warnings` y `gaps` de cada `FactorInventory`. Aplica categorías según el `factor_id`:
- `FI-007/008` → general + inventory + biodiversity
- `FI-009/010` → general + inventory + red_natura
- `FI-012` → general + inventory + heritage
- `FI-006/014` → general + inventory + noise_air
- `FI-004/005/016` → general + inventory + hydrology
- `FI-015` → general + inventory + climate
- Resto → general + inventory

### `validate_phase6_prudence(model: Phase6Model) -> PrudenceValidationResult`

Valida un `Phase6Model`. Detecta:
- Frases prohibidas (general) en textos libres de impactos, medidas y PVA.
- Frases de biodiversidad/red natura/patrimonio en receptores sensibles (`FR-007/008/009/010/012`).
- Cierres indebidos en impactos `INDETERMINADO` con receptores sensibles → `AU02-E002`.
- Compensación de impactos negativos con positivos → `AU02-E003`.
- Medidas `PRL_NO_EIA` con lenguaje de correctora ambiental → `AU02-W002`.

**Nota:** `COMPATIBLE/MODERADO/SEVERO/CRITICO` son **válidos** como significancias tipadas en `Phase6Model` — no se marcan como error.

### `validate_markdown_prudence(markdown, source, category) -> PrudenceValidationResult`

Valida un string markdown. Si `category="all"`, aplica todas las categorías.

### `validate_prudence_from_files(expediente_path) -> PrudenceValidationResult`

Escanea los markdowns del expediente en los directorios:
- `inventario/*.md`
- `impactos/*.md`
- `bloques/*.md` (si existe)
- `auditoria/*.md` (si existe)

No escanea `docs/`, `prompts/`, `control_interno/`, `src/`, `tests/`.

Si no hay markdowns: devuelve `WARNING`, no excepción.  
Si el directorio no existe: lanza `FileNotFoundError`.

### `build_prudence_report_markdown(result) -> str`

Genera informe en markdown con 7 secciones: resumen, fuentes, ERRORs, WARNINGs, INFOs, recomendaciones, advertencia de alcance.

### `write_prudence_validation_outputs(result, output_dir) -> tuple[Path, Path]`

Escribe:
- `{output_dir}/prudence_validation_result.json`
- `{output_dir}/prudence_validation_result.md`

---

## CLI

```
python run_expediente.py <expediente> audit-prudence [--write]
```

**Sin `--write`**: imprime el resumen por consola. No crea archivos.  
**Con `--write`**: además escribe `auditoria/prudence_validation_result.json` y `.md`.

**Códigos de salida:**
- `0` — sin incidencias ERROR (`is_valid() == True`)
- `1` — hay incidencias ERROR, o el expediente no existe

---

## Modelos de datos

### `PrudenceIssue`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `severity` | str | `ERROR` / `WARNING` / `INFO` |
| `code` | str | `AU02-E001` / `AU02-W001` / `AU02-I001` / `AU02-E002` / `AU02-E003` / `AU02-W002` |
| `source` | str | Ruta relativa de la fuente (`inventario/FI-007/description`) |
| `phrase` | str | Frase prohibida detectada (normalizada) |
| `context` | str | Fragmento de contexto (máx. 200 chars) |
| `message` | str | Descripción de la incidencia |
| `recommendation` | str | Acción recomendada |

### `PrudenceValidationResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `issues` | list[PrudenceIssue] | Incidencias detectadas |
| `checked_sources` | list[str] | Fuentes revisadas |
| `warnings` | list[str] | Avisos del validador (no incidencias) |
| `notes` | list[str] | Notas informativas |

Métodos: `error_count()`, `warning_count()`, `info_count()`, `is_valid()`, `to_dict()`, `summary()`.

---

## Códigos de incidencia

| Código | Severidad | Condición |
|--------|-----------|-----------|
| `AU02-E001` | ERROR | Frase de cierre indebido en texto libre |
| `AU02-W001` | WARNING | Lenguaje débil (`despreciable`, `compatible`...) |
| `AU02-I001` | INFO | Frase en contexto metodológico (no es uso real) |
| `AU02-E002` | ERROR | Cierre indebido en impacto INDETERMINADO con receptor sensible |
| `AU02-E003` | ERROR | Compensación de impacto negativo con impacto positivo |
| `AU02-W002` | WARNING | Medida PRL con lenguaje de correctora ambiental |

---

## Principios de diseño

- **Función pura**: no muta los objetos de inventario ni Phase6Model.
- **Sin IA**: detección determinista por búsqueda de cadenas normalizadas.
- **Sin red**: no consulta fuentes externas.
- **ASCII-safe**: `summary()` normaliza NFKD para salida en consola Windows (cp1252).
- **Acumulativo**: combina resultados de múltiples fuentes en un único `PrudenceValidationResult`.
