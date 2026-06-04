# EIA-Agent v2.1
## Sistema evidence-first para Documentos Ambientales de Evaluación de Impacto Ambiental

**Estado actual**: FASE DE PRODUCTIZACIÓN — piloto validado, extrayendo arquitectura reusable  
**Última actualización**: 2026-04-13  
**Piloto de referencia**: EIA-2026-RECIMETAL-PARCELA — EXPEDIENTE CON OBSERVACIONES EN MODO TEST  

---

## ¿Qué es este sistema?

EIA-Agent v2.1 es un sistema de generación asistida de Documentos Ambientales (DA) para la evaluación de impacto ambiental simplificada, conforme a la Ley 21/2013 y normativa autonómica canaria.

Principio rector: **Primero se prueba, después se delimita, luego se valora, y al final se redacta.**

El sistema es evidence-first: ningún dato entra en el DA sin un estado de evidencia explícito (CONFIRMADO / DECLARADO / INFERIDO / ESTIMADO / PENDIENTE / DESCARTADO) y una traza de origen.

---

## Estructura del repositorio

```
/proyecto-eia/
│
├── CLAUDE.md                           ← instrucciones del sistema para el agente LLM
├── README.md                           ← este archivo
│
├── expediente-EIA-2026-RECIMETAL-PARCELA/  ← PILOTO VALIDADO (modo test, congelado)
│   ├── README_EXPEDIENTE.md            ← estado y log de fases del piloto
│   ├── inputs/                         ← documentos del promotor (procesados)
│   ├── capas/                          ← 6 JSONs de la base de datos por capas
│   ├── mapas/                          ← 8 mapas WMS generados (MAP-001 a MAP-008)
│   ├── clima/                          ← datos AEMET + climograma (estación C029O)
│   ├── fichas_inventario/              ← 16 fichas FI-01 a FI-16
│   ├── impactos/                       ← matrices Conesa, medidas M-01..M-10, PVA-01..PVA-07
│   ├── bloques/                        ← bloques A-K en markdown
│   ├── control_interno/                ← auditoría M-12, logs, coherencia
│   └── output/                         ← DA_RECIMETAL_PARCELA_v1.docx (1.120 KB)
│
├── control_interno/                    ← documentos de productización
│   ├── postmortem_piloto_recimetal.md  ← qué funcionó, qué falló, baseline aprobado
│   ├── backlog_productizacion.md       ← 72 ítems priorizados en 13 áreas
│   └── roadmap_productizacion.md      ← fases P1, P2, P3 con criterios de éxito
│
└── prompts/                            ← system prompts por agente (en construcción)
    ├── README_PROMPTS.md               ← estructura y convenciones
    ├── SYSTEM_BASE.md                  ← reglas comunes a todos los agentes
    └── AG-10/
        └── bloque_J_rnt.md            ← RNT: reglas anti-hiperbolización (validado en piloto)
```

---

## Arquitectura del sistema (9 fases + gates)

| Fase | Agente | Descripción | Gate |
|------|--------|-------------|------|
| 1 | AG-1 + AG-2 + AG-3 | Ingesta, extracción de entidades, clasificación de evidencia | Documentos procesados e indexados |
| 2 | AG-4 | Cierre del objeto evaluado | Coordenadas, RC, operaciones, modo declarados |
| 3 | AG-5 | Triaje normativo vivo (BOE/BOC) | Procedimiento, normativa, órganos identificados |
| 4 | AG-6 + AG-7 | Cartografía WMS + clima AEMET (en paralelo) | 8 mapas + climograma |
| 5 | AG-8 | Inventario ambiental por factor | Fichas con diferenciación gabinete/campo |
| 6 | AG-9 | Impactos Conesa + medidas + PVA | Cadena completa sin impactos sin medida |
| 7 | AG-10 | Redacción bloques A-K | Sin pendientes críticos |
| 8 | M-11 | Ensamblaje DOCX | DOCX íntegro, abre sin errores |
| 9 | M-12 | Auditoría art.45 + coherencia + formato | CONFORME o CON OBSERVACIONES justificadas |

---

## Estado del piloto

