"""
block_a_gap_visibility -- OB-04
Verifica que los gaps de criticidad ALTA relacionados con identidad/objeto
evaluado aparecen mencionados explícitamente en A.1 o A.3.1 del Bloque A.

No usa IA. No redacta. No modifica bloques. No resuelve gaps.
No escribe nada.

Uso:
    from eia_agent.core.block_a_gap_visibility import check_block_a_gap_visibility

    result = check_block_a_gap_visibility(bloque_a_text, gaps_data)
    print(result.summary())
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Palabras clave que identifican gaps de identidad/objeto evaluado.
# Heurística determinista; no es exhaustiva.
_IDENTITY_KEYWORDS: frozenset[str] = frozenset({
    "titular",
    "promotor",
    "referencia catastral",
    "catastral",
    "coordenada",
    "ubicacion",
    "ubicación",
    "emplazamiento",
    "uso catastral",
    "uso declarado",
    "operacion incluida",
    "operacion excluida",
    "operación incluida",
    "operación excluida",
    "objeto evaluado",
    "delimitacion",
    "delimitación",
    "nave",
    "parcela",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GapVisibilityIssue:
    """Incidencia de visibilidad de un gap en el Bloque A."""
    severity: str                    # ERROR / WARNING / INFO
    code: str
    gap_id: str | None
    message: str
    section: str | None = None
    recommendation: str | None = None


@dataclass
class GapVisibilityResult:
    """Resultado de la verificación de visibilidad de gaps en Bloque A."""
    passed: bool
    checked_gaps: list[str]
    visible_gaps: list[str]
    missing_gaps: list[str]
    issues: list[GapVisibilityIssue] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_blocked(self) -> bool:
        return not self.passed

    def summary(self) -> str:
        status = "OK" if self.passed else "INCOMPLETO"
        lines = [
            f"Visibilidad gaps en Bloque A: {status}",
            f"  Revisados: {len(self.checked_gaps)} | "
            f"Visibles en A.1/A.3.1: {len(self.visible_gaps)} | "
            f"Sin visibilidad plena: {len(self.missing_gaps)}",
            f"  Errores: {self.error_count()} | "
            f"Avisos: {self.warning_count()} | "
            f"Info: {self.info_count()}",
        ]
        for issue in self.issues:
            gid = f" [{issue.gap_id}]" if issue.gap_id else ""
            sec = f" en {issue.section}" if issue.section else ""
            lines.append(f"  [{issue.severity}]{gid} {issue.code}: {issue.message}{sec}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def normalize_criticality(value: str) -> str:
    """Normaliza valor de criticidad a forma canónica.

    ALTA / CRÍTICA / CRITICA / BLOQUEANTE / CRITICAL → "ALTA"
    MEDIA / MEDIUM → "MEDIA"
    BAJA / LOW → "BAJA"
    Otros → valor en mayúsculas.
    """
    v = value.strip().upper().replace("Í", "I").replace("Á", "A")
    if v in {"ALTA", "CRITICA", "BLOQUEANTE", "CRITICAL"}:
        return "ALTA"
    if v in {"MEDIA", "MEDIUM"}:
        return "MEDIA"
    if v in {"BAJA", "LOW"}:
        return "BAJA"
    return v


def is_identity_related_gap(item: dict) -> bool:
    """Determina si el gap afecta a identidad/objeto evaluado.

    Heurística determinista: busca palabras clave en todos los valores
    de tipo str del dict (descripcion, campo, categoria, tipo, notes...).
    """
    parts: list[str] = []
    for v in item.values():
        if isinstance(v, str):
            parts.append(v.lower())
        elif isinstance(v, list):
            for elem in v:
                if isinstance(elem, str):
                    parts.append(elem.lower())
    combined = " ".join(parts)
    return any(kw in combined for kw in _IDENTITY_KEYWORDS)


def extract_markdown_section(markdown_text: str, heading: str) -> str:
    """Extrae el contenido de una sección por su heading markdown.

    Args:
        markdown_text: Texto markdown completo.
        heading:       Heading a buscar, incluyendo los # (e.g. "## A.1",
                       "### A.3.1"). Puede tener o no título tras el código.

    Returns:
        Texto de la sección (sin el heading), o "" si no existe.
    """
    heading = heading.strip()
    level = len(heading) - len(heading.lstrip("#"))

    lines = markdown_text.splitlines()
    start_idx: int | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if (stripped == heading
                or stripped.startswith(heading + " ")
                or stripped.startswith(heading + "\t")):
            start_idx = i + 1
            break

    if start_idx is None:
        return ""

    # Acumular líneas hasta el siguiente heading de nivel igual o superior
    result_lines: list[str] = []
    next_heading_re = re.compile(r'^#{1,' + str(level) + r'}\s')
    for line in lines[start_idx:]:
        if next_heading_re.match(line):
            break
        result_lines.append(line)

    return "\n".join(result_lines)


def load_gaps_json(path: "str | Path") -> list[dict]:
    """Carga inferencias_y_gaps.json y lo devuelve como lista de dicts.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError:        si el JSON es inválido o no es una lista.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(
            f"Se esperaba lista en {path}, "
            f"se obtuvo {type(data).__name__}"
        )
    return data


