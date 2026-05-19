"""
mitigation_measure_generator -- IM-05
Generador determinístico de medidas ambientales por tipo de impacto para Fase 6 EIA.

Genera propuestas de medidas preventivas, correctoras, protectoras,
diagnósticas, documentales y PRL_NO_EIA vinculadas a los impactos
identificados y valorados por IM-03 e IM-04.

ID canónico: IM-05 (el anterior IM-04 Medidas correctoras, renumerado para dar
paso al Asignador prudente de atributos Conesa en IM-04).

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica valoraciones Conesa (significance_without_measures ni
    significance_with_measures).
  - No genera PVA.
  - No reduce significancia de impactos.
  - No compensa impactos negativos con positivos.
  - Las medidas PRL_NO_EIA (measure_type='PRL_NO_EIA', is_prl_only=True) se
    generan separadas y no cuentan como medidas EIA reductoras de significancia.
  - Las medidas diagnósticas (is_diagnostic=True) no se contabilizan como
    reductoras de significancia.
  - Las medidas documentales para ENP/Red Natura/Flora/Fauna/Patrimonio no
    cierran la compatibilidad del impacto: el órgano ambiental decide.
  - No escribe archivos desde el módulo (responsabilidad del llamador / CLI).

Dependencias: IM-00 (impact_model), IM-03 (impact_identifier), IM-04
(conesa_attribute_assigner).
"""
from __future__ import annotations

