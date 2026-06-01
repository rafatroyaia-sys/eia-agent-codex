# Comandos operativos — run_expediente.py

Todos los comandos son de **solo lectura** salvo `recover --write-report`.
Ninguno modifica datos del expediente ni ejecuta agentes reales.

---

## Sintaxis general

```bash
python run_expediente.py <ruta-al-expediente> <COMANDO> [opciones]
```

La ruta puede ser relativa o absoluta:
```bash
python run_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA status
python run_expediente.py ../otro-expediente status
```

---

## status

Muestra el estado actual del orquestador: fases, gates, última actividad.

```bash
python run_expediente.py <expediente> status
```

**Cuándo usarlo**: siempre al inicio de una sesión de trabajo con un expediente.

**Qué devuelve**:
- Estado de cada fase (PENDING / IN_PROGRESS / COMPLETED / BLOCKED / FAILED)
- Fase activa
- Si hay gate bloqueado y en qué fase
- Ruta al log del orquestador

**Interpretar**:
```
Fase 1 COMPLETED  → ingesta terminada
Fase 2 BLOCKED    → gate 2 no pasado, hay pendientes críticos
Fase 3 PENDING    → no iniciada aún
```

---

## validate

Valida los 7 schemas JSON de las capas del expediente.

```bash
python run_expediente.py <expediente> validate
```

**Cuándo usarlo**: antes de evaluar cualquier gate, y tras modificar archivos JSON.

**Qué devuelve**:
- Lista de schemas validados con resultado (OK / ERROR)
- Errores de validación con path y mensaje concreto

**Interpretar**:
```
hechos_clave.json           OK
inferencias_y_gaps.json     ERROR — campo 'criticidad' esperado, encontrado 'severity'
```

**Si hay ERROR**: corregir el JSON antes de continuar. No saltarse este paso.

---

## gate

Evalúa el gate de una fase específica.

```bash
# Modo test (por defecto) — acepta AT activas, más permisivo
python run_expediente.py <expediente> gate <N>

# Modo producción — equivalente al estándar administrativo real
python run_expediente.py <expediente> gate <N> --prod
```

**Valores de N** (1–9, según fases del sistema):
- `gate 2` → cierre del objeto evaluado
- `gate 3` → encuadre normativo
- `gate 4` → cartografía + clima
- `gate 5` → inventario ambiental
- `gate 6` → impactos + medidas + PVA
- `gate 7` → redacción completa
- `gate 9` → auditoría CONFORME

**Cuándo usarlo**: antes de declarar una fase como completa y pasar a la siguiente.

**Qué devuelve**:
- ABIERTO / BLOQUEADO
- Lista de campos o artefactos que impiden el paso
- Severidad de cada incidencia (ERROR / WARNING / INFO)

**Ejemplo de salida**:
```
Gate 2 [TEST] — expediente-EIA-2026-RECIMETAL-PARCELA: APTO
  Errores: 0 | Avisos: 1 | Info: 2
  [INFO] [modo] OB02-I002: Modo GABINETE — solo fuentes documentales.
  [WARNING] [at_activos] OB02-W004: 1 asunción de test activa.
```

**Diferencia test vs --prod**:
- Test: AT activas → WARNING (no bloquea)
- --prod: AT activas → ERROR (bloquea)

---

## recover

Diagnostica sesiones interrumpidas o inconsistencias entre estado y log.

```bash
# Solo lectura — diagnóstico sin escribir
python run_expediente.py <expediente> recover

# Genera recovery_report.json en control_interno/
python run_expediente.py <expediente> recover --write-report
```

**Cuándo usarlo**: cuando el `status` muestra fases IN_PROGRESS que no avanzan,
o tras una sesión interrumpida inesperadamente.

**Qué devuelve**:
- Fases IN_PROGRESS sin completar
- Discrepancias entre estado del orquestador y log de eventos
- Archivos esperados que no existen
- Recomendaciones de acción

**Nota**: `--write-report` es la única operación de escritura del CLI.
El archivo escrito es solo en `control_interno/`, no toca datos del expediente.

---

## log-summary

Resume el historial de eventos del orquestador.

```bash
python run_expediente.py <expediente> log-summary
```

**Cuándo usarlo**: para entender qué pasó antes en el expediente, en qué orden
se ejecutaron las fases, y qué eventos quedaron registrados.

**Qué devuelve**:
- Lista cronológica de eventos (tipo, fase, estado, timestamp)
- Última actividad registrada
- Si el log está corrupto o truncado

---

## Casos de uso combinados

**Diagnóstico inicial completo**:
```bash
python run_expediente.py <expediente> status
python run_expediente.py <expediente> validate
python run_expediente.py <expediente> gate 2
```

**Revisar por qué está bloqueada la fase 3**:
```bash
python run_expediente.py <expediente> gate 3
python run_expediente.py <expediente> log-summary
```

**Tras sesión interrumpida**:
```bash
python run_expediente.py <expediente> recover
python run_expediente.py <expediente> status
```

**Preparar para presentación (modo producción)**:
```bash
python run_expediente.py <expediente> validate
python run_expediente.py <expediente> gate 2 --prod
python run_expediente.py <expediente> gate 7 --prod
python run_expediente.py <expediente> gate 9 --prod
```
