"""
diagnostic_measure_validator -- RD-08
Validador deterministico: medida diagnostica != medida reductora de significancia.

Regla canonica (RD-08):
  Ninguna medida cuya funcion primaria sea obtener informacion (estudio acustico,
  prospeccion de flora, consulta patrimonial, etc.) puede actuar como reductora
  material de la significancia ambiental de un impacto.

Una medida diagnostica aporta informacion para confirmar, dimensionar o justificar
medidas materiales posteriores. No reduce significancia por si misma.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No corrige automaticamente medidas ni textos.
  - No modifica el expediente salvo escritura del informe (--write).
  - No cambia la significancia de ningun impacto.
  - No declara aptitud administrativa.
  - Funcion pura: no muta Phase6Model ni medidas de entrada.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
)

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

DIAGNOSTIC_VALIDATION_STATUS: list[str] = [
    "OK",
    "CON_OBSERVACIONES",
    "NO_CONFORME",
    "SIN_DATOS",
]

DIAGNOSTIC_VALIDATION_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

DIAGNOSTIC_KEYWORDS: list[str] = [
    "estudio",
    "medicion",
    "medicion",
    "modelizacion",
    "modelizacion",
    "consulta",
    "verificacion",
    "verificacion",
    "prospeccion",
    "prospeccion",
    "caracterizacion",
    "caracterizacion",
    "diagnostico",
    "diagnostico",
    "informe previo",
    "analisis previo",
    "analisis previo",
]

# Preserved with accents for public API; normalized at comparison time
DIAGNOSTIC_KEYWORDS_DISPLAY: list[str] = [
    "estudio",
    "medicion",
    "modelizacion",
    "consulta",
    "verificacion",
    "prospeccion",
    "caracterizacion",
    "diagnostico",
    "informe previo",
    "analisis previo",
]

REDUCTION_KEYWORDS: list[str] = [
    "reduce",
    "reduccion",
    "disminuye",
    "mitiga",
    "corrige",
    "elimina",
    "evita completamente",
    "baja la significancia",
    "reduce la significancia",
    "pasa a compatible",
    "se considera compatible tras",
    "queda corregido",
]

# Palabras de negacion que invalidan una coincidencia de REDUCTION_KEYWORDS
_NEGATION_WORDS: frozenset[str] = frozenset({
    "no", "sin", "nunca", "jamas", "ni", "tampoco",
})

# Ranking interno de significancias negativas (mayor = mas severo)
_NEGATIVE_SIGNIFICANCE_RANK: dict[str, int] = {
    "COMPATIBLE": 1,
    "MODERADO": 2,
    "SEVERO": 3,
    "CRITICO": 4,
}

_HIGH_NEGATIVE_SIGNIFICANCES: frozenset[str] = frozenset({"SEVERO", "CRITICO"})

_MODEL_FILENAMES: list[str] = [
    "phase6_model_with_pva.json",
    "phase6_model_with_measures.json",
    "phase6_model_with_conesa.json",
    "phase6_model_with_impacts.json",
]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _norm(text: str) -> str:
    """Normaliza a minusculas, quita tildes y normaliza espacios."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _is_negated(text: str, kw_start: int) -> bool:
    """True si el keyword en kw_start esta precedido por una palabra de negacion."""
    prefix = text[max(0, kw_start - 30):kw_start].strip()
    last_words = prefix.split()[-3:] if prefix else []
    return any(w in _NEGATION_WORDS for w in last_words)


