# Análisis de Fase 6 — Impactos, Medidas y PVA
## EIA-Agent v2.1 — Pre-implementación

**Fecha de análisis**: 2026-05-03  
**Estado del sistema en el momento del análisis**: 3506 tests OK, 0 failures. Fase 5 cerrada con F5-01. IV-00 a IV-10 completados.  
**Fuentes**: `backlog_productizacion.md`, `roadmap_productizacion.md`, `matriz_maestra_items_productizacion.md`  
**Objetivo**: Proponer el orden correcto de implementación antes de escribir una línea de código.

---

## 1. Resumen ejecutivo

Fase 6 (AG-9) no tiene ningún ítem completado como código. Los pilotos PARCELA y NAVE-222 ejecutaron la valoración de impactos de forma manual con asistencia LLM narrativa, sin módulos Python. El backlog lista IM-01, IM-02, IM-03 como "Funcional en piloto", pero esa expresión significa "el técnico lo hizo con el LLM" — no existe ningún archivo `.py` en `src/eia_agent/core/` para ninguno de estos ítems.

**El problema estructural más grave**: no existe ningún modelo base de impactos equivalente a `inventory_model.py` (IV-00). El backlog declara IM-01 dependiente de `IV-01, NL-01`, pero la dependencia real es un modelo Python tipado que aún no existe. Sin ese modelo, cualquier implementación de IM-01 produciría un JSON no validable, sin tipos, sin reglas de coherencia aplicadas al dominio de impactos.

**Diagnóstico de viabilidad**:
- Ítems totalmente deterministas: IM-00 (modelo base), IM-05 (validador cobertura), RD-06 (Conesa checker), RD-08 (diagnóstico≠reductor), RD-09 (EIA/PRL).
- Ítems deterministas con tablas tipológicas R12/R13: IM-01 en modo offline (usando tabla de acciones+factores para Nave 222 como fixture base), IM-02, IM-03, IM-06.
- Ítems que requieren entrada humana supervisada o IA: la valoración de los 10 atributos Conesa por impacto (IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc) implica juicio técnico que no puede generarse automáticamente sin el documento del promotor. En modo offline/test, se acepta tabla tipológica R12/R13 con advertencia.
- Ítems bloqueados por dependencias no resueltas: IM-07 depende de OB-05 (clase `AsuncionTest`), que es PROMPT pero no CÓDIGO.

---

## 2. Tabla de ítems IM/AG09/PVA

### 2.1 Ítems del dominio principal (ÁREA 8)

| ID | Nombre | Prioridad | Esfuerzo | Estado real | Piloto | Determinista | Offline | Dep. |
|----|--------|-----------|----------|-------------|--------|--------------|---------|------|
| **IM-00** | Modelo base impactos/medidas/PVA | **P1 (faltante)** | S | ❌ No existe ni en backlog | — | ✅ Sí | ✅ Sí | IV-00 (patrón) |
| IM-01 | Matriz Conesa (constructor) | P1 | M | ❌ Sin código | Nave 222 (11 IMP) | ⚠️ Parcial (*) | ✅ Sí | IM-00, IV-02, NL-01 |
| IM-02 | Medidas correctoras (constructor) | P1 | M | ❌ Sin código | Nave 222 (M-01…M-10) | ⚠️ Parcial (*) | ✅ Sí | IM-01 |
| IM-03 | Fichas PVA (constructor) | P1 | M | ❌ Sin código | Nave 222 (PVA-01…PVA-07) | ⚠️ Parcial (*) | ✅ Sí | IM-01, IM-02 |
| IM-05 | Validador cobertura PVA | P1 | S | ❌ Sin código | PARCELA (IMP-05, IMP-06 sin PVA) | ✅ Sí | ✅ Sí | IM-03, NL-02 |
| IM-04 | PVA genérico Compatible | P2 | S | ❌ Sin código | — | ✅ Sí | ✅ Sí | IM-03 |

