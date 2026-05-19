"""
conesa_engine -- IM-01
Motor determinístico de valoración Conesa para Fase 6 EIA.

Calcula el índice de importancia de impactos ambientales según la metodología
Conesa-Fernández Vítora, a partir de los 10 atributos definidos en IM-00.

Fórmula:
    I = 3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc

Clasificación EIA-Agent v2.1 (convención interna):
    - Atributos incompletos (None)          → INDETERMINADO
    - I < 25                                → COMPATIBLE
    - 25 ≤ I < 50                           → MODERADO
    - 50 ≤ I < 75                           → SEVERO
    - I ≥ 75                                → CRITICO

Restricciones:
- No identifica impactos automáticamente.
- No asigna atributos Conesa automáticamente.
- No genera medidas reales.
- No genera fichas PVA reales.
- No consulta fuentes externas.
- No usa IA.
- No hace llamadas a APIs.
- No escribe archivos.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
)

# ---------------------------------------------------------------------------
# Constantes de valoración
# ---------------------------------------------------------------------------

CONESA_MIN_VALUE: int = 1
CONESA_MAX_VALUE: int = 12

# Umbrales de significancia (convención interna EIA-Agent v2.1)
_THRESHOLD_COMPATIBLE: int = 25
_THRESHOLD_MODERADO: int = 50
_THRESHOLD_SEVERO: int = 75

# Significancias negativas (resultado de la fórmula)
_CONESA_SIGNIFICANCE_COMPATIBLE: str = "COMPATIBLE"
_CONESA_SIGNIFICANCE_MODERADO: str = "MODERADO"
_CONESA_SIGNIFICANCE_SEVERO: str = "SEVERO"
_CONESA_SIGNIFICANCE_CRITICO: str = "CRITICO"
_CONESA_SIGNIFICANCE_INDETERMINADO: str = "INDETERMINADO"


# ---------------------------------------------------------------------------
# ConesaScoreResult
# ---------------------------------------------------------------------------

@dataclass
class ConesaScoreResult:
    """Resultado de la valoración Conesa de un impacto."""

    score: Optional[int]
    """Índice de importancia I calculado, o None si algún atributo falta."""

    significance: str
    """Significancia clasificada: COMPATIBLE / MODERADO / SEVERO / CRITICO / INDETERMINADO."""

    is_complete: bool
    """True si todos los atributos Conesa estaban presentes para el cálculo."""

    missing_attributes: list[str] = field(default_factory=list)
    """Nombres de los atributos faltantes (None) cuando is_complete=False."""

    warnings: list[str] = field(default_factory=list)
    """Avisos metodológicos generados durante la valoración."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "significance": self.significance,
            "is_complete": self.is_complete,
            "missing_attributes": list(self.missing_attributes),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        if self.is_complete:
            return f"I={self.score} → {self.significance}"
        missing = ", ".join(self.missing_attributes)
        return f"INDETERMINADO (faltan: {missing})"


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def classify_conesa_score(score: Optional[int]) -> str:
    """Clasifica un índice I en su categoría de significancia.

    Args:
        score: Índice de importancia calculado, o None si incompleto.

    Returns:
        Cadena de significancia según convención EIA-Agent v2.1.
    """
    if score is None:
        return _CONESA_SIGNIFICANCE_INDETERMINADO
    if score < _THRESHOLD_COMPATIBLE:
        return _CONESA_SIGNIFICANCE_COMPATIBLE
    if score < _THRESHOLD_MODERADO:
        return _CONESA_SIGNIFICANCE_MODERADO
    if score < _THRESHOLD_SEVERO:
        return _CONESA_SIGNIFICANCE_SEVERO
    return _CONESA_SIGNIFICANCE_CRITICO


def validate_conesa_attributes(attributes: ConesaAttributes) -> list[str]:
    """Valida rangos de los atributos Conesa.

    Verifica que cada atributo presente esté en [CONESA_MIN_VALUE, CONESA_MAX_VALUE].
    No genera error si el atributo es None (ausente = pendiente de valorar).

    Args:
        attributes: Instancia de ConesaAttributes a validar.

    Returns:
        Lista de cadenas de error. Vacía si todo es correcto.
    """
    errors: list[str] = []
    fields_map = {
        "intensidad": attributes.intensidad,
        "extension": attributes.extension,
        "momento": attributes.momento,
        "persistencia": attributes.persistencia,
        "reversibilidad": attributes.reversibilidad,
        "sinergia": attributes.sinergia,
        "acumulacion": attributes.acumulacion,
        "efecto": attributes.efecto,
        "periodicidad": attributes.periodicidad,
        "recuperabilidad": attributes.recuperabilidad,
    }
    for name, value in fields_map.items():
        if value is not None and not (CONESA_MIN_VALUE <= value <= CONESA_MAX_VALUE):
            errors.append(
                f"Atributo '{name}' fuera de rango: {value} "
                f"(debe estar entre {CONESA_MIN_VALUE} y {CONESA_MAX_VALUE})"
            )
    return errors


