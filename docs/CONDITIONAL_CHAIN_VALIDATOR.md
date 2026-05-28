# CONDITIONAL_CHAIN_VALIDATOR — IM-09

Validador determinístico de cadenas condicionales impacto-medida-PVA para Fase 6 EIA.

**Módulo**: `src/eia_agent/core/conditional_chain_validator.py`  
**ID de productización**: IM-09  
**Dependencias**: IM-00 (`impact_model`)

---

## Qué hace IM-09

- Lee un `Phase6Model` con impactos (`EnvironmentalImpact`), medidas (`MitigationMeasure`) y programas PVA (`PVAProgram`).
- Detecta qué impactos, medidas y PVA están en estado condicionado (por GAP, CONT, AT u otro marcador).
- Verifica que la condición se propague de forma coherente a lo largo de la cadena: si un impacto está condicionado, las medidas y PVA vinculados deben reflejar también ese estado.
- Genera incidencias tipificadas (ERROR / WARNING / INFO) con código, mensaje y recomendación.
- Produce un informe JSON estructurado y un informe Markdown legible.

---

## Qué NO hace IM-09

| Fuera de alcance | Razón |
|-----------------|-------|
| Resolver gaps (`data_gaps`) | Competencia de AG-8 / usuario |
| Cerrar CONTs (condicionantes técnicos) | Deben resolverse antes de redactar |
| Eliminar AT (asunciones de test) | Competencia del sistema AT |
| Modificar impactos, medidas o PVA | Solo lectura; nunca escribe en el modelo |
| Declarar aptitud administrativa del expediente | Este módulo es una herramienta de coherencia interna |
| Verificar suficiencia técnica de las medidas | Eso corresponde a IM-03 / AG-9 |

---

## Qué es una cadena condicional

Una **cadena condicional** es la tripla `impacto → medida → PVA` en la que alguno de los elementos está marcado como pendiente de datos, condicionado o indeterminado.

**Marcadores de condición reconocidos**:

| Marcador en el modelo | Detección |
|-----------------------|-----------|
| `status = INDETERMINADO` (impacto) | Campo `status` |
| `status = PENDIENTE_DATOS` (impacto) | Campo `status` |
| `status = CONDICIONADA` (medida) | Campo `status` |
| `status = CONDICION_PREVIA` (medida) | Campo `status` |
| `frequency = CONDICIONAL` (PVA) | Campo `frequency` |
| Texto "GAP", "CONT", "AT", "condicionado", "indeterminado", "pendiente_datos", "pendiente datos", "no determinado", "sin determinar", "a determinar", "sujeto a" | En `notes`, `warnings`, `name`, `indicator` |

---

## Relaciones impacto ↔ medida ↔ PVA

- **Impacto → medidas**: via `impact.measure_ids` y `measure.target_impact_ids`.
- **Impacto → PVA**: via `impact.pva_ids` y `pva.target_impact_ids`.
- **Medida → PVA**: via `pva.target_measure_ids`.

El validador recorre estas relaciones bidireccionalmente para comprobar coherencia.

---

## Códigos de incidencia

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| CC-IMP-E001 | ERROR | Impacto condicionado con medida o PVA que no refleja la condición |
| CC-IMP-E002 | ERROR | Impacto condicionado con medida "cerradora" (PROPUESTA no condicionada como única reductora) |
| CC-IMP-W001 | WARNING | Impacto condicionado sin ninguna medida condicionada vinculada |
| CC-IMP-W002 | WARNING | Impacto condicionado con PVA vinculado que no refleja la condición |
| CC-MEA-E001 | ERROR | Medida diagnóstica usada como único reductor de significancia en impacto condicionado |
| CC-MEA-W001 | WARNING | Medida condicionada sin PVA vinculado |
| CC-PVA-W001 | WARNING | PVA condicionado sin impactos ni medidas vinculadas |
| CC-PVA-W002 | WARNING | PVA condicionado con lenguaje de cierre en nombre/indicador |

---

## Estados de resultado

| Estado | Criterio |
|--------|----------|
| `SIN_DATOS` | El modelo no contiene impactos, medidas ni PVA |
| `OK` | Sin incidencias de tipo ERROR ni WARNING |
| `CON_OBSERVACIONES` | Hay WARNINGs pero ningún ERROR |
| `NO_CONFORME` | Hay al menos un ERROR |

`administrative_ready` siempre es `false` en el JSON de salida: este módulo no certifica aptitud administrativa.

---

## Uso CLI

```bash
# Solo imprime el resumen
python run_expediente.py <ruta_expediente> audit-conditional-chains

# Escribe JSON + Markdown en <expediente>/auditoria/
python run_expediente.py <ruta_expediente> audit-conditional-chains --write
```

**Códigos de salida**:
- `0`: resultado OK o SIN_DATOS (sin errores)
- `1`: hay ERRORs, o error de lectura

**Archivos generados** (con `--write`):
- `auditoria/conditional_chain_result.json`
- `auditoria/conditional_chain_result.md`

---

## Uso programático

```python
from pathlib import Path
from eia_agent.core.conditional_chain_validator import (
    validate_conditional_chains_from_files,
    validate_conditional_chains_from_json,
    validate_conditional_chains,
    write_conditional_chain_outputs,
    build_conditional_chain_report_markdown,
)

# Desde directorio de expediente
result = validate_conditional_chains_from_files(Path("expediente-EIA-001"))

# Desde JSON de fase 6
result = validate_conditional_chains_from_json(Path("expediente-EIA-001/impactos/phase6_model.json"))

# Desde objeto Phase6Model
from eia_agent.core.impact_model import Phase6Model
model = Phase6Model(...)
result = validate_conditional_chains(model)

# Informe Markdown
md = build_conditional_chain_report_markdown(result)

# Escribir outputs
json_path, md_path = write_conditional_chain_outputs(result, Path("expediente-EIA-001/auditoria"))
```

---

## Estructura del resultado

```python
@dataclass
class ConditionalChainResult:
    status: str                       # OK / CON_OBSERVACIONES / NO_CONFORME / SIN_DATOS
    checked_impacts: list[str]        # IDs de impactos analizados
    checked_measures: list[str]       # IDs de medidas analizadas
    checked_pva_programs: list[str]   # IDs de PVA analizados
    conditioned_impacts: list[str]    # IDs de impactos condicionados
    conditioned_measures: list[str]   # IDs de medidas condicionadas
    conditioned_pva_programs: list[str]  # IDs de PVA condicionados
    issues: list[ConditionalChainIssue]
    warnings: list[str]
    notes: list[str]
```

---

## Cómo ejecutar los tests

```bash
# Solo tests de este módulo
venv\Scripts\python -m unittest tests.test_conditional_chain_validator

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

Los tests están en `tests/test_conditional_chain_validator.py` (15 clases, 80+ casos).
