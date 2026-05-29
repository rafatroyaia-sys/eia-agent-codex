"""
positive_impact_gap_validator -- RD-07
Validador de impactos positivos con gaps ALTA e incertidumbre para Fase 6 EIA.

Verifica que los impactos positivos con gaps de criticidad ALTA, incertidumbre
relevante o falta de datos base mantienen visible esa incertidumbre en:
  1. el modelo de impactos (notes/warnings);
  2. el Markdown/Bloque C, si existe;
  3. la documentacion de salida, si procede.

Evita que un impacto positivo se presente como beneficio cerrado, compensatorio
o plenamente acreditado cuando depende de datos no confirmados.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica el modelo ni ningun impacto/medida/PVA.
  - No declara aptitud administrativa.
  - No resuelve gaps ni cierra incertidumbres.

Dependencias: IM-00 (impact_model) — solo para anotaciones de tipo (TYPE_CHECKING).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from eia_agent.core.impact_model import EnvironmentalImpact

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

POSITIVE_GAP_STATUS = {
    "OK": "OK",
    "CON_OBSERVACIONES": "CON_OBSERVACIONES",
    "NO_CONFORME": "NO_CONFORME",
    "SIN_DATOS": "SIN_DATOS",
}

POSITIVE_GAP_SEVERITY = {
    "ERROR": "ERROR",
    "WARNING": "WARNING",
    "INFO": "INFO",
}

POSITIVE_SIGNIFICANCE_VALUES: frozenset[str] = frozenset({
    "POSITIVO",
    "BENEFICIOSO",
    "FAVORABLE",
    "COMPATIBLE_POSITIVO",
    "POSITIVE",
    "POSITIVO_MODERADO",
    "POSITIVO_NOTABLE",
})

HIGH_GAP_VALUES: frozenset[str] = frozenset({
    "ALTA",
    "BLOQUEANTE",
})

UNCERTAINTY_KEYWORDS: tuple[str, ...] = (
    "condicionado",
    "pendiente",
    "estimado",
    "no acreditado",
    "no confirmado",
    "declarado por el promotor",
    "falta de datos",
    "gap alta",
    "incertidumbre",
    "debe verificarse",
    "no compensa",
    "no puede compensar",
    "no debe utilizarse para compensar",
)

PROHIBITED_POSITIVE_CLOSURE_PHRASES: tuple[str, ...] = (
    "beneficio neto acreditado",
    "compensa los impactos negativos",
    "compensa afecciones",
    "impacto positivo cerrado",
    "sin incertidumbre",
    "plenamente acreditado",
    "mejora garantizada",
    "queda compensado",
    "balance ambiental positivo",
    "no requiere comprobacion",
)

# Prefijos de negacion que permiten las frases prohibidas
_NEGATION_PREFIXES: tuple[str, ...] = (
    "no ",
    "no se ",
    "no debe ",
    "no puede ",
    "no es ",
    "no se considera ",
    "no declara ",
    "no implica ",
)

# Palabras/frases que sugieren incertidumbre alta en texto libre
_HIGH_GAP_TEXT_MARKERS: tuple[str, ...] = (
    "alta",
    "bloqueante",
    "no acreditado",
    "no confirmado",
    "sin confirmar",
    "dato pendiente",
    "pendiente de confirmar",
    "estimado",
    "declarado sin confirmacion",
    "falta de dato",
    "incertidumbre alta",
)

# Status del impacto que implican incertidumbre intrinseca
_UNCERTAIN_STATUSES: frozenset[str] = frozenset({
    "PENDIENTE_DATOS",
    "INDETERMINADO",
})

# Markdowns relevantes a revisar en el expediente (rutas relativas)
_RELEVANT_MD_PATTERNS: tuple[str, ...] = (
    "documento/documento_ambiental_borrador.md",
    "auditoria/final_audit_result.md",
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def normalize_positive_gap_text(text: str) -> str:
    """Normaliza a minusculas sin tildes y compacta espacios. Tolera None."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(ascii_str.split())


