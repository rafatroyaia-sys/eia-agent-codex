"""
prudence_validator -- AU-02
Validador de prudencia metodológica y lenguaje prohibido para EIA.

Detecta frases imprudentes, conclusiones prematuras o cierres indebidos
en textos, markdowns e inventarios del expediente.

Las frases prohibidas corresponden a las reglas del sistema:
  - Regla 4 CLAUDE.md: "Nunca afirmar 'no existe afección/flora/impacto'
    sin evidencia. Usar: 'no se detecta en las fuentes consultadas',
    'no consta prospección de campo', 'según la documentación analizada'."
  - §6 SYSTEM_BASE (anti-despreciable): prohibición de "despreciable",
    "nulo", "irrelevante", "insignificante" sin medición en modo gabinete.
  - OBS-M12-003: anti-despreciable en gabinete.
  - H-9: prohibición en Red Natura.
  - AG09-11 + C-10: efectos acumulativos no descartables sin datos.

Regla de contexto metodológico:
  Si una frase prohibida aparece dentro de texto de prohibición
  (e.g., "no debe decir 'sin afección'", "frases prohibidas: ..."),
  no se genera ERROR sino INFO. El validador detecta el contexto
  mediante una ventana de ±150 caracteres alrededor del hallazgo.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No corrige automáticamente textos.
  - No modifica el expediente.
  - No declara aptitud administrativa.
  - Función pura: no muta los objetos de inventario o Phase6Model.
  - En Fase 6 (Phase6Model), COMPATIBLE/MODERADO/SEVERO/CRITICO son
    válidos como significancias de impactos — no se marcan como ERROR.
    Solo en inventario (FactorInventory) el uso de esas palabras como
    calificativos de afección es un ERROR metodológico.

Dependencias:
  IV-00 (inventory_model — InventorySummary, FactorInventory)
  IM-00 (impact_model — Phase6Model)
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes — frases prohibidas por categoría
# ---------------------------------------------------------------------------

PROHIBITED_PHRASES_GENERAL: list[str] = [
    "sin afeccion",
    "sin impacto",
    "no hay impacto",
    "impacto inexistente",
    "afeccion inexistente",
    "se descarta",
    "descartado",
    "no existe riesgo",
    "riesgo nulo",
    "despreciable",
    "irrelevante",
    "nulo",
    "cumple limites",
    "cumple la normativa",
    "no se preven efectos",
    "no se esperan efectos",
]

PROHIBITED_IN_INVENTORY: list[str] = [
    "compatible",
    "moderado",
    "severo",
    "critico",
    "impacto significativo",
    "impacto no significativo",
    "significativo",
    "no significativo",
]

PROHIBITED_RED_NATURA: list[str] = [
    "sin afeccion apreciable",
    "sin afeccion significativa",
    "no hay red natura",
    "fuera de red natura",
    "no afecta a red natura",
    "se descarta afeccion a red natura",
]

PROHIBITED_BIODIVERSITY: list[str] = [
    "no hay flora",
    "no hay fauna",
    "sin especies protegidas",
    "sin habitats",
    "sin vegetacion",
    "sin aves",
    "sin nidificacion",
]

PROHIBITED_HERITAGE: list[str] = [
    "no hay patrimonio",
    "sin yacimientos",
    "sin afeccion patrimonial",
    "no existe patrimonio",
]

PROHIBITED_NOISE_AIR: list[str] = [
    "sin ruido",
    "sin emisiones",
    "no hay polvo",
    "cumple limites acusticos",
    "cumple objetivos acusticos",
]

PROHIBITED_HYDROLOGY: list[str] = [
    "no hay cauces",
    "sin escorrentia",
    "sin conectividad hidrica",
    "sin afeccion hidrologica",
]

PROHIBITED_CLIMATE: list[str] = [
    "emisiones despreciables",
    "carbono neutro",
    "sin emisiones",
    "riesgo climatico bajo",
    "cumple objetivos climaticos",
]

# Mapa categoría → lista de frases
_CATEGORY_MAP: dict[str, list[str]] = {
    "general": PROHIBITED_PHRASES_GENERAL,
    "inventory": PROHIBITED_IN_INVENTORY,
    "red_natura": PROHIBITED_RED_NATURA,
    "biodiversity": PROHIBITED_BIODIVERSITY,
    "heritage": PROHIBITED_HERITAGE,
    "noise_air": PROHIBITED_NOISE_AIR,
    "hydrology": PROHIBITED_HYDROLOGY,
    "climate": PROHIBITED_CLIMATE,
}

# Indicadores de contexto metodológico (no generan ERROR)
_METHODOLOGICAL_INDICATORS: tuple[str, ...] = (
    "no debe decir",
    "no debe usar",
    "prohibido",
    "frases prohibidas",
    "no usar",
    "evitar",
    "esta seccion no debe",
    "se prohibe",
    "inadecuado",
    "imprudente",
    "incorrecto",
    "lenguaje prohibido",
    "no se puede afirmar",
    "no se afirma",
    "formulacion correcta",
    "formulacion conforme",
    "patron imprudente",
    "imprudence",
    "prohibited",
)

# Factor → categorías de frases aplicables en inventario
_FACTOR_PRUDENCE_CATEGORIES: dict[str, list[str]] = {
    "FI-007": ["general", "inventory", "biodiversity"],
    "FI-008": ["general", "inventory", "biodiversity"],
    "FI-009": ["general", "inventory", "red_natura"],
    "FI-010": ["general", "inventory", "red_natura"],
    "FI-012": ["general", "inventory", "heritage"],
    "FI-006": ["general", "inventory", "noise_air"],
    "FI-014": ["general", "inventory", "noise_air"],
    "FI-004": ["general", "inventory", "hydrology"],
    "FI-005": ["general", "inventory", "hydrology"],
    "FI-016": ["general", "inventory", "hydrology"],
    "FI-015": ["general", "inventory", "climate"],
}
_DEFAULT_FACTOR_CATEGORIES: list[str] = ["general", "inventory"]
_DOCUMENT_MARKDOWN_CATEGORIES: str = (
    "general,red_natura,biodiversity,heritage,noise_air,hydrology,climate"
)

# Palabras que indican un impacto positivo está siendo usado para compensar negativos
_COMPENSATION_PHRASES: list[str] = [
    "compensa",
    "neutraliza",
    "contrapesa",
    "equilibra",
    "compensa el impacto negativo",
    "neutraliza el impacto negativo",
]

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# normalize_prudence_text
# ---------------------------------------------------------------------------

def normalize_prudence_text(text: str) -> str:
    """Normaliza texto para detección de frases prohibidas.

    - Quita tildes (NFKD → ASCII).
    - Convierte a minúsculas.
    - Normaliza espacios múltiples.
    - Elimina caracteres de control.

    No elimina puntuación para preservar contexto suficiente.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = no_accents.lower()
    # Normalizar espacios
    normalized = re.sub(r"[\r\n\t]+", " ", lowered)
    normalized = re.sub(r" {2,}", " ", normalized)
    return normalized.strip()


