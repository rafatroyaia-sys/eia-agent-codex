"""
pva_coverage_validator -- IM-07
Validador determinístico de cobertura PVA para Fase 6 EIA.

Verifica que los impactos relevantes tienen cobertura PVA suficiente en un
Phase6Model ya enriquecido con impactos, medidas y pva_programs.

Decisión de ID (2026-05-10):
  IM-07 = Este validador (cobertura PVA).
  IM-08 = reservado para template C.5 acumulativos/sinérgicos.
  El ítem "cadenas condicionales código" (antes IM-07 del backlog) se mantiene
  pendiente en el backlog como ítem sin ID confirmado hasta que el usuario decida
  su posición en la secuencia.

Tipos de cobertura:
  DIRECT      → impact.impact_id en pva.target_impact_ids y PVA no es revisión anual.
  BY_FACTOR   → pva.factor_id == FI-equivalente-de-receptor, impacto no en target_impact_ids.
  TRANSVERSAL → PVA con nota de cobertura transversal/global, no revisión anual.

La revisión anual global NO es cobertura suficiente para impactos individuales.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No genera PVA (eso es IM-06).
  - No modifica el modelo, impactos ni medidas.
  - No valora impactos.
  - Función pura: no muta el Phase6Model recibido.

Dependencias: IM-00 (impact_model), IM-06 (pva_generator — no importado directamente,
solo usa los tipos de IM-00).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
    PVAProgram,
    RECEPTOR_FACTOR_IDS,
    ReceptorFactor,
)

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    """Normaliza texto a ASCII para consola Windows cp1252."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# Constantes de cobertura
# ---------------------------------------------------------------------------

COVERAGE_DIRECT = "DIRECT"
COVERAGE_BY_FACTOR = "BY_FACTOR"
COVERAGE_TRANSVERSAL = "TRANSVERSAL"

# Significancias de impactos negativos que requieren seguimiento PVA
_REQUIRES_PVA_SIGNIFICANCE: frozenset[str] = frozenset({
    "COMPATIBLE", "MODERADO", "SEVERO", "CRITICO",
    "INDETERMINADO", "NO_VALORADO",
})

# Estados de impactos que requieren PVA cuando son negativos
_REQUIRES_PVA_STATUS: frozenset[str] = frozenset({
    "IDENTIFICADO", "VALORADO", "INDETERMINADO", "PENDIENTE_DATOS",
})

# Receptores sensibles: impactos INDETERMINADO en estos factores requieren PVA
_SENSITIVE_RECEPTORS: frozenset[str] = frozenset({
    "FR-007",  # Flora
    "FR-008",  # Fauna
    "FR-009",  # ENP
    "FR-010",  # Red Natura 2000
    "FR-012",  # Patrimonio cultural
})

# Palabras clave en notes que indican cobertura transversal declarada
_TRANSVERSAL_KEYWORDS: tuple[str, ...] = (
    "cobertura", "transversal", "global", "cubre indirectamente",
    "cubre tambien", "cubre implicitamente", "cobertura implicita",
    "seguimiento global",
)


# ---------------------------------------------------------------------------
# Helpers internos de PVA
# ---------------------------------------------------------------------------

def _is_annual_review_pva(pva: PVAProgram) -> bool:
    """True si el PVA es la revisión anual global (no es cobertura de factor específico)."""
    return "anual" in pva.name.lower() and "revision" in pva.name.lower()


def _pva_is_conditioned(pva: PVAProgram) -> bool:
    """True si el PVA tiene estado CONDICIONADO (por CONT abierto — E-9)."""
    return any("CONDICIONADO" in w for w in pva.warnings)


def _has_transversal_note(pva: PVAProgram) -> bool:
    """True si el PVA incluye una nota de cobertura transversal/global declarada."""
    all_text = " ".join(pva.notes).lower()
    return any(kw in all_text for kw in _TRANSVERSAL_KEYWORDS)


