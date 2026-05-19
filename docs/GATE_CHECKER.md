# GATE_CHECKER — NL-04

## Qué hace

`GateChecker` evalúa si un expediente EIA cumple las condiciones mínimas para avanzar de fase. Lee el expediente **sin modificarlo** y devuelve un `GateResult` con la lista de incidencias encontradas.

No es sustituto de la auditoría M-12. Es una comprobación automatizada previa a la redacción.

## Diferencia con la validación de esquema (NL-02)

| | NL-02 SchemaValidator | NL-04 GateChecker |
|---|---|---|
| Qué comprueba | Estructura JSON de las capas | Condiciones mínimas por fase |
| Cuándo se usa | Al ingestar documentos | Al cambiar de fase |
| Resultado | ValidationResult con issues por capa | GateResult con passed/blocked |
| Modifica expediente | No | No |

## Modos de operación

### test_mode=True (por defecto)
Condiciones AT/PROVISIONAL/INDETERMINADO producen `WARNING`, no `ERROR`. El gate puede pasar aunque existan estas condiciones. Útil durante el desarrollo del expediente.

### test_mode=False (producción)
Las mismas condiciones producen `ERROR` y bloquean el avance. Usar antes de entregar el documento final.

## Qué bloquea vs qué advierte

| Condición | test_mode=True | test_mode=False |
|---|---|---|
| Archivos de capas faltantes | ERROR | ERROR |
| Fase anterior no completada | WARNING | ERROR |
| Errores bloqueantes en log | ERROR | ERROR |
| Cartografía PROVISIONAL | WARNING | ERROR |
| Asunción de test (AT) | WARNING | ERROR |
| Impactos INDETERMINADO | WARNING | ERROR |
| Gaps ALTA/CRITICA abiertos | WARNING | ERROR |
| DOCX sin "BORRADOR"/"TEST" | WARNING | — |

## Uso básico

```python
from eia_agent.core.gate_checker import GateChecker

gc = GateChecker("expediente-EIA-NAVE-222")
result = gc.check_phase("4")

if result.is_blocked():
    for issue in result.issues:
        if issue.severity == "ERROR":
            print(issue)
else:
    print("Gate 4 OK →", result.summary())
```

## Clases principales

### GateIssue

```python
@dataclass
class GateIssue:
    severity: str   # ERROR / WARNING / INFO
    phase: str      # "1"–"9"
    code: str       # e.g. "LAYER_MISSING", "PHASE_NOT_COMPLETED"
    message: str
    path: Optional[str]
```

### GateResult

```python
@dataclass
class GateResult:
    expediente_path: Path
    phase: str
    passed: bool
    test_mode: bool
    issues: list[GateIssue]

    def is_blocked(self) -> bool   # True si hay al menos un ERROR
    def error_count(self) -> int
    def warning_count(self) -> int
    def summary(self) -> str       # resumen en una línea
```

### GateChecker

```python
class GateChecker:
    def __init__(self, expediente_path: str | Path, test_mode: bool = True)
    def check_phase(self, phase: str) -> GateResult
```

## Códigos de incidencia

| Código | Fase | Descripción |
|---|---|---|
| `LAYER_MISSING` | 1+ | Capa JSON faltante |
| `SCHEMA_INVALID` | 1 | Capa no pasa validación de esquema |
| `OBJETO_MISSING` | 2 | ficha_objeto_evaluado.md ausente |
| `NORMATIVA_MISSING` | 3 | nota_encuadre_legal.md ausente |
| `NORMATIVA_NOT_VERIFIED` | 3 | Normativa no tiene estado de verificación aceptable |
| `MAPA_MISSING` | 4 | Sin mapas mínimos |
| `CLIMA_MISSING` | 4 | Sin descripción climática |
| `CARTOGRAFIA_PROVISIONAL` | 4+ | Cartografía en estado PROVISIONAL |
| `INVENTORY_MISSING` | 5 | Sin fichas de inventario |
| `IMPACT_FILE_MISSING` | 6 | Archivo de impactos/medidas/PVA faltante |
| `IMPACT_EMPTY` | 6 | Archivo de impactos sin entradas |
| `BLOCK_MISSING` | 7 | Bloque markdown requerido ausente |
| `DOCX_MISSING` | 8 | Sin DOCX en output/ |
| `DOCX_NO_BORRADOR` | 8 | DOCX sin marca BORRADOR/TEST en test_mode |
| `AUDITORIA_MISSING` | 9 | Sin informe de auditoría final |
| `AUDITORIA_NOT_CONFORME` | 9 | Auditoría no alcanza conclusión aceptable |
| `PHASE_NOT_COMPLETED` | 2+ | Fase anterior no completada |
| `LOG_BLOCKING_ERROR` | 1+ | Error bloqueante en orchestrator_log |
| `ASUNCION_TEST` | 1+ | Condición AT en capas (test_mode) |
| `IMPACTO_INDETERMINADO` | 6+ | Impacto clasificado INDETERMINADO |
| `GAPS_ALTA` | 1+ | Gaps de criticidad ALTA o CRITICA abiertos |

## Ejecutar los tests

```bash
# Solo NL-04
venv\Scripts\python -m unittest tests.test_gate_checker

# Suite completa
venv\Scripts\python -m unittest discover -s tests
```

## Relación con otros módulos

| Módulo | Relación |
|---|---|
| NL-02 SchemaValidator | GateChecker llama a `validate_expediente()` en la comprobación de fase 1 |
| NL-03 EIAOrchestrator | GateChecker lee `orchestrator_state.json` para comprobar fases anteriores |
| NL-06 OrchestratorLog | GateChecker lee el log para detectar errores bloqueantes |
| CLI-01 (futuro) | El CLI invocará `check_phase()` automáticamente antes de `start_phase()` |

## Limitaciones

- No es sustituto de la auditoría M-12 (`informe_auditoria_final.md`).
- No comprueba la calidad técnica del contenido, solo la presencia de archivos y estados.
- En modo gabinete, la ausencia de prospección de campo no es un error de gate; es una declaración explícita en el expediente.
- Los aliases de nombres de archivo (NAVE-222 vs PARCELA) están codificados en `REQUIRED_IMPACT_FILES`; si se añaden nuevas tipologías, actualizar esa constante.
