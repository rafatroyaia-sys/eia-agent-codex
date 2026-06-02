# CLIENT_FORM_SCHEMA

`client_form_schema` genera un contrato de formulario para la futura app
cliente. Parte del intake y produce controles UI/API con obligatoriedad,
prioridad, estado, destino, formatos aceptados y validaciones minimas.

No ejecuta fases, no interpreta juridicamente y nunca declara
`administrative_ready=true`.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-form-schema --write
```

Genera:

- `documento/cliente_form_schema.json`
- `documento/cliente_form_schema.md`

## Controles

El esquema distingue:

- `text`: datos simples del promotor o expediente.
- `coordinates`: coordenadas WGS84 y, si se aporta, REGCAN95/UTM huso 28N.
- `operation_selector`: operaciones/codigos legales base como R12, R13 o D15.
- `file_upload`: memorias, fotos, planos, cartografia y alternativas.

## Validaciones minimas

El JSON incluye validaciones de producto:

- obligatoriedad;
- prioridad;
- formatos aceptados;
- limites de numero/tamano de ficheros;
- sistemas de coordenadas esperados;
- pista de referencia catastral;
- codigos legales orientativos para operaciones.

## Criterio

El esquema sirve para construir la interfaz y evitar entradas ambiguas. No
sustituye la ingesta, el cierre de objeto, la auditoria ni la revision tecnica.

