"""
prl_measure_validator -- RD-09
Validador deterministico: medidas PRL separadas de medidas ambientales EIA.

Regla canonica (RD-09 / AG09-14 / D-10):
  Las medidas de Prevención de Riesgos Laborales (PRL) son obligatorias en el
  ámbito laboral, pero no computan como medidas ambientales reductoras de
  significancia en el sentido de la evaluacion de impacto ambiental (EIA).
  Deben declararse en sección propia con measure_type='PRL_NO_EIA' y
  status='NO_EIA', sin aparecer en la tabla impacto-medida EIA como reductoras.

Diferencia clave:
  - Medida EIA: reduce o compensa una presion ambiental sobre un factor receptor.
  - Medida PRL: protege al trabajador. No reduce emisiones, ruido exterior,
    polvo, vertidos ni afección ecológica.

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

PRL_VALIDATION_STATUS: list[str] = [
    "OK",
    "CON_OBSERVACIONES",
    "NO_CONFORME",
    "SIN_DATOS",
]

PRL_VALIDATION_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

PRL_KEYWORDS: list[str] = [
    "epi",
    "epis",
    "equipo de proteccion individual",
    "equipos de proteccion individual",
    "proteccion auditiva",
    "casco",
    "guantes",
    "gafas",
    "mascarilla",
    "botas",
    "arnes",
    "formacion prl",
    "prevencion de riesgos laborales",
    "seguridad laboral",
    "senalizacion de seguridad",
    "plan de seguridad",
    "vigilancia de la salud",
    "reconocimiento medico",
    "trabajador",
    "trabajadores",
]

ENVIRONMENTAL_REDUCTION_KEYWORDS: list[str] = [
    "reduce emisiones",
    "reduce ruido exterior",
    "reduce significancia",
    "reduce impacto ambiental",
    "reduce el impacto ambiental",
    "corrige impacto",
    "mitiga impacto",
    "evita afeccion ambiental",
    "reduce polvo exterior",
    "reduce vertidos",
    "reduce afeccion",
    "medida correctora ambiental",
    "medida preventiva ambiental",
    "medida protectora ambiental",
]

# Keywords de PRL que, solos, son señal fuerte (no requieren contexto adicional)
_STRONG_PRL_KEYWORDS: tuple[str, ...] = (
    "epi",
    "epis",
    "equipo de proteccion individual",
    "equipos de proteccion individual",
    "proteccion auditiva",
    "casco",
    "arnes",
    "formacion prl",
    "prevencion de riesgos laborales",
    "seguridad laboral",
    "plan de seguridad",
    "vigilancia de la salud",
    "reconocimiento medico",
)

# Marcadores de separacion PRL explicita en markdown (safe zones)
_SAFE_PRL_SECTION_MARKERS: tuple[str, ...] = (
    "prl no eia",
    "prl_no_eia",
    "no computable",
    "no computables",
    "no son medidas eia",
    "no computan",
    "no reduce significancia",
    "no reducen significancia",
    "no reduce impacto ambiental",
    "medidas prl",
    "no eia",
)

# Contexto de tabla EIA de medidas (activa el WARNING en markdown)
_EIA_MEASURES_CONTEXT_MARKERS: tuple[str, ...] = (
    "medida correctora",
    "medidas correctoras",
    "medida preventiva",
    "medidas preventivas",
    "medida protectora",
    "medidas protectoras",
    "tabla de medidas",
    "impacto medida",
    "impacto-medida",
    "reduccion de la significancia",
    "reduce significancia",
    "correctoras ambientales",
    "preventivas ambientales",
)

# Palabras de negacion (suprimen deteccion de ENVIRONMENTAL_REDUCTION_KEYWORDS)
_NEGATION_WORDS: frozenset[str] = frozenset({
    "no", "sin", "nunca", "jamas", "ni", "tampoco",
})

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

_MD_SCAN_DIRS: tuple[str, ...] = ("impactos", "bloques", "auditoria")


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


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PRLMeasureIssue:
    """Incidencia detectada en la validacion de separacion EIA/PRL."""

    severity: str           # ERROR / WARNING / INFO
    code: str               # RD09-E001, RD09-W001, RD09-MD-E001 ...
    measure_id: Optional[str]
    impact_id: Optional[str]
    source: str             # "model" | ruta del fichero markdown
    message: str
    recommendation: str = ""
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.severity not in PRL_VALIDATION_SEVERITY:
            raise ValueError(f"severity invalido: {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "measure_id": self.measure_id,
            "impact_id": self.impact_id,
            "source": self.source,
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
class PRLMeasureValidationResult:
    """Resultado completo de la validacion de separacion EIA/PRL."""

    status: str                          # OK / CON_OBSERVACIONES / NO_CONFORME / SIN_DATOS
    checked_measures: list[str] = field(default_factory=list)
    prl_measures: list[str] = field(default_factory=list)
    problematic_measures: list[str] = field(default_factory=list)
    issues: list[PRLMeasureIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

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
            "prl_measures": list(self.prl_measures),
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
            f"RD-09 [{self.status}] "
            f"{len(self.checked_measures)} revisadas, "
            f"{len(self.prl_measures)} PRL, "
            f"{self.error_count()} errores, "
            f"{self.warning_count()} advertencias"
        )


# ---------------------------------------------------------------------------
# Funciones de deteccion
# ---------------------------------------------------------------------------


def is_prl_measure(measure: MitigationMeasure) -> bool:
    """True si la medida es PRL por flag, tipo, status o palabras clave."""
    if measure.is_prl_only:
        return True
    if measure.measure_type == "PRL_NO_EIA":
        return True
    if measure.status == "NO_EIA":
        return True
    combined = _norm(
        f"{measure.name} {measure.description} {' '.join(measure.notes)}"
    )
    seen: set[str] = set()
    for kw in PRL_KEYWORDS:
        nkw = _norm(kw)
        if nkw not in seen:
            seen.add(nkw)
            if nkw in combined:
                return True
    return False


def measure_is_presented_as_environmental_reduction(
    measure: MitigationMeasure,
) -> bool:
    """True si la medida PRL se presenta como reduccion ambiental EIA.

    Las frases precedidas por negacion ("no reduce", "sin reduccion",
    "no debe computarse") no se cuentan como infraccion.
    """
    combined = _norm(
        f"{measure.name} {measure.description} "
        f"{' '.join(measure.notes)} {' '.join(measure.warnings)}"
    )
    for kw in ENVIRONMENTAL_REDUCTION_KEYWORDS:
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
# validate_prl_measure
# ---------------------------------------------------------------------------


def validate_prl_measure(
    measure: MitigationMeasure,
    related_impacts: Optional[list[EnvironmentalImpact]] = None,
) -> list[PRLMeasureIssue]:
    """Valida una medida PRL en aislamiento o con sus impactos vinculados.

    Reglas:
    - RD09-E001: medida PRL con measure_type distinto de PRL_NO_EIA.
    - RD09-E002: medida PRL afirma reduccion ambiental EIA.
    - RD09-W001: medida PRL vinculada a impactos con status != NO_EIA.
    """
    issues: list[PRLMeasureIssue] = []

    # Regla 1 (E001): tipo incorrecto
    if measure.measure_type != "PRL_NO_EIA":
        issues.append(PRLMeasureIssue(
            severity="ERROR",
            code="RD09-E001",
            measure_id=measure.measure_id,
            impact_id=None,
            source="model",
            message=(
                f"La medida PRL '{_ascii_safe(measure.name)}' ({measure.measure_id}) "
                f"tiene measure_type={measure.measure_type!r} en lugar de 'PRL_NO_EIA'. "
                f"Las medidas PRL deben declararse con measure_type='PRL_NO_EIA' "
                f"para que no se computen como medidas ambientales EIA."
            ),
            recommendation=(
                f"Cambiar measure_type a 'PRL_NO_EIA' en {measure.measure_id}. "
                f"Si la medida tiene funcion ambiental real (no solo laboral), "
                f"crear una medida separada con el tipo ambiental correspondiente."
            ),
            evidence=[
                f"measure_type={measure.measure_type!r}",
                f"expected='PRL_NO_EIA'",
            ],
        ))

    # Regla 2 (E002): afirma reduccion ambiental
    if measure_is_presented_as_environmental_reduction(measure):
        combined = _norm(
            f"{measure.name} {measure.description} "
            f"{' '.join(measure.notes)} {' '.join(measure.warnings)}"
        )
        evidence = [kw for kw in ENVIRONMENTAL_REDUCTION_KEYWORDS if _norm(kw) in combined]
        issues.append(PRLMeasureIssue(
            severity="ERROR",
            code="RD09-E002",
            measure_id=measure.measure_id,
            impact_id=None,
            source="model",
            message=(
                f"La medida PRL '{_ascii_safe(measure.name)}' ({measure.measure_id}) "
                f"contiene lenguaje de reduccion ambiental EIA. "
                f"Las medidas PRL no reducen emisiones, ruido exterior, polvo, "
                f"vertidos ni afeccion ecologica."
            ),
            recommendation=(
                "Eliminar el lenguaje de reduccion ambiental del texto de la medida PRL. "
                "Si existe una medida correctora ambiental real, declararla por separado "
                "con measure_type distinto de PRL_NO_EIA."
            ),
            evidence=evidence or ["Termino de reduccion ambiental detectado"],
        ))

    # Regla 3 (W001): vinculada a impactos sin status NO_EIA
    if related_impacts and measure.status != "NO_EIA":
        issues.append(PRLMeasureIssue(
            severity="WARNING",
            code="RD09-W001",
            measure_id=measure.measure_id,
            impact_id=None,
            source="model",
            message=(
                f"La medida PRL '{_ascii_safe(measure.name)}' ({measure.measure_id}) "
                f"esta vinculada a {len(related_impacts)} impacto(s) ambiental(es) "
                f"pero tiene status={measure.status!r} en lugar de 'NO_EIA'. "
                f"Para que quede claro que no computa como medida EIA, "
                f"su status debe ser 'NO_EIA'."
            ),
            recommendation=(
                f"Cambiar el status de {measure.measure_id} a 'NO_EIA'. "
                f"Anadir una nota que aclare que es PRL y no reduce "
                f"la significancia ambiental del impacto."
            ),
            evidence=[
                f"status={measure.status!r}",
                f"vinculada a: {', '.join(i.impact_id for i in related_impacts)}",
            ],
        ))

    return issues


# ---------------------------------------------------------------------------
# validate_prl_measures_in_model
# ---------------------------------------------------------------------------


def validate_prl_measures_in_model(
    model: Phase6Model,
) -> PRLMeasureValidationResult:
    """Valida todas las medidas del modelo, detectando uso indebido de PRL.

    No muta model ni ningun objeto de entrada.
    """
    if not model.measures:
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=["El modelo no contiene medidas. No hay nada que validar."],
        )

    impact_index: dict[str, EnvironmentalImpact] = {
        imp.impact_id: imp for imp in model.impacts
    }

    # Por cada impacto: lista de measure_ids NO PRL vinculados
    non_prl_by_impact: dict[str, list[str]] = {}
    for m in model.measures:
        if not is_prl_measure(m):
            for tid in m.target_impact_ids:
                non_prl_by_impact.setdefault(tid, []).append(m.measure_id)

    all_issues: list[PRLMeasureIssue] = []
    checked_measures: list[str] = []
    prl_measures: list[str] = []
    problematic_set: set[str] = set()

    for m in model.measures:
        checked_measures.append(m.measure_id)
        if not is_prl_measure(m):
            continue
        prl_measures.append(m.measure_id)

        related_impacts = [
            impact_index[tid]
            for tid in m.target_impact_ids
            if tid in impact_index
        ]
        measure_issues = validate_prl_measure(m, related_impacts)

        # E003: PRL es la UNICA medida de un impacto de alta significancia
        for imp_id in m.target_impact_ids:
            imp = impact_index.get(imp_id)
            if imp is None:
                continue
            if imp.significance_without_measures in _HIGH_NEGATIVE_SIGNIFICANCES:
                if not non_prl_by_impact.get(imp_id):
                    measure_issues.append(PRLMeasureIssue(
                        severity="ERROR",
                        code="RD09-E003",
                        measure_id=m.measure_id,
                        impact_id=imp_id,
                        source="model",
                        message=(
                            f"La medida PRL '{_ascii_safe(m.name)}' ({m.measure_id}) "
                            f"es la UNICA medida vinculada al impacto {imp_id} "
                            f"(significancia {imp.significance_without_measures}). "
                            f"Las medidas PRL no reducen la significancia ambiental; "
                            f"este impacto necesita medidas correctoras o preventivas EIA."
                        ),
                        recommendation=(
                            f"Anadir medidas ambientales reales (correctoras/preventivas) "
                            f"para el impacto {imp_id}. La medida PRL puede mantenerse "
                            f"como PRL_NO_EIA pero no como unica respuesta a un impacto "
                            f"de alta significancia."
                        ),
                        evidence=[
                            f"significance_without_measures={imp.significance_without_measures!r}",
                            f"no hay medidas no-PRL para {imp_id}",
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

    return PRLMeasureValidationResult(
        status=status,
        checked_measures=checked_measures,
        prl_measures=prl_measures,
        problematic_measures=sorted(problematic_set),
        issues=all_issues,
    )


# ---------------------------------------------------------------------------
# Deserializador interno de Phase6Model
# ---------------------------------------------------------------------------


def _phase6_model_from_dict(data: dict, exp_id: str) -> Phase6Model:
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
# validate_prl_measures_from_json / _from_files
# ---------------------------------------------------------------------------


def validate_prl_measures_from_json(
    path: "str | Path",
) -> PRLMeasureValidationResult:
    """Carga un Phase6Model desde JSON y valida medidas PRL."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"Archivo no encontrado: {p}"],
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"JSON invalido en {p.name}: {exc}"],
        )

    try:
        model = _phase6_model_from_dict(data, p.stem)
    except (KeyError, TypeError, ValueError) as exc:
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=[f"Error deserializando {p.name}: {exc}"],
        )

    return validate_prl_measures_in_model(model)


