# PRL_MEASURE_VALIDATOR — RD-09

Módulo: `src/eia_agent/core/prl_measure_validator.py`  
CLI: `python run_expediente.py <expediente> audit-prl-measures [--write]`  
Tests: `tests/test_prl_measure_validator.py` (110 tests)

---

## Qué hace RD-09

Verifica que las medidas de Prevención de Riesgos Laborales (PRL) estén correctamente
separadas de las medidas ambientales EIA y no se usen como reductoras de significancia
ambiental, tanto en el modelo de datos (Phase6Model) como en los textos markdown.

**Fuente canónica:** regla AG09-14 / D-10 del backlog de productización.

---

## Qué NO hace RD-09

- **No corrige medidas.** Solo detecta; no modifica nombre, tipo ni descripción.
- **No cambia significancias.** Los valores de significancia del impacto no se tocan.
- **No valora impactos.** No calcula índices Conesa ni reclasifica impactos.
- **No declara aptitud administrativa.** La calificación es interna al sistema.
- **No usa IA.** Lógica determinista sobre texto y modelo de datos.
- **No consulta fuentes externas.** Solo opera sobre archivos locales.
- **No modifica** ningún archivo previo salvo los de auditoría (con `--write`).

---

## Diferencia entre medida EIA y medida PRL

| Concepto | Medida ambiental EIA | Medida PRL |
|----------|---------------------|------------|
| Objetivo | Reducir presión sobre factor ambiental | Proteger al trabajador |
| Ejemplo correcto | Pantalla acústica perimetral | EPI auditivo |
| Ejemplo correcto | Baliza de exclusión en zona sensible | Casco de seguridad |
| Reduce ruido exterior | Sí (pantalla acústica) | No (EPI auditivo) |
| Reduce emisiones al exterior | Sí (medida correctora) | No (EPI filtra lo que llega al trabajador) |
| Computa como medida EIA | Sí | **No** |
| Tipo en modelo | PREVENTIVA / CORRECTORA / PROTECTORA | **PRL_NO_EIA** |
| Status en modelo | PROPUESTA / CONDICIONADA / ... | **NO_EIA** |

---

## Detección de medidas PRL

Una medida se clasifica como PRL si cumple **cualquiera** de estas condiciones:

1. `is_prl_only == True`
2. `measure_type == "PRL_NO_EIA"`
3. `status == "NO_EIA"`
4. Nombre, descripción o notas contienen alguna de las palabras clave:

| Palabra clave |
|---------------|
| epi / epis |
| equipo de proteccion individual |
| equipos de proteccion individual |
| proteccion auditiva |
| casco |
| guantes |
| gafas |
| mascarilla |
| botas |
| arnes |
| formacion prl |
| prevencion de riesgos laborales |
| seguridad laboral |
| senalizacion de seguridad |
| plan de seguridad |
| vigilancia de la salud |
| reconocimiento medico |
| trabajador / trabajadores |

La comparación es insensible a tildes y mayúsculas.

---

## Reglas de validación (modelo)

### RD09-E001 — measure_type incorrecto
La medida PRL tiene `measure_type` distinto de `PRL_NO_EIA` (ej. CORRECTORA, PREVENTIVA).
Las medidas PRL deben declararse siempre con `measure_type='PRL_NO_EIA'`.

### RD09-E002 — Afirma reducción ambiental EIA
El texto de la medida (name/description/notes) contiene keywords de reducción ambiental.
Las frases precedidas de negación ("no reduce", "sin reducción") no se cuentan.

Keywords de reducción ambiental detectados:

| Keyword |
|---------|
| reduce emisiones |
| reduce ruido exterior |
| reduce el impacto ambiental |
| reduce impacto ambiental |
| reduce significancia |
| corrige impacto |
| mitiga impacto |
| evita afeccion ambiental |
| reduce polvo exterior |
| reduce vertidos |
| reduce afeccion |
| medida correctora ambiental |
| medida preventiva ambiental |
| medida protectora ambiental |

### RD09-E003 — Única medida de impacto SEVERO/CRITICO
La medida PRL es la única vinculada a un impacto de significancia SEVERO o CRITICO.
Las medidas PRL no reducen significancia ambiental; el impacto necesita medidas
correctoras/preventivas EIA reales.

### RD09-W001 — Status no alineado con tipo
La medida PRL está correctamente tipada como `PRL_NO_EIA` pero tiene
`status != "NO_EIA"` y está vinculada a impactos ambientales. Debe aclararse
que no computa como medida EIA.

---

## Reglas de validación (markdown)

El validador también escanea ficheros markdown buscando PRL mezclada en secciones EIA.

### RD09-MD-E001 — PRL en contexto de reducción ambiental
Palabra clave PRL detectada en contexto con keywords de reducción ambiental (sin marcador de separación explícita).

### RD09-MD-W001 — PRL en contexto de medidas EIA sin separación
Palabra clave PRL detectada en contexto de tabla de medidas correctoras/preventivas EIA, sin marcador de separación explícito.

**Marcadores de separación seguros** (suprimen el flag):
- `prl no eia`, `prl_no_eia`
- `no computable`, `no computables`
- `no son medidas eia`
- `no reduce significancia`, `no reducen significancia`
- `medidas prl`
- `no eia`

---

## Estado del resultado

| Estado | Condición |
|--------|-----------|
| `OK` | No hay incidencias de nivel ERROR |
| `CON_OBSERVACIONES` | Solo hay incidencias WARNING |
| `NO_CONFORME` | Hay incidencias ERROR |
| `SIN_DATOS` | No hay modelo ni markdowns disponibles |

