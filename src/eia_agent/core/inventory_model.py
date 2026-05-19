"""
inventory_model -- IV-00
Modelo base de inventario ambiental para Fase 5 EIA.

Define los tipos y funciones que representan los 16 factores ambientales
FI-001...FI-016, sus estados de evidencia, semáforos metodológicos,
necesidad de campo, gaps y preparación para valoración de impactos (Fase 6).

No genera fichas markdown.
No consulta fuentes externas.
No valora impactos.
No decide significancias de impacto.
No usa IA.

Los valores de evidence_status son compatibles con NL-05 (EvidenceState).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.evidence_state import EvidenceState

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------

FACTOR_NAMES: dict[str, str] = {
    "FI-001": "Clima",
    "FI-002": "Geología",
    "FI-003": "Suelos",
    "FI-004": "Hidrología",
    "FI-005": "Inundabilidad",
    "FI-006": "Calidad del aire",
    "FI-007": "Flora",
    "FI-008": "Fauna",
    "FI-009": "Espacios Naturales Protegidos",
    "FI-010": "Red Natura 2000",
    "FI-011": "Paisaje",
    "FI-012": "Patrimonio cultural",
    "FI-013": "Socioeconomía",
    "FI-014": "Ruido",
    "FI-015": "Cambio climático",
    "FI-016": "Riesgos naturales",
}

FACTOR_TYPES: dict[str, list[str]] = {
    "fisico": [
        "FI-001", "FI-002", "FI-003", "FI-004", "FI-005",
        "FI-006", "FI-014", "FI-015", "FI-016",
    ],
    "biologico": ["FI-007", "FI-008", "FI-009", "FI-010"],
    "perceptual": ["FI-011"],
    "socioeconomico": ["FI-012", "FI-013"],
    "integracion": [],   # reservado; ningún factor estándar actualmente
}

# Mapa inverso factor_id → tipo (construido una vez al cargar el módulo)
_FACTOR_ID_TO_TYPE: dict[str, str] = {
    fid: tipo
    for tipo, fids in FACTOR_TYPES.items()
    for fid in fids
}

# Todos los valores válidos de EvidenceState extraídos de NL-05
# Se mantienen alineados con evidence_state.py; no duplicar manualmente.
EVIDENCE_STATUS_VALUES: frozenset[str] = frozenset(e.value for e in EvidenceState)

# Semáforo de modo de obtención de datos de campo
FIELD_MODES: frozenset[str] = frozenset({
    "GABINETE_SUFICIENTE",   # datos de gabinete suficientes para EIA simplificada
    "CAMPO_RECOMENDADO",     # prospección conveniente pero no bloqueante en modo test
    "CAMPO_NECESARIO",       # sin campo no se puede valorar la afección
    "NO_CONSTA",             # no se ha podido determinar el modo necesario
})

# Semáforo de completitud del dato de inventario
INVENTORY_SEMAPHORES: frozenset[str] = frozenset({
    "VERDE",           # factor completamente caracterizado
    "VERDE_AMARILLO",  # factor mayormente caracterizado, gaps menores
    "AMARILLO",        # factor parcialmente caracterizado, gaps moderados
    "ROJO_AMARILLO",   # gaps significativos, datos insuficientes para precisión
    "ROJO",            # sin caracterización suficiente; bloquea gate 5 en producción
    "NO_CONSTA",       # factor no evaluado; bloquea siempre
})

GAP_CRITICALITIES: frozenset[str] = frozenset({"ALTA", "MEDIA", "BAJA"})
GAP_RESOLUTION_MODES: frozenset[str] = frozenset({
    "GABINETE",
    "CAMPO",
    "IRRESOLUBLE_OFFLINE",
})
GAP_STATUSES: frozenset[str] = frozenset({
    "PENDIENTE",
    "CUBIERTO",
    "CONDICIONADO",
    "DESCARTADO",
})

# Patrones de imprudencia (regla de prudencia IV-00, conforme Regla 4 CLAUDE.md)
_IMPRUDENCE_PATTERNS: tuple[str, ...] = (
    "no existe",
    "no hay",
    "inexistente",
    "sin presencia",
    "ausencia de",
    "no se detecta",
    "no se han detectado",
    "no se observa",
)


# ---------------------------------------------------------------------------
# Funciones auxiliares de validación y consulta
# ---------------------------------------------------------------------------

def validate_factor_id(factor_id: str) -> bool:
    """True solo si factor_id está en FI-001...FI-016."""
    return factor_id in FACTOR_NAMES


def validate_inventory_semaphore(value: str) -> bool:
    """True si value es un semáforo de inventario válido."""
    return value in INVENTORY_SEMAPHORES


def validate_field_mode(value: str) -> bool:
    """True si value es un modo de campo válido."""
    return value in FIELD_MODES


def factor_type_for(factor_id: str) -> str:
    """Devuelve el tipo de factor para un factor_id dado.

    Returns:
        "fisico" / "biologico" / "perceptual" / "socioeconomico" / "integracion"
        o "desconocido" si el factor_id no está en FACTOR_TYPES.
    """
    return _FACTOR_ID_TO_TYPE.get(factor_id, "desconocido")


# ---------------------------------------------------------------------------
# classify_semaphore_from_evidence
# ---------------------------------------------------------------------------

# Grupos de evidence_status por nivel de confianza operacional
_ES_CONFIRMED: frozenset[str] = frozenset({
    "CONFIRMADO_CAMPO", "CONFIRMADO_GABINETE", "CONFIRMADO",
})
_ES_HIGH_INFERRED: frozenset[str] = frozenset({"INFERIDO_TECNICO"})
_ES_INFERRED: frozenset[str] = frozenset({"INFERIDO"})
_ES_DECLARED: frozenset[str] = frozenset({"DECLARADO"})
_ES_ESTIMATED: frozenset[str] = frozenset({"ESTIMADO", "LIMITADO_ESCALA"})
_ES_PROVISIONAL: frozenset[str] = frozenset({"PROVISIONAL", "ASUNCION_TEST"})
_ES_PENDING: frozenset[str] = frozenset({"PENDIENTE_VERIFICACION", "PENDIENTE"})
_ES_TERMINAL: frozenset[str] = frozenset({"NO_CONSTA", "ERROR", "DESCARTADO"})


def classify_semaphore_from_evidence(
    evidence_status: str,
    gaps: "list[InventoryGap]",
) -> str:
    """Inferencia automática del semáforo de inventario.

    No es definitiva: puede sobreescribirse en FactorInventory.
    No reconocer evidence_status → NO_CONSTA.
    Solo gaps con status PENDIENTE o CONDICIONADO se consideran activos.
    """
    if evidence_status not in EVIDENCE_STATUS_VALUES:
        return "NO_CONSTA"
    if evidence_status in _ES_TERMINAL:
        return "NO_CONSTA"

    active = [g for g in gaps if g.status in ("PENDIENTE", "CONDICIONADO")]
    has_alta = any(g.criticality == "ALTA" for g in active)
    has_media = any(g.criticality == "MEDIA" for g in active)

    if evidence_status in _ES_CONFIRMED:
        return "VERDE" if not active else "VERDE_AMARILLO"

    if evidence_status in _ES_HIGH_INFERRED:
        if not active:
            return "VERDE_AMARILLO"
        return "AMARILLO" if has_alta else "VERDE_AMARILLO"

    if evidence_status in _ES_INFERRED:
        if not active:
            return "VERDE_AMARILLO"
        return "ROJO_AMARILLO" if (has_alta or has_media) else "VERDE_AMARILLO"

    if evidence_status in _ES_DECLARED:
        if not active:
            return "AMARILLO"
        return "ROJO_AMARILLO" if has_alta else "AMARILLO"

    if evidence_status in _ES_ESTIMATED:
        if not active:
            return "AMARILLO"
        if has_alta:
            return "ROJO"
        return "ROJO_AMARILLO" if has_media else "AMARILLO"

    if evidence_status in _ES_PROVISIONAL:
        if not active:
            return "ROJO_AMARILLO"
        return "ROJO" if has_alta else "ROJO_AMARILLO"

    if evidence_status in _ES_PENDING:
        if has_alta:
            return "ROJO"
        return "NO_CONSTA" if not active else "ROJO_AMARILLO"

    return "NO_CONSTA"


# ---------------------------------------------------------------------------
# InventoryGap
# ---------------------------------------------------------------------------

@dataclass
class InventoryGap:
    """Gap de inventario para un factor ambiental específico.

    Criterio de validación:
    - __post_init__ levanta ValueError para errores estructurales
      (criticality vacía/inválida, resolution_mode inválido, status inválido).
    - validate() devuelve lista de strings para errores semánticos
      (factor_id desconocido, campos vacíos).
    """

    gap_id: str
    factor_id: str
    field: str
    description: str
    criticality: str
    resolution_mode: str
    status: str = "PENDIENTE"

    def __post_init__(self) -> None:
        if not self.criticality:
            raise ValueError(
                f"InventoryGap.criticality no puede ser None ni vacío "
                f"(gap_id={self.gap_id!r})"
            )
        if self.criticality not in GAP_CRITICALITIES:
            raise ValueError(
                f"InventoryGap.criticality inválido: {self.criticality!r}. "
                f"Valores válidos: {sorted(GAP_CRITICALITIES)}"
            )
        if self.resolution_mode not in GAP_RESOLUTION_MODES:
            raise ValueError(
                f"InventoryGap.resolution_mode inválido: {self.resolution_mode!r}. "
                f"Valores válidos: {sorted(GAP_RESOLUTION_MODES)}"
            )
        if self.status not in GAP_STATUSES:
            raise ValueError(
                f"InventoryGap.status inválido: {self.status!r}. "
                f"Valores válidos: {sorted(GAP_STATUSES)}"
            )

    def validate(self) -> list[str]:
        """Validación semántica. Devuelve lista de warnings/errores textuales."""
        issues: list[str] = []
        if not validate_factor_id(self.factor_id):
            issues.append(
                f"factor_id inválido: {self.factor_id!r}. "
                f"Se esperaba FI-001...FI-016."
            )
        if not self.gap_id:
            issues.append("gap_id no puede estar vacío.")
        if not self.field:
            issues.append("field no puede estar vacío.")
        if not self.description:
            issues.append("description no puede estar vacía.")
        return issues

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "factor_id": self.factor_id,
            "field": self.field,
            "description": self.description,
            "criticality": self.criticality,
            "resolution_mode": self.resolution_mode,
            "status": self.status,
        }

    def summary(self) -> str:
        desc = self.description
        preview = desc[:60] + ("..." if len(desc) > 60 else "")
        return (
            f"{self.gap_id} [{self.factor_id}] {self.criticality} — "
            f"{self.field}: {preview} ({self.status})"
        )


# ---------------------------------------------------------------------------
# FactorInventory
# ---------------------------------------------------------------------------

@dataclass
class FactorInventory:
    """Inventario preoperacional de un factor ambiental.

    - factor_name y factor_type se infieren desde factor_id si no se
      proporcionan explícitamente.
    - ready_for_impact_assessment es False por defecto.
    - validate() aplica la regla de prudencia (Regla 4 CLAUDE.md) y la
      regla de coherencia semáforo/ready.
    """

    factor_id: str
    factor_name: Optional[str] = None
    factor_type: Optional[str] = None
    description: str = ""
    data_sources: list[str] = field(default_factory=list)
    evidence_status: str = "PENDIENTE"
    field_mode: str = "NO_CONSTA"
    field_mode_justification: str = ""
    inventory_semaphore: str = "NO_CONSTA"
    semaphore_justification: str = ""
    gaps: list[InventoryGap] = field(default_factory=list)
    ready_for_impact_assessment: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.factor_name is None:
            self.factor_name = FACTOR_NAMES.get(self.factor_id)
        if self.factor_type is None:
            self.factor_type = factor_type_for(self.factor_id)
        if not validate_factor_id(self.factor_id):
            self.warnings.append(
                f"factor_id no reconocido: {self.factor_id!r}. "
                f"Se esperaba FI-001...FI-016."
            )

    def validate(self) -> list[str]:
        """Validación semántica. Devuelve lista de warnings/errores textuales."""
        issues: list[str] = []

        if not validate_factor_id(self.factor_id):
            issues.append(f"factor_id inválido: {self.factor_id!r}.")

        if self.evidence_status not in EVIDENCE_STATUS_VALUES:
            issues.append(
                f"evidence_status no reconocido: {self.evidence_status!r}."
            )

        if not validate_field_mode(self.field_mode):
            issues.append(f"field_mode inválido: {self.field_mode!r}.")

        if not validate_inventory_semaphore(self.inventory_semaphore):
            issues.append(
                f"inventory_semaphore inválido: {self.inventory_semaphore!r}."
            )

        # Regla de coherencia: ready=True con semáforo bloqueante
        if self.ready_for_impact_assessment and self.inventory_semaphore in (
            "ROJO", "NO_CONSTA"
        ):
            issues.append(
                f"AVISO FUERTE: ready_for_impact_assessment=True con "
                f"inventory_semaphore={self.inventory_semaphore!r}. "
                f"No se puede valorar un factor sin información suficiente."
            )

        # Regla de prudencia: patrón de negación sin soporte de gabinete
        if self.field_mode != "GABINETE_SUFICIENTE":
            desc_lower = self.description.lower()
            for pattern in _IMPRUDENCE_PATTERNS:
                if pattern in desc_lower:
                    issues.append(
                        f"AVISO PRUDENCIA: descripción contiene '{pattern}' pero "
                        f"field_mode={self.field_mode!r}. "
                        f"No puede afirmarse ausencia sin prospección de campo "
                        f"o evidencia suficiente de gabinete. "
                        f"Usar: 'no se detecta en las fuentes consultadas'."
                    )
                    break  # un warning de prudencia por factor es suficiente

        for g in self.gaps:
            issues.extend(g.validate())

        return issues

    def to_dict(self) -> dict:
        return {
            "factor_id": self.factor_id,
            "factor_name": self.factor_name,
            "factor_type": self.factor_type,
            "description": self.description,
            "data_sources": list(self.data_sources),
            "evidence_status": self.evidence_status,
            "field_mode": self.field_mode,
            "field_mode_justification": self.field_mode_justification,
            "inventory_semaphore": self.inventory_semaphore,
            "semaphore_justification": self.semaphore_justification,
            "gaps": [g.to_dict() for g in self.gaps],
            "ready_for_impact_assessment": self.ready_for_impact_assessment,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        label_map = {
            "VERDE": "[VERDE]",
            "VERDE_AMARILLO": "[VERDE-AMARILLO]",
            "AMARILLO": "[AMARILLO]",
            "ROJO_AMARILLO": "[ROJO-AMARILLO]",
            "ROJO": "[ROJO]",
            "NO_CONSTA": "[NO CONSTA]",
        }
        sem_label = label_map.get(self.inventory_semaphore,
                                  f"[{self.inventory_semaphore}]")
        ready_label = "Listo Fase 6" if self.ready_for_impact_assessment else "Pendiente"
        gaps_alta = sum(
            1 for g in self.gaps
            if g.criticality == "ALTA" and g.status in ("PENDIENTE", "CONDICIONADO")
        )
        lines = [
            f"{self.factor_id} — {self.factor_name or '?'} {sem_label}",
            f"  Evidence: {self.evidence_status} | Campo: {self.field_mode}",
            f"  Estado: {ready_label} | Gaps ALTA: {gaps_alta}",
        ]
        for w in self.warnings[:3]:
            lines.append(f"  AVISO: {w[:80]}")
        return "\n".join(lines)

    def gap_count_by_criticality(self) -> dict[str, int]:
        """Cuenta gaps activos (PENDIENTE + CONDICIONADO) por criticidad."""
        result: dict[str, int] = {"ALTA": 0, "MEDIA": 0, "BAJA": 0}
        for g in self.gaps:
            if g.status in ("PENDIENTE", "CONDICIONADO") and g.criticality in result:
                result[g.criticality] += 1
        return result

    def has_critical_gaps(self) -> bool:
        """True si hay algún gap ALTA pendiente o condicionado."""
        return any(
            g.criticality == "ALTA" and g.status in ("PENDIENTE", "CONDICIONADO")
            for g in self.gaps
        )

    def needs_field_work(self) -> bool:
        """True si field_mode requiere o recomienda trabajo de campo."""
        return self.field_mode in ("CAMPO_RECOMENDADO", "CAMPO_NECESARIO")


# ---------------------------------------------------------------------------
# InventorySummary
# ---------------------------------------------------------------------------

@dataclass
class InventorySummary:
    """Resumen consolidado del inventario ambiental de un expediente.

    Las métricas son propiedades derivadas calculadas en tiempo real;
    no se almacenan en el objeto para evitar inconsistencias.
    """

    expediente_id: str
    factors: list[FactorInventory]
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total_factors(self) -> int:
        return len(self.factors)

    @property
    def ready_count(self) -> int:
        return sum(1 for f in self.factors if f.ready_for_impact_assessment)

    @property
    def campo_necesario_count(self) -> int:
        return sum(1 for f in self.factors if f.field_mode == "CAMPO_NECESARIO")

    @property
    def rojo_count(self) -> int:
        return sum(1 for f in self.factors if f.inventory_semaphore == "ROJO")

    @property
    def has_critical_gaps(self) -> bool:
        return any(f.has_critical_gaps() for f in self.factors)

    @property
    def all_ready_for_phase6(self) -> bool:
        """True solo si:
        - hay exactamente 16 factores;
        - todos tienen ready_for_impact_assessment=True;
        - ningún factor tiene semáforo ROJO o NO_CONSTA;
        - no hay gaps críticos pendientes.
        """
        if len(self.factors) != 16:
            return False
        if not all(f.ready_for_impact_assessment for f in self.factors):
            return False
        if any(f.inventory_semaphore in ("ROJO", "NO_CONSTA") for f in self.factors):
            return False
        if self.has_critical_gaps:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "factors": [f.to_dict() for f in self.factors],
            "total_factors": self.total_factors,
            "ready_count": self.ready_count,
            "campo_necesario_count": self.campo_necesario_count,
            "rojo_count": self.rojo_count,
            "has_critical_gaps": self.has_critical_gaps,
            "all_ready_for_phase6": self.all_ready_for_phase6,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Inventario ambiental — {self.expediente_id}",
            f"  Factores       : {self.total_factors}/16",
            f"  Listos F6      : {self.ready_count}/{self.total_factors}",
            f"  Campo necesario: {self.campo_necesario_count}",
            f"  Semaforo ROJO  : {self.rojo_count}",
            f"  Gaps criticos  : {'SI' if self.has_critical_gaps else 'NO'}",
            f"  Listo Fase 6   : {'SI' if self.all_ready_for_phase6 else 'NO'}",
        ]
        for w in self.warnings[:5]:
            lines.append(f"  AVISO: {w[:80]}")
        return "\n".join(lines)

    def factors_by_semaphore(self) -> dict[str, list[str]]:
        """Agrupa factor_ids por semáforo de inventario."""
        result: dict[str, list[str]] = {s: [] for s in INVENTORY_SEMAPHORES}
        for f in self.factors:
            result.setdefault(f.inventory_semaphore, []).append(f.factor_id)
        return result

    def factors_needing_field_work(self) -> list[str]:
        """Lista de factor_ids que necesitan o recomiendan trabajo de campo."""
        return [
            f.factor_id for f in self.factors
            if f.field_mode in ("CAMPO_RECOMENDADO", "CAMPO_NECESARIO")
        ]

    def missing_factor_ids(self) -> list[str]:
        """Factor IDs canónicos FI-001...FI-016 ausentes en este resumen."""
        present = {f.factor_id for f in self.factors}
        return [fid for fid in sorted(FACTOR_NAMES.keys()) if fid not in present]

    def validate(self) -> list[str]:
        """Validación del resumen. Devuelve lista de warnings/errores."""
        issues: list[str] = []
        missing = self.missing_factor_ids()
        if missing:
            issues.append(
                f"Faltan {len(missing)} factor(es) canonico(s): {', '.join(missing)}"
            )
        if self.total_factors != 16:
            issues.append(
                f"Se esperan 16 factores, hay {self.total_factors}."
            )
        for f in self.factors:
            for issue in f.validate():
                issues.append(f"[{f.factor_id}] {issue}")
        return issues


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def build_empty_factor_inventory(factor_id: str) -> FactorInventory:
    """Crea un FactorInventory vacío con semáforos NO_CONSTA y PENDIENTE.

    Raises:
        ValueError: si factor_id no está en FI-001...FI-016.
    """
    if not validate_factor_id(factor_id):
        raise ValueError(
            f"factor_id desconocido: {factor_id!r}. "
            f"Valores validos: {sorted(FACTOR_NAMES.keys())}"
        )
    return FactorInventory(
        factor_id=factor_id,
        inventory_semaphore="NO_CONSTA",
        field_mode="NO_CONSTA",
        evidence_status="PENDIENTE",
        ready_for_impact_assessment=False,
    )


def build_all_empty_factors() -> list[FactorInventory]:
    """Devuelve los 16 factores FI-001...FI-016 vacíos, ordenados."""
    return [build_empty_factor_inventory(fid) for fid in sorted(FACTOR_NAMES.keys())]


def build_inventory_summary(
    expediente_id: str,
    factors: list[FactorInventory],
) -> InventorySummary:
    """Construye un InventorySummary a partir de una lista de FactorInventory.

    Añade warning automático si faltan factores canónicos.
    """
    present = {f.factor_id for f in factors}
    missing = [fid for fid in sorted(FACTOR_NAMES.keys()) if fid not in present]
    warns: list[str] = []
    if missing:
        warns.append(
            f"Inventario incompleto: faltan {len(missing)} factor(es): "
            f"{', '.join(missing)}"
        )
    return InventorySummary(
        expediente_id=expediente_id,
        factors=factors,
        warnings=warns,
    )
