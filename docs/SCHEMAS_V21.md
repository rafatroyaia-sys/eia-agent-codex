# JSON Schema v2.1 — referencia tecnica

Item canonico: **NL-01**  
Directorio: `config/schemas/v2_1/`

---

## Objetivo

Formalizar la estructura de datos de las 6 capas del expediente EIA-Agent como
schemas JSON validables. Permite detectar errores reales (IDs invalidos, estados
desconocidos, campos obligatorios ausentes) antes de que lleguen a los bloques
de redaccion o a la auditoría M-12.

---

## Las 6 capas y sus schemas

| Capa | Archivo JSON del expediente | Schema |
|---|---|---|
| 1 — Hechos confirmados | `capas/hechos_confirmados.json` | `hechos_confirmados.schema.json` |
| 2 — Inferencias y gaps | `capas/inferencias_y_gaps.json` | `inferencias_y_gaps.schema.json` |
| 3 — Normativa aplicable | `capas/normativa_aplicable.json` | `normativa_aplicable.schema.json` |
| 4 — Matriz de trazabilidad | `capas/matriz_trazabilidad.json` | `matriz_trazabilidad.schema.json` |
| 5 — Trazabilidad cartografica | `capas/cartografia_trace.json` | `cartografia_trace.schema.json` |
| 6 — Salidas generadas | `capas/salidas_generadas.json` | `salidas_generadas.schema.json` |

Schema compartido: `common_defs.schema.json` (contiene `$defs` reutilizables)

Indice: `schema_index.json` (mapea nombre de capa → archivo → schema)

---

## Que valida NL-01

- Que la raiz de cada capa es un **array** (no objeto)
- **Campos obligatorios** por capa:
  - Hechos: `id`, `categoria`, `campo`, `valor`, `estado`, `fuentes`
  - Inferencias: `id`, `tipo`, `criticidad`, `campo`
  - Normativa: `id`, `tipo`, `norma`, `estado`
  - Trazabilidad: `id`, `dato`, `valor`, `estado_evidencia`, `fuente_primaria`
  - Cartografia: `id`, `titulo`, `tipo_cartografia`, `estado`, `archivo_resultado`
  - Salidas: `id`, `fase`, `agente`, `fecha`, `tipo`, `nombre_archivo`, `descripcion`
- **Tipos basicos**: string, number, boolean, array, object, null (segun campo)
- **Patrones de ID**: HC-001, CONT-001, GAP-010-FASE2, NJ-001, TR-001, CT-001, SG-001
- **Enum EvidenceState**: valida que `estado` / `estado_evidencia` usen valores canonicos
  (ver `src/eia_agent/core/evidence_state.py` y `docs/EVIDENCE_STATE.md`)
- **Enum EstadoNormativa**: VERIFICADA, VERIFICADA ONLINE, REFERENCIADA, etc.
- **Enum TipoCartografia / EstadoCartografia**
- **Formato de fecha**: YYYY-MM-DD (campo `fecha` en salidas_generadas)
- **Fuentes no vacias**: `fuentes` en hechos debe tener al menos 1 elemento
- `additionalProperties: true` — campos adicionales legítimos son admitidos

---

## Que NO valida todavia (pertenece a NL-02 / NL-04 / AU)

- Coherencia entre capas: que `hc_ids` en trazabilidad referencien IDs que existen en hechos
- Unicidad de IDs dentro de cada capa
- Que todos los gaps marcados como bloqueantes tengan resolucion
- Completitud de gates por fase
- Reglas cruzadas entre normativa y trazabilidad
- Presencia de todos los mapas requeridos en cartografia_trace

---

## Relacion con EvidenceState

Los enums de `estado` y `estado_evidencia` en los schemas estan alineados exactamente
con la clase `EvidenceState` de `src/eia_agent/core/evidence_state.py` (NL-05).

Los 15 valores admitidos:
```
CONFIRMADO_CAMPO | CONFIRMADO_GABINETE | CONFIRMADO | DECLARADO | ASUNCION_TEST
INFERIDO_TECNICO | INFERIDO | LIMITADO_ESCALA | ESTIMADO | PROVISIONAL
PENDIENTE_VERIFICACION | PENDIENTE | NO_CONSTA | DESCARTADO | ERROR
```

`DESCARTADO` y `ERROR` se incluyen por compatibilidad con expedientes existentes.

---

## Diseno del resolver ($ref)

Los 6 schemas de capa no tienen campo `$id`. Esto garantiza que los `$ref` relativos
(`common_defs.schema.json#/$defs/EvidenceState`) se resuelvan por URI de archivo
(`file:///...`) en lugar de por URI personalizado, lo que hace la resolucion
compatible con jsonschema 4.x sin dependencias adicionales.

---

## Como ejecutar los tests

```bash
# Windows
venv/Scripts/python -m unittest tests.test_schemas_v21 -v

# macOS / Linux
venv/bin/python -m unittest tests.test_schemas_v21 -v
```

Resultado esperado: `Ran 27 tests in ~0.2s — OK`

Los tests validan:
1. Existencia de los 7 archivos schema + schema_index.json
2. JSON valido en todos los schemas
3. `Draft202012Validator.check_schema()` pasa en todos
4. Los 6 capas del piloto PARCELA validan sin errores
5. Las 6 capas del piloto NAVE-222 validan sin errores
6. 10 ejemplos invalidos fallan correctamente

---

## Proximos pasos

- **NL-02** — Validador robusto: funcion `validar_expediente(ruta)` que carga las 6
  capas de un expediente y las valida contra estos schemas. Produce informe
  estructurado de errores con ruta JSON, campo y tipo de error.
- **NL-04** — Gate-checker: evalua campos de gate por fase y determina si puede
  avanzarse. Usa NL-01 (schemas) y NL-02 (validador) como base.
- **AU-01 a AU-04** — Auditoria programatica: checklists del art.45 + coherencia
  cruzada entre capas (lo que NL-01 no valida).
