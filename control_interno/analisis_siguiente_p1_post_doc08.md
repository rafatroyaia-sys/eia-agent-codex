# Análisis del siguiente ítem P1 pendiente — post DOC-08/QA-09

**Fecha:** 2026-05-28  
**Autor:** EIA-Agent v2.1 (sesión de análisis)  
**Baseline:** Suite 6214 OK, 12 skipped — git status limpio (verificado 2026-05-28)  
**Sesión previa cerrada con:** QA-09 SUPERADO (commit `25f8c80`), DOC-08 validado sobre NAVE-222

---

## 1. Verificación del entorno

| Check | Resultado |
|-------|-----------|
| `git status --short` | Limpio (sin cambios) |
| Suite tests (último dato conocido) | 6214 OK, 12 skipped — sin cambios de código desde QA-09 |
| Rama activa | master |
| Último commit | `25f8c80` QA-09: prueba preparacion para revision y firmas |

---

## 2. Inventario de ítems P1 pendientes

### 2.1 Ítems con código pendiente (prioridad alta)

| ID | Nombre | Descripción corta | Estado prompt | Estado código | Deps satisfechas |
|----|--------|-------------------|---------------|---------------|------------------|
| **IM-07** | Cadenas condicionales | Detecta CONTs en gaps → propaga CONDICIONADO a impactos, medidas y PVA | ✅ PROMPT | ❌ CÓDIGO | Sí: IM-01 ✅, OB-05 ✅, NL-01 ✅, NL-02 ✅ |
| **RD-07** | Cross-ref gap ALTA positivo | Verifica que impactos positivos con gap ALTA tienen nota de incertidumbre en bloque C | ✅ PROMPT | ❌ CÓDIGO | Sí: NL-02 ✅, IM-01 ✅ |

### 2.2 Ítems de infraestructura/config pendientes

| ID | Nombre | Descripción corta | Estado | Deps |
|----|--------|-------------------|--------|------|
| **BE-03** | Estructura carpetas código | `crear_expediente(ID)` formalizado como función Python (actualmente manual) | PARCIAL (manual) | Ninguna |
| **BE-04** | API key segura | AEMET API key via `.env` / `python-dotenv`, no hardcoded | PARCIAL | INST-01 ✅ |
| **EN-02** | Tabla posicionamiento bloques | Config JSON para qué bloques van al cuerpo/anejos del DOCX | Manual | EN-01 ✅ |
| **EN-04** | Eliminar numbering.xml huérfano | Elimina `rId3` a `numbering.xml` en DOCX — advertencia Word | Bug documentado (OBS-004) | EN-01 ✅ |

### 2.3 Ítems WMS/online condicionales (offline ya cubierto)

| ID | Nombre | Estado | Nota |
|----|--------|--------|------|
| CA-01 | wms_services.json | No estructurado | Offline cubierto por CA-09/CA-10/CA-11 ✅ |
| CA-02 | Cliente WMS | Funcional frágil | Offline cubierto |
| CA-03 | 8 mapas mínimos | Funcional en piloto | Offline cubierto |
| CA-04 | cartografia_trace.json | Funcional en piloto | Offline cubierto |
| CA-05 | canarias.json | Implícito | Offline cubierto |
| TN-01 | Consulta normativa online | Manual | Offline TN-05 ✅ |
| TN-02 | normativa_base.json | En CLAUDE.md | Referenciado en fase3 |
| TN-03 | Template nota encuadre | Funcional piloto | TN-05 ✅ ya genera |

> Nota: los ítems CA-01..CA-05 y TN-01..TN-03 corresponden a la capa online/WMS del sistema. Sus equivalentes offline (CA-09, CA-10, CA-11, CL-06, TN-05) están todos completados y validados. Estos ítems forman parte de P1 pero no son bloqueantes mientras no se inicie producción con datos en tiempo real.

---

## 3. Incoherencias detectadas entre ficheros de control

