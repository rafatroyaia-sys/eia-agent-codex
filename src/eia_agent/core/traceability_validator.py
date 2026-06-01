"""
traceability_validator -- AU-03
Validador de trazabilidad HC ↔ DA para EIA.

Comprueba que las afirmaciones técnicas contenidas en los textos del
Documento Ambiental (bloques markdown, fichas de inventario, tablas de
impactos) están respaldadas por referencias cargables desde las capas de
datos del expediente (hechos confirmados, inventario, impactos, medidas,
PVA, cartografía, normativa).

Estados de trazabilidad:
  TRAZADO   — La afirmación contiene un ID explícito que existe en las
               referencias cargadas, o bien hay coincidencia textual fuerte.
  PARCIAL   — La afirmación hace referencia a un tema ambiental identificable
               (flora, ruido, Red Natura…) pero sin ID explícito verificado.
  NO_TRAZADO — La afirmación es técnicamente concreta pero no se puede
               vincular a ninguna referencia ni tema conocido.
  NO_APLICA — La afirmación es puramente metodológica, un título genérico
               o una advertencia de alcance.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No corrige automáticamente textos.
  - No modifica el expediente.
  - No declara aptitud administrativa.
  - Función pura: no muta las referencias ni los modelos de entrada.

Dependencias: ninguna de otros módulos propios (stand-alone).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TRACEABILITY_STATUS: list[str] = [
    "TRAZADO",
    "PARCIAL",
    "NO_TRAZADO",
    "NO_APLICA",
]

TRACEABILITY_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

SOURCE_TYPES: list[str] = [
    "HECHO_CONFIRMADO",
    "INVENTARIO",
    "IMPACTO",
    "MEDIDA",
    "PVA",
    "GAP",
    "CARTOGRAFIA",
    "CLIMA",
    "NORMATIVA",
    "TEXTO",
]

# Patrón para detectar IDs explícitos del sistema EIA en textos
_ID_PATTERN = re.compile(
    r'\b(HC|GAP|FI|FR|IMP|MED|PVA|CT|NJ|ART45|AC|MAP)-\d{2,}\b',
    re.IGNORECASE,
)

# Campos de dict de los que extraer IDs al recorrer JSON
_ID_FIELD_TO_SOURCE: dict[str, str] = {
    "factor_id": "INVENTARIO",
    "receptor_id": "INVENTARIO",
    "impact_id": "IMPACTO",
    "measure_id": "MEDIDA",
    "pva_id": "PVA",
    "gap_id": "GAP",
    "hecho_id": "HECHO_CONFIRMADO",
    "action_id": "IMPACTO",
    "requirement_id": "NORMATIVA",
    "map_id": "CARTOGRAFIA",
    "station_id": "CLIMA",
}

# Campos de texto de los que extraer etiquetas/texto libre
_TEXT_FIELDS: tuple[str, ...] = (
    "name", "title", "description", "label", "text",
    "factor_name", "requirement_title", "indicator",
)

# Palabras clave por factor ambiental → utilizadas para coincidencia débil (PARCIAL)
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "FI-001": ["clima", "temperatura", "precipitacion", "viento", "humedad", "pluviometria"],
    "FI-002": ["geologia", "geotecnia", "litologia", "roca", "estratigrafia", "substrato"],
    "FI-003": ["suelo", "edafologia", "erosion", "tierra", "edafico", "edafica"],
    "FI-004": ["hidrologia", "cauce", "acuifero", "escorrentia", "hidrologico", "hidrologica", "aguas superficiales"],
    "FI-005": ["inundabilidad", "zona inundable", "riesgo de inundacion", "llanura de inundacion"],
    "FI-006": ["calidad del aire", "atmosfera", "emisiones atmosfericas", "polvo", "particulas", "contaminacion atmosferica"],
    "FI-007": ["flora", "vegetacion", "habitats", "botanica", "fitosociolog", "cobertura vegetal"],
    "FI-008": ["fauna", "aves", "mamiferos", "reptiles", "anfibios", "peces", "invertebrados", "mastofauna", "herpetofauna"],
    "FI-009": ["espacios naturales protegidos", "parque natural", "reserva natural", "ENP"],
    "FI-010": ["red natura", "natura 2000", "LIC", "ZEPA", "ZEC", "lugar de importancia comunitaria"],
    "FI-011": ["paisaje", "cuenca visual", "visibilidad", "impacto visual", "calidad paisajistica"],
    "FI-012": ["patrimonio", "yacimiento", "arqueolog", "bien de interes cultural", "BIC", "carta arqueologica"],
    "FI-013": ["socioeconom", "empleo", "poblacion", "sector productivo", "actividad economica"],
    "FI-014": ["ruido", "acustico", "acustica", "sonido", "nivel sonoro", "contaminacion acustica"],
    "FI-015": ["cambio climatico", "GEI", "CO2", "carbono", "emision de gases", "huella de carbono"],
    "FI-016": ["riesgo natural", "sismico", "volcanico", "movimiento de ladera", "riesgo geologico"],
}

# Indicadores de contenido puramente metodológico / estructural → NO_APLICA
_NO_APLICA_INDICATORS: tuple[str, ...] = (
    "el presente documento",
    "este documento",
    "este estudio",
    "el objetivo de",
    "la presente memoria",
    "a continuacion",
    "se describe a continuacion",
    "se presenta a continuacion",
    "de acuerdo con lo anterior",
    "vease el apartado",
    "ver apartado",
    "nota:",
    "advertencia:",
    "esta auditoria no",
    "no declara aptitud",
    "no corrige automaticamente",
    "segun la documentacion analizada",
    "para mas informacion",
    "indice de contenidos",
    "tabla de contenidos",
    "introduccion",
)

# Patrones de aserciones técnicas concretas → candidatas a NO_TRAZADO si no hay topic match
_TECHNICAL_PATTERNS: list[re.Pattern] = [
    re.compile(r'\d+[,.]?\d*\s*(?:ha|m2|km2|km|metros|m)\b', re.I),
    re.compile(r'\d+[,.]?\d*\s*(?:dba|db|decibelios)\b', re.I),
    re.compile(r'\d+[,.]?\d*\s*(?:°c|grados|celsius)\b', re.I),
    re.compile(r'\d+[,.]?\d*\s*(?:ppm|mg/l|ug/m3)\b', re.I),
    re.compile(r'\bpm10\b|\bpm2\.5\b|\bnox\b|\bno2\b|\bso2\b', re.I),
    re.compile(r'\bph\s+\d', re.I),
    re.compile(r'\d+[,.]?\d*\s*(?:t/ano|t/a|toneladas)', re.I),
]

# Longitud mínima (normalizada) para considerar un claim como revisable
_MIN_CLAIM_LENGTH = 15


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# normalize_traceability_text
# ---------------------------------------------------------------------------

def normalize_traceability_text(text: str) -> str:
    """Normaliza texto para trazabilidad.

    - Quita tildes (NFKD → ASCII).
    - Minúsculas.
    - Normaliza espacios múltiples y saltos de línea.
    - Conserva códigos tipo FI-006, IMP-001, MED-001, HC-001, etc.
    - No elimina signos de puntuación (preserva contexto).
    """
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = no_accents.lower()
    normalized = re.sub(r"[\r\n\t]+", " ", lowered)
    normalized = re.sub(r" {2,}", " ", normalized)
    return normalized.strip()


# ---------------------------------------------------------------------------
# TraceabilityReference
# ---------------------------------------------------------------------------

@dataclass
class TraceabilityReference:
    """Referencia cargada desde las capas de datos del expediente."""

    ref_id: str
    """ID de la referencia: FI-007, IMP-001, MED-003, HC-001, GAP-005..."""

    source_type: str
    """Tipo de fuente: INVENTARIO, IMPACTO, MEDIDA, PVA, GAP, HECHO_CONFIRMADO..."""

    label: str
    """Etiqueta corta: nombre del factor, nombre del impacto, etc."""

    text: str = ""
    """Texto libre asociado: descripción, notas, etc."""

    metadata: dict = field(default_factory=dict)
    """Metadatos adicionales (fuente JSON, ruta del archivo)."""

    def to_dict(self) -> dict:
        return {
            "ref_id": self.ref_id,
            "source_type": self.source_type,
            "label": self.label,
            "text": self.text[:200] if self.text else "",
            "metadata": self.metadata,
        }

    def summary(self) -> str:
        s = f"[{self.source_type:20s}] {self.ref_id:12s} — {self.label[:50]}"
        return _ascii_safe(s)


# ---------------------------------------------------------------------------
# TraceabilityIssue
# ---------------------------------------------------------------------------

@dataclass
class TraceabilityIssue:
    """Incidencia de trazabilidad detectada."""

    severity: str
    """ERROR / WARNING / INFO."""

    code: str
    """Código de la incidencia (AU03-E001, AU03-W001, AU03-I001)."""

    source: str
    """Fuente del texto donde se detectó la incidencia."""

    claim: str
    """Afirmación que no pudo trazarse o solo se trazó parcialmente."""

    message: str
    """Descripción de la incidencia."""

    recommendation: str
    """Acción recomendada."""

    candidate_refs: list[str] = field(default_factory=list)
    """Referencias candidatas encontradas (IDs)."""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
            "claim": self.claim,
            "message": self.message,
            "recommendation": self.recommendation,
            "candidate_refs": list(self.candidate_refs),
        }

    def summary(self) -> str:
        s = (
            f"[{self.severity:7s}] {self.code} | {self.source[:40]} | "
            f"'{self.claim[:60]}'"
        )
        return _ascii_safe(s)


# ---------------------------------------------------------------------------
# TraceabilityResult
# ---------------------------------------------------------------------------

@dataclass
class TraceabilityResult:
    """Resultado completo de la validación de trazabilidad."""

    checked_sources: list[str] = field(default_factory=list)
    references_loaded: list[TraceabilityReference] = field(default_factory=list)
    traced_claims: list[str] = field(default_factory=list)
    partial_claims: list[str] = field(default_factory=list)
    untraced_claims: list[str] = field(default_factory=list)
    issues: list[TraceabilityIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        """True si no hay incidencias ERROR."""
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "checked_sources": list(self.checked_sources),
            "references_loaded": [r.to_dict() for r in self.references_loaded],
            "traced_claims": list(self.traced_claims),
            "partial_claims": list(self.partial_claims),
            "untraced_claims": list(self.untraced_claims),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_valid": self.is_valid(),
        }

    def summary(self) -> str:
        lines = [
            "--- AU-03 Validador de trazabilidad HC <-> DA ---",
            f"Referencias cargadas   : {len(self.references_loaded)}",
            f"Fuentes revisadas      : {len(self.checked_sources)}",
            f"Afirmaciones trazadas  : {len(self.traced_claims)}",
            f"Afirmaciones parciales : {len(self.partial_claims)}",
            f"No trazadas            : {len(self.untraced_claims)}",
            f"Incidencias ERROR      : {self.error_count()}",
            f"Incidencias WARNING    : {self.warning_count()}",
            f"Incidencias INFO       : {self.info_count()}",
            f"Resultado              : {'VALIDO (sin ERRORs)' if self.is_valid() else 'NO VALIDO (hay ERRORs)'}",
        ]
        if self.error_count() > 0:
            for iss in self.issues[:3]:
                if iss.severity == "ERROR":
                    lines.append(f"  ! {_ascii_safe(iss.source)}: '{_ascii_safe(iss.claim[:60])}'")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# extract_traceability_references_from_dict
# ---------------------------------------------------------------------------

def extract_traceability_references_from_dict(
    data: "dict | list | object",
    source_type: str,
    prefix_hint: str = "",
    _depth: int = 0,
) -> list[TraceabilityReference]:
    """Extrae referencias de trazabilidad desde una estructura JSON.

    Recorre dicts y listas recursivamente. Para cada dict que contenga
    un campo de ID reconocido (factor_id, impact_id, measure_id, etc.),
    crea un TraceabilityReference.

    Es tolerante con estructuras incompletas: nunca lanza excepción.

    Args:
        data: Estructura JSON ya cargada (dict, list, o primitivo).
        source_type: Tipo de fuente por defecto si no se puede inferir.
        prefix_hint: Prefijo para etiquetas (p.ej. nombre del archivo JSON).
        _depth: Profundidad de recursión interna (límite: 8).

    Returns:
        Lista de TraceabilityReference extraídas.
    """
    if _depth > 8:
        return []

    refs: list[TraceabilityReference] = []

    if isinstance(data, list):
        for item in data:
            refs.extend(
                extract_traceability_references_from_dict(
                    item, source_type, prefix_hint, _depth + 1
                )
            )
        return refs

    if not isinstance(data, dict):
        return refs

    # Intentar extraer un ID de los campos conocidos
    ref_id: str | None = None
    inferred_source_type = source_type

    for id_field, mapped_type in _ID_FIELD_TO_SOURCE.items():
        val = data.get(id_field)
        if val and isinstance(val, str) and val.strip():
            ref_id = val.strip()
            if mapped_type:
                inferred_source_type = mapped_type
            break

    # Si no hay campo de ID canónico, intentar "id" / "code" / "codigo"
    if ref_id is None:
        for fallback_field in ("id", "code", "codigo"):
            val = data.get(fallback_field)
            if val and isinstance(val, str) and val.strip():
                ref_id = val.strip()
                break

    if ref_id:
        # Extraer etiqueta y texto libre
        label = ""
        text_parts: list[str] = []
        for tf in _TEXT_FIELDS:
            v = data.get(tf)
            if v and isinstance(v, str):
                if not label:
                    label = v[:80]
                text_parts.append(v[:300])

        refs.append(TraceabilityReference(
            ref_id=ref_id,
            source_type=inferred_source_type,
            label=label or ref_id,
            text=" | ".join(text_parts)[:500],
            metadata={"prefix": prefix_hint},
        ))

    # Recursión en valores de los campos (listas y dicts anidados)
    for key, val in data.items():
        if isinstance(val, (dict, list)):
            refs.extend(
                extract_traceability_references_from_dict(
                    val, source_type, prefix_hint, _depth + 1
                )
            )

    return refs


# ---------------------------------------------------------------------------
# load_traceability_references
# ---------------------------------------------------------------------------

# Archivos a cargar y su source_type por defecto
_REFERENCE_FILES: list[tuple[str, str]] = [
    # Capas y control
    ("capas/hechos_confirmados.json", "HECHO_CONFIRMADO"),
    ("capas/inferencias_y_gaps.json", "GAP"),
    ("capas/normativa_aplicable.json", "NORMATIVA"),
    ("capas/cartografia_trace.json", "CARTOGRAFIA"),
    ("control_interno/phase2_result.json", "TEXTO"),
    ("control_interno/phase3_result.json", "NORMATIVA"),
    # Inventario
    ("inventario/inventory_summary.json", "INVENTARIO"),
    ("inventario/phase5_gate_result.json", "INVENTARIO"),
    # Impactos (cadena de outputs de Fase 6, del más completo al más básico)
    ("impactos/phase6_model_with_pva.json", "IMPACTO"),
    ("impactos/phase6_model_with_measures.json", "IMPACTO"),
    ("impactos/phase6_model_scored.json", "IMPACTO"),
    ("impactos/phase6_model_with_impacts.json", "IMPACTO"),
    ("impactos/cumulative_synergistic_result.json", "IMPACTO"),
    ("impactos/pva_coverage_result.json", "PVA"),
    # Auditoría
    ("auditoria/art45_checklist_result.json", "NORMATIVA"),
    ("auditoria/prudence_validation_result.json", "TEXTO"),
]


def load_traceability_references(
    expediente_path: "str | Path",
) -> list[TraceabilityReference]:
    """Carga referencias de trazabilidad desde los JSONs del expediente.

    Carga lo que exista, ignora lo que no exista, añade warning en caso
    de JSON corrupto. No lanza excepción por archivos ausentes.

    Args:
        expediente_path: Ruta al directorio del expediente EIA.

    Returns:
        Lista de TraceabilityReference cargadas (puede ser vacía).
    """
    exp_path = Path(expediente_path)
    all_refs: list[TraceabilityReference] = []
    seen_ids: set[str] = set()

    for rel_path, source_type in _REFERENCE_FILES:
        json_path = exp_path / rel_path
        if not json_path.exists():
            continue

        try:
            with open(json_path, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # JSON corrupto: crear referencia especial de error
            all_refs.append(TraceabilityReference(
                ref_id=f"ERR-{json_path.stem}",
                source_type="TEXTO",
                label=f"JSON corrupto: {rel_path}",
                metadata={"corrupt": True, "path": str(json_path)},
            ))
            continue

        extracted = extract_traceability_references_from_dict(
            data, source_type, prefix_hint=rel_path
        )
        for ref in extracted:
            if ref.ref_id not in seen_ids:
                seen_ids.add(ref.ref_id)
                all_refs.append(ref)

    return all_refs


# ---------------------------------------------------------------------------
# extract_claims_from_markdown
# ---------------------------------------------------------------------------

_MD_SEPARATOR = re.compile(r'^[-*_=]{3,}\s*$')
_MD_HEADING = re.compile(r'^#{1,6}\s+(.+)$')
_MD_BULLET = re.compile(r'^[-*+]\s+(.+)$')
_MD_ORDERED = re.compile(r'^\d+[.)]\s+(.+)$')
_MD_TABLE_ROW = re.compile(r'^\|(.+)\|$')
_MD_TABLE_SEP = re.compile(r'^\|[-| :]+\|$')
_MD_CODE_FENCE = re.compile(r'^```')


def extract_claims_from_markdown(markdown: str) -> list[str]:
    """Extrae afirmaciones relevantes de un texto markdown.

    Extrae:
    - Encabezados (texto sin los '#').
    - Bullets (texto del bullet).
    - Listas ordenadas.
    - Filas de tabla (celdas concatenadas).
    - Párrafos (líneas de texto libre, agrupadas).

    Ignora:
    - Líneas vacías.
    - Separadores markdown (---, ***, ===).
    - Separadores de tabla (|---|---|).
    - Bloques de código (``` ... ```).
    - Líneas demasiado cortas (< _MIN_CLAIM_LENGTH chars normalizado).
    - Líneas puramente numéricas o de índice.

    No modifica el markdown de entrada.
    """
    claims: list[str] = []
    in_code_block = False
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            merged = " ".join(paragraph_lines).strip()
            if len(normalize_traceability_text(merged)) >= _MIN_CLAIM_LENGTH:
                claims.append(merged)
            paragraph_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()

        # Toggle code block
        if _MD_CODE_FENCE.match(line):
            flush_paragraph()
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Empty / separator
        if not line or _MD_SEPARATOR.match(line):
            flush_paragraph()
            continue

        # Table separator row |---|---|
        if _MD_TABLE_SEP.match(line):
            continue

        # Heading
        m = _MD_HEADING.match(line)
        if m:
            flush_paragraph()
            heading_text = m.group(1).strip()
            if len(normalize_traceability_text(heading_text)) >= _MIN_CLAIM_LENGTH:
                claims.append(heading_text)
            continue

        # Bullet
        m = _MD_BULLET.match(line) or _MD_ORDERED.match(line)
        if m:
            flush_paragraph()
            bullet_text = m.group(1).strip()
            if len(normalize_traceability_text(bullet_text)) >= _MIN_CLAIM_LENGTH:
                claims.append(bullet_text)
            continue

        # Table row
        m = _MD_TABLE_ROW.match(line)
        if m:
            flush_paragraph()
            cells = [c.strip() for c in line.strip("|").split("|") if c.strip()]
            joined = " | ".join(cells)
            if len(normalize_traceability_text(joined)) >= _MIN_CLAIM_LENGTH:
                claims.append(joined)
            continue

        # Paragraph text — accumulate
        if line:
            paragraph_lines.append(line)

    flush_paragraph()

    # Final dedup (preserve order)
    seen: set[str] = set()
    result: list[str] = []
    for c in claims:
        key = normalize_traceability_text(c)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# _build_ref_index
# ---------------------------------------------------------------------------

def _build_ref_index(
    references: list[TraceabilityReference],
) -> dict[str, TraceabilityReference]:
    """Construye un índice ref_id → TraceabilityReference normalizado."""
    return {normalize_traceability_text(r.ref_id): r for r in references}


# ---------------------------------------------------------------------------
# claim_has_traceability
# ---------------------------------------------------------------------------

def claim_has_traceability(
    claim: str,
    references: list[TraceabilityReference],
) -> tuple[str, list[str]]:
    """Evalúa la trazabilidad de una afirmación contra referencias cargadas.

    Algoritmo (en orden de prioridad):

    1. NO_APLICA: afirmación muy corta (<15 chars normalizados) o
       puramente metodológica/estructural.

    2. TRAZADO: la afirmación contiene uno o más IDs explícitos del
       sistema (FI-xxx, FR-xxx, IMP-xxx, MED-xxx, PVA-xxx, HC-xxx,
       GAP-xxx, CT-xxx, NJ-xxx) Y al menos uno de ellos existe en las
       referencias cargadas.

    3. PARCIAL si contiene IDs del sistema pero ninguno está en referencias
       (expediente incompleto — el autor usa el convenio de IDs pero los
       JSONs aún no están generados).

    4. PARCIAL si hay coincidencia con palabras clave de un factor ambiental
       (ruido → FI-014, flora → FI-007, etc.), aunque no haya ID explícito.

    5. NO_TRAZADO si la afirmación contiene patrones de medición técnica
       concreta (m², dBA, °C, mg/l, etc.) sin ningún tema conocido ni ID.

    6. NO_APLICA como fallback para texto genérico sin contenido técnico.

    Returns:
        Tupla (status, candidate_refs).
        candidate_refs: lista de ref_ids o IDs inferidos relacionados.
    """
    norm = normalize_traceability_text(claim)

    # ── 1. NO_APLICA por longitud o contenido metodológico ────────────────
    if len(norm) < _MIN_CLAIM_LENGTH:
        return "NO_APLICA", []

    for ind in _NO_APLICA_INDICATORS:
        if ind in norm:
            return "NO_APLICA", []

    # ── 2 y 3. IDs explícitos ─────────────────────────────────────────────
    found_ids = [m.group(0).upper() for m in _ID_PATTERN.finditer(claim)]
    if found_ids:
        ref_index = _build_ref_index(references)
        matched_ids = [
            fid for fid in found_ids
            if normalize_traceability_text(fid) in ref_index
        ]
        if matched_ids:
            return "TRAZADO", matched_ids
        # IDs del sistema presentes pero no en las referencias cargadas
        return "PARCIAL", found_ids

    # ── 4. Coincidencia por palabras clave de factor ──────────────────────
    candidate_factors: list[str] = []
    for factor_id, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in norm for kw in keywords):
            candidate_factors.append(factor_id)
    if candidate_factors:
        return "PARCIAL", candidate_factors

    # ── 5. NO_TRAZADO: patrón técnico sin tema conocido ───────────────────
    for pattern in _TECHNICAL_PATTERNS:
        if pattern.search(claim):
            return "NO_TRAZADO", []

    # ── 6. NO_APLICA por defecto (texto genérico sin contenido técnico) ───
    return "NO_APLICA", []


# ---------------------------------------------------------------------------
# validate_markdown_traceability
# ---------------------------------------------------------------------------

def validate_markdown_traceability(
    markdown: str,
    references: list[TraceabilityReference],
    source: str = "markdown",
) -> TraceabilityResult:
    """Valida la trazabilidad de afirmaciones en un texto markdown.

    Para cada claim extraído:
    - TRAZADO → no genera incidencia.
    - PARCIAL → WARNING AU03-W001.
    - NO_TRAZADO → ERROR AU03-E001.
    - NO_APLICA → INFO AU03-I001 (solo si hay contenido relevante).

    No modifica el markdown.

    Args:
        markdown: Texto markdown a analizar.
        references: Lista de referencias cargadas (puede ser vacía).
        source: Identificador de la fuente (para informes).

    Returns:
        TraceabilityResult con issues, traced_claims, partial_claims, etc.
    """
    claims = extract_claims_from_markdown(markdown)
    issues: list[TraceabilityIssue] = []
    traced: list[str] = []
    partial: list[str] = []
    untraced: list[str] = []

    for claim in claims:
        status, candidate_refs = claim_has_traceability(claim, references)

        if status == "TRAZADO":
            traced.append(claim)

        elif status == "PARCIAL":
            partial.append(claim)
            issues.append(TraceabilityIssue(
                severity="WARNING",
                code="AU03-W001",
                source=source,
                claim=claim[:120],
                message=(
                    f"Afirmacion parcialmente trazada en '{source}'. "
                    f"Referencia(s) candidata(s): {candidate_refs}. "
                    "La afirmacion menciona un tema ambiental reconocible "
                    "pero sin ID explicito verificado."
                ),
                recommendation=(
                    "Incluir el ID del factor/impacto/medida correspondiente "
                    "para trazabilidad completa (ej. FI-014, IMP-001)."
                ),
                candidate_refs=candidate_refs,
            ))

        elif status == "NO_TRAZADO":
            untraced.append(claim)
            issues.append(TraceabilityIssue(
                severity="ERROR",
                code="AU03-E001",
                source=source,
                claim=claim[:120],
                message=(
                    f"Afirmacion tecnica concreta sin trazabilidad en '{source}'. "
                    "Contiene mediciones o datos especificos sin referencia "
                    "a hechos confirmados, inventario o impactos."
                ),
                recommendation=(
                    "Vincular la afirmacion a un ID del sistema (HC-xxx, FI-xxx, "
                    "IMP-xxx) o verificar que el JSON de origen esta cargado."
                ),
                candidate_refs=[],
            ))

        # NO_APLICA: no genera incidencia

    return TraceabilityResult(
        checked_sources=[source],
        references_loaded=[],  # referencias se reportan a nivel de expediente
        traced_claims=traced,
        partial_claims=partial,
        untraced_claims=untraced,
        issues=issues,
        notes=[
            f"'{source}': {len(claims)} afirmaciones extraidas, "
            f"{len(traced)} trazadas, {len(partial)} parciales, "
            f"{len(untraced)} no trazadas."
        ],
    )


# ---------------------------------------------------------------------------
# _merge_results
# ---------------------------------------------------------------------------

def _merge_results(results: list[TraceabilityResult]) -> TraceabilityResult:
    """Combina múltiples TraceabilityResult en uno solo."""
    merged = TraceabilityResult()
    for r in results:
        merged.checked_sources.extend(r.checked_sources)
        merged.traced_claims.extend(r.traced_claims)
        merged.partial_claims.extend(r.partial_claims)
        merged.untraced_claims.extend(r.untraced_claims)
        merged.issues.extend(r.issues)
        merged.warnings.extend(r.warnings)
        merged.notes.extend(r.notes)
    return merged


# ---------------------------------------------------------------------------
# validate_traceability_from_files
# ---------------------------------------------------------------------------

def validate_traceability_from_files(
    expediente_path: "str | Path",
) -> TraceabilityResult:
    """Valida trazabilidad revisando markdowns del expediente.

    Carga referencias desde JSONs disponibles, luego revisa los markdowns
    en: bloques/, inventario/ e impactos/.

    No revisa: docs/, prompts/, control_interno/, auditoria/, src/, tests/.
    Los informes de auditoria se usan como referencias JSON cuando procede,
    pero no como texto del Documento Ambiental para evitar autoincidencias.

    Si no hay markdowns: devuelve WARNING, no excepción.
    Si el directorio no existe: lanza FileNotFoundError.

    Args:
        expediente_path: Ruta al directorio del expediente EIA.

    Raises:
        FileNotFoundError: si el directorio del expediente no existe.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(
            f"Directorio de expediente no encontrado: {exp_path}"
        )

    references = load_traceability_references(exp_path)
    search_dirs = [
        exp_path / "bloques",
        exp_path / "inventario",
        exp_path / "impactos",
    ]

    all_results: list[TraceabilityResult] = []
    warnings_out: list[str] = []
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
            result = validate_markdown_traceability(text, references, source=rel_source)
            all_results.append(result)
            found_any = True

    if not found_any:
        warnings_out.append(
            f"No se encontraron archivos markdown en el expediente {exp_path.name}. "
            "Ejecute las fases previas para generar outputs antes de validar trazabilidad."
        )

    merged = _merge_results(all_results)
    merged.references_loaded = references
    merged.warnings.extend(warnings_out)
    merged.notes.append(
        f"Expediente: {exp_path.name}. "
        f"Referencias cargadas: {len(references)}. "
        f"Archivos markdown revisados: {len(merged.checked_sources)}."
    )
    return merged


