"""
block_consistency_validator -- RD-04
Validador de coherencia entre bloques del Documento Ambiental EIA.

Detecta contradicciones entre bloques markdown del expediente en materias
sensibles: Red Natura 2000, flora/fauna, patrimonio, medidas diagnosticas,
PRL_NO_EIA, asunciones de test activas, PVA condicionado y conclusiones
que suavizan cautelas.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No corrige textos automaticamente.
  - No reescribe bloques.
  - No valora impactos.
  - No modifica el expediente salvo escritura del informe (--write).
  - No declara aptitud administrativa.
  - Funcion pura: no muta los textos de entrada.

Diferencia con AU-05 (P2):
  RD-04 valida coherencia entre bloques generados (textos .md).
  AU-05 (P2) validara coherencia de entidades entre todos los bloques A-K
  de forma mas profunda. RD-04 opera como paso previo, determinista y offline.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

CONSISTENCY_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

CONSISTENCY_STATUS: list[str] = [
    "COHERENTE",
    "CON_OBSERVACIONES",
    "INCOHERENTE",
    "SIN_DATOS",
]

BLOCK_FAMILIES: list[str] = [
    "A_IDENTIFICACION",
    "B_INVENTARIO",
    "C_IMPACTOS",
    "D_MEDIDAS",
    "E_PVA",
    "H_RED_NATURA",
    "I_CONCLUSIONES",
    "J_RNT",
    "K_ANEXOS",
    "GENERICO",
]

# ---------------------------------------------------------------------------
# Constantes privadas de deteccion
# ---------------------------------------------------------------------------

# Indicadores de cautela en bloques fuente
_CAUTELA_INDICATORS: frozenset[str] = frozenset({
    "indeterminado",
    "cautela",
    "pendiente",
    "at activa",
    "asuncion de test",
    "gap",
    "organo ambiental",
    "no se puede determinar",
    "requiere consulta",
    "prospeccion pendiente",
    "consulta pendiente",
    "campo necesario",
    "incertidumbre",
    "sin verificar",
    "no se ha verificado",
    "condicionado",
})

# Palabras clave para identificar contenido de Red Natura en un bloque
_RED_NATURA_KEYWORDS: frozenset[str] = frozenset({
    "red natura",
    "fi-010",
    "fr-010",
    "red natura 2000",
    "natura 2000",
    "zepa",
    "lic",
    "zec",
    "lugar de importancia comunitaria",
})

# Frases de cierre problematicas en bloques de conclusion sobre Red Natura
_RED_NATURA_CLOSERS: list[str] = [
    "sin afeccion apreciable",
    "sin afeccion significativa",
    "no afecta a red natura",
    "se descarta afeccion a red natura",
    "se descarta la afeccion",
    "no hay red natura",
    "fuera de red natura",
    "se descarta afeccion",
    "sin afeccion a la red natura",
]

# Palabras clave de biodiversidad
_BIO_KEYWORDS: frozenset[str] = frozenset({
    "flora",
    "fauna",
    "fi-007",
    "fi-008",
    "fr-007",
    "fr-008",
    "biodiversidad",
    "habitat",
    "vegetacion",
    "avifauna",
    "reptil",
    "mamifero",
    "herpetofauna",
})

# Frases de cierre de biodiversidad
_BIO_CLOSERS: list[str] = [
    "sin especies protegidas",
    "sin fauna",
    "sin flora",
    "sin afeccion a flora",
    "sin afeccion a fauna",
    "sin afeccion a la flora",
    "sin afeccion a la fauna",
    "no hay flora",
    "no hay fauna",
    "se descarta afeccion sobre flora",
    "se descarta afeccion sobre fauna",
    "no se detectan especies",
]

# Palabras clave de patrimonio
_HER_KEYWORDS: frozenset[str] = frozenset({
    "patrimonio",
    "fi-012",
    "fr-012",
    "yacimiento",
    "arqueolog",
    "bic",
    "bien de interes cultural",
    "catalogo de bienes",
})

# Frases de cierre de patrimonio
_HER_CLOSERS: list[str] = [
    "no hay patrimonio",
    "sin yacimientos",
    "sin afeccion patrimonial",
    "no existe patrimonio",
    "se descarta afeccion patrimonial",
    "sin patrimonio",
    "no hay bienes de interes",
]

# Frases de cierre administrativo (siempre ERROR en cualquier bloque)
_ADMIN_CLOSERS: list[str] = [
    "apto para presentacion",
    "apto administrativamente",
    "conforme para presentar",
    "expediente apto",
    "datos confirmados",
]

# Frases que suavizan indebidamente el estado del expediente
_SOFTENING_PHRASES: list[str] = [
    "todos los impactos son compatibles",
    "no existen impactos relevantes",
    "sin condicionantes",
    "sin observaciones relevantes",
    "no existen efectos significativos",
]

# Indicadores de AT activa en texto
_AT_ACTIVE_TEXT: frozenset[str] = frozenset({
    "at activa",
    "asuncion de test activa",
    "asuncion provisional",
    "modo test",
    "impide aptitud administrativa",
})

# Patrones de medida diagnostica mal usada
_DIAGNOSTIC_MARKERS: list[str] = [
    "diagnostica",
    "estudio acustico",
    "medicion acustica",
    "estudio de ruido",
    "diagnostico de ruido",
    "monitorizacion acustica",
]
_REDUCER_MARKERS: list[str] = [
    "reductora",
    "correctora",
    "reduce significancia",
    "impacto reducido",
    "significancia reducida",
    "reduce el impacto",
]

# Patrones de PRL/EPI mal usado
_PRL_MARKERS: list[str] = [
    "prl_no_eia",
    "prl no eia",
    "medida prl",
    "equipo de proteccion individual",
    "epi ",
    "auriculares",
    "protector auditivo",
]
_PRL_REDUCER_MARKERS: list[str] = [
    "correctora ambiental",
    "reductora ambiental",
    "reduccion del impacto exterior",
    "reduce el impacto acustico exterior",
    "reduce el ruido exterior",
]

# Indicadores de PVA condicionado
_PVA_CONDITIONED: list[str] = [
    "pva condicionado",
    "condicionado por cont",
    "condicionado por at",
    "sujeto a cont",
    "pendiente de dato",
    "ficha condicionada",
    "programa condicionado",
]

# Frases de cierre de PVA
_PVA_CLOSERS: list[str] = [
    "pva cerrado",
    "pva completado",
    "vigilancia ambiental finalizada",
    "todos los pva estan cerrados",
    "programa de vigilancia cerrado",
    "pva definitivo",
]


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------


def _ascii_safe(text: str) -> str:
    """Normaliza texto a ASCII para consola Windows cp1252."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BlockConsistencyIssue:
    """Incidencia de coherencia entre bloques."""

    severity: str       # ERROR / WARNING / INFO
    code: str
    source_block: str   # bloque que contiene la cautela/dato fuente
    target_block: str   # bloque donde aparece la incoherencia
    message: str
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""

    def __post_init__(self) -> None:
        if self.severity not in CONSISTENCY_SEVERITY:
            raise ValueError(f"severity invalido: {self.severity!r}")

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "source_block": self.source_block,
            "target_block": self.target_block,
            "message": self.message,
            "evidence": list(self.evidence),
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        return (
            f"[{self.severity}] {self.code} "
            f"({self.source_block} -> {self.target_block}): {self.message}"
        )