# ---------------------------------------------------------------------------
# PrudenceIssue
# ---------------------------------------------------------------------------

@dataclass
class PrudenceIssue:
    """Incidencia de prudencia metodológica detectada en un texto."""

    severity: str
    """ERROR / WARNING / INFO."""

    code: str
    """Código de la incidencia (ej. AU02-E001)."""

    source: str
    """Fuente del texto: 'inventario/FI-007', 'impactos/IMP-001', 'bloques/B_inventario.md'..."""

    phrase: str
    """Frase prohibida detectada (normalizada)."""

    context: str
    """Fragmento de contexto alrededor de la frase (máx. 150 chars)."""

    message: str
    """Descripción de la incidencia."""

    recommendation: str
    """Acción recomendada."""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
            "phrase": self.phrase,
            "context": self.context,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        s = (
            f"[{self.severity:7s}] {self.code} | {self.source[:40]} | "
            f"'{self.phrase[:40]}'"
        )
        return _ascii_safe(s)


# ---------------------------------------------------------------------------
# PrudenceValidationResult
# ---------------------------------------------------------------------------

@dataclass
class PrudenceValidationResult:
    """Resultado completo de la validación de prudencia."""

    issues: list[PrudenceIssue] = field(default_factory=list)
    checked_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

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
            "issues": [i.to_dict() for i in self.issues],
            "checked_sources": list(self.checked_sources),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_valid": self.is_valid(),
        }

    def summary(self) -> str:
        lines = [
            "--- AU-02 Validador de prudencia metodologica ---",
            f"Fuentes revisadas  : {len(self.checked_sources)}",
            f"Incidencias ERROR  : {self.error_count()}",
            f"Incidencias WARNING: {self.warning_count()}",
            f"Incidencias INFO   : {self.info_count()}",
            f"Resultado          : {'VALIDO (sin ERRORs)' if self.is_valid() else 'NO VALIDO (hay ERRORs)'}",
        ]
        if self.error_count() > 0:
            for iss in self.issues[:3]:
                if iss.severity == "ERROR":
                    lines.append(f"  ! {_ascii_safe(iss.source)}: '{_ascii_safe(iss.phrase)}'")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# _is_methodological_context