`is_valid()` devuelve `True` cuando no hay incidencias ERROR (OK y CON_OBSERVACIONES).

---

## Ejemplos correctos e incorrectos

### Correcto — EPI correctamente declarado

```json
{
  "measure_id": "MED-050",
  "name": "EPI auditivo para operarios",
  "description": "Proteccion auditiva PRL para el personal. No reduce ruido exterior. PRL_NO_EIA.",
  "measure_type": "PRL_NO_EIA",
  "status": "NO_EIA",
  "is_prl_only": true
}
```
→ Sin incidencias.

### Incorrecto — E001 — tipo incorrecto

```json
{
  "measure_id": "MED-051",
  "name": "EPI auditivo",
  "measure_type": "CORRECTORA",
  "is_prl_only": true
}
```
→ **RD09-E001**: EPI declarado como CORRECTORA.

### Incorrecto — E002 — afirma reducción ambiental

```json
{
  "measure_id": "MED-052",
  "name": "Formacion PRL",
  "description": "Reduce ruido exterior del recinto operativo.",
  "measure_type": "PRL_NO_EIA"
}
```
→ **RD09-E002**: "reduce ruido exterior" detectado.

### Incorrecto — E003 — única medida para impacto SEVERO

```json
{
  "measures": [{"measure_id": "MED-053", "name": "EPI auditivo",
                "measure_type": "PRL_NO_EIA", "status": "NO_EIA",
                "is_prl_only": true, "target_impact_ids": ["IMP-014"]}],
  "impacts": [{"impact_id": "IMP-014",
               "significance_without_measures": "SEVERO",
               "significance_with_measures": "SEVERO",
               "measure_ids": ["MED-053"]}]
}
```
→ **RD09-E003**: EPI es la única medida para un impacto SEVERO.

### Correcto en markdown — sección separada

```markdown
## D.5 Medidas PRL (PRL_NO_EIA — no computables como medidas EIA)

Las siguientes medidas son de PRL y no reducen significancia ambiental:
- EPI auditivo
- Casco de seguridad
```
→ Sin incidencias (safe marker "no computables como medidas eia" detectado).

### Incorrecto en markdown — PRL mezclada en tabla EIA

```markdown
## D.4 Medidas correctoras ambientales

| Medida | Tipo |
|--------|------|
| EPI auditivo | Correctora — reduce ruido exterior |
```
→ **RD09-MD-E001**: EPI en tabla de medidas correctoras con lenguaje de reducción.

---

## Ficheros markdown escaneados

```
impactos/*.md
bloques/*.md
auditoria/*.md
```

No se revisan `docs/`, `prompts/` ni `tests/` del proyecto.

---

## Orden de búsqueda del modelo de impactos

```
impactos/phase6_model_with_pva.json       ← prioridad 1
impactos/phase6_model_with_measures.json  ← prioridad 2
impactos/phase6_model_with_conesa.json         ← prioridad 3
impactos/phase6_model_with_impacts.json   ← prioridad 4
```

---

## CLI

```
python run_expediente.py <expediente> audit-prl-measures [--write]
```

El comando combina la validación del modelo con la validación de markdowns.

| Opción | Descripción |
|--------|-------------|
| `--write` | Escribe `auditoria/prl_measure_validation_result.json` y `.md` |

**Códigos de salida:**
- `0` → sin errores (`is_valid() == True`): OK o CON_OBSERVACIONES
- `1` → hay errores (NO_CONFORME) o expediente no existe

---

## API pública

### `is_prl_measure(measure) -> bool`
True si la medida es PRL por flag, tipo, status o palabras clave.

### `measure_is_presented_as_environmental_reduction(measure) -> bool`
True si el texto contiene keywords de reducción ambiental (con detección de negación).

### `validate_prl_measure(measure, related_impacts=None) -> list[PRLMeasureIssue]`
Valida una medida PRL en aislamiento o con sus impactos.

### `validate_prl_measures_in_model(model) -> PRLMeasureValidationResult`
Valida todas las medidas del Phase6Model. No muta el modelo.

### `validate_prl_measures_from_json(path) -> PRLMeasureValidationResult`
Carga JSON y valida.

### `validate_prl_measures_from_files(expediente_path) -> PRLMeasureValidationResult`
Busca el modelo en `impactos/` y valida.

### `validate_prl_markdown(markdown, source="markdown") -> PRLMeasureValidationResult`
Detecta PRL mezclada en secciones EIA en un texto markdown.

### `validate_prl_measures_markdowns_from_files(expediente_path) -> PRLMeasureValidationResult`
Escanea markdowns del expediente en `impactos/`, `bloques/`, `auditoria/`.

### `build_prl_measure_report_markdown(result) -> str`
Genera informe markdown con 6 secciones.

### `write_prl_measure_outputs(result, output_dir) -> tuple[Path, Path]`
Escribe `prl_measure_validation_result.json` y `.md`.

---

## Ejecución de tests

```
python -m unittest tests.test_prl_measure_validator
python -m unittest discover -s tests
```

Los tests son 100% offline: usan `tempfile` y objetos en memoria.

---

## Advertencia de alcance

Las medidas PRL pueden ser obligatorias y necesarias, pero no deben computarse
como medidas ambientales reductoras de significancia EIA.

Un EPI auditivo protege al trabajador del ruido; no reduce el nivel de ruido
exterior del foco emisor. Una pantalla acústica sí lo reduce. Solo la pantalla
computa como medida correctora ambiental.
