"""
conesa_attribute_assigner -- IM-04
Asignador prudente de atributos Conesa para impactos identificados en Fase 6 EIA.

Asigna los 10 atributos Conesa (IN, EX, MO, PE, RV, SI, AC, EF, PR, Mc) a los
impactos identificados por IM-03, usando tablas tipológicas por receptor y tipo
de acción para proyectos R12/R13 en Canarias.

Principio rector — PRUDENCIA:
  Cuando los datos de campo o el inventario no son suficientes para determinar
  un atributo con fiabilidad, el atributo se asigna como None (INDETERMINADO)
  y la significancia queda como INDETERMINADO. No se fuerza un valor numérico
  sin evidencia.

Reglas no negociables:
  - No se asignan atributos que requieran prospección de campo en modo gabinete.
  - Los receptores ENP, Red Natura, Flora, Fauna, Paisaje y Patrimonio quedan
    INDETERMINADO en modo gabinete sin excepción.
  - La asignación es tipológica (R12/R13), no específica del expediente.
  - Nunca se afirma significancia sin tener los 10 atributos completos.
  - El módulo no crea impactos, medidas ni PVA.
  - No consulta fuentes externas.
  - No usa IA.
  - No escribe archivos desde el módulo (responsabilidad del llamador / CLI).

Dependencias: IM-00 (impact_model), IM-01 (conesa_engine), IM-03 (impact_identifier).
"""
from __future__ import annotations