El piloto EIA-2026-RECIMETAL-PARCELA está **CONGELADO** como baseline de referencia. Las 9 fases están cerradas. El resultado de auditoría es **EXPEDIENTE CON OBSERVACIONES EN MODO TEST** — sin incoherencias materiales pero con 5 gaps de criticidad ALTA que requieren campo para el expediente real.

Ver `expediente-EIA-2026-RECIMETAL-PARCELA/control_interno/informe_auditoria_final.md` para el detalle completo.

---

## Estado de productización

**Fase activa**: P1 — Núcleo funcional automatizable  
**Prioridad inmediata**: Formalizar JSON schemas, reescribir ensamblador en Python, crear validadores de gates programáticos.

Ver:
- `control_interno/backlog_productizacion.md` — 72 ítems en 13 áreas
- `control_interno/roadmap_productizacion.md` — fases P1, P2, P3

---

## Comandos slash disponibles

```
/nuevo-expediente [ID]    → inicializa estructura + JSONs vacíos
/fase1 [ruta-a-inputs]   → ingesta + extracción
/fase2                   → cierre del objeto
/fase3                   → triaje normativo
/fase4                   → cartografía + clima
/fase5                   → inventario ambiental
/fase6                   → impactos + medidas + PVA
/fase7                   → redacción bloques A-K
/fase8                   → ensamblaje DOCX
/fase9                   → auditoría final
/estado                  → estado de fases y gates
/gaps                    → gaps de criticidad alta
/evidencia [campo]       → trazabilidad de un dato
```

---

## Validación automática

El proyecto usa **GitHub Actions** para validación automática en cada push y pull request.

El workflow CI ejecuta:
- instalación de dependencias desde `requirements.txt`
- verificación de imports del paquete `eia_agent`
- suite completa de tests unitarios (offline, sin APIs externas ni claves reales)
- comprobación de que no se versionan archivos prohibidos
- escaneo informativo de secretos

Ver `.github/workflows/ci.yml` y `docs/CI_GITHUB_ACTIONS.md` para más detalle.

---

## Compatibilidad con expedientes piloto

Los expedientes avanzados que ya tienen fichas AG-08 en
`fichas_inventario/indice_inventario.json` pueden reconstruir el
`inventario/inventory_summary.json` productizado mediante el adaptador legacy.
El sistema conserva gaps, cautelas y estados de evidencia; no eleva datos ni
declara aptitud administrativa.

Ver `docs/INVENTORY_LEGACY_ADAPTER.md`.

---

## Plan de accion cliente

Tras ejecutar `cliente-da --write`, el comando `cliente-plan --write` genera
`documento/plan_accion_cliente.json` y `.md`. El plan separa lo que debe pedirse
al promotor (por ejemplo alternativas o cartografia suficiente) de las
correcciones internas del equipo tecnico (lenguaje prudente, coherencia,
trazabilidad o estructura).

Ver `docs/CLIENT_ACTION_PLAN.md`.

---

## Normativa mínima por expediente

- **Ley 21/2013**: arts. 7, 16, 45, 46, 47, Anexos II, III
- **Ley 7/2022**: residuos y suelos contaminados
- **RD 445/2023**: modifica Anexos I, II y III de Ley 21/2013
- **Canarias**: Ley 4/2017, Decreto 181/2018, Ley 6/2022, DL 5/2024, DL 1/2026, DL 6/2025

**Verificar siempre online antes de cada expediente.**

## App web para cliente

La aplicacion cliente se puede desplegar como servicio web publico con frontend
y backend en el mismo dominio. El repositorio incluye:

- `Dockerfile`: entorno reproducible.
- `render.yaml`: Blueprint de Render con health check y disco persistente.
- `src/eia_agent/core/client_web_service.py`: servicio web desplegable.
- `docs/DEPLOY_PUBLIC_WEB.md`: instrucciones para obtener una URL publica.

En Render, conectar este repositorio mediante `New > Blueprint`, introducir una
clave privada en `EIA_ACCESS_TOKEN` y desplegar. El cliente solo necesitara la
URL y esa clave; no instala Python ni ejecuta archivos locales.

La app organiza y genera expedientes respetando gates tecnicos. No declara
automaticamente aptitud administrativa.

---

*EIA-Agent v2.1 — 2026-04-13*
