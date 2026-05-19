"""
pva_generator -- IM-06
Generador determinístico de fichas de Programa de Vigilancia Ambiental (PVA)
para Fase 6 EIA.

Genera propuestas de PVA vinculadas a los impactos identificados/valorados
(IM-03, IM-04) y a las medidas generadas (IM-05).

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica valoraciones Conesa.
  - No genera medidas.
  - No escribe archivos desde el módulo (responsabilidad del llamador / CLI).
  - Un PVA por receptor (no uno por impacto) para evitar duplicidad.
  - Los impactos POSITIVOS reciben PVA de eficacia (sin umbral de alarma).
  - Los impactos INDETERMINADO con data_gaps generan fichas CONDICIONADO (E-9).
  - Los impactos POSITIVOS con data_gaps no vacíos reciben nota de incertidumbre (E-10).
  - Siempre se genera una ficha de revisión anual global.
  - Los impactos negativos con significancia >= COMPATIBLE sin PVA quedan en
    uncovered_impact_ids (GAP-PVA obligatorio en el Bloque E).

Dependencias: IM-00 (impact_model), IM-03 (impact_identifier),
              IM-04 (conesa_attribute_assigner), IM-05 (mitigation_measure_generator).
"""
from __future__ import annotations

import dataclasses
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.impact_model import (
    EnvironmentalImpact,
    MitigationMeasure,
    Phase6Model,
    PVAProgram,
    RECEPTOR_FACTOR_IDS,
)

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    """Normaliza texto a ASCII para consola Windows cp1252."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# Significancias que requieren cobertura PVA obligatoria
_PVA_REQUIRED_SIGNIFICANCES: frozenset[str] = frozenset({
    "COMPATIBLE", "MODERADO", "SEVERO", "CRITICO",
})

# Natures que implican cobertura PVA obligatoria
_PVA_REQUIRED_NATURES: frozenset[str] = frozenset({"NEGATIVO", "MIXTO"})


# ---------------------------------------------------------------------------
# PVAGenerationRule
# ---------------------------------------------------------------------------

@dataclass
class PVAGenerationRule:
    """Regla tipológica de generación de ficha PVA por tipo de receptor/factor.

    Una regla cubre TODOS los impactos no descartados del receptor indicado
    en un único PVA (cobertura agregada por factor). Si hay impactos POSITIVOS
    y NEGATIVOS sobre el mismo receptor, la regla genera una ficha por cada
    naturaleza dominante detectada.

    target_natures vacío = aplica a cualquier naturaleza.
    significance_levels vacío = aplica a cualquier significancia.
    """

    rule_id: str
    """Identificador único de la regla (ej. 'PVAGEN-A')."""

    target_receptor_ids: list[str]
    """IDs de receptores objetivo (ej. ['FR-014'])."""

    pva_name: str
    """Nombre canónico de la ficha PVA."""

    factor_id: str
    """Factor del inventario que vigila esta ficha (FI-001...FI-016)."""

    indicator: str
    """Descripción concreta del indicador: qué se observa, dónde y cómo."""

    threshold: str
    """Umbral de alarma. Vacío si impacto positivo sin umbral."""

    frequency: str
    """Frecuencia de seguimiento (de PVA_FREQUENCIES en IM-00)."""

    records: list[str]
    """Documentos o registros que soportan el seguimiento."""

    target_natures: list[str] = field(default_factory=list)
    """Naturalezas de impacto que activan la regla. Vacío = cualquiera."""

    significance_levels: list[str] = field(default_factory=list)
    """Significancias que activan la regla. Vacío = cualquiera."""

    notes: list[str] = field(default_factory=list)
    """Notas metodológicas de la regla."""

    responsible_note: str = "Responsable Ambiental designado por el promotor"
    """Texto de responsable. Siempre AVISO si no hay designado real."""

    def matches(self, impact: EnvironmentalImpact) -> bool:
        """True si esta regla aplica al impacto dado.

        No aplica a impactos DESCARTADO_JUSTIFICADO.
        """
        if impact.status == "DESCARTADO_JUSTIFICADO":
            return False
        if impact.receptor_id not in self.target_receptor_ids:
            return False
        if self.target_natures and impact.nature not in self.target_natures:
            return False
        if self.significance_levels:
            if impact.significance_without_measures not in self.significance_levels:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "target_receptor_ids": list(self.target_receptor_ids),
            "pva_name": self.pva_name,
            "factor_id": self.factor_id,
            "indicator": self.indicator,
            "threshold": self.threshold,
            "frequency": self.frequency,
            "records": list(self.records),
            "target_natures": list(self.target_natures),
            "significance_levels": list(self.significance_levels),
            "notes": list(self.notes),
            "responsible_note": self.responsible_note,
        }


# ---------------------------------------------------------------------------
# PVAGenerationResult
# ---------------------------------------------------------------------------

@dataclass
class PVAGenerationResult:
    """Resultado de la generación de fichas PVA sobre un Phase6Model."""

    model: Phase6Model
    """Modelo actualizado con pva_programs generados e impactos con pva_ids."""

    generated_count: int = 0
    """Total de fichas PVA generadas (incluida revisión anual global)."""

    conditioned_count: int = 0
    """Fichas PVA en estado CONDICIONADO (por CONTs abiertos, E-9)."""

    uncovered_impact_ids: list[str] = field(default_factory=list)
    """IDs de impactos negativos/mixtos con significancia alta sin cobertura PVA.

    Cada ID aquí es un GAP-PVA obligatorio en el Bloque E del documento.
    """

    coverage_notes: list[str] = field(default_factory=list)
    """Notas de cobertura implícita (impactos cubiertos por PVA de otro factor)."""

    warnings: list[str] = field(default_factory=list)
    """Avisos generados durante la generación."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

    def to_dict(self) -> dict:
        return {
            "generated_count": self.generated_count,
            "conditioned_count": self.conditioned_count,
            "uncovered_impact_ids": list(self.uncovered_impact_ids),
            "coverage_notes": list(self.coverage_notes),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "model": self.model.to_dict(),
        }

    def summary(self) -> str:
        """Resumen ASCII-safe (compatible con consola Windows cp1252)."""
        total_impacts = len(self.model.impacts)
        lines = [
            "--- IM-06 Generador de fichas PVA ---",
            f"Impactos en el modelo   : {total_impacts}",
            f"Fichas PVA generadas    : {self.generated_count}",
            f"  Condicionadas (E-9)   : {self.conditioned_count}",
            f"Impactos sin cobertura  : {len(self.uncovered_impact_ids)}",
        ]
        if self.uncovered_impact_ids:
            lines.append(
                "  GAP-PVA obligatorios  : "
                + ", ".join(self.uncovered_impact_ids[:5])
                + ("..." if len(self.uncovered_impact_ids) > 5 else "")
            )
        if self.warnings:
            lines.append(f"Avisos ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"  AVISO: {_ascii_safe(w)}")
        if self.notes:
            for n in self.notes[:5]:
                lines.append(f"  Nota : {_ascii_safe(n)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reglas por defecto — PVAGEN-A a PVAGEN-P + PVAGEN-ANNUAL
# ---------------------------------------------------------------------------

def default_pva_generation_rules() -> list[PVAGenerationRule]:
    """Reglas tipológicas de generación de fichas PVA para proyectos R12/R13 en Canarias.

    Receptores cubiertos:
      FR-003 (Suelos), FR-004 (Hidrología), FR-006 (Calidad del aire),
      FR-007 (Flora), FR-008 (Fauna), FR-009 (ENP), FR-010 (Red Natura 2000),
      FR-011 (Paisaje), FR-012 (Patrimonio cultural), FR-013 (Socioeconomía,
      solo POSITIVO), FR-014 (Ruido), FR-015 (Cambio climático),
      FR-005 (Inundabilidad), FR-016 (Riesgos naturales).

    Principios metodológicos:
      - Un PVA por receptor (no uno por impacto individual).
      - Indicadores concretos: qué se observa, dónde, cómo se registra.
      - Frecuencias proporcionales al tipo de impacto (continuo → MENSUAL;
        episódico → CONDICIONAL; positivo → ANUAL).
      - La revisión anual global (PVAGEN-ANNUAL) se añade siempre aparte.
    """
    return [
        # ── PVAGEN-A: Calidad del aire (FR-006) — partículas/polvo ──
        PVAGenerationRule(
            rule_id="PVAGEN-A",
            target_receptor_ids=["FR-006"],
            pva_name="Seguimiento de deposicion de particulas y polvo en el entorno",
            factor_id="FI-006",
            indicator=(
                "Inspeccion visual quincenal de panos de tela (20x20 cm) colocados "
                "en puntos fijos perimetrales barlovento y sotavento. Indice de "
                "deposicion: 0 (limpio) - 3 (deposicion intensa visible). "
                "Registro fotografico en cada inspeccion."
            ),
            threshold=(
                "Indice >= 2 en dos inspecciones consecutivas en el punto sotavento. "
                "Activar revision inmediata de la medida de aspiracion/filtracion (MED)."
            ),
            frequency="MENSUAL",
            records=[
                "Libro de registro de PVA: ficha de inspeccion con fecha, punto, "
                "indice, fotografias y firma del Responsable Ambiental.",
                "Registro de incidencias con descripcion de la accion correctiva adoptada.",
            ],
            notes=[
                "Regla PVAGEN-A: seguimiento continuo de calidad del aire por polvo.",
                "Incluir seguimientos adicionales tras episodio de viento fuerte (>55 km/h).",
                "Reutilizar partes de incidencias del libro de operaciones si existen.",
            ],
        ),
        # ── PVAGEN-B: Suelos (FR-003) — contaminacion por derrames ──
        PVAGenerationRule(
            rule_id="PVAGEN-B",
            target_receptor_ids=["FR-003"],
            pva_name="Seguimiento del estado del suelo y prevencion de contaminacion",
            factor_id="FI-003",
            indicator=(
                "Inspeccion visual mensual de la solera, zonas de almacenamiento, "
                "cubetos de retencion y areas de operaciones para detectar presencia "
                "de manchas de aceite, fluidos, lixiviados u otras sustancias "
                "potencialmente contaminantes. Registro de presencia/ausencia con "
                "localizacion."
            ),
            threshold=(
                "Cualquier presencia de mancha de fluido o sustancia contaminante "
                "fuera de los cubetos de retencion o de la zona impermeabilizada. "
                "Aplicar protocolo de derrames de forma inmediata."
            ),
            frequency="MENSUAL",
            records=[
                "Ficha de inspeccion mensual con fecha, area inspeccionada, "
                "resultado (OK/INCIDENCIA) y fotografias si procede.",
                "Registro de derrames accidentales con causa, extension, "
                "accion adoptada y residuo generado.",
            ],
            notes=[
                "Regla PVAGEN-B: seguimiento mensual de integridad del suelo.",
                "Inspecciones adicionales tras cualquier derrame accidental documentado.",
            ],
        ),
        # ── PVAGEN-C: Hidrología (FR-004) — estado del drenaje ──
        PVAGenerationRule(
            rule_id="PVAGEN-C",
            target_receptor_ids=["FR-004"],
            pva_name="Seguimiento del sistema de drenaje y prevencion de arrastres",
            factor_id="FI-004",
            indicator=(
                "Inspeccion mensual del sistema de drenaje perimetral, arqueta de "
                "decantacion (si existe) y nivel de solidos en suspension. "
                "Comprobacion del estado de la red tras episodios de lluvia >10 mm "
                "en 24 horas. Registro del nivel de solidos en la arqueta: "
                "porcentaje de capacidad ocupada y coloracion del agua."
            ),
            threshold=(
                "Nivel de solidos en la arqueta >50% de su capacidad volumetrica, "
                "o coloracion metalica o aceitosa del agua en la arqueta. "
                "Limpieza inmediata y revision del foco de arrastre."
            ),
            frequency="MENSUAL",
            records=[
                "Ficha mensual de inspeccion de drenaje con nivel de solidos y estado.",
                "Registro de limpiezas de arqueta con fecha y destino del residuo.",
            ],
            notes=[
                "Regla PVAGEN-C: seguimiento hidrologico mensual + tras episodio de lluvia.",
                "Incluir seguimiento adicional tras episodio de lluvia >10 mm/24h.",
            ],
        ),
        # ── PVAGEN-D: Ruido (FR-014) — niveles de emision acustica ──
        PVAGenerationRule(
            rule_id="PVAGEN-D",
            target_receptor_ids=["FR-014"],
            pva_name="Seguimiento de la emision acustica y cumplimiento de limitaciones horarias",
            factor_id="FI-014",
            indicator=(
                "Registro mensual del cumplimiento del horario de operaciones ruidosas "
                "segun las limitaciones establecidas. Lista de verificacion por turno: "
                "cumple/no cumple/parcial. Si el estudio acustico (MED) define umbrales "
                "de nivel sonoro medibles, incluir control con sonometro segun protocolo "
                "del estudio. Registro de quejas formales de instalaciones vecinas."
            ),
            threshold=(
                "Operaciones ruidosas fuera del horario declarado, o recepcion de "
                "queja formal de instalacion vecina, o superacion del nivel de emision "
                "definido en el estudio acustico (si se ha realizado)."
            ),
            frequency="MENSUAL",
            records=[
                "Libro de registro de horarios de operaciones con firma del operario responsable.",
                "Registro de quejas formales recibidas y accion adoptada.",
                "Informe de medicion sonometrica si el estudio acustico lo establece.",
            ],
            notes=[
                "Regla PVAGEN-D: seguimiento mensual de ruido y limitacion horaria.",
                "El estudio acustico (MGEN-A si existe) puede precisar el protocolo.",
                "El libro de registro de operaciones puede reutilizarse como soporte.",
            ],
        ),
        # ── PVAGEN-E: Flora y Fauna (FR-007, FR-008) — verificacion de campo ──
        PVAGenerationRule(
            rule_id="PVAGEN-E",
            target_receptor_ids=["FR-007", "FR-008"],
            pva_name="Seguimiento de la ausencia de afeccion sobre flora y fauna del entorno",
            factor_id="FI-007",
            indicator=(
                "Inspeccion visual trimestral del perimetro exterior de la parcela "
                "para detectar senales de afeccion sobre vegetacion circundante "
                "(deposicion anormal de polvo, marchitamiento, danos visibles). "
                "Registro de presencia de fauna (aves, mamiferos, reptiles) en zona "
                "de influencia: avistamientos significativos y fecha."
            ),
            threshold=(
                "Presencia de deposicion de polvo o particulas metalicas visible sobre "
                "vegetacion natural en el perimetro exterior. "
                "Deteccion de fauna protegida en zona de influencia directa de la actividad."
            ),
            frequency="TRIMESTRAL",
            records=[
                "Ficha trimestral de inspeccion perimetral con resultado y fotografias.",
                "Registro de avistamientos de fauna relevante con especie, fecha y localizacion.",
            ],
            notes=[
                "Regla PVAGEN-E: seguimiento trimestral de flora y fauna del entorno.",
                "No afirmar ausencia de afeccion sin inspeccion de campo documentada.",
                "Esta ficha tambien cubre cobertura indirecta del vector polvo sobre flora.",
            ],
        ),
        # ── PVAGEN-F: ENP y Red Natura 2000 (FR-009, FR-010) — verificacion cartografica ──
        PVAGenerationRule(
            rule_id="PVAGEN-F",
            target_receptor_ids=["FR-009", "FR-010"],
            pva_name="Seguimiento documental de la relacion con ENP y Red Natura 2000",
            factor_id="FI-009",
            indicator=(
                "Verificacion anual de que no se han producido cambios normativos en "
                "la delimitacion de Espacios Naturales Protegidos o Red Natura 2000 "
                "que afecten a la instalacion. Consulta a la cartografia oficial del "
                "Gobierno de Canarias/MITECO. Registro del resultado."
            ),
            threshold=(
                "Modificacion normativa o cartografica que incluya la parcela o su "
                "entorno inmediato (<500 m) en un nuevo espacio protegido o zona "
                "de amortiguacion. Notificar al organo ambiental y consultar procedimiento."
            ),
            frequency="ANUAL",
            records=[
                "Registro anual de la verificacion con fecha de consulta y resultado.",
                "Copia o referencia de la cartografia oficial consultada.",
            ],
            notes=[
                "Regla PVAGEN-F: seguimiento anual de cambios en espacios protegidos.",
                "La evaluacion de repercusiones sobre Red Natura 2000 corresponde al "
                "organo ambiental cuando proceda — esta ficha no la sustituye.",
            ],
        ),
        # ── PVAGEN-G: Paisaje (FR-011) — integracion visual ──
        PVAGenerationRule(
            rule_id="PVAGEN-G",
            target_receptor_ids=["FR-011"],
            pva_name="Seguimiento del impacto visual y estado exterior de la instalacion",
            factor_id="FI-011",
            indicator=(
                "Inspeccion visual semestral del exterior de la instalacion: "
                "estado de la fachada, orden y limpieza del exterior, volumen de "
                "acopio visible desde viales publicos. "
                "Escala visual: 1 (integrado) - 3 (impacto visual significativo)."
            ),
            threshold=(
                "Valor >= 3 en dos inspecciones consecutivas, o recepcion de queja "
                "formal sobre el estado visual de la instalacion."
            ),
            frequency="SEMESTRAL",
            records=[
                "Ficha semestral de inspeccion visual exterior con escala y fotografias.",
                "Registro de quejas formales sobre impacto visual y accion adoptada.",
            ],
            notes=["Regla PVAGEN-G: seguimiento semestral del impacto visual."],
        ),
        # ── PVAGEN-H: Patrimonio cultural (FR-012) — vigilancia ante hallazgos ──
        PVAGenerationRule(
            rule_id="PVAGEN-H",
            target_receptor_ids=["FR-012"],
            pva_name="Protocolo de actuacion ante hallazgos patrimoniales",
            factor_id="FI-012",
            indicator=(
                "Registro inmediato ante cualquier hallazgo de materiales, estructuras "
                "u objetos de posible interes arqueologico o etnografico durante las "
                "operaciones de la instalacion. "
                "Instruccion escrita al personal sobre el protocolo de actuacion "
                "ante hallazgos (paralizar, no manipular, notificar)."
            ),
            threshold=(
                "Cualquier hallazgo de material que pudiera ser de interes patrimonial "
                "durante las operaciones. Suspension inmediata de la actividad en la zona "
                "y notificacion al organo competente en patrimonio cultural."
            ),
            frequency="CONDICIONAL",
            records=[
                "Acta de hallazgo con fecha, localizacion, descripcion y fotografias.",
                "Registro de notificacion al organo competente en patrimonio cultural.",
                "Instruccion al personal sobre protocolo de actuacion ante hallazgos.",
            ],
            notes=[
                "Regla PVAGEN-H: protocolo ante hallazgos patrimoniales (solo si se producen).",
                "La frecuencia es condicional — el seguimiento se activa ante un hallazgo.",
                "No descarta afeccion patrimonial sin respuesta del organo competente.",
            ],
        ),
        # ── PVAGEN-I: Inundabilidad / Riesgos naturales (FR-005, FR-016) ──
        PVAGenerationRule(
            rule_id="PVAGEN-I",
            target_receptor_ids=["FR-005", "FR-016"],
            pva_name="Seguimiento de exposicion a riesgos naturales e inundabilidad",
            factor_id="FI-005",
            indicator=(
                "Verificacion anual de que no se han producido cambios en la "
                "cartografia oficial de inundabilidad (SNCZI/MITECO) o de riesgos "
                "naturales (GRAFCAN para Canarias) que afecten a la parcela. "
                "Registro de episodios de lluvia extrema (>50 mm/24h) o fenomenos "
                "climaticos severos que afecten a la instalacion."
            ),
            threshold=(
                "Inclusion de la parcela en nueva zona de riesgo segun actualizacion "
                "cartografica oficial, o episodio hidrologico extremo que afecte "
                "a la instalacion."
            ),
            frequency="ANUAL",
            records=[
                "Registro anual de la verificacion cartografica con fecha y resultado.",
                "Ficha de episodio extremo si se produce (fecha, afeccion, medidas adoptadas).",
            ],
            notes=["Regla PVAGEN-I: seguimiento anual de riesgos naturales e inundabilidad."],
        ),
        # ── PVAGEN-J: Cambio climático (FR-015) — consumos energéticos ──
        PVAGenerationRule(
            rule_id="PVAGEN-J",
            target_receptor_ids=["FR-015"],
            pva_name="Seguimiento de consumos energeticos y medidas de eficiencia",
            factor_id="FI-015",
            indicator=(
                "Registro anual de los consumos de combustible y electricidad de "
                "la instalacion. Verificacion de que los equipos de combustion "
                "(si existen) han recibido el mantenimiento previsto. "
                "Lista de verificacion de medidas de eficiencia energetica adoptadas."
            ),
            threshold=(
                "Incremento >20% del consumo energetico anual sin justificacion "
                "por aumento de actividad documentado, o incumplimiento del "
                "mantenimiento previsto de equipos de combustion."
            ),
            frequency="ANUAL",
            records=[
                "Registro anual de consumos energeticos (facturas, contadores).",
                "Listado de mantenimientos realizados en equipos de combustion.",
                "Lista de verificacion de medidas de eficiencia energetica.",
            ],
            notes=["Regla PVAGEN-J: seguimiento anual de consumos y eficiencia energetica."],
        ),
        # ── PVAGEN-K: Socioeconomía POSITIVO (FR-013) — eficacia del empleo ──
        PVAGenerationRule(
            rule_id="PVAGEN-K",
            target_receptor_ids=["FR-013"],
            target_natures=["POSITIVO"],
            pva_name="Seguimiento de la eficacia del impacto positivo socioeconomico",
            factor_id="FI-013",
            indicator=(
                "Registro anual del numero de empleos directos mantenidos y/o creados "
                "por la actividad. Registro del volumen de actividad economica local "
                "generada (contratos con proveedores locales si es verificable). "
                "Fuente: datos internos de la empresa."
            ),
            threshold="No aplica — indicador de eficacia positiva. Sin umbral de alarma.",
            frequency="ANUAL",
            records=[
                "Registro anual de plantilla con numero de empleos directos.",
                "Memoria economica anual con dato de actividad si esta disponible.",
            ],
            notes=[
                "Regla PVAGEN-K: seguimiento anual del impacto positivo socioeconomico.",
                "Regla de no compensacion: este PVA es independiente de los negativos.",
                "No compensa ni reduce la significancia de impactos negativos.",
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Función interna: detectar si un impacto tiene CONTs abiertos
# ---------------------------------------------------------------------------

def _impact_has_cont(impact: EnvironmentalImpact) -> bool:
    """True si algún data_gap del impacto parece un CONT (E-9)."""
    for gap_id in impact.data_gaps:
        if "CONT" in gap_id.upper():
            return True
    return False


def _impact_is_conditioned(impact: EnvironmentalImpact) -> bool:
    """True si el impacto es INDETERMINADO o tiene CONTs abiertos (E-9)."""
    return (
        impact.nature == "INDETERMINADO"
        or impact.status == "INDETERMINADO"
        or _impact_has_cont(impact)
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def generate_pva_for_model(
    model: Phase6Model,
    rules: Optional[list[PVAGenerationRule]] = None,
) -> PVAGenerationResult:
    """Genera fichas PVA para todos los impactos de un Phase6Model.

    Estrategia:
    1. Agrupa los impactos por receptor_id.
    2. Por cada grupo, aplica la primera regla coincidente y genera UN PVA
       que cubre todos los impactos del grupo.
    3. Actualiza target_measure_ids del PVA con las medidas que apuntan a
       esos impactos.
    4. Detecta fichas CONDICIONADO por CONTs (E-9).
    5. Añade nota de incertidumbre en umbrales de impactos positivos con
       data_gaps no vacíos (E-10).
    6. Siempre añade una ficha de revisión anual global al final.
    7. Informa de impactos negativos/mixtos con significancia alta sin cobertura.

    Función pura sin efectos secundarios. No muta el modelo original.

    Args:
        model: Phase6Model con impactos, medidas y receptores poblados.
        rules: Reglas de generación. Si None, usa las reglas por defecto.

    Returns:
        PVAGenerationResult con el modelo actualizado y estadísticas.
    """
    if rules is None:
        rules = default_pva_generation_rules()

    # ── Índices de consulta rápida ──
    measure_by_impact: dict[str, list[str]] = {}
    for med in model.measures:
        for tid in med.target_impact_ids:
            measure_by_impact.setdefault(tid, []).append(med.measure_id)

    # Agrupar impactos no descartados por receptor_id
    impacts_by_receptor: dict[str, list[EnvironmentalImpact]] = {}
    for imp in model.impacts:
        if imp.status == "DESCARTADO_JUSTIFICADO":
            continue
        impacts_by_receptor.setdefault(imp.receptor_id, []).append(imp)

    all_pva: list[PVAProgram] = []
    pva_index = 1
    impact_pva_map: dict[str, list[str]] = {}  # impact_id → [pva_id]
    covered_impact_ids: set[str] = set()
    conditioned_count = 0
    coverage_notes: list[str] = []
    warnings: list[str] = []
    notes_out: list[str] = []

    # ── Generación por receptor ──
    for receptor_id, receptor_impacts in impacts_by_receptor.items():
        # Buscar regla aplicable (primera que coincida con algún impacto del grupo)
        matched_rule: Optional[PVAGenerationRule] = None
        for rule in rules:
            if any(rule.matches(imp) for imp in receptor_impacts):
                matched_rule = rule
                break

        if matched_rule is None:
            # Sin regla: registrar en avisos pero no bloquear
            warnings.append(
                f"Sin regla PVA para receptor {receptor_id}. "
                f"Impactos afectados: "
                + ", ".join(i.impact_id for i in receptor_impacts)
                + ". Declarar GAP-PVA en Bloque E."
            )
            continue

        # Impactos que cubre esta ficha (los que la regla acepta)
        covered = [imp for imp in receptor_impacts if matched_rule.matches(imp)]
        if not covered:
            continue

        target_imp_ids = [imp.impact_id for imp in covered]
        # Medidas que apuntan a esos impactos
        target_med_ids: list[str] = []
        seen_meds: set[str] = set()
        for imp_id in target_imp_ids:
            for mid in measure_by_impact.get(imp_id, []):
                if mid not in seen_meds:
                    target_med_ids.append(mid)
                    seen_meds.add(mid)

        # ── E-9: detectar si algún impacto está condicionado por CONT ──
        any_conditioned = any(_impact_is_conditioned(imp) for imp in covered)

        # ── E-10: impactos positivos con data_gaps no vacíos ──
        positive_with_gaps = [
            imp for imp in covered
            if imp.nature == "POSITIVO" and imp.data_gaps
        ]

        # Construir notas de la ficha
        pva_notes: list[str] = list(matched_rule.notes)
        pva_notes.append(
            f"Generada por {matched_rule.rule_id} para: "
            + ", ".join(target_imp_ids) + "."
        )

        pva_warnings: list[str] = []

        if any_conditioned:
            cont_ids = [
                gap for imp in covered for gap in imp.data_gaps
                if "CONT" in gap.upper()
            ]
            cont_ref = ", ".join(sorted(set(cont_ids))) if cont_ids else "CONT abierto"
            pva_warnings.append(
                f"CONDICIONADO — se activa si se confirma {cont_ref}. "
                f"Esta ficha no entra en vigor hasta la resolucion del CONT. "
                f"Si el CONT se resuelve negativamente, esta ficha queda DESCARTADA."
            )
            conditioned_count += 1

        # Nota de incertidumbre E-10 para impactos positivos con gaps
        if positive_with_gaps:
            gap_refs = ", ".join(
                g for imp in positive_with_gaps for g in imp.data_gaps
            )
            pva_warnings.append(
                f"NOTA DE INCERTIDUMBRE (E-10): El umbral de control de este "
                f"indicador positivo depende de datos afectados por gap(s) "
                f"activo(s): {gap_refs}. "
                f"El umbral es PROVISIONAL hasta la resolucion de esos gaps."
            )

        # Aviso si no hay Responsable Ambiental designado (siempre)
        pva_warnings.append(
            "AVISO GAP-PVA-001: El Responsable Ambiental no esta designado. "
            "Esta ficha PVA no puede ejecutarse hasta que el promotor "
            "designe un Responsable Ambiental (criticidad ALTA)."
        )

        pva = PVAProgram(
            pva_id=f"PVA-{pva_index:03d}",
            name=matched_rule.pva_name,
            factor_id=matched_rule.factor_id,
            indicator=matched_rule.indicator,
            threshold=matched_rule.threshold,
            frequency=matched_rule.frequency,
            target_impact_ids=target_imp_ids,
            target_measure_ids=target_med_ids,
            responsible=matched_rule.responsible_note,
            records=list(matched_rule.records),
            warnings=pva_warnings,
            notes=pva_notes,
        )
        all_pva.append(pva)

        for imp_id in target_imp_ids:
            impact_pva_map.setdefault(imp_id, []).append(pva.pva_id)
            covered_impact_ids.add(imp_id)

        pva_index += 1

    # ── Ficha de revisión anual global (siempre) ──
    all_pva_ids_except_annual = [p.pva_id for p in all_pva]
    annual_pva = _build_annual_review_pva(
        pva_id=f"PVA-{pva_index:03d}",
        all_pva_ids=all_pva_ids_except_annual,
        all_impact_ids=[imp.impact_id for imp in model.impacts
                        if imp.status != "DESCARTADO_JUSTIFICADO"],
    )
    all_pva.append(annual_pva)
    pva_index += 1

    # ── Detectar impactos negativos/mixtos con significancia alta sin cobertura ──
    uncovered: list[str] = []
    for imp in model.impacts:
        if imp.status == "DESCARTADO_JUSTIFICADO":
            continue
        if imp.nature not in _PVA_REQUIRED_NATURES:
            continue
        if imp.significance_without_measures not in _PVA_REQUIRED_SIGNIFICANCES:
            continue
        if imp.impact_id not in covered_impact_ids:
            uncovered.append(imp.impact_id)

    if uncovered:
        warnings.append(
            f"{len(uncovered)} impacto(s) negativos/mixtos con significancia "
            "alta sin cobertura PVA. Declarar GAP-PVA en Bloque E: "
            + ", ".join(uncovered[:5])
            + ("..." if len(uncovered) > 5 else "")
        )

    # ── Actualizar pva_ids en impactos ──
    new_impacts: list[EnvironmentalImpact] = []
    for imp in model.impacts:
        new_ids = impact_pva_map.get(imp.impact_id, [])
        if new_ids or imp.pva_ids:
            combined = list(imp.pva_ids)
            seen_ids: set[str] = set(combined)
            for pid in new_ids:
                if pid not in seen_ids:
                    combined.append(pid)
                    seen_ids.add(pid)
            new_imp = dataclasses.replace(imp, pva_ids=combined)
        else:
            new_imp = imp
        new_impacts.append(new_imp)

    updated_model = dataclasses.replace(
        model,
        impacts=new_impacts,
        pva_programs=all_pva,
    )

    generated_count = len(all_pva)

    if not model.impacts:
        warnings.append(
            "El modelo no contiene impactos. "
            "Ejecute primero IM-03 (phase6-identify-impacts --write) "
            "y IM-04 (phase6-assign-conesa --write)."
        )

    notes_out.append(
        f"{generated_count} ficha(s) PVA generadas "
        f"({generated_count - 1} por receptor + 1 revision anual global)."
    )
    notes_out.append(
        "Responsable Ambiental declarado como GAP-PVA-001 en todas las fichas. "
        "Debe designarse antes del inicio de la actividad (criticidad ALTA)."
    )
    if conditioned_count > 0:
        notes_out.append(
            f"{conditioned_count} ficha(s) CONDICIONADA(S) por CONTs abiertos (E-9). "
            "Revisar en Bloque E y tabla de gaps."
        )

    return PVAGenerationResult(
        model=updated_model,
        generated_count=generated_count,
        conditioned_count=conditioned_count,
        uncovered_impact_ids=uncovered,
        coverage_notes=coverage_notes,
        warnings=warnings,
        notes=notes_out,
    )


def _build_annual_review_pva(
    pva_id: str,
    all_pva_ids: list[str],
    all_impact_ids: list[str],
) -> PVAProgram:
    """Genera la ficha de revisión interna anual del PVA (siempre presente).

    Es una ficha agregada que verifica el cumplimiento global de todas las
    medidas y el estado de todos los indicadores. No tiene umbral de un
    indicador concreto — tiene un umbral de cumplimiento global.

    La nota de remisión al órgano ambiental es obligatoria en esta ficha
    (especificacion_bloque_e_pva §7).
    """
    pvas_ref = ", ".join(all_pva_ids) if all_pva_ids else "(ninguna ficha generada)"
    return PVAProgram(
        pva_id=pva_id,
        name="Revision interna anual del PVA",
        factor_id="FI-016",
        indicator=(
            "Revision anual de todas las fichas PVA del expediente ("
            + pvas_ref
            + "). Lista de verificacion por ficha: cumplimiento del "
            "indicador, estado del umbral, incidencias documentadas en el "
            "periodo, medidas correctivas adoptadas. "
            "Resultado: CONFORME / NO CONFORME (con incidencias) / "
            "NO EJECUTADO (por falta de Responsable Ambiental u otro motivo)."
        ),
        threshold=(
            "Incumplimiento reiterado de dos o mas fichas PVA sin accion "
            "correctiva documentada, o resultado NO EJECUTADO sin causa justificada. "
            "Notificar al promotor para designacion o refuerzo del Responsable Ambiental."
        ),
        frequency="ANUAL",
        target_impact_ids=list(all_impact_ids),
        target_measure_ids=[],
        responsible="Responsable Ambiental designado por el promotor",
        records=[
            "Informe anual de revision del PVA con resultado de cada ficha.",
            "Tabla de incidencias del periodo: ficha, fecha, descripcion, accion adoptada.",
        ],
        warnings=[
            "AVISO GAP-PVA-001: El Responsable Ambiental no esta designado. "
            "Esta revision anual no puede ejecutarse sin designacion previa "
            "(criticidad ALTA).",
            "NOTA REMISION (obligatoria): La obligacion y periodicidad de remision "
            "de informes formales al organo ambiental depende de las condiciones que "
            "fije el Informe de Impacto Ambiental (IIA) que resuelva el expediente "
            "(art. 47 Ley 21/2013). En ausencia de condicion expresa del IIA, no se "
            "asume automaticamente la obligacion de remitir informes periodicos. "
            "El registro interno del PVA estara disponible para inspeccion a solicitud "
            "del organo competente en cualquier momento.",
        ],
        notes=[
            "Ficha agregada de revision anual global — siempre presente.",
            "Es el soporte del informe anual interno del Responsable Ambiental.",
            "Cubre todos los impactos e indicadores del expediente de forma global.",
        ],
    )


def merge_pva_into_model(
    model: Phase6Model,
    pva_programs: list[PVAProgram],
) -> Phase6Model:
    """Sustituye los programas PVA del modelo y actualiza pva_ids de los impactos.

    Función pura. No muta el modelo original. Usa dataclasses.replace().
    Conserva: actions, receptor_factors, impacts (significancias), measures.

    Args:
        model: Phase6Model original.
        pva_programs: Lista de fichas PVA a sustituir en el modelo.

    Returns:
        Nueva instancia de Phase6Model con pva_programs sustituidos y
        pva_ids de impactos actualizados.
    """
    impact_pva_map: dict[str, list[str]] = {}
    for pva in pva_programs:
        for tid in pva.target_impact_ids:
            impact_pva_map.setdefault(tid, []).append(pva.pva_id)

    new_impacts: list[EnvironmentalImpact] = []
    for impact in model.impacts:
        new_ids = impact_pva_map.get(impact.impact_id, [])
        if new_ids != list(impact.pva_ids):
            new_impact = dataclasses.replace(impact, pva_ids=list(new_ids))
        else:
            new_impact = impact
        new_impacts.append(new_impact)

    return dataclasses.replace(
        model,
        impacts=new_impacts,
        pva_programs=list(pva_programs),
    )
