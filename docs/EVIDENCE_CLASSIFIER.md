# EVIDENCE_CLASSIFIER — IN-03

## Qué hace

`evidence_classifier` convierte entidades extraídas por IN-02 (`ExtractedEntity`) en hechos candidatos estructurados (`CandidateFact`), compatibles con la capa `hechos_confirmados.json` (schema NL-01).

Modo: **solo lectura**. No escribe en disco. No llama a IA. No confirma nada administrativamente.

## Diferencia entre entidad extraída y hecho candidato

| Concepto | Proviene de | Representa |
|----------|-------------|------------|
| `ExtractedEntity` (IN-02) | Regex sobre texto/tablas | Patrón detectado en el documento |
| `CandidateFact` (IN-03) | Clasificación de entidades | Hecho mapeado a categoria/campo del schema |

Una entidad es *lo que se encontró*. Un hecho candidato es *cómo se registra* ese hallazgo en la base de datos del expediente.

Ejemplo:
- Entidad: `ExtractedEntity(entity_type="LER", value="17 04 05", confidence="HIGH")`
- Hecho: `CandidateFact(categoria="residuos", campo="codigo_ler", valor="17 04 05", estado="DECLARADO")`

## Por qué casi todo sale como DECLARADO

Los datos proceden del Documento Ambiental del promotor. El sistema no ha podido verificarlos independientemente. Por tanto:

- **Fuente: promotor** → Estado: `DECLARADO` (el promotor lo afirma; nadie lo ha contrastado aún).
- Solo la confirmación administrativa posterior (comprobación catastral, trabajo de campo, consulta a registros) puede elevar el estado.
- El clasificador **nunca eleva DECLARADO a CONFIRMADO**. Eso requiere acción humana explícita.

## Cómo se trata ASUNCION_TEST

Si `default_state=EvidenceState.ASUNCION_TEST`:
- Todos los hechos salen con estado `ASUNCION_TEST`.
- Se añade automáticamente la nota: *"Dato procedente de asunción test; no apto para expediente administrativo real sin confirmación."*
- `ASUNCION_TEST` **nunca puede transicionar a CONFIRMADO** (regla de NL-05: `is_valid_transition()` bloquea AT→CONFIRMADO).

Uso: desbloquear pruebas de integración o demostraciones sin datos reales verificados.

## Cómo se detectan conflictos

`detect_simple_conflicts()` agrupa hechos por `(categoria, campo)`. Si hay más de un valor distinto para el mismo campo:
- Se registra un `conflict` en `ClassificationResult.conflicts`.
- Se añade un `warning` descriptivo.
- Los hechos conflictivos **no se modifican**: siguen con su estado original.
- El sistema no resuelve el conflicto; lo escala para revisión humana.

Ejemplo de conflicto: dos referencias catastrales distintas extraídas del mismo documento.

## Qué NO hace

- **No confirma administrativamente**: ningún dato sale como `CONFIRMADO` por este módulo.
- **No consulta fuentes externas**: no llama a Catastro, AEMET, BOE, ni ninguna API.
- **No resuelve contradicciones**: los conflictos se registran, no se resuelven.
- **No escribe en expedientes**: ningún archivo se crea ni modifica.
- **No usa IA**: todo es mapeo y heurísticas deterministas.
- **No procesa PDFs**: solo `.docx` vía IN-01.

## API

### `classify_entities(result, source_doc_id, source_doc_name, default_state) -> ClassificationResult`

Función principal. Recibe un `ExtractionResult` de IN-02 y devuelve un `ClassificationResult`.

```python
from eia_agent.core.evidence_classifier import classify_entities
from eia_agent.core.evidence_state import EvidenceState

classification = classify_entities(
    extraction_result,
    source_doc_id="DOC-001",
    source_doc_name="Documento_Ambiental.docx",
    default_state=EvidenceState.DECLARADO,
)
print(classification.summary())
```

### `classify_entities_from_docx(path, source_doc_id, default_state) -> ClassificationResult`

Acceso directo desde DOCX. Encadena IN-01 + IN-02 + IN-03 en un solo paso.

