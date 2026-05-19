# PHASE3_PIPELINE — TN-05

Pipeline programático de Fase 3. Toma los datos de Fase 1 (`candidate_facts`)
y Fase 2 (`object_scope`), detecta normativa potencialmente aplicable mediante
reglas Python puras y produce una nota de encuadre legal preliminar.

Sin IA. Sin consulta BOE online. Sin web scraping.
Sin escritura automática (requiere `write_outputs=True`).
Sin inicio de Fase 4.

## Módulo

`src/eia_agent/core/phase3_pipeline.py`

## Relación con módulos anteriores

```
phase1_result.json  ←── run_phase1() (IN-06)
        │
phase2_result.json  ←── run_phase2() (OB-06)   [OPCIONAL]
        │
        ▼
_build_text_corpus()      ← une todos los campos textuales relevantes
        │
        ▼
_detect_*()               ← 7 funciones de detección (campo + keyword)
        │
        ▼
_build_normativa()        ← construye lista de NormativeItem
        │
        ▼
_determine_procedimiento() ← SIMPLIFICADA / ORDINARIA_POSIBLE / NO_DETERMINADO
        │
        ▼
_build_cautelas()         ← cautelas operativas según contexto
        │
        ▼
Phase3Result
```

## API pública

```python
from eia_agent.core.phase3_pipeline import run_phase3

# Solo lectura (requiere phase1_result.json previo)
result = run_phase3("expediente-EIA-2026-RECIMETAL-PARCELA")
print(result.summary())

# Con escritura
result = run_phase3(
    "expediente-EIA-2026-RECIMETAL-PARCELA",
    write_outputs=True,
)
```

### run_phase3

```python
def run_phase3(
    expediente_path: str | Path,
    phase1_result_path: str | Path | None = None,
    phase2_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase3Result
```

Pasos internos:
1. Localizar `phase1_result.json` (por defecto en `control_interno/`; o ruta explícita). **Requerido.**
2. Localizar `phase2_result.json`. **Opcional** — si no existe, se continúa con ObjectScope vacío y se añade nota.
3. Construir corpus de texto con `_build_text_corpus()`.
4. Ejecutar las 7 detecciones (`_detect_residuos`, `_detect_ruido`, `_detect_natura`, `_detect_patrimonio`, `_detect_canarias`, `_detect_urbanismo`, `_detect_alta_capacidad`).
5. `_build_normativa()` — construye lista de `NormativeItem` según los flags de detección.
6. `_determine_procedimiento()` — SIMPLIFICADA / ORDINARIA_POSIBLE / NO_DETERMINADO.
7. `_build_cautelas()` — cautelas según scope y triaje.
8. Si `write_outputs=True`: escribe dos archivos en `output_dir/`.

**Raises** `FileNotFoundError` si `phase1_result.json` no existe y no se pasa ruta explícita.

### Phase3Result

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | Nombre del directorio del expediente |
| `normativa` | list[NormativeItem] | Normas detectadas por el triaje |
| `procedimiento_eia` | str | SIMPLIFICADA / ORDINARIA_POSIBLE / NO_DETERMINADO |
| `razones_procedimiento` | list[str] | Justificación del procedimiento determinado |
| `cautelas` | list[str] | Cautelas operativas activas |
| `warnings` | list[str] | Avisos de fases anteriores propagados + avisos de Fase 3 |
| `notes` | list[str] | Notas operativas |

Métodos: `summary() -> str`, `to_dict() -> dict`.

### NormativeItem

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | str | TN-A001, TN-B001, etc. |
| `titulo` | str | Nombre completo de la norma |
| `ambito` | str | estatal / autonomico / local / europeo / desconocido |
| `materia` | str | evaluacion_ambiental / residuos / ruido / natura2000 / patrimonio / clima / urbanismo |
| `referencia` | str \| None | Identificador BOE o None si no aplica |
| `estado` | str | REFERENCIADA / PENDIENTE_VERIFICACION / VERIFICADA_ONLINE |
| `razon_aplicabilidad` | str | Por qué se aplica esta norma (incluye fuente de detección) |
| `fuente_deteccion` | str | Qué triggereó la detección (campo, entity_type o texto:keyword) |
| `notas` | list[str] | Notas adicionales para el técnico |

