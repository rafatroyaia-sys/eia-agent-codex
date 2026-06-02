# CLIENT_SUBMISSION_VALIDATOR

`client_submission_validator` revisa una entrega cliente contra el formulario
esperado. Es una comprobacion previa a la ingesta/procesamiento inicial.

No ejecuta fases, no interpreta juridicamente y nunca declara
`administrative_ready=true`.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-submission-check --write
```

Genera:

- `documento/cliente_submission_validation.json`
- `documento/cliente_submission_validation.md`

## Que comprueba

- Obligatorios pendientes.
- Requisitos ALTA parciales.
- Formatos no aceptados en archivos detectados.
- Coordenadas WGS84 con forma basica latitud/longitud dentro de rango.

## Estados

- `BLOQUEADO_ENTRADA`: hay errores de entrada cliente.
- `CON_OBSERVACIONES`: no hay errores, pero quedan advertencias.
- `LISTO_PARA_INGESTA`: no se detectan incidencias de entrada.

## Criterio

Esta validacion solo responde a si la entrega puede pasar a ingesta o
procesamiento inicial. No sustituye el cierre del objeto, la revision normativa,
la cartografia oficial, la auditoria ni la firma tecnica.