# ---------------------------------------------------------------------------

def _is_methodological_context(normalized_text: str, match_start: int) -> bool:
    """True si la frase aparece dentro de texto metodológico de prohibición.

    Usa una ventana de ±150 chars alrededor del match para buscar indicadores.
    """
    window_start = max(0, match_start - 150)
    window_end = min(len(normalized_text), match_start + 150)
    window = normalized_text[window_start:window_end]
    return any(ind in window for ind in _METHODOLOGICAL_INDICATORS)


# ---------------------------------------------------------------------------
# _severity_for_phrase
# ---------------------------------------------------------------------------

def _severity_for_phrase(phrase: str, category: str) -> str:
    """Determina la severidad para una frase según categoría.

    ERROR: cierres indebidos fuertes (afirmar ausencia de elementos, descartados).
    WARNING: lenguaje débil o ambiguo (despreciable, irrelevante, nulo).
    """
    warning_phrases = {
        "despreciable", "irrelevante", "nulo", "compatible",
        "moderado", "severo", "critico", "significativo",
        "no significativo", "impacto significativo", "impacto no significativo",
    }
    if phrase in warning_phrases:
        return "WARNING"
    return "ERROR"


# ---------------------------------------------------------------------------
# find_forbidden_phrases
# ---------------------------------------------------------------------------

