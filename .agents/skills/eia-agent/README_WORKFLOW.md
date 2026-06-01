# Flujo operativo — EIA-Agent

## Pasos en orden

### 1. Identificar el expediente

```
expediente-EIA-[AÑO]-[PROMOTOR]-[REFERENCIA]/
```

Confirmar que existe la estructura mínima de carpetas (inputs/, capas/, control_interno/).
Si no existe, el expediente no ha sido inicializado → `/nuevo-expediente [ID]`.

---

### 2. Leer estado actual

```bash
python run_expediente.py <expediente> status
```

Devuelve:
- Fase actual del orquestador
- Estado de cada fase (PENDING / IN_PROGRESS / COMPLETED / BLOCKED / FAILED)
- Si hay gate bloqueado
- Ruta al log

**Interpretar:**
- `COMPLETED` en todas → listo para siguiente fase o auditoría
- `BLOCKED` en alguna → hay un gate sin pasar, leer qué falta
- `IN_PROGRESS` sin avanzar → sesión interrumpida, ir al paso 5

---

### 3. Validar schemas

```bash
python run_expediente.py <expediente> validate
```

Valida los 7 schemas JSON de capas (NL-01). Si falla:
- identificar el schema que falla
- revisar el archivo JSON correspondiente
- corregir datos o regenerar desde el módulo correspondiente

**Nunca avanzar de fase con un schema inválido.**

---

### 4. Evaluar gate de la fase actual

```bash
python run_expediente.py <expediente> gate <N>
# Modo test (por defecto, acepta AT activas)
python run_expediente.py <expediente> gate <N> --prod
# Modo producción (más estricto)
```

Gates críticos:
- Gate 2 → cierre del objeto evaluado (OB-01 + OB-02)
- Gate 4 → cartografía + clima completa
- Gate 7 → redacción cerrada (todos los bloques A–K)
- Gate 9 → auditoría CONFORME

Si el gate no pasa:
- leer qué campo o artefacto falta
- no avanzar hasta resolverlo

---

### 5. Recovery (si sesión interrumpida)

```bash
python run_expediente.py <expediente> recover
python run_expediente.py <expediente> recover --write-report
```

Devuelve diagnóstico de inconsistencias: fases IN_PROGRESS sin completar,
discrepancias entre log y estado, archivos faltantes.
`--write-report` genera `control_interno/recovery_report.json`.

---

### 6. Revisar log histórico

```bash
python run_expediente.py <expediente> log-summary
```

Devuelve resumen de eventos: qué se ejecutó, en qué orden, con qué resultado.
Útil para entender por qué el expediente está en el estado actual.

---

### 7. Resumir situación y decidir

Con la información de los pasos anteriores:

1. Completar `PLANTILLA_RESUMEN_ESTADO_EXPEDIENTE.md`
2. Identificar bloqueos y pendientes
3. Decidir:
   - **seguir con la fase actual** (resolver bloqueos)
   - **pedir documentación al promotor** (`PLANTILLA_SOLICITUD_PENDIENTES_PROMOTOR.md`)
   - **avanzar a la siguiente fase** (gate pasado, sin pendientes críticos)
   - **parar y escalar** (gap ALTA sin datos disponibles)

---

## Señales de alerta durante el flujo

| Señal | Acción |
|-------|--------|
| Schema inválido | Corregir antes de cualquier otra cosa |
| AT activa + gate --prod | No avanzar administrativamente |
| Gap ALTA abierto | Pedir dato al promotor o activar AT explícita |
| CONT sin resolver | No cerrar el objeto evaluado |
| Modo NO_DECLARADO | Pedir declaración de modo al usuario |
| Cartografía PROVISIONAL | No pasar gate 4 en modo producción |
| Auditoría CON OBSERVACIONES | Resolver antes de ensamblar DOCX final |
