# CLIENT_APP_PACKAGE

`client_app_package` genera la entrega profesional para cliente:

- app HTML autocontenida,
- navegacion interna con botones,
- ficha de nuevo proyecto exportable a JSON,
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

## Contenido principal

- `index.html`: app cliente autocontenida.
- `README_CLIENTE.md`: guia profesional de uso.
- `data/app_manifest.json`: flujo funcional, inputs y outputs esperados.
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

- Si falta `clima/climograma.png` pero existe tabla mensual en
  `clima/descripcion_clima.md`, la app genera un climograma PNG visual.
- La app incluye un catalogo de 12 mapas/planos profesionales, incluyendo
  topografico, delimitacion de parcela en rojo, ruido/receptores, Red Natura,
  hidrologia-inundabilidad, paisaje y sintesis ambiental.
- El documento `documento_ambiental_final_revisable.docx` dentro de la app se
  toma del DOCX mas completo y reciente disponible, priorizando el documento
  enriquecido con figuras.
