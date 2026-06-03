# CLIENT_APP_PACKAGE

`client_app_package` genera la entrega profesional para cliente:

- app HTML autocontenida,
- navegacion interna con botones,
- ficha de nuevo proyecto exportable a JSON,
- app especifica `nuevo_expediente.html` para iniciar proyectos nuevos,
- contratos JSON para UI/API,
- guia de uso cliente,
- Documento Ambiental disponible,
- mapas, planos, clima y anexos disponibles,
- manifest del flujo completo de expediente.

No es una demo. Es la app/paquete cliente para probar y operar el flujo de
expediente ambiental con datos reales o pre-reales.

## Comando

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-app-package --write
```

Genera:

- `documento/cliente_app/`
- `documento/eia_agent_cliente_app.zip`

## Entrega portatil para cliente

El ZIP es portable para un equipo Windows:

1. Descomprimir `eia_agent_cliente_app.zip`.
2. Ejecutar `INICIAR_APP_WINDOWS.bat`.
3. Usar la app en `http://127.0.0.1:8765/`.

El paquete incluye:

- `INICIAR_APP_WINDOWS.bat`: arranque por doble clic.
- `server/eia_client_server.py`: servidor local autonomo sin dependencias externas.
- `expedientes_cliente/`: carpeta que se crea para nuevos proyectos.
- `DEPLOY_PROVISIONAL.md`: guia de uso local y despliegue provisional.

## Backend local

Para usar la app como herramienta de trabajo con alta real de expedientes:

```powershell
venv\Scripts\python run_expediente.py expediente-EIA-2026-RECIMETAL-NAVE-222 cliente-backend --host 127.0.0.1 --port 8765
```

Despues abrir:

```text
http://127.0.0.1:8765/
```

El backend sirve la app y expone API local para:

- crear expedientes nuevos en `expedientes_cliente/`,
- guardar `control_interno/entrada_cliente.json`,
- subir memorias, fotos, planos y cartografia a `inputs/`,
- registrar `control_interno/inventario_archivos_cliente.json`,
- preparar el plan de comandos para generar el Documento Ambiental.

No ejecuta automaticamente la presentacion administrativa ni declara aptitud.

## Contenido principal

- `index.html`: app cliente autocontenida.
- `nuevo_expediente.html`: mesa de entrada para expedientes nuevos.
- `INICIAR_APP_WINDOWS.bat`: arranque portatil Windows.
- `server/eia_client_server.py`: backend portatil incluido en el ZIP.
- `DEPLOY_PROVISIONAL.md`: instrucciones de uso/deploy para cliente.
- `README_CLIENTE.md`: guia profesional de uso.
- `data/app_manifest.json`: flujo funcional, inputs y outputs esperados.
- `data/new_project_blueprint.json`: contrato para alta de nuevos proyectos.
- `data/map_requirements.json`: catalogo profesional de mapas requeridos.
- `data/cliente_form_schema.json`: campos, validaciones y subidas.
- `data/cliente_submission_validation.json`: control de entrega.
- `documentos/`: Documento Ambiental DOCX/MD disponible.
- `planos_mapas/`: mapas, planos y climograma disponibles.
- `control/`: checklist y resultados de calidad disponibles.

## Criterio

La app debe comunicar profesionalidad y utilidad real, pero no debe declarar
aptitud administrativa automatica. La aptitud depende de cierre de objeto,
normativa verificada, cartografia, inventario, impactos, medidas, PVA y
auditoria final conforme.

## Mejoras funcionales

- `nuevo_expediente.html` permite crear una entrada de proyecto nueva con
  datos esenciales, coordenadas, promotor, actividad, descripcion del objeto,
  documentos, fotos, planos y cartografia. Guarda proyectos en el navegador
  mediante `localStorage` y exporta `entrada_cliente.json` y checklist Markdown.
- Si falta `clima/climograma.png` pero existe tabla mensual en
  `clima/descripcion_clima.md`, la app genera un climograma PNG visual.
- La app incluye un catalogo de 12 mapas/planos profesionales, incluyendo
  topografico, delimitacion de parcela en rojo, ruido/receptores, Red Natura,
  hidrologia-inundabilidad, paisaje y sintesis ambiental.
- El documento `documento_ambiental_final_revisable.docx` dentro de la app se
  toma del DOCX mas completo y reciente disponible, priorizando el documento
  enriquecido con figuras.

## Uso para un proyecto nuevo

1. Abrir `nuevo_expediente.html`.
2. Rellenar los datos esenciales del proyecto y coordenadas WGS84.
3. Adjuntar memorias, fotos, planos y cartografia disponible.
4. Revisar el control de minimos y bloqueantes de entrada.
5. Descargar `entrada_cliente.json` y `checklist_entrada.md`.
6. Crear el expediente en el motor EIA-Agent y ejecutar las fases con gates.

La app de navegador prepara una entrada real y controlada para el motor. La
generacion completa del Documento Ambiental DOCX, mapas oficiales, climograma,
anejos y auditoria requiere ejecutar el backend/motor EIA-Agent o desplegarlo
como servicio web.