(*) La construcción de valores Conesa (IN, EX, MO…) requiere tabla tipológica offline o entrada humana. La estructura, validación y cálculo del índice son deterministas.

### 2.2 Ítems de Área 14 con componente de Fase 6 (código pendiente)

| ID | Nombre | Prioridad | Estado | Piloto | Determinista | Bloquea a | Dep. |
|----|--------|-----------|--------|--------|--------------|-----------|------|
| IM-06 | Template C.5 acumulativos/sinérgicos | P1 | ✅ PROMPT / ❌ CÓDIGO | Nave 222 (sección C.5) | ✅ Sí | IM-01 | IM-01 |
| IM-07 | Cadenas condicionales CONTs | P1 | ✅ PROMPT / ❌ CÓDIGO | Nave 222 (CONT-001) | ✅ Sí | — | IM-01, **OB-05** |
| RD-06 | Conesa checker (10 atributos) | P1 | ✅ PROMPT / ❌ CÓDIGO | PARCELA (IMP-03 sin Mc) | ✅ Sí | AU-01 | IM-01, NL-02 |
| RD-07 | Cross-ref gap ALTA positivo | **P2** | ✅ PROMPT / ❌ CÓDIGO | Nave 222 (IMP-09 empleo) | ✅ Sí | — | IM-01, NL-02 |
| RD-08 | Diagnóstico≠reductor | P1 | ✅ PROMPT / ❌ CÓDIGO | — (regla AG09-13) | ✅ Sí | AU-01 | IM-02, NL-02 |
| RD-09 | EIA/PRL separator | P1 | ✅ PROMPT / ❌ CÓDIGO | — (regla AG09-14) | ✅ Sí | AU-01 | IM-02, NL-02 |

### 2.3 Ítem predecesor necesario para IM-07

| ID | Nombre | Estado | Dep. de IM-07 |
|----|--------|--------|--------------|
| OB-05 | Sistema AT (`AsuncionTest`) | ✅ PROMPT / ❌ CÓDIGO | IM-07 depende de que los CONTs estén tipados |

---

## 3. Dependencias

### Grafo de dependencias Fase 6 (orientado hacia abajo)

```
IV-00 (inventory_model — COMPLETADO)
  └── IV-02 (inventory_builder — COMPLETADO)
        └── F5-01 (phase5_gate — COMPLETADO)
              │
              ▼
         IM-00 [NUEVO — modelo base impactos]
              ├──► IM-01 (matriz Conesa)
              │        ├──► IM-02 (medidas)
              │        │        ├──► IM-03 (PVA)
              │        │        │        └──► IM-05 (validador cobertura PVA)
              │        │        │        └──► IM-04 (PVA genérico Compatible) [P2]
              │        │        ├──► RD-08 (diagnóstico≠reductor)
              │        │        └──► RD-09 (EIA/PRL separator)
              │        ├──► IM-06 (template C.5 acumulativos)
              │        ├──► RD-06 (Conesa 10 atributos checker)
              │        └──► RD-07 (cross-ref gap ALTA positivo) [P2]
              │
OB-05 [código pendiente]
  └──► IM-07 (cadenas condicionales CONTs)
            └── (requiere IM-01 ya completado)
```

**Nodo crítico de desbloqueo**: `IM-00`. Sin él, ningún ítem de Fase 6 puede comenzar con garantías de coherencia.

**Dependencia externa bloqueante para IM-07**: `OB-05` (clase `AsuncionTest`). Si OB-05 no se implementa antes de IM-07, el módulo de cadenas condicionales no puede detectar qué CONTs están activos de forma tipada. IM-07 puede diseñarse para operar sin OB-05 (leyendo el JSON de `inferencias_y_gaps.json` directamente), pero perdería la integración con el sistema AT formalizado.

---

## 4. Incoherencias detectadas entre backlog, roadmap y matriz