@dataclass
class BlockConsistencyResult:
    """Resultado completo de la validacion de coherencia entre bloques."""

    status: str
    checked_blocks: list[str] = field(default_factory=list)
    issues: list[BlockConsistencyIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # administrative_ready nunca se declara desde aqui
    administrative_ready: bool = False

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        """True solo si no hay incidencias ERROR."""
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checked_blocks": list(self.checked_blocks),
            "issues": [i.to_dict() for i in self.issues],
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "is_valid": self.is_valid(),
            "administrative_ready": self.administrative_ready,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            "--- RD-04 Validador de coherencia entre bloques ---",
            f"Estado          : {self.status}",
            f"Bloques revisados: {len(self.checked_blocks)}",
            f"Incidencias ERROR   : {self.error_count()}",
            f"Incidencias WARNING : {self.warning_count()}",
            f"Incidencias INFO    : {self.info_count()}",
        ]
        if self.issues:
            lines.append("")
            lines.append("Incidencias:")
            for iss in self.issues[:10]:
                lines.append(f"  {iss.summary()}")
            if len(self.issues) > 10:
                lines.append(f"  ... ({len(self.issues) - 10} mas)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# normalize_block_text
# ---------------------------------------------------------------------------


def normalize_block_text(text: str) -> str:
    """Normaliza texto de bloque para comparacion.

    - Minusculas.
    - Quita tildes (normalizacion NFKD + encode ASCII).
    - Normaliza espacios.
    - Conserva codigos tipo FI-010, FR-010, IMP-001, GAP-001, AT-001, MED-001, PVA-001.
    """
    # Quitar tildes y pasar a ASCII (preserva guiones y digitos)
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    # Normalizar espacios
    return re.sub(r"\s+", " ", ascii_text).strip()


# ---------------------------------------------------------------------------
# detect_block_family
# ---------------------------------------------------------------------------


def detect_block_family(path_or_name: str) -> str:
    """Clasifica un bloque por su nombre o ruta."""
    name = str(path_or_name).lower().replace("\\", "/")

    # Clasificacion por directorio (mayor especificidad)
    if "/inventario/" in name or name.startswith("inventario/"):
        return "B_INVENTARIO"

    if "/impactos/" in name or name.startswith("impactos/"):
        stem = Path(name).stem
        if "pva" in stem:
            return "E_PVA"
        if "medid" in stem or "_d_" in stem or "bloque_d" in stem:
            return "D_MEDIDAS"
        return "C_IMPACTOS"

    if "/auditoria/" in name or name.startswith("auditoria/"):
        return "GENERICO"

    # Clasificacion por nombre de archivo
    stem = Path(name).stem.lower()

    if any(k in stem for k in ("bloque_a", "a_identificacion", "_a_", "identificacion")):
        return "A_IDENTIFICACION"
    if any(k in stem for k in ("bloque_b", "b_inventario", "inventario")):
        return "B_INVENTARIO"
    if any(k in stem for k in ("bloque_c", "c_impactos", "impactos", "valoracion")):
        return "C_IMPACTOS"
    if any(k in stem for k in ("bloque_d", "d_medidas", "medidas")):
        return "D_MEDIDAS"
    if any(k in stem for k in ("bloque_e", "e_pva", "pva")):
        return "E_PVA"
    if any(k in stem for k in ("bloque_h", "h_red_natura", "red_natura", "red_natura_2000")):
        return "H_RED_NATURA"
    if any(k in stem for k in ("bloque_i", "i_conclusiones", "conclusiones")):
        return "I_CONCLUSIONES"
    if any(k in stem for k in ("bloque_j", "j_rnt", "rnt", "resumen_no_tecnico")):
        return "J_RNT"
    if any(k in stem for k in ("anejo", "anexo", "bloque_k")):
        return "K_ANEXOS"

    return "GENERICO"


# ---------------------------------------------------------------------------
# load_markdown_blocks
# ---------------------------------------------------------------------------


def load_markdown_blocks(expediente_path: str | Path) -> dict[str, str]:
    """Carga todos los markdowns relevantes del expediente.

    Busca en: bloques/, inventario/, impactos/.
    No busca en: docs/, prompts/, auditoria/, tests/ del proyecto.
    Los informes de auditoria no se tratan como bloques del Documento
    Ambiental para evitar autoincidencias.

    Devuelve dict con clave=ruta relativa, valor=texto.
    Si no hay markdowns, devuelve dict vacio.
    """
    p = Path(expediente_path)
    SCAN_DIRS = ("bloques", "inventario", "impactos")
    blocks: dict[str, str] = {}

    for subdir in SCAN_DIRS:
        d = p / subdir
        if not d.is_dir():
            continue
        for md_file in sorted(d.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            key = f"{subdir}/{md_file.name}"
            blocks[key] = text

    return blocks


# ---------------------------------------------------------------------------
# Helpers internos de deteccion
# ---------------------------------------------------------------------------


def _has_any(text_norm: str, phrases: list[str]) -> tuple[bool, str]:
    """Devuelve (encontrado, frase) si alguna frase esta en el texto normalizado."""
    for phrase in phrases:
        if phrase in text_norm:
            return True, phrase
    return False, ""


def _has_cautela(text_norm: str) -> bool:
    return any(w in text_norm for w in _CAUTELA_INDICATORS)


def _classify_blocks(blocks: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """Agrupa bloques por familia. Devuelve {familia: [(nombre, texto_norm)]}."""
    classified: dict[str, list[tuple[str, str]]] = {f: [] for f in BLOCK_FAMILIES}
    for name, text in blocks.items():
        family = detect_block_family(name)
        classified[family].append((name, normalize_block_text(text)))
    return classified


def _all_closing_blocks(
    classified: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, str]]:
    """Devuelve todos los bloques de conclusion/RNT."""
    return (
        classified.get("I_CONCLUSIONES", [])
        + classified.get("J_RNT", [])
    )


# ---------------------------------------------------------------------------
# validate_red_natura_consistency
# ---------------------------------------------------------------------------


def validate_red_natura_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta contradiciones entre cautelas de Red Natura y cierres en conclusiones."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)

    if not closing_blocks:
        return issues

    # Buscar cautelas en bloques H o cualquier bloque con contenido Red Natura
    h_blocks = classified.get("H_RED_NATURA", [])
    # Tambien revisar inventario y C_IMPACTOS por si hay FR-010
    candidate_source = (
        h_blocks
        + [
            (n, t) for n, t in (
                classified.get("B_INVENTARIO", [])
                + classified.get("C_IMPACTOS", [])
                + classified.get("GENERICO", [])
            )
            if any(kw in t for kw in _RED_NATURA_KEYWORDS)
        ]
    )

    for src_name, src_text in candidate_source:
        has_rn = any(kw in src_text for kw in _RED_NATURA_KEYWORDS) or (
            detect_block_family(src_name) == "H_RED_NATURA"
        )
        if not has_rn:
            continue
        if not _has_cautela(src_text):
            continue
        # Fuente tiene Red Natura con cautela → revisar conclusiones
        for tgt_name, tgt_text in closing_blocks:
            found, phrase = _has_any(tgt_text, _RED_NATURA_CLOSERS)
            if found:
                issues.append(BlockConsistencyIssue(
                    severity="ERROR",
                    code="BC-RN-001",
                    source_block=src_name,
                    target_block=tgt_name,
                    message=(
                        f"'{src_name}' contiene cautela sobre Red Natura/ENP, "
                        f"pero '{tgt_name}' usa lenguaje de cierre: '{phrase}'"
                    ),
                    evidence=[phrase],
                    recommendation=(
                        "Revisar coherencia entre inventario/Red Natura y conclusiones/RNT. "
                        "Usar: 'no se detecta en las fuentes consultadas' o remitir al organo ambiental."
                    ),
                ))

    # WARNING si bloque I/J menciona Red Natura directamente con lenguaje ambiguo
    for tgt_name, tgt_text in closing_blocks:
        if any(kw in tgt_text for kw in _RED_NATURA_KEYWORDS):
            found, phrase = _has_any(tgt_text, ["se puede descartar", "parece que no afecta"])
            if found:
                issues.append(BlockConsistencyIssue(
                    severity="WARNING",
                    code="BC-RN-002",
                    source_block=tgt_name,
                    target_block=tgt_name,
                    message=(
                        f"'{tgt_name}' menciona Red Natura con lenguaje ambiguo: '{phrase}'"
                    ),
                    evidence=[phrase],
                    recommendation=(
                        "No usar 'se puede descartar' sin consulta al organo ambiental."
                    ),
                ))

    return issues


# ---------------------------------------------------------------------------
# validate_biodiversity_consistency
# ---------------------------------------------------------------------------


def validate_biodiversity_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta contradiciones entre cautelas de biodiversidad y cierres en conclusiones."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)

    if not closing_blocks:
        return issues

    # Fuentes de cautela biodiversidad: inventario + impactos con contenido bio
    candidate_source = [
        (n, t)
        for n, t in (
            classified.get("B_INVENTARIO", [])
            + classified.get("C_IMPACTOS", [])
            + classified.get("GENERICO", [])
        )
        if any(kw in t for kw in _BIO_KEYWORDS)
    ]

    for src_name, src_text in candidate_source:
        if not _has_cautela(src_text):
            continue
        for tgt_name, tgt_text in closing_blocks:
            found, phrase = _has_any(tgt_text, _BIO_CLOSERS)
            if found:
                issues.append(BlockConsistencyIssue(
                    severity="ERROR",
                    code="BC-BIO-001",
                    source_block=src_name,
                    target_block=tgt_name,
                    message=(
                        f"'{src_name}' contiene cautela de biodiversidad (flora/fauna), "
                        f"pero '{tgt_name}' usa lenguaje de cierre: '{phrase}'"
                    ),
                    evidence=[phrase],
                    recommendation=(
                        "No afirmar ausencia de flora/fauna sin prospeccion de campo confirmada. "
                        "Usar: 'no se detecta en las fuentes consultadas'."
                    ),
                ))

    return issues


# ---------------------------------------------------------------------------
# validate_heritage_consistency
# ---------------------------------------------------------------------------


def validate_heritage_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta contradiciones entre cautelas de patrimonio y cierres en conclusiones."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)

    if not closing_blocks:
        return issues

    candidate_source = [
        (n, t)
        for n, t in (
            classified.get("B_INVENTARIO", [])
            + classified.get("C_IMPACTOS", [])
            + classified.get("GENERICO", [])
        )
        if any(kw in t for kw in _HER_KEYWORDS)
    ]

    for src_name, src_text in candidate_source:
        if not _has_cautela(src_text):
            continue
        for tgt_name, tgt_text in closing_blocks:
            found, phrase = _has_any(tgt_text, _HER_CLOSERS)
            if found:
                issues.append(BlockConsistencyIssue(
                    severity="ERROR",
                    code="BC-HER-001",
                    source_block=src_name,
                    target_block=tgt_name,
                    message=(
                        f"'{src_name}' contiene cautela de patrimonio cultural, "
                        f"pero '{tgt_name}' usa lenguaje de cierre: '{phrase}'"
                    ),
                    evidence=[phrase],
                    recommendation=(
                        "No afirmar ausencia de patrimonio sin consulta al organismo competente. "
                        "Usar: 'no consta en las fuentes consultadas'."
                    ),
                ))

    return issues


# ---------------------------------------------------------------------------
# validate_measure_consistency
# ---------------------------------------------------------------------------


def validate_measure_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta medidas diagnosticas o PRL usadas como reductoras de impacto ambiental."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)

    # Revisar bloques de medidas, impactos y cualquier bloque
    all_blocks = [
        (n, normalize_block_text(t))
        for n, t in blocks.items()
    ]

    for name, norm in all_blocks:
        # Medida diagnostica usada como reductora
        for diag_marker in _DIAGNOSTIC_MARKERS:
            if diag_marker in norm:
                for red_marker in _REDUCER_MARKERS:
                    if red_marker in norm:
                        issues.append(BlockConsistencyIssue(
                            severity="ERROR",
                            code="BC-MEA-001",
                            source_block=name,
                            target_block=name,
                            message=(
                                f"'{name}' presenta medida diagnostica ('{diag_marker}') "
                                f"como reductora de impacto ('{red_marker}'). "
                                "Una medida diagnostica no reduce por si sola la significancia."
                            ),
                            evidence=[diag_marker, red_marker],
                            recommendation=(
                                "Separar claramente las medidas diagnosticas de las correctoras. "
                                "AG09-13: DIAGNOSTICA != reductora."
                            ),
                        ))
                        break  # un issue por marcador diagnostico es suficiente

        # PRL_NO_EIA usada como correctora ambiental
        for prl_marker in _PRL_MARKERS:
            if prl_marker in norm:
                for red_marker in _PRL_REDUCER_MARKERS:
                    if red_marker in norm:
                        issues.append(BlockConsistencyIssue(
                            severity="ERROR",
                            code="BC-MEA-002",
                            source_block=name,
                            target_block=name,
                            message=(
                                f"'{name}' presenta medida PRL/EPI ('{prl_marker}') "
                                f"como correctora ambiental ('{red_marker}'). "
                                "Las medidas PRL no reducen el impacto ambiental exterior."
                            ),
                            evidence=[prl_marker, red_marker],
                            recommendation=(
                                "Separar medidas PRL de medidas correctoras ambientales. "
                                "AG09-14: PRL_NO_EIA != correctora ambiental."
                            ),
                        ))
                        break

        # EPI / auricular usado como reductor exterior (WARNING)
        if any(m in norm for m in ("epi ", "auriculares", "protector auditivo")):
            if any(m in norm for m in ("exterior", "reduce el ruido", "reduccion de ruido exterior")):
                issues.append(BlockConsistencyIssue(
                    severity="WARNING",
                    code="BC-MEA-003",
                    source_block=name,
                    target_block=name,
                    message=(
                        f"'{name}' menciona EPI/proteccion auditiva junto a reduccion exterior. "
                        "Verificar que no se usa EPI como medida correctora ambiental exterior."
                    ),
                    evidence=["epi / auricular"],
                    recommendation=(
                        "EPI protege al trabajador, no reduce el impacto acustico al exterior."
                    ),
                ))

    return _dedup_issues(issues)


# ---------------------------------------------------------------------------
# validate_assumption_consistency
# ---------------------------------------------------------------------------


def validate_assumption_consistency(
    blocks: dict[str, str],
    assumptions_registry=None,
) -> list[BlockConsistencyIssue]:
    """Detecta conclusion que cierra expediente con ATs activas pendientes."""
    from eia_agent.core.assumption_test_system import AsuncionTestRegistry

    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)
    all_blocks_norm = {name: normalize_block_text(text) for name, text in blocks.items()}

    # Determinar si hay ATs activas
    registry_has_active = (
        isinstance(assumptions_registry, AsuncionTestRegistry)
        and assumptions_registry.blocks_administrative_submission()
    )

    # Detectar ATs activas en texto
    text_has_active = any(
        any(kw in norm for kw in _AT_ACTIVE_TEXT)
        for norm in all_blocks_norm.values()
    )

    has_active_at = registry_has_active or text_has_active

    if not has_active_at:
        return issues

    # Hay ATs activas: verificar que los cierres no suenen a aptitud
    at_source = "registry (AT activa)" if registry_has_active else "texto del expediente"

    for tgt_name, tgt_text in closing_blocks:
        found, phrase = _has_any(tgt_text, _ADMIN_CLOSERS)
        if found:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-AT-001",
                source_block=at_source,
                target_block=tgt_name,
                message=(
                    f"Existen asunciones de test activas ({at_source}), "
                    f"pero '{tgt_name}' usa lenguaje de cierre administrativo: '{phrase}'"
                ),
                evidence=[phrase],
                recommendation=(
                    "El expediente no puede considerarse apto para presentacion "
                    "mientras existan ATs activas."
                ),
            ))

        found2, phrase2 = _has_any(tgt_text, ["sin condicionantes", "datos confirmados"])
        if found2:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-AT-002",
                source_block=at_source,
                target_block=tgt_name,
                message=(
                    f"Existen asunciones de test activas ({at_source}), "
                    f"pero '{tgt_name}' dice: '{phrase2}'"
                ),
                evidence=[phrase2],
                recommendation=(
                    "Las ATs activas son condicionantes. No usar 'sin condicionantes' "
                    "ni 'datos confirmados' mientras existan ATs activas."
                ),
            ))

    return _dedup_issues(issues)


