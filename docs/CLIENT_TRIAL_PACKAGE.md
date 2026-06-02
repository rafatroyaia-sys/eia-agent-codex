# CLIENT_TRIAL_PACKAGE

`client_trial_package` genera un paquete entregable para que el cliente pruebe
la experiencia sin depender todavia de un deploy web.

No ejecuta fases tecnicas y no declara aptitud administrativa.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-trial-package --write
```

Genera:

- `documento/cliente_trial_package/`
- `documento/cliente_trial_package.zip`

## Contenido

- `index.html`: portal cliente estatico.
- `README_CLIENTE.md`: guia de prueba.
- `data/cliente_portal.json`: contrato completo para UI/API.
- `data/cliente_form_schema.json`: controles y validaciones.
- `data/cliente_submission_validation.json`: validacion de entrega.
- `markdown/`: versiones legibles para revision.

## Uso recomendado

1. Entregar el ZIP al cliente.
2. Indicarle que abra `index.html`.
3. Pedirle que revise los errores/advertencias y aporte la documentacion marcada.
4. Regenerar el paquete tras actualizar inputs.

## Criterio

El paquete permite prueba funcional y revision experta por el cliente. No debe
rotularse como apto administrativo. El objetivo es avanzar hacia
"preparado para revision/presentacion" solo cuando no existan bloqueos.
