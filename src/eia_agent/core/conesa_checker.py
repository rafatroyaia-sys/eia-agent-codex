"""
conesa_checker -- RD-06
Checker determinista de cobertura Conesa para impactos ambientales.

Regla canonica (RD-06 / OBS-M12):
  Todos los impactos del Documento Ambiental deben tener tabla/atributos
  Conesa o justificacion expresa de indeterminacion. Sin excepcion.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No recalcula la formula Conesa salvo en validacion auxiliar opcional.
  - No corrige automaticamente impactos ni textos.
  - No valora impactos nuevos.
  - No modifica el expediente salvo escritura del informe (--write).
  - No declara aptitud administrativa.
  - Funcion pura: no muta Phase6Model ni impactos de entrada.

Diferencia con IM-01:
  IM-01 calcula el indice I = 3·IN + 2·EX + MO + ... para un impacto.
  RD-06 verifica que los atributos existan y sean coherentes con la
  significancia declarada. No recalcula I salvo indicacion explicita.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.impact_model import (
    CONESA_ATTRIBUTE_NAMES,
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
)

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

CONESA_CHECK_STATUS: list[str] = [
    "OK",
    "CON_OBSERVACIONES",
    "NO_CONFORME",
    "SIN_DATOS",
]

CONESA_CHECK_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

CONESA_REQUIRED_ATTRIBUTES: tuple[str, ...] = CONESA_ATTRIBUTE_NAMES

# Significancias de impacto negativo que implican Conesa completo obligatorio
_VALUED_SIGNIFICANCES: frozenset[str] = frozenset({
    "COMPATIBLE",
    "MODERADO",
    "SEVERO",
    "CRITICO",
})

# Significancias positivas
_POSITIVE_SIGNIFICANCES: frozenset[str] = frozenset({
    "POSITIVO_MODERADO",
    "POSITIVO_NOTABLE",
})

# Palabras que indican explicacion valida de indeterminacion en notes/warnings
_EXPLANATION_KEYWORDS: frozenset[str] = frozenset({
    "gap",
    "at activa",
    "asuncion de test",
    "cont",
    "consulta pendiente",
    "campo necesario",
    "campo requerido",
    "indeterminado",
    "dato pendiente",
    "sin datos",
    "prospeccion pendiente",
    "prospección pendiente",
    "datos insuficientes",
    "incertidumbre",
    "no se puede determinar",
})

# Palabras clave de tabla/seccion Conesa en markdown
_CONESA_SECTION_KEYWORDS: tuple[str, ...] = (
    "conesa",
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
    "importancia",
    "significancia",
    "indice de importancia",
)

# Patron de IMP en markdown
_IMP_RE = re.compile(r"\bIMP-\d{3,}\b", re.IGNORECASE)

# Patron de IMP cerca de INDETERMINADO/PENDIENTE en markdown
_INDETERMINATE_NEAR_RE = re.compile(
    r"(indeterminado|pendiente|gap|at activa|datos insuficientes|prospeccion)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _norm(text: str) -> str:
    """Normaliza a minusculas + quita tildes + normaliza espacios."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _has_explanation_text(impact: EnvironmentalImpact) -> bool:
    """True si notes o warnings del impacto contienen explicacion de indeterminacion."""
    combined = _norm(" ".join(impact.notes + impact.warnings + [impact.description]))
    return any(kw in combined for kw in _EXPLANATION_KEYWORDS)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ConesaCheckIssue:
    """Incidencia detectada durante la verificacion de cobertura Conesa."""

    severity: str        # ERROR / WARNING / INFO
    code: str
    impact_id: Optional[str]
    message: str
    recommendation: str = ""
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.severity not in CONESA_CHECK_SEVERITY:
            raise ValueError(f"severity invalido: {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "impact_id": self.impact_id,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": list(self.evidence),
        }

    def summary(self) -> str:
        imp = f"[{self.impact_id}] " if self.impact_id else ""
        return f"[{self.severity}] {self.code} {imp}{self.message}"


