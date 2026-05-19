# CONESA_ENGINE — IM-01

Motor determinístico de valoración Conesa. Gate de scoring de Fase 6.

**Módulo**: `src/eia_agent/core/conesa_engine.py`  
**ID de productización**: IM-01  
**Completado**: 2026-05-03  
**Dependencias**: IM-00 (`impact_model`)

---

## Qué hace IM-01

Calcula y clasifica el índice de importancia Conesa (`I`) para impactos ambientales
(`EnvironmentalImpact`) definidos en IM-00, aplicando la metodología Conesa-Fernández Vítora.

1. **`classify_conesa_score(score)`** — Convierte un entero I en su categoría de significancia.
2. **`validate_conesa_attributes(attributes)`** — Verifica que cada atributo presente esté en `[1, 12]`.
3. **`calculate_conesa_score(attributes)`** — Aplica la fórmula y devuelve un `ConesaScoreResult`.
4. **`apply_conesa_to_impact(impact, with_measures=False)`** — Valora un impacto y devuelve una copia actualizada (no muta).
5. **`score_phase6_impacts(model, with_measures=False)`** — Valora todos los impactos de un `Phase6Model` y devuelve un modelo nuevo (no muta).

## Qué NO hace IM-01

| Capacidad | Estado |
|-----------|--------|
| Identificar impactos automáticamente | No — tarea del analista |
| Asignar atributos Conesa automáticamente | No — tarea del analista |
| Generar medidas reales para un expediente | No — Fase 6 / IM-02 |
| Generar fichas PVA reales | No — IM-03 |
| Redactar bloques del Documento Ambiental | No — Fase 7 |
| Consultar fuentes externas | No — offline |
| Usar IA | No |
| Llamadas a APIs | No |
| Escribir archivos desde el módulo | No |

---

## Fórmula

```
I = 3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc
```

Donde:

| Símbolo | Atributo | Peso |
|---------|----------|------|
| IN | Intensidad (`intensidad`) | ×3 |
| EX | Extensión (`extension`) | ×2 |
| MO | Momento (`momento`) | ×1 |
| PE | Persistencia (`persistencia`) | ×1 |
| RV | Reversibilidad (`reversibilidad`) | ×1 |
| SI | Sinergia (`sinergia`) | ×1 |
| AC | Acumulación (`acumulacion`) | ×1 |
| EF | Efecto (`efecto`) | ×1 |
| PR | Periodicidad (`periodicidad`) | ×1 |
| Mc | Recuperabilidad (`recuperabilidad`) | ×1 |

**Rango de I**: mínimo = 13 (todos = 1), máximo = 156 (todos = 12).

---

## Clasificación de significancia

Convención interna EIA-Agent v2.1:

| Condición | Significancia |
|-----------|--------------|
| Algún atributo = `None` | `INDETERMINADO` |
| I < 25 | `COMPATIBLE` |
| 25 ≤ I < 50 | `MODERADO` |
| 50 ≤ I < 75 | `SEVERO` |
| I ≥ 75 | `CRITICO` |

Los umbrales son inclusive en el límite inferior y exclusivos en el límite superior.

---

## API pública

### Constantes

| Constante | Tipo | Valor |
|-----------|------|-------|
| `CONESA_MIN_VALUE` | `int` | `1` |
| `CONESA_MAX_VALUE` | `int` | `12` |

### `ConesaScoreResult`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `score` | `int \| None` | Índice I calculado, o None si hay atributos faltantes |
| `significance` | `str` | Categoría de significancia |
| `is_complete` | `bool` | True si todos los atributos estaban presentes |
| `missing_attributes` | `list[str]` | Nombres de atributos faltantes |
| `warnings` | `list[str]` | Avisos metodológicos (p.ej. atributos fuera de rango) |
| `notes` | `list[str]` | Notas de trazabilidad |

Métodos: `to_dict()`, `summary()`.

`summary()` devuelve:
- Si completo: `"I=<score> → <SIGNIFICANCE>"`
- Si incompleto: `"INDETERMINADO (faltan: <lista>)"`

### `classify_conesa_score(score)`

```python
classify_conesa_score(score: int | None) -> str
```

Clasifica un índice I en su categoría. No lanza excepciones.

### `validate_conesa_attributes(attributes)`

```python
validate_conesa_attributes(attributes: ConesaAttributes) -> list[str]
```

Devuelve lista de errores de rango. Vacía si todo correcto. No modifica los atributos.

### `calculate_conesa_score(attributes)`

```python
calculate_conesa_score(attributes: ConesaAttributes) -> ConesaScoreResult
```

