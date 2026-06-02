# CLIENT_PORTAL_SITE

`client_portal_site` exporta una pagina HTML estatica a partir del contrato
`client_portal`. Es el primer prototipo visual entregable para cliente: estado,
documentacion pendiente, siguientes pasos y artefactos disponibles.

No requiere servidor, no llama a APIs externas y no declara aptitud
administrativa.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-portal-site --write
```

Genera:

- `documento/portal_cliente/index.html`

## Contenido

La pagina incluye:

- lectura ejecutiva del estado;
- accion principal recomendada;
- completitud de entrada;
- tabla de requisitos de cliente;
- pasos siguientes para promotor/equipo tecnico;
- artefactos disponibles o pendientes;
- avisos metodologicos.

## Criterio

El HTML es una vista de producto sobre datos ya calculados. No sustituye:

- cierre del objeto evaluado;
- verificacion normativa;
- cartografia oficial;
- auditoria final;
- firma o revision tecnica.

Por diseno, muestra `administrative_ready: false`.

