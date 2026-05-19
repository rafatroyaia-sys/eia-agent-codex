# Validador de expedientes — EIA-Agent v2.1

## Uso básico

```bash
python tools/validate_expediente.py <ruta_expediente>

# Ejemplo con el piloto:
python tools/validate_expediente.py expediente-EIA-2026-RECIMETAL-PARCELA
```

Salida:
- `exit 0` — VÁLIDO (sin errores de modelo)
- `exit 1` — INVÁLIDO (errores encontrados)

## Requisitos

- Python 3.8 o superior
- Sin dependencias externas (solo librería estándar)

### Instalar Python en Windows

Si Python no está instalado:
1. Ir a https://www.python.org/downloads/
2. Descargar Python 3.11+ para Windows
3. En el instalador, marcar "Add Python to PATH"
4. Verificar: `python --version`

## Qué valida

### 1. Existencia de capas requeridas

Comprueba que el directorio `capas/` contiene los 6 archivos obligatorios:

| Archivo | Descripción |
|---------|-------------|
| `hechos_confirmados.json` | HCs del expediente |
| `inferencias_y_gaps.json` | GAPs, CONTs, INFs, CAUTELAS |
| `normativa_aplicable.json` | Marco normativo verificado |
| `matriz_trazabilidad.json` | Trazabilidad de datos clave |
| `cartografia_trace.json` | Registro de mapas generados |
| `salidas_generadas.json` | Inventario de outputs |

### 2. Validez del JSON

- Cada archivo es JSON válido
- El contenido raíz es un array (`[]`), no un objeto

### 3. Campos obligatorios por capa

| Capa | Campos requeridos | Prefijo ID |
|------|------------------|-----------|
| hechos_confirmados | id, categoria, campo, valor, estado, fuentes | `HC-` |
| inferencias_y_gaps | id, tipo, criticidad, campo | `CONT-`, `INF-`, `GAP-`, `PS-INF-`, `CAUTELA-` |
| normativa_aplicable | id, tipo, norma, estado | `NJ-` |
| matriz_trazabilidad | id, dato, valor, estado_evidencia, fuente_primaria | `TR-` |
| cartografia_trace | id, titulo, tipo_cartografia, archivo_resultado, estado | `CT-` |
| salidas_generadas | id, fase, agente, fecha, tipo, nombre_archivo, descripcion | `SG-` |

### 4. Valores permitidos (enums)

**estados de evidencia** (hechos_confirmados.estado, matriz_trazabilidad.estado_evidencia):
```
CONFIRMADO | DECLARADO | INFERIDO | ESTIMADO | PENDIENTE | DESCARTADO
```

**normativa_aplicable.tipo**:
```
ley_estatal | real_decreto | ley_autonomica_canarias |
decreto_autonomico_canarias | decreto_ley_autonomico_canarias
```

**normativa_aplicable.estado**:
```
VERIFICADA ONLINE | REFERENCIADA
```

**cartografia_trace.tipo_cartografia**:
```
GENERADO_AUTOMATICAMENTE | VERIFICACION_INTERNA
```

**cartografia_trace.estado**:
```
GENERADO | VERIFICADO | ERROR | PENDIENTE
```

### 5. IDs únicos

Detecta IDs duplicados dentro de cada capa.

### 6. Consistencia mínima entre capas

- `hechos_confirmados` no debe estar vacía
- `salidas_generadas` no debe estar vacía (al menos una fase ejecutada)
- `normativa_aplicable` debe tener al menos una norma con `VERIFICADA ONLINE`
- `cartografia_trace` debe tener al menos un mapa en estado `GENERADO` o `VERIFICADO`

### 7. GAPs de criticidad ALTA

Lista todos los items de `inferencias_y_gaps` de tipo `PENDIENTE` con criticidad `ALTA`. No son errores de modelo pero se muestran como avisos, ya que bloquean el gate en producción.

### 8. Ficha del objeto evaluado (OB-01)

