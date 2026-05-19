# PHASE2_PIPELINE — OB-06

Pipeline programático de Fase 2. Toma los candidate facts de Fase 1,
construye el ObjectScope (OB-01) y ejecuta la validación de Gate 2 (OB-02).
Sin IA, sin escritura automática, sin modificación de inputs.

## Módulo

`src/eia_agent/core/phase2_pipeline.py`

## Relación con módulos anteriores

```
phase1_result.json  ←── run_phase1() (IN-06)
        │
        ▼
build_classification_result_from_phase1()   ← reconstruye ClassificationResult
        │
        ▼
build_object_scope()                         ← OB-01 (object_scope_builder)
        │
        ▼
evaluate_gate_2()                            ← OB-02 (object_gate_validator)
        │
        ▼
Phase2Result
```

## API pública

```python
from eia_agent.core.phase2_pipeline import run_phase2

# Solo lectura (requiere phase1_result.json previo)
result = run_phase2("expediente-EIA-2026-RECIMETAL-PARCELA")
print(result.summary())

# Con overrides y escritura
result = run_phase2(
    "expediente-EIA-2026-RECIMETAL-PARCELA",
    write_outputs=True,
    overrides={"modo": "GABINETE", "operaciones_excluidas": ["R1302"]},
    test_mode=True,
    context={"rc_verificada": False},
)
```

### run_phase2

```python
def run_phase2(
    expediente_path: str | Path,
    phase1_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
    overrides: dict | None = None,
    test_mode: bool = True,
    context: dict | None = None,
) -> Phase2Result
```

Pasos internos:
1. Localizar `phase1_result.json` (por defecto en `control_interno/`; o ruta explícita).
2. Cargar `candidate_facts` del JSON de Fase 1.
3. `build_classification_result_from_phase1()` → reconstruye `ClassificationResult` sin re-extraer DOCX.
4. `build_object_scope()` (OB-01) con `classification` y `overrides` opcionales.
5. `evaluate_gate_2()` (OB-02) con `test_mode` y `context` opcionales.
6. Si `write_outputs=True`: escribe tres archivos en `output_dir/`.

**Raises** `FileNotFoundError` si `phase1_result.json` no existe y no se pasa ruta explícita.

### Phase2Result

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | Nombre del directorio del expediente |
| `object_scope` | dict | ObjectScope serializado (OB-01) |
| `gate2_passed` | bool | True si Gate 2 no tiene ningún ERROR |
| `gate2_summary` | str | Resumen textual de Gate 2 (OB-02) |
| `issues` | list[dict] | Incidencias del Gate 2 (severity/code/message/field/recommendation) |
| `warnings` | list[str] | Avisos de Fase 1 propagados + avisos de Fase 2 |
| `notes` | list[str] | Notas operativas |

Métodos: `summary() -> str`, `to_dict() -> dict`.

### build_classification_result_from_phase1

```python
def build_classification_result_from_phase1(phase1_data: dict) -> ClassificationResult
```

Deserializa los `candidate_facts` del JSON de Fase 1 en objetos `CandidateFact` reales.
No re-procesa DOCX. No llama a IN-01/IN-02/IN-03.

### Overrides

Claves admitidas en el dict `overrides`:

| Clave | Tipo | Efecto |
|-------|------|--------|
| `titular` | str | Sobrescribe el titular/promotor |
| `referencia_catastral` | str | Sobrescribe la RC |
| `modo` | str | GABINETE, CAMPO o NO_DECLARADO |
| `coordenadas_wgs84` | list[str] | Añade/sobrescribe coords WGS84 |
| `coordenadas_utm` | list[str] | Añade/sobrescribe coords UTM |
| `operaciones_incluidas` | list[str] | Sobrescribe operaciones incluidas |
| `operaciones_excluidas` | list[str] | Declara operaciones excluidas |
| `at_activos` | list[str] | Declara asunciones de test activas |
| `gaps` | list[str] | Declara gaps identificados |
| `superficie_m2` | str | Sobrescribe superficie |
| `capacidad` | str | Sobrescribe capacidad |

Los overrides no crean AT automáticamente. Solo registran las AT que el usuario
declare explícitamente. No resuelven contradicciones.

### Context dict

Claves opcionales para `context` (pasadas a `evaluate_gate_2()`):

