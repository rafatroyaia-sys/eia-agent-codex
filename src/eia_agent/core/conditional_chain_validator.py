"""
conditional_chain_validator -- IM-09
Validador de cadenas condicionales impacto-medida-PVA para Fase 6 EIA.

Verifica que cuando un impacto, medida o PVA está condicionado por un gap,
CONT o AT activo, esa condición es visible y coherente en toda la cadena:
  Impacto condicionado → medida condicionada → PVA condicionado → auditoría.

Evita que una incertidumbre técnica se pierda al pasar de impactos a medidas
o vigilancia ambiental.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica el modelo ni ningún impacto/medida/PVA.
  - No declara aptitud administrativa.
  - No resuelve gaps ni cierra CONTs ni elimina ATs.

Dependencias: IM-00 (impact_model).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    PVAProgram,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CONDITIONAL_CHAIN_STATUS = {
    "OK": "OK",
    "CON_OBSERVACIONES": "CON_OBSERVACIONES",
    "NO_CONFORME": "NO_CONFORME",
    "SIN_DATOS": "SIN_DATOS",
}

CONDITIONAL_CHAIN_SEVERITY = {
    "ERROR": "ERROR",
    "WARNING": "WARNING",
    "INFO": "INFO",
}

CONDITIONAL_MARKERS: tuple[str, ...] = (
    "condicionado",
    "indeterminado",
    "pendiente_datos",
    "pendiente datos",
    "gap",
    "cont",
    "cont-",
    "at-",
    "asuncion_test",
    "asunción test",
    "consulta_pendiente",
    "consulta pendiente",
    "medida_diagnostica",
    "medida diagnóstica",
    "pva_condicionado",
    "pva condicionado",
    "incertidumbre",
    "no resuelto",
    "sin confirmar",
    "dato pendiente",
)

# Marcadores en texto libre (minúsculas sin tildes para comparación)
_TEXT_MARKERS_LOWER: tuple[str, ...] = (
    "condicionado",
    "indeterminado",
    "pendiente_datos",
    "pendiente datos",
    "gap",
    " cont",
    "cont-",
    "at-",
    "at_",
    "asuncion_test",
    "asuncion test",
    "consulta_pendiente",
    "consulta pendiente",
    "diagnostica",
    "incertidumbre",
    "no resuelto",
    "sin confirmar",
    "dato pendiente",
    "condicion previa",
    "condicion_previa",
)

_SIGNIFICANCE_CONDITIONED: frozenset[str] = frozenset({
    "INDETERMINADO",
    "NO_VALORADO",
})

_STATUS_CONDITIONED: frozenset[str] = frozenset({
    "INDETERMINADO",
    "PENDIENTE_DATOS",
})

_MEASURE_STATUS_CONDITIONED: frozenset[str] = frozenset({
    "CONDICIONADA",
    "CONDICION_PREVIA",
})


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normaliza a minúsculas sin tildes para comparación."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii").lower()


def _any_marker_in(text: str) -> bool:
    normalized = _normalize(text)
    return any(m in normalized for m in _TEXT_MARKERS_LOWER)


# ---------------------------------------------------------------------------
# ConditionalChainIssue
# ---------------------------------------------------------------------------

@dataclass
class ConditionalChainIssue:
    """Incidencia detectada en la auditoría de cadenas condicionales."""

    severity: str
    code: str
    impact_id: Optional[str] = None
    measure_id: Optional[str] = None
    pva_id: Optional[str] = None
    message: str = ""
    recommendation: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "impact_id": self.impact_id,
            "measure_id": self.measure_id,
            "pva_id": self.pva_id,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": list(self.evidence),
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}] {self.code}"]
        if self.impact_id:
            parts.append(f"impacto={self.impact_id}")
        if self.measure_id:
            parts.append(f"medida={self.measure_id}")
        if self.pva_id:
            parts.append(f"pva={self.pva_id}")
        parts.append(self.message)
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# ConditionalChainResult
# ---------------------------------------------------------------------------

@dataclass
class ConditionalChainResult:
    """Resultado de la auditoría de cadenas condicionales."""

    status: str
    checked_impacts: list[str] = field(default_factory=list)
    checked_measures: list[str] = field(default_factory=list)
    checked_pva_programs: list[str] = field(default_factory=list)
    conditioned_impacts: list[str] = field(default_factory=list)
    conditioned_measures: list[str] = field(default_factory=list)
    conditioned_pva_programs: list[str] = field(default_factory=list)
    issues: list[ConditionalChainIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "administrative_ready": False,
            "checked_impacts": list(self.checked_impacts),
            "checked_measures": list(self.checked_measures),
            "checked_pva_programs": list(self.checked_pva_programs),
            "conditioned_impacts": list(self.conditioned_impacts),
            "conditioned_measures": list(self.conditioned_measures),
            "conditioned_pva_programs": list(self.conditioned_pva_programs),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
        }

    def summary(self) -> str:
        lines = [
            f"Auditoria cadenas condicionales — {self.status}",
            f"  Impactos revisados  : {len(self.checked_impacts)}"
            f" ({len(self.conditioned_impacts)} condicionados)",
            f"  Medidas revisadas   : {len(self.checked_measures)}"
            f" ({len(self.conditioned_measures)} condicionadas)",
            f"  PVA revisados       : {len(self.checked_pva_programs)}"
            f" ({len(self.conditioned_pva_programs)} condicionados)",
            f"  Errores: {self.error_count()}"
            f"  Advertencias: {self.warning_count()}"
            f"  Infos: {self.info_count()}",
        ]
        if self.error_count():
            lines.append("  INCIDENCIAS CRITICAS:")
            for issue in self.issues:
                if issue.severity == "ERROR":
                    lines.append(f"    {issue.summary()}")
        if self.warnings:
            lines.append(f"  Avisos del proceso: {len(self.warnings)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Detección de marcadores condicionales
# ---------------------------------------------------------------------------

def text_contains_condition_marker(text: str) -> bool:
    """True si el texto contiene algún marcador condicional conocido."""
    if not text:
        return False
    return _any_marker_in(text)


# ---------------------------------------------------------------------------
# Clasificadores de elementos condicionados
# ---------------------------------------------------------------------------

def impact_is_conditioned(impact: EnvironmentalImpact) -> bool:
    """True si el impacto está condicionado por un gap, CONT, AT o dato pendiente."""
    if impact.status in _STATUS_CONDITIONED:
        return True
    if impact.significance_without_measures in _SIGNIFICANCE_CONDITIONED and impact.data_gaps:
        return True
    if impact.significance_with_measures in _SIGNIFICANCE_CONDITIONED and impact.data_gaps:
        return True
    if impact.data_gaps:
        return True
    for text in list(impact.notes) + list(impact.warnings):
        if text_contains_condition_marker(text):
            return True
    return False


def measure_is_conditioned(measure: MitigationMeasure) -> bool:
    """True si la medida está condicionada, es diagnóstica, o depende de datos pendientes."""
    if measure.measure_type == "DIAGNOSTICA" or measure.is_diagnostic:
        return True
    if measure.status in _MEASURE_STATUS_CONDITIONED:
        return True
    for text in list(measure.notes) + list(measure.warnings):
        if text_contains_condition_marker(text):
            return True
    for text in [measure.description, measure.name]:
        if text_contains_condition_marker(text):
            return True
    return False


def pva_is_conditioned(pva: PVAProgram) -> bool:
    """True si el programa PVA está condicionado o refleja incertidumbre activa."""
    for text in list(pva.notes) + list(pva.warnings):
        if text_contains_condition_marker(text):
            return True
    for text in [pva.name, pva.indicator]:
        if text_contains_condition_marker(text):
            return True
    if pva.frequency == "CONDICIONAL":
        return True
    return False


# ---------------------------------------------------------------------------
# Validadores de cadena
# ---------------------------------------------------------------------------

def validate_conditioned_impact_chain(
    impact: EnvironmentalImpact,
    measures: list[MitigationMeasure],
    pva_programs: list[PVAProgram],
) -> list[ConditionalChainIssue]:
    """
    Valida que un impacto condicionado tiene propagación coherente a medidas y PVA.

    Si el impacto está condicionado:
    - Debe tener al menos una medida condicionada/diagnóstica asociada.
    - No debe presentar medidas que aparentemente cierran el impacto sin condición.
    - Debe tener PVA condicionado o nota de incertidumbre visible.
    """
    issues: list[ConditionalChainIssue] = []

    impact_measures = [m for m in measures if impact.impact_id in m.target_impact_ids]
    impact_pva = [p for p in pva_programs if impact.impact_id in p.target_impact_ids]

    # Sin medidas asociadas: cadena rota
    if not impact_measures and not impact_pva:
        issues.append(ConditionalChainIssue(
            severity="ERROR",
            code="CC-IMP-E001",
            impact_id=impact.impact_id,
            message=(
                f"Impacto condicionado {impact.impact_id!r} sin medidas ni PVA asociados. "
                "La cadena condicional está rota."
            ),
            recommendation=(
                "Asociar al menos una medida diagnóstica y un PVA condicionado "
                "que reflejen la incertidumbre."
            ),
            evidence=[f"status={impact.status!r}", f"data_gaps={impact.data_gaps!r}"],
        ))
        return issues

    # Medidas: verificar que al menos una es condicionada/diagnóstica
    conditioned_measures = [m for m in impact_measures if measure_is_conditioned(m)]
    unconditioned_measures = [m for m in impact_measures if not measure_is_conditioned(m)]

    if not conditioned_measures and impact_measures:
        issues.append(ConditionalChainIssue(
            severity="WARNING",
            code="CC-IMP-W001",
            impact_id=impact.impact_id,
            message=(
                f"Impacto condicionado {impact.impact_id!r} tiene "
                f"{len(unconditioned_measures)} medida(s) sin condicion asociada. "
                "Ninguna medida refleja la incertidumbre del impacto."
            ),
            recommendation=(
                "Revisar si las medidas existentes cubren correctamente la incertidumbre "
                "del impacto o añadir una medida diagnóstica."
            ),
            evidence=[
                f"medidas_sin_condicion={[m.measure_id for m in unconditioned_measures]!r}"
            ],
        ))

    # Medidas no condicionadas que aparentan cerrar el impacto
    closing_measures = [
        m for m in unconditioned_measures
        if m.measure_type in {"CORRECTORA", "COMPENSATORIA"}
        and impact.significance_without_measures in {"SEVERO", "CRITICO", "INDETERMINADO"}
    ]
    if closing_measures:
        issues.append(ConditionalChainIssue(
            severity="ERROR",
            code="CC-IMP-E002",
            impact_id=impact.impact_id,
            message=(
                f"Impacto condicionado {impact.impact_id!r} tiene medida(s) "
                f"correctora/compensatoria sin condicion que pueden aparentar "
                "cerrar el impacto: "
                f"{[m.measure_id for m in closing_measures]}."
            ),
            recommendation=(
                "Las medidas correctoras sobre impactos condicionados deben marcarse "
                "como CONDICIONADA o DIAGNOSTICA hasta que el dato se confirme."
            ),
            evidence=[
                f"significance={impact.significance_without_measures!r}",
                f"medidas_cierre={[m.measure_id for m in closing_measures]!r}",
            ],
        ))

    # PVA: verificar que al menos uno está condicionado
    conditioned_pva = [p for p in impact_pva if pva_is_conditioned(p)]
    if impact_pva and not conditioned_pva:
        issues.append(ConditionalChainIssue(
            severity="WARNING",
            code="CC-IMP-W002",
            impact_id=impact.impact_id,
            message=(
                f"Impacto condicionado {impact.impact_id!r} tiene PVA asociados pero "
                "ninguno refleja la incertidumbre."
            ),
            recommendation=(
                "Al menos un PVA asociado a un impacto condicionado debe indicar "
                "la condición (frecuencia CONDICIONAL, nota de incertidumbre o similar)."
            ),
            evidence=[f"pva_sin_condicion={[p.pva_id for p in impact_pva]!r}"],
        ))

    return issues


def validate_conditioned_measure_chain(
    measure: MitigationMeasure,
    impacts: list[EnvironmentalImpact],
    pva_programs: list[PVAProgram],
) -> list[ConditionalChainIssue]:
    """
    Valida que una medida condicionada no se presenta como reductora cerrada
    y tiene seguimiento PVA coherente.
    """
    issues: list[ConditionalChainIssue] = []

    target_impacts = [i for i in impacts if i.impact_id in measure.target_impact_ids]
    related_pva = [p for p in pva_programs if measure.measure_id in p.target_measure_ids]

    # Medida diagnóstica presentada como única reductora de impacto SEVERO/CRITICO
    if measure.is_diagnostic or measure.measure_type == "DIAGNOSTICA":
        severo_impacts = [
            i for i in target_impacts
            if i.significance_without_measures in {"SEVERO", "CRITICO"}
        ]
        for imp in severo_impacts:
            # Si la medida diagnóstica es la ÚNICA medida del impacto
            other_measures = [
                m for m in impacts  # reutilizamos el modelo completo si disponible
            ]
            # Verificar si en el impacto hay más medidas reductoras
            imp_other_measures = [
                mid for mid in imp.measure_ids
                if mid != measure.measure_id
            ]
            if not imp_other_measures:
                issues.append(ConditionalChainIssue(
                    severity="ERROR",
                    code="CC-MEA-E001",
                    measure_id=measure.measure_id,
                    impact_id=imp.impact_id,
                    message=(
                        f"Medida diagnostica {measure.measure_id!r} es la unica medida "
                        f"del impacto {imp.impact_id!r} con significance={imp.significance_without_measures!r}. "
                        "Una medida DIAGNOSTICA no puede actuar como reductora unica."
                    ),
                    recommendation=(
                        "Añadir medidas correctoras/preventivas reales o "
                        "marcar el impacto como INDETERMINADO hasta confirmar datos."
                    ),
                    evidence=[
                        f"measure_type={measure.measure_type!r}",
                        f"significance={imp.significance_without_measures!r}",
                    ],
                ))

    # Medida condicionada vinculada a impacto: debe tener PVA de seguimiento
    if target_impacts and not related_pva:
        issues.append(ConditionalChainIssue(
            severity="WARNING",
            code="CC-MEA-W001",
            measure_id=measure.measure_id,
            message=(
                f"Medida condicionada {measure.measure_id!r} vinculada a impactos "
                f"{[i.impact_id for i in target_impacts]} "
                "sin PVA de seguimiento."
            ),
            recommendation=(
                "Una medida condicionada debe tener un PVA que verifique "
                "si la condición fue resuelta."
            ),
            evidence=[
                f"status={measure.status!r}",
                f"impactos={[i.impact_id for i in target_impacts]!r}",
            ],
        ))

    return issues


def validate_conditioned_pva_chain(
    pva: PVAProgram,
    impacts: list[EnvironmentalImpact],
    measures: list[MitigationMeasure],
) -> list[ConditionalChainIssue]:
    """
    Valida que un PVA condicionado referencia correctamente su origen de condición.
    """
    issues: list[ConditionalChainIssue] = []

    related_impacts = [i for i in impacts if i.impact_id in pva.target_impact_ids]
    related_measures = [m for m in measures if m.measure_id in pva.target_measure_ids]

    # PVA condicionado sin referencias a impacto, medida, GAP, CONT o AT
    has_references = bool(related_impacts or related_measures)
    has_marker_text = any(
        text_contains_condition_marker(t)
        for t in list(pva.notes) + list(pva.warnings) + [pva.name, pva.indicator]
    )

    if not has_references and not has_marker_text:
        issues.append(ConditionalChainIssue(
            severity="WARNING",
            code="CC-PVA-W001",
            pva_id=pva.pva_id,
            message=(
                f"PVA condicionado {pva.pva_id!r} sin referencia a impacto, "
                "medida, GAP, CONT ni AT."
            ),
            recommendation=(
                "El PVA condicionado debe referenciar al menos un impacto, medida "
                "o el identificador del gap/CONT/AT que lo condiciona."
            ),
            evidence=[f"pva_id={pva.pva_id!r}", f"factor_id={pva.factor_id!r}"],
        ))

    # PVA condicionado que intenta cerrar condición sin evidencia de resolución
    closing_text_markers = (
        "resuelto", "confirmado", "verificado", "cerrado", "superado"
    )
    all_texts = (
        list(pva.notes) + list(pva.warnings) + [pva.name, pva.indicator, pva.threshold]
    )
    has_closing = any(
        m in _normalize(t) for t in all_texts for m in closing_text_markers
    )
    if has_closing:
        issues.append(ConditionalChainIssue(
            severity="WARNING",
            code="CC-PVA-W002",
            pva_id=pva.pva_id,
            message=(
                f"PVA condicionado {pva.pva_id!r} contiene lenguaje de cierre "
                "('resuelto', 'confirmado', etc.) sin que conste evidencia de resolución."
            ),
            recommendation=(
                "Un PVA condicionado no debe presentarse como cierre definitivo. "
                "Usar lenguaje de seguimiento ('pendiente de verificacion', 'a confirmar')."
            ),
            evidence=[f"pva_id={pva.pva_id!r}"],
        ))

    return issues


# ---------------------------------------------------------------------------
# Función principal de validación
# ---------------------------------------------------------------------------

def validate_conditional_chains(model: Phase6Model) -> ConditionalChainResult:
    """
    Valida las cadenas condicionales en un Phase6Model.

    No modifica el model. Solo lectura.
    """
    if not model.impacts and not model.measures and not model.pva_programs:
        return ConditionalChainResult(
            status="SIN_DATOS",
            warnings=["El modelo no contiene impactos, medidas ni PVA."],
            notes=["Ejecutar Fase 6 antes de auditar cadenas condicionales."],
        )

    checked_impacts = [i.impact_id for i in model.impacts]
    checked_measures = [m.measure_id for m in model.measures]
    checked_pva = [p.pva_id for p in model.pva_programs]

    conditioned_impacts = [
        i.impact_id for i in model.impacts if impact_is_conditioned(i)
    ]
    conditioned_measures = [
        m.measure_id for m in model.measures if measure_is_conditioned(m)
    ]
    conditioned_pva = [
        p.pva_id for p in model.pva_programs if pva_is_conditioned(p)
    ]

    all_issues: list[ConditionalChainIssue] = []

    # Validar cadenas desde impactos condicionados
    for impact in model.impacts:
        if impact_is_conditioned(impact):
            issues = validate_conditioned_impact_chain(
                impact, model.measures, model.pva_programs
            )
            all_issues.extend(issues)

    # Validar cadenas desde medidas condicionadas
    for measure in model.measures:
        if measure_is_conditioned(measure):
            issues = validate_conditioned_measure_chain(
                measure, model.impacts, model.pva_programs
            )
            all_issues.extend(issues)

    # Validar cadenas desde PVA condicionados
    for pva in model.pva_programs:
        if pva_is_conditioned(pva):
            issues = validate_conditioned_pva_chain(
                pva, model.impacts, model.measures
            )
            all_issues.extend(issues)

    # Determinar status
    errors = sum(1 for i in all_issues if i.severity == "ERROR")
    warnings_count = sum(1 for i in all_issues if i.severity == "WARNING")

    if errors > 0:
        status = "NO_CONFORME"
    elif warnings_count > 0:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    notes = []
    if not conditioned_impacts and not conditioned_measures and not conditioned_pva:
        notes.append(
            "No se detectan elementos condicionados en el modelo. "
            "Si el expediente tiene CONTs o ATs activos, verificar que están "
            "reflejados en los campos notes/warnings de los elementos de Fase 6."
        )

    return ConditionalChainResult(
        status=status,
        checked_impacts=checked_impacts,
        checked_measures=checked_measures,
        checked_pva_programs=checked_pva,
        conditioned_impacts=conditioned_impacts,
        conditioned_measures=conditioned_measures,
        conditioned_pva_programs=conditioned_pva,
        issues=all_issues,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Carga desde JSON
# ---------------------------------------------------------------------------

def validate_conditional_chains_from_json(path: "str | Path") -> ConditionalChainResult:
    """Carga un Phase6Model desde JSON y valida sus cadenas condicionales."""
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        MitigationMeasure,
        Phase6Model,
        ProjectAction,
        PVAProgram,
        ReceptorFactor,
    )

    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return ConditionalChainResult(
            status="SIN_DATOS",
            warnings=[f"Archivo no encontrado: {path}"],
        )
    except json.JSONDecodeError as exc:
        return ConditionalChainResult(
            status="SIN_DATOS",
            warnings=[f"JSON invalido en {path}: {exc}"],
        )

    expediente_id = data.get("expediente_id", str(path.stem))

    actions = [
        ProjectAction(
            action_id=a["action_id"],
            name=a["name"],
            description=a.get("description", ""),
            action_type=a.get("action_type", "OTRO"),
            operation_code=a.get("operation_code"),
            source_refs=a.get("source_refs", []),
            notes=a.get("notes", []),
        )
        for a in data.get("actions", [])
    ]

    receptor_factors = [
        ReceptorFactor(
            receptor_id=r["receptor_id"],
            inventory_factor_id=r["inventory_factor_id"],
            name=r["name"],
            inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
            ready_from_inventory=r.get("ready_from_inventory", False),
            critical_gaps=r.get("critical_gaps", []),
            notes=r.get("notes", []),
        )
        for r in data.get("receptor_factors", [])
    ]

    impacts = [
        EnvironmentalImpact(
            impact_id=imp["impact_id"],
            action_id=imp["action_id"],
            receptor_id=imp["receptor_id"],
            name=imp["name"],
            description=imp.get("description", ""),
            nature=imp.get("nature", "INDETERMINADO"),
            status=imp.get("status", "PENDIENTE_DATOS"),
            significance_without_measures=imp.get("significance_without_measures", "NO_VALORADO"),
            significance_with_measures=imp.get("significance_with_measures", "NO_VALORADO"),
            conesa_attributes=ConesaAttributes(
                **{k: v for k, v in imp.get("conesa_attributes", {}).items()}
            ),
            data_gaps=imp.get("data_gaps", []),
            source_refs=imp.get("source_refs", []),
            measure_ids=imp.get("measure_ids", []),
            pva_ids=imp.get("pva_ids", []),
            warnings=imp.get("warnings", []),
            notes=imp.get("notes", []),
        )
        for imp in data.get("impacts", [])
    ]

    measures = [
        MitigationMeasure(
            measure_id=m["measure_id"],
            name=m["name"],
            description=m.get("description", ""),
            measure_type=m.get("measure_type", "CORRECTORA"),
            status=m.get("status", "PROPUESTA"),
            target_impact_ids=m.get("target_impact_ids", []),
            is_diagnostic=m.get("is_diagnostic", False),
            is_prl_only=m.get("is_prl_only", False),
            condition_before_submission=m.get("condition_before_submission", False),
            warnings=m.get("warnings", []),
            notes=m.get("notes", []),
        )
        for m in data.get("measures", [])
    ]

    pva_programs = [
        PVAProgram(
            pva_id=p["pva_id"],
            name=p["name"],
            factor_id=p["factor_id"],
            indicator=p["indicator"],
            threshold=p.get("threshold", ""),
            frequency=p.get("frequency", "ANUAL"),
            target_impact_ids=p.get("target_impact_ids", []),
            target_measure_ids=p.get("target_measure_ids", []),
            responsible=p.get("responsible", ""),
            records=p.get("records", []),
            warnings=p.get("warnings", []),
            notes=p.get("notes", []),
        )
        for p in data.get("pva_programs", [])
    ]

    model = Phase6Model(
        expediente_id=expediente_id,
        actions=actions,
        receptor_factors=receptor_factors,
        impacts=impacts,
        measures=measures,
        pva_programs=pva_programs,
        warnings=data.get("warnings", []),
        notes=data.get("notes", []),
    )

    return validate_conditional_chains(model)


def validate_conditional_chains_from_files(
    expediente_path: "str | Path",
) -> ConditionalChainResult:
    """
    Busca el modelo de Fase 6 en el expediente y valida las cadenas condicionales.

    Orden de búsqueda:
      1. impactos/phase6_model_with_pva.json
      2. impactos/phase6_model_with_measures.json
      3. impactos/phase6_model_with_conesa.json
      4. impactos/phase6_model_with_impacts.json
    """
    exp = Path(expediente_path)
    impactos_dir = exp / "impactos"

    candidates = [
        impactos_dir / "phase6_model_with_pva.json",
        impactos_dir / "phase6_model_with_measures.json",
        impactos_dir / "phase6_model_with_conesa.json",
        impactos_dir / "phase6_model_with_impacts.json",
    ]

    model_path = None
    for candidate in candidates:
        if candidate.exists():
            model_path = candidate
            break

    if model_path is None:
        return ConditionalChainResult(
            status="SIN_DATOS",
            warnings=[
                f"No se encontro ningun modelo de Fase 6 en {impactos_dir}. "
                "Ejecutar fase6-generate-pva --write antes de auditar cadenas."
            ],
        )

    return validate_conditional_chains_from_json(model_path)


# ---------------------------------------------------------------------------
# Generación de informe Markdown
# ---------------------------------------------------------------------------

def build_conditional_chain_report_markdown(result: ConditionalChainResult) -> str:
    """Genera el informe Markdown de auditoría de cadenas condicionales."""
    lines: list[str] = []

    lines.append("# Auditoría de cadenas condicionales")
    lines.append("")

    # --- 1. Resumen ---
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"**Estado:** {result.status}")
    lines.append("")
    lines.append("| Elemento | Revisados | Condicionados |")
    lines.append("|----------|-----------|---------------|")
    lines.append(
        f"| Impactos | {len(result.checked_impacts)} | {len(result.conditioned_impacts)} |"
    )
    lines.append(
        f"| Medidas | {len(result.checked_measures)} | {len(result.conditioned_measures)} |"
    )
    lines.append(
        f"| PVA | {len(result.checked_pva_programs)} | {len(result.conditioned_pva_programs)} |"
    )
    lines.append("")
    lines.append(
        f"**Errores:** {result.error_count()} | "
        f"**Advertencias:** {result.warning_count()} | "
        f"**Infos:** {result.info_count()}"
    )
    lines.append("")

    # --- 2. Impactos condicionados ---
    lines.append("## 2. Impactos condicionados")
    lines.append("")
    if result.conditioned_impacts:
        for iid in result.conditioned_impacts:
            lines.append(f"- {iid}")
    else:
        lines.append("No se detectan impactos condicionados en el modelo.")
    lines.append("")

    # --- 3. Medidas condicionadas ---
    lines.append("## 3. Medidas condicionadas")
    lines.append("")
    if result.conditioned_measures:
        for mid in result.conditioned_measures:
            lines.append(f"- {mid}")
    else:
        lines.append("No se detectan medidas condicionadas en el modelo.")
    lines.append("")

    # --- 4. PVA condicionados ---
    lines.append("## 4. PVA condicionados")
    lines.append("")
    if result.conditioned_pva_programs:
        for pid in result.conditioned_pva_programs:
            lines.append(f"- {pid}")
    else:
        lines.append("No se detectan PVA condicionados en el modelo.")
    lines.append("")

    # --- 5. Incidencias ---
    lines.append("## 5. Incidencias")
    lines.append("")
    if result.issues:
        for issue in result.issues:
            lines.append(f"### [{issue.severity}] {issue.code}")
            if issue.impact_id:
                lines.append(f"**Impacto:** {issue.impact_id}")
            if issue.measure_id:
                lines.append(f"**Medida:** {issue.measure_id}")
            if issue.pva_id:
                lines.append(f"**PVA:** {issue.pva_id}")
            lines.append("")
            lines.append(f"**Mensaje:** {issue.message}")
            lines.append("")
            if issue.recommendation:
                lines.append(f"**Recomendacion:** {issue.recommendation}")
                lines.append("")
            if issue.evidence:
                lines.append("**Evidencia:**")
                for ev in issue.evidence:
                    lines.append(f"- {ev}")
                lines.append("")
    else:
        lines.append("No se detectan incidencias en las cadenas condicionales.")
        lines.append("")

    # --- 6. Recomendaciones ---
    lines.append("## 6. Recomendaciones")
    lines.append("")
    recs = [i.recommendation for i in result.issues if i.recommendation and i.severity == "ERROR"]
    if recs:
        for rec in recs:
            lines.append(f"- {rec}")
    else:
        lines.append(
            "Sin recomendaciones criticas. Revisar advertencias si las hay."
        )
    lines.append("")
    if result.notes:
        for note in result.notes:
            lines.append(f"> **Nota:** {note}")
        lines.append("")

    # --- 7. Advertencia de alcance ---
    lines.append("## 7. Advertencia de alcance")
    lines.append("")
    lines.append(
        "> Esta auditoría no resuelve gaps, CONT ni AT. "
        "Solo verifica que las condiciones se mantienen visibles en la cadena "
        "impacto-medida-PVA."
    )
    lines.append("")
    lines.append(
        "> **administrative_ready = False.** "
        "Este informe no declara aptitud administrativa del expediente."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_conditional_chain_outputs(
    result: ConditionalChainResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """
    Escribe los outputs de la auditoría en output_dir.

    Genera:
      - auditoria/conditional_chain_result.json
      - auditoria/conditional_chain_result.md
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "conditional_chain_result.json"
    md_path = out / "conditional_chain_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_conditional_chain_report_markdown(result))

    return json_path, md_path