Valida el contenido mínimo de `control_interno/ficha_objeto_evaluado.md`, generada por AG-4 al cierre de la Fase 2.

**Condición de skip**: si el archivo no existe, se emite un WARNING (la existencia física como requisito de fase ya la controla el gate, no el validador general).

**Patrón de búsqueda**: `re.search(patron, contenido, re.IGNORECASE)` sobre el texto completo del archivo. Sin parseo de lenguaje natural — solo presencia de términos clave en encabezados o cuerpo.

**Secciones críticas** (ausencia → **ERROR** bloqueante):

| Nombre | Patrón buscado | Tipo |
|--------|---------------|------|
| identificacion_del_proyecto | `##.*identificaci` o `##.*expediente` | encabezado |
| operaciones_incluidas | `##.*operac.*incluid` | encabezado |
| operaciones_excluidas | `##.*operac.*excluid` | encabezado |
| referencia_catastral_en_cuerpo | `referencia catastral` | cuerpo |
| coordenadas_en_cuerpo | `coordenadas` | cuerpo |
| superficie_evaluada_en_cuerpo | `superficie` | cuerpo |

**Secciones informativas** (ausencia → `WARNING` no bloqueante):

| Nombre | Patrón buscado |
|--------|---------------|
| promotor | `##.*promotor` |
| ubicacion_o_delimitacion | `##.*ubicaci` o `##.*delimitaci` |
| equipos_o_recursos_materiales | `##.*equipo` |
| dependencia_funcional | `##.*dependencia` |
| puntos_sensibles_o_pendientes | `##.*puntos.sensibles` o `##.*pendientes` |

**Umbral de tamaño**: mínimo 500 caracteres → ERROR si no se alcanza.

### 9. Coherencia HC ↔ TR (AU-03)

Verifica que cada `HC` con `estado = CONFIRMADO` tenga al menos una entrada de trazabilidad asociada en `matriz_trazabilidad`.

**Campo de enlace**: `hc_ids` (array de HC-IDs) en cada entrada TR. Es un campo opcional por retrocompatibilidad; si ningún TR lo declara, AU-03 emite un aviso global y no comprueba cobertura.

**Categorías excluidas** de la comprobación de cobertura:
- `tecnico_redactor` — identificación administrativa del equipo redactor; no es dato material del expediente.

**Tipos de resultado:**

| Caso | Resultado |
|------|-----------|
| `hc_ids` contiene un ID que no existe en `hechos_confirmados` | **ERROR** (referencia colgante — bloqueante) |
| `hc_ids` no es un array | **ERROR** (tipo incorrecto — bloqueante) |
| HC CONFIRMADO sin cobertura en ningún TR | `WARNING` (no bloqueante) |
| Ningún TR tiene el campo `hc_ids` | `WARNING` (no bloqueante — campo no poblado) |

AU-03 produce **warnings, no errores**, para la cobertura incompleta. La razón: el campo `hc_ids` es nuevo y los expedientes en curso pueden no tenerlo completamente poblado. Los errores de integridad referencial (IDs colgantes) sí bloquean siempre.

### 9. Existencia física de archivos (EN-02)

Comprueba que los archivos referenciados en las capas existen en disco. Rutas relativas al directorio raíz del expediente.

**`cartografia_trace.json` — campo `archivo_resultado`:**

| Condición | Resultado |
|-----------|-----------|
| `archivo_resultado` empieza por `N/A` | Ignorado (declarado sin archivo) |
| `tipo_cartografia = VERIFICACION_INTERNA` | Ignorado (no produce archivo físico) |
| `estado = GENERADO` o `VERIFICADO` y archivo ausente | **ERROR** (bloqueante) |
| `estado = ERROR` o `PENDIENTE` y archivo ausente | `WARNING` (no bloqueante) |

**`salidas_generadas.json` — campo `nombre_archivo`:**