- Si algún atributo es `None`: `score=None`, `significance=INDETERMINADO`, `is_complete=False`.
- Si hay atributos fuera de `[1, 12]`: calcula igualmente, pero añade `warnings`.
- Función pura: sin efectos secundarios.

### `apply_conesa_to_impact(impact, with_measures=False)`

```python
apply_conesa_to_impact(
    impact: EnvironmentalImpact,
    with_measures: bool = False,
) -> EnvironmentalImpact
```

Devuelve una **nueva instancia** de `EnvironmentalImpact` (no muta el original).

| `with_measures` | Campo actualizado | Campo preservado |
|-----------------|-------------------|------------------|
| `False` (defecto) | `significance_without_measures` | `significance_with_measures` |
| `True` | `significance_with_measures` | `significance_without_measures` |

Si los atributos están completos: `status` → `"VALORADO"`.  
Si hay atributos faltantes: `status` sin cambio, añade aviso en `warnings`.

### `score_phase6_impacts(model, with_measures=False)`

```python
score_phase6_impacts(
    model: Phase6Model,
    with_measures: bool = False,
) -> Phase6Model
```

Aplica `apply_conesa_to_impact` a cada impacto del modelo.  
Devuelve un **nuevo `Phase6Model`** (no muta el original).  
Acciones, factores receptores, medidas y PVA se copian sin cambios.

---

## Principio de no mutación

Todos los objetos de entrada se preservan. Las funciones devuelven nuevas instancias usando
`dataclasses.replace()`. Esto garantiza que el mismo `Phase6Model` o `EnvironmentalImpact`
puede aplicarse repetidamente en distintos contextos (con/sin medidas) sin efectos secundarios.

```python
# Ejemplo: valorar sin medidas y con medidas sobre el mismo modelo
model_scored_pre  = score_phase6_impacts(model, with_measures=False)
model_scored_post = score_phase6_impacts(model, with_measures=True)
# model permanece sin cambios
```

---

## Relación con IM-00, IM-02, IM-03

```
IM-00 (tipos + reglas)
  └── IM-01 (motor de valoración Conesa) ← este módulo
            ├── IM-02 (constructor medidas correctoras)
            │         ├── IM-03 (constructor fichas PVA)
            │         │         └── IM-05 (validador cobertura PVA)
            │         ├── RD-08 (check diagnóstico≠reductor)
            │         └── RD-09 (check EIA/PRL separator)
            └── RD-06 (Conesa 10 atributos checker)
```

---

## Cómo ejecutar los tests

```bash
# Solo IM-01
venv\Scripts\python -m unittest tests.test_conesa_engine

# Suite completa (sin regresiones)
venv\Scripts\python -m unittest discover -s tests
```

## Tests

**Archivo**: `tests/test_conesa_engine.py`  
**Tests**: 77 | **Resultado**: OK (0 fallos, 0 errores)

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestClassifyConesaScore` | 11 | Umbrales exactos (24→COMPATIBLE, 25→MODERADO, 49→MODERADO, 50→SEVERO, 74→SEVERO, 75→CRITICO), None→INDETERMINADO, casos límite |
| `TestValidateConesaAttributes` | 10 | Todos válidos, todos None, límite mínimo/máximo, por debajo de min, por encima de max, negativo, múltiples errores, None no reportado |
| `TestCalculateConesaScore` | 20 | Todos-1=13/COMPATIBLE, fórmula de pesos IN×3/EX×2, atributo faltante→INDETERMINADO, todos None, score 25/50/75, aviso fuera de rango, to_dict, JSON, summary completo/incompleto, máximo=156, mínimo=13, missing_attributes precisos, umbrales 24/25/49/50/74/75 |
| `TestApplyConesaToImpact` | 14 | without_measures/with_measures, status VALORADO, no mutación del original, aviso si incompleto, significancia correcta, nueva instancia, campos preservados, defecto with_measures=False, aviso de rango propagado |
| `TestScorePhase6Impacts` | 10 | Modelo vacío, no mutación, nueva instancia, todos valorados (sin/con medidas), campos preservados, conteo intacto, incompletos→aviso, defecto with_measures=False, mixto completo/incompleto |
| `TestMethodologicalRules` | 12 | Constantes CONESA_MIN/MAX=1/12, secuencia completa de umbrales, peso IN=3/EX=2/resto=1, INDETERMINADO solo con None, to_dict serializable, idempotencia, sin efectos secundarios |

---

*Generado por EIA-Agent v2.1 — IM-01 — 2026-05-03*