@dataclass
class ConesaCheckResult:
    """Resultado completo de la verificacion de cobertura Conesa."""

    status: str
    checked_impacts: list[str] = field(default_factory=list)
    valued_impacts: list[str] = field(default_factory=list)
    indeterminate_impacts: list[str] = field(default_factory=list)
    impacts_missing_conesa: list[str] = field(default_factory=list)
    impacts_missing_markdown: list[str] = field(default_factory=list)
    issues: list[ConesaCheckIssue] = field(default_factory=list)
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
        """True solo si no hay incidencias ERROR."""
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checked_impacts": list(self.checked_impacts),
            "valued_impacts": list(self.valued_impacts),
            "indeterminate_impacts": list(self.indeterminate_impacts),
            "impacts_missing_conesa": list(self.impacts_missing_conesa),
            "impacts_missing_markdown": list(self.impacts_missing_markdown),
            "issues": [i.to_dict() for i in self.issues],
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_valid": self.is_valid(),
            "administrative_ready": self.administrative_ready,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            "--- RD-06 Auditoria de cobertura Conesa ---",
            f"Estado              : {self.status}",
            f"Impactos revisados  : {len(self.checked_impacts)}",
            f"Impactos valorados  : {len(self.valued_impacts)}",
            f"Impactos indet.     : {len(self.indeterminate_impacts)}",
            f"Sin Conesa completo : {len(self.impacts_missing_conesa)}",
            f"Sin cobertura MD    : {len(self.impacts_missing_markdown)}",
            f"Incidencias ERROR   : {self.error_count()}",
            f"Incidencias WARNING : {self.warning_count()}",
        ]
        if self.issues:
            lines.append("")
            lines.append("Incidencias:")
            for iss in self.issues[:10]:
                lines.append(f"  {iss.summary()}")
            if len(self.issues) > 10:
                lines.append(f"  ... ({len(self.issues) - 10} mas)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# has_complete_conesa_attributes
# ---------------------------------------------------------------------------


def has_complete_conesa_attributes(impact: EnvironmentalImpact) -> bool:
    """True si el impacto tiene los 10 atributos Conesa informados con int positivo."""
    attrs = impact.conesa_attributes
    for attr in CONESA_REQUIRED_ATTRIBUTES:
        val = getattr(attrs, attr)
        if val is None:
            return False
        if not isinstance(val, int) or val <= 0:
            return False
    return True


# ---------------------------------------------------------------------------
# missing_conesa_attributes
# ---------------------------------------------------------------------------


def missing_conesa_attributes(impact: EnvironmentalImpact) -> list[str]:
    """Devuelve lista de nombres de atributos Conesa faltantes o invalidos."""
    missing: list[str] = []
    attrs = impact.conesa_attributes
    for attr in CONESA_REQUIRED_ATTRIBUTES:
        val = getattr(attrs, attr)
        if val is None or not isinstance(val, int) or val <= 0:
            missing.append(attr)
    return missing


# ---------------------------------------------------------------------------
# impact_has_valid_conesa_explanation
# ---------------------------------------------------------------------------


def impact_has_valid_conesa_explanation(impact: EnvironmentalImpact) -> bool:
    """True si el impacto no tiene Conesa completo pero tiene explicacion valida.

    Casos admisibles:
    - status INDETERMINADO o PENDIENTE_DATOS con data_gaps no vacio.
    - significance_without_measures INDETERMINADO con data_gaps no vacio.
    - notes/warnings contienen explicacion de indeterminacion.

    No admisibles (devuelven False):
    - texto vacio.
    - 'no aplica' sin justificacion.
    - 'compatible' sin atributos.
    - 'se descarta' sin justificacion.
    """
    # Caso 1: status de incertidumbre + data_gaps
    if impact.status in ("INDETERMINADO", "PENDIENTE_DATOS") and impact.data_gaps:
        return True

    # Caso 2: significance indeterminada + data_gaps
    if (
        impact.significance_without_measures == "INDETERMINADO"
        and impact.data_gaps
    ):
        return True

    # Caso 3: texto explicativo en notes o warnings
    if _has_explanation_text(impact):
        return True

    return False


# ---------------------------------------------------------------------------
# validate_impact_conesa_coverage
# ---------------------------------------------------------------------------


def validate_impact_conesa_coverage(
    impact: EnvironmentalImpact,
) -> list[ConesaCheckIssue]:
    """Valida la cobertura Conesa de un impacto individual.

    Reglas A-F segun spec RD-06.
    """
    issues: list[ConesaCheckIssue] = []
    iid = impact.impact_id
    complete = has_complete_conesa_attributes(impact)
    missing = missing_conesa_attributes(impact)

    # Regla A: VALORADO debe tener 10 atributos + significance no NO_VALORADO/INDETERMINADO
    if impact.status == "VALORADO":
        if not complete:
            issues.append(ConesaCheckIssue(
                severity="ERROR",
                code="CC-A001",
                impact_id=iid,
                message=(
                    f"Impacto {iid} tiene status=VALORADO pero "
                    f"faltan atributos Conesa: {missing}"
                ),
                recommendation=(
                    "Un impacto VALORADO requiere los 10 atributos Conesa. "
                    "Completar o cambiar status a INDETERMINADO con justificacion."
                ),
                evidence=missing,
            ))
        if impact.significance_without_measures in ("NO_VALORADO", "INDETERMINADO"):
            issues.append(ConesaCheckIssue(
                severity="ERROR",
                code="CC-A002",
                impact_id=iid,
                message=(
                    f"Impacto {iid} tiene status=VALORADO pero "
                    f"significance_without_measures={impact.significance_without_measures!r}"
                ),
                recommendation=(
                    "Asignar significancia (COMPATIBLE/MODERADO/SEVERO/CRITICO) "
                    "o cambiar status a PENDIENTE_DATOS."
                ),
                evidence=[impact.significance_without_measures],
            ))
        return issues  # Rule A es definitiva para VALORADO

    # Regla B: significance conocida → atributos obligatorios
    if impact.significance_without_measures in _VALUED_SIGNIFICANCES:
        if not complete:
            issues.append(ConesaCheckIssue(
                severity="ERROR",
                code="CC-B001",
                impact_id=iid,
                message=(
                    f"Impacto {iid} tiene significancia "
                    f"{impact.significance_without_measures!r} "
                    f"pero faltan atributos Conesa: {missing}"
                ),
                recommendation=(
                    "Si la significancia esta asignada, los 10 atributos Conesa "
                    "son obligatorios para justificarla. Completar atributos."
                ),
                evidence=missing,
            ))

    # Regla C: atributos completos pero NO_VALORADO → WARNING
    if complete and impact.significance_without_measures == "NO_VALORADO":
        issues.append(ConesaCheckIssue(
            severity="WARNING",
            code="CC-C001",
            impact_id=iid,
            message=(
                f"Impacto {iid} tiene todos los atributos Conesa completos "
                "pero significance_without_measures=NO_VALORADO"
            ),
            recommendation=(
                "Los atributos estan completos. Ejecutar motor Conesa (IM-01) "
                "o documentar por que no se calcula la significancia."
            ),
            evidence=["NO_VALORADO con atributos completos"],
        ))

    # Regla D: INDETERMINADO/PENDIENTE_DATOS sin explicacion
    if impact.status in ("INDETERMINADO", "PENDIENTE_DATOS"):
        if not impact_has_valid_conesa_explanation(impact):
            # Puede ser ERROR o WARNING segun si hay algo de datos
            severity = "ERROR" if not impact.notes and not impact.data_gaps else "WARNING"
            issues.append(ConesaCheckIssue(
                severity=severity,
                code="CC-D001",
                impact_id=iid,
                message=(
                    f"Impacto {iid} tiene status={impact.status!r} "
                    "pero no tiene data_gaps ni explicacion en notes/warnings"
                ),
                recommendation=(
                    "Documentar por que el impacto esta indeterminado. "
                    "Añadir data_gaps o nota con referencia a gap/AT/CONT activo."
                ),
                evidence=[impact.status],
            ))

    # Regla E: POSITIVO sin nota de no compensacion
    if impact.nature == "POSITIVO":
        has_non_comp_note = any(
            any(kw in _norm(n) for kw in ("no compensa", "positivo tratado", "regla no compensacion"))
            for n in impact.notes
        )
        if not has_non_comp_note and not impact.notes:
            issues.append(ConesaCheckIssue(
                severity="WARNING",
                code="CC-E001",
                impact_id=iid,
                message=(
                    f"Impacto POSITIVO {iid} no tiene nota de no compensacion. "
                    "Un impacto positivo no puede compensar impactos negativos."
                ),
                recommendation=(
                    "Añadir nota en notes que indique que el impacto positivo "
                    "no compensa los negativos (regla de no compensacion)."
                ),
                evidence=["POSITIVO sin nota de no compensacion"],
            ))

    # Regla F: DESCARTADO_JUSTIFICADO sin justificacion
    if impact.status == "DESCARTADO_JUSTIFICADO":
        has_justif = (
            impact.description.strip()
            or impact.notes
            or impact.data_gaps
        )
        if not has_justif:
            issues.append(ConesaCheckIssue(
                severity="WARNING",
                code="CC-F001",
                impact_id=iid,
                message=(
                    f"Impacto {iid} tiene status=DESCARTADO_JUSTIFICADO "
                    "pero sin descripcion/notes/data_gaps que justifiquen el descarte"
                ),
                recommendation=(
                    "Añadir description o notes explicando por que el impacto fue descartado."
                ),
                evidence=["DESCARTADO_JUSTIFICADO sin justificacion"],
            ))

    return issues


# ---------------------------------------------------------------------------
# validate_phase6_conesa_coverage
# ---------------------------------------------------------------------------


def validate_phase6_conesa_coverage(
    model: Phase6Model,
) -> ConesaCheckResult:
    """Verifica la cobertura Conesa de todos los impactos de un Phase6Model.

    No modifica model.
    """
    if not model.impacts:
        return ConesaCheckResult(
            status="SIN_DATOS",
            notes=["El modelo no contiene impactos. Ejecutar Fase 6 primero."],
        )

    all_issues: list[ConesaCheckIssue] = []
    checked: list[str] = []
    valued: list[str] = []
    indeterminate: list[str] = []
    missing_conesa: list[str] = []

    for impact in model.impacts:
        iid = impact.impact_id
        checked.append(iid)

        # Clasificar
        if impact.significance_without_measures in _VALUED_SIGNIFICANCES:
            valued.append(iid)
        if impact.status in ("INDETERMINADO", "PENDIENTE_DATOS"):
            indeterminate.append(iid)

        # Validar
        impact_issues = validate_impact_conesa_coverage(impact)
        all_issues.extend(impact_issues)

        # Registrar si falta Conesa sin justificacion
        if not has_complete_conesa_attributes(impact) and not impact_has_valid_conesa_explanation(impact):
            if impact.status not in ("DESCARTADO_JUSTIFICADO",):
                missing_conesa.append(iid)

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    elif all_issues:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    return ConesaCheckResult(
        status=status,
        checked_impacts=checked,
        valued_impacts=valued,
        indeterminate_impacts=indeterminate,
        impacts_missing_conesa=missing_conesa,
        issues=all_issues,
        notes=[f"Impactos revisados: {len(checked)}"],
    )


# ---------------------------------------------------------------------------
# extract_impact_ids_from_markdown
# ---------------------------------------------------------------------------


def extract_impact_ids_from_markdown(markdown: str) -> list[str]:
    """Detecta todos los IMP-NNN mencionados en un texto markdown.

    Devuelve lista deduplicada preservando el orden de aparicion.
    """
    found: list[str] = []
    seen: set[str] = set()
    for m in _IMP_RE.finditer(markdown):
        imp_id = m.group(0).upper()
        if imp_id not in seen:
            found.append(imp_id)
            seen.add(imp_id)
    return found


# ---------------------------------------------------------------------------
# detect_conesa_table_like_sections
# ---------------------------------------------------------------------------


def detect_conesa_table_like_sections(
    markdown: str,
) -> dict[str, list[str]]:
    """Detecta si cada IMP-NNN aparece cerca de vocabulario Conesa.

    Busca en ±500 caracteres alrededor de cada IMP-NNN los atributos/palabras
    clave de tabla Conesa. Devuelve {imp_id: [keywords encontradas]}.
    """
    result: dict[str, list[str]] = {}
    md_norm = _norm(markdown)

    for m in _IMP_RE.finditer(markdown):
        imp_id = m.group(0).upper()
        start = max(0, m.start() - 500)
        end = min(len(markdown), m.end() + 500)
        context = _norm(markdown[start:end])

        found_kws: list[str] = [
            kw for kw in _CONESA_SECTION_KEYWORDS if kw in context
        ]
        if imp_id not in result:
            result[imp_id] = found_kws
        else:
            # Combinar si aparece varias veces
            existing = set(result[imp_id])
            result[imp_id] = list(existing | set(found_kws))

    return result


# ---------------------------------------------------------------------------
# validate_markdown_conesa_coverage
# ---------------------------------------------------------------------------


def validate_markdown_conesa_coverage(
    markdown: str,
    expected_impact_ids: list[str],
    source: str = "markdown",
) -> list[ConesaCheckIssue]:
    """Verifica que los IMP esperados aparecen en el markdown con cobertura Conesa.

    Para cada expected_impact_id:
    - ERROR si no aparece en el markdown.
    - WARNING si aparece pero sin tabla/seccion Conesa ni explicacion de indeterminacion.
    - INFO si aparece con tabla/seccion Conesa.
    """
    issues: list[ConesaCheckIssue] = []
    present_ids = set(extract_impact_ids_from_markdown(markdown))
    conesa_sections = detect_conesa_table_like_sections(markdown)
    md_norm = _norm(markdown)

    for imp_id in expected_impact_ids:
        imp_id_upper = imp_id.upper()

        if imp_id_upper not in present_ids:
            issues.append(ConesaCheckIssue(
                severity="ERROR",
                code="CC-MD-001",
                impact_id=imp_id,
                message=(
                    f"{imp_id} no aparece en el markdown '{source}'. "
                    "El impacto debe figurar en el Bloque C o tabla de valoracion."
                ),
                recommendation=(
                    f"Incluir {imp_id} en el bloque C o markdown de impactos "
                    "con su valoracion Conesa o justificacion de indeterminacion."
                ),
                evidence=[f"Busqueda en: {source}"],
            ))
            continue

        # El IMP aparece: verificar contexto
        kws = conesa_sections.get(imp_id_upper, [])
        has_conesa_context = len(kws) >= 3  # al menos 3 palabras clave Conesa

        # Verificar si hay indicador de indeterminacion cerca
        for m in _IMP_RE.finditer(markdown):
            if m.group(0).upper() == imp_id_upper:
                start = max(0, m.start() - 300)
                end = min(len(markdown), m.end() + 300)
                context_norm = _norm(markdown[start:end])
                has_indet = _INDETERMINATE_NEAR_RE.search(context_norm) is not None
                break
        else:
            has_indet = False

        if has_conesa_context:
            issues.append(ConesaCheckIssue(
                severity="INFO",
                code="CC-MD-OK",
                impact_id=imp_id,
                message=f"{imp_id} aparece en '{source}' con seccion/tabla Conesa.",
                evidence=kws[:5],
            ))
        elif has_indet:
            issues.append(ConesaCheckIssue(
                severity="INFO",
                code="CC-MD-INDET",
                impact_id=imp_id,
                message=(
                    f"{imp_id} aparece en '{source}' con indicador de "
                    "indeterminacion/pendiente. Cobertura Conesa diferida."
                ),
                evidence=["indeterminado/pendiente detectado"],
            ))
        else:
            issues.append(ConesaCheckIssue(
                severity="WARNING",
                code="CC-MD-002",
                impact_id=imp_id,
                message=(
                    f"{imp_id} aparece en '{source}' pero sin tabla/seccion Conesa "
                    "ni explicacion de indeterminacion."
                ),
                recommendation=(
                    "Añadir tabla de atributos Conesa o indicar explicitamente "
                    "el motivo de la indeterminacion junto a la mencion del impacto."
                ),
                evidence=kws or ["sin vocabulario Conesa detectado"],
            ))

    return issues


# ---------------------------------------------------------------------------
# Deserializador interno de Phase6Model
# ---------------------------------------------------------------------------


def _phase6_model_from_dict(data: dict, exp_id: str) -> Phase6Model:
    """Deserializa Phase6Model desde JSON. Solo mapeo de tipos, sin logica."""
    from eia_agent.core.impact_model import (
        MitigationMeasure,
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
# validate_conesa_coverage_from_files
# ---------------------------------------------------------------------------

_MODEL_FILENAMES: list[str] = [
    "phase6_model_with_pva.json",
    "phase6_model_with_measures.json",
    "phase6_model_with_conesa.json",
    "phase6_model_with_impacts.json",
]

_MD_SCAN_DIRS: tuple[str, ...] = ("bloques", "impactos")


def validate_conesa_coverage_from_files(
    expediente_path: str | Path,
) -> ConesaCheckResult:
    """Carga modelo e impactos desde archivos y ejecuta validacion Conesa.

    Busca modelo en impactos/*.json (por orden de prioridad).
    Busca markdowns en bloques/*.md e impactos/*.md.

    Si no encuentra modelo ni markdowns: SIN_DATOS.
    Lanza FileNotFoundError solo si expediente_path no existe.
    """
    p = Path(expediente_path)
    if not p.exists():
        raise FileNotFoundError(f"Expediente no encontrado: {p}")

    model: Optional[Phase6Model] = None
    extra_warnings: list[str] = []

    # Cargar modelo
    impactos_dir = p / "impactos"
    for filename in _MODEL_FILENAMES:
        model_path = impactos_dir / filename
        if model_path.exists():
            try:
                data = json.loads(model_path.read_text(encoding="utf-8"))
                model = _phase6_model_from_dict(data, p.name)
                break
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                extra_warnings.append(
                    f"JSON invalido en {model_path.name}: {exc}. Ignorando."
                )

    # Cargar markdowns
    markdowns: dict[str, str] = {}
    for subdir in _MD_SCAN_DIRS:
        d = p / subdir
        if d.is_dir():
            for md_file in sorted(d.glob("*.md")):
                try:
                    markdowns[f"{subdir}/{md_file.name}"] = md_file.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    pass

    if model is None and not markdowns:
        result = ConesaCheckResult(
            status="SIN_DATOS",
            warnings=extra_warnings + [
                "No se encontro modelo Phase6 ni markdowns de impactos. "
                "Ejecutar Fase 6 primero."
            ],
        )
        return result

    all_issues: list[ConesaCheckIssue] = []
    missing_md: list[str] = []

    # Validar modelo si existe
    model_result: Optional[ConesaCheckResult] = None
    if model is not None:
        model_result = validate_phase6_conesa_coverage(model)
        all_issues.extend(model_result.issues)

        # Verificar presencia en markdowns
        if markdowns:
            all_md_text = "\n\n".join(markdowns.values())
            present_in_md = set(extract_impact_ids_from_markdown(all_md_text))
            for imp in model.impacts:
                if imp.impact_id.upper() not in present_in_md:
                    missing_md.append(imp.impact_id)
                    all_issues.append(ConesaCheckIssue(
                        severity="WARNING",
                        code="CC-MD-003",
                        impact_id=imp.impact_id,
                        message=(
                            f"{imp.impact_id} esta en el modelo pero no "
                            "aparece en ningun markdown de bloques/ o impactos/"
                        ),
                        recommendation=(
                            "Incluir el impacto en el Bloque C o markdown de valoracion."
                        ),
                        evidence=["no encontrado en markdowns"],
                    ))

    # Validar markdowns independientemente si no hay modelo
    if model is None and markdowns:
        all_md_text = "\n\n".join(markdowns.values())
        found_ids = extract_impact_ids_from_markdown(all_md_text)
        if found_ids:
            for src, md_text in markdowns.items():
                md_issues = validate_markdown_conesa_coverage(md_text, found_ids, src)
                # Solo añadir ERRORs y WARNINGs de markdown independiente
                all_issues.extend(
                    i for i in md_issues if i.severity in ("ERROR", "WARNING")
                )

    # Combinar resultado
    if model_result is not None:
        base = model_result
    else:
        base = ConesaCheckResult(status="SIN_DATOS")

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    elif all_issues:
        status = "CON_OBSERVACIONES"
    elif model is not None and model.impacts:
        status = "OK"
    else:
        status = "SIN_DATOS"

    return ConesaCheckResult(
        status=status,
        checked_impacts=base.checked_impacts,
        valued_impacts=base.valued_impacts,
        indeterminate_impacts=base.indeterminate_impacts,
        impacts_missing_conesa=base.impacts_missing_conesa,
        impacts_missing_markdown=missing_md,
        issues=all_issues,
        warnings=extra_warnings + base.warnings,
        notes=base.notes,
    )


# ---------------------------------------------------------------------------
# build_conesa_check_report_markdown
# ---------------------------------------------------------------------------


def build_conesa_check_report_markdown(result: ConesaCheckResult) -> str:
    """Genera informe markdown de cobertura Conesa."""
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings = [i for i in result.issues if i.severity == "WARNING"]
    infos = [i for i in result.issues if i.severity == "INFO"]

    lines: list[str] = [
        "# Auditoria de cobertura Conesa",
        "",
        "## 1. Resumen",
        "",
        f"- Estado: **{result.status}**",
        f"- Impactos revisados: {len(result.checked_impacts)}",
        f"- Impactos valorados (significancia conocida): {len(result.valued_impacts)}",
        f"- Impactos indeterminados/pendientes: {len(result.indeterminate_impacts)}",
        f"- Sin cobertura Conesa completa: {len(result.impacts_missing_conesa)}",
        f"- Sin cobertura en markdown: {len(result.impacts_missing_markdown)}",
        f"- Incidencias ERROR: {len(errors)}",
        f"- Incidencias WARNING: {len(warnings)}",
        f"- Incidencias INFO: {len(infos)}",
        "",
        "## 2. Impactos revisados",
        "",
    ]

    if result.checked_impacts:
        for imp_id in sorted(result.checked_impacts):
            lines.append(f"- `{imp_id}`")
    else:
        lines.append("_Sin impactos revisados._")

    lines += ["", "## 3. Impactos valorados", ""]

    if result.valued_impacts:
        for imp_id in sorted(result.valued_impacts):
            lines.append(f"- `{imp_id}`")
    else:
        lines.append("_Sin impactos con significancia asignada._")

    lines += ["", "## 4. Impactos indeterminados o pendientes", ""]

    if result.indeterminate_impacts:
        for imp_id in sorted(result.indeterminate_impacts):
            lines.append(f"- `{imp_id}`")
    else:
        lines.append("_Sin impactos indeterminados o pendientes._")

    lines += ["", "## 5. Impactos con cobertura Conesa insuficiente", ""]

    if result.impacts_missing_conesa:
        for imp_id in sorted(result.impacts_missing_conesa):
            lines.append(f"- `{imp_id}` — sin atributos ni justificacion valida")
    else:
        lines.append("_Sin impactos con cobertura Conesa insuficiente._")

    lines += ["", "## 6. Impactos ausentes en markdown", ""]

    if result.impacts_missing_markdown:
        for imp_id in sorted(result.impacts_missing_markdown):
            lines.append(f"- `{imp_id}` — no encontrado en bloques/ ni impactos/")
    else:
        lines.append("_Todos los impactos aparecen en markdown._")

    lines += ["", "## 7. Incidencias", ""]

    for sev_label, sev_issues in (
        ("ERROR", errors),
        ("WARNING", warnings),
        ("INFO", infos),
    ):
        if sev_issues:
            lines.append(f"### {sev_label}")
            lines.append("")
            for iss in sev_issues:
                lines += [
                    f"- **{iss.code}** `{iss.impact_id or '—'}`: {iss.message}",
                ]
            lines.append("")

    if not errors and not warnings and not infos:
        lines.append("_Sin incidencias._")

    lines += ["", "## 8. Recomendaciones", ""]

    if result.status == "NO_CONFORME":
        lines.append(
            "El expediente presenta impactos sin cobertura Conesa obligatoria. "
            "Revisar los ERRORs y completar atributos o documentar la indeterminacion."
        )
    elif result.status == "CON_OBSERVACIONES":
        lines.append(
            "El expediente tiene observaciones sobre cobertura Conesa. "
            "Revisar los WARNINGs y documentar los casos pendientes."
        )
    else:
        lines.append(
            "Todos los impactos revisados tienen cobertura Conesa adecuada."
        )

    lines += [
        "",
        "## 9. Advertencia de alcance",
        "",
        "Esta auditoria no recalcula ni corrige automaticamente los impactos. "
        "No declara aptitud administrativa.",
        "",
        "La verificacion de cobertura Conesa es interna. "
        "La clasificacion del expediente corresponde al organo ambiental.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_conesa_check_outputs
# ---------------------------------------------------------------------------


def write_conesa_check_outputs(
    result: ConesaCheckResult,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y MD del resultado de cobertura Conesa.

    Devuelve (json_path, md_path).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "conesa_check_result.json"
    md_path = out / "conesa_check_result.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        build_conesa_check_report_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
