# EIA-AGENT v2.1 — Arquitectura depurada, evidence-first y lista para producción

> Este documento integra la arquitectura v2.0 de Claude con los 10 ajustes 
> propuestos en la revisión externa, resultando en la versión definitiva 
> para implementación en Claude Code.

## Changelog v2.0 → v2.1

| # | Ajuste | Estado |
|---|--------|--------|
| 1 | M-11 Ensamblador y M-12 Auditor como módulos formales | ✅ Incorporado |
| 2 | Art. 7.2.c (modificaciones) y 7.2.d (fraccionamiento) en triaje | ✅ Incorporado |
| 3 | Órgano sustantivo/ambiental parametrizable, no hardcoded | ✅ Incorporado |
| 4 | Cadena normativa autonómica viva (DL 1/2026, DL 6/2025) | ✅ Incorporado |
| 5 | Doble sistema coordenadas: WGS84 + REGCAN95/UTM 28N | ✅ Incorporado |
| 6 | Trazabilidad cartográfica completa (cartografia_trace.json) | ✅ Ya estaba en v2.0, reforzado |
| 7 | Campo formal gabinete/campo en inventario | ✅ Incorporado en ficha objeto + AG-8 |
| 8 | Conclusiones prudentes sin usurpar órgano ambiental | ✅ Incorporado en AG-10 |
| 9 | Doble capa códigos R/D: legal_base + operativo_interno | ✅ Incorporado en ficha objeto |
| 10 | Trazabilidad cartográfica como evidencia (no solo PNG) | ✅ Reforzado con hash + request |

## Arquitectura final

### Piezas del sistema: 10 agentes + 2 módulos + 1 orquestador

| Pieza | ID | Misión |
|-------|-----|--------|
| Orquestador | ORQ | Coordina fases, gates, retornos |
| Ingesta documental | AG-1 | Parsear, catalogar |
| Extracción estructurada | AG-2 | Texto → entidades |
| Evidencia y trazabilidad | AG-3 | Dato → fuente → nivel certeza |
| Cierre objeto + coherencia | AG-4 | Qué se evalúa / verificar entre bloques |
| Triaje normativo vivo | AG-5 | Encaje legal con consulta online |
| Cartógrafo SIG | AG-6 | Mapas temáticos con trazabilidad |
| Clima y riesgos | AG-7 | AEMET + climograma + riesgos |
| Inventario ambiental | AG-8 | Fichas probatorias por factor |
| Impactos, medidas, PVA | AG-9 | Cadena completa evaluación |
| Redactor técnico | AG-10 | Bloques A-K con datos cerrados |
| Ensamblador DOCX | M-11 | Maquetación profesional |
| Auditor final | M-12 | Última línea de defensa |

### 9 fases secuenciales con GATES

```
FASE 1: Ingesta ──→ GATE ──→ FASE 2: Cierre objeto ──→ GATE ──→
FASE 3: Triaje ──→ GATE ──→ FASE 4: Geodatos (paralelo) ──→ GATE ──→
FASE 5: Inventario ──→ GATE ──→ FASE 6: Impactos/PVA ──→ GATE ──→
FASE 7: Redacción ──→ GATE ──→ FASE 8: Ensamblaje ──→ GATE ──→
FASE 9: Auditoría ──→ CONFORME/NO CONFORME
```

### 6 capas de datos

1. `hechos_confirmados.json` — solo datos con prueba
2. `inferencias_y_gaps.json` — deducciones, pendientes, contradicciones
3. `normativa_aplicable.json` — registro vivo con fecha/hora consulta
4. `matriz_trazabilidad.json` — afirmación → origen → bloques donde aparece
5. `cartografia_trace.json` — request + bbox + CRS + hash por cada mapa
6. `salidas_generadas.json` — registro de todos los outputs

### Paquete de entrega

```
/expediente-EIA-[ID]/
├── DOCUMENTO_AMBIENTAL_[proyecto].docx    ← Entregable principal
├── PDF_FINAL_[proyecto].pdf               ← Versión PDF
├── anejos/                                ← Mapas, clima, impactos, PVA, fotos
├── control_interno/                       ← NO se entrega a administración
│   ├── hechos_confirmados.json
│   ├── inferencias_y_gaps.json
│   ├── normativa_aplicable.json
│   ├── matriz_trazabilidad.json
│   ├── cartografia_trace.json
│   ├── ficha_objeto_evaluado.md
│   ├── nota_encuadre_legal.md
│   ├── informe_coherencia.md
│   ├── informe_auditoria_final.md
│   └── log_orquestador.md
└── README_EXPEDIENTE.md
```

## Archivos operativos generados

| Archivo | Descripción |
|---------|-------------|
| `CLAUDE.md` | System prompt raíz para Claude Code |
| `schemas/eia_schemas_v21.json` | Schemas JSON de las 6 capas + ficha objeto |
| `init_expediente.sh` | Script de inicialización de carpetas |
| `EIA_AGENT_v21_ARQUITECTURA.md` | Este documento |

## Implementación recomendada

### Sprint 1 (semanas 1-2)
- Montar CLAUDE.md en Claude Code
- Crear schemas y validar con expediente RECIMETAL
- Implementar AG-1 → AG-2 → AG-3 (pipeline de ingesta)
- Probar: ¿extrae correctamente entidades de la Memoria de Explotación?

### Sprint 2 (semanas 3-4)
- Implementar AG-4 (cierre objeto) + AG-5 (triaje normativo)
- Probar GATE de Fase 2: ¿bloquea si falta compatibilidad urbanística?
- Probar consulta viva BOE/BOC

### Sprint 3 (semanas 5-6)
- Implementar AG-6 (cartógrafo) con Mapbox + 3-4 WMS
- Implementar AG-7 (clima) con AEMET OpenData
- Probar trazabilidad cartográfica completa

### Sprint 4 (semanas 7-8)
- Implementar AG-8 (inventario) + AG-9 (impactos)
- Probar cadena impacto → medida → PVA
- Validar con matrices reales de RECIMETAL

### Sprint 5 (semanas 9-10)
- Implementar AG-10 (redactor) con plantillas tipológicas
- Implementar M-11 (ensamblador DOCX)
- Implementar M-12 (auditor)
- Integración completa

### Sprint 6 (semanas 11-12)
- Test end-to-end con expediente RECIMETAL completo
- Comparar output con documento ya tramitado
- Ajuste fino y documentación
