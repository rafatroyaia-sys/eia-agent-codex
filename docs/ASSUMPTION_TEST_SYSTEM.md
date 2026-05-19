# ASSUMPTION_TEST_SYSTEM.md — OB-05

**Modulo:** `src/eia_agent/core/assumption_test_system.py`  
**CLI:** `python run_expediente.py <expediente> assumptions-summary [--write]`  
**Tests:** `tests/test_assumption_test_system.py` (110 tests OK)

---

## Que hace OB-05

El Sistema AT (Asunciones de Test) permite registrar, validar y consultar
asunciones provisionales que desbloquean el trabajo tecnico cuando falta
informacion real.

Una **Asuncion de Test (AT)** es un dato provisional aceptado explicitamente
para poder avanzar en el expediente en modo gabinete. Su presencia siempre
bloquea la aptitud administrativa: el expediente no puede presentarse mientras
existan ATs activas.

---

## Que NO hace OB-05

- **No confirma datos.** Una AT no convierte ningun campo a estado CONFIRMADO.
- **No resuelve gaps.** La AT documenta la asuncion; el gap sigue abierto.
- **No declara aptitud administrativa.** Solo el organo ambiental emite el IIA.
- **No modifica impactos ni medidas.** La AT es un registro documental.
- **No genera nuevos impactos, medidas ni PVA automaticamente.**
- **No usa IA, no consulta webs, no llama a APIs.**

---

## Conceptos clave

### Gap vs Contrad iccion vs AT

| Concepto | Que es | Quien lo crea |
|----------|--------|---------------|
| **GAP** | Dato necesario ausente o incompleto | Sistema (inventario, gate) |
| **CONT** | Contradiccion entre dos fuentes sobre el mismo dato | Sistema (AG-4, OB-02) |
| **AT** | Asuncion provisional que desbloquea trabajo | Tecnico (manual o via factory) |

Una AT puede resolver un GAP o un CONT, pero no los cierra: el gap sigue
siendo un gap y la contradiccion sigue siendo una contradiccion hasta que
se aportan datos reales.

### Por que una AT activa bloquea la aptitud administrativa

Porque el expediente contiene datos que no estan confirmados ni declarados
por el promotor, sino asumidos provisionalmente por el tecnico para poder
avanzar en modo test. Presentar un expediente con ATs activas seria declarar
como cierto algo que no ha sido probado.

### Estados de una AT

| Estado | Descripcion |
|--------|-------------|
| `ACTIVA` | En uso, bloquea aptitud administrativa |
| `RESUELTA` | El dato real fue aportado; la AT queda archivada |
| `DESCARTADA` | La AT fue descartada (el gap/cont se resolvio de otro modo) |
| `SUSTITUIDA` | Reemplazada por otra AT mas precisa |

Solo las ATs en estado `ACTIVA` bloquean la aptitud administrativa.

---

## API implementada

### Constantes

```python
ASSUMPTION_STATUS: list[str]   # ACTIVA, RESUELTA, DESCARTADA, SUSTITUIDA
ASSUMPTION_SCOPE: list[str]    # OBJETO, INVENTARIO, IMPACTO, MEDIDA, PVA,
                               # CARTOGRAFIA, CLIMA, NORMATIVA, AUDITORIA,
                               # BLOQUE_REDACCION, GLOBAL
ASSUMPTION_SEVERITY: list[str] # BLOQUEANTE_REAL, ALTA, MEDIA, BAJA
```

### Dataclass AsuncionTest

```python
@dataclass
class AsuncionTest:
    at_id: str                          # AT-001, AT-002...
    title: str
    description: str
    scope: str                          # de ASSUMPTION_SCOPE
    severity: str                       # de ASSUMPTION_SEVERITY
    status: str                         # de ASSUMPTION_STATUS
    justification: str
    impide_aptitud_administrativa: bool # siempre True en ACTIVA
    created_from: str = ""
    resolves_ref: str | None = None     # CONT-NNN o GAP-NNN
    linked_refs: list[str] = []
    affected_phases: list[str] = []
    affected_outputs: list[str] = []
    notes: list[str] = []
    warnings: list[str] = []

    def validate(self) -> list[str]: ...
    def is_active(self) -> bool: ...
    def blocks_administrative_submission(self) -> bool: ...
    def to_dict(self) -> dict: ...
    def summary(self) -> str: ...
```

### Dataclass AsuncionTestRegistry

```python
@dataclass
class AsuncionTestRegistry:
    expediente_id: str
    assumptions: list[AsuncionTest] = []
    warnings: list[str] = []
    notes: list[str] = []

    def active_assumptions(self) -> list[AsuncionTest]: ...
    def resolved_assumptions(self) -> list[AsuncionTest]: ...
    def blocks_administrative_submission(self) -> bool: ...
    def by_scope(self, scope: str) -> list[AsuncionTest]: ...
    def by_ref(self, ref: str) -> list[AsuncionTest]: ...
    def validate(self) -> list[str]: ...
    def to_dict(self) -> dict: ...
    def summary(self) -> str: ...
```

