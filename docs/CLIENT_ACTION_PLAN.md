# Plan de accion cliente

Modulo: `src/eia_agent/core/client_action_plan.py`

El plan de accion cliente transforma los resultados de `cliente-da` y de la
auditoria final en una lista operativa separada en dos bloques:

- **Peticiones al promotor**: documentos, planos, coordenadas, alternativas o
  aclaraciones que debe aportar el cliente/promotor.
- **Acciones internas del equipo tecnico**: correcciones de redaccion prudente,
  coherencia documental, trazabilidad o estructura.

## Archivos de entrada

- `auditoria/final_audit_result.json`
- `documento/estado_expediente_da.json`

Si ambos faltan, el modulo no inventa nada y emite un aviso para ejecutar antes
`cliente-da --write` o `audit-final --write`.

## Salidas

Con `--write` genera:

- `documento/plan_accion_cliente.json`
- `documento/plan_accion_cliente.md`

El Markdown incluye una ruta recomendada de cierre, separando primero los items
ALTA del promotor, despues las acciones tecnicas ALTA, y finalmente la
regeneracion del Documento Ambiental, paquete documental y auditoria final.
El JSON expone esa misma ruta en `closing_route`, con `order`, `title`,
`audience`, `priority` y `action_refs`, para que una UI pueda mostrarla sin
parsear el Markdown.

## Reglas

- No declara aptitud administrativa.
- No cierra gaps.
- No eleva evidencia.
- Deduplica incidencias repetidas entre DA-01 y AU-04.
- Los requisitos `ART45-03` y `ART45-10` se tratan como peticiones directas al
  promotor cuando faltan alternativas o cartografia suficiente.
- Las incidencias de lenguaje prudente y coherencia documental se tratan como
  acciones internas del equipo tecnico.
- Las incidencias internas repetitivas se agrupan por fuente de auditoria para
  que el plan sea accionable. En especial, `RD-04_BLOCK_CONSISTENCY` genera
  recomendaciones de redaccion segura para medidas diagnosticas, PRL/EPI,
  Red Natura/ENP y patrimonio, segun los patrones detectados.

## Uso

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-plan --write
```

El Markdown incluye un borrador de correo al promotor con los items de
criticidad alta y media que procedan.