import dataclasses
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MEASURE_STATUS,
    MEASURE_TYPES,
    MitigationMeasure,
    Phase6Model,
)


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    """Normaliza texto a ASCII para consola Windows cp1252."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# MeasureGenerationRule
# ---------------------------------------------------------------------------

@dataclass
class MeasureGenerationRule:
    """Regla tipológica de generación de medidas ambientales por tipo de impacto.

    Cada regla define qué medida generar cuando un impacto coincide con los
    criterios receptor + naturaleza + palabras clave + significancia.

    Primera regla NO gana — todas las reglas aplicables se aplican al mismo
    impacto, generando una medida por cada regla coincidente. La deduplicación
    se realiza por (measure_name, measure_type) para evitar duplicados sobre
    el mismo impacto.
    """

    rule_id: str
    """Identificador único de la regla (ej. 'MGEN-A')."""

    target_receptor_ids: list[str]
    """IDs de receptores objetivo (ej. ['FR-014'])."""

    impact_keywords: list[str]
    """Palabras clave en nombre/descripción del impacto. Vacío = cualquiera."""

    significance_levels: list[str]
    """Significancias que activan la regla. Vacío = cualquiera."""

    measure_name: str
    """Nombre canónico de la medida a generar."""

    measure_description: str
    """Descripción técnica de la medida."""

    measure_type: str
    """Tipo de medida (de MEASURE_TYPES en IM-00)."""

    status: str = "PROPUESTA"
    """Estado de la medida (de MEASURE_STATUS en IM-00)."""

    is_diagnostic: bool = False
    """True si la medida es diagnóstica (no reduce significancia por sí misma)."""

    is_prl_only: bool = False
    """True si es exclusivamente PRL (no reduce significancia ambiental)."""

    condition_before_submission: bool = False
    """True si debe acreditarse antes de la presentación del Documento Ambiental."""

    target_natures: list[str] = field(default_factory=list)
    """Naturalezas de impacto que activan la regla. Vacío = cualquiera."""

    notes: list[str] = field(default_factory=list)
    """Notas metodológicas de la regla."""

    def matches(self, impact: EnvironmentalImpact) -> bool:
        """True si esta regla aplica al impacto dado.

        Comprobaciones en orden:
          1. No aplica a impactos DESCARTADO_JUSTIFICADO.
          2. Receptor objetivo (obligatorio).
          3. Naturaleza del impacto (si la regla filtra por naturaleza).
          4. Palabras clave en nombre/descripción (si la regla filtra).
          5. Significancia sin medidas (si la regla filtra).

        No modifica el impacto.
        """
        # 1. Nunca para impactos descartados
        if impact.status == "DESCARTADO_JUSTIFICADO":
            return False

        # 2. Receptor (obligatorio)
        if impact.receptor_id not in self.target_receptor_ids:
            return False

        # 3. Naturaleza (si la regla filtra)
        if self.target_natures and impact.nature not in self.target_natures:
            return False

        # 4. Palabras clave (si la regla filtra)
        if self.impact_keywords:
            text = f"{impact.name} {impact.description}".lower()
            if not any(kw.lower() in text for kw in self.impact_keywords):
                return False

        # 5. Significancia (si la regla filtra)
        if self.significance_levels:
            if impact.significance_without_measures not in self.significance_levels:
                return False

        return True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "target_receptor_ids": list(self.target_receptor_ids),
            "impact_keywords": list(self.impact_keywords),
            "significance_levels": list(self.significance_levels),
            "measure_name": self.measure_name,
            "measure_description": self.measure_description,
            "measure_type": self.measure_type,
            "status": self.status,
            "is_diagnostic": self.is_diagnostic,
            "is_prl_only": self.is_prl_only,
            "condition_before_submission": self.condition_before_submission,
            "target_natures": list(self.target_natures),
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# MeasureGenerationResult
# ---------------------------------------------------------------------------

@dataclass
class MeasureGenerationResult:
    """Resultado de la generación de medidas sobre un Phase6Model."""

    model: Phase6Model
    """Modelo actualizado con medidas generadas e impactos con measure_ids actualizados."""

    generated_count: int = 0
    """Total de medidas generadas (incluyendo PRL_NO_EIA y diagnósticas)."""

    diagnostic_count: int = 0
    """Medidas con is_diagnostic=True (no reductoras de significancia)."""

    prl_only_count: int = 0
    """Medidas con is_prl_only=True (no son medidas EIA ambientales)."""

    condition_before_submission_count: int = 0
    """Medidas que deben acreditarse antes de presentar el Documento Ambiental."""

    warnings: list[str] = field(default_factory=list)
    """Avisos generados durante la generación."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

    def to_dict(self) -> dict:
        return {
            "generated_count": self.generated_count,
            "diagnostic_count": self.diagnostic_count,
            "prl_only_count": self.prl_only_count,
            "condition_before_submission_count": self.condition_before_submission_count,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "model": self.model.to_dict(),
        }

    def summary(self) -> str:
        """Resumen ASCII-safe (compatible con consola Windows cp1252)."""
        total_impacts = len(self.model.impacts)
        lines = [
            "--- IM-05 Generador de medidas ambientales ---",
            f"Impactos en el modelo   : {total_impacts}",
            f"Medidas generadas       : {self.generated_count}",
            f"  Diagnosticas          : {self.diagnostic_count}",
            f"  PRL_NO_EIA            : {self.prl_only_count}",
            f"  Condicion previa      : {self.condition_before_submission_count}",
        ]
        if self.warnings:
            lines.append(f"Avisos ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"  AVISO: {_ascii_safe(w)}")
        if self.notes:
            for n in self.notes[:5]:
                lines.append(f"  Nota : {_ascii_safe(n)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reglas por defecto — MGEN-A a MGEN-P
# ---------------------------------------------------------------------------

def default_measure_generation_rules() -> list[MeasureGenerationRule]:
    """16 reglas tipológicas de generación de medidas para proyectos R12/R13 en Canarias.

    Receptores cubiertos con reglas ambientales EIA:
      FR-003 (Suelos), FR-004 (Hidrología), FR-006 (Calidad del aire),
      FR-007 (Flora), FR-008 (Fauna), FR-009 (ENP), FR-010 (Red Natura 2000),
      FR-011 (Paisaje), FR-012 (Patrimonio cultural), FR-013 (Socioeconomía),
      FR-014 (Ruido), FR-015 (Cambio climático).
    Receptores DOCUMENTAL/DIAGNOSTICA para completar cobertura:
      FR-005 (Inundabilidad), FR-016 (Riesgos naturales).

    Regla de no compensación:
      Los impactos POSITIVOS (FR-013 Socioeconomía) se documentan de forma
      independiente. No compensan ni reducen los impactos negativos.

    Regla PRL_NO_EIA:
      Las medidas de protección individual (EPI auditivos) son obligaciones PRL,
      no reducen la emisión exterior ni la significancia ambiental.

    Regla de prudencia documental:
      Las medidas documentales/diagnósticas para ENP, Red Natura, Flora, Fauna y
      Patrimonio no cierran la compatibilidad del impacto. El órgano ambiental
      determina si procede la evaluación de repercusiones.
    """
    return [
        # ── MGEN-A: Ruido — Estudio acústico (DIAGNOSTICA, CONDICION_PREVIA) ──
        MeasureGenerationRule(
            rule_id="MGEN-A",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Estudio acustico previo a la presentacion",
            measure_description=(
                "Estudio acústico con modelización o medición de niveles de ruido "
                "conforme a la normativa aplicable (Ley 37/2003, Decreto 19/1997 de "
                "Canarias o equivalente autonómico). Permite dimensionar las medidas "
                "materiales necesarias para reducir la emisión a los niveles exigidos."
            ),
            measure_type="DIAGNOSTICA",
            status="CONDICION_PREVIA",
            is_diagnostic=True,
            is_prl_only=False,
            condition_before_submission=True,
            notes=[
                "No reduce por si misma la significancia ambiental.",
                "Diagnostica y permite dimensionar medidas materiales sobre focos emisores.",
                "Regla MGEN-A: ruido acustico.",
            ],
        ),
        # ── MGEN-B: Ruido — Insonorización / cerramientos (CORRECTORA) ──
        MeasureGenerationRule(
            rule_id="MGEN-B",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Encapsulado, cerramiento o aislamiento acustico de focos emisores",
            measure_description=(
                "Medida material sobre los focos emisores de ruido: encapsulado de "
                "maquinaria, cerramientos acústicos, aislamiento de paramentos o medidas "
                "constructivas equivalentes. La eficacia debe verificarse mediante el "
                "estudio acústico previo (MGEN-A)."
            ),
            measure_type="CORRECTORA",
            status="PROPUESTA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=False,
            notes=["Regla MGEN-B: medida material sobre focos de ruido."],
        ),
        # ── MGEN-C: Ruido — Limitación horaria (PREVENTIVA) ──
        MeasureGenerationRule(
            rule_id="MGEN-C",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Limitacion horaria y organizacion de operaciones ruidosas",
            measure_description=(
                "Restricción de las operaciones de mayor emisión sonora al horario "
                "diurno conforme a normativa. Organización de las operaciones de "
                "carga/descarga y uso de maquinaria pesada para minimizar la presión "
                "acústica en horario nocturno y festivo."
            ),
            measure_type="PREVENTIVA",
            status="PROPUESTA",
            notes=["Regla MGEN-C: limitacion horaria operaciones ruidosas."],
        ),
        # ── MGEN-D: Ruido — EPI auditivos (PRL_NO_EIA) ──
        MeasureGenerationRule(
            rule_id="MGEN-D",
            target_receptor_ids=["FR-014"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Proteccion auditiva individual (EPI) — obligacion PRL exclusiva",
            measure_description=(
                "Uso de protectores auditivos individuales por los trabajadores "
                "expuestos a niveles de ruido superiores a los valores de exposición "
                "(RD 286/2006 sobre la protección de la salud y la seguridad de los "
                "trabajadores contra los riesgos relacionados con la exposición al ruido). "
                "No reduce la emisión de ruido al exterior ni la significancia ambiental."
            ),
            measure_type="PRL_NO_EIA",
            status="NO_EIA",
            is_diagnostic=False,
            is_prl_only=True,
            condition_before_submission=False,
            notes=[
                "Obligacion de prevencion de riesgos laborales (PRL). No es una medida EIA.",
                "No reduce la emision exterior ni la significancia ambiental del impacto.",
                "Regla MGEN-D: EPI auditivos PRL_NO_EIA.",
            ],
        ),
        # ── MGEN-E: Calidad del aire — Aspiración/filtración (CORRECTORA, CONDICION_PREVIA) ──
        MeasureGenerationRule(
            rule_id="MGEN-E",
            target_receptor_ids=["FR-006"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Acreditacion y mantenimiento de sistema de aspiracion/filtracion de polvo",
            measure_description=(
                "El promotor debe acreditar que el sistema de aspiración, filtración y "
                "control de polvo está instalado, operativo y mantenido conforme a la "
                "normativa sectorial aplicable. Condición que debe acreditarse antes de "
                "la presentación del Documento Ambiental."
            ),
            measure_type="CORRECTORA",
            status="CONDICION_PREVIA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=True,
            notes=["Regla MGEN-E: control de polvo y calidad del aire."],
        ),
        # ── MGEN-F: Calidad del aire — Limpieza y buenas prácticas (PREVENTIVA) ──
        MeasureGenerationRule(
            rule_id="MGEN-F",
            target_receptor_ids=["FR-006"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Limpieza periodica y buenas practicas en manejo de materiales pulverulentos",
            measure_description=(
                "Limpieza periódica de la zona de trabajo, zonas de carga/descarga y "
                "accesos para evitar la dispersión de polvo. Humectación de zonas "
                "generadoras cuando las condiciones meteorológicas lo requieran. "
                "Cubrimiento de acopios de materiales pulverulentos."
            ),
            measure_type="PREVENTIVA",
            status="PROPUESTA",
            notes=["Regla MGEN-F: limpieza y prevencion de dispersion de polvo."],
        ),
        # ── MGEN-G: Suelo — Impermeabilización y cubetos (PROTECTORA) ──
        MeasureGenerationRule(
            rule_id="MGEN-G",
            target_receptor_ids=["FR-003"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Solera impermeable, almacenamiento en zonas protegidas y cubetos de retencion",
            measure_description=(
                "El área de trabajo dispone de solera impermeable. Los productos "
                "potencialmente contaminantes (aceites, combustibles, residuos peligrosos) "
                "se almacenan en zonas protegidas con cubetos o recipientes de retención "
                "adecuados que eviten derrames al suelo o al subsuelo."
            ),
            measure_type="PROTECTORA",
            status="PROPUESTA",
            notes=["Regla MGEN-G: proteccion del suelo ante contaminacion."],
        ),
        # ── MGEN-H: Suelo — Protocolo de derrames (PREVENTIVA) ──
        MeasureGenerationRule(
            rule_id="MGEN-H",
            target_receptor_ids=["FR-003"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Kit absorbente y protocolo de derrames accidentales",
            measure_description=(
                "Disponibilidad de material absorbente adecuado para el tipo de sustancias "
                "manejadas. Protocolo de actuación ante derrames accidentales que incluye "
                "contención inmediata, absorción, retirada del material como residuo "
                "peligroso y registro de incidencias."
            ),
            measure_type="PREVENTIVA",
            status="PROPUESTA",
            notes=["Regla MGEN-H: protocolo de derrames accidentales en suelo."],
        ),
        # ── MGEN-I: Hidrología — Drenaje/escorrentía (PROTECTORA, CONDICION_PREVIA) ──
        MeasureGenerationRule(
            rule_id="MGEN-I",
            target_receptor_ids=["FR-004"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Verificacion de red de drenaje y prevencion de arrastres al medio hidrico",
            measure_description=(
                "Verificar que la red de drenaje existente está en buen estado y "
                "evita el arrastre de contaminantes hacia el medio hídrico. Si la "
                "actividad genera escorrentías con posibilidad de arrastres, instalar "
                "arqueta de decantación o sistema equivalente de tratamiento previo al "
                "vertido. Condición a verificar antes de la presentación."
            ),
            measure_type="PROTECTORA",
            status="CONDICION_PREVIA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=True,
            notes=["Regla MGEN-I: proteccion del sistema hidrologico ante arrastres."],
        ),
        # ── MGEN-J: Inundabilidad/Riesgos naturales — Verificación oficial (DOCUMENTAL) ──
        MeasureGenerationRule(
            rule_id="MGEN-J",
            target_receptor_ids=["FR-005", "FR-016"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Verificacion oficial de inundabilidad y riesgos naturales",
            measure_description=(
                "Verificación mediante fuentes oficiales de la exposición de la parcela "
                "a inundabilidad (SNCZI/MITECO) y a riesgos naturales (cartografía de "
                "riesgos del GRAFCAN para Canarias). Resultado a documentar en el "
                "Documento Ambiental antes de su presentación."
            ),
            measure_type="DOCUMENTAL",
            status="CONDICION_PREVIA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=True,
            notes=["Regla MGEN-J: verificacion oficial de riesgos naturales e inundabilidad."],
        ),
        # ── MGEN-K: Red Natura / ENP — Verificación cartográfica (DOCUMENTAL) ──
        MeasureGenerationRule(
            rule_id="MGEN-K",
            target_receptor_ids=["FR-009", "FR-010"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Verificacion cartografica oficial de ENP y Red Natura 2000",
            measure_description=(
                "Verificación oficial mediante cartografía del MITECO y del Gobierno de "
                "Canarias de la posible afección a Espacios Naturales Protegidos y Red "
                "Natura 2000. Documentar distancia al espacio protegido más próximo y "
                "posibles vectores de afección indirecta."
            ),
            measure_type="DOCUMENTAL",
            status="CONDICION_PREVIA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=True,
            notes=[
                "La evaluacion de repercusiones sobre Red Natura 2000 corresponde al "
                "organo ambiental cuando proceda.",
                "Esta medida no cierra la compatibilidad del impacto.",
                "Regla MGEN-K: verificacion cartografica ENP y Red Natura 2000.",
            ],
        ),
        # ── MGEN-L: Flora / Fauna — Consulta/prospección (DIAGNOSTICA) ──
        MeasureGenerationRule(
            rule_id="MGEN-L",
            target_receptor_ids=["FR-007", "FR-008"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Consulta de fuentes oficiales y prospeccion de flora y fauna si procede",
            measure_description=(
                "Consulta del Banco de Datos de Biodiversidad de Canarias (GRAFCAN/SIAM) "
                "y otros inventarios oficiales disponibles. Prospección de campo específica "
                "si la cartografía o el contexto del expediente indican posible presencia "
                "de especies protegidas o hábitats de interés."
            ),
            measure_type="DIAGNOSTICA",
            status="CONDICION_PREVIA",
            is_diagnostic=True,
            is_prl_only=False,
            condition_before_submission=True,
            notes=[
                "No afirmar ausencia de especies sin verificacion en fuentes oficiales.",
                "No cierra la compatibilidad del impacto sobre flora o fauna.",
                "Regla MGEN-L: consulta y prospeccion de biodiversidad.",
            ],
        ),
        # ── MGEN-M: Patrimonio cultural — Consulta al órgano competente (DOCUMENTAL) ──
        MeasureGenerationRule(
            rule_id="MGEN-M",
            target_receptor_ids=["FR-012"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Consulta al inventario patrimonial y al organo competente en patrimonio cultural",
            measure_description=(
                "Consulta al inventario de Bienes de Interés Cultural (BIC) y al "
                "Servicio de Patrimonio Histórico del Cabildo o Consejería competente. "
                "El resultado de la consulta debe documentarse en el Documento Ambiental "
                "antes de su presentación al órgano ambiental."
            ),
            measure_type="DOCUMENTAL",
            status="CONDICION_PREVIA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=True,
            notes=[
                "No descarta afeccion patrimonial sin respuesta del organo competente.",
                "Regla MGEN-M: consulta patrimonial obligatoria.",
            ],
        ),
        # ── MGEN-N: Paisaje — Orden e integración visual (PREVENTIVA) ──
        MeasureGenerationRule(
            rule_id="MGEN-N",
            target_receptor_ids=["FR-011"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Orden, limpieza exterior e integracion visual de la actividad",
            measure_description=(
                "Mantener el orden y la limpieza exterior de la instalación. Minimizar "
                "el almacenamiento visible desde viales o zonas de uso público. "
                "Integración visual mediante vegetación, pantallas o tratamientos de "
                "fachada cuando sea técnicamente viable."
            ),
            measure_type="PREVENTIVA",
            status="PROPUESTA",
            notes=["Regla MGEN-N: integracion visual y reduccion del impacto paisajistico."],
        ),
        # ── MGEN-O: Cambio climático — Consumos y eficiencia (DOCUMENTAL) ──
        MeasureGenerationRule(
            rule_id="MGEN-O",
            target_receptor_ids=["FR-015"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Recopilacion de consumos y medidas de eficiencia energetica",
            measure_description=(
                "Recopilación de datos de consumo energético y de combustibles de la "
                "actividad. Mantenimiento periódico de la maquinaria para garantizar "
                "la eficiencia. Adoptar medidas de eficiencia energética y reducción "
                "de emisiones de GEI cuando sea técnicamente viable."
            ),
            measure_type="DOCUMENTAL",
            status="PROPUESTA",
            notes=[
                "Regla MGEN-O: documentacion de consumos y eficiencia para cambio climatico.",
                "La cuantificacion de emisiones de GEI requiere datos del promotor.",
            ],
        ),
        # ── MGEN-P: Socioeconomía POSITIVO — Nota de no compensación (DOCUMENTAL) ──
        MeasureGenerationRule(
            rule_id="MGEN-P",
            target_receptor_ids=["FR-013"],
            target_natures=["POSITIVO"],
            impact_keywords=[],
            significance_levels=[],
            measure_name="Documentacion del impacto positivo socioeconomico — nota de no compensacion",
            measure_description=(
                "El impacto positivo en socioeconomía (empleo, actividad económica local) "
                "se documenta de forma independiente. No compensa ni reduce los impactos "
                "negativos identificados sobre otros factores ambientales. Cada impacto "
                "se registra y evalúa de forma independiente conforme al principio de "
                "no compensación (AG09-14)."
            ),
            measure_type="DOCUMENTAL",
            status="PROPUESTA",
            is_diagnostic=False,
            is_prl_only=False,
            condition_before_submission=False,
            notes=[
                "Regla de no compensacion: el impacto positivo no compensa impactos negativos.",
                "Medida de registro documental: no reduce la significancia de ningun "
                "impacto negativo.",
                "Regla MGEN-P: socioeconomia positiva sin compensacion.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Función interna de generación por impacto
# ---------------------------------------------------------------------------

def _generate_measures_for_impact_internal(
    impact: EnvironmentalImpact,
    rules: list[MeasureGenerationRule],
    start_index: int,
) -> list[MitigationMeasure]:
    """Genera medidas para un único impacto aplicando todas las reglas coincidentes.

    Deduplicación por (measure_name, measure_type) para el mismo impacto.
    No muta el impacto original.
    """
    measures: list[MitigationMeasure] = []
    seen: set[tuple[str, str]] = set()
    idx = start_index

    for rule in rules:
        if not rule.matches(impact):
            continue
        key = (rule.measure_name, rule.measure_type)
        if key in seen:
            continue
        seen.add(key)

        measure = MitigationMeasure(
            measure_id=f"MED-{idx:03d}",
            name=rule.measure_name,
            description=rule.measure_description,
            measure_type=rule.measure_type,
            status=rule.status,
            target_impact_ids=[impact.impact_id],
            is_diagnostic=rule.is_diagnostic,
            is_prl_only=rule.is_prl_only,
            condition_before_submission=rule.condition_before_submission,
            notes=list(rule.notes) + [
                f"Generada por {rule.rule_id} para {impact.impact_id}."
            ],
        )
        measures.append(measure)
        idx += 1

    return measures


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def generate_measures_for_impact(
    impact: EnvironmentalImpact,
    rules: Optional[list[MeasureGenerationRule]] = None,
    start_index: int = 1,
) -> list[MitigationMeasure]:
    """Genera medidas ambientales para un impacto individual.

    Aplica todas las reglas coincidentes (no solo la primera). Deduplica por
    (measure_name, measure_type). No muta el impacto original.

    Args:
        impact: Impacto a evaluar.
        rules: Reglas de generación. Si None, usa las 16 reglas por defecto.
        start_index: Índice numérico del primer ID MED-XXX a generar.

    Returns:
        Lista de MitigationMeasure con target_impact_ids=[impact.impact_id].
        Lista vacía si ninguna regla coincide o el impacto es DESCARTADO_JUSTIFICADO.
    """
    if rules is None:
        rules = default_measure_generation_rules()
    return _generate_measures_for_impact_internal(impact, rules, start_index)


def generate_measures_for_model(
    model: Phase6Model,
    rules: Optional[list[MeasureGenerationRule]] = None,
) -> MeasureGenerationResult:
    """Genera medidas para todos los impactos de un Phase6Model.

    Función pura sin efectos secundarios. No muta el modelo original.
    Reemplaza (no acumula) la lista model.measures con las medidas generadas.
    Actualiza measure_ids en cada impacto con las medidas vinculadas.

    No modifica:
      - significance_without_measures ni significance_with_measures.
      - pva_programs.
      - actions ni receptor_factors.

    No genera PVA. No reduce significancia.

    Args:
        model: Paquete de Fase 6 con impactos identificados (output de IM-04).
        rules: Reglas de generación. Si None, usa las 16 reglas por defecto.

    Returns:
        MeasureGenerationResult con el modelo actualizado y estadísticas.
    """
    if rules is None:
        rules = default_measure_generation_rules()

    all_measures: list[MitigationMeasure] = []
    global_index = 1
    impact_measure_map: dict[str, list[str]] = {}

    for impact in model.impacts:
        measures = _generate_measures_for_impact_internal(
            impact, rules, start_index=global_index
        )
        for m in measures:
            all_measures.append(m)
            impact_measure_map.setdefault(impact.impact_id, []).append(m.measure_id)
        global_index += len(measures)

    # Actualizar measure_ids en cada impacto (deduplicando)
    new_impacts: list[EnvironmentalImpact] = []
    for impact in model.impacts:
        new_ids = impact_measure_map.get(impact.impact_id, [])
        if new_ids or impact.measure_ids:
            # Combinar existentes con nuevos, sin duplicados, preservando orden
            combined = list(impact.measure_ids)
            seen_ids: set[str] = set(combined)
            for mid in new_ids:
                if mid not in seen_ids:
                    combined.append(mid)
                    seen_ids.add(mid)
            new_impact = dataclasses.replace(impact, measure_ids=combined)
        else:
            new_impact = impact
        new_impacts.append(new_impact)

    updated_model = dataclasses.replace(
        model,
        impacts=new_impacts,
        measures=all_measures,
    )

    generated_count = len(all_measures)
    diagnostic_count = sum(1 for m in all_measures if m.is_diagnostic)
    prl_only_count = sum(1 for m in all_measures if m.is_prl_only)
    cbs_count = sum(1 for m in all_measures if m.condition_before_submission)

    warnings: list[str] = []
    notes: list[str] = []

    if not model.impacts:
        warnings.append(
            "El modelo no contiene impactos. "
            "Ejecute primero IM-03 (phase6-identify-impacts --write)."
        )

    if cbs_count > 0:
        notes.append(
            f"{cbs_count} medida(s) marcadas CONDICION_PREVIA: deben acreditarse "
            "antes de la presentacion del Documento Ambiental."
        )

    if prl_only_count > 0:
        notes.append(
            f"{prl_only_count} medida(s) PRL_NO_EIA: obligaciones de prevencion de "
            "riesgos laborales. No cuentan como medidas EIA reductoras de significancia."
        )

    if diagnostic_count > 0:
        notes.append(
            f"{diagnostic_count} medida(s) DIAGNOSTICA: no reducen la significancia "
            "por si mismas. Permiten dimensionar medidas materiales posteriores."
        )

    return MeasureGenerationResult(
        model=updated_model,
        generated_count=generated_count,
        diagnostic_count=diagnostic_count,
        prl_only_count=prl_only_count,
        condition_before_submission_count=cbs_count,
        warnings=warnings,
        notes=notes,
    )


def merge_measures_into_model(
    model: Phase6Model,
    measures: list[MitigationMeasure],
) -> Phase6Model:
    """Sustituye las medidas del modelo y actualiza measure_ids de los impactos.

    Función pura. No muta el modelo original. Usa dataclasses.replace().
    Conserva: actions, receptor_factors, impacts (significancias), pva_programs.

    Los measure_ids de cada impacto se reconstruyen desde cero a partir de
    target_impact_ids de las medidas proporcionadas.

    Args:
        model: Phase6Model original.
        measures: Lista de medidas a sustituir en el modelo.

    Returns:
        Nueva instancia de Phase6Model con las medidas sustituidas y
        measure_ids de impactos actualizados.
    """
    # Construir mapping impact_id → measure_ids desde las medidas nuevas
    impact_measure_map: dict[str, list[str]] = {}
    for m in measures:
        for tid in m.target_impact_ids:
            impact_measure_map.setdefault(tid, []).append(m.measure_id)

    # Actualizar impactos con los nuevos measure_ids (reemplaza los existentes)
    new_impacts: list[EnvironmentalImpact] = []
    for impact in model.impacts:
        new_ids = impact_measure_map.get(impact.impact_id, [])
        if new_ids != list(impact.measure_ids):
            new_impact = dataclasses.replace(impact, measure_ids=list(new_ids))
        else:
            new_impact = impact
        new_impacts.append(new_impact)

    return dataclasses.replace(
        model,
        impacts=new_impacts,
        measures=list(measures),
    )