Método: `to_dict() -> dict`.

## Normas detectadas

### Siempre (regla_base)

| ID | Norma | Estado |
|----|-------|--------|
| TN-A001 | Ley 21/2013, de evaluación ambiental | REFERENCIADA |
| TN-B001 | RD 445/2023, que modifica Anexos I, II y III de Ley 21/2013 | REFERENCIADA |

### Condicionales

| ID | Norma | Trigger | Estado |
|----|-------|---------|--------|
| TN-C001 | Ley 7/2022, de residuos | Detecta operaciones LER o código R/D | REFERENCIADA |
| TN-D001 | Ley 37/2003, del Ruido | Detecta maquinaria, equipos, ruido | REFERENCIADA |
| TN-D002 | RD 1367/2007, zonificación acústica | Mismo trigger que TN-D001 | REFERENCIADA |
| TN-E001 | Ley 42/2007, Patrimonio Natural y Biodiversidad | Detecta mención Natura 2000 / ZEC / ZEPA | REFERENCIADA |
| TN-F001 | Ley 16/1985, Patrimonio Histórico Español | Detecta mención arqueología / BIC | PENDIENTE_VERIFICACION |
| TN-G001 | Ley 4/2017, Suelo y ENP Canarias | Detecta proyecto en Canarias | REFERENCIADA |
| TN-G002 | Ley 6/2022, Cambio Climático Canarias | Detecta proyecto en Canarias | REFERENCIADA |
| TN-H001 | Normativa urbanística municipal (PGOU/PIOT) | Detecta RC o indicios urbanísticos | PENDIENTE_VERIFICACION |

## Estados de las normas

- **REFERENCIADA**: aplica según las reglas del triaje. Verificar vigencia y última modificación en BOE/BOC antes de la presentación.
- **PENDIENTE_VERIFICACION**: mención detectada; requiere comprobación manual antes de usar.
- **VERIFICADA_ONLINE**: verificada contra BOE/BOC en fecha de consulta. No se emite en este módulo (reservado para TN-01, fuera de scope).

## Determinación del procedimiento EIA

La función `_determine_procedimiento()` aplica esta jerarquía:

1. **ORDINARIA_POSIBLE** — si se detectan indicios de fraccionamiento, superación de umbral Anexo I, o capacidad > 50.000 unidades.
2. **SIMPLIFICADA** — si se detectan operaciones R12/R13 o residuos genéricos sin indicios de Anexo I.
3. **NO_DETERMINADO** — si no hay datos suficientes.

`ORDINARIA_POSIBLE` no significa que sea ordinaria: requiere verificación contra RD 445/2023 antes de determinar definitivamente.

## Detección de Canarias

Dos métodos independientes:
1. **Coordenadas WGS84** en rango lat 27–30°N, lon -19 a -13°W (ObjectScope de Fase 2).
2. **Keywords** en el corpus de texto: "canarias", "tenerife", "cabildo", "grafcan", etc.

## Corpus de texto

`_build_text_corpus()` concatena:
- Campos `valor`, `context`, `normalized_value`, `notes` de cada `candidate_fact` (Fase 1).
- Campos `titular`, `modo`, `capacidad`, `superficie_m2` del ObjectScope (Fase 2).
- Listas `operaciones_incluidas`, `operaciones_excluidas`, `gaps`, `at_activos` del ObjectScope.

## Cautelas activas

| Código | Condición |
|--------|-----------|
| CAUTELA-TN-01 | Siempre — normas REFERENCIADA deben verificarse en BOE/BOC |
| CAUTELA-TN-02 | Siempre — triaje automático no sustituye revisión jurídica |
| CAUTELA-TN-03 | modo=GABINETE — datos solo documentales |
| CAUTELA-TN-04 | at_activos no vacío — expediente no apto para tramitación real |
| CAUTELA-TN-05 | has_natura — no usar "afección significativa" sin EIHA previa |
| CAUTELA-TN-06 | has_canarias — órgano ambiental competente es CAARUP |
| CAUTELA-TN-07 | procedimiento=ORDINARIA_POSIBLE — no iniciar redacción sin confirmar encuadre |