def calculate_conesa_score(attributes: ConesaAttributes) -> ConesaScoreResult:
    """Calcula el índice de importancia Conesa a partir de los 10 atributos.

    Fórmula: I = 3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc

    Si algún atributo es None, devuelve score=None, significance=INDETERMINADO.

    Args:
        attributes: Atributos de valoración Conesa (ConesaAttributes).

    Returns:
        ConesaScoreResult con el índice calculado, su clasificación y metadatos.
    """
    warnings: list[str] = []

    # Validar rangos primero
    range_errors = validate_conesa_attributes(attributes)
    for err in range_errors:
        warnings.append(f"ERROR de rango: {err}")

    missing = attributes.missing_attributes()

    if missing:
        return ConesaScoreResult(
            score=None,
            significance=_CONESA_SIGNIFICANCE_INDETERMINADO,
            is_complete=False,
            missing_attributes=missing,
            warnings=warnings,
        )

    # Todos los atributos presentes — calcular
    # Los None están descartados por la rama anterior; cast seguro
    in_ = attributes.intensidad      # type: ignore[assignment]
    ex_ = attributes.extension       # type: ignore[assignment]
    mo_ = attributes.momento         # type: ignore[assignment]
    pe_ = attributes.persistencia    # type: ignore[assignment]
    rv_ = attributes.reversibilidad  # type: ignore[assignment]
    si_ = attributes.sinergia        # type: ignore[assignment]
    ac_ = attributes.acumulacion     # type: ignore[assignment]
    ef_ = attributes.efecto          # type: ignore[assignment]
    pr_ = attributes.periodicidad    # type: ignore[assignment]
    mc_ = attributes.recuperabilidad # type: ignore[assignment]

    score: int = 3 * in_ + 2 * ex_ + mo_ + pe_ + rv_ + si_ + ac_ + ef_ + pr_ + mc_
    significance = classify_conesa_score(score)

    return ConesaScoreResult(
        score=score,
        significance=significance,
        is_complete=True,
        missing_attributes=[],
        warnings=warnings,
    )


def apply_conesa_to_impact(
    impact: EnvironmentalImpact,
    with_measures: bool = False,
) -> EnvironmentalImpact:
    """Aplica la valoración Conesa a un impacto y devuelve una copia actualizada.

    No muta el impacto original. Usa dataclasses.replace() para clonar.

    Args:
        impact: Impacto ambiental con atributos Conesa a valorar.
        with_measures: Si False (por defecto), actualiza significance_without_measures.
                       Si True, actualiza significance_with_measures.

    Returns:
        Nueva instancia de EnvironmentalImpact con la significancia actualizada
        y status=VALORADO si los atributos estaban completos.
    """
    result = calculate_conesa_score(impact.conesa_attributes)

    new_warnings = list(impact.warnings)
    for w in result.warnings:
        if w not in new_warnings:
            new_warnings.append(w)

    if not result.is_complete:
        # No se puede valorar: añadir aviso y devolver copia con status sin cambio
        aviso = (
            f"No valorado: faltan atributos Conesa: "
            f"{', '.join(result.missing_attributes)}"
        )
        if aviso not in new_warnings:
            new_warnings.append(aviso)
        return dataclasses.replace(impact, warnings=new_warnings)

    # Atributos completos — actualizar la significancia correspondiente
    significance = result.significance

    if with_measures:
        updated = dataclasses.replace(
            impact,
            significance_with_measures=significance,
            status="VALORADO",
            warnings=new_warnings,
        )
    else:
        updated = dataclasses.replace(
            impact,
            significance_without_measures=significance,
            status="VALORADO",
            warnings=new_warnings,
        )

    return updated


def score_phase6_impacts(
    model: Phase6Model,
    with_measures: bool = False,
) -> Phase6Model:
    """Valora todos los impactos de un Phase6Model y devuelve un modelo actualizado.

    No muta el modelo original. Crea nuevas instancias de Phase6Model e impactos.

    Args:
        model: Paquete de Fase 6 con impactos a valorar.
        with_measures: Propagado a apply_conesa_to_impact para cada impacto.

    Returns:
        Nueva instancia de Phase6Model con impactos valorados.
        Acciones, factores, medidas y PVA se copian sin cambios.
    """
    scored_impacts = [
        apply_conesa_to_impact(impact, with_measures=with_measures)
        for impact in model.impacts
    ]

    return dataclasses.replace(model, impacts=scored_impacts)