import dataclasses
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.impact_model import (
    ConesaAttributes,
    EnvironmentalImpact,
    Phase6Model,
    ProjectAction,
)
from eia_agent.core.conesa_engine import apply_conesa_to_impact


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    """Normaliza texto a ASCII para consola Windows cp1252."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _all_none_attributes() -> ConesaAttributes:
    """ConesaAttributes con los 10 atributos a None (INDETERMINADO completo)."""
    return ConesaAttributes(
        intensidad=None, extension=None, momento=None,
        persistencia=None, reversibilidad=None, sinergia=None,
        acumulacion=None, efecto=None, periodicidad=None,
        recuperabilidad=None,
    )


# ---------------------------------------------------------------------------
# ConesaAssignmentRule
# ---------------------------------------------------------------------------

@dataclass
class ConesaAssignmentRule:
    """Regla tipológica de asignación de atributos Conesa a un impacto.

    Se aplica sobre el par (impacto, acción) para decidir qué conjunto de
    atributos Conesa corresponde a ese tipo de presión sobre ese receptor.

    La asignación sigue el principio de prudencia: cuando los datos de campo
    son insuficientes, los atributos quedan como None (INDETERMINADO).
    """

    rule_id: str
    """Identificador único de la regla (ej. 'CASSIGN-A')."""

    target_receptor_ids: list[str]
    """IDs de receptores objetivo (ej. ['FR-014'])."""

    conesa_attributes: ConesaAttributes
    """Atributos Conesa a asignar. None = INDETERMINADO en ese atributo."""

    action_types: list[str] = field(default_factory=list)
    """Tipos de acción que activan la regla. Vacío = cualquier tipo."""

    target_natures: list[str] = field(default_factory=list)
    """Naturalezas de impacto que activan la regla. Vacío = cualquiera."""

    notes: list[str] = field(default_factory=list)
    """Notas metodológicas de la regla."""

    def matches(
        self,
        impact: EnvironmentalImpact,
        action_lookup: Optional[dict[str, ProjectAction]] = None,
    ) -> bool:
        """Decide si esta regla aplica al impacto dado.

        Comprobaciones en orden:
          1. Receptor objetivo (obligatorio).
          2. Naturaleza del impacto (si la regla filtra por naturaleza).
          3. Tipo de acción (solo si action_lookup disponible y regla filtra
             por tipo; si action_lookup es None, se omite la comprobación).

        Args:
            impact: Impacto a evaluar.
            action_lookup: Mapa action_id → ProjectAction. Si None, la
                           comprobación de action_type se omite.

        Returns:
            True si el impacto cumple todos los criterios de la regla.
        """
        # 1. Receptor objetivo
        if impact.receptor_id not in self.target_receptor_ids:
            return False

        # 2. Naturaleza del impacto
        if self.target_natures and impact.nature not in self.target_natures:
            return False

        # 3. Tipo de acción (solo si hay lookup disponible)
        if self.action_types and action_lookup is not None:
            action = action_lookup.get(impact.action_id)
            if action is None or action.action_type not in self.action_types:
                return False

        return True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "target_receptor_ids": list(self.target_receptor_ids),
            "conesa_attributes": self.conesa_attributes.to_dict(),
            "action_types": list(self.action_types),
            "target_natures": list(self.target_natures),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# ConesaAssignmentResult
# ---------------------------------------------------------------------------

@dataclass
class ConesaAssignmentResult:
    """Resultado de la asignación de atributos Conesa sobre un Phase6Model."""

    model: Phase6Model
    """Modelo actualizado con atributos Conesa asignados."""

    assigned_count: int = 0
    """Impactos a los que se aplicó una regla."""

    scored_count: int = 0
    """De los asignados: los 10 atributos completos y significancia calculada."""

    indeterminate_count: int = 0
    """De los asignados: atributos incompletos, significancia INDETERMINADO."""

    skipped_count: int = 0
    """Impactos que ya tenían los 10 atributos completos (no se sobreescriben)."""

    no_rule_count: int = 0
    """Impactos sin regla CASSIGN aplicable."""

    warnings: list[str] = field(default_factory=list)
    """Avisos generados durante la asignación."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

    def to_dict(self) -> dict:
        return {
            "assigned_count": self.assigned_count,
            "scored_count": self.scored_count,
            "indeterminate_count": self.indeterminate_count,
            "skipped_count": self.skipped_count,
            "no_rule_count": self.no_rule_count,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "model": self.model.to_dict(),
        }

    def summary(self) -> str:
        """Resumen ASCII-safe (compatible con consola Windows cp1252)."""
        total = len(self.model.impacts)
        lines = [
            "--- IM-04 Asignador prudente de atributos Conesa ---",
            f"Impactos en el modelo : {total}",
            f"  Regla aplicada      : {self.assigned_count}",
            f"    Valorados (score) : {self.scored_count}",
            f"    Indeterminado     : {self.indeterminate_count}",
            f"  Ya completos        : {self.skipped_count}",
            f"  Sin regla aplicable : {self.no_rule_count}",
        ]
        if self.warnings:
            lines.append(f"Avisos ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"  AVISO: {_ascii_safe(w)}")
        if self.notes:
            for n in self.notes[:3]:
                lines.append(f"  Nota : {_ascii_safe(n)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reglas por defecto — CASSIGN-A a CASSIGN-J
# ---------------------------------------------------------------------------

def default_conesa_assignment_rules() -> list[ConesaAssignmentRule]:
    """10 reglas tipológicas de asignación Conesa para proyectos R12/R13 en Canarias.

    Receptores cubiertos:
      FR-003 (Suelos), FR-004 (Hidrología), FR-006 (Calidad del aire),
      FR-007 (Flora), FR-008 (Fauna), FR-009 (ENP), FR-010 (Red Natura 2000),
      FR-011 (Paisaje), FR-012 (Patrimonio cultural), FR-013 (Socioeconomía),
      FR-014 (Ruido), FR-015 (Cambio climático).

    Receptores NO cubiertos (no generados por IM-03):
      FR-001 (Clima), FR-002 (Geología), FR-005 (Inundabilidad),
      FR-016 (Riesgos naturales).

    Principio de prudencia gabinete:
      FR-007, FR-008, FR-009, FR-010, FR-011, FR-012 → todos los atributos
      a None (INDETERMINADO) por requerir prospección de campo o consultas
      a inventarios específicos no disponibles en modo gabinete.

    Fórmula Conesa: I = 3·IN + 2·EX + MO + PE + RV + SI + AC + EF + PR + Mc
    Umbrales: <25 COMPATIBLE · 25-49 MODERADO · 50-74 SEVERO · ≥75 CRITICO
    """
    return [
        # CASSIGN-A — Ruido (FR-014)
        # Fuente: tabla tipológica R12/R13 para ruido operacional y de transporte.
        # I = 3(2)+2(2)+4+2+2+1+4+4+4+2 = 33 → MODERADO
        ConesaAssignmentRule(
            rule_id="CASSIGN-A",
            target_receptor_ids=["FR-014"],
            action_types=["OPERACION", "TRANSPORTE", "AUXILIAR"],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=2, momento=4, persistencia=2,
                reversibilidad=2, sinergia=1, acumulacion=4, efecto=4,
                periodicidad=4, recuperabilidad=2,
            ),
            notes=[
                "Tabla tipologica R12/R13: ruido de operaciones mecanicas y transporte.",
                "I = 3(2)+2(2)+4+2+2+1+4+4+4+2 = 33 → MODERADO.",
                "Valores conservadores para polígono industrial tipo R12/R13.",
            ],
        ),
        # CASSIGN-B — Calidad del aire (FR-006)
        # Fuente: tabla tipológica R12/R13 para partículas y emisiones locales.
        # EX=1 (extensión puntual, afección local al entorno del polígono).
        # I = 3(2)+2(1)+4+2+2+1+4+4+4+2 = 31 → MODERADO
        ConesaAssignmentRule(
            rule_id="CASSIGN-B",
            target_receptor_ids=["FR-006"],
            action_types=["OPERACION", "TRANSPORTE", "AUXILIAR"],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=1, momento=4, persistencia=2,
                reversibilidad=2, sinergia=1, acumulacion=4, efecto=4,
                periodicidad=4, recuperabilidad=2,
            ),
            notes=[
                "Tabla tipologica R12/R13: particulas y emisiones de operaciones mecanicas.",
                "EX=1: extension puntual, afeccion local. I = 3(2)+2(1)+4+2+2+1+4+4+4+2 = 31 → MODERADO.",
            ],
        ),
        # CASSIGN-C — Suelos (FR-003)
        # Aplica a cualquier tipo de acción que genera impactos sobre suelos:
        # ALMACENAMIENTO (RULE-A), OPERACION (RULE-D), MANTENIMIENTO (RULE-G), CESE (RULE-I).
        # PE=4 y RV=4 por el carácter potencialmente irreversible de la contaminación de suelo.
        # I = 3(2)+2(1)+2+4+4+1+1+4+1+4 = 29 → MODERADO
        ConesaAssignmentRule(
            rule_id="CASSIGN-C",
            target_receptor_ids=["FR-003"],
            action_types=[],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=1, momento=2, persistencia=4,
                reversibilidad=4, sinergia=1, acumulacion=1, efecto=4,
                periodicidad=1, recuperabilidad=4,
            ),
            notes=[
                "Tabla tipologica: riesgo de contaminacion de suelo.",
                "PE=4 y RV=4: persistente y dificil de revertir si se produce contaminacion.",
                "I = 3(2)+2(1)+2+4+4+1+1+4+1+4 = 29 → MODERADO.",
            ],
        ),
        # CASSIGN-D — Hidrología (FR-004)
        # Aplica a cualquier tipo de acción (ALMACENAMIENTO por RULE-A, MANTENIMIENTO por RULE-G).
        # Valores conservadores: riesgo de afección indirecta, sin datos de campo.
        # I = 3(2)+2(1)+2+2+2+1+1+4+1+2 = 23 → COMPATIBLE
        ConesaAssignmentRule(
            rule_id="CASSIGN-D",
            target_receptor_ids=["FR-004"],
            action_types=[],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=1, momento=2, persistencia=2,
                reversibilidad=2, sinergia=1, acumulacion=1, efecto=4,
                periodicidad=1, recuperabilidad=2,
            ),
            notes=[
                "Tabla tipologica: riesgo de afeccion hidrologica indirecta.",
                "Valores conservadores sin datos de campo. I = 3(2)+2(1)+2+2+2+1+1+4+1+2 = 23 → COMPATIBLE.",
            ],
        ),
        # CASSIGN-E — ENP + Red Natura 2000 (FR-009, FR-010) → INDETERMINADO
        # Requiere cartografía detallada de la envolvente del espacio protegido
        # y prospección de campo para determinar presencia/ausencia de hábitats.
        ConesaAssignmentRule(
            rule_id="CASSIGN-E",
            target_receptor_ids=["FR-009", "FR-010"],
            action_types=[],
            conesa_attributes=_all_none_attributes(),
            notes=[
                "ENP y Red Natura 2000: INDETERMINADO en modo gabinete.",
                "Requiere cartografia detallada de la envolvente del espacio protegido",
                "y prospeccion de campo para determinar presencia/ausencia de habitats.",
                "Regla de prudencia: no se afirma ausencia de impacto sin estas fuentes.",
            ],
        ),
        # CASSIGN-F — Flora + Fauna (FR-007, FR-008) → INDETERMINADO
        # No se pueden asignar atributos Conesa sin inventario biológico específico.
        ConesaAssignmentRule(
            rule_id="CASSIGN-F",
            target_receptor_ids=["FR-007", "FR-008"],
            action_types=[],
            conesa_attributes=_all_none_attributes(),
            notes=[
                "Flora y fauna: INDETERMINADO sin prospeccion de campo.",
                "Se requiere inventario biologico especifico (flora y fauna).",
                "Regla de prudencia gabinete: no afirmar ausencia de impacto sin inventario biologico.",
            ],
        ),
        # CASSIGN-G — Patrimonio cultural (FR-012) → INDETERMINADO
        # Requiere consulta al inventario patrimonial de la CCAA y al Servicio de
        # Patrimonio Histórico del Cabildo/Consejería competente.
        ConesaAssignmentRule(
            rule_id="CASSIGN-G",
            target_receptor_ids=["FR-012"],
            action_types=[],
            conesa_attributes=_all_none_attributes(),
            notes=[
                "Patrimonio cultural: INDETERMINADO sin consulta al inventario patrimonial.",
                "Se requiere informe del Servicio de Patrimonio Historico.",
            ],
        ),
        # CASSIGN-H — Cambio climático (FR-015)
        # EX=8: el cambio climático tiene escala global.
        # RV, SI y Mc: INDETERMINADO sin cuantificación de emisiones de GEI.
        # → Significancia INDETERMINADO hasta disponer de huella de carbono.
        ConesaAssignmentRule(
            rule_id="CASSIGN-H",
            target_receptor_ids=["FR-015"],
            action_types=["OPERACION", "TRANSPORTE", "AUXILIAR"],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=8, momento=4, persistencia=4,
                reversibilidad=None, sinergia=None, acumulacion=4, efecto=4,
                periodicidad=4, recuperabilidad=None,
            ),
            notes=[
                "Cambio climatico: EX=8 (escala global). IN=2 conservador para R12/R13.",
                "RV, SI y Mc → INDETERMINADO sin cuantificacion de emisiones de GEI.",
                "Significancia INDETERMINADO hasta disponer de huella de carbono cuantificada.",
                "Regla de prudencia: no cuantificar GEI sin datos de emision del promotor.",
            ],
        ),
        # CASSIGN-I — Paisaje (FR-011) → INDETERMINADO
        # Requiere análisis de cuenca visual y fotomontaje desde puntos representativos.
        ConesaAssignmentRule(
            rule_id="CASSIGN-I",
            target_receptor_ids=["FR-011"],
            action_types=[],
            conesa_attributes=_all_none_attributes(),
            notes=[
                "Paisaje: INDETERMINADO sin analisis de cuenca visual ni fotomontaje.",
                "Se requiere estudio de impacto visual desde puntos representativos.",
            ],
        ),
        # CASSIGN-J — Socioeconomía positivo (FR-013, naturaleza POSITIVO)
        # Valores conservadores para empleo y actividad económica local (R12/R13).
        # I = 3(2)+2(2)+4+4+4+1+1+1+4+4 = 33 → MODERADO positivo.
        # Regla de no compensación: este impacto positivo no compensa los negativos.
        ConesaAssignmentRule(
            rule_id="CASSIGN-J",
            target_receptor_ids=["FR-013"],
            target_natures=["POSITIVO"],
            action_types=[],
            conesa_attributes=ConesaAttributes(
                intensidad=2, extension=2, momento=4, persistencia=4,
                reversibilidad=4, sinergia=1, acumulacion=1, efecto=1,
                periodicidad=4, recuperabilidad=4,
            ),
            notes=[
                "Impacto positivo en socioeconomia: empleo y actividad economica local.",
                "Valores conservadores. I = 3(2)+2(2)+4+4+4+1+1+1+4+4 = 33 → MODERADO positivo.",
                "Regla de no compensacion: este impacto POSITIVO no compensa impactos negativos.",
                "Cada impacto se registra y evalua de forma independiente.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Función interna de asignación por impacto
# ---------------------------------------------------------------------------

def _assign_single_impact(
    impact: EnvironmentalImpact,
    rules: list[ConesaAssignmentRule],
    action_lookup: Optional[dict[str, ProjectAction]],
    score: bool,
) -> tuple[EnvironmentalImpact, str]:
    """Asigna atributos Conesa a un único impacto y devuelve el código de resultado.

    Args:
        impact: Impacto a procesar.
        rules: Lista de reglas a evaluar en orden (primera coincidencia gana).
        action_lookup: Mapa action_id → ProjectAction para comprobación de tipo.
        score: Si True, aplica valoración Conesa (IM-01) tras la asignación.

    Returns:
        Tupla (nuevo_impacto, codigo_resultado) donde codigo_resultado es:
          'assigned_scored'        — regla aplicada, 10 atributos completos, score OK
          'assigned_indeterminate' — regla aplicada, atributos incompletos, INDETERMINADO
          'skipped'                — ya tenía atributos completos (no sobreescrito)
          'no_rule'                — sin regla aplicable para este impacto
    """
    # ── Impacto ya completo: no sobreescribir ──
    if impact.conesa_attributes.is_complete():
        if score:
            return apply_conesa_to_impact(impact, with_measures=False), "skipped"
        return impact, "skipped"

    # ── Buscar primera regla aplicable ──
    matched_rule: Optional[ConesaAssignmentRule] = None
    for rule in rules:
        if rule.matches(impact, action_lookup):
            matched_rule = rule
            break

    if matched_rule is None:
        return impact, "no_rule"

    # ── Aplicar atributos de la regla ──
    added_notes = (
        [f"Atributos Conesa asignados por {matched_rule.rule_id}."]
        + list(matched_rule.notes)
    )
    new_impact = dataclasses.replace(
        impact,
        conesa_attributes=matched_rule.conesa_attributes,
        notes=list(impact.notes) + added_notes,
    )

    # ── Puntuar si se solicita ──
    if score:
        new_impact = apply_conesa_to_impact(new_impact, with_measures=False)

    # ── Código de resultado según completitud ──
    if matched_rule.conesa_attributes.is_complete():
        return new_impact, "assigned_scored"
    return new_impact, "assigned_indeterminate"


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def assign_conesa_attributes_to_impact(
    impact: EnvironmentalImpact,
    rules: Optional[list[ConesaAssignmentRule]] = None,
    action_lookup: Optional[dict[str, ProjectAction]] = None,
    score: bool = True,
) -> EnvironmentalImpact:
    """Asigna atributos Conesa a un impacto individual.

    Función pura sin efectos secundarios. No muta el impacto original.

    Si el impacto ya tiene los 10 atributos completos, no se sobreescriben.
    Si no hay regla aplicable, el impacto se devuelve sin cambios.

    Args:
        impact: Impacto a enriquecer con atributos Conesa.
        rules: Reglas de asignación. Si None, usa las 10 reglas por defecto.
        action_lookup: Mapa action_id → ProjectAction para comprobación de tipo.
                       Si None, la comprobación de action_type se omite.
        score: Si True (por defecto), aplica la valoración Conesa (IM-01) tras
               la asignación y actualiza significance_without_measures.

    Returns:
        Nueva instancia de EnvironmentalImpact con los atributos asignados.
    """
    if rules is None:
        rules = default_conesa_assignment_rules()

    new_impact, _ = _assign_single_impact(impact, rules, action_lookup, score)
    return new_impact


def assign_conesa_attributes_to_model(
    model: Phase6Model,
    rules: Optional[list[ConesaAssignmentRule]] = None,
    score: bool = True,
) -> ConesaAssignmentResult:
    """Asigna atributos Conesa a todos los impactos de un Phase6Model.

    Función pura sin efectos secundarios. No muta el modelo original.
    Construye internamente el action_lookup a partir de model.actions.

    Args:
        model: Paquete de Fase 6 con impactos identificados (output de IM-03).
        rules: Reglas de asignación. Si None, usa las 10 reglas por defecto.
        score: Si True (por defecto), aplica la valoración Conesa (IM-01) a
               cada impacto tras la asignación de atributos.

    Returns:
        ConesaAssignmentResult con el modelo actualizado y estadísticas.
        Conserva actions, receptor_factors, measures y pva_programs sin cambios.
        Solo actualiza la lista impacts.
    """
    if rules is None:
        rules = default_conesa_assignment_rules()

    action_lookup: dict[str, ProjectAction] = {
        a.action_id: a for a in model.actions
    }

    new_impacts: list[EnvironmentalImpact] = []
    assigned_count = 0
    scored_count = 0
    indeterminate_count = 0
    skipped_count = 0
    no_rule_count = 0
    warnings: list[str] = []
    notes: list[str] = []

    for impact in model.impacts:
        new_impact, outcome = _assign_single_impact(
            impact, rules, action_lookup, score
        )
        new_impacts.append(new_impact)

        if outcome == "assigned_scored":
            assigned_count += 1
            scored_count += 1
        elif outcome == "assigned_indeterminate":
            assigned_count += 1
            indeterminate_count += 1
        elif outcome == "skipped":
            skipped_count += 1
        elif outcome == "no_rule":
            no_rule_count += 1
            warnings.append(
                f"Sin regla CASSIGN para {impact.impact_id} "
                f"(receptor={impact.receptor_id}, accion={impact.action_id})."
            )

    if not model.impacts:
        warnings.append(
            "El modelo no contiene impactos. "
            "Ejecute primero IM-03 (phase6-identify-impacts --write)."
        )

    if no_rule_count > 0:
        notes.append(
            f"{no_rule_count} impacto(s) sin regla CASSIGN aplicable. "
            "Los receptores FR-001, FR-002, FR-005 y FR-016 no tienen reglas "
            "porque IM-03 no genera impactos sobre ellos con las reglas por defecto."
        )

    updated_model = dataclasses.replace(model, impacts=new_impacts)

    return ConesaAssignmentResult(
        model=updated_model,
        assigned_count=assigned_count,
        scored_count=scored_count,
        indeterminate_count=indeterminate_count,
        skipped_count=skipped_count,
        no_rule_count=no_rule_count,
        warnings=warnings,
        notes=notes,
    )