def _significance_improved(sig_without: str, sig_with: str) -> bool:
    """True si la significancia mejoro (se redujo la severidad negativa)."""
    rank_without = _NEGATIVE_SIGNIFICANCE_RANK.get(sig_without, 0)
    rank_with = _NEGATIVE_SIGNIFICANCE_RANK.get(sig_with, 0)
    return rank_without > 0 and rank_with > 0 and rank_without > rank_with


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticMeasureIssue:
    """Incidencia detectada en la validacion de medidas diagnosticas."""

    severity: str          # ERROR / WARNING / INFO
    code: str              # RD08-E001, RD08-W001, ...
    measure_id: Optional[str]
    impact_id: Optional[str]
    message: str
    recommendation: str = ""
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.severity not in DIAGNOSTIC_VALIDATION_SEVERITY:
            raise ValueError(f"severity invalido: {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "measure_id": self.measure_id,
            "impact_id": self.impact_id,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": list(self.evidence),
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}]", self.code]
        if self.measure_id:
            parts.append(f"({self.measure_id})")
        if self.impact_id:
            parts.append(f"-> {self.impact_id}")
        parts.append(self.message[:120])
        return " ".join(parts)


@dataclass
class DiagnosticMeasureValidationResult:
    """Resultado completo de la validacion de medidas diagnosticas."""

    status: str                          # OK / CON_OBSERVACIONES / NO_CONFORME / SIN_DATOS
    checked_measures: list[str] = field(default_factory=list)
    diagnostic_measures: list[str] = field(default_factory=list)
    problematic_measures: list[str] = field(default_factory=list)
    issues: list[DiagnosticMeasureIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # administrative_ready nunca se declara desde aqui
    administrative_ready: bool = False

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        """True si no hay incidencias de severidad ERROR."""
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "administrative_ready": self.administrative_ready,
            "checked_measures": list(self.checked_measures),
            "diagnostic_measures": list(self.diagnostic_measures),
            "problematic_measures": list(self.problematic_measures),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
        }

    def summary(self) -> str:
        return (
            f"RD-08 [{self.status}] "
            f"{len(self.checked_measures)} revisadas, "
            f"{len(self.diagnostic_measures)} diagnosticas, "
            f"{self.error_count()} errores, "
            f"{self.warning_count()} advertencias"
        )


# ---------------------------------------------------------------------------
# Funciones de deteccion
# ---------------------------------------------------------------------------


def is_diagnostic_measure(measure: MitigationMeasure) -> bool:
    """True si la medida es diagnostica por flag, tipo o palabras clave."""
    if measure.is_diagnostic:
        return True
    if measure.measure_type == "DIAGNOSTICA":
        return True
    combined = _norm(
        f"{measure.name} {measure.description} {' '.join(measure.notes)}"
    )
    # Deduplicated normalized keywords
    seen: set[str] = set()
    for kw in DIAGNOSTIC_KEYWORDS:
        nkw = _norm(kw)
        if nkw not in seen:
            seen.add(nkw)
            if nkw in combined:
                return True
    return False


def measure_claims_material_reduction(measure: MitigationMeasure) -> bool:
    """True si la medida afirma reducir materialmente la significancia ambiental.

    Las ocurrencias precedidas por palabras de negacion ("no reduce", "sin reduccion",
    "nunca mitiga", etc.) NO se cuentan como afirmacion de reduccion.
    """
    combined = _norm(
        f"{measure.name} {measure.description} "
        f"{' '.join(measure.notes)} {' '.join(measure.warnings)}"
    )
    for kw in REDUCTION_KEYWORDS:
        nkw = _norm(kw)
        start = 0
        while True:
            pos = combined.find(nkw, start)
            if pos == -1:
                break
            if not _is_negated(combined, pos):
                return True
            start = pos + 1
    return False


# ---------------------------------------------------------------------------
# validate_diagnostic_measure
# ---------------------------------------------------------------------------