def validate_prl_measures_from_files(
    expediente_path: "str | Path",
) -> PRLMeasureValidationResult:
    """Busca el modelo de impactos y valida medidas PRL.

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
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=extra_warnings + [
                "No se encontro ningun modelo de impactos/medidas en impactos/. "
                "Ejecutar primero phase6-generate-measures."
            ],
        )

    result = validate_prl_measures_in_model(model)
    result.warnings.extend(extra_warnings)
    return result


# ---------------------------------------------------------------------------
# validate_prl_markdown
# ---------------------------------------------------------------------------


def validate_prl_markdown(
    markdown: str,
    source: str = "markdown",
) -> PRLMeasureValidationResult:
    """Detecta medidas PRL mezcladas en secciones de medidas EIA en markdown.

    Uso tipico: pasar el contenido de bloques/bloque_D_medidas.md.

    Detecta:
    - EPI/PRL en tabla de medidas EIA con lenguaje de reduccion ambiental -> ERROR.
    - EPI/PRL en contexto de medidas correctoras/preventivas EIA -> WARNING.

    No detecta como infraccion:
    - Secciones explicitamente marcadas como PRL_NO_EIA o "medidas PRL".
    - Frases con marcadores seguros como "no computable", "no eia", etc.
    """
    issues: list[PRLMeasureIssue] = []
    norm_md = _norm(markdown)

    # Keywords fuertes para deteccion en markdown (evita falsos positivos)
    seen_kws: set[str] = set()
    strong_prl_nkws: list[str] = []
    for kw in _STRONG_PRL_KEYWORDS:
        nkw = _norm(kw)
        if nkw not in seen_kws:
            seen_kws.add(nkw)
            strong_prl_nkws.append(nkw)

    # Normalized environmental reduction keywords
    env_nkws = [_norm(kw) for kw in ENVIRONMENTAL_REDUCTION_KEYWORDS]

    # Normalized EIA context markers
    eia_nkws = [_norm(mk) for mk in _EIA_MEASURES_CONTEXT_MARKERS]

    # Normalized safe markers
    safe_nkws = [_norm(sm) for sm in _SAFE_PRL_SECTION_MARKERS]

    # Track seen (code, prl_kw) to avoid duplicate issues
    seen_issues: set[tuple[str, str]] = set()

    for nkw in strong_prl_nkws:
        start = 0
        while True:
            pos = norm_md.find(nkw, start)
            if pos == -1:
                break
            start = pos + 1

            # Context window ±300 chars
            context = norm_md[max(0, pos - 300):pos + 300]

            # Check safe context — if safe markers present, skip
            if any(sm in context for sm in safe_nkws):
                continue

            # Check environmental reduction
            env_found = [kw for kw, nk in zip(ENVIRONMENTAL_REDUCTION_KEYWORDS, env_nkws) if nk in context]
            eia_context = any(mk in context for mk in eia_nkws)

            if env_found:
                key = ("RD09-MD-E001", nkw)
                if key not in seen_issues:
                    seen_issues.add(key)
                    issues.append(PRLMeasureIssue(
                        severity="ERROR",
                        code="RD09-MD-E001",
                        measure_id=None,
                        impact_id=None,
                        source=source,
                        message=(
                            f"Medida PRL ('{nkw}') detectada en contexto de reduccion "
                            f"ambiental EIA en '{source}'. "
                            f"Las medidas PRL no reducen la significancia ambiental exterior."
                        ),
                        recommendation=(
                            "Separar la medida PRL en una seccion propia marcada como "
                            "'PRL_NO_EIA' o 'Medidas PRL no computables como medidas EIA'. "
                            "No incluir EPIs ni medidas de seguridad laboral en la tabla "
                            "de medidas correctoras/preventivas ambientales."
                        ),
                        evidence=[f"prl_keyword='{nkw}'"] + env_found[:3],
                    ))
            elif eia_context:
                key = ("RD09-MD-W001", nkw)
                if key not in seen_issues:
                    seen_issues.add(key)
                    issues.append(PRLMeasureIssue(
                        severity="WARNING",
                        code="RD09-MD-W001",
                        measure_id=None,
                        impact_id=None,
                        source=source,
                        message=(
                            f"Medida PRL ('{nkw}') detectada en contexto de medidas "
                            f"EIA en '{source}' sin separacion clara. "
                            f"Verificar que no se incluye como medida correctora/preventiva ambiental."
                        ),
                        recommendation=(
                            "Incluir un encabezado claro de separacion PRL/EIA. "
                            "Usar 'Medidas PRL (PRL_NO_EIA) — no computan como medidas ambientales' "
                            "o equivalente."
                        ),
                        evidence=[f"prl_keyword='{nkw}'", "contexto de medidas EIA detectado"],
                    ))

    has_error = any(i.severity == "ERROR" for i in issues)
    has_warning = any(i.severity == "WARNING" for i in issues)

    if not issues:
        status = "OK"
    elif has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    return PRLMeasureValidationResult(
        status=status,
        checked_measures=[],
        prl_measures=[],
        problematic_measures=[],
        issues=issues,
    )


# ---------------------------------------------------------------------------
# validate_prl_measures_markdowns_from_files
# ---------------------------------------------------------------------------


def validate_prl_measures_markdowns_from_files(
    expediente_path: "str | Path",
) -> PRLMeasureValidationResult:
    """Escanea markdowns del expediente y detecta PRL mezclada en secciones EIA.

    Busca en: impactos/*.md, bloques/*.md, auditoria/*.md.
    No revisa docs/ del proyecto ni prompts/.
    """
    p = Path(expediente_path)
    if not p.exists():
        raise FileNotFoundError(f"Expediente no encontrado: {p}")

    all_issues: list[PRLMeasureIssue] = []
    extra_warnings: list[str] = []
    scanned: list[str] = []

    for subdir in _MD_SCAN_DIRS:
        d = p / subdir
        if not d.is_dir():
            continue
        for md_file in sorted(d.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                extra_warnings.append(f"No se pudo leer {md_file.name}: {exc}")
                continue
            scanned.append(str(md_file.relative_to(p)))
            partial = validate_prl_markdown(content, source=str(md_file.relative_to(p)))
            all_issues.extend(partial.issues)

    if not scanned:
        return PRLMeasureValidationResult(
            status="SIN_DATOS",
            warnings=extra_warnings + [
                "No se encontraron markdowns en impactos/, bloques/ ni auditoria/."
            ],
        )

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    return PRLMeasureValidationResult(
        status=status,
        issues=all_issues,
        warnings=extra_warnings,
        notes=[f"Markdowns analizados: {', '.join(scanned)}"],
    )


# ---------------------------------------------------------------------------
# _combine_results (interno)
# ---------------------------------------------------------------------------


def _combine_results(
    r1: PRLMeasureValidationResult,
    r2: PRLMeasureValidationResult,
) -> PRLMeasureValidationResult:
    """Combina dos resultados de validacion PRL."""
    all_issues = r1.issues + r2.issues
    all_warnings = list(dict.fromkeys(r1.warnings + r2.warnings))
    all_notes = list(dict.fromkeys(r1.notes + r2.notes))
    checked = list(dict.fromkeys(r1.checked_measures + r2.checked_measures))
    prl = list(dict.fromkeys(r1.prl_measures + r2.prl_measures))
    problematic = sorted(set(r1.problematic_measures) | set(r2.problematic_measures))

    both_sin_datos = r1.status == "SIN_DATOS" and r2.status == "SIN_DATOS"

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if both_sin_datos:
        status = "SIN_DATOS"
    elif has_error:
        status = "NO_CONFORME"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    return PRLMeasureValidationResult(
        status=status,
        checked_measures=checked,
        prl_measures=prl,
        problematic_measures=problematic,
        issues=all_issues,
        warnings=all_warnings,
        notes=all_notes,
    )


# ---------------------------------------------------------------------------
# build_prl_measure_report_markdown
# ---------------------------------------------------------------------------


def build_prl_measure_report_markdown(
    result: PRLMeasureValidationResult,
) -> str:
    lines: list[str] = []

    lines.append("# Auditoria separacion EIA / PRL")
    lines.append("")

    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"**Estado:** {result.status}")
    lines.append(f"**Medidas revisadas:** {len(result.checked_measures)}")
    lines.append(f"**Medidas PRL detectadas:** {len(result.prl_measures)}")
    lines.append(f"**Medidas con incidencias:** {len(result.problematic_measures)}")
    lines.append(f"**Errores:** {result.error_count()}")
    lines.append(f"**Advertencias:** {result.warning_count()}")
    lines.append(f"**Informativos:** {result.info_count()}")
    lines.append("")

    lines.append("## 2. Medidas revisadas")
    lines.append("")
    if result.checked_measures:
        for mid in result.checked_measures:
            marker = "**[PRL]**" if mid in result.prl_measures else ""
            lines.append(f"- {mid} {marker}".rstrip())
    else:
        lines.append("_No se revisaron medidas del modelo (SIN_DATOS o solo analisis markdown)._")
    lines.append("")

    lines.append("## 3. Medidas PRL detectadas")
    lines.append("")
    if result.prl_measures:
        for mid in result.prl_measures:
            prob = " _(con incidencias)_" if mid in result.problematic_measures else ""
            lines.append(f"- {mid}{prob}")
    else:
        lines.append("_No se detectaron medidas PRL en el modelo._")
    lines.append("")

    lines.append("## 4. Incidencias")
    lines.append("")
    if result.issues:
        for issue in result.issues:
            lines.append(f"### {issue.code} [{issue.severity}]")
            if issue.measure_id:
                lines.append(f"- **Medida:** {issue.measure_id}")
            if issue.impact_id:
                lines.append(f"- **Impacto:** {issue.impact_id}")
            lines.append(f"- **Fuente:** {issue.source}")
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
            "No se detectaron incidencias. Las medidas PRL estan correctamente "
            "separadas de las medidas ambientales EIA."
        )
        lines.append("")

    lines.append("## 6. Advertencia de alcance")
    lines.append("")
    lines.append(
        "Las medidas PRL pueden ser obligatorias y necesarias, pero no deben "
        "computarse como medidas ambientales reductoras de significancia EIA."
    )
    lines.append("")
    lines.append(
        "Un EPI auditivo protege al trabajador del ruido; no reduce el nivel "
        "de ruido exterior del foco emisor. Una pantalla acustica si lo reduce. "
        "Solo la pantalla computa como medida correctora ambiental."
    )
    lines.append("")
    lines.append(
        "Este validador no modifica medidas, no cambia significancias, "
        "no valora impactos y no declara aptitud administrativa del expediente."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_prl_measure_outputs
# ---------------------------------------------------------------------------


def write_prl_measure_outputs(
    result: PRLMeasureValidationResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe prl_measure_validation_result.json y .md en output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "prl_measure_validation_result.json"
    md_path = out / "prl_measure_validation_result.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        build_prl_measure_report_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
