# PHASE4_PRECHECK — CA-08

Precheck programático de Fase 4. Evalúa si un expediente tiene los datos mínimos
para poder ejecutar cartografía y clima en una fase posterior.

**No genera mapas. No genera climogramas. No llama a APIs externas.**
**No usa WMS/WMTS. No usa web. No usa IA.**
Solo comprueba preparación, riesgos y bloqueos.

## Módulo

`src/eia_agent/core/phase4_precheck.py`

## Relación con módulos anteriores

```
phase2_result.json  ←── run_phase2() (OB-06)    [REQUERIDO para datos completos]
        │
phase3_result.json  ←── run_phase3() (TN-05)    [OPCIONAL — solo informativo]
        │
        ▼
_check_coordinates()      ← coordenadas WGS84 + UTM
_check_rc()               ← referencia catastral
_check_api_keys_issues()  ← AEMET_API_KEY + MAPBOX_TOKEN (solo warnings)
_check_phase3_available() ← triaje normativo disponible (solo INFO)
        │
        ▼
Phase4PrecheckResult
```

## Qué hace el precheck de Fase 4

El precheck evalúa los requisitos previos para ejecutar cartografía y clima:

1. **Coordenadas geográficas** — verifica presencia, formato y fiabilidad de las
   coordenadas WGS84 y/o UTM del ObjectScope.
2. **Referencia catastral** — verifica presencia y formato de la RC (20 chars).
3. **Variables de entorno API** — comprueba si AEMET_API_KEY y MAPBOX_TOKEN están
   configuradas. **No las valida ni las usa.** Solo informa si están ausentes.
4. **Triaje normativo** — verifica si `phase3_result.json` está disponible para
   enriquecer las fichas de inventario ambiental. Solo informativo.
5. **Estado de preparación** — calcula `ready_for_cartography`, `ready_for_climate`
   y `ready_for_phase4` según las reglas descritas más abajo.

## Qué NO hace el precheck

- No genera ningún mapa (ni PNG, ni GeoJSON, ni WMS).
- No genera climogramas ni tablas de normales climáticas.
- No llama a AEMET, Catastro, Mapbox ni ningún servicio externo.
- No valida coordenadas contra el terreno real.
- No verifica la RC contra la sede electrónica del Catastro.
- No inicia Fase 5 (inventario ambiental).
- No escribe automáticamente (requiere `write_outputs=True`).

## Diferencia entre precheck y generación real

| Aspecto | Precheck (CA-08) | Generación real (CA-01…CA-07, CL-01…CL-05) |
|---------|-----------------|---------------------------------------------|
| Llama a APIs | No | Sí (AEMET, WMS, Catastro) |
| Genera archivos | Solo si `write_outputs=True` | Siempre |
| Requiere internet | No | Sí |
| Propósito | Verificar preparación | Generar cartografía/clima |
| Bloquea fase | Sí, si error_count > 0 | No aplica |

## Requisitos mínimos para cartografía

| Requisito | Nivel si falta | Bloquea `ready_for_cartography` |
|-----------|---------------|--------------------------------|
| Coordenadas WGS84 o UTM | ERROR (P4-E001) | Sí |
| Referencia catastral presente | WARNING (P4-W003) | No |
| Referencia catastral formato válido | ERROR (P4-E002) | No — pero bloquea `ready_for_phase4` |
| MAPBOX_TOKEN | WARNING (P4-W005) | No |
| phase2_result.json presente | ERROR (P4-E005) | Sí (indirectamente) |

Mapas mínimos requeridos: 6 (MAP-001 a MAP-006):
- MAP-001 situación general
- MAP-002 emplazamiento
- MAP-003 parcela/catastro
- MAP-004 Red Natura / ENP
- MAP-005 usos del suelo
- MAP-006 inundabilidad / riesgos físicos

## Requisitos mínimos para clima

| Requisito | Nivel si falta | Bloquea `ready_for_climate` |
|-----------|---------------|----------------------------|
| Coordenadas (para localizar estación) | ERROR (P4-E001) | Sí |
| AEMET_API_KEY | WARNING (P4-W004) | No |

Salidas climáticas requeridas (5):
- estación climática de referencia
- tabla climática mensual
- climograma
- clasificación Köppen
- riesgos climáticos relevantes