def _coverage_type(
    impact: EnvironmentalImpact,
    pva: PVAProgram,
) -> Optional[str]:
    """Devuelve el tipo de cobertura del PVA para el impacto, o None si no cubre."""
    if _is_annual_review_pva(pva):
        return None  # La revisión anual no es cobertura suficiente de factor

    fi_id = RECEPTOR_FACTOR_IDS.get(impact.receptor_id)

    # Cobertura directa
    if impact.impact_id in pva.target_impact_ids:
        return COVERAGE_DIRECT

    # Cobertura por factor equivalente
    if fi_id and pva.factor_id == fi_id:
        return COVERAGE_BY_FACTOR

    # Cobertura transversal declarada en notes (solo si factor coincide)
    if fi_id and pva.factor_id == fi_id and _has_transversal_note(pva):
        return COVERAGE_TRANSVERSAL

    return None


# ---------------------------------------------------------------------------
# PVACoverageIssue
# ---------------------------------------------------------------------------

@dataclass
class PVACoverageIssue:
    """Incidencia de cobertura PVA sobre un impacto específico.

    severity: ERROR (sin cobertura, is_valid=False) /
              WARNING (cobertura condicional o parcial) /
              INFO (impacto ignorado, no requiere PVA).
    code: código canónico de la incidencia.
    impact_id: ID del impacto afectado (None si es incidencia global).
    pva_id: ID del PVA relacionado (None si no hay cobertura).
    message: descripción del problema detectado.
    recommendation: acción recomendada para resolverlo.
    """

    severity: str
    code: str
    impact_id: Optional[str]
    pva_id: Optional[str]
    message: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "impact_id": self.impact_id,
            "pva_id": self.pva_id,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}]", self.code]
        if self.impact_id:
            parts.append(f"({self.impact_id})")
        parts.append(self.message[:80] + ("..." if len(self.message) > 80 else ""))
        return _ascii_safe(" ".join(parts))


# ---------------------------------------------------------------------------
# PVACoverageResult
# ---------------------------------------------------------------------------

