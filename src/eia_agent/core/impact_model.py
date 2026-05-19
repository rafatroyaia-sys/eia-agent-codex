"""
impact_model -- IM-00
Modelo base de impactos, acciones, factores receptores, medidas y PVA para Fase 6 EIA.

Define los tipos y funciones que representan:
- Acciones del proyecto (ProjectAction)
- Factores receptores (ReceptorFactor) — derivados de los 16 factores FI-001...FI-016
- Impactos ambientales (EnvironmentalImpact)
- Atributos de valoración tipo Conesa (ConesaAttributes)
- Medidas ambientales (MitigationMeasure)
- Programas de vigilancia ambiental (PVAProgram)
- Paquete estructurado de Fase 6 (Phase6Model)

No valora impactos (no calcula índice de importancia Conesa — eso es IM-01).
No genera medidas reales.
No genera PVA real.
No consulta fuentes externas.
No usa IA.
No escribe archivos.

Los tipos de este módulo son exclusivamente de Fase 6.
No deben exportarse ni usarse para el inventario ambiental (Fase 5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.inventory_model import InventorySummary

# ---------------------------------------------------------------------------
# Constantes de dominio (exclusivas de Fase 6)
# ---------------------------------------------------------------------------

ACTION_TYPES: frozenset[str] = frozenset({
    "OPERACION",
    "AUXILIAR",
    "TRANSPORTE",
    "ALMACENAMIENTO",
    "MANTENIMIENTO",
    "CESE",
    "OTRO",
})

# Mapping factores receptores Fase 6 → factores inventario Fase 5
RECEPTOR_FACTOR_IDS: dict[str, str] = {
    "FR-001": "FI-001",  # Clima
    "FR-002": "FI-002",  # Geología
    "FR-003": "FI-003",  # Suelos
    "FR-004": "FI-004",  # Hidrología
    "FR-005": "FI-005",  # Inundabilidad
    "FR-006": "FI-006",  # Calidad del aire
    "FR-007": "FI-007",  # Flora
    "FR-008": "FI-008",  # Fauna
    "FR-009": "FI-009",  # Espacios Naturales Protegidos
    "FR-010": "FI-010",  # Red Natura 2000
    "FR-011": "FI-011",  # Paisaje
    "FR-012": "FI-012",  # Patrimonio cultural
    "FR-013": "FI-013",  # Socioeconomía
    "FR-014": "FI-014",  # Ruido
    "FR-015": "FI-015",  # Cambio climático
    "FR-016": "FI-016",  # Riesgos naturales
}

# Reverse mapping FI → FR (construido una vez al cargar el módulo)
_INVENTORY_TO_RECEPTOR: dict[str, str] = {v: k for k, v in RECEPTOR_FACTOR_IDS.items()}

# Nombres canónicos de factores receptores
RECEPTOR_FACTOR_NAMES: dict[str, str] = {
    "FR-001": "Clima",
    "FR-002": "Geología",
    "FR-003": "Suelos",
    "FR-004": "Hidrología",
    "FR-005": "Inundabilidad",
    "FR-006": "Calidad del aire",
    "FR-007": "Flora",
    "FR-008": "Fauna",
    "FR-009": "Espacios Naturales Protegidos",
    "FR-010": "Red Natura 2000",
    "FR-011": "Paisaje",
    "FR-012": "Patrimonio cultural",
    "FR-013": "Socioeconomía",
    "FR-014": "Ruido",
    "FR-015": "Cambio climático",
    "FR-016": "Riesgos naturales",
}

IMPACT_NATURES: frozenset[str] = frozenset({
    "NEGATIVO",
    "POSITIVO",
    "MIXTO",
    "INDETERMINADO",
})

IMPACT_STATUS: frozenset[str] = frozenset({
    "IDENTIFICADO",
    "VALORADO",
    "INDETERMINADO",
    "DESCARTADO_JUSTIFICADO",
    "PENDIENTE_DATOS",
})

# Fase 6 únicamente — no usar para inventario ambiental
IMPACT_SIGNIFICANCE: frozenset[str] = frozenset({
    "COMPATIBLE",
    "MODERADO",
    "SEVERO",
    "CRITICO",
    "POSITIVO_MODERADO",
    "POSITIVO_NOTABLE",
    "INDETERMINADO",
    "NO_VALORADO",
})

# Significancias que indican afección negativa alta y requieren medidas
_HIGH_NEGATIVE_SIGNIFICANCES: frozenset[str] = frozenset({"SEVERO", "CRITICO"})

MEASURE_TYPES: frozenset[str] = frozenset({
    "PREVENTIVA",
    "CORRECTORA",
    "PROTECTORA",
    "COMPENSATORIA",
    "DIAGNOSTICA",   # AG09-13: no cuenta como reductora de significancia
    "DOCUMENTAL",
    "PVA",
    "PRL_NO_EIA",    # AG09-14: no reduce significancia ambiental
})

MEASURE_STATUS: frozenset[str] = frozenset({
    "PROPUESTA",
    "CONDICION_PREVIA",
    "CONDICIONADA",
    "NO_EIA",
    "DESCARTADA",
})

PVA_FREQUENCIES: frozenset[str] = frozenset({
    "DIARIA",
    "SEMANAL",
    "MENSUAL",
    "TRIMESTRAL",
    "SEMESTRAL",
    "ANUAL",
    "UNICA_PREVIA",
    "CONDICIONAL",
    "INMEDIATA",
})

CONESA_ATTRIBUTE_NAMES: tuple[str, ...] = (
    "intensidad",
    "extension",
    "momento",
    "persistencia",
    "reversibilidad",
    "sinergia",
    "acumulacion",
    "efecto",
    "periodicidad",
    "recuperabilidad",
)

# Tipos de medida que no se contabilizan como reductoras de significancia
_NON_REDUCING_MEASURE_TYPES: frozenset[str] = frozenset({"DIAGNOSTICA", "PRL_NO_EIA"})

# Tipos de medida que no requieren impacto objetivo obligatorio
_NO_TARGET_REQUIRED_TYPES: frozenset[str] = frozenset({
    "DOCUMENTAL", "DIAGNOSTICA", "PRL_NO_EIA", "PVA",
})

# Patrones de ID válidos
_AC_ID_RE = re.compile(r"^AC-\d{3,}$")
_FR_ID_RE = re.compile(r"^FR-\d{3,}$")
_FI_ID_RE = re.compile(r"^FI-\d{3,}$")
_IMP_ID_RE = re.compile(r"^IMP-\d{3,}$")
_MED_ID_RE = re.compile(r"^MED-\d{3,}$")
_PVA_ID_RE = re.compile(r"^PVA-\d{3,}$")


# ---------------------------------------------------------------------------
# ConesaAttributes
# ---------------------------------------------------------------------------

@dataclass
class ConesaAttributes:
    """Atributos de valoración según metodología Conesa-Fernández Vítora.

    Cada atributo es int (valor asignado) o None (pendiente de valoración).
    Los rangos válidos se verifican en validate(), no en construcción.

    La fórmula de importancia I = ±(3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc)
    y la clasificación de significancia NO se calculan en este módulo — eso es IM-01.
    """

    intensidad: Optional[int] = None
    extension: Optional[int] = None
    momento: Optional[int] = None
    persistencia: Optional[int] = None
    reversibilidad: Optional[int] = None
    sinergia: Optional[int] = None
    acumulacion: Optional[int] = None
    efecto: Optional[int] = None
    periodicidad: Optional[int] = None
    recuperabilidad: Optional[int] = None

    def is_complete(self) -> bool:
        """True si todos los 10 atributos tienen valor asignado."""
        return all(getattr(self, attr) is not None for attr in CONESA_ATTRIBUTE_NAMES)

    def missing_attributes(self) -> list[str]:
        """Lista de nombres de atributos sin valor (None)."""
        return [attr for attr in CONESA_ATTRIBUTE_NAMES if getattr(self, attr) is None]

    def validate(self) -> list[str]:
        """Validación de rangos. Devuelve lista de errores textuales."""
        issues: list[str] = []
        for attr in CONESA_ATTRIBUTE_NAMES:
            value = getattr(self, attr)
            if value is not None:
                if not isinstance(value, int) or value <= 0:
                    issues.append(
                        f"ConesaAttributes.{attr}: el valor debe ser un entero "
                        f"positivo (recibido: {value!r})."
                    )
        return issues

    def to_dict(self) -> dict:
        return {attr: getattr(self, attr) for attr in CONESA_ATTRIBUTE_NAMES}


# ---------------------------------------------------------------------------
# ProjectAction
# ---------------------------------------------------------------------------

@dataclass
class ProjectAction:
    """Acción del proyecto que genera presión ambiental en Fase 6.

    El action_id sigue el patrón AC-001, AC-002...
    Corresponde a operaciones del promotor (R12/R13 etc.) o actividades auxiliares.
    """

    action_id: str
    name: str
    description: str = ""
    action_type: str = "OTRO"
    operation_code: Optional[str] = None
    source_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not _AC_ID_RE.match(self.action_id):
            issues.append(
                f"action_id inválido: {self.action_id!r}. "
                f"Se esperaba patrón AC-NNN (p.ej. AC-001)."
            )
        if not self.name or not self.name.strip():
            issues.append(
                f"ProjectAction.name no puede estar vacío "
                f"(action_id={self.action_id!r})."
            )
        if self.action_type not in ACTION_TYPES:
            issues.append(
                f"action_type inválido: {self.action_type!r}. "
                f"Valores válidos: {sorted(ACTION_TYPES)}"
            )
        return issues

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "name": self.name,
            "description": self.description,
            "action_type": self.action_type,
            "operation_code": self.operation_code,
            "source_refs": list(self.source_refs),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        return f"{self.action_id} [{self.action_type}] — {self.name}"


# ---------------------------------------------------------------------------
# ReceptorFactor
# ---------------------------------------------------------------------------

@dataclass
class ReceptorFactor:
    """Factor ambiental receptor de impactos en Fase 6.

    Corresponde 1:1 con los 16 factores FI-001...FI-016 del inventario.
    El receptor_id sigue el patrón FR-001...FR-016.

    Se crea a partir del InventorySummary de Fase 5 (ver helper
    build_receptor_factors_from_inventory), o manualmente para pruebas.
    """

    receptor_id: str
    inventory_factor_id: str
    name: str
    inventory_semaphore: str = "NO_CONSTA"
    ready_from_inventory: bool = False
    critical_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not _FR_ID_RE.match(self.receptor_id):
            issues.append(
                f"receptor_id inválido: {self.receptor_id!r}. "
                f"Se esperaba patrón FR-NNN (p.ej. FR-001)."
            )
        if not _FI_ID_RE.match(self.inventory_factor_id):
            issues.append(
                f"inventory_factor_id inválido: {self.inventory_factor_id!r}. "
                f"Se esperaba patrón FI-NNN (p.ej. FI-001)."
            )
        # Si no está listo y no hay notas ni critical_gaps, no hay explicación visible
        if not self.ready_from_inventory and not self.notes and not self.critical_gaps:
            issues.append(
                f"AVISO [{self.receptor_id}]: ready_from_inventory=False pero "
                f"ni notes ni critical_gaps documentan el motivo. "
                f"Añadir nota o gap para visibilidad en Fase 6."
            )
        return issues

    def to_dict(self) -> dict:
        return {
            "receptor_id": self.receptor_id,
            "inventory_factor_id": self.inventory_factor_id,
            "name": self.name,
            "inventory_semaphore": self.inventory_semaphore,
            "ready_from_inventory": self.ready_from_inventory,
            "critical_gaps": list(self.critical_gaps),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        ready_label = "Listo" if self.ready_from_inventory else "Pendiente"
        return (
            f"{self.receptor_id} → {self.inventory_factor_id} "
            f"[{self.inventory_semaphore}] — {self.name} ({ready_label})"
        )


# ---------------------------------------------------------------------------
# EnvironmentalImpact
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentalImpact:
    """Registro de un impacto ambiental identificado en Fase 6.

    El impact_id sigue el patrón IMP-001, IMP-002...

    La valoración Conesa (significance_without_measures, significance_with_measures)
    no se calcula en este módulo; se asigna en IM-01.

    Regla de no compensación: un impacto POSITIVO no compensa uno NEGATIVO.
    Cada impacto se registra y evalúa de forma independiente.
    """

    impact_id: str
    action_id: str
    receptor_id: str
    name: str
    description: str = ""
    nature: str = "INDETERMINADO"
    status: str = "PENDIENTE_DATOS"
    significance_without_measures: str = "NO_VALORADO"
    significance_with_measures: str = "NO_VALORADO"
    conesa_attributes: ConesaAttributes = field(default_factory=ConesaAttributes)
    data_gaps: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    measure_ids: list[str] = field(default_factory=list)
    pva_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        issues: list[str] = []

        if not _IMP_ID_RE.match(self.impact_id):
            issues.append(
                f"impact_id inválido: {self.impact_id!r}. "
                f"Se esperaba patrón IMP-NNN (p.ej. IMP-001)."
            )
        if not _AC_ID_RE.match(self.action_id):
            issues.append(
                f"action_id inválido: {self.action_id!r}. "
                f"Se esperaba patrón AC-NNN."
            )
        if not _FR_ID_RE.match(self.receptor_id):
            issues.append(
                f"receptor_id inválido: {self.receptor_id!r}. "
                f"Se esperaba patrón FR-NNN."
            )
        if self.nature not in IMPACT_NATURES:
            issues.append(
                f"nature inválida: {self.nature!r}. "
                f"Valores válidos: {sorted(IMPACT_NATURES)}"
            )
        if self.status not in IMPACT_STATUS:
            issues.append(
                f"status inválido: {self.status!r}. "
                f"Valores válidos: {sorted(IMPACT_STATUS)}"
            )
        if self.significance_without_measures not in IMPACT_SIGNIFICANCE:
            issues.append(
                f"significance_without_measures inválida: "
                f"{self.significance_without_measures!r}. "
                f"Valores válidos: {sorted(IMPACT_SIGNIFICANCE)}"
            )
        if self.significance_with_measures not in IMPACT_SIGNIFICANCE:
            issues.append(
                f"significance_with_measures inválida: "
                f"{self.significance_with_measures!r}. "
                f"Valores válidos: {sorted(IMPACT_SIGNIFICANCE)}"
            )

        # Regla de coherencia: VALORADO con atributos Conesa incompletos
        if self.status == "VALORADO" and not self.conesa_attributes.is_complete():
            missing = self.conesa_attributes.missing_attributes()
            issues.append(
                f"ERROR [{self.impact_id}]: status=VALORADO pero atributos Conesa "
                f"incompletos. Atributos pendientes: {', '.join(missing)}."
            )

        # Regla metodológica: significancia alta sin medidas
        if (
            self.significance_without_measures in _HIGH_NEGATIVE_SIGNIFICANCES
            and not self.measure_ids
        ):
            issues.append(
                f"AVISO [{self.impact_id}]: significance_without_measures="
                f"{self.significance_without_measures!r} sin medidas asignadas. "
                f"Un impacto {self.significance_without_measures} debe tener "
                f"medidas correctoras o preventivas."
            )

        # Validación de atributos Conesa
        issues.extend(self.conesa_attributes.validate())

        return issues

    def to_dict(self) -> dict:
        return {
            "impact_id": self.impact_id,
            "action_id": self.action_id,
            "receptor_id": self.receptor_id,
            "name": self.name,
            "description": self.description,
            "nature": self.nature,
            "status": self.status,
            "significance_without_measures": self.significance_without_measures,
            "significance_with_measures": self.significance_with_measures,
            "conesa_attributes": self.conesa_attributes.to_dict(),
            "data_gaps": list(self.data_gaps),
            "source_refs": list(self.source_refs),
            "measure_ids": list(self.measure_ids),
            "pva_ids": list(self.pva_ids),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        return (
            f"{self.impact_id} [{self.nature}] {self.action_id}→{self.receptor_id} "
            f"— {self.name} "
            f"(sin med: {self.significance_without_measures}; "
            f"con med: {self.significance_with_measures})"
        )

    def is_indeterminate(self) -> bool:
        """True si la naturaleza o alguna significancia es INDETERMINADO."""
        return (
            self.nature == "INDETERMINADO"
            or self.significance_without_measures == "INDETERMINADO"
            or self.significance_with_measures == "INDETERMINADO"
        )

    def requires_measures(self) -> bool:
        """True si la significancia sin medidas indica afección negativa alta."""
        return self.significance_without_measures in _HIGH_NEGATIVE_SIGNIFICANCES


# ---------------------------------------------------------------------------
# MitigationMeasure
# ---------------------------------------------------------------------------

@dataclass
class MitigationMeasure:
    """Medida ambiental de prevención, corrección, compensación o vigilancia.

    El measure_id sigue el patrón MED-001, MED-002...

    Reglas metodológicas aplicadas en validate():
    - DIAGNOSTICA no puede actuar como reductora de significancia (AG09-13).
    - PRL_NO_EIA no puede estar en la tabla de impacto-medida EIA (AG09-14).
    - PRL_NO_EIA debe indicarse explícitamente con is_prl_only=True.
    """

    measure_id: str
    name: str
    description: str = ""
    measure_type: str = "PREVENTIVA"
    status: str = "PROPUESTA"
    target_impact_ids: list[str] = field(default_factory=list)
    is_diagnostic: bool = False
    is_prl_only: bool = False
    condition_before_submission: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        issues: list[str] = []

        if not _MED_ID_RE.match(self.measure_id):
            issues.append(
                f"measure_id inválido: {self.measure_id!r}. "
                f"Se esperaba patrón MED-NNN (p.ej. MED-001)."
            )
        if not self.name or not self.name.strip():
            issues.append(
                f"MitigationMeasure.name no puede estar vacío "
                f"(measure_id={self.measure_id!r})."
            )
        if self.measure_type not in MEASURE_TYPES:
            issues.append(
                f"measure_type inválido: {self.measure_type!r}. "
                f"Valores válidos: {sorted(MEASURE_TYPES)}"
            )
        if self.status not in MEASURE_STATUS:
            issues.append(
                f"status inválido: {self.status!r}. "
                f"Valores válidos: {sorted(MEASURE_STATUS)}"
            )

        # AG09-14: coherencia is_prl_only con measure_type
        if self.is_prl_only and self.measure_type != "PRL_NO_EIA":
            issues.append(
                f"AVISO [{self.measure_id}]: is_prl_only=True pero "
                f"measure_type={self.measure_type!r}. "
                f"Una medida PRL debe declarar measure_type='PRL_NO_EIA'."
            )

        # AG09-13: coherencia is_diagnostic con measure_type
        if self.is_diagnostic and self.measure_type != "DIAGNOSTICA":
            issues.append(
                f"AVISO [{self.measure_id}]: is_diagnostic=True pero "
                f"measure_type={self.measure_type!r}. "
                f"Inconsistencia: is_diagnostic debe coincidir con "
                f"measure_type='DIAGNOSTICA'."
            )

        # Medida reductora sin impacto objetivo
        if not self.target_impact_ids and self.measure_type not in _NO_TARGET_REQUIRED_TYPES:
            issues.append(
                f"AVISO [{self.measure_id}]: target_impact_ids vacío para "
                f"medida de tipo {self.measure_type!r}. "
                f"Una medida reductora debe vincularse a al menos un impacto."
            )

        return issues

    def to_dict(self) -> dict:
        return {
            "measure_id": self.measure_id,
            "name": self.name,
            "description": self.description,
            "measure_type": self.measure_type,
            "status": self.status,
            "target_impact_ids": list(self.target_impact_ids),
            "is_diagnostic": self.is_diagnostic,
            "is_prl_only": self.is_prl_only,
            "condition_before_submission": self.condition_before_submission,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        flags = []
        if self.is_diagnostic:
            flags.append("DIAGNÓSTICA")
        if self.is_prl_only:
            flags.append("PRL")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        return (
            f"{self.measure_id} [{self.measure_type}]{flag_str} — "
            f"{self.name} ({self.status})"
        )


# ---------------------------------------------------------------------------
# PVAProgram
# ---------------------------------------------------------------------------

@dataclass
class PVAProgram:
    """Programa de Vigilancia Ambiental para un factor e impacto específicos.

    El pva_id sigue el patrón PVA-001, PVA-002...
    El factor_id sigue el patrón FI-001...FI-016 (factor del inventario).
    """

    pva_id: str
    name: str
    factor_id: str
    indicator: str
    threshold: str = ""
    frequency: str = "CONDICIONAL"
    target_impact_ids: list[str] = field(default_factory=list)
    target_measure_ids: list[str] = field(default_factory=list)
    responsible: str = ""
    records: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        issues: list[str] = []

        if not _PVA_ID_RE.match(self.pva_id):
            issues.append(
                f"pva_id inválido: {self.pva_id!r}. "
                f"Se esperaba patrón PVA-NNN (p.ej. PVA-001)."
            )
        if not _FI_ID_RE.match(self.factor_id):
            issues.append(
                f"factor_id inválido: {self.factor_id!r}. "
                f"Se esperaba patrón FI-NNN (p.ej. FI-001)."
            )
        if not self.indicator or not self.indicator.strip():
            issues.append(
                f"PVAProgram.indicator no puede estar vacío "
                f"(pva_id={self.pva_id!r})."
            )
        if self.frequency not in PVA_FREQUENCIES:
            issues.append(
                f"frequency inválida: {self.frequency!r}. "
                f"Valores válidos: {sorted(PVA_FREQUENCIES)}"
            )

        # Avisos no bloqueantes
        if not self.threshold or not self.threshold.strip():
            issues.append(
                f"AVISO [{self.pva_id}]: threshold vacío. Se recomienda "
                f"definir un umbral de alerta para el indicador."
            )
        if not self.responsible or not self.responsible.strip():
            issues.append(
                f"AVISO [{self.pva_id}]: responsible vacío. Se recomienda "
                f"asignar un responsable de seguimiento."
            )

        return issues

    def to_dict(self) -> dict:
        return {
            "pva_id": self.pva_id,
            "name": self.name,
            "factor_id": self.factor_id,
            "indicator": self.indicator,
            "threshold": self.threshold,
            "frequency": self.frequency,
            "target_impact_ids": list(self.target_impact_ids),
            "target_measure_ids": list(self.target_measure_ids),
            "responsible": self.responsible,
            "records": list(self.records),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        indicator_preview = self.indicator[:60] + ("..." if len(self.indicator) > 60 else "")
        return (
            f"{self.pva_id} [{self.factor_id}] {self.frequency} — "
            f"{self.name}: {indicator_preview}"
        )


# ---------------------------------------------------------------------------
# Phase6Model
# ---------------------------------------------------------------------------

@dataclass
class Phase6Model:
    """Paquete estructurado de Fase 6: acciones, receptores, impactos, medidas, PVA.

    Contenedor canónico de salida de Fase 6.
    No evalúa gate administrativo.
    No calcula significancias.

    Regla de no compensación (validate() la detecta si es comprobable):
    Un impacto positivo no puede compensar uno negativo.
    Cada impacto se registra y evalúa de forma independiente.
    """

    expediente_id: str
    actions: list[ProjectAction] = field(default_factory=list)
    receptor_factors: list[ReceptorFactor] = field(default_factory=list)
    impacts: list[EnvironmentalImpact] = field(default_factory=list)
    measures: list[MitigationMeasure] = field(default_factory=list)
    pva_programs: list[PVAProgram] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validación estructural y de coherencia referencial."""
        issues: list[str] = []

        # --- Detección de IDs duplicados ---
        for id_list, label in [
            ([a.action_id for a in self.actions], "action_id"),
            ([r.receptor_id for r in self.receptor_factors], "receptor_id"),
            ([i.impact_id for i in self.impacts], "impact_id"),
            ([m.measure_id for m in self.measures], "measure_id"),
            ([p.pva_id for p in self.pva_programs], "pva_id"),
        ]:
            seen: set[str] = set()
            for id_val in id_list:
                if id_val in seen:
                    issues.append(f"ERROR: {label} duplicado: {id_val!r}.")
                seen.add(id_val)

        action_ids = {a.action_id for a in self.actions}
        receptor_ids = {r.receptor_id for r in self.receptor_factors}
        impact_ids = {i.impact_id for i in self.impacts}
        measure_ids = {m.measure_id for m in self.measures}

        # --- Impactos con referencias inexistentes ---
        for imp in self.impacts:
            if imp.action_id not in action_ids:
                issues.append(
                    f"ERROR [{imp.impact_id}]: action_id {imp.action_id!r} "
                    f"no existe en el modelo."
                )
            if imp.receptor_id not in receptor_ids:
                issues.append(
                    f"ERROR [{imp.impact_id}]: receptor_id {imp.receptor_id!r} "
                    f"no existe en el modelo."
                )

        # --- Medidas con referencias a impactos inexistentes ---
        for med in self.measures:
            for tid in med.target_impact_ids:
                if tid not in impact_ids:
                    issues.append(
                        f"ERROR [{med.measure_id}]: target_impact_id {tid!r} "
                        f"no existe en el modelo."
                    )

        # --- PVA con referencias a impactos/medidas inexistentes ---
        for pva in self.pva_programs:
            for tid in pva.target_impact_ids:
                if tid not in impact_ids:
                    issues.append(
                        f"ERROR [{pva.pva_id}]: target_impact_id {tid!r} "
                        f"no existe en el modelo."
                    )
            for tmid in pva.target_measure_ids:
                if tmid not in measure_ids:
                    issues.append(
                        f"ERROR [{pva.pva_id}]: target_measure_id {tmid!r} "
                        f"no existe en el modelo."
                    )

        # --- Impactos SEVERO/CRITICO sin medidas ---
        measures_by_imp = self.measures_by_impact()
        for imp in self.impacts:
            if imp.requires_measures():
                has_measures = bool(imp.measure_ids) or bool(measures_by_imp.get(imp.impact_id))
                if not has_measures:
                    issues.append(
                        f"AVISO [{imp.impact_id}]: significance_without_measures="
                        f"{imp.significance_without_measures!r} sin medidas asignadas."
                    )

        # --- Regla de no compensación: medida apuntando a POSITIVO y NEGATIVO ---
        nature_map = {i.impact_id: i.nature for i in self.impacts}
        for med in self.measures:
            targeted_natures = {
                nature_map[tid]
                for tid in med.target_impact_ids
                if tid in nature_map
            }
            if "POSITIVO" in targeted_natures and "NEGATIVO" in targeted_natures:
                issues.append(
                    f"AVISO [{med.measure_id}]: medida apunta a impactos POSITIVOS "
                    f"y NEGATIVOS. Riesgo de compensación metodológica: un impacto "
                    f"positivo no puede neutralizar uno negativo."
                )

        return issues

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "actions": [a.to_dict() for a in self.actions],
            "receptor_factors": [r.to_dict() for r in self.receptor_factors],
            "impacts": [i.to_dict() for i in self.impacts],
            "measures": [m.to_dict() for m in self.measures],
            "pva_programs": [p.to_dict() for p in self.pva_programs],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Phase6Model — {self.expediente_id}",
            f"  Acciones       : {len(self.actions)}",
            f"  Receptores     : {len(self.receptor_factors)}",
            f"  Impactos       : {len(self.impacts)}",
            f"  Medidas        : {len(self.measures)}",
            f"  PVA            : {len(self.pva_programs)}",
        ]
        by_status = self.impact_count_by_status()
        non_zero = {k: v for k, v in by_status.items() if v > 0}
        if non_zero:
            lines.append(
                "  Impactos/estado: " +
                ", ".join(f"{k}:{v}" for k, v in sorted(non_zero.items()))
            )
        return "\n".join(lines)

    def impact_count_by_status(self) -> dict[str, int]:
        """Cuenta de impactos por estado."""
        result: dict[str, int] = {s: 0 for s in IMPACT_STATUS}
        for imp in self.impacts:
            result[imp.status] = result.get(imp.status, 0) + 1
        return result

    def impacts_by_receptor(self) -> dict[str, list[str]]:
        """Agrupa impact_ids por receptor_id."""
        result: dict[str, list[str]] = {}
        for imp in self.impacts:
            result.setdefault(imp.receptor_id, []).append(imp.impact_id)
        return result

    def measures_by_impact(self) -> dict[str, list[str]]:
        """Agrupa measure_ids por impact_id (desde target_impact_ids de medidas)."""
        result: dict[str, list[str]] = {}
        for med in self.measures:
            for tid in med.target_impact_ids:
                result.setdefault(tid, []).append(med.measure_id)
        return result

    def pva_by_factor(self) -> dict[str, list[str]]:
        """Agrupa pva_ids por factor_id."""
        result: dict[str, list[str]] = {}
        for pva in self.pva_programs:
            result.setdefault(pva.factor_id, []).append(pva.pva_id)
        return result


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def build_receptor_factors_from_inventory(
    summary: InventorySummary,
) -> list[ReceptorFactor]:
    """Crea FR-001...FR-016 desde el InventorySummary de Fase 5.

    - Mantiene inventory_semaphore de cada factor.
    - ready_from_inventory = factor.ready_for_impact_assessment.
    - critical_gaps = IDs de gaps ALTA pendientes o condicionados.
    - No modifica el summary original.
    """
    result: list[ReceptorFactor] = []
    for factor in summary.factors:
        fi_id = factor.factor_id
        fr_id = _INVENTORY_TO_RECEPTOR.get(fi_id, fi_id.replace("FI-", "FR-"))

        critical_gap_ids = [
            g.gap_id
            for g in factor.gaps
            if g.criticality == "ALTA" and g.status in ("PENDIENTE", "CONDICIONADO")
        ]

        notes: list[str] = []
        if not factor.ready_for_impact_assessment:
            notes.append(
                f"Factor no listo para Fase 6 según inventario "
                f"(semáforo: {factor.inventory_semaphore})."
            )

        result.append(
            ReceptorFactor(
                receptor_id=fr_id,
                inventory_factor_id=fi_id,
                name=factor.factor_name or fi_id,
                inventory_semaphore=factor.inventory_semaphore,
                ready_from_inventory=factor.ready_for_impact_assessment,
                critical_gaps=critical_gap_ids,
                notes=notes,
            )
        )
    return result


def build_empty_phase6_model(
    expediente_id: str,
    inventory_summary: Optional[InventorySummary] = None,
) -> Phase6Model:
    """Construye un Phase6Model vacío.

    Si se proporciona inventory_summary, se populan receptor_factors.
    No crea impactos, medidas ni PVA.
    """
    notes: list[str] = []

    if inventory_summary is not None:
        receptor_factors = build_receptor_factors_from_inventory(inventory_summary)
        notes.append(
            f"Receptores cargados desde inventario de Fase 5 "
            f"({len(receptor_factors)} factores)."
        )
    else:
        receptor_factors = []
        notes.append(
            "Modelo creado sin inventario de Fase 5. "
            "receptor_factors vacío — poblar manualmente o via "
            "build_receptor_factors_from_inventory()."
        )

    return Phase6Model(
        expediente_id=expediente_id,
        receptor_factors=receptor_factors,
        notes=notes,
    )