## Papel de AEMET_API_KEY y MAPBOX_TOKEN

Ambas claves producen solo **WARNING** cuando están ausentes:

**AEMET_API_KEY** — permite la descarga automática de normales climatológicas.
Sin ella, los datos climáticos deben introducirse manualmente o usarse una fuente
climática documentada (publicaciones AEMET, atlas climático). El expediente no
queda bloqueado: los datos pueden proceder de una fuente manual con trazabilidad.

**MAPBOX_TOKEN** — permite usar tiles de mapa de fondo de alta calidad.
Sin ella, se usan servicios WMS/WMTS oficiales y públicos: GRAFCAN, MITECO,
IDECanarias, Catastro. Todos gratuitos para uso administrativo y técnicamente
equivalentes para la generación de mapas EIA.

## Por qué no se bloquea por falta de token

El principio del sistema es: **si existe una alternativa técnica válida, no se
bloquea**. Los servicios WMS/WMTS oficiales son fuentes válidas y verificables.
La ausencia de un token de conveniencia no impide la ejecución técnica de la
cartografía. Solo añade un WARNING para que el técnico tome una decisión informada.

## Reglas de precheck

### Coordenadas

| Condición | Código | Severidad | Efecto en `ready_for_cartography` |
|-----------|--------|-----------|----------------------------------|
| Sin WGS84 ni UTM | P4-E001 | ERROR | False |
| Contiene PENDIENTE/ESTIMADO/NO_DECLARADO/PROVISIONAL | P4-W001 | WARNING | No bloquea (has_location=True) |
| Formato WGS84 no reconocido | P4-W002 | WARNING | No bloquea |

### Referencia catastral

| Condición | Código | Severidad |
|-----------|--------|-----------|
| RC ausente o vacía | P4-W003 | WARNING |
| RC con formato inválido | P4-E002 | ERROR |

### Variables de entorno

| Condición | Código | Severidad |
|-----------|--------|-----------|
| AEMET_API_KEY ausente | P4-W004 | WARNING |
| MAPBOX_TOKEN ausente | P4-W005 | WARNING |

### Datos fuente

| Condición | Código | Severidad |
|-----------|--------|-----------|
| phase2_result.json no encontrado | P4-E005 | ERROR |
| phase2_result.json con JSON inválido | P4-E004 | ERROR |
| phase3_result.json no encontrado | P4-I001 | INFO |

### `ready_for_phase4`

`ready_for_phase4 = True` solo si:
- `ready_for_cartography = True`
- `ready_for_climate = True`
- `error_count() == 0`

Los WARNINGs e INFOs no bloquean en modo test, pero deben resolverse antes de
la presentación administrativa del Documento Ambiental.

## API pública

```python
from eia_agent.core.phase4_precheck import run_phase4_precheck

result = run_phase4_precheck("expediente-EIA-2026-RECIMETAL-PARCELA")
print(result.summary())

result = run_phase4_precheck(
    "expediente-EIA-2026-RECIMETAL-PARCELA",
    write_outputs=True,
)
```

### run_phase4_precheck

```python
def run_phase4_precheck(
    expediente_path: str | Path,
    phase2_result_path: str | Path | None = None,
    phase3_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase4PrecheckResult
```

- `phase2_result_path`: ruta explícita o None (busca en `control_interno/`). Si no
  existe, añade ERROR P4-E005 y continúa con ObjectScope vacío.
- `phase3_result_path`: ruta explícita o None. Solo comprobación informativa.
- `write_outputs=False`: por defecto no escribe nada.

### Phase4PrecheckResult

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `expediente_id` | str | Nombre del directorio del expediente |
| `ready_for_cartography` | bool | True si hay coordenadas sin errores de coords |
| `ready_for_climate` | bool | True si hay coordenadas (misma condición) |
| `ready_for_phase4` | bool | True si ambas ready + error_count == 0 |
| `coordinates_status` | str | OK / WARNING / ABSENT |
| `rc_status` | str | OK / ABSENT / INVALID |
| `api_keys_status` | dict | {"AEMET_API_KEY": bool, "MAPBOX_TOKEN": bool} |
| `required_maps` | list[str] | Los 6 mapas mínimos requeridos |
| `required_climate_outputs` | list[str] | Las 5 salidas climáticas requeridas |
| `issues` | list[Phase4PrecheckIssue] | Todos los issues con severity/code/message |
| `warnings` | list[str] | Avisos propagados de fases anteriores |
| `notes` | list[str] | Notas operativas |