# ---------------------------------------------------------------------------
# validate_pva_consistency
# ---------------------------------------------------------------------------


def validate_pva_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta PVA condicionado presentado como cerrado en conclusiones."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)

    if not closing_blocks:
        return issues

    # Buscar bloques PVA o C con condicionamiento
    pva_blocks = (
        classified.get("E_PVA", [])
        + [
            (n, t) for n, t in (
                classified.get("C_IMPACTOS", [])
                + classified.get("GENERICO", [])
            )
            if any(kw in t for kw in ("pva", "vigilancia ambiental", "programa de vigilancia"))
        ]
    )

    for src_name, src_text in pva_blocks:
        found_cond, phrase_cond = _has_any(src_text, _PVA_CONDITIONED)
        if not found_cond:
            continue
        for tgt_name, tgt_text in closing_blocks:
            found_close, phrase_close = _has_any(tgt_text, _PVA_CLOSERS)
            if found_close:
                issues.append(BlockConsistencyIssue(
                    severity="ERROR",
                    code="BC-PVA-001",
                    source_block=src_name,
                    target_block=tgt_name,
                    message=(
                        f"'{src_name}' indica PVA condicionado ('{phrase_cond}'), "
                        f"pero '{tgt_name}' lo presenta como cerrado ('{phrase_close}')"
                    ),
                    evidence=[phrase_cond, phrase_close],
                    recommendation=(
                        "Un PVA condicionado no puede presentarse como cerrado. "
                        "Indicar el condicionante y remitir al organo ambiental."
                    ),
                ))

    # WARNING: cobertura PVA global presentada como especifica
    for src_name, src_text in pva_blocks:
        if "revision anual" in src_text and "ficha especifica" in src_text:
            issues.append(BlockConsistencyIssue(
                severity="WARNING",
                code="BC-PVA-002",
                source_block=src_name,
                target_block=src_name,
                message=(
                    f"'{src_name}' menciona revision anual y ficha especifica en el mismo contexto. "
                    "Verificar que la revision anual no se presenta como cobertura especifica."
                ),
                evidence=["revision anual", "ficha especifica"],
                recommendation=(
                    "La revision anual es cobertura global, no sustituye a fichas especificas de impacto."
                ),
            ))

    return issues


