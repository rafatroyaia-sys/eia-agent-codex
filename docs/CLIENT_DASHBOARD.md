# Dashboard cliente

Modulo: `src/eia_agent/core/client_dashboard.py`

El dashboard cliente compone una fotografia estructurada del expediente para una
futura interfaz web o API. Lee outputs existentes y devuelve una respuesta unica
con estado ejecutivo, indicadores, ruta de cierre y artefactos descargables.

## Entradas

- `documento/estado_expediente_da.json`
- `documento/plan_accion_cliente.json`
- `auditoria/final_audit_result.json`
- Artefactos en `documento/`, `auditoria/` y `output/`

Si falta `plan_accion_cliente.json`, el modulo calcula el plan en memoria desde
las auditorias existentes, pero avisa de que no esta escrito en disco.

## Salidas

Con escritura genera:

- `documento/cliente_dashboard.json`
- `documento/cliente_dashboard.md`

El JSON incluye:

- `status`, `headline`, `next_action`
- `counts` para peticiones, acciones tecnicas, estado DA y auditoria
- `da_state` resumido
- `action_plan.executive_summary`
- `action_plan.closing_route`
- `artifacts` con disponibilidad y tamano
- `administrative_ready=false`

## Reglas

- No ejecuta fases.
- No modifica inputs.
- No cierra gaps.
- No declara aptitud administrativa.
- No sustituye revision tecnica ni juridica.

## Uso previsto

Este modulo es la capa de contrato para la futura app cliente:

1. El backend ejecuta `cliente-da` y `cliente-plan`.
2. El dashboard consolida los resultados.
3. La interfaz muestra estado, siguiente accion, pendientes y descargas.

## Ejemplo CLI futuro

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-dashboard --write
```