def _get_criticality(item: dict) -> str:
    for key in ("criticidad", "severity", "nivel", "prioridad"):
        if key in item:
            return normalize_criticality(str(item[key]))
    return ""


def _get_gap_code(item: dict) -> str | None:
    for key in ("id", "codigo", "code"):
        v = item.get(key)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def check_block_a_gap_visibility(
    block_a_md: str,
    gaps_data: list[dict],
    only_high: bool = True,
) -> GapVisibilityResult:
    """Verifica que los gaps de identidad/ALTA sean visibles en A.1 o A.3.1.

    Args:
        block_a_md: Texto markdown del Bloque A completo.
        gaps_data:  Lista de dicts de inferencias_y_gaps.json.
        only_high:  True (default) = solo revisar gaps de criticidad ALTA.
                    False = revisar todos los gaps de identidad.

    Returns:
        GapVisibilityResult. passed=True si no hay ningún ERROR.
    """
    a1_text = extract_markdown_section(block_a_md, "## A.1")
    a31_text = extract_markdown_section(block_a_md, "### A.3.1")
    valid_sections_text = a1_text + "\n" + a31_text

    checked_gaps: list[str] = []
    visible_gaps: list[str] = []
    missing_gaps: list[str] = []
    issues: list[GapVisibilityIssue] = []

    for item in gaps_data:
        # Filtro por criticidad
        if only_high and _get_criticality(item) != "ALTA":
            continue

        # Filtro por identidad/objeto evaluado
        if not is_identity_related_gap(item):
            continue

        gap_code = _get_gap_code(item)
        if not gap_code:
            continue

        checked_gaps.append(gap_code)

        if gap_code in valid_sections_text:
            # Visible en sección válida (A.1 o A.3.1)
            visible_gaps.append(gap_code)
            issues.append(GapVisibilityIssue(
                severity="INFO",
                code="OB04-I002",
                gap_id=gap_code,
                message=f"Gap {gap_code} mencionado correctamente en A.1 o A.3.1.",
                section="A.1/A.3.1",
            ))
        elif gap_code in block_a_md:
            # Visible en otro lugar del Bloque A, pero no en sección válida
            missing_gaps.append(gap_code)
            issues.append(GapVisibilityIssue(
                severity="WARNING",
                code="OB04-W001",
                gap_id=gap_code,
                message=(
                    f"Gap {gap_code} aparece en Bloque A pero no en A.1 ni A.3.1."
                ),
                section="otro",
                recommendation=(
                    "Mover la mención del gap a la sección A.1 o A.3.1 "
                    "para cumplir el requisito de visibilidad."
                ),
            ))
        else:
            # No visible en ninguna parte del Bloque A
            missing_gaps.append(gap_code)
            issues.append(GapVisibilityIssue(
                severity="ERROR",
                code="OB04-E001",
                gap_id=gap_code,
                message=(
                    f"Gap {gap_code} de criticidad alta no mencionado en A.1 "
                    f"ni en A.3.1 del Bloque A."
                ),
                section=None,
                recommendation=(
                    "Añadir mención explícita del código del gap en la sección A.1 "
                    "o A.3.1 del Bloque A."
                ),
            ))

    if not checked_gaps:
        issues.append(GapVisibilityIssue(
            severity="INFO",
            code="OB04-I001",
            gap_id=None,
            message=(
                "No se encontraron gaps de identidad/criticidad alta que verificar."
            ),
        ))

    passed = all(i.severity != "ERROR" for i in issues)

    return GapVisibilityResult(
        passed=passed,
        checked_gaps=checked_gaps,
        visible_gaps=visible_gaps,
        missing_gaps=missing_gaps,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Función de conveniencia: carga desde archivos
# ---------------------------------------------------------------------------

def check_block_a_gap_visibility_from_files(
    block_a_path: "str | Path",
    gaps_json_path: "str | Path",
    only_high: bool = True,
) -> GapVisibilityResult:
    """Carga Bloque A y gaps desde disco y evalúa visibilidad.

    No escribe nada. Lanza FileNotFoundError si algún archivo no existe.
    """
    block_a_path = Path(block_a_path)
    if not block_a_path.exists():
        raise FileNotFoundError(f"Bloque A no encontrado: {block_a_path}")
    block_a_md = block_a_path.read_text(encoding="utf-8")
    gaps_data = load_gaps_json(gaps_json_path)
    return check_block_a_gap_visibility(block_a_md, gaps_data, only_high=only_high)
