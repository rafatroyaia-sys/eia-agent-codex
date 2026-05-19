"""
inventory_renderer -- IV-01
Renderiza objetos FactorInventory e InventorySummary como fichas Markdown.

No consulta fuentes externas.
No inventa datos.
No valora impactos.
No genera Fase 6.
No usa IA.

Depende exclusivamente de IV-00 (inventory_model.py).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.inventory_model import (
    FactorInventory,
    InventorySummary,
)

# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

# Terminos de valoracion de impacto prohibidos en fichas de inventario.
# Deteccion por raiz (stem) para capturar formas masculinas y femeninas,
# singular y plural: moderado/a/os/as, severo/a, critico/a.
# Normalizados sin tilde para capturar variantes graficas.
_IMPACT_DETECTION_STEMS: tuple[str, ...] = (
    "compatible",   # invariable en genero y numero
    "moderad",      # moderado, moderada, moderados, moderadas
    "sever",        # severo, severa, severos, severas
    "critic",       # critico, critica, criticos, criticas
)
_IMPACT_DISPLAY_TERMS: tuple[str, ...] = (
    "COMPATIBLE",
    "MODERADO",
    "SEVERO",
    "CRITICO",
)

_METHODOLOGICAL_NOTE: str = (
    "Esta ficha forma parte del inventario ambiental de gabinete. "
    "No constituye valoracion de impactos ni sustituye las comprobaciones "
    "de campo que resulten necesarias."
)

_SEMAPHORE_LABELS: dict[str, str] = {
    "VERDE": "VERDE",
    "VERDE_AMARILLO": "VERDE-AMARILLO",
    "AMARILLO": "AMARILLO",
    "ROJO_AMARILLO": "ROJO-AMARILLO",
    "ROJO": "ROJO",
    "NO_CONSTA": "NO CONSTA",
}

_CANONICAL_SEMAPHORE_ORDER: tuple[str, ...] = (
    "VERDE",
    "VERDE_AMARILLO",
    "AMARILLO",
    "ROJO_AMARILLO",
    "ROJO",
    "NO_CONSTA",
)


# ---------------------------------------------------------------------------
# InventoryRenderConfig
# ---------------------------------------------------------------------------

@dataclass
class InventoryRenderConfig:
    """Configuracion de renderizado de fichas de inventario."""

    include_header: bool = True
    include_gap_table: bool = True
    include_readiness_section: bool = True
    include_methodological_note: bool = True
    language: str = "es"

    def to_dict(self) -> dict:
        return {
            "include_header": self.include_header,
            "include_gap_table": self.include_gap_table,
            "include_readiness_section": self.include_readiness_section,
            "include_methodological_note": self.include_methodological_note,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InventoryRenderConfig":
        return cls(
            include_header=data.get("include_header", True),
            include_gap_table=data.get("include_gap_table", True),
            include_readiness_section=data.get("include_readiness_section", True),
            include_methodological_note=data.get("include_methodological_note", True),
            language=data.get("language", "es"),
        )


# ---------------------------------------------------------------------------
# InventoryRenderResult
# ---------------------------------------------------------------------------

@dataclass
class InventoryRenderResult:
    """Resultado del proceso de renderizado de ficheros de inventario."""

    factor_files: list[str] = field(default_factory=list)
    summary_file: Optional[str] = None
    index_file: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "factor_files": list(self.factor_files),
            "summary_file": self.summary_file,
            "index_file": self.index_file,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Renderizado: {len(self.factor_files)} fichas de factor generadas.",
        ]
        if self.summary_file:
            lines.append(f"  Resumen: {self.summary_file}")
        if self.index_file:
            lines.append(f"  Indice JSON: {self.index_file}")
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  NOTA: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    """Elimina diacriticos y tildes de un texto."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _semaphore_label(semaphore: str) -> str:
    return _SEMAPHORE_LABELS.get(semaphore, semaphore)


def _detect_impact_language(text: str) -> list[str]:
    """Detecta terminos de valoracion de impacto en el texto.

    Usa raices (stems) para capturar formas masculinas, femeninas y plurales.
    Devuelve los terminos de visualizacion canonicos (COMPATIBLE, MODERADO...).
    """
    normalized = _strip_accents(text.lower())
    return [
        display
        for stem, display in zip(_IMPACT_DETECTION_STEMS, _IMPACT_DISPLAY_TERMS)
        if stem in normalized
    ]