Métodos: `error_count() -> int`, `warning_count() -> int`, `info_count() -> int`,
`summary() -> str`, `to_dict() -> dict`.

## Escritura de outputs

Con `write_outputs=True` escribe en `output_dir/` (default `control_interno/`):
- `phase4_precheck.json` — resultado completo serializado
- `phase4_precheck.md` — informe en Markdown

Nunca modifica `inputs/`. Nunca escribe en expedientes piloto durante tests.

## CLI

```bash
# Solo lectura (no escribe nada)
python run_expediente.py <expediente> phase4-precheck

# Con escritura de outputs
python run_expediente.py <expediente> phase4-precheck --write
```

Exit code: 0 si `error_count() == 0`, 1 si hay errores.

**Flujo típico completo:**
```bash
python run_expediente.py <exp> phase1 --write
python run_expediente.py <exp> phase2 --write
python run_expediente.py <exp> phase3 --write
python run_expediente.py <exp> phase4-precheck
```

## Limitaciones conocidas

1. **Requiere phase2 para datos completos**: sin `phase2_result.json`, solo puede
   reportar P4-E005 y los checks de API keys. No evalúa coordenadas ni RC.
2. **No valida coordenadas geográficamente**: no comprueba que las coords estén en
   el territorio declarado, solo que el formato sea correcto.
3. **No verifica RC contra Catastro**: solo comprueba el formato de 20 caracteres.
   Una RC con formato válido puede no existir en el Catastro.
4. **No determina bbox automáticamente**: requiere CA-01/CA-02 para obtener el
   bounding box a partir de las coordenadas y generar los mapas.
5. **API keys solo presencia**: no prueba que AEMET_API_KEY sea válida consultando
   el servicio. Una key presente pero inválida solo se detectará en CA-01+CL-01.
6. **No inicia Fase 4 real**: el precheck solo evalúa preparación. La generación
   de cartografía (CA-01…CA-05) y clima (CL-01…CL-05) es un hito separado.

## Tests

`tests/test_phase4_precheck.py` — 113 tests, 14 clases.

Cobertura:
- `Phase4PrecheckIssue`: campos, `to_dict()`, opcionales None
- `Phase4PrecheckResult`: `error_count()`, `warning_count()`, `info_count()`,
  `summary()`, `to_dict()`, JSON serializable
- `_parse_wgs84_coord`, `_looks_like_rc`: casos válidos e inválidos
- `_check_coordinates`: sin coords → ABSENT+ERROR; WGS84 → OK; UTM → OK;
  PENDIENTE/ESTIMADO → WARNING; formato inválido → WARNING; None tratado como vacío
- `_check_rc`: válida → OK; ausente → ABSENT+WARNING; inválida → INVALID+ERROR
- `_check_api_keys`: presente/ausente/empty; WARNINGs no ERRORs
- `run_phase4_precheck` sin phase2: P4-E005, ready=False, status ABSENT
- `run_phase4_precheck` sin coords: P4-E001, ready_for_cartography=False
- `run_phase4_precheck` con WGS84: ready_for_cartography=True, status OK
- `run_phase4_precheck` con UTM: ready_for_cartography=True
- Coordenadas no fiables: WARNING, has_location=True
- RC check: ausente/inválida/válida
- API keys: absent → WARNING (no ERROR); present → sin warning
- API absent no bloquea cartografía ni clima
- Fase 3 ausente → P4-I001 (INFO); presente → sin P4-I001
- `ready_for_phase4`: true cuando no hay errores; false con errores; warnings no bloquean
- write_outputs: no escribe por defecto; crea JSON+MD; dir personalizado; JSON completo
- propagación warnings de phase2; JSON inválido → P4-E004
- CLI: sin phase2 → exit 1; sin --write → no crea; con --write → crea; con phase2 válido → exit 0
- Pilots PARCELA/NAVE-222: usando tempfiles, sin modificar piloto