### INC-01 — IM-00 no existe en ningún documento
**Dónde**: Backlog ÁREA 8, Roadmap Semana 6-7, Matriz GRUPO 8.  
**Problema**: IV-00 (modelo base de inventario) fue el primer ítem de Fase 5. No existe un equivalente para Fase 6. IM-01 en la matriz tiene `dep: IV-01, NL-01`, pero la dependencia real es un modelo de dominio de impactos (tipos Python: `ProjectAction`, `ImpactRecord`, `MeasureRecord`, `PVARecord`, función `calculate_importance_index()`).  
**Riesgo**: Si se implementa IM-01 directamente sobre dicts Python sin modelo base, el JSON producido no puede ser validado de forma estructurada. Las reglas RD-06, RD-08, RD-09 quedarían sin un contrato de tipos que validar.  
**Acción recomendada**: Crear IM-00 como primer ítem de Fase 6.

### INC-02 — "Funcional en piloto" ≠ código ejecutable
**Dónde**: Backlog ÁREA 8 (IM-01, IM-02, IM-03), Matriz GRUPO 8.  
**Problema**: Los tres ítems dicen "✅ Funcional en piloto". Pero en el piloto, la matriz de impactos, las medidas y el PVA fueron generados por el LLM como texto narrativo en bloques .md, luego transcritos manualmente a un JSON de referencia. No existe ningún `impact_builder.py` ni `pva_builder.py` en el repositorio.  
**Riesgo**: Confundir este estado con "casi listo para productizar". El esfuerzo real es M/L para cada ítem, no S.  
**Acción recomendada**: Corregir la lectura del estado como "patrón validado como práctica LLM" — equivalente a como estaba IV-01 antes de la productización de Fase 5.

### INC-03 — OB-05 bloquea IM-07 pero no está en la cadena de Fase 6
**Dónde**: Roadmap Semana 9 (OB-05) vs. Semana 6-7 (IM-07).  
**Problema**: El roadmap planifica IM-07 en Semana 6-7, pero su dependencia OB-05 está planificada en Semana 9. La dependencia va hacia atrás en el tiempo.  
**Riesgo**: Implementar IM-07 antes de OB-05 fuerza a leer el estado CONT de los JSONs brutos, sin tipos. El código resultante no sería coherente con lo que producirá OB-05 cuando se implemente.  
**Acción recomendada**: Implementar IM-07 después de OB-05, o diseñar IM-07 con una interfaz de entrada genérica que pueda actualizarse cuando OB-05 esté listo.

### INC-04 — RD-07 (P2) aparece en Semana 9 del roadmap P1
**Dónde**: Roadmap Semana 9 lista RD-07 sin anotar que es P2.  
**Problema**: RD-07 (cross-ref gap ALTA positivo) está marcado explícitamente como P2 en el backlog. Su aparición en la Semana 9 de P1 genera ambigüedad sobre si debe implementarse en P1.  
**Acción recomendada**: Excluir RD-07 del sprint P1. Implementar después de IM-04 (P2).

### INC-05 — IM-05 depende de IM-03 que no existe aún, pero su definición de DONE asume PARCELA
**Dónde**: Matriz GRUPO 8, IM-05.  
**Problema**: La definición de DONE de IM-05 dice "Detecta IMP-05 e IMP-06 de PARCELA como sin cobertura propia". PARCELA es el piloto 1, cuyos datos de impactos son un JSON manual (no generado por código). Para que IM-05 tenga un fixture real, necesita que IM-03 ya haya generado el PVA de algún expediente.  
**Acción recomendada**: Aceptar fixture JSON manual de PARCELA como caso de prueba. No bloquear IM-05 hasta tener IM-03 ejecutándose sobre un expediente real.