def validate_diagnostic_measure(
    measure: MitigationMeasure,
    related_impacts: Optional[list[EnvironmentalImpact]] = None,
) -> list[DiagnosticMeasureIssue]:
    """Valida una medida diagnostica de forma aislada o con sus impactos vinculados.

    Reglas comprobadas:
    - RD08-E001: texto de la medida afirma reduccion material.
    - RD08-W001: medida vinculada a impacto cuya significancia mejora
                 (la causa de la mejora debe ser una medida no diagnostica).
    """
    issues: list[DiagnosticMeasureIssue] = []

    # Regla 1: claims material reduction
    if measure_claims_material_reduction(measure):
        combined = _norm(
            f"{measure.name} {measure.description} "
            f"{' '.join(measure.notes)} {' '.join(measure.warnings)}"
        )
        evidence = [kw for kw in REDUCTION_KEYWORDS if _norm(kw) in combined]
        issues.append(DiagnosticMeasureIssue(
            severity="ERROR",
            code="RD08-E001",
            measure_id=measure.measure_id,
            impact_id=None,
            message=(
                f"La medida diagnostica '{_ascii_safe(measure.name)}' ({measure.measure_id}) "
                f"contiene lenguaje de reduccion material. "
                f"Una medida diagnostica aporta informacion; no reduce significancia "
                f"ambiental por si misma."
            ),
            recommendation=(
                "Eliminar el lenguaje de reduccion de la descripcion de la medida "
                "diagnostica. Si existe una medida correctora real, declararla por "
                "separado con measure_type distinto de DIAGNOSTICA."
            ),
            evidence=evidence or ["Termino de reduccion detectado en texto"],
        ))

    # Regla 2: linked to impact with improved significance
    if related_impacts:
        for imp in related_impacts:
            if _significance_improved(
                imp.significance_without_measures,
                imp.significance_with_measures,
            ):
                issues.append(DiagnosticMeasureIssue(
                    severity="WARNING",
                    code="RD08-W001",
                    measure_id=measure.measure_id,
                    impact_id=imp.impact_id,
                    message=(
                        f"La medida diagnostica '{_ascii_safe(measure.name)}' ({measure.measure_id}) "
                        f"esta vinculada al impacto {imp.impact_id} cuya significancia mejora "
                        f"({imp.significance_without_measures} -> {imp.significance_with_measures}). "
                        f"Verificar que la reduccion la producen medidas correctoras/preventivas, "
                        f"no esta medida diagnostica."
                    ),
                    recommendation=(
                        f"Identificar que medida correctora o preventiva produce la mejora "
                        f"de significancia en {imp.impact_id}. Si solo hay medidas diagnosticas "
                        f"vinculadas a este impacto, anadir medidas materiales o corregir "
                        f"la significancia declarada."
                    ),
                    evidence=[
                        f"significance_without_measures={imp.significance_without_measures!r}",
                        f"significance_with_measures={imp.significance_with_measures!r}",
                    ],
                ))

    return issues


# ---------------------------------------------------------------------------
# validate_diagnostic_measures_in_model
# ---------------------------------------------------------------------------