def safe_factor_filename(factor: FactorInventory) -> str:
    """Genera nombre de archivo seguro para la ficha de un factor.

    Ejemplo: FI-001 Clima -> FI-001_clima.md
             FI-015 Cambio climatico -> FI-015_cambio_climatico.md
    """
    name = factor.factor_name or factor.factor_id
    normalized = _strip_accents(name).lower()
    chars: list[str] = []
    for c in normalized:
        if c.isalnum() or c == "-":
            chars.append(c)
        elif c in (" ", "_"):
            chars.append("_")
        # descartar otros caracteres especiales
    name_safe = "".join(chars).strip("_")
    while "__" in name_safe:
        name_safe = name_safe.replace("__", "_")
    return f"{factor.factor_id}_{name_safe}.md"


# ---------------------------------------------------------------------------
# render_factor_inventory_markdown
# ---------------------------------------------------------------------------

def render_factor_inventory_markdown(
    factor: FactorInventory,
    config: Optional[InventoryRenderConfig] = None,
) -> str:
    """Renderiza un FactorInventory como markdown de ficha de inventario ambiental.

    No inventa datos. No eleva evidencia. No valora impactos.
    Si aparecen terminos de valoracion (COMPATIBLE/MODERADO/SEVERO/CRITICO)
    en description, warnings o notes, añade aviso de prudencia en seccion 8.
    """
    if config is None:
        config = InventoryRenderConfig()

    lines: list[str] = []

    # --- Cabecera ---
    if config.include_header:
        fname = factor.factor_name or factor.factor_id
        lines.append(f"# {factor.factor_id} -- {fname}")
        lines.append("")

    # Detectar lenguaje de impacto en todos los campos de texto del factor
    all_text_parts = [
        factor.description or "",
        factor.field_mode_justification or "",
        factor.semaphore_justification or "",
    ] + list(factor.warnings) + list(factor.notes)
    found_impact = _detect_impact_language(" ".join(all_text_parts))
    impact_prudence_warning: Optional[str] = None
    if found_impact:
        terms = ", ".join(found_impact).upper()
        impact_prudence_warning = (
            f"AVISO DE PRUDENCIA: Se han detectado terminos de valoracion de impacto "
            f"({terms}) en los campos de esta ficha. "
            f"Las fichas de inventario NO deben contener valoracion de impactos. "
            f"Revisar: COMPATIBLE / MODERADO / SEVERO / CRITICO no corresponden "
            f"al inventario ambiental."
        )

    # --- 1. Estado de la informacion ---
    lines.append("## 1. Estado de la informacion")
    lines.append("")
    lines.append(f"- **Estado de evidencia**: {factor.evidence_status}")
    lines.append(f"- **Modo de trabajo**: {factor.field_mode}")
    lines.append(f"- **Semaforo de inventario**: {_semaphore_label(factor.inventory_semaphore)}")
    ready_label = "Si" if factor.ready_for_impact_assessment else "No"
    lines.append(f"- **Preparado para valoracion de impactos**: {ready_label}")
    lines.append("")

    # --- 2. Descripcion del factor ---
    lines.append("## 2. Descripcion del factor")
    lines.append("")
    desc = (factor.description or "").strip()
    lines.append(desc if desc else "NO CONSTA INFORMACION DESCRIPTIVA SUFICIENTE.")
    lines.append("")

    # --- 3. Fuentes de datos ---
    lines.append("## 3. Fuentes de datos")
    lines.append("")
    if factor.data_sources:
        for src in factor.data_sources:
            lines.append(f"- {src}")
    else:
        lines.append("NO CONSTA FUENTE DOCUMENTAL ESPECIFICA.")
    lines.append("")

    # --- 4. Justificacion del modo de trabajo ---
    lines.append("## 4. Justificacion del modo de trabajo")
    lines.append("")
    jm = (factor.field_mode_justification or "").strip()
    lines.append(jm if jm else "NO CONSTA JUSTIFICACION ESPECIFICA.")
    lines.append("")

    # --- 5. Justificacion del semaforo ---
    lines.append("## 5. Justificacion del semaforo")
    lines.append("")
    js = (factor.semaphore_justification or "").strip()
    lines.append(js if js else "NO CONSTA JUSTIFICACION ESPECIFICA.")
    lines.append("")

    # --- 6. Gaps y limitaciones ---
    if config.include_gap_table:
        lines.append("## 6. Gaps y limitaciones")
        lines.append("")
        if factor.gaps:
            lines.append(
                "| Gap ID | Campo | Descripcion | Criticidad | Resolucion | Estado |"
            )
            lines.append(
                "|--------|-------|-------------|------------|------------|--------|"
            )
            for g in factor.gaps:
                # truncar descripcion larga y escapar pipes
                d = g.description[:80].replace("|", "/")
                if len(g.description) > 80:
                    d += "..."
                lines.append(
                    f"| {g.gap_id} | {g.field} | {d} "
                    f"| {g.criticality} | {g.resolution_mode} | {g.status} |"
                )
        else:
            lines.append(
                "No se han registrado gaps especificos para este factor."
            )
        lines.append("")

    # --- 7. Preparacion para Fase 6 ---
    if config.include_readiness_section:
        lines.append("## 7. Preparacion para Fase 6")
        lines.append("")
        if factor.ready_for_impact_assessment:
            lines.append(
                "Este factor esta LISTO para su uso en la valoracion de impactos (Fase 6)."
            )
        else:
            lines.append(
                "Este factor NO esta listo para la valoracion de impactos (Fase 6). "
                "Este factor no debe utilizarse para valoracion de impactos sin revision previa."
            )
        lines.append("")

    # --- 8. Notas y advertencias ---
    lines.append("## 8. Notas y advertencias")
    lines.append("")
    has_content = bool(impact_prudence_warning or factor.warnings or factor.notes)
    if impact_prudence_warning:
        lines.append(f"> **{impact_prudence_warning}**")
        lines.append("")
    for w in factor.warnings:
        lines.append(f"- AVISO: {w}")
    for n in factor.notes:
        lines.append(f"- NOTA: {n}")
    if not has_content:
        lines.append("Sin advertencias ni notas adicionales.")
    lines.append("")

    # --- Nota metodologica ---
    if config.include_methodological_note:
        lines.append("---")
        lines.append("")
        lines.append(f"*{_METHODOLOGICAL_NOTE}*")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# render_inventory_summary_markdown
