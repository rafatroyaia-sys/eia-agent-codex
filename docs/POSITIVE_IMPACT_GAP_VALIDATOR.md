# POSITIVE_IMPACT_GAP_VALIDATOR — RD-07

Módulo: `src/eia_agent/core/positive_impact_gap_validator.py`  
CLI: `python run_expediente.py <expediente> audit-positive-gaps [--write]`

## Qué hace

Verifica que los impactos positivos del modelo de Fase 6 que tienen gaps de
criticidad ALTA (o indicadores equivalentes de incertidumbre) **mantienen esa
incertidumbre visible** en dos lugares:

1. El **modelo de impactos** (`notes` o `warnings` del impacto).
2. El **Markdown del documento** (`documento/documento_ambiental_borrador.md`,
   `bloques/*.md`, `impactos/*.md`), si existe.

Detecta también lenguaje de cierre o compensación prohibido cuando el impacto
aún no está acreditado.

## Qué NO hace

- No modifica impactos, medidas ni PVA.
- No declara el expediente apto para presentación administrativa
  (`administrative_ready = False` siempre).
- No usa IA, no consulta fuentes externas, no hace llamadas de red.
- No resuelve los gaps ni cierra la incertidumbre.
- No evalúa si el impacto positivo es real o verificable.

## Códigos de incidencia

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| RD07-E001 | ERROR | Impacto positivo con gap ALTA sin nota de incertidumbre visible en modelo ni Markdown |
| RD07-E002 | ERROR | Impacto positivo con gap ALTA usa lenguaje de cierre o compensación prohibido |
| RD07-W001 | WARNING | Impacto positivo parece estimado/declarado pero no incluye nota explícita de incertidumbre |
| RD07-W002 | WARNING | Nota de incertidumbre presente en modelo pero no propagada al Markdown del documento |

## Detección de impacto positivo

Un impacto se considera positivo si cumple al menos una de estas condiciones:

- `nature` = `POSITIVO`
- `significance_without_measures` o `significance_with_measures` ∈
  {`POSITIVO`, `BENEFICIOSO`, `FAVORABLE`, `COMPATIBLE_POSITIVO`, `POSITIVE`,
  `POSITIVO_MODERADO`, `POSITIVO_NOTABLE`}
- `description` o `name` contiene marcadores de texto positivo ("impacto
  positivo", "beneficio", "mejora ambiental"...) SIN negación previa.

## Detección de gap ALTA

Un impacto positivo tiene gap ALTA si:

- Algún gap en `data_gaps` tiene `criticality` `ALTA` o `BLOQUEANTE`.
- `status` ∈ {`PENDIENTE_DATOS`, `INDETERMINADO`} (incluso sin gaps explícitos).
- `notes` o `warnings` contienen marcadores de alta incertidumbre ("alta",
  "bloqueante", "no acreditado", "incertidumbre alta", etc.).
- `description`/`name` contienen marcadores fuertes (excluye "estimado" suelto,
  que sólo dispara W001).

## Detección de nota de incertidumbre (modelo)

`impact_has_uncertainty_note` sólo comprueba `notes` y `warnings`. Que la
`description` diga "estimado" no es una nota editorial: es el dato que
desencadena W001. Una nota editorial debe estar en `notes` o `warnings`.

## Detección de frases prohibidas (negación contextual)

Las frases de cierre/compensación se permiten si van precedidas de una negación
en los 35 caracteres anteriores:

- "no compensa los impactos negativos" → permitido
- "no se considera plenamente acreditado" → permitido
- "compensa los impactos negativos" → prohibido (RD07-E002)

## Outputs

Con `--write`:

```
<expediente>/auditoria/positive_gap_result.json
<expediente>/auditoria/positive_gap_result.md
```

El JSON incluye `administrative_ready: false`.

## Uso

```bash
# Solo lectura (dry-run)
python run_expediente.py expediente-EIA-NAVE-222 audit-positive-gaps

# Escribir outputs en auditoria/
python run_expediente.py expediente-EIA-NAVE-222 audit-positive-gaps --write
```

## Tests

```bash
$env:PYTHONPATH = "src"
python -m unittest tests.test_positive_impact_gap_validator -v
```

Suite: 99 tests, 17 clases, 100% offline.

## Relaciones

- Depende de: `IM-00` (impact_model, sólo TYPE_CHECKING)
- Modelo buscado en orden: `phase6_model_with_pva.json` →
  `phase6_model_with_measures.json` → `phase6_model_with_conesa.json` →
  `phase6_model_with_impacts.json`
- Puede complementarse con: `AU-02` (prudence_validator), `RD-06`
  (conesa_checker), `RD-08` (diagnostic_measure_validator)
- Integrado en pipeline: `PIPE-05` — paso `AUDIT_POSITIVE_GAPS` (posición 10
  en el pipeline técnico de 19 pasos), entre `AUDIT_CONDITIONAL_CHAINS` y
  `PHASE6_CUMULATIVE`
- Consumido por: `AU-04` (`final_audit_report.py`) como fuente
  `RD-07_POSITIVE_GAPS` — produce incidencias ALTA (ERROR) o MEDIA (WARNING)
  en el informe final
