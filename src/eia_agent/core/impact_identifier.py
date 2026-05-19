"""
impact_identifier -- IM-03
Identificador preliminar de impactos accion x receptor para Fase 6 EIA.

Lee las acciones (ProjectAction) y factores receptores (ReceptorFactor) de un
Phase6Model y aplica un conjunto de reglas deterministas para identificar los
posibles impactos ambientales preliminares.

Los impactos generados siempre tienen:
  - status: PENDIENTE_DATOS o INDETERMINADO (nunca VALORADO, IDENTIFICADO ni DESCARTADO)
  - significance_without_measures: NO_VALORADO (sin Conesa)
  - significance_with_measures: NO_VALORADO (sin Conesa)

Restricciones del modulo:
  - No valora impactos (sin calculo Conesa — eso es IM-01).
  - No genera medidas correctoras.
  - No genera PVA.
  - No usa IA.
  - No consulta fuentes externas.
  - No hace llamadas a APIs.
  - No escribe archivos (la escritura es responsabilidad del llamador o de la CLI).

Reglas por defecto (RULE-A a RULE-J):
  Cubren receptores FR-003/004/006/007/008/009/010/011/012/013/014/015.
  No cubren FR-001 (Clima), FR-002 (Geologia), FR-005 (Inundabilidad),
  FR-016 (Riesgos naturales): sin vias de afeccion directa para R12/R13.

Depende de:
  IM-00 (impact_model) — EnvironmentalImpact, Phase6Model, ProjectAction, ReceptorFactor
  IM-02 (project_action_builder) — proporciona el modelo con acciones ya construidas
"""
from __future__ import annotations

import dataclasses
import unicodedata
from dataclasses import dataclass, field

from eia_agent.core.impact_model import (
    RECEPTOR_FACTOR_IDS,
    RECEPTOR_FACTOR_NAMES,
    EnvironmentalImpact,
    Phase6Model,
    ProjectAction,
    ReceptorFactor,
)


# ---------------------------------------------------------------------------
# Normalización de texto
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Elimina acentos y convierte a minusculas para comparacion robusta."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii").lower()


# ---------------------------------------------------------------------------
# Dataclass de regla
# ---------------------------------------------------------------------------

@dataclass
class ImpactIdentificationRule:
    """Regla determinista de identificacion de impacto accion x receptor.

    Una regla se aplica cuando:
      1. action.action_type esta en action_types
         (lista vacia = cualquier tipo de accion).
      2. receptor.receptor_id esta en target_receptor_ids.
      3. Si operation_keywords es no vacio, al menos un keyword aparece en
         el texto normalizado de action.name + action.description.

    Genera un EnvironmentalImpact con status=status y nature=nature.
    No asigna significancia (siempre NO_VALORADO).
    """

    rule_id: str
    action_types: list[str] = field(default_factory=list)
    operation_keywords: list[str] = field(default_factory=list)
    target_receptor_ids: list[str] = field(default_factory=list)
    impact_name_template: str = "Impacto de {action_name} sobre {receptor_name}"
    nature: str = "NEGATIVO"
    status: str = "PENDIENTE_DATOS"
    default_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def matches(self, action: ProjectAction, receptor: ReceptorFactor) -> bool:
        """True si la regla aplica para el par (action, receptor)."""
        if self.action_types and action.action_type not in self.action_types:
            return False
        if receptor.receptor_id not in self.target_receptor_ids:
            return False
        if self.operation_keywords:
            text = _normalize(action.name + " " + action.description)
            if not any(kw in text for kw in self.operation_keywords):
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "action_types": list(self.action_types),
            "operation_keywords": list(self.operation_keywords),
            "target_receptor_ids": list(self.target_receptor_ids),
            "impact_name_template": self.impact_name_template,
            "nature": self.nature,
            "status": self.status,
            "default_gaps": list(self.default_gaps),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------