# ---------------------------------------------------------------------------
# validate_conclusion_consistency
# ---------------------------------------------------------------------------


def validate_conclusion_consistency(
    blocks: dict[str, str],
) -> list[BlockConsistencyIssue]:
    """Detecta conclusiones que suavizan indebidamente el estado del expediente."""
    issues: list[BlockConsistencyIssue] = []
    classified = _classify_blocks(blocks)
    closing_blocks = _all_closing_blocks(classified)
    all_norm = {name: normalize_block_text(text) for name, text in blocks.items()}

    # 1) Lenguaje de aptitud administrativa siempre ERROR
    for tgt_name, tgt_text in closing_blocks:
        found, phrase = _has_any(tgt_text, _ADMIN_CLOSERS)
        if found:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-CON-003",
                source_block=tgt_name,
                target_block=tgt_name,
                message=(
                    f"'{tgt_name}' usa lenguaje de aptitud administrativa: '{phrase}'. "
                    "Solo el organo ambiental puede emitir el Informe de Impacto Ambiental."
                ),
                evidence=[phrase],
                recommendation=(
                    "Eliminar cualquier declaracion de aptitud administrativa. "
                    "Regla juridica CLAUDE.md: el promotor presenta el DA, "
                    "el organo ambiental formula el IIA."
                ),
            ))

    # 2) "todos los impactos son compatibles" pero hay INDETERMINADO en otros bloques
    all_texts_others = {
        n: t for n, t in all_norm.items()
        if detect_block_family(n) not in ("I_CONCLUSIONES", "J_RNT")
    }
    has_indeterminado = any("indeterminado" in t for t in all_texts_others.values())

    for tgt_name, tgt_text in closing_blocks:
        if "todos los impactos son compatibles" in tgt_text and has_indeterminado:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-CON-001",
                source_block="otros bloques",
                target_block=tgt_name,
                message=(
                    f"'{tgt_name}' afirma 'todos los impactos son compatibles', "
                    "pero otros bloques contienen impactos INDETERMINADO."
                ),
                evidence=["todos los impactos son compatibles", "indeterminado"],
                recommendation=(
                    "No cerrar la valoracion con 'todos compatibles' si hay impactos INDETERMINADO. "
                    "Declarar el nivel de incertidumbre."
                ),
            ))

    # 3) "no existen impactos relevantes" pero hay bloques con impactos
    has_impacts = any(
        ("imp-" in t or ("impacto" in t and "no existen impactos" not in t))
        for n, t in all_texts_others.items()
        if "impactos" in n or "inventario" in n
    )

    for tgt_name, tgt_text in closing_blocks:
        if "no existen impactos relevantes" in tgt_text and has_impacts:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-CON-002",
                source_block="otros bloques",
                target_block=tgt_name,
                message=(
                    f"'{tgt_name}' afirma 'no existen impactos relevantes', "
                    "pero hay contenido de impactos en otros bloques."
                ),
                evidence=["no existen impactos relevantes"],
                recommendation=(
                    "Si hay impactos identificados en el expediente, "
                    "no puede afirmarse que no existen impactos relevantes."
                ),
            ))

    # 4) "sin condicionantes" cuando hay gaps ALTA o indeterminado en otros bloques
    has_condicionantes = any(
        "gap alta" in t or ("gap" in t and "alta" in t) or "indeterminado" in t
        for t in all_texts_others.values()
    )

    for tgt_name, tgt_text in closing_blocks:
        if "sin condicionantes" in tgt_text and has_condicionantes:
            issues.append(BlockConsistencyIssue(
                severity="ERROR",
                code="BC-CON-004",
                source_block="otros bloques",
                target_block=tgt_name,
                message=(
                    f"'{tgt_name}' dice 'sin condicionantes', "
                    "pero hay gaps ALTA o impactos INDETERMINADO en otros bloques."
                ),
                evidence=["sin condicionantes"],
                recommendation=(
                    "Los gaps ALTA y los impactos INDETERMINADO son condicionantes "
                    "del expediente. No usar 'sin condicionantes'."
                ),
            ))

    return _dedup_issues(issues)