| ID | Fichero | Incoherencia | Acción recomendada |
|----|---------|-------------|-------------------|
| **INC-01** | `matriz_maestra_items_productizacion.md`, GRUPO 9 línea CL-05 | Dice "❌ No resuelto" como entrada secundaria en GRUPO 9 (Ensamblador), pero GRUPO 6 registra CL-05 como ✅ COMPLETADO 2026-04-26. | No es un bug nuevo — la entrada de GRUPO 9 es una referencia cruzada que no se actualizó. CL-05 está correctamente completado. Actualizar si se edita la matriz. |
| **INC-02** | `matriz_maestra_items_productizacion.md`, tabla P2 línea IM-07 | La tabla de ítems P2 lista "IM-07 (PVA genérico Compatible)" — mismo ID que el IM-07 P1 (cadenas condicionales). | Colisión de IDs resuelta en práctica: el P1 IM-07 (cadenas condicionales) es el canónico. Si se implementa P2, ese ítem deberá recibir un ID distinto (IM-09 o similar). Sin acción inmediata. |
| **INC-03** | `backlog_productizacion.md`, tabla semana 9 | IM-06 aparece como "código: template C.5 en IM-01" — pero fue absorbido en IM-08 (COMPLETADO 2026-05-12). La entrada de semana 9 no refleja esto. | La entrada del roadmap es la canónica y dice IM-08 COMPLETADO. El backlog tiene la nota en la fila IM-06. No es bloqueante. |

---

## 4. Selección del siguiente ítem recomendado

### Candidatos finales

| ID | Valor técnico | Urgencia | Complejidad | Bloquea a |
|----|--------------|----------|-------------|-----------|
| **IM-07** | ALTO — cierra el último gap del pipeline IM | ALTA — NAVE-222 tiene AT-001/CONT activo | MEDIA | Segundo expediente real con CONTs; RD-07 indirectamente |
| **RD-07** | MEDIO — auditoría de impactos positivos | MEDIA | BAJA | Nada bloqueante |
| **BE-03** | BAJO-MEDIO — formaliza función de creación | BAJA | BAJA | Producción limpia |

### Justificación de la elección: **IM-07**

**Razón principal:** IM-07 es el único ítem del pipeline IM con código pendiente. Los módulos IM-00 a IM-08 están todos implementados y validados, pero IM-07 (cadenas condicionales) sólo tiene el componente prompt. Es la pieza que falta para que el pipeline Fase 6 sea completo en cuanto a propagación de condicionantes.

**Razón operativa:** NAVE-222 tiene AT-001 activa (almacén agrario vs. uso industrial declarado). IM-06 ya genera PVA con estado CONDICIONADO para los impactos afectados cuando hay CONTs activos (regla E-9). Pero la estructura de datos que describe explícitamente qué CONT condiciona qué impacto/medida/PVA no existe todavía como módulo de código. IM-07 la crea.

**Razón de trazabilidad:** Sin IM-07, un auditor no puede saber automáticamente qué cadena de condicionantes existe en el expediente. El DOCX final puede tener el texto correcto, pero el JSON de trazabilidad no tiene la estructura formal.

**Dependencias satisfechas:**
- `IM-01` (`conesa_engine.py`) ✅ — motor de valoración disponible
- `OB-05` (`assumption_test_system.py`) ✅ — sistema AT/CONT disponible
- `NL-01` (schemas v2.1) ✅ — schema de `inferencias_y_gaps.json` disponible
- `NL-02` (`schema_validator.py`) ✅ — validación disponible
- `IM-00` (`impact_model.py`) ✅ — tipos `Phase6Model`, `EnvironmentalImpact`, `MitigationMeasure`, `PVAProgram` disponibles
- `IM-06` (PVA generator, ahora con ID canónico) ✅ — `phase6_model_with_pva.json` disponible

---

## 5. Prompt de implementación: IM-07

### Encabezado

```
IM-07 — Módulo de propagación de cadenas condicionales
Archivo principal:  src/eia_agent/core/conditional_chain_builder.py
Archivo de tests:   tests/test_conditional_chain_builder.py
Documentación:      docs/CONDITIONAL_CHAIN_BUILDER.md
CLI:                run_expediente.py  →  subparser "phase6-conditional-chains [--write]"
Dependencias:       IM-00, IM-01, OB-05, NL-01, NL-02
Suite baseline:     6214 OK, 12 skipped
```

---

### Restricciones absolutas