### INC-06 — IM-06 tiene dep: IM-01, pero C.5 requiere también datos del inventario
**Dónde**: Matriz GRUPO 8, IM-06.  
**Problema**: La sección C.5 de acumulativos/sinérgicos requiere conocer qué factores tienen impactos significativos (viene de IM-01) y también saber qué instalaciones vecinas existen en el área (viene del inventario FI-009/FI-010 + cartografía). La dep declarada es solo `IM-01`.  
**Acción recomendada**: Añadir `IV-02` (summary de inventario) como dependencia de IM-06. El módulo debe poder leer el estado de FI-009 (ENP) y FI-010 (Red Natura) para generar la sección C.5 con el nivel de cautela correcto.

---

## 5. Reutilización de pilotos PARCELA y NAVE-222

### Datos de referencia disponibles

| Elemento | Piloto | Descripción | Uso en código |
|----------|--------|-------------|---------------|
| 11 impactos valorados (IMP-01…IMP-11) | NAVE-222 | Acción R1201/R1202/R1203 × 5 factores: aire, ruido, suelo, aguas, empleo | Fixture de referencia para IM-00 y tests de IM-01 |
| 10 atributos Conesa por impacto | NAVE-222 | IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc — todos con valores | Test `test_calculate_importance_index` reproduce índice correcto para cada IMP |
| M-01 a M-10 (medidas) | NAVE-222 | Tipología: 3 preventivas, 4 correctoras, 1 diagnóstico, 1 PRL, 1 gestión cierre | Fixture para IM-02; la medida diagnóstica M-08 sirve para test RD-08 |
| PVA-01 a PVA-07 | NAVE-222 | Impactos Moderado+: indicadores, umbrales, frecuencia semestral | Fixture para IM-03 |
| IMP-05, IMP-06 sin PVA propio | PARCELA | Dos impactos Compatible sin ficha PVA individual | Fixture para IM-05 (caso sin cobertura propia) |
| CONT-001 | NAVE-222 | Contradicción uso catastral ≠ uso industrial, AT activo | Fixture para IM-07 (cadena condicional) |
| Tabla de acciones R12/R13 | Ambos | R1201 (recepción/clasificación), R1202 (manipulación/prensado), R1203 (almacenamiento/expedición) | Seed data para tabla tipológica de `ProjectAction` en IM-00 |

### Qué NO reutilizar

- Los textos narrativos de los bloques C.1 a C.4 del piloto: son salidas LLM, no datos de entrada al modelo.
- Los nombres de medidas tal como están en el DOCX: tienen variaciones de redacción entre pilotos. Se necesita una tabla canónica normalizada.
- Las importancias calculadas en los pilotos sin verificar: en algún piloto hubo inconsistencias en los atributos Conesa (OBS-M12-001 habla de IMP-03 en PARCELA con `Mc` ausente).

---

## 6. Determinista vs. IA controlada

### Completamente determinista (sin IA, sin entrada humana)

| Ítem | Por qué |
|------|---------|
| IM-00 (modelo base) | Define tipos y reglas. Puro Python sin lógica de dominio subjetiva. |
| `calculate_importance_index(conesa_attrs)` | Fórmula aritmética fija: I = ±(3IN + 2EX + MO + PE + RV + SI + AC + EF + PR + Mc). |
| `classify_significance(index)` | Umbrales fijos: <25 → COMPATIBLE, 25-50 → MODERADO, 50-75 → SEVERO, ≥75 → CRÍTICO. |
| IM-05 (validador cobertura) | Comparación de listas: ¿tiene este IMP una PVA asociada? |
| RD-06 (Conesa checker) | Verifica que los 10 campos están presentes y son numéricos. |
| RD-08 (diagnóstico≠reductor) | Verifica que `tipo: diagnostico` no aparece en `tabla_impacto_medida`. |
| RD-09 (EIA/PRL) | Verifica que `tipo: prl` tiene `nota_alcance` y no tiene `significancia_residual`. |
| IM-06 (C.5 template) | Template con 4 áreas mínimas; contenido INDETERMINADO si no hay datos vecinos. |
| IM-07 (cadenas condicionales) | Lógica de propagación de estado CONDICIONADO a partir de CONTs activos. |

### Requiere tabla tipológica R12/R13 (determinista + datos externos)

