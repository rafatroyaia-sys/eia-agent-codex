"""
cumulative_synergistic_section -- IM-08
Generador determinístico de la sección C.5 de efectos acumulativos y
sinérgicos del Bloque C del Documento Ambiental EIA.

Contexto metodológico:
  Art. 45.1.f) Ley 21/2013 exige el análisis de efectos acumulativos y
  sinérgicos. La sección C.5 es obligatoria (regla C-10 del sistema de
  prompts). Este módulo genera el contenido de C.5 de forma determinista
  a partir del Phase6Model ya construido (outputs de IM-03 a IM-07).

Decisión de ID (2026-05-12):
  IM-08 = Este generador (C.5 acumulativos/sinérgicos).
  El template C.5 era "IM-06 código" en el Área 14 del backlog original;
  se implementa ahora con ID canónico IM-08 por asignación del usuario.

Tipos de análisis implementados:
  ACUMULATIVO: un mismo receptor (factor ambiental) recibe presión de 2 o
    más acciones distintas del proyecto → efecto que se suma en el tiempo
    o en el espacio.
  SINÉRGICO: dos factores distintos interactúan de forma que el efecto
    combinado puede ser mayor que la suma de sus efectos individuales.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No crea impactos nuevos.
  - No modifica valoraciones Conesa.
  - No modifica medidas.
  - No modifica PVA.
  - No cierra impactos INDETERMINADO: la incertidumbre se declara, no se absorbe.
  - Lenguaje prudente: nunca "no existen efectos acumulativos" ni "se descartan".
  - Función pura: no muta el Phase6Model recibido.

Dependencias: IM-00 (impact_model).
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
    RECEPTOR_FACTOR_NAMES,
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
# Constantes
# ---------------------------------------------------------------------------

# Reglas de sinergias: dict con clave canónica → (lado A, lado B)
# Un grupo sinérgico existe cuando ambos lados tienen ≥1 impacto no descartado.
_SYNERGY_RULES: dict[str, tuple[list[str], list[str]]] = {
    "aire_ruido": (["FR-006"], ["FR-014"]),
    "suelo_hidrologia": (["FR-003"], ["FR-004"]),
    "hidrologia_red_natura": (["FR-004"], ["FR-009", "FR-010"]),
    "biodiversidad_red_natura": (["FR-007", "FR-008"], ["FR-009", "FR-010"]),
    "clima_riesgos": (["FR-015"], ["FR-016"]),
}

# Descripción legible de cada tipo de sinergia
_SYNERGY_DESCRIPTIONS: dict[str, str] = {
    "aire_ruido": (
        "Sinergia potencial entre calidad del aire (FR-006) y ruido (FR-014). "
        "Las operaciones de tratamiento mecanico, carga/descarga y maquinaria "
        "generan simultaneamente emision de particulas y niveles de ruido. "
        "La presion combinada sobre el entorno puede superar la suma de los "
        "efectos individuales, especialmente en periodos de maxima actividad."
    ),
    "suelo_hidrologia": (
        "Sinergia potencial entre suelos (FR-003) e hidrologia (FR-004). "
        "Los riesgos de contaminacion del suelo por derrames accidentales, "
        "almacenamiento de residuos peligrosos o lixiviados pueden propagarse "
        "al sistema hidrologico superficial o subterraneo a traves de la "
        "escorrentia o infiltracion, amplificando el efecto sobre ambos factores."
    ),
    "hidrologia_red_natura": (
        "Sinergia potencial entre hidrologia (FR-004) y espacios protegidos "
        "(FR-009/FR-010). Los vectores hidrologicos (escorrentias, arrastres) "
        "pueden transportar contaminantes desde la instalacion hacia masas de "
        "agua superficial o subterranea vinculadas a espacios naturales proximos. "
        "El grado de afeccion depende de la proximidad y la conectividad hidrica."
    ),
    "biodiversidad_red_natura": (
        "Sinergia potencial entre flora/fauna (FR-007/FR-008) y espacios "
        "protegidos (FR-009/FR-010). La presion sobre especies o habitats del "
        "entorno inmediato puede tener implicaciones sobre la integridad de "
        "espacios de la Red Natura 2000 o ENP proximos, especialmente si "
        "existen vectores de afeccion indirecta como el polvo o el ruido."
    ),
    "clima_riesgos": (
        "Sinergia potencial entre cambio climatico (FR-015) y riesgos naturales "
        "(FR-016). El incremento de la frecuencia o intensidad de fenomenos "
        "climaticos extremos (lluvias torrenciales, sequias) puede amplificar "
        "la exposicion de la instalacion a riesgos naturales e incrementar la "
        "vulnerabilidad del entorno afectado."
    ),
}

# Factores sensibles: receptores donde INDETERMINADO requiere cautela adicional
_SENSITIVE_RECEPTORS: frozenset[str] = frozenset({
    "FR-007", "FR-008",  # Flora, Fauna
    "FR-009", "FR-010",  # ENP, Red Natura 2000
    "FR-012",            # Patrimonio cultural
})

# Natures que generan presión acumulable
_CUMULATIVE_NATURES: frozenset[str] = frozenset({"NEGATIVO", "MIXTO", "INDETERMINADO"})

# Status excluido de los análisis
_EXCLUDED_STATUS: str = "DESCARTADO_JUSTIFICADO"


# ---------------------------------------------------------------------------
# CumulativeSynergyIssue
# ---------------------------------------------------------------------------

@dataclass
class CumulativeSynergyIssue:
    """Incidencia del análisis de efectos acumulativos y sinérgicos.

    severity: WARNING (incertidumbre o dato insuficiente) /
              INFO (grupo detectado o impacto ignorado).
    code: código canónico de la incidencia.
    factor_id: factor principal afectado (FR-XXX) o None si es global.
    impact_ids: IDs de impactos involucrados.
    message: descripción del hallazgo.
    recommendation: acción recomendada.

    Nota: este módulo nunca genera ERROR — su propósito es declarar
    hallazgos y cautelas, no bloquear el expediente.
    """

    severity: str
    code: str
    factor_id: Optional[str]
    impact_ids: list[str]
    message: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "factor_id": self.factor_id,
            "impact_ids": list(self.impact_ids),
            "message": self.message,
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}]", self.code]
        if self.factor_id:
            parts.append(f"({self.factor_id})")
        parts.append(self.message[:80] + ("..." if len(self.message) > 80 else ""))
        return _ascii_safe(" ".join(parts))


# ---------------------------------------------------------------------------
# CumulativeSynergyResult
# ---------------------------------------------------------------------------

@dataclass
class CumulativeSynergyResult:
    """Resultado del análisis de efectos acumulativos y sinérgicos."""

    markdown: str = ""
    """Contenido completo de la sección C.5 en markdown."""

    cumulative_groups: dict[str, list[str]] = field(default_factory=dict)
    """Grupos acumulativos detectados: receptor_id → [impact_id, ...]."""

    synergistic_groups: dict[str, list[str]] = field(default_factory=dict)
    """Grupos sinérgicos detectados: synergy_key → [impact_id, ...]."""

    unresolved_gaps: list[str] = field(default_factory=list)
    """IDs de gaps sin resolver relevantes para el análisis acumulativo."""

    issues: list[CumulativeSynergyIssue] = field(default_factory=list)
    """Incidencias (INFO / WARNING) generadas durante el análisis."""

    warnings: list[str] = field(default_factory=list)
    """Avisos generales del proceso."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad."""

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def to_dict(self) -> dict:
        return {
            "markdown": self.markdown,
            "cumulative_groups": {k: list(v) for k, v in self.cumulative_groups.items()},
            "synergistic_groups": {k: list(v) for k, v in self.synergistic_groups.items()},
            "unresolved_gaps": list(self.unresolved_gaps),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
        }

    def summary(self) -> str:
        lines = [
            "--- IM-08 Generador C.5 Efectos acumulativos y sinergicos ---",
            f"Grupos acumulativos : {len(self.cumulative_groups)}",
            f"Grupos sinergicos   : {len(self.synergistic_groups)}",
            f"Gaps sin resolver   : {len(self.unresolved_gaps)}",
            f"WARNINGs            : {self.warning_count()}",
            f"INFOs               : {self.info_count()}",
        ]
        if self.cumulative_groups:
            for r_id, imp_ids in self.cumulative_groups.items():
                name = RECEPTOR_FACTOR_NAMES.get(r_id, r_id)
                lines.append(f"  Acum. {_ascii_safe(name)}: {', '.join(imp_ids)}")
        if self.synergistic_groups:
            for syn_key in self.synergistic_groups:
                lines.append(f"  Sinerg.: {syn_key}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones de análisis
# ---------------------------------------------------------------------------

def group_impacts_by_receptor(
    model: Phase6Model,
) -> dict[str, list[EnvironmentalImpact]]:
    """Agrupa impactos por receptor_id, excluyendo DESCARTADO_JUSTIFICADO.

    Mantiene impactos con status INDETERMINADO/PENDIENTE_DATOS para que
    el análisis acumulativo refleje la incertidumbre existente.

    No muta el modelo.
    """
    groups: dict[str, list[EnvironmentalImpact]] = {}
    for imp in model.impacts:
        if imp.status == _EXCLUDED_STATUS:
            continue
        groups.setdefault(imp.receptor_id, []).append(imp)
    return groups


def detect_cumulative_impact_groups(
    model: Phase6Model,
) -> dict[str, list[str]]:
    """Detecta grupos de impactos acumulativos por receptor.

    Un receptor tiene efecto acumulativo cuando recibe 2 o más impactos
    con nature en NEGATIVO / MIXTO / INDETERMINADO, procedentes de la
    misma instalación (incluso si provienen de la misma acción).

    También detecta acumulación cuando un receptor sensible tiene varios
    impactos INDETERMINADO/PENDIENTE_DATOS, aunque sean de la misma acción.

    No modifica valoraciones. No crea impactos nuevos.

    Returns:
        dict: receptor_id → lista de impact_ids que forman el grupo.
        Solo incluye receptores con ≥2 impactos relevantes.
    """
    groups = group_impacts_by_receptor(model)
    cumulative: dict[str, list[str]] = {}

    for receptor_id, impacts in groups.items():
        # Filtrar solo impactos con naturaleza que genera presión acumulable
        relevant = [
            imp for imp in impacts
            if imp.nature in _CUMULATIVE_NATURES
        ]
        if len(relevant) >= 2:
            cumulative[receptor_id] = [imp.impact_id for imp in relevant]
        elif (
            len(relevant) >= 1
            and receptor_id in _SENSITIVE_RECEPTORS
            and any(
                imp.status in ("INDETERMINADO", "PENDIENTE_DATOS")
                or imp.significance_without_measures == "INDETERMINADO"
                for imp in relevant
            )
        ):
            # Factor sensible con un impacto INDETERMINADO: cautela acumulativa
            cumulative[receptor_id] = [imp.impact_id for imp in relevant]

    return cumulative


def detect_synergistic_impact_groups(
    model: Phase6Model,
) -> dict[str, list[str]]:
    """Detecta grupos de impactos sinérgicos entre pares de receptores.

    Un par de receptores genera sinergia potencial cuando ambos lados
    tienen al menos 1 impacto no descartado con nature relevante.

    Pares implementados (clave canónica → descripción):
      "aire_ruido"            → FR-006 + FR-014
      "suelo_hidrologia"      → FR-003 + FR-004
      "hidrologia_red_natura" → FR-004 + (FR-009 o FR-010)
      "biodiversidad_red_natura" → (FR-007 o FR-008) + (FR-009 o FR-010)
      "clima_riesgos"         → FR-015 + FR-016

    Un impacto con nature POSITIVO solo se incluye si su presencia
    activa el cruce con un receptor de naturaleza negativa/indeterminada.

    No modifica valoraciones. No crea impactos nuevos.

    Returns:
        dict: synergy_key → lista de impact_ids de ambos lados del par.
        Solo incluye pares con ambos lados representados.
    """
    groups = group_impacts_by_receptor(model)

    def _has_relevant_impacts(receptor_ids: list[str]) -> list[str]:
        """Devuelve impact_ids de los receptores dados con nature relevante."""
        ids: list[str] = []
        for r_id in receptor_ids:
            for imp in groups.get(r_id, []):
                if imp.nature in _CUMULATIVE_NATURES or imp.nature == "POSITIVO":
                    ids.append(imp.impact_id)
        return ids

    synergistic: dict[str, list[str]] = {}

    for key, (side_a, side_b) in _SYNERGY_RULES.items():
        ids_a = _has_relevant_impacts(side_a)
        ids_b = _has_relevant_impacts(side_b)
        if ids_a and ids_b:
            # Deduplicar manteniendo orden
            seen: set[str] = set()
            combined: list[str] = []
            for imp_id in ids_a + ids_b:
                if imp_id not in seen:
                    combined.append(imp_id)
                    seen.add(imp_id)
            synergistic[key] = combined

    return synergistic


def extract_unresolved_cumulative_gaps(
    model: Phase6Model,
) -> list[str]:
    """Recopila gaps sin resolver relevantes para el análisis acumulativo.

    Fuentes:
      - data_gaps de impactos INDETERMINADO o con significancia INDETERMINADO.
      - data_gaps de impactos en receptores sensibles.
      - critical_gaps de los ReceptorFactor.

    Deduplica sin cambiar el orden de primera aparición.
    No muta el modelo.
    """
    gaps: list[str] = []
    seen: set[str] = set()

    def _add(gap_id: str) -> None:
        if gap_id and gap_id not in seen:
            gaps.append(gap_id)
            seen.add(gap_id)

    # De impactos INDETERMINADO o con significancia INDETERMINADO
    for imp in model.impacts:
        if imp.status == _EXCLUDED_STATUS:
            continue
        if (
            imp.status in ("INDETERMINADO", "PENDIENTE_DATOS")
            or imp.nature == "INDETERMINADO"
            or imp.significance_without_measures == "INDETERMINADO"
            or imp.receptor_id in _SENSITIVE_RECEPTORS
        ):
            for g in imp.data_gaps:
                _add(g)

    # De ReceptorFactor — critical_gaps
    for rf in model.receptor_factors:
        for g in rf.critical_gaps:
            _add(g)

    return gaps


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def build_cumulative_synergistic_markdown(
    model: Phase6Model,
) -> str:
    """Genera la sección C.5 de efectos acumulativos y sinérgicos en markdown.

    Estructura:
      ## C.5. Efectos acumulativos y sinérgicos
      ### C.5.1. Alcance metodológico
      ### C.5.2. Efectos acumulativos identificados
      ### C.5.3. Efectos sinérgicos potenciales
      ### C.5.4. Gaps e incertidumbres
      ### C.5.5. Conclusión prudente

    Reglas de prudencia aplicadas:
      - Nunca: "no existen efectos acumulativos"
      - Nunca: "se descartan efectos acumulativos"
      - Nunca: "no existen sinergias"
      - Nunca: "se descartan sinergias"
      - Si sin datos: "No se dispone de información suficiente para cerrar el
        análisis; se mantiene como cautela metodológica."
      - No cierra impactos INDETERMINADO.
      - No cambia la valoración individual.

    No muta el modelo.
    """
    cumulative = detect_cumulative_impact_groups(model)
    synergistic = detect_synergistic_impact_groups(model)
    gaps = extract_unresolved_cumulative_gaps(model)

    lines: list[str] = []

    lines.append("## C.5. Efectos acumulativos y sinérgicos")
    lines.append("")

    # ── C.5.1. Alcance metodológico ──────────────────────────────────────
    lines.append("### C.5.1. Alcance metodológico")
    lines.append("")
    lines.append(
        "Esta sección analiza los efectos ambientales que pueden manifestarse por "
        "la acumulación de presiones sobre un mismo factor receptor o por la "
        "interacción sinérgica entre factores distintos, conforme a lo exigido "
        "por el art. 45.1.f) de la Ley 21/2013, de 9 de diciembre, de evaluación "
        "ambiental."
    )
    lines.append("")
    lines.append(
        "El análisis se realiza de forma determinista a partir del modelo de "
        "impactos construido en las secciones C.1 a C.4. No sustituye la "
        "valoración técnica final ni modifica la significancia individual de "
        "ningún impacto. Los impactos con estado INDETERMINADO no quedan "
        "cerrados por este análisis: la incertidumbre se declara y se propaga "
        "a la conclusión."
    )
    lines.append("")
    lines.append(
        "**Limitación de gabinete**: Este análisis opera con los datos disponibles "
        "en el expediente. No se han podido verificar en campo ni consultar "
        "fuentes de datos de instalaciones vecinas o de carga ambiental acumulada "
        "del entorno. En consecuencia, los efectos acumulativos y sinérgicos "
        "con terceras instalaciones no pueden cuantificarse y se mantienen como "
        "cautela metodológica."
    )
    lines.append("")

    # ── C.5.2. Efectos acumulativos ──────────────────────────────────────
    lines.append("### C.5.2. Efectos acumulativos identificados")
    lines.append("")

    if cumulative:
        lines.append(
            "Se han identificado los siguientes grupos de impactos con potencial "
            "efecto acumulativo sobre el mismo factor receptor:"
        )
        lines.append("")
        for receptor_id, impact_ids in cumulative.items():
            factor_name = RECEPTOR_FACTOR_NAMES.get(receptor_id, receptor_id)
            fi_id = RECEPTOR_FACTOR_IDS.get(receptor_id, "")
            lines.append(
                f"**{receptor_id} — {factor_name}** ({fi_id}): "
                f"{len(impact_ids)} impacto(s) identificados — "
                + ", ".join(impact_ids)
                + "."
            )
            # Determinar si hay incertidumbre en el grupo
            group_impacts = [
                imp for imp in model.impacts
                if imp.impact_id in impact_ids
            ]
            any_indet = any(
                imp.status in ("INDETERMINADO", "PENDIENTE_DATOS")
                or imp.significance_without_measures == "INDETERMINADO"
                for imp in group_impacts
            )
            if any_indet:
                lines.append(
                    f"> ⚠️ Al menos un impacto en este grupo tiene datos "
                    "insuficientes para una valoración completa "
                    "(status INDETERMINADO o PENDIENTE_DATOS). "
                    "El efecto acumulativo sobre este factor no puede "
                    "cuantificarse en esta fase."
                )
            lines.append("")

        lines.append(
            "> **Nota metodológica**: El análisis acumulativo anterior "
            "identifica los focos de presión coincidente. No supone que el "
            "efecto acumulado sea necesariamente significativo: esa valoración "
            "requiere datos de campo o modelización que exceden el alcance "
            "del modo gabinete."
        )
    else:
        lines.append(
            "Con la información disponible, no se han detectado grupos de "
            "acciones que generen presión simultánea significativa sobre un "
            "mismo factor receptor. No se dispone de información suficiente "
            "para cerrar el análisis acumulativo de forma definitiva; "
            "se mantiene como cautela metodológica que podría activarse si "
            "se identificaran nuevas acciones o instalaciones en el entorno."
        )
    lines.append("")

    # ── C.5.3. Efectos sinérgicos ─────────────────────────────────────────
    lines.append("### C.5.3. Efectos sinérgicos potenciales")
    lines.append("")

    if synergistic:
        lines.append(
            "Se han identificado los siguientes pares de factores con potencial "
            "interacción sinérgica. Estos efectos potenciales se declaran como "
            "cautela metodológica y no implican que el efecto sinérgico sea "
            "necesariamente adverso ni cuantificable en modo gabinete:"
        )
        lines.append("")
        for key, impact_ids in synergistic.items():
            desc = _SYNERGY_DESCRIPTIONS.get(key, f"Sinergia entre factores: {key}.")
            lines.append(f"**{key.replace('_', ' ').capitalize()}**")
            lines.append("")
            lines.append(desc)
            lines.append("")
            lines.append(
                f"*Impactos involucrados*: {', '.join(impact_ids)}."
            )
            lines.append("")

        lines.append(
            "> **Nota metodológica**: La detección de sinergias potenciales no "
            "equivale a la confirmación de que dichos efectos se producirán. "
            "La evaluación definitiva requiere datos de campo, modelización "
            "o análisis de instalaciones vecinas que no están disponibles "
            "en modo gabinete. Estos efectos deben revisarse si se obtienen "
            "nuevos datos."
        )
    else:
        lines.append(
            "Con la información disponible, no se han detectado pares de "
            "factores con impactos suficientes en ambos lados para activar "
            "las reglas de sinergia implementadas. No se dispone de información "
            "suficiente para cerrar el análisis sinérgico de forma definitiva; "
            "se mantiene como cautela metodológica que podría activarse si "
            "se identificaran impactos adicionales sobre los factores sensibles."
        )
    lines.append("")

    # ── C.5.4. Gaps e incertidumbres ──────────────────────────────────────
    lines.append("### C.5.4. Gaps e incertidumbres")
    lines.append("")

    if gaps:
        lines.append(
            "Los siguientes gaps activos afectan a la calidad del análisis "
            "acumulativo y sinérgico. Deben resolverse antes de dar por "
            "cerrado este análisis:"
        )
        lines.append("")
        for gap_id in gaps:
            lines.append(f"- **{gap_id}**: gap activo que limita el análisis.")
        lines.append("")
        lines.append(
            "> Mientras estos gaps permanezcan abiertos, el análisis de efectos "
            "acumulativos y sinérgicos sobre los factores afectados se considera "
            "PROVISIONAL."
        )
    else:
        lines.append(
            "No se han identificado gaps con impacto directo sobre el análisis "
            "acumulativo y sinérgico en las fuentes disponibles. "
            "Esto no excluye la existencia de incertidumbres no documentadas "
            "en el expediente."
        )
    lines.append("")

    # ── C.5.5. Conclusión prudente ────────────────────────────────────────
    lines.append("### C.5.5. Conclusión")
    lines.append("")
    lines.append(
        "El análisis de efectos acumulativos y sinérgicos realizado en esta "
        "sección no modifica la valoración individual de ninguno de los impactos "
        "identificados en C.1 a C.4. Cada impacto mantiene su naturaleza, "
        "significancia y estado declarados en la sección correspondiente."
    )
    lines.append("")

    n_cumulative = len(cumulative)
    n_synergistic = len(synergistic)
    n_gaps = len(gaps)

    if n_cumulative > 0 or n_synergistic > 0:
        lines.append(
            f"Se han detectado {n_cumulative} grupo(s) con potencial efecto "
            f"acumulativo y {n_synergistic} par(es) con potencial efecto "
            "sinérgico. Estos hallazgos deben tenerse en cuenta en la redacción "
            "de las medidas correctoras y en el diseño del Programa de Vigilancia "
            "Ambiental, pero no suponen por sí mismos una modificación de la "
            "valoración individual de los impactos."
        )
    else:
        lines.append(
            "Con la información disponible no se han activado reglas de "
            "acumulación ni de sinergia. Esta circunstancia no permite concluir "
            "que no existan efectos acumulativos o sinérgicos; simplemente "
            "refleja la limitación del análisis en modo gabinete."
        )
    lines.append("")

    if n_gaps > 0:
        lines.append(
            f"Existen {n_gaps} gap(s) activo(s) que condicionan la fiabilidad "
            "de este análisis. El análisis acumulativo y sinérgico debe "
            "revisarse cuando se resuelvan estos gaps."
        )
    else:
        lines.append(
            "Los efectos acumulativos y sinérgicos deben revisarse si se "
            "identifican nuevas acciones, instalaciones vecinas o datos de "
            "campo que modifiquen el modelo de impactos."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def build_cumulative_synergistic_section(
    model: Phase6Model,
) -> CumulativeSynergyResult:
    """Genera el resultado completo del análisis C.5.

    Orquesta:
      1. detect_cumulative_impact_groups
      2. detect_synergistic_impact_groups
      3. extract_unresolved_cumulative_gaps
      4. build_cumulative_synergistic_markdown
      5. Generación de issues INFO/WARNING

    Función pura. No muta el Phase6Model recibido.
    No genera impactos, medidas ni PVA.
    No modifica valoraciones.

    Returns:
        CumulativeSynergyResult completo con markdown y datos estructurados.
    """
    cumulative = detect_cumulative_impact_groups(model)
    synergistic = detect_synergistic_impact_groups(model)
    gaps = extract_unresolved_cumulative_gaps(model)
    markdown = build_cumulative_synergistic_markdown(model)

    issues: list[CumulativeSynergyIssue] = []
    warnings_out: list[str] = []
    notes_out: list[str] = []

    # ── Incidencias de grupos acumulativos ──
    for receptor_id, impact_ids in cumulative.items():
        factor_name = RECEPTOR_FACTOR_NAMES.get(receptor_id, receptor_id)
        group_impacts = [
            imp for imp in model.impacts
            if imp.impact_id in impact_ids
        ]
        any_indet = any(
            imp.status in ("INDETERMINADO", "PENDIENTE_DATOS")
            or imp.significance_without_measures == "INDETERMINADO"
            for imp in group_impacts
        )
        severity = "WARNING" if any_indet else "INFO"
        code = "CS-W001" if any_indet else "CS-I001"
        issues.append(CumulativeSynergyIssue(
            severity=severity,
            code=code,
            factor_id=receptor_id,
            impact_ids=list(impact_ids),
            message=(
                f"Efecto acumulativo detectado en {factor_name} ({receptor_id}): "
                f"{len(impact_ids)} impacto(s)."
                + (" Datos insuficientes para cuantificar." if any_indet else "")
            ),
            recommendation=(
                "Revisar en Bloque D si las medidas correctoras cubren "
                "la presion acumulada sobre este factor."
            ),
        ))

    # ── Incidencias de grupos sinérgicos ──
    for key, impact_ids in synergistic.items():
        issues.append(CumulativeSynergyIssue(
            severity="INFO",
            code="CS-I002",
            factor_id=None,
            impact_ids=list(impact_ids),
            message=(
                f"Sinergia potencial detectada: {key}. "
                f"{len(impact_ids)} impacto(s) involucrados."
            ),
            recommendation=(
                "Considerar en el diseño de medidas y PVA si la "
                "interaccion entre factores puede amplificar el efecto."
            ),
        ))

    # ── Incidencias de gaps ──
    if gaps:
        issues.append(CumulativeSynergyIssue(
            severity="WARNING",
            code="CS-W002",
            factor_id=None,
            impact_ids=[],
            message=(
                f"{len(gaps)} gap(s) activo(s) limitan la fiabilidad "
                "del analisis acumulativo y sinergico."
            ),
            recommendation=(
                "Resolver los gaps indicados antes de dar por cerrado "
                "el analisis de efectos acumulativos y sinergicos."
            ),
        ))

    # ── Aviso si modelo vacío ──
    if not model.impacts:
        warnings_out.append(
            "El modelo no contiene impactos. "
            "Ejecute phase6-identify-impacts --write antes de generar C.5."
        )

    # ── Notas de trazabilidad ──
    notes_out.append(
        f"Analisis sobre {len(model.impacts)} impacto(s): "
        f"{len(cumulative)} grupo(s) acumulativo(s), "
        f"{len(synergistic)} par(es) sinergico(s), "
        f"{len(gaps)} gap(s)."
    )
    notes_out.append(
        "El analisis no modifica ninguna valoracion ni crea impactos nuevos."
    )

    return CumulativeSynergyResult(
        markdown=markdown,
        cumulative_groups=cumulative,
        synergistic_groups=synergistic,
        unresolved_gaps=gaps,
        issues=issues,
        warnings=warnings_out,
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# Carga desde JSON
# ---------------------------------------------------------------------------

def _parse_phase6_model_minimal(data: dict) -> Phase6Model:
    """Reconstruye Phase6Model mínimo desde dict JSON para el análisis C.5.

    Solo reconstruye impacts y receptor_factors (los únicos necesarios
    para el análisis acumulativo/sinérgico).
    """
    from eia_agent.core.impact_model import ProjectAction

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

    receptor_factors: list[ReceptorFactor] = []
    for r in data.get("receptor_factors", []):
        receptor_factors.append(ReceptorFactor(
            receptor_id=r["receptor_id"],
            inventory_factor_id=r.get(
                "inventory_factor_id",
                r["receptor_id"].replace("FR-", "FI-"),
            ),
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
        warnings=data.get("warnings", []),
        notes=data.get("notes", []),
    )


def build_cumulative_synergistic_section_from_json(
    path: "str | Path",
) -> CumulativeSynergyResult:
    """Carga un Phase6Model JSON y genera el análisis C.5.

    Args:
        path: Ruta al JSON del Phase6Model.

    Returns:
        CumulativeSynergyResult con el análisis completo.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el JSON es inválido.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido en {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"El JSON de {path} no es un objeto.")
    model = _parse_phase6_model_minimal(data)
    return build_cumulative_synergistic_section(model)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_cumulative_synergistic_outputs(
    result: CumulativeSynergyResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs del análisis acumulativo y sinérgico.

    Escribe:
      - {output_dir}/cumulative_synergistic_result.json
      - {output_dir}/C5_acumulativos_sinergicos.md

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "cumulative_synergistic_result.json"
    md_path = output_dir / "C5_acumulativos_sinergicos.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result.markdown)

    return json_path, md_path