```python
from eia_agent.core.evidence_classifier import classify_entities_from_docx

result = classify_entities_from_docx(
    "inputs/memorias/Documento_Ambiental.docx",
    source_doc_id="DOC-001",
)
for f in result.by_category("residuos"):
    print(f.campo, f.valor, f.estado)
```

### `ClassificationResult`

| Método | Descripción |
|--------|-------------|
| `by_category(cat)` | Hechos de la categoría indicada |
| `by_field(campo)` | Hechos del campo indicado |
| `values(campo)` | Lista de valores del campo indicado |
| `summary()` | Resumen: total, por categoría, conflictos, avisos |
| `to_hechos_confirmados(start_index, prefix)` | Lista de dicts schema-válidos con IDs HC-001... |

### `CandidateFact`

| Campo | Descripción |
|-------|-------------|
| `id` | None hasta que se asigna con `to_hechos_confirmados()` |
| `categoria` | Categoría temática (promotor, residuos, operaciones...) |
| `campo` | Campo del schema (codigo_ler, referencia_catastral...) |
| `valor` | Valor normalizado o bruto de la entidad |
| `estado` | Estado de evidencia (casi siempre DECLARADO) |
| `fuentes` | Lista de IDs documentales (e.g. ["DOC-001"]) |
| `entity_type` | Tipo original de IN-02 |
| `confidence` | Confianza de IN-02: HIGH/MEDIUM/LOW |
| `notes` | Notas automáticas (LOW confidence, ASUNCION_TEST...) |
| `to_hecho_confirmado()` | Dict compatible con `hechos_confirmados.schema.json` |

## Mapeo entity_type → categoria/campo

| entity_type (IN-02) | categoria | campo |
|---------------------|-----------|-------|
| REFERENCIA_CATASTRAL | emplazamiento | referencia_catastral |
| LER | residuos | codigo_ler |
| OPERACION | operaciones | operacion_residuos |
| COORDENADA (DEC...) | emplazamiento | coordenadas_wgs84 |
| COORDENADA (UTM...) | emplazamiento | coordenadas_utm |
| SUPERFICIE | superficies | superficie_no_clasificada |
| SUPERFICIE_PARCELA | superficies | superficie_parcela |
| SUPERFICIE_CONSTRUIDA | superficies | superficie_construida |
| SUPERFICIE_UTIL | superficies | superficie_util |
| SUPERFICIE_CATASTRAL | superficies | superficie_catastral |
| SUPERFICIE_NAVE | superficies | superficie_nave |
| CAPACIDAD | capacidades | capacidad |
| POTENCIA | equipos | potencia |
| FECHA | fechas | fecha_documental |
| PROMOTOR | promotor | nombre_promotor |
| TITULAR | titularidad | titular |
| EQUIPO | equipos | equipo |
| *(desconocido)* | otros | *(entity_type.lower())* |

## Cómo se usará en IN-05 y en Fase 1 real

**IN-05** (`inputs_index`) usará `ClassificationResult` para saber qué campos del gate cubre cada documento. Si `resultado.by_category("emplazamiento")` tiene una `referencia_catastral`, el índice marcará ese campo como cubierto por ese documento.

**Fase 1 real** (AG-1+AG-2+AG-3) encadenará:
```
parse_docx() → extract_entities_from_docx() → classify_entities() → escribir a hechos_confirmados.json
```

El módulo IN-03 cubre el tercer paso. La escritura final al JSON la realizará IN-05 o el orquestador, no este módulo.

## Fixture real validada

`expediente-EIA-2026-RECIMETAL-PARCELA/inputs/memorias/Documento_Ambiental_RECIMETAL_Parcela_v6.docx`

Resultado:
- `emplazamiento/referencia_catastral`: `2462302DS4026S0001GQ`
- `residuos/codigo_ler`: múltiples (LER extraídos de tablas)
- `promotor/nombre_promotor`: `RECIMETAL LANZAROTE, S.L.`
- `operaciones/operacion_residuos`: R1201, R1203, R13 y otros
- Estado de todos los hechos: `DECLARADO`
- Archivo no modificado (mtime invariante)

## Ejecutar tests

```bash
# Solo IN-03
venv\Scripts\python -m unittest tests.test_evidence_classifier

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```