def find_forbidden_phrases(
    text: str,
    source: str = "texto",
    category: str = "general",
) -> list[PrudenceIssue]:
    """Busca frases prohibidas en el texto según la categoría indicada.

    Categorías disponibles:
      general, inventory, red_natura, biodiversity, heritage,
      noise_air, hydrology, climate, all.

    Si category="all", aplica todas las categorías.

    Regla de contexto metodológico:
      Si la frase aparece en contexto de prohibición (e.g., "no debe decir
      'sin afección'"), genera INFO en lugar de ERROR/WARNING.

    No muta el texto de entrada.

    Returns:
        Lista de PrudenceIssue. Lista vacía si no se detectan frases.
    """
    if category == "all":
        phrases_to_check = list({
            p
            for cat_phrases in _CATEGORY_MAP.values()
            for p in cat_phrases
        })
    else:
        phrases_to_check = _CATEGORY_MAP.get(category, PROHIBITED_PHRASES_GENERAL)

    normalized = normalize_prudence_text(text)
    issues: list[PrudenceIssue] = []
    seen: set[tuple[str, int]] = set()  # (phrase, approx_position) dedup

    for phrase in phrases_to_check:
        # Buscar todas las ocurrencias
        start = 0
        while True:
            idx = normalized.find(phrase, start)
            if idx == -1:
                break

            # Deduplicar por frase + posición aproximada
            dedup_key = (phrase, idx // 50)
            if dedup_key in seen:
                start = idx + 1
                continue
            seen.add(dedup_key)

            # Contexto breve
            ctx_start = max(0, idx - 60)
            ctx_end = min(len(normalized), idx + len(phrase) + 60)
            context = "..." + normalized[ctx_start:ctx_end].strip() + "..."

            # Determinar severidad y si es contexto metodológico
            is_meta = _is_methodological_context(normalized, idx)
            if is_meta:
                severity = "INFO"
                code = "AU02-I001"
                msg = (
                    f"Frase '{phrase}' detectada en texto metodologico "
                    f"(contexto de prohibicion). No genera ERROR."
                )
                rec = (
                    "Verificar que el texto no usa la frase de forma afirmativa "
                    "en el expediente real."
                )
            else:
                severity = _severity_for_phrase(phrase, category)
                code = f"AU02-{'E' if severity == 'ERROR' else 'W'}001"
                msg = (
                    f"Frase prohibida detectada en {source}: '{phrase}'. "
                    "Uso imprudente de lenguaje en modo gabinete."
                )
                rec = (
                    "Sustituir por formulación prudente: "
                    "'no se detecta en las fuentes consultadas', "
                    "'no consta prospección de campo', "
                    "'según la documentación analizada'."
                )

            issues.append(PrudenceIssue(
                severity=severity,
                code=code,
                source=source,
                phrase=phrase,
                context=context[:200],
                message=msg,
                recommendation=rec,
            ))
            start = idx + 1

    return issues


# ---------------------------------------------------------------------------
# validate_inventory_prudence
# ---------------------------------------------------------------------------

def validate_inventory_prudence(
    summary: "InventorySummary",
) -> PrudenceValidationResult:
    """Valida prudencia metodológica en un inventario ambiental.

    Revisa:
      - description, notes, warnings de cada FactorInventory.
      - description de cada InventoryGap.
      - Aplica categorías de frases según el factor_id.
      - En inventario, COMPATIBLE/MODERADO/SEVERO/CRITICO en descripciones
        son ERROR porque son lenguaje de Fase 6, no de inventario.

    No muta el summary.
    """
    issues: list[PrudenceIssue] = []
    checked_sources: list[str] = []

    for factor in summary.factors:
        fi_id = factor.factor_id
        source_prefix = f"inventario/{fi_id}"
        categories = _FACTOR_PRUDENCE_CATEGORIES.get(fi_id, _DEFAULT_FACTOR_CATEGORIES)

        texts_to_check: list[tuple[str, str]] = []
        if factor.description:
            texts_to_check.append((factor.description, f"{source_prefix}/description"))
        for i, note in enumerate(factor.notes):
            texts_to_check.append((note, f"{source_prefix}/note[{i}]"))
        for i, warn in enumerate(factor.warnings):
            texts_to_check.append((warn, f"{source_prefix}/warning[{i}]"))
        for gap in factor.gaps:
            if gap.description:
                texts_to_check.append((gap.description, f"{source_prefix}/{gap.gap_id}"))

        for text, source in texts_to_check:
            checked_sources.append(source)
            for cat in categories:
                cat_issues = find_forbidden_phrases(text, source=source, category=cat)
                issues.extend(cat_issues)

    notes_out = [
        f"Inventario revisado: {len(summary.factors)} factor(es), "
        f"{len(checked_sources)} texto(s) analizados."
    ]

    return PrudenceValidationResult(
        issues=issues,
        checked_sources=list(set(checked_sources)),
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# validate_phase6_prudence
# ---------------------------------------------------------------------------

def validate_phase6_prudence(
    model: "Phase6Model",
) -> PrudenceValidationResult:
    """Valida prudencia metodológica en un Phase6Model.

    Revisa:
      - impacts: description, notes, warnings, data_gaps (como texto).
      - measures: description, notes, warnings.
      - pva_programs: indicator, threshold, notes, warnings.

    Nota: COMPATIBLE/MODERADO/SEVERO/CRITICO son VÁLIDOS como
    significancias de impactos (Fase 6 — campos tipados). Solo se
    detectan si aparecen en TEXTO LIBRE de descripción/notas de
    factores sensibles (Red Natura, Patrimonio, Biodiversidad) con
    status INDETERMINADO.

    También detecta:
      - PRL siendo presentada como medida correctora ambiental.
      - Impactos positivos usados para compensar negativos.

    No muta el modelo.
    """
    issues: list[PrudenceIssue] = []
    checked_sources: list[str] = []

    # ── Impactos ─────────────────────────────────────────────────────────
    sensitive_receptors: frozenset[str] = frozenset({
        "FR-007", "FR-008", "FR-009", "FR-010", "FR-012",
    })

    for imp in model.impacts:
        imp_source = f"impactos/{imp.impact_id}"
        is_sensitive = imp.receptor_id in sensitive_receptors
        is_indet = imp.status in ("INDETERMINADO", "PENDIENTE_DATOS")
        is_positive = imp.nature == "POSITIVO"

        texts: list[tuple[str, str]] = []
        if imp.description:
            texts.append((imp.description, f"{imp_source}/description"))
        for i, n in enumerate(imp.notes):
            texts.append((n, f"{imp_source}/note[{i}]"))
        for i, w in enumerate(imp.warnings):
            texts.append((w, f"{imp_source}/warning[{i}]"))
        for gap_id in imp.data_gaps:
            texts.append((gap_id, f"{imp_source}/data_gap"))

        for text, source in texts:
            checked_sources.append(source)
            # General phrases
            issues.extend(find_forbidden_phrases(text, source=source, category="general"))
            # Factor-specific for sensitive receptors
            if is_sensitive:
                for cat in ("red_natura", "biodiversity", "heritage"):
                    issues.extend(find_forbidden_phrases(text, source=source, category=cat))
                # Cierre indebido en INDETERMINADO con lenguaje de Fase 6 closure
                if is_indet:
                    norm = normalize_prudence_text(text)
                    for closure_phrase in ("compatible", "sin afeccion", "descartado"):
                        if closure_phrase in norm:
                            is_meta = _is_methodological_context(norm, norm.find(closure_phrase))
                            if not is_meta:
                                issues.append(PrudenceIssue(
                                    severity="ERROR",
                                    code="AU02-E002",
                                    source=source,
                                    phrase=closure_phrase,
                                    context=norm[:150],
                                    message=(
                                        f"Cierre indebido en impacto INDETERMINADO "
                                        f"({imp.impact_id}, receptor sensible "
                                        f"{imp.receptor_id}): '{closure_phrase}' "
                                        "sin datos de campo."
                                    ),
                                    recommendation=(
                                        "No cerrar impactos INDETERMINADO de factores "
                                        "sensibles (Red Natura, Patrimonio, Flora/Fauna) "
                                        "sin evidencia de campo verificada."
                                    ),
                                ))
            # Compensación de impactos negativos con positivos
            if is_positive:
                norm = normalize_prudence_text(text)
                for comp_phrase in _COMPENSATION_PHRASES:
                    comp_norm = normalize_prudence_text(comp_phrase)
                    if comp_norm in norm:
                        is_meta = _is_methodological_context(norm, norm.find(comp_norm))
                        if not is_meta:
                            issues.append(PrudenceIssue(
                                severity="ERROR",
                                code="AU02-E003",
                                source=source,
                                phrase=comp_phrase,
                                context=norm[:150],
                                message=(
                                    f"Impacto POSITIVO ({imp.impact_id}) presenta "
                                    f"lenguaje de compensacion: '{comp_phrase}'. "
                                    "Un impacto positivo no puede compensar ni neutralizar "
                                    "un impacto negativo (regla de no compensacion)."
                                ),
                                recommendation=(
                                    "Eliminar lenguaje de compensacion. Cada impacto se "
                                    "registra y evalua de forma independiente."
                                ),
                            ))

    # ── Medidas ───────────────────────────────────────────────────────────
    for med in model.measures:
        med_source = f"medidas/{med.measure_id}"
        texts = []
        if med.description:
            texts.append((med.description, f"{med_source}/description"))
        for i, n in enumerate(med.notes):
            texts.append((n, f"{med_source}/note[{i}]"))
        for i, w in enumerate(med.warnings):
            texts.append((w, f"{med_source}/warning[{i}]"))

        for text, source in texts:
            checked_sources.append(source)
            issues.extend(find_forbidden_phrases(text, source=source, category="general"))
            # PRL presentada como correctora ambiental
            if med.is_prl_only:
                norm = normalize_prudence_text(text)
                prl_incorrect_phrases = [
                    "reduce el impacto", "elimina el impacto",
                    "correctora ambiental", "medida ambiental",
                ]
                for p in prl_incorrect_phrases:
                    if normalize_prudence_text(p) in norm:
                        is_meta = _is_methodological_context(norm, norm.find(normalize_prudence_text(p)))
                        if not is_meta:
                            issues.append(PrudenceIssue(
                                severity="WARNING",
                                code="AU02-W002",
                                source=source,
                                phrase=p,
                                context=norm[:150],
                                message=(
                                    f"Medida PRL ({med.measure_id}) presenta lenguaje "
                                    f"de medida correctora ambiental: '{p}'. "
                                    "Las medidas PRL no reducen la significancia ambiental."
                                ),
                                recommendation=(
                                    "Clarificar que esta medida es PRL_NO_EIA y "
                                    "no reduce la significancia ambiental del impacto."
                                ),
                            ))

    # ── PVA ──────────────────────────────────────────────────────────────
    for pva in model.pva_programs:
        pva_source = f"pva/{pva.pva_id}"
        texts = []
        if pva.indicator:
            texts.append((pva.indicator, f"{pva_source}/indicator"))
        if pva.threshold:
            texts.append((pva.threshold, f"{pva_source}/threshold"))
        for i, n in enumerate(pva.notes):
            texts.append((n, f"{pva_source}/note[{i}]"))
        for i, w in enumerate(pva.warnings):
            texts.append((w, f"{pva_source}/warning[{i}]"))

        for text, source in texts:
            checked_sources.append(source)
            issues.extend(find_forbidden_phrases(text, source=source, category="general"))

    return PrudenceValidationResult(
        issues=issues,
        checked_sources=list(set(checked_sources)),
        notes=[
            f"Phase6Model revisado: {len(model.impacts)} impactos, "
            f"{len(model.measures)} medidas, {len(model.pva_programs)} PVA."
        ],
    )


# ---------------------------------------------------------------------------
# validate_markdown_prudence
# ---------------------------------------------------------------------------

def validate_markdown_prudence(
    markdown: str,
    source: str,
    category: str = "all",
) -> PrudenceValidationResult:
    """Valida prudencia metodológica en un texto markdown.

    Aplica las categorías indicadas. Si category="all", aplica todas.
    No muta el markdown.

    Returns:
        PrudenceValidationResult con los issues detectados.
    """
    issues = find_forbidden_phrases(markdown, source=source, category=category)
    return PrudenceValidationResult(
        issues=issues,
        checked_sources=[source],
        notes=[f"Markdown '{source}' revisado con categoria '{category}'."],
    )


def _category_for_markdown_source(rel_source: str) -> str:
    """Selecciona categorias segun la naturaleza documental de la fuente."""
    normalized = rel_source.replace("\\", "/").lower()
    if normalized.startswith("inventario/"):
        return "all"
    return _DOCUMENT_MARKDOWN_CATEGORIES


# ---------------------------------------------------------------------------
# validate_prudence_from_files
# ---------------------------------------------------------------------------

def validate_prudence_from_files(
    expediente_path: "str | Path",
) -> PrudenceValidationResult:
    """Valida prudencia revisando markdowns del expediente.

    Busca textos en:
      - inventario/*.md
      - impactos/*.md
      - bloques/*.md (si existe)
      - no revisa auditoria/*.md generados

    No revisa:
      - docs/ del proyecto (para evitar falsos positivos de documentación)
      - prompts/
      - control_interno/ (interno, no destinado al DA)
      - auditoria/ (informes generados que citan incidencias)
      - src/ ni tests/

    Si no se encuentran archivos: devuelve WARNING, no excepción.
    Si el directorio no existe: lanza FileNotFoundError.

    Args:
        expediente_path: Ruta al directorio del expediente EIA.

    Raises:
        FileNotFoundError: si el directorio del expediente no existe.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(f"Directorio de expediente no encontrado: {exp_path}")

    search_dirs = [
        exp_path / "inventario",
        exp_path / "impactos",
        exp_path / "bloques",
    ]

    all_issues: list[PrudenceIssue] = []
    all_sources: list[str] = []
    warnings_out: list[str] = []
    notes_out: list[str] = []

    found_any = False
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for md_path in sorted(search_dir.glob("*.md")):
            try:
                text = md_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                warnings_out.append(f"No se pudo leer: {md_path}")
                continue

            rel_source = str(md_path.relative_to(exp_path))
            category = _category_for_markdown_source(rel_source)
            result = validate_markdown_prudence(text, source=rel_source, category=category)
            all_issues.extend(result.issues)
            all_sources.append(rel_source)
            found_any = True

    if not found_any:
        warnings_out.append(
            f"No se encontraron archivos markdown en el expediente {exp_path.name}. "
            "Ejecute las fases previas para generar los outputs antes de validar prudencia."
        )

    notes_out.append(
        f"Revisados {len(all_sources)} archivo(s) markdown en el expediente."
    )

    return PrudenceValidationResult(
        issues=all_issues,
        checked_sources=all_sources,
        warnings=warnings_out,
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# build_prudence_report_markdown
# ---------------------------------------------------------------------------

def build_prudence_report_markdown(result: PrudenceValidationResult) -> str:
    """Genera el informe de validación de prudencia en markdown."""
    lines: list[str] = []

    lines.append("# Auditoria de prudencia metodologica — AU-02")
    lines.append("")

    # ── 1. Resumen ──
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"| Categoría | Cantidad |")
    lines.append(f"|-----------|---------|")
    lines.append(f"| Fuentes revisadas | {len(result.checked_sources)} |")
    lines.append(f"| ERRORs | {result.error_count()} |")
    lines.append(f"| WARNINGs | {result.warning_count()} |")
    lines.append(f"| INFOs | {result.info_count()} |")
    lines.append(
        f"| **Resultado** | **{'VALIDO' if result.is_valid() else 'NO VALIDO'}** |"
    )
    lines.append("")

    # ── 2. Fuentes revisadas ──
    lines.append("## 2. Fuentes revisadas")
    lines.append("")
    if result.checked_sources:
        for src in sorted(set(result.checked_sources))[:20]:
            lines.append(f"- {src}")
        if len(result.checked_sources) > 20:
            lines.append(f"- ... y {len(result.checked_sources) - 20} más")
    else:
        lines.append("_Ninguna fuente revisada._")
    lines.append("")

    # ── 3. Incidencias ERROR ──
    lines.append("## 3. Incidencias ERROR")
    lines.append("")
    errors = [i for i in result.issues if i.severity == "ERROR"]
    if errors:
        for iss in errors:
            lines.append(f"**[{iss.code}]** `{iss.source}`")
            lines.append(f"  - Frase: `{iss.phrase}`")
            lines.append(f"  - Contexto: _{iss.context[:120]}_")
            lines.append(f"  - Mensaje: {iss.message}")
            lines.append(f"  > Recomendación: {iss.recommendation}")
            lines.append("")
    else:
        lines.append("_Sin incidencias ERROR._")
        lines.append("")

    # ── 4. Incidencias WARNING ──
    lines.append("## 4. Incidencias WARNING")
    lines.append("")
    warnings_iss = [i for i in result.issues if i.severity == "WARNING"]
    if warnings_iss:
        for iss in warnings_iss:
            lines.append(f"**[{iss.code}]** `{iss.source}` — `{iss.phrase}`")
            lines.append(f"  > {iss.recommendation}")
            lines.append("")
    else:
        lines.append("_Sin incidencias WARNING._")
        lines.append("")

    # ── 5. Incidencias INFO ──
    lines.append("## 5. Incidencias INFO")
    lines.append("")
    infos = [i for i in result.issues if i.severity == "INFO"]
    if infos:
        for iss in infos[:10]:
            lines.append(f"[{iss.code}] `{iss.source}` — `{iss.phrase}` (contexto metodologico)")
        if len(infos) > 10:
            lines.append(f"... y {len(infos) - 10} incidencias INFO adicionales.")
    else:
        lines.append("_Sin incidencias INFO._")
    lines.append("")

    # ── 6. Recomendaciones ──
    lines.append("## 6. Recomendaciones")
    lines.append("")
    lines.append(
        "Las frases detectadas deben sustituirse por formulaciones prudentes "
        "conforme a la Regla 4 del sistema:"
    )
    lines.append("")
    lines.append("| En lugar de | Usar |")
    lines.append("|-------------|------|")
    lines.append("| 'sin afección' | 'no se detecta afección en las fuentes consultadas' |")
    lines.append("| 'despreciable' | 'de baja relevancia, sin prospección de campo que lo confirme' |")
    lines.append("| 'no hay flora/fauna' | 'no consta prospección de campo de flora/fauna' |")
    lines.append("| 'se descarta' | 'no se dispone de datos suficientes para descartar' |")
    lines.append("| 'cumple límites' | 'según la documentación disponible, cumple X' |")
    lines.append("")

    # ── 7. Advertencia de alcance ──
    lines.append("## 7. Advertencia de alcance")
    lines.append("")
    lines.append(
        "> **Esta auditoría no corrige automáticamente el expediente y no declara "
        "aptitud administrativa. Es una verificación de lenguaje que apoya la "
        "revisión técnica, pero no la sustituye.**"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_prudence_validation_outputs
# ---------------------------------------------------------------------------

def write_prudence_validation_outputs(
    result: PrudenceValidationResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs de la validación de prudencia.

    Escribe:
      - {output_dir}/prudence_validation_result.json
      - {output_dir}/prudence_validation_result.md

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "prudence_validation_result.json"
    md_path = output_dir / "prudence_validation_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_prudence_report_markdown(result))

    return json_path, md_path