# ---------------------------------------------------------------------------
# Helper deduplicacion
# ---------------------------------------------------------------------------


def _dedup_issues(
    issues: list[BlockConsistencyIssue],
) -> list[BlockConsistencyIssue]:
    """Elimina issues duplicados por (code, source_block, target_block, evidence[0])."""
    seen: set[tuple] = set()
    result: list[BlockConsistencyIssue] = []
    for iss in issues:
        ev0 = iss.evidence[0] if iss.evidence else ""
        key = (iss.code, iss.source_block, iss.target_block, ev0)
        if key not in seen:
            seen.add(key)
            result.append(iss)
    return result


# ---------------------------------------------------------------------------
# validate_block_consistency
# ---------------------------------------------------------------------------


def validate_block_consistency(
    blocks: dict[str, str],
    assumptions_registry=None,
) -> BlockConsistencyResult:
    """Ejecuta todos los validadores y combina resultados."""
    if not blocks:
        return BlockConsistencyResult(
            status="SIN_DATOS",
            checked_blocks=[],
            notes=["No se encontraron bloques markdown para revisar."],
        )

    all_issues: list[BlockConsistencyIssue] = []
    all_issues += validate_red_natura_consistency(blocks)
    all_issues += validate_biodiversity_consistency(blocks)
    all_issues += validate_heritage_consistency(blocks)
    all_issues += validate_measure_consistency(blocks)
    all_issues += validate_assumption_consistency(blocks, assumptions_registry)
    all_issues += validate_pva_consistency(blocks)
    all_issues += validate_conclusion_consistency(blocks)

    # Deduplicar globalmente
    all_issues = _dedup_issues(all_issues)

    # Ordenar: ERROR primero, luego WARNING, luego INFO
    _ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    all_issues.sort(key=lambda x: _ORDER.get(x.severity, 3))

    has_error = any(i.severity == "ERROR" for i in all_issues)
    has_warning = any(i.severity == "WARNING" for i in all_issues)

    if has_error:
        status = "INCOHERENTE"
    elif has_warning:
        status = "CON_OBSERVACIONES"
    elif all_issues:
        status = "CON_OBSERVACIONES"
    else:
        status = "COHERENTE"

    return BlockConsistencyResult(
        status=status,
        checked_blocks=sorted(blocks.keys()),
        issues=all_issues,
        notes=[
            f"Bloques revisados: {len(blocks)}",
            "Esta auditoria no corrige automaticamente el expediente.",
        ],
    )


