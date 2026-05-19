# Schema Validator — referencia tecnica

Item canonico: **NL-02**  
Modulo: `src/eia_agent/core/schema_validator.py`

---

## Diferencia entre NL-01 y NL-02

| | NL-01 | NL-02 |
|---|---|---|
| Que es | Los archivos `.schema.json` | El codigo Python que los usa |
| Donde vive | `config/schemas/v2_1/` | `src/eia_agent/core/schema_validator.py` |
| Rol | Define que estructura es valida | Valida un expediente real contra esa estructura |
| Salida | Schema JSON | `ValidationResult` con lista de `ValidationIssue` |

---

## Que valida NL-02

Para cada uno de los 6 archivos de capa en `capas/`:

1. **Existencia del archivo** — la capa esta presente en el directorio del expediente
2. **JSON valido** — el contenido se parsea sin errores
3. **Schema disponible** — el schema correspondiente existe en `config/schemas/v2_1/`
4. **Conformidad estructural** — el contenido pasa la validacion Draft 2020-12:
   - campos obligatorios presentes
   - tipos de datos correctos
   - patrones de ID validos
   - enums de EvidenceState correctos
   - formato de fecha YYYY-MM-DD

---

## Que NO valida todavia

- **Consistencia cruzada entre capas**: que `hc_ids` en trazabilidad referencien IDs que existen en hechos_confirmados
- **Existencia fisica de archivos referenciados**: que los archivos declarados en `salidas_generadas` o `cartografia_trace` esten en disco
- **Reglas de fase/gate**: que los campos requeridos para avanzar de fase esten en estado apto
- **Prudencia narrativa**: que el texto no use afirmaciones absolutas sin evidencia (eso es AU-02)
- **Validez administrativa real**: conformidad con art.45 Ley 21/2013 (eso es AU-01/AU-03)
- **Unicidad de IDs**: que no haya IDs duplicados dentro de una capa

Estas comprobaciones corresponden a NL-04 (gates), AU-01 a AU-04 (auditoria).

---

## API

### `validate_expediente`

```python
from eia_agent.core.schema_validator import validate_expediente

result = validate_expediente("expediente-EIA-2026-RECIMETAL-NAVE-222")
print(result.summary())

if not result.is_valid():
    for issue in result.issues:
        print(issue)
```

Firma:
```python
def validate_expediente(
    expediente_path: str | Path,
    schema_dir: str | Path | None = None,
) -> ValidationResult
```

- `expediente_path`: directorio raiz del expediente (con subcarpeta `capas/`)
- `schema_dir`: directorio con schemas. Por defecto `<project_root>/config/schemas/v2_1/`

### `validate_layer`

```python
from eia_agent.core.schema_validator import validate_layer

issues = validate_layer(
    expediente_path=Path("expediente-EIA-2026-..."),
    layer_name="hechos_confirmados",
    layer_file="capas/hechos_confirmados.json",
    schema_file="hechos_confirmados.schema.json",
    schema_dir=Path("config/schemas/v2_1"),
)
```

Devuelve `list[ValidationIssue]`. Vacia si la capa es valida.

### `load_schema_index`

```python
from eia_agent.core.schema_validator import load_schema_index

index = load_schema_index(Path("config/schemas/v2_1"))
# {"capas": [...], "comun": {...}}
```

---

## Clases

### `ValidationIssue`

```python
@dataclass
class ValidationIssue:
    severity: str       # ERROR / WARNING / INFO
    layer: str          # nombre de la capa
    path: str           # ruta dentro del JSON o descripcion
    message: str        # descripcion del problema
    code: str | None    # codigo para filtrado (LAYER_NOT_FOUND, JSON_PARSE_ERROR, etc.)
```

Codigos definidos:

| Codigo | Significado |
|---|---|
| `LAYER_NOT_FOUND` | El archivo de capa no existe |
| `FILE_READ_ERROR` | Error de lectura del archivo |
| `JSON_PARSE_ERROR` | El contenido no es JSON valido |
| `SCHEMA_NOT_FOUND` | El schema asociado no existe |
| `SCHEMA_PARSE_ERROR` | El schema tiene JSON mal formado |
| `SCHEMA_VALIDATION_ERROR` | El contenido no cumple el schema |
| `INDEX_NOT_FOUND` | schema_index.json no existe o no es valido |
| `INDEX_EMPTY` | schema_index.json no tiene capas |
| `JSONSCHEMA_NOT_AVAILABLE` | Libreria jsonschema no instalada |

### `ValidationResult`

```python
@dataclass
class ValidationResult:
    expediente_path: Path
    schema_version: str
    issues: list[ValidationIssue]

    def error_count() -> int
    def warning_count() -> int
    def info_count() -> int
    def is_valid() -> bool        # True si error_count() == 0
    def summary() -> str          # texto legible con estado y lista de issues
```

---

## Como ejecutar los tests

```bash
# Solo NL-02
venv/Scripts/python -m unittest tests.test_schema_validator -v

# Suite completa (NL-05 + NL-01 + NL-02)
venv/Scripts/python -m unittest discover -s tests
```

Resultado esperado: `Ran 118 tests in ~1.5s -- OK`

Los tests de NL-02 cubren:
- `ValidationIssue.__str__` con y sin code
- `ValidationResult` conteos, `is_valid()`, `summary()`
- `load_schema_index` correcto e inexistente
- `validate_layer` capa valida, archivo inexistente, JSON corrupto, schema inexistente, campo requerido ausente, ruta de error legible
- `validate_expediente` pilotos PARCELA y NAVE-222 (0 errores)
- `validate_expediente` con capa faltante, JSON invalido, campo ausente, directorio inexistente
- `summary()` de resultado invalido contiene informacion util

---

## Proximos pasos

- **NL-03** — `EIAOrchestrator`: clase que conoce el grafo de dependencias entre fases y evalua gates. Usa `validate_expediente` para comprobar el estado antes de ejecutar cada fase.
- **NL-04** — Gate-checker: evalua campos de gate por fase y determina si puede avanzarse. Extends NL-02 con reglas de fase.
- **AU-01 a AU-04** — Auditoria programatica: checklist art.45, regla de prudencia, trazabilidad, informe estructurado.