| Ítem | Por qué | Solución offline |
|------|---------|-----------------|
| IM-01 (valoración Conesa por impacto) | Los valores IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc de cada acción×factor son juicio técnico. | Tabla tipológica R12/R13 (con datos de NAVE-222 como referencia). Atributos marcados INDETERMINADO cuando no hay suficiente información. |
| IM-02 (asignación medidas a impactos) | Qué medida corresponde a qué impacto es criterio técnico. | Tabla de acciones-impactos-medidas para R12/R13 como datos precargados. |
| IM-03 (redacción indicador/umbral PVA) | "Concentración de PM10 < 50 μg/m³" es un dato técnico normativo. | Tabla de indicadores/umbrales por tipo de factor desde normativa offline (Decreto 833/1975, WHO 2021). |

### Requiere entrada humana o LLM supervisado (no automatizable offline)

| Ítem | Por qué | Estado en modo offline |
|------|---------|----------------------|
| Valoración de impactos positivos | El beneficio socioeconómico depende del contexto local, número de empleos, economía de la zona. | Marcar como INDETERMINADO con nota: "requiere datos del promotor sobre empleo previsto". |
| Impactos acumulativos con instalaciones vecinas (C.5) | Requiere conocer instalaciones próximas, carga ambiental acumulada. | Template C.5 genera las 4 áreas con estado INDETERMINADO + gap ALTA/GABINETE automáticamente. |

---

## 7. Primer ítem recomendado: IM-00

### Justificación

Todas las razones para empezar por un modelo base antes de los constructores, con el mismo razonamiento que llevó a crear IV-00 antes de IV-01 y IV-02:

1. Sin `ImpactRecord` tipado, `generar_matriz_impactos()` produce un dict Python sin validación.
2. Sin `calculate_importance_index()`, cada constructor de IM-01 calcularía el índice de forma ad hoc, sin tests canónicos.
3. Sin `MeasureRecord` con campo `tipo`, los checks RD-08 y RD-09 no tienen contrato de tipos sobre el que operar.
4. Sin `PVARecord` con campo `status`, el estado CONDICIONADO de IM-07 no tiene representación tipada.
5. Sin `ImpactMatrix` como contenedor canónico, los outputs de IM-01 a IM-07 no son interoperables.

### Definición de DONE para IM-00

- `src/eia_agent/core/impact_model.py` existe con los tipos descritos a continuación.
- `tests/test_impact_model.py` con ≥100 tests: tipos, validación, cálculo de índice, clasificación de significancia, reglas de coherencia.
- `calculate_importance_index(conesa_attrs)` reproduce los 11 índices de NAVE-222 correctamente.
- `classify_significance(index)` reproduce las 11 significancias de NAVE-222 correctamente.
- `validate_impact_record(record)` detecta: atributo Conesa fuera de rango, signo POSITIVO con significancia SEVERO/CRÍTICO sin nota de incertidumbre (regla E-10 detectada), `ready_for_phase7=True` con atributos INDETERMINADOS.
- `validate_measure_record(record)` detecta: `tipo: diagnostico` en `tabla_impacto_medida` (RD-08), `tipo: prl` sin `nota_alcance` (RD-09).
- No usa IA, no consulta fuentes externas, no modifica expedientes piloto.
- `docs/IMPACT_MODEL.md` creado.

### Especificación técnica de IM-00

#### Constantes de dominio