### Funciones de creacion

```python
def create_assumption_from_gap(
    at_id: str,
    gap_id: str,
    description: str,
    scope: str,
    severity: str = "ALTA",
    justification: str = "",
    affected_phases: list[str] | None = None,
) -> AsuncionTest: ...

def create_assumption_from_cont(
    at_id: str,
    cont_id: str,
    description: str,
    scope: str,
    severity: str = "ALTA",
    justification: str = "",
    affected_phases: list[str] | None = None,
) -> AsuncionTest: ...
```

### Funciones de I/O

```python
def load_assumptions_registry(path: str | Path) -> AsuncionTestRegistry: ...
# Si el archivo no existe → registry vacio
# Si JSON corrupto → ValueError

def write_assumptions_registry(
    registry: AsuncionTestRegistry,
    output_path: str | Path,
) -> Path: ...
```

### Funciones de consulta y reporte

```python
def extract_active_assumption_refs(registry: AsuncionTestRegistry) -> list[str]: ...
# Devuelve at_id + resolves_ref + linked_refs de ATs activas

def build_assumptions_markdown(registry: AsuncionTestRegistry) -> str: ...
# 5 secciones: Resumen, Activas, Resueltas, Efecto admin, Referencias

def assumptions_block_administrative_submission(
    expediente_path: str | Path,
) -> bool: ...
# Lee control_interno/asunciones_test.json; False si no existe o JSON invalido
```

---

## Reglas de validacion (AsuncionTest.validate)

| Regla | Condicion | Resultado |
|-------|-----------|-----------|
| at_id pattern | No cumple AT-NNN (minimo 3 digitos) | Error |
| title vacio | `title.strip() == ""` | Error |
| description vacia | `description.strip() == ""` | Error |
| scope invalido | No en ASSUMPTION_SCOPE | Error |
| severity invalida | No en ASSUMPTION_SEVERITY | Error |
| status invalido | No en ASSUMPTION_STATUS | Error |
| AT activa sin impide | ACTIVA + impide=False | Error |
| AT activa sin justification | ACTIVA + justification vacia | Error |

## Reglas de validacion (AsuncionTestRegistry.validate)

| Regla | Condicion | Resultado |
|-------|-----------|-----------|
| IDs duplicados | Dos ATs con mismo at_id | Error |
| Conflicto resolves_ref | Dos ATs activas con mismo resolves_ref | Error |
| AT individual invalida | validate() de la AT devuelve errores | Propagados |
| RESUELTA sin nota | status RESUELTA y notes vacio | WARNING: (prefijado) |

---

## Formato asunciones_test.json

```json
{
  "expediente_id": "EIA-2026-RECIMETAL-NAVE-222",
  "assumptions": [
    {
      "at_id": "AT-001",
      "title": "Asuncion provisional para GAP-FI-001-001",
      "description": "Datos climaticos no disponibles en fuentes abiertas para esta estacion.",
      "resolves_ref": "GAP-FI-001-001",
      "linked_refs": ["GAP-FI-001-001"],
      "scope": "INVENTARIO",
      "severity": "ALTA",
      "status": "ACTIVA",
      "justification": "Se asume clasificacion Koppen BWh segun datos AEMET historicos disponibles.",
      "affected_phases": ["5", "6"],
      "affected_outputs": ["inventario/FI-001_clima.md"],
      "impide_aptitud_administrativa": true,
      "created_from": "create_assumption_from_gap",
      "notes": [],
      "warnings": []
    }
  ],
  "warnings": [],
  "notes": []
}
```

El archivo se almacena en `control_interno/asunciones_test.json` del expediente.

---

## CLI assumptions-summary

```
python run_expediente.py <expediente> assumptions-summary [--write]
```

**Sin `--write`:**
- Lee `control_interno/asunciones_test.json` si existe.
- Si no existe, muestra "Sin asunciones registradas."
- Imprime el `summary()` del registry.
- Siempre exit 0 salvo JSON corrupto (exit 1).

**Con `--write`:**
- Escribe `control_interno/asunciones_test_resumen.md` con el informe completo.

**No crea asunciones** desde CLI en esta version. Las ATs se crean via codigo
o escribiendo directamente el JSON.

---

## Como ejecutar los tests

```bash
venv\Scripts\python -m unittest tests.test_assumption_test_system
venv\Scripts\python -m unittest discover -s tests
```

110 tests en `test_assumption_test_system.py`, 0 fallos esperados.

---

*OB-05 completado 2026-05-17. EIA-Agent v2.1 — Productizacion P1.*