# ---------------------------------------------------------------------------

def render_inventory_summary_markdown(
    summary: InventorySummary,
    config: Optional[InventoryRenderConfig] = None,
) -> str:
    """Renderiza un InventorySummary como markdown de resumen de inventario."""
    if config is None:
        config = InventoryRenderConfig()

    lines: list[str] = []

    lines.append("# Resumen del inventario ambiental")
    lines.append("")

    # --- 1. Expediente ---
    lines.append("## 1. Expediente")
    lines.append("")
    lines.append(f"- **ID de expediente**: {summary.expediente_id}")
    lines.append(f"- **Total de factores**: {summary.total_factors}/16")
    lines.append(f"- **Factores listos para Fase 6**: {summary.ready_count}/{summary.total_factors}")
    lines.append("")

    # --- 2. Estado general ---
    lines.append("## 2. Estado general")
    lines.append("")
    lines.append(f"- **Total de factores**: {summary.total_factors}")
    lines.append(f"- **Factores listos (ready)**: {summary.ready_count}")
    lines.append(f"- **Factores con campo necesario**: {summary.campo_necesario_count}")
    lines.append(f"- **Factores en semaforo ROJO**: {summary.rojo_count}")
    crits_label = "SI" if summary.has_critical_gaps else "NO"
    lines.append(f"- **Gaps criticos activos**: {crits_label}")
    all_ready_label = "SI" if summary.all_ready_for_phase6 else "NO"
    lines.append(f"- **all_ready_for_phase6**: {all_ready_label}")
    lines.append("")

    if not summary.all_ready_for_phase6:
        lines.append(
            "> **AVISO**: El inventario no debe avanzar a Fase 6 "
            "si all_ready_for_phase6 es False."
        )
        lines.append("")

    # --- 3. Tabla de factores ---
    lines.append("## 3. Tabla de factores")
    lines.append("")
    lines.append(
        "| Factor | Nombre | Tipo | Evidencia | Modo | Semaforo | Ready Fase 6 | Gaps criticos |"
    )
    lines.append(
        "|--------|--------|------|-----------|------|----------|--------------|---------------|"
    )
    for f in summary.factors:
        fname = f.factor_name or f.factor_id
        ftype = f.factor_type or "desconocido"
        sem = _semaphore_label(f.inventory_semaphore)
        ready = "Si" if f.ready_for_impact_assessment else "No"
        gaps_alta = f.gap_count_by_criticality().get("ALTA", 0)
        lines.append(
            f"| {f.factor_id} | {fname} | {ftype} | {f.evidence_status} "
            f"| {f.field_mode} | {sem} | {ready} | {gaps_alta} |"
        )
    lines.append("")

    # --- 4. Factores por semaforo ---
    lines.append("## 4. Factores por semaforo")
    lines.append("")
    by_semaphore = summary.factors_by_semaphore()
    for sem in _CANONICAL_SEMAPHORE_ORDER:
        fids = by_semaphore.get(sem, [])
        label = _semaphore_label(sem)
        count = len(fids)
        if fids:
            lines.append(f"- **{label}** ({count}): {', '.join(fids)}")
        else:
            lines.append(f"- **{label}** (0): ninguno")
    lines.append("")

    # --- 5. Factores que requieren trabajo de campo ---
    lines.append("## 5. Factores que requieren trabajo de campo")
    lines.append("")
    campo_ids = summary.factors_needing_field_work()
    if campo_ids:
        lines.append(
            "Los siguientes factores tienen asignado modo "
            "CAMPO_RECOMENDADO o CAMPO_NECESARIO:"
        )
        lines.append("")
        factor_map = {f.factor_id: f for f in summary.factors}
        for fid in campo_ids:
            f_obj = factor_map.get(fid)
            fname_c = f_obj.factor_name if f_obj else fid
            mode = f_obj.field_mode if f_obj else "?"
            lines.append(f"- **{fid}** ({fname_c}): {mode}")
    else:
        lines.append(
            "Ningun factor tiene asignado modo de campo "
            "(CAMPO_RECOMENDADO o CAMPO_NECESARIO)."
        )
    lines.append("")

    # --- 6. Advertencias y notas ---
    lines.append("## 6. Advertencias y notas")
    lines.append("")
    if summary.warnings:
        for w in summary.warnings:
            lines.append(f"- AVISO: {w}")
    if summary.notes:
        for n in summary.notes:
            lines.append(f"- NOTA: {n}")
    if not summary.warnings and not summary.notes:
        lines.append("Sin advertencias ni notas adicionales.")
    lines.append("")

    # Nota de bloqueo
    if not summary.all_ready_for_phase6:
        lines.append("---")
        lines.append("")
        lines.append(
            "*El inventario no debe avanzar a Fase 6 "
            "si all_ready_for_phase6 es False.*"
        )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_inventory_index
