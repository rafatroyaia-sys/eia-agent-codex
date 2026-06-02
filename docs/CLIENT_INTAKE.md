# CLIENT_INTAKE

`client_intake` define el contrato de entrada para la futura app cliente. Su
objetivo es ordenar lo que el promotor debe aportar antes de iniciar el flujo de
generacion del Documento Ambiental: datos de identidad, coordenadas, referencia
catastral, memorias, fotos, planos, cartografia y alternativas.

No ejecuta fases, no interpreta juridicamente el expediente y nunca declara
`administrative_ready=true`.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-intake --write
```

Sin `--write` solo muestra el resumen por consola. Con `--write` genera:

- `documento/cliente_intake.json`
- `documento/cliente_intake.md`

## Salida JSON

La salida esta pensada para una UI/API de cliente. Incluye:

- `ready_for_initial_processing`: permite saber si no falta ningun obligatorio
  totalmente pendiente para empezar el procesamiento inicial.
- `administrative_ready`: siempre `false`; la presentabilidad se decide con el
  cierre real del expediente y la auditoria final.
- `counts`: totales, completos, parciales, pendientes y ALTA no completos.
- `requirements`: lista estable de requisitos con destino esperado en formulario
  o carpeta de subida.
- `warnings`: avisos de estructura o fase 2 ausente.
- `disclaimer`: cautela metodologica para no confundir intake con aptitud.

## Requisitos actuales

| ID | Prioridad | Tipo | Obligatorio | Entrada |
|----|-----------|------|-------------|---------|
| DAT-001 | ALTA | FIELD | si | Promotor/titular |
| DAT-002 | ALTA | FIELD | si | Coordenadas WGS84 y REGCAN95/UTM si es posible |
| DAT-003 | ALTA | FIELD | si | Referencia catastral |
| DAT-004 | ALTA | FIELD | si | Operaciones y actividad |
| DAT-005 | MEDIA | FIELD | no | Capacidad, superficie, horarios o maquinaria |
| DOC-001 | ALTA | DOCUMENT | si | Memoria tecnica |
| DOC-002 | ALTA | DOCUMENT | si | Memoria de explotacion u operaciones |
| DOC-003 | MEDIA | MEDIA | no | Fotografias del emplazamiento |
| DOC-004 | ALTA | DOCUMENT | si | Planos o esquemas |
| DOC-005 | MEDIA | CARTOGRAPHY | no | Cartografia aportada |
| DOC-006 | ALTA | DOCUMENT | si | Alternativas estudiadas |

## Criterio de bloqueo

El intake distingue dos niveles:

- Procesamiento inicial: puede comenzar si no hay obligatorios en estado
  `PENDIENTE`.
- Cierre/presentacion: no puede declararse por este modulo. Los parciales de
  prioridad `ALTA`, como alternativas no suficientemente desarrolladas, deben
  quedar visibles hasta resolverse en fases posteriores.