- **NO modificar** `expediente-EIA-NAVE-222/` ni ningún expediente piloto original.
- **NO crear** impactos, medidas ni fichas PVA nuevas. IM-07 sólo lee y propaga.
- **NO resolver** CONTs ni cambiar su estado (eso es OB-05 / tarea del técnico).
- **NO modificar** la significancia ni los atributos Conesa de ningún impacto.
- **NO invocar** IA, web, WMS, APIs externas ni ficheros fuera del expediente.
- **NO modificar** `phase6_model_with_pva.json` ni ningún JSON de fases previas.
  El módulo sólo genera nuevos outputs; no sobreescribe los existentes.
- `administrative_ready` debe ser siempre `False` en todos los outputs.
- Sin comentarios innecesarios en el código.

---

### Tipos y constantes

```python
# src/eia_agent/core/conditional_chain_builder.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

# ---------- Constantes ----------

CONDITIONAL_CHAINS_JSON = "conditional_chains.json"
CONDITIONAL_CHAINS_MD   = "conditional_chains.md"

CONT_GAP_STATUSES = ("PENDIENTE", "ABIERTO", "ACTIVO")
# Gaps con cualquiera de estos statuses se consideran CONTs activos.

# ---------- Dataclasses ----------

@dataclass
class ConditionalChain:
    """Una cadena condicional: un CONT y los elementos del modelo que condiciona."""
    cont_id: str            # "CONT-001", o gap_id de tipo CONT
    cont_description: str   # Descripción del CONT
    source: str             # "inferencias_y_gaps" | "assumptions_registry"
    affected_factor_ids: list[str]       # ["FR-003", "FR-004"]
    affected_impact_ids: list[str]       # ["IMP-001", "IMP-005"]
    affected_measure_ids: list[str]      # ["MED-002"]
    affected_pva_ids: list[str]          # ["PVA-001"]
    chain_notes: list[str]               # Notas y advertencias

    def to_dict(self) -> dict:
        ...

    def summary(self) -> str:
        ...


@dataclass
class ConditionalChainResult:
    """Resultado del análisis de cadenas condicionales de un expediente."""
    expediente_id: str
    chains: list[ConditionalChain]
    total_conts_detected: int
    total_impacts_conditioned: int
    total_measures_conditioned: int
    total_pva_conditioned: int
    warnings: list[str]
    notes: list[str]

    @property
    def administrative_ready(self) -> bool:
        return False   # invariante: nunca declarar aptitud administrativa

    def has_active_conts(self) -> bool:
        return len(self.chains) > 0

    def is_success(self) -> bool:
        """Éxito si no hay errores de procesamiento (warnings no son errores)."""
        return True  # IM-07 nunca falla con exit 1 salvo FileNotFoundError

    def to_dict(self) -> dict:
        ...  # incluye "administrative_ready": False

    def summary(self) -> str:
        ...
```

---

### Funciones requeridas

#### `safe_load_json(path: Path) -> dict | None`
Carga JSON tolerante a errores. Devuelve `None` si el fichero no existe o no es JSON válido.
Puede reutilizarse de `document_presentation_preparer.py` si ya existe.

#### `detect_conts_from_gaps(gaps_data: dict) -> list[dict]`
Lee `inferencias_y_gaps.json` y devuelve los gaps con:
- `tipo` == "CONT" O `gap_type` == "CONT" (normalizado a minúsculas)
- `status` en `CONT_GAP_STATUSES`

Cada entrada devuelta es un dict con, como mínimo:
- `gap_id` (o `id`)
- `description`
- `status`
- `factor_id` (opcional — puede ser None si el CONT es transversal)

Si el fichero no existe → devuelve lista vacía, no lanza excepción.

#### `detect_conts_from_assumptions(assumptions_data: dict) -> list[dict]`
Lee `assumptions_registry.json` (salida de OB-05) y devuelve las asunciones de tipo CONT activas.
Criterio: `status == "ACTIVA"` y `tipo_referencia == "CONT"` (o similar según schema OB-05).
Si el fichero no existe → devuelve lista vacía, no lanza excepción.

#### `merge_cont_sources(from_gaps: list[dict], from_assumptions: list[dict]) -> list[dict]`
Combina ambas fuentes deduplicando por `cont_id` / `gap_id`. Fuente `assumptions_registry` tiene prioridad si hay conflicto.