def validate_diagnostic_measures_in_model(
    model: Phase6Model,
) -> DiagnosticMeasureValidationResult:
    """Valida todas las medidas del modelo Phase6, detectando uso indebido de diagnosticas.

    No muta model ni ningun objeto de entrada.
    """
    if not model.measures:
        return DiagnosticMeasureValidationResult(
            status="SIN_DATOS",
            checked_measures=[],
            diagnostic_measures=[],
            problematic_measures=[],
            issues=[],
            warnings=["El modelo no contiene medidas. No hay nada que validar."],
        )

    # Indices
    impact_index: dict[str, EnvironmentalImpact] = {
        imp.impact_id: imp for imp in model.impacts
    }

    # Por cada impacto: lista de measure_ids NO diagnosticos vinculados
    non_diag_by_impact: dict[str, list[str]] = {}
    for m in model.measures:
        if not is_diagnostic_measure(m):
            for tid in m.target_impact_ids:
                non_diag_by_impact.setdefault(tid, []).append(m.measure_id)

    all_issues: list[DiagnosticMeasureIssue] = []
    checked_measures: list[str] = []
    diagnostic_measures: list[str] = []
    problematic_set: set[str] = set()
    notes: list[str] = []

    for m in model.measures:
        checked_measures.append(m.measure_id)
        if not is_diagnostic_measure(m):
            continue
        diagnostic_measures.append(m.measure_id)

        related_impacts = [
            impact_index[tid]
            for tid in m.target_impact_ids
            if tid in impact_index
        ]
        measure_issues = validate_diagnostic_measure(m, related_impacts)

        # Sole-reducer check (agrega ERROR adicional si corresponde)
        for imp_id in m.target_impact_ids:
            imp = impact_index.get(imp_id)
            if imp is None:
                continue
            if _significance_improved(
                imp.significance_without_measures,
                imp.significance_with_measures,
            ):
                if not non_diag_by_impact.get(imp_id):
                    # Esta diagnostica es la UNICA reductora -> ERROR
                    measure_issues.append(DiagnosticMeasureIssue(
                        severity="ERROR",
                        code="RD08-E002",
                        measure_id=m.measure_id,
                        impact_id=imp_id,
                        message=(
                            f"La medida diagnostica '{_ascii_safe(m.name)}' ({m.measure_id}) "
                            f"es la UNICA medida vinculada al impacto {imp_id} "
                            f"({imp.significance_without_measures} -> {imp.significance_with_measures}). "
                            f"Se esta usando como reductora de significancia, lo que no "
                            f"es metodologicamente admisible."
                        ),
                        recommendation=(
                            f"Anadir al impacto {imp_id} una medida correctora o "
                            f"preventiva real que justifique la mejora de significancia. "
                            f"La medida diagnostica puede mantenerse como condicion previa "
                            f"pero no como unica reductora."
                        ),
                        evidence=[
                            f"significance_without_measures={imp.significance_without_measures!r}",
                            f"significance_with_measures={imp.significance_with_measures!r}",
                            f"no hay medidas no-diagnosticas para {imp_id}",
                        ],
                    ))
            elif imp.significance_without_measures in _HIGH_NEGATIVE_SIGNIFICANCES:
                # Diagnostica es la UNICA medida de impacto de alta significancia no mejorado
                if (
                    not non_diag_by_impact.get(imp_id)
                    and imp.significance_with_measures == imp.significance_without_measures
                ):
                    measure_issues.append(DiagnosticMeasureIssue(
                        severity="WARNING",
                        code="RD08-W002",
                        measure_id=m.measure_id,
                        impact_id=imp_id,
                        message=(
                            f"La medida diagnostica '{_ascii_safe(m.name)}' ({m.measure_id}) "
                            f"es la unica medida para el impacto {imp_id} "
                            f"(significancia {imp.significance_without_measures}), "
                            f"que no ha mejorado. Un impacto de alta significancia "
                            f"requiere medidas correctoras o preventivas reales."
                        ),
                        recommendation=(
                            f"Anadir medidas correctoras o preventivas para el impacto "
                            f"{imp_id}. La medida diagnostica puede coexistir como "
                            f"condicion previa."
                        ),
                        evidence=[
                            f"significance_without_measures={imp.significance_without_measures!r}",
                            f"significance_with_measures={imp.significance_with_measures!r}",
                            "no hay medidas no-diagnosticas para este impacto",
                        ],
                    ))

        if measure_issues:
            problematic_set.add(m.measure_id)
        all_issues.extend(measure_issues)

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    return DiagnosticMeasureValidationResult(
        status=status,
        checked_measures=checked_measures,
        diagnostic_measures=diagnostic_measures,
        problematic_measures=sorted(problematic_set),
        issues=all_issues,
        warnings=[],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Deserializador interno de Phase6Model
# ---------------------------------------------------------------------------


def _phase6_model_from_dict(data: dict, exp_id: str) -> Phase6Model:
    """Deserializa Phase6Model desde JSON. Solo mapeo de tipos, sin logica."""
    from eia_agent.core.impact_model import (
        ConesaAttributes,
        ProjectAction,
        PVAProgram,
        ReceptorFactor,
    )

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
            name=p.get("name", p["pva_id"]),
            factor_id=p.get("factor_id", "FI-001"),
            indicator=p.get("indicator", ""),
            threshold=p.get("threshold", ""),
            frequency=p.get("frequency", "CONDICIONAL"),
            target_impact_ids=p.get("target_impact_ids", []),
            target_measure_ids=p.get("target_measure_ids", []),
            responsible=p.get("responsible", ""),
            records=p.get("records", []),
            warnings=p.get("warnings", []),
            notes=p.get("notes", []),
        )
        for p in data.get("pva_programs", [])
    ]

    return Phase6Model(
        expediente_id=exp_id,
        actions=actions,
        receptor_factors=receptor_factors,
        impacts=impacts,
        measures=measures,
        pva_programs=pva_programs,
        warnings=data.get("warnings", []),
        notes=data.get("notes", []),
    )


