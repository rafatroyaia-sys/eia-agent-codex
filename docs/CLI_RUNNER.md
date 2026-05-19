# CLI_RUNNER — CLI-01

## Qué hace

`run_expediente.py` es el runner básico de EIA-Agent v2.1. Proporciona acceso desde consola a los módulos de productización sin ejecutar agentes reales ni modificar expedientes salvo bajo flag explícito.

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `status` | Estado del orquestador. No crea archivos si no hay estado previo. |
| `validate` | Valida los schemas JSON de las 6 capas del expediente. |
| `gate <FASE>` | Evalúa el gate mínimo de una fase. |
| `recover` | Diagnostica sesiones interrumpidas o inconsistentes. |
| `log-summary` | Resumen del log del orquestador (solo lectura). |

## Ejemplos — Windows

```bat
:: Estado del expediente
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 status

:: Validar schemas
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 validate

:: Gate de fase 4 en modo test (por defecto)
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 gate 4

:: Gate de fase 4 en modo producción (estricto)
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 gate 4 --prod

:: Diagnóstico de sesión sin escribir nada
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 recover

:: Diagnóstico con informe escrito
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 recover --write-report

:: Resumen del log
venv\Scripts\python run_expediente.py expediente-EIA-NAVE-222 log-summary
```

## Ejemplos — macOS / Linux

```bash
# Estado del expediente
python run_expediente.py expediente-EIA-NAVE-222 status

# Validar schemas
python run_expediente.py expediente-EIA-NAVE-222 validate

# Gate de fase 4 en modo test
python run_expediente.py expediente-EIA-NAVE-222 gate 4

# Gate de fase 4 en modo producción
python run_expediente.py expediente-EIA-NAVE-222 gate 4 --prod

# Diagnóstico sin escribir
python run_expediente.py expediente-EIA-NAVE-222 recover

# Diagnóstico con informe escrito
python run_expediente.py expediente-EIA-NAVE-222 recover --write-report

# Resumen del log
python run_expediente.py expediente-EIA-NAVE-222 log-summary
```

## Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK — sin errores bloqueantes / gate pasado / puede continuar |
| `1` | Error — validación fallida / gate bloqueado / no puede continuar / expediente no encontrado |

## Gate: test vs --prod

Por defecto, `gate` usa `test_mode=True`: las condiciones AT (asunción de test), cartografía PROVISIONAL e impactos INDETERMINADO producen `WARNING`, no `ERROR`, y el gate puede pasar.

Con `--prod`, esas mismas condiciones producen `ERROR` y bloquean el gate. Usar antes de entregar el documento final.

```
gate 4          → test_mode=True  (WARNING para PROVISIONAL)
gate 4 --prod   → test_mode=False (ERROR  para PROVISIONAL)
```

## Recover: con y sin --write-report

Sin `--write-report` (comportamiento por defecto): `recover` solo imprime el diagnóstico en consola. No escribe ningún archivo en el expediente.

Con `--write-report`: escribe `control_interno/recovery_report.json` con el detalle completo del diagnóstico. No modifica `orchestrator_state.json` ni `orchestrator_log.json`.

```
recover                → solo lectura, sin archivos creados
recover --write-report → crea control_interno/recovery_report.json
```

## Qué NO hace todavía

- **No ejecuta agentes reales** (AG-01..AG-10, M-11, M-12).
- **No genera fases** — no invoca ningún agente de procesamiento.
- **No crea estado del orquestador** si no existe — `status` avisa sin crear archivos.
- **No repara** inconsistencias detectadas por `recover`.
- **No lanza** el ensamblado DOCX ni la auditoría.
- **No tiene** interfaz web ni frontend.

Estas funcionalidades se añadirán en iteraciones posteriores (NL-10, AU-01, etc.).

## Relación con otros módulos

| Módulo | Comando que lo usa |
|---|---|
| NL-02 SchemaValidator | `validate` |
| NL-03 EIAOrchestrator | `status` |
| NL-04 GateChecker | `gate` |
| NL-06 OrchestratorLog | `log-summary` |
| NL-07 SessionRecovery | `recover` |

## Ejecutar los tests

```bash
# Solo CLI-01
venv\Scripts\python -m unittest tests.test_cli_runner

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

## Usar main() programáticamente

`main(argv)` acepta una lista de argumentos y devuelve el código de salida. Útil para pruebas o integración:

```python
from run_expediente import main

code = main(["expediente-EIA-NAVE-222", "validate"])
print("Válido" if code == 0 else "Con errores")
```