#### `find_impacts_for_cont(cont: dict, model_data: dict) -> list[str]`
Dado un CONT y el contenido de `phase6_model_with_pva.json`, devuelve los IDs de impactos (`IMP-NNN`) que se relacionan con el CONT:
- Si el CONT tiene `factor_id` → busca impactos donde `receptor_factor_id` == `factor_id`
- Si el CONT es transversal (sin `factor_id`) → todos los impactos con significancia SEVERO o CRITICO
- Si el modelo no tiene impactos con esos factores → devuelve lista vacía

#### `find_measures_for_impacts(impact_ids: list[str], model_data: dict) -> list[str]`
Devuelve los IDs de medidas (`MED-NNN`) vinculadas a los impactos dados.
Lee el campo `measures` o `mitigation_measure_ids` del modelo (verificar schema IM-00).

#### `find_pva_for_impacts(impact_ids: list[str], model_data: dict) -> list[str]`
Devuelve los IDs de fichas PVA (`PVA-NNN`) vinculadas a los impactos dados.
Lee el campo `pva_programs` o equivalente del modelo.

#### `build_conditional_chain(cont: dict, model_data: dict) -> ConditionalChain`
Construye un `ConditionalChain` a partir de un CONT dict y el modelo de impactos.
Llama a `find_impacts_for_cont`, `find_measures_for_impacts`, `find_pva_for_impacts`.

#### `build_conditional_chains(expediente_path: Path, model_data: dict | None = None) -> ConditionalChainResult`
Función principal de análisis. Carga:
1. `inferencias_y_gaps.json` → `detect_conts_from_gaps`
2. `control_interno/assumptions_registry.json` (si existe) → `detect_conts_from_assumptions`
3. `fase6/phase6_model_with_pva.json` (si existe y no se pasó `model_data`)

Construye una `ConditionalChain` por CONT detectado.
Si no hay CONTs → devuelve resultado vacío con mensaje informativo.
`administrative_ready` siempre `False`.

#### `build_conditional_chains_markdown(result: ConditionalChainResult) -> str`
Genera informe Markdown con:
- Sección de resumen: nº CONTs activos, impactos/medidas/PVA condicionados
- Sección por cadena: tabla con CONT → factores → impactos → medidas → PVA
- Sección de nota metodológica: los CONTs sólo se resuelven con datos confirmados del promotor
- Advertencia visible si `administrative_ready = False` (no debe confundirse con aptitud admin)

#### `write_conditional_chain_outputs(result: ConditionalChainResult, output_dir: Path) -> list[Path]`
Escribe:
- `fase6/conditional_chains.json`
- `fase6/conditional_chains.md`
Devuelve lista de rutas escritas.

#### `run_conditional_chain_analysis(expediente_path: Path, write_outputs: bool = False) -> ConditionalChainResult`
Función de entrada para CLI:
1. Llama a `build_conditional_chains`
2. Si `write_outputs=True` → llama a `write_conditional_chain_outputs`
3. Imprime resumen a stdout
4. Devuelve `ConditionalChainResult`

---

### CLI en `run_expediente.py`

Añadir subparser `phase6-conditional-chains`:

```python
# Función:
def cmd_phase6_conditional_chains(exp_path: Path, write: bool) -> int:
    from src.eia_agent.core.conditional_chain_builder import run_conditional_chain_analysis
    result = run_conditional_chain_analysis(exp_path, write_outputs=write)
    print(result.summary())
    return 0 if result.is_success() else 1

# Subparser:
# python run_expediente.py <exp_path> phase6-conditional-chains [--write]
```

Patrón idéntico al de otros módulos (phase6-generate-pva, audit-final, etc.).

---

### Tests requeridos — categorías

Se requieren al menos **70 tests** en `tests/test_conditional_chain_builder.py`.

#### TestConditionalChain (6 tests)
- `to_dict()` contiene todos los campos
- `summary()` menciona cont_id
- `to_dict()` no incluye `administrative_ready = True`