@dataclass
class ImpactIdentificationResult:
    """Resultado de la identificacion preliminar de impactos (IM-03).

    Campos:
        impacts:  Lista de EnvironmentalImpact identificados.
        warnings: Avisos metodologicos (sin acciones, sin receptores, etc.).
        notes:    Notas de trazabilidad del proceso de identificacion.
    """

    impacts: list[EnvironmentalImpact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "impacts": [i.to_dict() for i in self.impacts],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        count = len(self.impacts)
        plural_s = "s" if count != 1 else ""
        lines = [
            f"ImpactIdentificationResult: {count} "
            f"impacto{plural_s} preliminar{plural_s} identificado{plural_s}."
        ]
        if self.impacts:
            by_nature: dict[str, int] = {}
            by_status: dict[str, int] = {}
            for imp in self.impacts:
                by_nature[imp.nature] = by_nature.get(imp.nature, 0) + 1
                by_status[imp.status] = by_status.get(imp.status, 0) + 1
            lines.append(
                "  Por naturaleza: "
                + ", ".join(f"{k}:{v}" for k, v in sorted(by_nature.items()))
            )
            lines.append(
                "  Por estado: "
                + ", ".join(f"{k}:{v}" for k, v in sorted(by_status.items()))
            )
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reglas por defecto (RULE-A a RULE-J)
# ---------------------------------------------------------------------------

def default_impact_identification_rules() -> list[ImpactIdentificationRule]:
    """Devuelve las 10 reglas de identificacion de impactos por defecto.

    Cubren receptores FR-003/004/006/007/008/009/010/011/012/013/014/015.
    Las reglas son deterministas, sin IA, sin consultas externas.
    Los impactos generados necesitan revision tecnica para confirmacion.
    """
    return [
        # RULE-A: Almacenamiento → suelos e hidrologia
        ImpactIdentificationRule(
            rule_id="RULE-A",
            action_types=["ALMACENAMIENTO"],
            operation_keywords=[],
            target_receptor_ids=["FR-003", "FR-004"],
            impact_name_template=(
                "Riesgo de contaminacion de {receptor_name} "
                "por almacenamiento de residuos"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Confirmar tipo de solera (impermeabilizada o no)",
                "GAP: Verificar existencia de sistemas de contencion de lixiviados",
                "GAP: Comprobar distancia a masas de agua superficiales o subterraneas",
            ],
            notes=[
                "Regla para almacenamiento temporal: residuos sobre suelo "
                "pueden generar lixiviados."
            ],
        ),
        # RULE-B: Tratamiento mecanico → calidad del aire y ruido
        ImpactIdentificationRule(
            rule_id="RULE-B",
            action_types=["OPERACION"],
            operation_keywords=[
                "tratamiento", "trituraci", "cizalla", "molino",
                "prensa", "compactaci", "cribado", "mecanico",
            ],
            target_receptor_ids=["FR-006", "FR-014"],
            impact_name_template=(
                "Emisiones de polvo y ruido por {action_name} "
                "sobre {receptor_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Cuantificar emisiones de polvo y ruido "
                "(sin datos acusticos del promotor)",
                "GAP: Verificar distancia a receptores sensibles "
                "(viviendas, zonas residenciales)",
            ],
            notes=[
                "Regla para tratamiento mecanico: trituracion, molino y "
                "prensa generan polvo y ruido."
            ],
        ),
        # RULE-C: Transporte → calidad del aire, ruido y cambio climatico
        ImpactIdentificationRule(
            rule_id="RULE-C",
            action_types=["TRANSPORTE"],
            operation_keywords=[],
            target_receptor_ids=["FR-006", "FR-014", "FR-015"],
            impact_name_template=(
                "Emisiones y ruido por {action_name} sobre {receptor_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Estimar numero de movimientos de vehiculos pesados al dia",
                "GAP: Verificar tipo de vehiculos y antiguedad del parque "
                "de transportes",
            ],
            notes=[
                "Regla para transporte: movimiento de vehiculos genera "
                "emisiones, ruido y GEI."
            ],
        ),
        # RULE-D: Clasificacion y separacion → suelos
        ImpactIdentificationRule(
            rule_id="RULE-D",
            action_types=["OPERACION"],
            operation_keywords=["clasificaci", "separaci", "selecci", "triaje"],
            target_receptor_ids=["FR-003"],
            impact_name_template=(
                "Arrastre de finos y contaminacion de {receptor_name} "
                "por {action_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Verificar si la zona de clasificacion esta sobre "
                "solera impermeabilizada",
                "GAP: Comprobar si hay sistema de recogida de aguas "
                "pluviales contaminadas",
            ],
            notes=[
                "Regla para clasificacion: material fino y contaminantes "
                "pueden arrastrarse al suelo."
            ],
        ),
        # RULE-E: Actividades operativas → ENP y Red Natura 2000 (INDETERMINADO)
        ImpactIdentificationRule(
            rule_id="RULE-E",
            action_types=["OPERACION", "ALMACENAMIENTO", "TRANSPORTE"],
            operation_keywords=[],
            target_receptor_ids=["FR-009", "FR-010"],
            impact_name_template=(
                "Posible afeccion a {receptor_name} por {action_name}"
            ),
            nature="NEGATIVO",
            status="INDETERMINADO",
            default_gaps=[
                "GAP: Verificar distancia a ENP/Red Natura 2000 mas proximos "
                "(requiere consulta cartografica IDECAN/Grafcan)",
                "GAP: Determinar si el emplazamiento o su entorno proximo "
                "esta en zona de influencia de ENP",
            ],
            notes=[
                "Regla para ENP/Red Natura: afeccion indeterminada hasta "
                "consulta cartografica.",
                "No afirmar ausencia de afeccion sin verificacion en "
                "IDECAN/Grafcan.",
            ],
        ),
        # RULE-F: Cualquier actividad → flora y fauna (INDETERMINADO)
        ImpactIdentificationRule(
            rule_id="RULE-F",
            action_types=[],
            operation_keywords=[],
            target_receptor_ids=["FR-007", "FR-008"],
            impact_name_template=(
                "Posible afeccion a {receptor_name} por {action_name}"
            ),
            nature="NEGATIVO",
            status="INDETERMINADO",
            default_gaps=[
                "GAP: No consta prospeccion de campo para flora y fauna",
                "GAP: Comprobar si el emplazamiento esta en zona de interes "
                "faunistico segun cartografia disponible",
            ],
            notes=[
                "Regla para flora/fauna: en modo gabinete no es posible "
                "descartar afeccion.",
                "Segun Regla de prudencia: no afirmar ausencia de afeccion "
                "sin prospeccion de campo.",
            ],
        ),
        # RULE-G: Mantenimiento → suelos e hidrologia
        ImpactIdentificationRule(
            rule_id="RULE-G",
            action_types=["MANTENIMIENTO"],
            operation_keywords=[],
            target_receptor_ids=["FR-003", "FR-004"],
            impact_name_template=(
                "Riesgo de contaminacion de {receptor_name} "
                "por {action_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Confirmar zona habilitada para almacenamiento de "
                "residuos peligrosos propios",
                "GAP: Verificar existencia de deposito de emergencia "
                "en caso de vertido",
            ],
            notes=[
                "Regla para mantenimiento: aceites, filtros y baterias "
                "implican riesgo de vertido al suelo."
            ],
        ),
        # RULE-H: Operacion/Auxiliar → paisaje
        ImpactIdentificationRule(
            rule_id="RULE-H",
            action_types=["OPERACION", "AUXILIAR"],
            operation_keywords=[],
            target_receptor_ids=["FR-011"],
            impact_name_template=(
                "Integracion paisajistica de {action_name} "
                "sobre {receptor_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Caracterizar entorno visual del emplazamiento "
                "(uso industrial, periurbano, rural)",
                "GAP: Comprobar si la actividad es visible desde vias "
                "publicas o espacios habitados",
            ],
            notes=[
                "Regla para paisaje: instalaciones de gestion de residuos "
                "tienen impacto visual."
            ],
        ),
        # RULE-I: Cese → suelos y patrimonio cultural
        ImpactIdentificationRule(
            rule_id="RULE-I",
            action_types=["CESE"],
            operation_keywords=[],
            target_receptor_ids=["FR-003", "FR-012"],
            impact_name_template=(
                "Residuos de derribo y afeccion a {receptor_name} "
                "por {action_name}"
            ),
            nature="NEGATIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Definir plan de desmantelamiento y gestion de "
                "residuos de derribo",
                "GAP: Verificar si hay elementos con valor patrimonial "
                "en el entorno",
            ],
            notes=[
                "Regla para cese: el desmantelamiento genera residuos "
                "de construccion y demolicion."
            ],
        ),
        # RULE-J: Actividades productivas → socioeconomia (POSITIVO)
        ImpactIdentificationRule(
            rule_id="RULE-J",
            action_types=["ALMACENAMIENTO", "OPERACION"],
            operation_keywords=[],
            target_receptor_ids=["FR-013"],
            impact_name_template=(
                "Impacto socioeconomico positivo de {action_name} "
                "sobre {receptor_name}"
            ),
            nature="POSITIVO",
            status="PENDIENTE_DATOS",
            default_gaps=[
                "GAP: Cuantificar empleo directo e indirecto generado "
                "por la actividad",
            ],
            notes=[
                "Regla para socioeconomia: la actividad genera empleo "
                "y actividad economica local.",
                "NOTA: Un impacto positivo no compensa los negativos. "
                "Se registra de forma independiente.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Helper: factores receptores minimos sin inventario
# ---------------------------------------------------------------------------

def build_minimal_receptor_factors() -> list[ReceptorFactor]:
    """Crea 16 ReceptorFactor con valores por defecto, sin datos de inventario.

    Util para pruebas y para el CLI cuando no hay InventorySummary disponible.
    Los factores tienen ready_from_inventory=False y semaforo NO_CONSTA.
    No valida gaps — todos los factores empiezan sin critical_gaps.
    """
    result: list[ReceptorFactor] = []
    for fr_id in sorted(RECEPTOR_FACTOR_IDS.keys()):
        fi_id = RECEPTOR_FACTOR_IDS[fr_id]
        name = RECEPTOR_FACTOR_NAMES.get(fr_id, fr_id)
        result.append(
            ReceptorFactor(
                receptor_id=fr_id,
                inventory_factor_id=fi_id,
                name=name,
                inventory_semaphore="NO_CONSTA",
                ready_from_inventory=False,
                critical_gaps=[],
                notes=["Factor creado sin datos de inventario (IM-03)."],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Identificador principal
# ---------------------------------------------------------------------------

def identify_impacts_from_model(
    model: Phase6Model,
    rules: list[ImpactIdentificationRule] | None = None,
) -> ImpactIdentificationResult:
    """Identifica impactos preliminares aplicando reglas accion x receptor.

    Para cada par (action, receptor) y cada regla, si la regla aplica y la
    combinacion no ha sido vista antes, genera un EnvironmentalImpact con:
      - status: regla.status (PENDIENTE_DATOS o INDETERMINADO);
        si receptor tiene critical_gaps y la regla dice PENDIENTE_DATOS,
        se eleva a INDETERMINADO.
      - significance_without_measures / significance_with_measures: NO_VALORADO.
      - nature: regla.nature.
      - data_gaps: regla.default_gaps.

    No hay calculo Conesa. No hay medidas. No hay PVA.
    Garantiza unicidad por (action_id, receptor_id, rule_id).

    Args:
        model: Phase6Model con acciones y factores receptores.
        rules: Lista de reglas. Si None, usa default_impact_identification_rules().

    Returns:
        ImpactIdentificationResult con impactos, avisos y notas.
    """
    if rules is None:
        rules = default_impact_identification_rules()

    warnings_out: list[str] = []
    notes_out: list[str] = []

    if not model.actions:
        warnings_out.append(
            "No hay acciones en el modelo. No se generan impactos. "
            "Ejecute primero phase6-actions --write."
        )
        return ImpactIdentificationResult(
            impacts=[], warnings=warnings_out, notes=notes_out
        )

    if not model.receptor_factors:
        warnings_out.append(
            "No hay factores receptores en el modelo. No se generan impactos. "
            "Proporcione un InventorySummary o use build_minimal_receptor_factors()."
        )
        return ImpactIdentificationResult(
            impacts=[], warnings=warnings_out, notes=notes_out
        )

    impacts: list[EnvironmentalImpact] = []
    seen: set[tuple[str, str, str]] = set()  # (action_id, receptor_id, rule_id)
    counter = 1

    for action in model.actions:
        for receptor in model.receptor_factors:
            for rule in rules:
                key = (action.action_id, receptor.receptor_id, rule.rule_id)
                if key in seen:
                    continue
                if not rule.matches(action, receptor):
                    continue
                seen.add(key)

                impact_id = f"IMP-{counter:03d}"
                counter += 1

                try:
                    name = rule.impact_name_template.format(
                        action_name=action.name,
                        receptor_name=receptor.name,
                    )
                except (KeyError, IndexError):
                    name = f"Impacto de {action.name} sobre {receptor.name}"

                # Elevar a INDETERMINADO si receptor tiene gaps criticos
                status = rule.status
                if status == "PENDIENTE_DATOS" and receptor.critical_gaps:
                    status = "INDETERMINADO"

                impact = EnvironmentalImpact(
                    impact_id=impact_id,
                    action_id=action.action_id,
                    receptor_id=receptor.receptor_id,
                    name=name,
                    description=(
                        f"Identificado preliminarmente por regla {rule.rule_id}. "
                        "Sin valoracion Conesa. Requiere revision tecnica del analista."
                    ),
                    nature=rule.nature,
                    status=status,
                    significance_without_measures="NO_VALORADO",
                    significance_with_measures="NO_VALORADO",
                    data_gaps=list(rule.default_gaps),
                    source_refs=[f"IM-03 regla {rule.rule_id}"],
                    notes=[
                        f"Regla aplicada: {rule.rule_id}",
                        f"Accion: {action.action_id} [{action.action_type}]",
                        f"Receptor: {receptor.receptor_id} — {receptor.name}",
                    ] + list(rule.notes),
                )
                impacts.append(impact)

    if impacts:
        notes_out.append(
            f"IM-03: {len(impacts)} impacto(s) preliminar(es) identificado(s) "
            f"desde {len(model.actions)} accion(es) x "
            f"{len(model.receptor_factors)} receptor(es). "
            "Revisar con el tecnico responsable del expediente."
        )
    else:
        warnings_out.append(
            "No se identificaron impactos preliminares. "
            "Comprobar si las acciones y receptores estan correctamente "
            "configurados y si las reglas activas son adecuadas."
        )

    return ImpactIdentificationResult(
        impacts=impacts,
        warnings=warnings_out,
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# Integracion con Phase6Model
# ---------------------------------------------------------------------------

def merge_identified_impacts_into_model(
    model: Phase6Model,
    impacts: list[EnvironmentalImpact],
) -> Phase6Model:
    """Sustituye los impactos de un Phase6Model por una nueva lista.

    No muta el modelo original. Usa dataclasses.replace() para clonar.
    Conserva actions, receptor_factors, measures y pva_programs intactos.

    Args:
        model:   Phase6Model original (no se modifica).
        impacts: Nueva lista de EnvironmentalImpact a asignar.

    Returns:
        Nueva instancia de Phase6Model con los impactos actualizados.
    """
    return dataclasses.replace(model, impacts=list(impacts))


def build_phase6_model_with_identified_impacts(
    model: Phase6Model,
    rules: list[ImpactIdentificationRule] | None = None,
) -> Phase6Model:
    """Identifica impactos preliminares y los fusiona en el Phase6Model.

    Combina identify_impacts_from_model + merge_identified_impacts_into_model.
    No crea medidas ni PVA. No valora impactos (sin Conesa).

    Args:
        model: Phase6Model con acciones y factores receptores.
        rules: Lista de reglas. Si None, usa default_impact_identification_rules().

    Returns:
        Nueva instancia de Phase6Model con impactos preliminares.
        actions, receptor_factors, measures y pva_programs sin cambios.
    """
    result = identify_impacts_from_model(model, rules)
    return merge_identified_impacts_into_model(model, result.impacts)