```python
IMPACT_PHASES: frozenset[str] = frozenset({
    "CONSTRUCCION", "EXPLOTACION", "CIERRE", "RESTAURACION"
})

IMPACT_SIGNS: frozenset[str] = frozenset({
    "POSITIVO", "NEGATIVO", "INDETERMINADO"
})

IMPACT_SIGNIFICANCES: frozenset[str] = frozenset({
    "COMPATIBLE",     # I < 25
    "MODERADO",       # 25 ≤ I < 50
    "SEVERO",         # 50 ≤ I < 75
    "CRITICO",        # I ≥ 75
    "INDETERMINADO",  # atributos insuficientes para calcular
})

MEASURE_TYPES: frozenset[str] = frozenset({
    "PREVENTIVA",
    "CORRECTORA",
    "COMPENSATORIA",
    "DIAGNOSTICA",    # NO va en tabla_impacto_medida como reductora (AG09-13)
    "PRL",            # NO reduce significancia ambiental (AG09-14)
    "GESTION_CIERRE",
})

PVA_STATUSES: frozenset[str] = frozenset({
    "ACTIVO",
    "CONDICIONADO",      # hay CONT activo asociado al impacto (E-9)
    "PENDIENTE_DATOS",   # gap ALTA en factor receptor (E-10)
    "COMPLETADO",
})
```

#### Dataclass `ConesamAttributes`

Atributos Conesa con rangos válidos y valor centinela `"INDETERMINADO"`:

| Atributo | Símbolo | Rango válido |
|----------|---------|-------------|
| Intensidad | IN | 1, 2, 4, 8, 12 |
| Extensión | EX | 1, 2, 4, 8 |
| Momento | MO | 1, 2, 4 |
| Persistencia | PE | 1, 2, 4 |
| Reversibilidad | RV | 1, 2, 4 |
| Sinergia | SI | 1, 2, 4 |
| Acumulación | AC | 1, 4 |
| Efecto | EF | 1, 4 |
| Periodicidad | PR | 1, 2, 4 |
| Recuperabilidad | Mc | 1, 2, 4, 8 |

Cada atributo puede ser `int` (valor válido) o la cadena `"INDETERMINADO"`.

#### Función `calculate_importance_index`

```
I = ±(3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc)
```

Si algún atributo es `"INDETERMINADO"` → devuelve `None` y la significancia es `"INDETERMINADO"`.  
El signo del resultado sigue `signo` del `ImpactRecord`.

#### Función `classify_significance`

```
I < 25          → "COMPATIBLE"
25 ≤ I < 50     → "MODERADO"
50 ≤ I < 75     → "SEVERO"
I ≥ 75          → "CRITICO"
None (atribs)   → "INDETERMINADO"
```

#### Dataclass `ProjectAction`

```python
@dataclass
class ProjectAction:
    action_id: str           # AC-001, AC-002...
    action_code: str         # R1201, R1202, R1203...
    description: str
    phase: str               # CONSTRUCCION / EXPLOTACION / CIERRE
    notes: list[str]
```

#### Dataclass `ImpactRecord`

```python
@dataclass
class ImpactRecord:
    impact_id: str           # IMP-001...
    action_id: str
    factor_id: str           # FI-001...FI-016
    signo: str
    conesa_attrs: ConesamAttributes
    importance_index: Optional[int]
    significance: str
    indeterminate_reason: str  # por qué es INDETERMINADO, si aplica
    notes: list[str]
    ready_for_phase7: bool   # False por defecto
```

Reglas de coherencia en `validate()`:
- `signo=POSITIVO` con `significance=SEVERO` o `CRITICO` → WARNING: impacto positivo de alta magnitud requiere nota de incertidumbre (E-10).
- `ready_for_phase7=True` con atributos INDETERMINADOS → ERROR.
- `ready_for_phase7=True` con `significance=INDETERMINADO` → ERROR.

#### Dataclass `MeasureRecord`

```python
@dataclass
class MeasureRecord:
    measure_id: str          # M-001...
    measure_type: str        # de MEASURE_TYPES
    factor_ids: list[str]    # factores protegidos
    action_ids: list[str]    # acciones a las que aplica
    description: str
    residual_significance: Optional[str]   # None si DIAGNOSTICA o PRL
    nota_alcance: str        # obligatorio para PRL
    in_impact_reduction_table: bool        # False si DIAGNOSTICA o PRL
```