# ---------------------------------------------------------------------------

def build_inventory_index(
    summary: InventorySummary,
    factor_filenames: Optional[dict[str, str]] = None,
) -> dict:
    """Construye el diccionario del indice de inventario (JSON serializable).

    Args:
        summary: InventorySummary del expediente.
        factor_filenames: mapa factor_id -> nombre de archivo (opcional).

    Returns:
        Dict JSON serializable con metadatos e indice de factores.
    """
    if factor_filenames is None:
        factor_filenames = {}

    factors_list = [
        {
            "factor_id": f.factor_id,
            "factor_name": f.factor_name or f.factor_id,
            "semaphore": f.inventory_semaphore,
            "ready": f.ready_for_impact_assessment,
            "filename": factor_filenames.get(f.factor_id),
        }
        for f in summary.factors
    ]

    return {
        "expediente_id": summary.expediente_id,
        "total_factors": summary.total_factors,
        "ready_count": summary.ready_count,
        "all_ready_for_phase6": summary.all_ready_for_phase6,
        "factors": factors_list,
    }


# ---------------------------------------------------------------------------
# write_inventory_markdown_files
# ---------------------------------------------------------------------------

def write_inventory_markdown_files(
    summary: InventorySummary,
    output_dir: "str | Path",
    config: Optional[InventoryRenderConfig] = None,
) -> InventoryRenderResult:
    """Escribe fichas markdown del inventario ambiental en output_dir.

    Crea output_dir si no existe.
    Escribe una ficha .md por factor, resumen_inventario.md e indice_inventario.json.
    No escribe fuera de output_dir.

    Returns:
        InventoryRenderResult con rutas absolutas de los archivos generados.
    """
    if config is None:
        config = InventoryRenderConfig()

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    result = InventoryRenderResult()
    factor_filenames: dict[str, str] = {}

    # Ficha por factor
    for factor in summary.factors:
        filename = safe_factor_filename(factor)
        filepath = out / filename
        md = render_factor_inventory_markdown(factor, config)
        filepath.write_text(md, encoding="utf-8")
        result.factor_files.append(str(filepath))
        factor_filenames[factor.factor_id] = filename

    # Resumen
    summary_path = out / "resumen_inventario.md"
    summary_md = render_inventory_summary_markdown(summary, config)
    summary_path.write_text(summary_md, encoding="utf-8")
    result.summary_file = str(summary_path)

    # Indice JSON
    index_path = out / "indice_inventario.json"
    index_data = build_inventory_index(summary, factor_filenames)
    index_path.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result.index_file = str(index_path)

    result.notes.append(
        f"Escritos {len(result.factor_files)} fichas de factor + "
        f"resumen_inventario.md + indice_inventario.json en: {out}"
    )

    return result