def _get_field(impact, field_name: str, default=None):
    """Extrae un campo de un EnvironmentalImpact (dataclass) o dict."""
    if isinstance(impact, dict):
        return impact.get(field_name, default)
    return getattr(impact, field_name, default)


def _get_list(impact, field_name: str) -> list:
    """Extrae un campo de lista de impacto (dataclass o dict)."""
    val = _get_field(impact, field_name, [])
    if val is None:
        return []
    return list(val)


def _text_has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """True si el texto normalizado contiene alguna de las keywords."""
    norm = normalize_positive_gap_text(text)
    return any(k in norm for k in keywords)


# ---------------------------------------------------------------------------
# PositiveGapIssue
# ---------------------------------------------------------------------------

@dataclass
class PositiveGapIssue:
    """Incidencia detectada en la auditoria de impactos positivos con gaps ALTA."""

    severity: str
    code: str
    impact_id: Optional[str] = None
    source: str = ""
    message: str = ""
    recommendation: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "impact_id": self.impact_id,
            "source": self.source,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": list(self.evidence),
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}] {self.code}"]
        if self.impact_id:
            parts.append(f"impacto={self.impact_id}")
        parts.append(self.message)
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# PositiveGapValidationResult
# ---------------------------------------------------------------------------

@dataclass
class PositiveGapValidationResult:
    """Resultado de la auditoria de impactos positivos con gaps ALTA."""

    status: str
    checked_impacts: list[str] = field(default_factory=list)
    positive_impacts: list[str] = field(default_factory=list)
    positive_impacts_with_high_gaps: list[str] = field(default_factory=list)
    markdown_sources_checked: list[str] = field(default_factory=list)
    issues: list[PositiveGapIssue] = field(default_factory=list)
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
            "positive_impacts": list(self.positive_impacts),
            "positive_impacts_with_high_gaps": list(self.positive_impacts_with_high_gaps),
            "markdown_sources_checked": list(self.markdown_sources_checked),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
        }

    def summary(self) -> str:
        lines = [
            f"Auditoria impactos positivos con gaps ALTA — {self.status}",
            f"  Impactos revisados   : {len(self.checked_impacts)}",
            f"  Impactos positivos   : {len(self.positive_impacts)}",
            f"  Con gap ALTA         : {len(self.positive_impacts_with_high_gaps)}",
            f"  Markdowns revisados  : {len(self.markdown_sources_checked)}",
            (
                f"  Errores: {self.error_count()} | "
                f"Advertencias: {self.warning_count()} | "
                f"Infos: {self.info_count()}"
            ),
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
# Deteccion de impactos positivos
# ---------------------------------------------------------------------------

def impact_is_positive(impact: "EnvironmentalImpact | dict") -> bool:
    """
    True si el impacto es de naturaleza positiva.

    Detecta positivo por: nature, significance, o texto (description/name).
    Es prudente: 'no positivo' o 'sin efecto positivo' no se marcan como positivos.
    """
    # Por naturaleza declarada
    nature = str(_get_field(impact, "nature", "") or "")
    if nature == "POSITIVO":
        return True

    # Por significancia
    sig_wo = str(_get_field(impact, "significance_without_measures", "") or "")
    sig_w = str(_get_field(impact, "significance_with_measures", "") or "")
    if sig_wo in POSITIVE_SIGNIFICANCE_VALUES or sig_w in POSITIVE_SIGNIFICANCE_VALUES:
        return True

    # Por tipo de impacto (campo extra en algunos dicts)
    impact_type = str(_get_field(impact, "impact_type", "") or "")
    if impact_type.upper() in POSITIVE_SIGNIFICANCE_VALUES:
        return True

    # Por texto libre (description + name)
    _positive_text_markers = (
        "impacto positivo",
        "efecto positivo",
        "beneficio",
        "favorable",
        "mejora ambiental",
        "positivo sobre",
        "beneficioso",
    )
    _negative_guards = (
        "no positivo",
        "sin efecto positivo",
        "no genera beneficio",
        "no es positivo",
        "no implica beneficio",
    )

    for field_name in ("description", "name"):
        text = str(_get_field(impact, field_name, "") or "")
        norm = normalize_positive_gap_text(text)
        if any(g in norm for g in [normalize_positive_gap_text(n) for n in _negative_guards]):
            continue
        if any(m in norm for m in [normalize_positive_gap_text(m) for m in _positive_text_markers]):
            return True

    return False


# ---------------------------------------------------------------------------
# Extraccion de gaps del impacto
# ---------------------------------------------------------------------------

def extract_impact_gaps(impact: "EnvironmentalImpact | dict") -> list[dict]:
    """
    Extrae y normaliza los gaps del impacto como lista de dicts.

    Cada gap tiene: gap_id, criticality, description, status, source.
    Funciona con EnvironmentalImpact (data_gaps: list[str]) o dict
    (data_gaps: list[str|dict], gaps: list[dict]).
    """
    gaps: list[dict] = []

    # Fuente principal: data_gaps
    data_gaps_raw = _get_list(impact, "data_gaps")
    for item in data_gaps_raw:
        if isinstance(item, dict):
            gaps.append({
                "gap_id": str(item.get("gap_id", item.get("id", ""))),
                "criticality": str(item.get("criticality", item.get("criticidad", ""))).upper(),
                "description": str(item.get("description", item.get("descripcion", ""))),
                "status": str(item.get("status", "DESCONOCIDO")),
                "source": "data_gaps",
            })
        else:
            text = str(item)
            norm = normalize_positive_gap_text(text)
            crit = ""
            if "bloqueante" in norm:
                crit = "BLOQUEANTE"
            elif "alta" in norm:
                crit = "ALTA"
            elif "media" in norm:
                crit = "MEDIA"
            elif "baja" in norm:
                crit = "BAJA"
            gaps.append({
                "gap_id": text,
                "criticality": crit,
                "description": text,
                "status": "DESCONOCIDO",
                "source": "data_gaps",
            })

    # Fuente secundaria: gaps (campo presente en algunos dicts)
    gaps_raw = _get_list(impact, "gaps")
    for item in gaps_raw:
        if isinstance(item, dict):
            gaps.append({
                "gap_id": str(item.get("gap_id", item.get("id", ""))),
                "criticality": str(item.get("criticality", item.get("criticidad", ""))).upper(),
                "description": str(item.get("description", item.get("descripcion", ""))),
                "status": str(item.get("status", "DESCONOCIDO")),
                "source": "gaps",
            })
        else:
            text = str(item)
            gaps.append({
                "gap_id": text,
                "criticality": "",
                "description": text,
                "status": "DESCONOCIDO",
                "source": "gaps",
            })

    return gaps


# ---------------------------------------------------------------------------
# Deteccion de gap ALTA en impacto
# ---------------------------------------------------------------------------

def impact_has_high_gap(impact: "EnvironmentalImpact | dict") -> bool:
    """
    True si el impacto positivo tiene gaps de criticidad ALTA o indicadores
    equivalentes de incertidumbre alta.

    Detecta:
    - Algun gap con criticality ALTA o BLOQUEANTE.
    - notes/warnings que mencionan gap ALTA, incertidumbre, dato no acreditado.
    - Impacto marcado como PENDIENTE_DATOS o INDETERMINADO con data_gaps no vacios.
    - Status PENDIENTE_DATOS o INDETERMINADO en impacto estimado/declarado.
    """
    gaps = extract_impact_gaps(impact)

    # Gap con criticality explicita ALTA/BLOQUEANTE
    for g in gaps:
        if g.get("criticality", "") in HIGH_GAP_VALUES:
            return True

    # Status de incertidumbre + data_gaps presentes
    status_val = str(_get_field(impact, "status", "") or "")
    if status_val in _UNCERTAIN_STATUSES and gaps:
        return True

    # Solo status PENDIENTE_DATOS/INDETERMINADO sin gaps explícitos también es señal
    if status_val in _UNCERTAIN_STATUSES:
        return True

    # Textos libres: notes, warnings usan todos los marcadores
    norm_markers = tuple(normalize_positive_gap_text(m) for m in _HIGH_GAP_TEXT_MARKERS)
    for field_name in ("notes", "warnings"):
        for text in _get_list(impact, field_name):
            norm = normalize_positive_gap_text(str(text))
            if any(m in norm for m in norm_markers):
                return True

    # En description/name solo marcadores fuertes (no "estimado" suelto, que es W001)
    _strong_markers = tuple(
        m for m in norm_markers
        if m != normalize_positive_gap_text("estimado")
    )
    for field_name in ("description", "name"):
        text = str(_get_field(impact, field_name, "") or "")
        norm = normalize_positive_gap_text(text)
        if any(m in norm for m in _strong_markers):
            return True

    return False


# ---------------------------------------------------------------------------
# Deteccion de nota de incertidumbre en impacto
# ---------------------------------------------------------------------------

def impact_has_uncertainty_note(impact: "EnvironmentalImpact | dict") -> bool:
    """
    True si el impacto contiene una nota editorial explicita de incertidumbre
    en notes o warnings.

    No se comprueba description: que la descripcion diga "estimado" no es una
    nota editorial, sino el dato que desencadena W001. Solo notes/warnings
    son notas editoriales deliberadas del autor del modelo.
    """
    norm_keywords = tuple(normalize_positive_gap_text(k) for k in UNCERTAINTY_KEYWORDS)

    for field_name in ("notes", "warnings"):
        for text in _get_list(impact, field_name):
            norm = normalize_positive_gap_text(str(text))
            if any(k in norm for k in norm_keywords):
                return True

    return False


# ---------------------------------------------------------------------------
# Deteccion de nota de incertidumbre en texto Markdown
# ---------------------------------------------------------------------------

def text_has_positive_uncertainty_note(
    text: str,
    impact_id: Optional[str] = None,
) -> bool:
    """
    True si el texto (Markdown o documental) contiene:
    - el impact_id (si se proporciona) y alguna palabra/frase de incertidumbre
      en un contexto cercano (window de 600 chars); O
    - una seccion general de incertidumbre de impactos positivos.

    Si no se proporciona impact_id, busca seccion general de incertidumbre.
    """
    if not text:
        return False

    norm_text = normalize_positive_gap_text(text)
    norm_keywords = tuple(normalize_positive_gap_text(k) for k in UNCERTAINTY_KEYWORDS)

    if impact_id:
        norm_id = normalize_positive_gap_text(impact_id)
        # Buscar el impact_id en el texto
        start = 0
        while True:
            pos = norm_text.find(norm_id, start)
            if pos < 0:
                break
            # Ventana de contexto alrededor del impact_id
            window_start = max(0, pos - 300)
            window_end = min(len(norm_text), pos + 300)
            window = norm_text[window_start:window_end]
            if any(k in window for k in norm_keywords):
                return True
            start = pos + 1

    # Seccion general de impactos positivos con incertidumbre
    _positive_section_markers = (
        "impactos positivos",
        "efecto positivo",
        "beneficio",
        "impacto favorable",
    )
    for section_marker in _positive_section_markers:
        norm_marker = normalize_positive_gap_text(section_marker)
        start = 0
        while True:
            pos = norm_text.find(norm_marker, start)
            if pos < 0:
                break
            window_start = max(0, pos - 100)
            window_end = min(len(norm_text), pos + 400)
            window = norm_text[window_start:window_end]
            if any(k in window for k in norm_keywords):
                return True
            start = pos + 1

    return False


# ---------------------------------------------------------------------------
# Deteccion de frases de cierre/compensacion prohibidas
# ---------------------------------------------------------------------------

def text_has_prohibited_positive_closure(text: str) -> bool:
    """
    True si el texto contiene frases que declaran beneficio cerrado o
    compensacion de impactos negativos (sin negacion previa).

    Las formas negativas ('no compensa', 'no se considera plenamente acreditado')
    estan permitidas y no generan incidencia.
    """
    if not text:
        return False

    norm_text = normalize_positive_gap_text(text)
    norm_negations = tuple(normalize_positive_gap_text(p) for p in _NEGATION_PREFIXES)

    for phrase in PROHIBITED_POSITIVE_CLOSURE_PHRASES:
        norm_phrase = normalize_positive_gap_text(phrase)
        start = 0
        while True:
            pos = norm_text.find(norm_phrase, start)
            if pos < 0:
                break
            # Comprobar negacion en los 35 caracteres previos
            context_before = norm_text[max(0, pos - 35):pos]
            negated = any(context_before.rstrip().endswith(n) for n in norm_negations)
            if not negated:
                return True
            start = pos + 1

    return False


# ---------------------------------------------------------------------------
# Validacion de un impacto positivo
# ---------------------------------------------------------------------------

def validate_positive_impact_gap(
    impact: "EnvironmentalImpact | dict",
    markdown_texts: "dict[str, str] | None" = None,
) -> list[PositiveGapIssue]:
    """
    Valida un impacto individual. Solo genera issues si el impacto es positivo.

    Reglas:
    - Impacto no positivo → sin issues.
    - Impacto positivo con gap ALTA sin nota de incertidumbre → ERROR RD07-E001.
    - Impacto positivo con gap ALTA y lenguaje de cierre/compensacion → ERROR RD07-E002.
    - Impacto positivo estimado/declarado sin gap explicito → WARNING RD07-W001.
    - Nota en modelo pero no en Markdown → WARNING RD07-W002.
    """
    if not impact_is_positive(impact):
        return []

    impact_id = _get_field(impact, "impact_id")
    issues: list[PositiveGapIssue] = []

    has_high_gap = impact_has_high_gap(impact)
    has_model_note = impact_has_uncertainty_note(impact)

    # Comprobar si hay nota en algun Markdown
    has_md_note = False
    if markdown_texts:
        for src, md_text in markdown_texts.items():
            if text_has_positive_uncertainty_note(md_text, impact_id):
                has_md_note = True
                break

    # Comprobar frases de cierre/compensacion
    has_closure_in_model = False
    _model_texts = []
    for fname in ("description", "name"):
        t = str(_get_field(impact, fname, "") or "")
        if t:
            _model_texts.append(t)
    for fname in ("notes", "warnings"):
        _model_texts.extend(str(x) for x in _get_list(impact, fname))
    if any(text_has_prohibited_positive_closure(t) for t in _model_texts):
        has_closure_in_model = True

    has_closure_in_md = False
    if markdown_texts:
        for src, md_text in markdown_texts.items():
            if text_has_prohibited_positive_closure(md_text):
                has_closure_in_md = True
                break

    if has_high_gap:
        # RD07-E002: lenguaje de cierre/compensacion con gap ALTA
        if has_closure_in_model or has_closure_in_md:
            source_tag = "markdown" if has_closure_in_md else "modelo"
            issues.append(PositiveGapIssue(
                severity="ERROR",
                code="RD07-E002",
                impact_id=impact_id,
                source=source_tag,
                message=(
                    f"Impacto positivo {impact_id!r} con gap ALTA usa lenguaje de "
                    "cierre o compensacion que no puede estar presente mientras "
                    "el impacto depende de datos no confirmados."
                ),
                recommendation=(
                    "Eliminar o negar las frases de cierre/compensacion. "
                    "El impacto positivo no puede presentarse como beneficio acreditado "
                    "ni compensar impactos negativos hasta que los datos sean CONFIRMADOS."
                ),
                evidence=[
                    f"has_gap_alta={has_high_gap}",
                    f"closure_en={source_tag}",
                ],
            ))

        # RD07-E001: sin nota de incertidumbre visible
        if not has_model_note and not has_md_note:
            issues.append(PositiveGapIssue(
                severity="ERROR",
                code="RD07-E001",
                impact_id=impact_id,
                source="modelo",
                message=(
                    f"Impacto positivo {impact_id!r} tiene gap de criticidad ALTA pero "
                    "no incluye nota de incertidumbre visible en el modelo ni en el Markdown. "
                    "El impacto positivo queda presentado sin advertencia de incertidumbre."
                ),
                recommendation=(
                    "Anadir en el campo notes del impacto: "
                    "'Impacto positivo condicionado a la confirmacion de los datos aportados "
                    "por el promotor. No puede utilizarse para compensar impactos negativos.' "
                    "Asegurar que esta nota aparece tambien en el Bloque C del documento."
                ),
                evidence=[
                    f"impact_id={impact_id!r}",
                    f"has_high_gap={has_high_gap}",
                    f"nota_modelo={has_model_note}",
                    f"nota_markdown={has_md_note}",
                ],
            ))
        elif has_model_note and not has_md_note and markdown_texts:
            # RD07-W002: nota en modelo pero no propagada al Markdown
            issues.append(PositiveGapIssue(
                severity="WARNING",
                code="RD07-W002",
                impact_id=impact_id,
                source="markdown",
                message=(
                    f"Impacto positivo {impact_id!r} con gap ALTA tiene nota de "
                    "incertidumbre en el modelo pero no aparece en el Markdown del documento. "
                    "La incertidumbre es visible internamente pero no en el documento final."
                ),
                recommendation=(
                    "Verificar que la nota de incertidumbre del impacto positivo aparece "
                    "en el Bloque C del documento (seccion C.5 o la descripcion del impacto)."
                ),
                evidence=[
                    f"impact_id={impact_id!r}",
                    f"nota_modelo={has_model_note}",
                    f"markdowns_revisados={list(markdown_texts.keys())!r}",
                ],
            ))

    else:
        # Sin gap ALTA explicita: comprobar si el impacto es estimado/declarado
        status_val = str(_get_field(impact, "status", "") or "")
        _estimado_keywords = (
            "estimado",
            "declarado",
            "no acreditado",
            "pendiente",
        )
        norm_desc = normalize_positive_gap_text(
            str(_get_field(impact, "description", "") or "")
        )
        is_estimado = (
            status_val in _UNCERTAIN_STATUSES
            or any(
                k in norm_desc
                for k in [normalize_positive_gap_text(e) for e in _estimado_keywords]
            )
        )
        if is_estimado and not has_model_note:
            issues.append(PositiveGapIssue(
                severity="WARNING",
                code="RD07-W001",
                impact_id=impact_id,
                source="modelo",
                message=(
                    f"Impacto positivo {impact_id!r} parece ser estimado o declarado "
                    "(status={status_val!r}) pero no incluye nota explicita de incertidumbre. "
                    "Conveniente documentar la base de datos del impacto positivo."
                ),
                recommendation=(
                    "Anadir nota en el campo notes del impacto indicando la base de datos "
                    "sobre la que se estima el impacto positivo y su nivel de acreditacion."
                ),
                evidence=[
                    f"impact_id={impact_id!r}",
                    f"status={status_val!r}",
                ],
            ))

    return issues


# ---------------------------------------------------------------------------
# Validacion de la lista completa de impactos
# ---------------------------------------------------------------------------

def validate_positive_impacts_with_high_gaps(
    impacts: "list[EnvironmentalImpact | dict]",
    markdown_texts: "dict[str, str] | None" = None,
) -> PositiveGapValidationResult:
    """
    Valida todos los impactos de una lista. Identifica positivos y aplica reglas.

    No modifica ningun impacto.
    """
    if not impacts:
        return PositiveGapValidationResult(
            status="SIN_DATOS",
            warnings=["No se encontraron impactos en el modelo."],
        )

    md_sources = list(markdown_texts.keys()) if markdown_texts else []

    checked: list[str] = []
    positives: list[str] = []
    positives_high_gap: list[str] = []
    all_issues: list[PositiveGapIssue] = []

    for impact in impacts:
        impact_id = str(_get_field(impact, "impact_id", "") or "")
        if impact_id:
            checked.append(impact_id)

        if not impact_is_positive(impact):
            continue

        if impact_id:
            positives.append(impact_id)

        if impact_has_high_gap(impact):
            if impact_id:
                positives_high_gap.append(impact_id)

        issues = validate_positive_impact_gap(impact, markdown_texts)
        all_issues.extend(issues)

    if not positives:
        # Sin impactos positivos: OK con nota
        return PositiveGapValidationResult(
            status="OK",
            checked_impacts=checked,
            positive_impacts=[],
            positive_impacts_with_high_gaps=[],
            markdown_sources_checked=md_sources,
            notes=[
                "No se identificaron impactos positivos en el modelo. "
                "Verificar que los impactos positivos de empleo, socioeconomia "
                "o reutilizacion de residuos han sido incluidos si procede."
            ],
        )

    errors = sum(1 for i in all_issues if i.severity == "ERROR")
    warnings_count = sum(1 for i in all_issues if i.severity == "WARNING")

    if errors > 0:
        status = "NO_CONFORME"
    elif warnings_count > 0:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    notes: list[str] = []
    if not positives_high_gap:
        notes.append(
            "No se detectaron impactos positivos con gap ALTA. "
            "Si existen impactos positivos con datos estimados o no acreditados, "
            "verificar que su status esta correctamente asignado."
        )

    return PositiveGapValidationResult(
        status=status,
        checked_impacts=checked,
        positive_impacts=positives,
        positive_impacts_with_high_gaps=positives_high_gap,
        markdown_sources_checked=md_sources,
        issues=all_issues,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Carga desde JSON
# ---------------------------------------------------------------------------

def load_phase6_model_impacts_from_json(path: "str | Path") -> list[dict]:
    """
    Carga la lista de impactos desde un archivo JSON de Phase6Model.

    Devuelve lista vacia si el archivo no existe, no es JSON valido,
    o no contiene la clave 'impacts'.
    """
    try:
        with open(Path(path), encoding="utf-8") as fh:
            data = json.load(fh)
        impacts = data.get("impacts", [])
        return list(impacts) if impacts else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def load_relevant_markdowns(expediente_path: "str | Path") -> dict[str, str]:
    """
    Lee los Markdowns relevantes del expediente para la auditoria de impactos positivos.

    Lee:
    - documento/documento_ambiental_borrador.md
    - auditoria/final_audit_result.md
    - impactos/*.md (todos)
    - bloques/*.md (todos)

    No lee docs/ del proyecto ni prompts/.
    Omite archivos que no existen o no son legibles.
    """
    exp = Path(expediente_path)
    texts: dict[str, str] = {}

    # Archivos fijos
    for rel_path in _RELEVANT_MD_PATTERNS:
        full_path = exp / rel_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            texts[rel_path] = content
        except (FileNotFoundError, OSError):
            pass

    # Directorios con glob
    for subdir in ("impactos", "bloques"):
        dir_path = exp / subdir
        if not dir_path.is_dir():
            continue
        for md_file in dir_path.glob("*.md"):
            rel = str(md_file.relative_to(exp)).replace("\\", "/")
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                texts[rel] = content
            except OSError:
                pass

    return texts


# ---------------------------------------------------------------------------
# Funcion principal desde archivos del expediente
# ---------------------------------------------------------------------------

def validate_positive_gap_from_files(
    expediente_path: "str | Path",
) -> PositiveGapValidationResult:
    """
    Busca el modelo de Fase 6 en el expediente, carga markdowns relevantes
    y valida los impactos positivos con gaps ALTA.

    Orden de busqueda del modelo:
      1. impactos/phase6_model_with_pva.json
      2. impactos/phase6_model_with_measures.json
      3. impactos/phase6_model_with_conesa.json
      4. impactos/phase6_model_with_impacts.json

    Si no hay modelo: devuelve SIN_DATOS con warning.
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
        return PositiveGapValidationResult(
            status="SIN_DATOS",
            warnings=[
                "No se encontro ningun modelo de Fase 6 en el expediente. "
                "Ejecute primero: phase6-generate-pva, phase6-generate-measures o "
                "phase6-assign-conesa."
            ],
        )

    impacts = load_phase6_model_impacts_from_json(model_path)
    if not impacts:
        return PositiveGapValidationResult(
            status="SIN_DATOS",
            warnings=[
                f"El modelo {model_path.name} no contiene impactos o no pudo cargarse."
            ],
        )

    markdown_texts = load_relevant_markdowns(exp)

    result = validate_positive_impacts_with_high_gaps(impacts, markdown_texts)
    result.notes.insert(0, f"Modelo cargado desde: {model_path.name}")
    return result


# ---------------------------------------------------------------------------
# Generacion de informe Markdown
# ---------------------------------------------------------------------------

def build_positive_gap_report_markdown(result: PositiveGapValidationResult) -> str:
    """Genera el informe Markdown de la auditoria de impactos positivos con gaps ALTA."""
    lines: list[str] = []

    lines.append("# Auditoria de impactos positivos con gaps ALTA\n")
    lines.append(f"**Estado:** `{result.status}`  ")
    lines.append(
        f"**Errores:** {result.error_count()} | "
        f"**Advertencias:** {result.warning_count()} | "
        f"**Infos:** {result.info_count()}\n"
    )

    # 1. Resumen
    lines.append("## 1. Resumen\n")
    lines.append(f"- Impactos revisados: **{len(result.checked_impacts)}**")
    lines.append(f"- Impactos positivos identificados: **{len(result.positive_impacts)}**")
    lines.append(
        f"- Impactos positivos con gap ALTA: **{len(result.positive_impacts_with_high_gaps)}**"
    )
    lines.append(f"- Markdowns revisados: **{len(result.markdown_sources_checked)}**\n")

    # 2. Impactos positivos revisados
    lines.append("## 2. Impactos positivos revisados\n")
    if result.positive_impacts:
        for imp_id in result.positive_impacts:
            has_hg = imp_id in result.positive_impacts_with_high_gaps
            tag = " _(con gap ALTA)_" if has_hg else ""
            lines.append(f"- `{imp_id}`{tag}")
    else:
        lines.append("_No se identificaron impactos positivos en el modelo._")
    lines.append("")

    # 3. Impactos positivos con gap ALTA
    lines.append("## 3. Impactos positivos con gap ALTA\n")
    if result.positive_impacts_with_high_gaps:
        for imp_id in result.positive_impacts_with_high_gaps:
            lines.append(f"- `{imp_id}`")
    else:
        lines.append(
            "_No se detectaron impactos positivos con gap de criticidad ALTA "
            "en el modelo analizado._"
        )
    lines.append("")

    # 4. Incidencias
    lines.append("## 4. Incidencias\n")
    if result.issues:
        for issue in result.issues:
            icon = "**ERROR**" if issue.severity == "ERROR" else "Advertencia"
            lines.append(f"### [{issue.severity}] {issue.code}\n")
            if issue.impact_id:
                lines.append(f"**Impacto:** `{issue.impact_id}`  ")
            lines.append(f"**Descripcion:** {issue.message}  ")
            lines.append(f"**Recomendacion:** {issue.recommendation}\n")
    else:
        lines.append("_Sin incidencias detectadas._\n")

    # 5. Recomendaciones
    lines.append("## 5. Recomendaciones\n")
    lines.append(
        "- Verificar que los impactos positivos con gap ALTA incluyen en `notes`:"
    )
    lines.append(
        "  _\"Impacto positivo condicionado a la confirmacion de los datos "
        "aportados por el promotor. No puede utilizarse para compensar "
        "impactos negativos.\"_"
    )
    lines.append(
        "- Comprobar que la nota de incertidumbre aparece tambien en el "
        "Bloque C (seccion C.5) del Documento Ambiental."
    )
    lines.append(
        "- No usar impactos positivos con gap ALTA en el resumen no tecnico "
        "(Bloque J) como argumento compensatorio.\n"
    )

    if result.notes:
        lines.append("**Notas del proceso:**\n")
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")

    if result.warnings:
        lines.append("**Avisos del proceso:**\n")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # 6. Advertencia de alcance
    lines.append("## 6. Advertencia de alcance\n")
    lines.append(
        "> Esta auditoria no elimina incertidumbres ni convierte impactos positivos en "
        "compensaciones. Solo verifica que las incertidumbres relevantes permanezcan "
        "visibles.\n"
    )
    lines.append(
        "> `administrative_ready = False` — Esta auditoria no declara el expediente "
        "apto para presentacion administrativa.\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_positive_gap_outputs(
    result: PositiveGapValidationResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """
    Escribe positive_gap_result.json y positive_gap_result.md en output_dir.

    Devuelve (json_path, md_path).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "positive_gap_result.json"
    md_path = out / "positive_gap_result.md"

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

    md_content = build_positive_gap_report_markdown(result)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