| Condición | Resultado |
|-----------|-----------|
| Archivo no existe en disco | **ERROR** (bloqueante) |

Todas las entradas de `salidas_generadas` representan salidas ya producidas, por lo que la ausencia de archivo es siempre un error de modelo.

## Qué NO valida todavía

| Aspecto | Razón / Ítem backlog |
|---------|---------------------|
| Formato de coordenadas (WGS84 válido, UTM en rango) | A añadir en P1 cuando ficha_objeto sea JSON |
| Coherencia HC ↔ TR (todo HC relevante debe tener TR) | Backlog AU-03 |
| Coherencia TR ↔ bloques (todo TR debe aparecer en al menos un bloque) | Backlog AU-05 |
| Regla de prudencia (frases como "no existe" sin estado INFERIDO) | Backlog AU-02 — requiere procesado de texto de los bloques |
| Validación de tabla LER (códigos de 6 dígitos, fracciones válidas) | Añadir en próxima iteración |
| Presencia de `ficha_objeto_evaluado.md` con secciones mínimas | Backlog OB-01 — cuando ficha sea JSON |
| Validación de fechas (formato ISO, coherencia temporal) | A añadir |
| Checklist art.45 + Anexo VI programático | Backlog AU-01 |

## Salida de ejemplo (piloto Recimetal)

```
======================================================================
EIA-Agent v2.1 -- Validador de expediente
Expediente : C:\...\expediente-EIA-2026-RECIMETAL-PARCELA
======================================================================

--------------------------------------------------
1. EXISTENCIA DEL EXPEDIENTE Y CAPAS
--------------------------------------------------
  OK  hechos_confirmados.json
  OK  inferencias_y_gaps.json
  OK  normativa_aplicable.json
  OK  matriz_trazabilidad.json
  OK  cartografia_trace.json
  OK  salidas_generadas.json

--------------------------------------------------
2. VALIDEZ DEL JSON
--------------------------------------------------
  OK  hechos_confirmados.json     (37 registros)
  OK  inferencias_y_gaps.json     (17 registros)
  OK  normativa_aplicable.json    (10 registros)
  OK  matriz_trazabilidad.json    (N  registros)
  OK  cartografia_trace.json      (9  registros)
  OK  salidas_generadas.json      (35 registros)

--------------------------------------------------
3. CAMPOS, TIPOS Y VALORES PERMITIDOS
--------------------------------------------------
  hechos_confirmados    :  37 registros  0 errores
  inferencias_y_gaps    :  24 registros  0 errores
  normativa_aplicable   :  10 registros  0 errores
  matriz_trazabilidad   :  25 registros  0 errores
  cartografia_trace     :   9 registros  0 errores
  salidas_generadas     :  35 registros  0 errores

--------------------------------------------------
4. CONSISTENCIA ENTRE CAPAS
--------------------------------------------------
  AVISO: 1 GAP(s) de criticidad ALTA abiertos:
    - GAP-002  anejo_tecnico_drenaje_superficial

--------------------------------------------------
5. EXISTENCIA FISICA DE ARCHIVOS
--------------------------------------------------
  OK  Todos los archivos referenciados existen en disco

======================================================================
RESULTADO FINAL
======================================================================

  RESULTADO: VALIDO
  Registros validados: 140 | Advertencias: 0
```

## Integración en gates

El validador devuelve exit code 1 si hay errores de modelo. Puede usarse como gate automático al inicio de cada fase:

```bash
# En el orquestador, antes de ejecutar cada fase:
python tools/validate_expediente.py $EXPEDIENTE_PATH
if [ $? -ne 0 ]; then
    echo "Gate bloqueado: el modelo de datos tiene errores"
    exit 1
fi
```

## Relación con el schema

Los schemas formales están en `schemas/eia_schemas_v21.json`. El validador no los importa directamente (no requiere `jsonschema`), pero implementa la misma lógica de validación. En P2 se planea unificarlos añadiendo soporte opcional a `jsonschema`.