#### TestConditionalChainResult (8 tests)
- `administrative_ready` siempre `False` (propiedad no settable)
- `has_active_conts()` True/False según chains
- `is_success()` siempre True (no hay errores bloqueantes en análisis)
- `to_dict()` incluye `"administrative_ready": False`
- `summary()` menciona nº de CONTs

#### TestDetectContsFromGaps (10 tests)
- Detecta gap con tipo "CONT" y status "PENDIENTE"
- Detecta gap con tipo "cont" (minúsculas) — normalización
- Ignora gaps sin tipo CONT
- Ignora gaps CONT con status RESUELTO/CERRADO
- Devuelve lista vacía si `inferencias_y_gaps.json` no existe
- Devuelve lista vacía si JSON malformado
- Detecta múltiples CONTs
- Caso NAVE-222: AT-001/CONT-001 para almacén agrario detectado

#### TestDetectContsFromAssumptions (6 tests)
- Detecta asunción activa con tipo CONT
- Ignora asunciones INACTIVAS
- Devuelve vacío si fichero no existe
- Deduplicación correcta en `merge_cont_sources`

#### TestFindImpactsForCont (10 tests)
- CONT con factor_id → impactos del receptor correcto
- CONT sin factor_id (transversal) → impactos SEVERO/CRITICO
- CONT sin factor_id con modelo sin impactos SEVERO → lista vacía
- Factor_id sin impactos en modelo → lista vacía
- Caso con múltiples impactos afectados

#### TestFindMeasuresAndPVA (8 tests)
- `find_measures_for_impacts` con impactos que tienen medidas
- `find_measures_for_impacts` con impactos sin medidas → lista vacía
- `find_pva_for_impacts` con impactos con PVA
- `find_pva_for_impacts` sin PVA → lista vacía
- Deduplicación de IDs en resultado

#### TestBuildConditionalChain (6 tests)
- Construye cadena con CONT que tiene factor_id → encadena correctamente
- Construye cadena con CONT transversal
- `chain_notes` incluye advertencia si modelo sin PVA

#### TestBuildConditionalChains (10 tests)
- Sin CONTs → resultado con chains=[] y has_active_conts()=False
- 1 CONT detectado → 1 chain construida
- 2 CONTs → 2 chains
- Carga automática de `phase6_model_with_pva.json` si existe
- FileNotFoundError en inferencias_y_gaps.json → lista vacía, no lanza
- `administrative_ready=False` siempre
- Resultado completo con totales correctos

#### TestBuildConditionalChainsMarkdown (6 tests)
- Contiene sección de resumen
- Contiene tabla por cadena si hay CONTs
- Contiene nota metodológica
- Sin CONTs → mensaje "No se detectan CONTs activos" (no dice "no existen")
- No contiene frases de aptitud administrativa

#### TestRunConditionalChainAnalysis (8 tests)
- Dry-run: no crea ficheros
- `--write`: genera `conditional_chains.json` y `conditional_chains.md`
- Exit 0 siempre (análisis no falla con exit 1 salvo excepción técnica)
- Resultado en directorio `fase6/`

#### TestCLIPhase6ConditionalChains (6 tests)
- CLI sin `--write`: exit 0, sin ficheros escritos
- CLI con `--write`: exit 0, ficheros en `fase6/`
- CLI con expediente sin model → exit 0, resultado vacío

#### TestWriteConditionalChainOutputs (3 tests)
- Escribe JSON y MD
- JSON es JSON válido con `administrative_ready: False`
- Devuelve lista de 2 rutas

---

### Criterio de DONE

| Criterio | Verificación |
|----------|-------------|
| ≥70 tests OK | `python -m unittest tests/test_conditional_chain_builder.py` |
| 0 regresiones en suite | `python -m unittest discover -s tests` ≥ 6214 OK |
| CLI `phase6-conditional-chains` en `run_expediente.py` | `python run_expediente.py --help` muestra el subcommand |
| Dry-run exit 0 sobre copia NAVE-222 | Sin ficheros escritos |
| `--write` genera `fase6/conditional_chains.json` y `.md` | Ficheros ≥ 0.5 KB |
| `administrative_ready = False` en JSON | `jq .administrative_ready fase6/conditional_chains.json` == `false` |
| Expediente piloto original NAVE-222 intacto | `git status` limpio |
| Documentación `docs/CONDITIONAL_CHAIN_BUILDER.md` | Fichero presente con API completa |