Reglas de coherencia en `validate()`:
- `measure_type=DIAGNOSTICA` + `in_impact_reduction_table=True` → ERROR (AG09-13).
- `measure_type=PRL` + `in_impact_reduction_table=True` → ERROR (AG09-14).
- `measure_type=PRL` + `nota_alcance` vacío → ERROR (AG09-14).
- `measure_type=PRL` + `residual_significance` no None → ERROR (AG09-14).

#### Dataclass `PVARecord`

```python
@dataclass
class PVARecord:
    pva_id: str              # PVA-001...
    impact_id: str
    indicator: str
    threshold: str
    frequency: str
    responsible: str
    status: str              # de PVA_STATUSES
    conditioned_by_cont: Optional[str]  # ID del CONT si CONDICIONADO (E-9)
    uncertainty_note: str    # nota de incertidumbre para positivos (E-10)
```

#### Dataclass `ImpactMatrix`

```python
@dataclass
class ImpactMatrix:
    expediente_id: str
    actions: list[ProjectAction]
    impact_records: list[ImpactRecord]
    measures: list[MeasureRecord]
    pva_records: list[PVARecord]
    warnings: list[str]
    notes: list[str]
```

---

## 8. Prompt sugerido para implementar IM-00

```
Quiero implementar el siguiente hito: IM-00 — Modelo base de impactos, 
medidas y PVA para Fase 6 EIA.

Contexto:
- Equivalent to IV-00 (inventory_model.py) but for the impact assessment domain.
- Fase 5 offline está cerrada: IV-00 a IV-10 completados, F5-01 completado.
- Suite: 3506 tests OK, 0 failures.
- No modificar expedientes piloto.
- No IA, no web, no WMS, no CLI propio (se añadirá en IM-01).
- Offline-only.
- El piloto NAVE-222 tiene 11 impactos valorados con 10 atributos Conesa 
  que deben ser reproducibles por el modelo como fixture de test.

Módulo a crear:
  src/eia_agent/core/impact_model.py

Especificación técnica completa:
[pegar sección §7 de este documento]

Tests a crear:
  tests/test_impact_model.py

Clases de tests requeridas:
- TestConesamAttributes: rangos válidos, valor INDETERMINADO, 
  serialización to_dict.
- TestCalculateImportanceIndex: reproduce los 11 índices de NAVE-222 
  exactamente; None si algún atributo es INDETERMINADO; fórmula 
  I=±(3IN+2EX+MO+PE+RV+SI+AC+EF+PR+Mc).
- TestClassifySignificance: <25→COMPATIBLE, 25-50→MODERADO, 50-75→SEVERO, 
  ≥75→CRITICO, None→INDETERMINADO.
- TestProjectAction: to_dict, JSON serializable.
- TestImpactRecord: validate() detecta POSITIVO+SEVERO/CRITICO sin nota; 
  ready=True con INDETERMINADO → ERROR; to_dict serializable.
- TestMeasureRecord: validate() detecta DIAGNOSTICA en tabla reducción 
  (AG09-13); PRL sin nota_alcance (AG09-14); PRL con significancia_residual 
  (AG09-14); to_dict serializable.
- TestPVARecord: to_dict, CONDICIONADO con cont_id, nota incertidumbre.
- TestImpactMatrix: contenedor, to_dict, JSON serializable, 
  fixture NAVE-222 (11 IMP, 10 MED, 7 PVA).
- TestNave222Fixture: reproduce índices y significancias de NAVE-222.
- TestPrudenceRules: ausencia de lenguaje de compensación negativo+positivo, 
  no mezcla PRL con EIA.

Objetivo: ≥100 tests OK, 0 failures, suite completa sin regresiones.

Reglas no negociables:
- No se compensa un impacto negativo con uno positivo.
- DIAGNOSTICA y PRL nunca reducen significancia en tabla de impacto-medida.
- Atributos INDETERMINADOS → significancia INDETERMINADO, nunca forzar valor.
- ready_for_phase7=False por defecto.
- No lenguaje de valoración antes de tener datos: no afirmar "impacto 
  compatible" sin haber calculado I.

Al completar:
- Crear docs/IMPACT_MODEL.md con API pública y tabla de constantes.
- Actualizar control_interno/backlog_productizacion.md, roadmap y matriz 
  con IM-00 COMPLETADO.
```

