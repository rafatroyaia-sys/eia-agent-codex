# BLOCK_CONSISTENCY_VALIDATOR.md — RD-04

**Modulo:** `src/eia_agent/core/block_consistency_validator.py`  
**CLI:** `python run_expediente.py <expediente> audit-block-consistency [--write]`  
**Tests:** `tests/test_block_consistency_validator.py` (121 tests OK)

---

## Que hace RD-04

Valida la coherencia entre bloques del Documento Ambiental detectando
contradicciones entre textos markdown generados por el sistema o por el tecnico.

Opera sobre los bloques ya generados (no los redacta). Es un paso de auditoria,
no de redaccion.

---

## Que NO hace RD-04

- **No corrige textos.** Solo detecta y reporta.
- **No reescribe bloques.** El validador lee, nunca escribe bloques de contenido.
- **No valora impactos.** Eso es Fase 6 (IM-01 a IM-08).
- **No declara aptitud administrativa.** Solo el organo ambiental emite el IIA.
- **No usa IA.** Deteccion puramente determinista por pattern matching.
- **No modifica el expediente** salvo que se use `--write` para guardar el informe.

Diferencia con **AU-05 (P2)**: AU-05 validara coherencia de entidades entre todos
los bloques A-K de forma mas profunda. RD-04 opera como validador previo, offline y determinista.

---

## Familias de bloques revisadas

| Familia | Descripcion | Archivos tipicos |
|---------|-------------|-----------------|
| `A_IDENTIFICACION` | Datos del promotor, objeto del proyecto | `bloque_A.md` |
| `B_INVENTARIO` | Inventario ambiental por factor | `inventario/FI-*.md` |
| `C_IMPACTOS` | Identificacion y valoracion | `impactos/AG09_valoracion.md` |
| `D_MEDIDAS` | Medidas correctoras | `impactos/AG09_medidas.md` |
| `E_PVA` | Programa de Vigilancia Ambiental | `impactos/AG09_PVA.md` |
| `H_RED_NATURA` | Red Natura 2000 / ENP | `bloque_H.md` |
| `I_CONCLUSIONES` | Conclusiones tecncias | `bloque_I_conclusiones.md` |
| `J_RNT` | Resumen No Tecnico | `bloque_J_rnt.md` |
| `K_ANEXOS` | Anejos y anexos | `anejo_*.md` |
| `GENERICO` | Otros archivos tecnicos | markdowns no clasificados dentro de bloques/inventario/impactos |

---

## Coherencias revisadas

### 1. Red Natura 2000 (BC-RN-001, BC-RN-002)
- Bloque H (Red Natura) o inventario con FI-010/FR-010 contiene indicador de cautela
  (pendiente, indeterminado, consulta pendiente, gap, etc.)
- Y un bloque de conclusiones (I) o RNT (J) dice:
  "sin afeccion apreciable", "sin afeccion significativa", "no afecta a red natura",
  "se descarta afeccion a red natura", etc.
- **Resultado**: ERROR (BC-RN-001)

### 2. Biodiversidad — flora/fauna (BC-BIO-001)
- Inventario FI-007 (flora) o FI-008 (fauna) con cautela (campo necesario, gap, prospeccion pendiente)
- Y conclusiones/RNT dice:
  "sin especies protegidas", "sin fauna", "sin flora", "sin afeccion a flora", etc.
- **Resultado**: ERROR (BC-BIO-001)

### 3. Patrimonio cultural (BC-HER-001)
- Inventario FI-012 o bloque con "patrimonio"/"yacimiento"/"arqueolog" con cautela
- Y conclusiones/RNT dice:
  "no hay patrimonio", "sin yacimientos", "sin afeccion patrimonial", etc.
- **Resultado**: ERROR (BC-HER-001)

### 4. Medidas diagnosticas y PRL (BC-MEA-001, BC-MEA-002)
- Un bloque de medidas (D) presenta una medida diagnostica (estudio acustico,
  medicion acustica, diagnostica...) junto a lenguaje de reduccion de significancia
  (reductora, correctora, reduce el impacto...).
