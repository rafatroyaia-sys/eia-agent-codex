# CLIENT_PORTAL

`client_portal` genera el paquete unico para la futura interfaz cliente. Combina
el intake de entrada, el dashboard del expediente, los siguientes pasos y los
artefactos disponibles.

No ejecuta fases, no interpreta juridicamente y nunca declara
`administrative_ready=true`.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-portal --write
```

Sin `--write` muestra un resumen. Con `--write` genera:

- `documento/cliente_portal.json`
- `documento/cliente_portal.md`

## Uso en la app

La salida JSON esta pensada para alimentar una UI/API con:

- `status`: estado operativo visible para el cliente.
- `headline`: lectura ejecutiva del estado.
- `primary_action`: accion principal recomendada.
- `intake`: resumen de completitud de entrada.
- `form_schema`: controles y validaciones minimas para renderizar formularios.
- `dashboard`: resumen tecnico ya calculado.
- `upload_sections`: secciones de formulario/subida para memoria, coordenadas,
  fotos, planos, cartografia y alternativas.
- `next_steps`: pasos ordenados para promotor y equipo tecnico.
- `artifacts`: documentos descargables o pendientes.
- `warnings`: avisos que no deben ocultarse.

## Estados principales

- `ESPERANDO_DOCUMENTACION_CLIENTE`: faltan obligatorios del intake.
- `LISTO_PARA_PROCESAMIENTO_INICIAL`: la entrada permite comenzar, pero aun no
  hay estado tecnico consolidado.
- `BLOQUEADO_POR_ITEMS_ALTA`: hay items ALTA en plan/dashboard.

## Criterio metodologico

El portal es una capa de producto. No sustituye:

- cierre de objeto evaluado;
- triaje normativo verificado;
- cartografia oficial;
- auditoria final;
- revision/firma tecnica o juridica.

Por diseno, `administrative_ready` permanece siempre en `false`.