@dataclass
class PVACoverageResult:
    """Resultado de la validación de cobertura PVA sobre un Phase6Model."""

    covered_impact_ids: list[str] = field(default_factory=list)
    """Impactos con cobertura PVA directa y activa."""

    uncovered_impact_ids: list[str] = field(default_factory=list)
    """Impactos negativos/sensibles sin ninguna cobertura PVA. Cada uno genera ERROR."""

    conditional_coverage_ids: list[str] = field(default_factory=list)
    """Impactos con cobertura solo condicional (CONDICIONADO por CONT) o por factor."""

    ignored_impact_ids: list[str] = field(default_factory=list)
    """Impactos no evaluados: DESCARTADO o POSITIVO sin data_gaps."""

    issues: list[PVACoverageIssue] = field(default_factory=list)
    """Todas las incidencias generadas (ERROR + WARNING + INFO)."""

    warnings: list[str] = field(default_factory=list)
    """Avisos generales de proceso."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

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
            "covered_impact_ids": list(self.covered_impact_ids),
            "uncovered_impact_ids": list(self.uncovered_impact_ids),
            "conditional_coverage_ids": list(self.conditional_coverage_ids),
            "ignored_impact_ids": list(self.ignored_impact_ids),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_valid": self.is_valid(),
        }

    def summary(self) -> str:
        """Resumen ASCII-safe (compatible con consola Windows cp1252)."""
        lines = [
            "--- IM-07 Validador de cobertura PVA ---",
            f"Impactos cubiertos      : {len(self.covered_impact_ids)}",
            f"Impactos sin cobertura  : {len(self.uncovered_impact_ids)}",
            f"Cobertura condicional   : {len(self.conditional_coverage_ids)}",
            f"Impactos ignorados      : {len(self.ignored_impact_ids)}",
            f"ERRORs                  : {self.error_count()}",
            f"WARNINGs                : {self.warning_count()}",
            f"INFOs                   : {self.info_count()}",
            f"Resultado               : {'VALIDO' if self.is_valid() else 'NO VALIDO'}",
        ]
        if self.uncovered_impact_ids:
            lines.append(
                "Sin cobertura (GAP-PVA): "
                + ", ".join(self.uncovered_impact_ids[:5])
                + ("..." if len(self.uncovered_impact_ids) > 5 else "")
            )
        if self.warnings:
            for w in self.warnings[:3]:
                lines.append(f"  AVISO: {_ascii_safe(w)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# API pública — funciones de análisis
# ---------------------------------------------------------------------------

def impact_requires_pva(impact: EnvironmentalImpact) -> bool:
    """True si el impacto debe tener cobertura PVA.

    Reglas (en orden):
      1. DESCARTADO_JUSTIFICADO → False siempre.
      2. NEGATIVO + status relevante + significancia relevante → True.
      3. INDETERMINADO (cualquier nature) en receptor sensible → True.
      4. POSITIVO → False por defecto (los positivos con data_gaps generan
         WARNING pero no requieren PVA según la metodología actual).
      5. Cualquier otro caso → False.
    """
    # 1. Descartados: nunca requieren PVA
    if impact.status == "DESCARTADO_JUSTIFICADO":
        return False

    # 2. Impactos negativos con estado y significancia relevantes
    if impact.nature == "NEGATIVO":
        return (
            impact.status in _REQUIRES_PVA_STATUS
            and impact.significance_without_measures in _REQUIRES_PVA_SIGNIFICANCE
        )

    # 3. Cualquier impacto INDETERMINADO en receptor sensible
    if (
        impact.status == "INDETERMINADO"
        or impact.nature == "INDETERMINADO"
    ):
        if impact.receptor_id in _SENSITIVE_RECEPTORS:
            return True

    # 4. Positivos: no requieren PVA (tienen tratamiento informativo separado)
    if impact.nature == "POSITIVO":
        return False

    # 5. MIXTO con nature relevante — se trata como NEGATIVO
    if impact.nature == "MIXTO":
        return (
            impact.status in _REQUIRES_PVA_STATUS
            and impact.significance_without_measures in _REQUIRES_PVA_SIGNIFICANCE
        )

    return False


def find_pva_coverage_for_impact(
    impact: EnvironmentalImpact,
    pva_programs: list[PVAProgram],
) -> list[PVAProgram]:
    """Devuelve los PVAs que proporcionan cobertura para el impacto.

    Considera cobertura si:
      - DIRECT: impact.impact_id en pva.target_impact_ids (y PVA no es revisión anual).
      - BY_FACTOR: pva.factor_id coincide con FI-equivalente del receptor del impacto.
      - TRANSVERSAL: PVA tiene nota de cobertura transversal + factor coincide.

    La revisión anual global (nombre contiene "revision anual") NO se incluye como
    cobertura específica — es un instrumento de supervisión, no de seguimiento factual.

    No muta el impacto ni los PVAs.
    """
    covering: list[PVAProgram] = []
    for pva in pva_programs:
        ct = _coverage_type(impact, pva)
        if ct is not None:
            covering.append(pva)
    return covering


def validate_pva_coverage(model: Phase6Model) -> PVACoverageResult:
    """Valida la cobertura PVA de todos los impactos de un Phase6Model.

    Para cada impacto:
      - Si DESCARTADO_JUSTIFICADO → ignored (INFO).
      - Si POSITIVO sin data_gaps → ignored (INFO).
      - Si POSITIVO con data_gaps → ignored pero con WARNING recomendación.
      - Si requiere PVA:
          - Sin cobertura → ERROR (uncovered_impact_ids).
          - Solo cobertura CONDICIONADA (E-9) → WARNING (conditional_coverage_ids).
          - Solo cobertura BY_FACTOR (no en target_impact_ids) → WARNING (conditional_coverage_ids).
          - Al menos una cobertura DIRECT no condicionada → cubierto (covered_impact_ids).
      - INDETERMINADO en receptor sensible sin cobertura → ERROR.

    Función pura. No muta el modelo.

    Args:
        model: Phase6Model con impactos, medidas y pva_programs poblados.

    Returns:
        PVACoverageResult con el análisis de cobertura completo.
    """
    covered: list[str] = []
    uncovered: list[str] = []
    conditional: list[str] = []
    ignored: list[str] = []
    issues: list[PVACoverageIssue] = []
    warnings: list[str] = []
    notes: list[str] = []

    pva_programs = model.pva_programs

    if not model.impacts:
        warnings.append(
            "El modelo no contiene impactos. "
            "Ejecute phase6-identify-impacts --write antes de validar cobertura PVA."
        )
        issues.append(PVACoverageIssue(
            severity="INFO",
            code="PVA-COV-I003",
            impact_id=None,
            pva_id=None,
            message="El modelo no contiene impactos — cobertura PVA no aplicable.",
            recommendation="Ejecute phase6-identify-impacts --write para construir el modelo.",
        ))

    if not pva_programs:
        warnings.append(
            "El modelo no contiene fichas PVA. "
            "Ejecute phase6-generate-pva --write antes de validar cobertura."
        )
        issues.append(PVACoverageIssue(
            severity="INFO",
            code="PVA-COV-I004",
            impact_id=None,
            pva_id=None,
            message="No hay fichas PVA en el modelo — cobertura PVA no evaluable.",
            recommendation="Ejecute phase6-generate-pva --write para generar las fichas PVA.",
        ))

    for imp in model.impacts:
        # ── Descartados: siempre ignorados ──
        if imp.status == "DESCARTADO_JUSTIFICADO":
            ignored.append(imp.impact_id)
            issues.append(PVACoverageIssue(
                severity="INFO",
                code="PVA-COV-I002",
                impact_id=imp.impact_id,
                pva_id=None,
                message=(
                    f"{imp.impact_id}: impacto DESCARTADO_JUSTIFICADO — "
                    "no requiere cobertura PVA."
                ),
                recommendation="Ninguna acción requerida.",
            ))
            continue

        # ── Positivos ──
        if imp.nature == "POSITIVO":
            ignored.append(imp.impact_id)
            if imp.data_gaps:
                gap_refs = ", ".join(imp.data_gaps[:3])
                issues.append(PVACoverageIssue(
                    severity="WARNING",
                    code="PVA-COV-W003",
                    impact_id=imp.impact_id,
                    pva_id=None,
                    message=(
                        f"{imp.impact_id}: impacto POSITIVO con data_gaps activos "
                        f"({gap_refs}). "
                        "El umbral del PVA de eficacia puede ser PROVISIONAL (E-10)."
                    ),
                    recommendation=(
                        "Verificar que el PVA de este impacto positivo incluye "
                        "nota de incertidumbre E-10 si existe cobertura."
                    ),
                ))
            else:
                issues.append(PVACoverageIssue(
                    severity="INFO",
                    code="PVA-COV-I001",
                    impact_id=imp.impact_id,
                    pva_id=None,
                    message=(
                        f"{imp.impact_id}: impacto POSITIVO sin data_gaps — "
                        "no requiere cobertura PVA obligatoria."
                    ),
                    recommendation="Ninguna acción requerida.",
                ))
            continue

        # ── Evaluar si requiere PVA ──
        if not impact_requires_pva(imp):
            ignored.append(imp.impact_id)
            issues.append(PVACoverageIssue(
                severity="INFO",
                code="PVA-COV-I001",
                impact_id=imp.impact_id,
                pva_id=None,
                message=(
                    f"{imp.impact_id}: nature={imp.nature!r} status={imp.status!r} "
                    "no requiere cobertura PVA."
                ),
                recommendation="Ninguna acción requerida.",
            ))
            continue

        # ── Buscar cobertura ──
        covering_pvas = find_pva_coverage_for_impact(imp, pva_programs)

        if not covering_pvas:
            # Sin ninguna cobertura → ERROR
            uncovered.append(imp.impact_id)
            issues.append(PVACoverageIssue(
                severity="ERROR",
                code="PVA-COV-E001",
                impact_id=imp.impact_id,
                pva_id=None,
                message=(
                    f"{imp.impact_id} [{imp.nature}] "
                    f"(significancia: {imp.significance_without_measures}): "
                    "sin cobertura PVA. "
                    "Este impacto requiere al menos una ficha PVA activa."
                ),
                recommendation=(
                    "Ejecute phase6-generate-pva --write para generar la ficha PVA, "
                    "o declare cobertura implícita en una ficha PVA existente mediante "
                    "nota de cobertura en el campo 'notes'."
                ),
            ))
            continue

        # ── Clasificar la cobertura encontrada ──
        direct_non_conditioned = [
            pva for pva in covering_pvas
            if _coverage_type(imp, pva) == COVERAGE_DIRECT
            and not _pva_is_conditioned(pva)
        ]
        direct_conditioned = [
            pva for pva in covering_pvas
            if _coverage_type(imp, pva) == COVERAGE_DIRECT
            and _pva_is_conditioned(pva)
        ]
        by_factor = [
            pva for pva in covering_pvas
            if _coverage_type(imp, pva) == COVERAGE_BY_FACTOR
        ]

        if direct_non_conditioned:
            # Cobertura plena: hay al menos un PVA directo no condicionado
            covered.append(imp.impact_id)
            # No genera incidencia adicional — es el caso correcto

        elif direct_conditioned:
            # Cobertura directa pero condicionada (CONT abierto, E-9)
            conditional.append(imp.impact_id)
            pva_ids_ref = ", ".join(p.pva_id for p in direct_conditioned)
            issues.append(PVACoverageIssue(
                severity="WARNING",
                code="PVA-COV-W001",
                impact_id=imp.impact_id,
                pva_id=direct_conditioned[0].pva_id,
                message=(
                    f"{imp.impact_id}: cobertura PVA CONDICIONADA por CONT abierto "
                    f"(fichas: {pva_ids_ref}). "
                    "El PVA no entra en vigor hasta resolver el CONT."
                ),
                recommendation=(
                    "Resolver el CONT referenciado para activar el PVA. "
                    "Si el CONT se resuelve negativamente, abrir GAP-PVA en Bloque E."
                ),
            ))

        elif by_factor:
            # Cobertura por factor (no en target_impact_ids): coverage implícita no declarada
            conditional.append(imp.impact_id)
            pva_ids_ref = ", ".join(p.pva_id for p in by_factor)
            issues.append(PVACoverageIssue(
                severity="WARNING",
                code="PVA-COV-W002",
                impact_id=imp.impact_id,
                pva_id=by_factor[0].pva_id,
                message=(
                    f"{imp.impact_id}: cobertura PVA solo por factor "
                    f"(fichas: {pva_ids_ref}) — el impacto no figura "
                    "en target_impact_ids de ninguna ficha."
                ),
                recommendation=(
                    "Añadir el impacto a target_impact_ids de la ficha PVA correspondiente, "
                    "o declarar cobertura implícita explícita en el campo 'notes' de la ficha."
                ),
            ))

        else:
            # Solo transversal u otro tipo: también condicional
            conditional.append(imp.impact_id)
            pva_ids_ref = ", ".join(p.pva_id for p in covering_pvas)
            issues.append(PVACoverageIssue(
                severity="WARNING",
                code="PVA-COV-W002",
                impact_id=imp.impact_id,
                pva_id=covering_pvas[0].pva_id,
                message=(
                    f"{imp.impact_id}: cobertura PVA transversal no declarada formalmente "
                    f"(fichas: {pva_ids_ref})."
                ),
                recommendation=(
                    "Declarar la cobertura explícitamente en target_impact_ids o en notes "
                    "de la ficha PVA."
                ),
            ))

    # ── Notas finales ──
    notes.append(
        f"Analisis de {len(model.impacts)} impactos: "
        f"{len(covered)} cubiertos / "
        f"{len(uncovered)} sin cobertura / "
        f"{len(conditional)} condicionales / "
        f"{len(ignored)} ignorados."
    )
    if uncovered:
        notes.append(
            f"Declarar GAP-PVA en Bloque E para los {len(uncovered)} "
            "impacto(s) sin cobertura."
        )
    if not model.pva_programs and model.impacts:
        notes.append(
            "Sin fichas PVA en el modelo. Ejecute phase6-generate-pva --write "
            "antes de validar la cobertura."
        )

    return PVACoverageResult(
        covered_impact_ids=covered,
        uncovered_impact_ids=uncovered,
        conditional_coverage_ids=conditional,
        ignored_impact_ids=ignored,
        issues=issues,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def build_pva_coverage_markdown(result: PVACoverageResult) -> str:
    """Genera el informe de cobertura PVA en markdown.

    Secciones:
      1. Resumen
      2. Impactos cubiertos
      3. Impactos sin cobertura (GAP-PVA)
      4. Coberturas condicionadas
      5. Impactos ignorados
      6. Incidencias y recomendaciones
    """
    lines: list[str] = []

    lines.append("# Informe de Cobertura PVA — IM-07")
    lines.append("")
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"| Categoría | Cantidad |")
    lines.append(f"|-----------|---------|")
    lines.append(f"| Cubiertos (cobertura directa activa) | {len(result.covered_impact_ids)} |")
    lines.append(f"| Sin cobertura (GAP-PVA obligatorio) | {len(result.uncovered_impact_ids)} |")
    lines.append(f"| Cobertura condicional (WARNING) | {len(result.conditional_coverage_ids)} |")
    lines.append(f"| Ignorados (no requieren PVA) | {len(result.ignored_impact_ids)} |")
    lines.append(f"| ERRORs | {result.error_count()} |")
    lines.append(f"| WARNINGs | {result.warning_count()} |")
    lines.append(f"| **Resultado** | **{'VÁLIDO' if result.is_valid() else 'NO VÁLIDO'}** |")
    lines.append("")

    lines.append("## 2. Impactos cubiertos")
    lines.append("")
    if result.covered_impact_ids:
        for imp_id in result.covered_impact_ids:
            lines.append(f"- {imp_id}: cobertura directa activa ✅")
    else:
        lines.append("_Ningún impacto con cobertura directa activa._")
    lines.append("")

    lines.append("## 3. Impactos sin cobertura (GAP-PVA)")
    lines.append("")
    if result.uncovered_impact_ids:
        lines.append(
            "> ⚠️ Los siguientes impactos no tienen ninguna ficha PVA que los cubra. "
            "Deben declararse como GAP-PVA en la sección E.5 del Bloque E."
        )
        lines.append("")
        for imp_id in result.uncovered_impact_ids:
            lines.append(f"- **{imp_id}**: SIN COBERTURA PVA — GAP-PVA obligatorio en E.5")
    else:
        lines.append("_Todos los impactos relevantes tienen cobertura PVA. ✅_")
    lines.append("")

    lines.append("## 4. Coberturas condicionadas")
    lines.append("")
    if result.conditional_coverage_ids:
        lines.append(
            "> Los siguientes impactos tienen cobertura PVA parcial o condicional. "
            "Verificar y completar según las recomendaciones."
        )
        lines.append("")
        for imp_id in result.conditional_coverage_ids:
            lines.append(f"- {imp_id}: cobertura condicional o por factor — verificar")
    else:
        lines.append("_No hay coberturas condicionadas._")
    lines.append("")

    lines.append("## 5. Impactos ignorados (no requieren PVA)")
    lines.append("")
    if result.ignored_impact_ids:
        for imp_id in result.ignored_impact_ids:
            lines.append(f"- {imp_id}")
    else:
        lines.append("_Ningún impacto ignorado._")
    lines.append("")

    lines.append("## 6. Incidencias y recomendaciones")
    lines.append("")
    if result.issues:
        errors = [i for i in result.issues if i.severity == "ERROR"]
        warnings = [i for i in result.issues if i.severity == "WARNING"]
        infos = [i for i in result.issues if i.severity == "INFO"]

        if errors:
            lines.append("### ERRORs")
            lines.append("")
            for issue in errors:
                lines.append(f"**[{issue.code}]** {issue.message}")
                lines.append(f"> _Recomendación_: {issue.recommendation}")
                lines.append("")

        if warnings:
            lines.append("### WARNINGs")
            lines.append("")
            for issue in warnings:
                lines.append(f"**[{issue.code}]** {issue.message}")
                lines.append(f"> _Recomendación_: {issue.recommendation}")
                lines.append("")

        if infos:
            lines.append("### INFOs")
            lines.append("")
            for issue in infos:
                lines.append(f"[{issue.code}] {issue.message}")
    else:
        lines.append("_Sin incidencias._")
    lines.append("")

    if result.notes:
        lines.append("## 7. Notas de trazabilidad")
        lines.append("")
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Carga desde JSON
# ---------------------------------------------------------------------------

def _parse_phase6_model_from_dict(data: dict) -> Phase6Model:
    """Reconstruye un Phase6Model mínimo desde un dict JSON.

    Solo reconstruye impactos y pva_programs, que son los únicos necesarios
    para la validación de cobertura. Actions y measures se cargan como listas
    vacías si no están presentes.
    """
    expediente_id = data.get("expediente_id", "DESCONOCIDO")

    impacts: list[EnvironmentalImpact] = []
    for imp in data.get("impacts", []):
        ca_raw = imp.get("conesa_attributes", {}) or {}
        impacts.append(EnvironmentalImpact(
            impact_id=imp["impact_id"],
            action_id=imp.get("action_id", "AC-001"),
            receptor_id=imp.get("receptor_id", "FR-001"),
            name=imp.get("name", ""),
            description=imp.get("description", ""),
            nature=imp.get("nature", "INDETERMINADO"),
            status=imp.get("status", "PENDIENTE_DATOS"),
            significance_without_measures=imp.get(
                "significance_without_measures", "NO_VALORADO"
            ),
            significance_with_measures=imp.get(
                "significance_with_measures", "NO_VALORADO"
            ),
            conesa_attributes=ConesaAttributes(**{
                k: v for k, v in ca_raw.items()
                if k in (
                    "intensidad", "extension", "momento", "persistencia",
                    "reversibilidad", "sinergia", "acumulacion",
                    "efecto", "periodicidad", "recuperabilidad",
                )
            }),
            data_gaps=imp.get("data_gaps", []),
            source_refs=imp.get("source_refs", []),
            measure_ids=imp.get("measure_ids", []),
            pva_ids=imp.get("pva_ids", []),
            warnings=imp.get("warnings", []),
            notes=imp.get("notes", []),
        ))

    pva_programs: list[PVAProgram] = []
    for pva in data.get("pva_programs", []):
        pva_programs.append(PVAProgram(
            pva_id=pva["pva_id"],
            name=pva.get("name", ""),
            factor_id=pva.get("factor_id", "FI-001"),
            indicator=pva.get("indicator", ""),
            threshold=pva.get("threshold", ""),
            frequency=pva.get("frequency", "CONDICIONAL"),
            target_impact_ids=pva.get("target_impact_ids", []),
            target_measure_ids=pva.get("target_measure_ids", []),
            responsible=pva.get("responsible", ""),
            records=pva.get("records", []),
            warnings=pva.get("warnings", []),
            notes=pva.get("notes", []),
        ))

    receptor_factors: list[ReceptorFactor] = []
    for r in data.get("receptor_factors", []):
        receptor_factors.append(ReceptorFactor(
            receptor_id=r["receptor_id"],
            inventory_factor_id=r.get("inventory_factor_id", r["receptor_id"].replace("FR-", "FI-")),
            name=r.get("name", r["receptor_id"]),
            inventory_semaphore=r.get("inventory_semaphore", "NO_CONSTA"),
            ready_from_inventory=r.get("ready_from_inventory", False),
            critical_gaps=r.get("critical_gaps", []),
            notes=r.get("notes", []),
        ))

    return Phase6Model(
        expediente_id=expediente_id,
        receptor_factors=receptor_factors,
        impacts=impacts,
        pva_programs=pva_programs,
        warnings=data.get("warnings", []),
        notes=data.get("notes", []),
    )


def validate_pva_coverage_from_json(
    path: "str | Path",
) -> PVACoverageResult:
    """Carga un JSON de Phase6Model y valida la cobertura PVA.

    Args:
        path: Ruta al JSON del Phase6Model
              (p.ej. impactos/phase6_model_with_pva.json).

    Returns:
        PVACoverageResult con el análisis de cobertura.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON es inválido o no tiene estructura esperada.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"El JSON de {path} no es un objeto (dict).")

    model = _parse_phase6_model_from_dict(data)
    return validate_pva_coverage(model)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_pva_coverage_outputs(
    result: PVACoverageResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs del validador de cobertura PVA.

    Escribe:
      - impactos/pva_coverage_result.json
      - impactos/pva_coverage_result.md

    Args:
        result: Resultado de la validación.
        output_dir: Directorio de salida (normalmente expediente/impactos/).

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "pva_coverage_result.json"
    md_path = output_dir / "pva_coverage_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_pva_coverage_markdown(result))

    return json_path, md_path