---

### Notas de implementación

1. **Schema `inferencias_y_gaps.json`:** Verificar en `config/schemas/v2_1/` qué campo distingue un gap de tipo CONT. Si el schema usa `gap_type` en lugar de `tipo`, ajustar `detect_conts_from_gaps` en consecuencia. Priorizar lo que usan los JSONs reales de NAVE-222 antes de diseñar el código.

2. **Schema `assumptions_registry.json` (OB-05):** Revisar `src/eia_agent/core/assumption_test_system.py` para entender qué campo identifica el tipo CONT. No inventar campos.

3. **Schema `phase6_model_with_pva.json` (IM-06):** Revisar `src/eia_agent/core/pva_generator.py` para entender la estructura del modelo con PVA antes de `find_measures_for_impacts` y `find_pva_for_impacts`.

4. **Caso sin modelo:** Si `phase6_model_with_pva.json` no existe, el módulo puede trabajar sólo con la detección de CONTs (affected_impact_ids=[], affected_measure_ids=[], affected_pva_ids=[]). Nunca lanzar FileNotFoundError para el modelo.

5. **Propagación ≠ creación:** IM-07 no crea nuevos impactos, medidas ni PVA. Solo registra qué entidades existentes en el modelo están condicionadas por cada CONT.

6. **Nota metodológica obligatoria:** El Markdown debe incluir explícitamente: "Las cadenas condicionales identificadas en este informe no suponen resolución del CONT correspondiente. La resolución del CONT requiere datos confirmados del promotor y está bajo responsabilidad del técnico redactor."

---

### Secuencia de implementación sugerida

1. Leer `config/schemas/v2_1/inferencias_y_gaps.schema.json` para verificar schema real
2. Leer `src/eia_agent/core/assumption_test_system.py` para entender estructura OB-05
3. Leer `src/eia_agent/core/pva_generator.py` (o equivalent) para estructura IM-06
4. Implementar dataclasses y constantes
5. Implementar funciones de detección: `detect_conts_from_gaps` + `detect_conts_from_assumptions`
6. Implementar funciones de propagación: `find_impacts_for_cont` + `find_measures_for_impacts` + `find_pva_for_impacts`
7. Implementar `build_conditional_chains` + `build_conditional_chains_markdown`
8. Implementar `write_conditional_chain_outputs` + `run_conditional_chain_analysis`
9. Añadir CLI en `run_expediente.py`
10. Escribir tests (≥70)
11. Ejecutar suite completa
12. Actualizar backlog/roadmap/matrix

---

### Commit message esperado

```
IM-07: propagacion de cadenas condicionales desde CONTs activos
```

---

### Post-IM-07: siguientes candidatos naturales

Una vez completado IM-07, los siguientes ítems P1 con mayor valor son:

| Orden | ID | Justificación |
|-------|----|---------------|
| 1 | **QA-10** (nuevo) | Prueba end-to-end de IM-07 sobre copia NAVE-222 (AT-001 activo) |
| 2 | **RD-07** | Último validador de auditoría pendiente; deps (NL-02, IM-01) todas satisfechas |
| 3 | **BE-03** | Formalizar `crear_expediente(ID)` como función Python; bajo riesgo, fundamental para producción |
| 4 | **EN-04** | Bug fix DOCX numbering.xml; pequeño, aislado, mejora calidad del DOCX |
| 5 | **TN-02** | JSON estructurado de normativa base; prerequisito para TN-01 (consulta online) |

---

## 6. Resumen ejecutivo

**Siguiente ítem recomendado: IM-07** — Módulo de propagación de cadenas condicionales.

Es el único ítem del pipeline de impactos/medidas/PVA con código pendiente. Cierra el área IM. Sus dependencias están todas satisfechas. NAVE-222 tiene AT-001/CONT-001 activo, lo que lo hace directamente testeable sobre datos reales. El módulo no crea datos, sólo propaga condicionantes existentes, lo que lo hace seguro de implementar sin riesgo de regresión en el pipeline.

**No implementar todavía.** Este documento contiene la especificación completa lista para usar en la sesión de implementación.