---

## 9. Orden completo recomendado para Fase 6

| Paso | ID | Nombre | Tipo | Esfuerzo estimado | Notas |
|------|-----|--------|------|-------------------|-------|
| 1 | **IM-00** (nuevo) | Modelo base impactos/medidas/PVA | modelo | S | **Primer ítem. Bloqueante.** |
| 2 | **IM-01** | Constructor matriz Conesa offline | constructor | M | Tabla tipológica R12/R13 + fixture NAVE-222 |
| 3 | **IM-02** | Constructor medidas correctoras | constructor | M | Tipología completa; separar DIAGNOSTICA y PRL |
| 4 | **IM-03** | Constructor fichas PVA | constructor | M | E-9 (CONDICIONADO) + E-10 (incertidumbre positivos) |
| 5 | **IM-05** | Validador cobertura PVA | validador | S | Fixture PARCELA (IMP-05, IMP-06) |
| 6 | **IM-06** | Template C.5 acumulativos | constructor | S | 4 áreas mínimas; INDETERMINADO si sin datos vecinos |
| 7 | **RD-06** | Conesa checker 10 atributos | validador | S | Absorbible en AU-01 |
| 8 | **RD-08** | Diagnóstico≠reductor | validador | S | Absorbible en validación de IM-02 |
| 9 | **RD-09** | EIA/PRL separator | validador | S | Absorbible en validación de IM-02 |
| 10 | **(OB-05)** | Sistema AT (prerequisito externo) | sistema | M | Prerequisito de IM-07; implementar antes |
| 11 | **IM-07** | Cadenas condicionales CONTs | constructor | M | Solo después de OB-05 |
| — | IM-04 | PVA genérico Compatible | constructor | S | **P2** — implementar después de cerrar P1 |
| — | RD-07 | Cross-ref gap ALTA positivo | validador | S | **P2** — implementar después de IM-04 |

---

## 10. Puntos de decisión antes de implementar

Antes de comenzar IM-00, conviene confirmar:

**D-01**: ¿Los valores de los atributos Conesa se almacenan como `int` o como `str`?  
Recomendación: `int` para los valores numéricos, cadena `"INDETERMINADO"` como centinela. `Optional[int]` en Python, pero validado contra rangos permitidos.

**D-02**: ¿`ImpactRecord` calcula `importance_index` en `__post_init__` o por función externa?  
Recomendación: función externa `calculate_importance_index(conesa_attrs)` (igual que `classify_semaphore_from_evidence` en IV-00), y `importance_index` como campo calculado en construcción. Permite recalcular al modificar atributos.

**D-03**: ¿Debe `ImpactMatrix.to_dict()` incluir los índices calculados o solo los atributos?  
Recomendación: incluir ambos (`conesa_attrs` + `importance_index` + `significance`) para que el JSON sea legible sin recalcular.

**D-04**: ¿Se implementan RD-08 y RD-09 dentro de `MeasureRecord.validate()` o como funciones externas tipo checker?  
Recomendación: dentro de `validate()` de `MeasureRecord` (igual que la regla de prudencia en `FactorInventory.validate()`). El checker externo (para AU-01) lee la lista de medidas y llama a `validate()` individualmente.

**D-05**: ¿Tabla tipológica de acciones R12/R13 como datos hardcoded en código o como JSON externo?  
Recomendación: JSON externo en `config/tipologias/r12_r13_acciones.json`, cargado opcionalmente. IM-00 no depende de él; IM-01 lo usa como datos de entrada.

---

*Informe generado por EIA-Agent v2.1 — Análisis pre-implementación Fase 6 — 2026-05-03*