| Clave | Tipo | Efecto |
|-------|------|--------|
| `rc_verificada` | bool | False → WARNING (test_mode) / ERROR (prod) sobre RC no verificada |
| `cont_abiertos` | bool | True → comprueba que haya ops excluidas o AT antes de avanzar |
| `uso_catastral` | str | Uso según Catastro (para detección de discrepancias) |
| `uso_declarado` | str | Uso declarado por el promotor |

## Gate 2 técnico vs aptitud administrativa

**Gate 2 técnico** (lo que hace este módulo):
- Verifica que los campos obligatorios del objeto evaluado están presentes y tienen formato mínimo válido.
- No consulta Catastro, ni organismos oficiales.
- `passed=True` significa que la información está estructuralmente completa para continuar el análisis.

**Aptitud administrativa** (fuera de este módulo):
- Requiere verificación contra Catastro, Registro, autoridades competentes.
- Requiere que todos los datos estén en estado CONFIRMADO (no solo DECLARADO).
- Requiere ausencia de AT activas (`test_mode=False`).
- Requiere pasar el checklist completo de presentabilidad.

`gate2_passed=True` **no implica** aptitud administrativa.

## Diferencia entre lectura y escritura explícita

Por defecto (`write_outputs=False`), `run_phase2()` no escribe ningún archivo.

Con `write_outputs=True` escribe en `output_dir/` (por defecto `control_interno/`):
- `phase2_result.json` — resultado completo serializado
- `ficha_objeto_evaluado.md` — ficha markdown del objeto evaluado (OB-01 format)
- `object_scope.json` — ObjectScope serializado

Nunca modifica `inputs/`. Nunca escribe en los expedientes piloto durante tests.

## CLI

```bash
# Solo lectura (requiere phase1_result.json en control_interno/)
python run_expediente.py <expediente> phase2

# Con escritura de outputs
python run_expediente.py <expediente> phase2 --write

# Modo producción (AT activos y gaps ALTA son ERROR)
python run_expediente.py <expediente> phase2 --prod

# Combinado
python run_expediente.py <expediente> phase2 --write --prod
```

**Flujo típico completo desde cero:**
```bash
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA phase1 --write
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA phase2 --write
```

## Limitaciones conocidas

1. **Requiere Fase 1 previa**: `phase1_result.json` debe existir. No hay modo de "una sola pasada" que procese DOCX y evalúe Gate 2 en una llamada (se puede hacer encadenando `run_phase1()` + `run_phase2()` programáticamente).
2. **No resuelve contradicciones**: detecta campos en conflicto (via `warnings`) pero no elige un valor. Las contradicciones se documentan, no se resuelven (OB-03 es el módulo dedicado, fuera de scope).
3. **No crea AT automáticamente**: el sistema AT (OB-05) está fuera de scope. Los overrides permiten declarar AT existentes, no crearlas con validación.
4. **No cierra gaps**: los gaps se listan en el ObjectScope pero no se resuelven.
5. **No inicia Fase 3**: al completar Fase 2, no se activa ni sugiere ninguna fase siguiente de forma automática.
6. **Datos DECLARADO, no CONFIRMADO**: todos los datos del ObjectScope provienen de documentos del promotor. Ningún campo alcanza estado CONFIRMADO en este pipeline.

## Tests

`tests/test_phase2_pipeline.py` — 66 tests, 11 clases.

Cobertura:
- `Phase2Result`: structure, `summary()`, `to_dict()`, JSON serialización
- `build_classification_result_from_phase1`: vacío, claves ausentes, reconstrucción de campos
- `run_phase2` sin phase1_result: FileNotFoundError, mensaje útil
- `run_phase2` con datos mínimos: nota vacío, construcción scope, propagación warnings
- Gate 2 APTO/BLOQUEADO según datos (coords, titular, modo)
- test_mode vs producción: AT activos WARNING vs ERROR
- overrides: modo, ops excluidas, gaps, coords, AT, None/vacío
- write_outputs: no escribe por defecto, crea tres archivos, dir personalizado, JSON válido
- context: rc_verificada=False → WARNING (test) / ERROR (prod)
- CLI: exit codes, mensaje de error, --write, --prod, sin phase1
- Pilots PARCELA y NAVE-222: solo lectura, no modifica inputs ni control_interno