- O una medida PRL_NO_EIA junto a "correctora ambiental"/"reductora ambiental".
- **Resultado**: ERROR (BC-MEA-001 / BC-MEA-002)
- Reglas AG09-13 y AG09-14: DIAGNOSTICA y PRL_NO_EIA no reducen significancia.

### 5. Asunciones de test activas (BC-AT-001, BC-AT-002)
- El registro de ATs tiene asunciones ACTIVAS, O algun bloque menciona "at activa".
- Y un bloque de conclusion (I/J) dice:
  "apto para presentacion", "apto administrativamente", "sin condicionantes",
  "datos confirmados", etc.
- **Resultado**: ERROR

### 6. PVA condicionado (BC-PVA-001)
- Un bloque PVA indica "condicionado por cont/at", "sujeto a cont", "ficha condicionada".
- Y un bloque de conclusion dice "pva cerrado", "pva completado",
  "vigilancia ambiental finalizada".
- **Resultado**: ERROR (BC-PVA-001)

### 7. Conclusiones / RNT (BC-CON-001 a BC-CON-004)
- "todos los impactos son compatibles" pero otros bloques tienen INDETERMINADO → ERROR
- "no existen impactos relevantes" pero hay bloques de impactos → ERROR
- "apto para presentacion"/"apto administrativamente"/"conforme para presentar" → ERROR (siempre)
- "sin condicionantes" pero hay gaps ALTA o INDETERMINADO en otros bloques → ERROR

---

## Estados del resultado

| Estado | Descripcion |
|--------|-------------|
| `COHERENTE` | Sin incidencias |
| `CON_OBSERVACIONES` | Solo warnings |
| `INCOHERENTE` | Al menos un ERROR |
| `SIN_DATOS` | Sin bloques markdown para revisar |

`is_valid()` devuelve True solo si no hay ERRORs.
`administrative_ready` siempre False.

---

## API implementada

```python
def normalize_block_text(text: str) -> str: ...
def detect_block_family(path_or_name: str) -> str: ...
def load_markdown_blocks(expediente_path: str | Path) -> dict[str, str]: ...

def validate_red_natura_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...
def validate_biodiversity_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...
def validate_heritage_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...
def validate_measure_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...
def validate_assumption_consistency(
    blocks: dict[str, str],
    assumptions_registry: AsuncionTestRegistry | None = None,
) -> list[BlockConsistencyIssue]: ...
def validate_pva_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...
def validate_conclusion_consistency(blocks: dict[str, str]) -> list[BlockConsistencyIssue]: ...

def validate_block_consistency(
    blocks: dict[str, str],
    assumptions_registry: AsuncionTestRegistry | None = None,
) -> BlockConsistencyResult: ...

def validate_block_consistency_from_files(
    expediente_path: str | Path,
) -> BlockConsistencyResult: ...

def build_block_consistency_report_markdown(result: BlockConsistencyResult) -> str: ...
def write_block_consistency_outputs(
    result: BlockConsistencyResult,
    output_dir: str | Path,
) -> tuple[Path, Path]: ...
```

---

## CLI audit-block-consistency

```
python run_expediente.py <expediente> audit-block-consistency [--write]
```

**Sin `--write`:**
- Carga todos los .md de `bloques/`, `inventario/`, `impactos/`, `auditoria/`.
- Carga `control_interno/asunciones_test.json` si existe.
- Ejecuta todos los validadores.
- Imprime el `summary()` del resultado.
- exit 0 si `result.is_valid()`, exit 1 si hay ERRORs.

**Con `--write`:**
- Ademas, escribe:
  - `auditoria/block_consistency_result.json`
  - `auditoria/block_consistency_result.md`

Los informes `auditoria/*.md` generados no se escanean como bloques del
Documento Ambiental, para evitar que el validador se autogenere incoherencias
citando sus propias incidencias.

**No modifica** los bloques del expediente.

---

## Como ejecutar los tests

```bash
venv\Scripts\python -m unittest tests.test_block_consistency_validator
venv\Scripts\python -m unittest discover -s tests
```

121 tests en `test_block_consistency_validator.py`, 0 fallos esperados.

---

*RD-04 completado 2026-05-17. EIA-Agent v2.1 — Productizacion P1.*