# ---------------------------------------------------------------------------
# validate_block_consistency_from_files
# ---------------------------------------------------------------------------


def validate_block_consistency_from_files(
    expediente_path: str | Path,
) -> BlockConsistencyResult:
    """Carga markdowns y asunciones, ejecuta validate_block_consistency."""
    from eia_agent.core.assumption_test_system import (
        load_assumptions_registry,
        AsuncionTestRegistry,
    )

    p = Path(expediente_path)
    blocks = load_markdown_blocks(p)
    registry: AsuncionTestRegistry | None = None
    extra_warnings: list[str] = []

    at_json = p / "control_interno" / "asunciones_test.json"
    if at_json.exists():
        try:
            registry = load_assumptions_registry(at_json)
        except ValueError as exc:
            extra_warnings.append(
                f"JSON de asunciones corrupto en {at_json}: {exc}. "
                "Se ignora el registro de ATs para esta validacion."
            )

    result = validate_block_consistency(blocks, registry)
    result.warnings.extend(extra_warnings)
    return result


# ---------------------------------------------------------------------------
# build_block_consistency_report_markdown
# ---------------------------------------------------------------------------


def build_block_consistency_report_markdown(
    result: BlockConsistencyResult,
) -> str:
    """Genera informe markdown de coherencia entre bloques."""
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings = [i for i in result.issues if i.severity == "WARNING"]
    infos = [i for i in result.issues if i.severity == "INFO"]

    lines: list[str] = [
        "# Auditoria de coherencia entre bloques",
        "",
        "## 1. Resumen",
        "",
        f"- Estado: **{result.status}**",
        f"- Bloques revisados: {len(result.checked_blocks)}",
        f"- Incidencias ERROR: {len(errors)}",
        f"- Incidencias WARNING: {len(warnings)}",
        f"- Incidencias INFO: {len(infos)}",
        "",
        "## 2. Bloques revisados",
        "",
    ]

    if result.checked_blocks:
        for b in result.checked_blocks:
            lines.append(f"- `{b}`")
    else:
        lines.append("_Sin bloques revisados._")

    lines += ["", "## 3. Incidencias ERROR", ""]

    if errors:
        for iss in errors:
            lines += [
                f"### {iss.code}",
                "",
                f"- **Origen**: `{iss.source_block}`",
                f"- **Bloque afectado**: `{iss.target_block}`",
                f"- **Descripcion**: {iss.message}",
                f"- **Evidencia**: {', '.join(iss.evidence) or '—'}",
                f"- **Recomendacion**: {iss.recommendation or '—'}",
                "",
            ]
    else:
        lines.append("_Sin incidencias ERROR._")

    lines += ["", "## 4. Incidencias WARNING", ""]

    if warnings:
        for iss in warnings:
            lines += [
                f"### {iss.code}",
                "",
                f"- **Origen**: `{iss.source_block}`",
                f"- **Bloque afectado**: `{iss.target_block}`",
                f"- **Descripcion**: {iss.message}",
                f"- **Evidencia**: {', '.join(iss.evidence) or '—'}",
                "",
            ]
    else:
        lines.append("_Sin incidencias WARNING._")

    lines += ["", "## 5. Incidencias INFO", ""]

    if infos:
        for iss in infos:
            lines.append(f"- **{iss.code}**: {iss.message}")
    else:
        lines.append("_Sin incidencias INFO._")

    lines += ["", "## 6. Recomendaciones", ""]

    if result.status == "INCOHERENTE":
        lines.append(
            "El expediente presenta incoherencias entre bloques. "
            "Revisar los ERRORs indicados antes de continuar con la redaccion."
        )
    elif result.status == "CON_OBSERVACIONES":
        lines.append(
            "El expediente presenta observaciones de coherencia. "
            "Revisar los WARNINGs indicados y evaluar si requieren correccion."
        )
    else:
        lines.append(
            "No se detectaron incoherencias graves entre los bloques revisados."
        )

    lines += [
        "",
        "## 7. Advertencia de alcance",
        "",
        "Esta auditoria no corrige automaticamente el expediente y no declara "
        "aptitud administrativa.",
        "",
        "Los hallazgos son indicativos y deben ser revisados por el tecnico "
        "responsable del expediente.",
        "",
        "La clasificacion del expediente corresponde exclusivamente al organo ambiental.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_block_consistency_outputs
# ---------------------------------------------------------------------------


def write_block_consistency_outputs(
    result: BlockConsistencyResult,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Escribe JSON y MD del resultado de coherencia.

    Devuelve (json_path, md_path).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "block_consistency_result.json"
    md_path = out / "block_consistency_result.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        build_block_consistency_report_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