# ---------------------------------------------------------------------------
# validate_diagnostic_measures_from_json
# ---------------------------------------------------------------------------


def validate_diagnostic_measures_from_json(
    path: "str | Path",
) -> DiagnosticMeasureValidationResult:
    """Carga un Phase6Model desde un JSON y valida medidas diagnosticas."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DiagnosticMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"Archivo no encontrado: {p}"],
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return DiagnosticMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"JSON invalido en {p.name}: {exc}"],
        )

    try:
        model = _phase6_model_from_dict(data, p.stem)
    except (KeyError, TypeError, ValueError) as exc:
        return DiagnosticMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"Error deserializando {p.name}: {exc}"],
        )

    return validate_diagnostic_measures_in_model(model)


# ---------------------------------------------------------------------------
# validate_diagnostic_measures_from_files
# ---------------------------------------------------------------------------


def validate_diagnostic_measures_from_files(
    expediente_path: "str | Path",
) -> DiagnosticMeasureValidationResult:
    """Busca el modelo de impactos del expediente y valida medidas diagnosticas.

    Orden de busqueda:
      1. impactos/phase6_model_with_pva.json
      2. impactos/phase6_model_with_measures.json
      3. impactos/phase6_model_scored.json
      4. impactos/phase6_model_with_impacts.json
    """
    p = Path(expediente_path)
    if not p.exists():
        raise FileNotFoundError(f"Expediente no encontrado: {p}")

    impactos_dir = p / "impactos"
    extra_warnings: list[str] = []

    model: Optional[Phase6Model] = None
    for filename in _MODEL_FILENAMES:
        model_path = impactos_dir / filename
        if model_path.exists():
            try:
                data = json.loads(model_path.read_text(encoding="utf-8"))
                model = _phase6_model_from_dict(data, p.name)
                break
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                extra_warnings.append(
                    f"JSON invalido en {filename}: {exc}. Ignorando."
                )

    if model is None:
        result = DiagnosticMeasureValidationResult(
            status="SIN_DATOS",
            warnings=extra_warnings + [
                "No se encontro ningun modelo de impactos/medidas en impactos/. "
                "Ejecutar primero la Fase 6 (phase6-generate-measures)."
            ],
        )
        return result

    result = validate_diagnostic_measures_in_model(model)
    result.warnings.extend(extra_warnings)
    return result


# ---------------------------------------------------------------------------
# build_diagnostic_measure_report_markdown
# ---------------------------------------------------------------------------


def build_diagnostic_measure_report_markdown(
    result: DiagnosticMeasureValidationResult,
) -> str:
    lines: list[str] = []

    lines.append("# Auditoria de medidas diagnosticas")
    lines.append("")

    # --- 1. Resumen ---
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"**Estado:** {result.status}")
    lines.append(f"**Medidas revisadas:** {len(result.checked_measures)}")
    lines.append(f"**Medidas diagnosticas detectadas:** {len(result.diagnostic_measures)}")
    lines.append(f"**Medidas con incidencias:** {len(result.problematic_measures)}")
    lines.append(f"**Errores:** {result.error_count()}")
    lines.append(f"**Advertencias:** {result.warning_count()}")
    lines.append(f"**Informativos:** {result.info_count()}")
    lines.append("")

    # --- 2. Medidas revisadas ---
    lines.append("## 2. Medidas revisadas")
    lines.append("")
    if result.checked_measures:
        for mid in result.checked_measures:
            marker = "**[DIAG]**" if mid in result.diagnostic_measures else ""
            lines.append(f"- {mid} {marker}".rstrip())
    else:
        lines.append("_No se revisaron medidas (modelo sin medidas o SIN_DATOS)._")
    lines.append("")

    # --- 3. Medidas diagnosticas detectadas ---
    lines.append("## 3. Medidas diagnosticas detectadas")
    lines.append("")
    if result.diagnostic_measures:
        for mid in result.diagnostic_measures:
            prob = " _(con incidencias)_" if mid in result.problematic_measures else ""
            lines.append(f"- {mid}{prob}")
    else:
        lines.append("_No se detectaron medidas diagnosticas._")
    lines.append("")

    # --- 4. Incidencias ---
    lines.append("## 4. Incidencias")
    lines.append("")
    if result.issues:
        for issue in result.issues:
            lines.append(f"### {issue.code} [{issue.severity}]")
            if issue.measure_id:
                lines.append(f"- **Medida:** {issue.measure_id}")
            if issue.impact_id:
                lines.append(f"- **Impacto:** {issue.impact_id}")
            lines.append(f"- **Mensaje:** {issue.message}")
            lines.append(f"- **Recomendacion:** {issue.recommendation}")
            if issue.evidence:
                lines.append("- **Evidencia:**")
                for ev in issue.evidence:
                    lines.append(f"  - {ev}")
            lines.append("")
    else:
        lines.append("_No se detectaron incidencias._")
        lines.append("")

    # --- 5. Recomendaciones ---
    lines.append("## 5. Recomendaciones")
    lines.append("")
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings = [i for i in result.issues if i.severity == "WARNING"]
    if errors:
        lines.append("**Correcciones obligatorias (ERROR):**")
        lines.append("")
        for i in errors:
            lines.append(f"- [{i.code}] {i.recommendation}")
        lines.append("")
    if warnings:
        lines.append("**Observaciones a revisar (WARNING):**")
        lines.append("")
        for i in warnings:
            lines.append(f"- [{i.code}] {i.recommendation}")
        lines.append("")
    if not errors and not warnings:
        lines.append(
            "No se detectaron incidencias. Las medidas diagnosticas estan "
            "correctamente formuladas y no se usan como reductoras de significancia."
        )
        lines.append("")

    # --- 6. Advertencia de alcance ---
    lines.append("## 6. Advertencia de alcance")
    lines.append("")
    lines.append(
        "Una medida diagnostica no reduce por si sola la significancia ambiental. "
        "Solo aporta informacion para confirmar, dimensionar o justificar medidas "
        "materiales posteriores."
    )
    lines.append("")
    lines.append(
        "Si un impacto tiene significancia SEVERO o CRITICO, la reduccion de esa "
        "significancia debe provenir de medidas correctoras, preventivas o "
        "compensatorias reales, no de estudios, prospecciones, consultas o "
        "verificaciones."
    )
    lines.append("")
    lines.append(
        "Este validador no modifica medidas, no cambia significancias, "
        "no valora impactos y no declara aptitud administrativa del expediente."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_diagnostic_measure_outputs
# ---------------------------------------------------------------------------


def write_diagnostic_measure_outputs(
    result: DiagnosticMeasureValidationResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe diagnostic_measure_validation_result.json y .md en output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "diagnostic_measure_validation_result.json"
    md_path = out / "diagnostic_measure_validation_result.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        build_diagnostic_measure_report_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