# ---------------------------------------------------------------------------
# build_traceability_report_markdown
# ---------------------------------------------------------------------------

def build_traceability_report_markdown(result: TraceabilityResult) -> str:
    """Genera el informe de validación de trazabilidad en markdown."""
    lines: list[str] = []

    lines.append("# Auditoria de trazabilidad HC <-> DA — AU-03")
    lines.append("")

    # ── 1. Resumen ──
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append("| Categoría | Cantidad |")
    lines.append("|-----------|---------|")
    lines.append(f"| Referencias cargadas | {len(result.references_loaded)} |")
    lines.append(f"| Fuentes revisadas | {len(result.checked_sources)} |")
    lines.append(f"| Afirmaciones trazadas | {len(result.traced_claims)} |")
    lines.append(f"| Afirmaciones parciales | {len(result.partial_claims)} |")
    lines.append(f"| Afirmaciones no trazadas | {len(result.untraced_claims)} |")
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
        lines.append("_Ninguna fuente markdown revisada._")
    lines.append("")

    # ── 3. Referencias cargadas ──
    lines.append("## 3. Referencias cargadas")
    lines.append("")
    if result.references_loaded:
        by_type: dict[str, list[str]] = {}
        for r in result.references_loaded:
            by_type.setdefault(r.source_type, []).append(r.ref_id)
        for stype, ids in sorted(by_type.items()):
            lines.append(f"**{stype}** ({len(ids)}): {', '.join(sorted(ids)[:12])}"
                         + (f"... y {len(ids)-12} más" if len(ids) > 12 else ""))
        lines.append(f"\n_Total: {len(result.references_loaded)} referencias._")
    else:
        lines.append(
            "_Sin referencias cargadas. Ejecute las fases previas para "
            "generar los JSONs del expediente._"
        )
    lines.append("")

    # ── 4. Afirmaciones trazadas ──
    lines.append("## 4. Afirmaciones trazadas")
    lines.append("")
    if result.traced_claims:
        for c in result.traced_claims[:10]:
            lines.append(f"- ✓ {c[:100]}")
        if len(result.traced_claims) > 10:
            lines.append(f"- ... y {len(result.traced_claims) - 10} más.")
    else:
        lines.append("_Sin afirmaciones trazadas._")
    lines.append("")

    # ── 5. Afirmaciones parcialmente trazadas ──
    lines.append("## 5. Afirmaciones parcialmente trazadas")
    lines.append("")
    if result.partial_claims:
        for c in result.partial_claims[:10]:
            lines.append(f"- ~ {c[:100]}")
        if len(result.partial_claims) > 10:
            lines.append(f"- ... y {len(result.partial_claims) - 10} más.")
    else:
        lines.append("_Sin afirmaciones parcialmente trazadas._")
    lines.append("")

    # ── 6. Afirmaciones no trazadas ──
    lines.append("## 6. Afirmaciones no trazadas")
    lines.append("")
    if result.untraced_claims:
        for c in result.untraced_claims[:10]:
            lines.append(f"- ✗ {c[:100]}")
        if len(result.untraced_claims) > 10:
            lines.append(f"- ... y {len(result.untraced_claims) - 10} más.")
    else:
        lines.append("_Sin afirmaciones no trazadas._")
    lines.append("")

    # ── 7. Incidencias ──
    lines.append("## 7. Incidencias")
    lines.append("")
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings = [i for i in result.issues if i.severity == "WARNING"]
    if errors:
        lines.append("### Incidencias ERROR")
        lines.append("")
        for iss in errors[:15]:
            lines.append(f"**[{iss.code}]** `{iss.source}`")
            lines.append(f"  - Afirmacion: _{iss.claim[:100]}_")
            lines.append(f"  - Mensaje: {iss.message}")
            lines.append(f"  > Recomendacion: {iss.recommendation}")
            lines.append("")
    if warnings:
        lines.append("### Incidencias WARNING")
        lines.append("")
        for iss in warnings[:10]:
            lines.append(
                f"**[{iss.code}]** `{iss.source}` — _{iss.claim[:80]}_"
            )
            if iss.candidate_refs:
                lines.append(f"  > Referencias candidatas: {', '.join(iss.candidate_refs[:5])}")
            lines.append("")
    if not errors and not warnings:
        lines.append("_Sin incidencias ERROR ni WARNING._")
        lines.append("")

    # ── 8. Recomendaciones ──
    lines.append("## 8. Recomendaciones")
    lines.append("")
    lines.append(
        "Para mejorar la trazabilidad del expediente, incluir IDs explícitos "
        "del sistema en las afirmaciones técnicas:"
    )
    lines.append("")
    lines.append("| En lugar de | Usar |")
    lines.append("|-------------|------|")
    lines.append(
        "| 'La flora del área es diversa' "
        "| 'El factor FI-007 (flora) presenta...' |"
    )
    lines.append(
        "| 'El ruido supera los límites' "
        "| 'El impacto IMP-014 (ruido) supera...' |"
    )
    lines.append(
        "| 'La medida reduce el impacto' "
        "| 'La medida MED-001 reduce IMP-001' |"
    )
    lines.append("")

    # ── 9. Advertencia de alcance ──
    lines.append("## 9. Advertencia de alcance")
    lines.append("")
    lines.append(
        "> **Esta auditoría no corrige automáticamente el expediente y no declara "
        "aptitud administrativa. Es una verificación de trazabilidad que apoya la "
        "revisión técnica, pero no la sustituye. La clasificación final del "
        "expediente corresponde al órgano ambiental.**"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_traceability_validation_outputs
# ---------------------------------------------------------------------------

def write_traceability_validation_outputs(
    result: TraceabilityResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs de la validación de trazabilidad.

    Escribe:
      - {output_dir}/traceability_validation_result.json
      - {output_dir}/traceability_validation_result.md

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "traceability_validation_result.json"
    md_path = output_dir / "traceability_validation_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_traceability_report_markdown(result))

    return json_path, md_path
