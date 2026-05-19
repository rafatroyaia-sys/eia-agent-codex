# Gates automáticos — EIA-Agent v2.1

## Concepto

El gate valida el modelo de datos **antes de ejecutar una fase**. Si el modelo no
está en un estado consistente, la fase no debe ejecutarse — el resultado sería
documentación basada en datos corruptos o incompletos.

`run_gate.py` encapsula esta lógica: valida todas las capas, aplica los requisitos
mínimos de la fase solicitada, y devuelve un exit code claro.

---

## Uso

```bash
# Modo producción (GAPs ALTA bloquean)
python tools/run_gate.py <expediente_path> <fase>

# Modo test (GAPs ALTA producen aviso, no bloqueo)
python tools/run_gate.py <expediente_path> <fase> --test

# Ejemplos
python tools/run_gate.py expediente-EIA-2026-RECIMETAL-PARCELA 5
python tools/run_gate.py expediente-EIA-2026-RECIMETAL-PARCELA 4A --test
```

**Exit codes:**
- `0` — gate aprobado (puede haber avisos)
- `1` — gate bloqueado (no ejecutar la fase)

---

## Lógica de decisión

| Causa | Modo producción | Modo --test |
|-------|----------------|-------------|
| Error de modelo (JSON inválido, campo ausente, enum incorrecto, ID duplicado) | **BLOQUEO** | **BLOQUEO** |
| Archivo referenciado ausente en disco (SG estado=cualquiera; CT estado=GENERADO/VERIFICADO) | **BLOQUEO** | **BLOQUEO** |
| TR con `hc_ids` referenciando HC inexistente (referencia colgante) | **BLOQUEO** | **BLOQUEO** |
| `ficha_objeto_evaluado.md` demasiado pequeña o ausencia de sección crítica (OB-01) | **BLOQUEO** | **BLOQUEO** |
| Requisito mínimo de fase no cumplido | **BLOQUEO** | **BLOQUEO** |
| GAP de criticidad ALTA abierto | **BLOQUEO** | aviso |
| Archivo referenciado ausente (CT estado=ERROR/PENDIENTE) | aviso | aviso |
| HC CONFIRMADO sin trazabilidad en matriz_trazabilidad (AU-03) | aviso | aviso |
| Sección informativa ausente en `ficha_objeto_evaluado.md` (OB-01) | aviso | aviso |
| Aviso del validador (no crítico) | aviso | aviso |

Los errores de modelo y los requisitos de fase **siempre bloquean**, incluso en
modo test. Solo los GAPs ALTA cambian de comportamiento.

---

## Requisitos mínimos por fase

| Fase | Requisito |
|------|-----------|
| 1 | Solo validación estructural del modelo |
| 2 | ≥ 5 hechos confirmados |
| 3 | ≥ 10 hechos confirmados + `control_interno/ficha_objeto_evaluado.md` existe |
| 4 / 4A / 4B | ≥ 1 norma con estado `VERIFICADA ONLINE` |
| 5 | ≥ 1 mapa en estado `GENERADO` o `VERIFICADO` |
| 6 | ≥ 8 mapas en estado `GENERADO` o `VERIFICADO` |
| 7 | ≥ 10 hechos confirmados |
| 8 | ≥ 10 entradas en `salidas_generadas` de fase 7 con tipo MD |
| 9 | Al menos 1 entrada en `salidas_generadas` de fase 8 con tipo DOCX |

---

## Registro en log_orquestador.md

Cada ejecución del gate añade una fila al log del expediente si el archivo existe:

```
| YYYY-MM-DD | GATE FASE N | Orquestador | Validacion automatica del modelo de datos (run_gate.py) antes de Fase N | GATE APROBADO. ... |
```

El gate **no crea** el log si no existe — evitar crear artefactos sin contexto.

Los tres estados posibles en el log:
- `GATE APROBADO` — sin errores ni avisos
- `GATE APROBADO_CON_AVISOS` — hay avisos no bloqueantes
- `GATE BLOQUEADO` — causas de bloqueo listadas

---

## Integración en el flujo de trabajo

### Antes de ejecutar cualquier fase

```bash
python tools/run_gate.py $EXPEDIENTE 3
if [ $? -ne 0 ]; then
    echo "Gate bloqueado. Resolver issues antes de continuar."
    exit 1
fi
# ... ejecutar fase 3
```

### Integración con el orquestador Claude

El orquestador debe llamar al gate **antes de delegar a cada agente**. La salida
del gate es suficiente para decidir si continuar o detener. No es necesario
re-ejecutar el validador por separado si el gate ya lo ha invocado.

Patrón recomendado:

```
1. Usuario indica /fase5
2. Orquestador ejecuta: python tools/run_gate.py <expediente> 5
3. Si exit 1: detener, mostrar causas de bloqueo al usuario
4. Si exit 0: proceder con el agente AG-8
```

### Modo test durante el desarrollo del piloto

Usar `--test` cuando el expediente está en construcción y hay GAPs ALTA
pendientes de datos del promotor que no bloquean la redacción de otras secciones.

**No usar `--test` en producción** (expedientes reales para presentación).

---

## Relación con validate_expediente.py

`run_gate.py` importa directamente la lógica de `validate_expediente.py` — no hay
llamada a subproceso ni parsing de stdout. Comparten:

- `CAPAS_REQUERIDAS` — lista de los 6 JSONs obligatorios
- `Result` — clase acumuladora de errores y avisos
- Todas las funciones `validate_*` por capa
- `validate_cross_layer()` — consistencia entre capas
- `count_gaps_alta()` — lista de GAPs bloqueantes

Si se actualiza la lógica de validación en `validate_expediente.py`, el gate
la recoge automáticamente en la siguiente ejecución.

---

## Archivos del sistema de validación/gate

```
tools/
├── validate_expediente.py    → validador del modelo de datos (uso directo o importado)
├── run_gate.py               → gate automático por fase (invoca validate_expediente)
├── README_VALIDACION.md      → documentación del validador
└── README_GATES.md           → este archivo
```