## Diferencia entre este módulo y el triaje manual del piloto

**Triaje Fase 3 (este módulo)**:
- Detecta normativa potencialmente aplicable mediante reglas deterministas.
- No consulta el BOE ni verifica vigencia online.
- `estado=REFERENCIADA` significa "aplica según reglas del triaje", NO que esté verificada.
- No determina órganos competentes (TN-04, fuera de scope).

**Triaje manual (piloto)**:
- Incluía consulta manual del BOE en la fecha de análisis.
- Incluía confirmación de estado VIGENTE / MODIFICADO / DEROGADO.
- Incluía identificación del órgano competente por CCAA.

## Diferencia lectura vs escritura

Por defecto (`write_outputs=False`), `run_phase3()` no escribe ningún archivo.

Con `write_outputs=True` escribe en `output_dir/` (por defecto `control_interno/`):
- `phase3_result.json` — resultado completo serializado
- `nota_encuadre_legal.md` — nota en Markdown con tabla de normas, detalle y cautelas

Nunca modifica `inputs/`. Nunca escribe en los expedientes piloto durante tests.

## CLI

```bash
# Solo lectura (requiere phase1_result.json en control_interno/)
python run_expediente.py <expediente> phase3

# Con escritura de outputs
python run_expediente.py <expediente> phase3 --write
```

**Flujo típico completo desde cero:**
```bash
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA phase1 --write
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA phase2 --write
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA phase3 --write
```

## Limitaciones conocidas

1. **Requiere Fase 1 previa**: `phase1_result.json` debe existir.
2. **Fase 2 opcional pero recomendada**: Sin ObjectScope, la detección de Canarias por coordenadas y de urbanismo por RC no funciona.
3. **No consulta BOE/BOC**: Toda la normativa sale como REFERENCIADA o PENDIENTE_VERIFICACION, nunca VERIFICADA_ONLINE. TN-01 (consulta online) está fuera de scope.
4. **No determina órganos competentes**: TN-04 está fuera de scope.
5. **No inicia Fase 4**: al completar Fase 3, no se activa ni sugiere ninguna fase siguiente de forma automática.
6. **Heurística de capacidad**: el umbral de 50.000 unidades para ORDINARIA_POSIBLE es conservador y puede generar falsos positivos. Siempre verificar contra RD 445/2023.

## Tests

`tests/test_phase3_pipeline.py` — 21 clases de test.

Cobertura:
- `NormativeItem`: estructura, `to_dict()`, referencia None
- `Phase3Result`: `summary()`, `to_dict()`, JSON serializable
- `_has_any_keyword`: found, not found, case-insensitive
- `_build_text_corpus`: valor, context, operaciones, scope
- `_detect_residuos`: campo, entity_type, keyword
- `_has_r12_r13_operations`: facts, object_scope
- `_detect_ruido`: campo, entity_type, keyword
- `_detect_natura`: ZEC, Red Natura 2000
- `_detect_patrimonio`: yacimiento, BIC
- `_detect_canarias`: coords WGS84, keywords, límites
- `_detect_urbanismo`: RC en scope, campo RC, keyword PGOU
- `_detect_alta_capacidad`: keyword fraccionamiento, capacidad numérica
- `_build_normativa`: siempre TN-A001+TN-B001, todos los condicionales, estados
- `_determine_procedimiento`: SIMPLIFICADA, ORDINARIA_POSIBLE, NO_DETERMINADO
- `_build_cautelas`: todas las condiciones TN-01 a TN-07
- `run_phase3` sin phase1: FileNotFoundError, mensaje útil
- `run_phase3` mínimo: Phase3Result, nota sin phase2
- `run_phase3` con residuos+scope: Ley7, Canarias, urbanismo, propagación warnings
- `run_phase3` ORDINARIA_POSIBLE: fraccionamiento en corpus
- write_outputs: no escribe por defecto, crea 2 archivos, JSON válido, dir personalizado
- CLI: exit codes, --write, missing phase1
- Pilots PARCELA y NAVE-222: solo lectura, no modifica expediente
