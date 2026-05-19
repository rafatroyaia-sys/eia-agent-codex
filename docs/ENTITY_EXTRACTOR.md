# ENTITY_EXTRACTOR — IN-02

## Qué hace

`entity_extractor` detecta entidades ambientales, administrativas y técnicas en documentos `.docx` y texto plano. Opera sobre la salida de `DocxParser` (IN-01). Usa exclusivamente regex y heurísticas. No usa IA ni LLM.

Modo: **solo lectura**. No escribe en disco. No modifica el DOCX.

## Qué NO hace

- No usa IA para inferir ni interpretar — solo patrones estructurados.
- No asigna estado de evidencia (DECLARADO/PENDIENTE) — eso es IN-03.
- No escribe en capas JSON ni en `inputs_index.json` — eso es IN-05.
- No genera informes ni documentos de salida.

## Tipos de entidad detectados

| Tipo | Ejemplo | Confianza |
|------|---------|-----------|
| `REFERENCIA_CATASTRAL` | `2462302DS4026S0001GQ` | HIGH |
| `LER` | `17 04 05`, `160601*` | HIGH (espacios) / MEDIUM (compact) |
| `OPERACION` | `R1201`, `R13`, `D15` | HIGH |
| `COORDENADA` | `28.9234`, `E: 642000` | MEDIUM |
| `SUPERFICIE` / `SUPERFICIE_PARCELA`... | `1500 m²` | MEDIUM |
| `CAPACIDAD` | `500 tm/día`, `3.000 t/año` | MEDIUM |
| `POTENCIA` | `75 kW`, `100 CV`, `50 HP` | MEDIUM |
| `FECHA` | `15/03/2024`, `2024-03-15` | HIGH |
| `PROMOTOR` | `RECIMETAL LANZAROTE, S.L.` | HIGH (kv) / MEDIUM (texto) / LOW (empresa) |
| `EQUIPO` | `molino`, `criba`, `cizalla` | MEDIUM |

## API

### `extract_entities_from_text(texto, source) -> ExtractionResult`

Extrae entidades de texto plano.

```python
from eia_agent.core.entity_extractor import extract_entities_from_text

result = extract_entities_from_text("Residuo 17 04 05 con RC 2462302DS4026S0001GQ")
for e in result.by_type("LER"):
    print(e.normalized_value)  # '17 04 05'
```

- `texto` vacío o solo espacios → devuelve `ExtractionResult` con `entities=[]`.
- `source` es la etiqueta de origen que aparece en `ExtractedEntity.source`.

### `extract_entities_from_docx(path) -> ExtractionResult`

Extrae entidades de un archivo `.docx`. Combina texto principal y contenido de tablas. Deduplica por `(entity_type, value)`.

```python
from eia_agent.core.entity_extractor import extract_entities_from_docx

result = extract_entities_from_docx("inputs/memorias/Documento_Ambiental.docx")
print(result.summary())
for rc in result.by_type("REFERENCIA_CATASTRAL"):
    print(rc.value)
```

**Errores:**
- `FileNotFoundError` — el archivo no existe.
- `ValueError` — no es un DOCX válido (relanzado desde IN-01).

### `ExtractedEntity` (dataclass)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `entity_type` | `str` | Tipo de entidad (ver tabla superior) |
| `value` | `str` | Valor tal como aparece en el texto |
| `source` | `str` | `"texto"`, `"tabla:kv"`, `"tabla:cabecera"`, `"tabla:N:filaR:colC"` |
| `confidence` | `str` | `HIGH` / `MEDIUM` / `LOW` |
| `context` | `Optional[str]` | Fragmento de texto (±60 chars) donde se encontró |
| `normalized_value` | `Optional[str]` | Valor normalizado (LER: `XX XX XX[*]`, superficie: `N m²`, potencia: `N UNIDAD`) |

### `ExtractionResult` (dataclass)

| Método | Descripción |
|--------|-------------|
| `by_type(entity_type)` | Lista de `ExtractedEntity` del tipo indicado |
| `values(entity_type)` | Lista de `str` con los valores del tipo indicado |
| `summary()` | String con conteo por tipo: `"12 entidades — LER: 5, OPERACION: 3..."` |
| `.entities` | Lista completa de todas las entidades |
| `.warnings` | Avisos de procesamiento (e.g., tablas no leíbles) |

## Funciones de normalización

### `normalize_ler(value) -> str`

Normaliza cualquier formato de código LER a `XX XX XX[*]`.

```python
normalize_ler("170405")    # → "17 04 05"
normalize_ler("170405*")   # → "17 04 05*"
normalize_ler("17 04 05")  # → "17 04 05"
```

### `is_ler_peligroso(value) -> bool`

`True` si el código lleva asterisco (residuo peligroso).

### `normalize_surface(value) -> str`

Normaliza valores de superficie con separadores españoles.

```python
normalize_surface("1.931,40")  # → "1931.4 m²"
normalize_surface("1500")      # → "1500 m²"
```

### `normalize_power(value, unit) -> str`

```python
normalize_power("75", "kW")   # → "75 KW"
normalize_power("7,5", "kW")  # → "7.5 KW"
```

## Heurísticas de promotor

Tres estrategias en cascada:

1. **Texto con clave**: `"promovido por X"`, `"Promotor: X"`, `"Titular: X"` → confidence MEDIUM
2. **Empresa en texto**: patrón `X, S.L.` / `X, S.A.` sin prefijo clave → confidence LOW
3. **Tabla key-value**: clave contiene `promotor/titular/solicitante` → valor es el nombre → confidence HIGH
4. **Tabla cabecera invertida**: el nombre de empresa es la clave del dict (caso PARCELA) → confidence HIGH

## Casos especiales conocidos

### LER solo en tablas (PARCELA)

El fichero PARCELA no contiene códigos LER en el texto plano, solo en celdas de tabla. `extract_entities_from_docx()` escanea cada celda individualmente via `extract_tables_raw()`.

### Cabecera de tabla con empresa (PARCELA)

La tabla de promotor de PARCELA tiene estructura `{'Promotor': 'NIF', 'RECIMETAL LANZAROTE, S.L.': 'B72798846'}`. El nombre de empresa es la clave del dict, no el valor. El extractor detecta empresas en claves de dict usando `_EMPRESA_RE`.

### Bug corregido: regex LER compact

El patrón original `r'\b(\d{6})(\*?)\b'` no capturaba el `*` en `160601*` porque `\b` antes de `*` se resuelve antes de intentar capturar el asterisco. Corregido a `r'\b(\d{6})(\*?)(?!\d)'`.

## Fixture real disponible

`expediente-EIA-2026-RECIMETAL-PARCELA/inputs/memorias/Documento_Ambiental_RECIMETAL_Parcela_v6.docx`

Entidades detectadas:
- `REFERENCIA_CATASTRAL`: `2462302DS4026S0001GQ`
- `LER`: múltiples (solo en tablas)
- `PROMOTOR`: `RECIMETAL LANZAROTE, S.L.` (cabecera de tabla + texto)
- `OPERACION`: R1201, R1203, R13 y otras presentes en el documento

## Ejecutar tests

```bash
# Solo IN-02
venv\Scripts\python -m unittest tests.test_entity_extractor

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
