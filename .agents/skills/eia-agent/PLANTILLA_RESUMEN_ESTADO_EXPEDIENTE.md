# Plantilla: Resumen ejecutivo de expediente

## Instrucciones

Rellenar todos los campos. Si un campo no ha sido evaluado, escribir
"NO EVALUADO" (nunca dejar en blanco). Este resumen es interno — no va al DA.
Actualizar cada vez que se complete una fase o se resuelva un bloqueo.

---

```
═══════════════════════════════════════════════════════════════
RESUMEN EJECUTIVO — EXPEDIENTE EIA
Fecha: [FECHA]
Elaborado por: [NOMBRE TÉCNICO]
═══════════════════════════════════════════════════════════════

IDENTIFICACIÓN
  Expediente:         [ID del expediente]
  Promotor/Titular:   [Nombre oficial o PENDIENTE]
  Proyecto:           [Descripción breve]
  Tipo de proyecto:   [R12/R13 gestión residuos / cantera / industria / ...]
  Tipología EIA:      [Evaluación simplificada / ordinaria / exclusión]
  CCAA:               [Canarias / Andalucía / ...]
  Órgano ambiental:   [CAARUP-Canarias / Subdirección de EIA MITECO / ...]

───────────────────────────────────────────────────────────────

MODO DEL EXPEDIENTE
  ⚠️  MODO TEST   /   ✅ EXPEDIENTE REAL   ←   [marcar uno]
  Asunciones de test activas (AT):  [SÍ — listar / NO]
  Apto para presentación:           [SÍ / NO — justificar si NO]

───────────────────────────────────────────────────────────────

FASE ACTUAL
  Fase completada:    Fase [N] — [nombre]
  Fase en curso:      Fase [N+1] — [nombre]
  Gate actual:        Gate [N] — [ABIERTO / BLOQUEADO / PENDIENTE]
  Causa del bloqueo:  [si aplica]

───────────────────────────────────────────────────────────────

ESTADO DEL OBJETO EVALUADO (Gate 2)
  Titular:            [Nombre / PENDIENTE / DECLARADO sin verificar]
  RC:                 [RC / PENDIENTE / no verificada]
  Coordenadas WGS84:  [presentes / PENDIENTE / ESTIMADO]
  Coordenadas UTM:    [presentes / PENDIENTE / ESTIMADO]
  Modo:               [GABINETE / CAMPO / NO_DECLARADO]
  Operaciones incl.:  [lista breve / "ninguna declarada"]
  Operaciones excl.:  [lista breve / "ninguna"]
  estado_gate2:       [APTO / PENDIENTE / BLOQUEADO]
  Gate 2 (--prod):    [pasa / NO PASA — razón]

───────────────────────────────────────────────────────────────

BLOQUEOS ACTIVOS
  [Si no hay bloqueos, escribir "NINGUNO"]

  1. [Descripción del bloqueo] — Criticidad: [ALTA/MEDIA] — Fase afectada: [N]
  2. ...

───────────────────────────────────────────────────────────────

GAPS ABIERTOS DE CRITICIDAD ALTA
  [Si no hay, escribir "NINGUNO"]

  - [GAP-XXX]: [descripción breve] — Afecta a: [campo/bloque]
  - [CONT-XXX]: [descripción breve] — Estado: ABIERTO

───────────────────────────────────────────────────────────────

CAUTELAS ACTIVAS
  [Cautelas operativas que condicionan el avance]

  - [CAUTELA-XXX]: [descripción breve]

───────────────────────────────────────────────────────────────

PENDIENTES CRÍTICOS (necesitan acción del promotor)
  [Si no hay, escribir "NINGUNO"]

  1. [Documento o dato pendiente] — Criticidad: ALTA — Bloquea: [gate/fase]
  2. [Documento o dato pendiente] — Criticidad: MEDIA — Puede continuar con AT

───────────────────────────────────────────────────────────────

ESTADO POR FASE
  Fase 1 — Ingesta:       [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 2 — Objeto:        [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 3 — Normativa:     [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 4 — Geodatos:      [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 5 — Inventario:    [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 6 — Impactos/PVA:  [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 7 — Redacción:     [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 8 — Ensamblaje:    [COMPLETADO / EN CURSO / PENDIENTE / BLOQUEADO]
  Fase 9 — Auditoría:     [CONFORME / CON OBSERVACIONES / NO CONFORME / PENDIENTE]

───────────────────────────────────────────────────────────────

PRÓXIMO PASO RECOMENDADO
  [Acción concreta: resolver bloqueo X / pedir dato Y al promotor /
   iniciar fase N / ejecutar gate N / revisar CONT-XXX / ...]

───────────────────────────────────────────────────────────────

NOTAS
  [Cualquier observación relevante no capturada en los campos anteriores]

═══════════════════════════════════════════════════════════════
```
